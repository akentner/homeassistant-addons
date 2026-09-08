# Domain Pitfalls: OpenTofu Configuration Bridge for Home Assistant

**Domain:** Declarative remote-system management of a Home Assistant Supervisor add-on, accessed via an external
OpenTofu provider over HTTPS/Tailscale. **Researched:** 2026-08-31 **Confidence:** HIGH for HA Supervisor API behaviour
(verified against current `home-assistant/supervisor` source code on `main`); HIGH for the Terraform/OpenTofu plugin
framework (verified against current HashiCorp Developer docs); MEDIUM for Tailscale Serve semantics (verified against
current tailscale.com docs); LOW noted where flagged.

This is a _consequence-driven_ pitfall catalogue: each entry is paired with a concrete prevention strategy tied to a
phase/requirement so the roadmapper can wire it into acceptance tests and the planner can write executable checks. Every
pitfall was chosen because it is specific to _this_ system (Bridge → Supervisor → real HA install, with privileged
credentials, reached over Tailscale, talking to a single OpenTofu provider), not generic IaC advice.

---

## Summary

Three themes dominate this catalogue:

1. **Privilege concentration.** The Bridge holds `SUPERVISOR_TOKEN`, which can do _anything_ the Supervisor can do
   (install apps, restart Core, edit `/config`). From a security model perspective, the Bridge is the root of trust for
   the Provider. Every token-handling decision flows from this.
2. **Two clocks, one state file.** The OpenTofu state file lives in `/data/terraform.tfstate`. OpenTofu provides
   correctness through file locking; the HA add-on runtime provides correctness through add-on restart lifecycle (which
   can be initiated by Supervisor, HA Core, or user). The interaction of these two lifecycles is the source of most
   state-management pitfalls.
3. **The Supervisor API is _eventually consistent_ and partially _asynchronous_.** `install` returns a `job_id`;
   `start`/`stop`/`uninstall` block the HTTP request but use `asyncio.shield` so a Supervisor restart mid-op leaves the
   system in an unknown state. The Provider must model these operations explicitly, not assume synchronous CRUD
   semantics.

The roadmap implications are listed in §11. Every pitfall has a tied phase or requirement in §12 (Prevention Matrix).

---

## Quick Architecture Recap (so the pitfalls below make sense)

```
[OpenTofu on laptop/CI]
       │
       │  HTTPS over Tailscale
       │  Authorization: Bearer <BRIDGE_TOKEN>
       ▼
[terraform-bridge add-on container]      ← privileged: has SUPERVISOR_TOKEN
       │
       │  http://supervisor/
       │  Authorization: Bearer ${SUPERVISOR_TOKEN}
       ▼
[HA Supervisor]                          ← root: can edit /config, restart Core, etc.
       │
       ▼
[Home Assistant Core + add-ons]
```

State file lives at `/data/terraform.tfstate` inside the Bridge container (HA add-on volume, persistent across restarts
but wiped on uninstall).

---

## 1. Auth / Security

### Pitfall S-1: SUPERVISOR_TOKEN leaked to Provider logs or error bodies

**What goes wrong:** The Bridge authenticates to Supervisor with `SUPERVISOR_TOKEN`. If the Bridge ever echoes the
request it sent (e.g. for debugging, on retry, in a verbose error message), the token is exposed. If the Bridge's error
JSON includes the upstream request body, the Provider side can also leak it via TF_LOG=DEBUG or via the diagnostic
plugin framework surfaces.

**Why it happens:** `curl -v` in `run.sh`; a debug `log.Printf("%+v", req)` line; a debug "include upstream response
body on error" handler; an unhandled exception whose traceback includes env vars.

**Consequences:** The token is the Supervisor's root credential. Anyone holding it can install/uninstall arbitrary
add-ons, edit `/config`, restart Core, dump the entire HA installation. Tailscale isolation does not save you: the token
alone is sufficient.

**Prevention:**

- The Bridge **never reads `SUPERVISOR_TOKEN` into anything other than the outbound HTTP client config** (e.g. an
  `http.Client` constructed with a custom `Transport` that injects the header). Never `os.Getenv` it into a struct, log
  it, or marshal it to JSON.
- The Bridge HTTP API returns error bodies **as `{error_code, message, job_id?}` only** — never the upstream request,
  never the upstream response, never env, never the request ID. This pattern must be enforced in the error-handling
  middleware, not just in handlers.
- The Provider's client wraps `*http.Response` so the body is read once, redacted for `Authorization` headers, and
  released. `TF_LOG` debug output must not include the request body for any operation against `/auth/*` (Bridge token
  endpoints).
- Token rotation: the **Bridge bearer token** (Provider→Bridge) is short-lived and rotated by the Bridge on first
  install and on every Bridge restart if `rotate_token_on_start` is set. The **SUPERVISOR_TOKEN** (Bridge→Supervisor) is
  env-injected by Supervisor and immutable for the lifetime of the container.

**Detection:**

- `grep -r "SUPERVISOR_TOKEN" terraform-bridge/` finds zero hits in code paths (only Dockerfile ENV pass-through).
- A unit test on the error middleware asserts that no upstream response body or request is reachable from the public
  error body.

**Phase tie-in:** Phase 09.1 (Bridge scaffold) — error middleware + token scoping.

**Sources:** Supervisor source confirms token-based auth and role enforcement (`extract_supervisor_token`,
`SecurityMiddleware.token_validation` in `supervisor/api/middleware/security.py`); HA add-on docs confirm
`SUPERVISOR_TOKEN` env injection (`developers.home-assistant.io/docs/add-ons/communication`).

---

### Pitfall S-2: Bridge bearer token reuse after rotation

**What goes wrong:** The Bridge auto-rotates its bearer token on a schedule (or on user demand). The Provider caches the
token in `~/.config/tofu/credentials` or equivalent. After rotation, the Provider's cached token is invalid →
`terraform plan` fails with 401 → user manually updates credentials → CI re-applies and succeeds, masking the underlying
issue.

**Why it happens:** CI/laptop has no notification of the rotation. Long-lived credentials in shared CI vaults go stale.

**Consequences:**

- Stale Provider breaks apply in CI without warning (noisy, looks like a bug).
- Worse: if the user rotates the token to invalidate a compromised Provider, the compromised Provider cannot tell
  whether the new token came from rotation or from a re-paste into a phishing form.

**Prevention:**

- The Bridge rotates the token **only on explicit user action** (button in HA add-on UI) by default. Auto-rotation off.
  Optional schedule via add-on option, defaulting to "manual only".
- When the Bridge does rotate, it returns **both** the old token (with a short grace period, e.g. 5 minutes) and the new
  token in the rotation response. The Provider receives a `401` with header
  `X-Bridge-Token-Rotated: <new_token_fingerprint>` and uses this as a hint to re-prompt the user, not to silently
  re-auth.
- Provider stores the token with a `last_validated_at` timestamp and emits a warning at `tofu apply` time if the token
  is older than 30 days (configurable).
- The Bridge token never appears in HA logs (see S-1). To inspect it, the user must view the add-on UI or read
  `/data/bridge-token` directly (the file is `chmod 600`).

**Detection:**

- Provider has an integration test: rotate token via mock Bridge, assert 401 + rotation header, assert retry succeeds
  with new token after manual intervention.

**Phase tie-in:** Phase 09.1 (auth scaffold) — grace period + rotation header.

---

### Pitfall S-3: CSRF on the Bridge HTTP API

**What goes wrong:** The Bridge listens on the user's Tailscale network. Even though Tailscale is private, the user may
browse the web on the same machine. A malicious page could
`fetch('http://100.x.x.x:8099/addons', { method: 'POST', ... })` if the user pasted the URL into an unsecured location —
wait, this doesn't work cross-origin without CORS. **But** an `<img src="http://100.x.x.x:8099/apply">` or a `<form>`
POST _does_ fire on plain HTTP if the URL is reachable from the host. Tailscale IPs are RFC1918; in practice browsers
refuse, but tools like `curl --resolve` or compromised VPN clients don't.

**Why it happens:** Bearer-token auth is _not_ CSRF protection against same-origin or trusted-network attackers. Anyone
who can reach the Bridge HTTP port can fire requests with the bearer token if they obtain it once. Bearer auth prevents
unauthorized requests; it does not prevent authorized requests from being fired by something other than the Provider.

**Consequences:** Once an attacker has the bearer token (S-1 leak, shoulder-surf, accidental git commit), they can issue
any Provider-equivalent request as long as they can route to the Tailscale IP. Same exposure as the token itself, but
**CSRF specifically adds the risk of an attacker _initiating_ apply actions through the Provider's running process or a
browser visiting a malicious page**.

**Prevention:**

- Bind the Bridge to the **Tailscale interface only** (`bind: "100.x.y.z:8099"` via add-on option), not `0.0.0.0`. If
  the user's add-on host is not on Tailscale, refuse to start with a clear error.
- Use **`If-Match`/`ETag` style CSRF tokens for state-mutating methods** (POST/DELETE on `/addons/*`, `/apply`). The
  Bridge issues an opaque `X-CSRF-Token` per session; the Provider must echo it. Browsers will not auto-echo custom
  headers on cross-origin form submits, so this defeats naive CSRF.
- Set `Strict-Transport-Security` (HSTS) on responses if HTTPS terminates at the Bridge (it does, since Tailscale Serve
  provides TLS); `Cache-Control: no-store` on responses containing secrets.
- The Bridge MUST NOT serve any HTML that auto-runs the bearer token (i.e. no Swagger UI that exposes the "Authorize"
  button via JS).

**Detection:**

- A negative test: a request _without_ `X-CSRF-Token` to a mutating endpoint returns 403, even with a valid bearer
  token.
- A negative test: `OPTIONS` preflight from a non-Tailscale origin returns CORS-rejected (or no CORS headers at all).

**Phase tie-in:** Phase 09.2 (security hardening).

**Sources:** Tailscale Serve docs (`tailscale.com/kb/1312/tailscale-serve`) confirm Serve adds `Tailscale-User-*`
identity headers but **does not perform application-layer CSRF protection** — that is the Bridge's responsibility. The
"best practice: only listen on localhost" guidance in the Tailscale Serve docs is the same principle: minimise the
listening surface.

---

### Pitfall S-4: Bearer-token auth over plain HTTP only on internal Tailscale

**What goes wrong:** Tailscale already encrypts WireGuard traffic; the bearer token never leaves the encrypted tunnel.
But: (a) the Bridge could be accidentally exposed to a non-Tailscale interface, (b) the user may add an additional
bridge-host device that isn't on Tailscale, (c) future CI may run on a laptop that isn't always on the tailnet.

**Why it happens:** "It's on Tailscale so it's safe" is a common mental shortcut. Tailscale protects the network layer;
it does not enforce application-layer controls.

**Consequences:** If the Bridge accidentally binds to `0.0.0.0` and the user's HA host is on a LAN reachable by another
device, the bearer token traverses plain HTTP. Same for an OpenTofu state file backup containing the token if the user
copies it to an unencrypted USB stick.

**Prevention:**

- **Bind to Tailscale interface only** (see S-3) and reject startup if no Tailscale interface is detected. Add an
  explicit add-on option `bind_address` defaulting to "auto-detect Tailscale IP" so the user has to actively opt out.
- Optionally support **Tailscale HTTPS** via `tailscale serve` integration (the Bridge itself, not HA, runs Tailscale).
  This is opt-in because it requires the Tailscale CLI inside the container.
- State file backup (`/data/backup-*` from HA's backup integration) should **redact the bearer token header** before
  being written. Bridge has a hook that intercepts its own `/data` writes and redacts `<BRIDGE_TOKEN>=...`.
- The DOCS.md must state explicitly: "Tailscale is required. Do not expose this add-on's port to a non-Tailscale
  network."

**Detection:**

- Bridge emits a startup log line with the bound interface: `bridge.listening=100.x.y.z:8099 iface=tailscale0`. Alert if
  `iface != tailscale*`.
- A scanner-style integration test that connects to the Bridge from a non-Tailscale source IP and expects connection
  refused.

**Phase tie-in:** Phase 09.1 (bind enforcement) + DOCS.md (Phase 09.4).

**Sources:** Tailscale Serve best-practice text: "it's best practice to only have the service listen on localhost"
(`tailscale.com/kb/1312/tailscale-serve`).

---

### Pitfall S-5: SUPERVISOR_TOKEN exposure in add-on config schema or HA backup

**What goes wrong:** A developer, in a fit of convenience, exposes the Supervisor token as an add-on option (e.g.
`supervisor_token_override`). It then shows up in `options.json`, which HA backs up to the cloud (if HA Cloud is
enabled), and the user may paste it into an issue tracker. Alternatively, the Bridge writes the token to a config file
that gets included in the HA partial-backup manifest.

**Why it happens:** "I'll just put it in options so the user can rotate it manually." No. The Supervisor injects the
token for a reason.

**Consequences:** Token in HA's `/backup` files. If HA Cloud backup is enabled, in Backblaze/SMB. Token in
`config/.storage/core.config_entries` etc. Same blast radius as S-1.

**Prevention:**

- **Forbidden by code review:** no `supervisor_token` key in `config.yaml` schema. `internal/validate-addon-config.py`
  should warn-or-fail (warn for legacy add-ons, hard-fail for new ones) if the schema contains the literal `token`.
- The Bridge reads `${SUPERVISOR_TOKEN}` from env only. Never accepts it as an option.
- HA partial backup excludes `/data/bridge-*` by default (Bridge writes an `.nobackup` marker or HA's exclusion
  convention).
- DOCS.md states explicitly that the token is auto-injected and not user-configurable.

**Detection:**

- `grep -n "supervisor_token\|SUPERVISOR_TOKEN" terraform-bridge/config.yaml` → must return nothing.
- A CI check that greps for these patterns across all new add-ons.

**Phase tie-in:** Phase 09.1 (config schema).

---

## 2. State Management

### Pitfall ST-1: Concurrent Provider runs corrupting state file

**What goes wrong:** The user runs `tofu apply` from a laptop, then immediately from CI (or two laptops). Both reads
state, both compute plans, both write state back. Without locking, the last writer wins; intermediate state is lost.

**Why it happens:** Tofu local-backend state locking works on a _single host's filesystem_. The Provider is running on
two different hosts; each has its own view of the local state file. The state file actually lives inside the Bridge
container, so technically both Providers should be talking to the one Bridge. **But** the Provider stores its own copy
of state in `terraform.tfstate` _on the laptop_ (default backend) and only POSTs/PATCHes back to the Bridge via the
resource CRUD operations. The Bridge's job is only to manage real-world resources, not to be the state backend.

**Consequences:** Concurrent apply from two hosts → both compute plans referencing the same Bridge resources → both send
write requests → Bridge race conditions on its own internal state (if any), and on Supervisor calls.

**Prevention:**

- **Single-host apply** by default: warn in the Provider schema docs that the local-backend model assumes a single
  concurrent applyer. Do not promise S3-style remote state in Phase 1.
- The Bridge itself maintains **no application-level state** (except the bearer token file). It is stateless w.r.t.
  resource CRUD. Idempotency is derived from the Bridge comparing the requested state to a fresh `GET /apps/{slug}/info`
  response. Concurrent reads → Bridge handles them as it would any HA API call (Supervisor is itself concurrent-safe at
  the add-on level for reads).
- Writes (install/start/stop/uninstall) are **single-flighted at the Bridge per app slug** via an in-process mutex. If
  Provider A is installing `zigbee2mqtt`, Provider B's install request for the same slug blocks until A finishes.
  Different slugs proceed in parallel.
- Document explicitly: do not run `tofu apply` from two machines concurrently. (Future: introduce a real remote backend
  in v1.4+.)
- **File locking**: as defence in depth, the Provider uses `flock`-style advisory file locks on its _own_ state copy
  (this is OpenTofu local-backend default behaviour). This prevents the trivial "two `tofu apply` invocations on the
  same laptop" race. It does not prevent cross-laptop races; the per-slug mutex above is what does.

**Detection:**

- Bridge integration test: fire 10 concurrent install requests for the same slug → exactly one Supervisor `install` call
  is made, the other 9 return "already in progress" with the in-flight job_id.

**Phase tie-in:** Phase 09.3 (Bridge concurrency control).

**Sources:** OpenTofu local-backend docs confirm `flock`-style advisory file locking on the _client_ (laptop) side, with
`force-unlock` for manual recovery (`opentofu.org/docs/language/state/locking/`,
`opentofu.org/docs/language/settings/backends/local/`).

---

### Pitfall ST-2: Bridge restart during apply loses intermediate state

**What goes wrong:** Provider runs `apply`, sends `install zigbee2mqtt`. Supervisor returns `job_id=abc123` and starts
the install in the background. The Bridge container is restarted (auto-update, HA reboot, user click "Restart"). When
the Bridge comes back up, it has no record of job `abc123`. Provider polls `GET /jobs/abc123` and gets 404.

**Why it happens:** The Bridge is stateless across restarts (it has only the bearer token file in `/data`). Background
job IDs are owned by the _Supervisor_, not the Bridge — so the Bridge could re-poll them on the Provider's behalf. But
the Bridge has no way to know which job_id corresponds to which Provider-initiated operation.

**Consequences:** The Provider sees `404` on `GET /jobs/abc123` and assumes the install failed. The user runs
`tofu apply` again, which sees "not installed" → tries to install → Supervisor says "already installed" → error → user
manually fixes.

**Prevention:**

- The Bridge **does not invent its own job tracking**. Instead, it forwards Supervisor's `job_id` directly back to the
  Provider. The Provider is responsible for polling the **Supervisor's job endpoint via the Bridge** at `/jobs/{uuid}`.
  The Bridge exposes this as a passthrough: `GET /jobs/{uuid} → GET supervisor/jobs/{uuid}`.
- The Bridge maintains a **tiny write-ahead log** at `/data/jobs.jsonl`: for each Supervisor-mutation it forwards, it
  writes `{ts, slug, op, supervisor_job_id, provider_request_id}`. On startup, it reads this file and **re-attaches**
  any in-progress job to the next polling Provider that asks. This log is append-only; rotated daily; size-bounded.
- The `/data` volume persists across Bridge restarts but **not** across uninstall (see ST-3). The WAL survives Bridge
  restart, HA reboot, even HA Core restart.
- On Bridge restart, the Bridge logs `bridge.wal.entries=N` so the user can see how many in-flight jobs were
  re-attached.

**Detection:**

- Integration test: install add-on → kill Bridge container mid-install → restart Bridge → Provider polls via re-attached
  job_id → install completes successfully.

**Phase tie-in:** Phase 09.3 (WAL).

**Sources:** Supervisor source: `/jobs/{uuid}` is a real endpoint, registered in
`supervisor/api/__init__.py::_register_jobs`; jobs persist in `JobManager._jobs` (in-memory) but survive a Supervisor
restart only if the JobManager writes them out (it does via `FILE_CONFIG_JOBS`, see `supervisor/jobs/__init__.py`).

---

### Pitfall ST-3: State file in /data wiped on add-on reinstall

**What goes wrong:** The user reinstalls the Bridge add-on (after a config mistake, after an upgrade with breaking
schema changes, or after running `ha addons reinstall local_terraform-bridge`). HA **wipes `/data`** during reinstall.
The Provider's `terraform.tfstate` is gone. The next `tofu plan` shows "all resources need to be created" → user runs
apply → Provider tries to install add-ons that are already installed → errors.

**Why it happens:** HA add-on reinstall = wipe + re-pull image + re-create container. `/data` is add-on-scoped, not
repository-scoped. There is no automatic backup.

**Consequences:** A routine reinstall loses state. The user must re-import every resource, or accept drift and re-apply
(which double-installs if not idempotent).

**Prevention:**

- **DOCS.md must warn loudly:** "Reinstalling this add-on wipes `/data/terraform.tfstate`. Export the state file via
  `tofu state pull > backup-$(date).tfstate` BEFORE reinstalling."
- The Bridge provides a `/state/export` and `/state/import` endpoint pair that round-trips the state file via the
  Provider. CI workflows can call `tofu state pull` before any reinstall.
- **Optional improvement (Phase 2):** auto-restore from HA's own `/backup` partial addon_config snapshot — but HA's
  backup integration does **not** back up `/data` by default for add-ons that don't declare it. Even if declared,
  restoring requires the user to pick a backup and "restore partial", which is interactive.
- Belt-and-braces: the Bridge writes a **secondary state copy** to `/mnt/data/ha-addon-config-passthrough` if the user
  has `map: [addon_config:rw]` set. This is the same `/config/addons/<slug>/` path that HA's backup integration
  snapshots by default. **Enable this by default** for the Bridge so HA's standard backup covers state.

**Detection:**

- A documented runbook step: "Before `ha addons reinstall local_terraform-bridge`, run `tofu state pull`."
- A startup-time Bridge warning if it detects `/data/terraform.tfstate` is missing but
  `/config/addons/local/terraform-bridge/terraform.tfstate` exists → offer to restore.

**Phase tie-in:** Phase 09.1 (config schema `map: [addon_config:rw]`) + Phase 09.4 (DOCS.md).

**Sources:** HA add-on docs (`developers.home-assistant.io/docs/add-ons/configuration`) confirm `/data` is the
persistent volume, and `map: [...]` controls additional bind mounts into the container. There is no implicit HA-backup
integration for `/data`.

---

### Pitfall ST-4: State drift — state says installed, reality says not

**What goes wrong:** User uninstalls an add-on via the HA UI (not through the Provider). State file still has the
resource. Next `tofu plan` → "0 to add, 0 to change, 1 to destroy" — Provider tries to uninstall the not-installed
add-on → Supervisor returns 404 → Provider marks the resource as "tainted" → user is confused.

**Why it happens:** Terraform's mental model is "state = ground truth". When reality diverges from state, Terraform
plans to _destroy_ the missing resource. For an add-on that's already been removed manually, this means trying to call
`/addons/{slug}/uninstall` on a non-existent add-on.

**Consequences:** Noisy plans; possible chain reactions if other resources depend on the uninstalled one.

**Prevention:**

- The Provider's `Read` function always `GET /apps/{slug}/info` and matches against state. If the resource is gone, the
  Provider **drifts** the state to "removed" and presents a `tofu plan` output that says "1 to remove" rather than "1 to
  destroy".
- The Provider also re-checks _during_ `apply`: before issuing `uninstall`, it does `GET /apps/{slug}/info` again. If
  404, it skips the call and just removes the state entry, returning "already removed (drift reconciled)".
- This is the framework's `ResourceWithImportState` + `Read` returning `resp.State.RemoveResource(...)` pattern. See the
  framework docs for state-removal on missing remote.
- For _option_ changes (user edits add-on options via UI between applies), the Provider reads them on every `Refresh`
  and reports drift. The user can choose to `tofu apply -refresh-only` to reconcile.

**Detection:**

- Integration test: Provider installed add-on X → user uninstalls X via HA UI → Provider `Read` returns "removed" →
  `tofu plan` shows drift, not destroy.

**Phase tie-in:** Phase 09.4 (Provider Read semantics).

**Sources:** Terraform plugin framework docs on Read and state removal
(`developer.hashicorp.com/terraform/plugin/framework/resources`); OpenTofu docs on drift
(`opentofu.org/docs/language/resources/behavior`).

---

## 3. Idempotency

### Pitfall I-1: "Already installed" treated as error instead of no-op

**What goes wrong:** Provider wants to install `mosquitto`. Supervisor already has `mosquitto` installed (from a
previous manual install). The Provider's Create logic calls `POST /apps/{slug}/install` → Supervisor returns **404**
(because the `/apps/{slug}/info` lookup fails for a not-in-addon-list app — the install endpoint may behave differently;
verified behaviour below).

**Why it happens:** Adolescent-provider logic: "POST = create new, must succeed or fail". A Terraform provider must
treat "already in desired state" as success, not error.

**Consequences:** First-time bootstrap of a Provider against an existing HA install is broken. The user has to manually
run `tofu import` for every pre-existing add-on, which is tedious and easy to get wrong.

**Prevention:**

- Provider's Create function:
  1. `GET /apps/{slug}/info` first.
  2. If `is_installed: true` → adopt existing, write to state, return success. (Terraform framework: return
     `resp.State = plan` with the read values — this is "adoption", not creation.)
  3. If `is_installed: false` → `POST /store/{slug}/install` (or V2 equivalent), poll `GET /jobs/{uuid}` until done,
     then `GET /apps/{slug}/info` to populate state.
- The Bridge's install proxy translates Supervisor's `404` ("app not in store") into a clear 404 error, but its **own**
  idempotency layer returns 200 with the existing app info when the Provider asks for an app that's already installed.
- This is the standard Terraform `ResourceWithImportState` / adoption pattern. Phase 1 must not skip this; skipping it
  means the Provider only works on empty HA installs.

**Detection:**

- Integration test: HA already has `mosquitto` installed → Provider `apply` for `homeassistant_addon.mosquitto` → no
  install call made, state populated from existing app, plan is clean.

**Phase tie-in:** Phase 09.4 (Provider Create idempotency).

**Sources:** Supervisor source: `_extract_app` in `supervisor/api/store.py` distinguishes store-side from
installed-side; `/apps/{slug}/info` returns the installed app or 404. The V1 legacy route `/addons/{slug}/info` falls
back to store lookup for not-installed apps (see `apps_app_info` in `supervisor/api/__init__.py`).

---

### Pitfall I-2: Provider always creates new instead of adopting

**What goes wrong:** Related to I-1 but more subtle. The Provider's Create path unconditionally calls `POST /install`.
If the install endpoint returns a 200 because the add-on is already installed (Supervisor may return this on some
endpoints), the Provider thinks it created it, but the _side effects_ (e.g. reapplying options to defaults) overwrite
the user's existing configuration.

**Why it happens:** The Supervisor's `POST /apps/{slug}/install` is _idempotent at the install level_ (Supervisor
returns 200 if already installed), but **not idempotent at the options level** — calling install may reset options to
add-on defaults. (This is empirical — needs verification in Phase 09.4 spike.)

**Consequences:** User's carefully tuned `mosquitto` config (MQTT credentials, listener settings) gets reset to defaults
every apply. The user discovers this when devices stop connecting.

**Prevention:**

- Provider Create flow:
  1. Read current state.
  2. If installed and options match config → no-op, return current state.
  3. If installed and options differ → `POST /apps/{slug}/options` with the desired options (NOT a re-install).
  4. If not installed → install with the desired options in the _same_ request payload.
- The Provider NEVER calls `POST /install` after the initial install unless the add-on is missing.
- The Bridge exposes a **composite endpoint** `POST /addons/{slug}/ensure` that takes `{slug, options}` and does the
  right thing server-side, so the Provider doesn't have to sequence calls.

**Detection:**

- Integration test: existing `mosquitto` with non-default options → Provider apply → options unchanged → no install call
  observed in Bridge audit log.

**Phase tie-in:** Phase 09.4 (Provider ensure semantics).

---

### Pitfall I-3: Drift detection loops after manual HA UI changes

**What goes wrong:** User edits add-on options via HA UI (the normal way to fix a misconfigured add-on). Provider's next
`tofu plan` reports drift on every option. The user re-applies → Provider reverts the UI changes. User applies UI
changes again → drift loop.

**Why it happens:** Terraform's default model is "state == config == reality". When the user changes reality (via UI),
the Provider tries to put it back.

**Consequences:** Provider becomes useless for any add-on the user actively tunes. User abandons the tool.

**Prevention:**

- Educate via DOCS.md: "For add-ons you actively tune, add `lifecycle { ignore_changes = [options] }`." This is the
  standard Terraform escape hatch.
- The Provider's schema marks the `options` block as `Optional` and lets the user either set it explicitly (managed) or
  omit it (adopt whatever the add-on currently has).
- The Provider surfaces a **drift report** at `tofu plan` time: "Add-on `zigbee2mqtt` has 3 option differences from
  configuration. Set `lifecycle.ignore_changes = [options]` to suppress."
- The Bridge stores a `last_options_seen` timestamp on each resource's state, so the Provider can tell the user _when_
  the drift occurred. ("Options drifted at 2026-08-31T14:23:01Z; before that, plan was clean for 6 hours.")

**Detection:**

- Integration test: Provider sets options → user changes option via UI → `tofu plan` reports drift, NOT silent apply →
  after `lifecycle.ignore_changes`, plan is clean.

**Phase tie-in:** Phase 09.4 (Provider drift handling) + DOCS.md.

**Sources:** Terraform plugin framework docs confirm `ignore_changes` lifecycle block is the standard answer
(`opentofu.org/docs/language/resources/behavior`).

---

## 4. API Versioning

### Pitfall V-1: Bridge upgrades but Provider still points at old version

**What goes wrong:** Bridge version 1.1.0 introduces a new endpoint `POST /addons/{slug}/ensure` (composite). Provider
version 1.0.0 doesn't know about it and falls back to the old `POST /install` + `POST /options` two-step. Bridge version
1.1.0 is backward-compatible (old endpoints still work), so nothing breaks visibly — but the Provider is missing the new
safety.

**Why it happens:** Versioning is implicit. There's no handshake.

**Consequences:** Silent regressions — the Provider uses slower, less-safe paths without telling the user.

**Prevention:**

- The Bridge exposes a **meta endpoint** `GET /` (root) that returns
  `{bridge_version, min_provider_version, max_provider_version, supervisor_version, api_versions: [1]}`. The Provider
  reads this at startup and **fails fast** if its version is outside the supported range, with a clear error: "Provider
  1.0.0 is too old for Bridge 2.0.0; upgrade to ≥1.5.0."
- The Bridge uses **semantic versioning** of its API surface independently of its own version: `/v1/...` and `/v2/...`.
  The Provider includes `Accept: application/vnd.bridge.v1+json` style headers, or the URL has the version prefix.
- The 3-file version scheme from the project (config.yaml subpatch vs build.yaml) must apply to **Bridge and Provider
  together**, since the project decided to co-locate them. Any Bridge release that bumps `X.Y` requires a corresponding
  Provider release.

**Detection:**

- Integration test: Provider 1.0.0 against Bridge 2.0.0 → Provider refuses to start, error message names the minimum
  version.

**Phase tie-in:** Phase 09.1 (Bridge API contract).

---

### Pitfall V-2: Provider upgrades but Bridge is old → feature flag hell

**What goes wrong:** Provider 2.0.0 uses `POST /addons/{slug}/ensure`. Bridge 1.0.0 returns 404. Provider sees "feature
not supported" but tries the old path anyway → succeeds but with old semantics.

**Why it happens:** Provider has a feature-detection step, but the fallback is too forgiving.

**Consequences:** Same as V-1 but in the other direction: the user gets the _new_ Provider's diagnostic messages but the
_old_ Bridge's behaviour. Confusion about which is at fault.

**Prevention:**

- The Bridge responds to `OPTIONS /addons/{slug}/ensure` with `Allow: POST, OPTIONS` (always 405 for unsupported). The
  Provider treats 404/405 on a feature endpoint as "feature not available; abort apply with a clear error."
- The DOCS.md states the Bridge→Provider version compatibility matrix.
- The CI release workflow (auto-update from PROJECT.md) runs an integration test against the minimum supported Bridge
  version. If it fails, the new Provider release is blocked.

**Detection:**

- Integration test matrix: each Provider version × each Bridge version pair → expected pass/fail documented and enforced
  in CI.

**Phase tie-in:** Phase 09.4 (CI matrix).

---

### Pitfall V-3: Supervisor API changes between HA versions

**What goes wrong:** HA 2026.x removes the V1 endpoints (`/addons/{slug}/info`). Bridge still uses them. Provider's
calls fail with 404.

**Why it happens:** Supervisor is deprecating V1 in favour of V2. From the source code (`supervisor/api/__init__.py`):
`_V1_LEGACY_ERROR_KEY_MAP` already maps three error keys; the V1 routes carry comments like "Remove: 2023", "Deprecated
2026.03", "Deprecated 2026.05" — these are landmines waiting to fire.

**Consequences:** The Provider breaks every HA release until the Bridge is updated to use V2.

**Prevention:**

- The Bridge prefers **V2 (`/v2/apps/{slug}/info`) when available**, falls back to V1. The feature flag
  `SUPERVISOR_V2_API` (read from `/supervisor/info`) controls this.
- The Bridge's `/supervisor/info` response is cached and re-read on every request (cheap), so the Bridge auto-upgrades
  within seconds of HA flipping the flag.
- The DOCS.md states the supported HA version range.
- The README shield badge reflects `hassio_role: manager` and a min-HA-version assertion in the Bridge startup.

**Detection:**

- Integration test: Bridge detects missing V1 endpoints → switches to V2 transparently → Provider's existing calls
  succeed.

**Phase tie-in:** Phase 09.1 (Bridge → Supervisor version detection).

**Sources:** Supervisor source confirms V1/V2 split, feature-flag gating, and active V1→V2 deprecation:
`supervisor/api/__init__.py` ("Deprecated 2026.05", "Deprecated 2026.03", "Remove: 2023" comments);
`supervisor/api/middleware/security.py` has `_V1_PATTERNS` and `_V2_PATTERNS` distinct.

---

## 5. Destructive Operations

### Pitfall D-1: terraform apply uninstalls a critical add-on (Zigbee2MQTT, Mosquitto)

**What goes wrong:** User's `main.tf` declares 5 add-ons. They remove one from the file. `tofu plan` correctly says "1
to destroy". `tofu apply` uninstalls `zigbee2mqtt`. All Zigbee devices go offline. Worse: if `mosquitto` was declared
but somehow ends up in the destroy list (typo, refactor), every MQTT device goes offline.

**Why it happens:** Terraform destroy is unconditional for resources removed from configuration.

**Consequences:** **Device outages. Safety incident.** User loses trust in the tool permanently.

**Prevention:**

- **Default the Provider schema with `lifecycle.prevent_destroy = true`** on `homeassistant_addon` resources, baked into
  the schema's `PlanModifiers`. The user can opt out per-resource, but the safe default is in place.
- The Provider's `ModifyPlan` (destroy branch) returns a **diagnostic warning** on any planned destroy: "This will
  uninstall zigbee2mqtt, which is the Zigbee mesh bridge for 47 devices." The user must explicitly confirm
  `-allow-destroy` style behaviour.
- The Provider exposes a `critical_addons` list (Provider config, not per-resource) that names slugs which require an
  extra confirmation. Default list: `mosquitto`, `core_mosquitto`, `zigbee2mqtt`, `zwave-js-ui`, `esphome`. If any of
  these is in the destroy set, `ModifyPlan` returns an **error** diagnostic, not a warning — the apply cannot proceed
  without editing the config.
- The Bridge exposes a "destructive ops log": every uninstall call is appended to `/data/destructive.log` with
  `{ts, slug, requestor_ip, source_request_id}`. The user can grep this log to audit.

**Detection:**

- Integration test: Provider destroy plan includes `mosquitto` → `tofu plan` returns error → user must edit config to
  remove `mosquitto` from critical_addons or add `prevent_destroy` opt-out.

**Phase tie-in:** Phase 09.4 (Provider safety).

**Sources:** OpenTofu docs confirm `lifecycle.prevent_destroy` and `lifecycle.destroy` semantics
(`opentofu.org/docs/language/resources/behavior`); plugin framework's `ModifyPlan` supports returning diagnostics that
block apply.

---

### Pitfall D-2: No confirmation before destructive ops

**What goes wrong:** `tofu apply` in CI runs unattended. CI machine has Provider credentials. Auto-apply on a
misconfigured PR deletes production add-ons.

**Why it happens:** Terraform's default is "approve and go". CI workflows often add `-auto-approve`.

**Consequences:** Mass outage from a one-line PR.

**Prevention:**

- **Document explicitly in DOCS.md: "Do not run `tofu apply -auto-approve` against this provider. The Provider does not
  support unattended apply safely."**
- The Bridge implements a **two-step confirmation** for destructive operations (uninstall, options-delete, repo-delete):
  the Provider's first request is a `POST /destructive/preview` that returns a nonce + summary; the actual
  `POST /uninstall` requires `X-Confirm-Nonce: <nonce>` header. This adds an explicit "yes I really mean it" step that
  survives even an auto-approve script.
- The nonce expires after 60 seconds. The Provider emits it on the dashboard output; the user pastes it into the next
  CLI step.

**Detection:**

- Integration test: `tofu apply` with uninstall in plan → Provider refuses with "run `tofu apply -target=...` and
  confirm nonce".

**Phase tie-in:** Phase 09.4 (Provider destructive flow).

---

### Pitfall D-3: No "dry run" — `tofu plan` actually changes things

**What goes wrong:** The Bridge is so fast that some operations (e.g. `POST /options` to set an addon's boot order)
might be applied by the Provider's `Plan` step instead of `Apply`. This is a bug pattern in many IaC providers. The
OpenTofu spec says: **no resource creation, modification, or deletion in `Plan`.** A provider that violates this is
broken.

**Why it happens:** Confusing `Read` with `Apply`. Some authors implement `Plan` as a read-then-write.

**Consequences:** Silent state drift, because `Plan` doesn't update state but does change reality.

**Prevention:**

- The Provider implements **`ResourceWithModifyPlan`** for diff-computation only. All HTTP writes (POST/PUT/DELETE) are
  gated behind `Create`, `Update`, `Delete`. The unit test suite asserts this: a `Plan` against the mock Bridge records
  zero write requests.
- The framework docs explicitly call this out: "Plan modification can be added on resource schema attributes or an
  entire resource" but the modifications are _plan-only_; they don't call the API.
- The Bridge exposes a **`GET /audit/recent?writes_only=true`** endpoint that lists recent write operations. A CI step
  runs `tofu plan` and then queries this endpoint — if any writes appear, the CI fails. This is a regression test for
  the framework contract.

**Detection:**

- Unit test: spy on Bridge HTTP client → run `tofu plan` → assert zero write calls.
- Integration test: CI step runs `tofu plan` against real Bridge → reads `/audit/recent` → asserts empty.

**Phase tie-in:** Phase 09.4 (Provider test suite).

**Sources:** Terraform plugin framework docs explicitly state that `Plan` modifies plan but does not call the upstream
API (`developer.hashicorp.com/terraform/plugin/framework/resources/plan-modification`).

---

## 6. Operational

### Pitfall O-1: Bridge logs in HA Supervisor UI but user can't grep them

**What goes wrong:** HA stores add-on logs at `/config/home-assistant.log` via the Supervisor logger (s6), but the user
can't stream them, can't `jq` them, and they're rotated aggressively. A failed `tofu apply` at 2am leaves no usable
audit trail.

**Why it happens:** Default HA add-on log flow: stderr → s6 → journald → HA log. Not designed for JSON, not designed for
grep.

**Consequences:** When something goes wrong, the user has to SSH to the HA host and read journald. Slow, error-prone.

**Prevention:**

- The Bridge writes a **structured JSON log** to `/data/bridge.jsonl` in addition to stderr. Each line:
  `{ts, level, msg, request_id, method, path, status, duration_ms, app_slug?, op?}`.
- The Provider mirrors this log locally at `~/.config/tofu/logs/bridge-{date}.jsonl` if `TF_LOG_PROVIDER=bridge` is set.
- The Bridge exposes `GET /logs/recent?since=...&json=true` for ad-hoc retrieval.
- A **fallback** for users without SSH: an `ingress: true` flag on the add-on provides a read-only log viewer panel in
  the HA sidebar.

**Detection:**

- Smoke test: `tofu apply` → `/data/bridge.jsonl` contains ≥1 entry with the correct shape → `GET /logs/recent` returns
  the same entries.

**Phase tie-in:** Phase 09.1 (logging).

---

### Pitfall O-2: State file format invalid after Bridge upgrade

**What goes wrong:** Bridge 1.1 adds a new resource attribute to its internal mapping. Old state files (from Bridge 1.0)
don't have it. Next `tofu plan` errors with "schema mismatch" or, worse, silently drops the attribute.

**Why it happens:** OpenTofu local state format changes between provider versions. The provider MUST declare a
`Schema.Version` and implement `UpgradeState` to migrate.

**Consequences:** User's state file becomes unusable. Recovery: `tofu state pull`, edit, `tofu state push` — manual and
error-prone.

**Prevention:**

- The Provider implements **`schema.Schema.Version = N`** and **`ResourceWithUpgradeState`** with an upgrader for every
  prior version. The framework docs spell this out explicitly.
- The state schema version is **bumped** (not just attribute-changed) every time a non-additive schema change happens
  (rename, type change, required-now-optional). Additive-only changes (new Optional attribute) don't require a version
  bump.
- Bridge-side: the state file at `/data/terraform.tfstate` is OpenTofu-format, not Bridge-format. The Bridge doesn't
  touch state format. The Provider does. So this pitfall lives entirely in the Provider.

**Detection:**

- Unit test: hand-craft a v0 state JSON → load in Provider → assert `UpgradeState` is called → assert resulting state
  matches v1 schema.
- CI gate: the Provider's CI downloads the _previous_ release's test state and runs the migration on it.

**Phase tie-in:** Phase 09.4 (Provider state versioning).

**Sources:** Terraform plugin framework docs explicitly cover `ResourceWithStateUpgrade` with the `PriorSchema` and
`RawState` approaches (`developer.hashicorp.com/terraform/plugin/framework/resources/state-upgrade`).

---

### Pitfall O-3: Provider logs say "applied 3 add-ons" but Bridge did nothing

**What goes wrong:** Provider's optimistic apply reports success based on a 200 response from the Bridge. Bridge got the
request but failed to forward to Supervisor (network blip). HA state unchanged. User has 3 add-ons in state but not in
HA.

**Why it happens:** Two-phase commit without a coordinator.

**Consequences:** State lies. Next apply tries to re-apply, which works, so the user is unaware until they query HA
directly.

**Prevention:**

- The Bridge's response to a write operation always includes a **`X-Bridge-Write-Confirmed: true`** header **only when
  the Supervisor call has actually returned 2xx**. A 200 from the Bridge means the Supervisor acknowledged.
- For long-running operations (install returning `job_id`), the Bridge polls the Supervisor job until `done=true|false`
  before responding 200 to the Provider. The Provider sees a 200 only when the operation is fully complete (or has
  terminally failed).
- The Provider's `Create`/`Update`/`Delete` only marks state as current after reading this confirmation header. A
  missing header → Provider returns error diagnostic.

**Detection:**

- Integration test: simulate Bridge→Supervisor network blip (drop packets) → Bridge returns error → Provider marks
  resource as "apply failed" → user's next plan correctly retries.

**Phase tie-in:** Phase 09.3 (Bridge write confirmation).

---

## 7. HA-Supervisor Specific

### Pitfall H-1: SUPERVISOR_TOKEN behavior across Supervisor restart

**What goes wrong:** HA Supervisor restarts (auto-update, manual). Does the add-on's `SUPERVISOR_TOKEN` change?
Documentation says "auto-injected by Supervisor." If it changes on restart, the Bridge's env-injected token changes
mid-flight → mid-operation calls fail.

**Why it happens:** Ambiguity in the HA docs. The actual behavior depends on whether Supervisor re-issues tokens.

**Consequences:** Intermittent, hard-to-reproduce apply failures.

**Prevention:**

- **Verify empirically in Phase 09.1 spike:** restart Supervisor, check whether `SUPERVISOR_TOKEN` inside the add-on
  container is the same. If it changes, the Bridge must re-read it on every HTTP call to Supervisor (cheap: read env
  each time) and treat token change as a non-error.
- The Bridge keeps a SHA-256 fingerprint of the last-known token. On startup, if the env-injected token differs, log
  `bridge.token_rotated=true` and continue. No action needed because the new token is already valid.
- Document the behaviour in DOCS.md so users don't try to "fix" it.

**Detection:**

- Spike result (Phase 09.1): empirical answer for the running HA version.
- Integration test: Supervisor restart during Provider apply → Bridge continues working without intervention.

**Phase tie-in:** Phase 09.1 (verify empirically).

**Sources:** Supervisor source shows tokens are stored in `coresys.homeassistant.supervisor_token`
(`supervisor/api/middleware/security.py`), generated per installation. Per-add-on tokens come from `App.docker_tokens`
and persist for the lifetime of the install. The HA docs (`developers.home-assistant.io/docs/add-ons/communication`)
describe the token as "auto-injected" without specifying rotation behaviour. **LOW confidence on rotation specifics —
must verify empirically in the spike.**

---

### Pitfall H-2: Supervisor restart while Bridge in middle of API call

**What goes wrong:** Provider sends `POST /addons/mosquitto/start`. Bridge forwards to Supervisor. Supervisor is in the
middle of restarting (after a self-update). The TCP connection is reset mid-request. Bridge returns 502 to the Provider.
Provider retries. Supervisor comes back. Retry succeeds. **But:** if the Supervisor was actually in the middle of
_restarting itself_, the add-on might be in a half-started state.

**Why it happens:** Supervisor restarts are atomic from HA's perspective but not from individual add-ons. The Bridge
can't tell whether Supervisor is "down for maintenance" or "down for crash".

**Consequences:** Flaky state; user can't tell whether the apply completed.

**Prevention:**

- The Bridge retries once on connection-refused, with exponential backoff (200ms, 1s). The Bridge surfaces the retry in
  the log and to the Provider.
- The Bridge exposes `GET /supervisor/ready` as a passthrough to Supervisor's `/info` (or `ping`). The Provider **calls
  this first** if a previous call returned 5xx, and waits for it to return 200 before retrying.
- The Provider's `Create`/`Update`/`Delete` returns a clear diagnostic on persistent 502: "Bridge cannot reach
  Supervisor (HA might be restarting). Wait 30 seconds and re-run apply. Resources may be in an indeterminate state."

**Detection:**

- Integration test: stop Supervisor container mid-apply → Bridge retries → Supervisor returns → apply completes
  correctly OR surfaces "indeterminate state, check manually".

**Phase tie-in:** Phase 09.3 (Bridge retry).

**Sources:** Supervisor source `system_validation` middleware: "Check if core is ready to response"
(`supervisor/api/middleware/security.py`::`system_validation`). The `/supervisor/ping` endpoint exists specifically for
this.

---

### Pitfall H-3: /config not writable by Bridge for options.json-style edits

**What goes wrong:** Phase 2 plans might include editing `/config/configuration.yaml` (e.g. adding `automation`
entries). The Bridge does not have `homeassistant_config:rw` in its `map:` declaration → write fails with permission
denied.

**Why it happens:** The HA add-on `map:` list defaults to `data` only (always mapped, writable). Adding other types
requires explicit declaration and triggers an HA security review.

**Consequences:** Some Phase 2 features silently don't work. User blames the Bridge.

**Prevention:**

- For Phase 1, the Bridge does **not** need `homeassistant_config:rw`. Its scope is add-ons. Do not include
  `homeassistant_config` in the `map:` list.
- For Phase 2 (if/when it adds Core config editing), declare `homeassistant_config:rw` explicitly. This is a privileged
  mount — review carefully.
- The Provider schema surfaces this: any resource type that needs `/config` write is `homeassistant_core_config` or
  similar, separate from `homeassistant_addon`. Phase 1 does NOT include this resource type.

**Detection:**

- `grep -E "map:|homeassistant_config" terraform-bridge/config.yaml` → must NOT include `homeassistant_config` in
  Phase 1.

**Phase tie-in:** Phase 09.1 (config.yaml).

**Sources:** HA add-on docs (`developers.home-assistant.io/docs/add-ons/configuration`) confirm `map:` controls bind
mounts and `homeassistant_config` is one of the optional types.

---

### Pitfall H-4: Bridge API responses expose other add-ons' secrets

**What goes wrong:** The Bridge, when asked for one add-on's info, accidentally returns another add-on's options (which
may contain passwords, API keys, MQTT creds). The Provider writes them into state in plaintext, which is then committed
to the user's git repo.

**Why it happens:** A bug in the Bridge's `info` handler, or — more insidiously — the Provider asking for one add-on but
the Bridge forwarding to `/addons/{slug}/info` where `{slug}` matches a different one due to Supervisor's pattern
routing.

**Consequences:** Secret leakage into git history.

**Prevention:**

- The Supervisor source code (`supervisor/api/apps.py::info_data`) explicitly handles this:
  > "User options may contain secrets. Expose them only to trusted callers: Home Assistant Core (and other non-app
  > internals), the app itself, or an app with the manager/admin role. Any other app reading a different app's info gets
  > the options redacted."
- The Bridge holds `hassio_role: manager` in its config.yaml — confirmed required for options to be visible.
- The Provider **never persists the `options` attribute to state unless the resource is the one being managed** — i.e.
  never `terraform_remote_state` style sharing, never `output "options" { value = ... }`.
- Add-on options are marked `Sensitive: true` in the Provider schema, so they don't show in `tofu plan` output unless
  the user explicitly opts in via `TF_LOG`.

**Detection:**

- Bridge integration test: request info for add-on A → response.options is populated (because Bridge has manager role).
  Request info for add-on B → response.options is `{}` (Bridge isn't asked for self). Re-test with non-manager token →
  options are `{}` for everyone except self.

**Phase tie-in:** Phase 09.1 (config.yaml `hassio_role: manager`) + Phase 09.4 (Provider schema).

**Sources:** Supervisor source confirms the redacting logic (`supervisor/api/apps.py::info_data` line 169); add-on docs
confirm `hassio_role: manager` is the privilege to manage other apps.

---

### Pitfall H-5: Long-running ops block HA Supervisor

**What goes wrong:** Supervisor's `/apps/{slug}/uninstall` is wrapped in `asyncio.shield(...)` and awaits the task.
Uninstalling a 1GB add-on with a long image-pull can block for 60+ seconds. The Bridge's HTTP server holds the request
open. If the Bridge has a default client timeout (10s), the Bridge times out and the Provider sees a 504 — even though
Supervisor is still working.

**Why it happens:** HA add-on containers usually have a 30-60s default client timeout. Long installs exceed this.

**Consequences:** Provider sees timeout, but Supervisor finishes the install 30 seconds later. State is wrong.

**Prevention:**

- The Bridge's HTTP client to Supervisor has a **configurable timeout** (default 300s, max 1800s). Tied to the add-on
  option `supervisor_request_timeout_seconds`.
- The Bridge passes through Supervisor's `job_id` immediately and provides a `GET /jobs/{uuid}` passthrough so the
  Provider can poll instead of waiting.
- The Bridge uses HTTP **chunked response** for long-running operations: it streams progress lines
  (`event: progress\ndata: {...}\n\n`) so the Provider can display them. The Provider implements this as an SSE client.

**Detection:**

- Integration test: install a large add-on (e.g. Grafana) → Bridge does not time out → Provider receives final result.

**Phase tie-in:** Phase 09.3 (Bridge streaming + timeouts).

**Sources:** Supervisor source confirms uninstall uses `asyncio.shield(self.sys_apps.uninstall(...))`
(`supervisor/api/apps.py::uninstall`), which awaits the uninstall coroutine. Install uses `background_task` (returns
job_id when `background=true`). Both are blocking-by-default; long operations need explicit timeout handling.

---

## 8. Terraform Specific

### Pitfall T-1: terraform-plugin-framework typed schema vs untyped — when does it bite?

**What goes wrong:** The Provider uses the older SDKv2 (untyped schema via `map[string]*schema.Schema`). The framework's
typed schema (`schema.StringAttribute`, `schema.Int64Attribute`) gives compile-time type safety. SDKv2's
`d.Get("options")` returns `interface{}` — type assertion bugs cause panics.

**Why it happens:** SDKv2 has more Stack Overflow answers and more copy-pasteable examples. Authors default to it.

**Consequences:** Runtime panics when the Provider receives an unexpected schema shape (e.g. from a user with an old
`.terraformrc`). Hard to test exhaustively.

**Prevention:**

- **Use terraform-plugin-framework from day one.** The framework docs and OpenTofu docs both prefer it. The framework's
  typed schema (`types.String`, `types.Int64`, etc.) and schema data models
  (`struct { ID types.String `tfsdk:"id"` ... }`) eliminate type assertion bugs.
- The 3-file versioning scheme in the repo will catch framework SDK bumps via `make update-version`.
- The framework docs (`developer.hashicorp.com/terraform/plugin/framework/migrating/benefits`) explicitly enumerate the
  type-safety wins: "Some SDKv2 providers opted to type assert during these calls, which had the potential to cause Go
  runtime panics if they did not also check the assertion boolean."

**Detection:**

- `grep -r "schema.Resource " terraform-provider-homeassistant/` → must return zero hits (framework uses
  `resource.Resource` interface).

**Phase tie-in:** Phase 09.4 (Provider scaffold).

**Sources:** Terraform plugin framework docs (`developer.hashicorp.com/terraform/plugin/framework`),
`developer.hashicorp.com/terraform/plugin/framework/migrating/benefits`.

---

### Pitfall T-2: Import blocks vs `tofu import` — adoption mechanics

**What goes wrong:** User wants to bring an existing add-on under Provider management. They edit `main.tf` to add the
resource block, but `tofu plan` says "Resource not in state, will be created." User runs
`tofu import homeassistant_addon.mosquitto mosquitto` → Provider's `ImportState` method doesn't exist or doesn't work →
error.

**Why it happens:** Many providers ship without `ImportState` because it's an "advanced" feature. The framework docs
make it explicit: "If the resource does not support `terraform import`, skip the `ImportState` method implementation."

**Consequences:** Adoption friction is the #1 reason users abandon a Terraform provider. They have 20 existing add-ons
and the tool only works on greenfield installs.

**Prevention:**

- **Mandatory: implement `ResourceWithImportState` on `homeassistant_addon`** from day one. The `ImportState` method
  calls `GET /apps/{slug}/info` and writes the result into state. This is the same path as adoption (I-1) — keep them in
  lockstep.
- Use **`ImportStatePassthroughID`** for the simplest case: identity is the slug, so
  `tofu import homeassistant_addon.mosquitto mosquitto` makes `id = "mosquitto"`. The Read function then looks up by id.
- For multi-attribute identity (e.g. add-on + repository), implement the comma-separated `attr_one,attr_two` pattern
  documented in the framework.
- OpenTofu's `import { ... }` blocks (`opentofu.org/docs/language/import/`) are also supported but require the resource
  block to already exist. Both modes work; document both.

**Detection:**

- Integration test: `tofu import homeassistant_addon.mosquitto mosquitto` → state populated → subsequent plan is clean
  (no diff).

**Phase tie-in:** Phase 09.4 (Provider Import).

**Sources:** Terraform plugin framework docs (`developer.hashicorp.com/terraform/plugin/framework/resources/import`);
OpenTofu `import` block docs (`opentofu.org/docs/language/import/`).

---

### Pitfall T-3: State locks — does OpenTofu support file-based locking for the Provider's local state?

**What goes wrong:** User runs `tofu apply` twice from the same laptop (different terminals). Both compute plans
referencing the same state file. Without locking, last-writer-wins.

**Why it happens:** Users forget that OpenTofu local backend uses advisory file locks via `flock(2)`. Concurrent applies
on the same host _do_ have protection; cross-host races do not (see ST-1).

**Consequences:** State corruption on local backend.

**Prevention:**

- **Document the limitation:** "Do not run `tofu apply` from multiple machines concurrently. This provider assumes
  single-host apply."
- The Provider's local backend (default) uses OpenTofu's built-in `flock`. This protects against same-host races
  automatically — no Provider code needed. Document this in DOCS.md so users understand what's protected.
- For multi-host apply: introduce a remote backend (S3, etc.) in a future phase. Phase 1 explicitly out of scope.

**Detection:**

- N/A — this is OpenTofu behaviour, not Provider code. Smoke test: same-host concurrent `tofu apply` → second one waits
  for the first.

**Phase tie-in:** Phase 09.4 (DOCS.md).

**Sources:** OpenTofu docs (`opentofu.org/docs/language/state/locking/`,
`opentofu.org/docs/language/settings/backends/local/`).

---

### Pitfall T-4: `lifecycle` blocks not surfaced in plan output

**What goes wrong:** Provider implements `lifecycle.prevent_destroy` (D-1) but only as a schema-level attribute. The
user adds `lifecycle { ignore_changes = [tags] }` to their config expecting it to work. OpenTofu silently ignores
unknown lifecycle arguments on a resource type that doesn't declare support for them.

**Why it happens:** Resource lifecycle blocks are validated against the Provider's schema of supported arguments. Custom
lifecycle arguments are not supported unless the Provider opts in.

**Consequences:** User thinks they're protected when they aren't.

**Prevention:**

- The Provider's schema **explicitly documents** which `lifecycle` arguments are respected. Standard ones
  (`create_before_destroy`, `prevent_destroy`, `ignore_changes`, `replace_triggered_by`) are always respected by the
  framework. Custom ones require explicit Provider support.
- The DOCS.md has a "Supported lifecycle arguments" section that lists each argument and the Provider's behaviour.
- The Provider's `ModifyPlan` looks at `lifecycle.prevent_destroy` explicitly and returns an error if the planned action
  is destroy and the user has set it.

**Detection:**

- Unit test: set `prevent_destroy = true`, plan a destroy, assert `resp.Diagnostics.HasError()`.

**Phase tie-in:** Phase 09.4 (Provider safety).

**Sources:** OpenTofu resource behaviour docs (`opentofu.org/docs/language/resources/behavior`).

---

### Pitfall T-5: Provider's `id` attribute misnamed (e.g. `slug` vs `id`)

**What goes wrong:** Convention: the resource's `id` attribute is the API-side identifier. Some providers mistakenly use
`slug` or `name` or `uuid` as the import-time identifier. `tofu import` then fails because the framework expects `id`.

**Why it happens:** Domain modelling confusion. "slug" is the user's name for the thing; "id" is the API's.

**Consequences:** Import is awkward. Users can't refer to resources by intuitive names.

**Prevention:**

- The Provider has **both** an `id` (the API-side, used for tracking) and a `slug` (the user-facing name, used in
  `tofu import`). `id` is populated by the Read function with the slug initially, but the schema marks it
  `Computed: true` so the framework can populate it.
- Document: `id` and `slug` are equal for `homeassistant_addon` (the slug is the only identifier in Supervisor), but the
  schema separates them for forward compatibility (e.g. future `homeassistant_addon_options` resource has
  `id = "{slug}:options"`).

**Detection:**

- Integration test: `tofu import` by slug populates both `id` and `slug` in state.

**Phase tie-in:** Phase 09.4 (Provider schema).

---

## 9. Phase-Specific Warnings

These are the pitfalls most likely to bite each planned phase. Mapped to the project's rough phase numbering (Phase 09
onwards, since 01-08 are completed).

| Phase | Topic                                   | Most Likely Pitfall                                                                                         | Mitigation                                                                                                                    |
| ----- | --------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| 09.1  | Bridge scaffold                         | H-1 (token rotation unknown), H-4 (hassio_role), S-1 (token leak in logs)                                   | Verify token behaviour empirically; declare `hassio_role: manager`; structured logging with token redaction                   |
| 09.2  | Auth + CSRF + Tailscale binding         | S-3 (CSRF), S-4 (bind to Tailscale only), S-5 (no SUPERVISOR_TOKEN in config schema)                        | Custom CSRF header; bind enforcement at startup; schema lint check                                                            |
| 09.3  | Bridge API surface + WAL + concurrency  | ST-1 (concurrency), ST-2 (Bridge restart loses job), ST-3 (/data wipe on reinstall), H-5 (long op timeouts) | Per-slug mutex; WAL at `/data/jobs.jsonl`; addon_config passthrough; configurable timeouts                                    |
| 09.4  | Provider scaffold + homeassistant_addon | I-1, I-2, I-3 (idempotency), D-1, D-2, D-3 (safety), T-1, T-2, T-5 (provider quality)                       | Adoption in Create; critical_addons list; `lifecycle.prevent_destroy` baked in; framework from day 1; `ImportState` mandatory |
| 09.5  | State + drift + versioning              | ST-4 (drift), V-1/V-2 (version negotiation), T-4 (lifecycle args)                                           | Read returns `RemoveResource` for missing; `/meta` endpoint for handshake; docs lifecycle supported list                      |
| 09.6  | CI + testing                            | O-2 (state upgrade test), T-2 (import test), O-3 (no writes in plan)                                        | State upgrade unit tests; import integration tests; `Plan` write-spies                                                        |
| 09.7  | DOCS.md + operations                    | O-1 (logs greppable), ST-3 (reinstall warning), D-1, D-2 (runbook)                                          | Structured JSON log; DOCS.md warnings; destructive-op nonce                                                                   |

---

## 10. Confidence Assessment

| Area                                     | Confidence | Reason                                                                                                                                                                                                                                                       |
| ---------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| HA Supervisor auth + middleware          | HIGH       | Read directly from `home-assistant/supervisor` source code, current `main` branch. Behaviour of `SecurityMiddleware`, role checks, blacklist, and V1/V2 split are explicitly verified.                                                                       |
| HA Supervisor API endpoints              | HIGH       | All endpoint registrations read from current source. Confirmed `asyncio.shield` wrapping on mutations, `background_task` for installs.                                                                                                                       |
| OpenTofu state locking                   | HIGH       | OpenTofu official docs cover local backend locking explicitly.                                                                                                                                                                                               |
| OpenTofu plugin framework                | HIGH       | HashiCorp Developer docs current. `ResourceWithUpgradeState`, `ResourceWithImportState`, `ResourceWithModifyPlan`, typed schema vs SDKv2 — all verified.                                                                                                     |
| Add-on config + token injection          | HIGH       | HA add-on developer docs current. `SUPERVISOR_TOKEN` env injection, `/data` volume, `map:` semantics — all verified.                                                                                                                                         |
| Tailscale Serve identity/CSRF            | MEDIUM     | Tailscale docs confirm Serve forwards `Tailscale-User-*` headers but **does not perform app-layer CSRF**. Best-practice text quoted. No negative claim about CSRF (didn't find "Tailscale does X for CSRF") — handled by asserting Bridge must do it itself. |
| Token rotation across Supervisor restart | LOW        | Not explicitly documented in HA add-on docs. **Must verify empirically in Phase 09.1 spike.**                                                                                                                                                                |
| V1/V2 removal timeline                   | MEDIUM     | Source comments mention "Remove: 2023" (already overdue?), "Deprecated 2026.05", "Deprecated 2026.03". Exact removal dates for endpoints are not committed. Plan for V2 readiness from day one.                                                              |
| `/data` wipe on uninstall                | HIGH       | HA add-on lifecycle is well-documented; reinstall wipes `/data`.                                                                                                                                                                                             |
| HA backup integration behaviour          | MEDIUM     | HA's `backup` integration does not include `/data` by default for arbitrary add-ons. `addon_config` mount path may be included. **Verify in Phase 09.1 spike.**                                                                                              |

---

## 11. Implications for Roadmap

Based on the pitfall analysis, the suggested phase structure (subject to `gsd-roadmapper`):

1. **Phase 09.1: Bridge scaffold + token emission**
   - Add-on skeleton with `hassio_role: manager`, `hassio_api: true`, `bind: auto`, structured JSON logging, `/meta`
     endpoint.
   - Empirical spike: token rotation across Supervisor restart (H-1).
   - Addresses: S-1, S-4, S-5, H-3, H-4, V-3.

2. **Phase 09.2: Auth + CSRF + Tailscale binding**
   - Bearer token generation, rotation grace period, CSRF nonces, Tailscale interface binding.
   - Addresses: S-2, S-3, S-4.

3. **Phase 09.3: Bridge API surface + concurrency + WAL + timeouts**
   - Per-slug mutex, job WAL at `/data/jobs.jsonl`, streaming for long ops, configurable Supervisor timeouts.
   - Addresses: ST-1, ST-2, H-2, H-5.

4. **Phase 09.4: Provider scaffold + homeassistant_addon + safety**
   - terraform-plugin-framework, typed schema, `ImportState`, adoption in Create, `critical_addons` list,
     `lifecycle.prevent_destroy` baked in, two-step destructive confirm.
   - Addresses: I-1, I-2, D-1, D-2, D-3, T-1, T-2, T-4, T-5.

5. **Phase 09.5: State + drift + versioning handshake**
   - `Read` returns `RemoveResource` for missing; `GET /meta` handshake; `Tofu 1.x` semantic versioning; ST-4 drift
     handling; I-3 ignore_changes documentation.
   - Addresses: ST-4, V-1, V-2, I-3.

6. **Phase 09.6: CI + testing**
   - State upgrade unit tests, integration test matrix (Provider × Bridge), import tests, write-spies for `Plan`.
   - Addresses: O-2, O-3.

7. **Phase 09.7: Operations + DOCS.md**
   - JSON log panel via Ingress, runbook for destructive ops, reinstall warning, version compatibility matrix.
   - Addresses: O-1, ST-3, D-1, D-2 runbook.

**Phase ordering rationale:**

- 09.1 must come first: the Bridge scaffold (config schema, run.sh, Dockerfile) establishes the privilege boundary
  (H-4). Nothing else can be built without it.
- 09.2 before 09.3 because auth errors block all subsequent testing.
- 09.3 before 09.4 because the Provider depends on the Bridge's concurrency and WAL semantics being correct.
- 09.5 after 09.4 because drift detection is a Provider concern, not a Bridge concern.
- 09.6 (CI) can run in parallel with 09.5 since CI tests both.
- 09.7 last because DOCS depends on everything else being settled.

**Research flags for phases:**

- **Phase 09.1 needs deeper research:** H-1 (token rotation), H-3 (`/config` writability), V-3 (V1/V2 detection), O-1
  (HA backup integration). These are empirical questions.
- **Phase 09.4 likely needs deeper research:** T-2 (import block compatibility with OpenTofu 1.12+); D-1 (best UX for
  destructive-op confirm — UX spike recommended).
- **Phase 09.6 standard patterns, unlikely to need research.**

---

## 12. Prevention Matrix

Pitfall → Phase → Acceptance test (what the planner should write).

| Pitfall                         | Phase      | Acceptance Test                                                                                                                                                            |
| ------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S-1 (token leak)                | 09.1, 09.2 | `grep -rn "SUPERVISOR_TOKEN" terraform-bridge/` returns zero hits in code paths; unit test that asserts error middleware never includes upstream response body or request. |
| S-2 (token reuse)               | 09.2       | Integration test: rotate token via mock Bridge → assert 401 + `X-Bridge-Token-Rotated` header → assert retry with new token succeeds.                                      |
| S-3 (CSRF)                      | 09.2       | Negative test: POST to `/addons` _without_ `X-CSRF-Token` returns 403, even with valid bearer token.                                                                       |
| S-4 (bind surface)              | 09.1       | Startup log line includes `iface=...`; integration test that connects from non-Tailscale IP is refused.                                                                    |
| S-5 (token in config)           | 09.1       | `grep -n "supervisor_token\|SUPERVISOR_TOKEN" terraform-bridge/config.yaml` returns zero hits.                                                                             |
| ST-1 (concurrent apply)         | 09.3       | Integration test: 10 concurrent install requests for same slug → exactly 1 Supervisor install call observed in mock; other 9 return "already in progress".                 |
| ST-2 (Bridge restart mid-job)   | 09.3       | Integration test: install add-on → kill Bridge container mid-install → restart → Provider polls via re-attached job_id → install completes.                                |
| ST-3 (/data wipe)               | 09.1, 09.4 | DOCS.md contains the warning; Bridge startup warns if state missing but `addon_config` copy exists.                                                                        |
| ST-4 (drift)                    | 09.4, 09.5 | Integration test: Provider installed add-on X → user uninstalls via HA UI → next `tofu plan` reports drift, not destroy.                                                   |
| I-1 (already-installed)         | 09.4       | Integration test: HA already has `mosquitto` → Provider `apply` → no install call, state populated from existing app.                                                      |
| I-2 (always creates new)        | 09.4       | Integration test: existing `mosquitto` with non-default options → Provider apply → options unchanged, no install call.                                                     |
| I-3 (drift loops)               | 09.4       | Integration test: Provider sets options → user changes option via UI → `tofu plan` reports drift, not silent apply.                                                        |
| V-1 (Bridge upgrade)            | 09.5       | Integration test: Provider 1.0.0 against Bridge 2.0.0 → Provider refuses with clear min-version error.                                                                     |
| V-2 (Provider upgrade)          | 09.5       | CI matrix: each Provider × each Bridge pair, expected pass/fail documented.                                                                                                |
| V-3 (Supervisor V1/V2)          | 09.1       | Integration test: HA with V2 flag off → Bridge uses V1; flag on → Bridge uses V2; Provider unchanged.                                                                      |
| D-1 (uninstall critical add-on) | 09.4       | Integration test: destroy plan includes `mosquitto` → `tofu plan` returns error.                                                                                           |
| D-2 (no confirmation)           | 09.4       | Integration test: `tofu apply` with uninstall in plan → Provider refuses until nonce confirmed.                                                                            |
| D-3 (plan writes)               | 09.4, 09.6 | Unit test: spy on Bridge HTTP client during `tofu plan` → zero write calls. CI step runs plan then queries `/audit/recent?writes_only=true`.                               |
| O-1 (logs greppable)            | 09.1       | Smoke test: `tofu apply` → `/data/bridge.jsonl` has ≥1 structured entry.                                                                                                   |
| O-2 (state upgrade)             | 09.4, 09.6 | Unit test: hand-craft v0 state → load in Provider → assert UpgradeState called → assert state matches v1 schema.                                                           |
| O-3 (Bridge confirms writes)    | 09.3       | Integration test: simulate Bridge→Supervisor network blip → Bridge returns error → Provider marks "apply failed".                                                          |
| H-1 (token rotation)            | 09.1       | Spike result documented; integration test: Supervisor restart → Bridge continues.                                                                                          |
| H-2 (Supervisor restart)        | 09.3       | Integration test: Supervisor stop mid-apply → Bridge retries → either completes or surfaces "indeterminate".                                                               |
| H-3 (/config writable)          | 09.1       | `grep -E "homeassistant_config" terraform-bridge/config.yaml` returns zero hits in Phase 1.                                                                                |
| H-4 (other add-ons' secrets)    | 09.1, 09.4 | Bridge integration test: `hassio_role: manager` set, options exposed only for own queries; Provider marks `options` as `Sensitive`.                                        |
| H-5 (long ops)                  | 09.3       | Integration test: install large add-on (Grafana) → no Bridge timeout.                                                                                                      |
| T-1 (typed schema)              | 09.4       | `grep -r "schema.Resource " terraform-provider-homeassistant/` returns zero hits.                                                                                          |
| T-2 (import blocks)             | 09.4       | Integration test: `tofu import homeassistant_addon.mosquitto mosquitto` → state populated, subsequent plan clean.                                                          |
| T-3 (state locks)               | 09.4       | Smoke test: same-host concurrent `tofu apply` → second waits for first (OpenTofu behaviour).                                                                               |
| T-4 (lifecycle blocks)          | 09.4       | Unit test: `prevent_destroy=true`, plan a destroy, assert `resp.Diagnostics.HasError()`.                                                                                   |
| T-5 (id naming)                 | 09.4       | Integration test: `tofu import` populates both `id` and `slug` in state.                                                                                                   |

---

## 13. Sources

**Primary (HIGH confidence — code/docs read directly):**

- HA Supervisor source (current `main`):
  - `supervisor/api/__init__.py` — endpoint registration, V1/V2 split, MAX_CLIENT_SIZE.
  - `supervisor/api/middleware/security.py` — token validation, role checks, blacklist, V1/V2 patterns, FILTERS regex.
  - `supervisor/api/apps.py` — app CRUD endpoints, async.shield wrapping, `info_data` secrets redaction, install
    background_task.
  - `supervisor/api/store.py` — store/install endpoints, `_extract_app` semantics.
  - `supervisor/api/utils.py` — `api_process`, `background_task`, `api_return_error`, `extract_supervisor_token`.
  - `supervisor/api/auth.py` — auth flow, password reset.
  - `supervisor/jobs/__init__.py` — JobManager, SupervisorJob lifecycle.
  - `supervisor/validate.py` — token regex (`^[0-9a-f]{32,256}$`), `_migrate_supervisor_config`, `migrate_addon_to_app`.
- HA Add-on docs (`developers.home-assistant.io/docs/add-ons/configuration`, `/communication`).
- OpenTofu docs:
  - `state/locking/`, `state/backends/`, `state/sensitive-data/`, `state/import/`.
  - `language/settings/backends/local/` — local backend behaviour.
  - `language/import/` — import blocks.
  - `language/resources/behavior/` — lifecycle semantics.
  - `intro/whats-new/` — 1.12 features (`destroy = false`, etc.).
- Terraform plugin framework docs (`developer.hashicorp.com/terraform/plugin/framework`):
  - `framework/` (overview), `resources/import`, `resources/state-upgrade`, `resources/plan-modification`,
    `handling-data/schemas`, `migrating/benefits`.

**Secondary (MEDIUM confidence):**

- Tailscale Serve docs (`tailscale.com/kb/1312/tailscale-serve`) — TLS provision via tailnet, identity headers, "listen
  on localhost" best practice.

**Tertiary (LOW confidence, needs empirical verification in spike):**

- Token rotation across Supervisor restart.
- HA backup integration with `addon_config` mount.
- V1 endpoint removal timeline ("Remove: 2023" comment is from 2023, may already be overdue).

---

_Last updated: 2026-08-31 — Initial PITFALLS research for v1.3 opentofu-bridge milestone. 31 pitfalls across 8
categories; all tied to phases in the Prevention Matrix. Ready for `gsd-roadmapper` to consume._
