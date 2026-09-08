# Phase 17: Git Integration + Apply Job System - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents. Decisions are captured in
> CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-06 **Phase:** 17-git-integration-apply-job-system **Areas discussed:** Run metadata persistence;
Concurrent apply job cap; Output format + redaction timing; `ref` semantics in GIT-01; Startup clone recovery; Apply
timeout; Plan file lifecycle; Error code taxonomy; `dir` validation; Output line length **Deferred:** Ingress/WebUI with
live progress (v1.5 backlog — scope creep)

---

## Run metadata persistence

| Option            | Description                                                                                                      | Selected |
| ----------------- | ---------------------------------------------------------------------------------------------------------------- | -------- |
| JSON file per run | `/data/runs/{run_id}/meta.json` + `output.log`; flock + atomic rename; matches iac-runner file-on-volume posture | ✓        |
| Embedded BoltDB   | Single BoltDB with `runs` bucket; ACID + index filters; adds dep + corruption handling                           |          |
| SQLite            | Indexed queries; CGO concern on Alpine (terraform-bridge team avoided it for this reason)                        |          |

**User's choice:** JSON file per run (Recommended) **Notes:** Survives restart via boot transition of `running` →
`interrupted` (D-02). Mirrors existing `/data/keys/{repo}.key` pattern from Phase 16.

---

## Concurrent apply job cap

| Option               | Description                                                                                       | Selected |
| -------------------- | ------------------------------------------------------------------------------------------------- | -------- |
| Unbounded cross-repo | Per-repo mutex only; cross-repo parallel is unbounded                                             |          |
| Bounded via Options  | New `max_parallel_jobs` Option (default 4, range 1..32); global semaphore wrapping per-repo mutex | ✓        |
| You decide           | Hand-wave to planner                                                                              |          |

**User's choice:** Bounded via Options (Recommended) **Notes:** Operator-visible knob; bounded CPU/SSH contention on
homelab Tailscale subnet. Saturated semaphore returns 503 with `apply_capacity_exhausted` + `Retry-After: 30` (D-06) —
surfaces back-pressure rather than silently queuing.

---

## Output format + redaction timing

| Option                          | Description                                                                                           | Selected         |
| ------------------------------- | ----------------------------------------------------------------------------------------------------- | ---------------- |
| JSONL on disk + redact at read  | `{"ts","stream","line"}` per line; SEC-03 regex applied at GET /v1/runs/{id} read time; operator `cat | jq` works on raw | ✓   |
| Plaintext log + redact at write | `ts=… stream=… line=…` plaintext; redact in line-writer goroutine before disk                         |                  |
| Plaintext + raw sidecar         | Both redacted `output.log` and unredacted `raw_output.log` (chmod 600); two files per run             |                  |
| You decide                      | Hand-wave to planner                                                                                  |                  |

**User's choice:** JSONL on disk + redact at read (Recommended) **Notes:** Matches OBS-03's "file-on-disk is source of
truth, not in-memory buffer". Operator debug path stays open if the regex mis-fires on a novel secret pattern.

---

## `ref` semantics in GIT-01

| Option                  | Description                                                                                                                                       | Selected |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| Fetch + checkout to ref | After clone: `git fetch origin <ref> && git checkout FETCH_HEAD` (commit) or `git checkout <ref>` (branch/tag). Branch is ignored when ref is set | ✓        |
| Refspec fetch only      | `ref` is a refspec the runner appends to every fetch; never changes working tree                                                                  |          |
| Ref treated like branch | Ref is just an alternate branch name — `git pull` uses it instead of `branch`; can't pin a commit                                                 |          |
| You decide              | Hand-wave to planner                                                                                                                              |          |

**User's choice:** Fetch + checkout to ref (Recommended) **Notes:** Matches GIT-01 wording "optional commit/tag pin"
literally. `git pull --ff-only` (which only operates on the current branch) refuses when `ref` is set — surfaces
`git_ref_pull_incompatible` (D-12).

---

## Startup clone recovery

| Option                              | Description                                                                                         | Selected |
| ----------------------------------- | --------------------------------------------------------------------------------------------------- | -------- |
| Auto-retry with backoff             | 3 attempts at 1s/5s/30s; after that log + continue; subsequent apply fails with `git_clone_missing` | ✓        |
| Add /clone endpoint + no auto-retry | Single startup attempt; POST /v1/repos/{name}/clone to recover; adds 1 endpoint                     |          |
| Use /pull for everything            | /pull does `git clone` if /data/repos/ missing; semantically muddy                                  |          |
| You decide                          | Hand-wave to planner                                                                                |          |

**User's choice:** Auto-retry with backoff (Recommended) **Notes:** Per AGENTS.md Live Systems rule — startup never
degraded; clone is best-effort. `git_clone_missing` on subsequent /v1/plan makes the precondition explicit to the
operator.

---

## Apply timeout

| Option                                 | Description                                                                                                    | Selected |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------- | -------- |
| Options apply_timeout + auto-cancel    | New `apply_timeout_minutes` Option (default 60, range 5..1440); SIGTERM tofu at expiry; mark `failed: timeout` | ✓        |
| No timeout — tofu's own flag is enough | Pass `-timeout` flag to tofu; hangs on network blips still possible                                            |          |
| Timeout + cancel endpoint              | Both kill the process; cancel sends SIGTERM, timeout does the same                                             |          |
| You decide                             | Hand-wave to planner                                                                                           |          |

**User's choice:** Options apply_timeout + auto-cancel (Recommended) **Notes:** SIGTERM gives tofu a chance to release
its state-lock cleanly (R2/S3 lockfile release = single S3 DELETE; local-lock = unlink). 10s grace → SIGKILL.

---

## Plan file lifecycle

| Option                            | Description                                                                            | Selected |
| --------------------------------- | -------------------------------------------------------------------------------------- | -------- |
| Inline apply if no matching plan  | /v1/apply runs inline `tofu apply -auto-approve` when no matching plan file exists     | ✓        |
| Require matching prior plan       | /v1/apply requires matching prior /v1/plan; 409 if missing                             |          |
| Reuse most recent successful plan | Scan /data/runs/ for matching (repo, dir) and reuse if mtime newer than repo last-pull |          |
| You decide                        | Hand-wave to planner                                                                   |          |

**User's choice:** Inline apply if no matching plan (Recommended) **Notes:** RUN-03 wording explicitly supports this.
/v1/plan becomes optional — useful for preview, not required.

---

## Error code taxonomy

| Option                       | Description                                                                                                                                                                                                                                                                                        | Selected |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| Working draft + extend later | git__: ssh_handshake, dns_failure, ref_not_found, unauthorized, non_fast_forward, clone_failed, clone_missing, ref_pull_incompatible. run__: tofu_not_found, invalid_dir, unknown_repo, unknown_id, not_found, capacity_exhausted. apply__: already_running, timeout, failed. auth__: unauthorized | ✓        |
| Generic prefix-only codes    | Just `git`, `tofu`, `apply`, `auth` with free-text message; less machine-stable                                                                                                                                                                                                                    |          |
| You decide                   | Hand-wave to planner                                                                                                                                                                                                                                                                               |          |

**User's choice:** Working draft + extend later (Recommended) **Notes:** Codes are additive — old API consumers keep
working when new codes appear (D-20).

---

## `dir` validation

| Option                | Description                                                                                  | Selected |
| --------------------- | -------------------------------------------------------------------------------------------- | -------- |
| Strict at parse time  | Reject leading `/`, `..` segments, null bytes; 400 with `run_invalid_dir`; empty = repo root | ✓        |
| Validate at exec time | Pass through to `tofu init`, which fails with its own error                                  |          |
| You decide            | Hand-wave to planner                                                                         |          |

**User's choice:** Strict at parse time (Recommended) **Notes:** Path traversal is a security boundary; rejecting at
parse time prevents the operator's `/v1/plan` from being a confused-deputy vector.

---

## Output line length

| Option                                | Description                                                                  | Selected |
| ------------------------------------- | ---------------------------------------------------------------------------- | -------- |
| No truncation, paginate by line count | Lines written verbatim; OBS-03 pagination handles large outputs at API layer | ✓        |
| Truncate per-line to 8 KB             | Predictable disk usage; debug info may be lost                               |          |
| You decide                            | Hand-wave to planner                                                         |          |

**User's choice:** No truncation, paginate by line count (Recommended) **Notes:** Disk-usage bound by
`runs_retention_hours` rotation (D-25). Single pathological run can still grow large.

---

## Deferred Ideas

- **Ingress / WebUI with live progress streaming** (v1.5 backlog) — user explicitly added during gray-area selection.
  Scope creep: no Ingress integration exists in Phase 16 scaffold; PROJECT.md §Out of Scope already defers "Multi-Repo
  UI" to v1.5. Phase 18 MQTT Discovery is the v1.4 HA-side UI for status.
- **POST /v1/runs/{id}/cancel** — could be added later. `apply_timeout_minutes` SIGTERM covers the runaway-apply use
  case for v1.4.
- **Cross-restart mutex persistence** — RUN-06 spec locks in-process mutex; restart-during-apply marks running →
  interrupted on next boot.
- **Approval-gate before `tofu apply`** — PROJECT.md §Out of Scope. Manual REST trigger IS the approval gate.
