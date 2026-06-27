# Phase 6: Git Integration - Context

**Gathered:** 2026-06-27 **Status:** Ready for planning

<domain>
## Phase Boundary

Each namespace entry in the `directories` list gains optional git synchronization: a one-shot pull at startup
(`git_pull: true`) and/or a periodic background pull loop (`git_pull_interval: N` seconds). Git errors must never block
nginx from starting or a namespace from being served — failures log a warning and the locally cached Markdown is served
as-is. Optional `git_url` allows first-time `git clone` when the path is not yet a repo. SSH/private-repo auth is
explicitly out of scope (HTTPS public repos only in v1.1).

</domain>

<decisions>
## Implementation Decisions

### Schema Extensions

- **D-01:** Each `directories[]` entry gains two optional fields for git sync:
  - `git_pull: bool` — default `false`; when `true`, run `git pull --ff-only` at startup before nginx starts.
  - `git_pull_interval: int` — default `0` (disabled); when `> 0`, spawn a periodic background loop pulling every N
    seconds. Both fields are independently usable (startup-only, periodic-only, or both).
- **D-02:** A new optional `git_url: str` field on each `directories[]` entry enables first-time clone. Semantics:
  - If `git_pull: true` (or `git_pull_interval > 0`) AND the path is not a git repo AND `git_url` is set →
    `git clone <git_url> <path>` is executed instead of `git pull`.
  - If `git_url` is unset and the path is not a repo → log a warning, serve whatever local content exists (including
    empty dir → namespace serves an empty Docsify SPA).
- **D-03:** HA schema in `config.yaml` adds `git_pull: bool`, `git_pull_interval: int`, `git_url: str?` to the
  `directories[]` entry shape. All three are optional, no migration needed for existing configurations.

### Code Structure

- **D-04:** A new Python helper `markdown-renderer/_git_sync.py` owns all git operations. Rationale: keeps
  `generate_nginx.py` focused on nginx config; git is an independent concern; subprocess calls to `git` are easier to
  test in isolation. Both startup pull and periodic sync call into `_git_sync.py`.
- **D-05:** `run.sh` calls `python3 /app/_git_sync.py` (after `generate_nginx.py`, before `exec nginx`) for the one-shot
  startup pull. Background periodic loop runs in `run.sh` as a single
  `while true; do sleep <min_interval>; python3 /app/_git_sync.py --periodic; done &` shell loop — one background
  process, not one per namespace.

### Detection & Sync Logic

- **D-06:** Before any `git pull`, `_git_sync.py` probes with `git -C "$path" rev-parse --git-dir`. Exit 0 = git repo →
  proceed with `git pull --ff-only`. Non-zero exit = not a repo → check `git_url`; if set, run `git clone`; if unset,
  log warning and skip.
- **D-07:** All git operations run via `subprocess.run()` with `check=False`; non-zero exit codes translate to
  `WARNING:` log lines but never propagate as exceptions. GIT-05 ("git pull errors are logged but do not prevent the
  namespace from being served") is the contract.

### Periodic Sync Mechanics

- **D-08:** Periodic sync uses one single background loop in `run.sh`, not one loop per namespace. The loop calls
  `_git_sync.py --periodic` which iterates all namespaces with `git_pull_interval > 0` and pulls each one whose
  individual interval has elapsed since its last pull. Sleep interval for the outer loop = `min(git_pull_interval)`
  across all configured namespaces (clamped to a minimum of 5 seconds).
- **D-09:** Per-namespace interval tracking is in-memory only (a dict in `_git_sync.py`). Interval state is NOT
  persisted across restarts — each add-on restart resets all `last_pull` timestamps; the first periodic iteration pulls
  every namespace once if `git_pull_interval > 0`. This matches the existing v1.1 philosophy (no extra state files in
  `/data`).
- **D-10:** Log throttling: every periodic iteration logs each failure as `WARNING: git pull failed for <name>: <err>`.
  HA Supervisor already rate-limits logs; no in-add-on deduplication needed.
- **D-11:** Signal handling: `run.sh` traps SIGTERM/SIGINT, kills the background loop's PID, then forwards the signal to
  nginx (which is PID 1 via `exec`). Prevents orphaned periodic loops after HA Supervisor restart.

### Runtime Requirements

- **D-12:** `git` binary is added to the Dockerfile via `apk add --no-cache git` (extending the existing
  `apk add --no-cache nginx curl tar` line). The binary is always present in the image even when no namespace uses git
  sync (GIT-03 forbids _invocation_ of git when not configured; installation is fine — matches alpine-base size
  trade-off).
- **D-13:** `git config --global --add safe.directory '*'` runs in `run.sh` before any git operation (per GIT-02).
  Handles the mounted-volume UID mismatch (git 2.35.2+ refuses to operate on repos owned by a different UID by default).

### the agent's Discretion

- Exact Dockerfile ARG for pinning a git version (default: latest in alpine3.20).
- Exact wording of warning messages in `_git_sync.py`.
- How `_git_sync.py` handles a `git_url` that fails to clone (timeout? retry once? single attempt?) — recommend single
  attempt with clear warning, matching GIT-05's "non-blocking" contract.
- The exact shell-quoting pattern for `git -C "$path"` invocations from `_git_sync.py` (Python subprocess `list` form
  recommended to avoid shell-escaping pitfalls).
- Whether `_git_sync.py` uses `os.execvp` style or `subprocess.run` style for git invocations (recommend
  `subprocess.run` with explicit args for testability).

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements

- `.planning/REQUIREMENTS.md` §GIT — GIT-01..05 are the Phase 6 acceptance criteria
- `.planning/ROADMAP.md` Phase 6 — Phase goal + success criteria + dependency on Phase 5

### Prior Phase Decisions (carry forward)

- `.planning/phases/04-scaffold-ingress-validation/04-CONTEXT.md` D-01 — `directories: list({name, path})` schema is
  already in place; git fields extend this entry shape in Phase 6
- `.planning/phases/04-scaffold-ingress-validation/04-CONTEXT.md` D-03, D-04 — `generate_nginx.py` runs before nginx
  starts; `run.sh` is two-stage (Python → exec)
- `.planning/STATE.md` "share:rw vs share:ro" flag — confirmed in Phase 5: `map: share:rw config:rw media:rw` already in
  `config.yaml`, so `.git` writes from git pull work without further volume changes

### Existing Add-on Patterns (read before writing any file)

- `markdown-renderer/generate_nginx.py` — canonical pattern for Python helpers reading `/data/options.json`; follow the
  same module-docstring + type-hints + `pathlib.Path` + `if __name__ == '__main__': sys.exit(main())` structure for
  `_git_sync.py`
- `markdown-renderer/run.sh` — current two-stage pattern (Python gen → exec nginx); extend with new git-sync stage
  between gen and exec, plus background periodic loop
- `markdown-renderer/config.yaml` — current options schema; extend `directories[]` entry shape and `schema:` block
- `markdown-renderer/Dockerfile` — current `apk add --no-cache nginx curl tar` line; extend with `git`
- `phone-logger/generate_config.py` — secondary reference for the Python-helper-from-options.json pattern
- `phone-logger/run.sh` — secondary reference for two-stage run.sh

### Conventions

- `.planning/codebase/CONVENTIONS.md` — Python style (PEP 8 manually), 120-char limit, shellcheck ignores (`SC1091`,
  `SC2034`), Dockerfile label block
- `.planning/codebase/CONVENTIONS.md` §Versioning — if Phase 6 changes ship as a new add-on version, use
  `make update-version ADDON=markdown-renderer VERSION=1.1.0`

### Out of Scope References (for clarity, NOT for action)

- `.planning/REQUIREMENTS.md` §"Future Requirements" — SSH key handling for private git repos is explicitly deferred to
  v1.2; Phase 6 supports HTTPS public repos only

</canonical_refs>

## Existing Code Insights

### Reusable Assets

- **`generate_nginx.py`** — existing per-namespace iteration loop in `main()` (lines 487-490) is the structural template
  for `_git_sync.py`'s per-namespace iteration. Both scripts read the same `/data/options.json` and walk the same
  `directories[]` list.
- **`validate_directories()`** in `generate_nginx.py` — produces the canonical validated namespace list. Could be
  imported by `_git_sync.py` (rather than re-reading + re-validating options.json), but per D-04 the cleanest split is
  two independent scripts each reading options.json themselves.
- **`run.sh`** — already runs as a shell script with `set -e`; the new git-sync stage slots in between
  `generate_nginx.py` and `exec nginx`. Background loop syntax (`&` + `wait` or kill on trap) is standard POSIX sh.

### Established Patterns

- **Two-stage Python → exec** (Phase 4 D-04): the new `_git_sync.py` is invoked from `run.sh` exactly like
  `generate_nginx.py`. Same `flush=True` print discipline for containerized observability.
- **`/data/options.json` as single source of truth**: both Python scripts read this; no state files in `/data` for git
  interval tracking (D-09).
- **apk-only package additions in Dockerfile**: extending the existing `apk add --no-cache` line with `git` keeps the
  layer flat.
- **Container runs as root**: mounted volumes from `/share`, `/config`, `/media` are root-owned on the HA host, so the
  add-on's root user can write `.git/` updates without per-namespace chmod. (GIT-02's `safe.directory '*'` is the
  belt-and-braces measure for any edge case.)

### Integration Points

- `markdown-renderer/config.yaml` `options:` + `schema:` blocks — must add `git_pull`, `git_pull_interval`, `git_url` to
  the `directories[]` entry.
- `markdown-renderer/Dockerfile` line 12 — extend the `apk add` list with `git`.
- `markdown-renderer/run.sh` — add git-sync invocation, periodic loop, signal trap.
- `markdown-renderer/DOCS.md` — document the three new fields per entry, the auto-clone behavior, the periodic sync
  semantics, and the failure modes.
- `markdown-renderer/README.md` — add git sync to the features list; mention v1.2-deferred SSH private repo support.

<specifics>
## Specific Ideas

- User confirmed: auto-clone with optional `git_url` (not required-clone, not required-url) — flexible fallback when
  path is not yet a repo.
- User confirmed: new `_git_sync.py` helper (not extension of `generate_nginx.py`, not shell function) — keeps concerns
  separated and testable.
- User confirmed: single background loop with `min(interval)` sleep (not one loop per namespace) — simpler signal
  handling, no concurrent pulls.
- User confirmed: probe via `git rev-parse --git-dir` before any pull/clone (not "just run git pull and ignore errors")
  — clearer log messages.
- User confirmed: log every periodic failure (no state-transition dedup) — let HA Supervisor handle rate limiting.

</specifics>

<deferred>
## Deferred Ideas

- SSH key handling for private git repos — Future (v1.2); HTTPS public repos only in v1.1 (per REQUIREMENTS Future
  Requirements + Out of Scope)
- Webhook-triggered periodic git sync (vs time-based polling) — Future; out of v1.1 scope
- Per-namespace git auth tokens (PAT in config) — Future (v1.2); adds a sensitive-value handling surface
- Git LFS support — Not mentioned in requirements; out of scope unless surfaced as user need
- Pre-commit hooks or auto-push from inside the add-on — Out of scope; this is read/pull only

</deferred>

---

_Phase: 06-git-integration_ _Context gathered: 2026-06-27_
