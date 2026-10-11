---
phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
plan: 08
subsystem: docs
tags: [documentation, changelog, herdr, claude-code, herdr-web-service, verify-harness]

requires:
  - phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
    provides: "23-01..07: Claude Code, MCP registration, herdr, plugins at pinned commits, /services/ web UI, herdr_web_password"
provides:
  - "DOCS.md documenting the three new options, Claude Code, the MCP existing-entries-win limitation, herdr, the plugin opt-ins, the /services/ web UI (blast radius, network exposure) and the migration from tmux"
  - "CHANGELOG.md [Unreleased] Added/Changed/Removed with the stale Claude Code removal reconciled"
  - "add-on README, root README entry, config.yaml description and TOOLS.md plugin line describing Claude Code and herdr"
  - "harness scenario docs (static) with the legacy-tool sweep extended to the documentation"
affects: [23-09]

actuals:
  tokens: 11500
  tasks: 2
  commits: 2

plan_head_before: 0494467cb8322ee59d0931742ef9b6562d637568
plan_head_after: 0ad4df5af422b72757e1119fffd2af0817d4348c
commits: 2

tech-stack:
  added: []
  patterns:
    - "documentation claims checked against the shipped files AND against the tool itself: herdr keys against herdr's 0.9.3 docs, the claude-limits TOML snippet with `herdr config check` in a throwaway container, `claude mcp remove --scope` against the bundled claude binary"
    - "static harness scenario: headings, commands, plugin paths and pins in the docs must match the shipped Dockerfile/build.yaml/config.yaml; legacy-tool sweep with section stripping and two negative controls"

key-files:
  created: []
  modified:
    - coding-assistants/DOCS.md
    - coding-assistants/CHANGELOG.md
    - coding-assistants/README.md
    - coding-assistants/TOOLS.md
    - coding-assistants/config.yaml
    - README.md
    - internal/verify-coding-assistants.sh

key-decisions:
  - "The three plugins are documented as linked-but-not-configured with copy-paste opt-ins; the web-service plugin's own setup wizard is explicitly advised against (tunnels, installers, Claude status line) because the add-on sets the password through herdr_web_password"
  - "The sweep strips the `## Migrating from tmux` section by exact heading before scanning DOCS.md, so the migration section is the only place the old tool is named; the root README entry is swept via an awk extract of its `### [Coding Assistants]` block"
  - "claude-limits' missing licence is stated in DOCS.md (one sentence) because the user accepted the redistribution risk knowingly and readers deserve the same fact"

requirements-completed: [D-02, D-04, D-08]

coverage:
  - id: F1
    description: "DOCS.md covers the options (precedence, env_vars interplay, process-environment-only), Claude Code (native installer, updates and persistence, login, state paths, CLAUDE.md block, no settings defaults), MCP limitation and refresh procedure, herdr (shared session, keys, onboarding, respawn, escape hatch, herdr update), the plugin opt-ins with exact commands and snippet, the web UI with blast radius and network exposure, and the tmux migration"
    requirement: D-08
    verification:
      - kind: command
        ref: "bash internal/verify-coding-assistants.sh docs surface drift (all PASS, 56 checks incl. negative controls)"
        status: pass
    human_judgment: false
  - id: F2
    description: "CHANGELOG [Unreleased] records Added/Changed/Removed; the stale 'Removed: Claude Code CLI' bullet is replaced by an Added entry that keeps the 'legacy /data/claude contents are copied once, not deleted' sentence; released sections and links untouched"
    requirement: D-08
    verification:
      - kind: command
        ref: "pre-commit run (prettier, markdownlint-cli2) exit 0; git diff of CHANGELOG.md limited to [Unreleased]"
        status: pass
    human_judgment: false
  - id: F3
    description: "add-on README, root README entry, config.yaml description (single line changed) and TOOLS.md describe Claude Code and herdr; no mention of the old tool outside the migration section; versions untouched"
    requirement: D-02
    verification:
      - kind: command
        ref: "docs scenario sweep; make validate-versions exit 0; no shield/version line in the diff"
        status: pass
    human_judgment: false
  - id: F4
    description: "Documented behaviour that no automated check exercises: `claude update` against the real endpoint, the web UI in a real browser behind HA ingress, `subagent.watch.setup` actually editing the settings files, deleting auth.json returning the login to 503"
    verification: []
    human_judgment: true
    rationale: "These statements follow the plugin READMEs, the spike and the harness results, but were not run end to end; they belong to the 23-09 human verification"

duration: 45min
completed: 2026-10-11
status: complete
---

# Phase 23 Plan 08: Documentation of Claude Code, herdr, plugins and the web UI Summary

**DOCS.md, CHANGELOG.md, both READMEs, the config.yaml description and TOOLS.md now describe the shipped behaviour of the phase, including the deliberate non-automations, the MCP existing-entries-win limitation and the web UI's blast radius and network exposure; a static `docs` harness scenario keeps headings, commands, plugin paths and pins honest.**

## Performance

- **Duration:** about 45 min (22 min of it a full image build needed for the `surface` scenario)
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- DOCS.md: new option sections `claude_code_oauth_token`, `anthropic_api_key`, `herdr_web_password` (exported variable names,
  API key beats OAuth token, `env_vars` override, values only in the process environment, the plugin's password rules, option
  applied every start, removal does not delete the hash); `mcp_servers`, `zigbee2mqtt` and `mycli` text now covers Claude
  Code; new sections `Claude Code`, `herdr`, `herdr plugins`, `Web UI (/services/)` and `Migrating from tmux`; the SSH
  section and the tool table describe herdr and `claude`.
- Verified against the tools, not only against the repository: herdr keys against herdr's published 0.9.3 documentation
  (this corrected the research facts: `prefix+w` is "workspace navigation", the picker is `prefix+g`; splits are
  `prefix+v` / `prefix+minus`), the claude-limits snippet with `herdr config check` (`config: ok`) inside a throwaway
  container of the built image, `claude setup-token` and `claude mcp remove --scope user` against the bundled binary, the
  `subagent-watch` setup behaviour (backups named `<file>.subagent-watch.bak`, config validation and restore, `prefix+.`)
  against the plugin README in the image.
- CHANGELOG [Unreleased]: Added (Claude Code, auth options, MCP registration, herdr, plugins, web UI, escape hatch), Changed
  (shared herdr session), Removed (tmux); the stale Claude Code removal is gone.
- Add-on README, root README entry, `config.yaml` description (one line) and TOOLS.md plugin line updated.
- Harness scenario `docs` (static, part of `all`): headings, commands and paths, option names against the schema, plugin
  directories against the Dockerfile, documented pins against build.yaml, legacy-tool sweep over DOCS.md (migration section
  stripped), README.md, the root README entry and TOOLS.md, with a negative control for a mention outside and one inside the
  migration section.

## Task Commits

1. **Task 1: DOCS.md, CHANGELOG.md and the docs scenario** - `d1293bf` (docs)
2. **Task 2: READMEs, config.yaml description, TOOLS.md plugin line** - `0ad4df5` (docs)

## Verification

- `bash internal/verify-coding-assistants.sh docs surface drift` against a freshly built image (reused through
  `CA_VERIFY_IMAGE`): ALL CHECKS PASSED, no FAIL.
- `pre-commit run --files` over all seven touched files: exit 0 (prettier re-wrapped DOCS.md and CHANGELOG.md; the rewrapped
  text was reviewed and staged). `awk 'length > 120'` over DOCS.md and CHANGELOG.md outside tables: 0.
- `shellcheck -e SC1091 -e SC2034 internal/verify-coding-assistants.sh`: clean.
- `make validate-versions`: passed, no version line touched. `git diff --stat HEAD -- coding-assistants/config.yaml` showed a
  single changed line. All acceptance criteria of both tasks re-run and pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Task 1's verify depends on Task 2's files**
- **Found during:** Task 1 verification
- **Issue:** the `docs` scenario sweep (required by Task 1) also scans the add-on README.md and TOOLS.md, which Task 2 edits;
  Task 1 alone cannot pass its own verify.
- **Fix:** both tasks were edited before the harness ran and verified once on the combined tree; the commits stay separate.
  The Task 1 commit alone still has the old tool named in the add-on README.
- **Commit:** `d1293bf`, `0ad4df5`

**2. [Rule 1 - Bug] Research facts corrected against the sources**
- **Found during:** Task 1 (cross-check against herdr's docs and the image)
- **Issue:** `prefix+w` was listed as "workspace picker" in the plan's facts; herdr documents it as workspace navigation
  (`prefix+g` is the goto picker). The plan also said the OAuth token reaches "every process the add-on starts"; sshd does not
  hand its own environment to login sessions, so the text says the web terminal, the herdr server and its panes, and that a
  plain SSH shell from the escape hatch should not be expected to have it.
- **Files modified:** coding-assistants/DOCS.md
- **Commit:** `d1293bf`

**3. [Rule 3 - Blocking] A full image build was required for `surface`**
- **Found during:** verification
- **Issue:** the only local harness images predated herdr; `surface` reads `versions.json` and the MOTD of a real container.
- **Fix:** built `coding-assistants-verify:2308` by hand with the harness's build arguments (about 22 min, inside the GitHub API
  budget) and reused it via `CA_VERIFY_IMAGE`. The image is still present (2.8 GB) for 23-09 to reuse or remove; the harness
  scratch directory `/var/tmp/ca-verify-23-08` was removed. TOOLS.md changed after the build, which `docs`, `surface` and `drift`
  do not read from the image; `claude-state` was not re-run.
- **Files modified:** none

**4. [Rule 2 - Missing critical] Extra harness assertions beyond the plan list**
- Option names are checked against the config.yaml schema, the documented plugin pins against build.yaml, and the sweep has
  negative controls; the root README entry is swept through an awk extract. Commit `d1293bf`.

**Total deviations:** 4 (2 blocking, 1 bug, 1 missing critical). **Impact:** none on scope.

## Authentication Gates

None.

## Issues Encountered

- A shell `-c` invocation of the bundled `claude` binary was blocked by the harness's removal safety check (the script text
  contained `mcp remove`); the same checks ran as direct `docker run --entrypoint` calls instead.

## Known Stubs

None.

## Deferred Items

- Pre-existing and not fixed (already in the 23-03 summary): DOCS.md still says the zigbee2mqtt `MQTT_*` variables are "injected
  into every session", but run.sh appends them to the profile files before those files are truncated, so they are lost. Only the
  Claude Code entry (explicit `env`) is unaffected; the DOCS sentence about it is accurate.
- Pre-existing: `config.yaml` has no `args`/`env` in the `mcp_servers` schema although DOCS.md documents `env` (23-03 note).
- Statements not verified end to end (see coverage F4): `claude update` against the real endpoint, the web UI in a browser,
  `subagent.watch.setup` editing real files, and `auth.json` deletion returning the login to 503.

## Threat Flags

None. T-23-29 (placeholders only: `<token>`, `<ha-host>`, `<name>`; gitleaks passed on both commits) and T-23-30 (the blast
radius, the hassio-network exposure of `/terminal/` and `/services/`, the user-run plugin setup with its backups, all stated in
DOCS.md and asserted by the `docs` scenario) are mitigated as planned.

## Next Phase Readiness

23-09 owns the version bump (`make update-version`, after the user confirms its size) and the human verification list:
the Services tab in real HA ingress, the herdr first-start dialog in the web terminal and over SSH, `claude update` and a
login in the container, and the claims listed in coverage F4.

## Self-Check: PASSED

- FOUND: coding-assistants/DOCS.md, coding-assistants/CHANGELOG.md, coding-assistants/README.md, coding-assistants/TOOLS.md,
  coding-assistants/config.yaml, README.md, internal/verify-coding-assistants.sh
- FOUND commits: d1293bf, 0ad4df5
