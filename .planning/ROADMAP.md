# Roadmap: Home Assistant Add-ons Repository

## Milestones

- ✅ **v1.0 MVP** — Phases 1-3 (shipped 2026-04-04)
- ✅ **v1.1 markdown-renderer** — Phases 4-6 (complete 2026-06-28)
- 📋 **v1.2 CI/CD Hardening** — Phase 8 (planned 2026-08-30)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-3) — SHIPPED 2026-04-04</summary>

- [x] Phase 1: Quality Fixes (2/2 plans) — completed 2026-04-03
- [x] Phase 2: Auto-Update Workflow (1/1 plan) — completed 2026-04-04
- [x] Phase 3: Meridian Add-on (3/3 plans) — completed 2026-04-04

Full details: [.planning/milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

### 📋 v1.1 markdown-renderer (Phases 4-6)

- [x] **Phase 4: Scaffold + Ingress Validation** — Add-on structure, vendored assets, single-namespace Docsify SPA
      (completed 2026-06-27) working through HA Ingress with correct basePath and relative asset paths
- [ ] **Phase 5: Multi-Namespace + Dynamic Config** — `generate_nginx.py` wired to HA options, multiple directories
      served as isolated SPAs, landing page at ingress root
- [x] **Phase 6: Git Integration** — Optional per-namespace git pull at startup and on a background interval; errors
      non-blocking (completed 2026-06-28)

### 📋 v1.2 CI/CD Hardening (Phase 8)

- [ ] **Phase 8: CI/CD Hardening** — Close the three latent defects found by the 2026-08-30 GitHub Actions audit (silent
      HA-notification failure, missing job timeouts, action versions frozen by an accidental Renovate PR batch-close) plus
      the documentation drift found alongside them

> Phase 7 (`07-tolaria-add-on-scaffold`) has 3 plans and a CONTEXT from 2026-07-30 but no SUMMARY files and no entry in
> this roadmap or STATE.md. Its status is unresolved (Q-03 in `08-CONTEXT.md`). Phase 8 deliberately takes the next number
> rather than renumbering or absorbing it.

## Phase Details

### Phase 4: Scaffold + Ingress Validation

**Goal**: The markdown-renderer add-on is scaffolded following the repo's established 4-file pattern and a single
Docsify namespace works correctly end-to-end through HA Ingress — vendored JS assets load with no CDN requests, Mermaid
diagrams render, and the Docsify basePath resolves correctly for all `.md` file fetches.

**Depends on**: Nothing (first phase of milestone)

**Requirements**: ADD-01, ADD-02, ADD-03, ADD-04, INGRESS-01, INGRESS-02, INGRESS-03, INGRESS-04, INGRESS-05, MULTI-01,
MULTI-02, MULTI-03, MULTI-04, MULTI-05, MULTI-06, KROKI-01, KROKI-02, KROKI-03, KROKI-04, KROKI-05

**Success Criteria** (what must be TRUE):

1. The add-on appears in the HA sidebar via Ingress with the configured panel icon; opening it loads the Docsify SPA
   without browser errors
2. Docsify fetches and renders `.md` files from the mounted directory through HA Ingress; no requests go to a CDN
   (Docsify, Mermaid)
3. Mermaid diagrams in fenced ` ```mermaid ` code blocks render as SVG inside Docsify without JavaScript errors
4. All static assets (Docsify JS, Mermaid JS, CSS) load via relative paths; no absolute `/`-prefixed path causes a 404
   under the Ingress URL
5. Auto-update does not propose or apply a Docsify v5 RC upgrade; `.upstream.yaml` keeps the add-on on `v4.*`
6. PlantUML (or any non-Mermaid Kroki format) in fenced ` ```plantuml ` code blocks renders as `<img>` tags whose `src`
   points at the configured `kroki_url` (default `https://kroki.io`); if Kroki is unreachable the original code block
   remains visible

**Plans**: 3 plans in 2 waves

Plans:

- [x] 04-01-PLAN.md — Scaffold add-on skeleton (config.yaml, build.yaml, Dockerfile, run.sh, README, DOCS,
      .upstream.yaml, single-namespace generate_nginx.py skeleton)
- [x] 04-02-PLAN.md — Full multi-namespace generate_nginx.py: iterate directories, name validation, per-namespace
      index.html, landing page, nginx -t validation
- [x] 04-03-PLAN.md — make check-all + local docker build + README Verification section with 5-point HA Ingress
      checklist

**UI hint**: yes

### Phase 5: Multi-Namespace + Dynamic Config

**Goal**: Multiple Markdown directories are served as isolated Docsify SPAs under separate namespaces, configured
entirely through the HA UI; a landing page at the Ingress root lists all namespaces; invalid names are rejected at
startup.

**Depends on**: Phase 4

**Requirements**: MULTI-01, MULTI-02, MULTI-03, MULTI-04, MULTI-05, MULTI-06

**Success Criteria** (what must be TRUE):

1. User configures two or more directories in the HA add-on options UI; each namespace is accessible as an independent
   Docsify SPA at `/name/` with its own Markdown root
2. The Ingress root (`/`) shows a landing page with a clickable card for every configured namespace; cards are
   regenerated when the add-on restarts with a different config
3. An invalid namespace name (empty, contains `/`, or conflicts with `_docsify` / `api`) causes a clear startup log
   error and the add-on refuses to start rather than serving a broken route
4. Directories mounted from `/share`, `/config`, or `/media` are served without permission errors or volume
   configuration changes beyond setting `map: share:rw config:rw media:rw` in config.yaml

**Plans**: 1 plan in 1 wave

Plans:

- [x] 05-01-PLAN.md — Empirical multi-namespace verification inside container + DOCS.md/README.md updates for
      multi-namespace behavior + Manual HA Ingress Test Checklist expansion

**UI hint**: yes

### Phase 6: Git Integration

**Goal**: Namespaces backed by git repos stay current without manual intervention; git pull errors at startup are logged
but do not block the namespace from being served; periodic background sync is available via config.

**Depends on**: Phase 5

**Requirements**: GIT-01, GIT-02, GIT-03, GIT-04, GIT-05

**Success Criteria** (what must be TRUE):

1. A namespace with `git_pull: true` fetches latest commits from the remote before nginx starts; the pulled content is
   immediately visible in the browser on first load
2. A namespace with `git_pull_interval: N` (N > 0) receives background updates every N seconds while nginx serves
   traffic; content updates are visible after the next browser refresh
3. Namespaces without `git_pull` or `git_pull_interval` start without any git operations; no git binary is invoked for
   them
4. When a git remote is unreachable at startup, the namespace starts and serves its locally cached Markdown; a warning
   appears in HA logs but the add-on does not crash

**Plans**: 2 plans in 2 waves

Plans:

- [x] 06-01-PLAN.md — Implementation: extend `config.yaml` schema with `git_pull`, `git_pull_interval`, `git_url`; add
      `git` to Dockerfile apk list; create `_git_sync.py` with probe/pull/clone + periodic state; rewrite `run.sh` with
      startup pull, background loop, and signal trap (GIT-01..05)
- [x] 06-02-PLAN.md — Empirical verification: 5-scenario `verify-git-integration.sh` covering startup pull, graceful
      failure, no-invocation-when-disabled, periodic sync, and first-time clone via `git_url`; capture transcript;
      document in DOCS.md `## Git Sync` section and README.md checklist items 11–13

### Phase 8: CI/CD Hardening

**Goal**: The CI/CD pipeline's three invisible defects are closed and the conventions that prevent their recurrence are
written down. All 12 workflows reported green during the audit — these are the failures a green run-status column cannot
show: one fails silently by design, one has no failure mode until it triggers, one surfaces only as a warning annotation.

**Depends on**: Nothing (independent of the markdown-renderer milestone)

**Requirements**: CI-01, CI-02, CI-03, CI-04, CI-05, CI-06, CI-07, CI-08, CI-09, CI-10

**Success Criteria** (what must be TRUE):

1. Home Assistant observably processes a build notification — the receiving automation's `last_triggered` advances after
   a real build, rather than the script merely collecting an HTTP 200 (HA answers 200 for any webhook ID, registered or
   not)
2. An unauthenticated POST to the webhook path from the public internet is still redirected to the Cloudflare Access
   login; authenticating the runner did not make the path publicly triggerable
3. Every workflow job carries an explicit `timeout-minutes`; a hung aarch64 QEMU build can no longer burn a 6-hour
   runner block
4. No build run carries the "Node.js 20 is deprecated" annotation, and `actions/checkout` sits at a single major across
   all five files that use it
5. A real multi-arch build (amd64 + aarch64) is green on the bumped action set, proving emulation still works rather
   than assuming it
6. No document references the removed `.github/workflows/build.yml`, no document advertises the nonexistent
   `HA_WEBHOOK_SECRET` capability, and the per-add-on tag-trigger state is documented with its rationale

**Plans**: 4 plans in 4 waves (strictly serial — plans 01, 02 and 03 all modify `_build-template.yml`, so
single-writer-per-wave is the only safe ordering)

Plans:

- [x] 08-01-PLAN.md — `timeout-minutes` on all 6 jobs across 5 workflow files, each cap sized from measured runtime
      (build 45 / auto-update 20 / base-image 15 / lint 15 / lint-results 5 / opencode 30)
- [x] 08-02-PLAN.md — Bump 4 Docker actions + unify `actions/checkout` on one major; breaking-change audit re-verified
      empirically; one real multi-arch verification build (amd64 3m54s + aarch64 11m1s, both success, zero Node 20
      annotations); Renovate PRs #39/#40 auto-closed
- [ ] 08-03-PLAN.md — Cloudflare Access service token for the webhook path (separate path-scoped Access app, Service Auth
      policy, not a Bypass); `notify-ha.sh` gains auth, 3xx fail-fast and real diagnostics; 4 named secrets threaded
      through 7 callers
- [x] 08-04-PLAN.md — 9 documentation drift instances corrected across README / AGENTS / WEBHOOK_SETUP / RELEASE /
      DEVELOPMENT, plus the timeout, pinning and secrets conventions recorded

**UI hint**: no

## Progress

| Phase                               | Milestone | Plans Complete | Status   | Completed  |
| ----------------------------------- | --------- | -------------- | -------- | ---------- |
| 1. Quality Fixes                    | v1.0      | 2/2            | Complete | 2026-04-03 |
| 2. Auto-Update Workflow             | v1.0      | 1/1            | Complete | 2026-04-04 |
| 3. Meridian Add-on                  | v1.0      | 3/3            | Complete | 2026-04-04 |
| 4. Scaffold + Ingress Validation    | v1.1      | 3/3            | Complete | 2026-06-27 |
| 5. Multi-Namespace + Dynamic Config | v1.1      | 1/1            | Complete | 2026-06-27 |
| 6. Git Integration                  | v1.1      | 2/2            | Complete | 2026-06-28 |
| 8. CI/CD Hardening                  | v1.2      | 3/4            | Executing | —          |
