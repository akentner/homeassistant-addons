package main

import (
	"context"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
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

	// Signal handling: SIGTERM drains in-flight requests with a 30s deadline;
	// SIGHUP reopens logs without restart.  HandleSignals owns the entire
	// lifecycle — see cmd/bridge/signals.go for the implementation and the
	// defense-in-depth second-SIGTERM-during-drain escalation.  OPS-02.
	//
	// Run in a goroutine so the call does not block ListenAndServe below:
	// HandleSignals blocks on the signal channel for the lifetime of the
	// process and would prevent the HTTP server from ever binding to :8124
	// if invoked inline.  signalsDone is closed when HandleSignals returns
	// (after a successful drain) so main can wait for the lifecycle audit
	// trail before exiting — otherwise the "shutdown_complete" log record
	// would race with process termination.
	signalsDone := make(chan struct{})
	go func() {
		defer close(signalsDone)
		HandleSignals(context.Background(), srv, logger)
	}()

	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		slog.Error("listen_error", "err", err.Error())
		os.Exit(1)
	}

	<-signalsDone
}
