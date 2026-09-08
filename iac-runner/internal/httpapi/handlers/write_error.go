package handlers

// write_error is the single place every Phase 17 handler turns an
// error_code into an HTTP response. Centralizing it guarantees a
// uniform 4xx/5xx body shape across /v1/repos/{name}/pull, /v1/plan,
// /v1/apply and (17-08) /v1/runs, and keeps each handler focused on
// its success path.
//
// The mapping below is the wire contract. 17-08's read handlers call
// writeError / writeGitError instead of re-deriving a status, so there
// is exactly one place where "which code means which status" is
// decided — and exactly one place to change if a status ever has to
// move.

import (
	"encoding/json"
	"errors"
	"net/http"

	"iac-runner/internal/contract"
	"iac-runner/internal/git"
)

// statusForCode maps a contract error_code onto its HTTP status.
//
// The three status choices that are decisions rather than mechanics:
//
//   - 403 for git_ssh_handshake / git_unauthorized and 409 for
//     git_non_fast_forward are mandated verbatim by GIT-03 and ROADMAP
//     SC-3 ("non-fast-forward pulls and auth failures surface as typed
//     HTTP 409 / 403 errors"). They are NOT 502: the operator has to
//     fix a deploy key or a diverged branch, and a 5xx would read as
//     "the runner is broken, retry later".
//   - 503 for run_tofu_not_found and the two capacity codes: the
//     request is well-formed and the runner is simply unable to serve
//     it right now. /v1/plan and /v1/apply pair the capacity 503 with
//     Retry-After: 30 (D-06).
//   - 504 for apply_timeout / plan_timeout: the tofu process was
//     killed at the D-15/D-16 deadline. These codes only reach a
//     response body through a run's stored error_code (17-08); the
//     row exists so that path cannot fall through to the default.
//
// An unrecognized code returns 502. D-20 makes new codes additive, so
// an older build of this table WILL see codes it does not know; the
// default must be a safe failure, never a 200.
func statusForCode(code string) int {
	switch code {
	// git_* — GIT-04 taxonomy.
	case contract.ErrCodeGitSSHHandshake, contract.ErrCodeGitUnauthorized:
		return http.StatusForbidden
	case contract.ErrCodeGitNonFastForward:
		return http.StatusConflict
	case contract.ErrCodeGitRefNotFound, contract.ErrCodeGitCloneMissing:
		return http.StatusNotFound
	case contract.ErrCodeGitRefPullIncompatible:
		return http.StatusBadRequest
	case contract.ErrCodeGitDNSFailure, contract.ErrCodeGitCloneFailed:
		return http.StatusBadGateway

	// run_* — lookup and request-shape failures.
	case contract.ErrCodeRunUnknownRepo, contract.ErrCodeRunUnknownID, contract.ErrCodeRunNotFound:
		return http.StatusNotFound
	case contract.ErrCodeRunInvalidDir:
		return http.StatusBadRequest
	case contract.ErrCodeRunTofuNotFound, contract.ErrCodeRunCapacityExhausted:
		return http.StatusServiceUnavailable

	// apply_* / plan_* — job execution.
	case contract.ErrCodeApplyCapacityExhausted:
		return http.StatusServiceUnavailable
	case contract.ErrCodeApplyAlreadyRunning:
		return http.StatusConflict
	case contract.ErrCodeApplyTimeout, contract.ErrCodePlanTimeout:
		return http.StatusGatewayTimeout
	case contract.ErrCodeApplyFailed:
		return http.StatusInternalServerError

	// auth_* — the Phase 16 middleware value, listed so the taxonomy
	// is complete in one place even though auth.RequireBearer writes
	// its own 401 before any handler runs.
	case contract.ErrCodeUnauthorized:
		return http.StatusUnauthorized
	}
	return http.StatusBadGateway
}

// writeError writes the JSON error body with the supplied status and
// the contract error_code. The hint is the operator-facing
// Options-field fix from the D-19 taxonomy; an empty hint means "no
// actionable hint beyond the message".
//
// The hint is concatenated onto message rather than emitted as its own
// field because contract.ErrorResponse carries only error_code /
// message / request_id, and adding a field to that struct is 17-02's
// call, not a handler's. Operators read the JSON and find the hint as
// the last sentence of message.
//
// message must be caller-authored and single-line. Raw stderr, error
// strings from os/exec, stack traces and absolute paths never reach
// this function (GIT-04) — every call site either passes a literal or
// a *git.Error.Message, which internal/git guarantees is authored, not
// captured.
func writeError(w http.ResponseWriter, status int, code, message, hint string) {
	if hint != "" {
		message = message + " — " + hint
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
		ErrorCode: code,
		Message:   message,
	})
}

// writeGitError maps a typed *git.Error onto its HTTP response via
// statusForCode. Both internal/git and internal/jobq return this type
// for every operator-caused failure, so this one function covers the
// error paths of all five Phase 17 endpoints.
//
// errors.As (not a type assertion) is deliberate: jobq wraps some
// failures with %w, and a wrapped *git.Error must still map to its own
// status instead of falling through to the generic 500.
//
// A non-*git.Error is either a bug in this package or a failure mode
// nobody has classified yet. Its string is NOT put on the wire — it
// could carry a path, an errno or a wrapped exec error — so the
// response is a fixed 500 + apply_failed and the detail stays in the
// add-on log.
func writeGitError(w http.ResponseWriter, err error) {
	var ge *git.Error
	if errors.As(err, &ge) {
		writeError(w, statusForCode(ge.Code), ge.Code, ge.Message, ge.Hint)
		return
	}
	writeError(w, http.StatusInternalServerError, contract.ErrCodeApplyFailed,
		"the request failed for an unclassified reason; see the iac-runner log", "")
}
