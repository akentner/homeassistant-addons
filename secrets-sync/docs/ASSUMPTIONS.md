# Assumptions (ss-package)

One line each. Items marked DECIDED were confirmed by the user in the interview.

1. `bashio::config` needs the Supervisor API, so `run.sh` reads secrets from `options.json` with python3 - revisit.
2. `SS_ADDON_VERSION` comes from `bashio::app.version`, falling back to `addon.version`, then `unknown` - revisit.
3. Optional provider blocks use `bitwarden?:` / `sops?:` in the schema (HA syntax), not `{...}?` - revisit tonight.
4. `init: false` and `with-contenv bashio` as in haos-monitor/meridian - revisit tonight.
5. Only `BW_*` vars are exported when the option is non-empty; empty credentials are left unset - revisit tonight.
6. DECIDED: No `LOCAL_BUILD_ADDONS`, base-image-config or renovate entries (haos-monitor has none, CI discovers
   add-ons) - revisit tonight.
7. DECIDED: `BW_CLI_VERSION` pinned to 2026.10.0, no auto-bump, npm install without integrity check - revisit tonight.
8. DECIDED: Dockerfile commit used `SKIP=hadolint` because hadolint is not installed locally (needed once) - revisit
   tonight.
9. Verify scripts use python3+PyYAML instead of `yq` (local yq is the Python flavour) - revisit tonight.
10. GET / cannot be verified from inside the container (ingress only); the rendered page is covered by tests/web -
    revisit tonight.
11. Host path of `addon_config` documented as `/addon_configs/<repository-hash>_secrets_sync/` - revisit tonight.
12. Gatus example hostname `72a005f5-secrets-sync` copied from the haos-monitor naming - revisit tonight.
13. Icon and logo are generated placeholders - revisit tonight.

## Decided in the interview

- Renovate tracks `BW_CLI_VERSION` (npm `@bitwarden/cli`); a bump PR still needs a config.yaml subpatch bump.
- `secrets-sync` is listed in `internal/base-image-config.yaml` (automatic Alpine base bumps).
- First run replaces an existing `secrets.yaml` (previous kept as `.bak`); unmanaged files in `secrets_files` are never
  overwritten.
- `GET /` is ingress only; `/api/status.json` (key names, no values) stays readable on the optional TCP port.
- Manual sync gap stays 10 s; `run.sh` reads options with python3 instead of `bashio::config`.
- `shrink_guard_percent` default is 30; a provider failure after a restart writes nothing.
- hadolint 2.14.0 installed locally; Dockerfile is clean.
- Release tag scheme: `secrets-sync/v<version>` (e.g. `secrets-sync/v0.1.0-0`).
