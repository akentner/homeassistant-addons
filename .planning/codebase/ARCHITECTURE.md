# Architecture

_Last updated: 2026-04-03_

## Summary

This repository is a Home Assistant add-on repository containing two independent add-ons: `fritz-callmonitor2mqtt` and
`phone-logger`. Each add-on is a self-contained containerized application that integrates with Home Assistant Supervisor
via a standardized manifest-and-entrypoint pattern. Add-ons read their configuration through Home Assistant's `bashio`
helper (or via options.json), translate it to application-native formats, and run a single foreground process. Version
management is centralized through a 3-file synchronization scheme enforced by pre-commit hooks and a Python update
script.

## Add-on Container Pattern

Both add-ons share the same structural pattern mandated by the Home Assistant Supervisor SDK:

1. `config.yaml` — declares the add-on manifest, option schema, and default values to Home Assistant
2. `build.yaml` — provides Docker build arguments, base image, and the `VERSION` build arg
3. `Dockerfile` — downloads the upstream release artifact (binary or source tarball) and copies in add-on-specific
   override files
4. `run.sh` — the container entrypoint; translates HA configuration into application-native env vars or config files,
   then `exec`s the main process

The container base images are official Home Assistant base images from `ghcr.io/home-assistant/`.

## Configuration Bridge

Home Assistant Supervisor injects user-configured options as `/data/options.json` into the container at runtime. Each
add-on bridges this into its application:

**fritz-callmonitor2mqtt** (`fritz-callmonitor2mqtt/run.sh`):

- Uses `bashio::config` calls inside a `#!/usr/bin/with-contenv bashio` script
- Maps each option directly to a namespaced environment variable (e.g., `FRITZ_CALLMONITOR_FRITZBOX_HOST`)
- Handles YAML arrays by iterating with index-based `bashio::config` calls and building comma-separated strings
- `exec`s the pre-compiled Go binary at `/opt/fritz-callmonitor2mqtt/fritz-callmonitor2mqtt`

**phone-logger** (`phone-logger/run.sh` + `phone-logger/generate_config.py`):

- A thin `sh` script that runs `generate_config.py` first, then `exec`s the Python application
- `generate_config.py` reads `/data/options.json`, performs structural transformation (HA nested-dict schema → AppConfig
  list-of-AdapterConfig objects), and writes a YAML file to `/tmp/phone-logger-config.yaml`
- The application reads its config from the path set in `PHONE_LOGGER_CONFIG`
- This two-stage approach exists because phone-logger's AppConfig expects lists of adapter objects while HA's schema
  validator requires flat nested dicts

## Adapter Architecture (phone-logger)

phone-logger's upstream application uses an adapter pattern with three categories:

- **input_adapters**: Sources of call events (e.g., `fritz_callmonitor` via TCP port 1012, `rest` via HTTP)
- **resolver_adapters**: Lookup/enrichment of phone numbers (e.g., `json_file`, `sqlite`, `msn`, `tellows`,
  `dastelefon`)
- **output_adapters**: Consumers of processed call events (e.g., `call_log`, `webhook`, `mqtt`)

`generate_config.py` always enables certain adapters regardless of user config (e.g., `rest` input, `json_file`/
`sqlite`/`msn`/`dastelefon` resolvers, `call_log` output). User config in HA only toggles optional adapters
(`fritz_callmonitor` input, `tellows` resolver, `mqtt` output, `webhook` outputs).

## Upstream Binary Download Pattern

Both add-ons download their application code at Docker build time rather than bundling source:

- **fritz-callmonitor2mqtt**: Downloads a pre-compiled Go binary tarball from GitHub Releases via `curl`; selects
  architecture-appropriate artifact using `$TARGETARCH`
- **phone-logger**: Downloads the upstream Python source tarball from GitHub Releases via `curl | tar xz`; installs
  Python dependencies with `uv sync --frozen` from the upstream `uv.lock`; add-on-specific files (`run.sh`,
  `generate_config.py`) are copied in afterwards and override upstream placeholders

## Auto-Update System

Each add-on directory contains `.upstream.yaml` defining:

- `upstream.repository`: the GitHub repo to watch (e.g., `akentner/fritz-callmonitor2mqtt`)
- `upstream.version_pattern`: git tag glob pattern (`v*`)
- `upstream.version_strip`: regex to strip tag prefix (`^v`)
- `addon.version_pattern: sync`: signals add-on version tracks upstream exactly

A GitHub Actions workflow (daily at 6:00 UTC, not shown in this repo's workflows but referenced in docs) monitors these
upstream repos. When a new upstream version is detected, it calls `scripts/update-version.py` to synchronize the 3-file
version set and opens a PR.

## 3-File Version Synchronization

Every add-on maintains version state across exactly three files:

| File                  | Format                 | Role                                                        |
| --------------------- | ---------------------- | ----------------------------------------------------------- |
| `{addon}/config.yaml` | `X.Y.Z-N`              | HA manifest version (subpatch suffix for add-on-only fixes) |
| `{addon}/build.yaml`  | `X.Y.Z`                | Docker build arg `VERSION` used in Dockerfile curl URL      |
| `{addon}/README.md`   | `vX.Y.Z` in badge URLs | Shield badge and release link                               |

`scripts/validate-versions.sh` enforces consistency: strips subpatch from `config.yaml`, then checks all three match.
This runs as a pre-commit hook and in CI.

`scripts/update-version.py` atomically updates all three files via regex substitution and resets the subpatch to `-0`.

## CI / Quality Gates

`.github/workflows/lint.yml` runs on push/PR to `main`/`develop`:

- pre-commit hooks (yamllint, trailing-whitespace, shellcheck, prettier for Markdown, actionlint)
- yamllint standalone
- actionlint
- shellcheck
- markdownlint-cli2
- Custom add-on structure validation (checks for required files, valid `config.yaml`, valid `.upstream.yaml`)
- YAML tab/CRLF detection

## Data Persistence

Both add-ons use the `addon_config` volume mount (mapped by HA Supervisor):

- fritz-callmonitor2mqtt: mounts to `/opt/fritz-callmonitor2mqtt/data`
- phone-logger: mounts to `/addon_config`

This provides persistence for call history, contact files (phone-logger uses `contacts.json` and SQLite DB), and
application state across container restarts.

## Key Observations

- The configuration bridge is the most complex add-on-specific logic; each add-on solves this differently (env vars via
  bashio vs. Python config transform)
- The `generate_config.py` transform is the single choke-point for translating between HA schema conventions and
  phone-logger's AppConfig; changes to either side require updating this file
- phone-logger exposes an ingress port (8080) for HA ingress panel; fritz-callmonitor2mqtt does not use ingress
- Both add-ons are currently `amd64`-only in practice (other architectures commented out in `build.yaml`/`config.yaml`)
- The upstream source is always fetched at build time; there is no local copy of upstream code in this repository
- `uv` is used in phone-logger's container to manage Python deps and run the application; not used in CI for the add-on
  repo itself (CI uses `pip`)
