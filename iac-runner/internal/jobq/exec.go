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
			// os.Environ() carries the backend credentials 17-07
			// exports (AWS_ACCESS_KEY_ID and friends) plus TF_* knobs.
			Env:    os.Environ(),
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
	case contract.RunKindApply:
		// RUN-03 + D-17/D-18.
		args = []string{
			"apply",
			"-no-color",
			"-input=false",
			"-auto-approve",
		}
		if prior := q.priorPlanFile(repo, cleanDir); prior != "" {
			args = append(args, prior)
		}
	default:
		return ExecResult{ExitCode: -1}, "", fmt.Errorf("jobq: unknown run kind %q", kind)
	}

	res, err = run(args)
	if err != nil {
		return res, "", err
	}
	return res, planFile, nil
}

// priorPlanFile implements D-18: the newest succeeded plan run for the
// same (repo, dir) whose artifact is still on disk, or "" for the D-17
// inline apply.
func (q *Queue) priorPlanFile(repo, cleanDir string) string {
	metas, err := q.store.List(runs.ListFilter{
		Repo:   repo,
		Status: contract.RunStatusSucceeded,
		Limit:  contract.MaxRunListLimit,
	})
	if err != nil {
		// Losing the lookup is not a reason to refuse the apply: D-17
		// inline apply is a legal mode, so degrade to it.
		slog.Warn("jobq.prior_plan_lookup_failed", "repo", repo, "err", err.Error())
		return ""
	}
	// List is already sorted newest-first, so the first match is the
	// most recent plan for this (repo, dir).
	for _, m := range metas {
		if m.Kind != contract.RunKindPlan || m.Dir != cleanDir || m.PlanFile == "" {
			continue
		}
		if _, err := os.Stat(m.PlanFile); err != nil {
			// D-18 fallback: retention already swept the artifact the
			// meta still names. Keep scanning — an older retained plan
			// is still better than none.
			continue
		}
		return m.PlanFile
	}
	return ""
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

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return ExecResult{ExitCode: -1}, fmt.Errorf("jobq: stdout pipe: %w", err)
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return ExecResult{ExitCode: -1}, fmt.Errorf("jobq: stderr pipe: %w", err)
	}

	if err := cmd.Start(); err != nil {
		return ExecResult{ExitCode: -1}, fmt.Errorf("jobq: start %s: %w", spec.Path, err)
	}

	var wg sync.WaitGroup
	wg.Add(2)
	go scanLines(&wg, stdout, spec.Stdout)
	go scanLines(&wg, stderr, spec.Stderr)

	// Join the scanners BEFORE cmd.Wait() so no line emitted just
	// before exit is lost — Wait closes the pipes, which would cut a
	// still-running scanner short.
	//
	// The join is BOUNDED, though: a killed shell can leave an
	// orphaned grandchild holding the pipe's write end, in which case
	// EOF never arrives and an unbounded join would hang the worker
	// forever (exactly the wedge the whole timeout chain exists to
	// prevent). After killGrace we hand over to Wait, whose own
	// WaitDelay closes the pipes and unblocks the scanners.
	scanned := make(chan struct{})
	go func() {
		wg.Wait()
		close(scanned)
	}()
	joinTimer := time.NewTimer(killGrace)
	select {
	case <-scanned:
	case <-joinTimer.C:
		slog.Warn("jobq.output_join_timeout", "path", spec.Path)
	}
	joinTimer.Stop()

	// Wait's error is deliberately not propagated: a non-zero exit, a
	// signal death and a post-cancel exit all arrive here, and
	// ProcessState carries the only fact the caller needs.
	waitErr := cmd.Wait()

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
