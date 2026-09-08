package handlers

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"

	"iac-runner/internal/contract"
	"iac-runner/internal/git"
	"iac-runner/internal/jobq"
)

// Compile-time signature locks. A grep cannot assert a Go signature
// (the opening brace shares the line), but the compiler can: if either
// handler's parameter or return type drifts, this file stops building
// and so would 17-08's router mount.
var (
	_ func(*jobq.Queue) http.HandlerFunc = Plan
	_ func(*jobq.Queue) http.HandlerFunc = Apply
)

// errUnclassified is the shape of Submit's two untyped failure paths
// (run-id generation, store Create): a %w-wrapped os error whose
// string carries an absolute path. It must never reach the wire.
var errUnclassified = errors.New("jobq: create run: open /data/runs/ABCD/meta.json: permission denied")

// fakeQueue stands in for *jobq.Queue. The handlers only call Submit,
// so the seam is that one method; the admission gates, the per-repo
// serialization and the tofu invocation are proven by 17-05's own
// tests. fn drives whichever branch a test wants; submits records what
// the handler actually asked for, which is how the Kind/Repo/Dir
// translation gets asserted rather than assumed.
type fakeQueue struct {
	mu      sync.Mutex
	submits []jobq.Request
	fn      func(req jobq.Request) (string, error)
}

func (q *fakeQueue) Submit(req jobq.Request) (string, error) {
	q.mu.Lock()
	q.submits = append(q.submits, req)
	q.mu.Unlock()
	if q.fn == nil {
		return "", nil
	}
	return q.fn(req)
}

func (q *fakeQueue) recorded() []jobq.Request {
	q.mu.Lock()
	defer q.mu.Unlock()
	return append([]jobq.Request(nil), q.submits...)
}

// queueReturning builds a fake whose Submit always answers the same
// (runID, err) pair.
func queueReturning(runID string, err error) *fakeQueue {
	return &fakeQueue{fn: func(jobq.Request) (string, error) { return runID, err }}
}

// serveSubmit runs one of the two submit handlers against the fake.
func serveSubmit(t *testing.T, q submitter, kind contract.RunKind, body string) *httptest.ResponseRecorder {
	t.Helper()
	path := "/v1/plan"
	if kind == contract.RunKindApply {
		path = "/v1/apply"
	}
	r := httptest.NewRequest(http.MethodPost, path, strings.NewReader(body))
	r.Header.Set("Content-Type", "application/json")

	rec := httptest.NewRecorder()
	submitHandler(q, kind)(rec, r)
	return rec
}

func TestPlanQueuesRunKindPlan(t *testing.T) {
	q := queueReturning("RID123", nil)
	rec := serveSubmit(t, q, contract.RunKindPlan, `{"repo":"prod","dir":""}`)

	if rec.Code != http.StatusAccepted {
		t.Fatalf("status = %d, want 202 (body %q)", rec.Code, rec.Body.String())
	}
	if loc := rec.Header().Get("Location"); loc != "/v1/runs/RID123" {
		t.Errorf("Location = %q, want /v1/runs/RID123", loc)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type = %q, want application/json", ct)
	}

	var body contract.RunAccepted
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if body.RunID != "RID123" {
		t.Errorf("run_id = %q, want RID123", body.RunID)
	}
	if body.Status != contract.RunStatusQueued {
		t.Errorf("status = %q, want queued", body.Status)
	}

	got := q.recorded()
	if len(got) != 1 {
		t.Fatalf("Submit called %d times, want 1", len(got))
	}
	if got[0].Kind != contract.RunKindPlan {
		t.Errorf("Kind = %q, want plan", got[0].Kind)
	}
	if got[0].Repo != "prod" {
		t.Errorf("Repo = %q, want prod", got[0].Repo)
	}
}

func TestApplyQueuesRunKindApply(t *testing.T) {
	q := queueReturning("RID456", nil)
	rec := serveSubmit(t, q, contract.RunKindApply, `{"repo":"prod","dir":""}`)

	if rec.Code != http.StatusAccepted {
		t.Fatalf("status = %d, want 202 (body %q)", rec.Code, rec.Body.String())
	}
	if loc := rec.Header().Get("Location"); loc != "/v1/runs/RID456" {
		t.Errorf("Location = %q, want /v1/runs/RID456", loc)
	}

	got := q.recorded()
	if len(got) != 1 {
		t.Fatalf("Submit called %d times, want 1", len(got))
	}
	if got[0].Kind != contract.RunKindApply {
		t.Errorf("Kind = %q, want apply", got[0].Kind)
	}
}

// TestSubmitForwardsDirVerbatim proves the handler does NOT sanitize
// dir: runs.ValidateDir is called inside Submit (D-21), which is the
// only place allowed to decide what a legal dir is. A handler that
// pre-cleaned the value could smuggle a path past the validator.
func TestSubmitForwardsDirVerbatim(t *testing.T) {
	q := queueReturning("RID789", nil)
	serveSubmit(t, q, contract.RunKindPlan, `{"repo":"prod","dir":"envs/prod/"}`)

	got := q.recorded()
	if len(got) != 1 {
		t.Fatalf("Submit called %d times, want 1", len(got))
	}
	if got[0].Dir != "envs/prod/" {
		t.Errorf("Dir = %q, want envs/prod/ (verbatim)", got[0].Dir)
	}
}

func TestPlanCapacityExhausted(t *testing.T) {
	q := queueReturning("", jobq.ErrCapacityExhausted)
	rec := serveSubmit(t, q, contract.RunKindPlan, `{"repo":"prod","dir":""}`)

	if rec.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want 503 (body %q)", rec.Code, rec.Body.String())
	}
	if ra := rec.Header().Get("Retry-After"); ra != "30" {
		t.Errorf("Retry-After = %q, want 30", ra)
	}
	if er := decodeErr(t, rec); er.ErrorCode != contract.ErrCodeApplyCapacityExhausted {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeApplyCapacityExhausted)
	}
	if loc := rec.Header().Get("Location"); loc != "" {
		t.Errorf("Location = %q, want empty on a refusal", loc)
	}
}

// TestApplyCapacityExhausted proves the shared submit path gives both
// endpoints an identical D-06 response — an operator's retry logic
// cannot need to know which endpoint it hit.
func TestApplyCapacityExhausted(t *testing.T) {
	q := queueReturning("", jobq.ErrCapacityExhausted)
	rec := serveSubmit(t, q, contract.RunKindApply, `{"repo":"prod","dir":""}`)

	if rec.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want 503 (body %q)", rec.Code, rec.Body.String())
	}
	if ra := rec.Header().Get("Retry-After"); ra != "30" {
		t.Errorf("Retry-After = %q, want 30", ra)
	}
	if er := decodeErr(t, rec); er.ErrorCode != contract.ErrCodeApplyCapacityExhausted {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeApplyCapacityExhausted)
	}
}

// TestSubmitTypedErrorStatuses walks every *git.Error code Submit can
// return and asserts the status writeGitError assigns it.
func TestSubmitTypedErrorStatuses(t *testing.T) {
	cases := []struct {
		code string
		want int
	}{
		{contract.ErrCodeRunUnknownRepo, http.StatusNotFound},
		{contract.ErrCodeGitCloneMissing, http.StatusNotFound},
		{contract.ErrCodeRunInvalidDir, http.StatusBadRequest},
		{contract.ErrCodeRunTofuNotFound, http.StatusServiceUnavailable},
	}
	for _, c := range cases {
		t.Run(c.code, func(t *testing.T) {
			q := queueReturning("", &git.Error{Code: c.code, Message: "boom", Hint: "fix the Options field"})
			rec := serveSubmit(t, q, contract.RunKindPlan, `{"repo":"prod","dir":""}`)

			if rec.Code != c.want {
				t.Fatalf("status = %d, want %d (body %q)", rec.Code, c.want, rec.Body.String())
			}
			er := decodeErr(t, rec)
			if er.ErrorCode != c.code {
				t.Errorf("error_code = %q, want %q", er.ErrorCode, c.code)
			}
			if !strings.Contains(er.Message, "fix the Options field") {
				t.Errorf("message %q dropped the hint", er.Message)
			}
		})
	}
}

func TestPlanUnknownRepo(t *testing.T) {
	q := queueReturning("", &git.Error{
		Code:    contract.ErrCodeRunUnknownRepo,
		Message: "unknown repo staging",
		Hint:    "add it to the `repos` Options list",
	})
	rec := serveSubmit(t, q, contract.RunKindPlan, `{"repo":"staging","dir":""}`)

	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404 (body %q)", rec.Code, rec.Body.String())
	}
	if er := decodeErr(t, rec); er.ErrorCode != contract.ErrCodeRunUnknownRepo {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeRunUnknownRepo)
	}
}

func TestPlanInvalidDir(t *testing.T) {
	q := queueReturning("", &git.Error{
		Code:    contract.ErrCodeRunInvalidDir,
		Message: "dir must be a relative path inside the repo",
		Hint:    "set `dir` to a path relative to the repo root",
	})
	rec := serveSubmit(t, q, contract.RunKindPlan, `{"repo":"prod","dir":"../etc"}`)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 (body %q)", rec.Code, rec.Body.String())
	}
	if er := decodeErr(t, rec); er.ErrorCode != contract.ErrCodeRunInvalidDir {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeRunInvalidDir)
	}
}

func TestPlanCloneMissing(t *testing.T) {
	q := queueReturning("", &git.Error{
		Code:    contract.ErrCodeGitCloneMissing,
		Message: "repo prod has no working tree",
		Hint:    "the startup clone failed",
	})
	rec := serveSubmit(t, q, contract.RunKindPlan, `{"repo":"prod","dir":""}`)

	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404 (body %q)", rec.Code, rec.Body.String())
	}
	if er := decodeErr(t, rec); er.ErrorCode != contract.ErrCodeGitCloneMissing {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeGitCloneMissing)
	}
}

// TestPlanMalformedBody proves a bad body is refused before any slot,
// run directory or git command is touched — Submit is never called.
func TestPlanMalformedBody(t *testing.T) {
	q := queueReturning("RID000", nil)
	rec := serveSubmit(t, q, contract.RunKindPlan, `{not-json`)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 (body %q)", rec.Code, rec.Body.String())
	}
	er := decodeErr(t, rec)
	if er.ErrorCode != contract.ErrCodeRunInvalidDir {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeRunInvalidDir)
	}
	if !strings.Contains(er.Message, "repo") {
		t.Errorf("message %q does not describe the expected body", er.Message)
	}
	if got := q.recorded(); len(got) != 0 {
		t.Errorf("Submit called %d times, want 0 for a malformed body", len(got))
	}
}

// TestPlanUnknownField proves DisallowUnknownFields is on: a typo'd or
// invented field is a loud 400, not a silently dropped instruction.
func TestPlanUnknownField(t *testing.T) {
	q := queueReturning("RID000", nil)
	rec := serveSubmit(t, q, contract.RunKindPlan, `{"repo":"prod","dir":"","bogus":true}`)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 (body %q)", rec.Code, rec.Body.String())
	}
	if got := q.recorded(); len(got) != 0 {
		t.Errorf("Submit called %d times, want 0 for an unknown field", len(got))
	}
}

// TestApplyUnknownField proves the shared parser gives /v1/apply the
// same rejection.
func TestApplyUnknownField(t *testing.T) {
	q := queueReturning("RID000", nil)
	rec := serveSubmit(t, q, contract.RunKindApply, `{"repo":"prod","bogus":1}`)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 (body %q)", rec.Code, rec.Body.String())
	}
	if got := q.recorded(); len(got) != 0 {
		t.Errorf("Submit called %d times, want 0 for an unknown field", len(got))
	}
}

// TestPlanEmptyRepo documents where the empty-repo rejection lives:
// not in the handler (an empty string is valid JSON) but in Submit's
// Manager.Repo lookup, which returns the typed run_unknown_repo.
func TestPlanEmptyRepo(t *testing.T) {
	q := queueReturning("", &git.Error{
		Code:    contract.ErrCodeRunUnknownRepo,
		Message: "unknown repo ",
		Hint:    "add it to the `repos` Options list",
	})
	rec := serveSubmit(t, q, contract.RunKindPlan, `{"repo":"","dir":""}`)

	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404 (body %q)", rec.Code, rec.Body.String())
	}
	if got := q.recorded(); len(got) != 1 {
		t.Errorf("Submit called %d times, want 1 — the handler does not pre-judge the repo name", len(got))
	}
}

// TestPlanMissingDirIsLegal is D-23: an omitted dir means the repo
// root, so the field is optional on the wire.
func TestPlanMissingDirIsLegal(t *testing.T) {
	q := queueReturning("RIDROOT", nil)
	rec := serveSubmit(t, q, contract.RunKindPlan, `{"repo":"prod"}`)

	if rec.Code != http.StatusAccepted {
		t.Fatalf("status = %d, want 202 (body %q)", rec.Code, rec.Body.String())
	}
	got := q.recorded()
	if len(got) != 1 || got[0].Dir != "" {
		t.Errorf("recorded = %+v, want one call with Dir \"\"", got)
	}
}

// TestSubmitOpaqueErrorDoesNotLeak covers Submit's non-*git.Error
// paths (run-id generation, store create): a 500 with no part of the
// original error string.
func TestSubmitOpaqueErrorDoesNotLeak(t *testing.T) {
	q := queueReturning("", errUnclassified)
	rec := serveSubmit(t, q, contract.RunKindApply, `{"repo":"prod","dir":""}`)

	if rec.Code != http.StatusInternalServerError {
		t.Fatalf("status = %d, want 500 (body %q)", rec.Code, rec.Body.String())
	}
	if er := decodeErr(t, rec); er.ErrorCode != contract.ErrCodeApplyFailed {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeApplyFailed)
	}
	if raw := rec.Body.String(); strings.Contains(raw, "/data/runs") {
		t.Errorf("response body leaked a path: %s", raw)
	}
}

// TestSubmitRejectsAnOversizedBody is the WR-10 regression: the
// decoder had no http.MaxBytesReader, so a multi-gigabyte string value
// for `dir` was read into memory before validation ever rejected it —
// on an endpoint whose entire legal body is two short strings.
func TestSubmitRejectsAnOversizedBody(t *testing.T) {
	q := queueReturning("ABCDEFGH23456777", nil)

	oversized := `{"repo":"prod","dir":"` + strings.Repeat("a", maxRequestBodyBytes+1) + `"}`
	rec := serveSubmit(t, q, contract.RunKindPlan, oversized)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 (body %q)", rec.Code, rec.Body.String())
	}
	if n := len(q.recorded()); n != 0 {
		t.Errorf("Submit was called %d times for a body that never validated", n)
	}
}

// TestSubmitAcceptsABodyUnderTheLimit pins the cap as a ceiling rather
// than a new rejection rule: a legitimate request must be unaffected.
func TestSubmitAcceptsABodyUnderTheLimit(t *testing.T) {
	q := queueReturning("ABCDEFGH23456777", nil)

	rec := serveSubmit(t, q, contract.RunKindPlan, `{"repo":"prod","dir":"envs/prod"}`)
	if rec.Code != http.StatusAccepted {
		t.Fatalf("status = %d, want 202 (body %q)", rec.Code, rec.Body.String())
	}
}
