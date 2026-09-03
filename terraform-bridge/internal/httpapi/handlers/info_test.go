package handlers

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"terraform-bridge/contract"
	"terraform-bridge/internal/supervisor"
)

func TestInfoHandlerHappyPath(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"result": "ok",
			"data":   map[string]any{"supervisor": "2026.08.0"},
		})
	}))
	defer ts.Close()

	supClient := supervisor.NewClient(func() string { return "stub-token" })
	supClient = supClient.WithBaseURLForTest(ts.URL)

	startTime := time.Now().Add(-5 * time.Second)
	h := Info(supClient, "0.1.0", startTime, "/data/terraform.tfstate")

	rec := httptest.NewRecorder()
	h(rec, httptest.NewRequest("GET", "/v1/info", nil))

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200\nbody: %s", rec.Code, rec.Body.String())
	}
	var body contract.BridgeInfo
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.BridgeVersion != "0.1.0" {
		t.Errorf("BridgeVersion = %q, want %q", body.BridgeVersion, "0.1.0")
	}
	if body.SupervisorVersion != "2026.08.0" {
		t.Errorf("SupervisorVersion = %q, want %q", body.SupervisorVersion, "2026.08.0")
	}
	if body.UptimeSeconds < 5 {
		t.Errorf("UptimeSeconds = %d, want >= 5", body.UptimeSeconds)
	}
	if body.StateFilePath != "/data/terraform.tfstate" {
		t.Errorf("StateFilePath = %q, want %q", body.StateFilePath, "/data/terraform.tfstate")
	}
}

func TestInfoHandlerUpstreamError(t *testing.T) {
	// supClient whose tokenFn returns "" -> RoundTripper returns the
	// "SUPERVISOR_TOKEN is empty" error -> GetSupervisorInfo surfaces
	// it as a wrapped error -> handler returns 502 + upstream_error.
	supClient := supervisor.NewClient(func() string { return "" })
	h := Info(supClient, "0.1.0", time.Now(), "/data/terraform.tfstate")

	rec := httptest.NewRecorder()
	h(rec, httptest.NewRequest("GET", "/v1/info", nil))

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
