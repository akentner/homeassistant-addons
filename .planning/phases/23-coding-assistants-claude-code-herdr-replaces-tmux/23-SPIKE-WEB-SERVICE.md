VERDICT: GO

# Phase 23: herdr-web-service sub-path spike

Produced by plan 23-04 on 2026-10-11 by running `bash internal/spike-herdr-web-service.sh` (final run: 9/9 PASS, exit
0). All plugin code (fetch, patch, `bun install`, `bun run build`, `herdr server`, the plugin's bun server, both nginx
instances, every check) ran inside a throwaway container from `ghcr.io/home-assistant/amd64-base-debian:bookworm`
(`build.yaml` `build_from.amd64`). The host only ran `docker` (podman emulation). No add-on or HA credential was passed
into the container; the only mounts are the patch, the inner script and the nginx block, all read-only.

Consumers: plan 23-06 (Dockerfile web-service step) copies the patch and the build sequence below; plan 23-07 copies
the nginx block into `coding-assistants/nginx.conf` and re-proves it in the harness scenario `services`. Both halt on
their precondition when this first line is `VERDICT: NO-GO`.

## Pin used

`e9082b3fb969064e89153a8c6b2170366982f7f9` (`PIN HERDR_WEB_SERVICE_REF` in `23-PLUGIN-REVIEW.md`, approved by the user on
2026-10-11). The spike fetches exactly this sha (`git fetch --depth 1 origin <sha>`, detached checkout) and asserts
`git rev-parse HEAD` equals it before anything else happens. herdr is the release binary `v0.9.3`
(`herdr-linux-x86_64`, sha256 `18a8dc65f1c2fa485884344356dea1cfd911c6f06cf46fa78e193f4087f4dba7`, verified with
`sha256sum -c`). The constants live at the top of the spike script; the Dockerfile ARGs from plan 23-05 are the source
of truth and must keep matching them.

## Patch summary

File: `coding-assistants/patches/herdr-web-service-subpath.patch` (generated with `git diff HEAD` against the pinned
checkout, `git apply --check` + `git apply` pass at exactly that commit on every spike run). 9 files, +33 / -118 lines.
No file under `server/` is touched (server-side behaviour is unchanged; everything is client URL handling).

| File | Change | Why |
|------|--------|-----|
| `web/vite.config.ts` | `base: "./"` (+2) | every built asset URL becomes relative (`./assets/...`) |
| `web/src/api.ts` | every `/api/...` literal becomes `api/...` (+16 / -14) | `fetch("api/x")` resolves against the page URL, which always ends in `/services/` under ingress |
| `web/src/roster.ts` | WebSocket URL built as `new URL("ws", location.href)` with `ws:`/`wss:` protocol (+3 / -2) | no `location.host` + root `/ws` |
| `web/src/main.tsx` | service-worker registration and its message listener removed (+1 / -10) | a root-scoped `/sw.js` cannot work under a sub-path, and push needs HTTPS the ingress hop does not provide |
| `web/public/sw.js` | file deleted (-82) | dead code once nothing registers it; it also carried root-absolute strings that C3 would flag |
| `web/src/alerts.ts` | `supported = () => false` (+2 / -1) | push is reported as unsupported instead of hanging on `navigator.serviceWorker.ready` |
| `web/src/InstallBanner.tsx` | `icon-192.png` instead of `/icon-192.png` | relative |
| `web/src/ChatView.tsx` | `api/uploads/${name}` instead of `/api/uploads/${name}` (2 places) | relative |
| `web/public/manifest.webmanifest` | `id`, `start_url`, `scope` become `./`; icon `src` relative | the install manifest must not point at the HA root |

`web/index.html` is left untouched on purpose: Vite rewrites its `/manifest.webmanifest`, `/icon-192.png`,
`/apple-touch-icon.png` links to `./...` once `base: "./"` is set (visible in the built `index.html` in the transcript).
The router uses `location.hash`, which is sub-path safe.

## Validated nginx block

Exactly as the spike used it (single source in the script, echoed at the end of every run). Paste into the `server`
block of `coding-assistants/nginx.conf`; the existing `map $http_upgrade $connection_upgrade` in the `http` block is
required and already present.

```nginx
        # herdr-web-service (plugin on 127.0.0.1:7340), reached through HA ingress as <ingress>/services/
        # relative redirect: an absolute Location would leave the HA ingress prefix
        location = /services { absolute_redirect off; return 301 services/; }
        location /services/ {
            proxy_pass http://127.0.0.1:7340/;              # trailing slash strips the /services/ prefix
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host 127.0.0.1:7340;           # plugin allows only localhost/127.0.0.1/::1 hosts
            proxy_set_header Origin http://127.0.0.1:7340;  # /ws requires an allowed Origin (loopback only)
            proxy_set_header X-Forwarded-For "";            # HA ingress sends these; the plugin trusts them from a
            proxy_set_header X-Forwarded-Proto "";          # loopback peer and would turn cookies Secure / add HSTS
            proxy_hide_header Content-Security-Policy;      # plugin sends frame-ancestors 'none' (blocks the iframe)
            proxy_hide_header Strict-Transport-Security;    # never let it leak onto the HA origin
            add_header Content-Security-Policy "default-src 'self'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'self'; base-uri 'none'" always;
            proxy_read_timeout 86400;
            proxy_send_timeout 86400;
        }
```

Differences from the block in `23-RESEARCH.md` Pattern 5: the two `X-Forwarded-*` lines (explicitly emptied, see Open
issues item 1). Everything else is identical.

How it was exercised: an OUTER nginx on 8123 emulates HA ingress (`location /api/hassio_ingress/SPIKETOKEN/`,
`proxy_pass http://127.0.0.1:8099/`, `Host`, `Origin` and `Cookie` passed through unchanged, WebSocket upgrade headers,
plus the headers real HA ingress adds: `X-Forwarded-For`, `X-Forwarded-Proto https` as the worst case, and
`X-Ingress-Path`). An INNER nginx on 8099 represents the add-on (the `connection_upgrade` map plus the block above).
Requests carried `Host: ha.invalid:8123` and `Origin: http://ha.invalid:8123`.

## Build sequence for the Dockerfile

The ordered commands that worked (plan 23-06 must run them in this order; `${REF}` is the
`HERDR_WEB_SERVICE_REF` ARG, the patch is `COPY`ed to a temporary path first):

1. `mkdir -p /opt/herdr-plugins/herdr-web-service && cd /opt/herdr-plugins/herdr-web-service`
2. `git init -q . && git remote add origin https://github.com/i-montes/herdr-web-service.git`
3. `git fetch -q --depth 1 origin "${REF}"` then `git checkout -q --detach FETCH_HEAD`
4. assert `[ "$(git rev-parse HEAD)" = "${REF}" ]`
5. `git apply --check /tmp/herdr-web-service-subpath.patch` then `git apply /tmp/herdr-web-service-subpath.patch`
   (a moved pin fails the build here, loudly)
6. `bun install --frozen-lockfile` (153 packages, about 10 s, node_modules 148 MB)
7. `bun run build` (runs `bun --bun vite build --config web/vite.config.ts`, under 1 s; `dist/` 784 KB)
8. assert `test -f dist/index.html`
9. production prune, proven safe: `rm -rf node_modules && bun install --frozen-lockfile --production`
   (109 packages, node_modules 19 MB; the server, login and WebSocket all ran on the pruned tree)
10. `rm -rf /root/.bun/install/cache` (153 MB) and remove the temporary patch file
11. `rm -rf .git` is expected to be safe (the plugin never reads it) but was NOT exercised by the spike, which ran
    with `.git` present; the 23-06 plugins scenario re-proves it. If it ever breaks the start, keep `.git`.
12. final asserts: `test -f dist/index.html`, and the built JavaScript contains no quote- or backtick-prefixed root-absolute
    `/api/`, `/ws` or `/sw.js` string (the spike's C3 regex also covers `/assets/`, `/manifest`, `/icon`,
    `/apple-touch`, scanned over `dist/**/*.js`).

`herdr plugin link` skips the manifest `[[build]]` steps (only `plugin install` runs them), so steps 6 and 7 are ours.
`bun` must be on PATH for the startup hook; `scripts/bun.sh` found it with a minimal `PATH=/usr/local/bin:/usr/bin:/bin`
(the Dockerfile symlinks `/usr/local/bin/bun`).

## Runtime findings

- **Startup hook:** the plugin's `[[startup]]` entry (`sh scripts/bun.sh scripts/plugin.ts start`) ran by itself after
  `herdr server` started; `/api/health` answered `{"ok":true,"version":"0.2.0"}` within the 30 s window with no manual
  start. The plugin must be linked BEFORE the server starts (the spike did `herdr plugin link` first), as already
  planned for run.sh. The bun server runs as `/root/.bun/bin/bun /opt/herdr-plugins/herdr-web-service/server/index.ts`,
  a child detached from herdr (no systemd involved).
- **bun discovery:** `scripts/bun.sh` located bun through `command -v bun` (bun 1.4.3); no `BUN_INSTALL` needed.
- **State directory actually used:** `/root/.local/state/herdr/plugins/imontes.herdr-web-service/` (`server.pid`,
  `server.log`). It follows `XDG_STATE_HOME`/`$HOME`, NOT `XDG_CONFIG_HOME`; in the add-on that is inside the container
  filesystem, not `/data`, unless run.sh exports `XDG_STATE_HOME`. This is acceptable (pid and log are recreated on
  every start) and is noted for the 23-06/23-07 run.sh work (backup size and log location).
- **Config directory:** `herdr plugin config-dir imontes.herdr-web-service` printed
  `/data/.config/herdr/plugins/config/imontes.herdr-web-service` with `XDG_CONFIG_HOME=/data/.config` (the add-on's
  value), so `auth.json` (mode 600) persists in `/data`. The running server picked up the new password without a
  restart (login switched from 503 to 401/204 right after `set-password`).
- **Password setup:** `printf '%s\n' "$PASSWORD" | HERDR_PLUGIN_CONFIG_DIR=$(herdr plugin config-dir
  imontes.herdr-web-service) bun scripts/plugin.ts set-password` printed `password saved` and wrote `auth.json`;
  `Verify-Pass1!` satisfies the plugin's rules (6+ characters, symbol, number, uppercase).
- **Session cookie:** `hwv_session=...; Path=/; HttpOnly; SameSite=Strict`, no `Secure` flag, no HSTS, even though the
  emulated ingress sent `X-Forwarded-Proto: https` (the block empties both X-Forwarded headers).
- **`/api/session`:** ungated, returned `{"authenticated":false,"setup_required":true}` before the password existed and
  `authenticated` true only with the cookie afterwards. `/api/roster` is the gated probe (200 with the cookie, 401
  without).
- **WebSocket:** `.../services/ws` returned `101 Switching Protocols` with the cookie and `401` without; the curl
  timeout after the 101 is expected.
- **Sizes:** `node_modules` 148 MB before the prune and 19 MB after; bun cache 153 MB (removed); `dist/` 784 KB;
  `bun install` about 10 s, `bun run build` under 1 s.
- **herdr noise:** `herdr server` prints "did you mean to open the Herdr TUI?" when started headless; harmless.

## Check table

| ID | Check | Result |
|----|-------|--------|
| C1 | `GET .../services` returns 301 with a relative `Location: services/` | PASS |
| C2 | index 200, no root-absolute `src`/`href`, every referenced asset 200 (5 of 5), no root-absolute CSS `url()` | PASS |
| C3 | built JavaScript has no quote-prefixed `/api/`, `/ws`, `/sw.js`, `/assets/`, `/manifest`, `/icon` string | PASS |
| C4 | login 503 before a password, 401 for a wrong one, 204 + `hwv_session` HttpOnly, not Secure, for the right one | PASS |
| C5 | `/api/session` reports `setup_required` / `authenticated` correctly; `/api/roster` 200 with the cookie, 401 without | PASS |
| C6 | WebSocket upgrade 101 with the cookie, refused (401) without | PASS |
| C7 | exactly one CSP header with `frame-ancestors 'self'` and no `'none'`; no Strict-Transport-Security on the index or the login response | PASS |
| C8 | direct request to 127.0.0.1:7340 with `Host: evil.invalid` rejected (421); loopback Host still 200 | PASS |
| C9 | production prune: `bun install --frozen-lockfile --production` ok, `dist/index.html` kept, server healthy and login/WebSocket working on the pruned tree | PASS |

## Open issues

1. **X-Forwarded-For / X-Forwarded-Proto are emptied in the block (deviation from the plan, which only said "do not
   set"):** nginx forwards client request headers it does not override, and real HA ingress adds both. The plugin trusts
   them when the TCP peer is loopback (nginx qualifies), which per `server/access.ts` would mark the cookie `Secure` and
   add HSTS on plain-http LAN access and key its rate limiter on the browser address. Emptying them is deterministic and
   is what the spike validated (the emulated ingress sent `X-Forwarded-Proto: https` and no `Secure` flag or HSTS
   resulted). The converse (without the two lines) was derived from the source, not run.
2. **No real browser and no real HA ingress.** The page, API and WebSocket paths are proven with curl against an emulated
   ingress, and C3 proves statically that the shipped JavaScript contains no root-absolute string; the React app itself
   was not executed. A manual check of `<HA>/api/hassio_ingress/<token>/services/` in a browser (login page renders, sign
   in, roster loads, no console 404) belongs in the final human verification of plan 23-09 / UAT.
3. **Push notifications and PWA install are dropped by design** (no service worker; `supported()` is false).
4. **Residual exposure matches the ttyd path (threat T-23-17):** nginx rewrites Host and Origin to loopback values, so
   the plugin's origin check does not protect requests that arrive through nginx; the plugin password (argon2id, 503
   until set), the HttpOnly SameSite=Strict cookie, the WebSocket cookie requirement (C4 to C6) and HA ingress admin
   authentication remain in force. Other containers on the hassio network can reach the add-on's port 8099 exactly as
   they can reach `/terminal/` today.
5. **`.git` removal is untested in the spike** (build sequence item 11).
6. The state directory is outside `/data` (see Runtime findings); only the config directory persists.

## Transcript of the final run

Verbatim output of `bash internal/spike-herdr-web-service.sh` (ANSI colour codes stripped; the fixture password
`Verify-Pass1!` is a throwaway value that exists only inside the container; the session token is not printed):

```text
== herdr-web-service sub-path spike (throwaway container) ==
pin:        e9082b3fb969064e89153a8c6b2170366982f7f9
base image: ghcr.io/home-assistant/amd64-base-debian:bookworm
herdr:      v0.9.3
== running the throwaway container spike-hws-896884 ==
Emulate Docker CLI using podman. Create /etc/containers/nodocker to quiet msg.
== 1. toolchain ==
FINDING bun: 1.4.3
FINDING nginx: nginx version: nginx/1.22.1
== 2. herdr release binary (digest verified) ==
/usr/local/bin/herdr: OK
FINDING herdr: herdr 0.9.3
== 3. plugin at the pinned commit + patch ==
FINDING checkout: e9082b3fb969064e89153a8c6b2170366982f7f9
patch applied; diffstat:
     web/public/manifest.webmanifest | 12 +++---
     web/public/sw.js                | 82 -----------------------------------------
     web/src/ChatView.tsx            |  4 +-
     web/src/InstallBanner.tsx       |  2 +-
     web/src/alerts.ts               |  3 +-
     web/src/api.ts                  | 30 ++++++++-------
     web/src/main.tsx                | 11 +-----
     web/src/roster.ts               |  5 ++-
     web/vite.config.ts              |  2 +
     9 files changed, 33 insertions(+), 118 deletions(-)
FINDING patch touches server/: 0
== 4. bun install --frozen-lockfile + bun run build ==
    + remark-gfm@4.0.1

    153 packages installed [10.16s]
    dist/assets/bricolage-grotesque-latin-ext-opsz-normal-IcJDqblK.woff2    30.73 kB
    dist/assets/jetbrains-mono-latin-wght-normal-B9CIFXIH.woff2             40.40 kB
    dist/assets/bricolage-grotesque-latin-opsz-normal-Cre6nC2_.woff2        76.88 kB
    dist/assets/index-BKniRr8d.css                                          45.89 kB │ gzip:  11.96 kB
    dist/assets/ChatView-BOx2lNai.js                                       178.14 kB │ gzip:  53.32 kB
    dist/assets/index-BLmHMmZZ.js                                          329.70 kB │ gzip: 101.08 kB

    ✓ built in 266ms
FINDING dist/index.html present; dist size: 784K
FINDING node_modules before prune: 148 MB
FINDING bun cache before removal: 153 MB
built index.html:
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
        <meta name="theme-color" media="(prefers-color-scheme: light)" content="#f3f1ea" />
        <meta name="theme-color" media="(prefers-color-scheme: dark)" content="#141412" />
        <title>Herdr Web</title>
        <link rel="manifest" href="./manifest.webmanifest" />
        <link rel="icon" type="image/png" sizes="192x192" href="./icon-192.png" />
        <link rel="apple-touch-icon" href="./apple-touch-icon.png" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
        <meta name="apple-mobile-web-app-title" content="Herdr" />
        <script type="module" crossorigin src="./assets/index-BLmHMmZZ.js"></script>
        <link rel="stylesheet" crossorigin href="./assets/index-BKniRr8d.css">
      </head>
      <body>
        <div id="root"></div>
      </body>
    </html>
== 5. production prune ==
    + remark-gfm@4.0.1

    109 packages installed [91.00ms]
FINDING node_modules after prune: 19 MB (prune exit ok=1)
FINDING bun cache after removal: gone
== 6. herdr server + plugin startup hook ==
    {"id":"cli:plugin","result":{"plugin":{"actions":[{"command":["sh","-c","exec \"${HERDR_BIN_PATH:-herdr}\" plugin pane open --plugin \"$HERDR_PLUGIN_ID\" --entrypoint setup --focus"],"contexts":["global","workspace"],"id":"setup","title":"Web: setup (password, domain, HTTPS)"},{"command":["sh","scripts/bun.sh","scripts/plugin.ts","start"],"contexts":["global","workspace"],"id":"start","title":"Web: start server"},{"command":["sh","scripts/bun.sh","scripts/plugin.ts","status"],"contexts":["global","workspace"],"id":"status","title":"Web: status"},{"command":["sh","scripts/bun.sh","scripts/plugin.ts","stop"],"contexts":["global","workspace"],"id":"stop","title":"Web: stop server"},{"command":["sh","scripts/bun.sh","scripts/plugin.ts","uninstall"],"contexts":["global","workspace"],"id":"uninstall","title":"Web: uninstall (service and tunnel; keeps password and config)"}],"build":[{"command":["sh","scripts/bun.sh","install","--frozen-lockfile"]},{"command":["sh","scripts/bun.sh","run","build"]}],"description":"Chat-style web client for Herdr agents, with real login and HTTPS, built to run on a public VPS with zero manual setup","enabled":true,"manifest_path":"/opt/herdr-plugins/herdr-web-service/herdr-plugin.toml","min_herdr_version":"0.9.0","name":"Herdr Web Service","panes":[{"command":["sh","scripts/bun.sh","scripts/plugin.ts","setup"],"height":"80%","id":"setup","placement":"popup","title":"Herdr Web Service setup","width":"80%"}],"platforms":["linux","macos"],"plugin_id":"imontes.herdr-web-service","plugin_root":"/opt/herdr-plugins/herdr-web-service","source":{"kind":"local"},"startup":[{"command":["sh","scripts/bun.sh","scripts/plugin.ts","start"]}],"version":"0.2.0"},"type":"plugin_linked"}}
FINDING plugin config dir: /data/.config/herdr/plugins/config/imontes.herdr-web-service
--- herdr server log ---
    herdr server running; you can use any herdr CLI command in another terminal.
    api socket: /data/.config/herdr/herdr.sock
    client socket: /data/.config/herdr/herdr-client.sock
    logs: /data/.config/herdr/herdr-server.log
    did you mean to open the Herdr TUI? run `herdr`; you do not need `herdr server`.
FINDING startup hook: /api/health answered on 127.0.0.1:7340 without a manual start
FINDING bun server process: 882 /root/.bun/bin/bun /opt/herdr-plugins/herdr-web-service/server/index.ts
FINDING plugin state dir (server.pid): /root/.local/state/herdr/plugins/imontes.herdr-web-service/server.pid
FINDING plugin state dir listing: server.log server.pid
FINDING scripts/bun.sh with a minimal PATH: 1.4.3
FINDING health body: {"ok":true,"version":"0.2.0"}
== 7. nginx: inner (add-on, :8099) and outer (HA ingress emulation, :8123) ==
    inner: nginx: the configuration file /tmp/inner.conf syntax is ok
    inner: nginx: configuration file /tmp/inner.conf test is successful
    outer: nginx: the configuration file /tmp/outer.conf syntax is ok
    outer: nginx: configuration file /tmp/outer.conf test is successful

== 8. checks (all through http://127.0.0.1:8123/api/hassio_ingress/SPIKETOKEN/services/) ==
    - ok: status: HTTP/1.1 301 Moved Permanently
    - ok: Location: services/
CHECK C1 PASS GET /services -> 301 with relative Location
    - ok: index: HTTP/1.1 200 OK
    - index references: 5 (5 fetchable)
        ./manifest.webmanifest
        ./icon-192.png
        ./apple-touch-icon.png
        ./assets/index-BLmHMmZZ.js
        ./assets/index-BKniRr8d.css
    - ok: no root-absolute src/href attribute
    - ok: 200 /services/manifest.webmanifest
    - ok: 200 /services/icon-192.png
    - ok: 200 /services/apple-touch-icon.png
    - ok: 200 /services/assets/index-BLmHMmZZ.js
    - ok: 200 /services/assets/index-BKniRr8d.css
    - ok: no root-absolute url() in the built CSS
CHECK C2 PASS index 200, no root-absolute src/href, every referenced asset 200
    - scanned 2 JS file(s)
    - ok: no quote-prefixed /api/, /ws, /sw.js, /assets/, /manifest, /icon string
CHECK C3 PASS built JS contains no root-absolute /api/, /ws, /sw.js string
    - session before the password exists: {"authenticated":false,"setup_required":true}
    - ok: login before a password exists: 503
    - ok: set-password via pipe: password saved
    - ok: auth.json written in /data/.config/herdr/plugins/config/imontes.herdr-web-service
FINDING auth.json mode: 600
    - ok: wrong password: 401
    - ok: right password: HTTP/1.1 204 No Content
    - set-cookie: hwv_session=<token redacted> Path=/; HttpOnly; SameSite=Strict
    - ok: Set-Cookie carries hwv_session
    - ok: cookie is HttpOnly
    - ok: cookie has no Secure flag
CHECK C4 PASS login 503 before password, 401 wrong, 204 + HttpOnly cookie right
    - session, no cookie (before the password was set): {"authenticated":false,"setup_required":true}
    - ok: setup_required true before a password exists
    - ok: authenticated true with the cookie
    - ok: authenticated false without the cookie
    - ok: gated /api/roster with the cookie: 200
    - ok: gated /api/roster without the cookie: 401
CHECK C5 PASS session ungated (setup_required / authenticated), /api/roster gated
curl: (28) Operation timed out after 3001 milliseconds with 57 bytes received
    - ok: with the cookie: HTTP/1.1 101 Switching Protocols
    - ok: without the cookie refused: HTTP/1.1 401 Unauthorized
CHECK C6 PASS WebSocket upgrade 101 with the cookie, refused without
    - ok: exactly one Content-Security-Policy header
    - Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'self'; base-uri 'none'
    - ok: frame-ancestors 'self'
    - ok: no frame-ancestors 'none'
    - ok: no Strict-Transport-Security header
    - ok: no Strict-Transport-Security on the login response
CHECK C7 PASS one CSP header with frame-ancestors 'self', no HSTS
    - ok: direct request with Host: evil.invalid: 421
    - ok: direct request with the loopback Host: 200
CHECK C8 PASS plugin rejects a spoofed Host when reached directly
    - ok: bun install --frozen-lockfile --production succeeded
    - ok: dist/index.html present after the prune
    - ok: the whole run above used the pruned node_modules (19 MB), server healthy, login and WebSocket worked
CHECK C9 PASS production prune keeps the server startable

== summary ==
RESULT passed=9 failed=0

== check table ==
  C1 PASS GET /services -> 301 with relative Location
  C2 PASS index 200, no root-absolute src/href, every referenced asset 200
  C3 PASS built JS contains no root-absolute /api/, /ws, /sw.js string
  C4 PASS login 503 before password, 401 wrong, 204 + HttpOnly cookie right
  C5 PASS session ungated (setup_required / authenticated), /api/roster gated
  C6 PASS WebSocket upgrade 101 with the cookie, refused without
  C7 PASS one CSP header with frame-ancestors 'self', no HSTS
  C8 PASS plugin rejects a spoofed Host when reached directly
  C9 PASS production prune keeps the server startable

== candidate nginx block (single source, validated above) ==
        # herdr-web-service (plugin on 127.0.0.1:7340), reached through HA ingress as <ingress>/services/
        # relative redirect: an absolute Location would leave the HA ingress prefix
        location = /services { absolute_redirect off; return 301 services/; }
        location /services/ {
            proxy_pass http://127.0.0.1:7340/;              # trailing slash strips the /services/ prefix
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host 127.0.0.1:7340;           # plugin allows only localhost/127.0.0.1/::1 hosts
            proxy_set_header Origin http://127.0.0.1:7340;  # /ws requires an allowed Origin (loopback only)
            proxy_set_header X-Forwarded-For "";            # HA ingress sends these; the plugin trusts them from a
            proxy_set_header X-Forwarded-Proto "";          # loopback peer and would turn cookies Secure / add HSTS
            proxy_hide_header Content-Security-Policy;      # plugin sends frame-ancestors 'none' (blocks the iframe)
            proxy_hide_header Strict-Transport-Security;    # never let it leak onto the HA origin
            add_header Content-Security-Policy "default-src 'self'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'self'; base-uri 'none'" always;
            proxy_read_timeout 86400;
            proxy_send_timeout 86400;
        }

SPIKE RESULT: PASS (9/9)
```
