---
schema_version: 1
open_count: 2
waived_count: 0
fixed_count: 1
total_count: 3
last_updated: 2026-09-09T18:18:06.064Z
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
  }
]
````
