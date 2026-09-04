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
