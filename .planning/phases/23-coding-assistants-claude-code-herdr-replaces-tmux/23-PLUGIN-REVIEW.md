# Phase 23: herdr plugin supply-chain review dossier

Static review of the three third-party herdr plugins at the pinned commits from `23-RESEARCH.md` (D-06).
Produced by plan 23-02, task 1, on 2026-10-10.

Method and ground rules:

- Each commit was fetched with `git init`, `git remote add origin`, `git fetch --depth 1 origin <sha>` and
  `git checkout --detach FETCH_HEAD` into its own empty `mktemp -d` directory, and `git rev-parse HEAD` was compared to
  the pin (all three equal, see the per-plugin sections).
- Everything was read statically (`cat`, `grep`, `git`, `gh api`, `npm view`). Nothing from the plugins was installed,
  built, sourced or executed; no `bun install` / `npm install` was run; helper scripts lived in a different directory.
- File:line references are relative to the repository root at the pinned commit.
- Regular expressions used for the surface searches: `spawn|exec|execFile|child_process|sh -c|nohup|Bun\.spawn|eval\(|`
  `new Function|\$\(` (execution), `https?://|fetch\(|node:net|node:http|WebSocket|curl|wget|createServer|listen\(|`
  `Bun\.serve|hostname` (network), `writeFile|appendFile|rename|mkdir|unlink|rmSync|chmod|copyFile|symlink|`
  `createWriteStream|openSync|Bun\.write` (writes). Test, docs and markdown files were excluded from the searches.

## Summary for the human gate

- All three pins resolve and verify. Two of three repositories have not moved since the research pin
  (web-service, claude-limits). subagent-watch `main` moved by 10 commits (see the plugin section): the upstream
  author fixed several defects in exactly the code this add-on would run, so the research pin is the older, weaker
  state. Re-pinning to the newer HEAD is possible but requires a diff review (listed below).
- No plugin starts anything at install time. At runtime (after `herdr plugin link` and a herdr server start) two plugins
  run code automatically: web-service via a `[[startup]]` hook (detached bun server on `127.0.0.1:7340`) and
  claude-limits via a `[[startup]]` hook (detached shell poller). subagent-watch has no `[[startup]]`; it only acts
  when an action is invoked, and its `setup` action (which edits Claude `settings.json` and herdr `config.toml`) is
  never run by the add-on.
- Only claude-limits handles a credential (the Claude Code OAuth access token). It goes to `api.anthropic.com` only.
- claude-limits has no licence file.
- web-service: an authenticated browser session equals full terminal control of every pane (shell commands, agents) as
  root inside the add-on. The plugin password is the whole boundary behind HA ingress.
- npm: the 220 lockfile packages come from the public registry with integrity hashes; the only package with an
  install script is `fsevents` (macOS-only optional dependency, never installed on Linux). The two packages flagged
  `too-new` are the current `latest` of two very high-traffic, provenance-attested projects (verdicts below).

## Plugin: herdr-subagent-watch

### 1. Pin and fetch verification

- Repository: `silencechung/herdr-subagent-watch` (MIT, 0 stars, created 2026-10-09).
- Pin (research): `c47d49b247d8ca3387d88d5bb9731a3b7bf4f6a8`.
- `git fetch --depth 1 origin c47d49b247d8ca3387d88d5bb9731a3b7bf4f6a8` + detached checkout: OK.
- `git rev-parse HEAD` equals the pin: YES (exact match, 40/40 characters).
- No tag and no release exist.
- Current `main` HEAD (GitHub API, 2026-10-10): `c9cf7538855606af8b54ba30097eea6a6ec48be5` (pushed 2026-10-10T15:17Z).
  `main` is 10 commits ahead of the pin, `git log --oneline` equivalent (compare API, newest first):

```text
12e5bd6 fix: viewer 的 terminal escape、寬度、session 切換與穩定性
f1d2b37 fix: hook、setup 與 herdr 呼叫的安全性修正
3022b82 fix: lock 身分改成 inode 加內容比對
f122641 fix: session 改以 transcript 寫入時間選擇，修 review 找到的 regression
9ebd818 fix: 側邊欄不再用 herdr 的 session 否決事件，launcher 清掉相對 PATH
722d7ce docs: 補 sh -c 巢狀 claude 的已知限制、更正過時的測試標題
ced0865 fix: session 只在來源回報的值改變時才切換，C1 改成單字元剝除
c753a18 docs: Known limitations 補 session 切換的兩個邊角情況
0af42bb Merge pull request #4 from silencechung/fix/security-setup
c9cf753 Merge pull request #3 from silencechung/fix/viewer-correctness
```

- Size of the newer range: 29 files changed; non-test source touched: `bin/run.sh`, `hooks/sidebar-hook.mjs` (+269/-36),
  `lib/session.mjs` (+211/-34), `lib/text.mjs` (+177/-47), `lib/watcher.mjs` (+96/-47), `scripts/setup.mjs`
  (+128/-28), `lib/setup-claude.mjs`, `lib/subagent-state.mjs`, `lib/transcript.mjs`, `lib/herdr.mjs`,
  `lib/render.mjs`, `viewer.mjs` (+113/-22). Commit `f1d2b37` (security fixes) states, among others: PATH lookup for
  herdr accepts absolute paths only (so a repository-local `herdr` is not executed), the runtime state directory is
  checked for owner / not-a-symlink / 0700, temp files get random names and `wx`, the lock uses an atomic `link`, and
  the setup script validates the herdr config in a temp file before replacing the original. These are defects in the
  pinned (older) state. Re-pinning is the human's option; it requires reading that diff before approval.

### 2. Manifest summary (`herdr-plugin.toml`)

- `id = "subagent.watch"`, `version = "0.3.0"`, `min_herdr_version = "0.9.3"`, `platforms = ["linux"]` (lines 1-6).
- `[[build]]`: none. `[[startup]]`: none.
- `[[actions]]` `open` (line 9-14): `["sh", "bin/run.sh", "open-action.mjs"]`, contexts `pane`, `workspace`.
- `[[actions]]` `setup` (line 17-21): `["sh", "bin/run.sh", "scripts/setup.mjs"]`, context `global`.
- `[[actions]]` `remove` (line 23-27): `["sh", "bin/run.sh", "scripts/setup.mjs", "--remove"]`, context `global`.
- `[[panes]]` `viewer` (line 29-35): popup, `["sh", "bin/run.sh", "viewer.mjs"]`.

### 3. File inventory

- 58 tracked files, 8100 lines in total (31 files under `test/`; 27 non-test files, 4544 lines including READMEs and
  docs). Runtime code: `bin/run.sh` (139), `open-action.mjs` (69), `viewer.mjs` (366), `scripts/setup.mjs` (375),
  `hooks/sidebar-hook.mjs` (348), 13 files under `lib/`. No `package.json`, no dependencies (Node built-ins only),
  no build step.

### 4. EXECUTION SURFACE

- Launcher `bin/run.sh:139` `exec "$node" "$script"`: finds Node >= 22 (`bin/run.sh:104-127`: `SUBAGENT_WATCH_NODE`,
  `command -v node`, fnm / Volta / nvm directories, `/usr/local/bin`, `/usr/bin`). In the add-on image Node is on PATH.
- `open-action.mjs:64` `spawnSync(herdrBinPath, ["plugin","pane","open",...])` - opens the viewer popup (fixed argv, the
  pane id comes from `HERDR_PLUGIN_CONTEXT_JSON` / `HERDR_PANE_ID` and is passed as `--env SUBAGENT_WATCH_PANE_ID=...`,
  `open-action.mjs:28-34`).
- `lib/session.mjs:131` `execFileSync(herdrBinPath, args)` - `herdr pane get <id>` (fixed argv, 3 s timeout).
- `hooks/sidebar-hook.mjs:197` `spawnSync(binaryPath, argumentList, ...)` - herdr `pane report-metadata` calls from the
  Claude `SubagentStart` / `SubagentStop` hook. The hook only exists in the user's Claude settings after the `setup`
  action ran; the add-on never runs it.
- `scripts/setup.mjs:96` `spawnSync(herdrBinPath, ...)` - `herdr config check`, `herdr server reload-config`,
  `herdr notification show` (only inside the `setup` / `remove` actions).
- `herdrBinPath` resolution at the pin (`lib/herdr.mjs:15-28`): `HERDR_BIN_PATH` if set (herdr sets it for plugins),
  else a PATH walk that includes relative PATH entries (`lib/herdr.mjs:19-23`). This is the PATH-hijack weakness the
  upstream commit `f1d2b37` later fixes. In the add-on herdr always sets `HERDR_BIN_PATH`, so the fallback is not used.
- No `eval`, no `new Function`, no `sh -c`, no shell command construction from remote input. `bin/run.sh` contains
  `$(...)` substitutions only for version probing and path resolution (`bin/run.sh:10,45,65,77,109`).
- Hook command written by `setup` is `sh "<root>/bin/run.sh" "<root>/hooks/sidebar-hook.mjs"` with a
  shell-metacharacter check on the path (`lib/setup-claude.mjs:7-17`).

### 5. NETWORK SURFACE

- None at runtime. The repository-wide search finds no `fetch`, `http`, `https`, `net`, `curl` or `wget` use in
  executable code. The only URLs are documentation strings: `lib/demo.mjs:31-34` (demo fixture text) and
  `bin/run.sh:131` (error message pointing to nodejs.org).
- No credential is sent anywhere. The viewer talks only to the local herdr server through the `herdr` CLI.

### 6. FILESYSTEM WRITES (outside the plugin's own config and state directories)

- `scripts/setup.mjs` (action `setup` / `remove` only; NOT run by the add-on):
  - Claude Code `settings.json` at `$CLAUDE_CONFIG_DIR` or `~/.claude` (`lib/claude-config.mjs:18-20`) - adds
    `SubagentStart` / `SubagentStop` hooks. Backup `settings.json.subagent-watch.bak` (`scripts/setup.mjs:28,86-93`).
  - herdr `config.toml` (`HERDR_CONFIG_PATH` or `${XDG_CONFIG_HOME:-$HOME/.config}/herdr/config.toml`,
    `scripts/setup.mjs:50-59`) - adds `prefix+.` key binding and `ui.sidebar.agents.rows_by_agent` rows
    (`lib/setup-herdr.mjs:6-8`). Atomic write via temp + rename (`scripts/setup.mjs:73-84`), validated with
    `herdr config check`, restored on failure (`scripts/setup.mjs:296-300` region).
- `hooks/sidebar-hook.mjs:282-283` creates `$XDG_RUNTIME_DIR/subagent-watch` (mode 0700) and writes per-pane /
  per-session JSON and `.lock` files there (`:211-212`, `:222`) - only when the hook is installed.
- `open-action.mjs:53` appends `open-action.log` in the plugin state dir, only in dry-run mode.
- Reads (no writes): Claude transcripts under `<claude dir>/projects/**` (`lib/session.mjs:56-94,102-160`,
  `lib/watcher.mjs:51`).
- No systemd / launchd units, no tunnels, no status line files.

### 7. SECRETS

- No credential material is read. It reads Claude conversation transcripts (`~/.claude/projects/*.jsonl`) to display
  sub agent activity in a terminal popup; these can contain prompts and tool output (data sensitivity only; the data
  never leaves the pane).
- At the pin, terminal escape sequences inside transcript text are not fully stripped (the newer `12e5bd6` adds
  CSI/OSC/DCS stripping). Impact: transcript text from a malicious repository could inject terminal control
  sequences into the popup. Low severity, local.

### 8. LICENCE

- `LICENSE` file present: MIT, "Copyright (c) 2026 silencechung" (`LICENSE:1-3`). GitHub API reports `MIT`.
  Redistribution inside the image is permitted if the notice is kept (the plugin checkout in the image keeps the file).

### Reviewer assessment

- Smallest attack surface of the three: no network, no credentials, no startup hook, no dependencies.
- The risky code path (`setup` editing user config) is not invoked by the add-on (23-06 decision).
- Prefer the newer HEAD if the human is willing to accept the diff review above; otherwise the pin is acceptable
  because the weaker hook / setup paths are inactive without `setup`.

Nothing from this plugin was installed or executed during this review.

## Plugin: herdr-web-service

### 1. Pin and fetch verification

- Repository: `i-montes/herdr-web-service` (MIT, 1 star, created 2026-10-09).
- Pin (research): `e9082b3fb969064e89153a8c6b2170366982f7f9`.
- `git fetch --depth 1 origin e9082b3fb969064e89153a8c6b2170366982f7f9` + detached checkout: OK.
- `git rev-parse HEAD` equals the pin: YES (exact match, 40/40 characters).
- No tag and no release exist.
- Current `main` HEAD (GitHub API, 2026-10-10): `e9082b3fb969064e89153a8c6b2170366982f7f9` - identical to the pin,
  `main` has not moved (nothing to diff). Pin commit date 2026-10-09T12:55:15-05:00.

### 2. Manifest summary (`herdr-plugin.toml`)

- `id = "imontes.herdr-web-service"`, `version = "0.2.0"`, `min_herdr_version = "0.9.0"`,
  `platforms = ["linux", "macos"]` (lines 1-6).
- `[[build]]` (lines 10-14), run only by `herdr plugin install`, NOT by `herdr plugin link`:
  - `["sh", "scripts/bun.sh", "install", "--frozen-lockfile"]`
  - `["sh", "scripts/bun.sh", "run", "build"]` (-> `bun --bun vite build --config web/vite.config.ts`,
    `package.json:67`)
- `[[startup]]` (lines 17-18): `["sh", "scripts/bun.sh", "scripts/plugin.ts", "start"]`.
- `[[actions]]`: `start`, `stop`, `status`, `uninstall` -> `scripts/plugin.ts <verb>`; `setup` ->
  `sh -c 'exec "${HERDR_BIN_PATH:-herdr}" plugin pane open --plugin "$HERDR_PLUGIN_ID" --entrypoint setup --focus'`
  (line 42; fixed string, no untrusted interpolation).
- `[[panes]]` `setup` (lines 50-56): popup, `scripts/plugin.ts setup` (the interactive wizard).
- Confirms the planning note: the add-on must run `bun install --frozen-lockfile` and `bun run build` itself, and
  `dist/index.html` is required before `start` (`scripts/plugin.ts:42-44`).

### 3. File inventory

- 149 tracked files, 17703 lines in total. Server `server/` (TypeScript, Bun), client `web/` (React 19 + Tailwind,
  built by vite), control scripts `scripts/`, shared protocol `shared/`, tests (`*.test.ts` next to the sources and
  `tests/`). Generated and binary assets: PNG icons in `web/public/`, SVG agent logos in `web/src/assets/agents/`.

### 4. EXECUTION SURFACE

- `scripts/bun.sh:5-9` locates `bun` (`command -v bun`, `$BUN_INSTALL/bin/bun`, `/opt/homebrew/bin/bun`,
  `/usr/local/bin/bun`), prepends its directory to PATH and `exec`s it with the manifest arguments.
- `scripts/plugin.ts:61-65` (`start`): `spawn(process.execPath, [ROOT/server/index.ts], { cwd, detached: true,
  stdio: [ignore, log, log], env: { ...process.env } })`, `child.unref()` at `:67`, pid written to
  `<state>/server.pid` (mode 0600, `:72`). The server inherits the complete environment of the herdr server process
  (this is where HA / Supervisor / Claude tokens would be inherited). The server code does not read any of them: the
  only environment reads outside `config.ts` are `HOME`, `USER`, `LOGNAME`, `CLAUDE_CONFIG_DIR`, `HERDR_BIN_PATH`
  (`scripts/setup/*.ts`, wizard only); `config.ts:52-69` reads `HOST`, `PORT`, `PUBLIC_URL`, `ACCESS_MODE`, `TUNNEL`,
  `DEV_ORIGIN`, `HERDR_SOCKET_PATH`, `HERDR_BIN_PATH`.
- `scripts/plugin.ts:46-58`: if a systemd/launchd unit file exists (`unitInstalled`, `scripts/setup/service.ts:144`,
  a plain `existsSync`), `start` goes through `systemctl` / `launchctl` instead. No unit exists in the container, so this
  branch is inactive.
- Server control surface (inherent to the product): `server/index.ts:379-385` creates sessions (`tab.create` /
  `workspace.create`, optional one-line shell `command` typed into the pane via `pane.send_text`,
  `server/herdr/launch.ts:152`, and `agent.start`, `:155`); `:391-396` `pane.send_input`; `:413-422` agent prompts and
  slash commands typed into panes; `:455-459` `pane.close`; `:375-378` read-only directory listing inside `$HOME`
  (`server/fsbrowse.ts`, resolves symlinks and refuses paths outside home). All of these sit behind the session
  cookie (`server/index.ts:247-249`).
- Wizard-only (`setup` pane / action; NOT run by the add-on):
  - `scripts/setup/tunnel/tailscale.ts:52` `bash -c "set -o pipefail; curl -fsSL https://tailscale.com/install.sh | sh"`.
  - `scripts/setup/tunnel/portal.ts:63` curl-pipe-bash installer from `github.com/gosuda/portal-tunnel` releases.
  - `scripts/setup/tunnel/run.ts:29,32`, `portal.ts:77`, `scripts/setup/service.ts:32` `Bun.spawn(argv)` for `tailscale`,
    portal, `systemctl` / `launchctl`.
  - `scripts/statusline.ts:64` `Bun.spawn(["sh", "-c", command])` runs a user's previously configured Claude status line
    command (only reachable after the wizard installed this plugin's status line into Claude `settings.json`).
  - `scripts/tui.ts:192` `stty sane`.
- No `eval` / `new Function` in server or client code.

### 5. NETWORK SURFACE

- Listener: `Bun.serve({ hostname: config.host, port: config.port })` (`server/index.ts:468-470`),
  default `127.0.0.1:7340` (`server/config.ts:52-53`, `DEFAULT_PORT` at `:14`). A warning is logged when bound to a
  non-loopback address without a password (`server/index.ts:532-534`).
- Outbound HTTP at runtime: only Web Push delivery to the browser's push endpoint
  (`server/push/webpush.ts:109`), restricted to `fcm.googleapis.com`, `push.services.mozilla.com`, `push.apple.com`,
  `notify.windows.com` over HTTPS without port or userinfo (`server/push/store.ts:23,34-35`). Only occurs when a
  browser registered a push subscription. No credential is sent; the payload is a notification (title, body, url).
- Local-only: unix socket to the herdr server (`server/herdr/client.ts`, `config.herdrSocket`), `fetch` to its own
  `/api/health` (`scripts/plugin.ts:30`).
- Wizard-only outbound: `scripts/setup/verify.ts` (probes a user-supplied URL), the two installer downloads above.
- No telemetry, no analytics, no other hostnames in `server/`, `web/src/`, `scripts/` (searched).
- Security posture of the server (file:line):
  - Host allow-list: `localhost`, `127.0.0.1`, `::1`, host of `PUBLIC_URL`, bind host in `lan` mode
    (`server/access.ts:139-151`); enforced first (`server/index.ts:230`, 421 on mismatch).
  - Origin allow-list for non-GET requests and for `/ws` (required there): exact origins `http://localhost:PORT`,
    `http://127.0.0.1:PORT`, `http://[::1]:PORT`, `PUBLIC_URL`, bind address in `lan` mode, `DEV_ORIGIN`
    (`server/access.ts:163-183`, enforced `server/index.ts:231-233`, 403 on mismatch).
  - Login transport rules: `remote` needs HTTPS, `lan` accepts HTTP, `local` only from a loopback peer
    (`server/access.ts:185-190`). `X-Forwarded-For` / `X-Forwarded-Proto` are trusted only when the TCP peer is
    loopback (`server/access.ts:113-126`) - correct behind an nginx on 127.0.0.1.
  - Password gate: all `/api/*` (except `/api/health`, `/api/auth/login`, `/api/session`) and `/ws` require a session;
    without a configured password the API answers 401 "run setup first" (`server/index.ts:247-249`). `/api/session`
    discloses only `authenticated` and `setup_required` to anonymous callers (`:196-198`).
  - Password: argon2id via `Bun.password` (`memoryCost 65536, timeCost 3`, `server/auth/password.ts:52`); policy
    >= 6 characters + symbol + number + uppercase (`:14-28`); login rate limiting per address and globally
    (`server/auth/ratelimit.ts`, window 10 min at `:16`).
  - Session cookie: `hwv_session=<token>; Path=/; HttpOnly; SameSite=Strict; [Max-Age]; [Secure]`
    (`server/auth/sessions.ts:117-120`); only the SHA-256 of the token is stored (`:19`), file mode 0600 (`:59-60`).
  - Response headers on every response (`server/access.ts:192-203`): CSP
    `default-src 'self'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'`,
    `x-content-type-options: nosniff`, `referrer-policy: no-referrer`, HSTS when secure. Note `frame-ancestors 'none'`
    forbids the HA iframe; the later nginx step has to drop it (as in research) - this is a conscious relaxation.
  - Static file handler: `server/index.ts:219-221` uses `candidate.startsWith(config.distDir)` without a trailing
    separator. After `new URL` normalisation and `join`, a path could only reach a sibling directory whose name starts
    with `dist` (none exists in the plugin root, which contains only `dist`). Informational, no exploitable path found.
  - `development: false` so Bun's error page is never rendered (`server/index.ts:472`); request body cap `10 MB + 1 MB`
    (`:474`); uploads limited to PNG/JPEG/GIF/WebP (`server/uploads.ts`, files 0600 in a 0700 directory).
- Root-absolute client URLs that block hosting under a sub-path (the edit list for the later spike):
  - `web/src/api.ts:48-73`: every API URL starts with `/api/` (`pane()` helper at `:48`, `session` `:51`, `login` `:53`,
    `logout` `:54`, `roster` `:55`, `folders` `:56`, `createSession` `:57`, `upload` `:61`, `pushKey` `:68`,
    `pushSubscribe` `:69`, `pushUnsubscribe` `:70`, `signIns` `:71`, `signOutDevice` `:72`, `signOutOthers` `:73`).
  - `web/src/roster.ts:48`: `new WebSocket(`${protocol}://${location.host}/ws`)`.
  - `web/src/main.tsx:13`: `navigator.serviceWorker.register("/sw.js")`.
  - `web/src/InstallBanner.tsx:18`: `<img src="/icon-192.png">`.
  - `web/src/ChatView.tsx:467-468`: `/api/uploads/${name}` (link and image).
  - `web/index.html:9-11`: `/manifest.webmanifest`, `/icon-192.png`, `/apple-touch-icon.png`; line 19 `/src/main.tsx`
    (rewritten by vite from its `base`).
  - `web/public/manifest.webmanifest:6-8`: `"id": "/"`, `"start_url": "/"`, `"scope": "/"`.
  - `web/public/sw.js:20,23,39,43,64,72`: `/api/`, `/ws`, `/assets/`, `"/"` as navigation cache key and
    notification URL fallback.
  - Also relevant: `web/src/Home.tsx:25` and `web/src/OpenOnPhone.tsx:38` derive URLs from `location.host` / `hash`.
  - Dev proxy `web/vite.config.ts:16-17` (`/api`, `/ws`) is development only.

### 6. FILESYSTEM WRITES (outside the plugin's own config and state directories)

- Plugin config / state directories (`server/config.ts:19-22`): `HERDR_PLUGIN_CONFIG_DIR` (default
  `~/.config/herdr/plugins/config/<id>`) and `HERDR_PLUGIN_STATE_DIR`, created 0700. Written there: `auth.json` (password
  hash), `sessions.json`, `server.pid`, `server.log`, push subscriptions and VAPID keys (0600), a `.env` file in the
  config dir (written only by the wizard, read at startup `server/config.ts:41-48`), `claude-statusline.json`.
- Uploaded images: `server/uploads.ts:42-45` writes to a 0700 temp directory (`uploadDir()`), 0600 files, cleaned after
  a week (`server/index.ts:521-523`).
- Outside its own directories - wizard / action only, none of it run by the add-on:
  - Claude Code `settings.json` `statusLine` entry (`scripts/setup/statusline.ts:2-6,29-34,65-66`) - registers or chains
    `scripts/statusline.ts`; `uninstall` restores it.
  - systemd user units / launchd agents (`scripts/setup/service.ts:173-174,202`).
  - Tunnel software installed by `curl | sh` (see execution surface).
- `scripts/statusline.ts:34-37` (invoked by Claude after the wizard installed it) writes the status snapshot into the
  plugin state dir.
- The runtime server (start action) writes nothing outside its two directories and the uploads temp directory.

### 7. SECRETS

- The server stores a password hash (argon2id) and session token hashes; the plaintext password is only read from a TTY
  / pipe by `set-password` (`scripts/plugin.ts:162-165`, "asks for the password without echo (or reads one line from a
  pipe)") and never logged.
- It inherits the herdr server environment (`scripts/plugin.ts:65`) but does not read, log or forward `HA_TOKEN`,
  `SUPERVISOR_TOKEN` or Claude tokens (search for `SUPERVISOR|HA_TOKEN|HASSIO|ANTHROPIC|CLAUDE` finds only
  `CLAUDE_CONFIG_DIR` in the wizard). Child processes started through the web UI (panes) are created by the herdr
  server, not by this plugin, and inherit herdr's environment as they would anyway.
- Residual risk: the plugin reads agent transcripts and screens (`pane.read`, `~/.claude/projects`,
  `server/index.ts:330-362`) and returns them to the authenticated browser. That is the feature.

### 8. LICENCE

- `LICENSE` present: MIT, "Copyright (c) 2026 Ivan Montes". `package.json:7` `"license": "MIT"`. GitHub API: `MIT`.
  Redistribution inside the image is permitted if the notice is kept.

### npm dependencies (lockfile-resolved)

- `bun.lock` (`lockfileVersion 1`): 220 locked packages, all with `sha512` integrity (220/220), no git, file, link,
  workspace or non-registry sources (searched). There is no `trustedDependencies` entry in `package.json` or `bun.lock`
  (searched, none). Bun does not run dependency lifecycle scripts unless a package is trusted; `bun install` also has a
  built-in default-trusted list, and none of the 220 locked packages needs it: `npm view` of all 220 resolved
  `name@version` for `preinstall` / `install` / `postinstall` / `gypfile` reports one hit, `fsevents@2.3.3`
  (`node-gyp rebuild`, macOS-only optional dependency, not installed on Linux).
- `package.json` direct dependencies (lock-resolved version, publish date from `npm view <pkg> time --json`):
  - `@fontsource-variable/bricolage-grotesque` ^5.3.0 -> 5.3.0, 2026-07-19, SLSA provenance, verdict OK
  - `@fontsource-variable/jetbrains-mono` ^5.3.0 -> 5.3.0, 2026-07-19, SLSA provenance, verdict OK
  - `qrcode-generator` ^2.0.4 -> 2.0.4, 2025-08-07, verdict OK
  - `react` ^19.3.0 -> 19.3.0, 2026-09-09, SLSA provenance, verdict OK
  - `react-dom` ^19.3.0 -> 19.3.0, 2026-09-09, SLSA provenance, verdict OK
  - `react-markdown` ^10.1.0 -> 10.1.0, 2025-03-07, verdict OK
  - `remark-gfm` ^4.0.1 -> 4.0.1, 2025-02-10, verdict OK
- `package.json` devDependencies (build-time only; their output is bundled into `dist/`):
  - `@tailwindcss/vite` ^4.3.3 -> 4.3.3, 2026-07-16, SLSA provenance, verdict OK
  - `@types/bun` ^1.4.2 -> 1.4.2, 2026-09-08, verdict OK
  - `@types/react` ^19.3.0 -> 19.3.0, 2026-09-09, verdict OK
  - `@types/react-dom` ^19.3.0 -> 19.3.0, 2026-09-09, verdict OK
  - `tailwindcss` ^4.3.3 -> 4.3.3, 2026-07-16, SLSA provenance, verdict OK
  - `typescript` ^7.0.2 -> 7.0.2, 2026-07-08, verdict OK
  - `@vitejs/plugin-react` ^6.1.2 -> **6.1.2**, published 2026-10-05, SLSA provenance, 96.5M weekly downloads,
    verdict **SUS (`too-new`)**
  - `vite` ^8.3.4 -> **8.3.4**, published 2026-10-08, SLSA provenance, 193.9M weekly downloads,
    verdict **SUS (`too-new`)**
- Legitimacy tool: `gsd_run query package-legitimacy check --ecosystem npm vite @vitejs/plugin-react ...`. The tool
  takes package names only (it resolves the registry `latest`); a `name@version` argument is misread as a package
  name and returns a false `SLOP / does-not-exist`, so that form must not be used. The by-name result applies to the
  lockfile versions because `npm view <pkg> dist-tags.latest` returns exactly `vite` 8.3.4 and `@vitejs/plugin-react`
  6.1.2 on 2026-10-10, identical to the locked versions.
- Verdict for the two flagged packages:
  - Only reason code is `too-new` (published 2 and 5 days before the review). Both exist, are not deprecated, have no
    install scripts, have a GitHub repository (`github.com/vitejs/vite`, `github.com/vitejs/vite-plugin-react`) and
    carry registry-verified SLSA provenance attestations. Download volumes of 97M and 194M per week make a
    typosquat / slopsquat implausible. Classification: false-positive class (a very popular project releasing a fresh
    version), no `SLOP` verdict.
  - They are build-time tools only: they run in the image build (`bun --bun vite build`), and are not part of the
    runtime server. Residual risk is the normal risk of consuming a release that has had little time to be scrutinised.
  - Mitigation available if the human wants it: re-resolve with the previous `vite` 8.x / `@vitejs/plugin-react` 6.x
    release in the plugin lockfile (would be a patch of the third-party lockfile and diverges from `--frozen-lockfile`
    of the pinned commit; not recommended, listed for completeness).

### Reviewer assessment

- Largest surface of the three. The server itself is carefully built (loopback bind, Host and Origin allow-lists,
  password gate with argon2id and rate limiting, HttpOnly + SameSite=Strict cookie, CSP, no telemetry).
- The product is a remote terminal controller: a signed-in browser can create shells, send keystrokes and agent prompts
  to any pane, as root in the add-on. The password plus HA ingress authentication are the only boundary. Without a
  configured password the API refuses everything (`server/index.ts:249`).
- It inherits herdr's environment, so the HA tokens are in the web server's process environment (not read by its code).
- Wizard / tunnel / status line / systemd code (curl-pipe-shell installers, Claude `settings.json` edits) is present but
  only reachable through the `setup` and `uninstall` actions, which the add-on never invokes.
- Build requires network access to the npm registry during the image build (`bun install --frozen-lockfile`).

Nothing from this plugin was installed or executed during this review.

## Plugin: herdr-claude-limits

### 1. Pin and fetch verification

- Repository: `martin-saldinger/herdr-claude-limits` (NO licence, 0 stars, created 2026-10-09).
- Pin (research): `9c0c9a1931ac91f9d865031e2dc58d66a7d1b594`.
- `git fetch --depth 1 origin 9c0c9a1931ac91f9d865031e2dc58d66a7d1b594` + detached checkout: OK.
- `git rev-parse HEAD` equals the pin: YES (exact match, 40/40 characters).
- No tag and no release exist; the repository has 3 commits.
- Current `main` HEAD (GitHub API, 2026-10-10): `9c0c9a1931ac91f9d865031e2dc58d66a7d1b594` - identical to the pin,
  `main` has not moved (nothing to diff). Pin commit date 2026-10-08T22:48:29-05:00.

### 2. Manifest summary (`herdr-plugin.toml`)

- `id = "martin.claude-limits"`, `version = "0.1.0"`, `min_herdr_version = "0.9.0"`,
  `platforms = ["linux", "macos"]` (lines 1-6).
- `[[build]]`: none.
- `[[startup]]` (lines 8-9): `["sh", "bin/start.sh"]`.
- `[[actions]]` `show` (11-15): `["sh", "bin/open.sh"]`, `restart` (17-21): `["sh", "bin/start.sh"]`.
- `[[panes]]` `detail` (23-29): popup, `["sh", "bin/detail.sh"]`.

### 3. File inventory

- 8 tracked files, 264 lines: `herdr-plugin.toml` (29), `README.md` (30), `bin/start.sh` (15), `bin/open.sh` (2),
  `bin/status.sh` (10), `bin/detail.sh` (22), `bin/poller.sh` (106), `bin/limits.jq` (50). No `LICENSE`.
  Runtime tools needed: `sh`, `bash` (`detail.sh`), `curl`, `jq`, `stat`, `date`, `sed`.

### 4. EXECUTION SURFACE

- `bin/start.sh:13` `nohup sh "$HERDR_PLUGIN_ROOT/bin/poller.sh" >>"$state/poller.log" 2>&1 </dev/null &` - detached
  poller, pid file `bin/start.sh:6,14`. Before starting, it kills the pid recorded in its own pid file
  (`bin/start.sh:8-11`); a stale pid file after PID reuse could kill an unrelated process (low risk, root inside the
  add-on, own state directory).
- `bin/poller.sh:23` sources `$HERDR_PLUGIN_CONFIG_DIR/config.env` as shell code (`. file`), the user-editable
  option file of the plugin; it lives in the add-on's persistent config directory, so writing it already requires
  the access that would make the poller irrelevant. Absent by default.
- `bin/poller.sh:39` `security find-generic-password` (macOS Keychain; absent on Linux, failure is silenced and the file
  fallback is used).
- `bin/poller.sh:47` `curl -sS -m 15 ... https://api.anthropic.com/api/oauth/usage` (see network surface).
- `bin/poller.sh:68` `"$herdr" pane list`, `:92,97` `"$herdr" pane report-metadata` (only with `SIDEBAR=1`, off by default).
  Fixed argv; `$herdr` is `${HERDR_BIN_PATH:-herdr}` (`:15`).
- `bin/open.sh:2` `exec herdr plugin pane open --plugin "$HERDR_PLUGIN_ID" --entrypoint detail`.
- `bin/status.sh:9` and `bin/detail.sh:11` run `jq` over the cache file with the local `limits.jq` module.
- The poller exits on its own when the herdr server has been unreachable for 60 s (`bin/poller.sh:68-73`).
- No `eval`; no shell command is built from remote data (the API response is parsed with `jq` only).

### 5. NETWORK SURFACE

- Exactly one outbound endpoint: `https://api.anthropic.com/api/oauth/usage` (`bin/poller.sh:47-51`), every 180 s by
  default (`FETCH_INTERVAL`, `:18`), with backoff to a maximum of 600 s on HTTP 429 (`:54`).
- Credentials sent: the Claude Code OAuth access token as `Authorization: Bearer <token>` (`bin/poller.sh:49`) plus the
  headers `anthropic-beta: oauth-2025-04-20` and `User-Agent: herdr-claude-limits/0.1`. The destination host is
  Anthropic's own API host. The token is passed on the `curl` command line, so it is visible in the process list to
  other users of the same container (all root in the add-on; informational).
- No other URL, hostname, socket or listener (searched; `README.md` mentions none).

### 6. FILESYSTEM WRITES (outside the plugin's own config and state directories)

- None. Writes go only to `$HERDR_PLUGIN_STATE_DIR`: `poller.pid` (`bin/start.sh:14`), `poller.log` (`:13`),
  `usage.json` and `usage.json.tmp` (`bin/poller.sh:47,53`).
- It never edits Claude `settings.json` or herdr `config.toml`. Showing the tab-bar summary and the key binding needs
  the user to edit `~/.config/herdr/config.toml` themselves (`README.md:11-23`); the add-on does not do that
  (decision D-02). The popup action `show` can be invoked without config.

### 7. SECRETS

- Reads the Claude Code credentials: macOS Keychain item `Claude Code-credentials` or
  `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.credentials.json` (`bin/poller.sh:38-43`), extracts
  `.claudeAiOauth.accessToken` with `jq -er`. It does not read the refresh token and never refreshes the token
  (comment `:36-37`: refreshing would log Claude Code out).
- Destination of the token: only `api.anthropic.com` (section 5). Confirmed.
- Not logged and not written elsewhere: `log()` (`bin/poller.sh:34`) is only called with fixed strings or the HTTP
  status code (`:46,51,56,60,71`); the response body goes to `usage.json.tmp` and contains plan usage, not the token.
  Verified by reading all 106 lines.
- Without an interactive `claude login` credentials file there is nothing to read; the poller logs
  "no Claude Code credentials found" to `poller.log` and keeps running (research Pitfall 7, decision D-07).

### 8. LICENCE

- **No licence file.** The repository contains no `LICENSE`, `COPYING` or equivalent (`git ls-files` search), the README
  has no licence statement, and the GitHub API reports `license: null`.
- Without a licence, copyright law applies by default: the code is all-rights-reserved and no right to copy,
  modify or redistribute is granted. This add-on's image is published on `ghcr.io` (public), so including this plugin
  in the image is a redistribution the author has not permitted. The user must explicitly accept this risk or reject
  the plugin. Alternative: ask the author (`martin-saldinger`) to add a licence before the plugin is bundled.

### Reviewer assessment

- Technically the smallest and cleanest of the three (264 lines, a single fixed endpoint, no config writes).
- The only open issue is the licence status, which is a legal decision, not a technical one.
- The token is the same one Claude Code itself uses, held by a process inside the add-on that is already root.

Nothing from this plugin was installed or executed during this review.

## Decision

Date: 2026-10-11

User answer (verbatim): `approved: all`

All three plugins are approved at the reviewed research pins. No re-pin was requested. The approval also covers:

- the redistribution of herdr-claude-limits (no licence file) in the public ghcr.io image,
- the execution surface (plugins run as root inside the add-on with HA_TOKEN / SUPERVISOR_TOKEN in the herdr server
  environment),
- `vite` 8.3.4 and `@vitejs/plugin-react` 6.1.2 (both flagged `too-new`) as build-time dependencies resolved from the
  plugin's own `bun.lock`.

Accepted risks (recorded by the user's approval):

- herdr-claude-limits has no licence file: the code is all-rights-reserved, and bundling it in a public image is a
  redistribution the author has not permitted. Accepted by the user on 2026-10-11.
- herdr-subagent-watch is pinned to the older `c47d49b247d8ca3387d88d5bb9731a3b7bf4f6a8`; upstream `main`
  (`c9cf7538855606af8b54ba30097eea6a6ec48be5`) is 10 commits ahead and fixes hook, setup and viewer defects (PATH
  lookup, runtime directory checks, terminal escape stripping). The weaker paths are inactive in the add-on because
  `setup` is never run. Kept at the reviewed pin; a re-pin would need a diff review first.

Final pins (machine-readable, consumed by plans 23-04, 23-06 and 23-07):

PIN HERDR_SUBAGENT_WATCH_REF c47d49b247d8ca3387d88d5bb9731a3b7bf4f6a8
PIN HERDR_WEB_SERVICE_REF e9082b3fb969064e89153a8c6b2170366982f7f9
PIN HERDR_CLAUDE_LIMITS_REF 9c0c9a1931ac91f9d865031e2dc58d66a7d1b594
