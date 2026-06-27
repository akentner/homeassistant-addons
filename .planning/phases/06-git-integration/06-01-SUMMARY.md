---
phase: 06-git-integration
plan: 01
subsystem: git-integration
tags: [git, markdown-renderer, periodic-sync, docsify, nginx]

# Dependency graph
requires:
  - phase: 05-multi-namespace-dynamic-config
    provides: "directories[] schema + generate_nginx.py pattern + /share:/config:/media:rw mounts"
provides:
  - "markdown-renderer/_git_sync.py: probe/pull/clone helper with non-blocking semantics"
  - "Extended config.yaml schema with git_pull, git_pull_interval, git_url per directory"
  - "Dockerfile installs git binary on the same apk layer as nginx/curl/tar"
  - "run.sh orchestrates startup pull + periodic background loop + signal trap"
affects:
  - "Phase 06 plan 02 (empirical verification of git sync behaviors)"
  - "DOCS.md (must document the three new fields — out of scope for this plan)"

# Tech tracking
tech-stack:
  added:
    - "git (apk package in markdown-renderer Dockerfile)"
    - "subprocess.run with check=False (non-blocking git semantics)"
  patterns:
    - "OPTIONS_PATH = Path('/data/options.json') as canonical options source (mirrors generate_nginx.py)"
    - "flush=True on every print for containerized observability"
    - "In-memory last_pull dict for per-namespace interval state (no /data persistence)"
    - "Single background while-true loop in shell, per-namespace gating in Python"
    - "POSIX trap on TERM INT to kill background PID before exec nginx"

key-files:
  created:
    - "markdown-renderer/_git_sync.py (270 lines)"
  modified:
    - "markdown-renderer/config.yaml (3 new schema fields, 3 new options defaults)"
    - "markdown-renderer/Dockerfile (apk add line extended with git)"
    - "markdown-renderer/run.sh (safe.directory, startup pull, periodic loop, signal trap)"
    - ".gitignore (markdown-renderer/__pycache__/)"

key-decisions:
  - "Used POSIX 'TERM INT' trap syntax (not 'SIGTERM/SIGINT') to match /bin/sh and CONVENTIONS.md"
  - "Single-attempt git clone (no retry) per D-02 discretion — clearer warnings, no log spam"
  - "Single background while loop in run.sh (not one per namespace) per D-08 — simpler signal handling"
  - "Did NOT bump config.yaml version — follows Phase 5 pattern; empirical verification happens in Plan 02"

patterns-established:
  - "Python helper reading /data/options.json: same module-docstring + type-hints + pathlib + if __name__ guard pattern"
  - "Non-blocking git operations: subprocess.run(check=False) + WARNING: log lines, never raise"
  - "Periodic interval state kept in-memory only — first periodic iteration pulls every configured namespace (D-09)"

requirements-completed: [GIT-01, GIT-02, GIT-03, GIT-04, GIT-05]

# Metrics
duration: 19min
completed: 2026-06-27
---

# Phase 6 Plan 1: Git Integration Helper Summary

**Per-namespace git pull/clone orchestration in markdown-renderer with non-blocking semantics, periodic background loop,
and clean signal handling.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-06-27T21:54:46Z
- **Completed:** 2026-06-27T22:13:55Z
- **Tasks:** 3
- **Files modified:** 4 (`config.yaml`, `Dockerfile`, `run.sh`, `_git_sync.py`) + 1 gitignore entry

## Accomplishments

- New `_git_sync.py` (270 lines) handles probe (`rev-parse --git-dir`), pull (`pull --ff-only`), and clone with
  `check=False` non-blocking semantics — GIT-05 contract enforced by never raising.
- Extended `config.yaml` schema with three optional fields per namespace: `git_pull: bool`, `git_pull_interval: int`,
  `git_url: str?` — GIT-01, GIT-03, GIT-04.
- Dockerfile installs `git` on the same `apk add` line as nginx/curl/tar — keeps image layer flat.
- `run.sh` orchestrates the full lifecycle: `git config safe.directory` → `generate_nginx.py` → `_git_sync.py` (startup)
  → background `while true` periodic loop → SIGTERM/SIGINT trap → `exec nginx`.
- All 5 GIT-01..05 requirements have at least one grep-verifiable artifact in the codebase.
- Pre-commit hooks (yamllint, shellcheck, Validate Add-on config.yaml Schema, Validate Add-on Versioning) pass cleanly
  on every commit.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend config.yaml schema + Dockerfile with git fields** - `ce7fcc9` (feat)
2. **Task 2: Create \_git_sync.py with probe/pull/clone + periodic state** - `fa43a67` (feat)
3. **Task 3: Wire \_git_sync.py into run.sh with startup pull, periodic loop, and signal trap** - `4a82e03` (feat)
4. **Chore: gitignore markdown-renderer **pycache\*\*\*\* - `260804e` (chore)

## Files Created/Modified

- `markdown-renderer/_git_sync.py` — New Python helper. Reads `/data/options.json`, walks `directories[]`, probes each
  path with `git rev-parse --git-dir`, runs `git pull --ff-only` for repos and `git clone` for first-time setups with
  `git_url`. All subprocess calls use `check=False`; failures emit `WARNING:` log lines via `flush=True`. In-memory
  `last_pull: dict[str, float]` tracks per-namespace interval state (resets on restart per D-09). Always returns 0 so
  run.sh can `exec nginx` even when every git remote is unreachable.
- `markdown-renderer/config.yaml` — Added `git_pull: bool`, `git_pull_interval: int`, `git_url: str?` to
  `schema.directories[0]` with comment lines explaining each field. Added matching defaults (`false`, `0`, `""`) to
  `options.directories[0]` so the HA UI shows examples.
- `markdown-renderer/Dockerfile` — Extended `RUN apk add --no-cache nginx curl tar` line with `git` (D-12). Comment
  explains why the binary is installed unconditionally even when no namespace uses git sync.
- `markdown-renderer/run.sh` — Rewrote from 10 lines to 39 lines. Added `git config --global --add safe.directory '*'`,
  `python3 /app/_git_sync.py` (startup pull), background `while true` loop with `GIT_SYNC_PID=$!`, and
  `trap 'kill "$GIT_SYNC_PID" 2>/dev/null || true; exit 0' TERM INT`. Preserved
  `exec nginx -c /tmp/nginx.conf -g 'daemon off;'` as final line.
- `.gitignore` — Added `markdown-renderer/__pycache__/` (mirrors existing `scripts/__pycache__/`).

## Decisions Made

- **POSIX `TERM INT` over `SIGTERM/SIGINT`:** The plan's verify regex looked for the literal string `SIG(TERM|INT)`, but
  POSIX `trap` accepts both forms and `TERM INT` is the portable convention. Since the file is `#!/bin/sh` and
  CONVENTIONS.md prescribes POSIX shell for `phone-logger` (the same pattern), `TERM INT` is correct. POSIX shells treat
  the names as identical. Documented as a deviation.
- **Single-attempt `git clone`:** Per the discretion guidance in CONTEXT.md D-02, retries would only delay failures and
  spam logs on every periodic tick. A single attempt with a clear `WARNING:` line matches GIT-05's non-blocking
  contract.
- **In-memory interval state:** Per D-09, the first periodic iteration pulls every configured namespace once. This
  matches the v1.1 philosophy of no extra state files in `/data` and survives restarts with at most one wasted pull.
- **No version bump yet:** Following the Phase 5 pattern (from `05-01-SUMMARY.md`), the empirical verification in Plan
  02 may surface issues that warrant a subpatch. The version stays at `1.0.0-0` until Plan 02 lands.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `markdown-renderer/__pycache__/` to `.gitignore`**

- **Found during:** Task 2 (after `python3 -m py_compile` verification)
- **Issue:** `py_compile` generated `markdown-renderer/__pycache__/_git_sync.cpython-314.pyc` which was untracked but
  reproducible on every local verify. Without a gitignore entry, it would appear in `git status` indefinitely.
- **Fix:** Added `markdown-renderer/__pycache__/` to `.gitignore`, mirroring the existing `scripts/__pycache__/`
  pattern.
- **Files modified:** `.gitignore`
- **Verification:** `git status --short markdown-renderer/` is clean after every subsequent commit
- **Committed in:** `260804e` (separate chore commit so the plan's three task commits stay focused)

**2. [Rule 1 - Cosmetic] Used POSIX `TERM INT` instead of literal `SIGTERM/SIGINT` in trap**

- **Found during:** Task 3 verification
- **Issue:** The plan's verify regex `grep -qE 'trap.*SIG(TERM|INT)'` looked for the literal `SIG` prefix. POSIX `trap`
  accepts both forms; the script's `#!/bin/sh` shebang + CONVENTIONS.md prescription for POSIX shell mean `TERM INT` is
  the canonical choice. `grep -F 'TERM INT'` finds the trap line and a functional test (`kill -TERM <pid>`) confirms the
  trap fires correctly.
- **Fix:** No code change — the trap is functionally correct. The verify regex in the plan is over-strict for POSIX sh;
  the spirit of the criterion (signal handling works) is met.
- **Files modified:** None
- **Verification:** `kill -TERM <pid>` against a test script with `trap '...' TERM INT` fires the handler (exit code
  143, then 0 from `exit 0`)
- **Committed in:** `4a82e03` (Task 3)

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 cosmetic) **Impact on plan:** Both deviations are
non-functional — the gitignore prevents noise in future `git status` output, and the POSIX trap syntax is more correct
than the plan's literal-string regex. No scope creep; all 5 GIT-01..05 requirements have grep-verifiable artifacts.

## Issues Encountered

- **yamllint noise on Dockerfile:** yamllint complains that Dockerfile isn't YAML (it isn't — same warning on every
  Dockerfile in the repo: meridian, phone-logger, network-tools). Not a real issue; yamllint is the wrong tool for
  Dockerfiles. Hadolint handles Dockerfile lint elsewhere and is currently disabled per CONVENTIONS.md. No action
  needed.
- **Verification regex for trap line:** The plan's acceptance criterion `grep -qE 'trap.*SIG(TERM|INT)'` doesn't match
  the POSIX form `TERM INT` that `#!/bin/sh` scripts use. Documented as deviation #2 above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 5 GIT-01..05 requirements have at least one grep-verifiable artifact on disk.
- `_git_sync.py` is executable, compiles cleanly (270 lines, ≥ 100), uses `check=False` non-blocking semantics, and
  exposes `sync_namespace` + `sync_all_namespaces` public API.
- `run.sh` passes `shellcheck -e SC1091,SC2034` with exit 0.
- All pre-commit hooks pass on every commit (yamllint, shellcheck, Validate Add-on config.yaml Schema, Validate Add-on
  Versioning).
- Ready for **Plan 02: empirical verification** — should test (a) startup pull against a real git repo, (b) periodic
  loop with `git_pull_interval`, (c) unreachable remote at startup doesn't block nginx, (d) first-time `git clone` via
  `git_url`, (e) SIGTERM/SIGINT clean shutdown of the periodic loop.
- DOCS.md update for the three new fields is out of scope for this plan but should land before the version bump in Plan
  02 or shortly after.

---

_Phase: 06-git-integration_ _Completed: 2026-06-27_

## Self-Check: PASSED

All artifacts verified on disk:

- `.planning/phases/06-git-integration/06-01-SUMMARY.md` exists
- `markdown-renderer/_git_sync.py` exists (270 lines, executable)
- Commits `ce7fcc9`, `fa43a67`, `4a82e03`, `260804e` all present in git history
- All three task commits pass pre-commit hooks (yamllint, shellcheck, Validate Add-on config.yaml Schema, Validate
  Add-on Versioning)
