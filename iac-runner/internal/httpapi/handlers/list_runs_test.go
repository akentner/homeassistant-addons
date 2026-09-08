package handlers

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"iac-runner/internal/contract"
	"iac-runner/internal/runs"
)

// Compile-time signature lock — see the note in get_run_test.go.
var _ func(*runs.Store) http.HandlerFunc = ListRuns

// fakeRunLister stands in for *runs.Store. The handler calls only
// List, so the seam is that one method; the store's ordering, its
// corrupt-run skipping and its own limit clamp are proven by 17-04's
// tests.
type fakeRunLister struct {
	metas []runs.Meta
	err   error
	calls []runs.ListFilter
}

func (f *fakeRunLister) List(filter runs.ListFilter) ([]runs.Meta, error) {
	f.calls = append(f.calls, filter)
	if f.err != nil {
		return nil, f.err
	}
	return f.metas, nil
}

// metaFor builds one finished run for the listing fixtures.
func metaFor(id, repo string, status contract.RunStatus) runs.Meta {
	exit := 0
	finished := time.Date(2026, 9, 8, 10, 5, 0, 0, time.UTC)
	return runs.Meta{
		RunID:     id,
		Repo:      repo,
		Dir:       "envs/" + repo,
		Kind:      contract.RunKindPlan,
		Status:    status,
		ExitCode:  &exit,
		StartedAt: time.Date(2026, 9, 8, 10, 0, 0, 0, time.UTC),
		FinishedAt: func() *time.Time {
			if status == contract.RunStatusQueued || status == contract.RunStatusRunning {
				return nil
			}
			return &finished
		}(),
		PlanFile: "/data/runs/" + id + "/plan.tfplan",
	}
}

// serveListRuns runs the handler against the fake and returns the recorder.
func serveListRuns(t *testing.T, l runLister, rawQuery string) *httptest.ResponseRecorder {
	t.Helper()
	target := "/v1/runs"
	if rawQuery != "" {
		target += "?" + rawQuery
	}
	rec := httptest.NewRecorder()
	listRunsHandler(l)(rec, httptest.NewRequest(http.MethodGet, target, nil))
	return rec
}

// decodeRunList decodes a contract.RunListResponse body.
func decodeRunList(t *testing.T, rec *httptest.ResponseRecorder) contract.RunListResponse {
	t.Helper()
	var body contract.RunListResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode RunListResponse: %v (raw %q)", err, rec.Body.String())
	}
	return body
}

// TestListRunsDefaultLimit is the RUN-05 default: an unqualified
// listing asks the store for 20 and reports 20 as the applied limit,
// so a client knows the page was capped without guessing.
func TestListRunsDefaultLimit(t *testing.T) {
	f := &fakeRunLister{metas: []runs.Meta{
		metaFor("ABCDEFGH23456777", "prod", contract.RunStatusSucceeded),
		metaFor("BBCDEFGH23456777", "prod", contract.RunStatusFailed),
	}}

	rec := serveListRuns(t, f, "")

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type = %q, want application/json", ct)
	}
	if len(f.calls) != 1 {
		t.Fatalf("List called %d times, want 1", len(f.calls))
	}
	if f.calls[0].Limit != contract.DefaultRunListLimit {
		t.Errorf("filter.Limit = %d, want %d", f.calls[0].Limit, contract.DefaultRunListLimit)
	}
	if f.calls[0].Repo != "" || f.calls[0].Status != "" {
		t.Errorf("filter = %+v, want no repo/status filter", f.calls[0])
	}
	body := decodeRunList(t, rec)
	if body.Limit != contract.DefaultRunListLimit {
		t.Errorf("response limit = %d, want %d", body.Limit, contract.DefaultRunListLimit)
	}
	if body.Count != 2 || len(body.Runs) != 2 {
		t.Errorf("count = %d / runs = %d, want 2/2", body.Count, len(body.Runs))
	}
	first := body.Runs[0]
	if first.RunID != "ABCDEFGH23456777" || first.Repo != "prod" || first.Dir != "envs/prod" {
		t.Errorf("summary identity = %+v", first)
	}
	if first.Kind != contract.RunKindPlan || first.Status != contract.RunStatusSucceeded {
		t.Errorf("summary kind/status = %v/%v", first.Kind, first.Status)
	}
	if first.ExitCode == nil || *first.ExitCode != 0 {
		t.Errorf("summary exit_code = %v, want 0", first.ExitCode)
	}
	if first.StartedAt != "2026-09-08T10:00:00Z" || first.FinishedAt != "2026-09-08T10:05:00Z" {
		t.Errorf("summary timestamps = %q / %q", first.StartedAt, first.FinishedAt)
	}
}

// TestListRunsCarriesNoOutputLines is the RUN-05 shape decision:
// listing 20 runs must not read 20 log files, so a summary carries no
// output at all. Asserted on the raw body because a struct decode
// cannot see a field that is not in the wire type.
func TestListRunsCarriesNoOutputLines(t *testing.T) {
	f := &fakeRunLister{metas: []runs.Meta{metaFor("ABCDEFGH23456777", "prod", contract.RunStatusSucceeded)}}

	raw := serveListRuns(t, f, "").Body.String()

	for _, forbidden := range []string{"output_lines", "total_lines", "page_size", "plan_file"} {
		if strings.Contains(raw, forbidden) {
			t.Errorf("listing body carries %q, which belongs to GET /v1/runs/{id}: %s", forbidden, raw)
		}
	}
}

// TestListRunsRepoFilter: ?repo= reaches the store's filter verbatim.
func TestListRunsRepoFilter(t *testing.T) {
	f := &fakeRunLister{}

	if rec := serveListRuns(t, f, "repo=prod"); rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	if len(f.calls) != 1 {
		t.Fatalf("List called %d times, want 1", len(f.calls))
	}
	if f.calls[0].Repo != "prod" {
		t.Errorf("filter.Repo = %q, want prod", f.calls[0].Repo)
	}
}

// TestListRunsStatusFilterInterrupted is locked decision D-02:
// `interrupted` is a first-class filter value, so a run orphaned by a
// container restart is queryable rather than invisible.
func TestListRunsStatusFilterInterrupted(t *testing.T) {
	f := &fakeRunLister{metas: []runs.Meta{
		metaFor("ABCDEFGH23456777", "prod", contract.RunStatusInterrupted),
	}}

	rec := serveListRuns(t, f, "status=interrupted")

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	if len(f.calls) != 1 {
		t.Fatalf("List called %d times, want 1", len(f.calls))
	}
	if f.calls[0].Status != contract.RunStatusInterrupted {
		t.Errorf("filter.Status = %q, want %q", f.calls[0].Status, contract.RunStatusInterrupted)
	}
	body := decodeRunList(t, rec)
	if len(body.Runs) != 1 || body.Runs[0].Status != contract.RunStatusInterrupted {
		t.Errorf("runs = %+v, want one interrupted run", body.Runs)
	}
}

// TestListRunsStatusFilterEveryEnumValue: all five RunStatus values
// are accepted, not just the ones a happy path uses.
func TestListRunsStatusFilterEveryEnumValue(t *testing.T) {
	for _, want := range []contract.RunStatus{
		contract.RunStatusQueued,
		contract.RunStatusRunning,
		contract.RunStatusSucceeded,
		contract.RunStatusFailed,
		contract.RunStatusInterrupted,
	} {
		t.Run(string(want), func(t *testing.T) {
			f := &fakeRunLister{}

			rec := serveListRuns(t, f, "status="+string(want))

			if rec.Code != http.StatusOK {
				t.Fatalf("status = %d, want 200 (body %q)", rec.Code, rec.Body.String())
			}
			if len(f.calls) != 1 || f.calls[0].Status != want {
				t.Errorf("filter = %+v, want Status %q", f.calls, want)
			}
		})
	}
}

// TestListRunsLimitClamped is the RUN-05 cap: a caller asking for 500
// gets 100, and the response says 100 so the truncation is visible.
func TestListRunsLimitClamped(t *testing.T) {
	f := &fakeRunLister{}

	rec := serveListRuns(t, f, "limit=500")

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	if len(f.calls) != 1 {
		t.Fatalf("List called %d times, want 1", len(f.calls))
	}
	if f.calls[0].Limit != contract.MaxRunListLimit {
		t.Errorf("filter.Limit = %d, want %d", f.calls[0].Limit, contract.MaxRunListLimit)
	}
	if got := decodeRunList(t, rec).Limit; got != contract.MaxRunListLimit {
		t.Errorf("response limit = %d, want %d", got, contract.MaxRunListLimit)
	}
}

// TestListRunsBadLimitFallsBack: ?limit=0 and a non-numeric limit both
// fall back to the default rather than 400ing or asking the store for
// zero rows.
func TestListRunsBadLimitFallsBack(t *testing.T) {
	for _, raw := range []string{"limit=0", "limit=-5", "limit=nope"} {
		t.Run(raw, func(t *testing.T) {
			f := &fakeRunLister{}

			if rec := serveListRuns(t, f, raw); rec.Code != http.StatusOK {
				t.Fatalf("status = %d, want 200", rec.Code)
			}
			if len(f.calls) != 1 || f.calls[0].Limit != contract.DefaultRunListLimit {
				t.Errorf("filter = %+v, want Limit %d", f.calls, contract.DefaultRunListLimit)
			}
		})
	}
}

// TestListRunsUnknownStatus: an unknown ?status= is rejected at the
// HTTP boundary, before the store is touched — otherwise the caller
// would get a confident, empty 200 for what is really a typo.
func TestListRunsUnknownStatus(t *testing.T) {
	f := &fakeRunLister{}

	rec := serveListRuns(t, f, "status=bogus")

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 (body %q)", rec.Code, rec.Body.String())
	}
	body := decodeErr(t, rec)
	if body.ErrorCode == "" {
		t.Error("error_code is empty; every 4xx carries a typed code")
	}
	if !strings.Contains(body.Message, `invalid ?status= value "bogus"`) {
		t.Errorf("message = %q, want it to name the rejected value", body.Message)
	}
	if len(f.calls) != 0 {
		t.Errorf("List was called with %+v; the validation must run first", f.calls)
	}
}

// TestListRunsEmptyList: no runs is a 200 with an empty array, not a
// 404 — a fresh install and an unknown repo are both "nothing yet",
// and neither is an error.
func TestListRunsEmptyList(t *testing.T) {
	f := &fakeRunLister{}

	rec := serveListRuns(t, f, "repo=never-used")

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	if raw := strings.TrimSpace(rec.Body.String()); raw != `{"runs":[],"count":0,"limit":20}` {
		t.Errorf("body = %s, want an empty runs array", raw)
	}
}

// TestListRunsStoreFailureDoesNotLeak: a filesystem failure is a 5xx
// with a typed code and no path in the body.
func TestListRunsStoreFailureDoesNotLeak(t *testing.T) {
	f := &fakeRunLister{err: errors.New("runs: read runs dir: open /data/runs: permission denied")}

	rec := serveListRuns(t, f, "")

	if rec.Code < 500 {
		t.Fatalf("status = %d, want a 5xx (body %q)", rec.Code, rec.Body.String())
	}
	if decodeErr(t, rec).ErrorCode == "" {
		t.Error("error_code is empty; every 5xx carries a typed code")
	}
	for _, leak := range []string{"/data/runs", "permission denied"} {
		if strings.Contains(rec.Body.String(), leak) {
			t.Errorf("response body leaked %q: %s", leak, rec.Body.String())
		}
	}
}

// TestListRunsEmitsNoAuditRecord: a listing carries no output lines,
// so there is nothing redacted to audit. Emitting a record here would
// break the "exactly once per served page" contract 17-06 wrote.
func TestListRunsEmitsNoAuditRecord(t *testing.T) {
	buf := captureSlog(t)
	f := &fakeRunLister{metas: []runs.Meta{metaFor("ABCDEFGH23456777", "prod", contract.RunStatusSucceeded)}}

	serveListRuns(t, f, "")

	if audits := auditRecords(t, buf); len(audits) != 0 {
		t.Errorf("GET /v1/runs emitted %d redaction.audit records, want 0: %s", len(audits), buf.String())
	}
}
