---
phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
plan: 05
subsystem: infra
tags: [herdr, tmux-removal, ttyd, sshd, home-assistant-addon, bashio, verify-harness]

requires:
  - phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
    provides: "23-01: Claude auth exports in run.sh, versions.json/MOTD block, Docker verify harness with stub Supervisor"
provides:
  - "herdr 0.9.3 as sha256-verified release binary; version and both digests as Dockerfile ARG defaults mirrored in build.yaml"
  - "coding-assistants/coding-assistants-attach: the single attach-or-create wrapper (ttyd and SSH hooks), plain fish fallback"
  - "run.sh herdr server respawn loop with the add-on environment, workspace main created before sshd/ttyd"
  - "previous multiplexer removed (package, config, hooks, ttyd command); herdr in TOOLS.md, info.html, MOTD, versions.json, backup_exclude"
  - "harness: ca_pty_probe, scenarios drift, herdr-core, herdr-attach, surface, legacy_multiplexer_sweep (file-list function)"
affects: [23-06, 23-07, 23-08, 23-09]

actuals:
  tokens: 10600
  tasks: 3
  commits: 3

plan_head_before: 8a44313395ce2d30e87f3935f37439cb5aebf16d
plan_head_after: 0746b8aa655a400bc6a85f019e58b85358dc3b21
commits: 3

tech-stack:
  added: [herdr 0.9.3 (static release binary, sha256-pinned)]
  patterns:
    - "server owned by run.sh (started after all exports so the server env is every pane's env), clients only attach"
    - "respawn loop with `|| rc=$?` so errexit does not end it; clients degrade to a plain fish shell when no server answers"
    - "pins as Dockerfile ARG defaults mirrored in build.yaml, drift-checked with a negative control (CI forwards only the standard build args)"
    - "pty probe: concurrent clients each in a real pseudo-terminal inside the container, reporting comm/alive/bytes/text"

key-files:
  created:
    - coding-assistants/coding-assistants-attach
  modified:
    - coding-assistants/Dockerfile
    - coding-assistants/build.yaml
    - coding-assistants/run.sh
    - coding-assistants/TOOLS.md
    - coding-assistants/info.html
    - coding-assistants/config.yaml
    - internal/verify-coding-assistants.sh
  deleted:
    - coding-assistants/tmux.conf

key-decisions:
  - "The wrapper never starts a server; with no server after ~8 s it prints a message and `CODING_ASSISTANTS_NO_ATTACH=1 exec fish` so the profile hooks do not re-capture the fallback shell"
  - "`coding-assistants-attach --ensure` returns non-zero when no server answers or workspace main cannot be created; run.sh logs a warning instead of aborting (D-07)"
  - "No herdr config.toml is written by the add-on (D-02); the harness asserts it does not exist before the first client attached"
  - "Static harness scenarios (drift) skip the image build and the docker requirement"

requirements-completed: [D-01, D-02, D-06, D-07, D-08]

coverage:
  - id: D1
    description: "herdr 0.9.3 installed as a digest-verified binary; pins mirrored in build.yaml and checked for drift (negative controls fail as required)"
    requirement: D-06
    verification:
      - kind: command
        ref: "bash internal/verify-coding-assistants.sh drift (4/4 PASS incl. two negative controls); docker build with sha256sum -c OK"
        status: pass
    human_judgment: false
  - id: D2
    description: "run.sh owns the herdr server: workspace main at /homeassistant, fish panes with SHELL, HA_URL, HERDR_ENV, oauth token and PATH, respawn after kill -9"
    requirement: D-01
    verification:
      - kind: command
        ref: "bash internal/verify-coding-assistants.sh herdr-core"
        status: pass
    human_judgment: false
  - id: D3
    description: "Two concurrent clients attach to one session and leave exactly one workspace main; a missing server degrades to a plain fish shell"
    requirement: D-07
    verification:
      - kind: command
        ref: "bash internal/verify-coding-assistants.sh herdr-core (ca_pty_probe, shared session and fallback checks)"
        status: pass
    human_judgment: false
  - id: D4
    description: "SSH login hooks (bash and fish) and ttyd call the wrapper; escape variables keep nested and scripted shells out; a real sshd round trip starts a herdr client"
    requirement: D-01
    verification:
      - kind: command
        ref: "bash internal/verify-coding-assistants.sh herdr-attach"
        status: pass
    human_judgment: false
  - id: D5
    description: "The previous multiplexer is absent from package list, image, repository config and all code and UI files; no replacement config, no fallback"
    requirement: D-08
    verification:
      - kind: command
        ref: "bash internal/verify-coding-assistants.sh herdr-attach surface (sweep over Dockerfile, nginx.conf, run.sh code lines, TOOLS.md, info.html)"
        status: pass
    human_judgment: false
  - id: D6
    description: "TOOLS.md, info.html, MOTD, versions.json and backup_exclude describe herdr"
    requirement: D-07
    verification:
      - kind: command
        ref: "bash internal/verify-coding-assistants.sh surface"
        status: pass
    human_judgment: false
  - id: D7
    description: "The attach experience in a real browser and a real SSH client (herdr onboarding dialog on first start, key feel, detach)"
    requirement: D-02
    verification: []
    human_judgment: true
    rationale: "The harness proves process-level behaviour in pseudo-terminals; nothing renders the TUI in the HA web terminal or checks usability. Belongs in the phase 23-09 human verification."

duration: 57min
completed: 2026-10-11
status: complete
---

# Phase 23 Plan 05: herdr replaces tmux Summary

**herdr 0.9.3 runs as a respawning server owned by run.sh (add-on environment in every pane), SSH and the web terminal share one session through the single `coding-assistants-attach` wrapper, and the previous multiplexer is gone from image and code; 119 harness checks pass.**

## Performance

- **Duration:** about 57 min (mostly three image builds; the build with the apt change is a full rebuild of about 12 min)
- **Started:** 2026-10-11T16:34Z
- **Completed:** 2026-10-11T17:31Z
- **Tasks:** 3 (1 tracer, 2 auto)
- **Files modified:** 7 modified, 1 created, 1 deleted

## Accomplishments

- Dockerfile: `ARG HERDR_VERSION/HERDR_SHA256_X86_64/HERDR_SHA256_AARCH64` defaults plus a `RUN` that picks the digest by
  `uname -m` (anything else fails), verifies with `sha256sum -c` and requires `herdr --version` to print the pin. The
  digests were re-checked against the GitHub release asset digests of `v0.9.3` before pinning. build.yaml mirrors the
  three values; scenario `drift` fails when they diverge (negative controls: a changed value, a missing key).
- `coding-assistants-attach` (POSIX sh, shellcheck-clean, mode 100755): defaults for XDG/locale/TERM/PATH, waits up to
  about 8 s for a running server (`herdr status --json`), recreates `main` at `/homeassistant` under `flock` when the
  session is empty, then `exec herdr`. Without a server it prints a message and starts a plain fish shell with
  `CODING_ASSISTANTS_NO_ATTACH=1`. `--ensure` does the workspace step only.
- run.sh: `herdr server` in a respawn loop started after every export (before sshd/ttyd) with `SHELL=/usr/bin/fish` and
  the UTF-8 locale for that command only; `coding-assistants-attach --ensure` creates `main` before the first client.
  Bash and fish SSH hooks and the ttyd command all go through the wrapper (hooks guarded by `SSH_CONNECTION`, a tty or
  interactive shell, no `HERDR_ENV`, no `CODING_ASSISTANTS_NO_ATTACH`).
- Removal (D-08): apt package, `tmux.conf` file and COPY block, both SSH hooks, the ttyd command. No herdr config is
  written (D-02): the harness asserts `/data/.config/herdr/config.toml` does not exist before any client attached.
- Surface: TOOLS.md herdr bullet, info.html (Claude Code and herdr rows, `ttyd + herdr`), MOTD and `versions.json` with
  `herdr`, `backup_exclude` for herdr sockets, logs and session snapshots.
- Harness: `ca_pty_probe`, scenarios `drift` (static, skips the image build), `herdr-core`, `herdr-attach` (real sshd
  round trip with a throwaway key), `surface`, and `legacy_multiplexer_sweep FILE...` which 23-08 can extend to the docs.

## Task Commits

1. **Task 1 (tracer): herdr binary, wrapper, server bootstrap** - `8352c24` (feat)
2. **Task 2: ttyd/SSH through the wrapper, previous multiplexer removed** - `e7ad065` (feat)
3. **Task 3: user-visible surface** - `0746b8a` (feat)

Tracer gate: `bash internal/verify-coding-assistants.sh drift herdr-core` was green against a freshly built image before
Task 2 started (automated verify only, `gate` not `blocking-human`): tracer verified end-to-end, expansion continued.

## Verification

Final run on a rebuilt image (after the prettier re-wrap of TOOLS.md): `bash internal/verify-coding-assistants.sh all`
exits 0 with 119 PASS and no FAIL, covering `drift herdr-core herdr-attach surface` and the earlier `claude-*` and
`mcp-*` scenarios. shellcheck (wrapper, run.sh, harness), hadolint with the plan's ignore list and yamllint
(`.yamllint.yml`) are clean. All `<acceptance_criteria>` of the three tasks were re-run and pass.

## Deviations from Plan

### Auto-fixed / adjusted

**1. [Rule 3 - Blocking] Wrapper COPY placed at the end of the Dockerfile, not next to the HA API tools block**
- **Found during:** Task 1 (GitHub API budget: 60 unauthenticated calls per hour, one full build uses about 12)
- **Issue:** a COPY next to the HA API tools block would invalidate every download layer after it on each wrapper edit
- **Fix:** the `COPY coding-assistants-attach` + `chmod` block sits in the late block with the SSH config (a block of its
  own, as the plan asks), so wrapper edits only rebuild cheap layers; the herdr block follows the ttyd block as planned
- **Files modified:** coding-assistants/Dockerfile
- **Commit:** `8352c24`

**2. [Rule 2 - Missing critical] `--ensure` reports failure; static scenarios skip the image build**
- **Found during:** Task 1
- **Issue:** the plan makes run.sh warn when `--ensure` fails, which needs a non-zero exit; and `drift` is documented as
  "static, no Docker" but the harness always built the image first
- **Fix:** `--ensure` exits 1 when no server answers or `main` cannot be created; `STATIC_SCENARIOS` makes the harness skip
  the build and the docker requirement when only static scenarios are selected
- **Commit:** `8352c24`

**3. [Rule 3 - Blocking] prettier re-wrapped TOOLS.md at the first commit attempt**
- **Found during:** Task 3 commit
- **Fix:** staged the hook's re-wrap (lines stay within 120 characters), committed; a rebuilt image and the full run
  re-proved the Claude `CLAUDE.md` block equals the final TOOLS.md
- **Commit:** `0746b8a`

**Total deviations:** 3 (2 blocking, 1 missing critical). **Impact:** none on scope or behaviour.

## Authentication Gates

None.

## Issues Encountered

- The executor runs inside the user's own herdr (`HERDR_SOCKET_PATH` is set there), so a first read-only probe of
  `herdr status` talked to the user's real server (workspace list only, nothing mutated). All further herdr
  experiments ran inside the verify containers.
- The yamllint relaxed profile reports one pre-existing 81-column warning on `config.yaml` line 2 (description); the repo
  `.yamllint.yml` is clean.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register. T-23-08 (tampering): pinned version plus `sha256sum -c` per architecture, digests
re-checked. T-23-09: the server is started by run.sh only, tokens stay in process environments (harness proves the
pane environment). T-23-10: each hook guard is exercised by a test (`NO_ATTACH`, `HERDR_ENV`, no `SSH_CONNECTION`, fallback
shell not re-captured). T-23-11: kill -9 respawn proven within 20 s.

## Next Phase Readiness

23-06 can add the plugin build steps after the herdr block; the server loop is where plugin linking and the startup hooks
belong (`herdr plugin link` needs no running server and must precede the server start). 23-08 documents the herdr
onboarding dialog on first start (D-02, nothing suppressed), the SSH escape hatch `ssh -t host bash --noprofile` and
`CODING_ASSISTANTS_NO_ATTACH=1`, and the prefix keys; it also extends `legacy_multiplexer_sweep` to README.md and DOCS.md,
which still mention the old multiplexer. A clean `herdr server stop` restores the session, `kill -9` does not (empty
session, recreated by the next client through the wrapper).

## Self-Check: PASSED

- FOUND: coding-assistants/coding-assistants-attach (git mode 100755), coding-assistants/Dockerfile, coding-assistants/build.yaml,
  coding-assistants/run.sh, coding-assistants/TOOLS.md, coding-assistants/info.html, coding-assistants/config.yaml,
  internal/verify-coding-assistants.sh; coding-assistants/tmux.conf is gone
- FOUND commits: 8352c24, e7ad065, 0746b8a
