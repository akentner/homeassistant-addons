package handlers

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"terraform-bridge/contract"
	"terraform-bridge/internal/supervisor"
)

func TestAddonsHandlerHappyPath(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"result": "ok",
			"data": map[string]any{
				"apps": []map[string]any{
					{"slug": "a", "name": "A", "version": "1.0", "state": "started", "started": true, "repository": "core"},
					{"slug": "b", "name": "B", "version": "2.0", "state": "stopped", "started": false, "repository": "core"},
				},
			},
		})
	}))
	defer ts.Close()

	supClient := supervisor.NewClient(func() string { return "stub" })
	supClient = supClient.WithBaseURLForTest(ts.URL)

	h := Addons(supClient)
	rec := httptest.NewRecorder()
	h(rec, httptest.NewRequest("GET", "/v1/addons", nil))

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200\nbody: %s", rec.Code, rec.Body.String())
	}
	var body []contract.AddOnInfo
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if len(body) != 2 {
		t.Fatalf("got %d entries, want 2", len(body))
	}
	for _, e := range body {
		if e.Slug == "" || e.Name == "" || e.Version == "" || e.State == "" {
			t.Errorf("entry missing mandatory field: %+v", e)
		}
		// The Started boolean must be populated (whether V1 derived or V2 forwarded).
		if e.Slug == "a" && !e.Started {
			t.Errorf("entry a should have started=true; got %+v", e)
		}
		if e.Slug == "b" && e.Started {
			t.Errorf("entry b should have started=false; got %+v", e)
		}
	}
}

func TestAddonsHandlerUpstreamError(t *testing.T) {
	// tokenFn returns "" -> RoundTripper error -> ListAddons returns error.
	supClient := supervisor.NewClient(func() string { return "" })
	h := Addons(supClient)

	rec := httptest.NewRecorder()
	h(rec, httptest.NewRequest("GET", "/v1/addons", nil))

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
	if len(body.Message) != 0 {
		t.Errorf("Message = %q, want empty (no leak)", body.Message)
	}
}
