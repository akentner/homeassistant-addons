---
phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
plan: 01
subsystem: infra
tags: [claude-code, home-assistant-addon, docker, bashio, s6, persistence, verify-harness]

requires:
  - phase: 22-cups-paperless-ngx-pdf-document-upload
    provides: Docker verify-script conventions (stub server, trap cleanup, PASS/FAIL accumulator)
provides:
  - Claude Code (native installer) in the coding-assistants image, seeded from /opt/claude-initial
  - Persistent self-updating launcher layout (/data/.local/share/claude/versions, launcher re-pointed on every start)
  - Persisted ~/.claude and ~/.claude.json with one-time legacy migration
  - TOOLS.md marker block in /data/.claude/CLAUDE.md (rewritten on every start, user text preserved)
  - Optional claude_code_oauth_token / anthropic_api_key add-on options exported to the process environment only
  - internal/verify-coding-assistants.sh Docker harness with a stub Supervisor (reused by later plans of phase 23)
affects: [23-02, 23-03, 23-05, 23-06, 23-07, 23-09]

actuals:
  tokens: 8800
  tasks: 3
  commits: 3

plan_head_before: 910ea08733e450697e6eea58458a7073e4969ff9
plan_head_after: 1c1bfe396799d79214e20ca6fd594acf13d2c3bc
commits: 3

tech-stack:
  added: [Claude Code native installer (latest at build time, unpinned)]
  patterns:
    - "Seed in /opt/<tool>-initial, run.sh copies it into /data only when strictly newer (sort -V) and re-creates the launcher symlink into the persistent versions dir on every start"
    - "Docker verify harness: real run.sh against a stub Supervisor API (SUPERVISOR_API/SUPERVISOR_TOKEN), restart modelled as rm -f + fresh run on the same /data"
    - "Marker block (begin/end HTML comments) injected into a user-owned file with function replacement"

key-files:
  created:
    - internal/verify-coding-assistants.sh
  modified:
    - coding-assistants/Dockerfile
    - coding-assistants/run.sh
    - coding-assistants/config.yaml
    - coding-assistants/TOOLS.md

key-decisions:
  - "Claude persistence layout is /data/.local/share/claude/versions with ~/.local/bin/claude pointing INTO it (user decision 1, replaces the /data/claude/bin text of ROADMAP/D-04), so `claude update` really replaces the running version"
  - "Claude is not version-pinned (default A9): latest at build time like opencode, updater keeps it current"
  - "Legacy /data/claude/.claude* is copied once when the new paths are absent and never deleted (default 7)"
  - "Auth options are named like the env vars (claude_code_oauth_token, anthropic_api_key) and live only in the run.sh process environment"
  - "Harness scenario names: claude-launcher, claude-state, claude-auth; a bare prefix (claude) expands to the group"

patterns-established:
  - "bashio runs run.sh with errexit + pipefail: any pipeline that may legitimately yield nothing (find|grep|sort, claude --version|head) must end in || true"
  - "Harness captures must not use 2>&1 on docker calls: podman's docker emulation prints a notice to stderr"

requirements-completed: [D-03, D-04]

coverage:
  - id: D1
    description: "Claude Code runs from the persistent launcher ~/.local/bin/claude -> /data/.local/share/claude/versions/<ver>; version shown in MOTD and versions.json"
    requirement: D-04
    verification:
      - kind: integration
        ref: "bash internal/verify-coding-assistants.sh claude-launcher"
        status: pass
    human_judgment: false
  - id: D2
    description: "Persisted newer version wins over the image seed; strictly newer seed is copied in; legacy ~/.claude state migrated once; persisted modes 0700/0600"
    requirement: D-04
    verification:
      - kind: integration
        ref: "bash internal/verify-coding-assistants.sh claude-state"
        status: pass
    human_judgment: false
  - id: D3
    description: "TOOLS.md injected into /data/.claude/CLAUDE.md as a block rewritten every start with user text preserved"
    requirement: D-03
    verification:
      - kind: integration
        ref: "bash internal/verify-coding-assistants.sh claude-state"
        status: pass
    human_judgment: false
  - id: D4
    description: "Optional auth options exported only into the process environment when non-empty; absent from profile files and logs"
    requirement: D-04
    verification:
      - kind: integration
        ref: "bash internal/verify-coding-assistants.sh claude-auth"
        status: pass
    human_judgment: false
  - id: D5
    description: "`claude update` actually replaces the running version inside the container (network-dependent, not exercised by the harness)"
    verification: []
    human_judgment: true
    rationale: "Needs the real update endpoint; the layout it depends on is proven, the update itself was reproduced only in research"

duration: 55min
completed: 2026-10-10
status: complete
---

# Phase 23 Plan 01: Claude Code in coding-assistants Summary

**Claude Code from the native installer with a persistent, self-updating launcher (seed in /opt/claude-initial, newest persisted version wins), persisted ~/.claude state, a rewritten TOOLS.md block in CLAUDE.md and env-only optional auth, all proven by a new Docker harness with a stub Supervisor.**

## Performance

- **Duration:** 55 min (dominated by two full image builds of the 46-step Dockerfile)
- **Started:** 2026-10-10T14:55:09Z
- **Completed:** 2026-10-10T15:50Z
- **Tasks:** 3 (1 tracer, 2 auto)
- **Files modified:** 5 (1 created)

## Accomplishments

- Dockerfile installs Claude Code with the native installer, moves the single ~250 MB binary to `/opt/claude-initial`, runs it once with `--version` (a corrupt download fails the build) and removes all per-user state from `/root`.
- run.sh seeds `/data/.local/share/claude/versions` only when the image seed is strictly newer (`sort -V`), re-creates `/root/.local/bin/claude` on every start pointing INTO that directory (so `claude update` takes effect and survives rebuilds), and puts the Claude version into the MOTD and `versions.json` (`claude` key already read by index.html).
- `~/.claude` and `~/.claude.json` are symlinks to `/data/.claude` (0700) and `/data/.claude.json` (0600); a legacy `/data/claude/.claude*` is copied once when the new paths are absent, never deleted.
- TOOLS.md is injected into `/data/.claude/CLAUDE.md` between `<!-- coding-assistants:begin/end -->` on every start, with a function replacement, user text outside the block untouched, idempotent.
- `claude_code_oauth_token` / `anthropic_api_key` (`password?`) are exported into the run.sh process environment only when non-empty and not `null`; `.local/share/claude/*` is excluded from backups.
- `internal/verify-coding-assistants.sh`: builds the image like CI, runs the real run.sh in containers against a stub Supervisor, scenarios `claude-launcher` (6 PASS), `claude-state` (20 PASS), `claude-auth` (11 PASS).

## Task Commits

1. **Task 1 (tracer): Claude Code end-to-end, persistent launcher, harness** - `7ec38d4` (feat)
2. **Task 2: ~/.claude persistence, legacy migration, TOOLS.md block** - `e4974e6` (feat)
3. **Task 3: optional auth options, backup exclusion** - `1c1bfe3` (feat)

## Files Created/Modified

- `coding-assistants/Dockerfile` - Claude native installer block, `/opt/claude-initial` seed, difftastic asset selection fix
- `coding-assistants/run.sh` - launcher bootstrap, state persistence, CLAUDE.md block, auth exports, MOTD/versions.json `claude`
- `coding-assistants/config.yaml` - two `password?` options, `backup_exclude` entry
- `coding-assistants/TOOLS.md` - `claude` entry
- `internal/verify-coding-assistants.sh` - harness (stub Supervisor, helpers, three scenarios)

## Decisions Made

See `key-decisions`. No settings.json default, permission option or model option was introduced (D-04).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] difftastic Dockerfile step broke on upstream asset rename**
- **Found during:** Task 1 (first harness image build)
- **Issue:** upstream difftastic 0.71.0 renamed the release asset to `difft-0.71.0-x86_64-unknown-linux-gnu.tar.gz`; the exact-name jq selector returned nothing and the whole image build failed at step 17, before the Claude block.
- **Fix:** select by pattern `^difft-(.+-)?x86_64-unknown-linux-gnu[.]tar[.]gz$` (accepts old and new name); verified the 0.71.0 gnu binary runs on Bookworm.
- **Files modified:** coding-assistants/Dockerfile
- **Commit:** 7ec38d4

**2. [Rule 1 - Bug] run.sh aborted silently under bashio's errexit + pipefail**
- **Found during:** Task 1 (first container run; container exited right after "Initialized opencode binary")
- **Issue:** `grep` finding no version in an empty persistent dir returned 1, which killed run.sh. bashio runs the script with errexit/pipefail.
- **Fix:** the pipelines that may legitimately yield nothing end in `|| true`; documented in a comment.
- **Files modified:** coding-assistants/run.sh
- **Commit:** 7ec38d4

**3. [Rule 2 - Missing critical] harness development knob `CA_VERIFY_DOCKER_ARGS`**
- **Found during:** Task 1 (proving "the scenario must be able to fail")
- **Fix:** optional env knob adding extra `docker run` options to every container; used to mount a run.sh without the launcher line, which made checks (a)-(c) FAIL as required. Not used in normal runs.
- **Files modified:** internal/verify-coding-assistants.sh
- **Commit:** 7ec38d4

**Total deviations:** 3 auto-fixed (1 blocking, 1 bug, 1 test-infrastructure). **Impact:** none on scope; the difftastic fix is pre-existing breakage outside the plan's files that blocked the mandatory local `docker build`.

## Issues Encountered

- The `docker` CLI on this host is podman's emulation: it prints a notice to stderr (so harness captures must not merge stderr) and `rmi` of a harness-tagged image drops the build cache. Development used a manually built `coding-assistants-verify:dev` tag plus `CA_VERIFY_IMAGE`; the final `bash internal/verify-coding-assistants.sh claude` run built its own image (cached layers) and passed.
- GitHub's unauthenticated API limit (60/h) is consumed by roughly 12 calls per full Dockerfile build (pre-existing `curl api.github.com` steps); not changed here.

## Verification Results

- `bash internal/verify-coding-assistants.sh claude` -> exit 0, 37 PASS lines, no FAIL (final run on the committed state; image built by the harness)
- `shellcheck -e SC1091 -e SC2034 coding-assistants/run.sh internal/verify-coding-assistants.sh` -> clean
- `hadolint --ignore DL3008 --ignore DL3018 --ignore DL3059 --ignore DL4006 --ignore DL3016 coding-assistants/Dockerfile` -> clean
- `yamllint -d relaxed coding-assistants/config.yaml` -> no errors (one pre-existing line-length warning)
- Task 1/2/3 acceptance greps all pass; negative proof for claude-launcher: run.sh without the launcher line -> FAIL on checks (a)-(c)

## Known Stubs

None.

## Threat Flags

None - no new network endpoints or trust boundaries beyond the plan's threat model (T-23-01..04 mitigated and asserted by the harness; T-23-02 accepted).

## Next Phase Readiness

The harness (`start_ca`, `restart_ca`, `ca_exec`, `ca_pid`, `ca_environ`, assertion helpers, group-prefix scenario selection) is ready for 23-03, 23-05, 23-06, 23-07 and 23-09. Open for later plans: real `claude update` inside a container (needs network), MCP registration into `~/.claude.json` (23-03).

## Self-Check: PASSED
