package diagnostics_test

import (
	"errors"
	"fmt"
	"strings"
	"testing"

	"github.com/hashicorp/terraform-plugin-framework/diag"

	"terraform-bridge/contract"
	"terraform-provider-homeassistant/internal/client"
	"terraform-provider-homeassistant/internal/diagnostics"
)

// TestMapError_KnownCodes exercises the per-error-code switch in
// MapError. Every code listed in D-08's BRIDGE-09 vocabulary (plus
// the defensive unknown branch) gets a row that constructs a
// *client.BridgeError carrying the code + a request_id, calls
// MapError, and verifies the resulting Diagnostics.
//
// Per the plan acceptance criteria, each row asserts:
//
//   - exactly 1 Diagnostic is returned,
//   - the severity is Error (per D-09),
//   - the Summary text matches the doc.go constant for the code,
//   - the Detail text contains `request_id: rid-test`,
//   - the Detail text contains the DOCS.md anchor URL.
func TestMapError_KnownCodes(t *testing.T) {
	tests := []struct {
		name            string
		code            string
		wantSummary     string // a substring the Summary must contain
		wantDocAnchor   string // the DOCS.md anchor the Detail must include
		wantDetailText  string // an additional substring the Detail must include (besides request_id)
		wantMessageText string // the Bridge's message body — used for the bridge_message: assertion
	}{
		{
			name:            "unauthorized",
			code:            "unauthorized",
			wantSummary:     "Bridge authentication failed",
			wantDocAnchor:   "troubleshooting-unauthorized",
			wantDetailText:  "",
			wantMessageText: "token mismatch",
		},
		{
			name:            "not_found",
			code:            "not_found",
			wantSummary:     "not found at Bridge",
			wantDocAnchor:   "troubleshooting-not-found",
			wantDetailText:  "",
			wantMessageText: "",
		},
		{
			name:            "critical_addon_protected",
			code:            "critical_addon_protected",
			wantSummary:     "critical_addons",
			wantDocAnchor:   "troubleshooting-critical-addon-protected",
			wantDetailText:  "",
			wantMessageText: "",
		},
		{
			name:            "prevented_destroy",
			code:            "prevented_destroy",
			wantSummary:     "prevent_destroy",
			wantDocAnchor:   "troubleshooting-prevented-destroy",
			wantDetailText:  "",
			wantMessageText: "",
		},
		{
			name:            "already_installed",
			code:            "already_installed",
			wantSummary:     "already installed",
			wantDocAnchor:   "troubleshooting-already-installed",
			wantDetailText:  "",
			wantMessageText: "",
		},
		{
			name:            "locked",
			code:            "locked",
			wantSummary:     "Another operation is in flight",
			wantDocAnchor:   "troubleshooting-locked",
			wantDetailText:  "",
			wantMessageText: "",
		},
		{
			name:            "nonce_expired",
			code:            "nonce_expired",
			wantSummary:     "nonce is expired",
			wantDocAnchor:   "troubleshooting-nonce-expired",
			wantDetailText:  "",
			wantMessageText: "",
		},
		{
			name:            "nonce_used",
			code:            "nonce_used",
			wantSummary:     "nonce has already been used",
			wantDocAnchor:   "troubleshooting-nonce-used",
			wantDetailText:  "",
			wantMessageText: "",
		},
		{
			name:            "install_timeout",
			code:            "install_timeout",
			wantSummary:     "Install polling exceeded",
			wantDocAnchor:   "troubleshooting-install-timeout",
			wantDetailText:  "",
			wantMessageText: "",
		},
		{
			name:            "upstream_error",
			code:            "upstream_error",
			wantSummary:     "Transient Supervisor failure",
			wantDocAnchor:   "troubleshooting-upstream-error",
			wantDetailText:  "",
			wantMessageText: "",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			be := &client.BridgeError{
				StatusCode: 500,
				Err: contract.ErrorResponse{
					ErrorCode: tc.code,
					RequestID: "rid-test",
					Message:   tc.wantMessageText,
				},
				Method: "GET",
				Path:   "/v1/test",
			}
			got := diagnostics.MapError(be)

			if len(got) != 1 {
				t.Fatalf("MapError(%s): got %d diagnostics, want 1", tc.code, len(got))
			}
			d := got[0]
			if d.Severity() != diag.SeverityError {
				t.Errorf("MapError(%s): severity = %v, want Error", tc.code, d.Severity())
			}
			summary := d.Summary()
			if !strings.Contains(summary, tc.wantSummary) {
				t.Errorf("MapError(%s): summary %q does not contain %q", tc.code, summary, tc.wantSummary)
			}
			detail := d.Detail()
			if !strings.Contains(detail, "request_id: rid-test") {
				t.Errorf("MapError(%s): detail %q does not contain request_id", tc.code, detail)
			}
			if !strings.Contains(detail, tc.wantDocAnchor) {
				t.Errorf("MapError(%s): detail %q does not contain DOCS.md anchor %q", tc.code, detail, tc.wantDocAnchor)
			}
			if tc.wantMessageText != "" && !strings.Contains(detail, tc.wantMessageText) {
				t.Errorf("MapError(%s): detail %q does not contain bridge message %q", tc.code, detail, tc.wantMessageText)
			}
		})
	}
}

// TestMapError_UnknownCode asserts the defensive fallback: a
// Bridge error_code MapError does not explicitly handle still
// surfaces a Diagnostic with severity Error + a non-empty Summary
// + the unknown DOCS.md anchor. The test fails fast (the
// acceptance criteria explicitly require non-panic, non-empty
// behaviour for unknown codes).
func TestMapError_UnknownCode(t *testing.T) {
	be := &client.BridgeError{
		StatusCode: 500,
		Err: contract.ErrorResponse{
			ErrorCode: "definitely_not_a_real_code",
			RequestID: "rid-unknown",
			Message:   "Bridge invented a new code",
		},
		Method: "GET",
		Path:   "/v1/test",
	}
	got := diagnostics.MapError(be)

	if len(got) != 1 {
		t.Fatalf("MapError(unknown): got %d diagnostics, want 1 (defensive)", len(got))
	}
	d := got[0]
	if d.Severity() != diag.SeverityError {
		t.Errorf("MapError(unknown): severity = %v, want Error", d.Severity())
	}
	if d.Summary() == "" {
		t.Errorf("MapError(unknown): Summary is empty; defensive branch must produce a non-empty Summary")
	}
	if !strings.Contains(d.Detail(), "definitely_not_a_real_code") && !strings.Contains(d.Detail(), "definitely-not-a-real-code") {
		t.Errorf("MapError(unknown): detail should mention the unknown code (any case), got %q", d.Detail())
	}
	if !strings.Contains(d.Detail(), "troubleshooting-definitely-not-a-real-code") {
		t.Errorf("MapError(unknown): detail should contain the kebab-case DOCS.md anchor for the unknown code, got %q", d.Detail())
	}
}

// TestMapError_NilReturnsNil asserts the trivial case: nil error
// yields nil diagnostics (no spurious Diagnostic on success).
func TestMapError_NilReturnsNil(t *testing.T) {
	if got := diagnostics.MapError(nil); got != nil {
		t.Errorf("MapError(nil) = %v, want nil", got)
	}
}

// TestMapError_NonBridgeError exercises the generic-error branch
// in MapError. A non-*client.BridgeError (e.g. a transport failure
// from http.Client.Do) must produce a single Error Diagnostic so
// the user sees something useful — the BridgeError branch cannot
// match a transport error since errors.As to *client.BridgeError
// will fail.
func TestMapError_NonBridgeError(t *testing.T) {
	wrapped := errors.New("dial tcp 192.168.1.1:8124: connect: connection refused")
	got := diagnostics.MapError(wrapped)

	if len(got) != 1 {
		t.Fatalf("MapError(wrapped): got %d diagnostics, want 1", len(got))
	}
	d := got[0]
	if d.Severity() != diag.SeverityError {
		t.Errorf("MapError(wrapped): severity = %v, want Error", d.Severity())
	}
	if !strings.Contains(d.Detail(), "connection refused") {
		t.Errorf("MapError(wrapped): detail should include the underlying error text, got %q", d.Detail())
	}
}

// TestMapError_WrappedBridgeError ensures errors.As walks wrapped
// errors correctly. A *client.BridgeError wrapped in fmt.Errorf
// still surfaces the per-code Diagnostic.
func TestMapError_WrappedBridgeError(t *testing.T) {
	be := &client.BridgeError{
		StatusCode: 404,
		Err: contract.ErrorResponse{
			ErrorCode: "not_found",
			RequestID: "rid-wrapped",
			Message:   "",
		},
		Method: "GET",
		Path:   "/v1/addons/missing/info",
	}
	wrapped := fmt.Errorf("Resource.Read failed: %w", be)
	got := diagnostics.MapError(wrapped)

	if len(got) != 1 {
		t.Fatalf("MapError(wrapped): got %d diagnostics, want 1", len(got))
	}
	if !strings.Contains(got[0].Detail(), "rid-wrapped") {
		t.Errorf("MapError(wrapped): detail %q does not contain rid-wrapped", got[0].Detail())
	}
	if !strings.Contains(got[0].Summary(), "not found at Bridge") {
		t.Errorf("MapError(wrapped): summary %q does not contain 'not found at Bridge'", got[0].Summary())
	}
}

// TestAddPwnedWarning is the PROV-06 + CF-08 + D-09 regression
// guard. AddPwnedWarning must append a single Warning-severity
// Diagnostic whose Summary is the canonical PwnedWarningText from
// doc.go + whose Detail is the raw pwned payload (D-11 extended).
//
// The Link field on terraform-plugin-framework's Diagnostic type is
// NOT populated (the framework's WarningDiagnostic / ErrorDiagnostic
// do not carry a Link field — only tfprotov5/v6 Diagnostic does);
// the DOCS.md anchor URL is implicit in the PwnedWarningText via
// the operator's next-step guidance.
func TestAddPwnedWarning(t *testing.T) {
	pwnedInfo := "add-on a0d7c6b_test has leaked credentials"
	var diags diag.Diagnostics
	diagnostics.AddPwnedWarning(&diags, pwnedInfo)

	if len(diags) != 1 {
		t.Fatalf("AddPwnedWarning: got %d diagnostics, want 1", len(diags))
	}
	d := diags[0]
	if d.Severity() != diag.SeverityWarning {
		t.Errorf("AddPwnedWarning: severity = %v, want Warning (D-09: pwned is Warning, NOT Error)", d.Severity())
	}
	if !strings.Contains(d.Summary(), "pwned") {
		t.Errorf("AddPwnedWarning: summary %q does not contain 'pwned'", d.Summary())
	}
	if !strings.Contains(d.Detail(), pwnedInfo) {
		t.Errorf("AddPwnedWarning: detail %q does not contain raw payload %q", d.Detail(), pwnedInfo)
	}
	// Summary must be the canonical PwnedWarningText constant
	// verbatim — Plan 03's DOCS.md troubleshooting table copies
	// the same string so the on-screen text and the diagnostic
	// cannot drift.
	if d.Summary() != diagnostics.PwnedWarningText {
		t.Errorf("AddPwnedWarning: summary = %q, want canonical PwnedWarningText", d.Summary())
	}
}

// TestAddPwnedWarning_NilDiagsSafe asserts AddPwnedWarning does
// not panic when handed a nil *diag.Diagnostics. The mutator must
// defend against the empty diags slice case so a Create handler
// before any diagnostic has been added does not crash.
func TestAddPwnedWarning_NilDiagsSafe(t *testing.T) {
	defer func() {
		if r := recover(); r != nil {
			t.Errorf("AddPwnedWarning(nil): panicked: %v", r)
		}
	}()
	diagnostics.AddPwnedWarning(nil, "any payload")
}

// TestAddPwnedWarning_AppendsNotReplaces asserts that AddPwnedWarning
// mutates the input slice by appending rather than by overwriting.
// A Create handler that has already accumulated a non-fatal
// diagnostic must keep both.
func TestAddPwnedWarning_AppendsNotReplaces(t *testing.T) {
	diags := diag.Diagnostics{
		diag.NewWarningDiagnostic("existing warning", "kept"),
	}
	diagnostics.AddPwnedWarning(&diags, "pwned payload")
	if len(diags) != 2 {
		t.Fatalf("AddPwnedWarning: got %d diagnostics, want 2 (append, not replace)", len(diags))
	}
	if diags[0].Summary() != "existing warning" {
		t.Errorf("AddPwnedWarning: diags[0].Summary = %q, want %q (pre-existing entry preserved)",
			diags[0].Summary(), "existing warning")
	}
	if diags[1].Severity() != diag.SeverityWarning {
		t.Errorf("AddPwnedWarning: diags[1].Severity = %v, want Warning", diags[1].Severity())
	}
}

// TestMapError_StillIncludesAll10Codes is the Plan 02 regression
// guard for the 10-code switch in MapError. Plan 01's tests
// covered the same codes (TestMapError_KnownCodes); this explicit
// re-assertion ensures the AddPwnedWarning addition did not
// inadvertently break the existing switch.
func TestMapError_StillIncludesAll10Codes(t *testing.T) {
	codes := []string{
		"unauthorized",
		"not_found",
		"critical_addon_protected",
		"prevented_destroy",
		"already_installed",
		"locked",
		"nonce_expired",
		"nonce_used",
		"install_timeout",
		"upstream_error",
	}
	for _, code := range codes {
		t.Run(code, func(t *testing.T) {
			be := &client.BridgeError{
				StatusCode: 500,
				Err:        contract.ErrorResponse{ErrorCode: code, RequestID: "rid-x"},
				Method:     "POST",
				Path:       "/v1/test",
			}
			got := diagnostics.MapError(be)
			if len(got) != 1 {
				t.Fatalf("MapError(%s): got %d diagnostics, want 1", code, len(got))
			}
			if got[0].Severity() != diag.SeverityError {
				t.Errorf("MapError(%s): severity = %v, want Error (every non-pwned 4xx/5xx is Error per D-09)",
					code, got[0].Severity())
			}
		})
	}
}

// TestMapError_PwnedNotInError asserts the D-09 severity rule:
// pwned is NOT a known Bridge error_code in MapError's switch —
// the Warning branch is surfaced ONLY via AddPwnedWarning. If
// someone synthesizes an `error_code: "pwned"` BridgeError and
// passes it to MapError, the defensive fallback branch returns
// the generic ErrUnknownText diagnostic at severity Error, NOT a
// Warning. The pwned Warning path requires explicit
// AddPwnedWarning invocation by the resource handler.
func TestMapError_PwnedNotInError(t *testing.T) {
	be := &client.BridgeError{
		StatusCode: 200,
		Err: contract.ErrorResponse{
			ErrorCode: "pwned",
			RequestID: "rid-pwned",
			Message:   "add-on a0d7c6b_test has leaked credentials",
		},
		Method: "POST",
		Path:   "/v1/addons/a0d7c6b_test/options",
	}
	got := diagnostics.MapError(be)
	if len(got) != 1 {
		t.Fatalf("MapError(pwned): got %d diagnostics, want 1", len(got))
	}
	if got[0].Severity() != diag.SeverityError {
		t.Errorf("MapError(pwned): severity = %v, want Error (pwned is NOT a Bridge error_code — the Warning is surfaced via AddPwnedWarning separately, per D-09)",
			got[0].Severity())
	}
	// The defensive fallback surfaces the raw code in the Detail
	// so an operator can still diagnose the unknown condition.
	if !strings.Contains(got[0].Detail(), "pwned") {
		t.Errorf("MapError(pwned): detail %q should contain the raw code 'pwned'", got[0].Detail())
	}
}
