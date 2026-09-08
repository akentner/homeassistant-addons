package handlers

// plan is the POST /v1/plan + POST /v1/apply handler pair (RUN-02 /
// RUN-03). Both submit a job to jobq.Queue and answer 202 + a run id
// immediately; the tofu invocation lives in the worker goroutine
// (17-05). RequireBearer runs first (router.go), so a missing or wrong
// token never reaches this code.
//
// Everything past the body parse belongs to the queue: the unknown-repo
// lookup, the D-21 dir validation, the D-14 clone-present check, the
// tofu-path resolution, the D-04 capacity gate and the D-05 per-repo
// serialization all happen inside Submit, in that order, all before a
// run directory exists. The handler deliberately re-checks none of
// them — a second copy of those rules here would be a second thing to
// keep in sync, and the copy that drifted would be the one clients see.
//
// Status contract of both endpoints, all produced via statusForCode in
// write_error.go except the two written here:
//
//	202 http.StatusAccepted           — queued; Location: /v1/runs/{id}
//	400 http.StatusBadRequest         — malformed body (written here), run_invalid_dir
//	404                               — run_unknown_repo, git_clone_missing
//	503 http.StatusServiceUnavailable — apply_capacity_exhausted (+ Retry-After: 30,
//	                                    written here), run_tofu_not_found
//	500                               — an unclassified Submit failure

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"

	"iac-runner/internal/contract"
	"iac-runner/internal/jobq"
)

// maxRequestBodyBytes caps every request body this package decodes.
// Without it a json.Decoder reads a multi-gigabyte string value for
// `dir` into memory before validation ever rejects it, on an endpoint
// whose entire legal body is two short strings. 64 KiB is three orders
// of magnitude more than any legitimate request needs.
const maxRequestBodyBytes = 64 * 1024

// limitBody caps r.Body in place. The ResponseWriter argument is what
// lets net/http close the connection instead of leaving a client
// streaming into a body nobody will read.
func limitBody(w http.ResponseWriter, r *http.Request) {
	if r.Body == nil {
		return
	}
	r.Body = http.MaxBytesReader(w, r.Body, maxRequestBodyBytes)
}

// retryAfterCapacitySeconds is the D-06 back-pressure hint. It is a
// constant rather than a function of queue depth because there is no
// queue: a saturated runner refuses, so the only honest answer is "try
// again in a bit", and a stable number is one an operator's retry loop
// can be written against.
const retryAfterCapacitySeconds = "30"

// planApplyRequest is the shared body shape for /v1/plan and /v1/apply
// (RUN-02 / RUN-03). These two fields are the entire user-controlled
// surface of a run; nothing else in the body is read, and neither
// field reaches a command line before jobq validates it.
//
// dir is optional (D-23): omitted or "" means the repo root.
type planApplyRequest struct {
	Repo string `json:"repo"`
	Dir  string `json:"dir"`
}

// submitter is the seam the two handlers depend on: the single
// jobq.Queue method they call. The exported Plan / Apply still take
// the concrete *jobq.Queue (that is what router.go builds), but the
// testable core takes this interface, so every response branch can be
// driven without a real queue, a real store or a real tofu binary.
type submitter interface {
	Submit(req jobq.Request) (string, error)
}

// Plan returns the handler mounted at POST /v1/plan by router.go
// (17-08 owns the mount).
func Plan(q *jobq.Queue) http.HandlerFunc {
	return submitHandler(q, contract.RunKindPlan)
}

// Apply returns the handler mounted at POST /v1/apply by router.go
// (17-08 owns the mount).
func Apply(q *jobq.Queue) http.HandlerFunc {
	return submitHandler(q, contract.RunKindApply)
}

// submitHandler is the body-parse + Submit + 202/503/typed-error path
// shared by Plan and Apply.
//
// One function for both endpoints, parameterized only by kind, because
// they are otherwise identical — and because that identity is itself a
// contract: a client must not have to discover that /v1/apply rejects
// a malformed body differently from /v1/plan.
func submitHandler(q submitter, kind contract.RunKind) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limitBody(w, r)

		var body planApplyRequest
		dec := json.NewDecoder(r.Body)
		// An unknown field is a 400, not a shrug: {"repo":"prod","dirr":"envs"}
		// would otherwise run against the repo root and report success
		// for something the caller never asked for.
		dec.DisallowUnknownFields()
		if err := dec.Decode(&body); err != nil {
			writeError(w, http.StatusBadRequest, contract.ErrCodeRunInvalidDir,
				"request body must be JSON {\"repo\":\"<name>\",\"dir\":\"<subpath>\"}", "")
			return
		}

		runID, err := q.Submit(jobq.Request{Repo: body.Repo, Dir: body.Dir, Kind: kind})
		if err != nil {
			// Capacity exhaustion is the one Submit failure that is
			// not a *git.Error — it is the bare sentinel, matched with
			// errors.Is — and the one that carries a header. D-06: the
			// refusal is visible back-pressure, not an invisible queue,
			// so the operator gets both the code and the retry hint.
			if errors.Is(err, jobq.ErrCapacityExhausted) {
				w.Header().Set("Retry-After", retryAfterCapacitySeconds)
				writeError(w, http.StatusServiceUnavailable,
					contract.ErrCodeApplyCapacityExhausted,
					"apply capacity exhausted; retry after "+retryAfterCapacitySeconds+"s",
					"raise `max_parallel_jobs` in Options, or wait for the in-flight jobs to finish")
				return
			}
			slog.Warn("iac_runner.run.rejected",
				"repo", body.Repo, "dir", body.Dir, "kind", string(kind), "err", err.Error())
			writeGitError(w, err)
			return
		}

		slog.Info("iac_runner.run.queued",
			"run_id", runID, "repo", body.Repo, "dir", body.Dir, "kind", string(kind),
		)

		// A path, not an absolute URL: the add-on is reached through
		// the HA ingress proxy as often as directly, so baking in a
		// scheme and host would produce a Location the client cannot
		// follow. A relative Location is resolved against the request
		// URL by every HTTP client (RFC 7231 §7.1.2).
		w.Header().Set("Location", "/v1/runs/"+runID)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusAccepted)
		_ = json.NewEncoder(w).Encode(contract.RunAccepted{
			RunID: runID, Status: contract.RunStatusQueued,
		})
	}
}
