package handlers

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"iac-runner/internal/contract"
	"iac-runner/internal/keys"
	"iac-runner/internal/statebackend"
)

// fakeBackend implements statebackend.Backend with a configurable
// CredentialFiles list. The healthz test uses it to drive the keys
// validator without dragging in a real factory + /data/keys setup.
type fakeBackend struct {
	creds []string
}

func (f *fakeBackend) Endpoint() string            { return "" }
func (f *fakeBackend) Bucket() string               { return "" }
func (f *fakeBackend) Region() string               { return "" }
func (f *fakeBackend) UseLockfile() bool            { return false }
func (f *fakeBackend) CredentialFiles() []string    { return f.creds }
func (f *fakeBackend) Name() string                 { return "fake" }

// TestHealthzBothPass: tofu IS on PATH (typical CI / dev env) AND
// the keys validator passes → 200 + HealthResponse with both flags
// true and the runner version echoed back.
func TestHealthzBothPass(t *testing.T) {
	dir := t.TempDir()
	keysDir := filepath.Join(dir, "keys")
	if err := os.MkdirAll(keysDir, 0o700); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(keysDir, "r2-access.key"), []byte("AKIA"), 0o600); err != nil {
		t.Fatalf("write: %v", err)
	}
	v := keys.NewValidator(keysDir, &fakeBackend{creds: []string{"r2-access.key"}})
	h := Healthz("0.1.0", v)

	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rec := httptest.NewRecorder()
	h(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("status = %d, want 200", rec.Code)
	}
	var body contract.HealthResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if body.Status != "ok" || !body.TofuOnPath || !body.KeysChmod600 || body.RunnerVersion != "0.1.0" {
		t.Errorf("body = %+v, want status=ok + both true + version=0.1.0", body)
	}
}

// TestHealthzValidatorFail: keys validator fails (one required file
// is mode 0644 instead of 0600) → 503 + EMPTY body
// (Content-Length: 0). This is the SEC-02 layer-2 invariant: even
// if the scrubbing handler is bypassed, the response body never
// names the offending file.
func TestHealthzValidatorFail(t *testing.T) {
	dir := t.TempDir()
	keysDir := filepath.Join(dir, "keys")
	if err := os.MkdirAll(keysDir, 0o700); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(keysDir, "r2-access.key"), []byte("AKIA"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	v := keys.NewValidator(keysDir, &fakeBackend{creds: []string{"r2-access.key"}})
	h := Healthz("0.1.0", v)

	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rec := httptest.NewRecorder()
	h(rec, req)

	if rec.Code != http.StatusServiceUnavailable {
		t.Errorf("status = %d, want 503", rec.Code)
	}
	if rec.Body.Len() != 0 {
		t.Errorf("body len = %d, want 0 (empty body on 503 per SEC-02 layer 2)", rec.Body.Len())
	}
	if got := rec.Header().Get("Content-Length"); got != "0" {
		t.Errorf("Content-Length = %q, want \"0\"", got)
	}
}

// TestHealthzKeysOnly: local backend (no required keys). If tofu
// IS on PATH → 200 + HealthResponse; if tofu is missing → 503 +
// empty body. The local-backend-no-required-keys shape is the
// "happy dev path" — no /data/keys directory needed.
func TestHealthzKeysOnly(t *testing.T) {
	dir := t.TempDir()
	keysDir := filepath.Join(dir, "keys")
	if err := os.MkdirAll(keysDir, 0o700); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	v := keys.NewValidator(keysDir, &fakeBackend{creds: nil})
	h := Healthz("0.1.0", v)

	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	rec := httptest.NewRecorder()
	h(rec, req)

	// The validator passes (no required files). Whether we get 200
	// or 503 depends on whether `tofu` is on PATH in the test
	// environment — both outcomes are valid; the body MUST be empty
	// when 503.
	switch rec.Code {
	case http.StatusOK:
		// tofu is on PATH — happy path, decode the body to assert
		// the structure.
		var body contract.HealthResponse
		if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
			t.Fatalf("decode: %v", err)
		}
		if !body.KeysChmod600 || body.RunnerVersion != "0.1.0" {
			t.Errorf("body = %+v, want KeysChmod600=true + version=0.1.0", body)
		}
	case http.StatusServiceUnavailable:
		// tofu is missing — body MUST be empty.
		if rec.Body.Len() != 0 {
			t.Errorf("body len = %d on 503, want 0 (empty body on 503)", rec.Body.Len())
		}
	default:
		t.Errorf("status = %d, want 200 or 503", rec.Code)
	}
}

// Compile-time check: statebackend.ErrUnsupported is referenced
// (preserved) so an inadvertent future refactor doesn't accidentally
// drop the only place we use it in this package.
var _ = statebackend.ErrUnsupported
