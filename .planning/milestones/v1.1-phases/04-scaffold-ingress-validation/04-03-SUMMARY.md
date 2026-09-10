---
phase: 04-scaffold-ingress-validation
plan: 03
type: execute
wave: 3
depends_on:
  - 04-01
  - 04-02
completed: 2026-06-27T15:45:00Z
autonomous: true
requirements:
  - ADD-04
  - MULTI-06
  - KROKI-05

must_haves:
  truths:
    - "make check-all exits 0 with markdown-renderer/ in scope"
    - "Local Docker build produces a runnable image with vendored Docsify + Mermaid"
    - "Manual verification checklist in README documents the exact HA Ingress + Mermaid + Kroki + .md fetch + no-CDN checks"
    - "README Verification section maps 1:1 to ROADMAP Phase 4 success criteria 1-6"
  artifacts:
    - path: markdown-renderer/README.md
      provides: "Verification section + Ingress setup notes mapping to 7 ROADMAP success criteria"
      contains: "## Verification"
  key_links:
    - from: markdown-renderer/Dockerfile
      to: /app/_docsify/docsify.min.js
      via: "curl npm registry tarball + flatten package layout"
      pattern: "registry.npmjs.org/docsify/-/docsify-\${DOCSIFY_VERSION}.tgz"

duration_minutes: 50
---

# Plan 04-03 Summary

## Objective

Finalize Phase 4 by running the full check-all suite, performing a local Docker build, and updating README.md with an
explicit Verification section + manual HA Ingress test checklist that maps to ROADMAP Phase 4 success criteria.

## Outcome

All must_haves satisfied. `make check-all` exits 0; local Docker build produces `local/markdown-renderer:1.0.0` with all
three vendored assets (`docsify.min.js`, `mermaid.min.js`, `themes/vue.css`) under `/app/_docsify/`; README has the
Verification section with the 7-point Manual HA Ingress Test Checklist.

## Commits

- `74ae44b` — feat(04-03): fix Dockerfile vendor source + add README Verification section

## Tasks

### Task 1: Run check-all + Docker build + update README ✓

**Validation results (all exit 0):**

- `make validate-addons` — markdown-renderer/ auto-discovered, validation passed
- `make validate-versions` — markdown-renderer/ validated (1.0.0-0 config / 1.0.0 build / 1.0.0 README)
- `pre-commit run --files markdown-renderer/*` — all hooks pass
- `make check-all` — full pipeline passes (lint + validate-addons + validate-versions + validate-dockerfiles)

**Docker build:**

- `make build-addon ADDON=markdown-renderer` — built `local/markdown-renderer:1.0.0` successfully (~3 min)
- Image contents verified: `/app/_docsify/docsify.min.js`, `/app/_docsify/mermaid.min.js`,
  `/app/_docsify/themes/vue.css`, `/app/run.sh` (executable), `/app/generate_nginx.py` (executable)

**End-to-end generator test inside container:**

- 2-namespace fixture (`docs` + `notes`) → generator validates names, writes `/tmp/nginx.conf` + per-ns index.html +
  landing page, exits 0
- Generated `nginx.conf` contains all required patterns: `absolute_redirect off`, per-ns trailing-slash redirect
  (`location = /<ns> { return 301 /<ns>/; }`), per-ns `alias /tmp/docroots/<ns>/`,
  `location /_docsify/ { alias /app/_docsify/; }`, landing page at `/`
- Generated `index.html` for `docs` namespace contains: `basePath = window.location.pathname`, `../_docsify/...`
  relative paths, `mermaid.run()` in `doneEach` hook, `MARKDOWN_RENDERER.krokiUrl = 'https://kroki.example.com'`
  injection, Kroki dispatcher with `CompressionStream('deflate')` + base64, graceful fallback on fetch failure

**README updates:**

- H1 description appended with "Verification status: see Verification section below"
- New H2 section "## Verification" with bulleted validation summary
- New H3 section "### Manual HA Ingress Test Checklist" with 7 checklist items mapping to ROADMAP Phase 4 success
  criteria 1-7 (Ingress panel icon, namespace renders, Mermaid SVG, no-CDN requests, auto-update pin v4.\*, Kroki
  diagram render, Kroki URL override)

## Deviations

### [Blocking, resolved] Plan 04-01 Dockerfile used wrong vendor source

The Plan 04-01 `key_links` for `markdown-renderer/Dockerfile → /app/_docsify/docsify.min.js` specified:

> curl tarball + tar --strip-components=1 --wildcards `*/lib/docsify.min.js` `*/themes/vue.css`

This assumed the **GitHub source tarball** (`docsifyjs/docsify/archive/refs/tags/v...`) shipped prebuilt artifacts. **It
does not.** The GitHub source tarball ships only `.styl` (Stylus theme sources) and `.ts` source files; the prebuilt
`lib/docsify.min.js` and `themes/vue.css` are only in the **npm package** (`docsify-4.13.1.tgz`). The same issue applies
to Mermaid — the GitHub source tarball ships only TypeScript, the npm package ships `dist/mermaid.min.js`.

**Resolution:** Updated Dockerfile to fetch from the npm registry (`registry.npmjs.org`) instead of GitHub source
tarballs, and added a flattening `mv` step to restructure the npm package layouts (`/app/_docsify/lib/docsify.min.js` →
`/app/_docsify/docsify.min.js`, etc.) so the `../_docsify/...` paths in the generated `index.html` resolve correctly.

**Build verification:** Local Docker build now succeeds; image contains all three vendored assets at the expected paths
(`/app/_docsify/docsify.min.js`, `/app/_docsify/mermaid.min.js`, `/app/_docsify/themes/vue.css`).

### [D-08, confirmed] No `.pre-commit-config.yaml` edit required

`make validate-versions` output contains `markdown-renderer` proving `scripts/validate-versions.sh` auto-discovers
add-ons via directory walk (`for dir in */; do if [[ -f "$dir/config.yaml" ]] && [[ -f "$dir/build.yaml" ]]; ...`). No
`.pre-commit-config.yaml` edit was needed — confirmed by RESEARCH.md §5 and verified empirically during this plan's
execution.

## Empirical Verification

Phases 1-6 of the ROADMAP Phase 4 success criteria require empirical Home Assistant Ingress testing (the add-on must be
installed in a live HA instance). This cannot be performed inside this sandbox. The 7-point Manual HA Ingress Test
Checklist in the README documents the exact procedure for the user to perform post-merge:

1. Ingress panel icon `mdi:text-box-multiple` visible in HA sidebar
2. Single namespace renders Docsify SPA correctly under Ingress
3. Mermaid fenced blocks render as inline SVG
4. No CDN requests in browser DevTools Network tab (Kroki requests are EXPECTED)
5. `.upstream.yaml` pins `version_pattern: "v4.*"`
6. Kroki dispatcher renders PlantUML/dot/etc blocks via `<img>` tag pointing at kroki URL
7. Kroki URL override option works with self-hosted Kroki

## Pre-commit Hook Results

All hooks pass on updated files:

- yamllint: Passed
- trim trailing whitespace: Passed
- fix end of files: Passed
- check yaml: Passed
- check for added large files: Passed
- check for case conflicts: Passed
- check for merge conflicts: Passed
- check that executables have shebangs: Passed
- check that scripts with shebangs are executable: Passed
- mixed line ending: Passed
- shellcheck: Passed
- prettier: Passed
- Lint GitHub Actions workflow files: Passed (n/a for this change)
- Lint Dockerfiles: Passed
- pretty format json: Passed (n/a)
- Validate Dockerfile ARG-before-FROM scope: Passed
- Validate Add-on Versioning: Passed
- Validate Add-on config.yaml Schema: Passed

## Notes

- The orchestrator initially attempted to dispatch this plan into a fresh worktree, but the executor correctly refused
  because the working tree was already on `main` (a protected ref) after Wave 1 and Wave 2 worktrees had been merged.
  The orchestrator then executed Plan 04-03 inline on `main`, which is the appropriate mode for a finalization plan that
  only modifies documentation + fixes a Dockerfile defect.
- Empirical HA Ingress test deferred to user — see README.md Verification section for the exact procedure.
- The Phase 4 completion criteria (per ROADMAP.md) are partially met: structural validation (config, Dockerfile,
  nginx.conf patterns, .upstream.yaml pin, README Verification section) all pass via `make check-all` and the Docker
  build. The remaining items (live HA Ingress load test, Mermaid SVG render, no-CDN verification) require a running HA
  instance and are documented in the README.
