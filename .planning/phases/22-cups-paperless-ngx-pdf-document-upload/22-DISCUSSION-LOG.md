# Phase 22: cups-paperless-ngx-pdf-document-upload - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-28
**Phase:** 22-cups-paperless-ngx-pdf-document-upload
**Areas discussed:** Worker HTTP client, cups-pdf queue setup, Document title mapping, Exhausted-retry visibility

---

## Worker HTTP Client

| Option | Description | Selected |
|--------|-------------|----------|
| py3-requests | Add py3-requests (~199KiB, confirmed present in Alpine 3.24) to the Dockerfile — much simpler multipart code | ✓ |
| stdlib urllib only | Zero new deps, matches current "python3: stdlib json only" Dockerfile comment; hand-build multipart body | |
| You decide | Claude picks based on simplest-to-implement-correctly | |

**User's choice:** py3-requests (recommended)
**Notes:** Confirmed via live `docker run` + `apk info` against `ghcr.io/home-assistant/amd64-base:3.24` that
`py3-requests-2.33.1-r0` is available before presenting this option.

---

## cups-pdf Queue Setup

### Q1: Avahi/AirPrint advertisement

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, advertise it | Register through the existing printer-registration/Avahi code path — appears in iOS/macOS Print sheet | ✓ |
| No, LAN/admin-only | Registered in CUPS but excluded from Avahi/DNS-SD advertisement | |
| You decide | Claude picks based on existing code path simplicity | |

**User's choice:** Yes, advertise it

### Q2: Queue name

| Option | Description | Selected |
|--------|-------------|----------|
| "Paperless" | Directly communicates the destination | |
| "PDF" | Generic, matches cups-pdf tutorial conventions | |
| You decide | Fixed, non-configurable name | |

**User's choice:** Other (free text) — "Konfigurierbar, Default \"PDF-to-DMS\"" — user wants the name configurable
via option, defaulting to "PDF-to-DMS", overriding all three presented options.

### Q3: Output routing (per-user vs shared)

| Option | Description | Selected |
|--------|-------------|----------|
| Single shared AnonymousDirectory | Every job lands in one flat outbox/incoming/ dir regardless of client username | ✓ |
| Per-user subdirectories, worker scans recursively | Keeps cups-pdf's stock per-user default; worker walks subdirs | |

**User's choice:** Single shared AnonymousDirectory (recommended)

### Q4: Schema shape

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated block | New top-level `paperless_upload: {...}` block, separate from printers[] | ✓ |
| New entry in printers[] with driver: cups-pdf | Reuse existing list-of-objects schema | |

**User's choice:** Dedicated block (recommended)

### Q5: Disabled state

| Option | Description | Selected |
|--------|-------------|----------|
| Fully skipped | No queue registered at all when disabled — existing installs unaffected | ✓ |
| Queue registered but worker idle | Queue always exists/discoverable; only upload worker gated | |

**User's choice:** Fully skipped (recommended)

### Q6: UUID fixup extension

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, apply the same fixup | Extend fixup-printer-uuids.sh to cover every registered printer | ✓ |
| No, skip it for this queue | Leave fixup scoped to physical printers only | |

**User's choice:** Yes, apply the same fixup (recommended)

### Q7: Config defaults (timeout/retry count/delay)

| Option | Description | Selected |
|--------|-------------|----------|
| You decide | Claude picks conservative home-network defaults during planning | ✓ |
| I want to specify values now | User locks exact values | |

**User's choice:** You decide (recommended)

### Q8: Queue location/description metadata

| Option | Description | Selected |
|--------|-------------|----------|
| You decide | Claude picks a fixed description, not user-configurable | |
| Make location configurable too | Add `paperless_upload.location` alongside `queue_name` | ✓ |

**User's choice:** Make location configurable too

**Notes:** This area took multiple "more questions" rounds. When the user kept selecting "More questions" without a
specific new topic, the discussion re-offered an explicit topic picker twice (once mid-area, once at wrap-up) to
surface concrete signal rather than manufacturing arbitrary follow-ups — this surfaced Q8 and confirmed readiness
to move on.

---

## Document Title Mapping

### Q1: Title source

| Option | Description | Selected |
|--------|-------------|----------|
| Original print job title | cups-pdf's own job-title info, most useful in paperless-ngx's document list | ✓ |
| Timestamp-based name | Simple, always available, loses original context | |
| You decide | Claude verifies what cups-pdf actually exposes during planning | |

**User's choice:** Original print job title (recommended)

### Q2: Fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Timestamp-based name | e.g. "Scan_2026-09-28_14-32-05" — upload never fails due to missing title | ✓ |
| You decide | Claude picks fallback once title-capture mechanism is verified | |

**User's choice:** Timestamp-based name (recommended)

### Q3: Title handoff mechanism (print-time env → async worker)

| Option | Description | Selected |
|--------|-------------|----------|
| Sidecar metadata file | PostProcessing hook writes `<jobid>.json`; travels with PDF through outbox stages; deleted on success | ✓ |
| Encode title into PDF filename | Simpler but fragile under sanitization/collisions | |

**User's choice:** Sidecar metadata file (recommended)

### Q4: PostProcessing hook failure behavior

| Option | Description | Selected |
|--------|-------------|----------|
| PDF always lands in outbox | Hook is best-effort only, never blocks printing | ✓ |
| You decide | Claude picks safest failure mode | |

**User's choice:** PDF always lands in outbox (recommended)

### Q5: Title sanitization

| Option | Description | Selected |
|--------|-------------|----------|
| Trim + length-cap only | No filesystem-safety sanitization needed — title is a plain API string | ✓ |
| You decide | Claude picks exact rules during planning | |

**User's choice:** Trim + length-cap only (recommended)

**Notes:** Same "more questions" pattern as the previous area — an explicit topic picker surfaced "Title
sanitization rules" as the concrete remaining topic before the user confirmed readiness to move on.

---

## Exhausted-Retry Visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Silent | failed/ directory is the only record — matches add-on's minimalist, no-dashboard style | |
| One log line per failure | WARNING-level log line on move to failed/, same channel as print-history-poller.py | ✓ |
| You decide | Claude picks based on existing logging conventions | |

**User's choice:** One log line per failure (recommended)

---

## Claude's Discretion

- Default values for `paperless_upload.timeout` / `retry_count` / `retry_delay`.
- Exact retry/backoff algorithm (fixed interval vs. exponential).
- PPD/driver for the cups-pdf queue registration (its own auto-generated `CUPS-PDF.ppd` expected).
- Exact sidecar-file naming/format details beyond "a JSON file keyed by job id".
- Exact title-sanitization length cap, informed by paperless-ngx's real field constraints.

## Deferred Ideas

None — discussion stayed entirely within Phase 22's scope; every question raised during discussion was resolved
as an in-scope implementation decision.
