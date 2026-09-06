package handlers

// healthz is the GET /healthz STUB handler for Phase 16. It always
// returns 200 + HealthResponse with placeholder values for tofu_on_path
// and keys_chmod_600. Plan 02 replaces these with real checks:
//   - tofu_on_path: exec.LookPath("tofu")
//   - keys_chmod_600: SEC-01 validator scans /data/keys/ for non-0600
//     credential files at startup and the validator's runtime result is
//     exposed here.

import (
	"encoding/json"
	"net/http"

	"iac-runner/internal/contract"
)

// Healthz returns an http.HandlerFunc that emits the Plan 01 stub
// 200 + placeholder HealthResponse. runnerVersion is embedded in the
// 200 body so external monitors can correlate runner version with the
// liveness signal.
func Healthz(runnerVersion string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(contract.HealthResponse{
			Status:        "ok",
			TofuOnPath:    true,
			KeysChmod600:  true,
			RunnerVersion: runnerVersion,
		})
	}
}
