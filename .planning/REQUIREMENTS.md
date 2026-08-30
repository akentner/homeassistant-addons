# Requirements: v1.1 markdown-renderer

**Milestone:** v1.1 markdown-renderer **Goal:** New `markdown-renderer` add-on serving multiple Markdown directories as
namespaced HTML endpoints via HA Ingress, with Mermaid diagram support and optional Git sync.

---

## Requirements

### ADD — Add-on Scaffold

- [ ] **ADD-01**: Add-on follows established 4-file pattern (config.yaml, build.yaml, Dockerfile, run.sh) plus
      .upstream.yaml, consistent with existing add-ons in the repo
- [ ] **ADD-02**: Docsify 4.13.1 and Mermaid 11.15.0 UMD build are vendored into the Docker image at build time via
      `curl`; no CDN requests at runtime
- [ ] **ADD-03**: `.upstream.yaml` pins version_pattern to `v4.*` to prevent auto-update to Docsify v5 RC
- [ ] **ADD-04**: README.md includes version shield badges; DOCS.md documents all config options with examples

### INGRESS — HA Ingress + Single Namespace

- [ ] **INGRESS-01**: Add-on exposes a Docsify SPA via HA Ingress with a panel entry in the HA sidebar (`ingress: true`,
      `panel_icon: mdi:text-box-multiple`)
- [ ] **INGRESS-02**: Docsify `basePath` is set to `window.location.pathname` in generated `index.html` (never a static
      absolute path) so HA Ingress routing works correctly for all `.md` file fetches
- [ ] **INGRESS-03**: All static assets (Docsify JS, Mermaid JS, CSS) are referenced with relative paths in generated
      HTML (e.g., `../_docsify/docsify.min.js`); no absolute `/`-prefixed paths
- [ ] **INGRESS-04**: Per-namespace trailing-slash redirect (`location = /ns { return 301 /ns/; }`) and
      `absolute_redirect off` in nginx server block prevent broken `window.location.pathname` values
- [ ] **INGRESS-05**: Mermaid UMD diagrams in fenced code blocks (` ```mermaid `) render correctly inside Docsify via
      inline `doneEach` lifecycle hook calling `mermaid.run()`

### MULTI — Multi-Namespace Routing

- [x] **MULTI-01**: User configures multiple directories as a list of objects in HA options; each object has `name`
      (URI-safe string) and `path` (absolute path inside the container)
- [x] **MULTI-02**: Each configured directory is served as an independent Docsify SPA under `/name/` via nginx;
      namespaces are isolated (separate index.html, separate markdown root)
- [x] **MULTI-03**: Landing page at the Ingress root (`/`) lists all configured namespaces as clickable cards with name
      and path; generated at startup from config
- [x] **MULTI-04**: `generate_nginx.py` reads `/data/options.json` at startup and generates `/tmp/nginx.conf` +
      per-namespace `/tmp/docroots/{name}/index.html`; run.sh invokes it before starting nginx
- [x] **MULTI-05**: Namespace name validation rejects names that are empty, non-URI-safe, or conflict with reserved
      nginx locations (`_docsify`, `api`)
- [x] **MULTI-06**: Paths from `/share`, `/config`, and `/media` are supported as namespace directory sources;
      config.yaml `map:` includes `share:rw`, `config:rw`, `media:rw`

### KROKI — Kroki Diagram Service

- [ ] **KROKI-01**: Add-on supports any diagram format that Kroki supports (PlantUML, Mermaid, GraphViz, etc.) via
      fenced code blocks (` ```plantuml `, ` ```dot `, ` ```blockdiag `, etc.) in addition to inline Mermaid
- [ ] **KROKI-02**: HA options schema exposes a `kroki_url` string option with default `"https://kroki.io"` (the public
      Kroki web service); users can override to point at a self-hosted Kroki instance or compatible service
- [ ] **KROKI-03**: A fenced code block whose language identifier is not `mermaid` is rendered as an `<img>` tag whose
      `src` points at `{kroki_url}/{format}/{output_format}/<base64-encoded diagram source>` (Kroki's URL scheme);
      default output_format is `svg`
- [ ] **KROKI-04**: Diagram rendering happens at page-load time via Docsify `doneEach` lifecycle hook; the rendered
      `<img>` tags replace the raw `<pre><code>` blocks in the DOM after Docsify has rendered the markdown
- [ ] **KROKI-05**: If the Kroki service is unreachable for a specific diagram, the original code block remains visible
      (graceful degradation); errors are logged to the browser console but do not break the Docsify SPA

### GIT — Git Integration

- [x] **GIT-01**: Each namespace entry supports an optional `git_pull: bool` flag; when true, run.sh executes
      `git pull --ff-only` on the directory at startup before nginx starts
- [x] **GIT-02**: `git config --global --add safe.directory '*'` is executed in run.sh before any git operation to
      handle mounted volume UID mismatch (git 2.35.2+ requirement)
- [x] **GIT-03**: Namespaces without `git_pull: true` are served without any git operations; git integration is fully
      optional per namespace
- [x] **GIT-04**: Each namespace supports a `git_pull_interval: int` option (seconds, 0 = disabled) for periodic
      background git pull; run.sh spawns a background loop when interval > 0
- [x] **GIT-05**: Startup is not blocked if a git directory is unreachable; git pull errors are logged but do not
      prevent the namespace from being served

### CI — CI/CD Hardening (v1.2, Phase 8)

<!-- Added 2026-08-30 from the GitHub Actions audit. All runs were green; these are the defects that a green run-status
     column cannot show — one fails silently, one has no failure mode until it triggers, one is only a warning. -->

- [x] **CI-01**: Every job in every workflow declares an explicit `timeout-minutes`; no job relies on GitHub's
      360-minute default. The number of declarations equals the number of jobs (currently 6)
- [x] **CI-02**: The add-on build job is bounded such that a hung aarch64 QEMU leg cannot consume a 6-hour runner block;
      the cap is derived from the measured 13m28s emulated build, not guessed
- [x] **CI-03**: No action in any workflow targets the deprecated Node 20 runtime; the "Node.js 20 is deprecated"
      annotation no longer appears on build runs — closed by `grep -c 'Node.js 20 is deprecated'` returning `0` on
      the verification build (`gh run view 33319080212`, amd64 3m54s + aarch64 11m1s, both `success`)
- [x] **CI-04**: `actions/checkout` sits at one single major version across every workflow that uses it (no v4/v6/v7
      split) — closed by `grep -rh 'actions/checkout@' .github/workflows/ | sort -u` returning exactly one unique line
      (`actions/checkout@v7`), 5 occurrences total
- [ ] **CI-05**: Home Assistant receives and observably processes the `started` notification for a real add-on build —
      the receiving automation's `last_triggered` advances, since HA returns 200 for any webhook ID whether registered or
      not
- [ ] **CI-06**: Home Assistant receives the `finished` notification carrying `conclusion` and `image_tag`
- [ ] **CI-07**: The webhook path remains protected; an unauthenticated POST from the public internet is still
      redirected to the Cloudflare Access login and does not reach HA
- [ ] **CI-08**: A notification failure can never fail a build, but it is reported actionably — a `3xx` fails fast naming
      the Access policy instead of three identical retries against a non-transient condition
- [x] **CI-09**: No document references the removed `.github/workflows/build.yml`; the build trigger and the
      `<addon>/v<version>` tag schema are described as they actually are, and no doc advertises a capability the code
      lacks
- [x] **CI-10**: The per-add-on tag-trigger state is documented with its rationale, so the in-workflow comment pointing
      at `.github/RELEASE.md` resolves to a real explanation

---

## Future Requirements

<!-- Deferred — revisit in v1.2 -->

- SSH key handling for private git repos (HTTPS-only repos in v1.1; credential-free pull only)
- HA Camera Entity image proxying with hash-based cache expiry (`homeassistant_api`)
- Web editor / in-browser Markdown editing
- PDF export
- Multi-arch builds (arm64, armv7)
- Periodic git sync via external webhook trigger
- Per-namespace Docsify theme customization

---

## Out of Scope

<!-- Explicit exclusions with reasoning -->

- **SSH credentials for private repos** — Handling SSH keys in a personal add-on adds complexity and security surface
  without clear need; HTTPS public repos cover the primary use case for v1.1
- **Web editor** — Read-only viewer first; editing Markdown in the browser requires backend write access and conflict
  handling
- **PDF export** — HTML rendering is the stated goal; PDF adds Pandoc/Weasyprint and build latency
- **Multi-arch** — Both HA hosts are x86_64; consistent with all existing add-ons in this repo
- **HA state integration** — Camera entities, sensor values, entity state in Markdown deferred to v1.2; requires
  `homeassistant_api` proxying

---

## Traceability

| REQ-ID     | Phase                                     | Plan                                                                                                                |
| ---------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| ADD-01     | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| ADD-02     | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| ADD-03     | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| ADD-04     | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| INGRESS-01 | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| INGRESS-02 | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| INGRESS-03 | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| INGRESS-04 | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| INGRESS-05 | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| MULTI-01   | Phase 5: Multi-Namespace + Dynamic Config | —                                                                                                                   |
| MULTI-02   | Phase 5: Multi-Namespace + Dynamic Config | —                                                                                                                   |
| MULTI-03   | Phase 5: Multi-Namespace + Dynamic Config | —                                                                                                                   |
| MULTI-04   | Phase 5: Multi-Namespace + Dynamic Config | —                                                                                                                   |
| MULTI-05   | Phase 5: Multi-Namespace + Dynamic Config | —                                                                                                                   |
| MULTI-06   | Phase 5: Multi-Namespace + Dynamic Config | —                                                                                                                   |
| KROKI-01   | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| KROKI-02   | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| KROKI-03   | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| KROKI-04   | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| KROKI-05   | Phase 4: Scaffold + Ingress Validation    | —                                                                                                                   |
| GIT-01     | Phase 6: Git Integration                  | 06-02 (empirical: verify-git-integration.sh Scenario A, 18 assertions)                                              |
| GIT-02     | Phase 6: Git Integration                  | 06-02 (empirical: verify-git-integration.sh Scenario A — `git config --global` ran at startup)                      |
| GIT-03     | Phase 6: Git Integration                  | 06-02 (empirical: verify-git-integration.sh Scenario C — no git pull/clone in logs)                                 |
| GIT-04     | Phase 6: Git Integration                  | 06-02 (empirical: verify-git-integration.sh Scenario D — 4 git pull invocations during 15s window)                  |
| GIT-05     | Phase 6: Git Integration                  | 06-02 (empirical: verify-git-integration.sh Scenario B — unreachable URL, WARNING in logs, container stays running) |
| CI-01      | Phase 8: CI/CD Hardening                  | 08-01 (Tasks 1-3: 6 caps across 5 workflow files; invariant = declarations equal job count)                          |
| CI-02      | Phase 8: CI/CD Hardening                  | 08-01 (Task 1: build job capped at 45 min, derived from the measured 13m28s aarch64 leg)                             |
| CI-03      | Phase 8: CI/CD Hardening                  | 08-02 (Task 1 + Task 3: 4 Docker actions bumped; verified by absence of the Node 20 annotation on a real build)      |
| CI-04      | Phase 8: CI/CD Hardening                  | 08-02 (Task 2: all 5 `actions/checkout` references unified on one major)                                             |
| CI-05      | Phase 8: CI/CD Hardening                  | 08-05 (gap-closure — Task 5 #4: HA-side `last_triggered` advances; 08-03 partial covered Tasks 2-4 only)            |
| CI-06      | Phase 8: CI/CD Hardening                  | 08-05 (gap-closure — Task 5 #5: end-to-end build log shows two `HA notification OK` notices and zero 302 warnings) |
| CI-07      | Phase 8: CI/CD Hardening                  | 08-03 partial (Task 5 #2 negative edge probe PASSED — HTTP 302 to Access login); 08-05 Task 5 #4 re-confirms         |
| CI-08      | Phase 8: CI/CD Hardening                  | 08-03 partial (Task 2 script logic in place — `^3` branch precedes `LAST_ERR`, no `-L`, always `exit 0`)           |
| CI-09      | Phase 8: CI/CD Hardening                  | 08-04 (Tasks 1-2: 9 drift instances incl. the false `HA_WEBHOOK_SECRET` capability claim)                            |
| CI-10      | Phase 8: CI/CD Hardening                  | 08-04 (Task 3: per-add-on tag-trigger table + rationale from 287c79f / 60e7835)                                      |

---

_Last updated: 2026-08-30 — CI-01..CI-10 added for v1.2 Phase 8 (CI/CD Hardening); CI-01/02/03/04/09/10 closed, CI-05/06/07/08 deferred to gap-closure plan 08-05 (Cloudflare Access setup + verification probes blocked on user action)_
