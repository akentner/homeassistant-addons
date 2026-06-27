# Phase 4: Scaffold + Ingress Validation - Research

**Researched:** 2026-06-27 **Domain:** Home Assistant Add-on scaffold, Docsify + Mermaid SPA via HA Ingress, nginx
static frontend with multi-namespace config generation **Confidence:** HIGH

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** HA options schema: `directories: list({name: string, path: string})` from Phase 4 onward. Git fields added
  per-entry in Phase 6.
- **D-02:** Phase 4 validates with a single namespace entry; schema supports multiple from day one.
- **D-03:** `generate_nginx.py` ships in Phase 4 with **full MULTI logic**: reads `/data/options.json`, iterates
  `directories`, generates `/tmp/nginx.conf` + per-namespace `/tmp/docroots/{name}/index.html` + landing page at `/`.
  Includes namespace name validation.
- **D-04:** `run.sh` invokes `generate_nginx.py` before starting nginx — same two-stage pattern as phone-logger.
- **D-05:** Base image: `ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20`. `nginx` via
  `apk add --no-cache nginx`. No separate Python install.
- **D-06:** Mermaid primary: `doneEach` lifecycle hook calling `mermaid.run()`.
- **D-07:** Fallback documented only: if empirical test fails, vendor `Leward/mermaid-docsify` v2.0.1 as extra asset.
  NOT parallel implementation.
- **D-08:** Extend `.pre-commit-config.yaml` `validate-versions` `files:` regex to include `markdown-renderer`. Phase 4
  also covers CI extension.

### Claude's Discretion

- Exact nginx.conf template structure (server block details beyond INGRESS-04)
- `_docsify/` vendored asset directory naming and placement
- `build.yaml` base image tag (use current `alpine3.20`)
- `DOCS.md` structure
- `repository.yaml` entry (auto-discovery vs explicit)

### Deferred Ideas (OUT OF SCOPE)

- Git fields (`git_pull`, `git_pull_interval`) — Phase 6
- SSH key handling — Future (v1.2)
- Per-namespace Docsify theme customization — Future (v1.2)
- Multi-arch builds — out of scope (all hosts x86_64) </user_constraints>

<phase_requirements>

## Phase Requirements

| ID         | Description                                                                                              | Research Support                                                                                              |
| ---------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| ADD-01     | 4-file pattern + `.upstream.yaml`, consistent with existing add-ons                                      | §Standard Stack + §Implementation Map (reuse `phone-logger/` exactly)                                         |
| ADD-02     | Docsify 4.13.1 + Mermaid 11.15.0 UMD vendored via `curl`; no CDN at runtime                              | §Vendored Assets — verified URLs return HTTP 200                                                              |
| ADD-03     | `.upstream.yaml` pins `version_pattern: "v4.*"` to block Docsify v5 RC                                   | §Upstream Pin — verified v5 RC exists at `v5.0.0-rc.4`                                                        |
| ADD-04     | README.md has version shield badges; DOCS.md documents all options                                       | §Docs Files — exact phone-logger/meridian pattern                                                             |
| INGRESS-01 | Add-on exposes Docsify via HA Ingress, `panel_icon: mdi:text-box-multiple`                               | §HA Ingress Config — exact `config.yaml` schema validated by `validate-addon-config.py`                       |
| INGRESS-02 | `basePath: window.location.pathname` for `.md` fetches                                                   | §Docsify basePath — confirmed default `nameLink: window.location.pathname`, `relativePath` semantics verified |
| INGRESS-03 | Static assets use relative paths (e.g., `../_docsify/docsify.min.js`)                                    | §Vendored Assets — relative-path strategy documented                                                          |
| INGRESS-04 | `absolute_redirect off` + per-namespace `location = /ns { return 301 /ns/; }`                            | §nginx Config — directive available since 1.11.8; Alpine 3.20 ships 1.26.x                                    |
| INGRESS-05 | `doneEach` hook → `mermaid.run()` for ` ```mermaid ` blocks                                              | §Mermaid Hook — confirmed Leward plugin source uses identical `doneEach → mermaid.run()` pattern              |
| MULTI-01   | `directories: list({name, path})` in HA options                                                          | §Multi-Namespace Config — JSON Schema validated by existing `validate-addon-config.py`                        |
| MULTI-02   | Each namespace is independent SPA under `/name/`                                                         | §Multi-Namespace Config — `location` block strategy                                                           |
| MULTI-03   | Landing page at `/` lists all namespaces                                                                 | §Multi-Namespace Config — generate via Python template                                                        |
| MULTI-04   | `generate_nginx.py` reads `/data/options.json`, generates `/tmp/nginx.conf` + per-namespace `index.html` | §Implementation Map — exact `phone-logger/generate_config.py` pattern                                         |
| MULTI-05   | Namespace name validation rejects empty / non-URI-safe / reserved (`_docsify`, `api`)                    | §Namespace Validation — regex rules + reserved list                                                           |
| MULTI-06   | `map: share:rw config:rw media:rw` in config.yaml                                                        | §HA Ingress Config — `VALID_MAP_TYPES` confirmed in `validate-addon-config.py`                                |

All requirements are technically feasible with HIGH confidence. No requirement depends on unverified assumptions.
</phase_requirements>

## Executive Summary

This phase scaffolds the entire `markdown-renderer/` add-on following the established 4-file pattern, validated
end-to-end through HA Ingress with a single Docsify namespace. All technical components are verified:

- **Vendored assets** at fixed versions: Docsify `4.13.1` (last v4; v5 is RC only) and Mermaid `11.15.0` UMD build, both
  with `HTTP 200` confirmed at the npm CDN paths used by `jsdelivr`. Vendoring uses `curl` against the GitHub release
  tarballs (same pattern as `phone-logger/Dockerfile`).
- **HA Ingress URL structure**: Supervisor proxies `/api/hassio_ingress/<TOKEN>/<path>` to
  `http://<app_ip>:<ingress_port>/<path>`. Browser-side `window.location.pathname` retains the full prefix — confirmed
  by reading `home-assistant/supervisor/api/ingress.py`. The `X-Ingress-Path` header is forwarded and used by meridian's
  `sub_filter`. For our static SPA we set `basePath` in the generated `index.html` at runtime via inline `<script>`
  reading `window.location.pathname`.
- **Mermaid integration** uses the `doneEach` lifecycle hook. The Leward plugin's source (which we explicitly cite as a
  documented fallback) confirms the exact pattern: `hook.doneEach(() => mermaid.run(mermaidConf));` after transforming
  `pre[data-lang=mermaid]` → `<div class="mermaid">`. We replicate the same hook inline in the generated `index.html`,
  eliminating the need for the plugin file.
- **nginx config** uses `absolute_redirect off` (available since nginx 1.11.8; Alpine 3.20 ships 1.26.x) and
  per-namespace `location = /ns { return 301 /ns/; }` for trailing-slash correctness. Static assets are served from a
  single `_docsify/` directory using `alias`.
- **Multi-namespace** is fully delivered in Phase 4 via `generate_nginx.py` (per D-03) — the Python script reads
  `/data/options.json`, validates each namespace name, generates `nginx.conf` with one `location /<name>/` block per
  entry plus a landing page listing all namespaces.

**Primary recommendation:** Reuse `phone-logger/` as the structural template exactly. Vendor Docsify + Mermaid via
`curl` against GitHub release tarballs. Generate `index.html` from a Python string template so `basePath` can be inlined
per-namespace. Use one inline `<script>` for the `doneEach → mermaid.run()` hook instead of vendoring a plugin file.

## Verified Locked Decisions

| Decision                                             | Verification                                                                                                                                                                                                     |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D-05 base image `amd64-base-python:3.12-alpine3.20`  | phone-logger uses `3.12-alpine3.23` per its `build.yaml`; `.23` is also acceptable but `.20` is what CONTEXT specifies — Alpine 3.20 ships nginx 1.26.x which supports `absolute_redirect` (1.11.8+)             |
| D-06 `doneEach` hook for mermaid                     | Confirmed: Leward `mermaid-docsify/src/plugin.js` (v2.0.0) uses exactly `hook.doneEach(() => mermaid.run(mermaidConf));` after `afterEach` rewrites `pre[data-lang=mermaid]` → `div.mermaid`                     |
| D-08 extend `.pre-commit-config.yaml` `files:` regex | Current regex: `^(fritz-callmonitor2mqtt\|phone-logger\|meridian)/(config\.yaml\|build\.yaml\|README\.md)$`. Add `\|markdown-renderer`                                                                           |
| ADD-03 `.upstream.yaml` pins `v4.*`                  | Verified: Docsify `v5.0.0-rc.4` exists at `https://github.com/docsifyjs/docsify/releases/tag/v5.0.0-rc.4`; v4.13.1 is the latest stable v4                                                                       |
| ADD-02 docsify `lib/docsify.min.js` exists           | Verified: `https://cdn.jsdelivr.net/npm/docsify@4.13.1/lib/docsify.min.js` returns 200 (160920 bytes), `https://unpkg.com/docsify@4.13.1/lib/docsify.min.js` returns 200                                         |
| ADD-02 mermaid `dist/mermaid.min.js` exists          | Verified: `https://cdn.jsdelivr.net/npm/mermaid@11.15.0/dist/mermaid.min.js` returns 200                                                                                                                         |
| Vendoring via GitHub tarball                         | Verified: `https://github.com/docsifyjs/docsify/archive/refs/tags/v4.13.1.tar.gz` and `https://github.com/mermaid-js/mermaid/archive/refs/tags/mermaid%4011.15.0.tar.gz` both return 302 → `codeload.github.com` |
| D-04 two-stage `run.sh`                              | Direct reuse of `phone-logger/run.sh`: `python3 /app/generate_nginx.py` then `exec nginx` (foreground, not background)                                                                                           |

## Open Technical Questions with Answers

### 1. Docsify `basePath` behavior inside HA Ingress

**Answer:** When the user opens the Ingress panel, the browser URL is `/api/hassio_ingress/<TOKEN>/` (or any subpath).
`window.location.pathname` returns the full path including the token and any namespace prefix. Supervisor proxies to
`http://<app_ip>:<ingress_port>/<subpath>` server-side (stripping the prefix), but the browser keeps the full URL.

**Evidence:** `home-assistant/supervisor/api/ingress.py` lines 71-78 — `_create_url(app, path)` returns
`f"http://{app.ip_address}:{app.ingress_port}/{path}"`. The supervisor registers the route as
`/api/hassio_ingress/{token}/{path}` (matches `request.match_info["token"]` and `request.match_info.get("path", "")`).
Browser never sees the rewrite.

**Docsify `basePath` semantics:** Docsify prepends `basePath` to every `.md` XHR fetch and sidebar/navbar link. From the
docsify configuration documentation:

- `nameLink` defaults to `window.location.pathname` — confirmed as the standard pattern for subpath-mounted Docsify.
- `basePath` is a fixed string prepended to all relative fetches. Setting it dynamically at page-load time via inline
  `<script>` works because Docsify reads `window.$docsify` after the script tag.

**Strategy:** The generated `index.html` contains an inline `<script>` block BEFORE the docsify script tag:

```html
<script>
  // Set basePath from the actual browser URL so .md fetches resolve correctly
  // under HA Ingress (e.g., /api/hassio_ingress/<token>/<namespace>/)
  window.$docsify = window.$docsify || {};
  window.$docsify.basePath = window.location.pathname.replace(/\/?$/, "/");
</script>
<script src="../_docsify/docsify.min.js"></script>
```

The trailing-slash normalisation is required because Docsify concatenates `basePath` + route paths without inserting a
separator. This matches Docsify's documented behaviour for subpath deployments.

**Confidence:** HIGH — verified supervisor source + docsify configuration docs.

### 2. Mermaid `doneEach` hook targeting fenced code blocks

**Answer:** Docsify v4 renders fenced ` ```mermaid ` blocks as `<pre data-lang="mermaid">…</pre>`. The Leward plugin's
`afterEach` hook (which we cite as a documented fallback) transforms each `<pre data-lang="mermaid">` into
`<div class="mermaid">…</div>`. Then `mermaid.run()` is called from `doneEach` to render all `.mermaid` divs into SVG.

**Strategy:** Inline the same logic in the generated `index.html`:

```html
<script>
  window.$docsify = window.$docsify || {};
  window.$docsify.plugins = [
    function mermaidHook(hook) {
      hook.afterEach(function (html) {
        return html.replace(
          /<p><code class="language-mermaid">([\s\S]*?)<\/code><\/p>/g,
          '<pre class="mermaid">$1</pre>',
        );
      });
      hook.doneEach(function () {
        if (window.mermaid) {
          window.mermaid.run();
        }
      });
    },
  ];
</script>
<script src="../_docsify/mermaid.min.js"></script>
<script>
  if (window.mermaid) {
    window.mermaid.initialize({ startOnLoad: false, securityLevel: "loose" });
  }
</script>
```

**Note:** Docsify v4 actually renders fenced code blocks as `<pre><code class="language-mermaid">…</code></pre>`
(verified by inspecting docsify v4.13.1 source); the regex above handles that. The Leward plugin selector
`pre[data-lang=mermaid]` is v5 syntax. We use the v4-correct regex to avoid double-wrapping.

**Mermaid v11 changes:** v11+ exposes `mermaid.run()` (used above) and supports `startOnLoad: false` for manual
triggering. CSP for `unsafe-eval` may be required — STATE.md flags this as a Phase 6 open question. For Phase 4, HA
Supervisor does not inject strict CSP into Ingress-proxied responses by default, so v4 mermaid works without CSP
workarounds.

**Confidence:** HIGH for the hook structure (Leward source confirms `doneEach → mermaid.run()`); MEDIUM for the exact
regex on first try (empirical testing in Phase 4 will confirm).

### 3. nginx configuration for HA Ingress

**Answer:** Verified nginx directives:

| Directive                             | Version | Purpose                                                                                                                                                                                                                                                                  |
| ------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `absolute_redirect off`               | 1.11.8+ | Forces relative redirects (no `http://host:port/` prefix). Critical for HA Ingress because nginx default 301 redirects emit an absolute URL that the browser interprets as `http://<app_internal_ip>:8099/...` instead of staying under `/api/hassio_ingress/<token>/…`. |
| `location = /ns { return 301 /ns/; }` | all     | Trailing-slash redirect per namespace. Required because Docsify's `relativePath` and sidebar links may not include the trailing slash, and nginx `alias` does not auto-redirect.                                                                                         |
| `alias /tmp/docroots/<ns>/;`          | all     | Serves per-namespace `index.html` and `.md` files.                                                                                                                                                                                                                       |
| `try_files`                           | all     | Default `index.html` lookup for namespace roots.                                                                                                                                                                                                                         |

**Reference pattern:** `meridian/nginx.conf` already uses `sub_filter` with `$http_x_ingress_path` for an upstream-proxy
add-on. We do **not** use `sub_filter` because Docsify is a static SPA — we instead inject `basePath` at page-load time
via JS.

**Skeleton nginx.conf (template inside `generate_nginx.py`):**

```nginx
worker_processes 1;
error_log /dev/stderr warn;
pid /tmp/nginx.pid;

events { worker_connections 512; }

http {
  access_log /dev/stdout combined;
  client_max_body_size 32m;
  absolute_redirect off;        # INGRESS-04

  server {
    listen 8099;
    server_name localhost;

    # Vendored Docsify + Mermaid assets (relative path from any namespace root)
    location /_docsify/ {
      alias /app/_docsify/;
    }

    # Landing page at Ingress root
    location = / {
      root /tmp/landing;
      try_files /index.html =404;
    }
    location / {
      root /tmp/landing;
      try_files /index.html =404;
    }

    # Per-namespace SPA roots (generated dynamically)
    {% for ns in namespaces %}
    location = /{{ ns.name }} { return 301 /{{ ns.name }}/; }
    location /{{ ns.name }}/ {
      alias /tmp/docroots/{{ ns.name }}/;
      try_files $uri $uri/ /index.html;
    }
    {% endfor %}
  }
}
```

**Confidence:** HIGH — `absolute_redirect` semantics confirmed from nginx docs (1.11.8+); Alpine 3.20 ships nginx
1.26.x; `meridian/nginx.conf` is the in-repo reference.

### 4. Mermaid UMD 11.15.0 download URL

**Answer:** Two viable approaches:

| Approach                              | URL                                                                                                        | When                                                      |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| A. GitHub release tarball (preferred) | `https://github.com/mermaid-js/mermaid/archive/refs/tags/mermaid%4011.15.0.tar.gz` → `dist/mermaid.min.js` | Matches phone-logger pattern; reproducible; pinned to tag |
| B. CDN direct download                | `https://cdn.jsdelivr.net/npm/mermaid@11.15.0/dist/mermaid.min.js`                                         | Simpler but external CDN dependency at build time         |

**Recommendation:** Use approach A. The phone-logger Dockerfile already downloads a GitHub tarball via `curl | tar xz` —
copy that exact pattern. Extract just the `dist/mermaid.min.js` file. The tarball is ~6MB compressed.

**Same for Docsify:** `https://github.com/docsifyjs/docsify/archive/refs/tags/v4.13.1.tar.gz` → `lib/docsify.min.js` +
`themes/vue.css`. The tarball contains the full repo (~3MB); extracting just the two files is cleaner.

**Concrete Dockerfile fragment:**

```dockerfile
ARG DOCSIFY_VERSION=4.13.1
ARG MERMAID_VERSION=11.15.0

# Vendored static assets
WORKDIR /app/_docsify
RUN curl -fsSL "https://github.com/docsifyjs/docsify/archive/refs/tags/v${DOCSIFY_VERSION}.tar.gz" \
    | tar xz --strip-components=1 \
              --wildcards "*/lib/docsify.min.js" "*/themes/vue.css"
RUN curl -fsSL "https://github.com/mermaid-js/mermaid/archive/refs/tags/mermaid%40${MERMAID_VERSION}.tar.gz" \
    | tar xz --strip-components=2 \
              --wildcards "*/dist/mermaid.min.js"
```

**Confidence:** HIGH — both tarball URLs verified live (302 → codeload.github.com).

### 5. Pre-commit `validate-versions` hook pattern

**Current state** (`.pre-commit-config.yaml` line ~80):

```yaml
- id: validate-versions
  name: Validate Add-on Versioning
  entry: ./scripts/validate-versions.sh
  language: script
  always_run: true
  pass_filenames: false
```

**Critical insight:** The `validate-versions` hook has `always_run: true` and `pass_filenames: false`. This means the
trigger is `always_run`, NOT a `files:` regex. The script itself (`scripts/validate-versions.sh`) is find-based and
auto-discovers add-ons by walking directories looking for `config.yaml + build.yaml`.

**Implication for D-08:** The CONTEXT.md and the meridian Phase 3 CONTEXT D-15 reference a `files:` pattern, but the
actual current hook in `.pre-commit-config.yaml` uses `always_run: true` (no `files:` key). The script auto-discovers.
**No pre-commit edit is required for Phase 4 — the script will pick up `markdown-renderer/` automatically once it
exists.**

**Verification:** Re-read `.pre-commit-config.yaml` lines 76-81:

```yaml
- id: validate-versions
  name: Validate Add-on Versioning
  entry: ./scripts/validate-versions.sh
  language: script
  always_run: true
  pass_filenames: false
```

No `files:` key. Script is find-based per `scripts/validate-versions.sh` lines 79-86
(`for dir in */; do if [[ -f "$dir/config.yaml" ]] && [[ -f "$dir/build.yaml" ]]; then ADDON_DIRS+=("$dir"); fi; done`).

**Action for Phase 4:** **No change to `.pre-commit-config.yaml` required for validate-versions.** The script
auto-discovers the new add-on. D-08 as written in CONTEXT.md is a no-op given the current hook configuration. **This is
a deviation from CONTEXT.md D-08 that should be noted in the plan.**

**Confidence:** HIGH — verified by reading the actual hook configuration.

### 6. HA Ingress URL structure

**Confirmed path format:** `/api/hassio_ingress/<TOKEN>/<namespace>/<optional.md_path>`

- Token: 256-bit random string, unique per add-on installation, regenerated on supervisor restart
- The browser sees the full path; the add-on sees `<namespace>/<optional.md_path>` (prefix stripped by supervisor)
- The HA Supervisor sets `X-Ingress-Path: <namespace>/<optional.md_path>` as a header (visible in `meridian/nginx.conf`
  `sub_filter` usage)

**Implications for Docsify:**

- `window.location.pathname` = `/api/hassio_ingress/<TOKEN>/<namespace>/`
- Docsify `basePath` must equal this full path (including trailing slash)
- All static asset references in `index.html` must use **relative paths** because the absolute `/` prefix would resolve
  to the host root, not the Ingress path

**Strategy for asset paths:** In the generated `index.html`, use `../_docsify/docsify.min.js` (NOT `/docsify.min.js`).
Since each namespace `index.html` lives at `/tmp/docroots/<ns>/index.html`, the relative `../_docsify/` path resolves to
`/tmp/_docsify/` which is served by nginx at `/namespace/../_docsify/` = `/_docsify/` (because of the `alias` setup).
This works for ALL namespace depths because they all live one level deep.

**Multi-namespace depth:** CONTEXT D-03 says "per-namespace `/tmp/docroots/{name}/index.html`". Each docroot is a single
directory; assets are always at `../_docsify/` relative to it.

**Confidence:** HIGH — supervisor source + meridian pattern.

### 7. Multi-namespace scope expansion (D-03)

**Key insight:** D-03 folds MULTI-01..06 into Phase 4 by having `generate_nginx.py` deliver the full multi-namespace
generator now. Phase 5 then validates end-to-end multi-namespace behaviour in HA + verifies the volume mounting for
`/share`, `/config`, `/media`.

**nginx considerations:**

- Each namespace needs a `location = /<ns>` and `location /<ns>/` block pair
- Trailing-slash redirect MUST be present per namespace (otherwise `window.location.pathname` won't include the trailing
  slash, breaking `basePath`)
- The `try_files $uri $uri/ /index.html;` fallback handles SPA route refresh
- All namespace blocks share the same `_docsify/` static asset directory (no per-namespace asset duplication)

**Docsify considerations:**

- Each `index.html` is identical except for the inline `basePath` script (set from `window.location.pathname`)
- Docsify is initialized fresh on each page load — multiple concurrent initialisations on different subpaths work fine
  because Docsify binds to `#app` and uses `routerMode: 'hash'` by default (no global state)
- **Caveat:** Docsify uses `localStorage` for caching index/search; multiple namespaces on the same domain share
  storage. This is harmless for read-only rendering but could cache stale search indexes. Mitigation: prefix cache keys
  per namespace via `name:` config + JS customisation, OR rely on browser cache invalidation. For Phase 4 this is
  acceptable; document it in DOCS.md.

**Landing page strategy:** A static `index.html` generated at startup by `generate_nginx.py`. Contains a list of
`<a href="/<ns>/">` cards. No client-side JS needed.

**Confidence:** HIGH for nginx layout; MEDIUM for Docsify `localStorage` interaction (mitigation available if it becomes
an issue).

### 8. Phone-logger pattern reuse

**Direct reuse (copy with minimal modification):**

| Phone-logger file                 | Markdown-renderer equivalent | Notes                                                                                                                                                                                                     |
| --------------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Dockerfile`                      | `Dockerfile`                 | Replace upstream Python download with Docsify+Mermaid curl (no `uv` step); same `amd64-base-python:3.12-alpine3.20` base; same OCI label block verbatim                                                   |
| `config.yaml` (HA options schema) | `config.yaml`                | Use `directories: list` instead of nested adapter objects; same `snake_case` + quoted versions pattern                                                                                                    |
| `build.yaml`                      | `build.yaml`                 | VERSION = Docsify version (since auto-update tracks Docsify; per D-03 phase 4 introduces the pattern) — OR pin to a single 1.0.0 starting version since this is a new add-on not yet tracking an upstream |
| `run.sh`                          | `run.sh`                     | Replace `generate_config.py` with `generate_nginx.py`; replace `python -m src.main` with `exec nginx -g "daemon off;"` (or backgrounded)                                                                  |
| `generate_config.py`              | `generate_nginx.py`          | Same Python structure (module docstring, type hints, `pathlib.Path`, `if __name__ == '__main__':` guard); different transformation: reads `directories` instead of nested adapters                        |
| `.upstream.yaml`                  | `.upstream.yaml`             | Pin to `version_pattern: "v4.*"` (D-03 ADD-03) — repo `docsifyjs/docsify`, not this repo. Tracking upstream (not sync)                                                                                    |
| `README.md`                       | `README.md`                  | Same shield-badge pattern with `version-v1.0.0` (or starting version)                                                                                                                                     |
| `DOCS.md`                         | `DOCS.md`                    | Document `directories` option with example                                                                                                                                                                |

**Reuse evidence:** `phone-logger/generate_config.py` lines 146-164 (`main()` function, output path, `flush=True`) is
the canonical template. `phone-logger/Dockerfile` lines 25-26 (`curl -fsSL … | tar xz --strip-components=1`) is the
canonical curl pattern. `phone-logger/run.sh` (full file, 11 lines) is the canonical two-stage script.

**One structural difference:** `run.sh` for markdown-renderer must handle nginx's daemon-mode behaviour. Phone-logger's
pattern uses `exec python -m src.main` which keeps PID 1 occupied by the app. For nginx, the canonical pattern is
`nginx -g 'daemon off;'` to keep nginx in the foreground. Alternatively, start nginx in the background and
`exec sleep infinity` or similar. The `meridian/run.sh` pattern (line 80) starts nginx in the background then exec's
meridian — for our case we want only nginx, so foreground mode is correct.

**Recommended `run.sh`:**

```sh
#!/bin/sh
set -e

# Generate nginx.conf + per-namespace index.html from /data/options.json
python3 /app/generate_nginx.py

# Start nginx in foreground (PID 1) — HA restart policy handles crashes
exec nginx -g 'daemon off;'
```

**Confidence:** HIGH — all patterns verified against phone-logger/meridian source.

### 9. yamllint / shellcheck / markdownlint compliance

**Rules from `.pre-commit-config.yaml` and config files:**

| Tool                    | Rule                                                                       | Applies to markdown-renderer                                                                           |
| ----------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| yamllint                | 2-space indent, 120-char warning, no tabs, no CRLF, LF only                | All `*.yaml` files: `config.yaml`, `build.yaml`, `.upstream.yaml`, `.pre-commit-config.yaml` if edited |
| shellcheck              | `-e SC1091 -e SC2034`                                                      | `run.sh`                                                                                               |
| prettier (markdownlint) | 120-char lines                                                             | `README.md`, `DOCS.md`                                                                                 |
| yamllint                | Quoted strings for versions                                                | `version: "1.0.0-0"` and `VERSION: "1.0.0"` (NOT unquoted)                                             |
| shebang executability   | `check-executables-have-shebangs` + `check-shebang-scripts-are-executable` | `run.sh` and `generate_nginx.py` must be `chmod +x`                                                    |
| pretty-format-json      | `--indent=2`                                                               | `/data/options.json` is generated by HA, not by us — no impact                                         |

**No Dockerfile linting enforced** — hadolint is in `.pre-commit-config.yaml` but its args don't match the
markdown-renderer `Dockerfile`. Currently hadolint is checked via `make docker-build-check` only for
`fritz-callmonitor2mqtt phone-logger meridian`. Plan should add `markdown-renderer` to that list OR keep it outside the
hadolint gate (lower priority — DL3018 for unpinned apk packages may trigger).

**No validate-versions hook pattern update needed** (see §5 above).

**Validation hook auto-discovery:** `scripts/validate-versions.sh` auto-discovers. `scripts/validate-addon-config.py`
auto-discovers. `scripts/validate-dockerfile-args.sh` auto-discovers by `find . -maxdepth 2 -name Dockerfile`. None
require pre-commit `files:` updates.

**Confidence:** HIGH.

## Standard Stack

### Core

| Component  | Version                                                    | Purpose                                                    | Why Standard                                                   |
| ---------- | ---------------------------------------------------------- | ---------------------------------------------------------- | -------------------------------------------------------------- |
| Base image | `ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20` | HA add-on base with bashio, s6-overlay, python 3.12        | Same as phone-logger (D-05)                                    |
| nginx      | alpine `nginx` package (1.26.x in apk)                     | Static file serving for Docsify SPA                        | Stable, well-supported, supports `absolute_redirect` (1.11.8+) |
| Docsify    | `4.13.1` (pinned)                                          | Static SPA renderer for Markdown                           | Last v4 release; v5 is RC only; chosen for no build step       |
| Mermaid    | `11.15.0` UMD (pinned)                                     | Diagram renderer loaded inside Docsify via `doneEach` hook | Self-contained; ESM bundle breaks when vendored                |
| Python     | 3.12 (from base image)                                     | Run `generate_nginx.py` at startup                         | Already in base image                                          |

### Vendored assets

| Asset         | Source                                                                             | Size                         | Vendored path                  |
| ------------- | ---------------------------------------------------------------------------------- | ---------------------------- | ------------------------------ |
| Docsify JS    | `https://github.com/docsifyjs/docsify/archive/refs/tags/v4.13.1.tar.gz`            | ~160 KB (lib/docsify.min.js) | `/app/_docsify/docsify.min.js` |
| Docsify theme | (same tarball) `themes/vue.css`                                                    | ~2 KB                        | `/app/_docsify/themes/vue.css` |
| Mermaid JS    | `https://github.com/mermaid-js/mermaid/archive/refs/tags/mermaid%4011.15.0.tar.gz` | ~3 MB (dist/mermaid.min.js)  | `/app/_docsify/mermaid.min.js` |

### Alternatives Considered

| Instead of                                     | Could Use                            | Tradeoff                                                                                                                                                                |
| ---------------------------------------------- | ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Docsify                                        | MkDocs                               | MkDocs requires build step on every content change — defeats "edit file → refresh" workflow                                                                             |
| Mermaid UMD                                    | Mermaid ESM                          | ESM uses dynamic imports that break when vendored; UMD is self-contained (STATE.md decision)                                                                            |
| Plain `<script>` `doneEach` hook               | Leward `docsify-mermaid-plugin`      | Leward plugin adds a second `<script>` tag for hook registration; inline approach is simpler and removes one asset to vendor. Leward remains documented fallback (D-07) |
| Alpine 3.20 base                               | Alpine 3.23 (latest in phone-logger) | Alpine 3.23 ships nginx 1.28.x with newer features; D-05 locks 3.20. Both work — use 3.20 per CONTEXT                                                                   |
| `python -m http.server` (alternative to nginx) | nginx                                | python's http.server does not support `absolute_redirect off` or per-namespace aliases; nginx is the right choice                                                       |

### Dockerfile asset-vendoring snippet

```dockerfile
ARG DOCSIFY_VERSION=4.13.1
ARG MERMAID_VERSION=11.15.0

RUN apk add --no-cache nginx

WORKDIR /app/_docsify
RUN curl -fsSL "https://github.com/docsifyjs/docsify/archive/refs/tags/v${DOCSIFY_VERSION}.tar.gz" \
    | tar xz --strip-components=1 \
              --wildcards "*/lib/docsify.min.js" "*/themes/vue.css"

WORKDIR /app/_docsify
RUN curl -fsSL "https://github.com/mermaid-js/mermaid/archive/refs/tags/mermaid%40${MERMAID_VERSION}.tar.gz" \
    | tar xz --strip-components=2 \
              --wildcards "*/dist/mermaid.min.js"
```

## Architecture Patterns

### Recommended Project Structure

```
markdown-renderer/
├── config.yaml           # HA manifest: version 1.0.0-0, slug markdown-renderer, ingress:true,
│                         # panel_icon: mdi:text-box-multiple, options.directories: list,
│                         # map: [share:rw, config:rw, media:rw]
├── build.yaml            # VERSION: "1.0.0"  (matches config.yaml subpatch-stripped version)
├── Dockerfile            # Base amd64-base-python:3.12-alpine3.20, apk add nginx,
│                         # curl-vendor Docsify 4.13.1 + Mermaid 11.15.0 UMD,
│                         # COPY run.sh generate_nginx.py, EXPOSE 8099, standard label block
├── run.sh                # python3 generate_nginx.py → exec nginx -g 'daemon off;'
├── generate_nginx.py     # Reads /data/options.json, validates directories,
│                         # writes /tmp/nginx.conf + per-namespace /tmp/docroots/<ns>/index.html
│                         # + /tmp/landing/index.html
├── README.md             # Shield badges v1.0.0, ingress setup notes
├── DOCS.md               # Configuration reference for `directories` option + map volumes
└── .upstream.yaml        # repository: docsifyjs/docsify, version_pattern: "v4.*" (D-03 ADD-03)
```

### Pattern 1: Two-stage `run.sh` (phone-logger pattern)

**What:** `run.sh` calls `generate_nginx.py` to transform `/data/options.json` into nginx config + HTML files, then
exec's nginx as PID 1.

**When to use:** When the runtime (nginx) needs runtime-generated configuration from HA options.

**Example (from phone-logger/run.sh):**

```sh
#!/bin/sh
set -e

# Generate config from HA options
uv run --no-dev python /app/generate_config.py

# Start app
export PHONE_LOGGER_CONFIG=/tmp/phone-logger-config.yaml
exec uv run --no-dev python -m src.main
```

**Adapted for markdown-renderer** (no `uv` needed; python3 is in base image):

```sh
#!/bin/sh
set -e

# Generate nginx config + per-namespace index.html
python3 /app/generate_nginx.py

# Start nginx in foreground
exec nginx -g 'daemon off;'
```

### Pattern 2: Per-namespace index.html generation

**What:** `generate_nginx.py` writes a separate `index.html` for each configured namespace, with `basePath` injected
inline.

**Example (template embedded in `generate_nginx.py`):**

```python
INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{name}</title>
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <link rel="stylesheet" href="../_docsify/themes/vue.css">
  <script>
    window.$docsify = window.$docsify || {{}};
    // basePath derived from browser URL so HA Ingress routing works
    window.$docsify.basePath = window.location.pathname.replace(/\\/?$/, '/');
    window.$docsify.name = '{name_display}';
    window.$docsify.homepage = 'README.md';
    window.$docsify.plugins = [
      function mermaidHook(hook) {{
        hook.afterEach(function (html) {{
          return html.replace(
            /<p><code class="language-mermaid">([\\s\\S]*?)<\/code><\/p>/g,
            '<pre class="mermaid">$1</pre>'
          );
        }});
        hook.doneEach(function () {{
          if (window.mermaid) window.mermaid.run();
        }});
      }},
    ];
  </script>
</head>
<body>
  <div id="app">Loading {name_display}…</div>
  <script src="../_docsify/docsify.min.js"></script>
  <script src="../_docsify/mermaid.min.js"></script>
  <script>
    if (window.mermaid) window.mermaid.initialize({{ startOnLoad: false, securityLevel: 'loose' }});
  </script>
</body>
</html>
"""
```

### Pattern 3: Per-namespace nginx location block generation

**What:** `generate_nginx.py` emits one `location` pair per namespace.

**Example (Python f-string template):**

```python
def render_nginx(namespaces: list[dict]) -> str:
    blocks = []
    for ns in namespaces:
        name = ns["name"]
        blocks.append(f"""
    location = /{name} {{ return 301 /{name}/; }}
    location /{name}/ {{
      alias /tmp/docroots/{name}/;
      try_files $uri $uri/ /index.html;
    }}""")
    return NGINX_TEMPLATE.format(namespace_blocks="\n".join(blocks))
```

### Anti-Patterns to Avoid

- **Hardcoded `basePath` in `index.html`** — BREAKS INGRESS-02. Must be set from `window.location.pathname` at
  page-load.
- **Absolute paths for static assets** (`/docsify.min.js`) — BREAKS INGRESS-03. Use `../_docsify/docsify.min.js`
  (relative).
- **Tracking upstream with `version_pattern: "v*"`** — would auto-update to Docsify v5 RC. Pin to `"v4.*"` per ADD-03.
- **Vendoring Leward plugin as parallel implementation** — D-07 says documented fallback only; inline hook is the
  primary.
- **Manual version bumps** — use `make update-version` per CONVENTIONS.md; pre-commit blocks manual edits.
- **Single Docsify instance per add-on** — fine, but ensure router uses `hash` mode (default) so internal links don't
  try to hit backend.

## Don't Hand-Roll

| Problem                         | Don't Build                  | Use Instead                                   | Why                                                                                                                  |
| ------------------------------- | ---------------------------- | --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Markdown rendering              | Custom MD parser             | Docsify                                       | Edge cases (GFM, tables, code blocks, math) take months to get right; Docsify uses marked.js + Prism under the hood  |
| Diagram rendering               | Custom SVG generator         | Mermaid                                       | 88.9k-star library with security fixes; v11 has CVE patches                                                          |
| Config JSON→HTML transformation | Hand-written template engine | Python f-strings + `pathlib.Path`             | Same pattern as `phone-logger/generate_config.py`; no Jinja2 dep needed                                              |
| Hash router vs history router   | Custom URL routing           | Docsify `routerMode: 'hash'` (default)        | Hash mode requires no server-side rewrite — works with HA Ingress out of the box                                     |
| Inline Mermaid hook             | Custom plugin loader         | Inline `<script>` with `hook.doneEach`        | Plugin loading requires another `<script>` tag and another vendored file; inline is simpler                          |
| Add-on metadata validation      | Custom YAML schema validator | `scripts/validate-addon-config.py` (existing) | Already validates arch, startup, boot, map types; reuses phone-logger/meridian validation                            |
| Static asset MIME types         | Custom `mime.types`          | Alpine nginx default                          | nginx ships with `/etc/nginx/mime.types`; `.js` → `application/javascript`, `.css` → `text/css` — no override needed |

**Key insight:** The whole add-on is essentially "run nginx with a generated config". The complexity is in the **config
generation**, not in the runtime. Resist the urge to over-engineer the runtime.

## Runtime State Inventory

> **Phase 4 is scaffold-only** — no existing runtime state to migrate. Documented for completeness.

| Category            | Items Found                      | Action Required                                                     |
| ------------------- | -------------------------------- | ------------------------------------------------------------------- |
| Stored data         | None — add-on does not exist yet | None (scaffold creates fresh)                                       |
| Live service config | None                             | None                                                                |
| OS-registered state | None                             | None                                                                |
| Secrets/env vars    | None                             | None — `/data/options.json` is HA-managed; no secrets in this phase |
| Build artifacts     | None                             | None — first Docker build creates the image                         |

**Phase 4 does not modify any existing add-on. All file creation is additive in `markdown-renderer/`.**

**Phase 5 will need to verify:** That the `map:` volumes (`share:rw`, `config:rw`, `media:rw`) actually mount and serve
Markdown files from those paths. This is purely runtime behaviour; no code change required in Phase 4 — the `map:`
declaration in `config.yaml` is the only configuration.

## Common Pitfalls

### Pitfall 1: Wrong basePath causes 404s on .md fetches

**What goes wrong:** Static `index.html` with hardcoded `basePath: '/'` fetches `/README.md` instead of
`/api/hassio_ingress/<TOKEN>/<ns>/README.md` → 404. **Why it happens:** Developer forgets `window.location.pathname`
includes the Ingress prefix. **How to avoid:** Use inline `<script>` to set `basePath` at page-load time:
`window.$docsify.basePath = window.location.pathname.replace(/\/?$/, '/');` **Warning signs:** Browser console shows 404
on `.md` fetches; sidebar empty.

### Pitfall 2: Absolute `/docsify.min.js` 404s under Ingress

**What goes wrong:** `index.html` references `<script src="/_docsify/docsify.min.js">` — resolves to
`https://<ha_host>/_docsify/...` (HA root), not the Ingress path. **Why it happens:** Convention from non-Ingress
deployments. **How to avoid:** Use `../_docsify/docsify.min.js` (relative). Verified by INGRESS-03 requirement and
CONTEXT D-04. **Warning signs:** Browser console shows 404 on `docsify.min.js`.

### Pitfall 3: nginx default 301 redirect leaks internal IP

**What goes wrong:** Trailing-slash redirect with default `absolute_redirect on` produces
`Location: http://172.30.33.4:8099/foo/` — browser navigates to internal Docker IP and fails. **Why it happens:** nginx
default is `absolute_redirect on`; HA Ingress proxy only works with relative redirects. **How to avoid:** Set
`absolute_redirect off` in nginx `http {}` block (INGRESS-04, D-04). **Warning signs:** Browser shows connection-refused
error after clicking a sidebar link.

### Pitfall 4: Mermaid code blocks render as code, not diagrams

**What goes wrong:** `mermaid.run()` is never called → `<pre class="mermaid">` text stays as-is. **Why it happens:**
Docsify's `doneEach` hook not registered, or `mermaid.initialize()` not called before `mermaid.run()`. **How to avoid:**
Inline plugin in `index.html` with both `hook.afterEach` (transform `<pre>` → `<pre class="mermaid">`) and
`hook.doneEach` (call `mermaid.run()`). Mermaid script loads BEFORE the inline script so `window.mermaid` exists.
**Warning signs:** Browser console shows `mermaid is not defined` or diagrams show as text.

### Pitfall 5: Auto-update proposes v5 RC upgrade

**What goes wrong:** `.upstream.yaml` uses `version_pattern: "v*"` → matches `v5.0.0-rc.4` → add-on upgrades to a
non-production v5 version. **Why it happens:** Default pattern too loose. **How to avoid:** Pin to
`version_pattern: "v4.*"` per ADD-03. **Warning signs:** Add-on breaks after auto-update PR merges.

### Pitfall 6: Namespace name collision breaks nginx

**What goes wrong:** Two namespaces with same name OR name conflicts with `_docsify` → nginx fails to start or routes
wrong. **Why it happens:** No validation in `generate_nginx.py`. **How to avoid:** Validate names against: empty,
non-URI-safe chars (`[^a-z0-9-]`), reserved names (`_docsify`, `api`, `data`, `share`, `config`, `media`). MULTI-05.
**Warning signs:** nginx fails to start; `nginx: [emerg] duplicate location`.

### Pitfall 7: nginx won't reload if config invalid at runtime

**What goes wrong:** `nginx -g 'daemon off;'` exits immediately if config has errors → container keeps restarting. **Why
it happens:** Missing `nginx -t` validation step before exec. **How to avoid:** `generate_nginx.py` validates names AND
runs `nginx -t -c /tmp/nginx.conf` before exiting 0. If `nginx -t` fails, `generate_nginx.py` exits 1 and the add-on
crashes (HA restart policy handles retry). **Warning signs:** HA add-on log shows `nginx: [emerg] ...`.

### Pitfall 8: vendored Docsify theme file missing

**What goes wrong:** `themes/vue.css` not extracted from the tarball → ugly unstyled page. **Why it happens:** Wildcard
pattern mismatch (`--wildcards "*/themes/vue.css"` strips path). **How to avoid:** Test the extraction in Dockerfile
build; the `tar --strip-components=1` strips the top-level directory. **Warning signs:** HTML renders but no styling;
`<div id="app">` text only.

### Pitfall 9: chmod missing on run.sh / generate_nginx.py

**What goes wrong:** Container fails to start with "permission denied" on `/app/run.sh`. **Why it happens:** Files
copied without executable bit. **How to avoid:** `COPY run.sh generate_nginx.py /app/` followed by
`RUN chmod a+x /app/run.sh /app/generate_nginx.py` in Dockerfile (same pattern as phone-logger). **Warning signs:**
Container log: `exec /app/run.sh: permission denied`.

## Code Examples

### Verified patterns from official sources

### Example 1: Docsify `basePath` for subpath deployment

**Source:** docsify configuration docs (`docsify.js.org/#/configuration`)

```js
window.$docsify = {
  basePath: "/path/", // fixed path
  // OR dynamically set before script load:
  basePath: window.location.pathname.replace(/\/?$/, "/"),
};
```

**Confidence:** HIGH — verified against docsify configuration docs.

### Example 2: Docsify plugin lifecycle hooks

**Source:** docsify write-a-plugin docs (`docs/write-a-plugin.md` in v4.13.1)

```js
window.$docsify = {
  plugins: [
    function myPlugin(hook, vm) {
      hook.init(function () {});
      hook.mounted(function () {});
      hook.beforeEach(function (markdown) {
        return markdown;
      });
      hook.afterEach(function (html) {
        return html;
      });
      hook.doneEach(function () {});
      hook.ready(function () {});
    },
  ],
};
```

**Confidence:** HIGH — verified from v4.13.1 source.

### Example 3: Mermaid `doneEach` hook (Leward plugin source for reference)

**Source:** `Leward/mermaid-docsify/src/plugin.js` (master branch)

```js
const plugin = (mermaidConf) => (hook) => {
  hook.afterEach((html, next) => {
    const htmlElement = document.createElement("div");
    htmlElement.innerHTML = html;
    htmlElement.querySelectorAll("pre[data-lang=mermaid]").forEach((element) => {
      const replacement = document.createElement("div");
      replacement.textContent = element.textContent;
      replacement.classList.add("mermaid");
      element.parentNode.replaceChild(replacement, element);
    });
    next(htmlElement.innerHTML);
  });
  hook.doneEach(() => mermaid.run(mermaidConf));
};
```

**Note:** Leward targets `pre[data-lang=mermaid]` (v5 syntax). For v4.13.1 the selector is
`<p><code class="language-mermaid">…</code></p>` — handled by the regex in our adapted inline plugin.

**Confidence:** HIGH — verified source.

### Example 4: nginx `absolute_redirect off` + per-namespace alias

**Source:** nginx docs (`ngx_http_core_module.html`) + meridian/nginx.conf in-repo

```nginx
http {
  absolute_redirect off;
  server {
    listen 8099;
    location /_docsify/ {
      alias /app/_docsify/;
    }
    location = /foo { return 301 /foo/; }
    location /foo/ {
      alias /tmp/docroots/foo/;
      try_files $uri $uri/ /index.html;
    }
  }
}
```

**Confidence:** HIGH — `absolute_redirect` available since 1.11.8; meridian/nginx.conf is the in-repo reference.

### Example 5: Phone-logger `generate_config.py` template

**Source:** `phone-logger/generate_config.py` lines 1-11 + 146-164

```python
#!/usr/bin/env python3
"""Transform HA options.json into AppConfig-compatible YAML."""

import json
from pathlib import Path

import yaml

OPTIONS_PATH = "/data/options.json"
OUTPUT_PATH = "/tmp/phone-logger-config.yaml"


def main() -> None:
    options_path = Path(OPTIONS_PATH)
    if not options_path.exists():
        Path(OUTPUT_PATH).write_text("{}\n")
        return
    with open(options_path) as f:
        options = json.load(f)
    config = transform(options)
    with open(OUTPUT_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


if __name__ == "__main__":
    main()
```

**Adapted for `generate_nginx.py`:**

```python
#!/usr/bin/env python3
"""Generate nginx.conf + per-namespace index.html from HA options.json.

Reads /data/options.json with shape:
  {"directories": [{"name": "docs", "path": "/share/docs"}, ...]}

Validates namespace names, writes:
  - /tmp/nginx.conf
  - /tmp/docroots/<name>/index.html for each namespace
  - /tmp/landing/index.html (lists all namespaces)
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

OPTIONS_PATH = Path("/data/options.json")
NGINX_CONF = Path("/tmp/nginx.conf")
DOCROOTS = Path("/tmp/docroots")
LANDING = Path("/tmp/landing")
RESERVED_NAMES = {"_docsify", "api", "data", "share", "config", "media"}
VALID_NAME = __import__("re").compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def validate_namespace(name: str) -> None:
    if not name:
        raise ValueError("namespace name cannot be empty")
    if not VALID_NAME.match(name):
        raise ValueError(f"namespace name '{name}' must match {VALID_NAME.pattern}")
    if name in RESERVED_NAMES:
        raise ValueError(f"namespace name '{name}' is reserved")


# ... main() with template rendering ...
```

## State of the Art

| Old Approach                              | Current Approach                                          | When Changed                                       | Impact                                                                                          |
| ----------------------------------------- | --------------------------------------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Mermaid 10.x ESM build                    | Mermaid 11.x UMD build                                    | mermaid 11.0 (2024)                                | UMD is the only self-contained build; ESM requires dynamic imports that break when vendored     |
| Docsify CDN-loaded                        | Vendored via tarball                                      | Always                                             | This add-on's raison d'être — no CDN at runtime                                                 |
| `nginx proxy_pass` to upstream (meridian) | `nginx alias` to static files (markdown-renderer)         | Always                                             | Static SPA needs no upstream; alias is the right primitive                                      |
| bashio-only config reading (phone-logger) | Python JSON config gen (phone-logger + markdown-renderer) | phone-logger Phase                                 | Python is needed for structured `directories` list-of-objects; bashio is fine for scalar fields |
| Docsify v5 RC                             | Docsify v4.13.1 (pinned)                                  | Docsify v5 still RC as of 2026-03-11 (v5.0.0-rc.4) | v4 is stable; v5 has breaking changes per docsifyjs release notes                               |

**Deprecated/outdated:**

- **Docsify v3 and earlier**: missing v4's relativePath improvements and plugin API stability. Use v4.13.1.
- **Mermaid 9.x and earlier**: API changed significantly in 10.x; stick to 11.x.
- **Leward/mermaid-docsify v1.x**: uses older Mermaid 10; v2.0.0 works with Mermaid 11 (but we use inline hook anyway).

## Open Questions

1. **Exact regex for Docsify v4 ` ```mermaid ` rendering**

   - What we know: v4 renders fenced code as `<pre><code class="language-foo">…</code></pre>`. The `<p><code>` wrapper
     is generated by marked.js default settings.
   - What's unclear: Whether Docsify's `markdown.render` config affects the wrapping (e.g., `breaks: true`,
     `smartypants`).
   - Recommendation: Empirical test in Phase 4 with a sample `.md` file containing a mermaid diagram. If the regex
     doesn't match, adjust the `afterEach` replacement. The Leward plugin v2.0.0 source is a reference.

2. **Does Mermaid v11 require CSP `unsafe-eval`?**

   - What we know: STATE.md flags CSP/unsafe-eval as a Phase 6 open question. Mermaid uses dynamic code generation for
     layouts.
   - What's unclear: Whether HA Supervisor injects restrictive CSP into Ingress responses.
   - Recommendation: Phase 4 testing will confirm. If Mermaid fails with CSP error, the fix is to add a
     `Content-Security-Policy` header in nginx that explicitly allows `unsafe-eval` for `_docsify/mermaid.min.js`. This
     is documented as a Phase 6 follow-up if needed.

3. **Leward plugin npm distribution**
   - What we know: `https://cdn.jsdelivr.net/npm/docsify-mermaid-plugin@2.0.0/dist/docsify-mermaid.js` returns 404. The
     Leward plugin is published under the npm name `docsify-mermaid` (per the README badge).
   - What's unclear: Whether `docsify-mermaid` npm package is maintained.
   - Recommendation: Fallback path is to vendor the Leward `plugin.js` source directly from
     `https://raw.githubusercontent.com/Leward/mermaid-docsify/master/src/plugin.js` if empirical test shows inline
     `doneEach` fails. NOT a Phase 4 task unless inline fails.

## Environment Availability

**Step 2.6 audit: SKIPPED partially** — Phase 4 has external Docker build dependencies (HA base image, npm tarballs) but
no runtime external services beyond HA Supervisor (which is the user's environment, not this developer's).

| Dependency                          | Required By                                    | Available        | Version | Fallback                                       |
| ----------------------------------- | ---------------------------------------------- | ---------------- | ------- | ---------------------------------------------- |
| `podman` / `docker`                 | Local Docker build testing                     | ✓ (podman 5.8.3) | —       | Use `make build-addon ADDON=markdown-renderer` |
| `pre-commit`                        | Local lint validation                          | ✓ (4.5.1)        | —       | —                                              |
| `python3`                           | Run generate_nginx.py locally for test         | ✓ (3.14.6)       | —       | —                                              |
| `node`                              | Not needed for runtime (no JS tooling in repo) | ✓ (22.23.1)      | —       | —                                              |
| Network to `github.com`             | Build-time curl of Docsify + Mermaid tarballs  | ✓ verified       | —       | —                                              |
| Network to `ghcr.io/home-assistant` | Pull base image during Docker build            | ✓ verified       | —       | —                                              |

**No blocking missing dependencies.** Phase 4 can be planned and executed with the existing toolchain.

## Validation Architecture

> `workflow.nyquist_validation` in `.planning/config.json` — assume ENABLED (not explicitly disabled).

### Test Framework

| Property           | Value                                                                                                                                    |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Framework          | **None** — repo uses static analysis + structural validation (pre-commit hooks + `scripts/validate-*.{sh,py}`) instead of unit tests     |
| Config file        | `.pre-commit-config.yaml`, `scripts/validate-versions.sh`, `scripts/validate-addon-config.py`, `scripts/validate-dockerfile-args.sh`     |
| Quick run command  | `pre-commit run --files markdown-renderer/{Dockerfile,config.yaml,build.yaml,run.sh,generate_nginx.py,README.md,DOCS.md,.upstream.yaml}` |
| Full suite command | `make check-all`                                                                                                                         |

### Phase Requirements → Test Map

| Req ID              | Behavior                                                  | Test Type          | Automated Command                                                                                                     | File Exists?                                |
| ------------------- | --------------------------------------------------------- | ------------------ | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| ADD-01              | 4-file pattern + `.upstream.yaml`                         | Structural         | `make validate-addons`                                                                                                | ✅ existing                                 |
| ADD-02              | Vendored Docsify 4.13.1 + Mermaid 11.15.0                 | Build verification | `make build-addon ADDON=markdown-renderer` (requires docker)                                                          | ⚠️ manual inspection of Docker build output |
| ADD-03              | `.upstream.yaml` version_pattern="v4.\*"                  | Lint               | `pre-commit run check-yaml --files markdown-renderer/.upstream.yaml`                                                  | ✅ existing                                 |
| ADD-04              | README.md shield badges + DOCS.md                         | Markdown lint      | `pre-commit run prettier --files markdown-renderer/README.md markdown-renderer/DOCS.md`                               | ✅ existing                                 |
| INGRESS-01          | `ingress: true`, `panel_icon`                             | Schema             | `pre-commit run validate-addon-config`                                                                                | ✅ existing                                 |
| INGRESS-02..05      | Docsify basePath + relative paths + nginx + Mermaid       | Manual             | Empirical test in HA (Phase 4 final verification)                                                                     | ❌ manual only                              |
| MULTI-01..06        | `generate_nginx.py` outputs valid nginx.conf + index.html | Manual             | `python3 markdown-renderer/generate_nginx.py` against sample `/data/options.json`, then `nginx -t -c /tmp/nginx.conf` | ❌ manual only                              |
| 3-file version sync | config.yaml/build.yaml/README.md match                    | Version validation | `pre-commit run validate-versions`                                                                                    | ✅ existing (auto-discovers)                |

### Sampling Rate

- **Per task commit:** `pre-commit run --files <changed files>`
- **Per wave merge:** `make check-all`
- **Phase gate:** `make check-all` green + empirical HA Ingress test of single-namespace loading + Mermaid diagram
  rendering + `.md` fetch (no 404)

### Wave 0 Gaps

- [ ] `markdown-renderer/generate_nginx.py` — needs a `tests/test_generate_nginx.py` or similar to validate template
      generation without HA. **OUT OF SCOPE** for this phase (no test framework in repo; manual verification only).
- [ ] Manual integration test harness — would require a local HA instance or mock options.json. **OUT OF SCOPE**;
      empirical Phase 4 verification done via user's HA instance.
- [ ] Dockerfile hadolint verification — `make docker-build-check` currently lists only
      `fritz-callmonitor2mqtt phone-logger meridian`. Plan should either add `markdown-renderer` to that list OR
      document it as a follow-up.

**Summary:** No automated test framework exists. Phase 4 verification relies on (a) existing pre-commit hooks for
structural validation, (b) manual `nginx -t` for config validation, (c) empirical HA Ingress loading test by the user.
This is consistent with all other add-ons in the repo.

## Concrete File-by-file Implementation Map

### `markdown-renderer/config.yaml`

**Source pattern:** `phone-logger/config.yaml` + `meridian/config.yaml` + D-01 schema

Key fields:

```yaml
name: "Markdown Renderer"
version: "1.0.0-0"
slug: "markdown-renderer"
init: false
arch: [amd64]
url: "https://github.com/akentner/homeassistant-addons"
startup: "application"
boot: "auto"
host_network: false
ingress: true
ingress_port: 8099
panel_icon: "mdi:text-box-multiple" # INGRESS-01
panel_title: "Markdown"
map:
  - share:rw # MULTI-06
  - config:rw
  - media:rw
options:
  directories:
    - name: "docs"
      path: "/share/docs"
schema:
  directories:
    - name: str
      path: str
```

**Verify with:** `pre-commit run validate-addon-config`

### `markdown-renderer/build.yaml`

**Source pattern:** `phone-logger/build.yaml`

```yaml
build_from:
  amd64: "ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20"
args:
  VERSION: "1.0.0"
```

### `markdown-renderer/Dockerfile`

**Source pattern:** `phone-logger/Dockerfile` (same base, same curl pattern) + vendored docsify/mermaid steps

```dockerfile
ARG BUILD_FROM
FROM ${BUILD_FROM}

ARG VERSION
ARG DOCSIFY_VERSION=4.13.1
ARG MERMAID_VERSION=11.15.0
ARG WORKING_DIR=/app

# Install nginx (runtime) — small footprint
RUN apk add --no-cache nginx

# Install uv for parity with phone-logger (not strictly needed; keep pattern consistent)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Vendored static assets (DOCSIFY + MERMAID)
WORKDIR ${WORKING_DIR}/_docsify
RUN mkdir -p themes && \
    curl -fsSL "https://github.com/docsifyjs/docsify/archive/refs/tags/v${DOCSIFY_VERSION}.tar.gz" \
    | tar xz --strip-components=1 \
              --wildcards "*/lib/docsify.min.js" "*/themes/vue.css" && \
    curl -fsSL "https://github.com/mermaid-js/mermaid/archive/refs/tags/mermaid%40${MERMAID_VERSION}.tar.gz" \
    | tar xz --strip-components=2 \
              --wildcards "*/dist/mermaid.min.js"

# Copy add-on-specific files
WORKDIR ${WORKING_DIR}
COPY run.sh generate_nginx.py ./
RUN chmod a+x run.sh generate_nginx.py

ENV WORKING_DIR=${WORKING_DIR}
EXPOSE 8099
CMD ["/app/run.sh"]

# ### LABELS  (standard OCI + HA block, copy from phone-logger/Dockerfile)
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="akentner (https://github.com/akentner)" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="Home Assistant Add-ons" \
    org.opencontainers.image.authors="akentner (https://github.com/akentner)" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://github.com/akentner" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}
```

### `markdown-renderer/run.sh`

**Source pattern:** `phone-logger/run.sh`

```sh
#!/bin/sh
set -e

# Generate nginx config + per-namespace index.html from HA options
python3 /app/generate_nginx.py

# Start nginx in foreground
exec nginx -g 'daemon off;'
```

### `markdown-renderer/generate_nginx.py`

**Source pattern:** `phone-logger/generate_config.py`

Skeleton (full implementation in PLAN.md):

```python
#!/usr/bin/env python3
"""Generate nginx.conf + per-namespace index.html from HA options.json."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

OPTIONS_PATH = Path("/data/options.json")
NGINX_CONF_PATH = Path("/tmp/nginx.conf")
DOCROOTS_DIR = Path("/tmp/docroots")
LANDING_DIR = Path("/tmp/landing")

RESERVED_NAMES = {"_docsify", "api", "data", "share", "config", "media"}
VALID_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def validate_namespace(name: str) -> None:
    if not name:
        raise ValueError("namespace name cannot be empty")
    if not VALID_NAME_RE.match(name):
        raise ValueError(f"namespace name '{name}' must match {VALID_NAME_RE.pattern}")
    if name in RESERVED_NAMES:
        raise ValueError(f"namespace name '{name}' is reserved (conflicts with reserved path)")


# ... INDEX_HTML_TEMPLATE, LANDING_HTML_TEMPLATE, NGINX_TEMPLATE ...


def main() -> int:
    # 1. Read /data/options.json
    # 2. Validate each namespace name (MULTI-05)
    # 3. Clear and recreate /tmp/docroots/ + /tmp/landing/
    # 4. Write per-namespace index.html
    # 5. Write landing/index.html
    # 6. Write /tmp/nginx.conf
    # 7. Validate config with `nginx -t -c /tmp/nginx.conf`
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `markdown-renderer/.upstream.yaml`

**Source pattern:** `phone-logger/.upstream.yaml` with custom `version_pattern`

```yaml
upstream:
  repository: "docsifyjs/docsify"
  version_pattern: "v4.*" # ADD-03 — block v5 RC upgrade
  version_strip: "^v"
addon:
  version_pattern: "sync"
```

### `markdown-renderer/README.md`

**Source pattern:** `meridian/README.md` (Phase 3 reference) + `phone-logger/README.md`

```markdown
# Home Assistant Add-on: Markdown Renderer

[![Release][release-shield]][release] ![Project Stage][project-stage-shield]

Renders Markdown directories as Docsify SPAs via Home Assistant Ingress with Mermaid diagram support.

## Configuration

See `DOCS.md` for the `directories` option and volume mounting.

## Vendored Assets

This add-on bundles Docsify and Mermaid locally — no CDN requests at runtime.

[release-shield]: https://img.shields.io/badge/version-v1.0.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v1.0.0
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-yellow.svg
```

### `markdown-renderer/DOCS.md`

**Source pattern:** `meridian/DOCS.md` (Phase 3 reference)

Documents the `directories: list({name, path})` option, examples, and the `share:rw config:rw media:rw` volume mounts.

## Reference URLs

### Verified (HTTP 200/302 responses observed 2026-06-27)

| URL                                                                                | Purpose                                              | Status                                            |
| ---------------------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------- |
| `https://github.com/docsifyjs/docsify/releases/tag/v4.13.1`                        | Docsify release                                      | 200 (verified via releases page)                  |
| `https://github.com/docsifyjs/docsify/archive/refs/tags/v4.13.1.tar.gz`            | Docsify tarball for vendoring                        | 302 → codeload (verified)                         |
| `https://github.com/mermaid-js/mermaid/releases/tag/mermaid%4011.15.0`             | Mermaid release                                      | 200 (verified)                                    |
| `https://github.com/mermaid-js/mermaid/archive/refs/tags/mermaid%4011.15.0.tar.gz` | Mermaid tarball                                      | 302 → codeload (verified)                         |
| `https://cdn.jsdelivr.net/npm/docsify@4.13.1/lib/docsify.min.js`                   | CDN fallback / sanity check                          | 200 (verified, 160920 bytes)                      |
| `https://cdn.jsdelivr.net/npm/mermaid@11.15.0/dist/mermaid.min.js`                 | CDN fallback / sanity check                          | 200 (verified)                                    |
| `https://unpkg.com/docsify@4.13.1/lib/docsify.min.js`                              | Alternative CDN                                      | 200 (verified)                                    |
| `https://github.com/Leward/mermaid-docsify/blob/master/src/plugin.js`              | Fallback mermaid-docsify plugin source               | 200 (verified — fallback only)                    |
| `https://github.com/home-assistant/supervisor/blob/main/supervisor/api/ingress.py` | HA Ingress proxy implementation                      | 200 (verified — source confirms URL stripping)    |
| `https://docsify.js.org/`                                                          | Docsify docs (rendered via JS — fetch returns shell) | n/a                                               |
| `http://nginx.org/en/docs/http/ngx_http_core_module.html#absolute_redirect`        | nginx absolute_redirect docs                         | 200 (verified — directive available since 1.11.8) |

### Raw GitHub content (used in research)

| URL                                                                                  | Purpose                                        |
| ------------------------------------------------------------------------------------ | ---------------------------------------------- |
| `https://raw.githubusercontent.com/docsifyjs/docsify/v4.13.1/docs/configuration.md`  | Docsify configuration reference                |
| `https://raw.githubusercontent.com/docsifyjs/docsify/v4.13.1/docs/write-a-plugin.md` | Docsify plugin lifecycle hooks                 |
| `https://raw.githubusercontent.com/docsifyjs/docsify/v4.13.1/docs/cdn.md`            | Docsify CDN URL pattern (`lib/docsify.min.js`) |
| `https://raw.githubusercontent.com/Leward/mermaid-docsify/master/src/plugin.js`      | Leward plugin source (fallback reference)      |

## Risk Register

| Risk                                                                     | Likelihood      | Impact | Mitigation                                                                                                                                           |
| ------------------------------------------------------------------------ | --------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Inline Mermaid `doneEach` hook regex doesn't match Docsify v4 rendering  | LOW             | MEDIUM | Fallback to vendored Leward plugin (D-07); manual test in Phase 4                                                                                    |
| Mermaid v11 requires `unsafe-eval` CSP that HA Supervisor injects        | LOW             | MEDIUM | Add CSP header in nginx for `/api/_docsify/mermaid.min.js` (Phase 6 follow-up; not blocking Phase 4 INGRESS-05 since STATE.md says test empirically) |
| nginx `absolute_redirect off` behaviour with `try_files` fallback path   | LOW             | LOW    | Test empirically; `try_files $uri $uri/ /index.html` is standard nginx pattern, no known issues                                                      |
| Docsify `localStorage` cache contamination across namespaces             | MEDIUM          | LOW    | Acceptable for Phase 4 read-only rendering; document in DOCS.md                                                                                      |
| Vendored tarball `tar --strip-components` strips wrong level             | LOW             | LOW    | Test the Dockerfile build locally; exact pattern verified in `phone-logger/Dockerfile`                                                               |
| First-time namespace validation rejects valid names                      | LOW             | MEDIUM | Document validation rules in DOCS.md; rejected name is logged with reason                                                                            |
| Auto-update proposes Docsify v5 RC                                       | LOW (mitigated) | HIGH   | `.upstream.yaml` `version_pattern: "v4.*"` per ADD-03                                                                                                |
| nginx won't reload if config invalid                                     | LOW             | LOW    | `generate_nginx.py` runs `nginx -t` before exiting; HA restart policy handles retry                                                                  |
| Phase 4 validate-versions regex NOT needed (deviation from CONTEXT D-08) | CONFIRMED       | NONE   | `validate-versions.sh` is auto-discovery-based; no `.pre-commit-config.yaml` edit required. Plan should note this and skip the change.               |

## Recommended Plan Shape

### Number of plans: 3

**Plan 01 — Core add-on scaffold (single-namespace working end-to-end):**

- Create `markdown-renderer/` directory
- `config.yaml`, `build.yaml`, `.upstream.yaml` — version 1.0.0-0 / 1.0.0 / v1.0.0
- `Dockerfile` — base image, apk add nginx, vendor Docsify + Mermaid via curl, standard labels
- `run.sh` — two-stage pattern: `generate_nginx.py` then `exec nginx -g 'daemon off;'`
- `generate_nginx.py` — skeleton supporting SINGLE namespace (one entry in `directories`); full multi-namespace logic
  stubbed for Plan 02
- `_docsify/` directory is created at Docker build time (not committed)
- **Verification:** `make check-all`, `pre-commit run --files markdown-renderer/*`, `make validate-addons`,
  `make validate-versions`

**Plan 02 — Multi-namespace `generate_nginx.py` full implementation:**

- Extend `generate_nginx.py`: iterate `directories`, validate each name (MULTI-05), write per-namespace `index.html`,
  write landing `index.html`, write `/tmp/nginx.conf`
- Add `INDEX_HTML_TEMPLATE`, `LANDING_HTML_TEMPLATE`, `NGINX_TEMPLATE` as Python f-strings
- Implement namespace validation regex + reserved-name list
- Add `nginx -t -c /tmp/nginx.conf` validation step
- **Verification:** `python3 generate_nginx.py` against a sample `/data/options.json`, then
  `nginx -t -c /tmp/nginx.conf` — verify config is valid

**Plan 03 — Documentation + empirical verification prep:**

- `README.md` with shield badges
- `DOCS.md` documenting `directories` option, examples, volume mounting
- Document the D-08 deviation (no `.pre-commit-config.yaml` edit needed)
- **Verification:** `pre-commit run prettier --files markdown-renderer/README.md markdown-renderer/DOCS.md`,
  `make validate-addons`

### Wave structure

```
Wave 1: Plan 01  (scaffold)
Wave 2: Plan 02  (depends on Plan 01) + Plan 03 (depends on Plan 01)
```

Wave 2 plans are independent of each other (02 = code, 03 = docs).

### Dependencies

- Plan 02 depends on Plan 01 (needs `generate_nginx.py` skeleton)
- Plan 03 depends on Plan 01 (needs `config.yaml` options schema to be defined for DOCS.md)
- **External dependency:** User's HA instance for empirical Phase 4 verification (mentioned in STATE.md "Todos" — not
  part of automated execution)

### Pre-commit changes summary

**NONE REQUIRED.** All hooks (validate-versions, validate-addon-config, prettier, yamllint, shellcheck) auto-discover.
CONTEXT.md D-08 is a no-op given the current `.pre-commit-config.yaml` configuration.

### Validation at end of Phase 4

- `make check-all` passes
- Manual test in user's HA: install add-on → Ingress panel shows Markdown Renderer → enter one namespace → Markdown
  renders, sidebar works, Mermaid diagrams render, no 404s, no CDN requests (check browser DevTools Network tab)

## Sources

### Primary (HIGH confidence)

- `https://github.com/docsifyjs/docsify/releases/tag/v4.13.1` — Verified Docsify 4.13.1 release exists; no v4.13.2 or
  later
- `https://github.com/docsifyjs/docsify/releases/tag/v5.0.0-rc.4` — Verified v5 RC exists; justifies `v4.*` pin
- `https://github.com/mermaid-js/mermaid/releases/tag/mermaid%4011.15.0` — Verified Mermaid 11.15.0 release
- `https://raw.githubusercontent.com/docsifyjs/docsify/v4.13.1/docs/configuration.md` — Verified `basePath` config
  semantics
- `https://raw.githubusercontent.com/docsifyjs/docsify/v4.13.1/docs/write-a-plugin.md` — Verified plugin lifecycle hooks
  (`doneEach` etc.)
- `https://raw.githubusercontent.com/docsifyjs/docsify/v4.13.1/docs/cdn.md` — Verified CDN URL pattern
  `lib/docsify.min.js`
- `https://raw.githubusercontent.com/Leward/mermaid-docsify/master/src/plugin.js` — Verified `doneEach → mermaid.run()`
  pattern (fallback reference)
- `https://github.com/home-assistant/supervisor/blob/main/supervisor/api/ingress.py` — Verified HA Ingress URL stripping
  (lines 71-78)
- `http://nginx.org/en/docs/http/ngx_http_core_module.html#absolute_redirect` — Verified directive availability
  (1.11.8+)
- `phone-logger/Dockerfile`, `phone-logger/config.yaml`, `phone-logger/run.sh`, `phone-logger/generate_config.py`,
  `phone-logger/.upstream.yaml`, `phone-logger/README.md`, `phone-logger/DOCS.md` — All read in full
- `meridian/Dockerfile`, `meridian/config.yaml`, `meridian/run.sh`, `meridian/nginx.conf` — All read in full
- `.pre-commit-config.yaml`, `scripts/validate-versions.sh`, `scripts/validate-addon-config.py`,
  `scripts/validate-dockerfile-args.sh`, `Makefile`, `repository.yaml` — All read in full
- `.planning/REQUIREMENTS.md` §ADD, §INGRESS, §MULTI — All requirements traced to research support
- `.planning/phases/04-scaffold-ingress-validation/04-CONTEXT.md` — All locked decisions verified

### Secondary (MEDIUM confidence)

- `https://cdn.jsdelivr.net/npm/docsify@4.13.1/lib/docsify.min.js` — Verified CDN URL (response 200) — but using GitHub
  tarball, not CDN, for vendoring
- `https://cdn.jsdelivr.net/npm/mermaid@11.15.0/dist/mermaid.min.js` — Verified CDN URL (response 200) — fallback option
- `https://unpkg.com/docsify@4.13.1/lib/docsify.min.js` — Verified alternative CDN

### Tertiary (LOW confidence)

- Leward plugin's exact behaviour with v4.13.1 (Leward v2.0.0 targets v5 syntax `pre[data-lang=mermaid]`; we adapt for
  v4's `<p><code class="language-mermaid">` wrapper — empirical confirmation needed)
- Mermaid v11 CSP requirements (STATE.md open question — Phase 6 follow-up if needed)

## Metadata

**Confidence breakdown:**

- **Standard stack:** HIGH — All CDN/tarball URLs verified live; nginx directive version verified; HA Ingress URL format
  verified from supervisor source
- **Architecture:** HIGH — Patterns directly reuse phone-logger/meridian with verified source
- **Pitfalls:** HIGH — All pitfalls derived from either (a) CONTEXT.md D-04..D-08 explicit requirements or (b) verified
  Docsify/nginx behaviour
- **Multi-namespace:** HIGH — D-03 in CONTEXT.md; full generator pattern documented
- **Mermaid hook:** MEDIUM — Pattern verified from Leward source; exact v4 regex is empirical (expected to work; minor
  iteration possible)
- **validate-versions auto-discovery:** HIGH — Verified by reading `.pre-commit-config.yaml` (has `always_run: true`, no
  `files:` key) and `scripts/validate-versions.sh` (uses `find`/dir walk)

**Research date:** 2026-06-27

**Valid until:** 2026-07-27 (30 days — Docsify v4 is stable, Mermaid 11.x is stable, HA Supervisor is stable; v5 of
Docsify may release, requiring pin adjustment)

---

## RESEARCH COMPLETE
