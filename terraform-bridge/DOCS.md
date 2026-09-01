# Configuration

The Terraform Bridge add-on translates `Authorization: Bearer <token>` requests from the OpenTofu/Terraform provider
into HA Supervisor HTTP API calls authenticated by `SUPERVISOR_TOKEN`. This document covers the user-facing
configuration of the add-on plus the bearer-token lifecycle (issuance, rotation, recovery). Empirical HA-host
verification, per-error-code remediation, and the full troubleshooting section are deferred to Phase 14.

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

**To retrieve the plaintext** (one-time per fresh install), read `/data/initial-token` via one of:

```bash
# From the HA host shell — the add-on's /data volume is mounted under
# /usr/share/hassio/addons/data/<slug>/ on the host.
sudo cat /usr/share/hassio/addons/data/terraform-bridge/initial-token

# Or, from inside the running container via the Supervisor CLI:
ha addons cli terraform-bridge cat /data/initial-token
```

After configuring your Provider with the token, **delete the file** to minimise on-disk exposure:

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
window is persisted in `/data/bridge-token.grace` (chmod 600) and survives Bridge restart — a Provider apply
mid-rotation cannot lock out a still-valid token. After 24 hours the old token stops authenticating and returns
HTTP 401.

**Capture the `new_token` immediately.** It is surfaced exactly once — there is no log line, no Options UI entry, no
second chance. Update your Provider's `bearer_token` argument before the grace window expires.

Rotation requires an existing valid bearer (D-12). There is no break-glass path for anonymous rotation — see the
recovery section below for total token loss.

## Token recovery

If the bearer token is lost (HA backup restored to a host that did not preserve `/data`, an accidental
`rm /data/bridge-token`, or simply missing the `bridge.token.issued` line on first start), the only recovery path in
Phase 1 is **uninstall and reinstall the add-on**:

1. In the HA UI: Settings → Add-ons → Terraform Bridge → Uninstall
2. Reinstall the add-on (the same `akentner/homeassistant-addons` repository)
3. Start it — a fresh `bridge.token.issued` line appears in the log
4. Capture the new plaintext and update the Provider

Uninstall + reinstall destroys `/data` (HA Supervisor's add-on volume), which is why the recovery path is destructive.
There is no CLI-based token reset because no anonymous endpoint exists (D-12).

Phase 2+ may add an `X-Force-Destroy` nonce flow that enables authorized rotation without an existing bearer; out of
scope for Phase 1.

## Health check

`GET /healthz` returns HTTP 200 with body `{"status":"ok","supervisor_reachable":true,"bridge_version":"X.Y.Z"}` when
the Bridge can reach Supervisor via `/supervisor/ping` within a 2-second budget. Returns HTTP 503 with empty body when
Supervisor is unreachable. HA Supervisor's health-check polls this endpoint on the configured cadence.

## Logs

Every Bridge request produces one structured JSON log record with the fields `ts`, `level`, `msg`, `request_id`,
`route`, `method`, `status`, `duration_ms`. The `bridge.token.issued` and `bridge.token.rotated` records carry audit
fingerprints only — no plaintext tokens ever appear in logs after the one-shot issuance line.

## Add-on network access

The Bridge is **not** served through HA Ingress. Configure port 8124 to be reachable from the OpenTofu client
(Tailscale, LAN, or a reverse proxy). Plain HTTP — TLS termination is out of scope for v1.3.
