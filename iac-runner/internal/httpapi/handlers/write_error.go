package handlers

// write_error is the single place every Phase 17 handler turns an
// error_code into an HTTP response. Centralizing it guarantees a
// uniform 4xx/5xx body shape across /v1/repos/{name}/pull, /v1/plan,
// /v1/apply and (17-08) /v1/runs, and keeps each handler focused on
// its success path.
//
// RED skeleton (17-06 Task 1): the contracts below are published so
// the test suite compiles and fails on assertions rather than on a
// load error. The GREEN commit fills in the bodies.

import (
	"net/http"
)

// writeError writes the JSON error body with the supplied status and
// contract error_code.
func writeError(w http.ResponseWriter, status int, code, message, hint string) {
	w.WriteHeader(http.StatusNotImplemented)
}

// statusForCode maps a contract error_code onto its HTTP status.
func statusForCode(code string) int {
	return http.StatusNotImplemented
}

// writeGitError maps a typed *git.Error onto its HTTP response.
func writeGitError(w http.ResponseWriter, err error) {
	w.WriteHeader(http.StatusNotImplemented)
}
