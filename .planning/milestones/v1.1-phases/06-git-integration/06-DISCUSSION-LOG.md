# Phase 6: Git Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents. Decisions are captured in
> CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-27 **Phase:** 6 - Git Integration **Areas discussed:** First-time repo handling, Where git ops live,
Periodic sync mechanics, Detection of git repo

---

## First-time repo handling

| Option                               | Description                                                                                                                         | Selected |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- | -------- |
| Require user to clone first          | User must `git clone` into path on HA host before enabling `git_pull`. Add-on only runs `git pull`. Matches GIT-05 literal reading. |          |
| Auto-clone with `git_url` (required) | Add `git_url: str` (required when `git_pull: true`). Auto-clone on first run. Adds schema field.                                    |          |
| Auto-clone with optional `git_url`   | Add `git_url: str` (optional). Clone only if path is not a repo AND url is set. Otherwise warn and serve.                           | ✓        |

**User's choice:** Auto-clone fallback only **Notes:** Most flexible; requires no schema field when user has already
cloned manually, but enables bootstrap for empty paths.

---

## Where git ops live

| Option                     | Description                                                                                                    | Selected |
| -------------------------- | -------------------------------------------------------------------------------------------------------------- | -------- |
| New `_git_sync.py` helper  | Separate Python file. `run.sh` calls it for startup and in periodic loop. Mirrors `generate_nginx.py` pattern. | ✓        |
| Extend `generate_nginx.py` | Add git logic to existing script. Single file, but `generate_nginx.py` name becomes misleading.                |          |
| Shell function in `run.sh` | Inline `_git_pull() { ... }` in `run.sh`. Simpler but mixed shell+Python.                                      |          |

**User's choice:** New `_git_sync.py` helper **Notes:** Keeps concerns separated. Git is independent from nginx config
generation. Easier to test in isolation.

---

## Periodic sync mechanics

| Option                                | Description                                                                                                                                                          | Selected |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| Single loop iterating all namespaces  | One background loop in `run.sh`. Each iteration calls `_git_sync.py --periodic` which iterates all namespaces with `git_pull_interval > 0`. Sleep = `min(interval)`. | ✓        |
| One loop per namespace                | Backgrounded loop per namespace. Concurrent pulls. More complex signal handling.                                                                                     |          |
| Single loop with per-namespace timing | Track per-namespace `last_pull`; each namespace runs on its own cadence.                                                                                             |          |

**User's choice:** Single loop iterating all namespaces **Notes:** Simpler signal handling (one child PID to kill). No
concurrent pulls. Slight latency for fast intervals, but acceptable.

### Follow-up: Log throttling

| Option                     | Description                                                                       | Selected |
| -------------------------- | --------------------------------------------------------------------------------- | -------- |
| Log every failure          | Each iteration logs warning on failure. ~12 warnings/hour at 5-min interval.      | ✓        |
| Log only state transitions | Track success/failure state; only log on transitions. Avoids spam during outages. |          |

**User's choice:** Log every failure **Notes:** HA Supervisor already rate-limits logs. No need for in-add-on
deduplication. Keeps debug info visible.

---

## Detection of git repo

| Option                             | Description                                                                          | Selected |
| ---------------------------------- | ------------------------------------------------------------------------------------ | -------- |
| Probe via `git rev-parse`          | Run `git -C "$path" rev-parse --git-dir` first. Exit 0 = repo. Clear error messages. | ✓        |
| Just run `git pull`, ignore errors | Always pull. Non-zero exit = warn and continue. Confusing logs on first-run.         |          |

**User's choice:** Probe via `git rev-parse` **Notes:** Matches structured approach used elsewhere. Distinguishes "not a
repo" from "repo but pull failed" in logs.

---

## the agent's Discretion

- Exact Dockerfile ARG for git version pinning (default: alpine3.20 latest)
- Warning message wording in `_git_sync.py`
- Behavior on `git_url` clone failure (single attempt vs retry — recommend single attempt matching GIT-05)
- Shell-quoting pattern for git subprocess invocations (recommend subprocess list-form)
- subprocess.run vs os.execvp for git calls (recommend subprocess.run for testability)

---

## Deferred Ideas

- SSH key handling for private git repos — Future (v1.2)
- Webhook-triggered periodic sync — Future
- Per-namespace git PATs for private repos — Future (v1.2)
- Git LFS support — Out of scope
- Auto-push from inside add-on — Out of scope (read/pull only)
