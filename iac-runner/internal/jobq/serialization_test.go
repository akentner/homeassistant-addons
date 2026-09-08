package jobq

// RUN-06 is this phase's highest-risk guarantee: same-repo applies
// serialize, cross-repo applies parallelize, and the repo mutex is
// released on success, failure and crash alike. A single happy-path
// test proves almost nothing about a mutex, so this file attacks the
// guarantee from seven angles with a deterministic harness.
//
// Two rules keep the suite honest under `-race -count=5`:
//
//   - Nothing is inferred from timing. Every claim is asserted against
//     recorded concurrent OCCUPANCY (atomic counters incremented on
//     entry to the fake exec), never against timestamps.
//   - Every wait is a channel receive with a timeout guard, so a
//     regression fails with a readable message instead of hanging.

import (
	"context"
	"errors"
	"path/filepath"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"iac-runner/internal/contract"
	"iac-runner/internal/runs"
)

// counter tracks current and peak occupancy. max is maintained with a
// compare-and-swap loop so the peak survives concurrent entries.
type counter struct {
	cur atomic.Int32
	max atomic.Int32
}

func (c *counter) enter() {
	cur := c.cur.Add(1)
	for {
		peak := c.max.Load()
		if cur <= peak || c.max.CompareAndSwap(peak, cur) {
			return
		}
	}
}

func (c *counter) leave() { c.cur.Add(-1) }

// occupancy records how many fake exec calls were in flight at once,
// globally and per repo. The per-repo peak IS the RUN-06 assertion: a
// peak of 1 means two same-repo execution windows never overlapped.
type occupancy struct {
	global counter

	mu     sync.Mutex
	byRepo map[string]*counter
}

func newOccupancy() *occupancy {
	return &occupancy{byRepo: make(map[string]*counter)}
}

func (o *occupancy) forRepo(repo string) *counter {
	o.mu.Lock()
	defer o.mu.Unlock()
	c, ok := o.byRepo[repo]
	if !ok {
		c = &counter{}
		o.byRepo[repo] = c
	}
	return c
}

func (o *occupancy) enter(repo string) {
	o.global.enter()
	o.forRepo(repo).enter()
}

func (o *occupancy) leave(repo string) {
	o.forRepo(repo).leave()
	o.global.leave()
}

func (o *occupancy) peakGlobal() int32       { return o.global.max.Load() }
func (o *occupancy) peakRepo(r string) int32 { return o.forRepo(r).max.Load() }

// gatedExec is the ExecFunc every test in this file injects. It
// records occupancy, reports entry on a channel, and blocks until the
// repo's release channel is closed.
//
// `tofu init` passes straight through: it is not the execution window
// RUN-06 talks about, and gating it would double every wait for no
// added proof. Occupancy is still recorded for it, so an overlap
// during init would also be caught.
type gatedExec struct {
	occ     *occupancy
	entered chan string

	mu       sync.Mutex
	releases map[string]chan struct{}
	closed   map[string]bool
	// outcome scripts the n-th (1-based, per repo) gated call.
	outcome map[string]func(n int) (ExecResult, error)
	calls   map[string]int
}

func newGatedExec() *gatedExec {
	return &gatedExec{
		occ:      newOccupancy(),
		entered:  make(chan string, 64),
		releases: make(map[string]chan struct{}),
		closed:   make(map[string]bool),
		outcome:  make(map[string]func(n int) (ExecResult, error)),
		calls:    make(map[string]int),
	}
}

func (g *gatedExec) releaseFor(repo string) chan struct{} {
	g.mu.Lock()
	defer g.mu.Unlock()
	ch, ok := g.releases[repo]
	if !ok {
		ch = make(chan struct{})
		g.releases[repo] = ch
	}
	return ch
}

// release unblocks every gated call for repo. Idempotent.
func (g *gatedExec) release(repo string) {
	ch := g.releaseFor(repo)
	g.mu.Lock()
	defer g.mu.Unlock()
	if !g.closed[repo] {
		g.closed[repo] = true
		close(ch)
	}
}

func (g *gatedExec) releaseAll(repos ...string) {
	for _, r := range repos {
		g.release(r)
	}
}

// scriptOutcome sets the per-repo outcome function.
func (g *gatedExec) scriptOutcome(repo string, fn func(n int) (ExecResult, error)) {
	g.mu.Lock()
	defer g.mu.Unlock()
	g.outcome[repo] = fn
}

func (g *gatedExec) fn(_ context.Context, spec ExecSpec) (ExecResult, error) {
	// Every serialization test submits with an empty dir, so the work
	// directory IS the repo working tree and its basename is the repo
	// name (D-23).
	repo := filepath.Base(spec.WorkDir)

	g.occ.enter(repo)
	defer g.occ.leave(repo)

	if len(spec.Args) > 0 && spec.Args[0] == "init" {
		return ExecResult{}, nil
	}

	g.mu.Lock()
	g.calls[repo]++
	n := g.calls[repo]
	outcome := g.outcome[repo]
	g.mu.Unlock()

	g.entered <- repo
	<-g.releaseFor(repo)

	if outcome != nil {
		return outcome(n)
	}
	return ExecResult{}, nil
}

// waitEntered receives one entry report with a timeout guard.
func (g *gatedExec) waitEntered(t *testing.T, what string) string {
	t.Helper()
	select {
	case repo := <-g.entered:
		return repo
	case <-time.After(5 * time.Second):
		t.Fatalf("timed out waiting for %s", what)
		return ""
	}
}

// waitRunning polls the durable store until id is `running`. This is
// the same observation path the API uses (OBS-03).
func (e *testEnv) waitRunning(id string) {
	e.t.Helper()
	e.waitStatus(id, contract.RunStatusRunning)
}

// statusOf reads one run's persisted status.
func (e *testEnv) statusOf(id string) contract.RunStatus {
	e.t.Helper()
	m, err := e.store.Load(id)
	if err != nil {
		e.t.Fatalf("Load %s: %v", id, err)
	}
	return m.Status
}

func TestSameRepoAppliesSerialize(t *testing.T) {
	g := newGatedExec()
	e := newEnv(t, envOpts{repos: []string{"a"}, maxParallel: 4, exec: g.fn})

	first, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("first Submit: %v", err)
	}
	second, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("second Submit: %v", err)
	}
	if first == second {
		t.Fatal("both submissions got the same run id")
	}

	// Job 1 is inside the gated exec; job 2 must still be waiting on
	// the repo mutex, i.e. observably queued.
	g.waitEntered(t, "the first job to enter exec")
	e.waitRunning(first)
	if got := e.statusOf(second); got != contract.RunStatusQueued {
		t.Fatalf("second run status = %q while the first runs, want queued (RUN-06)", got)
	}
	if peak := g.occ.peakRepo("a"); peak != 1 {
		t.Fatalf("same-repo occupancy peaked at %d, want 1", peak)
	}

	g.release("a")
	g.waitEntered(t, "the second job to enter exec")
	e.drain()

	if peak := g.occ.peakRepo("a"); peak != 1 {
		t.Fatalf("same-repo occupancy peaked at %d, want 1 — the execution windows overlapped", peak)
	}
	for _, id := range []string{first, second} {
		if got := e.statusOf(id); got != contract.RunStatusSucceeded {
			t.Fatalf("run %s status = %q, want succeeded", id, got)
		}
	}
}

func TestSecondSameRepoRunIsQueuedWhileFirstRuns(t *testing.T) {
	g := newGatedExec()
	e := newEnv(t, envOpts{repos: []string{"a"}, maxParallel: 4, exec: g.fn})

	first, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("first Submit: %v", err)
	}
	second, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("second Submit: %v", err)
	}

	g.waitEntered(t, "the first job to enter exec")
	e.waitRunning(first)

	// The 202-then-wait contract: the caller already holds a run id
	// and can poll it, and what they see is `queued`.
	m, err := e.store.Load(second)
	if err != nil {
		t.Fatalf("Load second: %v", err)
	}
	if m.Status != contract.RunStatusQueued {
		t.Fatalf("second run status = %q, want queued", m.Status)
	}
	if m.ExitCode != nil {
		t.Fatalf("queued run reported exit_code %v, want null", *m.ExitCode)
	}

	g.release("a")
	e.drain()
}

func TestCrossRepoAppliesRunInParallel(t *testing.T) {
	g := newGatedExec()
	e := newEnv(t, envOpts{repos: []string{"a", "b"}, maxParallel: 4, exec: g.fn})

	if _, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply}); err != nil {
		t.Fatalf("Submit a: %v", err)
	}
	if _, err := e.q.Submit(Request{Repo: "b", Kind: contract.RunKindApply}); err != nil {
		t.Fatalf("Submit b: %v", err)
	}

	// Both jobs must be inside their exec call at the same time. A
	// global (rather than per-repo) mutex would make this wait time
	// out, which is why the guard reports a clear failure instead of
	// hanging the suite.
	seen := map[string]bool{}
	for i := 0; i < 2; i++ {
		seen[g.waitEntered(t, "both repos to enter exec concurrently")] = true
	}
	if !seen["a"] || !seen["b"] {
		t.Fatalf("entered repos = %v, want both a and b", seen)
	}
	if peak := g.occ.peakGlobal(); peak != 2 {
		t.Fatalf("global occupancy peaked at %d, want 2 — cross-repo jobs did not overlap", peak)
	}

	g.releaseAll("a", "b")
	e.drain()
}

func TestFailedJobReleasesRepoMutex(t *testing.T) {
	g := newGatedExec()
	// The first gated call for repo "a" fails; the second must still
	// get its turn.
	g.scriptOutcome("a", func(n int) (ExecResult, error) {
		if n == 1 {
			return ExecResult{ExitCode: 1}, nil
		}
		return ExecResult{}, nil
	})
	g.release("a") // ungated: the outcome, not the timing, is under test
	e := newEnv(t, envOpts{repos: []string{"a"}, maxParallel: 4, exec: g.fn})

	first, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("first Submit: %v", err)
	}
	second, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("second Submit: %v", err)
	}
	e.drain()

	m := e.waitStatus(first, contract.RunStatusFailed)
	if m.ErrorCode != contract.ErrCodeApplyFailed {
		t.Fatalf("first run error_code = %q, want %q", m.ErrorCode, contract.ErrCodeApplyFailed)
	}
	e.waitStatus(second, contract.RunStatusSucceeded)
	if peak := g.occ.peakRepo("a"); peak != 1 {
		t.Fatalf("same-repo occupancy peaked at %d, want 1", peak)
	}
}

func TestPanickingJobReleasesRepoMutex(t *testing.T) {
	g := newGatedExec()
	g.scriptOutcome("a", func(n int) (ExecResult, error) {
		if n == 1 {
			panic("boom inside the first job")
		}
		return ExecResult{}, nil
	})
	g.release("a")
	e := newEnv(t, envOpts{repos: []string{"a"}, maxParallel: 4, exec: g.fn})

	first, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("first Submit: %v", err)
	}
	e.waitStatus(first, contract.RunStatusFailed)

	second, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("Submit after the panic: %v", err)
	}
	e.drain()
	e.waitStatus(second, contract.RunStatusSucceeded)
}

func TestCapacityRefusesThirdSubmission(t *testing.T) {
	g := newGatedExec()
	e := newEnv(t, envOpts{repos: []string{"a", "b", "c", "d"}, maxParallel: 2, exec: g.fn})

	a, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("Submit a: %v", err)
	}
	if _, err := e.q.Submit(Request{Repo: "b", Kind: contract.RunKindApply}); err != nil {
		t.Fatalf("Submit b: %v", err)
	}
	// Both slots are occupied once both jobs are inside exec.
	for i := 0; i < 2; i++ {
		g.waitEntered(t, "the first two jobs to occupy both slots")
	}

	if _, err := e.q.Submit(Request{Repo: "c", Kind: contract.RunKindApply}); !errors.Is(err, ErrCapacityExhausted) {
		t.Fatalf("third Submit err = %v, want ErrCapacityExhausted (D-06)", err)
	}

	// Freeing one slot must make capacity available again.
	g.release("a")
	e.waitStatus(a, contract.RunStatusSucceeded)
	if _, err := e.q.Submit(Request{Repo: "d", Kind: contract.RunKindApply}); err != nil {
		t.Fatalf("Submit d after a slot was freed: %v", err)
	}
	g.waitEntered(t, "the fourth job to enter the freed slot")

	g.releaseAll("b", "c", "d")
	e.drain()
	if peak := g.occ.peakGlobal(); peak > 2 {
		t.Fatalf("global occupancy peaked at %d, want at most max_parallel_jobs (2)", peak)
	}
}

func TestDrainLeavesNoRunningRuns(t *testing.T) {
	g := newGatedExec()
	repos := []string{"a", "b", "c"}
	g.releaseAll(repos...)
	e := newEnv(t, envOpts{repos: repos, maxParallel: 4, exec: g.fn})

	var ids []string
	var wg sync.WaitGroup
	var mu sync.Mutex
	for _, repo := range repos {
		wg.Add(1)
		go func(repo string) {
			defer wg.Done()
			id, err := e.q.Submit(Request{Repo: repo, Kind: contract.RunKindApply})
			if err != nil {
				return
			}
			mu.Lock()
			ids = append(ids, id)
			mu.Unlock()
		}(repo)
	}
	wg.Wait()
	if len(ids) == 0 {
		t.Fatal("no submission succeeded")
	}
	e.drain()

	metas, err := e.store.List(runs.ListFilter{Limit: contract.MaxRunListLimit})
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(metas) != len(ids) {
		t.Fatalf("store holds %d runs, want %d", len(metas), len(ids))
	}
	for _, m := range metas {
		if m.Status == contract.RunStatusQueued || m.Status == contract.RunStatusRunning {
			t.Fatalf("run %s is still %q after Drain returned", m.RunID, m.Status)
		}
		if m.FinishedAt == nil {
			t.Fatalf("run %s has no finished_at after Drain returned", m.RunID)
		}
	}
}

// TestSameRepoWaiterDoesNotStarveOtherRepos is the WR-08 regression.
// The global slot used to be taken in Submit and held across the wait
// on the per-repo mutex, so a job queued behind another job on the
// SAME repo consumed capacity for the whole wait — up to
// apply_timeout, 60 minutes by default. Four queued applies against
// one repo pinned the entire runner: every other repo got 503
// apply_capacity_exhausted while three of the four slots had no tofu
// process behind them.
func TestSameRepoWaiterDoesNotStarveOtherRepos(t *testing.T) {
	g := newGatedExec()
	e := newEnv(t, envOpts{repos: []string{"a", "b"}, maxParallel: 2, exec: g.fn})

	first, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("Submit a#1: %v", err)
	}
	g.waitEntered(t, "the first job to occupy an execution slot")

	second, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply})
	if err != nil {
		t.Fatalf("Submit a#2: %v", err)
	}

	// The waiter hands its admission slot back asynchronously, so the
	// claim is that repo b becomes admissible — under the old
	// ordering it never would, until the first job finished.
	var third string
	deadline := time.Now().Add(5 * time.Second)
	for {
		id, err := e.q.Submit(Request{Repo: "b", Kind: contract.RunKindApply})
		if err == nil {
			third = id
			break
		}
		if !errors.Is(err, ErrCapacityExhausted) {
			t.Fatalf("Submit b: %v", err)
		}
		if time.Now().After(deadline) {
			t.Fatal("repo b stayed refused while a same-repo waiter held a slot (WR-08)")
		}
		time.Sleep(10 * time.Millisecond)
	}
	// Admitted is not enough: it has to actually execute, which means
	// it won a real slot while repo a's second job was still waiting.
	if repo := g.waitEntered(t, "repo b to enter exec"); repo != "b" {
		t.Fatalf("entered repo = %q, want b", repo)
	}
	if got := e.statusOf(second); got != contract.RunStatusQueued {
		t.Fatalf("repo a's second run = %q, want it still queued behind the first", got)
	}

	// The per-repo admission bound is what replaces "a waiter holds a
	// global slot": maxPending == max_parallel_jobs, so repo a refuses
	// its third submission exactly where it refused before.
	if _, err := e.q.Submit(Request{Repo: "a", Kind: contract.RunKindApply}); !errors.Is(err, ErrCapacityExhausted) {
		t.Fatalf("third same-repo Submit err = %v, want ErrCapacityExhausted", err)
	}

	g.releaseAll("a", "b")
	e.drain()
	for _, id := range []string{first, second, third} {
		e.waitStatus(id, contract.RunStatusSucceeded)
	}
	// RUN-06 still holds: the two repo-a jobs never overlapped.
	if peak := g.occ.peakRepo("a"); peak != 1 {
		t.Errorf("same-repo occupancy peaked at %d, want 1", peak)
	}
	if peak := g.occ.peakGlobal(); peak > 2 {
		t.Errorf("global occupancy peaked at %d, want at most max_parallel_jobs (2)", peak)
	}
}
