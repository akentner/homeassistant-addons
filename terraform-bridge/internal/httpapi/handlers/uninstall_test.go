package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"log/slog"
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

func newTestUninstallStack(t *testing.T, critical []string, uninstallStatus int) (*supervisor.Client, *nonce.Manager, *mutex.Manager, *httptest.Server) {
	t.Helper()

	var calls atomic.Int32
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		if r.URL.Path == "/apps/test_slug/uninstall" || r.URL.Path == "/addons/test_slug/uninstall" {
			w.WriteHeader(uninstallStatus)
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("{}"))
	}))
	t.Cleanup(ts.Close)

	supClient := supervisor.NewClient(func() string { return "stub" })
	supClient = supClient.WithBaseURLForTest(ts.URL)

	m, err := nonce.NewManager(t.TempDir(), nonce.DefaultTTL)
	if err != nil {
		t.Fatalf("NewManager: %v", err)
	}
	t.Cleanup(func() { _ = m.Close() })

	mgr := mutex.NewManager()

	return supClient, m, mgr, ts
}

func contextWithAuth(r *http.Request, plaintext string) *http.Request {
	return r.WithContext(r.Context())
	// Note: the handler reads the actor plaintext via auth.ActorTokenContextKey.
	// For handler-level tests we leave the value empty; the fingerprint
	// then is the empty-string fingerprint, which still asserts the
	// slog scrubber invariant. The router-level test (TestRouterUninstallEndToEnd)
	// covers the full auth path.
}

func TestUninstallNonCriticalSlug(t *testing.T) {
	supClient, nonceMgr, mutexMgr, _ := newTestUninstallStack(t, nil, http.StatusOK)
	h := Uninstall(supClient, mutexMgr, nonceMgr, nil)

	plaintext, _, err := nonceMgr.Issue("actor-fp", "req-1")
	if err != nil {
		t.Fatalf("Issue: %v", err)
	}

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/uninstall", nil)
	req.SetPathValue("slug", "test_slug")
	req.Header.Set("X-Force-Destroy", plaintext)
	h(rec, req.WithContext(contextWithAuth(req, "actor-plaintext").Context()))

	if rec.Code != http.StatusNoContent {
		t.Fatalf("status = %d, want 204\nbody: %s", rec.Code, rec.Body.String())
	}
}

func TestUninstallCriticalSlug403BeforeMutex(t *testing.T) {
	// PITFALLS Pitfall 2 regression: the critical_addons check
	// returns 403 in <100ms even when another goroutine holds
	// the per-slug mutex. We block the mutex for 500ms from a
	// parallel goroutine; the critical-slug 403 must arrive
	// much sooner than the mutex would be released.
	supClient, nonceMgr, mutexMgr, _ := newTestUninstallStack(t, []string{"core_mosquitto"}, http.StatusOK)
	mgr := mutexMgr
	_ = mgr

	// Pre-acquire the per-slug mutex from a background goroutine.
	released := make(chan struct{})
	go func() {
		ctx := context.Background()
		rel, err := mgr.TryAcquire(ctx, "core_mosquitto")
		if err != nil {
			t.Errorf("pre-acquire: %v", err)
			return
		}
		time.Sleep(500 * time.Millisecond)
		rel()
		close(released)
	}()

	// Give the goroutine a moment to actually acquire the lock.
	time.Sleep(50 * time.Millisecond)

	h := Uninstall(supClient, mgr, nonceMgr, []string{"core_mosquitto"})
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/core_mosquitto/uninstall", nil)
	req.SetPathValue("slug", "core_mosquitto")
	// Even with a missing/valid X-Force-Destroy the 403 must
	// come back BEFORE the X-Force-Destroy check.
	req.Header.Set("X-Force-Destroy", "anynonce")

	start := time.Now()
	h(rec, req.WithContext(contextWithAuth(req, "actor").Context()))
	elapsed := time.Since(start)

	if rec.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want 403\nbody: %s", rec.Code, rec.Body.String())
	}
	if elapsed > 100*time.Millisecond {
		t.Errorf("critical_addon 403 took %v, want < 100ms (Pitfall 2 regression)", elapsed)
	}

	// 403 body must be byte-exact {error_code: critical_addon_protected}.
	var body contract.ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.ErrorCode != "critical_addon_protected" {
		t.Errorf("ErrorCode = %q, want critical_addon_protected", body.ErrorCode)
	}
	if strings.Contains(rec.Body.String(), "core_mosquitto") {
		t.Errorf("body must not echo slug; got %s", rec.Body.String())
	}

	// Wait for the mutex-holder goroutine to finish so its
	// use-after-close doesn't bite us.
	<-released
}

func TestUninstallMissingNonceHeader401(t *testing.T) {
	supClient, nonceMgr, mutexMgr, _ := newTestUninstallStack(t, nil, http.StatusOK)
	h := Uninstall(supClient, mutexMgr, nonceMgr, nil)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/uninstall", nil)
	req.SetPathValue("slug", "test_slug")
	// No X-Force-Destroy header.
	h(rec, contextWithAuth(req, "actor"))

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

func TestUninstallExpiredNonce401(t *testing.T) {
	supClient, nonceMgr, mutexMgr, _ := newTestUninstallStack(t, nil, http.StatusOK)
	// Construct a Manager with a tight TTL so the nonce expires
	// immediately after issuance.
	shortMgr, err := nonce.NewManager(t.TempDir(), 10*time.Millisecond)
	if err != nil {
		t.Fatalf("NewManager: %v", err)
	}
	t.Cleanup(func() { _ = shortMgr.Close() })

	h := Uninstall(supClient, mutexMgr, shortMgr, nil)

	plaintext, _, err := shortMgr.Issue("actor-fp", "req-1")
	if err != nil {
		t.Fatalf("Issue: %v", err)
	}

	time.Sleep(20 * time.Millisecond) // past TTL

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/uninstall", nil)
	req.SetPathValue("slug", "test_slug")
	req.Header.Set("X-Force-Destroy", plaintext)
	h(rec, contextWithAuth(req, "actor"))

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

	// Suppress unused warning: nonceMgr is not used by this test.
	_ = nonceMgr
}

func TestUninstallUsedNonce401(t *testing.T) {
	supClient, nonceMgr, mutexMgr, _ := newTestUninstallStack(t, nil, http.StatusOK)
	h := Uninstall(supClient, mutexMgr, nonceMgr, nil)

	plaintext, _, err := nonceMgr.Issue("actor-fp", "req-1")
	if err != nil {
		t.Fatalf("Issue: %v", err)
	}

	// First call: a happy-path invocation succeeds.
	rec1 := httptest.NewRecorder()
	req1 := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/uninstall", nil)
	req1.SetPathValue("slug", "test_slug")
	req1.Header.Set("X-Force-Destroy", plaintext)
	h(rec1, contextWithAuth(req1, "actor"))
	if rec1.Code != http.StatusNoContent {
		t.Fatalf("first call: status = %d, want 204", rec1.Code)
	}

	// Second call with the same nonce -> 401 nonce_used.
	rec2 := httptest.NewRecorder()
	req2 := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/uninstall", nil)
	req2.SetPathValue("slug", "test_slug")
	req2.Header.Set("X-Force-Destroy", plaintext)
	h(rec2, contextWithAuth(req2, "actor"))

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

func TestUninstallSupervisorErrorMaps(t *testing.T) {
	cases := []struct {
		name     string
		httpIn   int
		errInj   error
		wantCode int
		wantBody string
	}{
		{"ErrLocked -> 423", http.StatusLocked, supervisor.ErrLocked, http.StatusLocked, "locked"},
		{"ErrCriticalAddon -> 403", http.StatusForbidden, supervisor.ErrCriticalAddon, http.StatusForbidden, "critical_addon_protected"},
		{"ErrAlreadyInstalled -> 409", http.StatusConflict, supervisor.ErrAlreadyInstalled, http.StatusConflict, "already_installed"},
		{"ErrTransient -> 502", http.StatusInternalServerError, supervisor.ErrTransient, http.StatusBadGateway, "upstream_error"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			// Build a custom stack whose Supervisor stub returns
			// tc.httpIn on /apps/<slug>/uninstall.
			supClient := supervisor.NewClient(func() string { return "stub" })
			ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path == "/apps/test_slug/uninstall" || r.URL.Path == "/addons/test_slug/uninstall" {
					w.WriteHeader(tc.httpIn)
					return
				}
				w.WriteHeader(http.StatusOK)
			}))
			defer ts.Close()
			supClient = supClient.WithBaseURLForTest(ts.URL)

			nonceMgr, err := nonce.NewManager(t.TempDir(), nonce.DefaultTTL)
			if err != nil {
				t.Fatalf("NewManager: %v", err)
			}
			t.Cleanup(func() { _ = nonceMgr.Close() })

			plaintext, _, err := nonceMgr.Issue("actor-fp", "req-1")
			if err != nil {
				t.Fatalf("Issue: %v", err)
			}
			h := Uninstall(supClient, mutex.NewManager(), nonceMgr, nil)

			rec := httptest.NewRecorder()
			req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/uninstall", nil)
			req.SetPathValue("slug", "test_slug")
			req.Header.Set("X-Force-Destroy", plaintext)
			h(rec, contextWithAuth(req, "actor"))

			if rec.Code != tc.wantCode {
				t.Errorf("status = %d, want %d\nbody: %s", rec.Code, tc.wantCode, rec.Body.String())
			}
			var body contract.ErrorResponse
			if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
				t.Fatalf("unmarshal: %v", err)
			}
			if body.ErrorCode != tc.wantBody {
				t.Errorf("ErrorCode = %q, want %q", body.ErrorCode, tc.wantBody)
			}

			_ = tc.errInj // not used directly; we drive the supervisor status code
		})
	}
}

func TestUninstallLogsFingerprintNotPlaintext(t *testing.T) {
	// PITFALLS S-1: capture slog output, issue a nonce, attempt
	// uninstall with a wrong nonce -> 401 nonce_expired. The
	// captured logs must NOT contain the plaintext nonce.
	var buf bytes.Buffer
	oldLogger := slog.Default()
	slog.SetDefault(slog.New(slog.NewJSONHandler(&buf, &slog.HandlerOptions{Level: slog.LevelInfo})))
	t.Cleanup(func() { slog.SetDefault(oldLogger) })

	supClient, nonceMgr, mutexMgr, _ := newTestUninstallStack(t, nil, http.StatusOK)
	h := Uninstall(supClient, mutexMgr, nonceMgr, nil)

	// Issue a nonce - get the plaintext from the journal
	// indirectly via the manager.
	plaintext, _, err := nonceMgr.Issue("actor-fp", "req-1")
	if err != nil {
		t.Fatalf("Issue: %v", err)
	}

	// Now drive the handler with a WRONG nonce to trigger the
	// nonce-expired log path.
	wrong := "thisisthewrongnoncedefinitelynottheissuedonethisismorethan43charsaactually"
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/uninstall", nil)
	req.SetPathValue("slug", "test_slug")
	req.Header.Set("X-Force-Destroy", wrong)
	h(rec, contextWithAuth(req, "actor"))

	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401\nbody: %s", rec.Code, rec.Body.String())
	}
	if bytes.Contains(buf.Bytes(), []byte(plaintext)) {
		t.Errorf("slog output contains plaintext issued nonce:\n%s", buf.String())
	}
	if !bytes.Contains(buf.Bytes(), []byte("nonce_fp")) {
		t.Errorf("slog output missing nonce_fp fingerprint:\n%s", buf.String())
	}
}

func TestUninstallAuthContextIsDefensive(t *testing.T) {
	// No actor-token context value (defensive 401 path; the
	// router normally gates this via RequireBearer but we
	// assert the handler does not panic).
	supClient := supervisor.NewClient(func() string { return "stub" })
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer ts.Close()
	supClient = supClient.WithBaseURLForTest(ts.URL)

	nonceMgr, err := nonce.NewManager(t.TempDir(), nonce.DefaultTTL)
	if err != nil {
		t.Fatalf("NewManager: %v", err)
	}
	t.Cleanup(func() { _ = nonceMgr.Close() })

	plaintext, _, err := nonceMgr.Issue("actor-fp", "req-1")
	if err != nil {
		t.Fatalf("Issue: %v", err)
	}
	h := Uninstall(supClient, mutex.NewManager(), nonceMgr, nil)

	// Provide neither Authorization nor auth context — the
	// handler should still respond correctly without panic.
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/uninstall", nil)
	req.SetPathValue("slug", "test_slug")
	req.Header.Set("X-Force-Destroy", plaintext)
	// Deliberately do NOT inject auth context.
	h(rec, req)

	if rec.Code == 0 {
		t.Fatal("handler did not write a response")
	}
}

func TestSupervisorClientMapErrorContract(t *testing.T) {
	// Sanity: verifies the sentinel->status mapping that's
	// used by Uninstall at runtime compiles and matches the
	// Phase 12 spec table.
	status, code := supervisor.MapError(supervisor.ErrLocked)
	if status != http.StatusLocked || code != "locked" {
		t.Errorf("MapError(ErrLocked) = (%d, %s), want (423, locked)", status, code)
	}
	status, code = supervisor.MapError(supervisor.ErrAlreadyInstalled)
	if status != http.StatusConflict || code != "already_installed" {
		t.Errorf("MapError(ErrAlreadyInstalled) = (%d, %s), want (409, already_installed)", status, code)
	}
	if !errors.Is(supervisor.ErrLocked, supervisor.ErrLocked) {
		t.Error("errors.Is invariant broken")
	}

	// Compile-time check that auth.Fingerprint exists.
	_ = auth.Fingerprint
}
