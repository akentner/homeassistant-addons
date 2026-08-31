# Home Assistant Add-on: Terraform Bridge

[![Release][release-shield]][release] [![License][license-shield]][license] ![Project Stage][project-stage-shield]
![Project Maintenance][maintenance-shield]

Bearer-authenticated JSON proxy of the Home Assistant Supervisor HTTP API, designed to be managed declaratively via the
co-located
[`terraform-provider-homeassistant`](https://github.com/akentner/homeassistant-addons/tree/main/terraform-provider-homeassistant).

## About

This add-on exposes a versioned JSON-over-HTTP API on port 8124 that mirrors the Supervisor `/apps`, `/store`, `/info`,
and `/jobs` endpoints. The OpenTofu/Terraform provider sends `Authorization: Bearer <token>` requests to this port; the
Bridge translates them into Supervisor requests authenticated by `SUPERVISOR_TOKEN`.

**Phase 9 status:** Scaffold only. The Bridge currently exposes a single `GET /` placeholder and accepts no
authenticated traffic. Token issuance, version handshake, and the read/write API land in Phases 10-12.

## Features (Phase 1 scope)

- Bearer-authenticated JSON proxy of Supervisor HTTP API
- Async job polling with typed diagnostic forwarding
- Schema-version handshake preventing provider/bridge version drift
- Per-slug write mutex preventing concurrent Provider applies from corrupting Supervisor job state
- `homeassistant_addon` resource (CRUD) + read-only data sources

## Direct Access

The Bridge is not exposed through HA Ingress. Configure port 8124 to be reachable from the OpenTofu client (Tailscale,
LAN, or a reverse proxy). Plain HTTP; TLS termination is out of scope for v1.3.

## Configuration

See [DOCS.md][docs]. Phase 9 ships with no user-facing options (empty schema); operator-configurable options land in
Phase 10 (`bind_address`).

[release-shield]: https://img.shields.io/badge/version-v0.1.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v0.1.0
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-orange.svg
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[license-shield]: https://img.shields.io/badge/license-MIT-green.svg
[license]: https://github.com/akentner/homeassistant-addons/blob/main/LICENSE
[docs]: https://github.com/akentner/homeassistant-addons/blob/main/terraform-bridge/DOCS.md
