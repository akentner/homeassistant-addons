---
phase: 23-coding-assistants-claude-code-herdr-replaces-tmux
verified: 2026-10-12T12:00:00Z
status: human_needed
score: 9/9 must-haves verified
covered_files:
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-01-PLAN.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-01-SUMMARY.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-02-PLAN.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-02-SUMMARY.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-03-PLAN.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-03-SUMMARY.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-04-PLAN.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-04-SUMMARY.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-05-PLAN.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-05-SUMMARY.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-06-PLAN.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-06-SUMMARY.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-07-PLAN.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-07-SUMMARY.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-08-PLAN.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-08-SUMMARY.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-09-PLAN.md"
  - ".planning/phases/23-coding-assistants-claude-code-herdr-replaces-tmux/23-09-SUMMARY.md"
  - ".pre-commit-config.yaml"
  - "coding-assistants/CHANGELOG.md"
  - "coding-assistants/DOCS.md"
  - "coding-assistants/Dockerfile"
  - "coding-assistants/README.md"
  - "coding-assistants/TOOLS.md"
  - "coding-assistants/build.yaml"
  - "coding-assistants/coding-assistants-attach"
  - "coding-assistants/config.yaml"
  - "coding-assistants/index.html"
  - "coding-assistants/info.html"
  - "coding-assistants/nginx.conf"
  - "coding-assistants/patches/herdr-web-service-subpath.patch"
  - "coding-assistants/run.sh"
  - "internal/spike-herdr-web-service.sh"
  - "internal/verify-coding-assistants.sh"
covered_digest: "v3:sha256:b163813dc31144dc7e357a309d76b47ea62702508c840645cbf05ca1476f81a7"
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Open the add-on through real Home Assistant ingress, switch to the Services tab, log in with the herdr_web_password value, check the roster and the browser console"
    expected: "/services/ loads inside the iframe under the ingress prefix (no CSP frame block, no 404 for assets), login succeeds, the roster renders, WebSocket connects, no console errors"
    why_human: "The harness proves the nginx/plugin behaviour with curl against an emulated ingress. Iframe embedding, cookie behaviour under the real HA origin, service-worker removal and runtime JS errors need a real browser behind real HA ingress."
  - test: "In a started add-on run `claude update` (network required), then re-create the container"
    expected: "A newer version lands in /data/.local/share/claude/versions, ~/.local/bin/claude points to it, and after re-creation the newer persisted version still wins over the image seed"
    why_human: "The harness proves layout, seed-vs-newest selection and a fake persisted 99.0.0; a real update against Anthropic's release endpoint is an external-service interaction that cannot be run here. The Dockerfile comment records that the earlier /data/claude/bin layout was a silent no-op, so the real updater behaviour is the load-bearing risk."
  - test: "Run the documented subagent-watch opt-in (DOCS.md: `herdr plugin action invoke subagent.watch.setup` / key binding / sidebar row) inside herdr with a real Claude subagent"
    expected: "The key binding / sidebar row appears and the viewer opens for a running subagent"
    why_human: "The plugin is linked but deliberately never configured (D-02, D-04); the harness only runs `setup --dry-run`. The interactive TUI behaviour needs a human inside herdr."
  - test: "In a running add-on with herdr_web_password set, delete the web-service auth file (`$(herdr plugin config-dir imontes.herdr-web-service)/auth.json`) and call POST /services/api/login"
    expected: "Login answers 503 again (no password exists) without restarting the add-on"
    why_human: "The harness proves 503 only for the never-configured state; the per-request re-read after deletion is plugin runtime behaviour not exercised by any test. Not run by the verifier because herdr commands must not be executed from this shell."
---

# Phase 23: coding-assistants: Claude Code + herdr (replaces tmux) Verification Report

**Phase Goal:** The `coding-assistants` add-on ships Claude Code next to opencode, with the same MCP servers registered, and uses herdr instead of tmux (with the subagent-watch, web-service and claude-limits plugins).
**Verified:** 2026-10-12
**Status:** human_needed
**Re-verification:** No, initial verification

## Method and evidence basis

ROADMAP Phase 23 carries no Success Criteria list, so must-haves were derived from the phase goal, the ROADMAP "Locked decisions", CONTEXT D-01..D-08 and every `must_haves` block in 23-01..23-09-PLAN.md (Option C plus plan merge). All findings below were read from the files in `coding-assistants/`, `internal/` and `.pre-commit-config.yaml`, not from SUMMARY text.

What I ran myself:

- `bash internal/verify-coding-assistants.sh drift docs` (static scenarios, TMPDIR under `/var/tmp`, removed afterwards): ALL CHECKS PASSED (10 drift + 33 docs checks, including the negative controls).
- `shellcheck -e SC1091 -e SC2034` on run.sh, coding-assistants-attach, verify-coding-assistants.sh, spike-herdr-web-service.sh: exit 0.
- `hadolint` on the Dockerfile with the repo hook ignore list (DL3008, DL3018, DL3059, DL4006, DL3016): exit 0.
- `make validate-versions`: passed (coding-assistants config.yaml 1.1.0-0, build.yaml VERSION 1.1.0, README badge v1.1.0).
- Local jq spot-checks of the `claude_mcp_merge` expression (existing entries win, other keys survive, a failing jq run yields an empty temp file that the `-s` guard refuses to copy) and of `sort -V` seed-vs-newest selection (99.0.0 beats a lower seed).
- `grep` sweep for the old multiplexer: it only appears in the "Migrating from tmux" section of DOCS.md, the CHANGELOG Removed entry, and the harness; `coding-assistants/tmux.conf` is gone.

What I did NOT run (constraint): the image-building harness scenarios (claude-launcher, claude-state, claude-auth, mcp-*, herdr-*, surface, plugins, services, services-auth). I read their assertions (see "Behavioral coverage") and they test the right state transitions, but their pass status rests on the recorded 23-09 run (225 PASS / 0 FAIL, 13 scenarios, on the candidate image; the only commit after it, 84739b0, changes version strings only and the drift scenario still passes). I treated that as evidence for the behavior-dependent truths and note the dependency openly here.

## Goal Achievement

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | Claude Code ships in the image and a self-updating launcher persists across rebuilds (D-04; layout supersedes the ROADMAP text `/data/claude/bin`, user decision 1) | VERIFIED | Dockerfile native installer, seed moved to `/opt/claude-initial`, single-binary assert plus `--version` smoke test, `/root/.local/share/claude`, `/root/.claude*` removed from the image. run.sh:48-65 seeds `/data/.local/share/claude/versions` only when strictly newer (`sort -V`) and re-points `~/.local/bin/claude` on every start. Harness `claude-launcher` / `claude-state` assert persisted 99.0.0 wins and an image seed newer than persisted 0.0.1 wins (lines 468-482). |
| 2 | Auth: optional `claude_code_oauth_token` / `anthropic_api_key` exported only when set; else interactive login; `~/.claude`, `~/.claude.json` persisted in /data (0700/0600), legacy layout migrated | VERIFIED | config.yaml schema `password?` for both; run.sh:456-466 exports only for non-empty, non-`null` values into the process env, nothing is written to profile.d or the fish conf (those heredocs at run.sh:413-432 and 482-510 carry no token), unset afterwards. run.sh:70-84 migrates legacy copy-only, chmod 700/600, symlinks. Harness `claude-auth` asserts absence from profile.d, fish conf and log, presence in the ttyd environment. |
| 3 | The same MCP servers OpenCode gets are registered for Claude Code at user scope by merging only `.mcpServers`; existing entries win; a failing jq never truncates `~/.claude.json`; no secret in the log | VERIFIED | `claude_mcp_merge` (run.sh:151-165) assigns only `.mcpServers = ($add + (.mcpServers // {}))`, copies back with `cp` only if jq succeeded and output is non-empty, else warns and returns 1; call sites for `mcp_servers` (http -> `{type,url}`, stdio -> `{type,command,args,env}`), zigbee2mqtt (explicit env object) and each `mariadb-<name>` wrapper (run.sh:197, 253, 377). Logs carry counts only. OpenCode registration block unchanged. Harness `mcp-servers` A/B/C and `mcp-integrations` cover oauthAccount/projects survival, user-edit wins, byte-identical corrupt file, no secrets in logs. |
| 4 | D-03: TOOLS.md is injected into `/data/.claude/CLAUDE.md` as a marked block rewritten on every start; user text outside it is preserved | VERIFIED | run.sh:90-117 (python block with begin/end markers, regex span replace via function replacement, append when absent, empty file replaced). Harness `claude-state` asserts block equals TOOLS.md, stale text gone, USER-NOTE-1/2 appear exactly once after restart. |
| 5 | herdr fully replaces tmux (D-01, D-02, D-08): shared session for SSH and ttyd, attach-or-create, no custom herdr config, hard tmux removal | VERIFIED | Dockerfile: no tmux package, `COPY tmux.conf` gone, `tmux.conf` file deleted; herdr 0.9.3 sha256-verified, `uname -m` arch selection. run.sh:620-646 starts `herdr server` after all exports in a respawn loop from /homeassistant with `SHELL=/usr/bin/fish`, then `coding-assistants-attach --ensure`. `coding-assistants-attach` is the single attach path (ttyd command at run.sh:692, bash hook run.sh:428, fish hook run.sh:506), never starts a server, flock-guards workspace `main`, falls back to plain fish with a message and `CODING_ASSISTANTS_NO_ATTACH` loop guard. No `config.toml` is written (harness asserts absence). Grep sweep finds the old name only in the allowed migration/CHANGELOG places. Harness `herdr-core`/`herdr-attach` assert one workspace after two concurrent clients, pane env inheritance, respawn within 20 s, fallback shell. |
| 6 | D-06/D-07: herdr and the three plugins installed at build time at pinned versions mirrored in build.yaml; a plugin failure only logs a warning | VERIFIED | Dockerfile ARG pins for HERDR_VERSION, both SHA256s and the three plugin commit SHAs; `git fetch --depth 1 <sha>` + detached checkout + `rev-parse HEAD` equality assert + `.git` removal. Pins equal the `PIN` lines in 23-PLUGIN-REVIEW.md (human approval "approved: all", 2026-10-11). `drift` scenario re-run by me: PASS including negative controls. run.sh:574-582 links every `/opt/herdr-plugins/*/` before the server start; a link failure is `bashio::log.warning`. The three plugins use `herdr plugin link` and no setup action is invoked; harness `plugins` asserts exact registered set, broken plugin dir only warns, no config.toml / settings.json. |
| 7 | D-05: herdr-web-service reachable at `/services/` next to `/terminal/` through nginx on the existing ingress port, with a Services tab; patched for the HA ingress sub-path | VERIFIED | nginx.conf `/services` relative 301, `/services/` proxy to 127.0.0.1:7340 with the spike-validated headers (Host/Origin pinned, X-Forwarded-* cleared, plugin CSP hidden and replaced by one CSP with `frame-ancestors 'self'`, HSTS hidden). No new port in config.yaml (`ports` unchanged: 2222, 4096). index.html has the Services tab and a lazy `./services/` iframe; info.html lists it. Dockerfile applies `patches/herdr-web-service-subpath.patch` (9 client files, `git apply --check` first), builds with `bun install --frozen-lockfile`, prunes, and fails the build on any root-absolute URL left in `dist`. 23-SPIKE-WEB-SERVICE.md opens with `VERDICT: GO`. Harness `services` / `services-auth` assert relative redirect, assets 200, one CSP, no HSTS, 503/401/204, HttpOnly cookie, gated roster and WebSocket (101 only with cookie). |
| 8 | `herdr_web_password` option feeds the plugin's own `set-password` via stdin; password never in args, files or logs; rejected password is a warning | VERIFIED | config.yaml schema `herdr_web_password: password?`; run.sh:591-612 pipes with `printf '%s\n'` into `scripts/plugin.ts set-password`, logs only the plugin's message on rejection, `unset`s the variables. Harness `services-auth` B asserts the weak password is warned about without appearing in the log; A asserts it is not in the config dir or log, also after re-creation. |
| 9 | Documentation and release gate (D-08): DOCS/CHANGELOG/README/TOOLS cover Claude Code, herdr, plugins, web UI; version bumped through `make update-version`; lint gates pass | VERIFIED | `docs` scenario passed in my run (headings for the three options, Claude Code, herdr, plugins, Web UI, Migrating from tmux; documented commands and pins cross-checked against config.yaml/Dockerfile/build.yaml). CHANGELOG [Unreleased] has Added/Changed/Removed. config.yaml 1.1.0-0, build.yaml 1.1.0, README badge v1.1.0, `make validate-versions` passes, HERDR_*/ref pins untouched by the bump. hadolint and shellcheck pass in my run. `.pre-commit-config.yaml` change is limited to excluding `patches/*.patch` from whitespace fixers (needed to keep the patch byte-exact). |

**Score:** 9/9 truths verified (0 present, behavior-unverified). Four interactive/runtime items remain for a human (below), so the overall status is `human_needed`.

### CONTEXT decision accounting

| Decision | Status | Where in code |
| -------- | ------ | ------------- |
| D-01 shared session, attach-or-create | VERIFIED | `coding-assistants-attach` + run.sh server loop; herdr has no native attach-or-create, so it is wrapped as the context allowed |
| D-02 no custom herdr keybindings/config, tmux.conf deleted | VERIFIED | no `config.toml` written anywhere in run.sh/Dockerfile; `tmux.conf` removed; harness asserts absence |
| D-03 TOOLS.md marked block in `/data/.claude/CLAUDE.md` | VERIFIED | run.sh:90-117 |
| D-04 `claude update` allowed, no settings/permission/model defaults | VERIFIED (with accepted deviation) | no settings.json written (harness asserts); update works through `XDG_DATA_HOME` versions dir instead of `/data/claude/bin` (user decision 1, documented in Dockerfile comment and DOCS) |
| D-05 `/services/` next to `/terminal/`, no new port | VERIFIED | nginx.conf, index.html, config.yaml ports |
| D-06 release binary + git-clone plugins at pinned refs via ARG/build.yaml | VERIFIED | Dockerfile + build.yaml + drift scenario |
| D-07 plugin failure warns and continues; terminal always usable | VERIFIED | run.sh link loop, respawn loop, attach fallback |
| D-08 hard tmux removal, CHANGELOG/DOCS note, bump via `make update-version` | VERIFIED (with accepted deviation) | tmux gone everywhere; bump is minor 1.1.0-0 rather than a subpatch, chosen by the user on 2026-10-12 (23-09 SUMMARY) |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `coding-assistants/Dockerfile` | Claude seed, herdr binary, 3 plugin checkouts, web-service build | VERIFIED | all present, hadolint clean, no tmux |
| `coding-assistants/run.sh` | launcher bootstrap, state, CLAUDE.md block, auth, MCP merge, plugin link, password, server loop | VERIFIED | all present, shellcheck clean |
| `coding-assistants/coding-assistants-attach` | single attach wrapper | VERIFIED | 76 lines, substantive, called from 3 places |
| `coding-assistants/config.yaml` | 3 password options, backup_exclude, description | VERIFIED | options, backup_exclude (`.local/share/claude/*`, herdr sock/log/snapshots) present |
| `coding-assistants/build.yaml` | HERDR_* and plugin ref mirrors | VERIFIED | drift scenario passes |
| `coding-assistants/nginx.conf`, `index.html`, `info.html` | /services/ block, tab, row | VERIFIED | |
| `coding-assistants/patches/herdr-web-service-subpath.patch` | 9-file client patch | VERIFIED (static) | structure and COPY/apply wiring confirmed; `git apply` against the pinned commit was proven by the spike and the 23-09 image build, not re-run by me (needs network clone) |
| `internal/verify-coding-assistants.sh` | 13 scenarios | VERIFIED | static scenarios re-run by me; image scenarios read, not re-run |
| `23-PLUGIN-REVIEW.md`, `23-SPIKE-WEB-SERVICE.md` | gate artifacts | VERIFIED | PIN lines match Dockerfile and build.yaml; `VERDICT: GO` |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| 23-PLUGIN-REVIEW.md PIN lines | Dockerfile ARG defaults | build.yaml mirror, `drift` | WIRED | identical SHAs in all three places |
| run.sh exports | herdr server env -> pane env | server started after exports | WIRED | run.sh:443-466 before 620-629 |
| profile.d / fish conf / ttyd | `coding-assistants-attach` | exec hooks, ttyd command | WIRED | run.sh:428, 506, 692 |
| `herdr_web_password` | plugin `set-password` | stdin pipe | WIRED | run.sh:601-604 |
| `/services/` nginx location | 127.0.0.1:7340 plugin startup hook | `herdr plugin link` before server start | WIRED | run.sh:574-580 and nginx.conf |
| Claude updater | persisted versions dir | `XDG_DATA_HOME=/data/.local/share` + launcher symlink | WIRED statically; real update needs human (item 2) | |
| DOCS statements | shipped files | `docs` scenario | WIRED | passed in my run |

### Data-Flow Trace (Level 4)

Not applicable in the UI-data sense (infrastructure add-on). The relevant flows are config values to runtime behaviour: `config.yaml` options -> run.sh -> process env / `.claude.json` / plugin auth file. Traced above; no hardcoded or static-fallback stand-ins found.

### Behavioral Coverage

| Behavior | Check | Result |
| -------- | ----- | ------ |
| MCP merge keeps existing entries and other keys | local jq run of the run.sh expression | PASS |
| Failed jq cannot overwrite the Claude state file | local run: jq exit 5, 0-byte temp file; run.sh guard `[[ -s tmp ]]` refuses the copy | PASS |
| Newest persisted version beats older seed | `sort -V` check | PASS |
| build.yaml mirrors Dockerfile pins | harness `drift` | PASS |
| Docs cross-check | harness `docs` | PASS |
| Image-level scenarios (13) | recorded 23-09 run, 225/0; not re-run by verifier | accepted as recorded evidence |

### Probe Execution

No `probe-*.sh` scripts declared by this phase; the harness `internal/verify-coding-assistants.sh` is the phase's own verification driver (see above).

### Requirements Coverage

REQUIREMENTS.md has no IDs mapped to Phase 23 (`phase_req_ids` null). The plans reference CONTEXT decisions D-01..D-08, all accounted for in the table above. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (all phase files) | - | TBD / FIXME / XXX / TODO scan | none found as unreferenced debt markers | - |
| `coding-assistants/run.sh` | 405, 432 | `: >` / `> /etc/profile.d/...` truncates the MQTT/MYCLI exports appended earlier at 263 and 400 | Info (pre-existing, documented in the Z2M comment at run.sh:242-244) | Not introduced by this phase; the Claude registration was deliberately built to not depend on it |
| `coding-assistants/run.sh` | 607 | plugin's `set-password` output is logged verbatim on rejection | Info | The harness proves the rejected sample password is not echoed; relies on the plugin not echoing input in other failure modes |

### Warnings (non-blocking, for the next planning pass)

1. **ROADMAP wording not synced with delivered deviations.** ROADMAP Phase 23 still says `/data/claude/bin`, "subpatch" and "zero-config" claude-limits. Delivered: versions-dir layout (user decision 1), minor bump 1.1.0-0 (user choice 2026-10-12), claude-limits linked-not-configured and documented as working only with an interactive `claude login` credentials file. All three are documented in DOCS/SUMMARY and user-approved, so they are not gaps; the ROADMAP text and the stale "TBD" plan bullet at ROADMAP.md:253 should be reconciled when the phase is closed.
2. **CHANGELOG still `[Unreleased]`**, and no tag exists by design (release hand-off to the operator: tag `coding-assistants/v1.1.0` after merge, per 23-09 SUMMARY).
3. **Verifier did not re-run the image scenarios** (constraint). A fresh run of `bash internal/verify-coding-assistants.sh all` before tagging is the cheap way to re-confirm.

## Human Verification Required

### 1. Services tab in a real browser behind HA ingress

**Test:** Open the add-on panel in Home Assistant, go to Services, log in with `herdr_web_password`, open the roster, check the browser console.
**Expected:** UI loads in the iframe under the ingress prefix, login works, roster and WebSocket work, no console errors.
**Why human:** Only a real browser behind real HA ingress exercises iframe embedding, cookies on the HA origin and client JS.

### 2. `claude update` end to end

**Test:** In a started add-on run `claude update`, then re-create the container.
**Expected:** New version under `/data/.local/share/claude/versions`, launcher points to it, persisted version wins over the seed after re-creation.
**Why human:** Needs the real Anthropic release endpoint; the previous layout failed silently here, so this is the load-bearing risk of the Claude persistence design.

### 3. subagent-watch opt-in setup

**Test:** Follow the DOCS.md subagent-watch opt-in inside herdr with a running Claude subagent.
**Expected:** Key binding / sidebar row appear, the viewer opens.
**Why human:** Plugin is intentionally unconfigured (D-02, D-04); interactive TUI behaviour.

### 4. Deleting the web-service auth file returns login to 503

**Test:** Delete `auth.json` in the plugin config dir of a running add-on, then POST `/services/api/login`.
**Expected:** 503, no restart needed.
**Why human:** Runtime plugin behaviour not covered by any scenario; herdr commands must not be run from the verifier's shell.

## Gaps Summary

No gaps. Every derived must-have and every CONTEXT decision is present in the code, wired, and (for the behavior-dependent ones) covered by a harness scenario whose recorded pass I did not re-execute. Two decisions deviate from the locked ROADMAP wording (Claude binary layout, minor instead of subpatch bump); both were explicit user decisions and are documented. Status is `human_needed` solely because of the four interactive/real-service items above.

---

_Verified: 2026-10-12_
_Verifier: Claude (gsd-verifier)_
