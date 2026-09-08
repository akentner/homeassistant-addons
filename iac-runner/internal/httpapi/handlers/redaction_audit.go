package handlers

// redaction_audit closes the second half of SEC-03. internal/runs does
// the redacting and reports a count; nothing in that package logs,
// because the request-scoped logger belongs to the HTTP layer.
//
// RED skeleton (17-06, inherited obligation): the contract below is
// published so the test suite compiles and fails on assertions rather
// than on a load error. The GREEN commit fills in the body.

import (
	"context"

	"iac-runner/internal/runs"
)

// auditRedactions emits the SEC-03 `redaction.audit` slog record for
// one served output page.
func auditRedactions(ctx context.Context, runID string, page runs.OutputPage) {
}
