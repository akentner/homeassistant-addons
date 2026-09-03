package handlers

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"regexp"
	"testing"

	"terraform-bridge/contract"
)

func TestStateIndexHandlerHappyPath(t *testing.T) {
	dir := t.TempDir()
	mustWriteFile(t, filepath.Join(dir, "terraform.tfstate"), []byte(`{"version":4}`))
	mustWriteFile(t, filepath.Join(dir, "terraform.tfstate.backup"), []byte(`{"backup":true}`))
	mustWriteFile(t, filepath.Join(dir, "terraform.tfstate.lock"), []byte("{}"))
	mustWriteFile(t, filepath.Join(dir, "README.md"), []byte("not state"))

	h := StateIndex(dir)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/v1/state/index", nil)
	h(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200\nbody: %s", rec.Code, rec.Body.String())
	}
	var body contract.StateIndexResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if len(body.Files) != 2 {
		t.Fatalf("files = %d, want 2 (tfstate.lock + README.md must be excluded): %+v", len(body.Files), body.Files)
	}
	if len(body.Skipped) != 0 {
		t.Errorf("skipped = %+v, want empty", body.Skipped)
	}
	for _, f := range body.Files {
		if !regexp.MustCompile(`^[a-f0-9]{64}$`).MatchString(f.SHA256) {
			t.Errorf("sha256 = %q, want hex64", f.SHA256)
		}
	}
}

func TestStateIndexHandlerEmpty(t *testing.T) {
	dir := t.TempDir()
	h := StateIndex(dir)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/v1/state/index", nil)
	h(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (empty result is valid, NOT 404)", rec.Code)
	}
	var body contract.StateIndexResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.Files == nil {
		t.Error("Files is nil, want []StateFileEntry{}")
	}
	if len(body.Files) != 0 {
		t.Errorf("Files len = %d, want 0", len(body.Files))
	}
}

func TestStateIndexHandlerRequiresAuth(t *testing.T) {
	// Router-level TestRouterStateIndexRequiresAuth covers the
	// RequireBearer wiring. The handler itself doesn't enforce
	// auth — that's the subrouter's job. Smoke test only.
	dir := t.TempDir()
	h := StateIndex(dir)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/v1/state/index", nil)
	h(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (auth is the router's job)", rec.Code)
	}
}

func TestStateIndexSkipsLockFiles(t *testing.T) {
	dir := t.TempDir()
	mustWriteFile(t, filepath.Join(dir, "terraform.tfstate.lock"), []byte("lock"))

	h := StateIndex(dir)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/v1/state/index", nil)
	h(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200\nbody: %s", rec.Code, rec.Body.String())
	}
	var body contract.StateIndexResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if len(body.Files) != 0 {
		t.Errorf("Files len = %d, want 0 (D-20 must skip *.tfstate.lock): %+v", len(body.Files), body.Files)
	}
}

func mustWriteFile(t *testing.T, path string, body []byte) {
	t.Helper()
	if err := os.WriteFile(path, body, 0o600); err != nil {
		t.Fatalf("WriteFile %s: %v", path, err)
	}
}
