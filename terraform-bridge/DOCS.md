# Configuration

The Terraform Bridge add-on translates `Authorization: Bearer <token>` requests from the OpenTofu/Terraform provider
into HA Supervisor HTTP API calls authenticated by `SUPERVISOR_TOKEN`. This document covers the user-facing
configuration of the add-on, the bearer-token lifecycle (issuance, rotation, recovery), the `/v1/*` endpoint reference,
the per-`error_code` troubleshooting cross-link table, observed issues from the live verify suite, the state-management
surface, and the HA backup integration.

## Options

`bind_address` (default `auto`)

: The interface IP the Bridge binds to. `auto` (default) auto-detects the first `tailscale*` interface in
`/sys/class/net` and uses its IPv4 address. An explicit IP is accepted only if it belongs to a Tailscale interface OR
falls inside one of `bind_allowed_subnets`. `bind_address: "0.0.0.0"` is **always refused** regardless of
`bind_allowed_subnets` — strict reading of PITFALLS S-4. Misconfiguration is fatal at startup (no degraded mode).

`bind_allowed_subnets` (default `[]`)

: A list of CIDR strings (e.g. `["192.168.1.0/24", "10.0.0.0/8"]`) that broaden the bind gate beyond Tailscale. Useful
when the Provider runs on a LAN device that cannot reach Tailscale. Each entry is logged at startup. **This is a Phase-1
escape hatch, not a relaxation of the strict-by-default policy** — every entry must be deliberate.

`critical_addons` (default `["core_mosquitto", "core_zigbee2mqtt", "core_esphome"]`)

: Add-on slugs the Bridge refuses to uninstall without a fresh `X-Force-Destroy` nonce. The default list covers the
add-ons whose removal would take down the most common HA installations (MQTT broker, Zigbee gateway, ESPHome). Operators
can append additional slugs; the verify suite's test add-on (`local_test-addon`) is **never** in this list (per Pitfall
4 — the suite needs to uninstall the test add-on between iterations without operator intervention).

`install_job_timeout_seconds` (default `300`)

: Per-install polling budget. The Bridge polls Supervisor's `/jobs/{id}` after issuing an install; if the job does not
reach a terminal state within this budget, the Bridge returns `504` with `error_code: "install_timeout"`. The Supervisor
job may continue server-side; operators can re-read state via `GET /v1/state/index` to see the eventual outcome. The
verify suite's [`09-install-timeout.sh`](../internal/verify-bridge-e2e/09-install-timeout.sh) is the synthetic scenario
that captures this surface.

`try_lock_timeout_seconds` (default `5`)

: Per-slug mutex wait budget. When the Bridge receives a mutating call (start, stop, uninstall, options) for a slug that
already has an in-flight operation, the handler waits up to this duration for the in-flight op to release the mutex. On
timeout the Bridge returns `423` with `error_code: "locked"`. The provider's middleware waits on this surface — in
normal Provider usage the operator does not see 423 because the per-slug mutex serializes operations transparently. The
verify suite's [`06-locked.sh`](../internal/verify-bridge-e2e/06-locked.sh) proves the mutex path.

The schema uses the YAML-list form (`- "str"`), not the string `list(str)` form. Supervisor's schema parser treats the
string `list(<inner>)` as a one-value enum (split on `|`); the YAML-list form correctly validates each element as `str`.
See `supervisor/apps/options.py` (`isinstance(typ, list)` → `_nested_validate_list` branch).

## Token issuance

On first start the Bridge generates a 256-bit bearer token via `crypto/rand`, encodes it base64url (43 chars, no
padding), writes its SHA-256 hash to `/data/bridge-token` (chmod 600), and writes the plaintext to `/data/initial-token`
(chmod 600). The plaintext **never enters a log stream** — the log record carries only the 16-char fingerprint, a
3+3-char preview, and the file path:

```json
{
  "ts": "...",
  "level": "INFO",
  "msg": "bridge.token.issued",
  "actor_token_fp": "...",
  "preview": "abc...xyz",
  "path": "/data/initial-token"
}
```

`/data/initial-token` is the canonical operator-side source for the plaintext. **To retrieve the plaintext** (one-time
per fresh install), read it via one of:

```bash
# From the HA host shell — the add-on's /data volume is mounted under
# /usr/share/hassio/addons/data/<slug>/ on the host.
sudo cat /usr/share/hassio/addons/data/terraform-bridge/initial-token

# Or, from inside the running container via the Supervisor CLI:
ha addons cli terraform-bridge cat /data/initial-token
```

After configuring your provider with the token, **delete the file** to minimise on-disk exposure:

```bash
sudo rm /usr/share/hassio/addons/data/terraform-bridge/initial-token
```

Subsequent restarts do NOT re-emit the `bridge.token.issued` record and do NOT re-write `/data/initial-token` — both
events fire exactly once per fresh install. Once the plaintext file is gone, recovery is the uninstall/reinstall flow
described below.

## Token rotation

To rotate the bearer token (routine hygiene or in response to a compromise suspicion), call `POST /v1/auth/rotate` with
the **current** bearer token in the `Authorization` header:

```bash
BRIDGE=https://bridge.akentner.ts.net:8124
TOKEN=<current-token>

curl -X POST -H "Authorization: Bearer $TOKEN" "$BRIDGE/v1/auth/rotate"
```

The response is:

```json
{
  "new_token": "<the-new-token>",
  "grace_expires_at": "2026-09-01T12:34:56Z",
  "old_token_valid_until": "2026-09-01T12:34:56Z"
}
```

For the next 24 hours (the grace window), **both** the old and the new token authenticate successfully. This grace
window is persisted in `/data/bridge-token.grace` (chmod 600) and survives Bridge restart — a provider apply
mid-rotation cannot lock out a still-valid token. After 24 hours the old token stops authenticating and returns
HTTP 401.

**Capture the `new_token` immediately.** It is surfaced exactly once — there is no log line, no Options UI entry, no
second chance. Update your provider's `bearer_token` argument before the grace window expires.

The Phase 14 verify run exercised the round-trip empirically on a live Bridge. The empirical observation was: a single
`POST /v1/auth/rotate` returns the new plaintext in the response body exactly once; the `bridge.token.rotated` log line
carries only the old + new token fingerprints (16-char each), never plaintext; the grace window was observed to persist
across a Bridge restart (a forced `ha addons restart terraform-bridge` did not invalidate the old token during its 24h
grace).

Rotation requires an existing valid bearer. There is no break-glass path for anonymous rotation — see the recovery
section below for total token loss.

## Token recovery

If the bearer token is lost (HA backup restored to a host that did not preserve `/data`, an accidental
`rm /data/bridge-token`, or simply missing the `bridge.token.issued` line on first start), the only recovery path in
Phase 1 is **uninstall and reinstall the add-on**:

1. In the HA UI: Settings → Add-ons → Terraform Bridge → Uninstall
2. Reinstall the add-on (the same `akentner/homeassistant-addons` repository)
3. Start it — a fresh `bridge.token.issued` line appears in the log
4. Capture the new plaintext and update the provider

Uninstall + reinstall destroys `/data` (HA Supervisor's add-on volume), which is why the recovery path is destructive.
There is no CLI-based token reset because no anonymous endpoint exists.

The Phase 12 `X-Force-Destroy` nonce flow provides authorized rotation against add-ons in `critical_addons` (POST
/v1/auth/nonce → use the nonce in the `X-Force-Destroy` header on the destructive call). It does NOT bypass token loss
for the Bridge itself — recovery from a lost Bridge token still requires uninstall + reinstall.

## Endpoints reference

Every `/v1/*` route exposed by the Bridge, with method, auth requirement, request shape, and response shape. The
response shape fields are pulled verbatim from `terraform-bridge/contract/types.go` — there is no paraphrasing.

| Method | Path                          | Auth   | Request                       | Response                                                |
| ------ | ----------------------------- | ------ | ----------------------------- | ------------------------------------------------------- |
| `GET`  | `/healthz`                    | none   | —                             | `HealthResponse`                                        |
| `GET`  | `/`                           | none   | —                             | Plaintext version + DOCS.md pointer                     |
| `GET`  | `/v1/info`                    | none   | —                             | `BridgeInfo` (build metadata)                           |
| `GET`  | `/v1/version`                 | bearer | —                             | `VersionHandshake` (min/max_provider_version)           |
| `GET`  | `/v1/whoami`                  | bearer | —                             | `TokenResponse` (SHA-256[8] of bearer)                  |
| `GET`  | `/v1/addons`                  | bearer | —                             | Array of `AddOnInfo`                                    |
| `GET`  | `/v1/addons/{slug}/info`      | bearer | —                             | `AddOnInfo` (see `contract/types.go`)                   |
| `GET`  | `/v1/state/index`             | bearer | —                             | `StateIndexResponse`                                    |
| `POST` | `/v1/auth/nonce`              | bearer | —                             | `NonceResponse` (TTL 60s)                               |
| `POST` | `/v1/auth/rotate`             | bearer | —                             | `RotateResponse` (24h grace)                            |
| `POST` | `/v1/addons/{slug}/install`   | bearer | —                             | `JobStatus` (polls until `install_job_timeout_seconds`) |
| `POST` | `/v1/addons/{slug}/start`     | bearer | —                             | `JobStatus`                                             |
| `POST` | `/v1/addons/{slug}/stop`      | bearer | —                             | `JobStatus`                                             |
| `POST` | `/v1/addons/{slug}/uninstall` | bearer | `X-Force-Destroy: <nonce>`    | `JobStatus` (destructive)                               |
| `POST` | `/v1/addons/{slug}/options`   | bearer | `application/json` (new opts) | `JobStatus` (destructive)                               |

Every error response (4xx, 5xx) carries the `ErrorResponse` envelope:

```json
{
  "error_code": "snake_case_error_code",
  "message": "human-readable message (optional)",
  "request_id": "uuid for log correlation (optional)"
}
```

The `request_id` field is the same UUID the Bridge's `RequestLogger` middleware stamps on the request; operators can
grep the Bridge logs for the `request_id` to find the full request trace.

## Troubleshooting

The provider surfaces every Bridge error as a typed Diagnostic with a `Link` field pointing at the provider's [DOCS.md
troubleshooting table][provider-troubleshooting]. The per-`error_code` Summary text is **owned by the provider** (single
source of truth in `terraform-provider-homeassistant/internal/diagnostics/doc.go`) — the Bridge DOCS.md does not
duplicate the text. The table below is a cross-link index: every `error_code` produced by the Bridge, with its
kebab-case anchor in the provider's DOCS.md.

| `error_code`                              | HTTP | Anchor (provider DOCS.md)                   |
| ----------------------------------------- | ---: | ------------------------------------------- |
| `unauthorized`                            |  401 | `#troubleshooting-unauthorized`             |
| `not_found`                               |  404 | `#troubleshooting-not-found`                |
| `critical_addon_protected`                |  403 | `#troubleshooting-critical-addon-protected` |
| `prevented_destroy`                       |  403 | `#troubleshooting-prevented-destroy`        |
| `already_installed`                       |  409 | `#troubleshooting-already-installed`        |
| `locked`                                  |  423 | `#troubleshooting-locked`                   |
| `nonce_expired`                           |  401 | `#troubleshooting-nonce-expired`            |
| `nonce_used`                              |  401 | `#troubleshooting-nonce-used`               |
| `install_timeout`                         |  504 | `#troubleshooting-install-timeout`          |
| `upstream_error`                          |  502 | `#troubleshooting-upstream-error`           |
| `pwned` (Warning)                         |  200 | `#troubleshooting-pwned`                    |
| `version_below_min` / `version_above_max` |  401 | `#troubleshooting-version`                  |

[provider-troubleshooting]:
  https://github.com/akentner/homeassistant-addons/blob/main/terraform-provider-homeassistant/DOCS.md#troubleshooting

For every per-`error_code` Summary text, the canonical source is the provider's `internal/diagnostics/doc.go`. The
verify suite in `internal/verify-bridge-e2e/` (one scenario per `error_code`) empirically captures the Bridge response
into `terraform-bridge/internal/testdata/diagnostics/<error_code>.txt` for post-mortem review.

## Observed issues

Issues observed during the Phase 14 verify run. Each entry names the surface, the symptom, the root cause, and the
remediation. Operators who hit a `tofu apply` failure should grep this section for the matching `error_code` first.

1. **`unauthorized` immediately after a Bridge restart.** Symptom: the provider surfaces a
   `troubleshooting-unauthorized` diagnostic on its very first call. Root cause: the operator forgot to update the
   provider's `bearer_token` after a token rotation OR the operator restored an HA backup whose `/data/bridge-token`
   does not match the current provider's `bearer_token`. Remediation: re-run `POST /v1/auth/rotate` (preserves the grace
   window for still-valid old tokens) OR retrieve a fresh plaintext from `/data/initial-token` if the file still exists.

2. **`install_timeout` after a long Supervisor install.** Symptom: a fresh `tofu apply` for a heavy-weight add-on (e.g.
   a 500MB image) returns `504 install_timeout` after `install_job_timeout_seconds` (default 300). Root cause: the
   Bridge's polling loop exceeded the budget; the Supervisor job may still be running server-side. Remediation: re-run
   `tofu apply` — the provider's adoption path (PROV-05) treats the second `409 already_installed` as success and reads
   the eventual state. If the install genuinely failed server-side, the second apply's `GET /v1/addons/{slug}/info` will
   surface the failure mode via the `state` field.

3. **`upstream_error` after a Supervisor restart.** Symptom: every Bridge call returns `502 upstream_error` for a few
   seconds after Supervisor restarts. Root cause: the Bridge's supervisor client returns `ErrTransient` (mapped to
   `upstream_error`) when Supervisor is unreachable. The Bridge's `/healthz` endpoint surfaces the upstream reachability
   state explicitly. Remediation: retry per the provider operation timeout (`terraform-plugin-framework-timeouts`); the
   Bridge recovers automatically once Supervisor is back.

4. **`pwned` Warning on a legitimate options change.** Symptom: `tofu apply` succeeds (exit 0) with a Warning diagnostic
   on stdout carrying `PwnedWarningText`. Root cause: the add-on's options payload matches an entry in the Bridge's
   pwned-credentials dataset (Hibp-style). Remediation: rotate the add-on's credentials, then re-apply with the rotated
   values. The apply proceeds — Warnings do not block the apply.

5. **Operator's `bind_address: "0.0.0.0"` is rejected at startup.** Symptom: the Bridge fails to start, the supervisor
   logs a fatal error mentioning the bind gate. Root cause: the bind-gate enforces PITFALLS S-4 — `0.0.0.0` is always
   refused regardless of `bind_allowed_subnets`. Remediation: set `bind_address: "auto"` (Tailscale auto-detect) or an
   explicit IP that belongs to a Tailscale interface OR falls inside one of the `bind_allowed_subnets`.

## State management

The Bridge maintains the OpenTofu state file at `/data/terraform.tfstate` (chmod 600). Every mutating call (install,
start, stop, uninstall, options) updates this file on success. The provider reads it back at the start of every apply —
the resource's last-known state is the source of truth for "already-installed?" adoption decisions (PROV-05).

`GET /v1/state/index` returns the current state-file inventory: every `.tfstate` and `.tfstate.bak.*` file under `/data`
with its size, mtime, and SHA-256 fingerprint. Operators can use this to confirm the state file exists after a Bridge
restart, or to detect corruption (mtime older than the last provider apply suggests the Bridge has not been writing
state).

The verify suite's `_lib.sh::snapshot_state` copies the live state to `/data/terraform.tfstate.bak.<scenario>` before
any destructive scenario; `_lib.sh::fingerprint_state` captures the post-scenario state via `GET /v1/state/index`. Plan
03's `99-cleanup.sh` removes `.tfstate.bak.*` files older than 7 days.

The state file is HA-backup-eligible (see HA backup integration below) — restoring an HA backup restores the Bridge's
state file as part of the add-on's `/data` mount.

## HA backup integration

`addon_config:rw` mount contents — including `terraform.tfstate`, `bridge-token`, `bridge-token.grace`,
`bridge-nonce-audit.json`, and `initial-token` (if still present) — are **auto-included** in
`ha backups new --app terraform-bridge` per the Phase 9 §pending-spike §10 result (CF-13).

Implications for operators:

- An HA backup captures the Bridge's current state, the active + grace tokens, and the nonce audit log. Restoring the
  backup to a fresh host brings the Bridge + provider back online without a token rotation, provided the operator still
  has the same `bearer_token` configured in the provider.
- The plaintext `initial-token` is captured by the backup while it exists. Delete the file promptly after retrieving the
  plaintext to keep it out of long-term backups.
- Restoring an HA backup to a host where the operator does NOT have the same `bearer_token` requires the recovery flow:
  the active `bridge-token` is on disk, but the operator cannot read it without the Bridge add-on running and the
  `/v1/whoami` + `/v1/auth/rotate` round-trip.

For automated daily backups that exclude the plaintext `initial-token`, operators can add a post-restore hook that
deletes the file (the Bridge re-emits `bridge.token.issued` only on a fresh install, not on a backup-restore).

## Health check

`GET /healthz` returns HTTP 200 with body `{"status":"ok","supervisor_reachable":true,"bridge_version":"X.Y.Z"}` when
the Bridge can reach Supervisor via `/supervisor/ping` within a 2-second budget. Returns HTTP 503 with empty body when
Supervisor is unreachable. HA Supervisor's health-check polls this endpoint on the configured cadence. The verify
suite's pre-flight gate (`_lib.sh::preflight`) uses `/healthz` to confirm readiness before entering the empirical loop.

## Logs

Every Bridge request produces one structured JSON log record with the fields `ts`, `level`, `msg`, `request_id`,
`route`, `method`, `status`, `duration_ms`. The `bridge.token.issued` and `bridge.token.rotated` records carry audit
fingerprints only — no plaintext tokens ever appear in logs after the one-shot issuance line. The `bridge.request`
record emitted by the `RequestLogger` middleware surfaces the same `request_id` the `ErrorResponse` envelope carries, so
operators can grep the Bridge logs for `request_id=<id>` to find the full request trace.

## Add-on network access

The Bridge is **not** served through HA Ingress. Configure port 8124 to be reachable from the OpenTofu client
(Tailscale, LAN, or a reverse proxy). Plain HTTP — TLS termination is out of scope for v1.3. Operators running the
provider on a LAN device that cannot reach Tailscale should set `bind_allowed_subnets` to the LAN CIDR (e.g.
`["192.168.1.0/24"]`) and the provider's `bridge_url` to the LAN IP (e.g. `http://192.168.1.10:8124`).
