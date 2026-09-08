package handlers

// repos_pull is the POST /v1/repos/{name}/pull handler (GIT-03). It is
// the HTTP surface of git.Manager.Pull (17-03): 17-03 owns the
// GIT_SSH_COMMAND construction, the backoff curve and the stderr
// classifier; this file owns the request parse, the typed-error →
// HTTP mapping (D-19) and the response shape.
//
// RED skeleton (17-06 Task 1): the contracts below are published so
// the test suite compiles and fails on assertions rather than on a
// load error. The GREEN commit fills in the bodies.

import (
	"context"
	"net/http"

	"iac-runner/internal/git"
)

// reposPullResponse is the 200 body of POST /v1/repos/{name}/pull.
type reposPullResponse struct {
	Name string `json:"name"`
	Mode string `json:"mode"`
	Head string `json:"head"`
}

// reposPullRequest is the optional body of POST /v1/repos/{name}/pull.
type reposPullRequest struct {
	FFOnly bool `json:"ff_only"`
}

// repoPuller is the seam the handler depends on.
type repoPuller interface {
	Repo(name string) (git.RepoConfig, bool)
	Pull(ctx context.Context, name string, ffOnly bool) (git.PullOutcome, error)
}

// ReposPull returns the handler mounted at POST /v1/repos/{name}/pull.
func ReposPull(gitMgr *git.Manager) http.HandlerFunc {
	return reposPullHandler(gitMgr)
}

// reposPullHandler is the testable core of ReposPull.
func reposPullHandler(p repoPuller) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotImplemented)
	}
}
