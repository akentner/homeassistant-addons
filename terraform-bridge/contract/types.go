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
//
// Phase 13 Plan 03 (D-01) appends the five Supervisor fields the Phase 9/11
// struct dropped: Hostname, DNS, IngressURL, IngressEntry, WebUIURL. All five
// carry `omitempty` so a Supervisor payload that omits them decodes cleanly to
// the Go zero value (empty string / nil slice) — per D-02 the Bridge passes
// Supervisor's payload through unmodified and the Provider surfaces the zero
// value verbatim, with no fallback synthesis. The extension is purely
// additive, so SchemaVersion stays at "1.0.0" per D-03 and the
// [min_provider_version, max_provider_version] window is unchanged.
type AddOnInfo struct {
	Slug         string            `json:"slug"`
	Name         string            `json:"name"`
	Version      string            `json:"version"`
	State        string            `json:"state"`
	Started      bool              `json:"started"`
	Options      map[string]string `json:"options,omitempty"`
	Boot         string            `json:"boot"`
	Repository   string            `json:"repository"`
	Hostname     string            `json:"hostname,omitempty"`
	DNS          []string          `json:"dns,omitempty"`
	IngressURL   string            `json:"ingress_url,omitempty"`
	IngressEntry string            `json:"ingress_entry,omitempty"`
	WebUIURL     string            `json:"webui_url,omitempty"`
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

// BridgeInfo is the body of GET /v1/info (BRIDGE-10, no auth).
// uptime_seconds is int64 (Terraform parses integers without coercion
// in lifecycle.precondition blocks); state_file_path is the absolute
// filesystem path of the bridge's OpenTofu state file - Phase 1
// hardcodes /data/terraform.tfstate per PROJECT.md architecture
// decision.
type BridgeInfo struct {
	BridgeVersion     string `json:"bridge_version"`
	SupervisorVersion string `json:"supervisor_version"`
	UptimeSeconds     int64  `json:"uptime_seconds"`
	StateFilePath     string `json:"state_file_path"`
}

// NonceResponse is the body of POST /v1/auth/nonce (LIFE-03 +
// CONTEXT D-05/D-06). The plaintext nonce is returned exactly
// once (X-Force-Destroy header on the next destructive call);
// expires_at is the RFC3339 instant after which the nonce is
// rejected as nonce_expired. The nonce value never enters a log
// path (PITFALLS S-1 + audit.go fingerprints).
type NonceResponse struct {
	Nonce     string `json:"nonce"`
	ExpiresAt string `json:"expires_at"`
}

// StateIndexResponse is the body of GET /v1/state/index
// (STATE-02 + CONTEXT D-20..D-23). Files enumerates every
// *.tfstate + *.tfstate.backup with size + sha256; Skipped
// accumulates per-file errors so a single unreadable file
// does not abort the index call (D-23). omitempty on Skipped
// keeps the wire clean when no errors occurred.
type StateIndexResponse struct {
	Files   []StateFileEntry `json:"files"`
	Skipped []string         `json:"skipped,omitempty"`
}

// StateFileEntry is one row of the StateIndexResponse.Files
// array. Name is the basename (no directory); SizeBytes is
// the file size on disk; SHA256 is the hex-encoded SHA-256
// digest of the file contents at Index() time.
type StateFileEntry struct {
	Name      string `json:"name"`
	SizeBytes int64  `json:"size_bytes"`
	SHA256    string `json:"sha256"`
}
