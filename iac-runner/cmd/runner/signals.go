package main

// Signal-handling logic for the iac-runner binary. Extracted into its
// own file so the lifecycle (SIGTERM drain with a 30s deadline, SIGHUP
// log reopen) is testable in isolation and so the hot-path of
// cmd/runner/main.go stays focused on HTTP wiring.
//
// Phase 16 sets up the slots; Phase 02 will wrap slog.NewJSONHandler
// with the scrubbingHandler that the SIGHUP reopen cycle will rotate.

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"iac-runner/internal/jobq"
)

// shutdownDeadline is the maximum time the runner will spend draining
// in-flight HTTP requests after the first SIGTERM. A second SIGTERM
// during this window escalates to an immediate exit (defense-in-depth:
// a hung downstream call must not block shutdown indefinitely).
const shutdownDeadline = 30 * time.Second

// httpDrainBudget and queueDrainBudget split shutdownDeadline between
// the two things that have to finish before the process exits. The
// HTTP server drains first and gets the bulk of the window (the Phase
// 16 behavior for an HTTP-only workload is unchanged in practice —
// requests finish in milliseconds); jobq.Queue.Drain gets the
// remainder so an in-flight tofu process that is already exiting is
// waited for instead of orphaned.
//
// The two MUST sum to no more than shutdownDeadline: HA Supervisor
// SIGKILLs the container after its own grace window, and a split that
// overran the 30s budget would simply be truncated by the kernel with
// no shutdown_complete record written.
//
// A long apply that cannot finish inside queueDrainBudget is NOT
// killed here: it is already on its own death-clock via
// apply_timeout_minutes and the CONTEXT D-16 SIGTERM→SIGKILL chain
// inside the worker. This budget only bounds how long shutdown waits.
const (
	httpDrainBudget  = 25 * time.Second
	queueDrainBudget = 5 * time.Second
)

// HandleSignals blocks the calling goroutine until SIGTERM (or a fatal
// signal) arrives, then drains the HTTP server with a hard 30s deadline
// before returning. SIGHUP is observed as a log-reopen trigger only —
// the process never restarts.
//
// On a successful drain the function returns normally and main() should
// expect srv.ListenAndServe() to have returned http.ErrServerClosed. On
// a deadline-exceeded drain (or an impatient second SIGTERM during
// drain) the process exits with status 1 via os.Exit — log records are
// flushed by the deferred signal.Stop call below before the process
// terminates.
//
// Parameters:
//
//	ctx     — parent context for the shutdown deadline; typically
//	          context.Background() so a cancel from elsewhere does not
//	          interrupt the drain itself.
//	server  — the *http.Server to shut down gracefully.
//	logger  — structured JSON logger; every lifecycle event is recorded.
//	done    — optional channel closed when HandleSignals returns (used
//	          by main() to join the signal-handling goroutine).
//	queue   — the job queue whose in-flight tofu jobs are drained after
//	          the HTTP server stops accepting; nil is tolerated (the
//	          drain step is then skipped).
//	stopRetention — the stop function returned by
//	          runs.Store.StartRetentionTicker; nil is tolerated. Called
//	          before the queue drain so no rotation tick fires while
//	          jobs are still finishing.
func HandleSignals(
	ctx context.Context,
	server *http.Server,
	logger *slog.Logger,
	done chan<- struct{},
	queue *jobq.Queue,
	stopRetention func(),
) {
	sigCh := make(chan os.Signal, 2)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGHUP)
	defer signal.Stop(sigCh)

	if done != nil {
		defer close(done)
	}

	draining := false

	for sig := range sigCh {
		switch sig {
		case syscall.SIGHUP:
			// Phase 16: stdout-only logger — reopen is a no-op
			// except for the audit record. Phase 02 hooks file
			// rotation here.
			logger.Info("iac_runner.log_reopen", "signal", "SIGHUP")

		case syscall.SIGTERM:
			if draining {
				// Second SIGTERM during the drain — operator is
				// impatient or something is hung. Bail out now;
				// in-flight requests will be aborted by the
				// kernel as the process exits.
				logger.Warn("shutdown_escalated",
					"signal", "SIGTERM",
					"reason", "second SIGTERM during drain; exiting immediately",
				)
				os.Exit(1)
			}
			draining = true

			logger.Info("shutdown_initiated",
				"signal", "SIGTERM",
				"deadline_seconds", int(shutdownDeadline.Seconds()),
				"http_drain_seconds", int(httpDrainBudget.Seconds()),
				"queue_drain_seconds", int(queueDrainBudget.Seconds()),
			)

			shutdownCtx, cancel := context.WithTimeout(ctx, httpDrainBudget)
			err := server.Shutdown(shutdownCtx)
			cancel()
			if err != nil {
				logger.Error("shutdown_deadline_exceeded", "err", err.Error())
				os.Exit(1)
			}

			// Stop the retention ticker before the queue drain so no
			// rotation walks /data/runs while a job is still writing
			// into it. The stop function is sync.Once-guarded, so
			// main()'s belt-and-braces defer cannot double-close.
			if stopRetention != nil {
				stopRetention()
				logger.Info("runs_retention_stopped")
			}

			// Wait for in-flight tofu jobs. A deadline here is a
			// warning, not an exit(1): the HTTP surface is already
			// closed and the run's own timeout chain owns the
			// process, so escalating would only lose the
			// shutdown_complete record.
			if queue != nil {
				queueCtx, queueCancel := context.WithTimeout(ctx, queueDrainBudget)
				if err := queue.Drain(queueCtx); err != nil {
					logger.Warn("jobq_drain_deadline_exceeded", "err", err.Error())
				}
				queueCancel()
			}

			logger.Info("shutdown_complete")
			return

		default:
			logger.Warn("unexpected_signal", "signal", sig.String())
		}
	}
}
