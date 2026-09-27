# Phase 22: paperless-ngx REST API Coverage Matrix

**Purpose:** Enumerate paperless-ngx's document-upload-relevant capability surface and record an explicit
INTEGRATE/OPT-OUT decision + reason for each, per CONTEXT.md's deliberately narrow v1 scope. Most rows are OPT-OUT —
that is an intentional, visible decision record, not a gap.

| Capability | paperless-ngx surface | Decision | Reason |
|---|---|---|---|
| Document upload | `POST /api/documents/post_document/`, multipart field `document` | **INTEGRATE** | Core v1 scope (ROADMAP Phase 22 goal, D-01) |
| Title field | multipart field `title` | **INTEGRATE** | D-10/D-11/D-12 — sourced from cups-pdf's own title-derived output filename via the PostProcess sidecar mechanism |
| Auth method | `Authorization: Token <token>` header | **INTEGRATE** (Token only) | CONTEXT.md verified this is the only mechanism this add-on uses; no session/OAuth alternative needed for a single-token personal deployment |
| Tags assignment | multipart field `tags` (list of numeric IDs) | **OPT-OUT** | CONTEXT.md v1 scope explicitly excludes — numeric IDs require a separate name→ID lookup step; relies on paperless-ngx's own automatic classification instead |
| Correspondent assignment | multipart field `correspondent` (numeric ID) | **OPT-OUT** | Same as tags — explicitly deferred per CONTEXT.md, automatic classification only |
| Document type assignment | multipart field `document_type` (numeric ID) | **OPT-OUT** | Same as tags — explicitly deferred per CONTEXT.md, automatic classification only |
| Custom fields | multipart field `custom_fields` | **OPT-OUT** | Same complexity class as tags/correspondent/document_type (per-install ID lookup); no locked decision requests it |
| Created/document-date override | multipart field `created` | **OPT-OUT** | paperless-ngx's own OCR-based date guessing is sufficient for v1; no locked decision requests overriding it |
| Archive serial number | multipart field `archive_serial_number` | **OPT-OUT** | No use case identified for a home single-printer add-on; not mentioned in any locked decision |
| Task-status polling | `GET /api/tasks/?task_id=<uuid>` | **OPT-OUT** | CONTEXT.md: "out of v1 scope unless planning finds it trivial" — not trivial (a second background polling loop + task-id bookkeeping surviving worker restarts); this add-on's own "sent" bookkeeping intentionally means "task accepted", not "confirmed stored" |
| Document search/retrieval | `GET /api/documents/`, `GET /api/documents/{id}/` | **OPT-OUT** | This add-on only ever uploads, never reads back — a one-directional pipeline per the phase's core architecture principle |
| Duplicate handling | server-side hash-based dedup (HTTP 400 on exact-duplicate re-upload) | **OPT-OUT** | paperless-ngx's own server-side duplicate detection is sufficient; this add-on's outbox model never resubmits a document once it has left `incoming/`, so no client-side dedup logic is needed |
| Consumption templates / workflow triggers | server-side paperless-ngx configuration | **OPT-OUT** | A server-side paperless-ngx feature; this add-on has no need to configure or be aware of it |

**Scope note:** Every OPT-OUT row above is consistent with CONTEXT.md's explicit "Do NOT build a generic multi-DMS
adapter abstraction for v1 — build directly against paperless-ngx's real API" instruction. Nothing here was omitted for
difficulty reasons; each row traces to an explicit CONTEXT.md scope boundary.
