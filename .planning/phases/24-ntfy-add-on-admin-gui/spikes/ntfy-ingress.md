# Spike: ntfy-ingress (Phase 24)

Date: 2026-11-01. Scope: ingress handling for the admin GUI, ntfy behind a reverse proxy, vendoring Preact/htm, HA
ingress specifics. Legend: **[V]** verified here (command + result), **[A]** assumption / from memory, not verified.

## 0. Verdict

- GUI under ingress works with plain relative URLs; `secrets-sync` is a proven template (copy gate + asset whitelist).
- ntfy itself **cannot live under a path prefix** (web app uses absolute `/static/...`). That is fine: D-03/D-10 keep ntfy
  on `listen_port` and ingress only for the GUI.
- Preact+htm: one 13 KB file (`htm@3.1.1/preact/standalone.module.js`, bundles Preact 10.x + hooks), fits D-16.
- Biggest open point: **`host_network: true` + ingress is unprecedented in this repo** (see 2.4). Needs a live check.

## 1. Ingress in the existing add-ons

### 1.1 secrets-sync (`secrets-sync/app/web/server.py`, `static/`) [V by reading]

- Gate (`server.py:14`, `:79-82`): `INGRESS_REMOTE = "172.30.32.2"`;
  `_is_ingress()` = `client_address[0] == "172.30.32.2" and bool(X-Ingress-Path header)`.
  The header alone is spoofable by anyone who can reach the port, hence the IP check on the TCP peer. Header value
  is only tested for presence, never used.
- Asset whitelist `ASSETS` (`:17-22`): `/`, `/static/app.css`, `/static/app.js`, `/icon` mapped to files; everything
  else 404. Pages/assets and all mutating POSTs return 403 `ingress_only` when not from ingress. Only
  `/api/health` and `/api/status.json` are open on the optional published port.
- Relative paths: `index.html` uses `href="static/app.css"`, `src="static/app.js"`, `src="./icon"` (no leading `/`);
  `app.js:419,441,458` use `fetch('api/status.json')`, `fetch('api/preview', {method:'POST'})`. No `<base>` tag, no
  server-side path injection. Hash routing (`location.hash`) for tabs, so no path-based routing.
- Note for us: the server must be reachable at `/` exactly as the Supervisor forwards it: Supervisor strips the
  `/api/hassio_ingress/<token>` prefix, so the add-on sees `/`, `/static/app.js`, `/api/...`. Hence routes are
  declared prefix-free and the browser URL needs the relative form. [A: stripping behaviour from HA docs/memory; consistent
  with how secrets-sync works in production.]
- Binds `0.0.0.0:8099` (`make_server` default), `ports: 8099/tcp: null` (not published by default).

### 1.2 haos-monitor [V by reading]

- `config.yaml`: `ingress: true`, `ingress_port: 8099`, `ports: 8099/tcp: null`.
- Busybox `httpd -p 8099` serves static `index.html` + CGI `*.json`/`*.txt` (`run.sh:95`, `httpd.conf`). **No ingress
  check at all**; it relies on the port not being published. `index.html:40` comment: "Relative URLs on purpose:
  Ingress serves this page below a token path"; `fetch(url)` with relative URLs (`:77`).

### 1.3 gatus [V by reading]

- Gatus uses absolute paths, so `gatus/nginx.conf` listens on 8099, reads `X-Ingress-Path` (`$http_x_ingress_path`),
  and rewrites the HTML with `sub_filter` (`src="/` -> `src="$ingress_path/`, same for `href`) plus an injected script
  patching `fetch`/XHR. That is the workaround when a third-party UI cannot be made relative. Lesson: **do not do this
  for ntfy's web app** (not needed, ntfy is not behind ingress) and **avoid it for our GUI** (write relative from the
  start).

### 1.4 Rules for the vanilla-JS + Preact/htm GUI

1. Every URL in HTML/JS/CSS is relative without a leading slash: `static/app.js`, `api/users`, `./icon`.
   `fetch('/api/x')` goes to HA Core (`http://ha:8123/api/x`) and breaks. [V: `urljoin` check below]
2. ES module imports inside `static/app.js` resolve relative to the module URL: `import './preact-htm.js'`. [V by
   urljoin; not browser-run]
3. `index.html` must be served at a URL ending in `/` (the Supervisor's ingress URL ends with `/`, so `static/...`
   resolves below the token). Never redirect `/` to something absolute; if a redirect is needed use a relative
   `Location`.
4. No `<base href>`, no `location.pathname`-based API prefix, no absolute `Location` redirects, no
   cookies with `Path=/` assumptions. State in hash (`#/users`) or in memory.
5. Whitelist static files in the server (like `ASSETS`) and apply the ingress gate to HTML, static files and **all API
   routes including GET** (our API exposes tokens/users, unlike secrets-sync's status JSON). Expose nothing on the
   published port except an optional `/api/health`.
6. Send `Cache-Control: no-cache` for static files so updates after an add-on upgrade show up (secrets-sync does).
7. URL-encode path segments of usernames/topics in `fetch` (`encodeURIComponent`) since topics may contain `*`
   wildcards (`%2A`).

URL resolution check [V]:

```text
base=http://ha:8123/api/hassio_ingress/TOKEN/
static/app.js    -> .../TOKEN/static/app.js
api/users        -> .../TOKEN/api/users
/api/users       -> http://ha:8123/api/users          (BREAKS)
module import './preact-htm.js' from .../TOKEN/static/app.js -> .../TOKEN/static/preact-htm.js
```

## 2. ntfy 2.36.0 behind a reverse proxy [V, real container]

Image `binwiederhier/ntfy:latest` = `ntfy version 2.36.0` (container `ntfy-spike-ingress`, host port 18082, data under
`/tmp/akentner/ntfy-spike-ingress`, throwaway admin `spikeadmin`). Config used:

```yaml
base-url: "https://ntfy.example.test"
listen-http: ":8080"
cache-file: /var/lib/ntfy/cache.db
auth-file: /var/lib/ntfy/auth.db
auth-default-access: deny-all
enable-login: true
behind-proxy: true
web-root: "/"
attachment-cache-dir: /var/lib/ntfy/att   # added for the attachment test
```

### 2.1 Web app and API with a `base-url` that differs from the request Host

| Check | Command (abridged) | Result |
| --- | --- | --- |
| health | `curl localhost:18082/v1/health` | `{"healthy":true,"role":"active"}` |
| web app | `curl -i localhost:18082/` and `/app` | 200 HTML both (`web-root: /` serves at `/`, `/app` too) |
| `config.js` | `curl localhost:18082/config.js` | `"base_url": ""`, `"app_root": "/"`, `enable_login: true` |
| Host mismatch | `curl -H 'Host: other.test' .../config.js` | same, `base_url` is `""` regardless of Host |
| assets | `curl / \| grep src/href` | all **absolute**: `/static/css/app.css`, `/static/media/index-*.js`, `/manifest.webmanifest` |
| prefix | `GET /prefix/static/css/app.css` vs `/static/css/app.css` | 404 vs 200 |
| web-root `/app` | `GET /` , `/app`, `/static/css/app.css`, `/app/static/css/app.css` | 404, 200, 200, 404 (assets still at `/static`, only the app entry moves) |
| attachment URL | `PUT` file with `Host: 192.168.1.5:8000` | `url` = `https://ntfy.example.test/file/<id>.txt`, so `base-url` is what appears in message payloads |
| publish w/o auth | `curl -d hello .../topicA` (deny-all) | 403 `forbidden` |
| publish w/ basic auth | same with `Authorization: Basic` | 200 message JSON |
| SSE | `GET /topicA/sse` with auth | `event: open` |
| WebSocket | `GET /topicA/ws` with `Upgrade: websocket` + auth | `101 Switching Protocols` |
| WebSocket w/o auth, deny-all | `/x/ws` | 403 (reaches ntfy, rejected by ACL, not by proxy) |

Conclusions:

- **No path-prefix support**: web app assets are absolute (`/static/...`). A reverse proxy must forward `/` of a host
  (or host-based routing) to ntfy; stripping/adding a prefix breaks the web app. The old add-on setup (Cloudflare /
  Traefik -> `ntfy.akentner.de` -> `:8000`) is a host-based setup and is fine. [V]
- `base-url` does not influence the web app (it uses the browser origin, `config.js` `base_url` stays `""`). It is used
  for attachment URLs and for server-generated links/e-mail/iOS upstream. A wrong `base-url` therefore breaks
  attachment links and iOS poll forwarding, not the UI. [V for attachments; iOS/e-mail path [A]]
- Web UI is toggled by `web-root: disable` in ntfy (`enable_web_ui` option should map to `web-root: "/"` vs
  `"disable"`). [V: flag exists in `serve --help`; value `disable` not exercised]
- `enable-login: true` is needed for the web app to log in; `auth-default-access` is orthogonal. [V: `config.js` flag]

### 2.2 Proxy headers

- `behind-proxy: true` (`--behind-proxy`, env `NTFY_BEHIND_PROXY`): ntfy takes the visitor IP (rate limiting,
  `basis: ip` in `/v1/account`) from `X-Forwarded-For` / `X-Client-IP`. [V: flag description in `serve --help`]
- Without `X-Forwarded-For` while `behind-proxy: true` ntfy still answers normally (`/v1/health` 200, no log
  warning in a short run). With a bogus `X-Forwarded-For: bogus` it also answers 200 (`/v1/account`). [V]
- Spoofing risk: with `host_network` and LAN-direct access, any client can set `X-Forwarded-For` and sidestep per-IP
  rate limits if `behind-proxy` is on. Set `behind_proxy` as option, default **true** only because the production path
  is Cloudflare/Traefik; document the trade-off. [V that header is accepted unauthenticated; impact is [A]]
- WebSocket: proxy must pass `Upgrade`/`Connection: upgrade` for `/<topic>/ws` (ntfy answered 101 direct). Nginx needs
  `proxy_http_version 1.1`, `Upgrade`, `Connection "upgrade"`, long `proxy_read_timeout`; SSE/JSON streams need
  `proxy_buffering off`. [V for ntfy side; proxy-side config [A] from ntfy docs]
- ntfy runs as root inside the official image (`id` -> uid 0). Irrelevant for HA add-ons, noted.

### 2.3 What ingress is (not) for

Ingress serves **only our admin GUI** (D-03). ntfy is reached on `listen_port` (default 8000) via host network
(D-10). The Supervisor never proxies ntfy, so the missing prefix support is not a problem.

### 2.4 Binding and port collision with `host_network: true`

- ntfy: `listen-http: ":<listen_port>"` (all interfaces; same as the old add-on). Container-internal test used
  `:8080`. With host networking the process binds directly in the host's namespace. [V in container; host semantics [A]]
- GUI: Python server on `8099` (D-16). With `host_network: true` it also binds in the host namespace, i.e. **port
  8099 is reachable from the LAN**, unlike bridge add-ons where `ports: 8099/tcp: null` keeps it closed. Consequences:
  1. The 172.30.32.2 + `X-Ingress-Path` gate is the *only* protection, so it is mandatory for every route, including
     reads (see rule 5).
  2. Port 8099 must not collide with another host-network service. Repo scan [V]: host_network add-ons here are
     `terraform-bridge`, `network-tools`, `iac-runner`; none declares `ingress`/8099; **no add-on in this repo combines
     host_network with ingress**, so there is no prior art. `listen_port` must also never be set to 8099 (add schema
     range or validate in `run.sh`).
  3. Ingress for host-network add-ons: HA docs say the Supervisor connects to the add-on at its internal IP; for
     host-network add-ons that is the host gateway address. Whether the request still arrives from `172.30.32.2` is
     **[A, unverified]**; if the peer address differs, the gate would lock out the GUI. Verify on a real HA before
     relying on the IP check (e.g. log `client_address` once), and consider configurable `INGRESS_REMOTE`
     (secrets-sync already takes it as a parameter).
  4. Mitigation options: bind GUI to the hassio bridge gateway (`172.30.32.1:8099`) instead of `0.0.0.0` to keep it
     off the LAN **[A, unverified]**; or drop `host_network` and publish only `listen_port` via `ports:` (changes
     D-10, would need a user decision; client IP preservation for `behind-proxy` then needs checking).
- Ports: HAOS host already uses 22222 (SSH), 8123, 4357; 8000 is the old add-on's port (free once the old add-on is
  removed - **both add-ons cannot run together on the same host_network port**, relevant for the migration test).
  [A from CLAUDE.md/DOCS of haos-monitor, not checked on host]

## 3. Vendoring Preact + htm [V]

Single file recommended: **`htm@3.1.1/preact/standalone.module.js`** (ESM; exports `html, render, Component,
createContext, useState, useReducer, useEffect, useLayoutEffect, useRef, useImperativeHandle, useMemo, useCallback,
useContext, useDebugValue, useErrorBoundary`; verified via `node -e "import(...)"`).

| Item | Value |
| --- | --- |
| Package | `htm` 3.1.1 (published 2022-04-26, far older than 2 weeks), Apache-2.0 |
| Bundles | Preact 10.x + hooks (MIT, Copyright Jason Miller) |
| Size | 13194 bytes (5342 gz) |
| sha256 | `72284e8e9079c87817145df1110f74e8a2aa040b2fc384922e18dfcb46fc1fd7` |
| jsDelivr | `https://cdn.jsdelivr.net/npm/htm@3.1.1/preact/standalone.module.js` |
| cdnjs | `https://cdnjs.cloudflare.com/ajax/libs/htm/3.1.1/preact/standalone.module.js` (byte-identical, `cmp` OK) |
| Licence files | `https://cdn.jsdelivr.net/npm/htm@3.1.1/LICENSE` (Apache-2.0), `.../preact@10.29.8/LICENSE` (MIT) |

Notes:

- Which Preact version is bundled is not stated in the file header (minified); the bundle predates Preact 11. Do not
  assume it equals `preact@10.29.8` (separate unbundled file, 11693 B, `.../preact@10.29.8/dist/preact.module.js`, was
  **not** used). [A: bundled version]
- Preact 11 exists (11.0.1 published 2026-10-08, 11.1.1 on 2026-10-31 = too fresh for the >=2 weeks rule); its dist
  layout differs (`dist/preact.module.js` 404 at 11.0.1). Stay on htm's standalone bundle; no benefit from 11 here.
- Ship both licence texts next to the file (Apache-2.0 requires the licence text; add a `static/LICENSES.txt` or
  `vendor/` README with source URL + sha256). Download once at dev time, commit the file; no CDN at runtime (D-16).
- Alternative if a plain `<script>` (non-module) is wanted: `htm@3.1.1/preact/standalone.umd.js` (exists in the
  package listing; not downloaded/measured). Module script works in all current HA frontends/browsers, preferred.

### 3.1 Minimal example (relative paths, table + select + JSON API)

Files (all relative): `index.html`, `static/app.js`, `static/preact-htm.js` (the vendored file), `static/app.css`.

`index.html`:

```html
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>demo</title>
<link rel="stylesheet" href="static/app.css"></head>
<body><div id="app"></div>
<script type="module" src="static/app.js"></script></body></html>
```

`static/app.js`:

```js
import { html, render, useState, useEffect } from './preact-htm.js';

const ROLES = ['user', 'admin'];

async function api(path, opts) {
  // relative path, no leading slash: resolves below the ingress prefix
  const r = await fetch('api/' + path, { cache: 'no-store', ...opts });
  if (!r.ok) throw new Error(r.status);
  return r.json();
}

function App() {
  const [users, setUsers] = useState([]);
  useEffect(() => { api('users').then(setUsers).catch(() => setUsers([])); }, []);
  const setRole = (name, role) => api('users/' + encodeURIComponent(name), {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role }),
  }).then(() => api('users').then(setUsers));
  return html`<table><thead><tr><th>User</th><th>Role</th></tr></thead><tbody>
    ${users.map((u) => html`<tr key=${u.name}><td>${u.name}</td><td>
      <select value=${u.role} onChange=${(e) => setRole(u.name, e.target.value)}>
        ${ROLES.map((r) => html`<option value=${r}>${r}</option>`)}
      </select></td></tr>`)}
  </tbody></table>`;
}
render(html`<${App} />`, document.getElementById('app'));
```

Verification status: the example files and a stdlib server (`GET /api/users`, `PATCH /api/users/<name>`) were created
under `/tmp/akentner/ntfy-spike-ingress` and `GET /api/users` returned the JSON [V]. **The example was not run in a
browser** (no chromium/playwright available here); the render/select flow is therefore **[A, untested]**. The
module-export list and URL resolution were checked [V]. Server must send `Content-Type: text/javascript` for `.js`
(browsers enforce MIME for module scripts) and also serve `static/preact-htm.js` from the whitelist.

## 4. HA ingress specifics (all [A] unless stated; none verified on a live HA, which was out of scope)

- `panel_admin: true` (used by secrets-sync [V config]) restricts the sidebar panel to HA admin users. It hides the
  sidebar entry; it is a UI restriction, **not** an authz mechanism for the add-on. Ingress requests are authenticated
  by HA (session) so only logged-in HA users can reach the proxy; admin-ness is additionally expressed by HA passing
  user headers (`X-Remote-User-*`) in recent Supervisor versions [A, unverified]. For D-12/D-03 treat "reached via
  ingress" as the trust boundary and keep `panel_admin: true`.
- Page is embedded in an iframe by the HA frontend, same origin as HA (`/api/hassio_ingress/<token>/`). Our server
  must **not** send `X-Frame-Options: DENY/SAMEORIGIN`-breaking headers or `frame-ancestors` CSP; secrets-sync sends
  only `X-Content-Type-Options: nosniff`, plus `Cache-Control`. A strict own CSP is possible if it allows
  `script-src 'self'` and `connect-src 'self'` (module script from `'self'`, no inline script/handlers needed with
  htm). Inline `<script>` in index.html would break such a CSP, so keep JS in files.
- Clipboard (token copy, D-13) and `confirm()`/`prompt()` inside the iframe: `navigator.clipboard.writeText` may need
  a user gesture and a secure context (HA over HTTPS or localhost); iframe permission policy may block it on plain
  HTTP. Provide a select-all fallback for revealed tokens. [A]
- WebSocket and SSE: the Supervisor ingress proxy (aiohttp) supports WebSocket upgrades and streams chunked
  responses, so ingress WS/SSE work in principle [A, from Supervisor source memory]. We do not need either: the GUI
  polls JSON (health refresh on a timer / button). If live ntfy messages were ever embedded, they would connect to
  ntfy on `listen_port` directly (CORS/mixed-content issues under HTTPS HA), not through ingress.
- Max body size: Supervisor's ingress proxy applies aiohttp's default `client_max_size` unless raised; I do not
  remember the exact value [A, unverified; must not rely on >1 MB]. Our payloads are small JSON; the only large
  transfer is the `auth.db` **download** (response direction, not limited by request size). Uploads (import) are
  deferred (Phase 25), so no body-size risk in Phase 24. secrets-sync caps request reads at 64 KiB
  (`server.py:114`); do the same.
- Supervisor adds `X-Ingress-Path` (value `/api/hassio_ingress/<token>`), `X-Forwarded-For`, and strips the prefix
  before forwarding [A]. Upstream peer is `172.30.32.2` for bridge add-ons [V by secrets-sync production usage per repo
  docs; not re-tested]; for host-network add-ons see 2.4(3).
- Downloads via ingress: `Content-Disposition: attachment` works through the proxy; use `<a href="api/backups/x.db"
  download>` relative links [A]. Do not use `window.open('/...')`.

## 5. Recommendations for the plan

1. Copy the secrets-sync gate + `ASSETS` whitelist; gate **all** routes (GET included); make `INGRESS_REMOTE` an
   env/option default `172.30.32.2`.
2. Add a Wave-0/early task: on a real HA host, start the add-on with `host_network: true` + `ingress: true` once and
   log the peer address and headers of an ingress request; decide then on binding GUI to the gateway IP or dropping
   host_network (decision for the user, D-10 is "costly").
3. Validate `listen_port` against 8099 (schema `port` + `run.sh` check) and reject the collision loudly.
4. Map options to ntfy: `base_url` -> `base-url`, `enable_web_ui` -> `web-root: "/"|"disable"`, `listen_port` ->
   `listen-http: ":N"`, `behind_proxy` (new, default true) -> `behind-proxy`, `enable-login: true`. Ship `server.yml`
   from `run.sh` (not env) so the CLI inside the add-on sees the same config.
5. Vendor `htm@3.1.1/preact/standalone.module.js` (+ licence texts + sha256 note) to `static/`, relative imports only.
6. Run a browser smoke test (Playwright/Chromium) for the GUI under a simulated prefix before release; this spike could
   not do it.

## 6. Cleanup and commands

Commands run (condensed): `docker pull/run binwiederhier/ntfy ...` (container `ntfy-spike-ingress`, `127.0.0.1:18082`),
`curl` checks above, `docker exec ... ntfy user add --role=admin spikeadmin` with a throwaway password supplied via
`NTFY_PASSWORD` (not stored in this file), `curl https://cdn.jsdelivr.net/npm/htm@3.1.1/preact/standalone.module.js`,
`node -e "import('...standalone.module.js')"`, npm registry metadata via `curl https://registry.npmjs.org/<pkg>`.
The container `ntfy-spike-ingress` and `/tmp/akentner/ntfy-spike-ingress` were removed at the end. The container
`ntfy-spike-cli` belongs to another spike and was left untouched.

## 7. Open questions

- Does an ingress request to a `host_network` add-on arrive from `172.30.32.2`? (2.4)
- Can/should the GUI bind to the hassio gateway address instead of `0.0.0.0`?
- Exact Supervisor ingress `client_max_size` and clipboard behaviour in the iframe (only matters for later import and
  token copy).
- Which Preact version is inside htm's standalone bundle (cosmetic, for the vendor note).
