package diagnostics

import (
	"errors"
	"fmt"

	"github.com/hashicorp/terraform-plugin-framework/diag"

	"terraform-provider-homeassistant/internal/client"
)

// MapError translates a Bridge error into one or more typed Provider
// diagnostics. The function accepts any error so callers can pass
// either a *client.BridgeError (the typical case — Bridge returned a
// non-200 with a decoded contract.ErrorResponse) or a wrapped /
// transport error (network failure, JSON decode error).
//
// The output always carries:
//
//   - Summary = the canonical per-error-code text from doc.go
//     (D-08). The bridge_error_code itself is NOT the summary text
//     — it is the rationale the text is built around.
//   - Detail = `request_id: <id>` (D-11). Empty request_id becomes
//     the literal string `request_id: ` (no id) so operators can
//     always grep for `request_id:` and find the diagnostic.
//   - Severity = Error (D-09). Warning severity is reserved for the
//     `pwned` field from /v1/addons/{slug}/options/validate (CF-08);
//     Plan 02 adds that branch.
//
// The Link field on the Diagnostic is intentionally NOT populated —
// terraform-plugin-framework's ErrorDiagnostic / WarningDiagnostic
// types do not carry a Link field (only `tfprotov5.Diagnostic` and
// `tfprotov6.Diagnostic` do). The D-10 URL is therefore surfaced
// inside the Detail text as a second line so it remains visible to
// operators even when the framework's wire format strips richer
// metadata. Future framework versions may add a richer Diagnostic
// type with a Link field — that upgrade is deferred to Plan 02 /
// later.
//
// On an unknown error_code (one not in the switch below) MapError
// falls back to ErrUnknownText + DocAnchor("unknown"). The fallback
// is defensive: it never panics, never returns an empty Diagnostic
// slice, and the resulting Detail always carries the request_id and
// the URL even when the Bridge emitted a new code the Provider has
// not been taught yet.
func MapError(err error) diag.Diagnostics {
	if err == nil {
		return nil
	}

	// Fast path: a *client.BridgeError (the canonical Bridge
	// non-200). Extract the error_code and request_id for the
	// Detail field.
	var be *client.BridgeError
	if errors.As(err, &be) {
		return mapBridgeError(be)
	}

	// Anything else — a transport-level error from http.Client.Do,
	// a JSON decode failure, a wrapped error from a higher layer.
	// Surface a generic diagnostic with the error's Error() text.
	// PITFALLS S-1 invariant: client.BridgeError.Error() never
	// contains the bearer token, and http.Client.Do errors that
	// reach here carry the request URL (NOT the Authorization
	// header) when wrapping preserves them.
	return diag.Diagnostics{
		diag.NewErrorDiagnostic(
			"Bridge communication failed",
			fmt.Sprintf("request_id: \nerror: %s\nDOCS.md#troubleshooting-upstream-error", err.Error()),
		),
	}
}

// mapBridgeError is the per-error-code switch. Keeping it as a
// separate helper keeps MapError itself short and makes the switch
// exhaustive-looking to future readers.
func mapBridgeError(be *client.BridgeError) diag.Diagnostics {
	code := be.Err.ErrorCode
	requestID := be.Err.RequestID
	summary, detail := summarize(code, requestID, be)
	return diag.Diagnostics{
		diag.NewErrorDiagnostic(summary, detail),
	}
}

// summarize returns the (Summary, Detail) pair for the given
// error_code. The Detail string is the concatenation of
// `request_id: <id>` plus the DOCS.md URL — both formatted with
// trailing newlines so they render cleanly in `terraform plan`
// output.
func summarize(code, requestID string, be *client.BridgeError) (string, string) {
	summary, ok := summaryForCode(code)
	if !ok {
		summary = ErrUnknownText + " (code=" + code + ")"
	}

	detail := "request_id: " + requestID + "\n"
	detail += DocAnchor(code) + "\n"
	if be.Err.Message != "" {
		detail += "bridge_message: " + be.Err.Message + "\n"
	}
	detail += "bridge_status: " + fmt.Sprintf("%d", be.StatusCode)
	return summary, detail
}

// summaryForCode returns the canonical Summary text for a known
// code (D-08). Unknown codes return ("", false) so the caller falls
// back to the defensive ErrUnknownText branch in summarize().
func summaryForCode(code string) (string, bool) {
	switch code {
	case "unauthorized":
		return ErrUnauthorizedText, true
	case "not_found":
		return ErrNotFoundText, true
	case "critical_addon_protected":
		return ErrCriticalAddonText, true
	case "prevented_destroy":
		return ErrPreventedDestroyText, true
	case "already_installed":
		return ErrAlreadyInstalledText, true
	case "locked":
		return ErrLockedText, true
	case "nonce_expired":
		return ErrNonceExpiredText, true
	case "nonce_used":
		return ErrNonceUsedText, true
	case "install_timeout":
		return ErrInstallTimeoutText, true
	case "upstream_error":
		return ErrUpstreamText, true
	default:
		return "", false
	}
}

// AddPwnedWarning appends a Warning-severity Diagnostic to diags
// describing a Bridge-surfaced pwned advisory. PROV-06 + CF-08 +
// D-09: pwned is the ONLY condition that surfaces as Warning
// severity (every other 4xx/5xx is Error per D-09). The apply
// proceeds; the operator sees the warning in tofu output.
//
// The Diagnostic shape:
//
//   - Summary: PwnedWarningText (the canonical user-action text
//     from doc.go).
//   - Detail: pwnedInfo verbatim — the raw `pwned` payload from
//     the Bridge so operators can grep Supervisor logs for the
//     underlying credential-leak signal (D-11 extended).
//   - Severity: Warning.
//
// The function mutates diags in place (the canonical
// terraform-plugin-framework idiom for in-handler diagnostic
// accumulation) and returns nothing — callers Append via:
//
//	resp.Diagnostics.Append(diagnostics.AddPwnedWarning(...))
//
// Wait — Append is not on diag.Diagnostics directly for single
// diagnostic construction. Callers use the helper as a side-effect
// mutator: AddPwnedWarning(diags, info) → diags now contains the
// warning.
//
// The terraform-plugin-framework diag package's WarningDiagnostic
// constructor does NOT carry a Link field (only the tfprotov5/v6
// Diagnostic does); D-10's DOCS.md anchor URL is therefore not
// carried here — operators see the Summary text + the Detail
// payload. Future framework versions may add a Link field; the
// helper can be extended then without changing call sites.
func AddPwnedWarning(diags *diag.Diagnostics, pwnedInfo string) {
	if diags == nil {
		return
	}
	*diags = append(*diags, diag.NewWarningDiagnostic(
		PwnedWarningText,
		pwnedInfo,
	))
}
