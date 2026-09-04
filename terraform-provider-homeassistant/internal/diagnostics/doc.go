// Package diagnostics contains the Provider's typed Diagnostic
// translation helpers. Every Diagnostic surfaced by the Provider
// originates here — there is no other place in the codebase that
// constructs Provider diagnostics from Bridge error codes.
//
// File layout (per CF-13 + D-08..D-11):
//
//   - doc.go         — canonical per-error-code Summary text (the
//     single source of truth shared with Plan 03's
//     DOCS.md troubleshooting table) + the DocAnchor
//     helper that produces the kebab-case URL fragment
//     the Link field carries.
//   - map_error.go   — MapError: the switch that turns a Bridge error
//     into a typed Provider Diagnostic.
//   - map_error_test.go — table-driven coverage of every code MapError
//     handles.
//
// Architectural contract (D-08..D-11):
//
//   - D-08: One explicit Diagnostic text per Bridge error_code. Each
//     code has its own sentence describing what the user should do.
//   - D-09: Severity rule — Error for every 4xx/5xx Bridge response.
//     Warning is reserved for the `pwned` field coming out of
//     /v1/addons/{slug}/options/validate (PROV-06, wired in Plan 02).
//   - D-10: Every Provider diagnostic carries a
//     DOCS.md#troubleshooting-<kebab-error_code> URL via the
//     framework Link field.
//   - D-11: Every Provider diagnostic includes the Bridge request_id
//     (from contract.ErrorResponse.RequestID) in the Detail field as
//     `request_id: <id>` so operators can grep Bridge logs for
//     correlation.
package diagnostics

import "strings"

// Per-error-code Summary text (D-08). These strings are the single
// source of truth for both the Provider Diagnostic text (consumed by
// MapError) and Plan 03's DOCS.md troubleshooting table. Plan 03
// copies these into the per-row Markdown cells verbatim so the
// on-screen text and the Diagnostic Summary cannot drift apart.
const (
	// ErrUnauthorizedText covers 401 from Bridge (token missing, wrong, or expired).
	ErrUnauthorizedText = "Bridge authentication failed: check the bearer_token Provider argument matches the Bridge's current token (rotate via POST /v1/auth/rotate if it changed)."

	// ErrNotFoundText covers 404 from Bridge when the requested add-on
	// (or other resource) does not exist at the Bridge.
	ErrNotFoundText = "The add-on was not found at Bridge: verify the slug spelling and that the add-on is installed."

	// ErrCriticalAddonText covers 403 critical_addon_protected. The
	// Bridge refuses destructive ops against add-ons in its
	// critical_addons list unless a fresh X-Force-Destroy nonce is
	// presented.
	ErrCriticalAddonText = "This add-on is in critical_addons; either remove it from the Bridge's critical_addons option or issue a nonce via POST /v1/auth/nonce and retry with X-Force-Destroy."

	// ErrPreventedDestroyText covers 403 prevented_destroy. The
	// resource has lifecycle.prevent_destroy = true set; the user
	// must comment it out (or destroy explicitly) to allow the
	// destroy to proceed.
	ErrPreventedDestroyText = "lifecycle.prevent_destroy = true is set on this resource; comment it out or destroy explicitly."

	// ErrAlreadyInstalledText covers 409 already_installed. The
	// Bridge's adoption flow (Phase 12 D-26) treats this as a
	// successful adoption (Create falls through to GET info) — for
	// the Provider that means the resource is already present and
	// no install is needed.
	ErrAlreadyInstalledText = "Add-on is already installed; this is treated as adoption success (Create will read existing state)."

	// ErrLockedText covers 423 locked. Another operation on this slug
	// is currently in flight at the Bridge (per-slug mutex, Phase 12
	// D-12..D-16). Retrying after the in-flight operation finishes
	// (try_lock_timeout_seconds, default 5s) succeeds.
	ErrLockedText = "Another operation is in flight on this slug; retry in 30s."

	// ErrNonceExpiredText covers 4xx nonce_expired. The X-Force-Destroy
	// nonce is past its TTL or was never issued; a fresh POST
	// /v1/auth/nonce is required.
	ErrNonceExpiredText = "The X-Force-Destroy nonce is expired or never issued; request a fresh nonce via POST /v1/auth/nonce."

	// ErrNonceUsedText covers 4xx nonce_used. The X-Force-Destroy
	// nonce has already been consumed (single-use per Phase 12 D-06);
	// request a fresh one.
	ErrNonceUsedText = "The X-Force-Destroy nonce has already been used (single-use); request a fresh nonce via POST /v1/auth/nonce."

	// ErrInstallTimeoutText covers 504 install_timeout. The Bridge's
	// polling loop exceeded install_job_timeout_seconds (default
	// 300s) before the Supervisor's /jobs/{id} reached a terminal
	// state. The Supervisor job may continue server-side; the user
	// can read state to see the outcome.
	ErrInstallTimeoutText = "Install polling exceeded the timeout; the Supervisor job may continue server-side."

	// ErrUpstreamText covers 502 upstream_error. The Bridge could not
	// reach Supervisor (network blip, Supervisor restarting, etc.).
	// Retrying per the operation timeout (terraform-plugin-framework-timeouts
	// in Plan 02) usually succeeds.
	ErrUpstreamText = "Transient Supervisor failure: retry per the operation timeout."

	// ErrUnknownText is the defensive fallback for any error_code
	// MapError does not explicitly handle. The Bridge may add new
	// codes in a future Phase; the diagnostic surfaces the raw code
	// rather than panicking.
	ErrUnknownText = "Bridge returned an unrecognized error_code."

	// PwnedWarningText covers the Warning-severity branch per
	// PROV-06 + CF-08 + D-09. The Bridge surfaces the `pwned`
	// advisory when an add-on's options payload contains known
	// compromised-credentials leaks; the Provider surfaces this
	// as a Warning (NOT an Error) so the apply proceeds while the
	// operator is informed of the leaked credentials. The raw
	// pwned payload (D-11 extended) is carried in the Detail
	// field for grep-ability against the Supervisor logs.
	PwnedWarningText = "This add-on has a known compromised credentials leak (pwned): review the supervisor warning and rotate the add-on credentials before continuing."
)

// DocAnchor returns the kebab-case DOCS.md URL fragment for the given
// error_code (D-10). The Plan 03 troubleshooting table MUST add a
// matching anchor (`#troubleshooting-<kebab>`) so every Diagnostic
// Link resolves.
//
// Conversion rules:
//
//   - snake_case → kebab-case (the underscore separator becomes a
//     hyphen).
//   - lowercase.
//
// For an unrecognised error_code (one without a case in MapError),
// DocAnchor returns `DOCS.md#troubleshooting-unknown`. This keeps
// MapError's default branch's Link field non-empty and consistent
// with the per-code branches.
func DocAnchor(errorCode string) string {
	if errorCode == "" {
		return "DOCS.md#troubleshooting-unknown"
	}
	kebab := strings.ReplaceAll(strings.ToLower(errorCode), "_", "-")
	return "DOCS.md#troubleshooting-" + kebab
}
