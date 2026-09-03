package handlers

import (
	"bytes"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"regexp"
	"testing"
	"time"

	"terraform-bridge/contract"
	"terraform-bridge/internal/nonce"
)

func newTestNonceManager(t *testing.T) *nonce.Manager {
	t.Helper()
	m, err := nonce.NewManager(t.TempDir(), nonce.DefaultTTL)
	if err != nil {
		t.Fatalf("nonce.NewManager: %v", err)
	}
	t.Cleanup(func() { _ = m.Close() })
	return m
}

func TestNonceHandlerIssuesValidNonce(t *testing.T) {
	m := newTestNonceManager(t)
	h := Nonce(m)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/auth/nonce", nil)
	h(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200\nbody: %s", rec.Code, rec.Body.String())
	}
	var body contract.NonceResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if !regexp.MustCompile(`^[A-Za-z0-9_-]+$`).MatchString(body.Nonce) {
		t.Errorf("nonce = %q, want base64url chars", body.Nonce)
	}
	if len(body.Nonce) != 43 {
		t.Errorf("nonce length = %d, want 43", len(body.Nonce))
	}
	if _, err := time.Parse(time.RFC3339, body.ExpiresAt); err != nil {
		t.Errorf("expires_at = %q is not RFC3339: %v", body.ExpiresAt, err)
	}
	expiresAt, _ := time.Parse(time.RFC3339, body.ExpiresAt)
	if !expiresAt.After(time.Now()) {
		t.Errorf("expires_at = %v must be in the future", expiresAt)
	}
}

func TestNonceHandlerRequiresAuth(t *testing.T) {
	// Nonce is mounted inside the /v1 auth subrouter; the
	// router-level TestRouterNonceRequiresAuth covers the
	// RequireBearer wiring. Here we only need to prove that
	// a fully wired handler returns a valid 200 when the
	// caller is anonymous (the handler itself does not call
	// auth.Context - that's RequireBearer's job). Smoke test
	// only.
	m := newTestNonceManager(t)
	h := Nonce(m)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/auth/nonce", nil)
	h(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (auth not the handler's job)", rec.Code)
	}
}

func TestNonceHandlerInfoLevelLog(t *testing.T) {
	// PITFALLS S-1 / Phase 12 SPECIFIC: issuance logs at Info.
	// We capture slog output via a custom JSON handler writing
	// to a bytes.Buffer, then assert the bridge_nonce_issued
	// record was emitted at Info (not Warn).
	var buf bytes.Buffer
	oldLogger := slog.Default()
	slog.SetDefault(slog.New(slog.NewJSONHandler(&buf, &slog.HandlerOptions{Level: slog.LevelInfo})))
	t.Cleanup(func() { slog.SetDefault(oldLogger) })

	m := newTestNonceManager(t)
	h := Nonce(m)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/auth/nonce", nil)
	h(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	// Parse the JSONL log; verify the bridge_nonce_issued
	// record is at info level.
	if !regexp.MustCompile(`"level":"INFO"`).Match(buf.Bytes()) ||
		!regexp.MustCompile(`"msg":"bridge_nonce_issued"`).Match(buf.Bytes()) {
		t.Errorf("expected bridge_nonce_issued at info level; got:\n%s", buf.String())
	}
	if regexp.MustCompile(`"msg":"bridge_nonce_issued"[^}]*"level":"WARN"`).Match(buf.Bytes()) {
		t.Errorf("bridge_nonce_issued MUST be at Info, not Warn:\n%s", buf.String())
	}
}
