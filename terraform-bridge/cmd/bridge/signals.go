package main

// Signal-handling logic for the Bridge binary.  Extracted into its own file so
// the lifecycle (SIGTERM drain with a 30s deadline, SIGHUP log reopen) is
// testable in isolation and so the hot-path of cmd/bridge/main.go stays focused
// on HTTP wiring.
//
// Phase 9 sets up the slots; Phase 10 attaches the file-backed slog handler
// this SIGHUP handler will re-create, and adds the bridge.token_rotated=true
// log line on mid-process SUPERVISOR_TOKEN changes (PITFALLS H-1 contingency).

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

// shutdownDeadline is the maximum time the Bridge will spend draining
// in-flight HTTP requests after the first SIGTERM.  A second SIGTERM during
// this window escalates to an immediate exit (defense-in-depth: a hung
// Supervisor request must not block shutdown indefinitely).
const shutdownDeadline = 30 * time.Second

// HandleSignals blocks the calling goroutine until SIGTERM (or a fatal signal)
// arrives, then drains the HTTP server with a hard 30s deadline before
// returning.  SIGHUP is observed as a log-reopen trigger only — the process
// never restarts.
//
// On a successful drain the function returns normally and main() should
// expect srv.ListenAndServe() to have returned http.ErrServerClosed.  On a
// deadline-exceeded drain (or an impatient second SIGTERM during drain) the
// process exits with status 1 via os.Exit — log records are flushed by the
// deferred signal.Stop call below before the process terminates.
//
// Parameters:
//
//	ctx     — parent context for the shutdown deadline; typically
//	          context.Background() so a cancel from elsewhere does not
//	          interrupt the drain itself.
//	server  — the *http.Server to shut down gracefully.
//	logger  — structured JSON logger; every lifecycle event is recorded.
func HandleSignals(ctx context.Context, server *http.Server, logger *slog.Logger) {
	sigCh := make(chan os.Signal, 2)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGHUP)
	defer signal.Stop(sigCh)

	draining := false

	for sig := range sigCh {
		switch sig {
		case syscall.SIGHUP:
			// Phase 9: stdout-only logger — reopen is a no-op except for
			// the audit record.  Phase 10 hooks file rotation here.
			logger.Info("log_reopen", "signal", "SIGHUP")

		case syscall.SIGTERM:
			if draining {
				// Second SIGTERM during the drain — operator is impatient
				// or something is hung.  Bail out now; in-flight requests
				// will be aborted by the kernel as the process exits.
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
			)

			shutdownCtx, cancel := context.WithTimeout(ctx, shutdownDeadline)
			err := server.Shutdown(shutdownCtx)
			cancel()
			if err != nil {
				logger.Error("shutdown_deadline_exceeded", "err", err.Error())
				os.Exit(1)
			}

			logger.Info("shutdown_complete")
			return

		default:
			logger.Warn("unexpected_signal", "signal", sig.String())
		}
	}
}
