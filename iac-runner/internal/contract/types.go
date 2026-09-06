// Package contract holds the JSON types shared between the iac-runner
// HTTP API and any external clients (Phase 17 opens up the apply/plan
// endpoints to OpenTofu workflows; Phase 18 publishes HA entities via
// MQTT).
//
// Plan 01 ships five types — ErrorResponse, HealthResponse,
// RotateResponse, VersionHandshake, RootResponse — that cover the
// Plan 01 endpoints (/, /healthz, /v1/auth/rotate) and reserve the
// /v1/version shape for Plan 03. Plans 02/03 extend with state-backend
// + run-history types as those endpoints land.
package contract

// ErrorResponse is the body of every 4xx/5xx response from the
// runner. error_code is the machine-readable identifier
// ("unauthorized", "rotate_failed", …); message is human-readable
// detail; request_id, when present, lets operators correlate the
// response with a specific runner log record. Plaintext tokens,
// request bodies, and env-derived secrets are NEVER included.
type ErrorResponse struct {
	ErrorCode string `json:"error_code"`
	Message   string `json:"message,omitempty"`
	RequestID string `json:"request_id,omitempty"`
}

// RotateResponse is the body of POST /v1/auth/rotate. Both timestamp
// fields carry the same RFC3339 instant; the duplication lets
// consumer schemas use whichever field name they prefer without an
// extra hop.
type RotateResponse struct {
	NewToken           string `json:"new_token"`
	GraceExpiresAt     string `json:"grace_expires_at"`
	OldTokenValidUntil string `json:"old_token_valid_until"`
}

// HealthResponse is the body of GET /healthz. Plan 01's stub always
// returns tofu_on_path=true + keys_chmod_600=true placeholders; Plan
// 02 replaces with real tofu binary lookup + /data/keys/ chmod-600
// validation (SEC-01).
type HealthResponse struct {
	Status        string `json:"status"`
	TofuOnPath    bool   `json:"tofu_on_path"`
	KeysChmod600  bool   `json:"keys_chmod_600"`
	RunnerVersion string `json:"runner_version"`
}

// VersionHandshake is the body of GET /v1/version (added in Plan 03).
// No external consumer handshake exists yet — schema_version is
// reserved for future cross-version compatibility. All version fields
// follow semver.
type VersionHandshake struct {
	RunnerVersion        string `json:"runner_version"`
	SchemaVersion        string `json:"schema_version"`
	MinSupportedOpenTofu string `json:"min_supported_opentofu"`
	MaxSupportedOpenTofu string `json:"max_supported_opentofu"`
}

// RootResponse is the body of GET /. Plan 01 placeholder; Plan 03
// may add a more complete status payload.
type RootResponse struct {
	RunnerVersion string `json:"runner_version"`
	Status        string `json:"status"`
	Msg           string `json:"msg"`
}
