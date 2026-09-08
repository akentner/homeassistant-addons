package jobq

// tofu invocation: the RUN-02 / RUN-03 command lines, the D-15/D-16
// timeout kill-chain, the D-17/D-18 plan-artifact lifecycle, and the
// line-by-line output capture that makes a running job observable
// through GET /v1/runs/{id} (OBS-02).
//
// Every command goes through Queue.exec (an ExecFunc), so the command
// lines and the short-circuit semantics are provable with no tofu
// binary; DefaultExec is the only place in the runner that spawns a
// tofu process.

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"time"

	"iac-runner/internal/contract"
	"iac-runner/internal/runs"
)

// killGrace is the D-16 grace window between SIGTERM and SIGKILL. It
// is a var, not a const, purely so the kill-chain tests can shrink it;
// the production value is 10 * time.Second and must not be weakened.
var killGrace = 10 * time.Second

// planFileName is the plan artifact inside the run directory. Keeping
// it under /data/runs/{run_id}/ means retention rotation reclaims the
// artifact together with the output log — no second lifecycle to get
// wrong.
const planFileName = "plan.tfplan"

// initialScanBufBytes / maxScanLineBytes mirror internal/runs/output.go:
// a tofu plan can emit a single multi-megabyte line (a large
// resource diff), and D-09/D-24 forbid truncating it.
const (
	initialScanBufBytes = 64 * 1024
	maxScanLineBytes    = 8 * 1024 * 1024
)

// tofuEnvKeep is the allowlist of environment variables a tofu child
// receives by name. Everything else is dropped.
//
//   - PATH   — tofu resolves provider plugins and any local-exec shell.
//   - HOME   — the plugin cache and CLI config live under it.
//   - TMPDIR — provider downloads and plan serialization need scratch.
//   - LANG / LC_ALL / TZ — output formatting only.
//
// Nothing else is required. In particular the HA base image needs no
// SSL_CERT_* to reach the provider registry: Go uses the system trust
// store at /etc/ssl/certs.
var tofuEnvKeep = []string{"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "TZ"}

// tofuEnvPrefixes are the operator-facing knob namespaces that are
// passed through wholesale. They are tofu's own documented
// configuration surface, and none of them is injected by the
// Supervisor.
var tofuEnvPrefixes = []string{"TF_", "TOFU_"}

// tofuEnv builds the ONLY environment a tofu child receives.
//
// Inheriting os.Environ() handed the whole add-on container
// environment to `tofu`, and `tofu` executes arbitrary operator IaC:
// providers downloaded from a registry, local-exec provisioners,
// external data sources. Everything in the runner's environment was
// readable by all of them — including SUPERVISOR_TOKEN, which the
// Supervisor injects and which config.yaml's `homeassistant_api: true`
// makes usable against http://supervisor/core/api for state writes and
// service calls. The runner's own posture (bearer auth, Tailscale
// bind-gate, chmod-600 key enforcement) cannot survive handing a Home
// Assistant API credential to code the runner does not control.
//
// NOTE: no backend credential projection exists yet. The r2/s3
// AWS_ACCESS_KEY_ID-style variables are NOT set anywhere in this
// repository (deferred to Phase 19 — see the phase 17
// deferred-items.md), so `tofu init` against r2/s3 authenticates only
// if the operator's own IaC supplies credentials another way. When
// that projection lands it appends to this slice rather than
// reintroducing inheritance.
func tofuEnv() []string {
	env := make([]string, 0, len(tofuEnvKeep)+8)
	for _, k := range tofuEnvKeep {
		if v, ok := os.LookupEnv(k); ok {
			env = append(env, k+"="+v)
		}
	}
	for _, kv := range os.Environ() {
		for _, prefix := range tofuEnvPrefixes {
			if strings.HasPrefix(kv, prefix) {
				env = append(env, kv)
				break
			}
		}
	}
	return env
}

// runJob executes one job's full command sequence and returns the
// outcome plus the plan-artifact path (empty for an apply).
//
// One deadline covers the WHOLE sequence (init + plan, or init +
// apply): apply_timeout_minutes is a budget for the job, not for each
// process, and a per-process deadline would let a slow init plus a
// slow apply together exceed the operator's configured bound. Plans
// reuse the same value per CONTEXT — the terminal mapping in
// Queue.finish reports plan_timeout for a plan and apply_timeout for
// an apply, so the two paths stay distinguishable without a second
// Options field.
func (q *Queue) runJob(runID, repo, cleanDir string, kind contract.RunKind, w *runs.OutputWriter) (ExecResult, string, error) {
	// cleanDir came out of runs.ValidateDir (D-21), so it can neither
	// be absolute nor contain a ".." segment; the empty string legally
	// means the repo root (D-23) and filepath.Join handles that on its
	// own. No redundant guard here on purpose.
	workDir := filepath.Join(q.git.WorkTree(repo), cleanDir)

	timeout := q.applyTimeout
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	// A write failure must NOT abort a running apply — a full disk is a
	// reason to lose log lines, not a reason to abandon half-applied
	// infrastructure. The sync.Once keeps a broken writer from emitting
	// one log record per captured line.
	var writeFailed sync.Once
	record := func(err error) {
		if err == nil {
			return
		}
		writeFailed.Do(func() {
			slog.Warn("jobq.output_write_failed", "run_id", runID, "err", err.Error())
		})
	}

	run := func(args []string) (ExecResult, error) {
		return q.exec(ctx, ExecSpec{
			Path:    q.tofuPath,
			WorkDir: workDir,
			Args:    args,
			// An explicit allowlist, never os.Environ() — see tofuEnv.
			Env:    tofuEnv(),
			Stdout: func(line string) { record(w.WriteLine("stdout", line)) },
			Stderr: func(line string) { record(w.WriteLine("stderr", line)) },
		})
	}

	// RUN-02 / RUN-03: init always runs first. -input=false is
	// mandatory — a tofu that decides to prompt inside a container
	// with no TTY would hang until the apply timeout fires.
	initArgs := []string{"init", "-input=false", "-no-color"}
	if q.backend != nil && q.backend.UseLockfile() {
		// STBK: r2/s3 use native S3 object locking; local uses a file
		// lock and must NOT get this flag.
		initArgs = append(initArgs, "-backend-config=use_lockfile=true")
	}

	res, err := run(initArgs)
	if err != nil {
		return res, "", err
	}
	// A failed init short-circuits: running plan/apply against an
	// uninitialized directory would only produce a second, more
	// confusing error, and the operator needs init's exit code.
	if res.ExitCode != 0 || res.TimedOut {
		return res, "", nil
	}

	var planFile string
	var args []string
	// prior/priorRunID are the D-18 artifact this apply consumes, if
	// any. They are needed after the process returns, which is why
	// they live outside the switch.
	var prior, priorRunID string
	switch kind {
	case contract.RunKindPlan:
		// RUN-02: the artifact lands inside the run directory so
		// retention rotation reclaims it together with the output log.
		planFile = filepath.Join(q.store.Dir(runID), planFileName)
		args = []string{
			"plan",
			"-no-color",
			"-input=false",
			"-out=" + planFile,
		}
		// D-18 freshness reference: a saved plan is only valid for the
		// commit it was built against, so record that commit now. An
		// apply compares it against the working tree's HEAD and
		// refuses a plan that predates a pull (CR-02).
		q.recordPlanHead(ctx, runID, repo)
	case contract.RunKindApply:
		// RUN-03 + D-17/D-18.
		args = []string{
			"apply",
			"-no-color",
			"-input=false",
			"-auto-approve",
		}
		prior, priorRunID = q.priorPlanFile(ctx, repo, cleanDir)
		if prior != "" {
			args = append(args, prior)
		}
	default:
		return ExecResult{ExitCode: -1}, "", fmt.Errorf("jobq: unknown run kind %q", kind)
	}

	res, err = run(args)
	if err != nil {
		return res, "", err
	}
	if prior != "" && res.ExitCode == 0 && !res.TimedOut {
		// D-18 consumption. tofu has applied the saved plan, so the
		// artifact now describes state that no longer exists: handing
		// it to a second apply gets it rejected as stale, which is how
		// /v1/apply became non-idempotent for a reason no error
		// message here could explain.
		q.consumePlanArtifact(priorRunID, prior)
	}
	return res, planFile, nil
}

// recordPlanHead stores the repo HEAD this plan is being built against
// in the plan run's meta. A failure is logged and tolerated: the
// consequence is a later apply that cannot establish freshness and
// therefore falls back to an inline apply — the safe direction.
func (q *Queue) recordPlanHead(ctx context.Context, runID, repo string) {
	head := q.git.Head(ctx, repo)
	if head == "" {
		slog.Warn("jobq.plan_head_unknown", "run_id", runID, "repo", repo)
		return
	}
	if _, err := q.store.Update(runID, func(m *runs.Meta) error {
		m.HeadSHA = head
		return nil
	}); err != nil {
		slog.Warn("jobq.plan_head_record_failed", "run_id", runID, "repo", repo, "err", err.Error())
	}
}

// priorPlanFile implements D-18: the newest succeeded plan run for the
// same (repo, dir) whose artifact is still on disk AND was built
// against the commit the working tree is on now. It returns the
// artifact path plus the run id that owns it, or ("", "") for the D-17
// inline apply.
//
// The freshness gate is the whole point. Without it a
// POST /v1/repos/{name}/pull between plan and apply hands tofu a plan
// built against the PRE-PULL commit: OpenTofu applies the saved plan,
// so the operator gets the previous revision's changes and no signal
// that their pull was ignored. When freshness cannot be established at
// all — git could not answer, or the plan predates this field — the
// artifact is skipped, because an inline apply is a supported D-17
// mode and is the only safe default.
func (q *Queue) priorPlanFile(ctx context.Context, repo, cleanDir string) (string, string) {
	metas, err := q.store.List(runs.ListFilter{
		Repo:   repo,
		Status: contract.RunStatusSucceeded,
		Kind:   contract.RunKindPlan,
		Dir:    cleanDir,
		DirSet: true,
		Limit:  1,
	})
	if err != nil {
		// Losing the lookup is not a reason to refuse the apply: D-17
		// inline apply is a legal mode, so degrade to it.
		slog.Warn("jobq.prior_plan_lookup_failed", "repo", repo, "err", err.Error())
		return "", ""
	}
	head := q.git.Head(ctx, repo)
	if head == "" {
		slog.Warn("jobq.plan_freshness_unknown", "repo", repo, "dir", cleanDir)
		return "", ""
	}
	// List is already sorted newest-first, so the first match is the
	// most recent plan for this (repo, dir).
	for _, m := range metas {
		if m.PlanFile == "" {
			continue
		}
		if m.HeadSHA != head {
			slog.Info("jobq.plan_artifact_stale",
				"repo", repo, "dir", cleanDir, "plan_run_id", m.RunID,
				"plan_head", m.HeadSHA, "worktree_head", head)
			continue
		}
		if _, err := os.Stat(m.PlanFile); err != nil {
			// D-18 fallback: retention already swept the artifact the
			// meta still names. Keep scanning — an older retained plan
			// is still better than none.
			continue
		}
		return m.PlanFile, m.RunID
	}
	return "", ""
}

// consumePlanArtifact retires a plan artifact an apply just used: the
// file goes, and the owning plan run stops advertising it so
// priorPlanFile cannot find it again.
//
// Both failures are logged and tolerated — the apply itself already
// succeeded, and refusing to report that because a cleanup step failed
// would be a lie about the infrastructure.
func (q *Queue) consumePlanArtifact(planRunID, path string) {
	if err := os.Remove(path); err != nil && !errors.Is(err, os.ErrNotExist) {
		slog.Warn("jobq.plan_artifact_remove_failed", "path", path, "err", err.Error())
	}
	if planRunID == "" {
		return
	}
	if _, err := q.store.Update(planRunID, func(m *runs.Meta) error {
		m.PlanFile = ""
		return nil
	}); err != nil {
		slog.Warn("jobq.plan_artifact_clear_failed", "run_id", planRunID, "err", err.Error())
	}
}

// DefaultExec is the production os/exec implementation and the only
// place in the runner that starts a tofu process.
//
// A non-zero exit is DATA, not a Go error: the error return is
// reserved for "the process could not be started at all" (a missing
// binary, an unusable working directory), mirroring
// git.DefaultCommandRunner.
func DefaultExec(ctx context.Context, spec ExecSpec) (ExecResult, error) {
	if spec.Path == "" {
		return ExecResult{ExitCode: -1}, errors.New("jobq: DefaultExec requires a binary path")
	}

	cmd := exec.CommandContext(ctx, spec.Path, spec.Args...)
	cmd.Dir = spec.WorkDir
	cmd.Env = spec.Env

	// CONTEXT D-16: at deadline expiry send SIGTERM, not SIGKILL, so
	// tofu can release its state lock (an S3 DELETE for r2/s3, an
	// unlink for local). WaitDelay escalates to SIGKILL killGrace
	// later if the process ignores the signal. Without Cancel,
	// CommandContext would SIGKILL immediately and leave the remote
	// state lock held — the next apply would then fail on a stale
	// lock that no operator asked for.
	cmd.Cancel = func() error { return cmd.Process.Signal(syscall.SIGTERM) }
	cmd.WaitDelay = killGrace

	// os.Pipe rather than cmd.StdoutPipe/StderrPipe, and the reason is
	// the ORDERING of the join against cmd.Wait().
	//
	// Wait() closes the pipes StdoutPipe created, which cuts a
	// still-running scanner short — so with those the scanners have to
	// be joined BEFORE Wait. But that join must be bounded (an
	// orphaned grandchild can hold the write end open forever), and a
	// bound armed before the process has even exited fires on every
	// command that runs longer than it: every real tofu init, plan and
	// apply. The result was a WARN per invocation plus a guarantee
	// that did not hold on the normal path.
	//
	// A pipe the runner owns is not touched by Wait, so the process
	// can be reaped FIRST and the scanners joined afterwards, when a
	// bound finally means what it says.
	outR, outW, err := os.Pipe()
	if err != nil {
		return ExecResult{ExitCode: -1}, fmt.Errorf("jobq: stdout pipe: %w", err)
	}
	defer outR.Close()
	errR, errW, err := os.Pipe()
	if err != nil {
		outW.Close()
		return ExecResult{ExitCode: -1}, fmt.Errorf("jobq: stderr pipe: %w", err)
	}
	defer errR.Close()
	cmd.Stdout = outW
	cmd.Stderr = errW

	if err := cmd.Start(); err != nil {
		outW.Close()
		errW.Close()
		return ExecResult{ExitCode: -1}, fmt.Errorf("jobq: start %s: %w", spec.Path, err)
	}
	// The child holds its own copies of the write ends now. The parent
	// MUST drop its copies or the reads below never see EOF.
	outW.Close()
	errW.Close()

	var wg sync.WaitGroup
	wg.Add(2)
	go scanLines(&wg, outR, spec.Stdout)
	go scanLines(&wg, errR, spec.Stderr)

	scanned := make(chan struct{})
	go func() {
		wg.Wait()
		close(scanned)
	}()

	// Wait's error is deliberately not propagated: a non-zero exit, a
	// signal death and a post-cancel exit all arrive here, and
	// ProcessState carries the only fact the caller needs.
	waitErr := cmd.Wait()

	// The process is gone, so EOF is imminent — unless a grandchild
	// inherited the write end, which is the wedge the whole timeout
	// chain exists to prevent. Bound the join from HERE, and on expiry
	// close the read ends: that is what unblocks the scanners, so the
	// join afterwards is guaranteed to complete and no goroutine
	// outlives this call.
	joinTimer := time.NewTimer(killGrace)
	defer joinTimer.Stop()
	select {
	case <-scanned:
	case <-joinTimer.C:
		slog.Warn("jobq.output_join_timeout", "path", spec.Path)
		outR.Close()
		errR.Close()
		<-scanned
	}

	res := ExecResult{
		ExitCode: -1,
		TimedOut: errors.Is(ctx.Err(), context.DeadlineExceeded),
	}
	if cmd.ProcessState != nil {
		res.ExitCode = cmd.ProcessState.ExitCode()
	} else {
		var exitErr *exec.ExitError
		if errors.As(waitErr, &exitErr) {
			res.ExitCode = exitErr.ExitCode()
		}
	}
	return res, nil
}

// scanLines feeds one pipe to emit, one line at a time. The buffer is
// enlarged the same way internal/runs/output.go does, because a tofu
// plan can print a single very long line and D-09/D-24 forbid
// truncating it.
func scanLines(wg *sync.WaitGroup, r io.Reader, emit func(string)) {
	defer wg.Done()
	if emit == nil {
		// Drain anyway: an unread pipe would block the process once
		// its buffer filled.
		_, _ = io.Copy(io.Discard, r)
		return
	}
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 0, initialScanBufBytes), maxScanLineBytes)
	for sc.Scan() {
		emit(sc.Text())
	}
	if err := sc.Err(); err != nil && !errors.Is(err, os.ErrClosed) {
		// A scan error is not fatal to the run: the process outcome is
		// what decides success, and losing tail output is strictly
		// better than failing an apply that already succeeded.
		emit(fmt.Sprintf("[iac-runner] output capture stopped: %v", err))
	}
}
