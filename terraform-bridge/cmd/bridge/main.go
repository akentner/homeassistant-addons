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
	"terraform-bridge/internal/mutex"
	"terraform-bridge/internal/nonce"
	"terraform-bridge/internal/supervisor"
)

// stateFilePath is the absolute filesystem path of the OpenTofu state
// file the Bridge manages. Phase 1 hardcodes /data/terraform.tfstate
// per PROJECT.md architecture decision; BRIDGE-10 surfaces this in the
// /v1/info response body so operator automation can locate it without
// out-of-band configuration. Phase 12 may add a state index endpoint
// that uses the same path.
const stateFilePath = "/data/terraform.tfstate"

// defaultCriticalAddons mirrors REQUIREMENTS.md LIFE-01 — the
// recommended slugs that the Bridge refuses to mutate without the
// X-Force-Destroy nonce. Operator-editable via the HA Options UI;
// the schema-validated field lands in /data/options.json.
var defaultCriticalAddons = []string{
	"core_mosquitto",
	"core_zigbee2mqtt",
	"core_esphome",
}

// options is the subset of /data/options.json the Bridge reads at
// startup. BindAddress defaults to "auto" (Tailscale detection);
// BindAllowedSubnets defaults to [] (strict refusal of non-Tailscale
// IPs). Phase 12 Plan 03 extends with the three BRIDGE-04..09 /
// STATE-03 / LIFE-01 tunables.
//
// BindAllowedSubnets is a []string — the HA Supervisor schema DSL uses
// the YAML-list form (`- "str?"`) for lists of arbitrary strings, NOT
// the string `list(str)?` form, which Supervisor parses as a one-value
// enum. See supervisor/apps/options.py:106 (isinstance(typ, list)
// → _nested_validate_list branch) vs :163 (string `list(<inner>)`
// → vol.In(<inner>.split("|")) enum branch).
type options struct {
	BindAddress          string   `json:"bind_address"`
	BindAllowedSubnets   []string `json:"bind_allowed_subnets"`
	CriticalAddons       []string `json:"critical_addons"`
	InstallJobTimeoutSec int      `json:"install_job_timeout_seconds"`
	TryLockTimeoutSec    int      `json:"try_lock_timeout_seconds"`
}

func main() {
	version := flag.Bool("version", false, "print bridge version and exit")
	flag.Parse()

	if *version {
		fmt.Fprintln(os.Stdout, bridgeVersion) //nolint:forbidigo // intentional stdout write for CLI
		return
	}

	// Capture process-startup time as the FIRST executable line of
	// func main() so uptime_seconds in /v1/info reflects the Bridge
	// process lifetime. The few microseconds of Go runtime
	// initialization before this line execute are negligible at
	// second-resolution granularity consumed by humans and
	// lifecycle.precondition blocks. Captured here (rather than
	// immediately before srv.ListenAndServe) so NewRouter can take
	// it as a constructor parameter without a setter or
	// package-level variable.
	startTime := time.Now()

	// Structured JSON logging via stdlib log/slog (Phase 9 baseline).
	// Plan 02 wraps this with a scrubbingHandler that masks sensitive
	// keys before serialization.
	logger := slog.New(logging.NewScrubbingHandler(slog.NewJSONHandler(os.Stdout, nil)))
	slog.SetDefault(logger)

	// Read add-on options from /data/options.json (HA add-on store).
	opts := options{
		BindAddress:          "auto",
		BindAllowedSubnets:   []string{},
		CriticalAddons:       defaultCriticalAddons,
		InstallJobTimeoutSec: 300,
		TryLockTimeoutSec:    5,
	}
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

	// Critical-addons startup audit (Pitfall 10 — defensive operator
	// visibility). Empty list disables protection per D-09; emit
	// slog.Warn so operators see the unprotected state in their log
	// stream. Non-empty: slog.Info with the count + slugs so the
	// audit record is greppable.
	if len(opts.CriticalAddons) == 0 {
		slog.Warn("bridge_critical_addons_empty", "count", 0)
	} else {
		slog.Info("bridge_critical_addons_loaded",
			"count", len(opts.CriticalAddons),
			"slugs", opts.CriticalAddons,
		)
	}

	// TokenStore — load from /data or generate on first start.
	store, err := auth.NewFileTokenStore("/data")
	if err != nil {
		slog.Error("token_store_init_failed", "err", err.Error())
		os.Exit(1)
	}
	if store.Hash() == nil {
		// First start: generate + persist + write the plaintext to a
		// chmod-600 file so the operator can configure their Provider
		// without the plaintext ever passing through a log stream.
		// The log record carries a 3+3-char preview (Truncate) and the
		// file path; subsequent restarts do NOT re-emit either.
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
		slog.Info("bridge.token.issued",
			"actor_token_fp", auth.Fingerprint(token),
			"preview", auth.Truncate(token), // 3...3 of 43 chars
			"path", path, // /data/initial-token — chmod 600
		)
	} else {
		slog.Info("bridge.token.loaded", "actor_token_fp", auth.HashFingerprint(store.Hash()))
	}

	// Supervisor HTTP client (Plan 02's /healthz uses it).
	supClient := supervisor.NewClient(supervisor.ReadSupervisorToken)

	// Phase 12 Plan 03 wiring: build the per-slug mutex + nonce
	// managers. The nonce Manager's TTL is 60s (CONTEXT D-06 / LIFE-03
	// default). The Bridge refuses to start without a writable
	// nonce journal — nonce.NewManager is the gate (T-12-20).
	mutexMgr := mutex.NewManager()
	nonceMgr, err := nonce.NewManager("/data", nonce.DefaultTTL)
	if err != nil {
		slog.Error("nonce_manager_init_failed", "err", err.Error())
		os.Exit(1)
	}

	// Nonce GC goroutine (Pitfall 9 — must respect SIGTERM so the
	// process exits promptly on shutdown). The deferred
	// nonceMgr.Close() from the previous iteration leaked across
	// restarts because defer runs in LIFO order AFTER main returns,
	// AFTER srv.ListenAndServe, AFTER HandleSignals — but the GC
	// goroutine had no cancellation signal of its own and would
	// keep ticking until process exit. Plan 03 wires the proper
	// pattern: explicit nonceCtx + nonceCancel; the goroutine
	// blocks on <-ctx.Done() and exits within 1s of cancellation
	// (covered by TestNonceGCRespectsContextCancellation).
	nonceCtx, nonceCancel := context.WithCancel(context.Background())
	go nonceMgr.StartGC(nonceCtx)

	// Convert /data/options.json seconds fields to time.Duration so
	// the handlers receive a typed value. Defaults above already
	// match Plan 02's hardcoded 5s/300s values; an empty
	// /data/options.json therefore produces no behavior change
	// for new installs (Plan 03 must_haves).
	installJobTimeout := time.Duration(opts.InstallJobTimeoutSec) * time.Second
	tryLockTimeout := time.Duration(opts.TryLockTimeoutSec) * time.Second

	logger.Info("starting",
		"bridge_version", bridgeVersion,
		"pid", os.Getpid(),
		"install_job_timeout_seconds", int(installJobTimeout.Seconds()),
		"try_lock_timeout_seconds", int(tryLockTimeout.Seconds()),
	)

	// Build the router — pass store so the auth middleware can validate.
	logger.Info("listening", "bind_address", bindIP+":8124", "state_file_path", stateFilePath)
	router := httpapi.NewRouter(bridgeVersion, store, supClient, mutexMgr, nonceMgr, opts.CriticalAddons, startTime, stateFilePath, tryLockTimeout, installJobTimeout)

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

	// Stop the nonce GC goroutine now that HandleSignals has
	// drained the HTTP server (Pitfall 9). Close the journal after
	// the GC exits so the GC pass cannot race against fd teardown.
	nonceCancel()
	_ = nonceMgr.Close()
}
