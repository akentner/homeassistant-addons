---
phase: "01"
slug: "bearer-api-listener"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-11-18"
---

# Phase 01 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary                                   | Description                                                                        | Data Crossing                      |
| ------------------------------------------ | ---------------------------------------------------------------------------------- | ---------------------------------- |
| network -> stdlib request parser -> gate   | Untrusted clients reach `http.server` and then the bearer gate on the API port     | raw HTTP bytes, credentials (high) |
| API handler -> consumer handler            | Request data passes to consumer code that must never see the token                 | headers, body (high)               |
| add-on option -> OptionToken               | Operator-supplied token value of unknown quality                                   | secret (high)                      |
| process -> /data hash file                 | Persistent secret material on disk                                                 | SHA-256 digest (medium)            |
| process -> stdout/stderr                   | Add-on logs are visible in the Home Assistant UI and in support dumps              | log text (high if leaked)          |
| ingress peer -> GUI port                   | Supervisor ingress traffic; the refactor must not weaken this gate (R-01)          | GUI requests (medium)              |
| consumer process                           | GUI and API run in one process and share shutdown handling                         | lifecycle signals (low)            |
| skeleton / admin-ui source -> consumers    | Generated copies ship inside four other add-ons                                    | code (medium)                      |
| blueprint docs, public repository          | Consumers configure exposure from R-16; DOCS and demo strings are published        | documentation (low)                |
| local worktree -> origin and registries    | Pushes, tags and images are outward-facing                                         | releases (high)                    |
| this worktree -> other worktrees           | Docker resources are shared on the host                                            | images, containers (low)           |

---

## Threat Register

| Threat ID | Category               | Component                                  | Severity | Disposition | Mitigation                                                                                                        | Status                                  |
| --------- | ---------------------- | ------------------------------------------ | -------- | ----------- | ----------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| T-01-01   | Spoofing               | `ApiHandler._dispatch`                     | high     | mitigate    | Gate before routing and body read; every `do_*` reaches `_dispatch`                                               | closed                                  |
| T-01-02   | Information disclosure | `OptionToken.verify`                       | medium   | mitigate    | SHA-256 digests compared with `hmac.compare_digest`                                                               | closed                                  |
| T-01-03   | Information disclosure | `Request.headers`, request log             | high     | mitigate    | `Authorization` hidden from handlers; request log silent                                                          | closed                                  |
| T-01-04   | Elevation of privilege | `make_api_server` bind                     | high     | mitigate    | Keyword-only `bind` without default, IPv4 literal checked before any socket                                       | closed                                  |
| T-01-05   | Tampering              | ingress gate R-01                          | high     | mitigate    | Characterisation matrix pinned before the refactor, green at HEAD                                                 | closed                                  |
| T-01-06   | Tampering              | `GuiHandler` refactor                      | high     | mitigate    | Existing gate suites unchanged and green; gate/static code untouched                                              | closed                                  |
| T-01-07   | Elevation of privilege | API public routes, static paths            | medium   | mitigate    | Router with public routes rejected; no static branch                                                              | closed                                  |
| T-01-08   | Spoofing               | identity headers on the API port           | medium   | mitigate    | Identity headers hidden via `_PublicHeaders`                                                                      | closed                                  |
| T-01-09   | Denial of service      | slow or large API clients                  | medium   | mitigate    | 30 s per read, 30 s per-request deadline, 32-connection cap, `MAX_BODY`, chunked rejected (WR-03)                 | closed                                  |
| T-01-10   | Information disclosure | cross-origin access                        | low      | mitigate    | No CORS headers; OPTIONS goes through the gate                                                                    | closed                                  |
| T-01-11   | Denial of service      | shutdown with two servers                  | low      | mitigate    | `serve(server, *more)` stops and closes every server                                                              | closed                                  |
| T-01-12   | Elevation of privilege | stdlib method and parser paths             | high     | mitigate    | `__getattr__`, `send_error` override, HTTP/0.9 rule                                                               | closed                                  |
| T-01-13   | Information disclosure | differences between failure responses      | medium   | mitigate    | One fixed 401 body and header set; byte-identity matrix                                                           | closed                                  |
| T-01-14   | Tampering              | keep-alive after an unread body            | medium   | mitigate    | `Connection: close` on every 401; body on GET/HEAD/OPTIONS closes; strict Content-Length (WR-04)                  | closed                                  |
| T-01-15   | Information disclosure | token in URL, cookie or other header       | medium   | mitigate    | Only one `Authorization` header is read                                                                           | closed                                  |
| T-01-16   | Denial of service      | verifier exceptions                        | medium   | mitigate    | `_verified` turns exceptions into a failed check                                                                  | closed                                  |
| T-01-17   | Elevation of privilege | listener without a token                   | high     | mitigate    | No verifier or empty token refuses before binding                                                                 | closed                                  |
| T-01-18   | Information disclosure | hash file                                  | medium   | mitigate    | `mkstemp` + fsync + `os.replace`, 0600 via `fchmod` on a valid regular file (WR-02)                               | closed                                  |
| T-01-19   | Information disclosure | plaintext delivery                         | high     | mitigate    | Plaintext offered exactly once under a lock; never printed                                                        | closed                                  |
| T-01-20   | Spoofing               | weak option tokens                         | medium   | mitigate    | `OPTION_TOKEN_MIN_LENGTH = 16`, printable ASCII only                                                              | closed                                  |
| T-01-21   | Information disclosure | logs, tracebacks, repr                     | high     | mitigate    | `handle_error` prints the class name only; redacting reprs; `from None`                                           | closed                                  |
| T-01-22   | Tampering              | rotate race, interrupted write             | medium   | mitigate    | Lock; digest swapped only after a successful write; directory fsync best effort (WR-01)                           | closed                                  |
| T-01-23   | Denial of service      | silent token regeneration                  | medium   | mitigate    | Only a missing file creates a token; anything else raises `ValueError` (WR-02)                                    | closed                                  |
| T-01-24   | Information disclosure | token over plain HTTP                      | medium   | transfer    | Transferred to the operator (D-03): R-16, bind and security notes in DOCS                                         | closed                                  |
| T-01-25   | Repudiation            | R-16 status                                | low      | mitigate    | R-16 status `review` in DOCS and the rules view, pinned by a test                                                 | closed                                  |
| T-01-26   | Information disclosure | DOCS content                               | low      | mitigate    | `test_docs_contains_no_secrets_or_real_hostnames`                                                                 | closed                                  |
| T-01-27   | Repudiation            | no request log on the API port             | low      | accept      | See Accepted Risks Log (AR-01)                                                                                    | closed                                  |
| T-01-28   | Tampering              | outward-facing release actions             | high     | mitigate    | No tags on any phase commit; feature branch only; CI publishes only from `main`                                   | closed                                  |
| T-01-29   | Tampering              | consumer copies                            | medium   | mitigate    | Copies only via `make sync-admin-ui`; strict drift check green                                                    | closed                                  |
| T-01-30   | Denial of service      | consumer contracts                         | medium   | mitigate    | `errors.py` unchanged; all consumer suites green after the WR re-syncs                                            | closed                                  |
| T-01-31   | Tampering              | image content                              | medium   | mitigate    | Five images rebuilt serially at `fdc0067`; `api.py` hash in four images equals HEAD; scaffold verify passed       | closed                                  |
| T-01-32   | Denial of service      | concurrent Docker use                      | low      | mitigate    | Builds one at a time with `docker ps` empty before each                                                           | closed                                  |
| T-01-33   | Tampering              | published consumer image tags              | medium   | mitigate    | Gap: coding-assistants `1.3.2-1` is already released on `main`; the branch bumps to the same version (see notes) | open — below high threshold (non-blocking) |
| T-01-SC   | Tampering              | package installs                           | high     | mitigate    | Skeleton imports stdlib only (test); no dependency or Dockerfile change                                           | closed                                  |

_Status: open · closed · open — below high threshold (non-blocking)_ _Severity: critical > high > medium > low — only open
threats at or above workflow.security_block_on count toward threats_open_ _Disposition: mitigate (implementation
required) · accept (documented risk) · transfer (third-party)_

### Open threat notes

- **T-01-33:** `origin/main` already carries `coding-assistants` `1.3.2-1` (its own CHANGELOG section, published by CI on
  push to `main`). Plan 06 bumped this branch to the same version, because the bump gate counted from the merge base and
  checked git tags only. `git merge-tree HEAD origin/main` conflicts in `coding-assistants/CHANGELOG.md`. A merge as-is
  would let CI rebuild `coding-assistants:1.3.2-1` with different content. Resolution needs an owner decision before
  merge: integrate `origin/main` and bump `coding-assistants` to `1.3.2-2` via `make update-version ... NO_TAG=yes`. The
  other consumers and admin-ui do not collide with the current `origin/main`.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale                                                                                                                                                             | Accepted By                | Date       |
| ------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | ---------- |
| AR-01   | T-01-27    | Request logging on the API port is silenced by design (D-09) so no header or token can leak; consumers may log action-level events without token values (DOCS, R-16) | plan-time decision (01-05) | 2026-11-18 |

_Accepted risks do not resurface in future audit runs._

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By                                                         |
| ---------- | ------------- | ------ | ---- | -------------------------------------------------------------- |
| 2026-11-18 | 34            | 33     | 1    | gsd-security-auditor + orchestrator (T-01-31 rebuild, T-01-27) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed (one non-blocking medium threat open: T-01-33)
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-18 (blocking gate); T-01-33 needs an owner decision before merge
