// Package contract holds the JSON types shared between the iac-runner
// HTTP API and any external clients (Phase 17 opens up the apply/plan
// endpoints to OpenTofu workflows; Phase 18 publishes HA entities via
// MQTT).
//
// Phase 16 ships five types — ErrorResponse, HealthResponse,
// RotateResponse, VersionHandshake, RootResponse — for the
// /, /healthz, /v1/auth/rotate, /v1/version endpoints. Phase 17
// extends with the run-history types (RunKind, RunStatus, RunAccepted,
// RunDetail, RunSummary, RunListResponse) and the D-19 error_code
// taxonomy consumed by /v1/plan, /v1/apply, /v1/runs/{id}, /v1/runs,
// and /v1/repos/{name}/pull.
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

// RunKind distinguishes plan vs apply jobs. The value is persisted in
// /data/runs/{run_id}/meta.json and echoed in every run response.
type RunKind string

const (
	RunKindPlan  RunKind = "plan"
	RunKindApply RunKind = "apply"
)

// RunStatus is the lifecycle state of a run. queued -> running ->
// succeeded | failed is the normal path; interrupted (CONTEXT D-02) is
// assigned at boot to any run still marked running after a container
// restart, so the operator can tell "tofu exited non-zero" apart from
// "the add-on restarted mid-apply".
type RunStatus string

const (
	RunStatusQueued      RunStatus = "queued"
	RunStatusRunning     RunStatus = "running"
	RunStatusSucceeded   RunStatus = "succeeded"
	RunStatusFailed      RunStatus = "failed"
	RunStatusInterrupted RunStatus = "interrupted"
)

// RunAccepted is the 202 body of POST /v1/plan and POST /v1/apply
// (RUN-02 / RUN-03). The Location response header carries
// /v1/runs/{run_id}.
type RunAccepted struct {
	RunID  string    `json:"run_id"`
	Status RunStatus `json:"status"`
}

// RunDetail is the 200 body of GET /v1/runs/{id} (RUN-04).
// OutputLines is the redacted (SEC-03 / CONTEXT D-08) page of
// captured tofu output; Page/PageSize/TotalLines let a client walk
// a long apply incrementally (OBS-03). ExitCode is *int so a queued
// or running run marshals exit_code:null rather than the misleading
// 0 that would read as success.
type RunDetail struct {
	RunID       string    `json:"run_id"`
	Repo        string    `json:"repo"`
	Dir         string    `json:"dir"`
	Kind        RunKind   `json:"kind"`
	Status      RunStatus `json:"status"`
	ExitCode    *int      `json:"exit_code"`
	StartedAt   string    `json:"started_at"`
	FinishedAt  string    `json:"finished_at,omitempty"`
	ErrorCode   string    `json:"error_code,omitempty"`
	OutputLines []string  `json:"output_lines"`
	Page        int       `json:"page"`
	PageSize    int       `json:"page_size"`
	TotalLines  int       `json:"total_lines"`
}

// RunSummary is one element of RunListResponse.Runs (RUN-05); listing
// 20 runs must not read 20 log files, so output is on-demand via
// GET /v1/runs/{id}.
type RunSummary struct {
	RunID      string    `json:"run_id"`
	Repo       string    `json:"repo"`
	Dir        string    `json:"dir"`
	Kind       RunKind   `json:"kind"`
	Status     RunStatus `json:"status"`
	ExitCode   *int      `json:"exit_code"`
	StartedAt  string    `json:"started_at"`
	FinishedAt string    `json:"finished_at,omitempty"`
	ErrorCode  string    `json:"error_code,omitempty"`
}

// RunListResponse is the 200 body of GET /v1/runs (RUN-05), ordered
// by started_at descending.
type RunListResponse struct {
	Runs  []RunSummary `json:"runs"`
	Count int          `json:"count"`
	Limit int          `json:"limit"`
}

// Pagination + listing bounds. The handlers in 17-06 reference these
// named constants instead of literals so RUN-04 / RUN-05 / OBS-03 caps
// cannot drift between handler and contract.
const (
	DefaultOutputPageSize = 100
	MaxOutputPageSize     = 1000
	DefaultRunListLimit   = 20
	MaxRunListLimit       = 100
)

// Stable error_code taxonomy (D-19). Every 4xx/5xx response carries
// one of these as ErrorCode so clients branch on a stable identifier
// instead of parsing prose. D-20: new codes are additive — adding a
// failure mode means adding a constant here and a DOCS.md row, never
// changing an existing value.
const (
	// git_* — GIT-04. Each one carries a hint at the Options field
	// to fix; see internal/git.Classify for the stderr mapping.
	ErrCodeGitSSHHandshake        = "git_ssh_handshake"
	ErrCodeGitDNSFailure          = "git_dns_failure"
	ErrCodeGitRefNotFound         = "git_ref_not_found"
	ErrCodeGitUnauthorized        = "git_unauthorized"
	ErrCodeGitNonFastForward      = "git_non_fast_forward"
	ErrCodeGitCloneFailed         = "git_clone_failed"
	ErrCodeGitCloneMissing        = "git_clone_missing"
	ErrCodeGitRefPullIncompatible = "git_ref_pull_incompatible"

	// run_* — request-shape and lookup failures.
	ErrCodeRunTofuNotFound      = "run_tofu_not_found"
	ErrCodeRunInvalidDir        = "run_invalid_dir"
	ErrCodeRunUnknownRepo       = "run_unknown_repo"
	ErrCodeRunUnknownID         = "run_unknown_id"
	ErrCodeRunNotFound          = "run_not_found"
	ErrCodeRunCapacityExhausted = "run_capacity_exhausted"

	// apply_* — job-execution failures.
	ErrCodeApplyAlreadyRunning = "apply_already_running"
	ErrCodeApplyTimeout        = "apply_timeout"
	ErrCodeApplyFailed         = "apply_failed"

	// plan_timeout is the plan-side counterpart of apply_timeout
	// (CONTEXT §"Post-decision refinements"). D-20 permits additive
	// codes, so it is its own constant rather than overloading
	// apply_timeout for a plan run.
	ErrCodePlanTimeout = "plan_timeout"

	// apply_capacity_exhausted is the value actually emitted with
	// HTTP 503 + Retry-After: 30 when max_parallel_jobs is saturated
	// (CONTEXT D-06). D-19's taxonomy sketch listed the same condition
	// under run_* as capacity_exhausted; D-06 is the decision that
	// specifies observable behavior, so its spelling wins on the wire.
	// ErrCodeRunCapacityExhausted is kept declared because the
	// taxonomy reserves it, but handlers MUST emit
	// ErrCodeApplyCapacityExhausted.
	ErrCodeApplyCapacityExhausted = "apply_capacity_exhausted"

	// auth_* — pre-existing AUTHR-02 value, emitted by
	// internal/auth/middleware.go since Phase 16. NOT renamed:
	// changing it would break every existing client.
	ErrCodeUnauthorized = "unauthorized"
)
