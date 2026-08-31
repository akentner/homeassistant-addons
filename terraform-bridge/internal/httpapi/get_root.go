package httpapi

import (
	"encoding/json"
	"net/http"
)

// rootResponse is the Phase 9 GET / JSON shape. The three keys are mandatory
// per CONTEXT.md D-05; the rest of the field set is the agent's discretion.
// Keep this distinct from the Phase 11 /v1/version response so a casual reader
// can't mistake the placeholder for the real handler.
type rootResponse struct {
	BridgeVersion string `json:"bridge_version"`
	Status       string `json:"status"`
	Msg          string `json:"msg"`
}

// rootHandler returns the Phase 9 placeholder. The msg field explicitly points
// readers at Phase 11 so the placeholder can't be confused with a finished
// /v1/version endpoint.
func rootHandler(bridgeVersion string) http.HandlerFunc {
	body := rootResponse{
		BridgeVersion: bridgeVersion,
		Status:        "scaffolded",
		Msg:           "Phase 9 foundation only — see Phase 11 for /v1/version",
	}

	encoded, err := json.Marshal(body)
	if err != nil {
		// json.Marshal of a static struct cannot fail in practice; panic is
		// appropriate to surface a programmer error during boot.
		panic("httpapi: failed to marshal root response: " + err.Error())
	}

	return func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(encoded)
	}
}
