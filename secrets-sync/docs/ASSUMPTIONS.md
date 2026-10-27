# Assumptions (ss-package)

One line each. All: revisit tonight.

1. `bashio::config` needs the Supervisor API, so `run.sh` reads secrets from `options.json` with python3 - revisit
   tonight.
2. `SS_ADDON_VERSION` comes from `bashio::app.version`, falling back to `addon.version`, then `unknown` - revisit
   tonight.
3. Optional provider blocks use `bitwarden?:` / `sops?:` in the schema (HA syntax), not `{...}?` - revisit tonight.
4. `init: false` and `with-contenv bashio` as in haos-monitor/meridian - revisit tonight.
5. Only `BW_*` vars are exported when the option is non-empty; empty credentials are left unset - revisit tonight.
6. No `LOCAL_BUILD_ADDONS`, base-image-config or renovate entries (haos-monitor has none, CI discovers add-ons) -
   revisit tonight.
7. `BW_CLI_VERSION` pinned to 2026.10.0, no auto-bump, npm install without integrity check - revisit tonight.
8. Dockerfile commit used `SKIP=hadolint` because hadolint is not installed locally (needed once) - revisit tonight.
9. Verify scripts use python3+PyYAML instead of `yq` (local yq is the Python flavour) - revisit tonight.
10. GET / cannot be verified from inside the container (ingress only); the rendered page is covered by tests/web -
    revisit tonight.
11. Host path of `addon_config` documented as `/addon_configs/<repository-hash>_secrets_sync/` - revisit tonight.
12. Gatus example hostname `72a005f5-secrets-sync` copied from the haos-monitor naming - revisit tonight.
13. Icon and logo are generated placeholders - revisit tonight.
