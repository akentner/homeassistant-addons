# Concerns & Technical Debt

_Last updated: 2026-04-03_

## Summary

The repository is well-structured for a Home Assistant add-on collection, but has several notable gaps: the documented
auto-update system is not implemented, version validation only partially covers add-ons, security practices around
Docker image fetching are weak, and the most complex code paths have no test coverage. Most issues are low-risk for a
personal/small-team project but would need addressing before wider distribution.

## Missing / Incomplete Implementations

### Auto-Update Workflow Not Implemented (HIGH)

- `.upstream.yaml` files in both add-ons and all documentation reference a daily GitHub Actions auto-update workflow
- **Only `lint.yml` exists in `.github/workflows/`** — the auto-update workflow is completely absent
- The daily version monitoring system described in CLAUDE.md does not actually run

### `validate-versions` Only Covers `fritz-callmonitor2mqtt` (MEDIUM)

- The pre-commit hook in `.pre-commit-config.yaml` (line 66) has a `files:` pattern scoped only to
  `fritz-callmonitor2mqtt`
- `phone-logger` version drift across its 3 files goes undetected by pre-commit

## Security Concerns

### No Binary Integrity Verification (MEDIUM)

- Both Dockerfiles download release tarballs from GitHub without SHA256 checksum verification
- A compromised release artifact would not be detected

### Default MQTT Password (LOW)

- `fritz-callmonitor2mqtt/config.yaml` ships `mqtt_password: "mosquitto"` as a hardcoded default
- Users who don't change this are exposed if MQTT is reachable on the network

### `uv:latest` Unpinned (LOW)

- `phone-logger/Dockerfile` copies from `ghcr.io/astral-sh/uv:latest` — a breaking uv update could silently break builds

## Known Issues / Documentation Mismatches

### `DOCS.md` Type Mismatch (MEDIUM)

- `phone-logger/DOCS.md` example shows `type: fritz`
- `generate_config.py` emits `type: fritz_callmonitor`
- This will cause confusion for users following the documentation

### Health Check Port Never Exposed (LOW)

- `app_health_check_port` is documented and referenced in the config schema
- No `EXPOSE` directive or port mapping exists in the Dockerfile or config

### Hardcoded Timezone in Dockerfile (LOW)

- `phone-logger/Dockerfile` sets `TZ=Europe/Berlin` at the system level
- This overrides the user-configurable `timezone` option in practice

## Technical Debt

### amd64-Only Builds (MEDIUM)

- Both add-ons are built for amd64 only
- Multi-arch support (arm64, armv7) is partially scaffolded but commented out in `build.yaml` files
- Many Home Assistant users run on Raspberry Pi (armv7/arm64)

### Hadolint Disabled (LOW)

- Dockerfile linting (`hadolint`) is disabled in `.pre-commit-config.yaml`
- The above issues (unpinned base images, no checksum verification) would likely be flagged if enabled

### Duplicated MSN/Extension Parsing (LOW)

- `fritz-callmonitor2mqtt/run.sh` has duplicated fallback logic for MSN/extension parsing
- Two parallel code paths for the same operation increase maintenance burden

### No Unit Tests on Core Logic (HIGH)

- `phone-logger/generate_config.py` `transform()` function: core config transformation, zero tests
- `scripts/update-version.py`: version bumping script, no regression tests
- Runtime correctness is entirely manual/observational

## Maintenance Risks

| Risk                                       | Likelihood                | Impact                     |
| ------------------------------------------ | ------------------------- | -------------------------- |
| Auto-update workflow never triggers        | Certain (not implemented) | Versions drift silently    |
| `phone-logger` version files desync        | Medium                    | Add-on fails HA validation |
| `uv:latest` breaks build                   | Low                       | phone-logger builds fail   |
| Documentation type mismatch confuses users | High (first-time setup)   | Configuration errors       |
| amd64-only limits user base                | High                      | Many HA installs excluded  |

## Key Observations

- The auto-update system is the biggest gap — it is documented but does not exist
- Most security issues are acceptable for a personal/trusted-network deployment but not for public add-on distribution
- Adding `phone-logger` to the `validate-versions` pre-commit scope is a one-line fix
- Re-enabling `hadolint` would catch several Dockerfile issues automatically
