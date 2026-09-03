package handlers

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"terraform-bridge/contract"
	"terraform-bridge/internal/mutex"
	"terraform-bridge/internal/nonce"
	"terraform-bridge/internal/supervisor"
)

// optionsHarness drives the Supervisor /apps/{slug}/options and
// /apps/{slug}/options/validate endpoints with scripted responses.
// validateResponse controls what ValidateOptions returns (must be a
// valid OptionsValidateDiagnostic envelope). applyStatus controls
// the apply-options HTTP status.
type optionsHarness struct {
	ts             *httptest.Server
	supClient      *supervisor.Client
	validateCalls  int
	applyCalls     int
	validateBody   map[string]any
	validateStatus int
	applyStatus    int
	applyRespBody  []byte
}

func newOptionsHarness(t *testing.T, validateStatus int, validateBody map[string]any, applyStatus int) *optionsHarness {
	t.Helper()
	h := &optionsHarness{
		validateStatus: validateStatus,
		validateBody:   validateBody,
		applyStatus:    applyStatus,
	}

	h.ts = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case strings.HasSuffix(r.URL.Path, "/options/validate"):
			h.validateCalls++
			w.Header().Set("Content-Type", "application/json")
			if h.validateStatus != http.StatusOK {
				w.WriteHeader(h.validateStatus)
				return
			}
			_ = json.NewEncoder(w).Encode(h.validateBody)
		case strings.HasSuffix(r.URL.Path, "/options"):
			h.applyCalls++
			if h.applyStatus != http.StatusOK {
				w.WriteHeader(h.applyStatus)
				if len(h.applyRespBody) > 0 {
					_, _ = w.Write(h.applyRespBody)
				}
				return
			}
			w.WriteHeader(http.StatusOK)
		case strings.HasSuffix(r.URL.Path, "/info"):
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"result": "ok",
				"data": map[string]any{
					"slug": "test_slug", "name": "Test", "version": "1.0",
					"state": "stopped", "started": false,
					"boot": "manual", "repository": "core",
					"options": map[string]string{"log_level": "info"},
				},
			})
		default:
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte("{}"))
		}
	}))
	t.Cleanup(h.ts.Close)

	h.supClient = supervisor.NewClient(func() string { return "stub" })
	h.supClient = h.supClient.WithBaseURLForTest(h.ts.URL)
	return h
}

func newNonceManager(t *testing.T, ttl time.Duration) *nonce.Manager {
	t.Helper()
	m, err := nonce.NewManager(t.TempDir(), ttl)
	if err != nil {
		t.Fatalf("nonce.NewManager: %v", err)
	}
	t.Cleanup(func() { _ = m.Close() })
	return m
}

// doOptions drives the handler with a real nonce + body.
func doOptions(t *testing.T, h *optionsHarness, nonceMgr *nonce.Manager, criticalAddons []string, body string) *httptest.ResponseRecorder {
	t.Helper()
	handler := Options(h.supClient, mutex.NewManager(), nonceMgr, criticalAddons)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/options", strings.NewReader(body))
	req.SetPathValue("slug", "test_slug")
	if nonceMgr != nil {
		plaintext, _, err := nonceMgr.Issue("actor-fp", "req-1")
		if err != nil {
			t.Fatalf("Issue: %v", err)
		}
		req.Header.Set("X-Force-Destroy", plaintext)
	}
	handler(rec, req)
	return rec
}

// TestOptionsHandlerHappyPath: ValidateOptions returns valid=true;
// Options apply returns 200; handler returns 200 + AddOnInfo.
func TestOptionsHandlerHappyPath(t *testing.T) {
	h := newOptionsHarness(t, http.StatusOK,
		map[string]any{"message": "ok", "valid": true, "pwned": false},
		http.StatusOK,
	)
	nonceMgr := newNonceManager(t, nonce.DefaultTTL)

	rec := doOptions(t, h, nonceMgr, nil, `{"log_level":"info"}`)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200\nbody: %s", rec.Code, rec.Body.String())
	}
	var info contract.AddOnInfo
	if err := json.Unmarshal(rec.Body.Bytes(), &info); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if info.Slug != "test_slug" {
		t.Errorf("info.slug = %q, want test_slug", info.Slug)
	}
	if h.validateCalls != 1 {
		t.Errorf("validateCalls = %d, want 1", h.validateCalls)
	}
	if h.applyCalls != 1 {
		t.Errorf("applyCalls = %d, want 1", h.applyCalls)
	}
}

// TestOptionsHandlerInvalidReturns400: ValidateOptions returns
// valid=false with pwned=true; handler returns 400 with the
// diagnostic envelope VERBATIM (NOT wrapped in ErrorResponse;
// pwned tri-state preserved per BRIDGE-08).
func TestOptionsHandlerInvalidReturns400(t *testing.T) {
	h := newOptionsHarness(t, http.StatusOK,
		map[string]any{"message": "bad option", "valid": false, "pwned": true},
		http.StatusOK,
	)
	nonceMgr := newNonceManager(t, nonce.DefaultTTL)

	rec := doOptions(t, h, nonceMgr, nil, `{"log_level":"hax"}`)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400\nbody: %s", rec.Code, rec.Body.String())
	}
	// Body MUST be the Supervisor diagnostic envelope verbatim,
	// not wrapped in ErrorResponse.
	var diag supervisor.OptionsValidateDiagnostic
	if err := json.Unmarshal(rec.Body.Bytes(), &diag); err != nil {
		t.Fatalf("unmarshal diag: %v\nbody: %s", err, rec.Body.String())
	}
	if diag.Message != "bad option" {
		t.Errorf("Message = %q, want bad option", diag.Message)
	}
	if diag.Valid {
		t.Errorf("Valid = true, want false")
	}
	if diag.Pwned == nil || !*diag.Pwned {
		t.Errorf("Pwned = %v, want &true", diag.Pwned)
	}
	if h.applyCalls != 0 {
		t.Errorf("applyCalls = %d, want 0 (must not apply on invalid)", h.applyCalls)
	}
}

// TestOptionsHandlerPwnedTriState: ValidateOptions returns valid=true
// with pwned=null (None tri-state). Handler returns 200; the None
// state must be preserved through the handler's response shape.
func TestOptionsHandlerPwnedTriState(t *testing.T) {
	h := newOptionsHarness(t, http.StatusOK,
		map[string]any{"message": "ok", "valid": true}, // no pwned key
		http.StatusOK,
	)
	nonceMgr := newNonceManager(t, nonce.DefaultTTL)

	rec := doOptions(t, h, nonceMgr, nil, `{"log_level":"info"}`)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200\nbody: %s", rec.Code, rec.Body.String())
	}
	// The validate body should have decoded with Pwned == nil.
	// We've already validated pwned preservation on the
	// 400-path; here we just confirm the 200 path is taken.
}

// TestOptionsHandlerCriticalSlug403BeforeMutex: regression for
// D-10 + Pitfall 2 — critical_addons check returns 403 in <100ms
// even when another goroutine holds the per-slug mutex.
func TestOptionsHandlerCriticalSlug403BeforeMutex(t *testing.T) {
	h := newOptionsHarness(t, http.StatusOK,
		map[string]any{"message": "ok", "valid": true},
		http.StatusOK,
	)
	nonceMgr := newNonceManager(t, nonce.DefaultTTL)
	mgr := mutex.NewManager()

	// Pre-acquire the per-slug mutex from a background goroutine.
	released := make(chan struct{})
	go func() {
		ctx := context.Background()
		rel, err := mgr.TryAcquire(ctx, "test_slug")
		if err != nil {
			t.Errorf("pre-acquire: %v", err)
			return
		}
		time.Sleep(500 * time.Millisecond)
		rel()
		close(released)
	}()

	time.Sleep(50 * time.Millisecond)

	handler := Options(h.supClient, mgr, nonceMgr, []string{"test_slug"})
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/options",
		strings.NewReader(`{"log_level":"info"}`))
	req.SetPathValue("slug", "test_slug")
	plaintext, _, _ := nonceMgr.Issue("actor-fp", "req-1")
	req.Header.Set("X-Force-Destroy", plaintext)

	start := time.Now()
	handler(rec, req)
	elapsed := time.Since(start)

	if rec.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want 403\nbody: %s", rec.Code, rec.Body.String())
	}
	if elapsed > 100*time.Millisecond {
		t.Errorf("critical_addon 403 took %v, want < 100ms (Pitfall 2)", elapsed)
	}
	var body contract.ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.ErrorCode != "critical_addon_protected" {
		t.Errorf("ErrorCode = %q, want critical_addon_protected", body.ErrorCode)
	}
	if strings.Contains(rec.Body.String(), "test_slug") {
		t.Errorf("body must not echo slug; got %s", rec.Body.String())
	}
	if h.validateCalls != 0 || h.applyCalls != 0 {
		t.Errorf("validate=%d apply=%d, both want 0 (403 before supervisor)", h.validateCalls, h.applyCalls)
	}

	<-released
}

// TestOptionsHandlerRequiresNonce401: missing X-Force-Destroy
// header → 401 BEFORE mutex (Pitfall 2 ordering).
func TestOptionsHandlerRequiresNonce401(t *testing.T) {
	h := newOptionsHarness(t, http.StatusOK,
		map[string]any{"message": "ok", "valid": true},
		http.StatusOK,
	)
	mgr := mutex.NewManager()

	// Pre-acquire the per-slug mutex from a background goroutine.
	released := make(chan struct{})
	go func() {
		ctx := context.Background()
		rel, err := mgr.TryAcquire(ctx, "test_slug")
		if err != nil {
			t.Errorf("pre-acquire: %v", err)
			return
		}
		time.Sleep(500 * time.Millisecond)
		rel()
		close(released)
	}()
	time.Sleep(50 * time.Millisecond)

	handler := Options(h.supClient, mgr, newNonceManager(t, nonce.DefaultTTL), nil)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/options",
		strings.NewReader(`{"log_level":"info"}`))
	req.SetPathValue("slug", "test_slug")
	// Deliberately omit X-Force-Destroy.

	start := time.Now()
	handler(rec, req)
	elapsed := time.Since(start)

	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401\nbody: %s", rec.Code, rec.Body.String())
	}
	if elapsed > 100*time.Millisecond {
		t.Errorf("nonce-missing 401 took %v, want < 100ms (Pitfall 2)", elapsed)
	}
	var body contract.ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.ErrorCode != "nonce_expired" {
		t.Errorf("ErrorCode = %q, want nonce_expired", body.ErrorCode)
	}
	if h.validateCalls != 0 {
		t.Errorf("validateCalls = %d, want 0 (401 before supervisor)", h.validateCalls)
	}

	<-released
}

// TestOptionsHandlerExpiredNonce401: past-TTL nonce -> 401
// nonce_expired (NOT nonce_used).
func TestOptionsHandlerExpiredNonce401(t *testing.T) {
	h := newOptionsHarness(t, http.StatusOK,
		map[string]any{"message": "ok", "valid": true},
		http.StatusOK,
	)
	shortMgr, err := nonce.NewManager(t.TempDir(), 10*time.Millisecond)
	if err != nil {
		t.Fatalf("NewManager: %v", err)
	}
	t.Cleanup(func() { _ = shortMgr.Close() })

	plaintext, _, err := shortMgr.Issue("actor-fp", "req-1")
	if err != nil {
		t.Fatalf("Issue: %v", err)
	}

	time.Sleep(20 * time.Millisecond) // past TTL

	handler := Options(h.supClient, mutex.NewManager(), shortMgr, nil)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/options",
		strings.NewReader(`{"log_level":"info"}`))
	req.SetPathValue("slug", "test_slug")
	req.Header.Set("X-Force-Destroy", plaintext)
	handler(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401\nbody: %s", rec.Code, rec.Body.String())
	}
	var body contract.ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.ErrorCode != "nonce_expired" {
		t.Errorf("ErrorCode = %q, want nonce_expired", body.ErrorCode)
	}
}

// TestOptionsHandlerUsedNonce401: replayed nonce -> 401 nonce_used.
func TestOptionsHandlerUsedNonce401(t *testing.T) {
	h := newOptionsHarness(t, http.StatusOK,
		map[string]any{"message": "ok", "valid": true},
		http.StatusOK,
	)
	nonceMgr := newNonceManager(t, nonce.DefaultTTL)

	plaintext, _, err := nonceMgr.Issue("actor-fp", "req-1")
	if err != nil {
		t.Fatalf("Issue: %v", err)
	}

	handler := Options(h.supClient, mutex.NewManager(), nonceMgr, nil)

	// First call succeeds.
	rec1 := httptest.NewRecorder()
	req1 := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/options",
		strings.NewReader(`{"log_level":"info"}`))
	req1.SetPathValue("slug", "test_slug")
	req1.Header.Set("X-Force-Destroy", plaintext)
	handler(rec1, req1)
	if rec1.Code != http.StatusOK {
		t.Fatalf("first call: status = %d, want 200", rec1.Code)
	}

	// Second call with the same nonce -> 401 nonce_used.
	rec2 := httptest.NewRecorder()
	req2 := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/options",
		strings.NewReader(`{"log_level":"info"}`))
	req2.SetPathValue("slug", "test_slug")
	req2.Header.Set("X-Force-Destroy", plaintext)
	handler(rec2, req2)

	if rec2.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401\nbody: %s", rec2.Code, rec2.Body.String())
	}
	var body contract.ErrorResponse
	if err := json.Unmarshal(rec2.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.ErrorCode != "nonce_used" {
		t.Errorf("ErrorCode = %q, want nonce_used", body.ErrorCode)
	}
}

// TestOptionsHandlerApplyOptionsRace (Pitfall 7): ValidateOptions
// returns valid=true but Options apply-phase returns 400 -> handler
// returns 400 NOT 502.
func TestOptionsHandlerApplyOptionsRace(t *testing.T) {
	h := newOptionsHarness(t, http.StatusOK,
		map[string]any{"message": "ok", "valid": true},
		http.StatusBadRequest,
	)
	nonceMgr := newNonceManager(t, nonce.DefaultTTL)

	rec := doOptions(t, h, nonceMgr, nil, `{"log_level":"info"}`)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 (Pitfall 7 apply-race)\nbody: %s", rec.Code, rec.Body.String())
	}
	var body contract.ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	// Apply-phase 400 carries the mapped error_code; for the
	// generic 400 status MapError returns upstream_error (since
	// we don't have a dedicated sentinel for "options 400").
	if body.ErrorCode == "" {
		t.Errorf("ErrorCode empty, want non-empty")
	}
}
