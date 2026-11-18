---
phase: "01"
slug: "git-serving-core"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
block_on: high
created: "2026-11-18"
---

# Phase 01 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| git client / other add-on -> lighttpd :8080 | Untrusted HTTP requests on the hassio network | Capability hash in the URL (secret) |
| lighttpd CGI -> filesystem | `git http-backend` runs as `lighttpd`, resolves symlinks under `/srv/git/access` | Bare repositories, access links |
| sync -> upstream (GitHub or test fixture) | PAT leaves the process only as an HTTP header of the git child | PAT (secret), repository data |
| upstream -> sync | git stderr and responses are untrusted text that reaches logs and status.json | Error text |
| add-on options -> Python | Supervisor-validated values become paths and refspecs | Owner, repo, branch, public_url |
| container env -> services | Test override and Supervisor token live in the container environment | Override URL, token |
| /data/access.json -> reconcile | Hand-edited, restored or corrupt file treated as untrusted structure | User labels, hashes |
| operator shell -> CLI | Trusted root operator; output may contain the full URL by design | Store URLs |
| add-on log -> operator / HA UI | Visible to anyone with add-on log access | Masked URLs, labels |
| CI workflow -> GitHub Actions runner | Workflow changes run with repository permissions | Read-only checkout |
| verify script -> Docker host | Local containers only, sentinel PAT by design | Sentinel values |
| repository docs -> public readers | Public repository | Placeholders only |
| feature branch -> `main` / published images | Bump becomes a release only after the squash merge | Version, tags |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-01-01 | Information disclosure | `app/gitops.py` auth env | high | mitigate | Token only in `GIT_CONFIG_VALUE_0` of a fresh env per git call; redactor for raw/header/base64 forms | closed |
| T-01-02 | Information disclosure | lighttpd CGI stderr | high | mitigate | `server.breakagelog = "/dev/null"`, no access log, no debug | closed |
| T-01-03 | Tampering | option values -> paths/refspecs | high | mitigate | Supervisor `match()` plus `fullmatch` validators (WR-02 fix), `.`/`..`/`.git` rejected, check-ref-format | closed |
| T-01-04 | Information disclosure | lighttpd environment | high | mitigate | lighttpd and access-watch run under plain `#!/bin/sh`; `/proc/*/environ` scan in verify | closed |
| T-01-05 | Tampering | push through the proxy | high | mitigate | Allow-list `info/refs` + `git-upload-pack`; `http.receivepack false`; pushurl disabled | closed |
| T-01-06 | Information disclosure | dumb-HTTP file reads | medium | mitigate | `http.getanyfile false`, empty docroot, 404 outside `/repo/` | closed |
| T-01-07 | Spoofing | test upstream override | high | mitigate | Env-only override, scheme/host/userinfo/query checks, WARNING at start | closed |
| T-01-08 | Elevation of privilege | `safe.directory` scope | low | mitigate | Limited to `/srv/git/repos/*`, `--replace-all` | closed |
| T-01-09 | Information disclosure | `/data` readable by CGI user | medium | mitigate | umask 077, `/data` 0700, files 0600, access dirs 0711 | closed |
| T-01-10 | Denial of service | empty repo before first fetch | low | mitigate | Temp dir renamed only after a good first fetch | closed |
| T-01-11 | Information disclosure | git stderr -> logs/status.json | high | mitigate | `sanitize`, `_scrub`, `SafeFormatter` + redactor filter | closed |
| T-01-12 | Information disclosure | auto-gc inheriting auth env | high | mitigate | `maintenance.auto=false`, `gc.auto=0` on the fetch; maintenance uses `local_env()` | closed |
| T-01-13 | Denial of service | slow or hung upstream | medium | mitigate | lowSpeedLimit/Time, `GIT_TIMEOUT=600` -> `fetch_failed` | closed |
| T-01-14 | Tampering | stale refs after a branch change | medium | mitigate | Explicit refspec, HEAD/refspec moved only after a good fetch (CR-01 fix), `prune_foreign_refs` | closed |
| T-01-15 | Spoofing | invalid override falling back | high | mitigate | `UpstreamOverrideError` -> `run_disabled`, no fallback to GitHub | closed |
| T-01-16 | Tampering | partially written status.json | low | mitigate | mkstemp + fsync + `os.replace` + directory fsync (WR-05 fix); single writer | closed |
| T-01-17 | Elevation of privilege | stale symlink after revoke/restore/hand edit | high | mitigate | Revoke writes and unlinks under one lock; 1 s watcher; reconcile at start; fail-closed on corrupt file | closed |
| T-01-18 | Information disclosure | hash in CLI/watcher/reconcile logs | high | mitigate | Logs name repo and user only; formatter masks 32-hex values; `users list` masks hashes | closed |
| T-01-19 | Tampering | concurrent writers on access.json | medium | mitigate | RLock + `fcntl.flock`, re-read under lock, atomic replace | closed |
| T-01-20 | Tampering | entries with path characters | high | mitigate | Links built only from validated spec parts and `HASH_RE.fullmatch`; real-directory walk | closed |
| T-01-21 | Information disclosure | hash enumeration by compromised CGI | medium | mitigate | Access dirs 0711 | closed |
| T-01-22 | Spoofing | predictable or reused hashes | high | mitigate | `secrets.token_hex(16)`, uniqueness check, `hash_conflict` | closed |
| T-01-23 | Denial of service | future-schema file crash-looping watcher | low | mitigate | Logs once per signature, keeps links, stays up | closed |
| T-01-24 | Repudiation | false-green verification | high | mitigate | `set -euo pipefail`, needle files, positive controls in verify script | closed |
| T-01-25 | Information disclosure | real credentials in verify script | medium | mitigate | Runtime sentinels, `example.invalid` placeholders, local fixture, gitleaks | closed |
| T-01-26 | Denial of service | parallel verify runs colliding | low | mitigate | Header warning, `MRP_VERIFY_PREFIX` | closed |
| T-01-27 | Tampering | leftover root-owned files/containers | low | mitigate | Cleanup trap removes containers, network, data dir | closed |
| T-01-28 | Information disclosure | hostnames/IPs/e-mail/tokens in docs | medium | mitigate | Placeholder-only docs, gitleaks | closed |
| T-01-29 | Information disclosure | backups/URLs treated as non-secret | medium | mitigate | DOCS.md security notes | closed |
| T-01-30 | Tampering | contract drift docs vs code | low | mitigate | DOCS.md written from code; object-level reachability documented (AR-02) | closed |
| T-01-31 | Information disclosure | startup log | high | mitigate | Labels + masked URLs only; credentials in `public_url` rejected (WR-03 fix) | closed |
| T-01-32 | Denial of service | init oneshot halting the container | medium | mitigate | Only OptionsError/AccessSchemaError return 1; every other input problem is logged and survived. Unparseable `public_url` (`http://[x`) rejected since 7d748d8 (`test_malformed_public_url_is_rejected_without_a_traceback`). `OSError` in init chmod/mkdir is an environment failure, not input (IN-06, deferred) | closed |
| T-01-33 | Tampering | `.github/workflows/lint.yml` | medium | mitigate | Appended job, `contents: read`, `persist-credentials: false`, existing pins, actionlint + zizmor | closed |
| T-01-34 | Information disclosure | `mrp users add` output | medium | mitigate | `print` to stdout only; `cli.py` imports no `logging` | closed |
| T-01-35 | Tampering | `make update-version` bump | medium | mitigate | 3-file sync, validate-versions exit 0, bump commit touches config.yaml only | closed |
| T-01-36 | Tampering | release tag from feature branch | medium | mitigate | `NO_TAG=yes`; no tag locally or on origin | closed |
| T-01-37 | Information disclosure | SPIKE.md edit | low | mitigate | No IP/e-mail in added lines; `## Decisions` byte-identical | closed |
| T-01-SC | Tampering | apk installs, test runner pins | low | accept | See AR-01 | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01 | T-01-SC | Only Alpine distro packages from the base image repositories (`git git-daemon lighttpd python3`); CI reuses existing `pytest`/`pyyaml` pins; nothing from PyPI or npm in the image | plan threat model | 2026-11-18 |
| AR-02 | WR-01 (unregistered, medium) | Protocol v2 serves unadvertised objects by SHA until gc prunes them. Needs a valid capability URL for the same repository plus the exact object id; exposure limited to objects once fetched into that bare repo. Documented in DOCS.md security notes ("Old commits") since d53f52a | user (review disposition: deferred) | 2026-11-18 |
| AR-03 | WR-04 (unregistered, low) | `access.json` moved aside on transient read errors; earlier `.corrupt` overwritten. Fail-closed, availability only | user (review disposition: deferred) | 2026-11-18 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-18 | 38 | 37 | 1 (T-01-32, medium, non-blocking) | gsd-security-auditor at c6f9786 |
| 2026-11-18 | 38 | 38 | 0 | orchestrator: T-01-32 closed by 7d748d8, AR-02 documented by d53f52a |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-18
