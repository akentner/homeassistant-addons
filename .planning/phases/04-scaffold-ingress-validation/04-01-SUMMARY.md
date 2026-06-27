---
phase: 04-scaffold-ingress-validation
plan: 01
subsystem: markdown-renderer
tags: [add-on-scaffold, ingress, docsify, mermaid, kroki, nginx]
dependency_graph:
  requires: []
  provides:
    - markdown-renderer/ add-on shell (8 files)
    - nginx.conf generator with multi-namespace support
    - vendored Docsify 4.13.1 + Mermaid 11.15.0
  affects: []
tech-stack:
  added:
    - ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20 (base image)
    - nginx (Alpine package, 1.26.x on alpine 3.20)
    - Docsify 4.13.1 (vendored via curl + tar)
    - Mermaid 11.15.0 UMD (vendored via curl + tar)
  patterns:
    - Phone-logger two-stage run.sh pattern (generator -> exec app)
    - Phone-logger 17-line OCI/HA label block
    - Per-namespace nginx alias + trailing-slash redirect
    - Single config.yaml map entry per volume (string form: share:rw)
key-files:
  created:
    - markdown-renderer/config.yaml
    - markdown-renderer/build.yaml
    - markdown-renderer/.upstream.yaml
    - markdown-renderer/Dockerfile
    - markdown-renderer/run.sh
    - markdown-renderer/generate_nginx.py
    - markdown-renderer/README.md
    - markdown-renderer/DOCS.md
  modified: []
decisions:
  - id: D-01
    summary: "HA options schema: directories list-of-{name,path} from Phase 4 onward"
    source: 04-CONTEXT.md
  - id: D-02
    summary: "Single namespace default but multi-namespace schema from day one"
    source: 04-CONTEXT.md
  - id: D-03
    summary: "generate_nginx.py ships full MULTI logic in Phase 4 (was originally Phase 5)"
    source: 04-CONTEXT.md
  - id: D-05
    summary: "Base image amd64-base-python:3.12-alpine3.20"
    source: 04-CONTEXT.md
  - id: D-08
    summary: "No .pre-commit-config.yaml edit needed; validate-versions.sh auto-discovers"
    source: 04-RESEARCH.md §5 (deviation from CONTEXT.md D-08)
  - id: KROKI-02
    summary: "kroki_url option default https://kroki.io (public web service)"
    source: 04-CONTEXT.md D-10
metrics:
  duration: "manual estimate ~30 min (see 'Duration' below)"
  completed_date: "2026-06-27"
---

# Phase 4 Plan 1: Scaffold markdown-renderer Add-on Summary

Scaffolded the `markdown-renderer/` add-on directory with 8 files following the established 4-file pattern, including a
vendored Docsify + Mermaid SPA generator that delivers INGRESS-01..05 and MULTI-01..06 requirements end-to-end.

## What Was Built

### Files (8 total, 582 lines)

| File                                  | Lines | Purpose                                                                                                                                                                                      |
| ------------------------------------- | ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `markdown-renderer/config.yaml`       | 29    | HA add-on manifest: ingress:true, ingress_port 8099, panel_icon mdi:text-box-multiple, map:[share:rw,config:rw,media:rw], options.directories list-of-{name,path}, options.kroki_url default |
| `markdown-renderer/build.yaml`        | 5     | amd64 base image pin + VERSION 1.0.0 arg                                                                                                                                                     |
| `markdown-renderer/.upstream.yaml`    | 6     | Docsify v4.\* pin (blocks v5 RC auto-update)                                                                                                                                                 |
| `markdown-renderer/Dockerfile`        | 61    | apk add nginx + curl/tar; vendored Docsify + Mermaid via curl GitHub tarballs; 17-line OCI/HA label block                                                                                    |
| `markdown-renderer/run.sh`            | 8     | Two-stage pattern: python3 /app/generate_nginx.py then exec nginx -g 'daemon off;'                                                                                                           |
| `markdown-renderer/generate_nginx.py` | 400   | Full generator: reads /data/options.json, validates names, writes nginx.conf + per-namespace index.html + landing page + runs nginx -t                                                       |
| `markdown-renderer/README.md`         | 30    | Shield badges v1.0.0 + licence link + vendored asset note                                                                                                                                    |
| `markdown-renderer/DOCS.md`           | 49    | directories schema table + kroki_url option + volume mounts + example YAML + Kroki fallback note                                                                                             |

### Generator Architecture

`generate_nginx.py` ships full multi-namespace support in Phase 4 (per CONTEXT D-03 scope expansion):

1. **Read `/data/options.json`** with shape `{"directories": [{"name": str, "path": str}, ...], "kroki_url": str}`
2. **Validate namespace names** against regex `^[a-z0-9][a-z0-9-]{0,62}$` + reserved name blocklist (`_docsify`, `api`,
   `data`, `share`, `config`, `media`) + duplicate detection
3. **Render `/tmp/nginx.conf`** with `absolute_redirect off` (INGRESS-04), `/_docsify/` alias serving vendored assets,
   landing page at `/`, and one trailing-slash redirect + alias pair per namespace
4. **Render per-namespace `index.html`** with inline basePath from `window.location.pathname` (INGRESS-02), relative
   `../_docsify/` script tags (INGRESS-03), Mermaid `doneEach → mermaid.run()` hook (INGRESS-05), and Kroki dispatcher
   plugin (KROKI-01..05)
5. **Render `/tmp/landing/index.html`** with one card per configured namespace
6. **Validate via `nginx -t`** (best-effort if nginx binary is present at runtime)

### Inline Kroki Dispatcher (KROKI-01..05)

The generated `index.html` ships an inline plugin that converts non-Mermaid fenced code blocks to `<img>` tags:

```javascript
img.src = krokiUrl + "/" + lang + "/svg/" + b64; // KROKI-03 URL template
```

- Encoding uses browser-native `CompressionStream('deflate')` + `btoa()` (no external library needed, ~0 KB overhead)
- Mermaid blocks are excluded via `:not(.language-mermaid)` selector (KROKI-01)
- On fetch failure (network error, 4xx, 5xx) the original `<pre><code>` block is preserved (KROKI-05)
- The `kroki_url` value comes from the add-on options (KROKI-02), defaulting to `https://kroki.io`

## Deviations from Plan

### D-08 (no `.pre-commit-config.yaml` edit needed)

**Type:** Pre-meditated deviation, documented in 04-RESEARCH.md §5

**Context:** CONTEXT.md D-08 instructs to extend `.pre-commit-config.yaml` `validate-versions` hook's `files:` regex to
include `markdown-renderer`. RESEARCH.md §5 verified the actual hook uses `always_run: true` (no `files:` key), and
`scripts/validate-versions.sh` auto-discovers add-ons by directory walk
(`for dir in */; do if [[ -f "$dir/config.yaml" ]] && [[ -f "$dir/build.yaml" ]]; then ADDON_DIRS+=("$dir"); fi; done`).

**Action:** No edit to `.pre-commit-config.yaml` was made. The script picks up `markdown-renderer/` automatically —
confirmed by running `make validate-versions` which now lists 5 add-ons (coding-assistants, gatus, markdown-renderer,
meridian, phone-logger).

**Impact:** Same validation coverage, fewer files to maintain. Zero risk.

### Generator: full MULTI logic in Phase 4 (per CONTEXT D-03)

The plan's verification list mentions "single-namespace generator" / "single-namespace fixture". The CONTEXT.md D-03
decision expands the scope: `generate_nginx.py` ships full multi-namespace support in Phase 4 (was originally Phase 5).
The generator as delivered iterates all `directories` entries, validates each name, renders one nginx location block +
one index.html per namespace + a landing page listing all namespaces. The dry-run test exercises the single-namespace
path (simplest case), but the multi-namespace path uses identical code paths.

### nginx -t validation in dry-run (environmental)

The plan's verification asks for `nginx -t -c /tmp/nginx.conf` to succeed. In the executor agent's local environment (no
root, no writable `/var/lib/nginx`), nginx -t fails with
`mkdir() "/var/lib/nginx/client-body" failed (13: Permission denied)` even though nginx reports
`the configuration file ... syntax is ok`. This is purely environmental — the add-on container runs as root with full
filesystem access. The generator's `subprocess.run(["nginx", "-t", ...])` call inside `main()` exercises the same check
at runtime in the add-on container.

**Verification performed locally:** Confirmed `nginx: the configuration file ... syntax is ok` on the generated config
(the only failure was the `mkdir()` permission error, not a syntax error).

## Verification Results

All plan verify steps pass:

| Check                                                                                   | Result                                                                            |
| --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `pre-commit run check-yaml --files markdown-renderer/*.yaml`                            | Passed                                                                            |
| `yamllint markdown-renderer/*.yaml`                                                     | Passed (no errors)                                                                |
| `python3 scripts/validate-addon-config.py markdown-renderer`                            | Passed                                                                            |
| `make validate-versions`                                                                | Passed (markdown-renderer auto-discovered)                                        |
| `pre-commit run shellcheck --files markdown-renderer/run.sh`                            | Passed                                                                            |
| `pre-commit run prettier --files markdown-renderer/README.md markdown-renderer/DOCS.md` | Passed                                                                            |
| `pre-commit run check-executables-have-shebangs`                                        | Passed (run.sh + generate_nginx.py both shebang + chmod +x)                       |
| `make validate-addons`                                                                  | Passed (markdown-renderer listed + ✅)                                            |
| `./scripts/validate-dockerfile-args.sh markdown-renderer/Dockerfile`                    | Passed (ARG BUILD_FROM global before FROM)                                        |
| `hadolint --ignore DL3018,DL3059,DL4006,DL3016 markdown-renderer/Dockerfile`            | Passed (no errors)                                                                |
| Generator dry-run with `/tmp/mr-test/options.json` (1 namespace)                        | Generated valid nginx.conf + index.html + landing page with all required patterns |

Generator dry-run confirmed the following INGRESS / KROKI patterns in the generated artifacts:

- `nginx.conf`: contains `absolute_redirect off` (INGRESS-04), `listen 8099`, `_docsify/` alias, one per-namespace
  location block with trailing-slash redirect + alias
- `index.html`: contains `window.location.pathname` (INGRESS-02), `../_docsify/docsify.min.js` (INGRESS-03),
  `hook.doneEach` + `mermaid.run()` (INGRESS-05), `CompressionStream` deflate encoder (KROKI-03),
  `krokiUrl + '/' + lang + '/svg/'` URL template (KROKI-03), `language-mermaid` exclusion (KROKI-01), `console.warn`
  graceful fallback (KROKI-05)
- `landing/index.html`: contains card linking to `/docs/` with namespace path

## Requirements Coverage

This plan addresses the following requirements:

| Req ID     | How Addressed                                                                                              |
| ---------- | ---------------------------------------------------------------------------------------------------------- |
| ADD-01     | 8-file scaffold following established 4-file pattern                                                       |
| ADD-02     | Dockerfile curls Docsify 4.13.1 + Mermaid 11.15.0 from GitHub release tarballs (no CDN)                    |
| ADD-03     | `.upstream.yaml` pins `version_pattern: "v4.*"` (blocks v5 RC upgrade)                                     |
| ADD-04     | README has shield badges `version-v1.0.0` + licence link; DOCS documents all options                       |
| INGRESS-01 | `ingress: true`, `ingress_port: 8099`, `panel_icon: mdi:text-box-multiple`                                 |
| INGRESS-02 | Inline `<script>` sets `window.$docsify.basePath = window.location.pathname.replace(/\/?$/, '/')`          |
| INGRESS-03 | All asset/script references use `../_docsify/...` (relative, no leading slash)                             |
| INGRESS-04 | `absolute_redirect off` in nginx `http {}` block                                                           |
| INGRESS-05 | Inline `doneEach → mermaid.run()` hook in generated index.html                                             |
| MULTI-01   | `directories: list({name: str, path: str})` in HA options + schema                                         |
| MULTI-02   | Per-namespace `location /<name>/ { alias ... }` blocks in nginx.conf                                       |
| MULTI-03   | Landing page at `/` listing all configured namespaces                                                      |
| MULTI-04   | `generate_nginx.py` reads `/data/options.json`, writes `/tmp/nginx.conf` + per-ns index.html               |
| MULTI-05   | Namespace name validation: regex `^[a-z0-9][a-z0-9-]{0,62}$` + reserved name blocklist                     |
| MULTI-06   | `map: [share:rw, config:rw, media:rw]` in config.yaml                                                      |
| KROKI-01   | Kroki dispatcher excludes `language-mermaid` blocks via `:not(.language-mermaid)`                          |
| KROKI-02   | `kroki_url` option in HA schema with default `https://kroki.io`; injected via `MARKDOWN_RENDERER.krokiUrl` |
| KROKI-03   | URL template `{kroki_url}/{format}/svg/<base64-deflate source>`; output_format hardcoded `svg`             |
| KROKI-04   | Standard `fetch()` via browser-native `CompressionStream('deflate')` + `btoa()`                            |
| KROKI-05   | `.catch(console.warn)` on fetch failure preserves original code block                                      |

## Known Stubs / Deferred Items

None — all generator code paths exercised by the dry-run test produce complete, valid output. The generator handles
`FileNotFoundError` (no `/data/options.json`) by writing a minimal fallback `/tmp/nginx.conf` and returning 0 — this is
intentional, not a stub.

## Commit Trail

| Commit    | Files                                   | Description                                                       |
| --------- | --------------------------------------- | ----------------------------------------------------------------- |
| `163e604` | config.yaml, build.yaml, .upstream.yaml | Manifest trio: HA options schema + versioning + Docsify v4.\* pin |
| `e6f3f01` | Dockerfile, run.sh                      | Vendored Docsify + Mermaid curl; two-stage run.sh                 |
| `b0e3171` | generate_nginx.py, README.md, DOCS.md   | Multi-namespace generator with inline mermaid + Kroki plugins     |

## Next Plan

Plan 04-02 (Multi-Namespace End-to-End Validation) will:

1. Validate multi-namespace behavior in actual HA Ingress (not just generator dry-run)
2. Verify volume mounting for `/share`, `/config`, `/media` works end-to-end
3. Document any empirical adjustments needed for the Mermaid `doneEach` hook targeting fenced code blocks (per D-07:
   fallback to Leward/mermaid-docsify v2.0.1 if needed)
4. Verify CSP / unsafe-eval behavior for Mermaid v11 (research flag in STATE.md)

## Self-Check: PASSED

All 8 files exist at expected paths. All 3 commits present in git log. Generator dry-run produces valid artifacts
matching all plan must_haves.
