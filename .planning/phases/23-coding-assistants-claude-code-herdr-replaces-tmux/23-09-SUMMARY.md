---
phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
plan: 09
subsystem: release
tags: [release-gate, verify-harness, version-bump, coding-assistants]

requires:
  - phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
    provides: "23-01..08: Claude Code, MCP registration, herdr, plugins, /services/ web UI, documentation"
provides:
  - "release-candidate evidence: full harness (13 scenarios, 225 PASS, 0 FAIL) on a freshly built image plus every scoped lint gate"
  - "coding-assistants bumped to 1.1.0-0 through make update-version (no tag, no push)"
  - "operator release hand-off"
affects: []

actuals:
  tokens: 400
  tasks: 3
  commits: 1

plan_head_before: be6c202cb66dafa72496a06a6783739d01cc2202
plan_head_after: 84739b01d4b7925cc4ce366fc16760345d9a808c
commits: 1

tech-stack:
  added: []
  patterns:
    - "gate task changes no file; the only code commit of the plan is the sanctioned version bump"

key-files:
  created: []
  modified:
    - coding-assistants/config.yaml
    - coding-assistants/build.yaml
    - coding-assistants/README.md

key-decisions:
  - "Bump size: Minor, version 1.1.0-0 (chosen by the user on 2026-10-12, relayed through the orchestrator's question; deviates from the literal D-08 wording 'subpatch', which the plan offered as the alternative 1.0.0-3)"
  - "Applied only with `make update-version ADDON=coding-assistants VERSION=1.1.0-0 NO_TAG=yes NO_PUSH=yes`; no tag, no push (T-23-31)"

requirements-completed: [D-08]

status: complete

coverage:
  - id: G1
    description: "Full harness `bash internal/verify-coding-assistants.sh all` passes on a freshly built image with every registered scenario executed"
    requirement: D-08
    verification:
      - kind: command
        ref: "TMPDIR=/var/tmp/ca-verify-23-09 bash internal/verify-coding-assistants.sh all -> ALL CHECKS PASSED, exit 0, 225 PASS / 0 FAIL, 13 scenarios"
        status: pass
    human_judgment: false
  - id: G2
    description: "Scoped lint gates: hadolint (hook ignore list), validate-dockerfile-args, shellcheck, yamllint, validate-addon-config, make validate-addons, make validate-versions, pre-commit over every file the phase changed"
    requirement: D-08
    verification:
      - kind: command
        ref: "all exit 0; pre-commit over 18 files passed every hook and left git status clean"
        status: pass
    human_judgment: false
  - id: G3
    description: "Version bump applied only through make update-version; 3-file sync valid; HERDR_* and plugin ref pins untouched; no tag; no push"
    requirement: D-08
    verification:
      - kind: command
        ref: "make validate-versions exit 0; harness `drift` scenario ALL CHECKS PASSED; git tag --list 'coding-assistants/v1.0.0-3' 'coding-assistants/v1.1.0-0' empty"
        status: pass
    human_judgment: false
  - id: G4
    description: "Browser / HA-ingress behaviour of the Services tab and the other interactive items listed under Human-Judgment Items Still Open"
    requirement: D-08
    verification:
      - kind: manual
        ref: "see Human-Judgment Items Still Open"
        status: open
    human_judgment: true
---

# Phase 23 Plan 09: Release-candidate gate and version bump Summary

**Full 13-scenario harness (225 checks) and every scoped lint gate pass on a freshly built image; coding-assistants bumped to 1.1.0-0 via `make update-version` with no tag and no push.**

## Performance

- **Harness duration (`all`, including the image build):** 260 s
- **Image size (printed by the plugins scenario):** 2843886404 bytes (about 2.84 GB)
- **Harness scenarios executed (13):** claude-launcher, claude-state, claude-auth, mcp-servers, mcp-integrations, drift,
  herdr-core, herdr-attach, surface, plugins, services, services-auth, docs. All three plugins and the web-service were
  approved in 23-PLUGIN-REVIEW.md, so no scenario was dropped.

## Task Results

| Task | Name | Result | Commit |
| ---- | ---- | ------ | ------ |
| 1 | Release-candidate gate | passed, no file changed | none (gate task) |
| 2 | Confirm bump size (checkpoint:decision, blocking-human) | answered before spawn: **Minor: 1.1.0-0**, chosen by the user on 2026-10-12 and relayed by the orchestrator | none |
| 3 | Apply the bump, validate, hand off | passed | 84739b0 |

### Task 1 gate results

- `bash internal/verify-coding-assistants.sh all` -> `ALL CHECKS PASSED`, exit 0, 225 PASS lines, 0 FAIL
- `hadolint` with the pre-commit ignore list (DL3008, DL3018, DL3059, DL4006, DL3016) on `coding-assistants/Dockerfile` -> 0
- `./internal/validate-dockerfile-args.sh coding-assistants/Dockerfile` -> OK
- `shellcheck -e SC1091 -e SC2034` on run.sh, coding-assistants-attach, verify-coding-assistants.sh,
  spike-herdr-web-service.sh -> 0
- `yamllint -d relaxed` on config.yaml and build.yaml -> only the pre-existing line-length warning (config.yaml:2)
- `python3 internal/validate-addon-config.py coding-assistants`, `make validate-addons`, `make validate-versions` -> 0
- `pre-commit run --files` over the 18 existing files of plans 23-01..23-08 (build.yaml, CHANGELOG.md,
  coding-assistants-attach, config.yaml, Dockerfile, DOCS.md, index.html, info.html, nginx.conf,
  patches/herdr-web-service-subpath.patch, README.md, run.sh, TOOLS.md, internal/spike-herdr-web-service.sh,
  internal/verify-coding-assistants.sh, root README.md, 23-PLUGIN-REVIEW.md, 23-SPIKE-WEB-SERVICE.md) -> every hook
  passed, `git status` clean afterwards (no hook rewrote a file)
- The scoped hadolint command was used instead of the bare `make docker-build-check` (known unrelated authentik DL3008
  finding, broken-windows ledger entry 13)

### Task 3 bump

- **Final version:** `1.1.0-0`
- **Exact command:** `make update-version ADDON=coding-assistants VERSION=1.1.0-0 NO_TAG=yes NO_PUSH=yes`
- **Diff (`git diff --stat HEAD`, 3 files, 4 lines):** config.yaml `version: "1.0.0-2"` -> `"1.1.0-0"`; build.yaml
  `VERSION: "1.0.0"` -> `"1.1.0"` (the `VERSION:` line only); README.md badge lines `v1.0.0` -> `v1.1.0` (shield and
  release link only). No HERDR_* / plugin ref key changed; the `drift` scenario passes afterwards.
- `make validate-versions` passes; tagging was skipped by `NO_TAG=yes`.
- No tag exists for `coding-assistants/v1.0.0-3` or `coding-assistants/v1.1.0-0`; nothing was pushed.

## Release Hand-off (operator)

1. Review and merge the phase (milestone work lands through the repo's branch convention: squash-merge into `main`).
2. Follow `.github/RELEASE.md`: the tag name is `coding-assistants/v<args.VERSION>`, i.e. **`coding-assistants/v1.1.0`**
   (build.yaml `VERSION` has no subpatch). The push of the version files to `main` is what triggers
   `.github/workflows/build.yml` and publishes the image the Supervisors pull.
3. Suggested sequence once satisfied: push the branch/merge to `main`, then tag and push the tag. The `[Unreleased]`
   CHANGELOG section written in 23-08 is still named `[Unreleased]`; it is not converted to `[1.1.0]` by this plan, do
   that as part of the release if you keep dated CHANGELOG sections.
4. The release notes should call out: herdr replaces tmux (hard removal, see the migration section of DOCS.md), the
   three new options (`claude_code_oauth_token`, `anthropic_api_key`, `herdr_web_password`), the `/services/` web UI
   running as root with its login, and the three third-party plugins pinned by commit.

## Human-Judgment Items Still Open

These cannot be proven by the container harness and remain for the operator before or right after release:

- **Browser / HA-ingress UI:** open the Services tab in real Home Assistant ingress, log in with `herdr_web_password`,
  see the roster, check the browser console for errors (from 23-07).
- **`claude update` end to end:** run `claude update` in a started add-on and confirm the new version survives a
  container re-creation (harness proves the layout and seed/newest selection, not a real network update).
- **subagent-watch setup:** the plugin is linked but not configured (D-02, D-04); the opt-in key binding / sidebar setup
  from DOCS.md still needs a human try-out inside herdr.
- **Auth file deletion -> login 503:** delete the web-service auth file in a running add-on, and confirm the login
  answers 503 again (the harness proves 503 only for the never-configured state).

## Deviations from Plan

None - plan executed exactly as written. The only note: the checkpoint (Task 2) was answered upstream by the user through
the orchestrator rather than as an in-run stop, per the dispatch instructions; the answer is recorded above.

## Known Stubs

None.

## Threat Flags

None. T-23-31 (unintended release) is mitigated: blocking-human decision recorded, `NO_TAG=yes NO_PUSH=yes`, harness on the
exact candidate before the bump, tag and push left to the operator.

## Issues Encountered

None. Environment note: /tmp is a small tmpfs, so the harness ran with `TMPDIR=/var/tmp/ca-verify-23-09` (scratch removed
afterwards); the harness removed its own image and containers.

## Self-Check: PASSED

- FOUND: coding-assistants/config.yaml (`version: "1.1.0-0"`), coding-assistants/build.yaml, coding-assistants/README.md
- FOUND commit: 84739b0 (ancestor of HEAD)
