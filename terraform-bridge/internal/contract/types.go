// Package contract holds the JSON types shared between the Bridge HTTP API
// and the co-located terraform-provider-homeassistant Go module.
//
// Per CONTEXT.md D-03, both Bridge and Provider reference these types via the
// Provider's `replace terraform-bridge => ../terraform-bridge` directive in
// go.mod, so drift is caught at `go build ./...` time on the Provider side.
//
// Phase 9 ships skeletal structs with json tags only; Phase 13 fills in CRUD
// bodies for homeassistant_addon resources.
package contract

// AddOnInfo mirrors the Supervisor /apps/{slug}/info payload that
// GET /v1/addons/{slug}/info (Phase 11) returns to the Provider. Field names
// follow Supervisor's existing schema; JSON tags use snake_case for the wire
// format. Field names are the agent's discretion per CONTEXT §the agent's
// Discretion — but the same import path must be used from Plan 02.
type AddOnInfo struct {
	Slug       string            `json:"slug"`
	Name       string            `json:"name"`
	Version    string            `json:"version"`
	State      string            `json:"state"`
	Started    bool              `json:"started"`
	Options    map[string]string `json:"options,omitempty"`
	Boot       string            `json:"boot"`
	Repository string            `json:"repository"`
}

// JobStatus wraps a Supervisor job_id round-trip. The Bridge's write API
// (Phase 12) polls /jobs/{id} and returns the final job state to the
// Provider, who decides success/failure based on the Done + Result fields.
type JobStatus struct {
	JobID  string `json:"job_id"`
	Done   bool   `json:"done"`
	Result any    `json:"result,omitempty"`
}

// VersionHandshake is the body of GET /v1/version (Phase 11). The Provider's
// Configure (Phase 13) refuses to operate if the bridge's schema_version is
// outside [min_provider_version, max_provider_version]. All version fields
// follow semver.
type VersionHandshake struct {
	BridgeVersion      string `json:"bridge_version"`
	SchemaVersion      string `json:"schema_version"`
	MinProviderVersion string `json:"min_provider_version"`
	MaxProviderVersion string `json:"max_provider_version"`
}