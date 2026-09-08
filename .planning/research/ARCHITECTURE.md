# Architecture: Terraform/OpenTofu Configuration Bridge

**Domain:** Home Assistant add-on exposing the Supervisor HTTP API as a stable, versioned JSON service consumable by an
external OpenTofu provider

**Milestone:** v1.3 opentofu-bridge (subsequent milestone, planning)

**Researched:** 2026-08-31

**Overall confidence:** HIGH (Supervisor API endpoints verified at
[developers.home-assistant.io/docs/api/supervisor/endpoints](https://developers.home-assistant.io/docs/api/supervisor/endpoints/);
Terraform framework patterns verified at developer.hashicorp.com; in-repo precedent from meridian, network-tools,
markdown-renderer, and the Phase 8 Cloudflare Access integration pattern)

---

## Summary

The `terraform-bridge` add-on is a thin HTTP service that lives inside the HA Supervisor network and exposes a versioned
JSON API over a single TCP port. The `terraform-provider-homeassistant` Go binary runs on a developer laptop (or CI
runner) and speaks to the Bridge over HTTPS using the standard Terraform plugin framework. Both artifacts share one
version (3-file scheme) and one release pipeline.

Two distinct auth flows are involved and must not be confused:

| Direction           | Auth                                        | Lifetime                                                      | Surface                                |
| ------------------- | ------------------------------------------- | ------------------------------------------------------------- | -------------------------------------- |
| Bridge → Supervisor | `Authorization: Bearer ${SUPERVISOR_TOKEN}` | Auto-injected by Supervisor into every add-on container's env | Bridge → `http://supervisor/`          |
| Provider → Bridge   | `Authorization: Bearer ${TF_BRIDGE_TOKEN}`  | Persistent; rotated via the add-on's Options UI               | Provider → `https://<ha-host>:<port>/` |

The Bridge adds **zero new capability** to HA — every Supervisor API call it issues is one a user could have issued
manually from a script with `SUPERVISOR_TOKEN`. The Bridge exists to give that capability a stable, schema-versioned,
authenticated, OpenTofu-consumable contract. Phase 1 covers `homeassistant_addon` (CRUD) and `homeassistant_repository`
(read; install from store is the only write). The HTTP state backend
([developer.hashicorp.com/terraform/language/backend/http](https://developer.hashicorp.com/terraform/language/backend/http))
gives us free state locking via `LOCK`/`UNLOCK` if we later want a remote-style backend.

**New components vs. existing patterns:**

| Component                                                 | Reuse from                          | New                                            |
| --------------------------------------------------------- | ----------------------------------- | ---------------------------------------------- |
| 4-file add-on skeleton                                    | meridian, markdown-renderer         | nothing new                                    |
| HTTP server inside the add-on                             | meridian:8099 / network-tools:18080 | —                                              |
| nginx reverse proxy + bashio config                       | meridian                            | —                                              |
| Bashio `bashio::services` / `bashio::api.supervisor` call | phone-logger                        | —                                              |
| 3-file versioning                                         | all add-ons                         | —                                              |
| Cloudflare Access service-token auth                      | Phase 8 `notify-ha.sh`              | nothing new (same pattern, different surface)  |
| Go provider with `terraform-plugin-framework`             | none in this repo                   | Terraform-plugin-framework v1.x                |
| HTTP state backend                                        | none in this repo                   | `http` backend in user `*.tf` config           |
| Bearer-token issuance + rotation UI                       | none                                | one HA option field + one Bridge HTTP endpoint |

**Confidence:** HIGH for the Supervisor API surface and the HTTP backend protocol (both primary-source verified). MEDIUM
for the exact Tailscale + Cloudflare Access composition on this repo's three hosts — Phase 8 set up CF Access for
webhooks only, and the Bridge needs a separate path-scoped Access app if exposed publicly. See Networking.

---

## Topology

### Where the components live

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Provider host (developer laptop / CI runner)                                 │
│                                                                              │
│   terraform-provider-homeassistant                                            │
│   ┌──────────────────────────────────────────────────────────┐                │
│   │  .terraform/providers/.../terraform-provider-homeassistant│              │
│   │   (Go binary, terraform-plugin-framework v1.x)            │               │
│   │                                                          │               │
│   │   main.tf:                                               │               │
│   │     terraform {                                          │               │
│   │       backend "local" {                                  │               │
│   │         path = "/some/path/terraform.tfstate"            │               │
│   │       }                                                  │               │
│   │     }                                                    │               │
│   │     provider "homeassistant" {                           │               │
│   │       endpoint = "https://haos-op3050-1:8124"            │               │
│   │       token    = var.bridge_token                        │               │
│   │     }                                                    │               │
│   │                                                          │               │
│   │   resource "homeassistant_addon" "mosquitto" {           │               │
│   │     slug    = "core_mosquitto"                           │               │
│   │     started = true                                       │               │
│   │     options = { log_level = "info" }                     │               │
│   │   }                                                      │               │
│   └──────────────────────────────────────────────────────────┘               │
│                                  │                                           │
│                                  │ HTTPS + Bearer                            │
│                                  │ (Tailscale:100.x or LAN or CF Access)    │
│                                  ▼                                           │
└──────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   │
                ┌──────────────────┴──────────────────┐
                │  Tailscale overlay / LAN / CF edge  │
                └──────────────────┬──────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ HA host (haos-op3050-1 / lxc-haos-104 / hassio-n2plus)                       │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │  Supervisor (PID 1 inside HA OS)                                    │     │
│  │                                                                     │     │
│  │  /store/addons/.../install   ┐                                      │     │
│  │  /addons/...                 │  HTTP+JSON, SUPERVISOR_TOKEN        │     │
│  │  /store/addons/.../install   │  ← from add-ons in same docker net   │     │
│  │  /supervisor/info            │                                      │     │
│  │                              │                                      │     │
│  │  internal docker network     │                                      │     │
│  │  supervisor hostname = "supervisor"                                │     │
│  └──────────────────────────────┼──────────────────────────────────────┘     │
│                                 │                                            │
│                                 │ docker network (DNS: supervisor)          │
│                                 ▼                                            │
│  ┌────────────────────────────────────────────────────────┐                 │
│  │  addon_local_terraform-bridge container                │                 │
│  │  ┌──────────────────────────────────────────────────┐  │                 │
│  │  │  bashio entrypoint                              │  │                 │
│  │  │    ↓                                             │  │                 │
│  │  │  generate_config.py (read options.json)          │  │                 │
│  │  │    ↓                                             │  │                 │
│  │  │  python -m terraform_bridge.app  (port 8124)     │  │                 │
│  │  │    ├── bearer-token middleware                   │  │                 │
│  │  │    ├── version endpoint (/v1/version)            │  │                 │
│  │  │    ├── addons read  →  GET /supervisor/addons... │  │                 │
│  │  │    ├── addons write →  POST /supervisor/...      │  │                 │
│  │  │    └── /v1/state (for HTTP backend; optional)    │  │                 │
│  │  │    ↑                                             │  │                 │
│  │  │  nginx (ingress only if used; otherwise omitted) │  │                 │
│  │  └──────────────────────────────────────────────────┘  │                 │
│  │   │                                                   │                 │
│  │   │ data volume: /data → host path /mnt/data/         │                 │
│  │   │                supervisor/addons/local_terraform-bridge/            │
│  │   │   ↳ token.json     (the bearer token, rotated)   │                 │
│  │   │   ↳ terraform.tfstate  (OpenTofu state file)     │                 │
│  │   │   ↳ audit.log      (one line per request)       │                 │
│  │   │   ↳ ca.pem         (if TLS enabled; see Auth)   │                 │
│  │   │                                                   │                 │
│  │   │ ingress: false                                   │                 │
│  │   │ ports: 8124/tcp: 8124                            │                 │
│  │   └───────────────────────────────────────────────────┘                 │
│  │          │                                                               │
│  │          │ host port 8124 (also reachable on Tailscale 100.x:8124)      │
│  │          ▼                                                               │
│  │     provider reaches HTTPS://<ha-host>:8124/                            │
│  └─────────────────────────────────────────────────────────────────────────┘
└──────────────────────────────────────────────────────────────────────────────┘
```

### Data flow per command

**`terraform plan`**

```
Provider
  1. Read .terraform/terraform.tfstate from local disk (if it exists)
  2. Read /v1/version on Bridge (check Bridge↔Provider compatibility)
  3. For each homeassistant_addon resource declared in *.tf:
     a. GET /v1/addons/<slug> on Bridge
        ↳ Bridge issues  GET  http://supervisor/addons/<slug>/info  + SUPERVISOR_TOKEN
        ↳ Supervisor returns AddonModel JSON
        ↳ Bridge caches the response, returns to Provider
     b. Provider diffs config vs. live state
  4. Emit plan: "create / update / no-op" per resource
```

**`terraform apply`**

```
Provider
  For each resource in plan:
    1. POST/PUT /v1/addons/<slug>... on Bridge
       ↳ Bridge maps HCL body → Supervisor API call:
          ├── install   → POST  http://supervisor/store/addons/<slug>/install
          ├── uninstall → POST  http://supervisor/addons/<slug>/uninstall?remove_config=true
          ├── start     → POST  http://supervisor/addons/<slug>/start
          ├── stop      → POST  http://supervisor/addons/<slug>/stop
          ├── restart   → POST  http://supervisor/addons/<slug>/restart
          └── options   → POST  http://supervisor/addons/<slug>/options
                            { options: { ...hcl fields... } }
       ↳ Supervisor returns { result: "ok", job_id: "..." } (some are async)
       ↳ For async ops (install/update): Bridge polls  GET http://supervisor/jobs/<job_id>
                                          until state ∈ {done, error}, with bounded timeout
       ↳ Bridge returns 200 { slug, state, version, options } to Provider
    2. Provider writes new state to .terraform/terraform.tfstate (local backend)
       — OR — to /v1/state on the Bridge (http backend)
```

**`terraform refresh`** (deprecated in favor of `terraform apply -refresh-only`)

```
Same as plan, but step 1 is skipped and the live state is treated as authoritative.
```

### Async Supervisor jobs

Three Supervisor calls return immediately with a `job_id`: `store/addons/<slug>/install`, `store/addons/<slug>/update`,
and `store/reload`. The Bridge polls `GET /jobs/<job_id>` until completion. From the Terraform side, `Apply` blocks
until the Bridge returns — this is acceptable because Terraform already expects provisioning to be sequential within a
resource. The Phase 1 polling budget should be 10 minutes (most installs complete in <60s; image pulls from ghcr.io
dominate).

---

## Supervisor API Mapping

### Phase 1 endpoint inventory

All calls are `http://supervisor/<path>` from inside the Bridge container, with
`Authorization: Bearer ${SUPERVISOR_TOKEN}` injected by Supervisor. The Bridge maps each call to a versioned URL under
`/v1/...` on its own listener.

| Terraform action on `homeassistant_addon`      | Supervisor HTTP call                                             | Phase 1?        | Notes                                                                                                                                                                   |
| ---------------------------------------------- | ---------------------------------------------------------------- | --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `terraform plan` (read)                        | `GET /addons`                                                    | ✓               | List all installed add-ons; Provider matches by `slug`.                                                                                                                 |
| `terraform plan` (read)                        | `GET /addons/<slug>/info`                                        | ✓               | The canonical "live state" of one add-on. Returns full `AddonModel` (slug, version, state, options, schema, …).                                                         |
| `terraform plan` (read)                        | `GET /store/addons`                                              | ✓               | Catalog of all store-available add-ons. Used to validate `slug` exists before `apply`.                                                                                  |
| `terraform apply` (create)                     | `POST /store/addons/<slug>/install` body `{"background": false}` | ✓               | `background: false` makes Supervisor block until install completes — no need for Provider-side polling, but Bridge still polls `/jobs/<job_id>` for error detail.       |
| `terraform apply` (delete)                     | `POST /addons/<slug>/uninstall` body `{"remove_config": true}`   | ✓               | `remove_config: true` deletes `/data` so re-install starts from defaults.                                                                                               |
| `terraform apply` (start)                      | `POST /addons/<slug>/start`                                      | ✓               | Sync call; returns immediately.                                                                                                                                         |
| `terraform apply` (stop)                       | `POST /addons/<slug>/stop`                                       | ✓               | Sync call.                                                                                                                                                              |
| `terraform apply` (restart)                    | `POST /addons/<slug>/restart`                                    | ✓               | Sync call.                                                                                                                                                              |
| `terraform apply` (update options)             | `POST /addons/<slug>/options` body `{"options": {...}}`          | ✓               | JSON dict mirroring `options` from `config.yaml`. Other keys (`boot`, `auto_update`, `watchdog`) accepted by Supervisor but Phase 1 ignores them — they're for Phase 2. |
| `terraform apply` (validate options pre-apply) | `POST /addons/<slug>/options/validate` body `{"options": {...}}` | ✓ (recommended) | Bridge calls this before `POST /options` to surface schema-validation errors as typed diagnostics.                                                                      |
| `data.homeassistant_addon` (read)              | `GET /addons/<slug>/info`                                        | ✓               | Same as plan-read. Data source uses `info` for description, schema, etc.                                                                                                |
| `data.homeassistant_repository` (read)         | `GET /store` or `GET /store/repositories`                        | ✓               | Read-only catalog of configured repositories.                                                                                                                           |

| Phase 2+ (not in v1.3 Phase 1) | Supervisor call                                                  | Notes                                |
| ------------------------------ | ---------------------------------------------------------------- | ------------------------------------ |
| Update add-on                  | `POST /store/addons/<slug>/update`                               | Used when `version` drifts.          |
| Add/remove repository          | `POST /store/repositories` / `DELETE /store/repositories/<slug>` | Different resource type; deferred.   |
| Toggle protection              | `POST /addons/<slug>/security`                                   | Phase 2.                             |
| Logs                           | `GET /addons/<slug>/logs/latest`                                 | Possible data source for debugging.  |
| Stats                          | `GET /addons/<slug>/stats`                                       | Possible data source for monitoring. |

### Bridge `/v1/...` surface (proposed)

```
GET  /v1/version
     → 200 { "bridge_version": "1.3.0-2", "schema_version": 1,
             "min_provider_version": "1.3.0-2", "max_provider_version": null }

GET  /v1/addons
     → 200 { "addons": [ AddonModel, ... ] }
     (proxies GET /addons; redaction stripped since caller = bridge-issued bearer)

GET  /v1/addons/<slug>
     → 200 AddonModel
     → 404 { "error": "addon_not_found", "slug": "...", "detail": "Supervisor returned 404" }

GET  /v1/store/addons
     → 200 [ StoreAddonModel, ... ]
     (proxies GET /store/addons)

POST /v1/addons/<slug>/install
     body: (none — install is idempotent on Supervisor side)
     → 202 { "job_id": "...", "poll_url": "/v1/jobs/<job_id>" }
     → 200 AddonModel  (after job completes; 10-minute ceiling)
     → 409 { "error": "already_installed", "slug": "..." }

POST /v1/addons/<slug>/uninstall
     body: { "remove_config": true }
     → 204 No Content

POST /v1/addons/<slug>/start    → 204
POST /v1/addons/<slug>/stop     → 204
POST /v1/addons/<slug>/restart  → 204

POST /v1/addons/<slug>/options/validate
     body: { "options": {...} }
     → 200 { "valid": true }  or  400 { "error": "invalid_options", "message": "...", "pwned": false }

POST /v1/addons/<slug>/options
     body: { "options": {...} }
     → 200 AddonModel  (options + computed hash)
     → 400 { "error": "invalid_options", "message": "..." }

GET  /v1/jobs/<job_id>
     → 200 { "id": "...", "state": "done"|"error"|"running", "progress": 0..100, "error": null|"..." }
     (proxies GET /jobs/<job_id>)
```

### Important Supervisor-API gotchas

- **`options` redaction.** Supervisor returns an empty `{}` for the `options` field in `/addons/<slug>/info` unless the
  caller is HA Core, the add-on itself, or an add-on with `manager`/`admin` role. The Bridge is _not_ HA Core and the
  Terraform role (`default`) doesn't qualify. Two ways to handle this: (a) request `manager` role via
  `hassio_role: manager` in the Bridge `config.yaml`, which unlocks `options`; (b) read options via
  `GET /addons/self/options/config` only when targeting self, which doesn't help here. **Recommendation:
  `hassio_role: manager`.** It is the minimum role that exposes options; `admin` is overkill and would require user
  confirmation.

- **`/addons/<slug>/info` includes `options` only for callers with sufficient role.** Confirmed in Supervisor API docs
  (HIGH confidence). Setting `hassio_role: manager` in `config.yaml` solves this.

- **`POST /addons/<slug>/options` requires at least one key in the payload.** Per Supervisor docs. If the user removes
  all options in HCL, the Bridge should send `{ "options": {} }` which Supervisor accepts (the whole `options` block is
  the one key). Edge case to test in Phase 1.

- **`store/addons/<slug>` slug format.** Repository-prefixed: `local_mosquitto`, `core_mosquitto`,
  `<hashed_repo>_<slug>`. The Provider's schema must take the full slug as a string attribute, not split repository +
  name. Users learn the slug once and reuse.

- **`background: true` is the wrong default.** If the Bridge uses `background: true`, every `terraform apply` returns
  immediately and the Provider sees a non-existent add-on — drift and re-applies. Use `background: false` so Supervisor
  blocks; Bridge then surfaces install errors directly.

---

## Schema Versioning

### Recommendation: (a) + (b) combined

The question lists three options. Adopt **both (a) and (b)**; reject (c) only because silent acceptance of extra fields
defeats the purpose of having a versioned contract.

**Mechanism (a) — `/v1/version` endpoint (recommended).** Bridge exposes its version + Provider-compat bounds at
startup; the Provider calls it as the very first RPC after `Configure`. The response:

```json
{
  "bridge_version": "1.3.0-2",
  "schema_version": 1,
  "min_provider_version": "1.3.0-2",
  "max_provider_version": null
}
```

The Provider compares `bridge.schema_version` against the schema version the Provider was built against. Mismatch → hard
error in `Configure`. Provider also compares `bridge_version` semver against
`min_provider_version`/`max_provider_version` for in-band breakage windows (e.g., "this Bridge requires Provider ≥ 1.4
because we removed the legacy `homeassistant_addon.image` field").

_*Mechanism (b) — reject on /v1/* mismatches (recommended)._* The Bridge also embeds the minimum acceptable
`schema_version` for every `/v1/*` route. If a Provider sends `X-Bridge-Schema: 0` and the Bridge requires `1`, the
Bridge returns `400 { "error": "schema_mismatch", "bridge_schema": 1, "provider_schema": 0, "min_required": 1 }`.
Defense in depth — the `/v1/version` check protects the Provider from misconfiguration; the per-request check protects
the Bridge from a downgraded Provider sneaking past the startup probe.

**Reject (c).** Schema evolution should be explicit. Silent field dropping produces confusing Provider behavior: the
Provider thinks it set an option, but the Bridge ignored it, and the next `plan` shows perpetual drift. Phase 2
migration policy belongs in `/v1/version` where the Provider can decide whether to upgrade or warn.

### How Bridge version and Provider version stay in lock-step

The repo's 3-file versioning scheme is the binding glue:

- `terraform-bridge/config.yaml` version = `1.3.0-N` (subpatch N)
- `terraform-provider-homeassistant/build.yaml` version = `1.3.0` (no subpatch — Go modules don't use subpatch)
- README badges display `v1.3.0`

Both the Bridge and the Provider are tagged from the same version. A
`make update-version ADDON=terraform-bridge VERSION=1.4.0` would normally bump only the Bridge, but for v1.3 the
Provider MUST ship a matching version. This constraint belongs in `validate-versions.sh`: it already enforces
consistency across the 3 files; extend it so that if `terraform-bridge/config.yaml` shows `1.4.0-0`,
`terraform-provider-homeassistant/build.yaml` must show `1.4.0`. This makes accidental solo-bumping a pre-commit
failure.

### Versioning policy inside a version

- **Additive new fields on `homeassistant_addon`**: bump `schema_version` from N to N+1. Providers built against schema
  N still work (they ignore new fields); Providers built against N+1 fail with a clear message on a Bridge running
  schema N.
- **Removing or renaming fields**: bump `schema_version` AND raise `min_provider_version`. Coordinated release.
- **Bridge internal refactor (no API change)**: bump subpatch only (`1.3.0-0` → `1.3.0-1`). No schema bump.

---

## State Storage

### Phase 1: local backend in `/data`

```
.terraform/
  terraform.tfstate     ← OpenTofu state (lives on Provider host, NOT in the add-on)
```

For Phase 1, the user runs `tofu apply` from a directory on their laptop or CI, and the state file lives there. The
Bridge stores **no** state — it is stateless with respect to Terraform.

**Implication:** the Provider is the only writer of state. There is no concurrent-write problem between Provider runs
because the user runs them serially (or, with `-lock=true`, OpenTofu serializes via the local lockfile). Multiple
Providers cannot run against the same Bridge from the same directory simultaneously because OpenTofu locks the local
`.terraform.tfstate.lock` file.

### Phase 1 alt: HTTP backend pointing at the Bridge (still optional)

The Terraform `http` backend
([developer.hashicorp.com](https://developer.hashicorp.com/terraform/language/backend/http)) natively supports
`GET`/`POST`/`DELETE`/`LOCK`/`UNLOCK`. If the user wants state on the Bridge (e.g., to back it up via HA snapshots),
they declare:

```hcl
terraform {
  backend "http" {
    address        = "https://haos-op3050-1:8124/v1/state"
    lock_address   = "https://haos-op3050-1:8124/v1/state/lock"
    unlock_address = "https://haos-op3050-1:8124/v1/state/lock"
    username       = "tf"          # or use TF_HTTP_USERNAME env var
    password       = var.bridge_token
  }
}
```

The Bridge implements the four verbs:

| HTTP verb on `/v1/state` | Behavior                                                                                                                                                                                                                                |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`                    | Read `/data/terraform.tfstate` (or 404 if absent).                                                                                                                                                                                      |
| `POST`                   | Atomic rename: write to `/data/terraform.tfstate.tmp`, fsync, rename over. Use `os.replace()` in Go or `os.rename()` in Python — both are atomic on Linux same-filesystem.                                                              |
| `DELETE`                 | `os.unlink()`.                                                                                                                                                                                                                          |
| `LOCK`                   | Write a `lock.json` with `{ "id": "<uuid>", "who": "<user-agent>", "created": "<iso>" }` to `/data/terraform.tfstate.lock`. Use O_CREAT\|O_EXCL so concurrent `LOCK` returns EEXIST → Bridge returns `423 Locked` with the holder info. |
| `UNLOCK`                 | Read `lock.json`, verify the `X-Lock-ID` header matches the holder's id; unlink; or 409 Conflict if not.                                                                                                                                |

The HTTP backend `LOCK` flow returns `423 Locked` (per Hashicorp docs) on contention. The Bridge returns
`{ "error": "state_locked", "lock_id": "...", "who": "...", "created": "..." }`.

### Concurrency scenarios

**Provider A starts an apply while Provider B is mid-apply.** With `local` backend: OpenTofu's local
`.terraform.tfstate.lock` file serializes them — second one waits up to lock timeout. With HTTP backend: second one sees
423 immediately. Either way, no corruption.

**Provider runs while Bridge is restarting.** With HTTP backend: Bridge is down, GET/POST return 503; OpenTofu errors
out. With local backend: Provider doesn't touch Bridge until apply; reads are batched.

**Bridge restart during apply.** `terraform apply` issues a series of Bridge HTTP calls. If the Bridge restarts
mid-sequence, an in-flight call returns 5xx; Provider retries, then errors. The user can re-run; since
`terraform refresh` already saw the partial state, the user only pays the cost of the remaining operations.

**HA host restart.** The state file lives in `/mnt/data/supervisor/addons/local_terraform-bridge/`. HA Supervisor
persists this directory across add-on restarts. HA host restarts do not lose state. HA OS reinstall does — the user must
back up `/mnt/data/supervisor/addons/local_terraform-bridge/` alongside other HA backups.

### Phase 2+: S3-compatible backend

Deferred per PROJECT.md. When CI apply runs become a thing, switch to S3/GCS/Azure Blob via the existing OpenTofu
backends. No Bridge work needed.

---

## Auth Flow

### Two layers, two token types

**Layer 1: Bridge → Supervisor.** The `SUPERVISOR_TOKEN` environment variable is auto-injected by Supervisor into every
add-on container. The Bridge reads it from the environment (or via `bashio::config` is not needed — it comes from
`os.environ`). The Bridge uses this token on every call to `http://supervisor/<path>`.

```python
# Bridge (Python pseudo-code)
supervisor_token = os.environ["SUPERVISOR_TOKEN"]  # auto-injected
session.headers["Authorization"] = f"Bearer {supervisor_token}"
```

No user interaction required for this layer. Same mechanism every add-on in this repo uses.

**Layer 2: Provider → Bridge.** The Bridge issues a single long-lived bearer token at first startup, stores it in
`/data/token.json`, and surfaces it through the add-on's Options UI (one of the few `password`-type schema fields HA
supports natively). The user copies that token into their Provider config (`TF_BRIDGE_TOKEN` env var or `bridge_token`
variable).

```python
# Bridge startup (pseudo-code)
token_path = "/data/token.json"
if not os.path.exists(token_path):
    token = secrets.token_urlsafe(32)  # 256-bit entropy
    os.write(token_path, json.dumps({"token": token, "created_at": now}).encode())
    os.chmod(token_path, 0o600)
else:
    token = json.load(open(token_path))["token"]

# Provider request (pseudo-code)
@app.middleware("http")
async def check_bearer(request, call_next):
    if request.headers.get("Authorization") != f"Bearer {token}":
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)
```

### Token rotation

A single Bridge endpoint, callable with the _current_ valid token, generates a new token and atomically swaps:

```
POST /v1/admin/rotate-token
  Authorization: Bearer <current>
  → 200 { "token": "<new>", "created_at": "<iso>" }
```

The Bridge writes the new token to `token.json` _before_ returning the response. If the user accidentally closes their
terminal between the rotate call and updating their Provider config, they can re-read the token via the HA Options UI
(`bashio::addon.option 'bridge_token'` in the add-on terminal logs it on startup).

A revoke endpoint is intentionally **not** exposed: there is no need to invalidate the only token. If the token is
compromised, the user rotates (and the compromised token becomes immediately useless).

### Why not Cloudflare Access?

The Phase 8 `notify-ha.sh` work set up Cloudflare Access for the build webhook path (`/api/webhook/*`) using a service
token. The same pattern works for the Bridge: a path-scoped Access app for `/v1/*` on `haos-op3050-1` protects the
bridge from the public internet. Two constraints favor bearer-token-only over CF Access for Phase 1:

1. **The Bridge is reachable on Tailscale.** All three hosts (`haos-op3050-1`, `lxc-haos-104`, `hassio-n2plus`) are on
   the user's Tailscale network. Tailscale already provides device-level auth — a CF Access app would add a second auth
   layer that protects against device compromise, not against internet exposure.
2. **mTLS was considered and rejected in PROJECT.md.** The reasoning recorded: "mTLS needs a CA inside the container;
   OAuth adds a UI surface for one client. Bearer is the smallest correct primitive."

**Phase 2 candidate:** if the Bridge ever needs to be exposed beyond Tailscale (e.g., shared with a teammate), a
path-scoped CF Access app on `/v1/*` with a separate service token mirrors the existing webhook setup. The bearer token
stays (defense in depth — Access + bearer), and both layers can be misconfigured without compromising the other.

### Audit log

The Bridge writes one JSONL line per authenticated request to `/data/audit.log`:

```json
{
  "ts": "2026-08-31T14:22:01Z",
  "method": "POST",
  "path": "/v1/addons/core_mosquitto/start",
  "status": 204,
  "duration_ms": 42,
  "client_ip": "100.64.1.42",
  "user_agent": "tofu/1.6.0"
}
```

Log rotation is handled by logrotate via `/data` volume's standard cleanup (or simply by the user — `audit.log` should
not grow unbounded in normal use; an aggressive applier might write 1000s of lines per session, well below the 10MB
daily budget that would matter). Phase 2 candidate: ship a `homeassistant_audit_log` data source so Terraform can read
its own history.

### Threat model

| Adversary                                 | Mitigation                                                                                                                                                             |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Internet attacker                         | Bridge listens only on the host's LAN/Tailscale IP; not reachable from the public internet unless CF Access is set up.                                                 |
| LAN attacker                              | Bearer token is 256-bit; not transmitted in plan output. The Bridge logs the client IP so an attacker scraping the LAN would leave traces.                             |
| Token leaked via git                      | Token is in env var `TF_BRIDGE_TOKEN`, never in `*.tf`. Add a pre-commit grep check that fails if a `bridge_token` value with literal value appears in any `.tf` file. |
| Malicious add-on reads `/data/token.json` | Supervisor runs containers as separate UIDs by default; `/data` is per-add-on. An add-on cannot read another add-on's `/data`.                                         |
| Token burned (user suspects compromise)   | Rotate via `POST /v1/admin/rotate-token`.                                                                                                                              |

---

## Build Order

The recommended sequence: **Bridge skeleton → Bridge read wrap → Provider skeleton → Provider↔Bridge handshake →
Provider write ops → Bridge state HTTP backend → polish**. Auth enters at the read-wrap phase because every write later
needs auth in place.

### Phase 1: `terraform-bridge` Skeleton + Read-only Supervisor Wrap

**Goal:** A Bridge add-on that boots, issues one authenticated `GET /addons` against Supervisor, and returns the result
on a single `GET /v1/addons` endpoint. No Provider yet — `curl` from the host is the verification.

**Deliverables:**

- `terraform-bridge/config.yaml` — 4-file scaffold, `hassio_role: manager`, `hassio_api: true`, ports mapping
- `terraform-bridge/Dockerfile` — Python 3 base from HA, `python3` only (no nginx needed for Phase 1)
- `terraform-bridge/run.sh` — bashio + exec Python
- `terraform-bridge/bridge.py` — FastAPI app, bearer middleware, `/v1/version`, `/v1/addons`
- `terraform-bridge/DOCS.md`, `README.md`
- `terraform-bridge/.upstream.yaml` — **NOT present** (no external upstream; project is built in this repo)

**Verification:** `curl -H "Authorization: Bearer $(cat token.json)" http://haos-op3050-1:8124/v1/addons` returns the
JSON list of installed add-ons from Supervisor.

**Depends on:** Nothing (first phase of v1.3).

### Phase 2: `terraform-provider-homeassistant` Skeleton + Single Read Resource

**Goal:** A Go Provider that does nothing but expose `data "homeassistant_addon"` — read-only. Calls the Bridge, returns
one add-on's info as a Terraform data source.

**Deliverables:**

- `terraform-provider-homeassistant/go.mod`, `main.go` — provider server bootstrap
- `terraform-provider-homeassistant/internal/provider/addon_data_source.go` — schema + `Read` RPC
- `terraform-provider-homeassistant/internal/client/bridge_client.go` — HTTP client to Bridge
- `terraform-provider-homeassistant/Makefile` — `build`, `install` (place in `~/.terraform.d/plugins/...`)
- `terraform-provider-homeassistant/.tool-versions` — Go 1.22+
- Phase 1 token surfaced through `terraform-provider-homeassistant`'s schema
  (`provider "homeassistant" { endpoint = "...", token = "..." }`)

**Verification:** `data "homeassistant_addon" "mosquitto" { slug = "core_mosquitto" }` returns the add-on's description,
version, state, and a derived `options` JSON object.

**Depends on:** Phase 1 (Bridge must exist).

### Phase 3: Provider Reads All Add-ons + `terraform plan` against One Resource

**Goal:** `homeassistant_addon` resource type works for `terraform plan` and `terraform refresh`. The Provider can read
all installed add-ons and produce a meaningful plan diff.

**Deliverables:**

- `internal/provider/addon_resource.go` — schema + `Read` + `Schema` methods; no `Create`/`Update`/`Delete` yet
- `/v1/version` endpoint on Bridge with the schema-version contract
- `terraform-provider-homeassistant/internal/client/diagnostics.go` — typed `diag.Diagnostics` for known Supervisor
  error classes

**Verification:** `terraform plan` shows "no-op" for every installed add-on that matches the HCL, and a "create" plan
for an HCL-declared add-on that isn't installed.

**Depends on:** Phase 2.

### Phase 4: Write Operations + End-to-End `terraform apply`

**Goal:** `terraform apply` actually installs/starts/stops/uninstalls add-ons and updates options.

**Deliverables:**

- `Create`, `Update`, `Delete` methods on the resource
- `install` mapping (calls `POST /store/addons/<slug>/install` with `background: false`)
- `uninstall` mapping
- `start`/`stop`/`restart` mapping
- `options` mapping with pre-validate (`POST /addons/<slug>/options/validate`)
- Bridge `/v1/addons/<slug>/options/validate` endpoint
- Bridge `/v1/jobs/<job_id>` polling for any async Supervisor jobs

**Verification:** `terraform apply` against a real HA host installs mosquitto (or any cheap add-on), starts it, updates
its options, and stops it; `terraform destroy` uninstalls it cleanly.

**Depends on:** Phase 3.

### Phase 5: HTTP State Backend on Bridge (optional, defer if local backend is enough)

**Goal:** `terraform { backend "http" { address = ".../v1/state" } }` works with locking.

**Depends on:** Phase 4.

### Phase 6: Polish — Tests, Docs, CI Integration

**Goal:** `terraform-plugin-testing` acceptance tests against a live HA host; CI step that runs `make check-all` and
validates the Provider's Go module compiles; update `validate-versions.sh` to enforce Provider+Bridge version lock-step.

**Depends on:** Phase 4 (or 5).

### Where auth fits

- Phase 1: bearer-token middleware, but the user hand-pastes the token via `curl`. No Provider yet.
- Phase 2: Provider accepts `token` provider attribute, sends it on every request.
- Phase 3+: rotation endpoint, audit log shipped together. No retroactive auth work needed in later phases.

### Why this order

- **Bridge first**: The Provider is just a typed wrapper around the Bridge. If the Bridge can't issue a `GET /addons`,
  the Provider has nothing to model. E2E testing is `curl`, which is cheaper than spinning up Terraform on every
  iteration.
- **Read-only before write**: Plan-time reads are the harder correctness problem (matching Supervisor's response to the
  Terraform schema). If the schema is wrong, _no_ write operation will behave predictably. The Provider's `Read` is the
  most-tested code path — build it first, lean on it.
- **Auth from the start, not retrofitted**: Middleware is 10 lines of code in Phase 1 and an architectural pain point if
  bolted on in Phase 3. The user runs `curl` with the token from day one — that's a forcing function to validate the
  auth model on a real network path before the Provider wraps it.

---

## Networking

### Three transport options, ranked for Phase 1

**Option A: `host_network: false` + `ports:` mapping (RECOMMENDED for Phase 1)**

```yaml
# terraform-bridge/config.yaml
host_network: false
ingress: false
ports:
  8124/tcp: 8124
ports_description:
  8124/tcp: "Terraform Bridge HTTP API (Provider → Bridge)"
```

- The add-on listens on `0.0.0.0:8124` inside the container; Supervisor maps this to the HA host's LAN IP at port 8124.
- The Provider reaches it via `https://<ha-host>:8124/v1/...` (HTTPS if the user puts a reverse proxy like Caddy in
  front; plain HTTP if they trust the LAN/Tailscale).
- Why: clean separation — no interaction with HA Ingress, no `host_network: true` permission. Standard pattern, used by
  meridian (`3456/tcp: 3456`).
- Caveat: the host port 8124 must be free. Document this in `DOCS.md`.

**Option B: `host_network: true` (REJECTED for Phase 1)**

- Used by `network-tools` because it needs raw L2 ARP access. The Bridge has no such need.
- `host_network: true` removes the container network namespace; the Bridge shares the host's IP. Less defensible posture
  than `ports:` for an HTTP service with auth tokens.

**Option C: `ingress: true` (REJECTED)**

- HA Ingress is browser-only: requests come from a logged-in HA user via the sidebar. It cannot be reached by a CLI tool
  on a developer laptop.
- Even if it could, Ingress auth is HA-user-session-based, not bearer-token-based — it would be the wrong auth model for
  a non-interactive API client.
- Confirmed by the existing markdown-renderer / meridian precedent: Ingress is for the UI surface only.

### TLS posture

The Bridge speaks plain HTTP inside the container. The Provider's `endpoint` attribute is `https://...`, which implies
the user has terminated TLS in front. Two options:

1. **Plain HTTP on Tailscale.** Tailscale is a private mesh; the encryption is at the WireGuard layer, not TLS.
   Acceptable for Phase 1. The Provider `endpoint` becomes `http://haos-op3050-1:8124`.
2. **TLS via Caddy/nginx on the HA host.** A standard L7 reverse proxy on the host listens on 443 and forwards to
   `127.0.0.1:8124`. Provider `endpoint` = `https://haos-op3050-1/v1/...` with a real cert (Caddy obtains one via Let's
   Encrypt or the user uses Tailscale's HTTPS feature).

Phase 1 supports both: the Provider's `endpoint` is whatever the user puts in their `*.tf`; the Bridge just speaks HTTP
on whatever port Supervisor exposes.

### Where the Bridge IP comes from

```
terraform-provider-homeassistant/
  main.tf:
    provider "homeassistant" {
      endpoint = "http://haos-op3050-1:8124"   # LAN IP
      # or
      endpoint = "http://100.89.14.27:8124"    # Tailscale IP
    }
```

The user puts the IP/hostname in their `*.tf` or in a `TF_BRIDGE_ENDPOINT` env var. Phase 2 candidate: an `endpoint`
discovery data source that uses Tailscale's MagicDNS or a hostname convention (`terraform-bridge.local`).

### Cloudflare Access integration (deferred to Phase 2)

If the user wants to apply from outside Tailscale (e.g., a CI runner on the public internet), mirror the Phase 8 pattern
for `notify-ha.sh`:

1. In Cloudflare Zero Trust, create an Access app scoped to `haos-op3050-1.lxc-haos-104.hassio-n2plus.akentner.de/v1/*`
   (hostname-wide path-scoped). Three separate apps, one per host (or a wildcard app if all three are on the same
   Cloudflare-managed domain).
2. Issue a service token; store `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET` as GitHub secrets.
3. The Provider sends `CF-Access-Client-Id` and `CF-Access-Client-Secret` headers alongside (or instead of) the bearer
   token. The Bridge forwards them through (or validates them locally if Cloudflare is reachable in-band).
4. Negative probe: an unauthenticated request from the public internet must be 302-redirected to the Access login, not
   reach the Bridge — exactly the `08-03-SUMMARY.md` pattern, ported.

The 08-03 partial-summary lesson applies: **never `-L` follow redirects**, fail fast on 3xx, log the Access policy name.
The Bridge is a better place to do this than the Provider because the Bridge can return a typed diagnostic with the
Access policy name and remediation hint.

---

## Error Model

### Source of errors

| Source                  | When                                    | How it surfaces to Provider                                         |
| ----------------------- | --------------------------------------- | ------------------------------------------------------------------- |
| **Bridge**              | 401/403 missing or bad bearer           | `401 { "error": "unauthorized" }`                                   |
| **Bridge**              | 404 unknown route                       | `404 { "error": "not_found" }`                                      |
| **Bridge**              | 503 Supervisor unreachable              | `503 { "error": "supervisor_unavailable", "detail": "..." }`        |
| **Bridge**              | 504 Supervisor timeout (10s default)    | `504 { "error": "supervisor_timeout" }`                             |
| **Supervisor → Bridge** | 404 add-on not installed                | `404 { "error": "addon_not_found", "slug": "..." }`                 |
| **Supervisor → Bridge** | 400 schema validation                   | `400 { "error": "invalid_options", "message": "..." }`              |
| **Supervisor → Bridge** | 423 add-on is protected (security mode) | `423 { "error": "addon_protected" }`                                |
| **Supervisor → Bridge** | 409 install already in progress         | `409 { "error": "install_in_progress", "job_id": "..." }`           |
| **Supervisor → Bridge** | job error (async)                       | `200 { "state": "error", "error": "..." }` from `/jobs/<id>`        |
| **Provider**            | Schema mismatch                         | Caught at startup; Provider refuses to configure                    |
| **Provider**            | Network failure                         | Provider's `net/http` retry; after backoff, `diag.Diagnostic` error |

### Provider-side: typed diagnostics with `terraform-plugin-framework`

The Provider uses `diag.Diagnostics` (verified at
[developer.hashicorp.com/terraform/plugin/framework/diagnostics](https://developer.hashicorp.com/terraform/plugin/framework/diagnostics))
to surface Bridge errors. The recommended pattern: a single helper in
`terraform-provider-homeassistant/internal/client/diagnostics.go`:

```go
// APIErrorDiagnostic maps a Bridge HTTP error to a typed diagnostic.
func APIErrorDiagnostic(httpStatus int, body BridgeError) diag.Diagnostic {
    summary := fmt.Sprintf("Bridge returned HTTP %d", httpStatus)
    switch body.Error {
    case "addon_not_found":
        summary = "Home Assistant add-on not found"
    case "invalid_options":
        summary = "Add-on options failed schema validation"
    case "addon_protected":
        summary = "Add-on is in protected mode"
    case "supervisor_unavailable":
        summary = "HA Supervisor unreachable from Bridge"
    case "install_in_progress":
        summary = "Add-on install already in progress"
    }
    detail := fmt.Sprintf(
        "Error: %s\nDetail: %s\nHint: %s\n\nURL: %s",
        body.Error, body.Detail, body.Hint, body.URL,
    )
    return diag.NewErrorDiagnostic(summary, detail)
}
```

`terraform-plugin-framework` uses `Summary` (short) + `Detail` (long, with newlines OK). The `Detail` field should
include the remediation hint from the Bridge when available (e.g., "rotation required — `POST /v1/admin/rotate-token`").

### Severity: error vs. warning

Per [HashiCorp framework docs](https://developer.hashicorp.com/terraform/plugin/framework/diagnostics):

- **Error** halts Terraform's execution. Use for: not found, schema mismatch, install failure, options invalid.
- **Warning** displays but doesn't halt. Use for: deprecation notices (Phase 2), configuration that the Provider accepts
  but doesn't recommend (Phase 2).

The Provider **never uses `diag.Diagnostic` with `Severity` other than Error or Warning** — those are the only two
supported values. For debug-level info, use `tflog` (the Provider's structured logger, see Phase 8 `08-03-SUMMARY.md`
patterns-established for analogous logging).

### Idempotency and "error after partial success"

A critical concern: Terraform persists state even when a `Create`/`Update` returns an error. If the Bridge installed an
add-on but then failed to update its options, the Provider state shows `installed=true` but `options` are stale. The
Provider must reset the state to prior-state in this case, per the framework docs: "When returning error diagnostics, we
recommend resetting the state in the response to the prior state available in the configuration."

The Bridge can help by making `install` and `update_options` separate operations (which they already are — the Phase 1
schema maps install to `POST /store/addons/<slug>/install` and options to `POST /addons/<slug>/options`). If the user
changes both `started` and `options` in one apply, the Provider issues install first (state: installed), then options
(state: installed + new options). If options fails, the state reads `installed=true, options=old` — and the user knows
what happened from the typed diagnostic.

---

## Sources

**HIGH confidence (primary sources, verified during research):**

- [HA Supervisor Endpoints](https://developers.home-assistant.io/docs/api/supervisor/endpoints/) — every Phase 1
  endpoint, payload shape, response shape
- [HA App configuration](https://developers.home-assistant.io/docs/add-ons/configuration) — `config.yaml` schema,
  `hassio_role` semantics, `ports` mapping, `host_network`, `ingress`
- [HA App communication](https://developers.home-assistant.io/docs/add-ons/communication) — `SUPERVISOR_TOKEN`
  injection, internal DNS `{REPO}_{SLUG}`, supervisor hostname, default permissions per endpoint
- [Terraform Plugin Framework: Diagnostics](https://developer.hashicorp.com/terraform/plugin/framework/diagnostics) —
  severity model, `diag.Diagnostic`, `diag.Diagnostics.Append`, severity constants
- [Terraform Plugin Framework: Schemas](https://developer.hashicorp.com/terraform/plugin/framework/handling-data/schemas)
  — `schema.Schema`, `Version`, `DeprecationMessage`, `Description`
- [Terraform State Locking](https://developer.hashicorp.com/terraform/language/state/locking) — lock semantics,
  force-unlock nonce
- [Terraform HTTP Backend](https://developer.hashicorp.com/terraform/language/backend/http) — `LOCK`/`UNLOCK` verbs,
  `423 Locked` semantics, request/response shape
- [OpenTofu JSON Format](https://opentofu.org/docs/internals/json-format/) — `format_version` semantic-versioning rules
  for forward compatibility
- [OpenTofu 1.12 release notes](https://opentofu.org/docs/intro/whats-new/) — confirms 1.12 is the current major (Jan
  2026 release), OpenTofu is alive, `-json-into` for machine-readable output

**HIGH confidence (in-repo primary sources):**

- `meridian/config.yaml` + `meridian/run.sh` — the established pattern for a long-running add-on with `ports:` mapping +
  nginx ingress + bashio config reading. Use as the template for `terraform-bridge`.
- `network-tools/config.yaml` + `network-tools/run.sh` — alternative pattern for an HTTP service with
  `host_network: true` (only relevant if Bridge ever needs raw L2; currently it does not).
- `markdown-renderer/config.yaml` + `markdown-renderer/run.sh` — the alternative `ingress: true` pattern; we reject this
  for the Bridge because Ingress is browser-only.
- `.planning/phases/08-ci-cd-hardening/08-03-SUMMARY.md` — Cloudflare Access service-token auth pattern (negative-edge
  probe, 3xx fail-fast, no `-L`). Reuse for Phase 2 if Bridge is exposed beyond Tailscale.
- `.planning/REQUIREMENTS.md` + `.planning/ROADMAP.md` — current milestone state, prior phase patterns.

**MEDIUM confidence (assumptions about Tailscale + CF Access composition):**

- The exact hostname(s) the user has on Cloudflare (`haos-op3050-1.lxc-haos-104.hassio-n2plus.akentner.de` is an
  educated guess based on the README + AGENTS.md "akentner.de" pattern; verify before implementing Phase 2 Access
  integration).
- Tailscale subnet routes — assumed but not confirmed in this research. The Provider may need to honor MagicDNS names
  like `haos-op3050-1.tail-name.ts.net`, depending on how the user has configured their tailnet.

**Gaps to address in Phase 1 research:**

1. **Exact async-job latency.** Phase 1 assumes 10 minutes is enough for any install. The Bridge should record observed
   install times in production for a future refinement.
2. **Supervisor install state for already-installed add-ons.** Verified that `POST /store/addons/<slug>/install` is
   idempotent — it returns success if the add-on is already installed at the requested version, and a
   `version_latest`-newer state otherwise. The Bridge should detect the latter and call
   `POST /store/addons/<slug>/update` instead, but this is Phase 2 polish.
3. **Bridge memory budget.** HA add-ons share host memory. FastAPI on uvicorn defaults to a small footprint, but the
   Bridge may want to specify `mem_limit` or watch for OOM in production. Phase 1 doesn't need a number; Phase 4 polish
   should measure.
4. **Provider build/install UX.** Terraform discovers Providers via `~/.terraform.d/plugins/<host>/<name>/<version>/` or
   a `dev_overrides` block in `~/.terraformrc`. The Makefile target for `make install` should put the Provider there.
   This is a 30-line Makefile target — Phase 2 deliverable, not research.
