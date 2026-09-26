# Phase 21: cups-print-server-addon-airprint-mdns-fixes - Pattern Map

**Mapped:** 2026-09-26
**Files analyzed:** 8 (new: config.yaml, build.yaml, Dockerfile, run.sh, generate_config.py/avahi.conf.tpl, README.md, DOCS.md; modified: internal/base-image-config.yaml)
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `cups/config.yaml` | config | request-response (HA manifest+schema) | `gatus/config.yaml` (options/schema shape) + `phone-logger/config.yaml` (list-of-objects schema for `printers`) | exact (composite) |
| `cups/build.yaml` | config | batch (build arg) | `network-tools/build.yaml` / `gatus/build.yaml` | exact — no `VERSION` arg needed (apk-only, like network-tools) |
| `cups/Dockerfile` | config | file-I/O (apk install + COPY) | `network-tools/Dockerfile` | exact — single-stage HA base + apk packages, no upstream tarball/binary stage |
| `cups/run.sh` | utility (entrypoint) | event-driven (startup: config-gen → daemon exec) | `gatus/run.sh` (config-gen-then-exec shape) + `meridian/run.sh` (bashio idiom, `exec` handoff) | role-match |
| `cups/generate_config.py` (avahi-daemon.conf template renderer) | utility (config generator) | transform (options.json → daemon conf) | `gatus/generate_config.py` | exact — same job: read `/data/options.json`, render a native config file before `exec` |
| `cups/README.md` | doc | — | `gatus/README.md` | exact — same doc structure (badges, About, Features, Configuration) |
| `cups/DOCS.md` | doc | — | `gatus/DOCS.md` | exact — same doc structure (options table, user-facing config detail) |
| `internal/base-image-config.yaml` (add `cups:` entry) | config | batch (version-tracking metadata) | existing `gatus:` / `meridian:` / `network-tools:` entries in same file | exact — identical 4-line Alpine-base block |

## Pattern Assignments

### `cups/config.yaml` (config, request-response)

**Analog 1:** `gatus/config.yaml` (manifest shape, scalar options/schema, `host_network`/`capabilities` usage)
**Analog 2:** `phone-logger/config.yaml` (list-of-objects schema syntax for `printers`)

**Manifest header pattern** (gatus/config.yaml lines 1-24):
```yaml
name: "Gatus"
description: "..."
version: "5.36.0-11"
slug: "gatus"
init: false
arch:
  - amd64
image: "ghcr.io/akentner/homeassistant-addons/{arch}-gatus"
url: "https://github.com/akentner/homeassistant-addons"
startup: "application"
boot: "auto"
host_network: false
capabilities:
  - NET_RAW
  - NET_ADMIN
ingress: true
ingress_port: 8099
```
For `cups`: needs `slug: "cups"`, `image: ".../{arch}-cups"`, and per D-01/CONTEXT `host_network: true` (the whole reflector fix depends on this — do not copy gatus's `host_network: false`). No `ingress`/`ingress_port` needed unless a web UI is added — CUPS's own web UI on 631 is typically exposed via `ports:`, closer to how `meridian/config.yaml` exposes `ports: {3456/tcp: 3456}` + `ports_description`.

**Scalar options/schema pattern** (gatus/config.yaml lines 26-38):
```yaml
options:
  log_level: "info"
  storage_type: "memory"
  metrics: false
schema:
  log_level: "list(debug|info|warning|error)?"
  storage_type: "list(memory|sqlite)?"
  metrics: "bool?"
```
Apply directly to `avahi_reflector` (bool), `avahi_hostname` (str), `avahi_use_ipv6` (bool), `log_level`.

**List-of-objects schema pattern** (phone-logger/config.yaml lines 69-90, `output_webhooks` and `trunks`/`devices`):
```yaml
options:
  output_webhooks: []          # (top-level list default is empty array)
schema:
  output_webhooks:
    - url: url
      method: list(GET|POST)?
      headers:
        - key: str
          value: str
  ...
  msns:
    - number: str
      label: str
  devices:
    - id: str
      name: str
      type: list(voicebox|dect|voip)
      extension: str
```
This is the exact syntax to copy for `printers`:
```yaml
options:
  printers: []
schema:
  printers:
    - name: str
      uri: str
      enabled: bool?
```
(matches D-04's `{name, uri, enabled}` shape exactly — `enabled` optional/bool, defaults handled in `generate_config.py`/`run.sh` per D-14 discretion).

---

### `cups/build.yaml` (config, batch)

**Analog:** `network-tools/build.yaml` (apk-only add-on, no upstream `VERSION` arg) — verify exact content before copying; `gatus/build.yaml` shown for contrast (has `args: VERSION:` for upstream binary pinning, which `cups` does NOT need since D-06 explicitly rejects `.upstream.yaml`/tag tracking):
```yaml
build_from:
  amd64: "ghcr.io/home-assistant/amd64-base:3.24"
```
No `args:` block — `cups` has no downloaded binary version to inject (CUPS/Avahi come from `apk add`).

---

### `cups/Dockerfile` (config, file-I/O)

**Analog:** `network-tools/Dockerfile` (single-stage, apk-only, includes `avahi avahi-tools dbus` packages already — nearly identical package set to what `cups` needs)

**Core pattern** (network-tools/Dockerfile lines 1-26):
```dockerfile
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM $BUILD_FROM

RUN apk add --no-cache \
    nmap \
    ...
    avahi \
    avahi-tools \
    dbus \
    nginx

COPY arping_scan.py /usr/local/bin/arping_scan.py
COPY run.sh /run.sh
COPY nginx.conf /etc/nginx/network-tools.conf

RUN chmod +x /run.sh \
    && mkdir -p /data/results \
    && mkdir -p /var/run/nginx \
    && mkdir -p /var/lib/nginx/tmp/client_body

CMD ["/run.sh"]
```
For `cups`: replace package list with `cups cups-filters avahi avahi-tools dbus python3 py3-yaml` (python3/py3-yaml only if `generate_config.py` is Python, mirroring gatus rather than pure-shell templating). `COPY run.sh generate_config.py /` (gatus/Dockerfile line: `COPY run.sh generate_config.py /`). No nginx needed unless ingress UI added.

**LABELS footer** — identical boilerplate in every add-on Dockerfile (gatus/Dockerfile lines ~40-60, network-tools/Dockerfile same block) — copy verbatim, it's the shared `io.hass.*`/`org.opencontainers.*` label block.

---

### `cups/run.sh` (utility/entrypoint, event-driven)

**Analog 1 (config-gen-then-exec shape):** `gatus/run.sh`:
```sh
#!/bin/sh
set -e

# Generate config from HA options + user config
python3 /generate_config.py

LOG_LEVEL=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('log_level','info'))" 2>/dev/null || echo "info")
export GATUS_LOG_LEVEL="$LOG_LEVEL"

exec /usr/local/bin/gatus
```

**Analog 2 (bashio idiom, preferred over raw `python3 -c` option reads):** `meridian/run.sh`:
```bash
#!/usr/bin/with-contenv bashio
LOG_LEVEL=$(bashio::config 'log_level')
export MERIDIAN_LOG_LEVEL="$LOG_LEVEL"
...
if bashio::config.true 'passthrough'; then
    export MERIDIAN_PASSTHROUGH=true
fi
...
exec meridian
```
For `cups/run.sh`: use the `bashio::config` idiom (meridian style — cleaner than gatus's raw `python3 -c` reads) to read `avahi_reflector`, `avahi_hostname`, `avahi_use_ipv6`, `log_level`; call `python3 /generate_config.py` (gatus style) to render `avahi-daemon.conf` from the options + iterate `printers` list registering each via `lpadmin`; then `exec cupsd -f` (or start `avahi-daemon` + `exec cupsd`, since two daemons are needed — CUPS's own foreground exec should be last, avahi-daemon backgrounded first, same ordering idea as gatus backgrounding nginx before `exec gatus`).

---

### `cups/generate_config.py` (utility, transform)

**Analog:** `gatus/generate_config.py` — full structure to copy:
```python
#!/usr/bin/env python3
"""Docstring describing the merge."""
import json
from pathlib import Path

OPTIONS_PATH = "/data/options.json"
OUTPUT_PATH = "/tmp/gatus-config.yaml"   # -> /etc/avahi/avahi-daemon.conf for cups

def load_options() -> dict:
    path = Path(OPTIONS_PATH)
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)

def build_config(options: dict) -> str:
    # render template string using options["avahi_reflector"], options["avahi_hostname"], options["avahi_use_ipv6"]
    ...

def main() -> None:
    options = load_options()
    config = build_config(options)
    Path(OUTPUT_PATH).write_text(config)
    print(f"Config written to {OUTPUT_PATH}", flush=True)

if __name__ == "__main__":
    sys.exit(main())
```
Adapt `build_config` to render an INI-style `avahi-daemon.conf` (not YAML) — string template with `enable-reflector=`, `host-name=`, `use-ipv6=` lines driven by the three options per D-07/D-09/D-10. Also handle `printers` list here or in `run.sh` (issuing `lpadmin -p <name> -v <uri> -E` per enabled printer) — phone-logger's list-of-objects iteration pattern (Go-side, not directly reusable code, but same "iterate list of dicts, register each") is the conceptual analog; concretely in Python this is just `for p in options.get("printers", []): if p.get("enabled", True): ...`.

---

### `cups/README.md` / `cups/DOCS.md` (doc)

**Analog:** `gatus/README.md` + `gatus/DOCS.md`

README structure (gatus/README.md lines 1-30): badges line, `## About`, `## Features`, `## Configuration` — copy this skeleton, replace Gatus-specific prose with CUPS/AirPrint description referencing the DIAGNOSIS.md root causes.

DOCS.md structure (gatus/DOCS.md lines 1-15): `## Add-on Options` markdown table with `| Option | Default | Description |` — copy this table shape for `avahi_reflector`, `avahi_hostname`, `avahi_use_ipv6`, `printers`, `log_level`. Include D-13's migration-suggestion note (reading `f1c878cb_cups`'s config) as a "Migrating from the third-party add-on" doc section — no existing analog for this subsection; write it fresh.

---

### `internal/base-image-config.yaml` (config, batch — modified, not new)

**Analog:** existing `gatus:` / `meridian:` / `network-tools:` entries in the same file (lines 17-33):
```yaml
  gatus:
    image: "ghcr.io/home-assistant/amd64-base"
    source_repo: "home-assistant/docker-base"
    source_file: "alpine/Dockerfile"
    version_pattern: 'ARG ALPINE_VERSION=(?P<version>\d+\.\d+)'
```
Add a `cups:` entry with the identical 4 lines (per D-06) — `cups` uses the same `amd64-base` (not `amd64-base-python`) since no Python runtime dependency exists at the OS-package level beyond what apk provides for the generator script (python3 is just an apk package, doesn't change which base-image family to track).

## Shared Patterns

### LABELS boilerplate (all Dockerfiles)
**Source:** `gatus/Dockerfile` (and every other add-on Dockerfile) — the `ARG BUILD_ARCH`...`LABEL io.hass.*` block at the bottom is byte-identical across add-ons. Copy verbatim into `cups/Dockerfile`.

### bashio config-read idiom
**Source:** `meridian/run.sh` — `bashio::config 'key'` for scalars, `bashio::config.true 'key'` for bool gating. Preferred over gatus's `python3 -c "import json..."` one-liners for simple scalar reads in shell; reserve Python (`generate_config.py`) for the templated file generation and the `printers` list iteration where JSON structure handling is easier in Python than bash/jq.

### Config-generation-before-exec startup shape
**Source:** `gatus/run.sh` — generate config file synchronously first, then `exec` the real daemon as PID 1 last so HA Supervisor's process supervision (restart policy, log capture) attaches to the actual service, not a wrapper shell. `cups/run.sh` should follow the same shape: generate `avahi-daemon.conf` → register printers via `lpadmin` → start `avahi-daemon` (backgrounded, like gatus backgrounds nginx) → `exec cupsd -f` last.

### 3-file version sync
**Source:** repo-wide convention (`config.yaml` `X.Y.Z-N`, `build.yaml` `args.VERSION` `X.Y.Z`, `README.md` badge `vX.Y.Z`) — for `cups`, since there is no `args.VERSION` (apk-only per D-06), the version sync applies only to `config.yaml`'s subpatch and `README.md` badge; `build.yaml` carries no `VERSION` arg (matches `network-tools/build.yaml`, not `gatus/build.yaml`). Confirm this nuance with `make validate-versions` behavior before finalizing — may need `internal/validate-versions.sh` inspection during planning if it hard-requires an `args.VERSION` field.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| Migration-suggestion output (D-13: reading live `f1c878cb_cups` config, printing suggested `printers` YAML) | utility (one-off rollout script or doc instructions) | transform | No existing add-on in this repo reads another add-on's live Supervisor config and emits a migration snippet — this is a rollout-time, possibly manual/ad-hoc step (e.g. `ha apps info f1c878cb_cups` inspected by hand) rather than a repo file with a prior pattern. Planner should treat this as a rollout task/checklist item, not a source file with an analog.

## Metadata

**Analog search scope:** `gatus/`, `meridian/`, `network-tools/`, `phone-logger/`, `internal/base-image-config.yaml`
**Files scanned:** gatus/{Dockerfile,run.sh,generate_config.py,config.yaml,build.yaml,nginx.conf,README.md,DOCS.md}, meridian/{Dockerfile,run.sh,config.yaml}, network-tools/{Dockerfile}, phone-logger/config.yaml, internal/base-image-config.yaml, cups/DIAGNOSIS.md
**Pattern extraction date:** 2026-09-26
**Tracked-source verification:** all named analog paths confirmed via `git ls-files` (gatus/*, meridian/*, network-tools/*, phone-logger/config.yaml, internal/base-image-config.yaml all tracked; no gitignored mirrors involved)
</content>
