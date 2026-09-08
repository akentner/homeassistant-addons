package handlers

// repos_pull is the POST /v1/repos/{name}/pull handler (GIT-03). It is
// the HTTP surface of git.Manager.Pull (17-03): 17-03 owns the
// GIT_SSH_COMMAND construction, the backoff curve and the stderr
// classifier; this file owns the request parse, the typed-error →
// HTTP mapping (D-19) and the response shape. RequireBearer runs
// first (router.go), so a missing or wrong token never reaches this
// code.
//
// The handler mutates no persistent state of its own — Pull does the
// work and returns; the handler is a translator.
//
// Status contract of this endpoint (ROADMAP SC-3), all produced via
// statusForCode in write_error.go:
//
//	200 http.StatusOK          — pulled; body {name, mode, head}
//	400 http.StatusBadRequest  — malformed body, or git_ref_pull_incompatible (D-12)
//	403                        — git_ssh_handshake / git_unauthorized
//	404 http.StatusNotFound    — run_unknown_repo, git_clone_missing (D-14), git_ref_not_found
//	409                        — git_non_fast_forward
//	502 http.StatusBadGateway  — git_dns_failure, and the "git_clone_failed" opaque fallback

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"

	"iac-runner/internal/contract"
	"iac-runner/internal/git"
)

// pullTimeout bounds one POST /v1/repos/{name}/pull. A pull is a
// synchronous network operation (unlike a plan or an apply, which get
// a run id and a worker goroutine), so the handler owns its deadline.
// Two minutes is generous for a fast-forward on a homelab repo and
// well inside the server's WriteTimeout.
const pullTimeout = 2 * time.Minute

// reposPullResponse is the 200 body of POST /v1/repos/{name}/pull.
// Mode is "ff-only" for a fast-forward pull on the configured branch
// and "ref" for an explicit ref checkout (D-10/D-11) — the handler
// reports whatever the manager did rather than re-deriving it. Head is
// the post-pull commit SHA, so an operator can tell a no-op pull from
// a real advance and can pin the next plan to the same state.
type reposPullResponse struct {
	Name string `json:"name"`
	Mode string `json:"mode"`
	Head string `json:"head"`
}

// reposPullRequest is the OPTIONAL body of POST /v1/repos/{name}/pull.
//
// ff_only is the D-12 escape hatch and nothing else. 17-03 resolved
// the D-10/D-12 contradiction in favor of D-10: a body-less pull on a
// ref-pinned repo re-lands on that ref (otherwise a pinned repo could
// never be refreshed at all). D-12's refusal therefore fires only when
// a caller EXPLICITLY asks for fast-forward semantics against a repo
// the operator explicitly pinned — two requests that genuinely
// contradict each other. Defaulting this field to false is what makes
// that distinction possible, so the zero value is load-bearing.
type reposPullRequest struct {
	FFOnly bool `json:"ff_only"`
}

// repoPuller is the seam the handler depends on: the two git.Manager
// methods it actually calls. The exported ReposPull still takes the
// concrete *git.Manager (that is what router.go has), but the testable
// core takes this interface, so the handler's branches can be driven
// without a real repository, a real key or a real git process — the
// manager's own behavior is proven by 17-03's tests against an
// injected CommandRunner.
type repoPuller interface {
	Repo(name string) (git.RepoConfig, bool)
	Pull(ctx context.Context, name string, ffOnly bool) (git.PullOutcome, error)
}

// ReposPull returns the handler mounted at POST /v1/repos/{name}/pull
// by router.go (17-08 owns the mount).
func ReposPull(gitMgr *git.Manager) http.HandlerFunc {
	return reposPullHandler(gitMgr)
}

// reposPullHandler is the testable core of ReposPull.
func reposPullHandler(p repoPuller) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		name := chi.URLParam(r, "name")

		cfg, ok := p.Repo(name)
		if !ok {
			writeError(w, http.StatusNotFound, contract.ErrCodeRunUnknownRepo,
				"unknown repo \""+name+"\"",
				"add it to the `repos` Options list")
			return
		}

		// limitBody / maxRequestBodyBytes live in plan.go: the cap is
		// package-wide, and every POST in this package shares it.
		limitBody(w, r)

		body, err := decodeReposPullBody(r)
		if err != nil {
			// A body-shape failure has no dedicated code in the D-19
			// taxonomy, and inventing one here would be a contract
			// change (17-02 owns contract/types.go, D-20 requires a
			// DOCS.md row). run_invalid_dir is the taxonomy's
			// request-shape slot and is what /v1/plan and /v1/apply
			// already return for a malformed body, so the two write
			// endpoints stay consistent for a client.
			writeError(w, http.StatusBadRequest, contract.ErrCodeRunInvalidDir,
				"request body must be empty or JSON {\"ff_only\":<bool>}", "")
			return
		}

		// A pull spawns a network-touching git process, and
		// r.Context() alone bounds it by the CLIENT's patience: a curl
		// left open would hold a git process indefinitely. The
		// deadline is the runner's own ceiling; ssh's ConnectTimeout
		// (17-03) is what makes an unreachable remote fail faster
		// than this.
		ctx, cancel := context.WithTimeout(r.Context(), pullTimeout)
		defer cancel()

		outcome, err := p.Pull(ctx, name, body.FFOnly)
		if err != nil {
			var ge *git.Error
			if !errors.As(err, &ge) {
				// Opaque failure: 502 + "git_clone_failed" is the
				// taxonomy's generic git-side bucket. The original
				// error string stays in the log — it can carry a
				// path, an errno or an exec wrapper, and GIT-04
				// forbids all three on the wire.
				slog.Error("iac_runner.repo.pull_unclassified",
					"repo", name, "url", cfg.URL, "err", err.Error())
				writeError(w, http.StatusBadGateway, contract.ErrCodeGitCloneFailed,
					"git pull failed; see the iac-runner log", "")
				return
			}
			slog.Warn("iac_runner.repo.pull_failed",
				"repo", name, "url", cfg.URL, "error_code", ge.Code, "message", ge.Message)
			writeGitError(w, ge)
			return
		}

		slog.Info("iac_runner.repo.pulled",
			"repo", name, "url", cfg.URL, "mode", outcome.Mode, "head", outcome.Head,
		)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(reposPullResponse{
			Name: outcome.Name, Mode: outcome.Mode, Head: outcome.Head,
		})
	}
}

// decodeReposPullBody parses the optional request body.
//
// Three shapes are all legal and mean the same thing — no body at all
// (`curl -X POST`), an empty body, and `{}` — because the endpoint's
// documented usage is a bare POST. Anything else must be well-formed:
// DisallowUnknownFields turns a typo like {"ffonly":true} into a loud
// 400 instead of a silently ignored flag that would change which git
// commands run.
func decodeReposPullBody(r *http.Request) (reposPullRequest, error) {
	var body reposPullRequest
	if r.Body == nil {
		return body, nil
	}
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	if err := dec.Decode(&body); err != nil {
		if errors.Is(err, io.EOF) {
			// Empty body — the documented bare-POST shape.
			return reposPullRequest{}, nil
		}
		return reposPullRequest{}, err
	}
	return body, nil
}
