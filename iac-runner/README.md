# IaC Runner

[![Release][release-shield]][release] ![Project Stage][project-stage-shield]
![Supports amd64 Architecture][amd64-shield]

Bearer-authenticated OpenTofu/Terraform runner for homelab IaC against R2/S3/local state backends.
Tailscale-bind-gated, no `SUPERVISOR_TOKEN` required.

## About

The runner exposes a versioned JSON-over-HTTP API on port 8125 (distinct from `terraform-bridge`'s 8124 so both add-ons
can coexist on the same HA host). Phase 16 ships the authentication, state-backend configuration, and healthcheck
surface. Phase 17 adds `POST /v1/plan` + `POST /v1/apply` with per-repo mutex; Phase 18 adds MQTT Discovery (three
sensors + two buttons).

Plain HTTP; TLS termination is out of scope (network-layer access control via Tailscale ACL or LAN).

## Features

- 256-bit bearer-token auth (SHA-256 hash on disk, `crypto/subtle.ConstantTimeCompare` validation, 24h rotation grace)
- Three state backends: R2 (Cloudflare, S3-compatible, default), S3 (any provider), local (`/data/terraform.tfstate`)
- `use_lockfile` semantics for R2/S3 (no DynamoDB required); file-based lock for local
- Tailscale-bind-gate: auto-detects the first `tailscale*` interface in `/sys/class/net`; refuses `0.0.0.0` at startup
- `/data/keys/` chmod-600 enforcement (fail-fast at startup)
- Log scrubbing (key-name mask for Authorization/Bearer/token/password/key/secret) — case-insensitive
- SIGTERM 30s drain + SIGHUP log-reopen handler

## Install

1. In the HA UI: **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and add
   `https://github.com/akentner/homeassistant-addons`.
2. Search for **IaC Runner** in the Add-on Store, click it, then **Install**.
3. Start the add-on. The first start generates a fresh bearer token (see First-time setup below).

## First-time setup

1. On the HA host shell, retrieve the freshly generated bearer from the add-on log:
   `sudo ha addons logs iac-runner | grep iac_runner.token.issued`
   The log line carries a 3+3-char preview (`preview`) and the `actor_token_fp` (SHA-256[8] hex).
   **The plaintext token itself appears ONLY in this single log line** — subsequent restarts do NOT re-emit it.
2. Copy the value into your CI's `IAC_RUNNER_BEARER` secret (or the equivalent for your orchestrator).
3. Optionally delete the `/data/initial-iac-runner-token` file to minimize on-disk exposure.

## Configuration

See [DOCS.md](DOCS.md) for the full operator reference: every config option with example, every HTTP endpoint, the
bearer-token issuance + rotation flow, the `/data/keys/` chmod-600 requirement per backend, the three state backends
with `use_lockfile` semantics, and the log-scrubbing invariant.

[release-shield]: https://img.shields.io/badge/version-v0.1.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v0.1.0
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-orange.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
