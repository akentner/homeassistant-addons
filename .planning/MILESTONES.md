# Milestones

## v1.0 MVP (Shipped: 2026-04-04)

**Phases completed:** 3 phases, 6 plans **Timeline:** 2026-04-03 → 2026-04-04 **Files changed:** 75 files, 8,740
insertions

**Key accomplishments:**

1. `validate-versions` pre-commit hook extended to cover all three add-ons (fritz-callmonitor2mqtt, phone-logger,
   meridian)
2. `phone-logger/DOCS.md` adapter type corrected (`fritz` → `fritz_callmonitor`)
3. hadolint v2.14.0 re-enabled in pre-commit with four HA-specific ignore rules (DL3006, DL3018, DL3059, DL4006); DL3016
   added for `npm install -g`
4. GitHub Actions auto-update workflow: daily upstream version check (06:00 UTC), fully automatic 3-file version
   update + commit to main via GITHUB_TOKEN, dynamic add-on discovery via `.upstream.yaml`
5. Meridian add-on: two-stage Dockerfile (oven/bun:1 build + HA amd64-base:3.22 runtime), GitHub tarball fetch at build
   time, auto-update wiring for rynfar/meridian
6. Meridian run.sh: OAuth token persisted via `/data/.claude` symlink, credential guard with actionable error message,
   port 3456 exposed on 0.0.0.0 for LAN/Tailscale

**Archive:**

- `.planning/milestones/v1.0-ROADMAP.md`
- `.planning/milestones/v1.0-REQUIREMENTS.md`

---
