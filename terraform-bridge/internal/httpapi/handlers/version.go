// Package handlers: GET /v1/version is the BRIDGE-01 handshake
// endpoint. The Providers PROV-03 Configure flow calls this at
// startup and refuses to operate if the schema_version is outside
// [min_provider_version, max_provider_version]. The endpoint requires
// a valid bearer (mounted inside the /v1 auth subrouter).
package handlers

import (
	"encoding/json"
	"net/http"

	"terraform-bridge/contract"
	"terraform-bridge/internal/version"
)

// Version returns the handler mounted at GET /v1/version (router.go).
// The response body carries the Bridges compile-time bridgeVersion
// (cmd/bridge/version.go) plus the three semver constants from
// internal/version. SchemaVersion follows semver; bump the MAJOR
// segment on every breaking Bridge API change per the policy in
// internal/version/version.go.
func Version(bridgeVersion string) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(contract.VersionHandshake{
			BridgeVersion:      bridgeVersion,
			SchemaVersion:      version.SchemaVersion,
			MinProviderVersion: version.MinProviderVersion,
			MaxProviderVersion: version.MaxProviderVersion,
		})
	}
}
