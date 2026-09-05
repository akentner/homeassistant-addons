# Test Add-on

[![Release][release-badge]][repo]

[release-badge]: https://img.shields.io/badge/version-v0.1.0-blue.svg
[repo]: https://github.com/akentner/homeassistant-addons/tree/v0.1.0

Live test target for the Phase 14 verify suite. The Provider can install, configure, start, stop, and uninstall this
add-on without touching any real add-on on the host.

## What it does

Nothing observable. The container runs a no-op `sleep infinity` wrapped in `bashio` setup so Supervisor observes the
add-on as `started: true`. The schema exposes two string options (`log_level` default `info`, `dummy_setting` default
`default`) so Update and pwned-warning scenarios have something to vary. The slug follows HA's `local_` convention for
locally-built add-ons.

## Building

```bash
docker build -t local_test-addon tools/test-addon/
ha addons reload
ha addons rebuild local_test-addon
```

The verify suite (`internal/verify-bridge-e2e/00-happy-path.sh`) targets this add-on as the canonical
install/start/options/stop/uninstall cycle target.
