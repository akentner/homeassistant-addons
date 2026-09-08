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
	"fmt"
	"log/slog"
	"os"
	"os/exec"
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
//
// Path and Env are not in the plan's published interface sketch but
// are required by its own DefaultExec body (`exec.CommandContext(ctx,
// spec.Path, spec.Args...)` / `cmd.Env = spec.Env`): the resolved tofu
// binary and the backend credential environment have to reach the
// process somehow, and threading them through the spec keeps ExecFunc
// a pure function of its argument rather than a closure over Queue.
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

// Deps is the constructor input for New. 17-07 fills it from Options.
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

// Request is one submission from the HTTP layer (17-06).
type Request struct {
	Repo string
	Dir  string
	Kind contract.RunKind
}

// ErrCapacityExhausted is returned by Submit when every
// max_parallel_jobs slot is occupied. CONTEXT D-06: saturation is
// refused, never queued, so 17-06 can map it to HTTP 503 +
// Retry-After: 30 with error_code apply_capacity_exhausted.
var ErrCapacityExhausted = errors.New("jobq: max_parallel_jobs saturated")

// Queue owns the two admission gates and the worker goroutines.
type Queue struct {
	store   *runs.Store
	git     *git.Manager
	backend statebackend.Backend

	// sem is the D-04 global semaphore. Its capacity IS
	// max_parallel_jobs; a send that would block means saturation.
	sem chan struct{}

	// locksMu guards locks. A plain map behind an RWMutex beats
	// sync.Map here for the same reason terraform-bridge's
	// internal/mutex documents: sync.Map has no Clear before process
	// exit, so entries leak. Repo names come from a bounded Options
	// list, so this map cannot grow unboundedly either way.
	locksMu sync.RWMutex
	locks   map[string]*sync.Mutex

	// pending counts admitted-but-unfinished jobs per repo: the one
	// executing plus the ones waiting on that repo's mutex. It is the
	// per-repo admission bound that replaces "a waiter holds a global
	// slot" — see work for why that mattered. maxPending is
	// max_parallel_jobs, so the refusal threshold for a single repo is
	// unchanged.
	pendingMu  sync.Mutex
	pending    map[string]int
	maxPending int

	wg sync.WaitGroup

	exec         ExecFunc
	now          func() time.Time
	tofuPath     string
	applyTimeout time.Duration
}

// New validates deps, applies the D-04/D-15 defaults and returns a
// ready Queue.
func New(d Deps) (*Queue, error) {
	if d.Store == nil {
		return nil, errors.New("jobq: New requires a runs.Store")
	}
	if d.Git == nil {
		return nil, errors.New("jobq: New requires a git.Manager")
	}

	maxParallel := d.MaxParallel
	if maxParallel <= 0 {
		maxParallel = defaultMaxParallel
	}
	if maxParallel > maxMaxParallel {
		maxParallel = maxMaxParallel
	}
	applyTimeout := d.ApplyTimeout
	if applyTimeout <= 0 {
		applyTimeout = defaultApplyTimeout
	}
	execFn := d.Exec
	if execFn == nil {
		execFn = DefaultExec
	}
	now := d.Now
	if now == nil {
		now = time.Now
	}

	tofuPath := d.TofuPath
	if tofuPath == "" {
		// A failed lookup is deliberately NOT fatal at construction.
		// The add-on must still start so GET /healthz can report
		// tofu_on_path=false — the real cause — instead of the
		// container crash-looping with no diagnosable surface. Submit
		// turns the empty path into run_tofu_not_found per request.
		if resolved, err := exec.LookPath("tofu"); err == nil {
			tofuPath = resolved
		}
	}

	return &Queue{
		store:        d.Store,
		git:          d.Git,
		backend:      d.Backend,
		sem:          make(chan struct{}, maxParallel),
		locks:        make(map[string]*sync.Mutex),
		pending:      make(map[string]int),
		maxPending:   maxParallel,
		exec:         execFn,
		now:          now,
		tofuPath:     tofuPath,
		applyTimeout: applyTimeout,
	}, nil
}

// lockFor returns the per-repo mutex, creating it on first reference
// (D-05 lazy population). Read-then-upgrade so concurrent lookups for
// distinct repos do not serialize on the map itself.
func (q *Queue) lockFor(repo string) *sync.Mutex {
	q.locksMu.RLock()
	lock, ok := q.locks[repo]
	q.locksMu.RUnlock()
	if ok {
		return lock
	}

	q.locksMu.Lock()
	// Re-check under the write lock — a concurrent caller may have
	// raced us to create the entry.
	lock, ok = q.locks[repo]
	if !ok {
		lock = &sync.Mutex{}
		q.locks[repo] = lock
	}
	q.locksMu.Unlock()
	return lock
}

// Submit admits one job and returns its run id. It never blocks: the
// tofu process runs in a worker goroutine, so RUN-02/RUN-03 can answer
// 202 + Location immediately.
//
// ORDER MATTERS. Every rejection in steps 1-4 happens BEFORE the
// semaphore acquire and before any run directory exists, so a stream
// of malformed requests can neither consume capacity nor litter
// /data/runs with stillborn runs.
func (q *Queue) Submit(req Request) (string, error) {
	// 1. Unknown repo (D-19 run_unknown_repo).
	cfg, ok := q.git.Repo(req.Repo)
	if !ok {
		return "", &git.Error{
			Code:    contract.ErrCodeRunUnknownRepo,
			Message: fmt.Sprintf("unknown repo %s", req.Repo),
			Hint:    "add it to the `repos` Options list",
		}
	}

	// 2. dir shape (D-21/D-22). The cleaned value is the ONLY string
	// that may later be joined onto the repo working tree.
	cleanDir, err := runs.ValidateDir(req.Dir)
	if err != nil {
		return "", &git.Error{
			Code:    contract.ErrCodeRunInvalidDir,
			Message: runs.InvalidDirMessage,
			Hint:    "set `dir` to a path relative to the repo root, or omit it for the repo root",
		}
	}

	// 3. Working tree present. EnsureCloned already returns the typed
	// *git.Error carrying contract.ErrCodeGitCloneMissing (D-14), so
	// jobq propagates git's error verbatim rather than re-deriving the
	// code — one owner per taxonomy entry.
	if err := q.git.EnsureCloned(req.Repo); err != nil {
		return "", err
	}

	// 4. tofu binary resolvable. See New for why this is a per-request
	// rejection rather than a startup failure.
	if q.tofuPath == "" {
		return "", &git.Error{
			Code:    contract.ErrCodeRunTofuNotFound,
			Message: "the tofu binary could not be resolved on PATH",
			Hint:    "the tofu binary is missing from the image — check GET /healthz",
		}
	}

	// 5. Global slot, NON-BLOCKING (D-06). A full semaphore is a
	// refusal, not a wait: an invisible queue would hide back-pressure
	// from the operator and let request timeouts pile up upstream.
	//
	// The slot admitted here covers the SUBMISSION only. work() hands
	// it straight back before it waits on the repo mutex and takes a
	// fresh one for the execution window, so capacity means "tofu
	// processes running", not "jobs that exist" (WR-08).
	select {
	case q.sem <- struct{}{}:
	default:
		return "", ErrCapacityExhausted
	}

	// 6. Per-repo admission bound. Because a waiter no longer holds a
	// global slot, something else has to stop one repo from accruing
	// unbounded goroutines and run directories. maxPending equals
	// max_parallel_jobs, so a single repo still refuses the same
	// submission it refused before — the difference is that OTHER
	// repos are no longer refused with it.
	if !q.reservePending(cfg.Name) {
		<-q.sem
		return "", ErrCapacityExhausted
	}
	releaseAdmission := func() {
		q.releasePending(cfg.Name)
		<-q.sem
	}

	runID, err := runs.NewRunID()
	if err != nil {
		releaseAdmission()
		return "", fmt.Errorf("jobq: generate run id: %w", err)
	}

	if err := q.store.Create(runs.Meta{
		RunID:     runID,
		Repo:      req.Repo,
		Dir:       cleanDir,
		Kind:      req.Kind,
		Status:    contract.RunStatusQueued,
		StartedAt: q.now().UTC(),
	}); err != nil {
		releaseAdmission()
		// Create does MkdirAll and THEN writes meta.json, so a
		// writeMeta failure — a full disk, precisely when this matters
		// — leaves a meta-less directory behind. Retention can only
		// age a run by its metadata, so that directory would be
		// permanent garbage under /data/runs.
		if dir := q.store.Dir(runID); dir != "" {
			if rmErr := os.RemoveAll(dir); rmErr != nil {
				slog.Warn("jobq.stillborn_run_dir_cleanup_failed",
					"run_id", runID, "err", rmErr.Error())
			}
		}
		return "", fmt.Errorf("jobq: create run: %w", err)
	}

	q.wg.Add(1)
	go q.work(runID, cfg.Name, cleanDir, req.Kind)
	return runID, nil
}

// work is the worker goroutine. Its release discipline IS the RUN-06
// guarantee: the repo mutex, the per-repo admission reservation and
// the global slot are given back on every exit path — success,
// non-zero exit, timeout, store failure, and a recovered panic.
//
// ORDER: the admission slot Submit took is released BEFORE the wait on
// the repo mutex, and a fresh slot is taken after the mutex is held.
//
// Holding one slot across the wait made a same-repo waiter consume
// capacity for the entire wait — bounded only by apply_timeout, 60
// minutes by default. With max_parallel_jobs at its default of 4, four
// queued applies against ONE repo pinned the whole runner: every other
// repo's /v1/plan got 503 apply_capacity_exhausted while three of
// those four slots had no tofu process behind them at all. That
// contradicts D-06's purpose, which is for saturation to mean "the
// runner is busy".
//
// Deadlock is not possible in the new order: a slot is only ever held
// by a job that already owns its repo mutex and is executing, and
// every such job finishes or times out.
//
// The recover defer is registered BEFORE lock.Lock() so a panic
// raised while holding the mutex is still recovered.
func (q *Queue) work(runID, repo, cleanDir string, kind contract.RunKind) {
	defer q.wg.Done()
	defer q.releasePending(repo)
	defer func() {
		if r := recover(); r != nil {
			// A panic in exec or in the store must not wedge the repo
			// mutex or leak a slot. Record the run as failed and let
			// the deferred unlock and slot release do their job.
			slog.Error("jobq.panic", "run_id", runID, "repo", repo, "panic", fmt.Sprint(r))
			q.finish(runID, ExecResult{ExitCode: -1}, kind, "", errors.New("panic"))
		}
	}()

	// Hand the admission slot back: waiting on a repo mutex is not
	// work, and it must not look like capacity to another repo.
	<-q.sem

	lock := q.lockFor(repo)
	// RUN-06 normal case: serialize-and-wait. The bound exists only so
	// a wedged apply cannot pin a repo forever; see acquire.
	if !acquire(lock, q.applyTimeout) {
		q.fail(runID, contract.ErrCodeApplyAlreadyRunning,
			fmt.Sprintf("another job for repo %s held the serialization lock for longer than %s", repo, q.applyTimeout))
		return
	}
	defer lock.Unlock()

	// The execution window is the only thing max_parallel_jobs bounds.
	// This wait is short by construction: every holder is a running
	// job, and each one is capped by apply_timeout.
	if !acquireSlot(q.sem, q.applyTimeout) {
		q.fail(runID, contract.ErrCodeApplyCapacityExhausted,
			fmt.Sprintf("no execution slot became free for repo %s within %s", repo, q.applyTimeout))
		return
	}
	defer func() { <-q.sem }()

	if _, err := q.store.Update(runID, func(m *runs.Meta) error {
		m.Status = contract.RunStatusRunning
		// StartedAt is refreshed to the ACTUAL start: for a job that
		// waited on the repo mutex the queued timestamp would make the
		// run look far slower than tofu actually was.
		m.StartedAt = q.now().UTC()
		return nil
	}); err != nil {
		// Returning here without a terminal state left the run
		// `queued` forever — and Rotate skips queued runs, so the
		// directory was never reclaimed either. The operator saw a job
		// that never starts and never explains itself.
		slog.Error("jobq.status_update_failed", "run_id", runID, "status", "running", "err", err.Error())
		q.fail(runID, contract.ErrCodeApplyFailed, "the run could not be marked running")
		return
	}

	w, err := q.store.OpenOutput(runID)
	if err != nil {
		slog.Error("jobq.output_open_failed", "run_id", runID, "err", err.Error())
		q.fail(runID, contract.ErrCodeApplyFailed, "the run output log could not be opened")
		return
	}
	defer func() { _ = w.Close() }()

	res, planFile, runErr := q.runJob(runID, repo, cleanDir, kind, w)
	q.finish(runID, res, kind, planFile, runErr)
}

// reservePending takes one per-repo admission reservation, reporting
// whether it won. A full repo is refused, never queued — the same D-06
// posture the global semaphore has.
func (q *Queue) reservePending(repo string) bool {
	q.pendingMu.Lock()
	defer q.pendingMu.Unlock()
	if q.pending[repo] >= q.maxPending {
		return false
	}
	q.pending[repo]++
	return true
}

// releasePending gives one reservation back. The map entry is deleted
// at zero so the map stays the size of the ACTIVE repo set.
func (q *Queue) releasePending(repo string) {
	q.pendingMu.Lock()
	defer q.pendingMu.Unlock()
	if q.pending[repo] <= 1 {
		delete(q.pending, repo)
		return
	}
	q.pending[repo]--
}

// acquireSlot blocks until a semaphore slot is free or timeout
// elapses, reporting whether it won. Unlike the admission acquire in
// Submit this one WAITS: the caller already holds its repo mutex, so
// refusing here would fail a job the runner has already accepted.
func acquireSlot(sem chan struct{}, timeout time.Duration) bool {
	timer := time.NewTimer(timeout)
	defer timer.Stop()
	select {
	case sem <- struct{}{}:
		return true
	case <-timer.C:
		return false
	}
}

// acquire blocks until lock is held or timeout elapses, reporting
// whether it won. sync.Mutex has no deadline, so the wait runs in a
// goroutine and the caller selects on a timer — the terraform-bridge
// internal/mutex pattern.
//
// On expiry the acquisition is handed off: a second goroutine waits for
// the (eventual) lock and immediately releases it. Without that
// hand-off the abandoned Lock() would succeed with nobody left to
// Unlock, permanently wedging the repo — the exact failure this whole
// file exists to prevent.
func acquire(lock *sync.Mutex, timeout time.Duration) bool {
	acquired := make(chan struct{}, 1)
	go func() {
		lock.Lock()
		acquired <- struct{}{}
	}()

	timer := time.NewTimer(timeout)
	defer timer.Stop()

	select {
	case <-acquired:
		return true
	case <-timer.C:
		go func() {
			<-acquired
			lock.Unlock()
		}()
		return false
	}
}

// finish writes the terminal state for runID.
func (q *Queue) finish(runID string, res ExecResult, kind contract.RunKind, planFile string, runErr error) {
	exitCode := res.ExitCode
	status := contract.RunStatusSucceeded
	errorCode := ""

	switch {
	case res.TimedOut:
		// D-16: a timed-out run is failed, never left running. The
		// plan and apply paths report distinct codes (D-20 additive).
		status = contract.RunStatusFailed
		errorCode = contract.ErrCodeApplyTimeout
		if kind == contract.RunKindPlan {
			errorCode = contract.ErrCodePlanTimeout
		}
	case runErr != nil:
		// The process could not be started at all, or a panic was
		// recovered. Either way there is no tofu exit code to report.
		status = contract.RunStatusFailed
		errorCode = contract.ErrCodeApplyFailed
	case exitCode != 0:
		status = contract.RunStatusFailed
		errorCode = contract.ErrCodeApplyFailed
	}

	finishedAt := q.now().UTC()
	if _, err := q.store.Update(runID, func(m *runs.Meta) error {
		m.Status = status
		m.ExitCode = &exitCode
		m.ErrorCode = errorCode
		m.FinishedAt = &finishedAt
		if status == contract.RunStatusSucceeded && kind == contract.RunKindPlan {
			m.PlanFile = planFile
		}
		return nil
	}); err != nil {
		slog.Error("jobq.terminal_update_failed", "run_id", runID, "status", string(status), "err", err.Error())
	}
}

// fail records a terminal failure that never reached a tofu process, so
// there is no exit code to report.
func (q *Queue) fail(runID, errorCode, message string) {
	finishedAt := q.now().UTC()
	if _, err := q.store.Update(runID, func(m *runs.Meta) error {
		m.Status = contract.RunStatusFailed
		m.ErrorCode = errorCode
		m.FinishedAt = &finishedAt
		return nil
	}); err != nil {
		slog.Error("jobq.fail_update_failed", "run_id", runID, "error_code", errorCode, "err", err.Error())
		return
	}
	slog.Warn("jobq.run_failed", "run_id", runID, "error_code", errorCode, "message", message)
}

// Drain waits for every in-flight job to finish, or returns ctx.Err()
// when the deadline passes first. cmd/runner/signals.go's 30s SIGTERM
// window calls this (wired in 17-07).
func (q *Queue) Drain(ctx context.Context) error {
	done := make(chan struct{})
	go func() {
		q.wg.Wait()
		close(done)
	}()
	select {
	case <-done:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}
