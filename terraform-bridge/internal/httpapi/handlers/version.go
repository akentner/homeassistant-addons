package handlers

import (
	"encoding/json"
	"net/http"

	"terraform-bridge/contract"
)

// NewVersionHandler returns the GET /v1/version handler. The returned JSON
// carries the Bridge's compile-time BridgeVersion so the OpenTofu Provider
// can perform the schema-version handshake (PROV-03). Phase 11 extends this
// with Supervisor reachability + addon schema info; Phase 15 just needs the
// bridge_version field for the E2E CI verification.
func NewVersionHandler(bridgeVersion string) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(contract.VersionHandshake{
			BridgeVersion: bridgeVersion,
		})
	}
}