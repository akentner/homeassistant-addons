package logging

import (
	"bytes"
	"encoding/json"
	"log/slog"
	"strings"
	"testing"
)

// newTestLogger returns a slog.Logger that writes JSON records to buf
// through the scrubbing handler. Used by every test below.
func newTestLogger(buf *bytes.Buffer) *slog.Logger {
	return slog.New(NewScrubbingHandler(slog.NewJSONHandler(buf, nil)))
}

// TestScrubbingHandlerAllKeys asserts that for each key in the
// sensitive set (Authorization, Bearer, token, password, key, secret)
// the crafted malicious value never appears in the serialized output
// AND the serialized value is exactly "<redacted>". Subtests cover
// each key independently so a regression in one matcher is isolated.
func TestScrubbingHandlerAllKeys(t *testing.T) {
	cases := []struct {
		key   string
		value string
	}{
		{"Authorization", "AKIAIOSFODNN7EXAMPLE"},
		{"Bearer", "real-bearer-token-do-not-leak-abc123"},
		{"token", "tok-LIVE-9f8e7d6c5b4a3210"},
		{"password", "P@ssw0rd!2026-secret"},
		{"key", "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAK..."},
		{"secret", "shhh-this-is-the-secret-value"},
	}
	for _, tc := range cases {
		t.Run(tc.key, func(t *testing.T) {
			var buf bytes.Buffer
			logger := newTestLogger(&buf)

			logger.Info("audit", tc.key, tc.value)

			out := buf.String()
			if strings.Contains(out, tc.value) {
				t.Errorf("scrubbed output contains forbidden value %q\noutput: %s", tc.value, out)
			}

			var rec map[string]any
			if err := json.Unmarshal(buf.Bytes(), &rec); err != nil {
				t.Fatalf("unmarshal: %v", err)
			}
			if got := rec[tc.key]; got != scrubbedValue {
				t.Errorf("%s = %v, want %s", tc.key, got, scrubbedValue)
			}
		})
	}
}

// TestScrubbingHandlerCaseInsensitive asserts that the scrubber is
// case-insensitive: "TOKEN" and "Token" both match the "token" entry.
// "authorization" + "Authorization" + "AUTHORIZATION" all match.
func TestScrubbingHandlerCaseInsensitive(t *testing.T) {
	cases := []struct {
		key   string
		value string
	}{
		{"TOKEN", "token-value-uppercase"},
		{"Token", "token-value-titlecase"},
		{"AUTHORIZATION", "auth-uppercase"},
		{"AuThOrIzAtIoN", "auth-mixedcase"},
	}
	for _, tc := range cases {
		t.Run(tc.key, func(t *testing.T) {
			var buf bytes.Buffer
			logger := newTestLogger(&buf)

			logger.Info("audit", tc.key, tc.value)

			out := buf.String()
			if strings.Contains(out, tc.value) {
				t.Errorf("scrubbed output contains forbidden value %q\noutput: %s", tc.value, out)
			}
			var rec map[string]any
			if err := json.Unmarshal(buf.Bytes(), &rec); err != nil {
				t.Fatalf("unmarshal: %v", err)
			}
			if got := rec[tc.key]; got != scrubbedValue {
				t.Errorf("%s = %v, want %s", tc.key, got, scrubbedValue)
			}
		})
	}
}

// TestScrubbingHandlerPassesNonSensitive asserts that keys NOT in the
// sensitive set survive the handler unchanged (no false positives).
// This includes both non-sensitive bare keys (route, method, status,
// duration_ms, request_id, count) and substrings of sensitive keys
// (the value of a "token_count" field carries an int, NOT a token).
func TestScrubbingHandlerPassesNonSensitive(t *testing.T) {
	var buf bytes.Buffer
	logger := newTestLogger(&buf)

	logger.Info("request",
		"route", "/v1/plan",
		"method", "POST",
		"status", 202,
		"duration_ms", 42,
		"request_id", "req-abc-123",
		"token_count", 3,    // "token_count" is NOT "token" — must pass
		"bind_address", "100.99.10.5",
		"path", "/data/keys/r2-access.key",
	)

	var rec map[string]any
	if err := json.Unmarshal(buf.Bytes(), &rec); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if rec["route"] != "/v1/plan" {
		t.Errorf("route lost: %v", rec["route"])
	}
	if rec["method"] != "POST" {
		t.Errorf("method lost: %v", rec["method"])
	}
	if rec["status"].(float64) != 202 {
		t.Errorf("status lost: %v", rec["status"])
	}
	if rec["token_count"].(float64) != 3 {
		t.Errorf("token_count (substring of sensitive 'token') MUST survive: got %v", rec["token_count"])
	}
	if rec["bind_address"] != "100.99.10.5" {
		t.Errorf("bind_address lost: %v", rec["bind_address"])
	}
	// "path" must NOT match "password" — the substring "password" is
	// not how the scrubber works; only exact-case-insensitive key
	// names match. path containing "/keys/" must survive.
	if rec["path"] != "/data/keys/r2-access.key" {
		t.Errorf("path lost: %v", rec["path"])
	}
}

// TestScrubbingHandlerWithGroup asserts that the scrubber still
// matches a sensitive key when nested inside a slog.WithGroup
// namespace. chi middleware produces `component.foo` style keys
// via WithGroup; without group-aware scrubbing an Authorization
// attr under WithGroup("http") would leak.
func TestScrubbingHandlerWithGroup(t *testing.T) {
	var buf bytes.Buffer
	base := slog.New(NewScrubbingHandler(slog.NewJSONHandler(&buf, nil)))
	logger := base.WithGroup("http")

	logger.Info("audit",
		"Authorization", "bearer-leak-attempt-under-group",
		"route", "/v1/auth/rotate", // non-sensitive — must survive
	)

	out := buf.String()
	if strings.Contains(out, "bearer-leak-attempt-under-group") {
		t.Errorf("group-nested Authorization value leaked: %s", out)
	}
	var rec map[string]any
	if err := json.Unmarshal(buf.Bytes(), &rec); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	// slog.JSONHandler renders the group's children as a nested
	// object ("http" → {Authorization, route}). The scrubber
	// matches on the leaf key (Authorization) before the inner
	// JSON handler serializes; the rendered shape is nested.
	http, ok := rec["http"].(map[string]any)
	if !ok {
		t.Fatalf("rec[http] = %T (%v), want nested map[string]any", rec["http"], rec["http"])
	}
	if got := http["Authorization"]; got != scrubbedValue {
		t.Errorf("http.Authorization = %v, want %s", got, scrubbedValue)
	}
	if http["route"] != "/v1/auth/rotate" {
		t.Errorf("http.route lost: %v", http["route"])
	}
}

// TestScrubbingHandlerWithAttrs asserts that WithAttrs (used by
// slog.Logger.With("component", "x")) chains through the scrubber.
// An attr named "token" added via .With(...) is scrubbed.
func TestScrubbingHandlerWithAttrs(t *testing.T) {
	var buf bytes.Buffer
	base := slog.New(NewScrubbingHandler(slog.NewJSONHandler(&buf, nil)))
	logger := base.With("token", "scrubbed-by-With")

	logger.Info("event")

	out := buf.String()
	if strings.Contains(out, "scrubbed-by-With") {
		t.Errorf("WithAttrs('token', ...) leaked: %s", out)
	}
	var rec map[string]any
	if err := json.Unmarshal(buf.Bytes(), &rec); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if rec["token"] != scrubbedValue {
		t.Errorf("token = %v, want %s", rec["token"], scrubbedValue)
	}
}

// TestScrubbingHandlerValueContainingBearerSubstring documents the
// design choice: scrubbing is key-name based, not value-substring
// based. A log message containing "Bearer" for human readers must
// NOT be corrupted.
func TestScrubbingHandlerValueContainingBearerSubstring(t *testing.T) {
	var buf bytes.Buffer
	logger := newTestLogger(&buf)

	logger.Info("note: Bearer auth scheme described in DOCS.md")
	out := buf.String()
	if !strings.Contains(out, "Bearer auth scheme described in DOCS.md") {
		t.Errorf("msg field lost Bearer reference\noutput: %s", out)
	}
}