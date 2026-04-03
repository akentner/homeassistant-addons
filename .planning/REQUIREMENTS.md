# Requirements: Home Assistant Add-ons Repository

**Defined:** 2026-04-04 **Core Value:** Any upstream release is automatically reflected in the add-on within 24 hours —
zero manual version tracking.

## v1 Requirements

### Auto-Update Workflow

- [ ] **AUTO-01**: GitHub Actions workflow runs daily (cron) and checks each add-on's upstream for new releases using
      `gh     release view --repo <upstream>`
- [ ] **AUTO-02**: When a new version is detected, `scripts/update-version.py` is called to synchronize the 3-file
      version set (config.yaml, build.yaml, README.md)
- [ ] **AUTO-03**: Updated files are committed directly to `main` branch (no PR step, fully automatic merge)
- [ ] **AUTO-04**: Workflow skips commit when no version change is detected (prevents empty commits)
- [ ] **AUTO-05**: Workflow authenticates via `GITHUB_TOKEN` — no additional secrets required

### Meridian Add-on

- [ ] **MER-01**: `meridian/` add-on directory with complete standard structure: `config.yaml`, `build.yaml`,
      `Dockerfile`, `run.sh`, `README.md`, `DOCS.md`, `.upstream.yaml`
- [ ] **MER-02**: Dockerfile uses multi-stage build: `oven/bun:1` for TypeScript compilation,
      `ghcr.io/home-assistant/amd64-base` as runtime base with `nodejs` and `npm` installed via `apk`
- [ ] **MER-03**: Source is fetched from the GitHub Release archive (`rynfar/meridian`) at Docker build time — no
      bundled source in this repo
- [ ] **MER-04**: Port 3456 is declared in `config.yaml` and accessible from LAN and Tailscale
- [ ] **MER-05**: `run.sh` creates `/root/.claude → /data/.claude` symlink so the OAuth token persists across container
      restarts
- [ ] **MER-06**: `run.sh` detects missing Claude credentials and prints clear setup instructions (how to run
      `claude     login` via the HA terminal add-on), then exits with an error
- [ ] **MER-07**: `MERIDIAN_HOST=0.0.0.0` is set so the proxy accepts connections from outside the container
- [ ] **MER-08**: Version tracked via 3-file scheme; `.upstream.yaml` watches `rynfar/meridian` for new releases

### Quality Fixes

- [x] **FIX-01**: `validate-versions` pre-commit hook covers `phone-logger` (currently scoped to
      `fritz-callmonitor2mqtt` only)
- [x] **FIX-02**: `phone-logger/DOCS.md` adapter type example corrected (`type: fritz` → `type: fritz_callmonitor`)
- [x] **FIX-03**: `hadolint` re-enabled in `.pre-commit-config.yaml` (currently disabled)

## v2 Requirements

### Multi-Architecture Support

- **ARCH-01**: `fritz-callmonitor2mqtt` add-on builds for `arm64` and `armv7` in addition to `amd64`
- **ARCH-02**: `phone-logger` add-on builds for `arm64` and `armv7`
- **ARCH-03**: `meridian` add-on builds for `arm64`

### Testing

- **TEST-01**: Unit tests for `phone-logger/generate_config.py` `transform()` function covering all adapter combinations
- **TEST-02**: Regression tests for `scripts/update-version.py` covering edge cases (version downgrade prevention,
  subpatch increment)

## Out of Scope

| Feature                             | Reason                                                                               |
| ----------------------------------- | ------------------------------------------------------------------------------------ |
| Binary integrity verification (SHA) | Trusted GitHub Releases source; personal deployment, not public distribution         |
| Automatic `claude login` via config | OAuth token cannot safely be stored as plaintext config option                       |
| Meridian multi-user support         | Single-user personal deployment; upstream handles sessions                           |
| Auto-update via PR (manual review)  | Upstream releases are trusted (own projects + well-known meridian); no review needed |
| Generic Alpine/node base images     | HA base images required for Supervisor compatibility                                 |

## Traceability

| Requirement | Phase   | Status  |
| ----------- | ------- | ------- |
| FIX-01      | Phase 1 | Complete |
| FIX-02      | Phase 1 | Complete |
| FIX-03      | Phase 1 | Complete |
| AUTO-01     | Phase 2 | Pending |
| AUTO-02     | Phase 2 | Pending |
| AUTO-03     | Phase 2 | Pending |
| AUTO-04     | Phase 2 | Pending |
| AUTO-05     | Phase 2 | Pending |
| MER-01      | Phase 3 | Pending |
| MER-02      | Phase 3 | Pending |
| MER-03      | Phase 3 | Pending |
| MER-04      | Phase 3 | Pending |
| MER-05      | Phase 3 | Pending |
| MER-06      | Phase 3 | Pending |
| MER-07      | Phase 3 | Pending |
| MER-08      | Phase 3 | Pending |

**Coverage:**

- v1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0 ✓

---

_Requirements defined: 2026-04-04_ _Last updated: 2026-04-04 after initial definition_
