package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"

	"iac-runner/internal/contract"
	"iac-runner/internal/runs"
)

// Compile-time signature lock. An anchored grep cannot assert a Go
// signature (the opening brace shares the line), but the compiler
// can: if GetRun's parameter or return type drifts, this file stops
// building and so does 17-07's main.go wiring.
var _ func(*runs.Store) http.HandlerFunc = GetRun

// validRunID is a well-formed run id (16 chars, base32 alphabet), so
// runs.IsValidRunID accepts it without a real run on disk.
const validRunID = "ABCDEFGH23456777"

// readOutputCall records one ReadOutput invocation, so a test can
// assert the page/page_size the handler actually asked the store for
// rather than only what it echoed back.
type readOutputCall struct {
	id       string
	page     int
	pageSize int
}

// fakeRunReader stands in for *runs.Store. The handler calls only
// Load and ReadOutput; the store's real behavior (meta.json layout,
// redaction, the scanner ceiling) is proven by 17-04's own tests.
type fakeRunReader struct {
	meta    runs.Meta
	loadErr error
	page    runs.OutputPage
	readErr error
	loads   []string
	reads   []readOutputCall
}

func (f *fakeRunReader) Load(runID string) (runs.Meta, error) {
	f.loads = append(f.loads, runID)
	return f.meta, f.loadErr
}

func (f *fakeRunReader) ReadOutput(runID string, page, pageSize int) (runs.OutputPage, error) {
	f.reads = append(f.reads, readOutputCall{id: runID, page: page, pageSize: pageSize})
	if f.readErr != nil {
		return runs.OutputPage{}, f.readErr
	}
	p := f.page
	if p.Page == 0 {
		p.Page = page
	}
	if p.PageSize == 0 {
		p.PageSize = pageSize
	}
	return p, nil
}

// queuedRun is the default fake: a queued run with no exit code, no
// finish time and no output yet — the shape that used to panic when a
// handler assumed *int and *time.Time were populated.
func queuedRun() *fakeRunReader {
	return &fakeRunReader{
		meta: runs.Meta{
			RunID:     validRunID,
			Repo:      "prod",
			Dir:       "envs/prod",
			Kind:      contract.RunKindApply,
			Status:    contract.RunStatusQueued,
			StartedAt: time.Date(2026, 9, 8, 10, 0, 0, 0, time.UTC),
		},
	}
}

// newGetRunRequest builds a GET /v1/runs/{id} request with the chi
// route parameter populated, so the handler runs without a router.
func newGetRunRequest(t *testing.T, id, rawQuery string) *http.Request {
	t.Helper()
	target := "/v1/runs/" + id
	if rawQuery != "" {
		target += "?" + rawQuery
	}
	r := httptest.NewRequest(http.MethodGet, target, nil)
	rctx := chi.NewRouteContext()
	rctx.URLParams.Add("id", id)
	return r.WithContext(context.WithValue(r.Context(), chi.RouteCtxKey, rctx))
}

// serveGetRun runs the handler against the fake and returns the recorder.
func serveGetRun(t *testing.T, rd runReader, id, rawQuery string) *httptest.ResponseRecorder {
	t.Helper()
	rec := httptest.NewRecorder()
	getRunHandler(rd)(rec, newGetRunRequest(t, id, rawQuery))
	return rec
}

// decodeRunDetail decodes a contract.RunDetail body.
func decodeRunDetail(t *testing.T, rec *httptest.ResponseRecorder) contract.RunDetail {
	t.Helper()
	var d contract.RunDetail
	if err := json.NewDecoder(rec.Body).Decode(&d); err != nil {
		t.Fatalf("decode RunDetail: %v (raw %q)", err, rec.Body.String())
	}
	return d
}

// TestGetRunSuccess is RUN-04: every Meta field plus the paginated
// output page reaches the wire in one response.
func TestGetRunSuccess(t *testing.T) {
	f := queuedRun()
	exit := 0
	finished := time.Date(2026, 9, 8, 10, 5, 0, 0, time.UTC)
	f.meta.Status = contract.RunStatusSucceeded
	f.meta.ExitCode = &exit
	f.meta.FinishedAt = &finished
	f.page = runs.OutputPage{
		Lines:      []string{"a", "b", "c", "d", "e"},
		Page:       1,
		PageSize:   contract.DefaultOutputPageSize,
		TotalLines: 5,
	}

	rec := serveGetRun(t, f, validRunID, "")

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type = %q, want application/json", ct)
	}
	d := decodeRunDetail(t, rec)
	if d.RunID != validRunID || d.Repo != "prod" || d.Dir != "envs/prod" {
		t.Errorf("identity fields = %+v", d)
	}
	if d.Kind != contract.RunKindApply || d.Status != contract.RunStatusSucceeded {
		t.Errorf("kind/status = %v/%v", d.Kind, d.Status)
	}
	if d.ExitCode == nil || *d.ExitCode != 0 {
		t.Errorf("exit_code = %v, want 0", d.ExitCode)
	}
	if d.StartedAt != "2026-09-08T10:00:00Z" {
		t.Errorf("started_at = %q", d.StartedAt)
	}
	if d.FinishedAt != "2026-09-08T10:05:00Z" {
		t.Errorf("finished_at = %q", d.FinishedAt)
	}
	if len(d.OutputLines) != 5 {
		t.Errorf("output_lines = %v, want 5 entries", d.OutputLines)
	}
	if d.Page != 1 || d.PageSize != contract.DefaultOutputPageSize || d.TotalLines != 5 {
		t.Errorf("pagination = page %d size %d total %d", d.Page, d.PageSize, d.TotalLines)
	}
}

// TestGetRunMalformedIDIsRunUnknownID is the path-traversal guard:
// the id is validated BEFORE any filesystem access, so a hostile
// value never reaches filepath.Join inside the store.
func TestGetRunMalformedIDIsRunUnknownID(t *testing.T) {
	f := queuedRun()

	rec := serveGetRun(t, f, "../etc", "")

	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404 (body %q)", rec.Code, rec.Body.String())
	}
	if got := decodeErr(t, rec).ErrorCode; got != contract.ErrCodeRunUnknownID {
		t.Errorf("error_code = %q, want %q", got, contract.ErrCodeRunUnknownID)
	}
	if len(f.loads) != 0 {
		t.Errorf("store.Load was called with %v; the guard must run first", f.loads)
	}
	if len(f.reads) != 0 {
		t.Errorf("store.ReadOutput was called %d times; the guard must run first", len(f.reads))
	}
}

// TestGetRunNotFound: a well-formed id with no run behind it is a
// typed 404, not a filesystem error.
func TestGetRunNotFound(t *testing.T) {
	f := queuedRun()
	f.loadErr = runs.ErrRunNotFound

	rec := serveGetRun(t, f, validRunID, "")

	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404 (body %q)", rec.Code, rec.Body.String())
	}
	if got := decodeErr(t, rec).ErrorCode; got != contract.ErrCodeRunNotFound {
		t.Errorf("error_code = %q, want %q", got, contract.ErrCodeRunNotFound)
	}
}

// TestGetRunLoadFailureDoesNotLeak: a non-ErrRunNotFound store
// failure is a 5xx whose body carries a typed code and no path,
// errno or wrapped error string (GIT-04's rule applies to every
// endpoint).
func TestGetRunLoadFailureDoesNotLeak(t *testing.T) {
	f := queuedRun()
	f.loadErr = errors.New("open /data/runs/ABCDEFGH23456777/meta.json: permission denied")

	rec := serveGetRun(t, f, validRunID, "")

	if rec.Code < 500 {
		t.Fatalf("status = %d, want a 5xx (body %q)", rec.Code, rec.Body.String())
	}
	body := decodeErr(t, rec)
	if body.ErrorCode == "" {
		t.Error("error_code is empty; every 5xx carries a typed code")
	}
	for _, leak := range []string{"/data/runs", "permission denied", "meta.json"} {
		if strings.Contains(rec.Body.String(), leak) {
			t.Errorf("response body leaked %q: %s", leak, rec.Body.String())
		}
	}
}

// TestGetRunWithRedactionsEmitsAudit is ROADMAP SC-10 through the
// production path: the handler is the single caller of
// auditRedactions, and the audited numbers are the ones the client
// received.
func TestGetRunWithRedactionsEmitsAudit(t *testing.T) {
	buf := captureSlog(t)
	f := queuedRun()
	f.page = runs.OutputPage{
		Lines:      []string{"access_key = <redacted>", "x", "y"},
		Page:       1,
		PageSize:   contract.DefaultOutputPageSize,
		TotalLines: 3,
		Redactions: 3,
	}

	rec := serveGetRun(t, f, validRunID, "")

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	audits := auditRecords(t, buf)
	if len(audits) != 1 {
		t.Fatalf("emitted %d redaction.audit records, want exactly 1: %s", len(audits), buf.String())
	}
	if audits[0]["run_id"] != validRunID {
		t.Errorf("run_id = %v, want %q", audits[0]["run_id"], validRunID)
	}
	if audits[0]["redactions"] != float64(3) {
		t.Errorf("redactions = %v, want 3", audits[0]["redactions"])
	}
	if strings.Contains(buf.String(), "access_key") || strings.Contains(buf.String(), "<redacted>") {
		t.Errorf("audit record leaked page content: %s", buf.String())
	}
}

// TestGetRunNoRedactionsNoAudit keeps the audit trail meaningful: a
// polled run with a clean page emits nothing.
func TestGetRunNoRedactionsNoAudit(t *testing.T) {
	buf := captureSlog(t)
	f := queuedRun()
	f.page = runs.OutputPage{Lines: []string{"clean"}, Page: 1, PageSize: 100, TotalLines: 1, Redactions: 0}

	if rec := serveGetRun(t, f, validRunID, ""); rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	if audits := auditRecords(t, buf); len(audits) != 0 {
		t.Errorf("emitted %d redaction.audit records for a clean page, want 0: %s", len(audits), buf.String())
	}
}

// TestGetRunAuditEmittedOncePerRequest is the "exactly once" half of
// the 17-06 call contract: two requests produce two records, never
// four, so no second emission point crept in.
func TestGetRunAuditEmittedOncePerRequest(t *testing.T) {
	buf := captureSlog(t)
	f := queuedRun()
	f.page = runs.OutputPage{Lines: []string{"x"}, Page: 1, PageSize: 100, TotalLines: 1, Redactions: 1}

	serveGetRun(t, f, validRunID, "")
	serveGetRun(t, f, validRunID, "")

	if audits := auditRecords(t, buf); len(audits) != 2 {
		t.Errorf("emitted %d redaction.audit records for 2 requests, want 2: %s", len(audits), buf.String())
	}
}

// TestGetRunPagination: ?page= and ?page_size= reach the store
// verbatim and are echoed from the page the store returned.
func TestGetRunPagination(t *testing.T) {
	f := queuedRun()
	f.page = runs.OutputPage{Lines: []string{"k"}, Page: 2, PageSize: 10, TotalLines: 25}

	rec := serveGetRun(t, f, validRunID, "page=2&page_size=10")

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	if len(f.reads) != 1 {
		t.Fatalf("ReadOutput called %d times, want 1", len(f.reads))
	}
	if f.reads[0] != (readOutputCall{id: validRunID, page: 2, pageSize: 10}) {
		t.Errorf("ReadOutput call = %+v, want {id, 2, 10}", f.reads[0])
	}
	d := decodeRunDetail(t, rec)
	if d.Page != 2 || d.PageSize != 10 || d.TotalLines != 25 {
		t.Errorf("pagination = page %d size %d total %d, want 2/10/25", d.Page, d.PageSize, d.TotalLines)
	}
}

// TestGetRunPageSizeClamped: OBS-03's cap is applied before the store
// is asked, so an oversized request cannot make the runner read an
// unbounded window.
func TestGetRunPageSizeClamped(t *testing.T) {
	f := queuedRun()

	rec := serveGetRun(t, f, validRunID, "page_size=5000")

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	if len(f.reads) != 1 {
		t.Fatalf("ReadOutput called %d times, want 1", len(f.reads))
	}
	if f.reads[0].pageSize != contract.MaxOutputPageSize {
		t.Errorf("pageSize = %d, want %d", f.reads[0].pageSize, contract.MaxOutputPageSize)
	}
}

// TestGetRunBadPaginationFallsBack: a typo in ?page= must not block a
// pagination read — the documented contract silently falls back to
// the defaults rather than 400ing.
func TestGetRunBadPaginationFallsBack(t *testing.T) {
	f := queuedRun()

	rec := serveGetRun(t, f, validRunID, "page=nope&page_size=-3")

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	if len(f.reads) != 1 {
		t.Fatalf("ReadOutput called %d times, want 1", len(f.reads))
	}
	if f.reads[0].page != 1 || f.reads[0].pageSize != contract.DefaultOutputPageSize {
		t.Errorf("ReadOutput call = %+v, want page 1 / size %d", f.reads[0], contract.DefaultOutputPageSize)
	}
}

// TestGetRunQueuedRunHasEmptyOutput: a queued run has no output.log
// yet. The response is a 200 with an empty (never null) output_lines
// array, so a client needs no special case and nothing panics on the
// nil ExitCode / FinishedAt.
func TestGetRunQueuedRunHasEmptyOutput(t *testing.T) {
	f := queuedRun()
	f.page = runs.OutputPage{Page: 1, PageSize: contract.DefaultOutputPageSize}

	rec := serveGetRun(t, f, validRunID, "")

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	if raw := rec.Body.String(); strings.Contains(raw, `"output_lines":null`) {
		t.Errorf("output_lines marshalled as null, want []: %s", raw)
	}
	d := decodeRunDetail(t, rec)
	if len(d.OutputLines) != 0 || d.TotalLines != 0 {
		t.Errorf("output = %v / total %d, want empty", d.OutputLines, d.TotalLines)
	}
	if d.ExitCode != nil {
		t.Errorf("exit_code = %v, want null for a queued run", *d.ExitCode)
	}
	if d.FinishedAt != "" {
		t.Errorf("finished_at = %q, want empty for a queued run", d.FinishedAt)
	}
}

// TestGetRunReadOutputFailureDoesNotLeak: an unreadable output.log is
// a 5xx with a typed code, never the raw error string.
func TestGetRunReadOutputFailureDoesNotLeak(t *testing.T) {
	f := queuedRun()
	f.readErr = errors.New("read /data/runs/ABCDEFGH23456777/output.log: input/output error")

	rec := serveGetRun(t, f, validRunID, "")

	if rec.Code < 500 {
		t.Fatalf("status = %d, want a 5xx (body %q)", rec.Code, rec.Body.String())
	}
	if decodeErr(t, rec).ErrorCode == "" {
		t.Error("error_code is empty; every 5xx carries a typed code")
	}
	for _, leak := range []string{"/data/runs", "input/output error", "output.log"} {
		if strings.Contains(rec.Body.String(), leak) {
			t.Errorf("response body leaked %q: %s", leak, rec.Body.String())
		}
	}
}

// auditRecords returns only the `redaction.audit` records in buf, so
// an assertion on "exactly one audit" is not disturbed by any other
// record the handler emits on the same request.
func auditRecords(t *testing.T, buf *bytes.Buffer) []map[string]any {
	t.Helper()
	var out []map[string]any
	for _, rec := range records(t, buf) {
		if rec["msg"] == "redaction.audit" {
			out = append(out, rec)
		}
	}
	return out
}

// TestGetRunPageClamped is the handler half of WR-03: ?page= is now
// bounded where every other pagination parameter already was, so an
// absurd page number cannot reach the store's window arithmetic.
func TestGetRunPageClamped(t *testing.T) {
	f := queuedRun()

	rec := serveGetRun(t, f, validRunID, "page=184467440737095517")

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	if len(f.reads) != 1 {
		t.Fatalf("ReadOutput called %d times, want 1", len(f.reads))
	}
	if f.reads[0].page != maxOutputPage {
		t.Errorf("page = %d, want the clamp %d", f.reads[0].page, maxOutputPage)
	}
}
