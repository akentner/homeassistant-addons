package handlers

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"terraform-bridge/contract"
	"terraform-bridge/internal/supervisor"
)

// We can't directly satisfy supervisor.Client (it's a concrete
// struct), so the tests below use httptest.NewServer to drive the
// real Client through the network.

func TestAddonInfoHandlerHappyPath(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"result": "ok",
			"data": map[string]any{
				"slug": "matter", "name": "Matter Server",
				"version": "9.2.0", "state": "started",
				"started": true, "options": map[string]string{},
				"boot": "auto", "repository": "core",
			},
		})
	}))
	defer ts.Close()

	supClient := supervisor.NewClient(func() string { return "stub" })
	supClient = supClient.WithBaseURLForTest(ts.URL)

	h := AddonInfo(supClient)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/v1/addons/matter/info", nil)
	req.SetPathValue("slug", "matter")
	h(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200\nbody: %s", rec.Code, rec.Body.String())
	}
	var body contract.AddOnInfo
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.Slug != "matter" || body.Name != "Matter Server" || body.Version != "9.2.0" {
		t.Errorf("body mismatch: %+v", body)
	}
	if !body.Started {
		t.Errorf("Started = false, want true")
	}
}

func TestAddonInfoHandlerNotFound(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/apps/ghost/info", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	})
	mux.HandleFunc("/addons/ghost/info", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	})
	ts := httptest.NewServer(mux)
	defer ts.Close()

	supClient := supervisor.NewClient(func() string { return "stub" })
	supClient = supClient.WithBaseURLForTest(ts.URL)

	h := AddonInfo(supClient)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/v1/addons/ghost/info", nil)
	req.SetPathValue("slug", "ghost")
	h(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404\nbody: %s", rec.Code, rec.Body.String())
	}
	var body contract.ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.ErrorCode != "not_found" {
		t.Errorf("ErrorCode = %q, want %q", body.ErrorCode, "not_found")
	}
	if len(body.Message) != 0 {
		t.Errorf("Message = %q, want empty (literal BRIDGE-03 shape)", body.Message)
	}
	// Body must NOT echo the slug (PITFALLS S-1 - no internal-state leak).
	if strings.Contains(rec.Body.String(), "ghost") {
		t.Errorf("body should not echo slug; got %s", rec.Body.String())
	}
}

func TestAddonInfoHandlerUpstreamError(t *testing.T) {
	// tokenFn returns "" -> RoundTripper error -> GetAddonInfo returns error.
	supClient := supervisor.NewClient(func() string { return "" })
	h := AddonInfo(supClient)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/v1/addons/x/info", nil)
	req.SetPathValue("slug", "x")
	h(rec, req)

	if rec.Code != http.StatusBadGateway {
		t.Fatalf("status = %d, want 502\nbody: %s", rec.Code, rec.Body.String())
	}
	var body contract.ErrorResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.ErrorCode != "upstream_error" {
		t.Errorf("ErrorCode = %q, want %q", body.ErrorCode, "upstream_error")
	}
}
