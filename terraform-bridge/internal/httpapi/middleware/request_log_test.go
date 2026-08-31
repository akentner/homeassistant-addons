package middleware

import (
	"bytes"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5/middleware"
)

func TestRequestLoggerEmitsOPS01Fields(t *testing.T) {
	var buf bytes.Buffer
	prev := slog.Default()
	slog.SetDefault(slog.New(slog.NewJSONHandler(&buf, nil)))
	defer slog.SetDefault(prev)

	// Build a minimal handler chain with RequestID + RequestLogger.
	h := middleware.RequestID(RequestLogger()(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusTeapot)
	})))

	req := httptest.NewRequest("GET", "/v1/whoami", nil)
	req.Header.Set("X-Request-Id", "test-req-id-42")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	// Parse the single log line.
	var entry map[string]any
	if err := json.Unmarshal(buf.Bytes(), &entry); err != nil {
		t.Fatalf("unmarshal: %v\noutput: %s", err, buf.String())
	}
	if entry["request_id"] != "test-req-id-42" {
		t.Errorf("request_id = %v, want test-req-id-42", entry["request_id"])
	}
	if entry["route"] != "/v1/whoami" {
		t.Errorf("route = %v, want /v1/whoami", entry["route"])
	}
	if entry["method"] != "GET" {
		t.Errorf("method = %v, want GET", entry["method"])
	}
	if entry["status"].(float64) != 418 {
		t.Errorf("status = %v, want 418", entry["status"])
	}
	// duration_ms present and >= 0.
	if _, ok := entry["duration_ms"].(float64); !ok {
		t.Errorf("duration_ms missing or wrong type: %v", entry["duration_ms"])
	}
}

func TestRequestLoggerStripsAuthorizationValue(t *testing.T) {
	var buf bytes.Buffer
	prev := slog.Default()
	slog.SetDefault(slog.New(slog.NewJSONHandler(&buf, nil)))
	defer slog.SetDefault(prev)

	h := RequestLogger()(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest("GET", "/v1/x", nil)
	req.Header.Set("Authorization", "Bearer SENTINEL-TOKEN-VALUE")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	out := buf.String()
	if strings.Contains(out, "SENTINEL-TOKEN-VALUE") {
		t.Errorf("captured output contains Authorization value\noutput: %s", out)
	}
}
