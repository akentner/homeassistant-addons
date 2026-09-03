package httpapi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"terraform-bridge/contract"
	"terraform-bridge/internal/auth"
)

func TestRouterVersionRequiresAuth(t *testing.T) {
	// NewFileTokenStore with an empty data dir returns a TokenStore
	// with no hash loaded. Any Validate call returns ErrInvalidToken.
	// We don't need to call Generate+Persist — we just need to prove
	// that RequireBearer is mounted on the /v1 subrouter and that
	// anonymous calls return 401 + {error_code: "unauthorized"}.
	store, err := auth.NewFileTokenStore(t.TempDir())
	if err != nil {
		t.Fatalf("NewFileTokenStore: %v", err)
	}

	router := NewRouter("0.1.0", store, nil /* supClient unused for this route */, time.Now(), "/data/terraform.tfstate")

	// Anonymous request -> RequireBearer returns 401.
	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, httptest.NewRequest("GET", "/v1/version", nil))
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401\nbody: %s", rec.Code, rec.Body.String())
	}
	var body contract.ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.ErrorCode != "unauthorized" {
		t.Errorf("ErrorCode = %q, want %q", body.ErrorCode, "unauthorized")
	}

	// /v1/info remains public (BRIDGE-10) - no RequireBearer.
	rec2 := httptest.NewRecorder()
	router.ServeHTTP(rec2, httptest.NewRequest("GET", "/v1/info", nil))
	if rec2.Code == http.StatusUnauthorized {
		t.Errorf("/v1/info must be public; got 401 with body %s", rec2.Body.String())
	}
}
