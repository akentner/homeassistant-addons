# External Integrations

_Last updated: 2026-04-03_

## Summary

Both add-ons in this repository integrate with FRITZ!Box routers (AVM) for call monitoring data and publish events to
MQTT brokers. `phone-logger` additionally supports outbound webhooks, Home Assistant MQTT discovery, a Tellows caller-ID
resolver, and a built-in REST adapter. The repository itself integrates with GitHub for upstream release tracking and
GitHub Actions for CI linting.

## Hardware / Protocol Integrations

**AVM FRITZ!Box Call Monitor (TCP port 1012):**

- Both add-ons connect to a FRITZ!Box router's call monitor interface over a raw TCP socket on port 1012
- Default host: `fritz.box` (fritz-callmonitor2mqtt) / `192.168.178.1` (phone-logger)
- This is a proprietary AVM protocol; there is no SDK — the upstream Go and Python applications implement the protocol
  directly
- Config keys: `fritzbox_host` / `fritzbox_port` (fritz-callmonitor2mqtt); `input_adapters.fritz_callmonitor.host` /
  `input_adapters.fritz_callmonitor.port` (phone-logger)

## Message Broker

**MQTT:**

- Both add-ons publish call events to an MQTT broker
- Default broker for fritz-callmonitor2mqtt: `core-mosquitto` (HA Mosquitto add-on) on port 1883
- Default topic prefix: `fritz/callmonitor` (fritz-callmonitor2mqtt), `phone-logger` (phone-logger)
- Config in `fritz-callmonitor2mqtt/config.yaml`: `mqtt_broker`, `mqtt_port`, `mqtt_username`, `mqtt_password`,
  `mqtt_client_id`, `mqtt_topic_prefix`, `mqtt_qos`, `mqtt_retain`, `mqtt_keep_alive`, `mqtt_connect_timeout`
- Config in `phone-logger/config.yaml` under `mqtt:`: `host`, `port`, `client_id`, `username`, `password`, `topic`,
  `qos`, `retain`, `keep_alive`, `connect_timeout`, `reconnect_delay`
- phone-logger MQTT adapter is optional — only activated when `mqtt.host` is non-empty
- phone-logger supports **Home Assistant MQTT Discovery** (`mqtt.ha_discovery`, `mqtt.ha_discovery_prefix`,
  `mqtt.ha_entity_id_prefix`)

## Home Assistant Platform

**Home Assistant Supervisor / Add-on API:**

- Both add-ons are HA add-ons; configuration is read from `/data/options.json` (HA supervisor injects this)
- `bashio` library provides `bashio::config` to read options in `run.sh` files
- `phone-logger/generate_config.py` transforms `/data/options.json` into an app-native YAML at
  `/tmp/phone-logger-config.yaml`
- `phone-logger` uses HA Ingress (port 8080) — `ingress: true`, `ingress_port: 8080` in `config.yaml`
- Both add-ons map `addon_config` for persistent storage:
  - fritz-callmonitor2mqtt: `/opt/fritz-callmonitor2mqtt/data`
  - phone-logger: `/addon_config`

## External APIs & Caller-ID Services

**Tellows (caller-ID / spam scoring):**

- Integrated as a resolver adapter in phone-logger
- Enabled via `resolver_adapters.tellows.enabled: true` in add-on config
- Cache TTL configurable: `resolver_adapters.tellows.cache_ttl_days` (default: 30)
- The actual Tellows API calls are handled by the upstream phone-logger Python app

**DasTelefon:**

- Another resolver adapter in phone-logger, always enabled (hardcoded in `generate_config.py`)
- Cache TTL: 30 days (hardcoded)

## Outbound Webhooks (phone-logger)

- phone-logger supports configurable outbound HTTP webhooks for call events
- Configured as a list under `output_webhooks` in add-on config: `url`, `method` (GET/POST), `headers`
- Processed in `phone-logger/generate_config.py` and passed to the upstream app as `webhook` output adapters

## GitHub (Upstream Release Tracking)

**GitHub Releases API:**

- `scripts/update-version.py` optionally verifies upstream release existence via HTTP HEAD request to
  `https://github.com/akentner/<addon-name>/releases/tag/v<version>` (invoked with `--check-release`)

**GitHub Release Artifact Downloads (at Docker build time):**

- `fritz-callmonitor2mqtt` Dockerfile downloads:
  `https://github.com/akentner/fritz-callmonitor2mqtt/releases/download/v{VERSION}/fritz-callmonitor2mqtt-{VERSION}-linux-{ARCH}.tar.gz`
- `phone-logger` Dockerfile downloads: `https://github.com/akentner/phone-logger/archive/refs/tags/v{VERSION}.tar.gz`

**GitHub Actions CI:**

- Workflow: `.github/workflows/lint.yml` — triggers on push to `main`/`develop`, PRs to `main`
- Installs `actionlint` by fetching the latest release from
  `https://api.github.com/repos/rhysd/actionlint/releases/latest`

**.upstream.yaml (auto-update config):**

- `fritz-callmonitor2mqtt/.upstream.yaml`: tracks `akentner/fritz-callmonitor2mqtt`, `v*` tags, `version_pattern: sync`
- `phone-logger/.upstream.yaml`: tracks `akentner/phone-logger`, `v*` tags, `version_pattern: sync`
- A GitHub Actions workflow (not present in this repo — likely in a separate automation repo) is expected to read these
  files and open PRs when upstream releases a new version

## Container Registry

**ghcr.io (GitHub Container Registry):**

- All base images pulled from `ghcr.io/home-assistant/`:
  - `ghcr.io/home-assistant/amd64-base:3.22` (fritz-callmonitor2mqtt)
  - `ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20` (phone-logger)
  - `ghcr.io/home-assistant/devcontainer:3-addons` (dev container)
- `uv` binary pulled from `ghcr.io/astral-sh/uv:latest` during phone-logger Docker build

## Data Storage

**Persistent (add-on config volume):**

- fritz-callmonitor2mqtt: call history / database stored in `/opt/fritz-callmonitor2mqtt/data` (mapped via
  `addon_config`)
- phone-logger: contacts.json, SQLite database, and other persistent state in `/addon_config`

**Ephemeral:**

- phone-logger config file written to `/tmp/phone-logger-config.yaml` at startup by `generate_config.py`

**No external database** — both add-ons use local file/SQLite storage only.

## Key Observations

- MQTT is the primary integration surface for both add-ons — all call events flow out via MQTT to the HA ecosystem
- The FRITZ!Box TCP call monitor on port 1012 must be manually enabled on the router (AVM dial pad feature)
- There is no authentication on the FRITZ!Box TCP socket — it is assumed to be on a trusted local network
- phone-logger's REST adapter is always enabled (hardcoded in `generate_config.py`) and exposes a local HTTP API on port
  8080 accessible via HA Ingress
- Both add-ons download their primary runtime from GitHub at image build time — broken GitHub connectivity or deleted
  releases will cause failed Docker builds
- `uv:latest` is pinned to `latest` (not a fixed version) in the phone-logger Dockerfile — this can cause
  non-reproducible builds if uv introduces breaking changes
