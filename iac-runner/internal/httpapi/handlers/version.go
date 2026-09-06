// Package handlers: GET /v1/version is the Phase 16 SC#8 handshake
// endpoint. The response body carries the runner's compile-time
// runnerVersion (cmd/runner/version.go) plus the three semver
// constants from internal/version (SchemaVersion +
// Min/MaxSupportedOpenTofu). Mounted inside the /v1 auth subrouter
// (RequireBearer-wrapped) so a missing or wrong token returns 401 +
// {"error_code":"unauthorized"}.
package handlers

import (
	"encoding/json"
	"net/http"

	"iac-runner/internal/contract"
	"iac-runner/internal/version"
)

// Version returns the handler mounted at GET /v1/version (router.go).
// The response body carries the runner's compile-time runnerVersion
// (cmd/runner/version.go) plus the three semver constants from
// internal/version. SchemaVersion follows semver; bump the MAJOR
// segment on every breaking change to the /v1/* HTTP API surface
// (per the bump policy in internal/version/version.go).
func Version(runnerVersion string) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(contract.VersionHandshake{
			RunnerVersion:        runnerVersion,
			SchemaVersion:        version.SchemaVersion,
			MinSupportedOpenTofu: version.MinSupportedOpenTofu,
			MaxSupportedOpenTofu: version.MaxSupportedOpenTofu,
		})
	}
}
