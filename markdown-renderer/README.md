# Home Assistant Add-on: Markdown Renderer

[![Release][release-shield]][release] [![License][license-shield]][license]

Renders Markdown directories as Docsify SPAs via Home Assistant Ingress with Mermaid diagram support. Vendored Docsify
and Mermaid - no CDN requests at runtime. Multiple namespaces can be configured and are served as isolated Docsify SPAs
under separate URLs. - Verification status: see Verification section below

## Configuration

See [`DOCS.md`](DOCS.md) for the full configuration reference including the `directories` list-of-objects schema and the
`kroki_url` option.

## Vendored Assets

Both Docsify `4.13.1` and Mermaid `11.15.0` UMD are fetched at build time via `curl` from GitHub release tarballs and
vendored into `/app/_docsify/`. The generated `index.html` references them via relative paths
(`../_docsify/docsify.min.js`) so they resolve correctly under HA Ingress without depending on any external CDN at
runtime.

## Upstream

This add-on tracks [docsifyjs/docsify](https://github.com/docsifyjs/docsify) pinned to the `v4.*` version pattern so v5
release-candidates are never auto-applied.

## Verification

The add-on has been validated by:

- `make check-all` (lint + validate-addons + validate-versions + validate-dockerfiles)
- Local Docker build via `make build-addon ADDON=markdown-renderer` produces `local/markdown-renderer:1.0.0`
- Generator dry-run with single-namespace + multi-namespace fixtures passes `nginx -t -c /tmp/nginx.conf`

### Manual HA Ingress Test Checklist

Phase 4 success criteria require empirical verification in Home Assistant. To confirm:

1. **Ingress panel** - Install add-on, open Settings > Devices & Services > Markdown Renderer. Panel icon
   `mdi:text-box-multiple` is visible in HA sidebar.
2. **Single namespace renders** - Configure `directories: [{name: docs, path: /share/docs}]` in the add-on options. Put
   a `README.md` in `/share/docs/` on the HA host. Open the panel; the Docsify SPA loads without browser console errors;
   README.md renders as HTML.
3. **Mermaid diagrams** - Add a fenced ` ```mermaid ` block to a .md file. Open the page; the block renders as inline
   SVG (not as code text).
4. **No CDN requests** - Open browser DevTools Network tab; verify all `.js` and `.css` requests resolve to relative
   paths under the Ingress URL (e.g., `../_docsify/docsify.min.js`). Zero requests to `cdn.jsdelivr.net`, `unpkg.com`,
   or any other external host. Note: requests to `kroki.io` are EXPECTED for non-Mermaid diagram blocks (PlantUML,
   GraphViz, etc.) and confirm the Kroki dispatcher is working.
5. **Auto-update pin** - Inspect .upstream.yaml; confirm `version_pattern: "v4.*"`. Verify the next daily auto-update
   run does not propose a Docsify v5 RC upgrade.
6. **Kroki diagram render** - Add a fenced ` ```plantuml ` block (or `dot`, `blockdiag`, etc.) to a .md file. Open the
   page; the block is replaced by an `<img>` tag whose `src` starts with `https://kroki.io/plantuml/svg/` (or the
   format-appropriate path). If Kroki is unreachable, the original code block remains visible and the browser console
   logs a `Kroki render failed` warning (KROKI-05 graceful fallback).
7. **Kroki URL override** - Change `kroki_url` in the add-on options to a self-hosted Kroki instance URL (e.g.,
   `http://192.168.1.100:8000`). Restart the add-on. Re-load a page with a PlantUML block; the `<img>` `src` now points
   at the custom URL.
8. **Multi-namespace landing page** - Configure two or more directories in the add-on options (e.g. docs and runbooks).
   Open the Markdown Renderer panel; the landing page at the Ingress root shows two clickable cards. Click each card and
   confirm the corresponding Docsify SPA loads. Restart the add-on with a different `directories:` list; the landing
   page regenerates with the new set of cards (no caching).
9. **Invalid namespace name rejected** - Configure a `directories:` entry with a name like `bad/name` (contains `/`) or
   `Docs` (uppercase) or `_docsify` (reserved). Restart the add-on. The HA Supervisor log shows the clear error
   `ERROR: namespace name '...' ...` and the add-on does not start. Fix the name and the add-on starts normally.
10. **Volume mounts serve files** - Place a `README.md` file in each of `/share/docs/`, `/config/runbooks/`, and
    `/media/photos/` on the HA host. Configure three corresponding namespaces. Confirm each namespace renders its
    respective `README.md` content (Docsify reads `.md` files from the configured path via the mounted volume).

<!-- Badge Links -->

[release-shield]: https://img.shields.io/badge/version-v1.1.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v1.1.0
[license-shield]: https://img.shields.io/badge/license-MIT-green.svg
[license]: https://github.com/akentner/homeassistant-addons/blob/main/LICENSE
