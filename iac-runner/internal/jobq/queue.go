// Package jobq executes OpenTofu plan and apply jobs in the
// background and is the only place in the runner that starts a
// process on behalf of an HTTP request.
//
// Two independent admission gates, per CONTEXT D-04..D-06:
//
//  1. A global semaphore of max_parallel_jobs slots, acquired
//     NON-BLOCKING. A full semaphore means the runner refuses the
//     submission (D-06) so back-pressure is visible to the
//     operator as 503 + Retry-After instead of an invisible queue.
//
//  2. A per-repo mutex, acquired BLOCKING inside the worker
//     goroutine. RUN-06 requires two applies on the same repo to
//     serialize while the second one still gets its 202 + run id
//     immediately, so the wait happens after the response, not
//     before it. Cross-repo jobs never contend.
//
// The mutex is in-process only (D-05): a restart mid-apply does not
// resume anything, and internal/runs' boot sweep marks the orphan
// interrupted (D-02).
package jobq

import (
	"context"
	"errors"
	"sync"
	"time"

	"iac-runner/internal/contract"
	"iac-runner/internal/git"
	"iac-runner/internal/runs"
	"iac-runner/internal/statebackend"
)

// Admission bounds. defaultMaxParallel and maxMaxParallel mirror the
// D-04 `max_parallel_jobs` schema (default 4, range 1..32) so a
// zero-value Deps in a test is still sane and a hand-edited
// /data/options.json cannot ask for unbounded concurrency.
// defaultApplyTimeout mirrors the D-15 `apply_timeout_minutes`
// default of 60.
const (
	defaultMaxParallel  = 4
	maxMaxParallel      = 32
	defaultApplyTimeout = 60 * time.Minute
)

// ExecFunc runs one command and reports its outcome. Production uses
// DefaultExec (os/exec with the D-16 kill-chain); tests inject a fake
// so admission control, serialization and the run lifecycle are
// verifiable with no tofu binary and no real repository.
type ExecFunc func(ctx context.Context, spec ExecSpec) (ExecResult, error)

// ExecSpec is one command invocation.
type ExecSpec struct {
	Path    string
	WorkDir string
	Args    []string
	Env     []string
	Stdout  func(line string)
	Stderr  func(line string)
}

// ExecResult is one command's outcome. A non-zero ExitCode is data,
// not a Go error; the error return of an ExecFunc is reserved for
// "could not start the process at all".
type ExecResult struct {
	ExitCode int
	TimedOut bool
}

// Deps is the constructor input for New.
type Deps struct {
	Store        *runs.Store
	Git          *git.Manager
	Backend      statebackend.Backend
	MaxParallel  int
	ApplyTimeout time.Duration
	Exec         ExecFunc         // nil -> DefaultExec
	Now          func() time.Time // nil -> time.Now
	TofuPath     string           // "" -> resolved via exec.LookPath("tofu")
}

// Request is one submission from the HTTP layer.
type Request struct {
	Repo string
	Dir  string
	Kind contract.RunKind
}

// ErrCapacityExhausted is returned by Submit when every
// max_parallel_jobs slot is occupied. CONTEXT D-06: saturation is
// refused, never queued, so 17-06 can map it to HTTP 503 +
// Retry-After: 30.
var ErrCapacityExhausted = errors.New("jobq: max_parallel_jobs saturated")

// Queue owns the two admission gates and the worker goroutines.
type Queue struct {
	store   *runs.Store
	git     *git.Manager
	backend statebackend.Backend

	sem chan struct{}

	locksMu sync.RWMutex
	locks   map[string]*sync.Mutex

	wg sync.WaitGroup

	exec         ExecFunc
	now          func() time.Time
	tofuPath     string
	applyTimeout time.Duration
}

// New validates deps and returns a ready Queue.
func New(d Deps) (*Queue, error) {
	if d.Store == nil {
		return nil, errors.New("jobq: New requires a runs.Store")
	}
	if d.Git == nil {
		return nil, errors.New("jobq: New requires a git.Manager")
	}
	return &Queue{
		store:        d.Store,
		git:          d.Git,
		backend:      d.Backend,
		sem:          make(chan struct{}, 1),
		locks:        make(map[string]*sync.Mutex),
		exec:         d.Exec,
		now:          time.Now,
		tofuPath:     d.TofuPath,
		applyTimeout: d.ApplyTimeout,
	}, nil
}

// lockFor returns the per-repo mutex, creating it on first reference.
func (q *Queue) lockFor(repo string) *sync.Mutex {
	q.locksMu.Lock()
	defer q.locksMu.Unlock()
	lock, ok := q.locks[repo]
	if !ok {
		lock = &sync.Mutex{}
		q.locks[repo] = lock
	}
	return lock
}

// Submit admits one job and returns its run id.
func (q *Queue) Submit(req Request) (string, error) {
	return "", errors.New("jobq: Submit not implemented")
}

// Drain waits for every in-flight job to finish.
func (q *Queue) Drain(ctx context.Context) error {
	return nil
}

// DefaultExec is the production os/exec implementation. Task 2
// replaces this placeholder with the real SIGTERM->SIGKILL kill-chain
// in exec.go.
func DefaultExec(ctx context.Context, spec ExecSpec) (ExecResult, error) {
	return ExecResult{}, errors.New("jobq: DefaultExec not implemented")
}
