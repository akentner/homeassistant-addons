package handlers

// list_runs is the GET /v1/runs handler (RUN-05): the most recent N
// runs, newest-first, filtered by ?repo= and ?status=, default 20 and
// capped at 100.
//
// A summary carries no output. Listing 20 runs must not read 20 log
// files, so runs.Store.List reads meta.json only and output stays
// on-demand via GET /v1/runs/{id}. That is also why this handler
// never calls auditRedactions: nothing here was redacted, so there
// is nothing to audit (the single-emission contract in
// redaction_audit.go).
//
// No per-call slog record either. A dashboard polls this endpoint;
// one record per poll would drown the log stream, and the OBS-01
// request logger already reports the request itself.
//
// Status contract (D-19):
//
//	200 http.StatusOK          — always, including an empty result
//	400 (run_invalid_dir)      — ?status= is not a RunStatus enum value
//	500 (apply_failed)         — a real filesystem failure; detail stays in the log

import (
	"encoding/json"
	"log/slog"
	"net/http"

	"iac-runner/internal/contract"
	"iac-runner/internal/runs"
)

// runLister is the seam the handler depends on: the single runs.Store
// method it calls. The exported ListRuns keeps the concrete
// *runs.Store (that is what router.go has), so the unexported core is
// what tests drive.
type runLister interface {
	List(f runs.ListFilter) ([]runs.Meta, error)
}

// ListRuns returns the handler mounted at GET /v1/runs by router.go.
// store is the runs.Store constructed in main.go at startup (17-07).
func ListRuns(store *runs.Store) http.HandlerFunc {
	return listRunsHandler(store)
}

// listRunsHandler is the testable core of ListRuns.
func listRunsHandler(l runLister) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		q := r.URL.Query()

		// ?repo= is free-form. An unknown repo yields no rows, which
		// is the right answer rather than a 404: a repo that exists
		// with zero runs and a repo nobody configured are both
		// "nothing to show", and only the operator can tell them
		// apart from the Options list.
		repo := q.Get("repo")

		// ?status= must be one of the five enum values. Validating
		// here rather than passing the string through is what keeps a
		// typo from returning a confident, empty 200.
		statusStr := q.Get("status")
		if statusStr != "" && !isKnownRunStatus(statusStr) {
			// run_invalid_dir is the D-19 taxonomy's request-shape
			// slot, and is what 17-06 already returns for a malformed
			// body on all three write endpoints. Inventing a code for
			// this case would be a contract change — 17-02 owns
			// contract/types.go and D-20 needs a DOCS.md row.
			writeError(w, http.StatusBadRequest, contract.ErrCodeRunInvalidDir,
				"invalid ?status= value \""+statusStr+"\"",
				"use one of: queued, running, succeeded, failed, interrupted")
			return
		}

		// ?limit= is clamped here so the response's limit field
		// reports what was actually applied. runs.Store.List clamps
		// too (defence in depth), but only the handler can tell the
		// client what it got.
		limit := contract.DefaultRunListLimit
		if n, ok := positiveInt(q.Get("limit")); ok {
			limit = n
		}
		if limit > contract.MaxRunListLimit {
			limit = contract.MaxRunListLimit
		}

		metas, err := l.List(runs.ListFilter{
			Repo:   repo,
			Status: contract.RunStatus(statusStr),
			Limit:  limit,
		})
		if err != nil {
			// List only fails on a filesystem problem (a corrupt or
			// mid-creation run is skipped, not surfaced). The error
			// string can carry a path, so it is logged, not served.
			slog.ErrorContext(r.Context(), "iac_runner.run.list_failed", "err", err.Error())
			writeError(w, http.StatusInternalServerError, contract.ErrCodeApplyFailed,
				"failed to list runs; see the iac-runner log", "")
			return
		}

		// Non-nil even when empty: an empty result marshals as
		// "runs":[] rather than "runs":null, so a client can iterate
		// unconditionally.
		summaries := make([]contract.RunSummary, 0, len(metas))
		for _, m := range metas {
			summaries = append(summaries, runSummary(m))
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(contract.RunListResponse{
			Runs:  summaries,
			Count: len(summaries),
			Limit: limit,
		})
	}
}

// runSummary projects a Meta onto the listing wire type.
//
// Field-by-field, like runDetail in get_run.go, and for the same
// reason: Meta carries time.Time plus the internal PlanFile, and
// spelling the projection out is what stops a future Meta field from
// reaching the API by accident. RunSummary deliberately has no
// output/pagination fields.
func runSummary(m runs.Meta) contract.RunSummary {
	return contract.RunSummary{
		RunID:      m.RunID,
		Repo:       m.Repo,
		Dir:        m.Dir,
		Kind:       m.Kind,
		Status:     m.Status,
		ExitCode:   m.ExitCode,
		StartedAt:  formatRunTime(&m.StartedAt),
		FinishedAt: formatRunTime(m.FinishedAt),
		ErrorCode:  m.ErrorCode,
	}
}

// isKnownRunStatus reports whether s is one of the five RunStatus
// values declared in contract/types.go (17-02). D-02's `interrupted`
// is one of them: a run orphaned by a container restart has to be
// queryable, or the operator cannot tell "tofu failed" from "the
// add-on restarted mid-apply".
func isKnownRunStatus(s string) bool {
	switch contract.RunStatus(s) {
	case contract.RunStatusQueued,
		contract.RunStatusRunning,
		contract.RunStatusSucceeded,
		contract.RunStatusFailed,
		contract.RunStatusInterrupted:
		return true
	}
	return false
}

// positiveInt parses s as a positive int, reporting whether it was
// usable. Unlike parsePositiveInt in get_run.go this reports the
// miss instead of substituting, because the caller's fallback
// (DefaultRunListLimit) still has to pass through the max clamp.
func positiveInt(s string) (int, bool) {
	if s == "" {
		return 0, false
	}
	n := 0
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c < '0' || c > '9' {
			return 0, false
		}
		n = n*10 + int(c-'0')
		if n > contract.MaxRunListLimit {
			// Already above the cap; the caller clamps, and this
			// guard keeps a 40-digit limit from overflowing.
			return contract.MaxRunListLimit + 1, true
		}
	}
	if n <= 0 {
		return 0, false
	}
	return n, true
}
