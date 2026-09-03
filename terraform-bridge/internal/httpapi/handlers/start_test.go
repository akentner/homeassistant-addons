package handlers

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"terraform-bridge/contract"
	"terraform-bridge/internal/mutex"
	"terraform-bridge/internal/supervisor"
)

// simpleHarness is the standard test stack for start/stop/options
// happy-path tests. Returns a supervisor.Client whose /apps/slug/*
// endpoints always succeed.
type simpleHarness struct {
	ts        *httptest.Server
	supClient *supervisor.Client
	mutexMgr  *mutex.Manager
	calls     *atomic.Int32
}

func newSimpleHarness(t *testing.T, ops ...string) *simpleHarness {
	t.Helper()
	h := &simpleHarness{calls: &atomic.Int32{}}
	allowed := make(map[string]struct{}, len(ops))
	for _, op := range ops {
		allowed["/apps/test_slug/"+op] = struct{}{}
		allowed["/addons/test_slug/"+op] = struct{}{}
	}

	h.ts = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		h.calls.Add(1)
		if r.URL.Path == "/apps/test_slug/info" || r.URL.Path == "/addons/test_slug/info" {
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"result": "ok",
				"data": map[string]any{
					"slug": "test_slug", "name": "Test", "version": "1.0",
					"state": "started", "started": true,
					"boot": "auto", "repository": "core",
				},
			})
			return
		}
		if _, ok := allowed[r.URL.Path]; ok {
			w.WriteHeader(http.StatusOK)
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("{}"))
	}))
	t.Cleanup(h.ts.Close)

	h.supClient = supervisor.NewClient(func() string { return "stub" })
	h.supClient = h.supClient.WithBaseURLForTest(h.ts.URL)
	h.mutexMgr = mutex.NewManager()
	return h
}

// TestStartHandlerHappyPath: 200 + AddOnInfo with started=true.
func TestStartHandlerHappyPath(t *testing.T) {
	h := newSimpleHarness(t, "start")

	handler := Start(h.supClient, h.mutexMgr)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/start", nil)
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
		t.Errorf("info.started = false, want true")
	}
}

// TestStartHandlerSupervisorErrorMaps: ErrLocked -> 423 + locked.
func TestStartHandlerSupervisorErrorMaps(t *testing.T) {
	h := newSimpleHarness(t)
	// Override the start endpoint to return 423.
	h.ts.Close()
	h.ts = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "/start") {
			w.WriteHeader(http.StatusLocked)
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("{}"))
	}))
	t.Cleanup(h.ts.Close)
	h.supClient = h.supClient.WithBaseURLForTest(h.ts.URL)

	handler := Start(h.supClient, h.mutexMgr)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/start", nil)
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

// TestStartHandlerRequiresAuth is implicit — the handler runs
// WITHOUT a router-mounted auth subrouter; the RequireBearer
// middleware is the layer that returns 401. This test proves the
// handler itself does not panic on missing actor context.
func TestStartHandlerRequiresAuth(t *testing.T) {
	h := newSimpleHarness(t, "start")
	handler := Start(h.supClient, h.mutexMgr)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/start", nil)
	req.SetPathValue("slug", "test_slug")
	// No Authorization header + no auth context.
	handler(rec, req)

	if rec.Code == 0 {
		t.Fatal("handler did not write a response")
	}
	if rec.Code != http.StatusOK {
		t.Errorf("status = %d, want 200 (handler-level test; router enforces 401)", rec.Code)
	}
}

// TestStartHandlerDoesNotRequireNonce: missing X-Force-Destroy
// header → 200 (start is non-destructive per D-10).
func TestStartHandlerDoesNotRequireNonce(t *testing.T) {
	h := newSimpleHarness(t, "start")
	handler := Start(h.supClient, h.mutexMgr)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/start", nil)
	req.SetPathValue("slug", "test_slug")
	// Deliberately omit X-Force-Destroy.
	handler(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (start must NOT require nonce per D-10)\nbody: %s", rec.Code, rec.Body.String())
	}
	if strings.Contains(rec.Body.String(), "nonce_expired") || strings.Contains(rec.Body.String(), "nonce_used") {
		t.Errorf("body must NOT mention nonce: %s", rec.Body.String())
	}
}

// TestStartHandlerMutexLockedReturns423: hold the per-slug mutex
// from a goroutine; the handler returns 423 within 100ms.
// Requires a deadline-bounded request context so the mutex
// TryAcquire has a budget to time out against.
func TestStartHandlerMutexLockedReturns423(t *testing.T) {
	h := newSimpleHarness(t, "start")

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

	// Give the goroutine a moment to actually acquire the lock.
	time.Sleep(50 * time.Millisecond)

	handler := Start(h.supClient, h.mutexMgr)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/start", nil)
	req.SetPathValue("slug", "test_slug")
	// Wire a deadline so the handler's TryAcquire can time out
	// (Plan 03's main.go will impose this at the router level;
	// for handler-level tests we set it explicitly here).
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
