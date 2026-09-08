package handlers

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"iac-runner/internal/contract"
	"iac-runner/internal/git"
)

// TestStatusForCodeTable locks the single error_code → HTTP status
// mapping every Phase 17 handler shares. 17-08's read handlers reuse
// this table instead of re-deriving it, so a change here is a wire
// change — the table is the contract.
func TestStatusForCodeTable(t *testing.T) {
	cases := []struct {
		code string
		want int
	}{
		// git_* — GIT-03/SC-3 mandates 403 for auth failures and 409
		// for a non-fast-forward pull.
		{contract.ErrCodeGitSSHHandshake, http.StatusForbidden},
		{contract.ErrCodeGitUnauthorized, http.StatusForbidden},
		{contract.ErrCodeGitNonFastForward, http.StatusConflict},
		{contract.ErrCodeGitRefNotFound, http.StatusNotFound},
		{contract.ErrCodeGitCloneMissing, http.StatusNotFound},
		{contract.ErrCodeGitRefPullIncompatible, http.StatusBadRequest},
		{contract.ErrCodeGitDNSFailure, http.StatusBadGateway},
		{contract.ErrCodeGitCloneFailed, http.StatusBadGateway},

		// run_* — lookup and request-shape failures.
		{contract.ErrCodeRunUnknownRepo, http.StatusNotFound},
		{contract.ErrCodeRunUnknownID, http.StatusNotFound},
		{contract.ErrCodeRunNotFound, http.StatusNotFound},
		{contract.ErrCodeRunInvalidDir, http.StatusBadRequest},
		{contract.ErrCodeRunTofuNotFound, http.StatusServiceUnavailable},
		{contract.ErrCodeRunCapacityExhausted, http.StatusServiceUnavailable},

		// apply_* / plan_* — job execution.
		{contract.ErrCodeApplyCapacityExhausted, http.StatusServiceUnavailable},
		{contract.ErrCodeApplyAlreadyRunning, http.StatusConflict},
		{contract.ErrCodeApplyTimeout, http.StatusGatewayTimeout},
		{contract.ErrCodePlanTimeout, http.StatusGatewayTimeout},
		{contract.ErrCodeApplyFailed, http.StatusInternalServerError},

		// auth_* — the Phase 16 middleware value.
		{contract.ErrCodeUnauthorized, http.StatusUnauthorized},

		// D-20: an additive code this table has not seen yet must not
		// produce a 200. 502 is the conservative default.
		{"git_something_new", http.StatusBadGateway},
	}

	for _, c := range cases {
		t.Run(c.code, func(t *testing.T) {
			if got := statusForCode(c.code); got != c.want {
				t.Errorf("statusForCode(%q) = %d, want %d", c.code, got, c.want)
			}
		})
	}
}

// TestStatusForCodeNeverSucceeds is the invariant behind the table: no
// error_code may map to a 2xx or 3xx status, because writeError is only
// ever called on a failure path.
func TestStatusForCodeNeverSucceeds(t *testing.T) {
	codes := []string{
		contract.ErrCodeGitSSHHandshake, contract.ErrCodeGitDNSFailure,
		contract.ErrCodeGitRefNotFound, contract.ErrCodeGitUnauthorized,
		contract.ErrCodeGitNonFastForward, contract.ErrCodeGitCloneFailed,
		contract.ErrCodeGitCloneMissing, contract.ErrCodeGitRefPullIncompatible,
		contract.ErrCodeRunTofuNotFound, contract.ErrCodeRunInvalidDir,
		contract.ErrCodeRunUnknownRepo, contract.ErrCodeRunUnknownID,
		contract.ErrCodeRunNotFound, contract.ErrCodeRunCapacityExhausted,
		contract.ErrCodeApplyAlreadyRunning, contract.ErrCodeApplyTimeout,
		contract.ErrCodeApplyFailed, contract.ErrCodePlanTimeout,
		contract.ErrCodeApplyCapacityExhausted, contract.ErrCodeUnauthorized,
		"", "totally_unknown",
	}
	for _, code := range codes {
		if got := statusForCode(code); got < 400 {
			t.Errorf("statusForCode(%q) = %d, want >= 400", code, got)
		}
	}
}

func TestWriteErrorBodyShape(t *testing.T) {
	rec := httptest.NewRecorder()
	writeError(rec, http.StatusNotFound, contract.ErrCodeRunUnknownRepo, "unknown repo \"prod\"", "")

	if rec.Code != http.StatusNotFound {
		t.Errorf("status = %d, want 404", rec.Code)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type = %q, want application/json", ct)
	}

	var er contract.ErrorResponse
	if err := json.NewDecoder(rec.Body).Decode(&er); err != nil {
		t.Fatalf("decode: %v (raw %q)", err, rec.Body.String())
	}
	if er.ErrorCode != contract.ErrCodeRunUnknownRepo {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeRunUnknownRepo)
	}
	if er.Message != "unknown repo \"prod\"" {
		t.Errorf("message = %q", er.Message)
	}
}

// TestWriteErrorAppendsHint proves the D-19 Options-field hint survives
// onto the wire even though contract.ErrorResponse has no hint field.
func TestWriteErrorAppendsHint(t *testing.T) {
	rec := httptest.NewRecorder()
	writeError(rec, http.StatusForbidden, contract.ErrCodeGitSSHHandshake,
		"pull of repo prod failed", "check the deploy key at /data/keys/prod.key")

	var er contract.ErrorResponse
	if err := json.NewDecoder(rec.Body).Decode(&er); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if !strings.Contains(er.Message, "pull of repo prod failed") {
		t.Errorf("message %q dropped the summary", er.Message)
	}
	if !strings.Contains(er.Message, "check the deploy key") {
		t.Errorf("message %q dropped the hint", er.Message)
	}
}

// TestWriteGitErrorUsesTypedCode proves writeGitError routes a
// *git.Error through statusForCode rather than a per-handler switch.
func TestWriteGitErrorUsesTypedCode(t *testing.T) {
	cases := []struct {
		code string
		want int
	}{
		{contract.ErrCodeGitSSHHandshake, http.StatusForbidden},
		{contract.ErrCodeGitNonFastForward, http.StatusConflict},
		{contract.ErrCodeGitCloneMissing, http.StatusNotFound},
		{contract.ErrCodeRunInvalidDir, http.StatusBadRequest},
		{contract.ErrCodeRunUnknownRepo, http.StatusNotFound},
		{contract.ErrCodeRunTofuNotFound, http.StatusServiceUnavailable},
	}
	for _, c := range cases {
		t.Run(c.code, func(t *testing.T) {
			rec := httptest.NewRecorder()
			writeGitError(rec, &git.Error{Code: c.code, Message: "boom", Hint: "fix it"})

			if rec.Code != c.want {
				t.Errorf("status = %d, want %d", rec.Code, c.want)
			}
			var er contract.ErrorResponse
			if err := json.NewDecoder(rec.Body).Decode(&er); err != nil {
				t.Fatalf("decode: %v", err)
			}
			if er.ErrorCode != c.code {
				t.Errorf("error_code = %q, want %q", er.ErrorCode, c.code)
			}
		})
	}
}

// TestWriteGitErrorUnwrapsWrappedError proves errors.As is used (not a
// type assertion), so a %w-wrapped *git.Error still maps correctly.
func TestWriteGitErrorUnwrapsWrappedError(t *testing.T) {
	wrapped := fmt.Errorf("jobq: submit: %w",
		&git.Error{Code: contract.ErrCodeRunUnknownRepo, Message: "unknown repo prod"})

	rec := httptest.NewRecorder()
	writeGitError(rec, wrapped)

	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404", rec.Code)
	}
	if er := decodeErr(t, rec); er.ErrorCode != contract.ErrCodeRunUnknownRepo {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeRunUnknownRepo)
	}
}

// TestWriteGitErrorOpaqueFallback proves an untyped error becomes a
// generic 500 whose body carries no part of the original error string
// (GIT-04: no stack traces, no file paths, no stderr).
func TestWriteGitErrorOpaqueFallback(t *testing.T) {
	rec := httptest.NewRecorder()
	writeGitError(rec, errors.New("open /data/runs/ABC/meta.json: permission denied\ngoroutine 7"))

	if rec.Code != http.StatusInternalServerError {
		t.Fatalf("status = %d, want 500 (body %q)", rec.Code, rec.Body.String())
	}
	er := decodeErr(t, rec)
	if er.ErrorCode != contract.ErrCodeApplyFailed {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeApplyFailed)
	}

	raw := rec.Body.String()
	for _, leak := range []string{"/data/", "goroutine", "permission denied"} {
		if strings.Contains(raw, leak) {
			t.Errorf("response body leaked %q: %s", leak, raw)
		}
	}
}
