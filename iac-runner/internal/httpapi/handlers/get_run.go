package handlers

// get_run is the GET /v1/runs/{id} handler (RUN-04 / OBS-03). It
// projects one runs.Meta plus a paginated output page into
// contract.RunDetail and does nothing else: the handler is read-only
// and writes nothing to disk.
//
// Redaction is NOT done here. runs.Store.ReadOutput already applies
// runs.Redact at read time (17-04 / SEC-03 / D-08), so the lines this
// handler serves are redacted by construction. What this handler owns
// is the other half of SEC-03: it calls auditRedactions once with the
// page it is about to serve, which is the single emission point of the
// `redaction.audit` record ROADMAP SC-10 requires (call contract in
// redaction_audit.go).
//
// Status contract of this endpoint (D-19, all via statusForCode):
//
//	200 http.StatusOK       — the run exists; body contract.RunDetail
//	404 (run_unknown_id)    — the {id} path parameter is not a run id
//	404 (run_not_found)     — well-formed id, no such run (or corrupt meta.json)
//	500 (apply_failed)      — a real filesystem failure; detail stays in the log

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"

	"iac-runner/internal/contract"
	"iac-runner/internal/runs"
)

// runReader is the seam the handler depends on: the two runs.Store
// methods it actually calls. The exported GetRun keeps the concrete
// *runs.Store (that is what router.go has), so the unexported core is
// what tests drive — no run directory, no meta.json, no output.log.
type runReader interface {
	Load(runID string) (runs.Meta, error)
	ReadOutput(runID string, page, pageSize int) (runs.OutputPage, error)
}

// GetRun returns the handler mounted at GET /v1/runs/{id} by
// router.go. store is the runs.Store constructed in main.go at
// startup (17-07).
func GetRun(store *runs.Store) http.HandlerFunc {
	return getRunHandler(store)
}

// getRunHandler is the testable core of GetRun.
func getRunHandler(rd runReader) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := chi.URLParam(r, "id")

		// The IsValidRunID guard runs BEFORE any filesystem access:
		// a hostile value like "../etc" must never reach the
		// filepath.Join inside store.Load.
		if !runs.IsValidRunID(id) {
			writeError(w, statusForCode(contract.ErrCodeRunUnknownID), contract.ErrCodeRunUnknownID,
				"unknown run id",
				"run ids are 16 characters from the base32 alphabet (A-Z, 2-7)")
			return
		}

		meta, err := rd.Load(id)
		if err != nil {
			if errors.Is(err, runs.ErrRunNotFound) {
				// Load collapses missing, invalid and corrupt into
				// ErrRunNotFound on purpose (17-04): from the API's
				// side a corrupt meta.json is operationally the same
				// as a missing run, and the on-disk layout stays off
				// the wire.
				writeError(w, statusForCode(contract.ErrCodeRunNotFound), contract.ErrCodeRunNotFound,
					"no run with id "+id, "")
				return
			}
			// Anything else is a real filesystem problem. Its string
			// can carry a path or an errno, so it is logged and never
			// serialized (the GIT-04 rule, applied to the read side).
			slog.ErrorContext(r.Context(), "iac_runner.run.load_failed", "run_id", id, "err", err.Error())
			writeError(w, http.StatusInternalServerError, contract.ErrCodeApplyFailed,
				"failed to load the run; see the iac-runner log", "")
			return
		}

		// ?page= (default 1) and ?page_size= (default
		// contract.DefaultOutputPageSize, capped at
		// MaxOutputPageSize). The cap is applied HERE, before the
		// store is asked, so an oversized request cannot make the
		// runner read an unbounded window even though ReadOutput
		// clamps again on its own.
		q := r.URL.Query()
		page := parsePositiveInt(q.Get("page"), 1)
		pageSize := parsePositiveInt(q.Get("page_size"), contract.DefaultOutputPageSize)
		if pageSize > contract.MaxOutputPageSize {
			pageSize = contract.MaxOutputPageSize
		}

		outputPage, err := rd.ReadOutput(id, page, pageSize)
		if err != nil {
			slog.ErrorContext(r.Context(), "iac_runner.run.read_output_failed", "run_id", id, "err", err.Error())
			writeError(w, http.StatusInternalServerError, contract.ErrCodeApplyFailed,
				"failed to read the run output; see the iac-runner log", "")
			return
		}

		// SEC-03 / SC-10 / D-08 — exactly one call, after ReadOutput
		// and before the response body, passing the page that is
		// about to be served. auditRedactions is silent on a
		// zero-redaction page (a running apply is polled repeatedly).
		auditRedactions(r.Context(), id, outputPage)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(runDetail(meta, outputPage))
	}
}

// runDetail projects a Meta plus the served page onto the wire type.
//
// The projection is field-by-field rather than a shared struct: Meta
// carries time.Time / *time.Time and an internal PlanFile that has no
// place on the wire, while contract.RunDetail carries RFC3339 strings
// and the pagination triple. Spelling every field out is also what
// keeps a future Meta field from leaking into the API by accident.
func runDetail(meta runs.Meta, page runs.OutputPage) contract.RunDetail {
	lines := page.Lines
	if lines == nil {
		// A queued run has produced nothing yet. An empty slice
		// marshals as [] where a nil marshals as null, and a client
		// walking pages should not need a null case.
		lines = []string{}
	}
	return contract.RunDetail{
		RunID:       meta.RunID,
		Repo:        meta.Repo,
		Dir:         meta.Dir,
		Kind:        meta.Kind,
		Status:      meta.Status,
		ExitCode:    meta.ExitCode,
		StartedAt:   formatRunTime(&meta.StartedAt),
		FinishedAt:  formatRunTime(meta.FinishedAt),
		ErrorCode:   meta.ErrorCode,
		OutputLines: lines,
		Page:        page.Page,
		PageSize:    page.PageSize,
		TotalLines:  page.TotalLines,
	}
}

// formatRunTime renders a run timestamp in the wire format. A nil or
// zero instant becomes the empty string, which the contract's
// omitempty tag drops — a run that has not finished reports no
// finished_at rather than the Unix epoch.
func formatRunTime(t *time.Time) string {
	if t == nil || t.IsZero() {
		return ""
	}
	return t.UTC().Format(time.RFC3339)
}

// parsePositiveInt returns the int parsed from s, or fallback when s
// is empty or not a positive integer.
//
// A bad value falls back rather than 400ing: page and page_size are
// navigation hints, and a typo in a hand-typed curl should show the
// operator the first page, not an error they then have to decode.
func parsePositiveInt(s string, fallback int) int {
	if s == "" {
		return fallback
	}
	n, err := strconv.Atoi(s)
	if err != nil || n <= 0 {
		return fallback
	}
	return n
}
