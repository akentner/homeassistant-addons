package httpapi

// router_test asserts the two things a router change can break and a
// handler test cannot see: that every URL is actually reachable, and
// that it sits on the intended side of the auth gate.
//
// 17-08 is the plan that touches router.go, so the Phase 16
// non-regression claim is proven here rather than assumed: /,
// /healthz, /v1/version and /v1/auth/rotate are exercised alongside
// the five new Phase 17 mounts.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"iac-runner/internal/auth"
	"iac-runner/internal/contract"
	"iac-runner/internal/git"
	"iac-runner/internal/jobq"
	"iac-runner/internal/keys"
	"iac-runner/internal/runs"
	"iac-runner/internal/statebackend"
)

// Compile-time signature lock. An anchored grep cannot match this
// signature (it spans several lines), but the compiler can — and this
// is the exact argument order 17-07's main.go wiring compiles against.
var _ func(string, *auth.TokenStore, *keys.Validator, *git.Manager, *runs.Store, *jobq.Queue) http.Handler = NewRouter

const testRunnerVersion = "0.0.0-test"

// testRouter builds a router over real auth/keys/runs dependencies and
// returns it with the valid bearer token.
//
// gitMgr and the queue are nil: every assertion in this file is about
// routing and the auth gate, and both of those are decided before a
// handler body runs. Constructing a real git.Manager or jobq.Queue
// would re-test 17-03/17-05 and need a repository and a tofu binary.
func testRouter(t *testing.T) (http.Handler, string) {
	t.Helper()

	dataDir := t.TempDir()
	store, err := auth.NewFileTokenStore(dataDir)
	if err != nil {
		t.Fatalf("NewFileTokenStore: %v", err)
	}
	token, err := store.Generate()
	if err != nil {
		t.Fatalf("Generate: %v", err)
	}
	if err := store.Persist(token); err != nil {
		t.Fatalf("Persist: %v", err)
	}

	backend, err := statebackend.New("local", statebackend.Options{DataDir: dataDir})
	if err != nil {
		t.Fatalf("statebackend.New: %v", err)
	}
	validator := keys.NewValidator(filepath.Join(dataDir, "keys"), backend)

	runStore, err := runs.NewStore(filepath.Join(dataDir, "runs"), nil)
	if err != nil {
		t.Fatalf("runs.NewStore: %v", err)
	}

	return NewRouter(testRunnerVersion, store, validator, nil, runStore, nil), token
}

// do issues one request against the router. token == "" means no
// Authorization header at all.
func do(t *testing.T, h http.Handler, method, target, token string) *httptest.ResponseRecorder {
	t.Helper()
	r := httptest.NewRequest(method, target, nil)
	if token != "" {
		r.Header.Set("Authorization", "Bearer "+token)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, r)
	return rec
}

// TestRouterPhase16SurfaceUnauthenticated: / and /healthz must stay
// outside the auth gate, or an external monitor loses its liveness
// probe. /healthz is asserted as "not 401" rather than "200" because
// its body depends on a `tofu` binary being on PATH, which is a
// property of the host, not of the router.
func TestRouterPhase16SurfaceUnauthenticated(t *testing.T) {
	h, _ := testRouter(t)

	rec := do(t, h, http.MethodGet, "/", "")
	if rec.Code != http.StatusOK {
		t.Errorf("GET / = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	var root contract.RootResponse
	if err := json.NewDecoder(rec.Body).Decode(&root); err != nil {
		t.Errorf("GET / body is not a RootResponse: %v", err)
	} else if root.RunnerVersion != testRunnerVersion {
		t.Errorf("GET / runner_version = %q, want %q", root.RunnerVersion, testRunnerVersion)
	}

	if rec := do(t, h, http.MethodGet, "/healthz", ""); rec.Code == http.StatusUnauthorized {
		t.Error("GET /healthz returned 401; it must stay unauthenticated")
	}
}

// TestRouterVersionStillMounted is RUN-01 through the router: the
// Phase 16 handshake endpoint survives the Phase 17 mount refactor,
// still behind the bearer gate, still returning VersionHandshake.
func TestRouterVersionStillMounted(t *testing.T) {
	h, token := testRouter(t)

	rec := do(t, h, http.MethodGet, "/v1/version", token)
	if rec.Code != http.StatusOK {
		t.Fatalf("GET /v1/version = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	var body contract.VersionHandshake
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode VersionHandshake: %v", err)
	}
	if body.RunnerVersion != testRunnerVersion {
		t.Errorf("runner_version = %q, want %q", body.RunnerVersion, testRunnerVersion)
	}
	if body.SchemaVersion == "" || body.MinSupportedOpenTofu == "" || body.MaxSupportedOpenTofu == "" {
		t.Errorf("handshake has empty semver fields: %+v", body)
	}
}

// TestRouterAuthRotateStillMounted: the Phase 16 rotation endpoint
// answers on a valid bearer and hands back a fresh token plus the
// grace window.
func TestRouterAuthRotateStillMounted(t *testing.T) {
	h, token := testRouter(t)

	rec := do(t, h, http.MethodPost, "/v1/auth/rotate", token)
	if rec.Code != http.StatusOK {
		t.Fatalf("POST /v1/auth/rotate = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	var body contract.RotateResponse
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("decode RotateResponse: %v", err)
	}
	if body.NewToken == "" || body.NewToken == token {
		t.Errorf("new_token = %q, want a fresh token", body.NewToken)
	}
	if body.GraceExpiresAt == "" {
		t.Error("grace_expires_at is empty")
	}
}

// TestRouterPhase17EndpointsRequireBearer is the security half of the
// mount: all five new URLs are inside the /v1 subrouter, so an
// anonymous caller is refused by the middleware before any handler
// body runs. A 404 here would mean the route was never mounted; a 2xx
// would mean it was mounted outside the gate.
func TestRouterPhase17EndpointsRequireBearer(t *testing.T) {
	h, _ := testRouter(t)

	for _, tc := range []struct{ method, target string }{
		{http.MethodPost, "/v1/repos/prod/pull"},
		{http.MethodPost, "/v1/plan"},
		{http.MethodPost, "/v1/apply"},
		{http.MethodGet, "/v1/runs/ABCDEFGH23456777"},
		{http.MethodGet, "/v1/runs"},
	} {
		t.Run(tc.method+" "+tc.target, func(t *testing.T) {
			rec := do(t, h, tc.method, tc.target, "")
			if rec.Code != http.StatusUnauthorized {
				t.Fatalf("status = %d, want 401 (body %q)", rec.Code, rec.Body.String())
			}
			var body contract.ErrorResponse
			if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
				t.Fatalf("decode ErrorResponse: %v", err)
			}
			if body.ErrorCode != contract.ErrCodeUnauthorized {
				t.Errorf("error_code = %q, want %q", body.ErrorCode, contract.ErrCodeUnauthorized)
			}
		})
	}
}

// TestRouterReadEndpointsReachable: with a valid bearer the two read
// endpoints reach their handlers and answer from the run store — the
// mount is wired to the right handler, not merely present.
func TestRouterReadEndpointsReachable(t *testing.T) {
	h, token := testRouter(t)

	rec := do(t, h, http.MethodGet, "/v1/runs", token)
	if rec.Code != http.StatusOK {
		t.Fatalf("GET /v1/runs = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	var list contract.RunListResponse
	if err := json.NewDecoder(rec.Body).Decode(&list); err != nil {
		t.Fatalf("decode RunListResponse: %v", err)
	}
	if list.Count != 0 || len(list.Runs) != 0 || list.Limit != contract.DefaultRunListLimit {
		t.Errorf("empty listing = %+v, want count 0 / limit %d", list, contract.DefaultRunListLimit)
	}

	// A well-formed but absent id proves GetRun (not ListRuns) is
	// behind /v1/runs/{id}: only GetRun can produce run_not_found.
	rec = do(t, h, http.MethodGet, "/v1/runs/ABCDEFGH23456777", token)
	if rec.Code != http.StatusNotFound {
		t.Fatalf("GET /v1/runs/{id} = %d, want 404 (body %q)", rec.Code, rec.Body.String())
	}
	var errBody contract.ErrorResponse
	if err := json.NewDecoder(rec.Body).Decode(&errBody); err != nil {
		t.Fatalf("decode ErrorResponse: %v", err)
	}
	if errBody.ErrorCode != contract.ErrCodeRunNotFound {
		t.Errorf("error_code = %q, want %q", errBody.ErrorCode, contract.ErrCodeRunNotFound)
	}

	// A malformed id is the traversal guard, all the way through the
	// router: no filesystem access, a typed 404.
	rec = do(t, h, http.MethodGet, "/v1/runs/..%2Fetc", token)
	if rec.Code != http.StatusNotFound {
		t.Fatalf("GET /v1/runs/../etc = %d, want 404 (body %q)", rec.Code, rec.Body.String())
	}
	if raw := rec.Body.String(); strings.Contains(raw, "/data") || strings.Contains(raw, "no such file") {
		t.Errorf("traversal response leaked filesystem detail: %s", raw)
	}
}

// TestRouterGetRunServesAStoredRun closes the loop the handler tests
// cannot: a run written through runs.Store is served by the mounted
// GET /v1/runs/{id}, including the SEC-03 redacted output page. This
// is the end-to-end path ROADMAP SC-7 and SC-10 describe.
func TestRouterGetRunServesAStoredRun(t *testing.T) {
	dataDir := t.TempDir()
	store, err := auth.NewFileTokenStore(dataDir)
	if err != nil {
		t.Fatalf("NewFileTokenStore: %v", err)
	}
	token, err := store.Generate()
	if err != nil {
		t.Fatalf("Generate: %v", err)
	}
	if err := store.Persist(token); err != nil {
		t.Fatalf("Persist: %v", err)
	}
	backend, err := statebackend.New("local", statebackend.Options{DataDir: dataDir})
	if err != nil {
		t.Fatalf("statebackend.New: %v", err)
	}
	runsDir := filepath.Join(dataDir, "runs")
	runStore, err := runs.NewStore(runsDir, nil)
	if err != nil {
		t.Fatalf("runs.NewStore: %v", err)
	}

	runID, err := runs.NewRunID()
	if err != nil {
		t.Fatalf("NewRunID: %v", err)
	}
	if err := runStore.Create(runs.Meta{
		RunID:     runID,
		Repo:      "prod",
		Dir:       "envs/prod",
		Kind:      contract.RunKindApply,
		Status:    contract.RunStatusRunning,
		StartedAt: runStore.Now(),
	}); err != nil {
		t.Fatalf("Create: %v", err)
	}
	w, err := runStore.OpenOutput(runID)
	if err != nil {
		t.Fatalf("OpenOutput: %v", err)
	}
	if err := w.WriteLine("stdout", "Apply complete!"); err != nil {
		t.Fatalf("WriteLine: %v", err)
	}
	if err := w.Close(); err != nil {
		t.Fatalf("Close: %v", err)
	}

	h := NewRouter(testRunnerVersion, store,
		keys.NewValidator(filepath.Join(dataDir, "keys"), backend), nil, runStore, nil)

	rec := do(t, h, http.MethodGet, "/v1/runs/"+runID, token)
	if rec.Code != http.StatusOK {
		t.Fatalf("GET /v1/runs/{id} = %d, want 200 (body %q)", rec.Code, rec.Body.String())
	}
	var detail contract.RunDetail
	if err := json.NewDecoder(rec.Body).Decode(&detail); err != nil {
		t.Fatalf("decode RunDetail: %v", err)
	}
	if detail.RunID != runID || detail.Repo != "prod" || detail.Status != contract.RunStatusRunning {
		t.Errorf("detail = %+v", detail)
	}
	if len(detail.OutputLines) != 1 || detail.OutputLines[0] != "Apply complete!" {
		t.Errorf("output_lines = %v, want the one written line", detail.OutputLines)
	}
	if detail.Page != 1 || detail.PageSize != contract.DefaultOutputPageSize || detail.TotalLines != 1 {
		t.Errorf("pagination = %d/%d/%d", detail.Page, detail.PageSize, detail.TotalLines)
	}
	if detail.ExitCode != nil {
		t.Errorf("exit_code = %v, want null for a running run", *detail.ExitCode)
	}

	// D-01 / 17-04's chmod contract, re-checked through the handler
	// flow: the run tree is 0700 and meta.json 0600, so a run's
	// output is unreadable to anything but the add-on process.
	assertMode(t, runsDir, 0o700)
	assertMode(t, filepath.Join(runsDir, runID), 0o700)
	assertMode(t, filepath.Join(runsDir, runID, "meta.json"), 0o600)
}

// assertMode fails the test unless path's permission bits are want.
func assertMode(t *testing.T, path string, want os.FileMode) {
	t.Helper()
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat %s: %v", path, err)
	}
	if got := info.Mode().Perm(); got != want {
		t.Errorf("%s mode = %o, want %o", path, got, want)
	}
}
