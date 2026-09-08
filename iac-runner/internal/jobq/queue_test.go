package jobq

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"iac-runner/internal/contract"
	"iac-runner/internal/git"
	"iac-runner/internal/runs"
)

// Compile-time signature locks. The plan's acceptance criteria pin
// these exported signatures with regexes anchored at end-of-line,
// which no valid Go declaration can satisfy (the language requires
// `{` on the signature line). These assertions check the same
// contracts at the type level, where drift is a build failure rather
// than a grep miss.
var (
	_ func(Deps) (*Queue, error)                          = New
	_ func(Request) (string, error)                       = (&Queue{}).Submit
	_ func(context.Context) error                         = (&Queue{}).Drain
	_ ExecFunc                                            = DefaultExec
	_ func(context.Context, ExecSpec) (ExecResult, error) = DefaultExec
)

// fakeBackend is a statebackend.Backend whose only interesting method
// is UseLockfile.
type fakeBackend struct{ lockfile bool }

func (f fakeBackend) Endpoint() string          { return "https://example.invalid" }
func (f fakeBackend) Bucket() string            { return "bucket" }
func (f fakeBackend) Region() string            { return "auto" }
func (f fakeBackend) UseLockfile() bool         { return f.lockfile }
func (f fakeBackend) CredentialFiles() []string { return nil }
func (f fakeBackend) Name() string              { return "fake" }

// okGitRunner is a git.CommandRunner that succeeds silently. No test
// in this package spawns a real git process.
func okGitRunner(_ context.Context, _ string, _ []string, _ string, _ ...string) (git.CommandResult, error) {
	return git.CommandResult{}, nil
}

// envOpts configures newEnv.
type envOpts struct {
	// repos are configured AND cloned (a file is planted in the
	// working tree so git.Manager.IsCloned reports true).
	repos []string
	// uncloned repos are configured but have no working tree, which
	// is exactly the D-14 git_clone_missing precondition.
	uncloned []string
	// maxParallel is passed through to Deps.MaxParallel.
	maxParallel int
	// noTofu clears the RESOLVED tofu path after construction so
	// Submit must report run_tofu_not_found. Deps.TofuPath == ""
	// means "look it up on PATH", and the CI/dev container does have
	// a tofu on PATH, so the missing-binary condition can only be
	// expressed by clearing the field New resolved.
	noTofu bool
	// exec is the injected ExecFunc.
	exec ExecFunc
	// applyTimeout bounds both the tofu deadline and the per-repo
	// mutex wait.
	applyTimeout time.Duration
	// backend is the injected state backend.
	backend fakeBackend
}

type testEnv struct {
	t        *testing.T
	q        *Queue
	store    *runs.Store
	runsDir  string
	reposDir string
}

func newEnv(t *testing.T, o envOpts) *testEnv {
	t.Helper()
	root := t.TempDir()
	runsDir := filepath.Join(root, "runs")
	reposDir := filepath.Join(root, "repos")
	keysDir := filepath.Join(root, "keys")
	for _, d := range []string{runsDir, reposDir, keysDir} {
		if err := os.MkdirAll(d, 0o700); err != nil {
			t.Fatalf("mkdir %s: %v", d, err)
		}
	}

	var cfgs []git.RepoConfig
	for _, name := range o.repos {
		cfgs = append(cfgs, git.RepoConfig{Name: name, URL: "git@example.invalid:org/" + name + ".git"})
		wt := filepath.Join(reposDir, name)
		if err := os.MkdirAll(filepath.Join(wt, "envs", "prod"), 0o700); err != nil {
			t.Fatalf("mkdir worktree: %v", err)
		}
		if err := os.WriteFile(filepath.Join(wt, "main.tf"), []byte("# fixture\n"), 0o600); err != nil {
			t.Fatalf("write fixture: %v", err)
		}
	}
	for _, name := range o.uncloned {
		cfgs = append(cfgs, git.RepoConfig{Name: name, URL: "git@example.invalid:org/" + name + ".git"})
	}

	gm, err := git.NewManager(reposDir, keysDir, cfgs, okGitRunner, func(time.Duration) {})
	if err != nil {
		t.Fatalf("git.NewManager: %v", err)
	}
	store, err := runs.NewStore(runsDir, nil)
	if err != nil {
		t.Fatalf("runs.NewStore: %v", err)
	}

	timeout := o.applyTimeout
	if timeout == 0 {
		timeout = 30 * time.Second
	}
	execFn := o.exec
	if execFn == nil {
		execFn = func(context.Context, ExecSpec) (ExecResult, error) { return ExecResult{}, nil }
	}

	q, err := New(Deps{
		Store:        store,
		Git:          gm,
		Backend:      o.backend,
		MaxParallel:  o.maxParallel,
		ApplyTimeout: timeout,
		Exec:         execFn,
		TofuPath:     "/usr/bin/tofu",
	})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if o.noTofu {
		q.tofuPath = ""
	}
	return &testEnv{t: t, q: q, store: store, runsDir: runsDir, reposDir: reposDir}
}

// runDirCount counts materialized run directories.
func (e *testEnv) runDirCount() int {
	e.t.Helper()
	entries, err := os.ReadDir(e.runsDir)
	if err != nil {
		e.t.Fatalf("read runs dir: %v", err)
	}
	n := 0
	for _, en := range entries {
		if en.IsDir() && runs.IsValidRunID(en.Name()) {
			n++
		}
	}
	return n
}

// drain drains the queue with a generous deadline.
func (e *testEnv) drain() {
	e.t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := e.q.Drain(ctx); err != nil {
		e.t.Fatalf("Drain: %v", err)
	}
}

// gate returns an ExecFunc that signals entry exactly once and then
// blocks until release is closed. runJob issues TWO exec calls per job
// (init, then plan or apply), so the entry signal has to be
// idempotent — a bare close() would panic on the second call.
func gate(entered chan struct{}, release <-chan struct{}, res ExecResult) ExecFunc {
	var once sync.Once
	return func(context.Context, ExecSpec) (ExecResult, error) {
		once.Do(func() { close(entered) })
		<-release
		return res, nil
	}
}

// waitFor receives from ch with a timeout guard so a regression fails
// with a readable message instead of hanging the suite.
func waitFor(t *testing.T, ch <-chan struct{}, what string) {
	t.Helper()
	select {
	case <-ch:
	case <-time.After(5 * time.Second):
		t.Fatalf("timed out waiting for %s", what)
	}
}

// errCode extracts the contract error_code from a typed jobq/git error.
func errCode(t *testing.T, err error) string {
	t.Helper()
	if err == nil {
		t.Fatal("expected an error, got nil")
	}
	var gerr *git.Error
	if !errors.As(err, &gerr) {
		t.Fatalf("error %v is not a *git.Error", err)
	}
	return gerr.Code
}

// waitStatus polls the persisted meta until status matches or the
// deadline passes. Polling the durable store is the same observation
// path the API uses (OBS-03).
func (e *testEnv) waitStatus(id string, want contract.RunStatus) runs.Meta {
	e.t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	var last runs.Meta
	for time.Now().Before(deadline) {
		m, err := e.store.Load(id)
		if err == nil {
			last = m
			if m.Status == want {
				return m
			}
		}
		time.Sleep(2 * time.Millisecond)
	}
	e.t.Fatalf("run %s never reached status %s (last=%s)", id, want, last.Status)
	return last
}

func TestSubmitUnknownRepo(t *testing.T) {
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2})
	_, err := e.q.Submit(Request{Repo: "nope", Dir: "", Kind: contract.RunKindPlan})
	if got := errCode(t, err); got != contract.ErrCodeRunUnknownRepo {
		t.Fatalf("error_code = %q, want %q", got, contract.ErrCodeRunUnknownRepo)
	}
	if n := e.runDirCount(); n != 0 {
		t.Fatalf("rejected submission created %d run dirs, want 0", n)
	}
}

func TestSubmitInvalidDir(t *testing.T) {
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2})
	_, err := e.q.Submit(Request{Repo: "infra", Dir: "../etc", Kind: contract.RunKindApply})
	if got := errCode(t, err); got != contract.ErrCodeRunInvalidDir {
		t.Fatalf("error_code = %q, want %q", got, contract.ErrCodeRunInvalidDir)
	}
	if !strings.Contains(err.Error(), "relative path") {
		t.Fatalf("message %q does not carry the D-22 wording", err.Error())
	}
	if n := e.runDirCount(); n != 0 {
		t.Fatalf("rejected submission created %d run dirs, want 0", n)
	}
}

func TestSubmitCloneMissing(t *testing.T) {
	e := newEnv(t, envOpts{repos: []string{"infra"}, uncloned: []string{"ghost"}, maxParallel: 2})
	_, err := e.q.Submit(Request{Repo: "ghost", Dir: "", Kind: contract.RunKindPlan})
	if got := errCode(t, err); got != contract.ErrCodeGitCloneMissing {
		t.Fatalf("error_code = %q, want %q", got, contract.ErrCodeGitCloneMissing)
	}
	if n := e.runDirCount(); n != 0 {
		t.Fatalf("rejected submission created %d run dirs, want 0", n)
	}
}

func TestSubmitTofuMissing(t *testing.T) {
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2, noTofu: true})
	_, err := e.q.Submit(Request{Repo: "infra", Dir: "", Kind: contract.RunKindPlan})
	if got := errCode(t, err); got != contract.ErrCodeRunTofuNotFound {
		t.Fatalf("error_code = %q, want %q", got, contract.ErrCodeRunTofuNotFound)
	}
	if n := e.runDirCount(); n != 0 {
		t.Fatalf("rejected submission created %d run dirs, want 0", n)
	}
}

func TestSubmitReturnsRunIDAndQueuedMeta(t *testing.T) {
	entered := make(chan struct{})
	release := make(chan struct{})
	e := newEnv(t, envOpts{
		repos:       []string{"infra"},
		maxParallel: 2,
		exec:        gate(entered, release, ExecResult{}),
	})

	id, err := e.q.Submit(Request{Repo: "infra", Dir: "envs/prod", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("Submit: %v", err)
	}
	if !runs.IsValidRunID(id) {
		t.Fatalf("run id %q is not valid", id)
	}
	m, err := e.store.Load(id)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if m.Status != contract.RunStatusQueued && m.Status != contract.RunStatusRunning {
		t.Fatalf("status = %q, want queued or running", m.Status)
	}
	if m.Repo != "infra" || m.Dir != "envs/prod" || m.Kind != contract.RunKindApply {
		t.Fatalf("meta = %+v, want repo/dir/kind echoed", m)
	}
	waitFor(t, entered, "exec entry")
	close(release)
	e.drain()
}

func TestSubmitCapacityExhausted(t *testing.T) {
	entered := make(chan struct{})
	release := make(chan struct{})
	e := newEnv(t, envOpts{
		repos:       []string{"a", "b"},
		maxParallel: 1,
		exec:        gate(entered, release, ExecResult{}),
	})

	first, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("first Submit: %v", err)
	}
	waitFor(t, entered, "first job to occupy the slot")

	before := e.runDirCount()
	_, err = e.q.Submit(Request{Repo: "b", Kind: contract.RunKindApply})
	if !errors.Is(err, ErrCapacityExhausted) {
		t.Fatalf("second Submit err = %v, want ErrCapacityExhausted", err)
	}
	if after := e.runDirCount(); after != before {
		t.Fatalf("refused submission created state: %d -> %d run dirs", before, after)
	}

	close(release)
	e.drain()
	e.waitStatus(first, contract.RunStatusSucceeded)
}

func TestSubmitSlotReleasedAfterCompletion(t *testing.T) {
	release := make(chan struct{})
	entered := make(chan struct{})
	e := newEnv(t, envOpts{
		repos:       []string{"a", "b"},
		maxParallel: 1,
		exec:        gate(entered, release, ExecResult{}),
	})

	if _, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply}); err != nil {
		t.Fatalf("first Submit: %v", err)
	}
	waitFor(t, entered, "first job entry")
	if _, err := e.q.Submit(Request{Repo: "b", Kind: contract.RunKindApply}); !errors.Is(err, ErrCapacityExhausted) {
		t.Fatalf("expected saturation, got %v", err)
	}

	close(release)
	e.drain()

	// The slot must be free again now that the first job finished.
	id, err := e.q.Submit(Request{Repo: "b", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("Submit after completion: %v", err)
	}
	e.drain()
	e.waitStatus(id, contract.RunStatusSucceeded)
}

func TestWorkerPanicIsRecoveredAndSlotReleased(t *testing.T) {
	var mu sync.Mutex
	var calls int
	e := newEnv(t, envOpts{
		repos:       []string{"a"},
		maxParallel: 1,
		exec: func(context.Context, ExecSpec) (ExecResult, error) {
			mu.Lock()
			calls++
			n := calls
			mu.Unlock()
			// The first exec call of the first job — tofu init — is
			// where the panic is injected.
			if n == 1 {
				panic("boom from the fake exec")
			}
			return ExecResult{}, nil
		},
	})

	first, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("first Submit: %v", err)
	}
	e.drain()
	m := e.waitStatus(first, contract.RunStatusFailed)
	if m.ErrorCode != contract.ErrCodeApplyFailed {
		t.Fatalf("error_code = %q, want %q", m.ErrorCode, contract.ErrCodeApplyFailed)
	}

	second, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("Submit after panic: %v", err)
	}
	e.drain()
	e.waitStatus(second, contract.RunStatusSucceeded)
}

func TestTerminalStatusesFromExitCode(t *testing.T) {
	for _, tc := range []struct {
		name      string
		exit      int
		want      contract.RunStatus
		errorCode string
	}{
		{"exit0", 0, contract.RunStatusSucceeded, ""},
		{"exit1", 1, contract.RunStatusFailed, contract.ErrCodeApplyFailed},
	} {
		t.Run(tc.name, func(t *testing.T) {
			e := newEnv(t, envOpts{
				repos:       []string{"a"},
				maxParallel: 2,
				exec: func(context.Context, ExecSpec) (ExecResult, error) {
					return ExecResult{ExitCode: tc.exit}, nil
				},
			})
			id, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
			if err != nil {
				t.Fatalf("Submit: %v", err)
			}
			e.drain()
			m := e.waitStatus(id, tc.want)
			if m.ExitCode == nil || *m.ExitCode != tc.exit {
				t.Fatalf("exit_code = %v, want %d", m.ExitCode, tc.exit)
			}
			if m.ErrorCode != tc.errorCode {
				t.Fatalf("error_code = %q, want %q", m.ErrorCode, tc.errorCode)
			}
			if m.FinishedAt == nil {
				t.Fatal("finished_at is nil on a terminal run")
			}
		})
	}
}

func TestTimeoutMarksRunFailedWithTimeoutCode(t *testing.T) {
	for _, tc := range []struct {
		kind contract.RunKind
		code string
	}{
		{contract.RunKindApply, contract.ErrCodeApplyTimeout},
		{contract.RunKindPlan, contract.ErrCodePlanTimeout},
	} {
		t.Run(string(tc.kind), func(t *testing.T) {
			e := newEnv(t, envOpts{
				repos:       []string{"a"},
				maxParallel: 2,
				exec: func(context.Context, ExecSpec) (ExecResult, error) {
					return ExecResult{ExitCode: -1, TimedOut: true}, nil
				},
			})
			id, err := e.q.Submit(Request{Repo: "a", Kind: tc.kind})
			if err != nil {
				t.Fatalf("Submit: %v", err)
			}
			e.drain()
			m := e.waitStatus(id, contract.RunStatusFailed)
			if m.ErrorCode != tc.code {
				t.Fatalf("error_code = %q, want %q", m.ErrorCode, tc.code)
			}
		})
	}
}

func TestDrainWaitsForInFlight(t *testing.T) {
	entered := make(chan struct{})
	release := make(chan struct{})
	e := newEnv(t, envOpts{
		repos:       []string{"a"},
		maxParallel: 2,
		exec:        gate(entered, release, ExecResult{}),
	})
	id, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("Submit: %v", err)
	}
	waitFor(t, entered, "exec entry")

	drained := make(chan struct{})
	go func() {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := e.q.Drain(ctx); err != nil {
			t.Errorf("Drain: %v", err)
		}
		close(drained)
	}()

	select {
	case <-drained:
		t.Fatal("Drain returned while a job was still in flight")
	case <-time.After(50 * time.Millisecond):
	}

	close(release)
	waitFor(t, drained, "Drain to return")

	m, err := e.store.Load(id)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if m.Status != contract.RunStatusSucceeded {
		t.Fatalf("status after drain = %q, want succeeded", m.Status)
	}
}

func TestDrainRespectsContextDeadline(t *testing.T) {
	entered := make(chan struct{})
	release := make(chan struct{})
	defer close(release)
	e := newEnv(t, envOpts{
		repos:       []string{"a"},
		maxParallel: 2,
		exec:        gate(entered, release, ExecResult{}),
	})
	if _, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply}); err != nil {
		t.Fatalf("Submit: %v", err)
	}
	waitFor(t, entered, "exec entry")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Millisecond)
	defer cancel()
	if err := e.q.Drain(ctx); !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("Drain err = %v, want context.DeadlineExceeded", err)
	}
}

func TestNewDefaultsAndValidation(t *testing.T) {
	if _, err := New(Deps{}); err == nil {
		t.Fatal("New with no Store must fail")
	}
	root := t.TempDir()
	store, err := runs.NewStore(filepath.Join(root, "runs"), nil)
	if err != nil {
		t.Fatalf("NewStore: %v", err)
	}
	if _, err := New(Deps{Store: store}); err == nil {
		t.Fatal("New with no Git must fail")
	}

	gm, err := git.NewManager(filepath.Join(root, "repos"), filepath.Join(root, "keys"), nil, okGitRunner, func(time.Duration) {})
	if err != nil {
		t.Fatalf("git.NewManager: %v", err)
	}
	q, err := New(Deps{Store: store, Git: gm, TofuPath: "/usr/bin/tofu"})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if cap(q.sem) != defaultMaxParallel {
		t.Fatalf("MaxParallel 0 gave cap %d, want the D-04 default %d", cap(q.sem), defaultMaxParallel)
	}
	if q.applyTimeout != defaultApplyTimeout {
		t.Fatalf("ApplyTimeout 0 gave %v, want the D-15 default %v", q.applyTimeout, defaultApplyTimeout)
	}
	if q.now == nil {
		t.Fatal("Now default was not applied")
	}
	if q.exec == nil {
		t.Fatal("Exec default was not applied")
	}

	clamped, err := New(Deps{Store: store, Git: gm, MaxParallel: 999, TofuPath: "/usr/bin/tofu"})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if cap(clamped.sem) != maxMaxParallel {
		t.Fatalf("MaxParallel 999 gave cap %d, want the schema ceiling %d", cap(clamped.sem), maxMaxParallel)
	}
}

func TestLockForReturnsSameMutexPerRepo(t *testing.T) {
	e := newEnv(t, envOpts{repos: []string{"a", "b"}, maxParallel: 2})
	if e.q.lockFor("a") != e.q.lockFor("a") {
		t.Fatal("lockFor returned two different mutexes for the same repo")
	}
	if e.q.lockFor("a") == e.q.lockFor("b") {
		t.Fatal("lockFor returned the same mutex for two different repos")
	}
}
