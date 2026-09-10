---
schema_version: 1
open_count: 8
waived_count: 0
fixed_count: 4
total_count: 12
last_updated: 2026-09-10T19:24:43.304Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 17 | unmet-truth | iac-runner/internal/httpapi/handlers/redaction_audit.go | 51 | auditRedactions is implemented and unit-tested but has no production caller until 17-08 mounts GET /v1/runs/{id}; ROADMAP SC-10 is not observable end-to-end until then | fixed |  | 2026-09-08T11:50:39.004Z | 2026-09-08T12:08:09.469Z |
| 2 | 17 | unmet-truth | CLAUDE.md | 80 | CLAUDE.md documents 'yq eval --unsafe' for parsing HA config.yaml, but the yq installed on this host is python-yq (kislyuk) 4.1.2, which has no 'eval' subcommand and no '--unsafe' flag - the documented command fails locally. CI is unaffected (ubuntu-latest ships mikefarah/yq, which _build-template.yml relies on). Local scripts and agents must use python3 -c 'import yaml' instead, which is what make validate-addons already does. | open |  | 2026-09-08T21:06:25.807Z |  |
| 3 | 17 | lint-warning | .github/workflows/lint.yml | 94 | The 'Lint shell scripts' step ends in '\|\| echo "No shell scripts to check"', which swallows shellcheck's exit code - the step can never fail, so the repo's strictest shell gate (shellcheck with no -e exclusions) is non-blocking. Verified: repo-wide shellcheck without -e flags exits 1 with 46 diagnostics on main today. Removing the '\|\|' would immediately turn CI red, so the fix is ordered: clear the pre-existing SC2034/SC1091 findings first, then drop the fallback. Until then the effective shell gate is pre-commit's '-e SC1091 -e SC2034'. | open |  | 2026-09-09T18:18:06.064Z |  |
| 4 | quick-260909-rlj | unrun-verify | .github/workflows/auto-update.yml |  | actionlint was verified only under the pre-commit-pinned v1.7.3; lint.yml installs the latest release at run time and that build could not be exercised locally (no actionlint on PATH, no go toolchain, no network install in scope). The three edited workflows pass v1.7.3 and parse under PyYAML; latest-release actionlint remains CI-verified only. | fixed |  | 2026-09-09T20:12:43.269Z | 2026-09-09T20:25:44.422Z |
| 5 | quick-260909-rll | unrun-verify | .github/workflows/auto-update.yml |  | Live-run truth unverified: that a real auto-update run creates no tag (git ls-remote --tags origin after the next run) - not reachable from a repo checkout | open |  | 2026-09-09T20:38:21.321Z |  |
| 6 | quick-260909-rll | unrun-verify | .github/workflows/base-image-update.yml |  | Live-run truth unverified: that the two bump workflows actually queue behind the shared addon-version-bump group - needs two overlapping GitHub runs | open |  | 2026-09-09T20:38:26.589Z |  |
| 7 | quick-260909-rll | deviation | .github/workflows/auto-update.yml |  | Sibling 260909-rlj GATE-T1-14 (loop-region sha256 7b7356ab) is intentionally red: 7b7356ab -> cdaa8113. Replaced by narrower flanking pins GATE-T1-B/C/D | open |  | 2026-09-09T20:38:29.158Z |  |
| 8 | quick-260909-rlk | unrun-verify | .github/workflows/verify-image-availability.yml | 1 | The if: failure() HA-webhook leg has never executed. Run 34402464619 (workflow_dispatch, grace-minutes=0) was GREEN, so the notify step was correctly skipped: self-test, scan and checkout all succeeded. Proving the notify leg needs a genuinely red run, which requires a config.yaml version with no published image on the default branch - deliberately not manufactured. Everything else in the workflow is exercised: the self-test runs as its own step before the scan and passes all three probe directions. | open |  | 2026-09-09T20:41:32.937Z |  |
| 9 | quick-260909-rll | deviation | .planning/quick/stage-4-depends-on-stage-1-same-workflow-files-fix-the-tag-o/260909-rll-PLAN.md | 191 | The GATE-T1-14 supersession leaves a 9-line unpinned window (auto-update.yml 115-123) where only one line is the intended edit. A verifier's mutation probe injected shell code between the AUTO-02 and --check-release anchors and ALL replacement gates (GATE-T1-A..F) stayed green, while rlj's original whole-loop sha256 caught it. The shipped workflow is correct - this is a gap in the verification apparatus for future re-runs, not in the delivered code. Free fix: end Region A at the --check-release comment INCLUSIVE, leaving only comment text unpinned. Lesson: recomputing a hash proves a pin is correct; only mutation proves it catches. | open |  | 2026-09-09T20:55:30.424Z |  |
| 10 | quick-260909-rli | lint-warning | .github/workflows/auto-update.yml | 114 | auto-update.yml prepends upstream release notes to <addon>/CHANGELOG.md and runs 'npx prettier --write' on it with the stated intent 'so lint.yml does not reject the commit' - but prettier does not fix bare URLs and markdownlint (MD034/no-bare-urls) is what rejects them. Measured: the 2026-09-09 authentik 2026.8.2 bump produced authentik/CHANGELOG.md:1 with a bare URL and 'make lint' exit 1. The previous entry (2026.8.1) already carried the URL wrapped in <>, so this has been hand-fixed before and recurs on every authentik release. It went unnoticed because GITHUB_TOKEN pushes trigger neither the build workflows (fixed by 260909-rlj) nor lint.yml (still open). Fix: pipe the release body through a bare-URL wrapper, or run markdownlint --fix on the changelog, before committing. | open |  | 2026-09-09T21:04:47.128Z |  |
| 11 | quick-260909-rln | unmet-truth | Makefile | 234 | make release prints 'the build workflow will pick it up on the tag push'; after 260909-rln removed every tags: trigger this is false — the bump commit's build.yml run publishes the image | fixed |  | 2026-09-10T18:32:47.209Z | 2026-09-10T19:24:43.131Z |
| 12 | quick-260909-rln | unmet-truth | README.md | 161 | README says the pre-push hook 'enforces' a matching tag; 260909-wgm made internal/check-version-tags.sh advisory (it never fails a push). Plan 260909-rln item 2 mandated keeping the rest of that bullet intact, so it was not changed here | fixed |  | 2026-09-10T18:32:53.178Z | 2026-09-10T19:24:43.304Z |

````json
[
  {
    "id": 1,
    "kind": "unmet-truth",
    "phase": "17",
    "file": "iac-runner/internal/httpapi/handlers/redaction_audit.go",
    "line": 51,
    "description": "auditRedactions is implemented and unit-tested but has no production caller until 17-08 mounts GET /v1/runs/{id}; ROADMAP SC-10 is not observable end-to-end until then",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-08T11:50:39.004Z",
    "resolved_at": "2026-09-08T12:08:09.469Z"
  },
  {
    "id": 2,
    "kind": "unmet-truth",
    "phase": "17",
    "file": "CLAUDE.md",
    "line": 80,
    "description": "CLAUDE.md documents 'yq eval --unsafe' for parsing HA config.yaml, but the yq installed on this host is python-yq (kislyuk) 4.1.2, which has no 'eval' subcommand and no '--unsafe' flag - the documented command fails locally. CI is unaffected (ubuntu-latest ships mikefarah/yq, which _build-template.yml relies on). Local scripts and agents must use python3 -c 'import yaml' instead, which is what make validate-addons already does.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-08T21:06:25.807Z",
    "resolved_at": null
  },
  {
    "id": 3,
    "kind": "lint-warning",
    "phase": "17",
    "file": ".github/workflows/lint.yml",
    "line": 94,
    "description": "The 'Lint shell scripts' step ends in '|| echo \"No shell scripts to check\"', which swallows shellcheck's exit code - the step can never fail, so the repo's strictest shell gate (shellcheck with no -e exclusions) is non-blocking. Verified: repo-wide shellcheck without -e flags exits 1 with 46 diagnostics on main today. Removing the '||' would immediately turn CI red, so the fix is ordered: clear the pre-existing SC2034/SC1091 findings first, then drop the fallback. Until then the effective shell gate is pre-commit's '-e SC1091 -e SC2034'.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-09T18:18:06.064Z",
    "resolved_at": null
  },
  {
    "id": 4,
    "kind": "unrun-verify",
    "phase": "quick-260909-rlj",
    "file": ".github/workflows/auto-update.yml",
    "line": null,
    "description": "actionlint was verified only under the pre-commit-pinned v1.7.3; lint.yml installs the latest release at run time and that build could not be exercised locally (no actionlint on PATH, no go toolchain, no network install in scope). The three edited workflows pass v1.7.3 and parse under PyYAML; latest-release actionlint remains CI-verified only.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-09T20:12:43.269Z",
    "resolved_at": "2026-09-09T20:25:44.422Z"
  },
  {
    "id": 5,
    "kind": "unrun-verify",
    "phase": "quick-260909-rll",
    "file": ".github/workflows/auto-update.yml",
    "line": null,
    "description": "Live-run truth unverified: that a real auto-update run creates no tag (git ls-remote --tags origin after the next run) - not reachable from a repo checkout",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-09T20:38:21.321Z",
    "resolved_at": null
  },
  {
    "id": 6,
    "kind": "unrun-verify",
    "phase": "quick-260909-rll",
    "file": ".github/workflows/base-image-update.yml",
    "line": null,
    "description": "Live-run truth unverified: that the two bump workflows actually queue behind the shared addon-version-bump group - needs two overlapping GitHub runs",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-09T20:38:26.589Z",
    "resolved_at": null
  },
  {
    "id": 7,
    "kind": "deviation",
    "phase": "quick-260909-rll",
    "file": ".github/workflows/auto-update.yml",
    "line": null,
    "description": "Sibling 260909-rlj GATE-T1-14 (loop-region sha256 7b7356ab) is intentionally red: 7b7356ab -> cdaa8113. Replaced by narrower flanking pins GATE-T1-B/C/D",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-09T20:38:29.158Z",
    "resolved_at": null
  },
  {
    "id": 8,
    "kind": "unrun-verify",
    "phase": "quick-260909-rlk",
    "file": ".github/workflows/verify-image-availability.yml",
    "line": 1,
    "description": "The if: failure() HA-webhook leg has never executed. Run 34402464619 (workflow_dispatch, grace-minutes=0) was GREEN, so the notify step was correctly skipped: self-test, scan and checkout all succeeded. Proving the notify leg needs a genuinely red run, which requires a config.yaml version with no published image on the default branch - deliberately not manufactured. Everything else in the workflow is exercised: the self-test runs as its own step before the scan and passes all three probe directions.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-09T20:41:32.937Z",
    "resolved_at": null
  },
  {
    "id": 9,
    "kind": "deviation",
    "phase": "quick-260909-rll",
    "file": ".planning/quick/stage-4-depends-on-stage-1-same-workflow-files-fix-the-tag-o/260909-rll-PLAN.md",
    "line": 191,
    "description": "The GATE-T1-14 supersession leaves a 9-line unpinned window (auto-update.yml 115-123) where only one line is the intended edit. A verifier's mutation probe injected shell code between the AUTO-02 and --check-release anchors and ALL replacement gates (GATE-T1-A..F) stayed green, while rlj's original whole-loop sha256 caught it. The shipped workflow is correct - this is a gap in the verification apparatus for future re-runs, not in the delivered code. Free fix: end Region A at the --check-release comment INCLUSIVE, leaving only comment text unpinned. Lesson: recomputing a hash proves a pin is correct; only mutation proves it catches.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-09T20:55:30.424Z",
    "resolved_at": null
  },
  {
    "id": 10,
    "kind": "lint-warning",
    "phase": "quick-260909-rli",
    "file": ".github/workflows/auto-update.yml",
    "line": 114,
    "description": "auto-update.yml prepends upstream release notes to <addon>/CHANGELOG.md and runs 'npx prettier --write' on it with the stated intent 'so lint.yml does not reject the commit' - but prettier does not fix bare URLs and markdownlint (MD034/no-bare-urls) is what rejects them. Measured: the 2026-09-09 authentik 2026.8.2 bump produced authentik/CHANGELOG.md:1 with a bare URL and 'make lint' exit 1. The previous entry (2026.8.1) already carried the URL wrapped in <>, so this has been hand-fixed before and recurs on every authentik release. It went unnoticed because GITHUB_TOKEN pushes trigger neither the build workflows (fixed by 260909-rlj) nor lint.yml (still open). Fix: pipe the release body through a bare-URL wrapper, or run markdownlint --fix on the changelog, before committing.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-09T21:04:47.128Z",
    "resolved_at": null
  },
  {
    "id": 11,
    "kind": "unmet-truth",
    "phase": "quick-260909-rln",
    "file": "Makefile",
    "line": 234,
    "description": "make release prints 'the build workflow will pick it up on the tag push'; after 260909-rln removed every tags: trigger this is false — the bump commit's build.yml run publishes the image",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-10T18:32:47.209Z",
    "resolved_at": "2026-09-10T19:24:43.131Z"
  },
  {
    "id": 12,
    "kind": "unmet-truth",
    "phase": "quick-260909-rln",
    "file": "README.md",
    "line": 161,
    "description": "README says the pre-push hook 'enforces' a matching tag; 260909-wgm made internal/check-version-tags.sh advisory (it never fails a push). Plan 260909-rln item 2 mandated keeping the rest of that bullet intact, so it was not changed here",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-09-10T18:32:53.178Z",
    "resolved_at": "2026-09-10T19:24:43.304Z"
  }
]
````
