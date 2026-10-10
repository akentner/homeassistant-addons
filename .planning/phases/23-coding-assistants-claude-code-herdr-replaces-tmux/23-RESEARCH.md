# Phase 23: coding-assistants: Claude Code + herdr (replaces tmux) - Research

**Researched:** 2026-10-10
**Domain:** Home Assistant add-on (Debian bookworm container): Claude Code native install + persistence, herdr terminal
multiplexer (headless server, plugins), nginx/HA-ingress reverse proxy, MCP registration
**Confidence:** MEDIUM-HIGH (herdr and Claude Code behaviour was verified empirically in a scratch bookworm container;
the three third-party plugins were read statically but NOT executed, see Assumptions Log A1)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**herdr session model**
- **D-01:** SSH and ttyd attach to **one shared herdr session** (same model as the old tmux `main`): start dir
  `/homeassistant`, shell `fish`, attach-or-create semantics. Research must verify herdr has a native
  attach-or-create; otherwise wrap it in run.sh/profile logic.
- **D-02:** **No custom herdr keybindings/config.** herdr defaults only; the tmux prefix (Ctrl-a), Alt-+/- splits,
  resize and vi-copy bindings are NOT ported. `tmux.conf` is deleted.

**Claude Code defaults & context**
- **D-03:** `TOOLS.md` is injected into `/data/.claude/CLAUDE.md` (persisted `~/.claude`) as a **marked block that
  run.sh rewrites on every start**; user content outside the block is preserved (mirrors the opencode `instructions`
  update).
- **D-04:** `claude update` stays allowed (binary in `/data/claude/bin`); **no settings.json defaults** and no
  permission/model add-on option. Settings stay user-controlled.

**herdr-web-service ingress**
- **D-05:** Exposed at **`/services/`** next to `/terminal/` via nginx `proxy_pass` to the local service (no new
  port), with a link/tab in `index.html`. Research must verify the plugin's base-path/subpath behavior under the
  HA ingress prefix and WebSocket needs.

**Plugin installation & failure handling**
- **D-06:** herdr installed as a **release binary**; the three plugins via **`git clone` at a pinned tag/commit**.
  Versions pinned via ARGs in `build.yaml` (e.g. `HERDR_VERSION`, one ref ARG per plugin).
- **D-07:** A plugin failing at runtime (e.g. claude-limits without credentials) -> **log a warning and continue**;
  terminal/SSH must always stay usable.
- **D-08:** tmux removed **hard in one step** (package, `tmux.conf`, SSH auto-attach in bash+fish profile, ttyd
  attach); no fallback install. CHANGELOG/DOCS note + subpatch bump via `make update-version`.

(Plus the ROADMAP Phase 23 locked decisions: native installer + `/opt/claude-initial` bootstrap, optional
`CLAUDE_CODE_OAUTH_TOKEN` / `ANTHROPIC_API_KEY` password options, `~/.claude.json` `.mcpServers`-only merge with
"existing user entries win", herdr + plugins installed at build time with pinned ARGs, web-service behind nginx/HA
ingress with no new port, claude-limits zero-config "research must verify".)

### Claude's Discretion
- Exact ARG names, nginx location/rewrite details, run.sh bootstrap ordering, warning wording.

### Deferred Ideas (OUT OF SCOPE)
None - discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

No requirement IDs are mapped to this phase (`phase_req_ids` is null, ROADMAP says "Requirements: TBD"). The planner
should derive must-haves from the ROADMAP Phase 23 goal and the CONTEXT decisions D-01..D-08.
</phase_requirements>

## Project Constraints (from CLAUDE.md)

Extracted from `/home/akentner/Projects/addons-coding-assistants/CLAUDE.md` (repo) plus the parent CLAUDE.md files:

- **Local `docker build` before commit** for any Dockerfile change that touches packages, base images or stages. Do not
  commit untested Dockerfile changes.
- **No `Co-Authored-By` / AI attribution** in commit messages or PR descriptions (overrides any default).
- **Versions are never edited by hand**: use `make update-version ADDON=coding-assistants VERSION=X.Y.Z-N`; the 3-file
  sync is `config.yaml` (`X.Y.Z-N`), `build.yaml` `args.VERSION` (`X.Y.Z`), `README.md` shield badges (`vX.Y.Z`).
- **Ask first / challenge the approach** for critical tasks (version bumps, deployment, CI changes). Summary items 2 and 3 and Open
  Questions 1-5 below are such challenges and need user confirmation before they are baked into plans.
- **GSD workflow:** file changes only through GSD commands; one short-lived branch/worktree per add-on; stage by path
  (`git add coding-assistants/ ...`), never `git add -A`; `STATE.md`/`ROADMAP.md` updates only in the main worktree.
- **Base images:** only `ghcr.io/home-assistant/` base images; Dockerfiles download upstream artifacts at build time
  (no bundled source).
- **Lint:** YAML 2-space, 120 chars; Markdown 120 chars (prettier `proseWrap: always`, markdownlint MD013 error);
  shellcheck for shell scripts (SC1091/SC2034 ignored globally); hadolint (`make docker-build-check`).
- **Docker verify scripts** (`internal/verify-*.sh`) build images and start containers; never run the same one in two
  worktrees concurrently.
- Global (`~/CLAUDE.md`): code, commits, comments in English; chat to the user in German.

## Summary

The phase is feasible with the locked decisions, with three significant corrections found by running things:

1. **herdr covers D-01 natively.** A bare `herdr` launches or attaches to the persistent default session and
   auto-starts a detached server if none runs; two full TUI clients (SSH + ttyd) attach concurrently, each with its own
   size. The binary is statically linked (no glibc concern on bookworm). Start dir `/homeassistant` and shell `fish` need
   **no config file**: start `herdr server` with `SHELL=/usr/bin/fish` from `/homeassistant`, create the workspace with
   `herdr workspace create --cwd /homeassistant`, and wrap attach in a tiny script that re-creates the workspace when the
   last pane was closed (an empty session otherwise opens a new workspace in `$HOME`).
   [VERIFIED: scratch container test, herdr 0.9.3]
2. **The locked Claude persistence layout (`/data/claude/bin` + symlinked `~/.local/bin/claude`) makes `claude update`
   silently ineffective.** Claude treats such a symlink as a *custom launcher*: `claude update` prints "Successfully
   updated" but installs into `$XDG_DATA_HOME/claude/versions/` and leaves the launcher on the old binary.
   [VERIFIED: scratch container test, Claude Code 2.1.250 -> 2.1.296] The updater honours `XDG_DATA_HOME`, which the
   add-on already exports as `/data/.local/share`, so the working design is: persist
   `/data/.local/share/claude/versions/`, seed it from `/opt/claude-initial`, and let run.sh re-point
   `~/.local/bin/claude` at the newest version on every start. This honours the intent of the decision ("`claude update`
   survives rebuilds") but changes the literal path, so it needs user confirmation (Open Question 2).
3. **herdr-web-service cannot be mounted under a sub-path as shipped.** Its SPA hard-codes root-absolute URLs
   (`/api/...`, `/ws`, `/assets/...`, `/sw.js`, `/manifest.webmanifest`) and its server sends
   `frame-ancestors 'none'`, so an nginx `proxy_pass` alone yields a broken page under the HA ingress prefix. A small
   build-time patch (relative URLs + `vite build --base ./`) plus nginx header rewriting is required, and it has a login
   password that can only be set from the host (Open Questions 3 and 4).

Two more facts shape planning: CI forwards **only** the standard build args to `docker build`, so the "pinned ARGs in
`build.yaml`" (D-06) must also exist as **Dockerfile defaults** (repo precedent: `litellm/Dockerfile`), and two of the
three plugins need `config.toml` / `settings.json` edits to show anything in the UI, which collides with D-02/D-04
unless handled as documented opt-in (Open Question 1).

**Primary recommendation:** Build in five serial plans on `coding-assistants/Dockerfile` + `run.sh` (they all touch the
same two files): (1) Claude install + XDG-based persistence + auth options, (2) Claude MCP registration, (3) herdr
replaces tmux (server bootstrap, attach wrapper, ttyd/SSH), (4) plugins + web-service patch + nginx `/services/`,
(5) docs/version/verify. Resolve Open Questions 1-5 with the user before plan 1 is written.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Web terminal (browser) | Frontend/proxy: nginx `/terminal/` -> ttyd | herdr client (child of ttyd) | ttyd spawns one `herdr` client per websocket; nginx is the only ingress-visible listener (port 8099). |
| SSH access | sshd (port 2222) -> bash login -> `exec` attach wrapper | herdr client | Profile hook replaces the tmux auto-attach; sshd and ttyd both end in the same herdr client. |
| Session persistence / sharing | herdr headless server (started by run.sh) | `/data/.config/herdr/session.json` | The server owns panes; clients are disposable. State persists in `/data` via `XDG_CONFIG_HOME`. |
| Claude Code binary + updates | `/data/.local/share/claude/versions` (persistent) | `/opt/claude-initial` (image seed) | Native updater writes to `$XDG_DATA_HOME/claude/versions`; run.sh only seeds and re-points the launcher. |
| Claude auth + state | `/data/.claude`, `/data/.claude.json` (symlinked) | env vars exported by run.sh | Credentials in `.credentials.json` (0600) or token env vars from add-on options. |
| MCP registration | run.sh (jq merge into `/data/.claude.json` `.mcpServers`) | opencode.json (unchanged) | Same add-on config source (`mcp_servers`, zigbee2mqtt, mycli) feeds both assistants. |
| Plugin execution | herdr server (startup hooks, actions) | plugin-spawned daemons (web-service bun server) | Plugins run as children of the herdr server with its env (PATH, tokens). |
| Web UI for agents (`/services/`) | nginx location -> `127.0.0.1:7340` (plugin's own bun server) | HA ingress (auth) | HA ingress authenticates; nginx adapts Host/Origin/CSP; plugin adds its own password login. |
| Landing page / versions | nginx static `index.html` + `versions.json` (run.sh) | `info.html` | Tab added for `/services/`; versions JSON gains claude + herdr. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| herdr | 0.9.3 (release `v0.9.3`, 2026-09-29) | terminal workspace manager / session server | Locked (D-06). Static binary `herdr-linux-x86_64` (sha256 `18a8dc65f1c2fa485884344356dea1cfd911c6f06cf46fa78e193f4087f4dba7`) and `herdr-linux-aarch64` (sha256 `4de7aa3e25678812e92960de64f7c2aaa1bca1f0f80a3c5e559837e231e1f5c0`) [VERIFIED: GitHub releases API 2026-10-10; x86_64 digest re-checked with `sha256sum`] |
| Claude Code | native installer, `latest` at build (2.1.296 on 2026-10-10) | coding assistant | Locked (ROADMAP). Single ~257 MB ELF; launcher symlink `~/.local/bin/claude` -> `~/.local/share/claude/versions/<ver>` [VERIFIED: scratch container install] |
| ttyd | latest at build (existing) | web terminal | Existing; only the command changes from `tmux ...` to the attach wrapper. |
| nginx | Debian bookworm (existing) | ingress proxy | Existing; add `/services/` block. |
| jq / bashio | existing | config merge / options | Existing patterns in run.sh. |

### Supporting (herdr plugins, all pinned by commit SHA - none of the three repos has any tag or release)

| Plugin | Pinned ref (HEAD of `main` on 2026-10-10) | Purpose | Runtime needs |
|--------|-------------------------------------------|---------|---------------|
| `silencechung/herdr-subagent-watch` (id `subagent.watch`, v0.3.0, MIT) | `c47d49b247d8ca3387d88d5bb9731a3b7bf4f6a8` | popup/sidebar view of Claude sub agents | herdr >= 0.9.3, Node >= 22 (image has 24.x), Linux; no build step |
| `i-montes/herdr-web-service` (id `imontes.herdr-web-service`, v0.2.0, MIT) | `e9082b3fb969064e89153a8c6b2170366982f7f9` | chat-style web client for agents | Bun >= 1.3 (image has bun), build step `bun install --frozen-lockfile` + `bun run build` (vite) |
| `martin-saldinger/herdr-claude-limits` (id `martin.claude-limits`, v0.1.0, **no license file**) | `9c0c9a1931ac91f9d865031e2dc58d66a7d1b594` | Claude plan usage in tab bar/popup | `jq`, `curl`, `~/.claude/.credentials.json` |

[VERIFIED: GitHub API (tags/releases empty for all three, `commits` listing) and raw manifests, 2026-10-10]

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `git clone` at SHA | tarball `https://github.com/<o>/<r>/archive/<sha>.tar.gz` | Equivalent pin, no `.git`, matches the existing `mcp2zigbee2mqtt` pattern in the Dockerfile. The tarball route was verified to download; `git fetch --depth 1 origin <sha>` is [ASSUMED] to work for these repos. Either satisfies D-06 ("pinned commit"). |
| `herdr plugin install <o>/<r> --ref` at build | `plugin link` at runtime | `plugin install` writes its registry under the build-time `$HOME/.config/herdr`, but the runtime config dir is `$XDG_CONFIG_HOME/herdr` = `/data/.config/herdr` (verified: herdr honours `XDG_CONFIG_HOME`), so the registry would be invisible at runtime. Use clone/tarball into `/opt/herdr-plugins/<name>` and `herdr plugin link` on every start. |
| Persist `/data/claude/bin` (locked) | persist `$XDG_DATA_HOME/claude/versions` | See Summary item 2 - the locked layout breaks `claude update`. |

**Installation (Dockerfile sketch):**
```bash
# herdr (static binary; arch via uname so the aarch64 leg is not made worse)
ARG HERDR_VERSION=0.9.3
RUN A="$(uname -m)" && curl -fsSL -o /usr/local/bin/herdr \
      "https://github.com/herdrdev/herdr/releases/download/v${HERDR_VERSION}/herdr-linux-${A}" \
    && chmod +x /usr/local/bin/herdr && herdr --version
# Claude Code (native installer; seed moved out of /root so it is not stored twice in the image)
RUN curl -fsSL https://claude.ai/install.sh | bash \
    && mkdir -p /opt/claude-initial && mv /root/.local/share/claude/versions/* /opt/claude-initial/ \
    && rm -rf /root/.local/bin/claude /root/.local/share/claude /root/.claude /root/.claude.json
```

**Version verification:** herdr `v0.9.3` published 2026-09-29T19:29:23Z; Claude installer resolved `2.1.296`;
plugin SHAs resolved from the GitHub API on 2026-10-10. These are 1-3 weeks old projects (plugins) - re-resolve the
SHAs at plan-execution time and re-pin if `main` moved.

## Package Legitimacy Audit

The phase installs no npm/PyPI/crates package directly. The web-service plugin's **build step** installs npm packages
from the plugin's own `bun.lock` (`bun install --frozen-lockfile`). Direct dependencies from its `package.json` were
checked with `gsd-tools query package-legitimacy check --ecosystem npm`:

| Package | Registry | Latest publish | Downloads/wk | Source Repo | Verdict | Disposition |
|---------|----------|----------------|--------------|-------------|---------|-------------|
| react / react-dom | npm | 2026-09-09 | 185M / 175M | github.com/react/react | OK | Approved |
| react-markdown / remark-gfm | npm | 2025-03 / 2025-02 | 37M / 45M | github.com/remarkjs/* | OK | Approved |
| qrcode-generator | npm | 2025-08-07 | 3.4M | github.com/kazuhikoarase/qrcode-generator | OK | Approved |
| @fontsource-variable/{bricolage-grotesque,jetbrains-mono} | npm | 2026-07-19 | 0.4M / 1.9M | github.com/fontsource/font-files | OK | Approved |
| tailwindcss / @tailwindcss/vite | npm | 2026-07-16 (vite plugin) | 134M / 48M | github.com/tailwindlabs/tailwindcss | OK | Approved |
| typescript, @types/bun, @types/react, @types/react-dom | npm | recent | 16M-305M | github.com/DefinitelyTyped / microsoft | OK | Approved |
| vite | npm | 2026-10-08 | 194M | github.com/vitejs/vite | SUS (`too-new`) | Flagged - false-positive class (very high downloads, fresh release); real versions come from the plugin's lockfile |
| @vitejs/plugin-react | npm | 2026-10-05 | 97M | github.com/vitejs/vite-plugin-react | SUS (`too-new`) | Flagged - same reason |

**Packages removed due to SLOP verdict:** none.
**Packages flagged SUS:** `vite`, `@vitejs/plugin-react` (both `too-new` only; no postinstall script on any package).
The planner should add one `checkpoint:human-verify` before the web-service build step: review the pinned plugin
commit and its `bun.lock` versions.

Non-registry artifacts: the three plugin repos are 0-1 star, < 3 weeks old (`claude-limits` has no license) and run as
root inside the add-on with HA tokens in the environment. Their legitimacy is [ASSUMED] (no authoritative source);
mitigation is the SHA pin plus a source review checkpoint. herdr binary: checksum verified against the GitHub release
digest. Claude installer: vendor script; downloads a manifest-checksummed binary [VERIFIED: read `install.sh`].

## Architecture Patterns

### System Architecture Diagram

```
                         HA Supervisor (ingress, admin auth)
                                   |
                         nginx :8099 (ingress_port)
        +--------------+-----------+---------------+--------------------+
        |              |                           |                    |
   /  (index.html,   /terminal/                /services/           /opencode (link :4096)
   info.html,        ttyd 127.0.0.1:7681       rewrite -> 127.0.0.1:7340
   versions.json)    (per-websocket)           Host/Origin -> localhost
                          |                    drop plugin CSP/HSTS
                          v                          v
             coding-assistants-attach        herdr-web-service (bun, spawned by
             (wrapper, new)                   plugin startup hook, own password)
                          ^                          |
   sshd :2222 -> bash login -> exec wrapper          | unix socket $XDG_CONFIG_HOME/herdr/herdr.sock
                          |                          |
                          v                          v
                 herdr client  ----------------> herdr headless server  (started by run.sh BEFORE sshd/ttyd,
                 (one per SSH/ttyd connection,        env: PATH, HA_*, SUPERVISOR_TOKEN, SHELL=fish,
                  each its own size)                   CLAUDE_CODE_OAUTH_TOKEN / ANTHROPIC_API_KEY, cwd /homeassistant)
                                                          |  startup hooks: web-service start, claude-limits poller
                                                          v
                                          panes: fish -> claude / opencode / copilot ...
 Persistence: /data/.config/herdr (session.json, plugins.json, plugin config)   /data/.claude(.json)
              /data/.local/share/claude/versions (updatable binary)  <- seeded from /opt/claude-initial
 Boot order in run.sh: persist dirs -> claude bootstrap -> CLAUDE.md block -> MCP merge -> env/profile -> plugin link
                       -> herdr server + workspace -> sshd -> opencode serve -> ttyd -> nginx -> wait
```

### Recommended Project Structure

```
coding-assistants/
├── Dockerfile            # - tmux, - tmux.conf; + herdr, + claude seed, + plugin checkouts/build, + attach wrapper
├── build.yaml            # args: VERSION + HERDR_VERSION + 3 plugin refs (mirror of Dockerfile defaults)
├── config.yaml           # + claude_code_oauth_token / anthropic_api_key (password?), + backup_exclude, + description
├── run.sh                # Claude bootstrap, CLAUDE.md block, MCP merge helper, herdr server, plugin link, ttyd cmd
├── nginx.conf            # + /services/ block
├── coding-assistants-attach   # NEW wrapper script (COPY to /usr/local/bin like ha-api)
├── patches/herdr-web-service-subpath.patch   # NEW (see Summary item 3) applied in Dockerfile before the vite build
├── index.html / info.html / TOOLS.md / DOCS.md / README.md / CHANGELOG.md   # docs + Services tab
└── tmux.conf             # DELETED
```

### Pattern 1: herdr server bootstrap + attach wrapper (D-01)

**What:** run.sh starts the headless server itself (so panes inherit the add-on env), links plugins first, creates the
`main` workspace once; ttyd and the SSH profile call one wrapper that guarantees a workspace and then `exec herdr`.
**When to use:** always; never let a client auto-start the server (it would inherit the client's env: no HA tokens,
wrong cwd).
**Example (skeleton, verified building blocks):**
```bash
# run.sh - before sshd/ttyd (all commands below were run in the scratch container)
export XDG_CONFIG_HOME=/data/.config            # already exported by run.sh
for p in /opt/herdr-plugins/*/; do herdr plugin link "$p" >/dev/null 2>&1 \
  || bashio::log.warning "herdr plugin link failed: $p"; done     # D-07; link needs no running server
( cd /homeassistant && SHELL=/usr/bin/fish exec herdr server ) &
for _ in $(seq 1 50); do herdr status >/dev/null 2>&1 && break; sleep 0.2; done
if [ "$(herdr workspace list | jq '.result.workspaces | length')" = 0 ]; then
  herdr workspace create --cwd /homeassistant --label main --no-focus >/dev/null
fi
# /usr/local/bin/coding-assistants-attach (sh): export XDG_CONFIG_HOME default, TERM default, wait briefly for the
# server (fall back to a login shell with a message if absent), recreate the workspace if the list is empty, then:
exec herdr
```
[VERIFIED: scratch container - `herdr plugin link` without server; `SHELL=/usr/bin/fish herdr server` gives fish panes;
`workspace create --cwd` gives a pane with cwd `/homeassistant`; session restored from `session.json` on restart; a bare
`herdr` with no server auto-starts a detached server; after `exit` in the only pane `workspace list` is empty and the
next bare `herdr` opens a workspace in `$HOME`, hence the wrapper]

### Pattern 2: Claude binary persistence via XDG (replaces `/data/claude/bin`)

**What:** keep the Claude-managed layout, just rooted in `/data`.
```bash
# run.sh (skeleton). XDG_DATA_HOME=/data/.local/share is already exported by this add-on.
V=/data/.local/share/claude/versions; mkdir -p "$V" /root/.local/bin
seed=$(ls /opt/claude-initial); newest=$(ls "$V" | sort -V | tail -1)
# seed when empty or when the image ships a newer version than what is persisted
if [ -z "$newest" ] || [ "$(printf '%s\n%s\n' "$seed" "$newest" | sort -V | tail -1)" != "$newest" ]; then
  cp -a "/opt/claude-initial/$seed" "$V/$seed"; newest=$seed
fi
ln -sfn "$V/$newest" /root/.local/bin/claude          # launcher points INTO versions/ => Claude keeps managing it
```
[VERIFIED: scratch container: (a) installer layout `~/.local/bin/claude -> ~/.local/share/claude/versions/2.1.296`;
(b) with `XDG_DATA_HOME=/tmp/xdgdata`, `claude update` re-pointed `~/.local/bin/claude` to
`/tmp/xdgdata/claude/versions/2.1.296`; (c) with a launcher symlink to an external copy (`/tmp/d2/claude/bin/claude`),
`claude update` reported success, wrote `/tmp/x2/claude/versions/2.1.296` and `claude --version` stayed `2.1.250`]
Docs corroborate: "If you replace that launcher with your own script or symlink, auto-update and `claude update` leave
it in place" [CITED: code.claude.com/docs/en/setup#auto-updates].

### Pattern 3: marked block in `~/.claude/CLAUDE.md` (D-03)

Reuse the proven implementation from git history (`git show fbb1f56:coding-assistants/run.sh`, python3 regex between
`<!-- coding-assistants:begin -->` / `<!-- coding-assistants:end -->`, user text outside preserved) and point it at
`/data/.claude/CLAUDE.md`. Block-level HTML comments are stripped before injection into Claude's context, so the
markers cost no tokens [CITED: code.claude.com/docs/en/memory]. [CITED: git history fbb1f56]

### Pattern 4: MCP registration helper (shared by 3 blocks)

Claude user-scope entries live in `~/.claude.json` `.mcpServers`. Formats written by Claude itself (verified by running
`claude mcp add`): stdio `{"type":"stdio","command":..,"args":[],"env":{}}`, http `{"type":"http","url":..}`.
Merge only that key, add-on defaults on the left so existing entries win, write **through** the symlink with `cp`
(Claude does not break a `~/.claude.json` symlink: verified), never `mv` onto it:
```bash
jq --argjson add "$MCP_OBJ" '.mcpServers = ($add + (.mcpServers // {}))' "$CLAUDE_JSON" > "$tmp" && cp "$tmp" "$CLAUDE_JSON"
```
Build `$MCP_OBJ` for `mcp_servers` (http -> `{type:"http",url}`, else stdio with `args`/`env` defaults), and add
`zigbee2mqtt` (command `node`, args `["/opt/mcp2zigbee2mqtt/dist/index.js"]`, **explicit `env`** with the MQTT values) and
the per-connection `mariadb-<name>` wrapper scripts (`command: /usr/local/bin/mariadb-<name>`). Introduce one shell
function used by all three blocks instead of copying the opencode jq three times.
[VERIFIED: scratch container for formats and symlink behaviour; the z2m/mycli shapes are [CITED: git history fbb1f56]]

### Pattern 5: nginx `/services/` (D-05)

```nginx
# relative redirect: an absolute Location would leave the HA ingress prefix
location = /services { absolute_redirect off; return 301 services/; }
location /services/ {
    proxy_pass http://127.0.0.1:7340/;            # trailing slash strips the prefix
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_set_header Host 127.0.0.1:7340;          # plugin allows only localhost/127.0.0.1/::1 (+PUBLIC_URL host)
    proxy_set_header Origin http://127.0.0.1:7340; # /ws requires an allowed Origin; HA forwards the real one
    proxy_hide_header Content-Security-Policy;     # plugin sends frame-ancestors 'none' (blocks our iframe)
    proxy_hide_header Strict-Transport-Security;   # never let it leak onto the HA origin
    add_header Content-Security-Policy "default-src 'self'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'self'; base-uri 'none'" always;
    proxy_read_timeout 86400; proxy_send_timeout 86400;
}
```
Reasoning sources: plugin `server/access.ts` (`allowedHosts`, `allowedOrigins`, `originAllowed` requires Origin on
`/ws`, `CSP` constant) [CITED: raw.githubusercontent.com/i-montes/herdr-web-service/e9082b3.../server/access.ts];
HA ingress forwards `Host`, `Origin`, `Cookie` unchanged and returns `Set-Cookie` unmodified
[CITED: home-assistant/core `homeassistant/components/hassio/ingress.py`]. The block itself is [ASSUMED] to work
end-to-end (A1) and must be proven by a verify script.

### Anti-Patterns to Avoid

- **Letting a client start the herdr server** - env of the first SSH/ttyd client becomes the env of every pane.
- **Launcher symlink outside `versions/`** (the locked `/data/claude/bin` design) - `claude update` becomes a no-op.
- **`mv`/`jq > file` onto the symlinked `~/.claude.json`** - replaces the symlink; use `cp` into the target.
- **Writing token secrets into `/data` shell snippets** - `/data/.config/fish/conf.d/00-coding-assistants.fish` is
  persistent and world-readable inside the volume. Export `CLAUDE_CODE_OAUTH_TOKEN` / `ANTHROPIC_API_KEY` only in
  run.sh's process environment (panes inherit it from the herdr server).
- **Exporting an empty `ANTHROPIC_API_KEY=""`** when the option is unset; export only when non-empty and not `null`.
- **`bashio::config` of an unset `password?` option returns `null`** - compare against `"null"` like the existing mycli code.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Attach-or-create session | custom socket/pty mux or tmux emulation | bare `herdr` + `herdr server` | Native; multi-client verified. |
| Claude updates | custom downloader / version pinning script | `claude update` + XDG-rooted `versions/` | Vendor-managed, checksum-verified, keeps 2 newest. |
| MCP file edits | hand-written JSON string splicing | `jq` with `--argjson`/`--arg`, or `claude mcp add-json` | Quoting/secret-safety. |
| Plugin install | own clone+register logic | `herdr plugin link <dir>` | Idempotent, no server needed; registry handled by herdr. |
| Web-service login/hash | own auth proxy | plugin's `set-password` (argon2id) + HA ingress | Do not reimplement crypto. |
| Wrapper for secrets in shell | writing tokens to profile files | process env inheritance | See anti-patterns. |

**Key insight:** every piece needed already exists as a vendor mechanism; the work is wiring and persistence paths,
and the two places where a vendor default conflicts with this add-on (launcher semantics, sub-path hosting).

## Runtime State Inventory

> Not a rename phase, but tmux is removed and Claude was previously shipped and removed, so leftover state matters.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Possibly `/data/claude/.claude` and `/data/claude/.claude.json` from the pre-1.0.0 Claude integration (CHANGELOG `[Unreleased]` "Existing `/data/claude/` contents are left on disk"). No tmux state is persisted. | Optional one-time migration `/data/claude/.claude(.json)` -> `/data/.claude(.json)` if the new paths are absent (Open Question 8). Otherwise none. |
| Live service config | None - no external service stores "tmux". | None - verified by grep of `coding-assistants/`. |
| OS-registered state | None (container). sshd host keys in `/data/ssh` are unaffected. | None. |
| Secrets/env vars | `HA_TOKEN`/`SUPERVISOR_TOKEN` already written in plaintext to `/data/.config/fish/conf.d/00-coding-assistants.fish`. New Claude token options must NOT be added there. | Code edit only (process-env export). |
| Build artifacts | `tmux` apt package and `/etc/tmux.conf` in the image; the Claude installer also creates `/root/.claude`, `/root/.claude.json` at build. | Remove `tmux` + `COPY tmux.conf`; `rm -rf /root/.claude /root/.claude.json` in the seed RUN and again before symlinking in run.sh. |

Stale-reference sweep (grep): `tmux` occurs in `Dockerfile`, `run.sh` (l.261, 283-286, 344-347, 450), `TOOLS.md:8`,
`info.html:62`, `DOCS.md:159-167,189,206-217`, `README.md:15`, plus the deleted `tmux.conf`. All must change in the
same plan (D-08). The earlier `CHANGELOG.md` "Removed: Claude Code CLI" entry must be reconciled (Claude returns).

## Common Pitfalls

### Pitfall 1: `claude update` appears to work but changes nothing
**What goes wrong:** user runs `claude update`, sees success, version unchanged.
**Why:** launcher symlink pointing outside `versions/` is a "custom launcher".
**How to avoid:** XDG layout (Pattern 2). **Warning signs:** `claude doctor` reports a launcher the native installer
did not create; `/data/.local/share/claude/versions` has more versions than the launcher uses.

### Pitfall 2: Persistent volume and HA backups balloon
**What:** each Claude version is ~220-260 MB; the updater keeps the two newest plus the seed; HA backs up `/data`.
**How to avoid:** add `.local/share/claude/*` (and `.config/herdr/*.sock`, `.config/herdr/session-snapshots/*`) to
`backup_exclude` (existing list is `.config/opencode/cache/*`, `.local/share/opencode/cache/*`, `.npm/*`, `.cache/*`);
the binary is re-creatable from `/opt/claude-initial` or `claude update`.

### Pitfall 3: herdr server started with the wrong environment
**What:** panes lack `HA_TOKEN`, `PATH` entries (`/root/.local/bin`), `CLAUDE_CODE_OAUTH_TOKEN`.
**Why:** a client (SSH/ttyd) auto-started the server, or run.sh started it before the exports.
**How to avoid:** start `herdr server` explicitly *after* all `export`s (l.300-316 of current run.sh) and *before*
sshd/ttyd; the wrapper never auto-starts. [VERIFIED: scratch container - the startup hook env showed PATH/XDG exactly as
the server's env]

### Pitfall 4: First client after an emptied session lands in `$HOME`
**Why:** closing the last pane empties the workspace list; a bare `herdr` creates `~`. **How:** wrapper recreates
`main` at `/homeassistant` when the list is empty. [VERIFIED]

### Pitfall 5: web-service UI blank/404 under ingress
**Why:** root-absolute asset/API/WS URLs + `frame-ancestors 'none'` + Host/Origin allow-list (Summary item 3).
**How:** build-time patch + nginx block (Pattern 5) + verify script that fetches the page through nginx with an
`X-Ingress-Path`-style prefix and opens a WebSocket.

### Pitfall 6: web-service is unusable without a password
`POST /api/auth/login` returns 503 `setup_required` until `<config dir>/auth.json` exists; the hash can only be created
on the host via `bun scripts/plugin.ts set-password` (reads one line from a pipe) or the setup wizard; rules: >= 6
chars, a symbol, a number, an uppercase letter. [CITED: plugin `server/auth/login.ts`, `password.ts`, `scripts/plugin.ts`]
Needs a decision (Open Question 3).

### Pitfall 7: claude-limits shows nothing / logs "no Claude Code credentials found"
It reads `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.credentials.json` `.claudeAiOauth.accessToken` and calls
`https://api.anthropic.com/api/oauth/usage`. That file only exists after an interactive `claude login`; a
`CLAUDE_CODE_OAUTH_TOKEN` env token or `ANTHROPIC_API_KEY` writes no credentials file (docs: setup-token "does not save
the token anywhere"). So "zero-config" holds only for interactive logins [CITED: plugin `bin/poller.sh`;
code.claude.com/docs/en/authentication]; D-07 (warn and continue) already covers the failure mode - the poller just logs
to `$HERDR_PLUGIN_STATE_DIR/poller.log`. The `user:profile` scope requirement of the endpoint is [ASSUMED] (A3).

### Pitfall 8: "existing user entries win" freezes stale add-on values
Because run.sh writes defaults into the same `.mcpServers` the user may edit, the first-written value (e.g. the
`ha-mcp` URL with its secret path) becomes an "existing user entry" and later option changes never propagate - the
opencode merge (`.mcp = ($mcp + (.mcp // {}))`) has the same flaw. Mitigation: keep a ledger file (e.g.
`/data/.claude-addon-mcp.json` with the last written entries) and overwrite an entry only if it still equals the ledger
value; or document the limitation. Decision in Open Question 6.

### Pitfall 9: PRE-EXISTING bug that affects the Claude z2m entry
run.sh appends MQTT/MYCLI exports to `/etc/profile.d/00-coding-assistants.sh` (l.124-129, l.251-258) and to the fish
conf (l.131-138) *before* those files are truncated/overwritten (`: > /etc/profile.d/00-coding-assistants.sh` at l.263,
`} > /etc/profile.d/...` at l.288, `} > "${FISH_CONF}"` at l.349), so the appended lines are lost (only the later MYCLI
fish append at l.369-378 survives). The existing OpenCode z2m registration has no `env`, so it relies on those lost
exports. For Claude put the MQTT values in the entry's explicit `env` (as the old git-history implementation did).
Fixing the ordering is out of scope unless the user wants it; log it as a deferred item.

### Pitfall 10: build.yaml args are not forwarded by CI
`_build-template.yml` passes exactly `BUILD_FROM, VERSION, BUILD_ARCH, BUILD_DATE, BUILD_NAME, BUILD_DESCRIPTION,
BUILD_REF, BUILD_REPOSITORY, BUILD_VERSION` (l.166-175). `litellm/Dockerfile` documents the consequence ("addon-specific
args from build.yaml are not forwarded, so this default keeps the build self-sufficient"). Put the pins in the
Dockerfile as `ARG HERDR_VERSION=0.9.3` etc., mirror them in `build.yaml` (D-06) and add a drift check to the verify
script (compare `build.yaml` args to Dockerfile defaults).

### Pitfall 11: ttyd client dies / SSH exits when herdr exits
`prefix+q` (detach) ends the client, closing the SSH session or showing ttyd's reconnect prompt - same as tmux detach.
Document an SSH escape hatch (`ssh -t host bash --noprofile`) because the profile `exec`s the wrapper. Guard the
profile hook with `[ -t 0 ]` and `HERDR_ENV` so non-interactive logins and nested shells are not captured.

## Code Examples

### SSH profile hooks (replace the tmux blocks at run.sh l.283-286 and l.344-347)
```bash
# bash/profile.d
if [[ -n "$SSH_CONNECTION" ]] && [[ -z "$HERDR_ENV" ]] && [[ -t 0 ]]; then
    exec coding-assistants-attach
fi
```
```fish
# fish conf.d
if set -q SSH_CONNECTION; and not set -q HERDR_ENV; and status is-interactive
    exec coding-assistants-attach
end
```
[ASSUMED skeleton; `HERDR_ENV=1` is set in every herdr-managed pane/plugin env - verified from the startup hook env dump]

### ttyd (replace l.450 `tmux new-session -A -s main -c /homeassistant &`)
```bash
ttyd --port 7681 --interface 127.0.0.1 --base-path /terminal/ --writable \
     --client-option "fontSize=${FONT_SIZE}" --client-option "fontFamily=${FONT_FAMILY}" \
     --client-option "theme=${THEME_JSON}" coding-assistants-attach &
```

### Auth exports (run.sh, before the herdr server starts)
```bash
CC_TOKEN=$(bashio::config 'claude_code_oauth_token'); [[ -n "${CC_TOKEN}" && "${CC_TOKEN}" != "null" ]] && export CLAUDE_CODE_OAUTH_TOKEN="${CC_TOKEN}"
API_KEY=$(bashio::config 'anthropic_api_key');        [[ -n "${API_KEY}"  && "${API_KEY}"  != "null" ]] && export ANTHROPIC_API_KEY="${API_KEY}"
```
Precedence if both are set: `ANTHROPIC_API_KEY` beats `CLAUDE_CODE_OAUTH_TOKEN`; in interactive mode Claude asks once
to approve the key [CITED: code.claude.com/docs/en/authentication#authentication-precedence]. Option names are Claude's
discretion; config.yaml needs `password?` schema entries (existing precedent: `mqtt_password: password?`).

### Persistence of `~/.claude` (carry over from the earlier implementation)
`rm -rf /root/.claude /root/.claude.json; ln -s /data/.claude /root/.claude; ln -s /data/.claude.json /root/.claude.json`
(create `{}` if missing). Using `CLAUDE_CONFIG_DIR=/data/.claude` instead also works (verified: `.claude.json` then lives
inside the dir) and is honoured by the plugins, but the locked decision names the two symlinks; keep the symlinks.
[VERIFIED: scratch container for both variants]

### Versions JSON / MOTD
`index.html` already has `<b id="v-claude">` and reads `v.claude`; add `"claude"` (and optionally `"herdr"`) to the
`versions.json` printf (run.sh l.17-19) and the MOTD heredoc (l.11-14). Claude's version is available only after the
bootstrap, so move the Claude bootstrap above the MOTD/versions block.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `npm install -g @anthropic-ai/claude-code` (this add-on pre-1.0.0) | native installer, `~/.local/share/claude/versions` | native is "Recommended" in current docs | binary is a single ELF; auto-updates in background; npm needs Node >= 22 |
| tmux session `main` | herdr persistent default session | this phase | mouse-first UI, default prefix `ctrl+b`, workspaces/tabs/panes |

**Deprecated/outdated:** `claude` via npm in this repo (removed already); the `/data/claude/` layout of the 1.0.0-alpha era.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A build-time patch (vite `--base ./`, `fetch("."+path)`, ws URL from `location.pathname`, `sw.js` registration dropped) plus Pattern 5 makes the web-service UI work through HA ingress. The plugin code was read statically; **running third-party plugin code was blocked by this session's permission classifier**, so nothing in the plugins was executed. | Summary item 3, Pattern 5, Pitfall 5 | `/services/` unusable -> fall back to hiding the tab or deferring web-service; needs a spike/verify task. |
| A2 | `git fetch --depth 1 origin <sha>` works for the three repos (tarball download by SHA was verified for web-service only). | Alternatives | Build fails; use tarball route. |
| A3 | The `/api/oauth/usage` endpoint needs a login with `user:profile` scope, so claude-limits works only with interactive `claude login`. | Pitfall 7 | claude-limits could work with setup-token tokens too (harmless). |
| A4 | Claude Code stdio MCP servers may not inherit the full parent env, so explicit `env` is safer. | Pattern 4 | None if explicit env is used anyway. |
| A5 | HA backup (python tar) tolerates unix sockets under `/data/.config/herdr`; excluded anyway. | Pitfall 2 | Backup warning only. |
| A6 | ttyd spawns one `herdr` client process per websocket (existing tmux design relied on the same). | Architecture | Shared-client behaviour differs; low. |
| A7 | subagent-watch's popup works without its `setup` action when invoked via `herdr plugin action invoke subagent.watch.open` (it falls back to herdr `agent_session` / pane map / cwd guess). | Open Question 1 | Plugin useless until setup is run. |
| A8 | The three plugin repos are legitimate and stay stable at their pinned SHAs (no authoritative source; days-old projects). | Package Legitimacy | Supply-chain risk -> human review checkpoint. |
| A9 | Pinning Claude to `latest` at build (not an ARG) is acceptable, like opencode. | Standard Stack | User may want `CLAUDE_VERSION` ARG. |

## Open Questions (RESOLVED)

1. **D-02 vs plugin wiring (needs user decision).** herdr defaults show nothing for `claude-limits` (needs RESOLVED: user chose no config, documented opt-ins (23-06, 23-08).
   `[ui] tab_bar_right` command entry + optional `[[keys.command]]`) and the sub-agent sidebar/popup key needs
   `herdr plugin action invoke subagent.watch.setup`, which edits `~/.claude/settings.json` hooks **and**
   `config.toml`. herdr also shows a first-run onboarding dialog until `onboarding = false` is saved.
   - Known: all of these are config/settings edits; plugin actions are otherwise reachable only via
     `herdr plugin action invoke <id>` or a key binding [CITED: herdr plugins.mdx].
   - Recommendation: honour D-02/D-04 literally (write no `config.toml`, no `settings.json`); ship the plugins linked and
     document copy-paste snippets and the CLI invocations in DOCS.md as opt-in. Alternative: seed a minimal
     plugin-wiring `config.toml` only when absent (needs explicit user OK because it bends D-02).
2. **Claude persistence path (needs user confirmation).** Locked: `/data/claude/bin` + symlinked launcher; verified RESOLVED: user chose the versions-dir layout (23-01).
   to break `claude update`. Recommendation: `/data/.local/share/claude/versions` (Pattern 2). The seed stays in
   `/opt/claude-initial` as locked.
3. **web-service password.** Without a password the UI returns 503. Recommendation: add an optional `password?` option RESOLVED: user chose the optional `herdr_web_password` option (23-07).
   (e.g. `herdr_web_password`) that run.sh pipes to `bun scripts/plugin.ts set-password` with
   `HERDR_PLUGIN_CONFIG_DIR=$(herdr plugin config-dir imontes.herdr-web-service)` after linking; if unset, log a clear
   info line. Also validate the plugin's password rules before piping (otherwise the call fails and only a warning is
   logged, per D-07).
4. **Patching a third-party plugin at build time** (Summary item 3). D-06 says "git clone at a pinned commit"; the sub-path fix RESOLVED: user chose patch plus spike/verify checkpoint (23-02, 23-04).
   needs ~6 sed/patch edits (`web/src/api.ts`, `roster.ts:48`, `main.tsx:13`, `InstallBanner.tsx:18`,
   `ChatView.tsx:467-468`, build with `vite build --base ./`). Recommendation: keep a `patches/*.patch` file applied with
   `patch -p1` (fails the build loudly if the pin moves) and gate the tab behind a verify script. Alternative: skip
   web-service ingress and publish a port (rejected by the ROADMAP) or drop the plugin.
5. **CI arg forwarding.** Recommendation: Dockerfile defaults + mirror in `build.yaml` + drift check (no CI change). RESOLVED: Dockerfile defaults, build.yaml mirror, drift check (23-05, 23-06).
   Alternative: extend `_build-template.yml` to forward all `build.yaml` args (cross-add-on change, out of scope).
6. **Stale MCP defaults** (Pitfall 8): ledger approach vs documented limitation. RESOLVED: documented limitation, no ledger (23-03, 23-08).
7. **claude-limits "zero-config" caveat** (Pitfall 7): only with interactive `claude login`. RESOLVED: documented caveat (23-08).
8. **Migrate old `/data/claude/.claude*`?** Optional one-time copy if the new paths are absent. RESOLVED: trivial one-time copy (23-01).
9. **Version bump size.** D-08 says subpatch (`1.0.0-3`); the change is feature-sized, a user may prefer `1.1.0-0`. RESOLVED: decided at the 23-09 checkpoint.
   Follow D-08 unless told otherwise; use `make update-version ADDON=coding-assistants VERSION=1.0.0-3` (add `NO_TAG=yes`
   / `NO_PUSH=yes` per the repo's recent convention; release tag left to the operator).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| docker (podman emulation) | mandatory local `docker build` | yes | podman 5.x ("Emulate Docker CLI using podman") | - |
| ghcr.io/home-assistant/amd64-base-debian:bookworm | build + scratch tests | yes (pulled during research) | bookworm | - |
| hadolint | `make docker-build-check` | yes | 2.14.0 | - |
| shellcheck / yamllint / pre-commit / yq / jq / uv | repo lint gates | yes | 0.x / 1.38.0 / 4.6.2 / 4.4.0 / 1.8.2 / 0.12.7 | - |
| herdr (host) | optional host-side experiments | yes | 0.9.3 (already installed for the user) | - |
| network to github.com, claude.ai, downloads.claude.ai, deps.nodesource, bun.sh | image build | yes (all reachable in research) | - | - |
| bun | web-service build (already in Dockerfile as `bun`) | yes in image (bun 1.4.x) | 1.4.3 | - |
| Node >= 22 | subagent-watch | yes in image (NodeSource 24.x) | 24.21.0 | - |

**Missing dependencies with no fallback:** none.
**Full image build time** is not measured; expect a long build (existing steps + 257 MB Claude seed + vite build). Do
not run `internal/verify-*.sh` for this add-on in two worktrees at once.

## Security Domain

`security_enforcement` is not disabled in `.planning/config.json` (absent = enabled).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Claude: `CLAUDE_CODE_OAUTH_TOKEN` / `ANTHROPIC_API_KEY` from `password?` options, process-env only; web-service: plugin's argon2id password (do not hand-roll) |
| V3 Session Management | yes | plugin cookie `hwv_session` (HttpOnly, SameSite=Strict, server stores hash only); HA ingress session in front |
| V4 Access Control | yes | ingress `panel_admin` default (admin-only) is the first gate; `/services/` lets an authenticated user start shells/agents in a root container with `/homeassistant` rw - same blast radius as the existing ttyd terminal, so keep ingress admin-only |
| V5 Input Validation | yes | jq `--arg/--argjson` for all option values; `printf %q` for shell snippets; validate web-service password rules before piping; never interpolate options into command strings |
| V6 Cryptography | yes | no custom crypto; plugin's argon2id via `Bun.password` |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Third-party plugin code runs as root with HA tokens in env (3 repos, days old, one without license) | Elevation / Tampering | SHA pin, source review checkpoint, patch applied with `patch` (fails if upstream moves), D-07 failure isolation |
| Token written to persistent `/data` files | Information disclosure | process-env only; do not append to fish `conf.d` / profile.d |
| Secret in `.claude.json` (`ha-mcp` URL secret path, z2m MQTT password) | Information disclosure | file mode 600 (Claude creates it 0600), no logging of values (log counts only, as existing code does) |
| Host/Origin spoofing against the plugin | Spoofing | plugin allow-list + nginx fixes Host/Origin to localhost; plugin stays on `127.0.0.1:7340`, no published port |
| Clickjacking weakened when CSP is replaced | Spoofing | replacement CSP keeps `frame-ancestors 'self'` (not `*`) |
| HSTS leaking onto the HA origin | Tampering | `proxy_hide_header Strict-Transport-Security` |
| Command injection through add-on options into generated scripts | Tampering | jq/printf %q only (existing mycli wrapper pattern) |
| Claude as root: `--dangerously-skip-permissions` offered by the web UI's "bypass" mode | Elevation | informational: Claude refuses it as root unless sandbox env is set; do not set `IS_SANDBOX` |

## Sources

### Primary (HIGH confidence - executed/read this session)
- Scratch container `ghcr.io/home-assistant/amd64-base-debian:bookworm` (podman) running herdr 0.9.3 and Claude Code
  2.1.250/2.1.296: static binary, `herdr server`, bare-`herdr` auto-start, two concurrent clients, `XDG_CONFIG_HOME`,
  `SHELL` env, `workspace create --cwd`, empty-session behaviour, stale-socket recovery after `kill -9`, `plugin link`
  without server and startup-hook env, Claude installer layout, `claude update` XDG + custom-launcher behaviour,
  `~/.claude.json` symlink + `CLAUDE_CONFIG_DIR`, `claude mcp add` output shapes, herdr detecting `claude` as agent.
- Repo files read this session: `coding-assistants/{run.sh,config.yaml,build.yaml,nginx.conf,Dockerfile,index.html,
  info.html,DOCS.md,TOOLS.md,README.md,CHANGELOG.md,tmux.conf,sshd_config}`, `.github/workflows/_build-template.yml`
  (build-args l.166-175), `.github/workflows/build.yml`, `litellm/Dockerfile` (arg-forwarding comment), Makefile, git
  history `fbb1f56` (earlier Claude implementation).
- herdr docs v0.9.3: install, plugins, persistence-remote, session-state, cli-reference, integrations
  (`raw.githubusercontent.com/herdrdev/herdr/v0.9.3/docs/next/website/src/content/docs/*.mdx`); `herdr --default-config`,
  `herdr --help` on the installed 0.9.3.
- Claude Code docs: code.claude.com/docs/en/setup, /authentication, /mcp, /memory.
- Plugin sources at the pinned SHAs (raw files + tarball read, **not executed**): manifests, READMEs, `bin/*.sh`,
  `server/{access,config,http,index,ws}.ts`, `server/auth/*`, `web/src/*`, `web/vite.config.ts`.
- HA core `homeassistant/components/hassio/ingress.py` (header/cookie/WebSocket handling).

### Secondary (MEDIUM)
- GitHub REST API for repo metadata, tags/releases (empty), commit SHAs, release digests.

### Tertiary (LOW)
- None used as a basis for recommendations; see Assumptions Log.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - versions/checksums verified; plugin SHAs resolved from the API.
- Architecture (herdr, Claude persistence, MCP merge): HIGH - exercised in a scratch container.
- web-service ingress + plugin runtime behaviour: LOW-MEDIUM - static reading only, never executed (A1).
- Pitfalls: HIGH for items marked VERIFIED, MEDIUM otherwise.

**Research date:** 2026-10-10
**Valid until:** 2026-10-24 (herdr and plugins are days-to-weeks old and move fast; Claude Code ships weekly)
