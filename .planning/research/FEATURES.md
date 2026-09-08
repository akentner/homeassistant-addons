# Feature Landscape: OpenTofu Configuration Bridge for Home Assistant

**Domain:** OpenTofu/Terraform provider + Bridge add-on that manages Home Assistant Supervisor resources
declaratively
**Researched:** 2026-08-31
**Milestone:** v1.3 opentofu-bridge (SUBSEQUENT to v1.1 markdown-renderer and v1.2 ci-cd-hardening)
**Phase 1 scope (already decided in PROJECT.md):** `homeassistant_addon` resource (CRUD: install / start / stop /
uninstall + options update). Optional in Phase 1: `homeassistant_addon_repository`.

> **Scope of this file:** Feature landscape only — what to BUILD in the Bridge + Provider. Companion files in
> this research drop cover stack choices (STACK.md), architecture (ARCHITECTURE.md), pitfalls (PITFALLS.md), and the
> executive summary (SUMMARY.md). Existing repo add-ons (7 in production) and their conventions are out of scope;
> see PROJECT.md and ROADMAP.md.

---

## Summary

The OpenTofu Configuration Bridge turns the HA Supervisor API into a versioned, idempotent JSON-over-HTTP surface
that an in-repo Go provider consumes via declarative `*.tf` files. The feature set is shaped by three converging
constraints:

1. **Terraform / OpenTofu user expectations** — CRUD, idempotent Read, schema validation, computed attributes,
   sensitive values, Import, timeouts, plan modifiers. Anything less is rejected by `terraform plan`/`apply` as a
   broken provider.
2. **HA Supervisor API reality** — verified against the primary source
   ([`home-assistant/supervisor/supervisor/api/apps.py`](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/apps.py)
   and [`store.py`](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/store.py)) at research
   time: install/start/stop/restart are POSTs, options update is POST, app state transitions are asynchronous
   (`startup`/`started`/`stopped`/`unknown`/`error` from `AppState` enum in
   [`supervisor/const.py`](https://github.com/home-assistant/supervisor/blob/main/supervisor/const.py)).
3. **Phase-1 budget** — PROJECT.md has already fixed Phase 1 to the `homeassistant_addon` resource. Other resource
   types (config, scripts, automations, integrations, devices, areas, zones, backups, dashboards) are deferred to
   later milestones because their underlying Supervisor endpoints are either unstable (V2-only behind the
   `SUPERVISOR_V2_API` feature flag) or do not exist at all in Phase-1's scope.

The headline finding: **there is no existing `terraform-provider-homeassistant` on GitHub, on the public Terraform
Registry, or on the OpenTofu Registry.** The GitHub topic `terraform-provider-homeassistant` shows zero
repositories ([source](https://github.com/topics/terraform-provider-homeassistant)). This is a green-field provider.
The closest reference points are the **authentik provider** (same shape — REST API with long-lived bearer tokens,
138 stars, framework-based, actively maintained — verified at
[`goauthentik/terraform-provider-authentik`](https://github.com/goauthentik/terraform-provider-authentik)) and the
**plugin framework reference docs** at `developer.hashicorp.com/terraform/plugin/framework/...`.

Phase 1 = 1 resource type + 1 data source. The Bridge add-on is a thin pass-through over the Supervisor API with
bearer-token auth + idempotency wrapping; the Provider is a Go module built from local source in this repo (see
PROJECT.md key decisions) using `terraform-plugin-framework`.

---

## Phase-1 Resources (decided in PROJECT.md)

### Resource types shipping in Phase 1

| Resource | Schema source | CRUD verbs | Notes |
| --- | --- | --- | --- |
| `homeassistant_addon` | Supervisor `apps.py` + `store.py` | `Create` = install + start; `Read` = info; `Update` = options change; `Delete` = uninstall. Restart/stop/start are exposed as separate actions, not lifecycle verbs (see Phase-1 Resources → Add-on Lifecycle below). | Phase-1 resource. |
| `homeassistant_addon_repository` | Supervisor `store.py` | `Create` = add_repository; `Read` = repositories_list; `Delete` = remove_repository | Optional in Phase 1 (PROJECT.md). Marked as **opt-in Phase-1 stretch**: include only if Phase-1 scope budget allows; otherwise defer to Phase 2. |

### Data sources shipping in Phase 1

| Data source | Purpose | Notes |
| --- | --- | --- |
| `homeassistant_addon` (data) | Look up an add-on by `slug` from outside `*.tf` resources | Uses `apps/{app}/info`. Needed so users can pull `version_latest`, `state`, `ingress_url`, etc. into outputs without managing the resource. |
| `homeassistant_supervisor_info` | Read supervisor version / healthy / arch | Uses `supervisor/info`. Optional but cheap; useful for `lifecycle.precondition` checks. |

### Resource surface for `homeassistant_addon` (Phase 1)

Schema derived from Supervisor primary source (see Source-Notes at end of file). Phase-1 attributes only; later
phases add the deferred columns.

| Attribute | Phase 1? | Type | Source ATTR_* in Supervisor | Notes |
| --- | --- | --- | --- | --- |
| `slug` | **required** | string (immutable) | `ATTR_SLUG` | Resource identifier. Forces replacement if changed. Import key. |
| `repository` | **required** | string | `ATTR_REPOSITORY` | Repository slug (e.g., `a0d7b954`, `core`, `local`). Forces replacement. |
| `version` | optional | string (write-only on Create) | `ATTR_VERSION` in `SCHEMA_VERSION` | Pin install to a specific version (matches `store/{app}/install` request body when present). On Update it is informational only; the Provider ignores it if state already matches. |
| `url` | optional | string | `ATTR_URL` (computed) | Source repository URL — read-only. |
| `options` (TypeMap of nested object, schema-driven) | optional | dynamic / `attr.Value` map | `ATTR_OPTIONS` validated against `app.schema` (voluptuous schema exposed as `ATTR_SCHEMA`) | The validated user-config JSON. Provider must accept the add-on's `ATTR_SCHEMA` JSON-schema and translate it to nested `schema.Attribute` definitions (see Pitfall in PITFALLS.md). Sensitive values flagged with `Sensitive: true` where marked in `ATTR_SCHEMA`. |
| `boot` | optional | enum (`auto`, `manual`) | `ATTR_BOOT` (`AppBoot` enum) | Maps to `ATTR_BOOT` in `SCHEMA_OPTIONS`. |
| `auto_update` | optional | bool | `ATTR_AUTO_UPDATE` | Matches `ATTR_AUTO_UPDATE` field in `SCHEMA_OPTIONS`. |
| `ingress_panel` | optional | bool | `ATTR_INGRESS_PANEL` | Whether the add-on registers a sidebar panel in HA. |
| `watchdog` | optional | bool | `ATTR_WATCHDOG` | Supervisor watchdog for restart-on-fail. |
| `start` (boolean, **default: true**) | optional | bool | (Provider-side convention) | When true, `Create` installs AND starts the add-on. When false, only install — caller can start later via separate action. |
| `id` | computed | string | `ATTR_SLUG` | Read-only. Convention: ID == slug. |
| `state` | computed | enum (`startup`, `started`, `stopped`, `unknown`, `error`) | `ATTR_STATE` (`AppState` enum in `supervisor/const.py`) | Latest observed runtime state. **NOT** a `force_new` trigger — supervisor state churns on restart; use `ignore_changes` lifecycle meta-argument if drift alarms are noisy. |
| `version_installed` | computed | string | `ATTR_VERSION` from `info_data` | The currently installed version (distinct from configured `version` and from `version_latest`). |
| `version_latest` | computed | string | `ATTR_VERSION_LATEST` | The latest version available in the repository. |
| `update_available` | computed | bool | `ATTR_UPDATE_AVAILABLE` | `latest_version != installed.version` |
| `ingress_url` | computed | string | `ATTR_INGRESS_URL` | Only present when `ingress_panel = true`. |
| `ingress_port` | computed | int | `ATTR_INGRESS_PORT` | Dynamic port (`INGRESS_DYNAMIC_PORT_MIN`..`MAX` from `const.py`). |
| `available` | computed | bool | `ATTR_AVAILABLE` | Architecturally supported on this host. |
| `protected` | computed | bool | `ATTR_PROTECTED` | Cannot be uninstalled while true. Used by Provider to surface "would destroy" plans more clearly. |
| `timeouts` (nested block) | optional | `create`/`update`/`delete` durations | Provider-side | Use the `terraform-plugin-framework-timeouts` module ([source](https://github.com/hashicorp/terraform-plugin-framework-timeouts)). Phase-1 default: `create = 10m` (install can pull large images), `update = 5m` (option apply + restart), `delete = 5m`. |

### Phase-1 add-on lifecycle (action vs. CRUD split)

Terraform CRUD verbs (`Create`/`Read`/`Update`/`Delete`) don't map cleanly to HA's install/start/stop model because
**start and stop are separate POSTs and the runtime state is async**. The cleanest mapping:

| Terraform operation | HA Supervisor call | Notes |
| --- | --- | --- |
| `Create` | `POST /store/{app}/install` (background task; wait for `ATTR_JOB_ID` completion), then if `start = true` → `POST /apps/{app}/start`, wait for `state == "started"` | The install handler at `store.py:apps_app_install` returns `{job_id}` when `background=true` — Provider must poll `/jobs/{uuid}` (see `/jobs/{uuid}` route in `__init__.py`). |
| `Read` | `GET /apps/{app}/info` | Must be **idempotent and side-effect-free**. Called after every operation and on every `terraform plan`. |
| `Update` (options changed) | `POST /apps/{app}/options` | If the running add-on needs to be restarted for options to take effect, Provider calls `POST /apps/{app}/restart` after options apply and waits for `state == "started"`. |
| `Update` (state change — start/stop) | Handled via `lifecycle` and **separate Provider actions** (Terraform 1.5+ `action` block) — NOT via in-place update | See Differentiators → Provider Actions below. |
| `Delete` | `POST /apps/{app}/uninstall` with `remove_config = false` (default) | The `SCHEMA_UNINSTALL` schema's default. Config can be retained; terraform-managed add-ons default to NOT removing config on `terraform destroy` because re-install on next apply would otherwise fail schema validation. |

**Drift semantics:** `Read` always returns latest state. The Provider uses the **options hash** (SHA-256 of the
normalized options JSON, with secrets stripped) as the drift key, NOT the `state` field, because `state` flutters
(`startup` → `started` → `stopped` during restarts).

---

## Table Stakes Per Resource

These are the features the Provider MUST expose for `terraform apply` to be correct, predictable, and not generate
spurious diffs. Missing any of these makes the Provider unusable. Confidence HIGH — each is verified either against
primary source (Supervisor code), primary source (HashiCorp plugin framework docs), or both.

### Category: Schema

| Feature | Why required | Complexity | Source |
| --- | --- | --- | --- |
| Resource schema with `Required`/`Optional`/`Computed`/`Sensitive` markers | `terraform plan` cannot run without a schema | Low | [`plugin/framework/resources`](https://developer.hashicorp.com/terraform/plugin/framework/resources) |
| `Sensitive: true` on add-on options whose add-on schema marks as secret | Secrets must not appear in `terraform plan` output or state diffs | Medium — needs to thread `ATTR_SCHEMA` from Supervisor into Provider at startup or refresh time | [`apps.py:info_data` expose_options gating](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/apps.py) — options already gated by `ROLE_ADMIN/ROLE_MANAGER` |
| `WriteOnly` arguments (framework 1.x) for one-shot secrets | Tokens / one-time credentials should never be persisted in state | Low | [`plugin/framework/resources/write-only-arguments`](https://developer.hashicorp.com/terraform/plugin/framework/resources) — Provider framework 1.x feature. **MEDIUM confidence** — framework API surface may shift; verify in Phase-1 implementation. |
| Provider block with `endpoint` + `token` arguments | Auth config; no provider block = no resource access | Low | Provider-config pattern from [`goauthentik/terraform-provider-authentik`](https://github.com/goauthentik/terraform-provider-authentik) (same REST + bearer-token shape) |

### Category: CRUD

| Feature | Why required | Complexity | Source |
| --- | --- | --- | --- |
| `Create` (install + optionally start) | Without it, `terraform apply` creates nothing | Medium — install is async; Provider must poll `/jobs/{uuid}` until completion | Supervisor `store.py:apps_app_install` returns `{job_id}` when `background=true`; `/jobs/{uuid}` route in `__init__.py` |
| `Read` returning schema-shaped data | State refresh after every operation and on `plan` | Low | Supervisor `apps.py:info` |
| `Update` for options change | Options must be updatable in place | Medium — must validate against `ATTR_SCHEMA` first, restart if needed | Supervisor `apps.py:options` |
| `Delete` (uninstall) | Without it, `terraform destroy` leaks add-ons | Low | Supervisor `apps.py:uninstall` |
| **Idempotency on Read**: must be side-effect-free and not alter state | A non-idempotent Read causes infinite diff loops | Low — verified by reading `apps.py:info_data` (read-only) | Supervisor primary source |
| **Idempotency on Create**: re-running `apply` on an already-installed add-on must report "no changes" | Otherwise `terraform apply` is unsafe to re-run | Medium — Provider must detect "already installed" by slug in `GET /apps`, skip the install POST, and run start if `start=true` | Derived from `apps.py:_list_apps_data` |
| **State drift detection**: plan shows a diff when state ≠ desired | Otherwise `terraform plan` is useless | Low | Standard Terraform contract |

### Category: Lifecycle (meta-arguments)

These are configuration-side features users add in their `*.tf` files. The Provider must support them via the
framework; it does not need to "implement" them — but its schema must be designed so they work.

| Feature | Why required | Phase 1? | Notes |
| --- | --- | --- | --- |
| `lifecycle.prevent_destroy = true` | Users may want to mark an add-on as "managed but never destroyed" (e.g., `core`, `auth-providers`) | YES — schema-level support | Standard framework support |
| `lifecycle.create_before_destroy = true` | Rarely useful for add-ons (slug is unique per repository) but allowed | YES | Standard framework support |
| `lifecycle.ignore_changes = [...]` | Common: ignore `state`/`update_available` because they change independently of config | YES | Standard framework support; document in DOCS.md which fields are safe to ignore |
| `lifecycle.replace_triggered_by` | Useful when an add-on depends on another resource (e.g., repository add) and must be replaced if the repository changes | YES | Standard framework support |
| `lifecycle.precondition` / `postcondition` | E.g., `precondition { condition = self.state != "error"; error_message = "..." }` | YES | Standard framework support; one of the most powerful user-facing primitives |
| `for_each` over a set of add-ons (e.g., a map of `slug` → `options`) | Common pattern for managing N add-ons from one block | YES — schema must use `TypeSet`/`TypeMap` where the underlying collection is order-independent | Standard framework support |
| `count` | Less idiomatic than `for_each` but allowed | YES | Standard framework support |
| `depends_on` | E.g., `homeassistant_addon_repository` must exist before `homeassistant_addon` in same repository | YES | Standard framework support |

### Category: State

| Feature | Why required | Complexity | Notes |
| --- | --- | --- | --- |
| `ImportState` by slug (e.g., `terraform import homeassistant_addon.meridian local/meridian`) | Adopt pre-existing add-ons (Phase-1 add-ons, anything manually installed) into TF state | Low | Framework `ImportStatePassthroughID` works if ID == slug. **MULTI-ATTRIBUTE CASE:** for repository-scoped add-ons, `ImportState` parses `repo/slug` or accepts an `import_block_id_format`. **MEDIUM confidence** — see Sources note on multi-attribute imports. |
| `ImportState` populating `schema_ui` (`ATTR_SCHEMA` from Supervisor) | Without schema, imported options cannot be type-checked | Medium | Provider must round-trip options through `ATTR_SCHEMA` during Import; see PITFALLS.md |
| `StateUpgrader` for schema-version migration | Forward compatibility for state files written by older Provider versions | Low (deferred to phase 2 if no schema change yet) | Framework `UpgradeState` — required once Phase-2 adds attributes |
| Local state backend in `/data/terraform.tfstate` | Single-host setup, no S3 in Phase 1 | Low | Per PROJECT.md key decisions |
| `Ignore`/`Move` state operations | Out of Phase-1 scope unless a rename is needed; framework supports them for free | — | — |

### Category: Provider-side

| Feature | Why required | Complexity | Notes |
| --- | --- | --- | --- |
| Bearer-token auth via provider block | Without it, no requests succeed | Low | PROJECT.md fixed this decision (vs mTLS/OAuth) |
| Pluggable `endpoint` URL | User may run the Bridge on a non-default port or Tailscale hostname | Low | Trivial |
| `Configure` validates the token (`GET /supervisor/ping`) at provider startup | Fail-fast vs first-resource error | Low | Supervisor `supervisor.py:ping` |
| Retry on transient HTTP errors (502/503/504, network errors) | Supervisor can return 503 during concurrent operations | Medium | Use a bounded exponential backoff (e.g., 3 retries, 250ms→1s) |
| Polling for async Supervisor jobs (install, uninstall) | Install returns `{job_id}`; Provider must wait | Medium | Use `/jobs/{uuid}` endpoint |
| Validation that the configured `options` conform to `ATTR_SCHEMA` **before** sending POST | Better errors, faster feedback | Medium | Bridge can call Supervisor's own `apps/{app}/options/validate` (`apps.py:options_validate`) for free |
| Computed `state` attribute with `UseStateForUnknown()` plan modifier | Suppress `(known after apply)` in plans when state was already known | Low | Framework `stringplanmodifier.UseStateForUnknown()` |
| `RequiresReplace()` plan modifier on `slug` and `repository` | Changing these requires uninstall + reinstall | Low | Framework `stringplanmodifier.RequiresReplace()` |
| Provider `SchemaVersion` field | Required even if v1; future-proofs for upgrades | Trivial | — |

### Category: Auth (Bridge ↔ Supervisor)

| Feature | Why required | Complexity | Notes |
| --- | --- | --- | --- |
| Add-on → Supervisor: `SUPERVISOR_TOKEN` (`Authorization: Bearer`) | Established pattern (meridian uses `curl -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" http://supervisor/...`) | Trivial | Supervisor injects `SUPERVISOR_TOKEN` env var; add-on `hassio_api: true` |
| Provider → Bridge: bearer token, generated and rotated by the Bridge | Provider must authenticate to the Bridge | Medium | Token surfaced via add-on options UI; rotation requires Bridge to keep an old-token grace period |
| Token persisted in `/data/bridge-token` | Token survives container restart | Low | Mirror meridian's `/data/.claude` pattern |
| Per-request logging in Bridge (audit trail) | Diagnose "why did the Provider just uninstall my add-on?" | Low | Log to stdout; HA captures in supervisor log |

---

## Differentiators (Deferred)

Features that are NOT table stakes but are valuable enough to plan for in Phase 2+. Each has a complexity note so
the Phase-2 scope is realistic. Confidence varies — most are HIGH-confidence extrapolations from Supervisor primary
source, a few are MEDIUM because they touch unstable V2-only endpoints.

### Phase 2 candidates

| Resource / feature | Why differentiator | Complexity | Notes / Supervisor endpoint |
| --- | --- | --- | --- |
| `homeassistant_addon_repository` (Phase-1 stretch if budget allows; else Phase 2) | Manage add-on store URLs declaratively — required if user has multiple repos | Low | Supervisor `store.py:repositories_list`, `add_repository`, `remove_repository`, `repositories_repository_repair` |
| `homeassistant_addon_update` action (or in-place `version` field with `RequiresReplace()`) | Pin / roll forward / roll back add-on versions | Low | Supervisor `store.py:apps_app_update`; `SCHEMA_UPDATE` accepts `backup: bool, background: bool` |
| `homeassistant_addon_options_validate` data source | Pre-flight check that options satisfy `ATTR_SCHEMA` without applying | Low | Supervisor `apps.py:options_validate` (returns `{message, valid, pwned}`) |
| Provider `Actions`: `homeassistant_addon_start`, `homeassistant_addon_stop`, `homeassistant_addon_restart`, `homeassistant_addon_rebuild`, `homeassistant_addon_stdin` | Terraform 1.5+ action blocks give users one-off imperative verbs in `*.tf` without leaving IaC | Medium — uses framework Actions API | All endpoints exist in `apps.py` |
| `homeassistant_backup` resource | Backups are the prerequisite for safe add-on upgrades | Medium | Supervisor `backups.py` exposes full backup / restore / freeze / thaw / download endpoints |
| `homeassistant_addon_stats` data source | Live CPU/memory/network for an add-on | Trivial | Supervisor `apps.py:stats` |

### Phase 3+ candidates

| Resource | Why differentiator | Complexity | Notes |
| --- | --- | --- | --- |
| `homeassistant_core` resource | Manage HA Core itself: update / restart / stop / start / check | Low | Supervisor `homeassistant.py` |
| `homeassistant_supervisor` resource | Update Supervisor, toggle diagnostics, change channel | Low | Supervisor `supervisor.py` |
| `homeassistant_host` resource | Host reboot, shutdown, options | Medium — touches host, not containers | `host.py` |
| `homeassistant_network` / `homeassistant_dns` resources | Manage network interfaces, VLANs, DNS | Medium | `network.py`, `dns.py` |
| `homeassistant_discovery` resource | mDNS service announcements (e.g., expose add-on to LAN as a printer) | Medium | `discovery.py` |
| `homeassistant_service` resource | User-defined service mappings | Low | `services.py` |
| `homeassistant_mount` resource | CIFS/NFS mounts | Low | `mounts.py` |
| **Home Assistant Core entities** (Phase N, very different): `homeassistant_automation`, `homeassistant_script`, `homeassistant_scene`, `homeassistant_integration`, `homeassistant_area`, `homeassistant_zone`, `homeassistant_device`, `homeassistant_dashboard`, `homeassistant_entity_registry_*` | The full IaC story for HA | High | These hit the **HA Core REST API** (`/api/...`), not Supervisor. Would require a separate Bridge sub-app or a second Provider. **MEDIUM confidence** on scope; the Core API surface is large and unstable across HA versions. |

### Differentiators NOT to build (Phase-N anti-priorities)

| Anti-differentiator | Why not | What to do instead |
| --- | --- | --- |
| `terraform plan -destroy` showing the diff of every secret | Secrets in options would appear in plan output | Mark secrets `Sensitive: true` and instruct users to keep secrets in env vars or `*.auto.tfvars` (gitignored) |
| A GUI for browsing managed add-ons | The HA add-on store already provides this | Use the HA UI for browsing; use TF for declaratively managing a subset |
| Provider-side `apply` queueing | Terraform CLI already serializes resource operations | None |
| Per-resource polling daemon running on the Bridge | State is queried on demand, not pushed | Use Read on demand; consider webhook events in Phase N (long-horizon) |

---

## Anti-Features (Explicitly Out of Scope for All Phases)

What the Bridge + Provider MUST NOT do. Each row is documented so a future contributor doesn't re-add it.

| Anti-feature | Why avoid | What to do instead |
| --- | --- | --- |
| Write arbitrary files to `/config`, `/share`, `/media`, `/data` from the Bridge | The Bridge is a thin pass-through; filesystem writes are the add-on's job | Add-ons read `/data/options.json` (HA-managed) and do their own writes. Bridge does not touch files. |
| Restart Home Assistant Core from the Provider | Disrupts every running add-on and breaks live user-facing automations | Core restart is a Phase-3+ `homeassistant_core` resource with explicit `prevent_destroy` defaults and a `lifecycle.precondition` requiring user ack. NEVER in Phase 1. |
| Modify the host OS (reboot, shutdown, OS update) | Same as Core restart but with more blast radius | Phase-3 `homeassistant_host` resource, gated by `lifecycle.precondition` |
| Read or exfiltrate HA Core secrets (`homeassistant_api`, `auth_api` tokens) | The Bridge does not need them; exposing them in TF state is a leak vector | Bridge stays at Supervisor scope. Provider does not surface Core secrets. |
| Execute arbitrary commands inside an add-on's container | `stdin` endpoint exists in Supervisor but is for add-on-specific protocols, not shell. Misuse is a backdoor | Do not wrap `stdin` as a Phase-1 Provider feature; if Phase-N adds it, document it as "add-on-protocol only" |
| Run the Provider server inside the HA Supervisor itself | Mixing Provider binary lifecycle with Supervisor lifecycle is operationally fragile | Provider is a separate Go binary built from local source, downloaded by `terraform init` from a local dev_overrides directory or a co-located `terraform-provider-homeassistant` directory (per PROJECT.md). |
| Auto-rotate the bearer token without a grace period | Running `terraform apply` while rotation is mid-flight produces 401s on the in-flight request | Token rotation keeps the old token valid for ≥ 1 hour after rotation; new tokens issued via POST to a Bridge endpoint that returns `{new_token, grace_expires_at}` |
| Manage Supervisor itself (update, repair, restart) from Phase 1 | Touching Supervisor from a Provider whose data depends on Supervisor is a circular dependency | Phase-3+ resource; Phase 1 Provider is read-only against Supervisor endpoints other than `/apps/{app}/*` and `/store/...` |
| Embed the OpenTofu binary in the add-on | Duplicates the binary the user already has, and adds a maintenance burden | User runs `tofu`/`terraform` from their workstation; Provider is downloaded per `terraform init` |

---

## Lifecycle Hooks

User-facing primitives the Provider must support, and the framework mechanisms that implement them. Cross-reference
with the meta-arguments table above.

### Terraform lifecycle meta-arguments (user side)

| Meta-argument | Phase 1? | Notes |
| --- | --- | --- |
| `lifecycle.create_before_destroy` | YES | Slug is unique per repo so this is rarely meaningful; allow it anyway |
| `lifecycle.prevent_destroy` | YES | Useful for `core`-level add-ons (e.g., `mosquitto`, `samba`) |
| `lifecycle.ignore_changes` | YES | Common: ignore `state`, `update_available`, `version_installed` |
| `lifecycle.replace_triggered_by` | YES | Useful for repository-dep cascades |
| `lifecycle.precondition` | YES | Provider's `Schema` must be rich enough for meaningful conditions |
| `lifecycle.postcondition` | YES | Same |
| `action_trigger` (Terraform 1.5+ on `resource` blocks) | Phase 2 (via Provider Actions) | Bridge can emit webhook-style events in Phase N |
| `import` block (Terraform 1.5+) | YES | Import by ID; multi-attribute parsing for `repo/slug` |

### Framework-level resource lifecycle (Provider side)

| Resource method | Phase 1? | Implementation hint |
| --- | --- | --- |
| `Schema()` | YES | Returns `schema.Schema` with the attributes in the Phase-1 schema table |
| `Configure()` | YES | Provider-level: builds Bridge HTTP client from provider block |
| `Create()` | YES | `POST /store/{app}/install` (background), poll `/jobs/{uuid}`, then `POST /apps/{app}/start` if `start=true` |
| `Read()` | YES | `GET /apps/{app}/info`; if 404 → set `resp.State = nil` so TF knows the resource was deleted out-of-band |
| `Update()` | YES | `POST /apps/{app}/options`; if restart required, `POST /apps/{app}/restart`, poll until `state == started` |
| `Delete()` | YES | `POST /apps/{app}/uninstall`; poll job |
| `ImportState()` | YES | `ImportStatePassthroughID` if single-attribute; parse `repo/slug` for multi-attribute |
| `ModifyPlan()` | YES | Required for `RequiresReplace` on slug/repository, `UseStateForUnknown` on computed |
| `SchemaVersion()` | Trivial (1) | Future-proofs `UpgradeState` for Phase-2 schema changes |
| `Timeouts()` | YES | Use `terraform-plugin-framework-timeouts/resource/timeouts` module |

### Timeouts

Per-framework conventions, all four CRUD verbs need configurable timeouts:

| Verb | Default | Why this duration | Notes |
| --- | --- | --- | --- |
| `create` | 10m | Install can pull a 200MB+ image and start a multi-container add-on | Long-tail: authentik, gatus |
| `update` | 5m | Options apply + optional restart | Most updates are <30s; this is generous |
| `delete` | 5m | Uninstall + image cleanup | Most uninstalls are <30s |
| `read` | 30s (default framework) | Idempotent read; should never be slow | — |

### Drift detection strategy

Drift = state ≠ reality. The Provider distinguishes **config drift** (user wants X but reality is Y) from **state
churn** (reality is fluttering between acceptable values).

- **Config drift** = diff in `options`, `boot`, `auto_update`, `ingress_panel`, `watchdog`. The Provider detects by
  comparing `desired` to `Read()`'s normalized return; emits a `+ update` plan line.
- **State churn** = `state` field flipping between `startup`/`started` during restarts. The Provider uses
  `UseStateForUnknown()` so re-plans after a successful apply don't show `(known after apply)` for `state`; users
  who find this noisy add `lifecycle.ignore_changes = [state]` to their block.
- **Version drift** = `version_latest` ≠ `version_installed`. The Provider surfaces `update_available = true` in
  state but does NOT trigger Update — version bumps are an explicit user choice (matches Supervisor UX; an
  automatic update is gated behind `auto_update = true` and is itself a Phase-2 resource).
- **Hard drift** = resource gone (404 from `/apps/{app}/info`). Framework convention: set
  `resp.State.RemoveResource()` so TF plans to recreate. This is the right behavior for an add-on manually
  uninstalled via HA UI.

### Retry on transient error

Bounded exponential backoff in the Provider's HTTP client:

| Status | Retry? | Max attempts | Backoff |
| --- | --- | --- | --- |
| 5xx (502/503/504) | YES | 3 | 250ms → 500ms → 1s |
| 408 Request Timeout | YES | 3 | same |
| 429 Too Many Requests | YES (respect `Retry-After` header) | 3 | header value, capped at 30s |
| 4xx (other) | NO | — | Caller bug or auth issue |
| Network errors (timeout, connection reset) | YES | 3 | same |

Provider does NOT retry on 401 — that's an auth misconfig, not a transient failure.

---

## Sources

**Primary (HIGH confidence)** — verified during research:

- [`home-assistant/supervisor/supervisor/api/apps.py`](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/apps.py) — verified Phase-1 CRUD endpoints (`info`, `options`, `start`, `stop`, `restart`, `uninstall`, `rebuild`, `stdin`, `security`, `stats`, `options_validate`, `options_config`) and schemas (`SCHEMA_OPTIONS`, `SCHEMA_UNINSTALL`, `SCHEMA_REBUILD`, `SCHEMA_SECURITY`, `SCHEMA_SYS_OPTIONS`).
- [`home-assistant/supervisor/supervisor/api/store.py`](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/store.py) — verified Phase-1 install + repository endpoints (`apps_app_install`, `apps_app_info`, `apps_app_update`, `repositories_list`, `add_repository`, `remove_repository`, `repositories_repository_repair`).
- [`home-assistant/supervisor/supervisor/api/__init__.py`](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/__init__.py) — verified route table; `/jobs/{uuid}` for async; V1 routes (legacy `addons`) vs V2 routes (`apps`); V2 is feature-flag-gated (`SUPERVISOR_V2_API`).
- [`home-assistant/supervisor/supervisor/api/supervisor.py`](https://github.com/home-assistant/supervisor/blob/main/supervisor/api/supervisor.py) — verified `supervisor/ping` and `supervisor/info`.
- [`home-assistant/supervisor/supervisor/const.py`](https://github.com/home-assistant/supervisor/blob/main/supervisor/const.py) — verified `AppState` enum (`startup`, `started`, `stopped`, `unknown`, `error`), `AppBoot` enum (`auto`, `manual`), `AppBootConfig` enum (`auto`, `manual`, `manual_only`), auth headers (`HEADER_TOKEN = X-Supervisor-Token`).
- [`home-assistant/supervisor/AGENTS.md`](https://github.com/akentner/homeassistant-addons/blob/main/AGENTS.md) (this repo) — confirmed add-on → Supervisor auth pattern via `SUPERVISOR_TOKEN` and `Authorization: Bearer` header (meridian uses exactly this).
- [HashiCorp `terraform-plugin-framework` Timeouts](https://developer.hashicorp.com/terraform/plugin/framework/resources/timeouts) — verified timeout module API and `terraform-plugin-framework-timeouts` dependency.
- [HashiCorp `terraform-plugin-framework` Import State](https://developer.hashicorp.com/terraform/plugin/framework/resources/import) — verified `ImportStatePassthroughID` (single-attribute) and multi-attribute parsing pattern.
- [HashiCorp `terraform-plugin-framework` Plan Modification](https://developer.hashicorp.com/terraform/plugin/framework/resources/plan-modification) — verified `RequiresReplace()`, `UseStateForUnknown()` modifiers.
- [HashiCorp Lifecycle meta-arguments](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle) — verified `create_before_destroy`, `prevent_destroy`, `ignore_changes`, `replace_triggered_by`, `precondition`, `postcondition`.
- [HashiCorp Import overview](https://developer.hashicorp.com/terraform/language/import) — verified `import` block, `generate-config-out`.
- [Terraform plugin framework overview](https://developer.hashicorp.com/terraform/plugin/framework) — confirmed `terraform-plugin-framework` is the recommended SDK for new providers.

**Secondary (MEDIUM confidence)** — verified for reference patterns but not authoritative:

- [`goauthentik/terraform-provider-authentik`](https://github.com/goauthentik/terraform-provider-authentik) (138 stars, 47 forks, latest commit recent) — verified as an active framework-based provider for a REST + bearer-token API with the same shape the Bridge needs. Used as a reference pattern; not authoritative for HA specifics.
- [`authentik_user` resource docs](https://raw.githubusercontent.com/goauthentik/terraform-provider-authentik/main/docs/resources/user.md) — verified schema conventions: `Required` / `Optional` with defaults / `Sensitive` / `Read-Only` (id) / `Generated` cross-references (groups, roles).

**Tertiary (LOW confidence, verified absence)**:

- GitHub topic [`terraform-provider-homeassistant`](https://github.com/topics/terraform-provider-homeassistant) — **zero repositories**. Confirms green-field.
- Terraform Registry search `homeassistant` — no providers indexed. (Registry search requires JS; only confirmed the absence by reading the rendered empty-state.)
- OpenTofu Registry search `homeassistant` — empty.
- Several guessed candidate repos (`ionutbalosin/...`, `sergeymirzoyan/...`, `devops-services/...`, `martinbjeldbak/...`, `MaximeHeckel/...`, `sl1pm4t/...`, `bpg/...`) — **all 404**. None exist publicly.

**Repository-internal (HIGH confidence)**:

- `PROJECT.md` — Phase-1 scope, co-located provider decision, bearer-token auth decision, local state backend decision.
- `AGENTS.md` — 3-file versioning scheme; `.upstream.yaml` does NOT apply to `terraform-bridge/` (no upstream).
- `meridian/run.sh` — confirmed `SUPERVISOR_TOKEN` + `Authorization: Bearer` + `http://supervisor/` pattern.

---

## Open Questions for Phase-1 Implementation

1. **Phase-1 stretch**: include `homeassistant_addon_repository` in Phase 1 or defer to Phase 2? PROJECT.md marks
   it "optional in Phase 1". Recommendation: defer — focus Phase 1 on getting `homeassistant_addon` rock-solid with
   full lifecycle, imports, timeouts, and drift detection. The repository resource is a one-call CRUD with no
   lifecycle complexity.
2. **Options schema translation**: how does the Provider translate Supervisor's voluptuous JSON-schema
   (`ATTR_SCHEMA` field) into `terraform-plugin-framework` schema attributes at runtime? Static schema per add-on
   is straightforward; dynamic schema (the add-on's schema is read at runtime) is harder. **Phase-1 fallback**:
   treat `options` as a `TypeMap` of `String` and rely on Bridge-side validation via `apps/{app}/options/validate`.
   Defer typed-schema magic to Phase 2.
3. **V1 vs V2 Supervisor endpoints**: V2 (`/apps`, `/apps/{app}/info`) requires the `SUPERVISOR_V2_API` feature
   flag. The Bridge must support both. Recommendation: target V1 (`/addons`, `/addons/{app}/info`) in Phase 1 for
   broad compatibility; add V2 in Phase 2 as the V1 routes are deprecated (note: `list_apps_v1` returns
   `addons`, `info` is at `/addons/{app}/info`, all V1 routes are confirmed in `__init__.py:_register_apps`).
4. **`pwned` secrets**: Supervisor's `apps/{app}/options/validate` returns `pwned: bool|None` for known-leaked
   secrets. The Bridge should expose this as a `precondition` check or a warning. Phase 1: surface it in the
   Provider's `Create`/`Update` error path.
5. **`start` semantics on Create**: PROJECT.md is silent. Recommendation: default `start = true` (Phase-1 column
   table) because install-without-start is rarely useful; allow `start = false` for staged rollouts.

---

_Research completed: 2026-08-31 | Ready for roadmap: yes (after PHASE 1 / STRETCH / DEFERRED split is confirmed
in discuss-phase)_
