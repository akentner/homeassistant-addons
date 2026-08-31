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

// ErrorResponse is the body of every 4xx/5xx response from the
// Bridge. error_code is the machine-readable identifier
// ("unauthorized", "not_found", "critical_addon_protected", …);
// request_id, when present, lets operators correlate the response
// with a specific Bridge log record. Plaintext tokens, request
// bodies, and env-derived secrets are NEVER included.
type ErrorResponse struct {
	ErrorCode string `json:"error_code"`
	Message   string `json:"message,omitempty"`
	RequestID string `json:"request_id,omitempty"`
}

// TokenResponse is returned by /v1/whoami (this phase) and any
// future endpoint that needs to identify the authenticated caller
// without echoing the bearer token itself. actor_token_fp is the
// 16-char hex SHA-256[8] fingerprint of the validated token; two
// tokens never collide at this width with negligible probability.
type TokenResponse struct {
	ActorTokenFP string `json:"actor_token_fp"`
}

// RotateResponse is the body of POST /v1/auth/rotate (Plan 03).
// Both timestamp fields carry the same RFC3339 instant; the
// duplication lets Provider consumers use whichever field the
// OpenTofu schema prefers without an extra hop (CONTEXT D-03).
type RotateResponse struct {
	NewToken           string `json:"new_token"`
	GraceExpiresAt     string `json:"grace_expires_at"`
	OldTokenValidUntil string `json:"old_token_valid_until"`
}

// HealthResponse is the body of GET /healthz (Plan 02) on the
// success path. On failure (Supervisor unreachable), the response
// is HTTP 503 with an empty body (D-08: never leak internal state
// on health-check failure). SupervisorReachable mirrors the HTTP
// status for callers that prefer JSON over status-code parsing.
type HealthResponse struct {
	Status              string `json:"status"`
	SupervisorReachable bool   `json:"supervisor_reachable"`
	BridgeVersion       string `json:"bridge_version"`
}
