package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"time"

	"terraform-bridge/internal/auth"
	"terraform-bridge/internal/httpapi"
	"terraform-bridge/internal/logging"
	"terraform-bridge/internal/supervisor"
)

// options is the subset of /data/options.json the Bridge reads at
// startup. BindAddress defaults to "auto" (Tailscale detection);
// BindAllowedSubnets defaults to [] (strict refusal of non-Tailscale
// IPs).
//
// BindAllowedSubnets is a []string — the HA Supervisor schema DSL uses
// the YAML-list form (`- "str?"`) for lists of arbitrary strings, NOT
// the string `list(str)?` form, which Supervisor parses as a one-value
// enum. See supervisor/apps/options.py:106 (isinstance(typ, list)
// → _nested_validate_list branch) vs :163 (string `list(<inner>)`
// → vol.In(<inner>.split("|")) enum branch).
type options struct {
	BindAddress        string   `json:"bind_address"`
	BindAllowedSubnets []string `json:"bind_allowed_subnets"`
}

func main() {
	version := flag.Bool("version", false, "print bridge version and exit")
	flag.Parse()

	if *version {
		fmt.Fprintln(os.Stdout, bridgeVersion) //nolint:forbidigo // intentional stdout write for CLI
		return
	}

	// Structured JSON logging via stdlib log/slog (Phase 9 baseline).
	// Plan 02 wraps this with a scrubbingHandler that masks sensitive
	// keys before serialization.
	logger := slog.New(logging.NewScrubbingHandler(slog.NewJSONHandler(os.Stdout, nil)))
	slog.SetDefault(logger)

	// Read add-on options from /data/options.json (HA add-on store).
	opts := options{BindAddress: "auto", BindAllowedSubnets: []string{}}
	if b, err := os.ReadFile("/data/options.json"); err == nil {
		_ = json.Unmarshal(b, &opts) // fall back to defaults on parse failure
	} else if !os.IsNotExist(err) {
		slog.Error("options_read_failed", "err", err.Error())
	}

	// Resolve the bind address (D-04..D-06). Refusal is fatal — no
	// degraded mode (AGENTS.md Live Systems rule).
	bindIP, err := auth.ResolveBindAddress(opts.BindAddress, opts.BindAllowedSubnets, "/sys/class/net")
	if err != nil {
		slog.Error("bind_resolution_failed",
			"bind_address", opts.BindAddress,
			"err", err.Error(),
		)
		os.Exit(1)
	}
	slog.Info("bind_resolved",
		"bind_address", opts.BindAddress,
		"bind_ip", bindIP,
		"allowed_subnets", opts.BindAllowedSubnets,
	)

	// TokenStore — load from /data or generate on first start.
	store, err := auth.NewFileTokenStore("/data")
	if err != nil {
		slog.Error("token_store_init_failed", "err", err.Error())
		os.Exit(1)
	}
	if store.Hash() == nil {
		// First start: generate + persist + log exactly once.
		token, err := store.Generate()
		if err != nil {
			slog.Error("token_generate_failed", "err", err.Error())
			os.Exit(1)
		}
		if err := store.Persist(token); err != nil {
			slog.Error("token_persist_failed", "err", err.Error())
			os.Exit(1)
		}
		// CF-02: plaintext surfaces exactly once in this single log
		// record. Subsequent restarts do NOT re-surface.
		slog.Info("bridge.token.issued",
			"actor_token_fp", auth.Fingerprint(token),
			"plaintext", token, // single emission, never repeated
		)
	} else {
		slog.Info("bridge.token.loaded", "actor_token_fp", auth.HashFingerprint(store.Hash()))
	}

	// Supervisor HTTP client (Plan 02's /healthz uses it).
	supClient := supervisor.NewClient(supervisor.ReadSupervisorToken)

	logger.Info("starting",
		"bridge_version", bridgeVersion,
		"pid", os.Getpid(),
	)

	// Build the router — pass store so the auth middleware can validate.
	router := httpapi.NewRouter(bridgeVersion, store, supClient)

	srv := &http.Server{
		Addr:              bindIP + ":8124",
		Handler:           router,
		ReadHeaderTimeout: 5 * time.Second,
	}

	// Signal handling — Phase 9's HandleSignals owns the lifecycle.
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
