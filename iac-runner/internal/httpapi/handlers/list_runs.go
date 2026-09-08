package handlers

// list_runs is the GET /v1/runs handler (RUN-05).
//
// SKELETON (RED phase) — the contract is published so the test file
// compiles; the behavior lands in GREEN.

import (
	"net/http"

	"iac-runner/internal/runs"
)

// runLister is the seam the handler depends on: the single runs.Store
// method it calls. The exported ListRuns keeps the concrete
// *runs.Store for router.go.
type runLister interface {
	List(f runs.ListFilter) ([]runs.Meta, error)
}

// ListRuns returns the handler mounted at GET /v1/runs.
func ListRuns(store *runs.Store) http.HandlerFunc {
	return listRunsHandler(store)
}

// listRunsHandler is the testable core of ListRuns.
func listRunsHandler(_ runLister) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNotImplemented)
	}
}
