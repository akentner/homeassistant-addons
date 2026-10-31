---
phase: quick-261031-srb
plan: 01
subsystem: haos-monitor
tags: [ssh, fingerprint, status-json, mqtt, ingress-ui]
status: complete
commits: 1
plan_head_before: 3b1b31661f7b0dbbf42961b02c8f134a1e55abb9
plan_head_after: 7edc35a
actuals:
  tokens: 12000
  tasks: 3
  commits: 1
key-files:
  modified:
    - haos-monitor/run.sh
    - haos-monitor/status.sh
    - haos-monitor/index.html
    - haos-monitor/mqtt.sh
    - haos-monitor/DOCS.md
    - haos-monitor/CHANGELOG.md
    - haos-monitor/config.yaml
  created:
    - .planning/quick/261031-srb-haos-monitor-show-ssh-key-fingerprint-pe/261031-srb-verify.sh
completed: 2026-10-31
---

# Quick 261031-srb: SSH key fingerprint per host (haos-monitor 0.6.1-1)

`run.sh` now derives the SHA256 fingerprint and key type of each host's configured key
(`ssh-keygen -y -P '' | ssh-keygen -l -E sha256 -f -`), hands them through hosts-file columns 5 and 6 to `status.sh`
(`key_fp`, `key_type` in the status JSON), the Ingress status page ("SSH key" line) and the MQTT `problem` sensor
attributes (`key_fingerprint`, `key_type`). A key `ssh-keygen` rejects shows `invalid` and the host stays monitored.

## Tasks

1. Tracer: `key_fingerprint()` in run.sh, hosts file columns, status.sh fields, verify script (stages fingerprint,
   status, docker, red first, then green).
2. UI `keyText()` plus `.key` line, MQTT `PROBLEM_ATTRS` extension (stages ui, mqtt).
3. DOCS.md section, CHANGELOG entry, `make update-version ADDON=haos-monitor VERSION=0.6.1-1 NO_TAG=yes`, final gate.

All in one commit per the plan: `7edc35a feat(haos-monitor): show the SSH key fingerprint per host (0.6.1-1)`.

## Verification (real results)

- verify.sh stages: fingerprint OK, status OK, mqtt OK (jinja render ran, not skipped), ui OK, docker OK (local
  `docker build` of haos-monitor/ succeeded; real container served matching fingerprints for intact ed25519,
  space-flattened RSA, `invalid` for the damaged key; hosts file 6 columns; no key body, comment or PEM marker leaked).
- `make validate-versions` passed; `config.yaml` 0.6.1-1, `build.yaml` and `README.md` unchanged.
- shellcheck (`-e SC1091 -e SC2034`) and the full pre-commit hook set (prettier, markdownlint, gitleaks, version
  validation) passed, also at commit time.
- Docker image/container and temp dir are removed by the verify script's EXIT trap; none left behind.

## Deviations from Plan

- [Rule 1 - Bug in verify script] The first draft of the `evil_host` filter assertions passed vacuously (`jq -r` printed
  `null` on the unchanged tree); they now require a string type. Shellcheck info-level findings in the script were fixed
  (pre-commit runs shellcheck at default severity).
- Only `261031-srb-verify.sh` was committed from the quick directory; PLAN.md and this SUMMARY were left uncommitted per
  the caller's constraints (the plan's `git add <quick dir>` would have included PLAN.md).
- `Dockerfile` unchanged (ssh-keygen ships with `openssh-client`, confirmed in the docker stage).

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model (values filtered with `tr -cd` in status.sh, rendered via `textContent`).

## Self-Check: PASSED

Commit 7edc35a exists on the worktree branch; all modified files present; no tag created, nothing pushed.
