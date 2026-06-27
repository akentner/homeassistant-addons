# Home Assistant Add-on: Markdown Renderer

[![Release][release-shield]][release] [![License][license-shield]][license]

Renders Markdown directories as Docsify SPAs via Home Assistant Ingress with Mermaid diagram support. Vendored Docsify
and Mermaid - no CDN requests at runtime.

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

<!-- Badge Links -->

[release-shield]: https://img.shields.io/badge/version-v1.0.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v1.0.0
[license-shield]: https://img.shields.io/badge/license-MIT-green.svg
[license]: https://github.com/akentner/homeassistant-addons/blob/main/LICENSE
