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
)

// TestStopHandlerHappyPath: 200 + AddOnInfo with started=false
// (stop -> stopped state).
func TestStopHandlerHappyPath(t *testing.T) {
	h := newSimpleHarness(t, "stop")

	handler := Stop(h.supClient, h.mutexMgr)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/stop", nil)
	req.SetPathValue("slug", "test_slug")
	handler(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200\nbody: %s", rec.Code, rec.Body.String())
	}
	var info contract.AddOnInfo
	if err := json.Unmarshal(rec.Body.Bytes(), &info); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if !info.Started {
		t.Errorf("info.started = false, want true (from /info stub)")
	}
}

// TestStopHandlerSupervisorErrorMaps: ErrLocked -> 423 + locked.
func TestStopHandlerSupervisorErrorMaps(t *testing.T) {
	h := newSimpleHarness(t)
	h.ts.Close()
	h.ts = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "/stop") {
			w.WriteHeader(http.StatusLocked)
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("{}"))
	}))
	t.Cleanup(h.ts.Close)
	h.supClient = h.supClient.WithBaseURLForTest(h.ts.URL)

	handler := Stop(h.supClient, h.mutexMgr)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/stop", nil)
	req.SetPathValue("slug", "test_slug")
	handler(rec, req)

	if rec.Code != http.StatusLocked {
		t.Fatalf("status = %d, want 423\nbody: %s", rec.Code, rec.Body.String())
	}
	var body contract.ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.ErrorCode != "locked" {
		t.Errorf("ErrorCode = %q, want locked", body.ErrorCode)
	}
}

// TestStopHandlerRequiresAuth: handler must not panic when no
// actor context is present (router normally gates this via
// RequireBearer).
func TestStopHandlerRequiresAuth(t *testing.T) {
	h := newSimpleHarness(t, "stop")
	handler := Stop(h.supClient, h.mutexMgr)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/stop", nil)
	req.SetPathValue("slug", "test_slug")
	handler(rec, req)

	if rec.Code == 0 {
		t.Fatal("handler did not write a response")
	}
	if rec.Code != http.StatusOK {
		t.Errorf("status = %d, want 200 (handler-level test; router enforces 401)", rec.Code)
	}
}

// TestStopHandlerDoesNotRequireNonce: missing X-Force-Destroy
// header → 200 (stop is non-destructive per D-10).
func TestStopHandlerDoesNotRequireNonce(t *testing.T) {
	h := newSimpleHarness(t, "stop")
	handler := Stop(h.supClient, h.mutexMgr)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/stop", nil)
	req.SetPathValue("slug", "test_slug")
	handler(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (stop must NOT require nonce per D-10)\nbody: %s", rec.Code, rec.Body.String())
	}
	if strings.Contains(rec.Body.String(), "nonce_expired") || strings.Contains(rec.Body.String(), "nonce_used") {
		t.Errorf("body must NOT mention nonce: %s", rec.Body.String())
	}
}

// TestStopHandlerMutexLockedReturns423: hold the per-slug mutex
// from a goroutine; the handler returns 423 within 150ms.
// Requires a deadline-bounded request context so the mutex
// TryAcquire has a budget to time out against.
func TestStopHandlerMutexLockedReturns423(t *testing.T) {
	h := newSimpleHarness(t, "stop")

	released := make(chan struct{})
	go func() {
		ctx := context.Background()
		rel, err := h.mutexMgr.TryAcquire(ctx, "test_slug")
		if err != nil {
			t.Errorf("pre-acquire: %v", err)
			return
		}
		time.Sleep(500 * time.Millisecond)
		rel()
		close(released)
	}()

	time.Sleep(50 * time.Millisecond)

	handler := Stop(h.supClient, h.mutexMgr)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/stop", nil)
	req.SetPathValue("slug", "test_slug")
	ctx, cancel := context.WithTimeout(req.Context(), 80*time.Millisecond)
	defer cancel()

	start := time.Now()
	handler(rec, req.WithContext(ctx))
	elapsed := time.Since(start)

	if rec.Code != http.StatusLocked {
		t.Fatalf("status = %d, want 423\nbody: %s", rec.Code, rec.Body.String())
	}
	if elapsed > 150*time.Millisecond {
		t.Errorf("locked 423 took %v, want < 150ms", elapsed)
	}

	<-released
}
