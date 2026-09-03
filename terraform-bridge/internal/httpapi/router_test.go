package httpapi

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"terraform-bridge/contract"
	"terraform-bridge/internal/auth"
	"terraform-bridge/internal/mutex"
	"terraform-bridge/internal/nonce"
	"terraform-bridge/internal/supervisor"
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

	nonceMgr, err := nonce.NewManager(t.TempDir(), nonce.DefaultTTL)
	if err != nil {
		t.Fatalf("nonce.NewManager: %v", err)
	}
	t.Cleanup(func() { _ = nonceMgr.Close() })

	router := NewRouter("0.1.0", store, nil, /* supClient unused for this route */
		mutex.NewManager(), nonceMgr, nil, /* criticalAddons */
		time.Now(), "/data/terraform.tfstate",
		5*time.Second, 300*time.Second)

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

// TestRouterStateIndexRequiresAuth is the regression test for
// STATE-02 auth requirement: /v1/state/index MUST be inside
// the /v1 auth subrouter. Anonymous requests return 401.
func TestRouterStateIndexRequiresAuth(t *testing.T) {
	store, err := auth.NewFileTokenStore(t.TempDir())
	if err != nil {
		t.Fatalf("NewFileTokenStore: %v", err)
	}
	nonceMgr, err := nonce.NewManager(t.TempDir(), nonce.DefaultTTL)
	if err != nil {
		t.Fatalf("nonce.NewManager: %v", err)
	}
	t.Cleanup(func() { _ = nonceMgr.Close() })

	router := NewRouter("0.1.0", store, nil,
		mutex.NewManager(), nonceMgr, nil,
		time.Now(), "/data/terraform.tfstate",
		5*time.Second, 300*time.Second)

	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, httptest.NewRequest("GET", "/v1/state/index", nil))
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
}

// TestRouterNonceRequiresAuth is the regression test for the
// anti-CSRF invariant (DISCUSSION-LOG open items):
// /v1/auth/nonce MUST be mounted inside the /v1 auth subrouter.
// Anonymous requests return 401 — otherwise an attacker on the
// Tailscale network could trivially mint nonces and bypass
// X-Force-Destroy entirely.
func TestRouterNonceRequiresAuth(t *testing.T) {
	store, err := auth.NewFileTokenStore(t.TempDir())
	if err != nil {
		t.Fatalf("NewFileTokenStore: %v", err)
	}
	nonceMgr, err := nonce.NewManager(t.TempDir(), nonce.DefaultTTL)
	if err != nil {
		t.Fatalf("nonce.NewManager: %v", err)
	}
	t.Cleanup(func() { _ = nonceMgr.Close() })

	router := NewRouter("0.1.0", store, nil,
		mutex.NewManager(), nonceMgr, nil,
		time.Now(), "/data/terraform.tfstate",
		5*time.Second, 300*time.Second)

	rec := httptest.NewRecorder()
	router.ServeHTTP(rec, httptest.NewRequest("POST", "/v1/auth/nonce", nil))
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401 (anti-CSRF)\nbody: %s", rec.Code, rec.Body.String())
	}
	var body contract.ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.ErrorCode != "unauthorized" {
		t.Errorf("ErrorCode = %q, want %q", body.ErrorCode, "unauthorized")
	}
}

// TestRouterUninstallEndToEnd is the TRACER-level integration
// test for Phase 12. Full chain through the real router:
//
//   - valid bearer (persisted to a temp token store)
//   - POST /v1/auth/nonce -> 200 + NonceResponse
//   - POST /v1/addons/test_slug/uninstall with X-Force-Destroy +
//     Authorization -> 204
//   - The Supervisor mock received exactly one POST
//     /apps/test_slug/uninstall (proves mutex acquired + released
//   - nonce consumed).
func TestRouterUninstallEndToEnd(t *testing.T) {
	// Real TokenStore with a known bearer so the /v1 auth subrouter
	// accepts the calls below.
	plaintext := "test-bearer-token-43-chars-base64url-AAA"
	store, err := auth.NewFileTokenStore(t.TempDir())
	if err != nil {
		t.Fatalf("NewFileTokenStore: %v", err)
	}
	if err := store.Persist(plaintext); err != nil {
		t.Fatalf("Persist: %v", err)
	}

	// Stub Supervisor that records all inbound calls.
	var uninstallCalls atomic.Int32
	sup := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/apps/test_slug/uninstall" || r.URL.Path == "/addons/test_slug/uninstall":
			uninstallCalls.Add(1)
			w.WriteHeader(http.StatusOK)
		default:
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte("{}"))
		}
	}))
	t.Cleanup(sup.Close)

	supClient := supervisor.NewClient(func() string { return "stub" })
	supClient = supClient.WithBaseURLForTest(sup.URL)

	nonceMgr, err := nonce.NewManager(t.TempDir(), nonce.DefaultTTL)
	if err != nil {
		t.Fatalf("nonce.NewManager: %v", err)
	}
	t.Cleanup(func() { _ = nonceMgr.Close() })

	mutexMgr := mutex.NewManager()

	router := NewRouter("0.1.0", store, supClient,
		mutexMgr, nonceMgr, nil,
		time.Now(), "/data/terraform.tfstate",
		5*time.Second, 300*time.Second)

	// --- Step 1: POST /v1/auth/nonce -> 200 + {nonce, expires_at}
	rec1 := httptest.NewRecorder()
	req1 := httptest.NewRequest(http.MethodPost, "/v1/auth/nonce", nil)
	req1.Header.Set("Authorization", "Bearer "+plaintext)
	router.ServeHTTP(rec1, req1)
	if rec1.Code != http.StatusOK {
		t.Fatalf("nonce issuance status = %d, want 200\nbody: %s", rec1.Code, rec1.Body.String())
	}
	var nonceBody contract.NonceResponse
	if err := json.Unmarshal(rec1.Body.Bytes(), &nonceBody); err != nil {
		t.Fatalf("nonce unmarshal: %v", err)
	}
	if !strings.HasPrefix(nonceBody.Nonce, "test-bearer") && len(nonceBody.Nonce) != 43 {
		t.Errorf("nonce shape invalid: %+v", nonceBody)
	}

	// --- Step 2: POST /v1/addons/test_slug/uninstall with
	// X-Force-Destroy -> 204 No Content
	rec2 := httptest.NewRecorder()
	req2 := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/uninstall", nil)
	req2.Header.Set("Authorization", "Bearer "+plaintext)
	req2.Header.Set("X-Force-Destroy", nonceBody.Nonce)
	router.ServeHTTP(rec2, req2)
	if rec2.Code != http.StatusNoContent {
		t.Fatalf("uninstall status = %d, want 204\nbody: %s", rec2.Code, rec2.Body.String())
	}

	// --- Step 3: assert Supervisor received exactly one POST.
	if got := uninstallCalls.Load(); got != 1 {
		t.Errorf("supervisor install calls = %d, want 1", got)
	}

	// --- Step 4: replay the same nonce -> 401 nonce_used
	rec3 := httptest.NewRecorder()
	req3 := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/uninstall", nil)
	req3.Header.Set("Authorization", "Bearer "+plaintext)
	req3.Header.Set("X-Force-Destroy", nonceBody.Nonce)
	router.ServeHTTP(rec3, req3)
	if rec3.Code != http.StatusUnauthorized {
		t.Fatalf("nonce replay status = %d, want 401\nbody: %s", rec3.Code, rec3.Body.String())
	}
	if uninstallCalls.Load() != 1 {
		t.Errorf("supervisor install calls = %d, want still 1 (replay must NOT trigger Supervisor)", uninstallCalls.Load())
	}
}

// TestRouterAllPhase12EndpointsRequireAuth is the comprehensive
// anti-CSRF regression test for the entire Phase 12 write surface.
// It enumerates every new Phase 12 endpoint and asserts each
// returns HTTP 401 + {error_code: "unauthorized"} without a valid
// bearer. Guards the DISCUSSION-LOG Area F invariant: every
// mutating route MUST live behind the /v1 auth subrouter so an
// anonymous attacker on the Tailscale network cannot mint nonces,
// trigger destructive handlers, or enumerate state.
//
// Construction:
//
//   - Real TokenStore with a generated + persisted bearer (via
//     NewFileTokenStore + Persist) — proves RequireBearer is wired
//     by demonstrating the same route returns 200/204 WITH the
//     bearer.
//   - Real nonce.Manager with t.TempDir() journal (60s TTL per
//     CONTEXT D-06 / LIFE-03).
//   - Real mutex.Manager (per-slug write serialization).
//   - Stub Supervisor that 200s every path; only path-not-found
//     matters here because the handlers must short-circuit on
//     auth before reaching Supervisor.
//
// Sanity pass: fire the same routes WITH the valid bearer and
// assert the response status is NOT 401 — proves the auth
// middleware actually accepts the token (vs. silently rejecting
// due to a misconfigured store).
func TestRouterAllPhase12EndpointsRequireAuth(t *testing.T) {
	const bearer = "test-bearer-phase12-router-coverage-A"

	store, err := auth.NewFileTokenStore(t.TempDir())
	if err != nil {
		t.Fatalf("NewFileTokenStore: %v", err)
	}
	if err := store.Persist(bearer); err != nil {
		t.Fatalf("Persist: %v", err)
	}

	nonceMgr, err := nonce.NewManager(t.TempDir(), nonce.DefaultTTL)
	if err != nil {
		t.Fatalf("nonce.NewManager: %v", err)
	}
	t.Cleanup(func() { _ = nonceMgr.Close() })

	// Stub Supervisor — accept every path so a 401 short-circuit
	// cannot be hidden behind a downstream 4xx/5xx that would
	// confuse the assertions below. The /v1/addons/{slug}/info
	// endpoint used by the tracer re-fetch path expects a Supervisor
	// envelope, so we serve a minimal valid one.
	sup := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/apps/test_slug/info", "/addons/test_slug/info":
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			_, _ = fmt.Fprintf(w, `{"data":{"slug":"test_slug","name":"test_slug","version":"1.0.0","installed":true,"started":false,"available":true}}`)
		default:
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte("{}"))
		}
	}))
	t.Cleanup(sup.Close)

	supClient := supervisor.NewClient(func() string { return "stub" })
	supClient = supClient.WithBaseURLForTest(sup.URL)

	mutexMgr := mutex.NewManager()

	router := NewRouter("0.1.0", store, supClient,
		mutexMgr, nonceMgr, []string{"core_mosquitto"}, // non-empty so we exercise the critical-addons code path too
		time.Now(), "/data/terraform.tfstate",
		5*time.Second,        // tryLockTimeout: short — proves the middleware wraps ctx correctly
		500*time.Millisecond) // installJobTimeout: short — keeps the install route's polling loop bounded during the sanity pass (production uses 300s)

	// Every Phase 12 endpoint that Plan 01 + Plan 02 mounted inside
	// the /v1 auth subrouter. Order: read endpoints first, then
	// mutating endpoints in install/start/stop/uninstall/options
	// order (mirrors router.go). POST /v1/auth/rotate is a
	// pre-Phase-12 endpoint that also lives behind RequireBearer
	// — included so the enumeration covers the whole /v1/* surface.
	endpoints := []struct {
		route  string
		method string
	}{
		{"/v1/state/index", http.MethodGet},
		{"/v1/auth/nonce", http.MethodPost},
		{"/v1/addons/test_slug/install", http.MethodPost},
		{"/v1/addons/test_slug/uninstall", http.MethodPost},
		{"/v1/addons/test_slug/start", http.MethodPost},
		{"/v1/addons/test_slug/stop", http.MethodPost},
		{"/v1/addons/test_slug/options", http.MethodPost},
		{"/v1/auth/rotate", http.MethodPost},
	}

	// --- Anonymous pass: every endpoint must reject with 401 +
	// {error_code: "unauthorized"}.
	for _, ep := range endpoints {
		rec := httptest.NewRecorder()
		req := httptest.NewRequest(ep.method, ep.route, nil)
		// Intentionally NO Authorization header.
		router.ServeHTTP(rec, req)
		if rec.Code != http.StatusUnauthorized {
			t.Errorf("anonymous %s %s: status = %d, want 401\nbody: %s",
				ep.method, ep.route, rec.Code, rec.Body.String())
			continue
		}
		var body contract.ErrorResponse
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Errorf("anonymous %s %s: unmarshal: %v\nbody: %s",
				ep.method, ep.route, err, rec.Body.String())
			continue
		}
		if body.ErrorCode != "unauthorized" {
			t.Errorf("anonymous %s %s: error_code = %q, want %q\nbody: %s",
				ep.method, ep.route, body.ErrorCode, "unauthorized", rec.Body.String())
		}
	}

	// --- Sanity pass: every endpoint with the valid bearer must
	// NOT return 401 + {error_code: "unauthorized"} (proves
	// RequireBearer accepts the token, not that we have a
	// misconfigured TokenStore). Some routes (uninstall, options)
	// additionally require an X-Force-Destroy nonce — those return
	// 401 + nonce_expired when called without the nonce, which is
	// proof the bearer was accepted and the request reached the
	// downstream nonce check.
	for _, ep := range endpoints {
		rec := httptest.NewRecorder()
		req := httptest.NewRequest(ep.method, ep.route, nil)
		req.Header.Set("Authorization", "Bearer "+bearer)
		router.ServeHTTP(rec, req)
		if rec.Code != http.StatusUnauthorized {
			continue
		}
		var body contract.ErrorResponse
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Errorf("with bearer %s %s: 401 body unmarshal: %v\nbody: %s",
				ep.method, ep.route, err, rec.Body.String())
			continue
		}
		if body.ErrorCode == "unauthorized" {
			t.Errorf("with bearer %s %s: error_code = %q (auth middleware did NOT pass through); body: %s",
				ep.method, ep.route, body.ErrorCode, rec.Body.String())
		}
	}
}
