package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"log/slog"
	"net/http/httptest"
	"testing"

	"github.com/go-chi/chi/v5/middleware"

	"iac-runner/internal/runs"
)

// captureSlog swaps the default logger for a JSON handler writing into
// a buffer and restores it afterwards. The audit record is an
// observable side effect of a request, so the assertion has to be on
// the emitted record, not on a return value.
func captureSlog(t *testing.T) *bytes.Buffer {
	t.Helper()
	var buf bytes.Buffer
	prev := slog.Default()
	slog.SetDefault(slog.New(slog.NewJSONHandler(&buf, &slog.HandlerOptions{Level: slog.LevelDebug})))
	t.Cleanup(func() { slog.SetDefault(prev) })
	return &buf
}

// records decodes every JSON log line in buf.
func records(t *testing.T, buf *bytes.Buffer) []map[string]any {
	t.Helper()
	var out []map[string]any
	dec := json.NewDecoder(bytes.NewReader(buf.Bytes()))
	for dec.More() {
		var rec map[string]any
		if err := dec.Decode(&rec); err != nil {
			t.Fatalf("decode log record: %v (raw %q)", err, buf.String())
		}
		out = append(out, rec)
	}
	return out
}

// TestAuditRedactionsEmitsRecord is ROADMAP SC-10 / SEC-03: the
// redaction count of a served page reaches the operator's log under
// the exact record name `redaction.audit`.
func TestAuditRedactionsEmitsRecord(t *testing.T) {
	buf := captureSlog(t)

	auditRedactions(context.Background(), "ABCDEFGH12345678", runs.OutputPage{
		Lines: []string{"a", "b"}, Page: 2, PageSize: 100, TotalLines: 250, Redactions: 3,
	})

	recs := records(t, buf)
	if len(recs) != 1 {
		t.Fatalf("emitted %d records, want exactly 1: %s", len(recs), buf.String())
	}
	rec := recs[0]
	if rec["msg"] != "redaction.audit" {
		t.Errorf("msg = %v, want redaction.audit", rec["msg"])
	}
	if rec["run_id"] != "ABCDEFGH12345678" {
		t.Errorf("run_id = %v", rec["run_id"])
	}
	if rec["redactions"] != float64(3) {
		t.Errorf("redactions = %v, want 3", rec["redactions"])
	}
	if rec["page"] != float64(2) {
		t.Errorf("page = %v, want 2", rec["page"])
	}
	if rec["page_size"] != float64(100) {
		t.Errorf("page_size = %v, want 100", rec["page_size"])
	}
	if rec["total_lines"] != float64(250) {
		t.Errorf("total_lines = %v, want 250", rec["total_lines"])
	}
}

// TestAuditRedactionsSilentWhenNothingRedacted keeps the audit trail
// meaningful: a clean page has nothing to audit, and a running apply
// is polled repeatedly, so emitting a zero record per poll would bury
// the real ones.
func TestAuditRedactionsSilentWhenNothingRedacted(t *testing.T) {
	buf := captureSlog(t)

	auditRedactions(context.Background(), "ABCDEFGH12345678", runs.OutputPage{
		Lines: []string{"a"}, Page: 1, PageSize: 100, TotalLines: 1, Redactions: 0,
	})

	if recs := records(t, buf); len(recs) != 0 {
		t.Errorf("emitted %d records for a zero-redaction page, want 0: %s", len(recs), buf.String())
	}
}

// TestAuditRedactionsCarriesRequestID proves the record can be
// correlated with the http.request record the middleware emits.
func TestAuditRedactionsCarriesRequestID(t *testing.T) {
	buf := captureSlog(t)

	r := httptest.NewRequest("GET", "/v1/runs/ABCDEFGH12345678", nil)
	ctx := context.WithValue(r.Context(), middleware.RequestIDKey, "runner/abc123-7")

	auditRedactions(ctx, "ABCDEFGH12345678", runs.OutputPage{Page: 1, PageSize: 100, Redactions: 1})

	recs := records(t, buf)
	if len(recs) != 1 {
		t.Fatalf("emitted %d records, want 1: %s", len(recs), buf.String())
	}
	if recs[0]["request_id"] != "runner/abc123-7" {
		t.Errorf("request_id = %v, want runner/abc123-7", recs[0]["request_id"])
	}
}

// TestAuditRedactionsNeverLogsContent is the point of the whole
// exercise: the audit record proves redaction happened, so it must not
// itself carry the redacted lines. A logged secret is a leaked secret
// even if the API response was clean.
func TestAuditRedactionsNeverLogsContent(t *testing.T) {
	buf := captureSlog(t)

	auditRedactions(context.Background(), "ABCDEFGH12345678", runs.OutputPage{
		Lines:      []string{"access_key = <redacted>", "plain output line"},
		Page:       1,
		PageSize:   100,
		TotalLines: 2,
		Redactions: 1,
	})

	raw := buf.String()
	for _, leak := range []string{"access_key", "<redacted>", "plain output line"} {
		if bytes.Contains([]byte(raw), []byte(leak)) {
			t.Errorf("audit record leaked page content %q: %s", leak, raw)
		}
	}
}
