package httpapi

import (
	"encoding/json"
	"net/http"

	"iac-runner/internal/contract"
)

// rootHandler returns the Phase 16 GET / placeholder. The msg field
// explicitly points readers at the real handlers (/healthz and
// /v1/auth/rotate) so the placeholder can't be confused with a
// finished root handler.
func rootHandler(runnerVersion string) http.HandlerFunc {
	body := contract.RootResponse{
		RunnerVersion: runnerVersion,
		Status:        "scaffolded",
		Msg:           "Phase 16 scaffold only — see /healthz and /v1/auth/rotate",
	}

	encoded, err := json.Marshal(body)
	if err != nil {
		// json.Marshal of a static struct cannot fail in practice;
		// panic is appropriate to surface a programmer error during
		// boot.
		panic("httpapi: failed to marshal root response: " + err.Error())
	}

	return func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(encoded)
	}
}
