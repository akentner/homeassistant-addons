package handlers

// redaction_audit closes the second half of SEC-03. internal/runs does
// the redacting and reports a count (runs.OutputPage.Redactions); it
// deliberately does no logging, because the request-scoped logger
// belongs to the HTTP layer. This file is where the count becomes the
// `redaction.audit` record ROADMAP SC-10 requires.
//
// CALL CONTRACT — the record must be emitted exactly once per response
// that carries output, and this is the only function that emits it:
//
//   - 17-08's GET /v1/runs/{id} calls auditRedactions once, right after
//     runs.Store.ReadOutput returns and before writing the response
//     body, passing the same OutputPage it is about to serve.
//   - GET /v1/runs (RUN-05) does NOT call it: a listing carries no
//     output lines, so there is nothing redacted to audit.
//   - Nothing else calls it. In particular the write endpoints in this
//     plan (/v1/repos/{name}/pull, /v1/plan, /v1/apply) never serve
//     output, so they never emit the record — which is why a single
//     emission point is enough to guarantee "exactly once".
//
// Passing the served page (rather than a count) is what makes that
// contract checkable: the audited numbers are by construction the ones
// the client received.

import (
	"context"
	"log/slog"

	"github.com/go-chi/chi/v5/middleware"

	"iac-runner/internal/runs"
)

// auditRedactions emits the SEC-03 `redaction.audit` slog record for
// one served output page.
//
// A page with zero redactions emits nothing. The record exists so an
// operator can see that credential-shaped output was withheld; a
// running apply is polled repeatedly, so a zero record per poll would
// bury the ones that matter and turn the audit trail into noise. The
// counted event is "redaction happened", not "output was read" — the
// latter is already the middleware's http.request record.
//
// The record carries counts and identifiers only, never page.Lines. A
// redacted line is still tofu output, and an audit record that logged
// it would reintroduce on disk exactly what the API just withheld.
func auditRedactions(ctx context.Context, runID string, page runs.OutputPage) {
	if page.Redactions <= 0 {
		return
	}
	slog.InfoContext(ctx, "redaction.audit",
		"request_id", middleware.GetReqID(ctx),
		"run_id", runID,
		"redactions", page.Redactions,
		"page", page.Page,
		"page_size", page.PageSize,
		"total_lines", page.TotalLines,
	)
}
