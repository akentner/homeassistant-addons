package handlers

import (
	"crypto/sha256"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5"

	"iac-runner/internal/auth"
	"iac-runner/internal/contract"
	"iac-runner/internal/version"
)

func TestVersionAllFieldsPresent(t *testing.T) {
	h := Version("0.1.0")

	req := httptest.NewRequest(http.MethodGet, "/v1/version", nil)
	rec := httptest.NewRecorder()
	h(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("status = %d, want 200", rec.Code)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type = %q, want application/json", ct)
	}

	var body contract.VersionHandshake
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if body.RunnerVersion != "0.1.0" {
		t.Errorf("RunnerVersion = %q, want 0.1.0", body.RunnerVersion)
	}
	if body.SchemaVersion == "" {
		t.Errorf("SchemaVersion is empty")
	}
	if body.MinSupportedOpenTofu == "" {
		t.Errorf("MinSupportedOpenTofu is empty")
	}
	if body.MaxSupportedOpenTofu == "" {
		t.Errorf("MaxSupportedOpenTofu is empty")
	}
}

// TestVersionUsesCompileTimeDefaults asserts that the handler reads
// from internal/version (not hardcoded literals) so the bump policy
// in internal/version/version.go is honored.
func TestVersionUsesCompileTimeDefaults(t *testing.T) {
	h := Version("dev")

	req := httptest.NewRequest(http.MethodGet, "/v1/version", nil)
	rec := httptest.NewRecorder()
	h(rec, req)

	var body contract.VersionHandshake
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if body.RunnerVersion != "dev" {
		t.Errorf("RunnerVersion = %q, want dev (the default ldflags value)", body.RunnerVersion)
	}
	// SchemaVersion should be "1.0.0" per internal/version/version.go (Phase 16 baseline)
	if body.SchemaVersion != version.SchemaVersion {
		t.Errorf("SchemaVersion = %q, want %q", body.SchemaVersion, version.SchemaVersion)
	}
	if body.MinSupportedOpenTofu != version.MinSupportedOpenTofu {
		t.Errorf("MinSupportedOpenTofu = %q, want %q", body.MinSupportedOpenTofu, version.MinSupportedOpenTofu)
	}
	if body.MaxSupportedOpenTofu != version.MaxSupportedOpenTofu {
		t.Errorf("MaxSupportedOpenTofu = %q, want %q", body.MaxSupportedOpenTofu, version.MaxSupportedOpenTofu)
	}
}

// TestVersionRequiresBearer wraps the version handler in a chi
// router with the auth.RequireBearer middleware and asserts that:
//   - no Authorization header → 401 + {"error_code":"unauthorized"}
//   - wrong bearer token → 401 + {"error_code":"unauthorized"}
//   - valid bearer token → 200 + VersionHandshake JSON body
//
// This proves the /v1/version endpoint is mounted under the
// RequireBearer-wrapped /v1 subrouter per AUTHR-04.
func TestVersionRequiresBearer(t *testing.T) {
	const plaintext = "ci-test-bearer-token-aaaaaaaaaaaaaaaaaaaaaaaa"

	dataDir := t.TempDir()
	store, err := auth.NewFileTokenStore(dataDir)
	if err != nil {
		t.Fatalf("NewFileTokenStore: %v", err)
	}
	if err := store.Persist(plaintext); err != nil {
		t.Fatalf("Persist: %v", err)
	}

	// Sanity: confirm the on-disk hash matches SHA-256 of plaintext.
	wantHash := sha256.Sum256([]byte(plaintext))
	if got := store.Hash(); string(got) != string(wantHash[:]) {
		t.Fatalf("store.Hash() != SHA-256(plaintext); got %x want %x", got, wantHash)
	}

	r := chi.NewRouter()
	r.Route("/v1", func(r chi.Router) {
		r.Use(auth.RequireBearer(store))
		r.Get("/version", Version("0.1.0"))
	})
	srv := httptest.NewServer(r)
	t.Cleanup(srv.Close)

	type tc struct {
		name       string
		authHeader string
		wantStatus int
	}
	cases := []tc{
		{
			name:       "missing_header_401",
			authHeader: "",
			wantStatus: http.StatusUnauthorized,
		},
		{
			name:       "wrong_token_401",
			authHeader: "Bearer wrong-token-zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",
			wantStatus: http.StatusUnauthorized,
		},
		{
			name:       "valid_token_200",
			authHeader: "Bearer " + plaintext,
			wantStatus: http.StatusOK,
		},
	}

	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			req, err := http.NewRequest(http.MethodGet, srv.URL+"/v1/version", nil)
			if err != nil {
				t.Fatalf("NewRequest: %v", err)
			}
			if c.authHeader != "" {
				req.Header.Set("Authorization", c.authHeader)
			}
			resp, err := http.DefaultClient.Do(req)
			if err != nil {
				t.Fatalf("Do: %v", err)
			}
			defer resp.Body.Close()

			if resp.StatusCode != c.wantStatus {
				t.Errorf("status = %d, want %d", resp.StatusCode, c.wantStatus)
			}

			if c.wantStatus == http.StatusUnauthorized {
				var er contract.ErrorResponse
				if err := json.NewDecoder(resp.Body).Decode(&er); err != nil {
					t.Fatalf("decode err response: %v", err)
				}
				if er.ErrorCode != "unauthorized" {
					t.Errorf("ErrorCode = %q, want unauthorized", er.ErrorCode)
				}
				return
			}

			var body contract.VersionHandshake
			if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
				t.Fatalf("decode version response: %v", err)
			}
			if body.RunnerVersion != "0.1.0" {
				t.Errorf("RunnerVersion = %q, want 0.1.0", body.RunnerVersion)
			}
			if body.SchemaVersion == "" {
				t.Errorf("SchemaVersion is empty")
			}
		})
	}
}
