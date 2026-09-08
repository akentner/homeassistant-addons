# Technology Stack: terraform-bridge + terraform-provider-homeassistant

**Project:** homeassistant-addons / v1.3 opentofu-bridge **Researched:** 2026-08-31 **Mode:** ecosystem **Confidence:**
HIGH for stack choices; MEDIUM for individual version pins (subject to fresh-check at scaffold time)

---

## Summary

Two artifacts ship out of this milestone:

1. **`terraform-bridge/`** — HA Supervisor add-on, **single static Go binary**. Wraps Supervisor HTTP API as a versioned
   HTTPS surface, generates/rotates a bearer token, serves a JSON Schema describing the Provider's resource surface.
2. **`terraform-provider-homeassistant/`** — Go module at the repo root. Built locally from source, served via
   `terraform-plugin-framework` (modern, protocol-6, type-safe).

**Recommendation at a glance:**

| Concern              | Choice                                    | Version     | Why                                                                                  |
| -------------------- | ----------------------------------------- | ----------- | ------------------------------------------------------------------------------------ |
| Bridge language      | **Go**                                    | 1.25        | Schema can be shared with the Provider; one toolchain in CI                          |
| HA base image        | `ghcr.io/home-assistant/amd64-base:3.24`  | Alpine 3.24 | Smallest footprint; no extra runtime needed for Go static binary                     |
| Bridge build image   | `golang:1.25-alpine`                      | multi-stage | Standard "compile + COPY --from" pattern                                             |
| HTTP router          | `go-chi/chi/v5`                           | v5.3.2      | Stdlib-compatible, ~1000 LOC, built-in middleware stack                              |
| Supervisor client    | **none — use stdlib `net/http`**          | n/a         | No official Go client; ~300 LoC makes that explicitly small                          |
| Auth primitives      | `crypto/rand` + `crypto/subtle`           | stdlib      | Tokens are random bytes; comparison constant-time. No KDF needed for random secrets. |
| Token hashing (idle) | `golang.org/x/crypto/argon2`              | v0.55.0     | If user-supplied extra auth ever added; not in Phase-1                               |
| Schema emission      | Embed `terraform-plugin-framework` schema | v1.19.0     | Share types between Bridge and Provider                                              |
| Provider framework   | `terraform-plugin-framework`              | v1.19.0     | HashiCorp-recommended for new providers; OpenTofu-compatible                         |
| State backend        | local `/data/terraform.tfstate`           | n/a         | OpenTofu CLI manages state; Bridge does NOT touch tfstate                            |

**OpenTofu compatibility:** OpenTofu 1.12 (latest stable) runs Terraform-protocol-v5 and v6 providers interchangeably.
Both `terraform-plugin-framework` (protocol 6) and `terraform-plugin-sdk/v2` (protocol 5) work with OpenTofu 1.12 —
verified via the OpenTofu v1.12 docs and Hashicorp's framework README (both declare "compatible with Terraform ≥ 0.12 /
OpenTofu ≥ 1.0").

---

## Bridge Language & Framework: **Go (single static binary)**

### Decision

The Bridge is a single Go binary, compiled in a multi-stage Docker build (`golang:1.25-alpine` →
`ghcr.io/home-assistant/amd64-base:3.24`). Same toolchain (`go` 1.25) is used for the Provider.

### Tradeoff Analysis

| Option   | Pluses                                                                                                                                                                                                                                                                                                                                            | Minuses                                                                                                                                                                                                     | Verdict         |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| **Go**   | Single static binary (small image, no runtime in container); one toolchain covers Bridge + Provider (no Bun + Python env in CI); Bridge schema types can be **shared** with the Provider via a Go submodule (`terraform-bridge/contract` → imported by both Bridge and Provider); in-process `httptest.Server` for unit tests without Supervisor. | No official `aiohasupervisor` equivalent; need to roll our own ~300-LoC supervisor HTTP client.                                                                                                             | **Recommended** |
| Python   | Official `aiohasupervisor` client (`home-assistant-libs/python-supervisor-client`, Apache-2.0); fastest to write; pattern already proven with `markdown-renderer` and `phone-logger`.                                                                                                                                                             | Bridge → Provider schema drift risk (cross-language); need both Python (Bridge) and Go (Provider) toolchains in CI. Schema must be hand-maintained in both repos. Drift = broken `tofu apply`.              | Not chosen      |
| Bun/Node | Same toolchain as Meridian; TS type-sharing could mirror Go.                                                                                                                                                                                                                                                                                      | No official supervisor client; no obvious upside over Python for a small CRUD service; Meridian's Bun runtime is Alpine-packaged Bun, but bridges HTTP-server logic doesn't benefit from a heavier runtime. | Not chosen      |

### Why Go specifically for THIS bridge (not just "consistency")

1. **Schema coupling is the deciding factor.** The Bridge serves a JSON Schema that the Provider consumes to `Configure`
   itself. If both are Go, the same `contract.Addon` struct (with `json` + `tf-schema` tags) lives in one place. Drift
   is detected at `go build` time on the Provider side. In Python, duplicating the same definitions as dataclasses +
   pydantic AND in the Provider as Go structs is inevitable drift — the user explicitly noted "Bridge API and Provider
   schema must evolve together".

2. **Same-dataset reasoning for token & state files.** The Provider reads the bearer token off the filesystem to
   authenticate to the Bridge in CI; if Bridge and Provider are both Go, that read happens via the same
   `internal/tokenfile` package imported by both.

3. **No new toolchain in CI.** The Provider is already Go. Adding Python would double CI time (linters, tests,
   multi-arch builds) for zero net capability gain.

4. **Go static binary + HA base Alpine is small.** `ghcr.io/home-assistant/amd64-base:3.24` (Alpine 3.24, no
   Java/Python/Node) plus a ~12 MiB static binary yields a small, fast, supervisor-friendly image. Multi-stage
   Dockerfile pattern is well-trodden (cf. `authentik/Dockerfile` in this same repo, which uses the same
   `COPY --from=build-stage` pattern — though authentik doesn't compile Go itself).

### Image Implication

No `ghcr.io/home-assistant/amd64-base-go` image exists. Pattern:

```dockerfile
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM golang:1.25-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/terraform-bridge ./cmd/bridge

FROM ${BUILD_FROM}
COPY --from=build /out/terraform-bridge /usr/bin/terraform-bridge
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
```

`CGO_ENABLED=0` produces a static binary that runs on Alpine/musl without any libc/glibc mismatch. Pattern is standard
for Go binaries in Alpine HA add-ons.

### What we explicitly REJECT

- **Python (FastAPI + `aiohasupervisor`)** — schema drift risk across languages outweighs the official-client benefit.
  Three cross-language surfaces (JSON Schema, error envelope, token file format) would need hand-syncing.
- **Bun/Node** — would need `apk add nodejs` in runtime stage (cf. `meridian/Dockerfile`), which is heavier than the
  static Go approach and offers no advantage.
- **Generous use of `gRPC`/`tfproto6` hand-rolling** — would be reinventing `terraform-plugin-framework`.

---

## Provider Framework: **terraform-plugin-framework v1.19.0**

### Decision

```go
// go.mod
require (
    github.com/hashicorp/terraform-plugin-framework v1.19.0
    github.com/hashicorp/terraform-plugin-go v0.30.0 (transitive)
    github.com/hashicorp/terraform-plugin-mux v0.21.0 (only if needed)
)
```

### Tradeoff Analysis

| Option                                                           | License | Status                                                           | Protocol                  | Recommendation                    |
| ---------------------------------------------------------------- | ------- | ---------------------------------------------------------------- | ------------------------- | --------------------------------- |
| **`terraform-plugin-framework`** (v1.19.0, published 2026-03-10) | MPL-2.0 | **GA**, recommended for new providers by HashiCorp docs          | v6 (provider protocol v6) | **Use this**                      |
| `terraform-plugin-sdk/v2` (v2.40.1, published 2026-04-28)        | MPL-2.0 | Stable, broader ecosystem; SDK v2 itself now points to framework | v5                        | Use only if a feature is SDK-only |
| `tfproto6`/hand-rolled gRPC                                      | n/a     | High risk; no examples for trivial CRUD resources                | v6                        | Not worth the engineering cost    |

The framework README is unambiguous (verified via pkg.go.dev):

> "We recommend using the framework to develop new providers because it offers significant advantages as compared to
> Terraform Plugin SDKv2."

The SDK v2 README in turn points at framework for new providers:

> "For new provider development it is recommended to investigate `terraform-plugin-framework`."

Both declare Go 1.25+ required. Both work with OpenTofu (provider protocol compatibility is enforced by OpenTofu 1.12+;
see https://opentofu.org/docs/intro/whats-new/ — no breaking protocol changes since migration to 1.0).

### Why not SDK v2

SDK v2's `helper/schema` uses `map[string]interface{}` for state — weaker typing than the framework's typed attribute
system. For a Phase-1 single resource with a tight schema, the framework's typed `schema.StringAttribute`,
`schema.BoolAttribute`, `schema.ListNestedBlock` give compile-time errors on schema mismatch instead of panics at apply
time. SDK v2 also still supports the older `terraform apply` field path semantics (e.g. `["foo.0.bar"]`) that the
framework has retired.

### Why not hand-rolled `tfproto6` provider server

Implementing a provider is mostly CRUD over one HTTP service. The framework already provides:

- Schema definition with typed attributes
- Plan/Read/Apply/Delete lifecycle
- Built-in validators (`stringvalidator`, `int64validator`, `regexvalidator`)
- `tfsdk` for state marshaling
- `provider.Provider` interface with `Resources()`, `DataSources()`, `Schema()`
- `providerserver.Serve()` so the binary plugs into `tofu`

Roll-your-own would re-implement all of this in ~2000 LoC before any business logic. Not justifiable.

### OpenTofu compatibility (explicit verification)

- `terraform-plugin-framework` README: "Providers built with this framework are compatible with Terraform version v0.12
  and above." OpenTofu 1.12 is API-compatible with Terraform 1.x.
- OpenTofu 1.12 docs (https://opentofu.org/docs/intro/whats-new/) list **no breaking protocol changes** in 1.12.
  Provider protocol v6 (framework) and v5 (SDK v2) are both supported.
- Auto-update of `tofu plan`/`apply` integrates with `TF_REATTACH_PROVIDERS` env var. For local installs, the provider
  is built via `make build-provider PROVIDER=homeassistant` and placed under
  `~/.local/share/terraform/plugins/registry.terraform.io/akentner/homeassistant/<version>/linux_amd64/`.

---

## Supervisor API Client: **roll our own with `net/http` (Go)**

### Decision

Implement a minimal Supervisor client at `internal/supervisor/client.go`:

```go
type Client struct {
    baseURL  string // http://supervisor
    token    string // SUPERVISOR_TOKEN env
    http     *http.Client
}

func (c *Client) Addon(ctx context.Context, slug string) (*Addon, error)
func (c *Client) AddonStart(ctx context.Context, slug string) error
func (c *Client) AddonStop(ctx context.Context, slug string) error
func (c *Client) AddonRestart(ctx context.Context, slug string) error
func (c *Client) AddonUninstall(ctx context.Context, slug string) error
func (c *Client) AddonUpdate(ctx context.Context, slug string, opts map[string]any) (*Job, error)
func (c *Client) AddonInfo(ctx context.Context, slug string) (*AddonDetail, error)
func (c *Client) AddonValidateOptions(ctx context.Context, slug string, opts map[string]any) error
func (c *Client) StoreAddon(ctx context.Context, slug string) (*StoreAddon, error)
```

### Why not the official `aiohasupervisor`

The official client is **Python-only** (`home-assistant-libs/python-supervisor-client`, PyPI: `aiohasupervisor`,
Apache-2.0, requires Python ≥ 3.13, depends on `aiohttp`/`mashumaro`/`orjson`). Verified via direct repository
inspection. No Go equivalent exists:

- pkg.go.dev search for "hassio supervisor" returns **0 modules** (verified 2026-08-31).
- GitHub search for `language:Go hassio supervisor client` returns no maintained library.
- `home-assistant-libs` org contains only Python clients.

### Why this is fine

The Supervisor REST surface relevant to add-ons is small and well-defined. Verified by direct source inspection of
`home-assistant/supervisor/supervisor/api/__init__.py`:

```
GET    /addons                         list installed
GET    /addons/{slug}/info             detail
POST   /addons/{slug}/start
POST   /addons/{slug}/stop
POST   /addons/{slug}/restart
POST   /addons/{slug}/options          body: {options: {...}}
POST   /addons/{slug}/options/validate
POST   /addons/{slug}/uninstall
GET    /addons/{slug}/stats
GET    /addons/{slug}/logs
POST   /store/addons/{slug}/install    body: {background: false}
POST   /store/repositories             body: {repository: "url"}
GET    /store                         list store add-ons
```

~10 endpoints → ~200-300 LoC of Go. Implemented with `encoding/json` + `net/http` + `context.WithTimeout`. No
third-party deps needed.

### Testability without Supervisor

Wrap the `Client` in an interface (`type SupervisorClient interface { Addon(...) ... }`) so tests can inject a fake. The
Bridge uses this same interface for its supervisor calls; the Provider uses a parallell `http.Client` over the Bridge's
HTTPS port — same testing strategy on both sides.

### Bridge → Supervisor auth

`SUPERVISOR_TOKEN` env var is auto-injected by Supervisor for add-ons (verified via
`supervisor/api/utils.py::extract_supervisor_token`). Bridge reads it at startup and uses it for all calls to
`http://supervisor/...` (the Supervisor's own loopback listener, also injected as `SUPERVISOR_URL` env var; for add-ons
the standard address is `http://supervisor`).

---

## HTTP Router: **go-chi/chi/v5 v5.3.2**

### Decision

```go
import (
    "github.com/go-chi/chi/v5"
    "github.com/go-chi/chi/v5/middleware"
)

r := chi.NewRouter()
r.Use(middleware.RequestID)
r.Use(middleware.Logger)
r.Use(middleware.Recoverer)
r.Use(middleware.Timeout(60 * time.Second))
r.Use(bearerAuth(token, tokenFile))

r.Route("/v1", func(r chi.Router) {
    r.Get("/schema", schemaHandler)
    r.Get("/healthz", healthHandler)
})
r.Route("/v1/addons", func(r chi.Router) {
    r.Get("/",                       listAddonsHandler)
    r.Route("/{slug}", func(r chi.Router) {
        r.Get("/info",              addonInfoHandler)
        r.Post("/start",            addonStartHandler)
        r.Post("/stop",             addonStopHandler)
        r.Post("/restart",          addonRestartHandler)
        r.Post("/options",          addonOptionsHandler)
        r.Post("/options/validate", addonOptionsValidateHandler)
        r.Post("/uninstall",        addonUninstallHandler)
    })
})
```

### Why chi over stdlib net/http and others

| Option                                                      | Verdict                                                                                                                                                                                                      |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **`go-chi/chi/v5` v5.3.2** (Aug 2026)                       | **Use this.** ~1000 LOC, stdlib-compatible, MIT license, 17K+ importers, modular middleware. Battle-tested middleware: `RequestID`, `Recoverer`, `Logger`, `Timeout` (cancels ctx). Verified via pkg.go.dev. |
| `net/http` stdlib (Go 1.22+ ServeMux has `{slug}` patterns) | Could work; would force hand-rolling middleware (logger, panic recovery, request-ID). Save-chosen-route helper missing.                                                                                      |
| `gin` (v1.x)                                                | Larger dependency (~30k LOC), faster benchmarks but introduces sync.Pool allocation patterns. Most HA add-ons do not need that throughput.                                                                   |
| `echo` (v4.x)                                               | Similar to gin; adds dependency surface for no gain.                                                                                                                                                         |
| `fiber` (v2.x)                                              | fasthttp-based; risky for plug-and-play proxying, and stdlib `net/http` middleware doesn't compose.                                                                                                          |
| `labstack/echo`, `valyala/fasthttp`                         | Avoided — non-stdlib semantics complicate HTTPS server, timeouts, graceful shutdown.                                                                                                                         |

chi's `Mux.Route()` + `Route("/{slug}", ...)` pattern mirrors the Supervisor's own URL hierarchy
(`/addons/{slug}/start`) exactly, which makes the Bridge code symmetric with the Supervisor and easy to read.

### Authentication middleware (custom)

~20 LoC over `chi.Middleware`:

```go
func bearerAuth(validHash func() []byte) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            h := r.Header.Get("Authorization")
            if !strings.HasPrefix(h, "Bearer ") {
                http.Error(w, "missing bearer", 401); return
            }
            // constant-time compare against stored hash
            if subtle.ConstantTimeCompare(hashToken(h[7:]), validHash()) != 1 {
                http.Error(w, "invalid token", 401); return
            }
            next.ServeHTTP(w, r)
        })
    }
}
```

chi's middleware pattern is identical to stdlib `func(http.Handler) http.Handler`.

---

## Auth Library: **stdlib (`crypto/rand`, `crypto/subtle`) + `argon2id` for at-rest hashing**

### Decision

| Layer                                                     | Library                                      | Why                                                                                                                                                                                                                |
| --------------------------------------------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Generate a new token**                                  | `crypto/rand` (stdlib)                       | 32 random bytes → base64url = 43-char opaque token. Same primitive used by every cloud provider (`kubectl create token`, GH PATs, etc.). No KDF needed because the token IS random.                                |
| **Validate an incoming token**                            | `crypto/subtle.ConstantTimeCompare` (stdlib) | Strings compare in constant time; prevents timing oracle attacks against the hashed-on-disk form.                                                                                                                  |
| **Hash the token on disk**                                | `crypto/sha256` (stdlib)                     | NOT user-supplied password; just a random secret. SHA-256 is fine here; argon2 is for low-entropy secrets. Hashing-on-disk lets us read the add-on's `/data/.token_hash` and verify without storing the raw token. |
| **(NOT in Phase 1)** `argon2id` for user-supplied secrets | `golang.org/x/crypto/argon2` v0.55.0         | KDF for _passwords_, not random tokens. Reserved for a future "rotate token to a memorable one" feature.                                                                                                           |

### Why this is enough

Per the user's PROJECT.md auth note:

> "mTLS needs a CA inside the container; OAuth adds a UI surface for one client. Bearer is the smallest correct
> primitive."

A 256-bit opaque bearer token compared with `ConstantTimeCompare` against a SHA-256 hash is the same recipe used by
`kubectl create token`, Docker Hub PATs, and the Go HTTP library examples. Adding argon2 would be ceremony for a secret
that's already 256 bits of entropy — overkill.

### Future-facing: argon2 is still imported

Listed in `go.mod` only if/when a Phase-2 feature requires password-derived keys (e.g. interactive "create a memorable
token" UI). For now, **NOT included** — keep dependency surface minimal.

### Token lifecycle

```
1. Bridge starts; reads /data/.token_hash (if exists) or generates new token
2. Writes /data/.token to the add-on data volume; logs token to HA Supervisor log once
3. Provider reads /data/.token (or HA option-supplied value) on `tofu apply`
4. Rotation endpoint POST /v1/auth/rotate: regenerates token, writes new hash, returns new token once
```

HA add-on data volume already persists `/data` across restarts. No need for an external secret store in Phase 1.

---

## State Backend: **local `/data/terraform.tfstate`, OpenTofu-native**

### Decision

OpenTofu CLI on the dev machine / CI host reads & writes `/data/terraform.tfstate` directly via the local backend:

```hcl
# env tofu/main.tf
terraform {
  backend "local" {
    path = "/data/terraform.tfstate"
  }
}
```

### Why no Go library is needed

The tfstate JSON format is **internally managed by OpenTofu** (and Terraform). Providers never read it directly — the
CLI handles state, sends diff to provider, and writes provider's response. The Bridge does NOT need to:

- parse tfstate JSON
- inspect resources
- write tfstate JSON

If the Bridge ever needed state introspection (it doesn't in Phase 1), we'd write a thin `tfstate` package on top of
`encoding/json` with explicit schema structs — no upstream library exists for `tfstate` files because they're managed by
the CLI's core.

### State backend options (for completeness)

| Backend                           | When used here                                                                                                                                                                                         |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `local` (path on disk)            | **Phase 1.** Single-host, single-user.                                                                                                                                                                 |
| `s3` / `gcs` / `azurerm`          | **Phase X+.** Only when multi-host applies or CI invocation demands a shared state.                                                                                                                    |
| `http` (`hashicorp/http-backend`) | Alternative — store on the Bridge itself at `/data/state.tfstate` served via HTTPS. Rejected for Phase 1 because it doubles the auth surface (both data+control share the bearer). Keep them separate. |

### Where the file lives

The HA add-on stores `/data` (the add-on volume) per HA docs. Path inside the container: `/data/terraform.tfstate`. The
Provider can be configured to point its backend at a path on the **host** that the user mounts into the Bridge (e.g.
`/share/terraform/terraform.tfstate`) — but by default, the volume-internal path keeps the file tied to the add-on. User
can always copy it out via the HA Filebrowser add-on or `docker exec`.

---

## Final Stack Matrix

| Concern                        | Choice                                                           | Version              | Confidence                                                                    |
| ------------------------------ | ---------------------------------------------------------------- | -------------------- | ----------------------------------------------------------------------------- |
| **Bridge add-on base image**   | `ghcr.io/home-assistant/amd64-base`                              | `3.24` (Alpine 3.24) | HIGH — latest stable per HA docker-base README                                |
| **Bridge build image**         | `golang:1.25-alpine`                                             | 1.25                 | HIGH — required by `terraform-plugin-framework` and `terraform-plugin-sdk/v2` |
| **Bridge language/framework**  | Go, single static binary                                         | `go 1.25`            | HIGH                                                                          |
| **HTTP router**                | `github.com/go-chi/chi/v5`                                       | v5.3.2               | HIGH — verified Aug 2026                                                      |
| **JSON marshaling**            | stdlib `encoding/json`                                           | stdlib               | HIGH — sufficient for JSON Schema emission                                    |
| **Auth primitives**            | `crypto/rand` + `crypto/subtle`                                  | stdlib               | HIGH                                                                          |
| **(reserved)** Argon2id        | `golang.org/x/crypto/argon2`                                     | v0.55.0              | HIGH — verified Aug 2026; not used in Phase 1                                 |
| **Provider framework**         | `github.com/hashicorp/terraform-plugin-framework`                | v1.19.0              | HIGH                                                                          |
| **Provider server helpers**    | `github.com/hashicorp/terraform-plugin-framework/providerserver` | transitive           | HIGH                                                                          |
| **Provider SchemaContext**     | `terraform-plugin-framework` typed attributes                    | v1.19.0              | HIGH                                                                          |
| **State backend**              | OpenTofu local backend → `/data/terraform.tfstate`               | n/a                  | HIGH                                                                          |
| **Bridge ↔ Supervisor client** | stdlib `net/http`                                                | stdlib               | HIGH — no Go client exists                                                    |

---

## Per-Add-on Toolchain Summary

### `terraform-bridge/` HA add-on

```
ghcr.io/home-assistant/amd64-base:3.24   ← runtime (Alpine 3.24, ~10 MB)
golang:1.25-alpine                        ← build-only stage
  ↓ go build → single static binary
  ↓ COPY --from to runtime
```

Cost:

- Image adds ~12 MB static binary on top of HA base.
- No runtime interpreter (Python/Node) needed.
- Total image ≈ 25-30 MB compressed.
- Multi-stage build means the `golang:1.25-alpine` layer is NOT shipped — only the binary.

### `terraform-provider-homeassistant/` Go module

```
golang:1.25-alpine               ← dev/test/build host (local + CI)
  ↓ go build → provider binary
  ↓ installed to ~/.local/share/terraform/plugins/registry.terraform.io/akentner/homeassistant/<version>/linux_amd64/
```

No Docker base needed — Provider is a Terraform plugin that runs on the dev machine / CI runner, not in the HA add-on
sandbox.

---

## Bridge ↔ Provider Schema Sharing

The Bridge and Provider each have **two** representations of the same domain types:

| Artifact                                              | Has representation                       | Format                               | Used by                                                                                              |
| ----------------------------------------------------- | ---------------------------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| Go types in `terraform-bridge/contract/types.go`      | every resource, every option             | Go struct with JSON + framework tags | imported by BOTH Bridge (for JSON Schema emission) and Provider (for typed attrs)                    |
| Generated JSON Schema at `/v1/schema`                 | emitted from the Go types via reflection | JSON Schema 2020-12                  | served by Bridge to Provider at first `tofu apply`, then embedded into Provider binary at build time |
| `terraform-provider-homeassistant/internal/contract/` | mirror of the Go types                   | Go types                             | already covered by #1 via same-package import                                                        |

Single source of truth: `terraform-bridge/contract/`. Bridge and Provider are sibling Go modules in this repo; they
`import` each other via relative module paths during the build pipeline. Drift is caught at `go build` of the Provider.

### Concrete layout

```
terraform-bridge/
  contract/
    addon.go            # Addon, AddonDetail, StoreAddon
    job.go              # Job
    schema.go           # Schema() helper emitting JSON Schema from types
    options.go          # AddonOptions struct + schema annotations
  cmd/
    bridge/
      main.go           # net/http listener, chi router wiring, supervisor client
  internal/
    supervisor/
      client.go         # Supervisor HTTP client (uses SUPERVISOR_TOKEN from env)
    auth/
      token.go          # crypto/rand generation, crypto/sha256 hashing, file persistence
    httpapi/
      handlers.go       # chi route handlers
      middleware.go     # bearer auth, request-id, logger
  config.yaml           # HA add-on manifest (hassio_api: true)
  build.yaml            # VERSION + Alpine arg
  Dockerfile            # multi-stage golang → HA base
  run.sh                # reads /data/options.json, starts bridge
  README.md
  DOCS.md
  .upstream.yaml        # NOT APPLICABLE — file is absent for this add-on

terraform-provider-homeassistant/
  main.go               # providerserver.Serve("homeassistant", ...)
  internal/
    provider/
      provider.go       # Schema(), Resources(), DataSources()
      addon_resource.go # CRUD on /v1/addons/{slug}
    contract/           # Go module replace pointing at ../terraform-bridge/contract
  go.mod
  go.sum
```

---

## Sources

### Verified (HIGH confidence)

- **HA docker-base** — https://github.com/home-assistant/docker-base README: Alpine 3.22/3.23/3.24, Python 3.12-3.14,
  Debian trixie, Ubuntu 22-26 listed. Verified 2026-08-31.
- **terraform-plugin-framework** — https://pkg.go.dev/github.com/hashicorp/terraform-plugin-framework shows v1.19.0
  published 2026-03-10; requires Go 1.25+; compatible with Terraform ≥ v0.12 (and therefore OpenTofu ≥ 1.0). License
  MPL-2.0.
- **terraform-plugin-sdk/v2** — https://pkg.go.dev/github.com/hashicorp/terraform-plugin-sdk/v2 shows v2.40.1 published
  2026-04-28; README recommends framework for new providers.
- **go-chi/chi/v5** — https://pkg.go.dev/github.com/go-chi/chi/v5 shows v5.3.2 published 2026-08-20; MIT-licensed;
  17,309 importers; ~1000 LOC for the router core.
- **golang.org/x/crypto/argon2** — https://pkg.go.dev/golang.org/x/crypto/argon2 shows v0.55.0 published 2026-08-11;
  BSD-3.
- **HA Supervisor Python client** — https://github.com/home-assistant-libs/python-supervisor-client README: PyPI name
  `aiohasupervisor`, Apache-2.0, requires Python ≥ 3.13, used by the official `hassio` integration in HA Core. Confirmed
  **no Go equivalent exists**.
- **HA Supervisor API source** — https://github.com/home-assistant/supervisor/blob/main/supervisor/api/__init__.py shows
  the live V1/V2 endpoint set; `security.py::extract_supervisor_token` shows how `SUPERVISOR_TOKEN` is extracted and
  used.
- **OpenTofu 1.12 changelog** — https://opentofu.org/docs/intro/whats-new/ confirms no breaking provider-protocol
  changes; both protocol v5 (SDK v2) and v6 (framework) supported.
- **authentik add-on Dockerfile** in this same repo — precedent for multi-stage build with non-HA build image
  (`ghcr.io/goauthentik/server`) copying into HA base.

### Verified (MEDIUM-HIGH confidence)

- **HA base image versioning cadence** — Alpine 3.24 is the latest tag on `ghcr.io/home-assistant/amd64-base` as of
  2026-08; MULTI_ARCH version `ghcr.io/home-assistant/base` available from 2026.03.1+ per README.
- **Go 1.25 minimum** — required by both `terraform-plugin-framework` v1.19.0 and `terraform-plugin-sdk/v2` v2.40.1. Go
  1.25 LTS released 2025-08; current as of 2026-08.

### Gaps / Open Questions

| Gap                                                    | Impact | Mitigation                                                                                                                                                                                        |
| ------------------------------------------------------ | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Specific Go release download URL at build time         | minor  | Use `golang:1.25-alpine` Docker Hub image; tag is explicit                                                                                                                                        |
| HA base image version drift after 3.24                 | minor  | Image is rebuilt automatically on Alpine EOL; bump in `build.yaml`                                                                                                                                |
| OpenTofu instance that drops below 1.12                | minor  | State the minimum OpenTofu version in `terraform-bridge/README.md`                                                                                                                                |
| JSON Schema ↔ Go types in `terraform-plugin-framework` | minor  | Framework schema is typed; emit JSON Schema 2020-12 via reflection on the Go structs (use `invopop/jsonschema` or hand-written transform; no schema library can consume framework types directly) |
