# Roadmap: Home Assistant Add-ons Repository

## Milestones

- ✅ **v1.0 MVP** — Phases 1-3 (shipped 2026-04-04)
- 📋 **v1.1 markdown-renderer** — Phases 4-6 (planned)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-3) — SHIPPED 2026-04-04</summary>

- [x] Phase 1: Quality Fixes (2/2 plans) — completed 2026-04-03
- [x] Phase 2: Auto-Update Workflow (1/1 plan) — completed 2026-04-04
- [x] Phase 3: Meridian Add-on (3/3 plans) — completed 2026-04-04

Full details: [.planning/milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

### 📋 v1.1 markdown-renderer (Phases 4-6)

- [ ] **Phase 4: Scaffold + Ingress Validation** — Add-on structure, vendored assets, single-namespace Docsify SPA
      working through HA Ingress with correct basePath and relative asset paths
- [ ] **Phase 5: Multi-Namespace + Dynamic Config** — `generate_nginx.py` wired to HA options, multiple directories
      served as isolated SPAs, landing page at ingress root
- [ ] **Phase 6: Git Integration** — Optional per-namespace git pull at startup and on a background interval; errors
      non-blocking

## Phase Details

### Phase 4: Scaffold + Ingress Validation

**Goal**: The markdown-renderer add-on is scaffolded following the repo's established 4-file pattern and a single
Docsify namespace works correctly end-to-end through HA Ingress — vendored JS assets load with no CDN requests, Mermaid
diagrams render, and the Docsify basePath resolves correctly for all `.md` file fetches.

**Depends on**: Nothing (first phase of milestone)

**Requirements**: ADD-01, ADD-02, ADD-03, ADD-04, INGRESS-01, INGRESS-02, INGRESS-03, INGRESS-04, INGRESS-05, MULTI-01,
MULTI-02, MULTI-03, MULTI-04, MULTI-05, MULTI-06

**Success Criteria** (what must be TRUE):

1. The add-on appears in the HA sidebar via Ingress with the configured panel icon; opening it loads the Docsify SPA
   without browser errors
2. Docsify fetches and renders `.md` files from the mounted directory through HA Ingress; no requests go to a CDN
3. Mermaid diagrams in fenced ` ```mermaid ` code blocks render as SVG inside Docsify without JavaScript errors
4. All static assets (Docsify JS, Mermaid JS, CSS) load via relative paths; no absolute `/`-prefixed path causes a 404
   under the Ingress URL
5. Auto-update does not propose or apply a Docsify v5 RC upgrade; `.upstream.yaml` keeps the add-on on `v4.*`

**Plans**: 3 plans in 2 waves

Plans:

- [ ] 04-01-PLAN.md — Scaffold add-on skeleton (config.yaml, build.yaml, Dockerfile, run.sh, README, DOCS,
      .upstream.yaml, single-namespace generate_nginx.py skeleton)
- [ ] 04-02-PLAN.md — Full multi-namespace generate_nginx.py: iterate directories, name validation, per-namespace
      index.html, landing page, nginx -t validation
- [ ] 04-03-PLAN.md — make check-all + local docker build + README Verification section with 5-point HA Ingress
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

**Plans**: TBD

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

**Plans**: TBD

## Progress

| Phase                               | Milestone | Plans Complete | Status      | Completed  |
| ----------------------------------- | --------- | -------------- | ----------- | ---------- |
| 1. Quality Fixes                    | v1.0      | 2/2            | Complete    | 2026-04-03 |
| 2. Auto-Update Workflow             | v1.0      | 1/1            | Complete    | 2026-04-04 |
| 3. Meridian Add-on                  | v1.0      | 3/3            | Complete    | 2026-04-04 |
| 4. Scaffold + Ingress Validation    | v1.1      | 0/0            | Not started | —          |
| 5. Multi-Namespace + Dynamic Config | v1.1      | 0/0            | Not started | —          |
| 6. Git Integration                  | v1.1      | 0/0            | Not started | —          |
