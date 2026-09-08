package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"

	"iac-runner/internal/contract"
	"iac-runner/internal/git"
)

// Compile-time signature lock. A grep cannot assert a Go signature
// (the opening brace shares the line), but the compiler can: if
// ReposPull's parameter or return type ever drifts, this file stops
// building and 17-08's router mount would too.
var _ func(*git.Manager) http.HandlerFunc = ReposPull

// pullCall records one Pull invocation so a test can assert the
// ff_only wire flag actually reached git.Manager.Pull (the D-10/D-12
// contract 17-03 shipped: the handler owns the wire, the manager owns
// the semantics).
type pullCall struct {
	name   string
	ffOnly bool
}

// stubPuller stands in for *git.Manager. The handler only calls Repo
// and Pull, so the seam is those two methods; the real integration
// (GIT_SSH_COMMAND, the backoff, the stderr classifier) is proven by
// 17-03's own tests against an injected CommandRunner.
type stubPuller struct {
	cfg     git.RepoConfig
	known   bool
	outcome git.PullOutcome
	err     error
	calls   []pullCall
}

func (s *stubPuller) Repo(string) (git.RepoConfig, bool) { return s.cfg, s.known }

func (s *stubPuller) Pull(_ context.Context, name string, ffOnly bool) (git.PullOutcome, error) {
	s.calls = append(s.calls, pullCall{name: name, ffOnly: ffOnly})
	return s.outcome, s.err
}

// knownRepo is the default stub: repo "prod" is registered and Pull
// fast-forwards successfully.
func knownRepo() *stubPuller {
	return &stubPuller{
		cfg:     git.RepoConfig{Name: "prod", URL: "git@example.invalid:org/prod.git", Branch: "main"},
		known:   true,
		outcome: git.PullOutcome{Name: "prod", Mode: git.PullModeFastForward, Head: "abc123"},
	}
}

// newPullRequest builds a POST /v1/repos/{name}/pull request with the
// chi route parameter populated, so the handler can be called directly
// without mounting a router.
func newPullRequest(t *testing.T, name, body string) *http.Request {
	t.Helper()
	var r *http.Request
	if body == "" {
		r = httptest.NewRequest(http.MethodPost, "/v1/repos/"+name+"/pull", nil)
	} else {
		r = httptest.NewRequest(http.MethodPost, "/v1/repos/"+name+"/pull", strings.NewReader(body))
		r.Header.Set("Content-Type", "application/json")
	}
	rctx := chi.NewRouteContext()
	rctx.URLParams.Add("name", name)
	return r.WithContext(context.WithValue(r.Context(), chi.RouteCtxKey, rctx))
}

// servePull runs the handler against the stub and returns the recorder.
func servePull(t *testing.T, p repoPuller, name, body string) *httptest.ResponseRecorder {
	t.Helper()
	rec := httptest.NewRecorder()
	reposPullHandler(p)(rec, newPullRequest(t, name, body))
	return rec
}

// decodeErr decodes a contract.ErrorResponse body, failing the test if
// the body is not valid JSON.
func decodeErr(t *testing.T, rec *httptest.ResponseRecorder) contract.ErrorResponse {
	t.Helper()
	var er contract.ErrorResponse
	if err := json.NewDecoder(rec.Body).Decode(&er); err != nil {
		t.Fatalf("decode error body: %v (raw %q)", err, rec.Body.String())
	}
	return er
}

func TestReposPullSuccess(t *testing.T) {
	p := knownRepo()
	rec := servePull(t, p, "prod", "")

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type = %q, want application/json", ct)
	}

	var body reposPullResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if body.Name != "prod" || body.Mode != "ff-only" || body.Head != "abc123" {
		t.Errorf("body = %+v, want {prod ff-only abc123}", body)
	}

	// D-10 is the default: an operator POSTing /pull with no body must
	// not get the D-12 refusal on a pinned repo, so ffOnly defaults to
	// false.
	if len(p.calls) != 1 {
		t.Fatalf("Pull called %d times, want 1", len(p.calls))
	}
	if p.calls[0].ffOnly {
		t.Errorf("Pull ffOnly = true, want false for a body-less request (D-10 default)")
	}
	if p.calls[0].name != "prod" {
		t.Errorf("Pull name = %q, want prod", p.calls[0].name)
	}
}

// TestReposPullRefModeIsPassedThrough proves the handler does not
// interpret the ref semantics — it reports whatever Mode the manager
// returns (D-10/D-11 live in 17-03).
func TestReposPullRefModeIsPassedThrough(t *testing.T) {
	p := knownRepo()
	p.cfg.Ref = "v1.2.3"
	p.outcome = git.PullOutcome{Name: "prod", Mode: git.PullModeRef, Head: "deadbee"}

	rec := servePull(t, p, "prod", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	var body reposPullResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if body.Mode != "ref" {
		t.Errorf("mode = %q, want ref", body.Mode)
	}
}

// TestReposPullFFOnlyFlagReachesPull is the D-12 wire contract: the
// optional ff_only body flag is the ONLY thing that can trigger the
// pinned-repo refusal, so it must actually reach Pull.
func TestReposPullFFOnlyFlagReachesPull(t *testing.T) {
	p := knownRepo()
	rec := servePull(t, p, "prod", `{"ff_only":true}`)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	if len(p.calls) != 1 {
		t.Fatalf("Pull called %d times, want 1", len(p.calls))
	}
	if !p.calls[0].ffOnly {
		t.Errorf("Pull ffOnly = false, want true for {\"ff_only\":true}")
	}
}

func TestReposPullUnknownRepo(t *testing.T) {
	p := &stubPuller{known: false}
	rec := servePull(t, p, "nope", "")

	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404 (body %q)", rec.Code, rec.Body.String())
	}
	er := decodeErr(t, rec)
	if er.ErrorCode != contract.ErrCodeRunUnknownRepo {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeRunUnknownRepo)
	}
	if !strings.Contains(er.Message, "nope") {
		t.Errorf("message %q does not name the repo", er.Message)
	}
	if len(p.calls) != 0 {
		t.Errorf("Pull called %d times, want 0 for an unknown repo", len(p.calls))
	}
}

// TestReposPullSSHHandshakeIs403 locks GIT-03 / ROADMAP SC-3: an auth
// failure is 403, not a generic upstream error.
func TestReposPullSSHHandshakeIs403(t *testing.T) {
	p := knownRepo()
	p.err = &git.Error{
		Code:    contract.ErrCodeGitSSHHandshake,
		Message: "pull of repo prod failed",
		Hint:    "check the deploy key at /data/keys/prod.key",
	}

	rec := servePull(t, p, "prod", "")
	if rec.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want 403 (body %q)", rec.Code, rec.Body.String())
	}
	er := decodeErr(t, rec)
	if er.ErrorCode != contract.ErrCodeGitSSHHandshake {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeGitSSHHandshake)
	}
	if !strings.Contains(er.Message, "deploy key") {
		t.Errorf("message %q dropped the operator hint", er.Message)
	}
}

// TestReposPullNonFastForwardIs409 locks the other half of SC-3.
func TestReposPullNonFastForwardIs409(t *testing.T) {
	p := knownRepo()
	p.err = &git.Error{
		Code:    contract.ErrCodeGitNonFastForward,
		Message: "pull of repo prod failed",
		Hint:    "pin with `ref`",
	}

	rec := servePull(t, p, "prod", "")
	if rec.Code != http.StatusConflict {
		t.Fatalf("status = %d, want 409 (body %q)", rec.Code, rec.Body.String())
	}
	if er := decodeErr(t, rec); er.ErrorCode != contract.ErrCodeGitNonFastForward {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeGitNonFastForward)
	}
}

// TestReposPullRefPullIncompatibleIs400 is D-12: ref + explicit
// ff_only is a request-shape contradiction, not an infrastructure
// failure.
func TestReposPullRefPullIncompatibleIs400(t *testing.T) {
	p := knownRepo()
	p.cfg.Ref = "v1.2.3"
	p.err = &git.Error{
		Code:    contract.ErrCodeGitRefPullIncompatible,
		Message: "repo prod is pinned to ref v1.2.3; a fast-forward pull is not applicable",
		Hint:    "drop ff_only from the request",
	}

	rec := servePull(t, p, "prod", `{"ff_only":true}`)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 (body %q)", rec.Code, rec.Body.String())
	}
	if er := decodeErr(t, rec); er.ErrorCode != contract.ErrCodeGitRefPullIncompatible {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeGitRefPullIncompatible)
	}
}

// TestReposPullCloneMissingIs404 is D-14 on the pull path.
func TestReposPullCloneMissingIs404(t *testing.T) {
	p := knownRepo()
	p.err = &git.Error{
		Code:    contract.ErrCodeGitCloneMissing,
		Message: "repo prod has no working tree",
		Hint:    "the startup clone failed",
	}

	rec := servePull(t, p, "prod", "")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404 (body %q)", rec.Code, rec.Body.String())
	}
	if er := decodeErr(t, rec); er.ErrorCode != contract.ErrCodeGitCloneMissing {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeGitCloneMissing)
	}
}

// TestReposPullOpaqueErrorDoesNotLeak is the GIT-04 no-stack-trace
// guarantee. An untyped error must never have its string put on the
// wire.
func TestReposPullOpaqueErrorDoesNotLeak(t *testing.T) {
	p := knownRepo()
	p.err = errors.New(
		"internal: process exited with code 128\n\tgoroutine 1 [running]:\n\tmain.foo() /data/repos/prod/x.go:12")

	rec := servePull(t, p, "prod", "")
	if rec.Code != http.StatusBadGateway {
		t.Fatalf("status = %d, want 502 (body %q)", rec.Code, rec.Body.String())
	}
	er := decodeErr(t, rec)
	if er.ErrorCode != contract.ErrCodeGitCloneFailed {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeGitCloneFailed)
	}

	raw := rec.Body.String()
	for _, leak := range []string{"goroutine", "process exited", "/data/", "main.foo"} {
		if strings.Contains(raw, leak) {
			t.Errorf("response body leaked %q: %s", leak, raw)
		}
	}
}

// TestReposPullMalformedBody proves a bad body is rejected before any
// git command runs.
func TestReposPullMalformedBody(t *testing.T) {
	p := knownRepo()
	rec := servePull(t, p, "prod", `{not-json`)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 (body %q)", rec.Code, rec.Body.String())
	}
	if er := decodeErr(t, rec); er.ErrorCode != contract.ErrCodeRunInvalidDir {
		t.Errorf("error_code = %q, want %q", er.ErrorCode, contract.ErrCodeRunInvalidDir)
	}
	if len(p.calls) != 0 {
		t.Errorf("Pull called %d times, want 0 for a malformed body", len(p.calls))
	}
}

// TestReposPullUnknownBodyField proves DisallowUnknownFields is on, so
// a typo like {"ffonly":true} is a loud 400 instead of a silently
// ignored flag that changes git semantics.
func TestReposPullUnknownBodyField(t *testing.T) {
	p := knownRepo()
	rec := servePull(t, p, "prod", `{"ffonly":true}`)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 (body %q)", rec.Code, rec.Body.String())
	}
	if len(p.calls) != 0 {
		t.Errorf("Pull called %d times, want 0 for an unknown body field", len(p.calls))
	}
}

// TestReposPullEmptyJSONBodyIsLegal covers the curl -X POST -d '{}'
// shape as well as a body-less POST.
func TestReposPullEmptyJSONBodyIsLegal(t *testing.T) {
	p := knownRepo()
	rec := servePull(t, p, "prod", `{}`)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	if len(p.calls) != 1 || p.calls[0].ffOnly {
		t.Errorf("calls = %+v, want one call with ffOnly=false", p.calls)
	}
}
