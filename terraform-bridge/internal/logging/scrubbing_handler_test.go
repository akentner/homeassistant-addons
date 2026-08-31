package logging

import (
	"bytes"
	"encoding/json"
	"log/slog"
	"strings"
	"testing"
)

func newTestLogger(buf *bytes.Buffer) *slog.Logger {
	return slog.New(NewScrubbingHandler(slog.NewJSONHandler(buf, nil)))
}

func TestScrubbingHandlerMasksSensitiveKeys(t *testing.T) {
	var buf bytes.Buffer
	logger := newTestLogger(&buf)

	logger.Info("test",
		"Authorization", "Bearer abc.def",
		"Bearer", "xyz",
		"bridge_token", "tok-12345",
		"SUPERVISOR_TOKEN", "sup-67890",
		"supervisor_token", "sup-abcdef",
		"bearer", "lowercase-bearer",
		"token", "plain-token",
		"password", "p4ssw0rd",
	)

	out := buf.String()
	for _, f := range []string{"abc.def", "tok-12345", "sup-67890", "sup-abcdef", "lowercase-bearer", "plain-token", "p4ssw0rd"} {
		if strings.Contains(out, f) {
			t.Errorf("scrubbed output contains forbidden value %q\noutput: %s", f, out)
		}
	}
	var rec map[string]any
	if err := json.Unmarshal(buf.Bytes(), &rec); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if rec["Authorization"] != "<redacted>" {
		t.Errorf("Authorization = %v, want <redacted>", rec["Authorization"])
	}
	if rec["bridge_token"] != "<redacted>" {
		t.Errorf("bridge_token = %v, want <redacted>", rec["bridge_token"])
	}
}

func TestScrubbingHandlerPreservesNonSensitiveKeys(t *testing.T) {
	var buf bytes.Buffer
	logger := newTestLogger(&buf)

	logger.Info("test",
		"route", "/v1/whoami",
		"method", "GET",
		"status", 200,
		"duration_ms", 12,
		"request_id", "abc-123",
	)

	var rec map[string]any
	if err := json.Unmarshal(buf.Bytes(), &rec); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if rec["route"] != "/v1/whoami" {
		t.Errorf("route lost: %v", rec["route"])
	}
	if rec["method"] != "GET" {
		t.Errorf("method lost: %v", rec["method"])
	}
	if rec["status"].(float64) != 200 {
		t.Errorf("status lost: %v", rec["status"])
	}
}

func TestScrubbingHandlerPreservesValueContainingBearerSubstring(t *testing.T) {
	// Per CONTEXT §the agent's Discretion: scrub is key-name based,
	// not value-substring based. A log message that mentions "Bearer"
	// for documentation purposes must NOT be corrupted.
	var buf bytes.Buffer
	logger := newTestLogger(&buf)

	logger.Info("note: Bearer auth scheme not yet implemented")
	out := buf.String()
	if !strings.Contains(out, "Bearer auth scheme not yet implemented") {
		t.Errorf("msg field lost Bearer reference\noutput: %s", out)
	}
}
