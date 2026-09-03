package handlers

import (
	"bytes"
	"encoding/json"
	"io"
	"log/slog"
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

// installHarness is the standard test stack for the install
// handler. jobs drives /jobs/{jobID} scripted responses: each
// call to the JobStatus endpoint returns the next entry's
// Done/Result. When the slice is exhausted, every subsequent call
// returns the LAST entry's Done/Result (proves the polling loop
// keeps retrying). infoStatuses drives /info responses: each
// call to either /apps/{slug}/info or /addons/{slug}/info
// (GetAddonInfo uses V2-first/V1-fallback, so a single attempt
// counts as 2 hits) returns the next entry's HTTP status. After
// the slice is exhausted every /info call returns 200 + payload.
type installHarness struct {
	ts          *httptest.Server
	supClient   *supervisor.Client
	mutexMgr    *mutex.Manager
	pollCalls   *atomic.Int32
	installHits *atomic.Int32
	infoHits    *atomic.Int32
}

func newInstallHarness(t *testing.T, jobs []contract.JobStatus, infoStatuses []int) *installHarness {
	t.Helper()
	h := &installHarness{
		pollCalls:   &atomic.Int32{},
		installHits: &atomic.Int32{},
		infoHits:    &atomic.Int32{},
	}

	jobIndex := &atomic.Int32{}

	h.ts = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/store/apps/test_slug/install":
			h.installHits.Add(1)
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"result": "ok",
				"data":   map[string]any{"job_id": "job-123"},
			})
		case strings.HasPrefix(r.URL.Path, "/jobs/"):
			h.pollCalls.Add(1)
			idx := int(jobIndex.Add(1) - 1)
			var resp contract.JobStatus
			if idx < len(jobs) {
				resp = jobs[idx]
			} else if len(jobs) > 0 {
				resp = jobs[len(jobs)-1]
			}
			_ = json.NewEncoder(w).Encode(resp)
		case strings.HasSuffix(r.URL.Path, "/info"):
			idx := int(h.infoHits.Add(1) - 1)
			status := http.StatusOK
			if idx < len(infoStatuses) {
				status = infoStatuses[idx]
			}
			if status == http.StatusOK {
				_ = json.NewEncoder(w).Encode(map[string]any{
					"result": "ok",
					"data": map[string]any{
						"slug":       "test_slug",
						"name":       "Test",
						"version":    "1.2.3",
						"state":      "stopped",
						"started":    false,
						"boot":       "manual",
						"repository": "core",
					},
				})
				return
			}
			w.WriteHeader(status)
		default:
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte("{}"))
		}
	}))
	t.Cleanup(h.ts.Close)

	h.supClient = supervisor.NewClient(func() string { return "stub" })
	h.supClient = h.supClient.WithBaseURLForTest(h.ts.URL)
	h.mutexMgr = mutex.NewManager()
	return h
}

func doInstall(t *testing.T, h *installHarness, timeout time.Duration) *httptest.ResponseRecorder {
	t.Helper()
	handler := Install(h.supClient, h.mutexMgr, nil, timeout)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/install", nil)
	req.SetPathValue("slug", "test_slug")
	handler(rec, req)
	return rec
}

// TestInstallHandlerHappyPath: single Done=true poll + post-install
// info succeeds; expect 200 + AddOnInfo body.
func TestInstallHandlerHappyPath(t *testing.T) {
	h := newInstallHarness(t, []contract.JobStatus{
		{JobID: "job-123", Done: true, Result: map[string]any{"ok": true}},
	}, []int{http.StatusOK})

	rec := doInstall(t, h, 5*time.Second)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200\nbody: %s", rec.Code, rec.Body.String())
	}
	var info contract.AddOnInfo
	if err := json.Unmarshal(rec.Body.Bytes(), &info); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if info.Slug != "test_slug" || info.Version != "1.2.3" {
		t.Errorf("info = %+v", info)
	}
	if got := h.installHits.Load(); got != 1 {
		t.Errorf("install calls = %d, want 1", got)
	}
}

// TestInstallHandlerPollsUntilDone: 2x Done=false then 1x Done=true.
// Handler must wait at least 2s (1s per false poll) but < 3s.
func TestInstallHandlerPollsUntilDone(t *testing.T) {
	h := newInstallHarness(t, []contract.JobStatus{
		{JobID: "job-123", Done: false},
		{JobID: "job-123", Done: false},
		{JobID: "job-123", Done: true, Result: map[string]any{"ok": true}},
	}, []int{http.StatusOK})

	start := time.Now()
	rec := doInstall(t, h, 5*time.Second)
	elapsed := time.Since(start)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200\nbody: %s", rec.Code, rec.Body.String())
	}
	if h.pollCalls.Load() < 3 {
		t.Errorf("poll calls = %d, want >= 3", h.pollCalls.Load())
	}
	if elapsed < 1900*time.Millisecond {
		t.Errorf("elapsed = %v, want >= 1.9s (proves 1s tick cadence)", elapsed)
	}
	if elapsed > 3500*time.Millisecond {
		t.Errorf("elapsed = %v, want < 3.5s (sluggish)", elapsed)
	}
}

// TestInstallHandlerBudgetExhausted: Done=false forever. With
// installJobTimeout=2s the handler returns 504 + install_timeout
// within 3s.
func TestInstallHandlerBudgetExhausted(t *testing.T) {
	h := newInstallHarness(t, []contract.JobStatus{
		{JobID: "job-123", Done: false},
	}, nil)

	// Capture slog to assert bridge_install_polling_timeout.
	var logBuf bytes.Buffer
	oldLogger := slog.Default()
	slog.SetDefault(slog.New(slog.NewJSONHandler(&logBuf, &slog.HandlerOptions{Level: slog.LevelInfo})))
	t.Cleanup(func() { slog.SetDefault(oldLogger) })

	start := time.Now()
	rec := doInstall(t, h, 2*time.Second)
	elapsed := time.Since(start)

	if rec.Code != http.StatusGatewayTimeout {
		t.Fatalf("status = %d, want 504\nbody: %s", rec.Code, rec.Body.String())
	}
	var body contract.ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.ErrorCode != "install_timeout" {
		t.Errorf("ErrorCode = %q, want install_timeout", body.ErrorCode)
	}
	if elapsed > 3500*time.Millisecond {
		t.Errorf("elapsed = %v, want < 3.5s", elapsed)
	}
	if !bytes.Contains(logBuf.Bytes(), []byte("bridge_install_polling_timeout")) {
		t.Errorf("missing bridge_install_polling_timeout log:\n%s", logBuf.String())
	}
	if !bytes.Contains(logBuf.Bytes(), []byte(`"elapsed_seconds":2`)) {
		t.Errorf("missing elapsed_seconds=2 log:\n%s", logBuf.String())
	}
}

// TestInstallHandlerAdoptionOn409: the Supervisor /store/apps
// install endpoint returns 409; handler falls through to
// GetAddonInfo and returns 200 + info payload (D-26 adoption
// signal for Phase 13 PROV-05).
func TestInstallHandlerAdoptionOn409(t *testing.T) {
	h := newInstallHarness(t, nil, []int{http.StatusOK})

	// Override the install endpoint to return 409.
	h.ts.Close()
	h.ts = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/store/apps/test_slug/install":
			w.WriteHeader(http.StatusConflict)
		case strings.HasSuffix(r.URL.Path, "/info"):
			h.infoHits.Add(1)
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]any{
				"result": "ok",
				"data": map[string]any{
					"slug":       "test_slug",
					"name":       "Test",
					"version":    "1.0.0",
					"state":      "started",
					"started":    true,
					"boot":       "auto",
					"repository": "core",
				},
			})
		default:
			w.WriteHeader(http.StatusOK)
		}
	}))
	t.Cleanup(h.ts.Close)
	h.supClient = h.supClient.WithBaseURLForTest(h.ts.URL)

	rec := doInstall(t, h, 5*time.Second)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (adoption path)\nbody: %s", rec.Code, rec.Body.String())
	}
	var info contract.AddOnInfo
	if err := json.Unmarshal(rec.Body.Bytes(), &info); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if !info.Started {
		t.Errorf("info.started = false, want true (adopted running addon)")
	}
	if h.infoHits.Load() < 1 {
		t.Errorf("info calls = %d, want >= 1 (adoption must fetch info)", h.infoHits.Load())
	}
}

// TestInstallHandlerPostInstallRetry: the post-install
// GetAddonInfo returns 404 for the first 2 attempts (V2 + V1
// fallback each = 4 hits) then succeeds. The 3x500ms retry
// path must survive the brief race (Pitfall 8).
func TestInstallHandlerPostInstallRetry(t *testing.T) {
	h := newInstallHarness(t, []contract.JobStatus{
		{JobID: "job-123", Done: true, Result: map[string]any{"ok": true}},
	}, []int{
		http.StatusNotFound, http.StatusNotFound, // attempt 1 (V2, V1)
		http.StatusNotFound, http.StatusNotFound, // attempt 2 (V2, V1)
		http.StatusOK, // attempt 3 (V2) — V1 not even hit
	})

	start := time.Now()
	rec := doInstall(t, h, 5*time.Second)
	elapsed := time.Since(start)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200\nbody: %s", rec.Code, rec.Body.String())
	}
	if h.infoHits.Load() < 5 {
		t.Errorf("info calls = %d, want >= 5 (2 attempts x 2 endpoints + 1 success)", h.infoHits.Load())
	}
	// 2 backoffs × 500ms = 1s minimum.
	if elapsed < 900*time.Millisecond {
		t.Errorf("elapsed = %v, want >= 0.9s (proves 2x500ms backoff)", elapsed)
	}
}

// TestInstallHandlerDoesNotRequireNonce: install is non-destructive
// per D-10; calling without X-Force-Destroy must succeed.
func TestInstallHandlerDoesNotRequireNonce(t *testing.T) {
	h := newInstallHarness(t, []contract.JobStatus{
		{JobID: "job-123", Done: true, Result: map[string]any{"ok": true}},
	}, []int{http.StatusOK})

	handler := Install(h.supClient, h.mutexMgr, nil, 5*time.Second)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/install", nil)
	req.SetPathValue("slug", "test_slug")
	// Deliberately omit X-Force-Destroy header.
	handler(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (install must not require nonce)\nbody: %s", rec.Code, rec.Body.String())
	}
}

// TestInstallHandlerCriticalSlugAllowed: a slug in
// critical_addons must STILL be installable (D-10 explicit:
// install is allowed even on critical slugs for idempotent
// re-install / upgrade).
func TestInstallHandlerCriticalSlugAllowed(t *testing.T) {
	h := newInstallHarness(t, []contract.JobStatus{
		{JobID: "job-123", Done: true, Result: map[string]any{"ok": true}},
	}, []int{http.StatusOK})

	handler := Install(h.supClient, h.mutexMgr, []string{"test_slug"}, 5*time.Second)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/install", nil)
	req.SetPathValue("slug", "test_slug")
	handler(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (install on critical slug MUST be allowed per D-10)\nbody: %s", rec.Code, rec.Body.String())
	}
	if strings.Contains(rec.Body.String(), "critical_addon_protected") {
		t.Errorf("body must not echo critical_addon_protected:\n%s", rec.Body.String())
	}
}

// Sanity: confirm the body is read once and not echoed back.
// This guards against accidental body forwarding regressions.
func TestInstallHandlerIgnoresRequestBody(t *testing.T) {
	h := newInstallHarness(t, []contract.JobStatus{
		{JobID: "job-123", Done: true, Result: map[string]any{"ok": true}},
	}, []int{http.StatusOK})

	handler := Install(h.supClient, h.mutexMgr, nil, 5*time.Second)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/addons/test_slug/install",
		strings.NewReader(`{"ignored":true}`))
	req.SetPathValue("slug", "test_slug")
	handler(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200\nbody: %s", rec.Code, rec.Body.String())
	}
	// Read everything the recorder has buffered.
	body, _ := io.ReadAll(rec.Body)
	if bytes.Contains(body, []byte(`"ignored":true`)) {
		t.Errorf("response must not echo request body: %s", body)
	}
}
