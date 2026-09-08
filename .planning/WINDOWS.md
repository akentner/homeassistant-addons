---
schema_version: 1
open_count: 1
waived_count: 0
fixed_count: 0
total_count: 1
last_updated: 2026-09-08T11:50:39.004Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 17 | unmet-truth | iac-runner/internal/httpapi/handlers/redaction_audit.go | 51 | auditRedactions is implemented and unit-tested but has no production caller until 17-08 mounts GET /v1/runs/{id}; ROADMAP SC-10 is not observable end-to-end until then | open |  | 2026-09-08T11:50:39.004Z |  |

````json
[
  {
    "id": 1,
    "kind": "unmet-truth",
    "phase": "17",
    "file": "iac-runner/internal/httpapi/handlers/redaction_audit.go",
    "line": 51,
    "description": "auditRedactions is implemented and unit-tested but has no production caller until 17-08 mounts GET /v1/runs/{id}; ROADMAP SC-10 is not observable end-to-end until then",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-08T11:50:39.004Z",
    "resolved_at": null
  }
]
````
