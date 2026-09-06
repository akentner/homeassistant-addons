# IaC Runner — Operator Documentation

## Overview

Bearer-authenticated OpenTofu/Terraform runner for homelab IaC against R2/S3/local state backends. The runner exposes a
JSON-over-HTTP API on port 8125 (distinct from `terraform-bridge`'s 8124) for plan/apply jobs in Phase 17+. Phase 16
ships the authentication, state-backend configuration, and healthcheck surface; `/v1/plan` + `/v1/apply` land in Phase
17.

## Install

1. In the HA UI: **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and add
   `https://github.com/akentner/homeassistant-addons`.
2. Search for **IaC Runner** in the Add-on Store, click it, then **Install**.
3. Start the add-on. The first start generates a fresh bearer token (see First-time setup below).

## First-time setup

1. On the HA host shell, retrieve the freshly generated bearer from the add-on log:
   `sudo ha addons logs iac-runner | grep iac_runner.token.issued`
   The log line carries a 3+3-char preview (`preview`) and the `actor_token_fp` (SHA-256[8] hex) for correlation.
   **The plaintext token itself appears ONLY in this single log line** — subsequent restarts do NOT re-emit it.
2. For production use, copy the value into your CI's `IAC_RUNNER_BEARER` secret. The token file
   `/data/initial-iac-runner-token` (chmod 600) is written exactly once and contains the plaintext; operators SHOULD
   delete this file after configuring CI so the plaintext is not stored on disk any longer than necessary.

## Configuration

See `iac-runner/config.yaml` for the full schema. Every option is documented below with an example.

### `bind_address`

Default: `"auto"`. The address the runner binds to.

- `"auto"` (default): auto-detect the first `tailscale*` interface in `/sys/class/net` and bind to its IPv4 address.
  Recommended for Tailscale-only deployments.
- Explicit IP (e.g. `"100.64.0.1"`): bind to this specific IP. Accepted only if it belongs to a `tailscale*`
  interface OR falls inside one of the configured `bind_allowed_subnets`.
- `"0.0.0.0"`: **ALWAYS REFUSED** at startup regardless of `bind_allowed_subnets`. The runner exits with status 1 and
  a clear error message naming the refused value.

### `bind_allowed_subnets`

Default: `[]` (empty). List of CIDR strings (e.g. `["10.0.0.0/8", "192.168.0.0/16"]`). An explicit `bind_address` is
accepted if it falls inside one of these subnets OR belongs to a Tailscale interface. The `bind_allowed_subnets` does
NOT override the `0.0.0.0` refusal.

### `state_backend`

Default: `"r2"`. Selects the Terraform state backend. One of `"r2"`, `"s3"`, `"local"`.

- `state_backend: "r2"` (default): Cloudflare R2 via the S3-compatible API. Endpoint is constructed from
  `/data/keys/r2-account-id`. Uses `use_lockfile = true` (no DynamoDB required).
- `state_backend: "s3"`: any S3-compatible endpoint supplied via `s3_endpoint`. Uses `use_lockfile = true` (no
  DynamoDB required).
- `state_backend: "local"`: state stored at `/data/terraform.tfstate`. No external credentials required. Lock is
  file-based at `/data/terraform.tfstate.lock` (HA backup covers both files automatically).

Any other value is rejected at the HA Supervisor UI level (the `config.yaml` schema uses
`list(match(^(r2|s3|local)$))`) AND at runtime by `statebackend.New` (returns `ErrUnsupported`).

### `r2_bucket`

Required when `state_backend: "r2"`. The R2 bucket name (e.g. `"homelab-iac-state"`). The runner constructs the
endpoint as `https://<account_id>.r2.cloudflarestorage.com`; `<account_id>` is read from
`/data/keys/r2-account-id`.

### `s3_endpoint`, `s3_bucket`, `s3_region`

Required when `state_backend: "s3"`. The S3-compatible endpoint URL (e.g. `"https://s3.amazonaws.com"`), bucket name,
and region (e.g. `"us-east-1"`).

## State backend credential files

The runner reads credential files from `/data/keys/` (chmod 600 required, current process UID ownership required). On
startup, **non-conforming files cause startup failure** (exit 1) with a clear error message naming the offending file —
there is no degraded mode.

### R2 backend required files

| File | Mode | Notes |
| ------ | ------ | ------- |
| `/data/keys/r2-access.key` | 0600 | R2 access key ID (e.g. `AKIAEXAMPLE`) |
| `/data/keys/r2-secret.key` | 0600 | R2 secret access key (40+ chars base64) |
| `/data/keys/r2-account-id` | 0600 | Cloudflare account ID (32-char hex, plaintext non-sensitive) |

### S3 backend required files

| File | Mode | Notes |
| ------ | ------ | ------- |
| `/data/keys/s3-access.key` | 0600 | S3 access key ID |
| `/data/keys/s3-secret.key` | 0600 | S3 secret access key |

### Local backend required files

None. The local backend uses `/data/terraform.tfstate` (no external credentials).

## HTTP API

The runner exposes the following endpoints on port 8125:

| Method | Path | Auth | Description |
| -------- | ------ | ------ | ------------- |
| GET | `/` | none | Placeholder JSON with `runner_version`, `status`, `msg` |
| GET | `/healthz` | none | 200 + JSON when tofu on PATH AND `/data/keys/` chmod-600 passes; 503 empty body otherwise |
| POST | `/v1/auth/rotate` | Bearer | Issue a new bearer token; for 24h both old and new authenticate |
| GET | `/v1/version` | Bearer | Returns runner + schema + min/max supported OpenTofu versions |

### `/healthz` (no auth)

```bash
curl http://<runner-host>:8125/healthz
```

Returns 200 + JSON when BOTH checks pass:

```json
{
  "status": "ok",
  "tofu_on_path": true,
  "keys_chmod_600": true,
  "runner_version": "0.1.0"
}
```

Returns 503 with empty body when EITHER check fails (tofu binary missing from PATH, or any file under `/data/keys/` is
not chmod 600 owned by the current process UID). The 503 body is intentionally empty to avoid leaking internal state.

### `POST /v1/auth/rotate` (Bearer required)

```bash
curl -X POST -H "Authorization: Bearer <token>" http://<runner-host>:8125/v1/auth/rotate
```

Returns 200 + JSON:

```json
{
  "new_token": "...",
  "grace_expires_at": "2026-09-07T17:39:00Z",
  "old_token_valid_until": "2026-09-07T17:39:00Z"
}
```

The `new_token` plaintext appears in this response exactly once. After rotation, BOTH the old and the new token
authenticate for 24 hours (the grace window); after 24h the old token stops authenticating. Grace state persists in
`/data/iac-runner-token.grace` (chmod 600) and survives restart.

### `GET /v1/version` (Bearer required)

```bash
curl -H "Authorization: Bearer <token>" http://<runner-host>:8125/v1/version
```

Returns 200 + JSON:

```json
{
  "runner_version": "0.1.0",
  "schema_version": "1.0.0",
  "min_supported_opentofu": "1.6.0",
  "max_supported_opentofu": "1.999.0"
}
```

`schema_version` follows semver; bump MAJOR on every breaking change to the /v1/* HTTP API surface.

## State backend use_lockfile semantics

For R2 and S3 backends, the runner invokes `tofu` with `use_lockfile = true` so locking uses the native S3 object-lock
semantics (no DynamoDB required). For the local backend, locking is file-based at `/data/terraform.tfstate.lock`. HA
Supervisor's backup integration covers both files automatically.

Apply fails fast with HTTP 423 (`locked`) when another apply holds the lock. The `use_lockfile` semantics for R2 were
verified empirically in Phase 16 (IRUN-H-1 spike result documented in `16-SUMMARY.md`).

## Log scrubbing

The runner's structured JSON logger (stdlib `log/slog`) wraps every record through a key-name scrubber
(case-insensitive). Values for the keys `Authorization`, `Bearer`, `token`, `password`, `key`, `secret` are replaced
with `"<redacted>"` before serialization. A unit test asserts the invariant; `chi` middleware additionally strips the
`Authorization` request header from the per-request log snapshot.
