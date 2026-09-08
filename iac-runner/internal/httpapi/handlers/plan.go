package handlers

// plan is the POST /v1/plan + POST /v1/apply handler pair (RUN-02 /
// RUN-03). Both submit a job to jobq.Queue and answer 202 + a run id
// immediately; the tofu invocation lives in the worker goroutine
// (17-05).
//
// RED skeleton (17-06 Tasks 2+3): the contracts below are published so
// the test suite compiles and fails on assertions rather than on a
// load error. The GREEN commit fills in the bodies.

import (
	"net/http"

	"iac-runner/internal/contract"
	"iac-runner/internal/jobq"
)

// planApplyRequest is the shared body shape for /v1/plan and /v1/apply.
type planApplyRequest struct {
	Repo string `json:"repo"`
	Dir  string `json:"dir"`
}

// submitter is the seam the two handlers depend on.
type submitter interface {
	Submit(req jobq.Request) (string, error)
}

// Plan returns the handler mounted at POST /v1/plan by router.go.
func Plan(q *jobq.Queue) http.HandlerFunc {
	return submitHandler(q, contract.RunKindPlan)
}

// Apply returns the handler mounted at POST /v1/apply by router.go.
func Apply(q *jobq.Queue) http.HandlerFunc {
	return submitHandler(q, contract.RunKindApply)
}

// submitHandler is the testable core shared by Plan and Apply.
func submitHandler(q submitter, kind contract.RunKind) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotImplemented)
	}
}
