# Terraform Bridge

[![Release][release-shield]][release] [![License][license-shield]][license] ![Project Stage][project-stage-shield]
![Project Maintenance][maintenance-shield]

Bearer-authenticated JSON proxy of the Home Assistant Supervisor HTTP API, designed to be managed declaratively via the
co-located [terraform-provider-homeassistant][provider-repo] OpenTofu/Terraform provider.

## About

The Bridge exposes a versioned JSON-over-HTTP API on port 8124 that mirrors the Supervisor `/apps`, `/store`, `/info`,
and `/jobs` endpoints. The provider sends `Authorization: Bearer <token>` requests; the Bridge translates them into
Supervisor calls authenticated by `SUPERVISOR_TOKEN`.

Plain HTTP; TLS termination is out of scope for v1.3. The Bridge is **not** exposed through HA Ingress — port 8124 must
be reachable from the OpenTofu client (Tailscale, LAN, or reverse proxy).

## Features

- Bearer-authenticated JSON proxy of the Supervisor HTTP API
- Schema-version handshake preventing provider/bridge drift
- Per-slug write mutex preventing concurrent provider applies from corrupting Supervisor job state
- `homeassistant_addon` resource (CRUD) + read-only data sources

## Install

1. In the HA UI: **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and add
   `https://github.com/akentner/homeassistant-addons`.
2. Search for **Terraform Bridge** in the Add-on Store, click it, then **Install**.
3. Start the add-on. The first start generates a fresh bearer token (see First-time setup below).

## First-time setup

1. On the HA host shell, retrieve the freshly generated bearer:
   `sudo cat /usr/share/hassio/addons/data/terraform-bridge/initial-token`
2. Copy the value into the provider's `bearer_token` argument (and the `bridge_url` argument set to the Bridge's
   reachable URL — default `https://ha-nextgen.akentner.ts.net:8124`).
3. **Delete the file** to minimise on-disk exposure:
   `sudo rm /usr/share/hassio/addons/data/terraform-bridge/initial-token`

Subsequent restarts do not re-emit the token. If the file is lost, see the recovery flow in
[DOCS.md](DOCS.md#token-recovery).

## Configuration

See [DOCS.md](DOCS.md) for the full operator reference: every option, every `/v1/*` endpoint, the per-`error_code`
troubleshooting cross-link table, the state-management surface, and the HA backup integration notes.

[release-shield]: https://img.shields.io/badge/version-v0.2.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v0.2.0
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-orange.svg
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[license-shield]: https://img.shields.io/badge/license-MIT-green.svg
[license]: https://github.com/akentner/homeassistant-addons/blob/main/LICENSE
[provider-repo]: https://github.com/akentner/homeassistant-addons/tree/main/terraform-provider-homeassistant
