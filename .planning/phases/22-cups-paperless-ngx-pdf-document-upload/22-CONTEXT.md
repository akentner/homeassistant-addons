# Phase 22: cups-paperless-ngx-pdf-document-upload - Context

**Gathered:** 2026-09-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a second, PDF-only virtual printer queue (via `cups-pdf`) to the existing `cups/` add-on, separate from and
non-disruptive to the physical Brother-MFC-7460DN queue. Output from this queue lands in a local outbox directory
under `/data`, and a decoupled background worker process (co-located with `generate_config.py` /
`print-history-poller.py`, started from `run.sh` the same way) uploads each PDF to a paperless-ngx instance's REST
API. Core principle: "CUPS erzeugt das Dokument; ein separater Worker besitzt die Verantwortung für die Zustellung"
— the physical printer and cupsd itself must stay fully unaffected if paperless-ngx is down, misconfigured, or
disabled.

**Locked before this discussion (see ROADMAP.md Phase 22 for full text — not re-litigated here):**
- Target DMS is paperless-ngx specifically; no generic multi-DMS adapter for v1.
- paperless-ngx REST facts (verified live against actual docs): `POST /api/documents/post_document/`, multipart
  field `document` (not `file`), `Authorization: Token <token>` (not `Bearer`), response is HTTP 200 with an
  async consumption-task UUID — not a "stored successfully" confirmation.
- v1 sends only `document` + `title` — no tags/correspondent/document_type mapping.
- Outbox/worker design: incoming/processing/sent/failed directory pattern with retry/backoff; a failed document is
  never deleted.
- Config surface must cover: enable/disable toggle defaulting OFF, base URL, API token (`password?`-style schema),
  upload timeout, retry count/delay.

</domain>

<decisions>
## Implementation Decisions

### Worker HTTP Client
- **D-01:** The upload worker uses **`py3-requests`** (confirmed available as an Alpine 3.24 apk package, ~199 KiB)
  for the multipart POST + `Authorization: Token <token>` request, added to the Dockerfile's `apk add` list.
  Rejected: hand-rolled stdlib `urllib` multipart encoding — `requests`' `files=` param and built-in
  timeout/retry ergonomics carry much lower risk of a hand-rolled multipart bug than reimplementing
  `multipart/form-data` encoding by hand. — **Reversibility:** reversible — a small, well-isolated dependency;
  swapping back to stdlib later touches only the worker's HTTP call.

### cups-pdf Queue Setup
- **D-02:** The queue **is Avahi/AirPrint-advertised** like the physical printer — registered through the same
  printer-registration/Avahi code path in `generate_config.py`, so it appears in iOS/macOS Print sheets without
  extra client setup.
- **D-03:** The queue's name is **configurable** (not fixed), via a new `paperless_upload.queue_name` option,
  defaulting to `"PDF-to-DMS"`.
- **D-04:** The queue's **location/description metadata is also configurable**, via `paperless_upload.location`,
  mirroring `printers[].location` for the physical printer (no fixed/hardcoded description).
- **D-05:** cups-pdf output routing uses a **single shared `AnonymousDirectory`** (or equivalent `Out` directive)
  pointed at the outbox's `incoming/` stage — every job lands flat in one directory regardless of the requesting
  client's username, since this headless container has no meaningful per-user home-directory concept. The worker
  only ever scans one directory, never walks per-user subdirectories.
- **D-06:** The PDF queue's configuration lives in a **dedicated top-level `paperless_upload` block** in
  `config.yaml` — `{enabled, queue_name, location, url, token, timeout, retry_count, retry_delay}` — separate from
  the existing `printers[]` list. `printers[]` continues to model URI-addressable devices only (`uri` would be
  meaningless for a `cups-pdf` backend). — **Reversibility:** costly — moving this into `printers[]` later would
  need an options-schema migration for existing installs; keeping it separate from day one avoids that.
- **D-07:** When `paperless_upload.enabled` is **false (the default)**, the cups-pdf queue is **fully skipped** —
  `generate_config.py` never registers it, no `cups-pdf.conf` is generated, nothing appears via Avahi. Existing
  installations without paperless-ngx configured see zero change. — **Reversibility:** reversible.
- **D-08:** The existing stable-UUID fixup (`fixup-printer-uuids.sh` — stop cupsd, patch `printers.conf`, restart,
  to prevent iOS ghost-duplicate entries across container restarts) is **extended to cover every registered
  printer**, physical or `cups-pdf` — both are equally susceptible to the same restart-induced UUID churn.
- **D-09:** Default values for `timeout` / `retry_count` / `retry_delay` are **Claude's discretion** during
  planning — conservative home-network defaults, documented in DOCS.md, overridable via Options.

### Document Title Mapping
- **D-10:** `title` is populated from the **original CUPS print job's title** (the source document's
  filename/window title as CUPS received it) wherever cups-pdf can capture it — more useful in paperless-ngx's
  document list than a generic name.
- **D-11:** **Fallback:** if the original title is unavailable or empty, use a **timestamp-based name** (e.g.
  `"Scan_2026-09-28_14-32-05"`) — upload must never fail or be skipped just because a title couldn't be recovered.
- **D-12:** **Title handoff mechanism:** cups-pdf's job-title info is only available in an environment variable
  inside its `PostProcessing` hook, at print time — the worker, however, runs later and asynchronously with no
  access to that environment. The hook writes a **sidecar metadata file** (e.g. `<jobid>.json` with
  `{"title": "..."}`) next to the PDF in the outbox at print time. The sidecar travels alongside its PDF through
  every outbox stage (incoming → processing → sent/failed) and is read by the worker (falling back to the
  timestamp per D-11 if missing/malformed); it is deleted once the upload succeeds. Rejected: encoding the title
  into the PDF filename directly — fragile under sanitization/collisions.
- **D-13:** If the `PostProcessing` hook itself fails (e.g. cannot write the sidecar), the **print job still
  succeeds and the PDF still lands in the outbox** (title falls back to timestamp per D-11) — the hook is
  best-effort only and must never block or fail printing, matching the phase's core "cupsd stays unaffected"
  principle.
- **D-14:** Title sanitization before sending to paperless-ngx is **trim + length-cap only** (e.g. to
  paperless-ngx's own title field length limit) — no filesystem-safety sanitization is needed since `title` is a
  plain API string, never used as a filename; paperless-ngx's API accepts arbitrary UTF-8.

### Exhausted-Retry Visibility
- **D-15:** Once retry/backoff is exhausted and a document moves to `failed/`, the worker emits **one
  WARNING-level log line per failure** (visible via `ha apps logs` / `docker logs`, same channel as
  `print-history-poller.py`'s own WARNING lines) — no new dashboard or notification infrastructure, but at least
  discoverable without knowing in advance to check `/data`.

### Claude's Discretion
- Default values for `paperless_upload.timeout` / `retry_count` / `retry_delay` (D-09).
- Exact retry/backoff algorithm (fixed interval vs. exponential) for failed uploads.
- PPD/driver registered for the `cups-pdf` queue (its own auto-generated `CUPS-PDF.ppd` is the expected default;
  no alternative was raised).
- Exact sidecar filename/format details beyond "a JSON file keyed by job id" (D-12).
- Exact sanitization length cap and rules (D-14) — informed by paperless-ngx's actual field constraints, to be
  verified during planning/implementation.

### Folded Todos
None — `cross_reference_todos` found no pending todos matching Phase 22's scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase boundary + locked decisions
- `.planning/ROADMAP.md` §"Phase 22: cups: paperless-ngx PDF document upload" — the full locked design (paperless-ngx
  REST facts, outbox/worker architecture, v1 field scope, config surface shape) that this CONTEXT.md's decisions
  build on top of. Read this FIRST — it is the primary source of phase scope.

### Current add-on state (read before planning — modified extensively 2026-09-27)
- `cups/config.yaml` — current options/schema (`printers[]`, `avahi_reflector`, `admin_username`/`admin_password`
  as the existing `password?`-schema precedent).
- `cups/run.sh` — startup sequence: `generate_config.py` runs first, then dbus/avahi, admin provisioning, cupsd
  start, printer registration (`register-printers.sh`), UUID fixup (`fixup-printer-uuids.sh`), log-level
  (`cupsctl`), log-tailing, and the existing background worker (`print-history-poller.py`) launched the same way
  the new paperless-ngx worker must be launched (`python3 /worker.py &`, tracked PID, killed in the shutdown trap).
- `cups/generate_config.py` (1220 lines) — the config-generation pattern (reads `/data/options.json`, renders
  `avahi-daemon.conf`, `cupsd.conf`, `register-printers.sh`, `provision-admin.sh`); the `paperless_upload` block's
  rendering (cups-pdf.conf generation, PostProcessing hook script, queue registration) must follow this same
  generate-then-execute pattern.
- `cups/print-history-poller.py` (180 lines) — the **direct structural precedent** for the new upload worker:
  standalone Python script, started as a backgrounded process from `run.sh`, polling loop with a documented
  interval, state persisted to `/data` (atomic write via temp-file + rename), never crashes the loop (broad
  `except Exception` around the poll cycle, logs and continues), forward-only semantics, documented limitations
  in its own module docstring.
- `cups/Dockerfile` — current `apk add` list (`cups cups-filters avahi avahi-tools dbus python3 brlaser`) — confirms
  `python3` is currently stdlib-only; `cups-pdf` (3.0.2-r0) and `py3-requests` (2.33.1-r0) are both confirmed
  present in the `ghcr.io/home-assistant/amd64-base:3.24` apk repos and must be added.
- `cups/DOCS.md` — existing operator documentation structure/conventions to extend for `paperless_upload`.

### Prior-phase precedent (same add-on, immediately preceding phase)
- `.planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-CONTEXT.md` — D-09 (generated-config-from-
  template pattern), the printer-list-of-objects schema precedent, and the UUID-fixup rationale this phase's D-08
  extends.

### Secrets/schema precedent (cross-add-on)
- `.planning/phases/20-litellm-addon/20-CONTEXT.md` D-11/D-12/D-25 — `password?` schema + persistent-secret-file
  pattern precedent for handling the `paperless_upload.token` option, and the general "generate_config.py-style
  config synthesis" precedent this add-on already follows independently.

No other external specs/ADRs apply.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `cups/print-history-poller.py` — copy its shape wholesale for the new worker: standalone script, `while True`
  loop with `time.sleep(INTERVAL)`, atomic state persistence via temp-file + `.replace()`, broad exception guard
  around each cycle so the loop itself never dies, `print(..., flush=True)` for log visibility (background
  processes' stdout is not redirected in `run.sh`, so this reaches `docker logs`/`ha apps logs` automatically).
- `cups/generate_config.py`'s existing `build_cupsd_conf` / printer-registration rendering functions — the
  `paperless_upload` block needs an analogous `build_cups_pdf_conf()` + a generated `PostProcessing` hook script,
  following the same "render a file from `bashio::config`/options.json, execute it later" split already
  established for `register-printers.sh` and `provision-admin.sh`.
- `cups/run.sh`'s existing background-process pattern (step 11: `python3 /print-history-poller.py &`, PID tracked,
  killed in the `trap ... TERM INT` at the bottom) — the new worker is launched and torn down identically.

### Established Patterns
- Generated-file-then-executed split (`generate_config.py` writes `/tmp/*.sh`, `run.sh` executes them) — applies to
  the new `cups-pdf.conf` + `PostProcessing` hook script.
- Outbox/state-file conventions from `print-history-poller.py`: state in `/data`, atomic temp-file+rename writes,
  forward-only (no retroactive backfill on first run), non-fatal on transient failures.
- 3-file version sync + 4-file add-on pattern apply unchanged — this phase only adds files/options within the
  existing `cups/` add-on, no new add-on directory.

### Integration Points
- The new worker and the `paperless_upload` PostProcessing hook are the only new integration points; cupsd itself,
  the physical printer path, and the print-history poller are untouched.

</code_context>

<specifics>
## Specific Ideas

- Default queue name: `"PDF-to-DMS"` (user's own naming choice, not "Paperless" or "PDF" as originally proposed).
- The sidecar-metadata-file mechanism (D-12) is the linchpin technical decision of this phase — without it, the
  title (D-10) cannot survive from cupsd's synchronous print-time context into the worker's asynchronous later
  pickup. Downstream planning must treat this as a first-class design element, not an afterthought.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope; all raised questions were resolved as in-scope decisions above.

### Reviewed Todos (not folded)
None — discussion stayed within phase scope.

</deferred>

---

*Phase: 22-cups-paperless-ngx-pdf-document-upload*
*Context gathered: 2026-09-28*
