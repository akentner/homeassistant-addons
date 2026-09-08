package handlers

// get_run is the GET /v1/runs/{id} handler (RUN-04 / OBS-03). It
// projects one runs.Meta plus a paginated, already-redacted output
// page into contract.RunDetail.
//
// SKELETON (RED phase) — the contract is published so the test file
// compiles; the behavior lands in GREEN.

import (
	"net/http"

	"iac-runner/internal/runs"
)

// runReader is the seam the handler depends on: the two runs.Store
// methods it actually calls. The exported GetRun keeps the concrete
// *runs.Store (that is what router.go has), so the unexported core is
// what tests drive.
type runReader interface {
	Load(runID string) (runs.Meta, error)
	ReadOutput(runID string, page, pageSize int) (runs.OutputPage, error)
}

// GetRun returns the handler mounted at GET /v1/runs/{id}.
func GetRun(store *runs.Store) http.HandlerFunc {
	return getRunHandler(store)
}

// getRunHandler is the testable core of GetRun.
func getRunHandler(_ runReader) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNotImplemented)
	}
}
