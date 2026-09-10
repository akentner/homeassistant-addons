# Phase 4: Scaffold + Ingress Validation - Context

**Gathered:** 2026-06-27 **Status:** Ready for planning

<domain>
## Phase Boundary

Build the complete `markdown-renderer/` add-on following the established 4-file pattern and validate a single Docsify
namespace end-to-end through HA Ingress. Vendored assets (Docsify 4.13.1, Mermaid 11.15.0 UMD) load without CDN
requests. Mermaid diagrams render via `doneEach` lifecycle hook.

**Scope expansion decision:** Phase 4 also delivers the full `generate_nginx.py` implementation including
multi-namespace support, landing page, and namespace validation (originally MULTI-01..06 in Phase 5). Phase 5 becomes
end-to-end multi-namespace validation in HA + volume mounting verification (share/config/media mounts).

</domain>

<decisions>
## Implementation Decisions

### Config Schema

- **D-01:** HA options schema uses `directories: list({name: string, path: string})` from Phase 4 onward. No migration
  needed between phases. Git fields (`git_pull`, `git_pull_interval`) are added to each entry in Phase 6.
- **D-02:** Phase 4 validates with a single namespace entry; the schema supports multiple entries from day one.

### generate_nginx.py Scope

- **D-03:** `generate_nginx.py` is introduced in Phase 4 with **full MULTI logic**: reads `/data/options.json`, iterates
  `directories` list, generates `/tmp/nginx.conf` and per-namespace `/tmp/docroots/{name}/index.html`, plus landing page
  at `/` listing all namespaces. Namespace name validation (empty, non-URI-safe, conflicts with `_docsify`/`api`) is
  also included in Phase 4.
- **D-04:** `run.sh` invokes `generate_nginx.py` before starting nginx — same two-stage pattern as phone-logger
  (`generate_config.py` then `exec` app).

### Base Image

- **D-05:** Base image: `ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20` — consistent with phone-logger.
  `nginx` installed via `apk add --no-cache nginx`. No separate Python installation needed.

### Mermaid Integration

- **D-06:** Primary approach: `doneEach` lifecycle hook calling `mermaid.run()` (per INGRESS-05). This is the planned
  implementation.
- **D-07:** Fallback documented in plan: if empirical HA Ingress testing shows `mermaid.run()` in `doneEach` fails to
  target fenced code blocks correctly, fall back to vendoring `Leward/mermaid-docsify` v2.0.1 as an additional asset
  (extra `curl` in Dockerfile). Fallback is a plan note, not a parallel implementation.

### Pre-commit / CI Extension

- **D-08:** The `validate-versions` hook's `files:` pattern in `.pre-commit-config.yaml` is extended to include
  `markdown-renderer` alongside existing add-ons. CI extension is part of Phase 4 (per ADD-01 "consistent with existing
  add-ons" implies validation tooling covers the new add-on).

### Kroki Integration

- **D-09:** Kroki support is added in Phase 4 via a single Docsify `doneEach` plugin that dispatches on the fenced code
  block's language identifier. Mermaid (`mermaid`) continues to render client-side via `mermaid.run()` (per D-06); all
  other formats are sent to the Kroki URL as `<img>` tags. This keeps Mermaid offline-capable while extending coverage
  to the full Kroki format set (PlantUML, GraphViz, BlockDiag, D2, Excalidraw, etc.).
- **D-10:** The Kroki URL is a single string option `kroki_url` in the HA options schema, default `"https://kroki.io"`.
  No per-namespace override, no URL allowlist, no authentication header support in Phase 4 (deferred). Users running a
  self-hosted Kroki (e.g., as another HA add-on) point `kroki_url` at it.
- **D-11:** The Kroki URL scheme is `{kroki_url}/{format}/{output_format}/<base64-encoded diagram source>`. Phase 4
  hardcodes `output_format = "svg"` (per KROKI-03). Format identifier is taken directly from the fenced code block's
  language tag (e.g., ` ```plantuml ` → format `plantuml`). Encoding is `deflate + base64` per the Kroki HTTP API spec
  (zlib-compressed source, then standard base64).
- **D-12:** Kroki requests use the standard `fetch()` API with no caching. If a request fails (network error, 4xx, 5xx)
  the original `<pre><code>` block is preserved (KROKI-05). No retry logic, no offline cache, no pre-rendering — those
  are future enhancements. This matches the existing Phase 4 philosophy of "minimal viable + documented fallback".

### Claude's Discretion

- Exact nginx.conf template structure (server block details beyond what INGRESS-04 specifies)
- Which specific fenced code-block languages to support beyond Mermaid (the default is "anything that isn't `mermaid`
  goes to Kroki"; explicit list deferred to research)
- `_docsify/` vendored asset directory naming and placement within nginx root
- `build.yaml` base image version tag (use current latest `alpine3.20` variant)
- `DOCS.md` structure and configuration option descriptions
- `repository.yaml` entry for the new add-on (check auto-discovery vs. explicit registration)

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements

- `.planning/REQUIREMENTS.md` §ADD, §INGRESS — ADD-01..04, INGRESS-01..05 are the Phase 4 acceptance criteria
- `.planning/REQUIREMENTS.md` §MULTI — MULTI-01..06 are also in Phase 4 scope (generate_nginx.py full logic)

### Existing Add-on Patterns (read before writing any file)

- `phone-logger/Dockerfile` — reference for GitHub tarball download pattern + `amd64-base-python` base image
- `phone-logger/generate_config.py` — canonical pattern for Python config generation from `/data/options.json`
- `phone-logger/run.sh` — two-stage pattern: Python config gen → exec app
- `fritz-callmonitor2mqtt/Dockerfile` — reference for ARG/ENV pattern, standard label block
- `fritz-callmonitor2mqtt/config.yaml` — reference for config.yaml schema and options section structure
- `fritz-callmonitor2mqtt/build.yaml` — reference for build.yaml format
- `fritz-callmonitor2mqtt/.upstream.yaml` — canonical `.upstream.yaml` structure
- `meridian/Dockerfile` — recent example (bun+node stages); note: markdown-renderer does NOT use this multi-stage
  pattern — single stage with Python base is the right model

### Versioning + CI Tooling

- `scripts/validate-versions.sh` — must cover `markdown-renderer` after `.pre-commit-config.yaml` update (D-08)
- `.pre-commit-config.yaml` — `files:` pattern in validate-versions hook must include `markdown-renderer`

### Conventions

- `.planning/codebase/CONVENTIONS.md` — versioning rules (3-file scheme), Dockerfile label block, YAML quoting,
  snake_case config options, shell script shebang conventions

### Phase Context

- `.planning/phases/03-meridian-add-on/03-CONTEXT.md` — D-15 shows the pre-commit pattern update needed; D-16 shows
  hadolint ignore-rule pattern; both apply to markdown-renderer as well

</canonical_refs>

<code_context>

## Existing Code Insights

### Reusable Patterns

- **GitHub tarball fetch** (`phone-logger/Dockerfile`):
  `curl -fsSL "https://github.com/owner/repo/archive/refs/tags/v${VERSION}.tar.gz" | tar xz --strip-components=1` — copy
  directly for Docsify asset download pattern
- **Python config generation** (`phone-logger/generate_config.py`): module docstring, type hints, `pathlib.Path`,
  `if __name__ == '__main__': sys.exit(main())` guard — copy this structure for `generate_nginx.py`
- **Two-stage run.sh** (`phone-logger/run.sh`): invoke Python script → exec app; same pattern for generate_nginx.py →
  exec nginx
- **Standard label block** (both Dockerfiles): OCI + HA labels at bottom using `ARG`-injected values — copy as-is
- **Pre-commit files pattern update** (from Phase 3 CONTEXT D-15):
  `files: ^(fritz-callmonitor2mqtt|phone-logger|meridian)/(config\.yaml|build\.yaml|README\.md)$` → extend with
  `|markdown-renderer`

### Integration Points

- `scripts/validate-versions.sh` — find-based, auto-discovers add-ons; the pre-commit `files:` trigger is the only thing
  that needs updating (not the script itself)
- `Makefile` `validate-addons` target — verify it picks up the new `markdown-renderer/` directory automatically
- `repository.yaml` — verify whether HA auto-discovers add-ons by directory scan or needs explicit entry

</code_context>

<specifics>
## Specific Ideas

- User confirmed: `directories` list-of-objects is the right schema from day one — no migration between phases
- User confirmed: generate_nginx.py delivers full MULTI capability in Phase 4; Phase 5 is validation-only
- User confirmed: doneEach Hook is the primary Mermaid approach; Leward plugin is documented fallback only

</specifics>

<deferred>
## Deferred Ideas

- Git fields (`git_pull`, `git_pull_interval`) in options schema — Phase 6 adds these to each namespace entry
- SSH key handling for private git repos — Future (v1.2)
- Per-namespace Docsify theme customization — Future (v1.2)
- Multi-arch builds — Out of scope (all hosts x86_64)

</deferred>

---

_Phase: 04-scaffold-ingress-validation_ _Context gathered: 2026-06-27_
