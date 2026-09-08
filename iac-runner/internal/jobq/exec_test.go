package jobq

import (
	"bytes"
	"context"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"iac-runner/internal/contract"
	"iac-runner/internal/runs"
)

// recordedExec is a fake ExecFunc that records every ExecSpec it was
// handed and lets a test script each invocation's outcome. Command-line
// assertions never start a process — the whole point of the ExecFunc
// seam.
type recordedExec struct {
	mu    sync.Mutex
	calls []ExecSpec
	// respond scripts the n-th (1-based) invocation. A nil respond
	// means exit 0 for every call.
	respond func(n int, spec ExecSpec) (ExecResult, error)
}

func (r *recordedExec) fn(_ context.Context, spec ExecSpec) (ExecResult, error) {
	r.mu.Lock()
	copySpec := spec
	copySpec.Args = append([]string(nil), spec.Args...)
	r.calls = append(r.calls, copySpec)
	n := len(r.calls)
	respond := r.respond
	r.mu.Unlock()
	if respond == nil {
		return ExecResult{}, nil
	}
	return respond(n, spec)
}

func (r *recordedExec) recorded() []ExecSpec {
	r.mu.Lock()
	defer r.mu.Unlock()
	return append([]ExecSpec(nil), r.calls...)
}

// seedRun materializes a run directory with the given meta so runJob
// has somewhere to write and priorPlanFile has something to find.
func (e *testEnv) seedRun(m runs.Meta) runs.Meta {
	e.t.Helper()
	if m.RunID == "" {
		id, err := runs.NewRunID()
		if err != nil {
			e.t.Fatalf("NewRunID: %v", err)
		}
		m.RunID = id
	}
	if m.StartedAt.IsZero() {
		m.StartedAt = time.Now().UTC()
	}
	if err := e.store.Create(m); err != nil {
		e.t.Fatalf("Create: %v", err)
	}
	return m
}

// runJobFor drives runJob directly for one seeded run and returns the
// result plus the plan-artifact path.
func (e *testEnv) runJobFor(m runs.Meta) (ExecResult, string, error) {
	e.t.Helper()
	w, err := e.store.OpenOutput(m.RunID)
	if err != nil {
		e.t.Fatalf("OpenOutput: %v", err)
	}
	defer func() { _ = w.Close() }()
	return e.q.runJob(m.RunID, m.Repo, m.Dir, m.Kind, w)
}

func TestRunJobPlanCommandLine(t *testing.T) {
	rec := &recordedExec{}
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2, exec: rec.fn})
	m := e.seedRun(runs.Meta{Repo: "infra", Dir: "envs/prod", Kind: contract.RunKindPlan, Status: contract.RunStatusRunning})

	_, planFile, err := e.runJobFor(m)
	if err != nil {
		t.Fatalf("runJob: %v", err)
	}

	calls := mustCalls(t, rec, 2)
	if calls[0].Args[0] != "init" {
		t.Fatalf("first call args = %v, want init first", calls[0].Args)
	}
	if !hasArg(calls[0].Args, "-input=false") {
		t.Fatalf("init args = %v, want -input=false (RUN-02)", calls[0].Args)
	}
	if calls[1].Args[0] != "plan" {
		t.Fatalf("second call args = %v, want plan", calls[1].Args)
	}
	for _, want := range []string{"-no-color", "-input=false"} {
		if !hasArg(calls[1].Args, want) {
			t.Fatalf("plan args = %v, want %s", calls[1].Args, want)
		}
	}
	wantOut := "-out=" + filepath.Join(e.store.Dir(m.RunID), "plan.tfplan")
	if !hasArg(calls[1].Args, wantOut) {
		t.Fatalf("plan args = %v, want %s", calls[1].Args, wantOut)
	}
	if planFile != filepath.Join(e.store.Dir(m.RunID), "plan.tfplan") {
		t.Fatalf("planFile = %q, want the artifact inside the run dir", planFile)
	}
	if calls[1].Path != e.q.tofuPath {
		t.Fatalf("exec path = %q, want the resolved tofu path %q", calls[1].Path, e.q.tofuPath)
	}
}

// mustCalls returns exactly n recorded invocations, failing the test
// with a readable message rather than panicking on an index when the
// implementation made a different number of calls.
func mustCalls(t *testing.T, rec *recordedExec, n int) []ExecSpec {
	t.Helper()
	calls := rec.recorded()
	if len(calls) != n {
		t.Fatalf("got %d exec calls, want %d: %+v", len(calls), n, calls)
	}
	for i, c := range calls {
		if len(c.Args) == 0 {
			t.Fatalf("exec call %d has no arguments", i)
		}
	}
	return calls
}

func hasArg(args []string, want string) bool {
	for _, a := range args {
		if a == want {
			return true
		}
	}
	return false
}

func TestRunJobApplyInlineWhenNoPriorPlan(t *testing.T) {
	rec := &recordedExec{}
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2, exec: rec.fn})
	m := e.seedRun(runs.Meta{Repo: "infra", Dir: "envs/prod", Kind: contract.RunKindApply, Status: contract.RunStatusRunning})

	if _, planFile, err := e.runJobFor(m); err != nil || planFile != "" {
		t.Fatalf("runJob = (%q, %v), want no plan artifact for an apply", planFile, err)
	}

	calls := mustCalls(t, rec, 2)
	args := calls[1].Args
	if args[0] != "apply" || !hasArg(args, "-auto-approve") || !hasArg(args, "-no-color") {
		t.Fatalf("apply args = %v, want the RUN-03 form", args)
	}
	// D-17: no trailing plan-file argument.
	last := args[len(args)-1]
	if !strings.HasPrefix(last, "-") {
		t.Fatalf("apply args = %v, want no trailing plan-file argument (D-17)", args)
	}
}

func TestExecApplyUsesPriorPlanFile(t *testing.T) {
	rec := &recordedExec{}
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2, exec: rec.fn})

	prior := e.seedRun(runs.Meta{
		Repo:      "infra",
		Dir:       "envs/prod",
		Kind:      contract.RunKindPlan,
		Status:    contract.RunStatusSucceeded,
		StartedAt: time.Now().UTC().Add(-time.Minute),
		HeadSHA:   fixtureHeadSHA, // D-18 freshness: built against the current worktree HEAD
	})
	priorPlan := filepath.Join(e.store.Dir(prior.RunID), "plan.tfplan")
	if err := os.WriteFile(priorPlan, []byte("binary plan"), 0o600); err != nil {
		t.Fatalf("write prior plan: %v", err)
	}
	if _, err := e.store.Update(prior.RunID, func(m *runs.Meta) error {
		m.PlanFile = priorPlan
		return nil
	}); err != nil {
		t.Fatalf("Update prior: %v", err)
	}

	apply := e.seedRun(runs.Meta{Repo: "infra", Dir: "envs/prod", Kind: contract.RunKindApply, Status: contract.RunStatusRunning})
	if _, _, err := e.runJobFor(apply); err != nil {
		t.Fatalf("runJob: %v", err)
	}

	calls := mustCalls(t, rec, 2)
	args := calls[len(calls)-1].Args
	if args[len(args)-1] != priorPlan {
		t.Fatalf("apply args = %v, want %s as the last argument (D-18)", args, priorPlan)
	}
}

func TestApplyFallsBackWhenPriorPlanFileMissing(t *testing.T) {
	rec := &recordedExec{}
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2, exec: rec.fn})

	prior := e.seedRun(runs.Meta{
		Repo:      "infra",
		Dir:       "envs/prod",
		Kind:      contract.RunKindPlan,
		Status:    contract.RunStatusSucceeded,
		StartedAt: time.Now().UTC().Add(-time.Minute),
		HeadSHA:   fixtureHeadSHA, // D-18 freshness: built against the current worktree HEAD
	})
	// Retention already swept the artifact: the meta still names it,
	// the file is gone (D-18 fallback).
	if _, err := e.store.Update(prior.RunID, func(m *runs.Meta) error {
		m.PlanFile = filepath.Join(e.store.Dir(prior.RunID), "plan.tfplan")
		return nil
	}); err != nil {
		t.Fatalf("Update prior: %v", err)
	}

	apply := e.seedRun(runs.Meta{Repo: "infra", Dir: "envs/prod", Kind: contract.RunKindApply, Status: contract.RunStatusRunning})
	if _, _, err := e.runJobFor(apply); err != nil {
		t.Fatalf("runJob: %v", err)
	}

	calls := mustCalls(t, rec, 2)
	args := calls[len(calls)-1].Args
	if last := args[len(args)-1]; !strings.HasPrefix(last, "-") {
		t.Fatalf("apply args = %v, want the inline form when the artifact is gone (D-18)", args)
	}
}

func TestPriorPlanIgnoresOtherDirsAndKinds(t *testing.T) {
	rec := &recordedExec{}
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2, exec: rec.fn})

	// A succeeded plan for a DIFFERENT dir must not be consumed.
	other := e.seedRun(runs.Meta{
		Repo:      "infra",
		Dir:       "envs/stage",
		Kind:      contract.RunKindPlan,
		Status:    contract.RunStatusSucceeded,
		StartedAt: time.Now().UTC().Add(-time.Minute),
		HeadSHA:   fixtureHeadSHA, // D-18 freshness: built against the current worktree HEAD
	})
	otherPlan := filepath.Join(e.store.Dir(other.RunID), "plan.tfplan")
	if err := os.WriteFile(otherPlan, []byte("binary plan"), 0o600); err != nil {
		t.Fatalf("write plan: %v", err)
	}
	if _, err := e.store.Update(other.RunID, func(m *runs.Meta) error {
		m.PlanFile = otherPlan
		return nil
	}); err != nil {
		t.Fatalf("Update: %v", err)
	}

	apply := e.seedRun(runs.Meta{Repo: "infra", Dir: "envs/prod", Kind: contract.RunKindApply, Status: contract.RunStatusRunning})
	if _, _, err := e.runJobFor(apply); err != nil {
		t.Fatalf("runJob: %v", err)
	}
	args := mustCalls(t, rec, 2)[1].Args
	if args[len(args)-1] == otherPlan {
		t.Fatalf("apply consumed a plan artifact from a different dir: %v", args)
	}
}

func TestRunJobUsesRepoWorkTreeAndDir(t *testing.T) {
	rec := &recordedExec{}
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2, exec: rec.fn})
	worktree := filepath.Join(e.reposDir, "infra")

	sub := e.seedRun(runs.Meta{Repo: "infra", Dir: "envs/prod", Kind: contract.RunKindApply, Status: contract.RunStatusRunning})
	if _, _, err := e.runJobFor(sub); err != nil {
		t.Fatalf("runJob: %v", err)
	}
	for _, c := range rec.recorded() {
		if c.WorkDir != filepath.Join(worktree, "envs", "prod") {
			t.Fatalf("WorkDir = %q, want %q", c.WorkDir, filepath.Join(worktree, "envs", "prod"))
		}
	}

	// D-23: the empty dir legally means the repo root.
	rec2 := &recordedExec{}
	e.q.exec = rec2.fn
	root := e.seedRun(runs.Meta{Repo: "infra", Dir: "", Kind: contract.RunKindApply, Status: contract.RunStatusRunning})
	if _, _, err := e.runJobFor(root); err != nil {
		t.Fatalf("runJob: %v", err)
	}
	for _, c := range rec2.recorded() {
		if c.WorkDir != worktree {
			t.Fatalf("WorkDir = %q, want the repo root %q", c.WorkDir, worktree)
		}
	}
}

func TestInitFailureShortCircuits(t *testing.T) {
	rec := &recordedExec{respond: func(n int, _ ExecSpec) (ExecResult, error) {
		if n == 1 {
			return ExecResult{ExitCode: 1}, nil
		}
		return ExecResult{}, nil
	}}
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2, exec: rec.fn})
	m := e.seedRun(runs.Meta{Repo: "infra", Dir: "envs/prod", Kind: contract.RunKindApply, Status: contract.RunStatusRunning})

	res, _, err := e.runJobFor(m)
	if err != nil {
		t.Fatalf("runJob: %v", err)
	}
	if res.ExitCode != 1 {
		t.Fatalf("exit code = %d, want init's 1", res.ExitCode)
	}
	if n := len(rec.recorded()); n != 1 {
		t.Fatalf("got %d exec calls, want 1 — apply must not run after a failed init", n)
	}
}

func TestUseLockfileFlagFollowsBackend(t *testing.T) {
	for _, tc := range []struct {
		name     string
		lockfile bool
	}{{"r2_or_s3", true}, {"local", false}} {
		t.Run(tc.name, func(t *testing.T) {
			rec := &recordedExec{}
			e := newEnv(t, envOpts{
				repos:       []string{"infra"},
				maxParallel: 2,
				exec:        rec.fn,
				backend:     fakeBackend{lockfile: tc.lockfile},
			})
			m := e.seedRun(runs.Meta{Repo: "infra", Kind: contract.RunKindPlan, Status: contract.RunStatusRunning})
			if _, _, err := e.runJobFor(m); err != nil {
				t.Fatalf("runJob: %v", err)
			}
			got := hasArg(mustCalls(t, rec, 2)[0].Args, "-backend-config=use_lockfile=true")
			if got != tc.lockfile {
				t.Fatalf("use_lockfile flag present = %v, want %v", got, tc.lockfile)
			}
		})
	}
}

func TestRunJobStreamsOutputToRunLog(t *testing.T) {
	rec := &recordedExec{respond: func(_ int, spec ExecSpec) (ExecResult, error) {
		spec.Stdout("Plan: 1 to add")
		spec.Stderr("Warning: deprecated argument")
		return ExecResult{}, nil
	}}
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2, exec: rec.fn})
	m := e.seedRun(runs.Meta{Repo: "infra", Kind: contract.RunKindPlan, Status: contract.RunStatusRunning})
	if _, _, err := e.runJobFor(m); err != nil {
		t.Fatalf("runJob: %v", err)
	}

	page, err := e.store.ReadOutput(m.RunID, 1, 100)
	if err != nil {
		t.Fatalf("ReadOutput: %v", err)
	}
	joined := strings.Join(page.Lines, "\n")
	for _, want := range []string{"Plan: 1 to add", "Warning: deprecated argument"} {
		if !strings.Contains(joined, want) {
			t.Fatalf("output log = %q, want it to contain %q", joined, want)
		}
	}
	if page.TotalLines != 4 {
		t.Fatalf("total lines = %d, want 4 (two per exec call)", page.TotalLines)
	}
}

func TestDefaultExecCapturesBothStreams(t *testing.T) {
	var mu sync.Mutex
	var out, errLines []string
	res, err := DefaultExec(context.Background(), ExecSpec{
		Path: "/bin/sh",
		Args: []string{"-c", "echo out-one; echo out-two; echo err-one 1>&2"},
		Stdout: func(l string) {
			mu.Lock()
			out = append(out, l)
			mu.Unlock()
		},
		Stderr: func(l string) {
			mu.Lock()
			errLines = append(errLines, l)
			mu.Unlock()
		},
	})
	if err != nil {
		t.Fatalf("DefaultExec: %v", err)
	}
	if res.ExitCode != 0 || res.TimedOut {
		t.Fatalf("result = %+v, want exit 0 and no timeout", res)
	}
	mu.Lock()
	defer mu.Unlock()
	if strings.Join(out, ",") != "out-one,out-two" {
		t.Fatalf("stdout = %v, want both lines in order", out)
	}
	if strings.Join(errLines, ",") != "err-one" {
		t.Fatalf("stderr = %v, want err-one", errLines)
	}
}

func TestDefaultExecNonZeroExitIsNotAnError(t *testing.T) {
	res, err := DefaultExec(context.Background(), ExecSpec{
		Path:   "/bin/sh",
		Args:   []string{"-c", "exit 7"},
		Stdout: func(string) {},
		Stderr: func(string) {},
	})
	if err != nil {
		t.Fatalf("DefaultExec err = %v, want nil for a non-zero exit", err)
	}
	if res.ExitCode != 7 {
		t.Fatalf("exit code = %d, want 7", res.ExitCode)
	}
}

func TestDefaultExecStartFailureIsAnError(t *testing.T) {
	if _, err := DefaultExec(context.Background(), ExecSpec{
		Path:   "/nonexistent/definitely-not-a-binary",
		Stdout: func(string) {},
		Stderr: func(string) {},
	}); err == nil {
		t.Fatal("DefaultExec must return an error when the process cannot start")
	}
}

func TestDefaultExecTimeoutSendsSIGTERMThenSIGKILL(t *testing.T) {
	restore := killGrace
	killGrace = 400 * time.Millisecond
	defer func() { killGrace = restore }()

	ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
	defer cancel()

	start := time.Now()
	res, err := DefaultExec(ctx, ExecSpec{
		Path:   "/bin/sh",
		Args:   []string{"-c", `trap "" TERM; sleep 30`},
		Stdout: func(string) {},
		Stderr: func(string) {},
	})
	elapsed := time.Since(start)
	if err != nil {
		t.Fatalf("DefaultExec: %v", err)
	}
	if !res.TimedOut {
		t.Fatalf("result = %+v, want TimedOut", res)
	}
	if res.ExitCode == 0 {
		t.Fatal("a SIGKILLed process must not report exit code 0")
	}
	if elapsed > 5*time.Second {
		t.Fatalf("elapsed %v — the kill chain did not escalate", elapsed)
	}
}

func TestDefaultExecGracefulExitNotKilled(t *testing.T) {
	restore := killGrace
	killGrace = 2 * time.Second
	defer func() { killGrace = restore }()

	ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
	defer cancel()

	res, err := DefaultExec(ctx, ExecSpec{
		Path:   "/bin/sh",
		Args:   []string{"-c", `trap "exit 0" TERM; sleep 5 & wait`},
		Stdout: func(string) {},
		Stderr: func(string) {},
	})
	if err != nil {
		t.Fatalf("DefaultExec: %v", err)
	}
	if res.ExitCode != 0 {
		t.Fatalf("exit code = %d, want 0 — the process handled SIGTERM itself", res.ExitCode)
	}
	if !res.TimedOut {
		t.Fatalf("result = %+v, want TimedOut (the deadline still expired)", res)
	}
}

// TestApplyIgnoresPlanBuiltAgainstAnotherCommit is the CR-02
// data-integrity regression: a plan artifact describes ONE commit, so
// an apply issued after the working tree moved (POST
// /v1/repos/{name}/pull) must not hand tofu the pre-pull plan.
func TestApplyIgnoresPlanBuiltAgainstAnotherCommit(t *testing.T) {
	rec := &recordedExec{}
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2, exec: rec.fn})

	prior := e.seedRun(runs.Meta{
		Repo:      "infra",
		Dir:       "envs/prod",
		Kind:      contract.RunKindPlan,
		Status:    contract.RunStatusSucceeded,
		StartedAt: time.Now().UTC().Add(-time.Minute),
		// A commit the working tree is no longer on.
		HeadSHA: "1111111111111111111111111111111111111111",
	})
	priorPlan := filepath.Join(e.store.Dir(prior.RunID), "plan.tfplan")
	if err := os.WriteFile(priorPlan, []byte("binary plan"), 0o600); err != nil {
		t.Fatalf("write prior plan: %v", err)
	}
	if _, err := e.store.Update(prior.RunID, func(m *runs.Meta) error {
		m.PlanFile = priorPlan
		return nil
	}); err != nil {
		t.Fatalf("Update prior: %v", err)
	}

	apply := e.seedRun(runs.Meta{Repo: "infra", Dir: "envs/prod", Kind: contract.RunKindApply, Status: contract.RunStatusRunning})
	if _, _, err := e.runJobFor(apply); err != nil {
		t.Fatalf("runJob: %v", err)
	}

	args := mustCalls(t, rec, 2)[1].Args
	if last := args[len(args)-1]; !strings.HasPrefix(last, "-") {
		t.Fatalf("apply args = %v, want the inline form for a stale plan (CR-02)", args)
	}
	// The stale artifact is left alone: only a CONSUMED plan is
	// retired, and this one was never handed to tofu.
	if _, err := os.Stat(priorPlan); err != nil {
		t.Errorf("stale plan artifact was removed without being consumed: %v", err)
	}
}

// TestApplyIgnoresPlanWithNoRecordedHead covers the "freshness cannot
// be established" branch: a plan written before HeadSHA existed (or by
// a runner whose git could not answer rev-parse) is not eligible.
func TestApplyIgnoresPlanWithNoRecordedHead(t *testing.T) {
	rec := &recordedExec{}
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2, exec: rec.fn})

	prior := e.seedRun(runs.Meta{
		Repo:      "infra",
		Dir:       "envs/prod",
		Kind:      contract.RunKindPlan,
		Status:    contract.RunStatusSucceeded,
		StartedAt: time.Now().UTC().Add(-time.Minute),
	})
	priorPlan := filepath.Join(e.store.Dir(prior.RunID), "plan.tfplan")
	if err := os.WriteFile(priorPlan, []byte("binary plan"), 0o600); err != nil {
		t.Fatalf("write prior plan: %v", err)
	}
	if _, err := e.store.Update(prior.RunID, func(m *runs.Meta) error {
		m.PlanFile = priorPlan
		return nil
	}); err != nil {
		t.Fatalf("Update prior: %v", err)
	}

	apply := e.seedRun(runs.Meta{Repo: "infra", Dir: "envs/prod", Kind: contract.RunKindApply, Status: contract.RunStatusRunning})
	if _, _, err := e.runJobFor(apply); err != nil {
		t.Fatalf("runJob: %v", err)
	}
	args := mustCalls(t, rec, 2)[1].Args
	if last := args[len(args)-1]; !strings.HasPrefix(last, "-") {
		t.Fatalf("apply args = %v, want the inline form when freshness is unknown", args)
	}
}

// TestApplyConsumesPlanArtifact asserts the other half of CR-02: after
// a successful apply the artifact is gone and the plan run stops
// advertising it, so a second apply cannot be handed the same saved
// plan (which tofu would reject as stale).
func TestApplyConsumesPlanArtifact(t *testing.T) {
	rec := &recordedExec{}
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2, exec: rec.fn})

	prior := e.seedRun(runs.Meta{
		Repo:      "infra",
		Dir:       "envs/prod",
		Kind:      contract.RunKindPlan,
		Status:    contract.RunStatusSucceeded,
		StartedAt: time.Now().UTC().Add(-time.Minute),
		HeadSHA:   fixtureHeadSHA,
	})
	priorPlan := filepath.Join(e.store.Dir(prior.RunID), "plan.tfplan")
	if err := os.WriteFile(priorPlan, []byte("binary plan"), 0o600); err != nil {
		t.Fatalf("write prior plan: %v", err)
	}
	if _, err := e.store.Update(prior.RunID, func(m *runs.Meta) error {
		m.PlanFile = priorPlan
		return nil
	}); err != nil {
		t.Fatalf("Update prior: %v", err)
	}

	first := e.seedRun(runs.Meta{Repo: "infra", Dir: "envs/prod", Kind: contract.RunKindApply, Status: contract.RunStatusRunning})
	if _, _, err := e.runJobFor(first); err != nil {
		t.Fatalf("first runJob: %v", err)
	}
	args := mustCalls(t, rec, 2)[1].Args
	if args[len(args)-1] != priorPlan {
		t.Fatalf("first apply args = %v, want the artifact consumed (D-18)", args)
	}
	if _, err := os.Stat(priorPlan); !os.IsNotExist(err) {
		t.Errorf("consumed plan artifact still on disk: err = %v", err)
	}
	m, err := e.store.Load(prior.RunID)
	if err != nil {
		t.Fatalf("Load prior: %v", err)
	}
	if m.PlanFile != "" {
		t.Errorf("plan run still advertises plan_file = %q after consumption", m.PlanFile)
	}

	// A second apply with no intervening plan must go inline rather
	// than re-submitting a plan tofu has already applied.
	second := e.seedRun(runs.Meta{Repo: "infra", Dir: "envs/prod", Kind: contract.RunKindApply, Status: contract.RunStatusRunning})
	if _, _, err := e.runJobFor(second); err != nil {
		t.Fatalf("second runJob: %v", err)
	}
	args = mustCalls(t, rec, 4)[3].Args
	if last := args[len(args)-1]; !strings.HasPrefix(last, "-") {
		t.Fatalf("second apply args = %v, want the inline form (CR-02)", args)
	}
}

// TestPlanRecordsWorktreeHead asserts the freshness reference is
// actually written at plan time — the input every assertion above
// depends on.
func TestPlanRecordsWorktreeHead(t *testing.T) {
	rec := &recordedExec{}
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2, exec: rec.fn})
	m := e.seedRun(runs.Meta{Repo: "infra", Dir: "envs/prod", Kind: contract.RunKindPlan, Status: contract.RunStatusRunning})

	if _, _, err := e.runJobFor(m); err != nil {
		t.Fatalf("runJob: %v", err)
	}
	got, err := e.store.Load(m.RunID)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if got.HeadSHA != fixtureHeadSHA {
		t.Errorf("plan run head_sha = %q, want %q", got.HeadSHA, fixtureHeadSHA)
	}
}

// TestTofuChildEnvironmentIsAllowlisted is the CR-03 regression. tofu
// executes arbitrary operator IaC (providers, local-exec provisioners,
// external data sources), so the runner must hand it a built
// environment rather than its own: SUPERVISOR_TOKEN is injected into
// add-on containers and config.yaml sets homeassistant_api: true,
// which makes that token usable against the Core API.
func TestTofuChildEnvironmentIsAllowlisted(t *testing.T) {
	t.Setenv("SUPERVISOR_TOKEN", "supervisor-token-must-not-leak")
	t.Setenv("R2_SECRET_ACCESS_KEY", "r2-secret-must-not-leak")
	t.Setenv("TF_LOG", "DEBUG")

	rec := &recordedExec{}
	e := newEnv(t, envOpts{repos: []string{"infra"}, maxParallel: 2, exec: rec.fn})
	m := e.seedRun(runs.Meta{Repo: "infra", Dir: "envs/prod", Kind: contract.RunKindPlan, Status: contract.RunStatusRunning})
	if _, _, err := e.runJobFor(m); err != nil {
		t.Fatalf("runJob: %v", err)
	}

	for i, call := range mustCalls(t, rec, 2) {
		if len(call.Env) == 0 {
			t.Fatalf("call %d got an empty Env — nil would make os/exec inherit the parent environment", i)
		}
		for _, kv := range call.Env {
			for _, forbidden := range []string{"SUPERVISOR_TOKEN=", "R2_SECRET_ACCESS_KEY="} {
				if strings.HasPrefix(kv, forbidden) {
					t.Errorf("call %d leaked %s to the tofu child", i, strings.TrimSuffix(forbidden, "="))
				}
			}
		}
		if !hasEnvKey(call.Env, "PATH") {
			t.Errorf("call %d env = %v, want PATH (tofu resolves plugins and local-exec through it)", i, call.Env)
		}
		if !hasArg(call.Env, "TF_LOG=DEBUG") {
			t.Errorf("call %d env = %v, want the TF_* operator knobs passed through", i, call.Env)
		}
	}
}

func hasEnvKey(env []string, key string) bool {
	for _, kv := range env {
		if strings.HasPrefix(kv, key+"=") {
			return true
		}
	}
	return false
}

// lockedBuffer serializes writes so one slog handler can be shared
// with the goroutines DefaultExec starts.
type lockedBuffer struct {
	mu sync.Mutex
	b  bytes.Buffer
}

func (l *lockedBuffer) Write(p []byte) (int, error) {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.b.Write(p)
}

func (l *lockedBuffer) String() string {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.b.String()
}

// TestDefaultExecLongCommandJoinsCleanly is the WR-01 regression. The
// bounded join used to be armed right after Start, so every command
// that outlived killGrace — i.e. every real tofu init, plan and apply
// — took the timeout branch, logged a WARN, and voided the
// "join before Wait" guarantee on the normal path. The bound now
// starts when the process is already gone, so a slow-but-healthy
// command joins silently and keeps its tail output.
func TestDefaultExecLongCommandJoinsCleanly(t *testing.T) {
	restoreGrace := killGrace
	killGrace = 300 * time.Millisecond
	defer func() { killGrace = restoreGrace }()

	var buf lockedBuffer
	restoreLogger := slog.Default()
	slog.SetDefault(slog.New(slog.NewTextHandler(&buf, nil)))
	defer slog.SetDefault(restoreLogger)

	var mu sync.Mutex
	var out []string
	res, err := DefaultExec(context.Background(), ExecSpec{
		Path: "/bin/sh",
		// Runs ~3x killGrace, and prints AFTER the old bound would
		// have fired.
		Args: []string{"-c", "echo first; sleep 1; echo last"},
		Stdout: func(l string) {
			mu.Lock()
			out = append(out, l)
			mu.Unlock()
		},
		Stderr: func(string) {},
	})
	if err != nil {
		t.Fatalf("DefaultExec: %v", err)
	}
	if res.ExitCode != 0 || res.TimedOut {
		t.Fatalf("result = %+v, want a clean exit", res)
	}
	mu.Lock()
	got := strings.Join(out, ",")
	mu.Unlock()
	if got != "first,last" {
		t.Errorf("stdout = %q, want %q — the tail line was lost", got, "first,last")
	}
	if logged := buf.String(); strings.Contains(logged, "output_join_timeout") {
		t.Errorf("a healthy long command logged the join timeout:\n%s", logged)
	}
}
