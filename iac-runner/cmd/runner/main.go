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

	"iac-runner/internal/auth"
	"iac-runner/internal/httpapi"
)

// defaultStateBackend mirrors REQUIREMENTS.md STBK-01 — the
// recommended state backend that the runner defaults to when
// /data/options.json is missing or unset. Operator-editable via the
// HA Options UI; the schema-validated field lands in /data/options.json
// with state_backend: list(match(^(r2|s3|local)$)).
var defaultStateBackend = "r2"

// options is the subset of /data/options.json the runner reads at
// startup. BindAddress defaults to "auto" (Tailscale detection);
// BindAllowedSubnets defaults to [] (strict refusal of non-Tailscale
// IPs). Plan 02 extends with the state-backend credentials fields.
//
// BindAllowedSubnets is a []string — the HA Supervisor schema DSL uses
// the YAML-list form (`- "str?"`) for lists of arbitrary strings, NOT
// the string `list(str)?` form, which Supervisor parses as a one-value
// enum.
type options struct {
	BindAddress        string   `json:"bind_address"`
	BindAllowedSubnets []string `json:"bind_allowed_subnets"`
	StateBackend       string   `json:"state_backend"`
	R2Bucket           string   `json:"r2_bucket"`
	S3Endpoint         string   `json:"s3_endpoint"`
	S3Bucket           string   `json:"s3_bucket"`
	S3Region           string   `json:"s3_region"`
}

func main() {
	version := flag.Bool("version", false, "print runner version and exit")
	flag.Parse()

	if *version {
		fmt.Fprintln(os.Stdout, runnerVersion) //nolint:forbidigo // intentional stdout write for CLI
		return
	}

	// Structured JSON logging via stdlib log/slog. Phase 16 ships
	// the unwrapped baseline; Plan 02 wraps slog.NewJSONHandler with
	// the scrubbingHandler (SEC-02).
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	// Read add-on options from /data/options.json (HA add-on store).
	opts := options{
		BindAddress:        "auto",
		BindAllowedSubnets: []string{},
		StateBackend:       defaultStateBackend,
		R2Bucket:           "",
		S3Endpoint:         "",
		S3Bucket:           "",
		S3Region:           "",
	}
	if b, err := os.ReadFile("/data/options.json"); err == nil {
		_ = json.Unmarshal(b, &opts) // fall back to defaults on parse failure
	} else if !os.IsNotExist(err) {
		slog.Error("options_read_failed", "err", err.Error())
	}

	// Resolve the bind address. Refusal is fatal — no degraded
	// mode (AGENTS.md Live Systems rule).
	bindIP, err := auth.ResolveBindAddress(opts.BindAddress, opts.BindAllowedSubnets, "/sys/class/net", nil)
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
		// First start: generate + persist + write the plaintext to
		// a chmod-600 file so the operator can configure their
		// client without the plaintext ever passing through a log
		// stream. The log record carries a 3+3-char preview
		// (Truncate) and the file path; subsequent restarts do NOT
		// re-emit either.
		token, err := store.Generate()
		if err != nil {
			slog.Error("token_generate_failed", "err", err.Error())
			os.Exit(1)
		}
		if err := store.Persist(token); err != nil {
			slog.Error("token_persist_failed", "err", err.Error())
			os.Exit(1)
		}
		path, err := store.WriteInitialTokenFile(token)
		if err != nil {
			slog.Error("token_file_write_failed", "err", err.Error())
			os.Exit(1)
		}
		slog.Info("iac_runner.token.issued",
			"actor_token_fp", auth.Fingerprint(token),
			"preview", auth.Truncate(token), // 3...3 of 43 chars
			"path", path, // /data/initial-iac-runner-token — chmod 600
		)
	} else {
		slog.Info("iac_runner.token.loaded", "actor_token_fp", auth.HashFingerprint(store.Hash()))
	}

	logger.Info("starting",
		"runner_version", runnerVersion,
		"pid", os.Getpid(),
		"state_backend", opts.StateBackend,
	)

	// Build the router — pass store so the auth middleware can
	// validate.
	router := httpapi.NewRouter(runnerVersion, store)

	srv := &http.Server{
		Addr:              bindIP + ":8125",
		Handler:           router,
		ReadHeaderTimeout: 5 * time.Second,
	}

	// Signal handling — HandleSignals owns the lifecycle.
	signalsDone := make(chan struct{})
	go HandleSignals(context.Background(), srv, logger, signalsDone)

	logger.Info("listening", "bind_address", bindIP+":8125")

	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		slog.Error("listen_error", "err", err.Error())
		os.Exit(1)
	}

	<-signalsDone
}
