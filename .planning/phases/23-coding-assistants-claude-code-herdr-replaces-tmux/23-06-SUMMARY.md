---
phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
plan: 06
subsystem: infra
tags: [herdr, herdr-plugins, supply-chain-pins, bun, home-assistant-addon, bashio, verify-harness]

requires:
  - phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
    provides: "23-02: approved plugins and PIN lines; 23-04: sub-path patch and build sequence for herdr-web-service (VERDICT: GO); 23-05: herdr binary, run.sh server block, drift scenario"
provides:
  - "subagent-watch, claude-limits and the patched web-service checked out at pinned commits in /opt/herdr-plugins/<repository-name>"
  - "HERDR_SUBAGENT_WATCH_REF, HERDR_WEB_SERVICE_REF, HERDR_CLAUDE_LIMITS_REF as Dockerfile ARG defaults mirrored in build.yaml and covered by the drift scenario"
  - "run.sh links every plugin directory before the herdr server starts (link failure is a warning)"
  - "harness scenario plugins (registration, D-07 isolation, no config.toml / settings.json, subagent-watch launcher, claude-limits poller, web-service health / relative client / 503 login)"
affects: [23-07, 23-08, 23-09]

actuals:
  tokens: 4400
  tasks: 2
  commits: 2

plan_head_before: a19766d4eba9b974e094b707c6225827a9e0a873
plan_head_after: ab9a45731b0afc030000fe4f66731b48123b795a
commits: 2

tech-stack:
  added: ["herdr-subagent-watch c47d49b (MIT)", "herdr-claude-limits 9c0c9a1 (no licence, accepted by the user)", "herdr-web-service e9082b3 (MIT, patched, bun/vite build)"]
  patterns:
    - "plugin pins are commits fetched with `git fetch --depth 1 origin <sha>`, HEAD asserted equal to the ARG, .git removed"
    - "patch applied with `git apply --check` + `git apply` so a moved pin fails the build loudly"
    - "plugin link loop before the server start; failures only warn (D-07)"
    - "no config.toml and no settings.json written by the add-on (D-02, D-04, user decision 2)"

key-files:
  created: []
  modified:
    - coding-assistants/Dockerfile
    - coding-assistants/build.yaml
    - coding-assistants/run.sh
    - internal/verify-coding-assistants.sh

key-decisions:
  - "Plugin blocks sit after the global npm install (all download layers), not directly after the herdr block, so a pin bump does not re-run the GitHub-API-heavy download layers (60 calls/h budget); still after bun, git, jq, curl and Node which the plugins need"
  - "The drift scenario now asserts each pin key by name plus 40-character SHAs for the *_REF keys, instead of the previous hard-coded count of three"
  - "Plugin registration is read from `herdr plugin list --json` (ids sorted and compared as a set) and actions from `herdr plugin action list` (`.result.actions[]`)"

requirements-completed: [D-02, D-04, D-06, D-07]

coverage:
  - id: E1
    description: "All three approved plugins are installed at pinned commits, mirrored in build.yaml and drift-checked; REJECT lines do not exist (none were rejected)"
    requirement: D-06
    verification:
      - kind: command
        ref: "bash internal/verify-coding-assistants.sh drift (all PASS incl. both negative controls); docker build asserts git rev-parse HEAD == ARG for each plugin"
        status: pass
    human_judgment: false
  - id: E2
    description: "Plugins are linked before the server starts; the registered set is exactly the approved ids; a broken plugin directory only produces a warning and leaves herdr, nginx and the terminal healthy"
    requirement: D-07
    verification:
      - kind: command
        ref: "bash internal/verify-coding-assistants.sh plugins (zz-broken mounted read-only with an invalid herdr-plugin.toml)"
        status: pass
    human_judgment: false
  - id: E3
    description: "No herdr config.toml and no Claude settings.json exist after start, after subagent-watch `setup --dry-run`, and at the end of the scenario"
    requirement: D-02
    verification:
      - kind: command
        ref: "bash internal/verify-coding-assistants.sh plugins (6 absence checks incl. the default /root/.config/herdr path)"
        status: pass
    human_judgment: false
  - id: E4
    description: "claude-limits startup hook ran without credentials: poller.pid exists, poller.log reports the missing credentials, the poller process is alive, container/herdr/terminal stay usable"
    requirement: D-07
    verification:
      - kind: command
        ref: "bash internal/verify-coding-assistants.sh plugins"
        status: pass
    human_judgment: false
  - id: E5
    description: "Patched web-service is built in the image, its startup hook brings the server up on 127.0.0.1:7340, the index has no root-absolute src/href, and login answers 503 while no password exists"
    requirement: D-04
    verification:
      - kind: command
        ref: "bash internal/verify-coding-assistants.sh plugins (health, server.pid, dist/index.html, no .git, index 200, login 503)"
        status: pass
    human_judgment: false
  - id: E6
    description: "The patched client renders and works behind real HA ingress in a browser (login page, roster, no console 404)"
    requirement: D-04
    verification: []
    human_judgment: true
    rationale: "Only curl-level behaviour is proven (spike and harness); the React app is never executed. Belongs in 23-09 human verification, as already noted in 23-SPIKE-WEB-SERVICE.md open issue 2."

duration: 33min
completed: 2026-10-11
status: complete
---

# Phase 23 Plan 06: Herdr plugins at pinned commits Summary

**subagent-watch, claude-limits and the sub-path-patched, bun-built herdr-web-service are installed at their reviewed commit pins, linked into herdr before the server starts, and proven by the `plugins` scenario (startup hooks, D-07 isolation, no herdr or Claude config written); every harness check passes.**

## Performance

- **Duration:** about 33 min (two full image builds of about 8 min each; the second reused the first's cached layers)
- **Tasks:** 2 (1 tracer, 1 auto)
- **Files modified:** 4

## Accomplishments

- Dockerfile: three `ARG HERDR_*_REF` defaults (the PIN lines of 23-PLUGIN-REVIEW.md, all three approved, no REJECT) and
  one `RUN` per plugin: `git init`, `remote add`, `fetch --depth 1 origin <sha>`, detached checkout, `rev-parse HEAD`
  asserted equal to the ARG, `.git` removed. The web-service step additionally runs `git apply --check` + `git apply`
  of `patches/herdr-web-service-subpath.patch`, `bun install --frozen-lockfile`, `bun run build`, the production prune
  and bun cache removal proven in the spike, then asserts `dist/index.html` and no quote/backtick-prefixed root-absolute
  `/api/`, `/ws`, `/sw.js`, `/assets/`, `/manifest`, `/icon`, `/apple-touch` string in the built JavaScript (the same
  expression as the spike's C3). `.git` removal, untested in the spike, is now proven: the server starts without it.
- build.yaml mirrors the three refs; the `drift` scenario passes with both negative controls.
- run.sh: a `herdr plugin link` loop over `/opt/herdr-plugins/*/` placed before the `herdr server` block; a failure logs
  `herdr plugin link failed for <dir>, continuing`; the count of registered plugins is logged. No setup action runs and
  no config is written (comment documents D-02, D-04, user decision 2).
- Harness scenario `plugins` (registered in `all`): a read-only mounted `zz-broken` directory with an invalid manifest
  proves D-07; registered ids equal `imontes.herdr-web-service,martin.claude-limits,subagent.watch`; subagent-watch
  registers `open,remove,setup` and `sh bin/run.sh scripts/setup.mjs --dry-run` exits 0 without writing anything;
  claude-limits' `poller.pid` appears with no credentials and the poller logs "no Claude Code credentials found";
  web-service `/api/health` answers within 30 s, `server.pid` exists, index returns 200 without root-absolute
  attributes, login POST returns 503 before a password exists.

## Task Commits

1. **Task 1 (tracer): subagent-watch and claude-limits checkouts, link loop, plugins scenario** - `3a6e3e6` (feat)
2. **Task 2: patched herdr-web-service build and runtime proof** - `ab9a457` (feat)

Tracer gate: `drift plugins` was green against a freshly built image before Task 2 started (automated verify only,
`gate` not `blocking-human`): tracer verified end-to-end, expansion continued.

## Verification

- `bash internal/verify-coding-assistants.sh drift plugins` against the final image: no FAIL, exit 0.
- `bash internal/verify-coding-assistants.sh claude mcp herdr-core herdr-attach surface` against the same image: 115
  PASS, exit 0 (the earlier "no config.toml before any client attached" check still holds with plugins linked).
- shellcheck (run.sh, harness), hadolint with the plan's ignore list, yamllint on build.yaml and all pre-commit hooks are
  clean. All `<acceptance_criteria>` of both tasks pass (the Dockerfile `ARG ...=<40 hex>` lines, the link block
  preceding the `herdr server` block, the drift scenario).
- Image size: 2815396419 bytes after Task 1, 2843840833 bytes after Task 2; the patched, pruned web-service adds about
  28 MB (22 MB for the plugin directory), subagent-watch and claude-limits are negligible (264 and about 4500 lines).
  The harness prints the size as an INFO line.

## Deviations from Plan

### Auto-fixed / adjusted

**1. [Rule 3 - Blocking] Plugin blocks placed after the global npm install, not directly after the herdr block**
- **Found during:** Task 1 (GitHub API budget: 60 unauthenticated calls per hour, one full build uses about 12)
- **Issue:** inserting the blocks right after the herdr block would invalidate every download layer after it
  (fff, eza, delta, difft, yazi, ...) on each pin bump or patch edit; the web-service step also needs `bun`, which is
  installed after the herdr block
- **Fix:** all four blocks (three plugins and the patch COPY) sit after the last download layer, still before the web UI
  and nginx COPY; the comment block says so
- **Files modified:** coding-assistants/Dockerfile
- **Commit:** `3a6e3e6`, `ab9a457`

**2. [Rule 1 - Bug] drift scenario hard-coded "three herdr pins"**
- **Found during:** Task 1
- **Issue:** `grep -c '^HERDR_'` equal to 3 would fail as soon as a pin was added and carried no information about which
  pins exist
- **Fix:** the scenario asserts each pin key by name (exactly once) and that every `*_REF` is a 40-character SHA
- **Commit:** `3a6e3e6`, `ab9a457`

**3. [Rule 2 - Missing critical] Extra harness assertions beyond the plan list**
- `/root/.config/herdr/config.toml` absence (the dry-run's default path), the poller log message, the web-service
  checkout carrying no `.git`, and the web-service `dist/index.html` presence were added; they strengthen the D-02 and
  build-integrity claims and cost nothing.
- **Commit:** `3a6e3e6`, `ab9a457`

**Total deviations:** 3 (1 blocking, 1 bug, 1 missing critical). **Impact:** none on scope or behaviour.

## Authentication Gates

None.

## Issues Encountered

- The first image build of the plan is a full rebuild (no cache from the earlier plans' images); it took about 8 min and
  stayed inside the GitHub API budget. The second build reused 34 cached steps.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-23-19 (pins asserted by `rev-parse`, `git apply --check`, `--frozen-lockfile`),
T-23-21 (broken plugin directory and missing credentials injected by the harness) and T-23-22 (prune, cache removal,
`.git` removal, size printed) are mitigated as planned. T-23-20 (plugins run as root with the add-on tokens in the herdr
server environment) remains the residual risk accepted in the 23-02 checkpoint and is documented in 23-08.

## Next Phase Readiness

- 23-07 can add the nginx `/services/` block and `herdr_web_password` handling: the service answers on 127.0.0.1:7340,
  refuses login (503) until a password exists, and its state dir (`/root/.local/state/herdr/plugins/<id>`) is outside
  `/data`, only the config dir (`auth.json`) persists.
- 23-08 documents the opt-ins: `herdr plugin action invoke subagent.watch.open`, the `setup` action (edits
  `~/.claude/settings.json` and herdr's config.toml, user-run), claude-limits' `[ui] tab_bar_right` snippet, using the
  paths `/opt/herdr-plugins/herdr-subagent-watch`, `/opt/herdr-plugins/herdr-claude-limits`.

## Self-Check: PASSED

- FOUND: coding-assistants/Dockerfile, coding-assistants/build.yaml, coding-assistants/run.sh,
  internal/verify-coding-assistants.sh
- FOUND commits: 3a6e3e6, ab9a457
