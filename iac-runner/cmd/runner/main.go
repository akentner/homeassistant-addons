package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"iac-runner/internal/auth"
	"iac-runner/internal/git"
	"iac-runner/internal/httpapi"
	"iac-runner/internal/jobq"
	"iac-runner/internal/keys"
	"iac-runner/internal/logging"
	"iac-runner/internal/runs"
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

// defaultReposDir holds one working tree per configured `repos` entry
// (CONTEXT D-01). git.NewManager creates it with 0700 — the checkouts
// can contain private tfvars and only this process reads them.
const defaultReposDir = defaultDataDir + "/repos"

// defaultRunsDir holds one directory per run (meta.json + output.log +
// plan.tfplan). runs.NewStore creates it with 0700; the retention
// ticker (CONTEXT D-25) bounds its growth.
const defaultRunsDir = defaultDataDir + "/runs"

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

	// Phase 17 fields — see CONTEXT D-04 / D-15 / D-25 and the
	// config.yaml schema shipped by 17-01. Repos unmarshals the
	// Supervisor's list-of-dict straight into []git.RepoConfig, so the
	// JSON tags on git.RepoConfig ARE the Options contract; the three
	// ints carry the schema defaults applied in main() below.
	Repos               []git.RepoConfig `json:"repos"`
	MaxParallelJobs     int              `json:"max_parallel_jobs"`
	ApplyTimeoutMinutes int              `json:"apply_timeout_minutes"`
	RunsRetentionHours  int              `json:"runs_retention_hours"`
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
		BindAddress:         "auto",
		BindAllowedSubnets:  []string{},
		StateBackend:        defaultStateBackend,
		R2Bucket:            "",
		S3Endpoint:          "",
		S3Bucket:            "",
		S3Region:            "",
		Repos:               []git.RepoConfig{},
		MaxParallelJobs:     4,  // CONTEXT D-04
		ApplyTimeoutMinutes: 60, // CONTEXT D-15
		RunsRetentionHours:  24, // CONTEXT D-25
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

	// ─── Phase 17: git manager + run store + retention + job queue ───
	//
	// Everything below runs BEFORE the HTTP listener starts, so no
	// client can observe a half-initialized runner: a repo is either
	// cloned or logged as failed, and a stale `running` run from the
	// previous container is already rewritten to `interrupted` by the
	// time /v1/runs can be queried.

	// git.NewManager validates every `repos` entry, rejects duplicate
	// names and creates /data/repos with 0700. A construction error is
	// fatal: it means the operator's `repos` list is malformed, and
	// booting with a silently-empty repo set would make every
	// /v1/plan answer run_unknown_repo with no clue why.
	gitMgr, err := git.NewManager(
		defaultReposDir,
		defaultKeysDir, // already chmod-600-validated above
		opts.Repos,
		nil, // git.DefaultCommandRunner
		nil, // time.Sleep
	)
	if err != nil {
		slog.Error("git_manager_init_failed", "err", err.Error())
		os.Exit(1)
	}
	if warn := gitMgr.SafeDirectoryWarning(); warn != nil {
		// The one-time `git config --global --add safe.directory '*'`
		// guard failed. Not fatal (ROADMAP SC-2): it only matters on a
		// UID-mismatched /data volume, and git operations are attempted
		// regardless — but the operator needs the record when a later
		// pull reports "dubious ownership".
		slog.Warn("git_safe_directory_guard_failed", "err", warn.Error())
	}
	slog.Info("repos_loaded",
		"count", len(opts.Repos),
		"repos", repoNames(opts.Repos),
		"key_issues", repoKeyIssues(defaultKeysDir, opts.Repos),
		"max_parallel_jobs", opts.MaxParallelJobs,
		"apply_timeout_minutes", opts.ApplyTimeoutMinutes,
		"runs_retention_hours", opts.RunsRetentionHours,
	)

	// Best-effort startup clone with the CONTEXT D-13 backoff curve
	// (1s / 5s / 30s, 3 attempts). CloneAll never returns an error;
	// per-repo outcomes are logged here so a failed clone is
	// operator-visible without blocking startup (CONTEXT D-14 —
	// a later /v1/plan for that repo answers git_clone_missing).
	for _, outcome := range gitMgr.CloneAll(context.Background()) {
		switch {
		case outcome.Err != nil:
			slog.Warn("git_clone_failed",
				"repo", outcome.Name,
				"attempts", outcome.Attempts,
				"err", outcome.Err.Error(),
			)
		case outcome.Skipped:
			slog.Info("git_clone_skipped", "repo", outcome.Name)
		default:
			slog.Info("git_clone_succeeded",
				"repo", outcome.Name,
				"attempts", outcome.Attempts,
			)
		}
	}

	// runs.NewStore does os.MkdirAll(runsDir, 0700), so /data/runs
	// exists by the time the sweep below reads it.
	runStore, err := runs.NewStore(defaultRunsDir, nil) // nil clock -> time.Now
	if err != nil {
		slog.Error("runs_store_init_failed", "err", err.Error())
		os.Exit(1)
	}

	// CONTEXT D-02: a run still marked `running` belongs to a tofu
	// process that died with the previous container and can never
	// resolve itself. Rewrite it to `interrupted` before the listener
	// opens so no client ever observes a perpetual `running`.
	if swept, err := runStore.SweepInterrupted(); err != nil {
		slog.Warn("runs_sweep_interrupted_failed", "err", err.Error())
	} else if swept > 0 {
		slog.Info("runs_swept_interrupted", "count", swept)
	}

	// CONTEXT D-25. The Supervisor schema bounds runs_retention_hours
	// to 1..720, but a hand-edited /data/options.json can still deliver
	// 0 — and Rotate(0) would delete every terminal run on the first
	// tick. Clamp to the schema default instead of trusting the file.
	retention := time.Duration(opts.RunsRetentionHours) * time.Hour
	if opts.RunsRetentionHours <= 0 {
		retention = 24 * time.Hour
		slog.Warn("runs_retention_invalid",
			"configured_hours", opts.RunsRetentionHours,
			"applied_hours", int(retention.Hours()),
		)
	}

	// One explicit reclaim at boot, so the startup sweep is its own
	// observable record; StartRetentionTicker deliberately does not
	// rotate on start (17-04 contract) and only handles steady state.
	if deleted, err := runStore.Rotate(retention); err != nil {
		slog.Warn("runs_rotate_failed", "err", err.Error())
	} else if deleted > 0 {
		slog.Info("runs_rotated_at_boot",
			"deleted", deleted,
			"retention_hours", int(retention.Hours()),
		)
	}

	// The ticker fires every retention/4 (default 6h), floored at 1
	// minute by internal/runs. stopRetention is passed to
	// HandleSignals so the goroutine dies inside the SIGTERM drain
	// rather than outliving the process; the defer is belt-and-braces
	// for the paths that never reach the signal handler.
	stopRetention := runStore.StartRetentionTicker(context.Background(), retention)
	defer stopRetention()
	slog.Info("runs_retention_started",
		"runs_dir", runStore.RunsDir(),
		"retention_hours", int(retention.Hours()),
	)

	// jobq.New applies the D-04 / D-15 defaults for a zero value and
	// resolves the tofu binary via exec.LookPath. A missing tofu is
	// deliberately NOT fatal there — /healthz reports tofu_on_path
	// false and Submit answers run_tofu_not_found per request, which
	// beats a crash-looping container with no diagnosable surface.
	q, err := jobq.New(jobq.Deps{
		Store:        runStore,
		Git:          gitMgr,
		Backend:      backend,
		MaxParallel:  opts.MaxParallelJobs,
		ApplyTimeout: time.Duration(opts.ApplyTimeoutMinutes) * time.Minute,
	})
	if err != nil {
		slog.Error("jobq_init_failed", "err", err.Error())
		os.Exit(1)
	}
	slog.Info("jobq_ready",
		"max_parallel_jobs", opts.MaxParallelJobs,
		"apply_timeout_minutes", opts.ApplyTimeoutMinutes,
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
	// validate; pass keysValidator so /healthz can probe /data/keys/;
	// pass the three Phase 17 dependencies constructed above so
	// /v1/repos/{name}/pull, /v1/plan, /v1/apply, /v1/runs/{id} and
	// /v1/runs all serve real work.
	router := httpapi.NewRouter(runnerVersion, store, keysValidator, gitMgr, runStore, q)

	srv := &http.Server{
		Addr:              bindIP + ":8125",
		Handler:           router,
		ReadHeaderTimeout: 5 * time.Second,
	}

	// Signal handling — HandleSignals owns the lifecycle.
	signalsDone := make(chan struct{})
	go HandleSignals(context.Background(), srv, logger, signalsDone, q, stopRetention)

	logger.Info("listening", "bind_address", bindIP+":8125")

	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		slog.Error("listen_error", "err", err.Error())
		os.Exit(1)
	}

	<-signalsDone
}

// repoNames returns the configured repo names for the `repos_loaded`
// record. The list is bounded by the schema-validated Options (a
// handful of entries in practice), so a fresh slice per startup costs
// nothing.
func repoNames(rs []git.RepoConfig) []string {
	names := make([]string, len(rs))
	for i, r := range rs {
		names[i] = r.Name
	}
	return names
}

// repoKeyIssues reports the missing SSH prerequisites for the
// configured repos: one entry per repo whose deploy key
// <keysDir>/<name>.key is absent, plus one entry when
// <keysDir>/known_hosts is absent while at least one repo is
// configured.
//
// Presence only — the keys validator (SEC-01) has already asserted
// chmod 600 and UID ownership for every file that DOES exist under
// keysDir, and a missing deploy key is deliberately not fatal: the
// clone for that repo fails with git_ssh_handshake, every other repo
// still works, and the operator gets a named list at boot instead of
// having to decode an ssh error.
func repoKeyIssues(keysDir string, rs []git.RepoConfig) []string {
	if len(rs) == 0 {
		return []string{}
	}
	issues := make([]string, 0, len(rs)+1)
	for _, r := range rs {
		keyPath := filepath.Join(keysDir, r.Name+".key")
		if _, err := os.Stat(keyPath); err != nil {
			issues = append(issues, r.Name+": missing deploy key "+keyPath)
		}
	}
	knownHosts := filepath.Join(keysDir, "known_hosts")
	if _, err := os.Stat(knownHosts); err != nil {
		issues = append(issues, "missing "+knownHosts)
	}
	return issues
}
