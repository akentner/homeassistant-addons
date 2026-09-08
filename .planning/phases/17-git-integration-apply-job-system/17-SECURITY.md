---
phase: "17"
slug: "git-integration-apply-job-system"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-09-08"
---

# Phase 17 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Retroactive STRIDE audit: no `<threat_model>` block existed in any `17-0N-PLAN.md`, so the register below was built from
the implementation files and then verified, rather than verified against a plan-time register. Audited at HEAD
`455920f`, which includes all 17 code-review fixes from `17-REVIEW-FIX.md`.

Findings marked **probe-verified** were established by running code against the real call path, not by reading it.

---

## Trust Boundaries

| Boundary                      | Description                                                                                                       | Data Crossing                                                         |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Ingress → `/v1` subrouter     | All five Phase 17 endpoints sit behind `auth.RequireBearer`; the Phase 16 surface is unchanged                    | Bearer token, `repo`/`dir`/`ref` request fields, run ids              |
| Runner → `git` + `ssh` child  | `sshEnv()` builds a minimal environment carrying only the per-repo deploy key and `known_hosts`                   | Deploy key path, host-key pin; no agent socket, no container env      |
| Runner → `tofu` child         | `tofuEnv()` allowlist; the child inherits the runner's UID and mount namespace (see R-01)                         | Backend credentials via allowlisted vars; full `/data` via filesystem |
| `tofu` output → HTTP response | Stateful cross-line redactor applied at read time, single audit emission point in `GetRun`                        | Redacted output lines, redaction counts                               |
| Runner → `/data` persistence  | Run metadata under `/data/runs/{run_id}/`, checkouts under `/data/repos/<name>/`, credentials under `/data/keys/` | Run metadata, raw (unredacted) `output.log`, deploy keys              |

---

## Threat Register

| Threat ID | Category                                                                                | Component                             | Severity | Disposition | Mitigation                                                                                                                                                                                                    | Status                                     |
| --------- | --------------------------------------------------------------------------------------- | ------------------------------------- | -------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| T-01      | Spoofing — unauthenticated access to the five new endpoints                             | `httpapi/router.go`                   | high     | mitigate    | All five mounted inside `r.Route("/v1", …)` with `r.Use(auth.RequireBearer(store))` — `router.go:71-84`                                                                                                       | closed                                     |
| T-02      | Spoofing — timing / brute-force on the bearer token                                     | `internal/auth`                       | medium   | mitigate    | `subtle.ConstantTimeCompare` on SHA-256 digests `token.go:256,261`; 256-bit `crypto/rand` token `token.go:132`                                                                                                | closed                                     |
| T-03      | Tampering — traversal via repo `name` into `/data/repos` (F2)                           | `internal/git`                        | high     | mitigate    | `repoNameRe` `repo.go:30` enforced in the sole constructor `manager.go:130`; all 6 `WorkTree` call sites gated by `m.repos[name]` membership                                                                  | closed                                     |
| T-04      | Tampering — traversal via request `dir` (F5)                                            | `internal/runs`, `internal/jobq`      | high     | mitigate    | `runs.ValidateDir` `dir.go:37-66` (NUL, leading `/`, `..` pre+post-`Clean`, absolute) at `queue.go:244`                                                                                                       | closed                                     |
| T-05      | Tampering — traversal via run `{id}`                                                    | `internal/runs`, handlers             | high     | mitigate    | `IsValidRunID` `ids.go:54-68` at `get_run.go:71` **and** again in the store `store.go:142-147`                                                                                                                | closed                                     |
| T-06      | Tampering — argv injection via operator `url` / `ref` / `branch`                        | `internal/git`                        | medium   | mitigate    | `repoURLRe` `repo.go:37` (rejects `ext::`, `file://`, leading `-`), `refRe` `repo.go:44`; `--` separators `manager.go:383,385,404,461`                                                                        | closed                                     |
| T-07      | Info disclosure — credentials in tofu output cross the API (SEC-03)                     | `internal/runs/redact.go`             | high     | mitigate    | Stateful cross-line `redactor` latch `redact.go:113-158`; read-time application `output.go:242`; single audit emission `redaction_audit.go:48-60` — **probe-verified**                                        | closed                                     |
| T-08      | Info disclosure — `SUPERVISOR_TOKEN` reaching the tofu child (F4 / CR-03)               | `internal/jobq/exec.go`               | high     | mitigate    | `tofuEnv()` allowlist `exec.go:62,68,90-106`, wired `exec.go:150` — **probe-verified**: none of four planted credentials emitted                                                                              | closed                                     |
| T-09      | Info disclosure — container env / SSH agent reaching git+ssh (F3)                       | `internal/git/manager.go`             | high     | mitigate    | `baseEnv()` `manager.go:284-292`, `envKeep` `manager.go:273`, `sshEnv()` `manager.go:253-264` — **probe-verified**; enforced at two layers (`IdentitiesOnly=yes` **and** no `SSH_AUTH_SOCK` in the child env) | closed                                     |
| T-09a     | Info disclosure — GIT-03 pinning never observed against a live remote (F3 residual)     | `internal/git/manager.go`             | medium   | mitigate    | Code-level control present (T-09); end-to-end proof assigned to Phase 19 per `17-03-SUMMARY.md:440,465`                                                                                                       | open — below high threshold (non-blocking) |
| T-10      | Info disclosure — git stderr / stack traces on the wire (GIT-04)                        | handlers, `internal/git/errors.go`    | medium   | mitigate    | `git.Error` stores no stderr `errors.go:20-25,47-50`; `writeGitError` logs-not-serves `write_error.go:129-137`                                                                                                | closed                                     |
| T-11      | Info disclosure — `statusForCode` over-disclosure (F8)                                  | `handlers/write_error.go`             | low      | mitigate    | `write_error.go:46-85` verified row-by-row: auth codes share 403, five lookup codes share 404, unknown → 502                                                                                                  | closed                                     |
| **R-01**  | **Elevation of privilege — tofu child shares the runner's UID and mount namespace**     | `Dockerfile`, `internal/jobq/exec.go` | **high** | **accept**  | **No privilege boundary. Accepted risk — see Accepted Risks Log R-01**                                                                                                                                        | closed (accepted)                          |
| T-13      | Tampering — `ValidateDir` is lexical; a repo-committed symlink escapes the working tree | `internal/runs/dir.go`                | low      | accept      | Lexical check only; no `EvalSymlinks` at `exec.go:124`. Requires repo commit access, which already grants provisioner code execution                                                                          | open — below high threshold (non-blocking) |
| T-14      | Info disclosure — SEC-03 misses the runner's own token shape and JWT-shaped secrets     | `internal/runs/redact.go`             | medium   | mitigate    | No rule for 43-char `base64url` or dot-separated JWTs — **probe-verified unredacted**. An HA long-lived access token is a JWT                                                                                 | open — below high threshold (non-blocking) |
| T-15      | Tampering — tofu plan-file operand appended with no `--` separator                      | `internal/jobq/exec.go`               | low      | mitigate    | `exec.go:207-210` appends `prior` bare. Not request-reachable; reachable by anything that can write `meta.json`                                                                                               | open — below high threshold (non-blocking) |
| T-16      | Repudiation — mutating requests are not attributable to a token                         | `handlers/plan.go`, `repos_pull.go`   | medium   | mitigate    | No `actor_token_fp` logged. Mechanism exists in the same codebase (`auth/middleware.go:23`). `GraceWindow = 24h` keeps two tokens valid                                                                       | open — below high threshold (non-blocking) |
| T-17      | DoS — request-level resource exhaustion                                                 | handlers, `cmd/runner/main.go`        | medium   | mitigate    | 64 KiB body cap `plan.go:42-52`; server timeouts `main.go:417-424`; `page`/`page_size`/`limit` clamps with overflow guards                                                                                    | closed                                     |
| T-18      | DoS — job / process exhaustion, wedged locks                                            | `internal/jobq`                       | medium   | mitigate    | Non-blocking semaphore `queue.go:279-283`; per-repo bound + slot handoff `queue.go:291-294,372,387`; release on every path incl. recovered panic; SIGTERM→SIGKILL `exec.go:350-351`                           | closed                                     |
| T-19      | DoS — hang on an unreachable remote                                                     | `internal/git`, handlers              | medium   | mitigate    | `ConnectTimeout=10` `manager.go:258`; 5-min sweep ceiling `main.go:261-279`; 2-min pull ceiling `repos_pull.go:127`                                                                                           | closed                                     |
| T-20      | DoS — unbounded `/data` growth (age-only retention)                                     | `internal/runs/retention.go`          | low      | accept      | Retention is age-only by design; OBS-02 mandates only age-based rotation. No size cap; write path forbids truncation (D-08)                                                                                   | open — below high threshold (non-blocking) |
| T-21      | Tampering — `git config --global --add safe.directory '*'` (F1)                         | `internal/git/manager.go`             | low      | accept      | Present `manager.go:162-172`, justified in-code `manager.go:148-161`, non-fatal `main.go:233-240`. See Accepted Risks Log R-02                                                                                | closed (accepted)                          |
| T-22      | Tampering — bodies accept trailing JSON, discarding the 2nd value                       | `handlers/plan.go`, `repos_pull.go`   | low      | mitigate    | `Decode` once, no stream-exhaustion assert — same class `DisallowUnknownFields` was added to prevent                                                                                                          | open — below high threshold (non-blocking) |
| T-23      | Info disclosure — a password in a repo `url` is logged verbatim                         | `handlers/repos_pull.go`              | low      | mitigate    | `repoURLRe` accepts `ssh://user:pass@host/…`; `url` is not in `sensitiveKeys` `scrubbing_handler.go:31-40`                                                                                                    | open — below high threshold (non-blocking) |
| T-24      | Tampering — apply silently reuses a stale plan artifact (CR-02)                         | `internal/jobq/exec.go`               | medium   | mitigate    | `Meta.HeadSHA` freshness gate `exec.go:288-293`; unknown→skip `exec.go:277-281`; consumption `exec.go:219-226,312-325`                                                                                        | closed                                     |

_Status: open · closed · open — below high threshold (non-blocking)_ _Severity: critical > high > medium > low — only
open threats at or above `workflow.security_block_on` count toward `threats_open`_ _Disposition: mitigate
(implementation required) · accept (documented risk) · transfer (third-party)_

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Accepted By | Date       |
| ------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ---------- |
| R-01    | R-01       | The `tofu` child process inherits the runner's UID (root — there is no `USER` directive in `iac-runner/Dockerfile`) and its mount namespace. Operator IaC, `local-exec` provisioners, and any third-party provider plugin `tofu init` downloads can therefore read every file under `/data`: all per-repo deploy keys (`/data/keys/<name>.key`), the state-backend credential files, and `/data/initial-iac-runner-token` — the plaintext bearer token. They can also write `/data/runs/*/meta.json`. Accepted because the add-on is single-tenant and the operator authors the IaC being executed: anyone who can submit an apply already controls code the runner executes. The residual exposure is third-party provider plugins, which the operator selects. Mitigating properly requires a privilege boundary (`SysProcAttr.Credential` UID drop, `chown` on `/data/keys`, unlinking the plaintext token after first read) — a change to the exec and boot paths that belongs in its own plan, not in this phase. | akentner    | 2026-09-08 |
| R-02    | T-21       | `NewManager` runs `git config --global --add safe.directory '*'`, relaxing git's ownership check process-wide for the container. Justified in-code as single-tenant and made non-fatal at boot. Only exploitable on a UID-mismatched `/data`, and the exploiting write (planting `core.fsmonitor` for the local `rev-parse`) already requires root or the tofu child — which is root per R-01, so this grants no capability R-01 does not already concede.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | akentner    | 2026-09-08 |

_Accepted risks do not resurface in future audit runs._

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By               |
| ---------- | ------------- | ------ | ---- | -------------------- |
| 2026-09-08 | 25            | 16     | 9    | gsd-security-auditor |

Closed counts the 15 mitigations the auditor verified plus R-01, closed by acceptance. The nine remaining open threats
are all below the `high` block threshold and are tracked, not waived.

---

## Follow-Up Candidates

Ranked by the auditor as worth their own plan rather than an ad-hoc fix:

1. **R-01** — a real privilege boundary for the tofu child (UID drop, `chown /data/keys`, unlink the plaintext token
   after first read). Accepted here, not solved.
2. **T-14** — extend the SEC-03 pattern set to the runner's own 43-char `base64url` token shape and to dot-separated
   JWTs. Directly relevant: a Home Assistant long-lived access token **is** a JWT, and a `terraform output` or an
   unmarked variable puts one on the wire.
3. **T-16** — log `actor_token_fp` on `/v1/plan`, `/v1/apply` and `/v1/repos/{name}/pull`. The mechanism already exists
   in this codebase (`auth/middleware.go:23` → `auth_rotate.go:38`); the 24 h `GraceWindow` means a destructive apply
   currently cannot be attributed to either valid token.

---

## Documentation Drift (not threats)

- `iac-runner/DOCS.md` describes the tofu-env containment without stating that the filesystem is fully shared. Corrected
  in this phase alongside R-01's acceptance.
- `internal/logging/scrubbing_handler.go:13` states "iac-runner does not hold a `SUPERVISOR_TOKEN` (AUTHR-01)". False —
  `config.yaml:12` sets `homeassistant_api: true`, so the Supervisor injects it. The token is never used or logged, and
  CR-03 makes the practical claim true, but the comment's premise is wrong.
- `handlers/write_error.go:98-102` claims absolute paths never reach the wire; `git/manager.go:219-222` and
  `git/errors.go:71,93,110` put `/data/keys/<name>.key` and `/data/repos/<name>/` into `Hint`/`Message`. Intentional and
  harmless, but the stated invariant is not the enforced one.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-08
