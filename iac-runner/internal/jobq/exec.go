package jobq

// Placeholder for Task 2. runJob builds the RUN-02/RUN-03 tofu command
// sequences and DefaultExec is the os/exec implementation with the D-16
// SIGTERM->SIGKILL kill-chain. Task 1 needs both to exist so the queue
// lifecycle compiles and is testable through an injected ExecFunc; the
// real bodies land in the next commit.

import (
	"context"
	"errors"
	"time"

	"iac-runner/internal/contract"
	"iac-runner/internal/runs"
)

// killGrace is the D-16 grace window between SIGTERM and SIGKILL. It
// is a var, not a const, purely so the kill-chain tests can shrink it;
// the production value is 10 * time.Second.
var killGrace = 10 * time.Second

// runJob executes one job's command sequence. Task 1 seam: a single
// exec call whose result drives the terminal state. Task 2 replaces
// the body with init + plan/apply, the prior-plan lookup and the
// deadline.
func (q *Queue) runJob(runID, repo, cleanDir string, kind contract.RunKind, w *runs.OutputWriter) (ExecResult, string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), q.applyTimeout)
	defer cancel()
	res, err := q.exec(ctx, ExecSpec{
		Path:   q.tofuPath,
		Args:   nil,
		Stdout: func(line string) { _ = w.WriteLine("stdout", line) },
		Stderr: func(line string) { _ = w.WriteLine("stderr", line) },
	})
	return res, "", err
}

// DefaultExec is the production os/exec implementation. Task 2 replaces
// this placeholder with the real SIGTERM->SIGKILL kill-chain.
func DefaultExec(ctx context.Context, spec ExecSpec) (ExecResult, error) {
	return ExecResult{}, errors.New("jobq: DefaultExec not implemented")
}
