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
	"iac-runner/internal/keys"
	"iac-runner/internal/logging"
	"iac-runner/internal/statebackend"
)

// defaultStateBackend mirrors REQUIREMENTS.md STBK-01 — the
// recommended state backend that the runner defaults to when
// /data/options.json is missing or unset. Operator-editable via the
// HA Options UI; the schema-validated field lands in /data/options.json
// with state_backend: list(match(^(r2|s3|local)$)).
var defaultStateBackend = "r2"

// defaultDataDir is the HA Supervisor bind-mounted data volume that
// holds the token file, /data/keys/, and the local-backend state
// file. Hard-coded to match the v1.4 PROJECT.md decisions
// (file-on-volume instead of config) and the v1.3
// terraform-bridge's /data/initial-token pattern.
const defaultDataDir = "/data"

// defaultKeysDir is the secrets directory inside the HA Supervisor
// data volume. Every credential file the runner uses (R2/S3 access
// keys, SSH deploy keys for git, known_hosts) MUST live here with
// chmod 600 — the keys validator (SEC-01) enforces this at startup.
const defaultKeysDir = defaultDataDir + "/keys"

// options is the subset of /data/options.json the runner reads at
// startup. BindAddress defaults to "auto" (Tailscale detection);
// BindAllowedSubnets defaults to [] (strict refusal of non-Tailscale
// IPs). StateBackend defaults to "r2" (per PROJECT.md locked
// decision); the r2_bucket / s3_endpoint / s3_bucket / s3_region
// fields are read when their respective backend is selected.
//
// BindAllowedSubnets is a []string — the HA Supervisor schema DSL
// uses the YAML-list form (`- "str?"`) for lists of arbitrary
// strings, NOT the string `list(str)?` form, which Supervisor parses
// as a one-value enum.
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

	// Structured JSON logging via stdlib log/slog. SEC-02 layer 1:
	// wrap slog.NewJSONHandler with the scrubbing handler so every
	// record's values for sensitive keys (Authorization, Bearer,
	// token, password, key, secret — case-insensitive) are replaced
	// with "<redacted>" before the JSON handler serializes. The
	// scrubbing wrapper preserves the slog.Handler contract
	// (Handle / WithAttrs / WithGroup), so downstream .With() and
	// .WithGroup() chains keep scrubbing.
	logger := slog.New(logging.NewScrubbingHandler(slog.NewJSONHandler(os.Stdout, nil)))
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

	// Construct the state backend via the factory. The factory reads
	// r2-account-id from /data/keys/ at construction time (r2 only);
	// a missing file fails fast here. The endpoint + bucket +
	// use_lockfile bits are logged for operator visibility — a
	// wrong bucket name in Options surfaces as `homelab-tfstate`
	// (or whatever the operator typed) in the bootstrap log line.
	backend, err := statebackend.New(opts.StateBackend, statebackend.Options{
		R2Bucket:   opts.R2Bucket,
		S3Endpoint: opts.S3Endpoint,
		S3Bucket:   opts.S3Bucket,
		S3Region:   opts.S3Region,
		DataDir:    defaultDataDir,
	})
	if err != nil {
		slog.Error("state_backend_init_failed",
			"state_backend", opts.StateBackend,
			"err", err.Error(),
		)
		os.Exit(1)
	}
	slog.Info("state_backend_ready",
		"backend", backend.Name(),
		"endpoint", backend.Endpoint(),
		"bucket", backend.Bucket(),
		"region", backend.Region(),
		"use_lockfile", backend.UseLockfile(),
	)

	// SEC-01: validate /data/keys/ against the configured backend's
	// required credential file list. Every required file must
	// exist + be chmod 600 + be owned by the current process UID.
	// Failures wrap ErrKeysNotChmod600 or ErrKeysMissing with the
	// offending filename so the operator can `chmod 600 <file>` and
	// restart. Refusal is fatal — no degraded mode.
	keysValidator := keys.NewValidator(defaultKeysDir, backend)
	if err := keysValidator.Validate(); err != nil {
		slog.Error("keys_validation_failed",
			"keys_dir", defaultKeysDir,
			"required_files", keysValidator.RequiredFiles(),
			"err", err.Error(),
		)
		os.Exit(1)
	}
	slog.Info("keys_validated",
		"keys_dir", defaultKeysDir,
		"required_files", keysValidator.RequiredFiles(),
	)

	// TokenStore — load from /data or generate on first start.
	store, err := auth.NewFileTokenStore(defaultDataDir)
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
		"state_backend", backend.Name(),
	)

	// Build the router — pass store so the auth middleware can
	// validate; pass keysValidator so /healthz can probe /data/keys/.
	//
	// TODO(17-07): the last three arguments — *git.Manager,
	// *runs.Store, *jobq.Queue — are the Phase 17 dependencies and
	// are still nil here. 17-08 owns the router mount and 17-07 owns
	// the startup wiring that constructs them, so the nils are the
	// deliberate seam between those two plans: /v1/version,
	// /v1/auth/rotate, /healthz and / are fully functional, while the
	// five Phase 17 endpoints answer 500 (via chi's Recoverer) until
	// 17-07 replaces these arguments with real dependencies.
	router := httpapi.NewRouter(runnerVersion, store, keysValidator, nil, nil, nil)

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
