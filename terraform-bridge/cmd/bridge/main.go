package main

import (
	"context"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"terraform-bridge/internal/httpapi"
)

func main() {
	// CLI flag: -version prints the embedded bridge version and exits 0.
	// Used by build verification, smoke tests, and operators double-checking
	// which binary is running inside the Supervisor container.
	version := flag.Bool("version", false, "print bridge version and exit")
	flag.Parse()

	if *version {
		fmt.Fprintln(os.Stdout, bridgeVersion) //nolint:forbidigo // intentional stdout write for CLI
		return
	}

	// Structured JSON logging via stdlib log/slog (Phase 9 baseline).
	// Phase 10 OPS-01 extends this with request_id / route / method / status /
	// duration_ms via chi middleware.
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	slog.Info("starting",
		"bridge_version", bridgeVersion,
		"pid", os.Getpid(),
	)

	// HTTP router (chi v5) wired with the single Phase 9 endpoint.
	// Plan 03 binds the listener to a Tailscale-only address; Phase 9 binds
	// to :8124 (any) because Tailscale interface detection lands in Phase 10.
	router := httpapi.NewRouter(bridgeVersion)

	srv := &http.Server{
		Addr:              ":8124",
		Handler:           router,
		ReadHeaderTimeout: 5 * time.Second,
	}

	// SIGTERM drains in-flight requests for up to 30s then exits; SIGHUP
	// is accepted (no-op in Phase 9 — log reopen lands in Plan 03). Plan 03
	// extends this further with token-rotation tracking and the hard 30s
	// shutdown deadline.
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGHUP)
	defer stop()

	go func() {
		<-ctx.Done()
		slog.Info("shutdown_signal_received", "cause", ctx.Err())

		shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()

		if err := srv.Shutdown(shutdownCtx); err != nil {
			slog.Error("shutdown_error", "err", err.Error())
		}
	}()

	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		slog.Error("listen_error", "err", err.Error())
		os.Exit(1)
	}
}