# terraform-provider-homeassistant

The `homeassistant` Terraform/OpenTofu provider manages Home Assistant add-ons declaratively. It talks to the
[terraform-bridge](../terraform-bridge/DOCS.md) add-on over HTTP; the Bridge in turn translates every call into a Home
Assistant Supervisor API request. The provider never talks to the Supervisor directly and never holds a
`SUPERVISOR_TOKEN`.

This document is the operator-facing reference: how to install the provider, how to configure it, the full resource and
data source schemas, worked examples, and a per-`error_code` troubleshooting section. Every typed diagnostic the
provider emits carries an anchor into the [Troubleshooting](#troubleshooting) section below, so a failing `tofu apply`
points straight at its own remediation.

> **Phase 1 status.** The provider is under active development during the v1.3 milestone. Expect breaking changes
> between milestones. Empirical end-to-end verification against a live Home Assistant host lands in Phase 14.

## Installation

The provider is not published to a registry yet. Phase 1 installs it from source via OpenTofu's `dev_overrides`
mechanism, which points the CLI at a locally built binary and skips the registry download entirely.

### Prerequisites

- **Go 1.25+** — to build the provider binary.
- **OpenTofu 1.12+** or **Terraform 1.5+** — the provider speaks plugin protocol v6.
- **Home Assistant** with the **terraform-bridge add-on installed and started**. The Bridge exposes the HTTP API this
  provider consumes; without it there is nothing to talk to.
- **Network reachability** from the machine running `tofu` to the Bridge's listen address (default port `8124`).

### Step 1 — build the provider binary

```bash
cd terraform-provider-homeassistant
go build -o terraform-provider-homeassistant .
```

This produces a `terraform-provider-homeassistant` executable in the module directory. Note its absolute path — the next
step references it.

```bash
pwd   # e.g. /share/development/homeassistant-addons/terraform-provider-homeassistant
```

### Step 2 — register the binary via `dev_overrides`

Create (or edit) `~/.terraformrc` and add a `provider_installation` block pointing at the **directory** containing the
binary — not the binary itself:

```hcl
provider_installation {
  dev_overrides {
    "registry.opentofu.org/akentner/homeassistant" = "/absolute/path/to/terraform-provider-homeassistant"
  }

  # Everything else still resolves normally from the registry.
  direct {}
}
```

If you use Terraform rather than OpenTofu, use the `registry.terraform.io/akentner/homeassistant` address instead. Both
addresses resolve to the same binary; only the CLI you run decides which one is consulted.

### Step 3 — declare the provider in your configuration

```hcl
terraform {
  required_providers {
    homeassistant = {
      source = "akentner/homeassistant"
    }
  }
}

provider "homeassistant" {
  endpoint     = "http://homeassistant.local:8124"
  bearer_token = var.bridge_token
}
```

### Step 4 — initialise and plan

```bash
tofu init
tofu plan
```

With `dev_overrides` active, `tofu init` prints a warning that the provider is overridden and `tofu plan` prints a
reminder on every run. Both are expected — the warning is how OpenTofu signals that you are not running a
registry-published build.

On the first `tofu plan` the provider performs a version handshake against the Bridge's `GET /v1/version` endpoint. If
that handshake fails, the run stops before any add-on is touched; see
[Troubleshooting: version](#troubleshooting-version).

### State file placement

The provider stores add-on state in the standard Terraform/OpenTofu state file. Configure the local backend explicitly:

```hcl
terraform {
  backend "local" {
    path = "/data/terraform.tfstate"
  }
}
```

- **Running on the Home Assistant host** (the usual case): use `path = "/data/terraform.tfstate"`. That path is inside
  the Bridge add-on's `addon_config:rw` mount, which is where the Bridge itself reports its state file lives — see the
  `state_file_path` attribute of the [`homeassistant_supervisor_info`](#homeassistant_supervisor_info) data source.
- **Running off-host** (from a workstation): keep the state file wherever your workflow expects it, but mirror it into
  the add-on's share volume so the on-host copy stays authoritative for backups.

**Backups.** Contents of the `addon_config:rw` mount — including `terraform.tfstate` — are included in Home Assistant
backups taken with `ha backups new --app terraform-bridge`. Keeping state at `/data/terraform.tfstate` therefore means
your infrastructure state is backed up alongside the add-on that serves it, with no extra automation.

**State contents are sensitive.** Add-on `options` are written to state verbatim, and add-on options frequently contain
credentials. Treat the state file as a secret: restrict its permissions, and enable state encryption at rest if your
threat model calls for it.

### Phase 1 transport limitation (no TLS)

The Bridge currently serves **plain HTTP**. TLS termination is deferred to Phase 2+. During Phase 1 the access-control
boundary is the **network layer** — the Bridge is expected to be reachable only over a Tailscale ACL (or an equivalent
private overlay), never from an untrusted network.

If your threat model requires transport encryption today, put a reverse proxy in front of the Bridge, terminate TLS
there, and point the provider's `endpoint` at the proxy. Do not expose the Bridge's port directly to a network you do
not control.

## Provider Configuration

```hcl
provider "homeassistant" {
  endpoint     = "http://homeassistant.local:8124"
  bearer_token = var.bridge_token
}
```

| Argument       | Type     | Required | Sensitive | Description                                                 |
| -------------- | -------- | -------- | --------- | ----------------------------------------------------------- |
| `endpoint`     | `string` | yes      | no        | Base URL of the Bridge HTTP API, including scheme and port. |
| `bearer_token` | `string` | yes      | yes       | Bearer token matching the Bridge's stored token hash.       |

**`endpoint`** must parse as a URL with an `http` or `https` scheme and a non-empty host. The default Bridge port is
`8124`. Do not include a trailing slash or a path.

**`bearer_token`** is marked `Sensitive` in the schema, so OpenTofu redacts it from plan output and CLI logs. The
provider additionally guarantees that the token value never appears in any diagnostic message or error string.

### Obtaining the bearer token

The Bridge generates a 256-bit token on first start and surfaces the **plaintext exactly once**:

1. Open **Settings → Add-ons → Terraform Bridge → Log** immediately after the first start. The issuance log record names
   the file the plaintext was written to.
2. Read the plaintext from `/data/initial-token` inside the add-on (mode `0600`).
3. Copy it into your Terraform variables — never into a committed `.tf` file.

The Bridge only ever stores the SHA-256 **hash** of the token, so a lost plaintext cannot be recovered. Issue a
replacement with `POST /v1/auth/rotate`; the old token stays valid for a short grace window so you can update the
provider configuration without an outage.

Supply the token through a variable rather than a literal:

```hcl
variable "bridge_token" {
  type      = string
  sensitive = true
}
```

```bash
export TF_VAR_bridge_token='...'
tofu plan
```

## Resource Reference

### `homeassistant_addon`

Manages the full lifecycle of one Home Assistant add-on: install, configure, start, and uninstall.

#### Arguments

| Name         | Type          | Required | Default  | Description                                            |
| ------------ | ------------- | -------- | -------- | ------------------------------------------------------ |
| `slug`       | `string`      | yes      | —        | Add-on slug. Changing it forces replacement.           |
| `repository` | `string`      | no       | `"core"` | Repository the add-on is installed from.               |
| `url`        | `string`      | no       | —        | Explicit repository URL for unregistered repositories. |
| `options`    | `map(string)` | no       | —        | Add-on options, sent to the Supervisor verbatim.       |
| `start`      | `bool`        | no       | `true`   | Start the add-on after install or adoption.            |
| `boot`       | `string`      | no       | —        | Boot mode: `auto`, `manual`, or `manual_only`.         |

- **`slug`** carries `RequiresReplace`: a different slug is a different add-on, so changing it destroys and recreates.
- **`options`** is a flat string map. The provider does not validate option keys — the Supervisor re-validates the
  payload against the add-on's own schema and rejects anything invalid.
- **`boot`** is a closed enum. Any other value fails at plan time, before a request is sent.

#### Attributes

All of the following are read-only (`Computed`) and refreshed from `GET /v1/addons/{slug}/info` after every operation.

| Name            | Type           | Description                                             |
| --------------- | -------------- | ------------------------------------------------------- |
| `version`       | `string`       | Currently installed add-on version.                     |
| `state`         | `string`       | Supervisor-reported state, e.g. `started` or `stopped`. |
| `started`       | `bool`         | Whether the add-on is currently running.                |
| `hostname`      | `string`       | Container hostname assigned by the Supervisor.          |
| `dns`           | `list(string)` | DNS names resolving to the add-on container.            |
| `ingress_url`   | `string`       | Ingress URL, when the add-on exposes Ingress.           |
| `ingress_entry` | `string`       | Ingress entry path, when the add-on exposes Ingress.    |
| `webui_url`     | `string`       | Web UI URL, when the add-on publishes one.              |

The last five attributes are **pass-through values**: whatever the Supervisor reports is what lands in state. When the
Supervisor omits a field, the provider surfaces an empty string (or a null list for `dns`) rather than synthesising a
substitute. An empty `hostname` means "the Supervisor did not report one", not "the provider failed to look it up".

`state` carries the `UseStateForUnknown` plan modifier, so a refresh that finds no change does not produce a spurious
diff.

#### Timeouts

```hcl
timeouts {
  create = "10m"
  update = "2m"
  delete = "5m"
}
```

| Operation | Default | Rationale                                                            |
| --------- | ------- | -------------------------------------------------------------------- |
| `create`  | `10m`   | Installs pull a container image; large add-ons dominate this budget. |
| `read`    | `2m`    | A single Supervisor info call.                                       |
| `update`  | `2m`    | Options writes are synchronous and fast.                             |
| `delete`  | `5m`    | Uninstall plus the nonce round-trip.                                 |

#### Lifecycle behaviour

**Create is adoption-aware.** The provider first calls `GET /v1/addons/{slug}/info`:

- **200** — the add-on already exists, so it is _adopted_ rather than reinstalled. If your `options` or `boot` differ
  from what the Supervisor reports, the difference is pushed in the same apply. This makes the first apply against a
  pre-existing add-on fully convergent: no second run needed.
- **404** — the add-on is installed via `POST /v1/addons/{slug}/install`.
- **409 `already_installed`** — a concurrent apply installed it first; the provider falls through to the adoption path.

After either path, if `start = true` and the add-on is not running, the provider issues `POST /v1/addons/{slug}/start`.
A successful apply therefore leaves the add-on running.

**Update** pushes `options` and `boot` through `POST /v1/addons/{slug}/options` in a single request. Keys present in the
Supervisor's current options but absent from your configuration are carried forward rather than dropped, so a partial
`options` map does not silently reset Supervisor-side defaults. If the Bridge flags leaked credentials in the submitted
options, the provider emits a **warning** and the apply proceeds — see [Troubleshooting: pwned](#troubleshooting-pwned).

**Delete** is nonce-protected. The provider requests a single-use nonce from `POST /v1/auth/nonce` and presents it as
the `X-Force-Destroy` header on `POST /v1/addons/{slug}/uninstall`. If the nonce expires or was already consumed, the
provider retries exactly once with a fresh nonce, then fails. A `404` during delete is treated as success — the add-on
is already gone.

**Read** is idempotent. A `404` clears the resource from state, so `tofu destroy` against an add-on that was removed
outside Terraform is a no-op rather than an error.

#### Import

```bash
tofu import homeassistant_addon.mosquitto core_mosquitto
tofu import homeassistant_addon.custom my-repo/my_addon
```

The import ID accepts either `{slug}` — in which case `repository` defaults to `"core"` — or `{repository}/{slug}`.
Every other attribute is populated by the refresh that follows the import.

## Data Source Reference

### `homeassistant_addon`

Reads one add-on by slug without managing it. Use it to reference an add-on's attributes from other resources.

| Name   | Type     | Required | Description             |
| ------ | -------- | -------- | ----------------------- |
| `slug` | `string` | yes      | Add-on slug to look up. |

Read-only attributes: `name`, `version`, `state`, `started`, `options`, `boot`, `repository`, `hostname`, `dns`,
`ingress_url`, `ingress_entry`, and `webui_url`. Types and pass-through semantics match the
[resource attributes](#attributes) above.

Unlike the resource, a missing add-on is an **error** here, not an empty state: a data source is an assertion that
something exists. See [Troubleshooting: not found](#troubleshooting-not-found).

### `homeassistant_supervisor_info`

Reads the Bridge's own status. Takes **no arguments**.

| Name                 | Type     | Description                                           |
| -------------------- | -------- | ----------------------------------------------------- |
| `bridge_version`     | `string` | Version of the terraform-bridge add-on.               |
| `supervisor_version` | `string` | Version of the Home Assistant Supervisor.             |
| `uptime_seconds`     | `number` | Seconds since the Bridge process started.             |
| `state_file_path`    | `string` | Absolute path of the Bridge's state file on the host. |

`uptime_seconds` is a 64-bit integer, so it compares cleanly inside `lifecycle.precondition` blocks without coercion.
This data source is designed for exactly that use — asserting Bridge or Supervisor versions before an apply proceeds.

## Examples

### Full add-on resource

```hcl
resource "homeassistant_addon" "mosquitto" {
  slug       = "core_mosquitto"
  repository = "core"

  options = {
    logins    = "[]"
    anonymous = "false"
  }

  start = true
  boot  = "auto"

  timeouts {
    create = "10m"
    update = "2m"
    delete = "5m"
  }

  lifecycle {
    # Recommended: refuse to destroy this add-on by accident.
    # Comment this out to allow destroy; use `terraform destroy` carefully.
    prevent_destroy = true
  }
}

output "mosquitto_hostname" {
  value = homeassistant_addon.mosquitto.hostname
}
```

`prevent_destroy = true` is the recommended default for any add-on holding data you care about. It makes OpenTofu refuse
a plan that would destroy the resource, which turns an accidental `slug` edit or a stray `tofu destroy` into a plan-time
error instead of a deleted add-on.

### Adopting an already-installed add-on

The provider adopts rather than reinstalls, so pointing a resource at an existing add-on needs no import step:

```hcl
resource "homeassistant_addon" "file_editor" {
  slug = "core_configurator"

  options = {
    ssl = "false"
  }

  lifecycle {
    # Recommended: refuse to destroy this add-on by accident.
    # Comment this out to allow destroy; use `terraform destroy` carefully.
    prevent_destroy = true
  }
}
```

The first apply reads the add-on's current state, pushes the `options` difference, and converges. Use `tofu import`
instead when you want the resource in state without any configuration change.

### Reading an add-on without managing it

```hcl
data "homeassistant_addon" "mosquitto" {
  slug = "core_mosquitto"
}

output "mqtt_endpoint" {
  value = "mqtt://${data.homeassistant_addon.mosquitto.hostname}:1883"
}
```

### Guarding an apply with `lifecycle.precondition`

```hcl
data "homeassistant_supervisor_info" "bridge" {}

resource "homeassistant_addon" "nodered" {
  slug  = "a0d7b954_nodered"
  start = true

  lifecycle {
    # Recommended: refuse to destroy this add-on by accident.
    # Comment this out to allow destroy; use `terraform destroy` carefully.
    prevent_destroy = true

    precondition {
      condition     = data.homeassistant_supervisor_info.bridge.uptime_seconds > 60
      error_message = "Bridge started less than a minute ago; wait for the Supervisor connection to settle."
    }
  }
}
```

Preconditions are evaluated at plan time, so a failing assertion stops the run before any add-on is touched.

## Troubleshooting

Every error the Bridge returns carries a machine-readable `error_code`. The provider translates each one into a typed
diagnostic whose detail includes the Bridge's `request_id` and a link to the matching subsection below. Grep the Bridge
logs for that `request_id` to correlate a failed apply with the exact server-side record.

Each subsection lists the code, the HTTP status, the Bridge-side condition, and the remediation, followed by the
diagnostic text the provider prints verbatim.

### Troubleshooting: unauthorized

| `error_code`   | HTTP status | Bridge condition                | Remediation                             |
| -------------- | ----------- | ------------------------------- | --------------------------------------- |
| `unauthorized` | `401`       | Token missing, wrong, or stale. | Re-copy the token, or rotate a new one. |

Anchor: `DOCS.md#troubleshooting-unauthorized`

The token you configured does not hash to the value stored at `/data/bridge-token`. This is the expected failure after a
rotation whose new token was never propagated into the provider configuration. Copy the current token, or issue a fresh
one via `POST /v1/auth/rotate` and update `bearer_token`.

> Bridge authentication failed: check the bearer_token Provider argument matches the Bridge's current token (rotate via
> POST /v1/auth/rotate if it changed).

### Troubleshooting: not found

| `error_code` | HTTP status | Bridge condition                   | Remediation                              |
| ------------ | ----------- | ---------------------------------- | ---------------------------------------- |
| `not_found`  | `404`       | The Supervisor has no such add-on. | Check the slug; confirm it is installed. |

Anchor: `DOCS.md#troubleshooting-not-found`

For the **resource**, a `404` during refresh is not an error — it clears the resource from state so a subsequent destroy
is a no-op. For the **data source**, a `404` is an error, because the data source asserts the add-on exists. Add-on
slugs are frequently prefixed (`core_mosquitto`, `a0d7b954_nodered`); copy the exact slug from the add-on's URL in the
Home Assistant UI.

> The add-on was not found at Bridge: verify the slug spelling and that the add-on is installed.

### Troubleshooting: critical addon protected

| `error_code`               | HTTP status | Bridge condition             | Remediation                    |
| -------------------------- | ----------- | ---------------------------- | ------------------------------ |
| `critical_addon_protected` | `403`       | Add-on is a critical add-on. | Unlist it, or present a nonce. |

Anchor: `DOCS.md#troubleshooting-critical-addon-protected`

The Bridge maintains a `critical_addons` list of add-ons that must not be destroyed by automation — typically the Bridge
itself and anything whose loss would lock you out of Home Assistant. This guard is deliberate: reaching it usually means
the plan is wrong, not the guard.

> This add-on is in critical_addons; either remove it from the Bridge's critical_addons option or issue a nonce via POST
> /v1/auth/nonce and retry with X-Force-Destroy.

### Troubleshooting: prevented destroy

| `error_code`        | HTTP status | Bridge condition                    | Remediation                        |
| ------------------- | ----------- | ----------------------------------- | ---------------------------------- |
| `prevented_destroy` | `403`       | Destroy blocked by lifecycle guard. | Comment the guard out, then apply. |

Anchor: `DOCS.md#troubleshooting-prevented-destroy`

The resource has `lifecycle.prevent_destroy = true` (the recommended default in the [Examples](#examples) above). This
is working as intended. If the destroy really is what you want, comment the meta-argument out, apply, and consider
putting it back afterwards.

> lifecycle.prevent_destroy = true is set on this resource; comment it out or destroy explicitly.

### Troubleshooting: already installed

| `error_code`        | HTTP status | Bridge condition                    | Remediation                         |
| ------------------- | ----------- | ----------------------------------- | ----------------------------------- |
| `already_installed` | `409`       | Install raced a concurrent install. | None — the provider adopts instead. |

Anchor: `DOCS.md#troubleshooting-already-installed`

Not a failure in normal operation. The provider checks for an existing add-on before installing, so this code only
appears when two applies race for the same slug. The losing run falls through to the adoption path and converges. Seeing
it repeatedly means two automations are managing the same add-on — fix that, not the provider.

> Add-on is already installed; this is treated as adoption success (Create will read existing state).

### Troubleshooting: locked

| `error_code` | HTTP status | Bridge condition                          | Remediation          |
| ------------ | ----------- | ----------------------------------------- | -------------------- |
| `locked`     | `423`       | Another operation holds this slug's lock. | Retry in about 30 s. |

Anchor: `DOCS.md#troubleshooting-locked`

The Bridge serialises operations per add-on slug. A concurrent install, options write, or uninstall is still running.
Retrying after the in-flight operation finishes succeeds. Persistent locking suggests an operation that never completed
— check the Bridge log for the stuck request.

> Another operation is in flight on this slug; retry in 30s.

### Troubleshooting: nonce expired

| `error_code`    | HTTP status | Bridge condition                  | Remediation                     |
| --------------- | ----------- | --------------------------------- | ------------------------------- |
| `nonce_expired` | `401`       | `X-Force-Destroy` nonce past TTL. | Retry; a fresh nonce is issued. |

Anchor: `DOCS.md#troubleshooting-nonce-expired`

Destroy nonces are short-lived. The provider fetches one immediately before each uninstall and retries once
automatically if it expires in flight, so reaching this diagnostic means both attempts expired — usually a sign of
severe latency or a clock skew between the provider host and the Bridge. Check both clocks.

> The X-Force-Destroy nonce is expired or never issued; request a fresh nonce via POST /v1/auth/nonce.

### Troubleshooting: nonce used

| `error_code` | HTTP status | Bridge condition             | Remediation                     |
| ------------ | ----------- | ---------------------------- | ------------------------------- |
| `nonce_used` | `401`       | Nonce already consumed once. | Retry; a fresh nonce is issued. |

Anchor: `DOCS.md#troubleshooting-nonce-used`

Nonces are single-use by design, so a replayed destroy request cannot succeed. As with an expired nonce, the provider
retries once with a fresh value. Reaching this diagnostic after the retry points at two concurrent destroys competing
for the same nonce.

> The X-Force-Destroy nonce has already been used (single-use); request a fresh nonce via POST /v1/auth/nonce.

### Troubleshooting: install timeout

| `error_code`      | HTTP status | Bridge condition                       | Remediation                            |
| ----------------- | ----------- | -------------------------------------- | -------------------------------------- |
| `install_timeout` | `504`       | Supervisor install job did not finish. | Re-run apply; the job may have landed. |

Anchor: `DOCS.md#troubleshooting-install-timeout`

The Bridge stopped polling the Supervisor's install job before it reached a terminal state. **The install may still be
running server-side.** Re-run `tofu plan` — if the add-on finished installing, the provider adopts it and converges with
no second install. Large images on slow storage are the usual cause; raise the resource's `create` timeout if it recurs.

> Install polling exceeded the timeout; the Supervisor job may continue server-side.

### Troubleshooting: upstream error

| `error_code`     | HTTP status | Bridge condition                   | Remediation                     |
| ---------------- | ----------- | ---------------------------------- | ------------------------------- |
| `upstream_error` | `502`       | Bridge could not reach Supervisor. | Retry; check Supervisor health. |

Anchor: `DOCS.md#troubleshooting-upstream-error`

A transport-level failure between the provider and the Bridge surfaces here too, with the underlying error in the
detail. If retries keep failing, confirm the Supervisor is healthy and that the Bridge add-on is running.

> Transient Supervisor failure: retry per the operation timeout.

### Troubleshooting: pwned

| `error_code` | HTTP status | Bridge condition                           | Remediation                           |
| ------------ | ----------- | ------------------------------------------ | ------------------------------------- |
| `pwned`      | `200`       | Submitted options contain a leaked secret. | Rotate the credential, then re-apply. |

Anchor: `DOCS.md#troubleshooting-pwned`

**This is the only condition the provider reports as a warning rather than an error**, and the only one where the apply
still succeeds. The Bridge checked a credential in your `options` against a known-breach corpus and matched it. The
add-on is configured, but the credential it was configured with is public. Rotate it and apply again; the warning clears
once the leaked value is gone.

> This add-on has a known compromised credentials leak (pwned): review the supervisor warning and rotate the add-on
> credentials before continuing.

### Troubleshooting: version

| `error_code` | HTTP status | Bridge condition                        | Remediation                             |
| ------------ | ----------- | --------------------------------------- | --------------------------------------- |
| `version`    | `200`       | Handshake outside the supported window. | Align the provider and Bridge versions. |

Anchor: `DOCS.md#troubleshooting-version`

Not a Bridge error code but a provider-side refusal. During `Configure` the provider reads `GET /v1/version` and
compares versions against the Bridge's advertised `[min_provider_version, max_provider_version]` window. Two failures
are possible:

- **Provider too old** — your provider version is below the Bridge's `min_provider_version`. Rebuild the provider from a
  matching checkout.
- **Bridge too new** — the Bridge's `schema_version` exceeds its own `max_provider_version`. Update the provider, or pin
  the Bridge add-on to the previous version.

The diagnostic detail carries all three version fields the Bridge reported, so you can see exactly which bound was
violated. The handshake runs before any add-on is touched — a version mismatch never leaves a half-applied change.

### Troubleshooting: unknown

| `error_code` | HTTP status | Bridge condition                      | Remediation                     |
| ------------ | ----------- | ------------------------------------- | ------------------------------- |
| `unknown`    | any         | Bridge returned an unrecognised code. | Update the provider; report it. |

Anchor: `DOCS.md#troubleshooting-unknown`

The defensive fallback. A Bridge newer than the provider can emit codes the provider has not been taught yet; rather
than failing opaquely, the provider surfaces the raw code, the HTTP status, and the `request_id`. If you hit this with
matching versions, it is a bug worth reporting.

> Bridge returned an unrecognized error_code.

### Reading a diagnostic

Every error diagnostic follows the same shape:

```text
Summary: <one sentence naming the condition and the action to take>
Detail:  request_id: <bridge request id>
         DOCS.md#troubleshooting-<code>
         bridge_message: <optional Bridge-supplied message>
         bridge_status: <http status>
```

The `request_id` is the correlation key: grep the Bridge add-on log for it to find the server-side record of the same
request. The anchor is the link into this section. Neither the bearer token nor a destroy nonce ever appears in a
diagnostic — that invariant is regression-tested on every provider build.
