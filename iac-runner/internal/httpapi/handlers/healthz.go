package handlers

// healthz is the GET /healthz handler. Replaces Plan 01's always-200
// stub with real probes:
//   - exec.LookPath("tofu") — is the `tofu` binary on PATH? Without
//     it, /v1/plan and /v1/apply cannot invoke OpenTofu. Plan 17
//     adds the apply endpoints; a false-positive /healthz 200 when
//     tofu is missing would mask Phase 17's apply failures.
//   - validator.Validate() — every credential file under /data/keys/
//     chmod 600 + owned by the current UID. SEC-01 fail-fast; the
//     per-request re-check ensures a degraded key file fails
//     /healthz even if the validator was OK at boot.
//
// On either failure the response is HTTP 503 with Content-Length: 0
// — no error details, no file paths, no exit codes. The actual
// failure is logged server-side via slog (with the scrubbing
// wrapper from main.go) so an external monitor that polls /healthz
// learns only "service degraded", not "your /data/keys/r2-access.key
// is mode 644".
//
// The 2s per-request budget is enforced via context.WithTimeout. The
// context is currently unused (validator.Validate() and exec.LookPath
// are both fast synchronous calls), but the timeout slot is wired so
// Phase 17's deeper /healthz probes (tofu version probe, remote-state
// reachability check) can plug in without changing the handler
// signature.

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"os/exec"
	"time"

	"iac-runner/internal/contract"
	"iac-runner/internal/keys"
)

// healthzTimeout caps each /healthz probe's wall-clock budget at 2
// seconds per the agent's discretion in PLAN.md. validator.Validate()
// and exec.LookPath both complete in microseconds today; the budget
// is reserved for future per-request probes that may be slower.
const healthzTimeout = 2 * time.Second

// Healthz returns an http.HandlerFunc that probes the runner's
// runtime readiness: tofu binary on PATH (Phase 17 prerequisite) +
// keys validator pass (SEC-01). runnerVersion is embedded in the
// 200 body so external monitors can correlate runner version with
// the liveness signal. validator is the keys.Validator constructed
// in main.go and bound to /data/keys/ + the configured state
// backend's CredentialFiles.
//
// Response shape on success (200):
//
//	{
//	  "status": "ok",
//	  "tofu_on_path": true,
//	  "keys_chmod_600": true,
//	  "runner_version": "<version>"
//	}
//
// On failure (503): empty body (Content-Length: 0). The failure
// reason is logged via slog.Warn("healthz_failed", …) but never
// returned to the caller.
func Healthz(runnerVersion string, validator *keys.Validator) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), healthzTimeout)
		defer cancel()

		_, lookErr := exec.LookPath("tofu")
		keysErr := validator.Validate()

		if lookErr != nil || keysErr != nil {
			slog.Warn("healthz_failed",
				"tofu_on_path", lookErr == nil,
				"keys_chmod_600", keysErr == nil,
				"tofu_err", errString(lookErr),
				"keys_err", errString(keysErr),
			)
			w.Header().Set("Content-Length", "0")
			w.WriteHeader(http.StatusServiceUnavailable)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(contract.HealthResponse{
			Status:        "ok",
			TofuOnPath:    true,
			KeysChmod600:  true,
			RunnerVersion: runnerVersion,
		})

		_ = ctx
	}
}

// errString returns err.Error() or the empty string when err is nil.
// Keeps the slog.Warn call site readable — no nested
// `if err != nil { err.Error() } else { "" }` chains.
func errString(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}
