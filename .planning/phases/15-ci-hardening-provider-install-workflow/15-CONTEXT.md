# Phase 15: CI Hardening + Provider Install Workflow - Context

**Gathered:** 2026-09-05 **Status:** Complete (executed in prior session, captures decisions as audit trail)
**Milestone:** v1.3 opentofu-bridge

> **Audit-trail note.** Phase 15 was executed in a prior session (orphaned commits `5d7027b`, `04b7557`, `22e614f`,
> `12256e3`, `1e214d8`, `e07f60c`, `339456a`, `2226a00` exist in git's object DB but are NOT reachable from current
> `main` HEAD `56ba9fd`). The on-disk state reflects subsequent Phase 11 evolution of the `/v1/version` handler. This
> CONTEXT.md documents the decisions that were locked in the executed plans so future audits can reconstruct what was
> intended, what shipped, and what has since evolved.

<domain>

## Phase Boundary

The Bridge add-on and the Provider source are both built and tested by GitHub Actions on every push;
`make install-provider` is verified end-to-end in CI; the three-file versioning scheme is enforced across both artifacts
in a single release cycle.

Specifically this phase delivers:

- `.github/workflows/build-terraform-bridge.yml` builds the multi-stage Bridge image on push to `main` touching
  `terraform-bridge/**`; every job carries an explicit `timeout-minutes` (per Phase-8 pattern); image is pushed to
  `ghcr.io/akentner/homeassistant-addons/terraform-bridge`.
- `.github/workflows/test-terraform-provider.yml` runs `go test ./...`, `go vet ./...`, and `gofmt -l` against the
  Provider source on push to `main` touching `terraform-provider-homeassistant/**`; job has explicit `timeout-minutes`.
- CI verifies `make install-provider` end-to-end: builds the Provider, installs it to a temporary plugins directory,
  starts an ephemeral test Bridge fixture, runs `tofu init/plan` against it, and confirms the schema-version handshake
  succeeds — proving the install workflow is not broken by a future Provider release.
- Pushing the `<addon>/v<version>` git tag triggers both Bridge build and Provider test workflows; pre-commit
  `validate-versions.sh` blocks commits where Bridge `build.yaml` and Provider `build.yaml` versions drift; the existing
  pre-push hook (`internal/check-version-tags.sh`) extends cleanly to cover the new add-on.

**What this phase is NOT:** Bridge read/write API surface (Phases 11/12), Provider schema + resources (Phase 13),
real-HA empirical verification (Phase 14), `homeassistant_addon_repository` resource (v1.4 deferred), aarch64
cross-compile (post-v1.3 deferred), multi-arch builds, golangci-lint (Phase 8 deferred to v1.4). Phase 15 gates releases
on CI; it does not change application behavior.

</domain>

<decisions>

## Implementation Decisions

### Makefile install-provider target (Area 1 — from Plan 15-01)

- **D-01:** `make install-provider` builds `terraform-provider-homeassistant` from local source and installs the binary
  to `${DESTDIR}${HOME}/.terraform.d/plugins/localhost/akentner/homeassistant/<version>/` so OpenTofu discovers it via
  `dev_overrides`. The `<version>` directory IS required (TOFU-04 wording honors it, even though `dev_overrides` would
  tolerate its absence). The dev_overrides host segment is conventionally `localhost`; any value works. —
  **Reversibility:** `reversible` — local Makefile change.
- **D-02:** `make install-provider DESTDIR=/tmp/foo` MUST honor the override so the same target is reusable inside CI
  without touching the host `~/.terraform.d`. The destination path is `$(DESTDIR)$(HOME)/.terraform.d/...` (NOT
  `${DESTDIR}${HOME}`); `mkdir -p` collapses the resulting double-slash. On a non-root CI runner, `DESTDIR` with empty
  `$HOME` produces `/tmp/foo//home/runner/.terraform.d/...` — this is intentional, the shell verifier (D-05) handles
  both layouts via `find`. — **Reversibility:** `reversible`.
- **D-03:** Version is read from `terraform-provider-homeassistant/build.yaml` at invocation time using the
  whitespace-tolerant regex `^[[:space:]]*VERSION:` (mirrors `internal/validate-versions.sh:114`). Do NOT switch to
  `^VERSION:` — the existing validation tolerates leading whitespace. — **Reversibility:** `costly` — switching regexes
  would touch the verifiers and break consistency with `validate-versions.sh`.
- **D-04:** The target emits a `dev_overrides { "akentner/homeassistant" = "<path>" }` CLI config snippet for the user,
  with a printed hint that `dev_overrides` is supported by OpenTofu >= 1.6 and does NOT work with `terraform init`
  against the registry. — **Reversibility:** `reversible`.
- **D-05:** `make install-provider` fails fast (exit non-zero) if `terraform-provider-homeassistant/build.yaml` is
  missing, the Provider source fails to compile, or the destination directory cannot be created. Failure modes are loud;
  partial installs do not silently succeed. — **Reversibility:** `reversible`.
- **D-06:** `verify-install-provider` wraps the shell verifier (Plan 02). The wrapper target exists alongside Plan 01
  even though the verifier script is added in Plan 02; the wrapper is exercised end-to-end when Plan 02 finalizes. —
  **Reversibility:** `reversible`.
- **D-07:** Plan 01 deviation: the verify command in the plan asserts the binary lands at `$TMP/root/.terraform.d/...`
  (root-runner perspective). As `akentner`, `$HOME` is `/home/akentner`, so the binary actually lands at
  `$TMP/home/akentner/.terraform.d/...`. The Makefile target is correct (uses `$(HOME)` literally); the shell verifier
  (Plan 02) uses `find` against the documented suffix and handles both layouts. Not a functional bug — just a
  verify-command path mismatch. — **Reversibility:** `reversible`.

### Bridge build workflow (Area 2 — from Plan 15-02 Task 1)

- **D-08:** `.github/workflows/build-terraform-bridge.yml` is a thin wrapper calling `_build-template.yml` with
  `addon-name: terraform-bridge`. It mirrors `build-meridian.yml` line-by-line for `permissions:`, `secrets:`, and
  `workflow_dispatch`. The wrapper inherits `timeout-minutes: 45` from `_build-template.yml:56` (Phase 8 already added
  it). Do NOT redeclare `timeout-minutes` in the wrapper — the reusable workflow's value applies. — **Reversibility:**
  `reversible`.
- **D-09:** `tags: [terraform-bridge/v*]` is UNCOMMENTED and ACTIVE in `build-terraform-bridge.yml`. Unlike other
  per-addon workflows (e.g., `build-meridian.yml`) where tag lines are commented, Bridge releases are tag-gated per
  TOFU-05 (`internal/validate-versions.sh:104-124` enforces Bridge/Provider version sync;
  `make update-version ADDON=terraform-bridge VERSION=X.Y.Z` creates the `terraform-provider-homeassistant/vX.Y.Z` tag
  via `internal/update-version.py`). — **Reversibility:** `costly` — re-commenting the tag trigger would require also
  reverting TOFU-05.
- **D-10:** `archs: '["amd64"]'` (single arch) is correct for v1.3: Phase 9 only scaffolded the Bridge for amd64; the
  multi-stage `golang:1.25-alpine` → `ghcr.io/home-assistant/amd64-base:3.24` build has not been cross-compiled. Do NOT
  widen to `["amd64", "aarch64"]` until aarch64 cross-compile lands post-v1.3. — **Reversibility:** `reversible`.
- **D-11:** `secrets:` block (HA_BASE_URL, HA_WEBHOOK_ID, CF_ACCESS_CLIENT_ID, CF_ACCESS_CLIENT_SECRET) is passed
  verbatim even if the secrets are unset. The reusable workflow's `if: ${{ inputs.notify-ha && env.HA_BASE_URL != '' }}`
  (template line 110) skips the HA-notify steps when the secret is empty, so passing an unset secret is harmless. —
  **Reversibility:** `reversible`.

### Provider test workflow (Area 3 — from Plan 15-02 Task 2)

- **D-12:** `.github/workflows/test-terraform-provider.yml` is a standalone Go CI workflow (the Provider is not an HA
  add-on, so `_build-template.yml` is not used). Single `test:` job runs `gofmt -l .` / `go vet ./...` / `go test ./...`
  against `terraform-provider-homeassistant/`. — **Reversibility:** `reversible`.
- **D-13:** The single `test:` job has `timeout-minutes: 10` at 4-space indentation. Sized for a clean Go module cache +
  cold `go test -count=1 ./...` of the full module (Provider is ~5000 LOC including indirect deps; gofmt/vet/test finish
  in seconds on a warm cache). — **Reversibility:** `reversible`.
- **D-14:** Job-level `defaults.run.working-directory: terraform-provider-homeassistant` keeps the three step commands
  flat. `cache-dependency-path: terraform-provider-homeassistant/go.sum` is required because the workflow runs from repo
  root. — **Reversibility:** `reversible`.
- **D-15:** `tags: [terraform-provider-homeassistant/v*]` is UNCOMMENTED. A tagged Provider release implies a new binary
  that downstream consumers will pick up; the test gate ensures the tag was not pushed without `gofmt`/`vet`/`test`
  passing. — **Reversibility:** `costly` — re-commenting would weaken the release gate.
- **D-16:** Do NOT add a `-race` flag — the Provider is a single-process plugin, race detection adds 2-5x runtime for no
  benefit. Do NOT add a `golangci-lint` step — Phase 8 deferred that to v1.4 (PROJECT.md §"Deferred"); adding it here
  would force a new linter config that Phase 8 deliberately deferred. — **Reversibility:** `reversible`.

### Hermetic install-provider verifier (Area 4 — from Plan 15-02 Task 3)

- **D-17:** `internal/verify-install-provider.sh` exists as a hermetic shell verifier (executable, `set -euo pipefail`,
  RED/GREEN/YELLOW color codes, BASH_SOURCE-based repo-root resolution, `mktemp -d` + `trap EXIT` cleanup). Calls
  `make install-provider DESTDIR="$TMP/"`, locates the binary via `find` at
  `*plugins/localhost/akentner/homeassistant/<version>/terraform-provider-homeassistant`, asserts executable +
  non-empty, runs `$BINARY -version` as a tolerated bonus signal (Phase 9 stub does not wire `-version`). —
  **Reversibility:** `reversible`.
- **D-18:** `set -euo pipefail` (stricter than `verify-bridge-scaffold.sh`'s `set -e` — pipefail matters here). The
  `-version` flag check is deliberately tolerant (non-zero exit downgraded to warning, not failure). The strict
  requirement is "binary exists, is executable, and is non-empty". — **Reversibility:** `reversible`.

### GET /v1/version handler + fixture (Area 5 — from Plan 15-03 Tasks 1-2)

- **D-19:** `terraform-bridge/internal/httpapi/handlers/version.go` exposes
  `func Version(bridgeVersion string) http.HandlerFunc` (originally `NewVersionHandler` in Plan 03's first draft; Phase
  11 renamed to `Version` and added `SchemaVersion`, `MinProviderVersion`, `MaxProviderVersion` fields). Returns
  `contract.VersionHandshake{...}` JSON with the compile-time `bridgeVersion`. Mounted at the chi mux top level
  (alongside `/` and `/healthz`) rather than under the `auth.RequireBearer` subroute — the PROV-03 handshake happens
  BEFORE any token issuance, so the endpoint MUST be unauthenticated. — **Reversibility:** `one-way` — published
  contract; changing the JSON shape or auth posture would break Provider clients.
- **D-20:** Reuse existing `terraform-bridge/contract.VersionHandshake` (root-level package, NOT `internal/contract/` as
  Plan 03's read-first mistakenly referenced). The struct is already fully declared with `BridgeVersion` +
  `SchemaVersion` + `MinProviderVersion` + `MaxProviderVersion`. All other handlers (healthz, whoami, auth_rotate)
  import `terraform-bridge/contract` from the root path; creating a duplicate at `internal/contract/` would produce two
  `VersionHandshake` types in two packages. — **Reversibility:** `costly` — touch every handler that imports the
  contract.
- **D-21:** `tools/test-bridge-fixture/` is a STANDALONE Go module (`module test-bridge-fixture`, `go 1.25`, NO
  `require` block). This is critical: `terraform-provider-homeassistant/go.mod` has
  `replace terraform-bridge => ../terraform-bridge` (line 33), so if the fixture were inside the Bridge module, the
  Provider's `go test` would pull in the fixture. Keeping the fixture in its own module preserves the Provider's
  hermetic test surface. — **Reversibility:** `one-way` — moving the fixture into a parent module would change which
  packages are tested.
- **D-22:** The fixture uses ONLY stdlib (`net/http`, `encoding/json`, `flag`, `log`, `os`, `path/filepath`, `strings`)
  — no chi, no terraform-plugin-framework. Reads `terraform-bridge/build.yaml` VERSION at startup via `strings.Split` +
  `strings.HasPrefix(line, "VERSION: ")` + `strings.Trim`. Listens on `127.0.0.1:<port>` where `<port>` is configurable
  via `--port` flag (default 18224); `--repo-root` flag controls the path to `terraform-bridge/build.yaml` (default
  `..`). — **Reversibility:** `reversible`.
- **D-23:** Plan 03 deviation: the workflow passes `--repo-root "$GITHUB_WORKSPACE"` to the fixture invocation (not the
  default `..`). The default `..` only resolves correctly when the binary is invoked from inside its own directory; the
  workflow invokes it from the repo root. Without this flag, the fixture would try to read
  `tools/terraform-bridge/build.yaml` (nonexistent). — **Reversibility:** `reversible`.
- **D-24:** Plan 03 deviation: the fixture uses stdlib `strings.Split`/`Trim`/`HasPrefix` instead of the plan's verbatim
  `splitLines`/`trim`/`contains` custom helpers. The plan itself acknowledged the verbatim `<action>` block contained a
  duplicated `if` line and noted the stdlib version is the right fix. ~25 fewer lines, same parsing semantics. —
  **Reversibility:** `reversible`.

### E2E CI verification workflow (Area 6 — from Plan 15-03 Task 3)

- **D-25:** `.github/workflows/test-install-provider.yml` runs the full TOFU-04 install workflow on push to main: builds
  the Provider, installs to a temp DESTDIR, starts an ephemeral test Bridge fixture, runs `tofu init/plan`, and confirms
  the schema-version handshake succeeds. Single `test-install-provider:` job with `timeout-minutes: 15` (build +
  install + fixture start + tofu init + tofu plan + teardown; measured ~20s for build/install/fixture, ~10s for tofu
  init + plan cold cache). — **Reversibility:** `reversible`.
- **D-26:** The workflow installs OpenTofu via `opentofu/setup-opentofu@v1` with `opentofu-version: '~> 1.6'`
  (community-maintained action; hashicorp/setup-tofu does not exist). Sets up Go via `actions/setup-go@v6` with
  `go-version: '1.25'`. — **Reversibility:** `reversible`.
- **D-27:** The fixture is started as a background process inside a single step (using `&` and capturing the PID into
  `$GITHUB_ENV`). The follow-up step polls `/v1/version` for readiness (`for i in $(seq 1 30); do curl ...; done`). The
  cleanup step (`if: always()`) kills the fixture PID before exit. — **Reversibility:** `reversible`.
- **D-28:** The `paths:` trigger is intentionally BROAD: any change to the Makefile, this workflow, the fixture, the
  Provider source, the Bridge `/v1/version` handler, the Bridge contract types, or the planning docs re-runs the E2E.
  This is the safety net — the E2E catches a class of regressions that no individual unit test can. — **Reversibility:**
  `reversible`.
- **D-29:** The workflow does NOT tag-trigger — `workflow_dispatch` is enough for manual re-runs. Tag pushes to
  `terraform-provider-homeassistant/v*` are already gated by Plan 02's `test-terraform-provider.yml`; this E2E is a
  superset that catches install-level regressions. — **Reversibility:** `reversible`.
- **D-30:** Plan 03 deviation: actionlint rejected the workflow as written; three fixes were applied: (a) quoted the
  step name `"Pre-flight: verify install-provider works"` (unquoted `name: Pre-flight: ...` parsed as a YAML mapping
  key); (b) added a dedicated `Export PLUGIN_DEST` step that writes `${{ runner.temp }}/plugins` to `$GITHUB_ENV` (the
  `runner` context is not allowed at job-level `env:`); (c) pre-computed `PLUGIN_DIR` shell variable before the heredoc
  to keep the heredoc line under yamllint's 120-char limit. All three are necessary for actionlint + yamllint
  compliance. — **Reversibility:** `reversible`.

### Version-drift enforcement + pre-push hook coverage (Area 7)

- **D-31:** `internal/validate-versions.sh` blocks Bridge/Provider version drift (TOFU-05, Phase 9 — already shipped and
  committed). `internal/check-version-tags.sh` auto-discovers `terraform-bridge/` and
  `terraform-provider-homeassistant/` via the existing
  `[ -f "$addon_dir/config.yaml" ] && [ -f "$addon_dir/build.yaml" ]` test (lines 36-38). The Provider
  (`terraform-provider-homeassistant/`) has a `build.yaml` but no conventional HA add-on `config.yaml` — its
  `build.yaml` is a single-line VERSION file. The hook treats it as a tag-checked add-on, which is fine: its version tag
  pattern is `terraform-provider-homeassistant/v<version>`, and Plan 02's test workflow triggers on that exact tag. —
  **Reversibility:** `costly` — touches the validation rules.

### Pre-existing bug fix shipped alongside (Area 8)

- **D-32:** Plan 02 deviation: pre-existing YAML parse error in `.pre-commit-config.yaml` line 109 fixed separately
  (Phase 10 regression). The unescaped `:` in `verify-bridge-no-token-leak`'s description
  (`invariants: no SUPERVISOR_TOKEN...`) was a YAML mapping error that blocked `pre-commit validate-config` and
  `make check-all`. This bug was introduced by commit `8ce3035` (Phase 10) and would have blocked Phase 15's acceptance
  criterion regardless. Fix: wrap the description in double quotes. Committed separately as
  `fix(pre-commit): quote ... description (Phase 10 regression)` BEFORE the Phase 15 code commits so the
  pre-commit-config fix is not bundled with feature work. — **Reversibility:** `one-way` — touching
  `.pre-commit-config.yaml` again would require re-validation.

### Carried forward from prior phases (locked, not re-discussed)

- **CF-01:** 3-file versioning scheme (Bridge `config.yaml` X.Y.Z-N, build.yaml X.Y.Z, README badges vX.Y.Z) is enforced
  by `internal/validate-versions.sh` and is not re-discussed in Phase 15. Phase 15 does NOT bump versions — it gates
  releases on CI. (AGENTS.md §"Critical Gotchas #1".)
- **CF-02:** Phase 8's reusable workflow template (`.github/workflows/_build-template.yml`) accepts `addon-name`,
  `addon-display-name`, `addon-description`, `archs` (JSON array). On invocation it yq-extracts `VERSION`,
  `config.yaml version`, `BUILD_FROM.<arch>` from `<addon-name>/{build,config}.yaml`. It pushes to
  `${{ env.IMAGE_BASE }}/${{ matrix.arch }}-${{ steps.slug.outputs.slug }}:${{ steps.meta.outputs.CONFIG_VERSION }}`
  where `IMAGE_BASE` is hardcoded to `ghcr.io/akentner/homeassistant-addons` (template line 151). Phase 15's wrapper
  inherits this template's `timeout-minutes: 45`.
- **CF-03:** Phase 8's per-job `timeout-minutes` pattern is the established CI convention. Phase 9 measured 2m49s for
  amd64 + 13m28s for aarch64 Bridge build legs; 45 minutes per matrix leg absorbs a slow runner. Phase 15's test
  workflows honor this pattern (10 min Provider test, 15 min E2E).
- **CF-04:** `opentofu/setup-opentofu@v1` is the community-maintained action for OpenTofu install.
  `opentofu-version: '~> 1.6'` for range-pinned versions. OpenTofu 1.6+ is required for `dev_overrides` (older Terraform
  ignores it).
- **CF-05:** `dev_overrides` accepts a directory containing the provider binary directly. Binary filename MUST be
  `terraform-provider-<provider>` for dev_overrides. The Provider is built as `terraform-provider-homeassistant`.
- **CF-06:** `make verify-install-provider` is a wrapper around the shell verifier added in Plan 02, so
  `make verify-install-provider` works alongside the other `make verify-*` style targets (`make verify-bridge-scaffold`,
  `make verify-bridge-no-token-leak`).

### the agent's Discretion

- Exact wording of the `dev_overrides { ... }` CLI config snippet printed by `make install-provider` — the `make`
  recipe's `@echo` lines use `\"` escapes for literal `"akentner/homeassistant"`. Format follows the existing
  `update-version` target's user-facing output style.
- Whether `internal/verify-install-provider.sh` enforces a minimum binary size or only checks non-empty — Plan 02 chose
  "non-empty + executable" as the strict requirement; size is informational.
- Whether the test Bridge fixture binds to `127.0.0.1` only (current default) vs `0.0.0.0` (would need `--allow-host`
  flag) — fixture is CI-only and 127.0.0.1 binding is the safe choice.

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase boundary + success criteria (HIGH confidence)

- `.planning/ROADMAP.md` §"Phase 15: CI Hardening + Provider Install Workflow" — the four success criteria (SC-1..SC-4)
  the phase must satisfy; SC-3 is the E2E CI verification gate
- `.planning/REQUIREMENTS.md` §"TOFU — Terraform/OpenTofu" TOFU-04 — the single Phase-15 requirement:
  `make install-provider` installs the Provider binary to
  `~/.terraform.d/plugins/<host>/akentner/homeassistant/<version>/` so OpenTofu discovers it via the dev_overrides
  workflow
- `.planning/REQUIREMENTS.md` §"TOFU — Terraform/OpenTofu" TOFU-05 (Phase 9, locked) — `internal/validate-versions.sh`
  enforces Bridge/Provider build.yaml version sync; Phase 15 SC-4 verifies this

### Executed plans + summaries (HIGH confidence — audit trail source)

- `.planning/phases/15-ci-hardening-provider-install-workflow/15-01-PLAN.md` — `make install-provider` +
  `verify-install-provider` Makefile targets
- `.planning/phases/15-ci-hardening-provider-install-workflow/15-01-SUMMARY.md` — Plan 01 verification + 2 deviations
  (D-06, D-07)
- `.planning/phases/15-ci-hardening-provider-install-workflow/15-02-PLAN.md` — Bridge build workflow + Provider test
  workflow + hermetic verifier
- `.planning/phases/15-ci-hardening-provider-install-workflow/15-02-SUMMARY.md` — Plan 02 verification + 1 deviation
  (D-32)
- `.planning/phases/15-ci-hardening-provider-install-workflow/15-03-PLAN.md` — `/v1/version` handler +
  test-bridge-fixture + E2E CI verification workflow
- `.planning/phases/15-ci-hardening-provider-install-workflow/15-03-SUMMARY.md` — Plan 03 verification + 4 deviations
  (D-23, D-24, D-30)
- `.planning/phases/15-ci-hardening-provider-install-workflow/15-VERIFICATION.md` — phase-level verification report
  (status: passed 2026-08-31)

### Prior phases (locked, not re-discussed)

- `.planning/phases/09-bridge-foundation-token-rotation-spike/09-CONTEXT.md` — Bridge scaffold + multi-stage Go
  Dockerfile + `make update-version` cross-artifact version sync (TOFU-05)
- `.planning/phases/08-ci-cd-hardening/08-01-PLAN.md` — the timeout-minutes pattern Phase 15 follows;
  `_build-template.yml` reusable workflow
- `.planning/phases/11-bridge-read-api/11-CONTEXT.md` — Bridge Read API; subsequently evolved `GET /v1/version` to add
  `SchemaVersion` + `MinProviderVersion` + `MaxProviderVersion` fields (post-Phase-15 evolution; see specifics below)
- `.planning/phases/13-provider-resource-data-sources-schema-handshake/13-CONTEXT.md` — Provider schema handshake via
  `GET /v1/version` (PROV-03); the E2E workflow's `tofu init` validates this handshake

### Existing implementation as templates (HIGH confidence)

- `.github/workflows/_build-template.yml` — Phase 8 reusable workflow; `build-terraform-bridge.yml` is a thin wrapper
  around it. Image base hardcoded `ghcr.io/akentner/homeassistant-addons` (line 151); slug = addon-name with `-` → `_`
  (line 107); yq-extracts `VERSION`, `config.yaml version`, `BUILD_FROM.<arch>` (lines 74-78).
- `.github/workflows/build-meridian.yml` — canonical thin wrapper that calls `_build-template.yml`;
  `build-terraform-bridge.yml` mirrors it line-by-line except for `paths:` and `tags:`.
- `.github/workflows/lint.yml` — the repo's existing lint workflow; closest analogue for `runs-on: ubuntu-latest` +
  Go-less workflow.
- `.planning/codebase/TESTING.md` — `make test` is an alias for `make lint`; the repo has no unit-test framework. Phase
  15 adds no test files.
- `.planning/codebase/CONVENTIONS.md` — 120-char line limit for Markdown; YAML 2-space indent; snake_case option names;
  quoted strings for versions and sensitive values.

### Bridge implementation (HIGH confidence)

- `terraform-bridge/contract/types.go` — `VersionHandshake` struct (root-level package, NOT `internal/contract/` as Plan
  03's read-first mistakenly referenced). All other handlers import `terraform-bridge/contract` from the root path.
- `terraform-bridge/internal/httpapi/handlers/version.go` — the current `/v1/version` handler (rewritten by Phase 11 to
  add `SchemaVersion`, `MinProviderVersion`, `MaxProviderVersion`); Plan 03's `NewVersionHandler` no longer exists.
- `terraform-bridge/internal/httpapi/router.go` — chi router with `/v1/version` mounted at the top level
  (unauthenticated) before the auth subroute.
- `terraform-bridge/cmd/bridge/version.go` — `BridgeVersion` wired via ldflags
  (`-ldflags -X main.bridgeVersion=$VERSION`).
- `terraform-bridge/build.yaml` — `args.VERSION` is the Dockerfile ARG that the Bridge binary embeds;
  `_build-template.yml`'s yq extraction already handles this.

### Provider implementation (HIGH confidence)

- `terraform-provider-homeassistant/build.yaml` — single-line `VERSION: "0.1.0"`. Whitespace-tolerant extraction:
  `grep -E '^[[:space:]]*VERSION:' terraform-provider-homeassistant/build.yaml | sed 's/^[[:space:]]*VERSION: *"\([^"]*\)".*/\1/'`
  (mirrors `internal/validate-versions.sh:114`).
- `terraform-provider-homeassistant/main.go` line 29 — `Address: "registry.terraform.io/akentner/homeassistant"`. The
  Provider's compile-time `Version` constant (line 22) is `const Version = "0.0.0"` in the Phase 9 stub.
- `terraform-provider-homeassistant/go.mod` line 3 — `go 1.25.0`. Line 33 —
  `replace terraform-bridge => ../terraform-bridge`.

### Pre-push hook (HIGH confidence)

- `internal/check-version-tags.sh` line 36-38 — auto-discovers add-ons by
  `[ -f "$addon_dir/config.yaml" ] && [ -f "$addon_dir/build.yaml" ]`. `terraform-bridge/` and
  `terraform-provider-homeassistant/` both have these files.
- `internal/validate-versions.sh` lines 109-124 — whitespace-tolerant `VERSION:` extraction; Phase 9's TOFU-05
  enforcement of Bridge/Provider build.yaml sync.

### Test fixtures (HIGH confidence)

- `tools/test-bridge-fixture/main.go` — stdlib HTTP server; `--port` (default 18224), `--repo-root` (default `..`);
  reads `terraform-bridge/build.yaml` via `strings.HasPrefix(line, "VERSION: ")`; serves
  `{"bridge_version": "<version>"}` on `/v1/version`, 404 elsewhere.
- `tools/test-bridge-fixture/go.mod` — `module test-bridge-fixture`, `go 1.25`, NO `require` block (stdlib only).
- `internal/verify-install-provider.sh` — hermetic verifier; `set -euo pipefail`; uses `find` to locate the binary at
  the documented dev_overrides path component (handles both root and non-root `$HOME` layouts).
- `internal/verify-bridge-no-token-leak.sh` (Phase 10) — structural template for `verify-install-provider.sh`; same
  exit-gate discipline (exits non-zero on assertion failure).

</canonical_refs>

<code_context>

## Existing Code Insights

### Reusable Assets

- `.github/workflows/_build-template.yml` (Phase 8) — reusable workflow that `build-terraform-bridge.yml` wraps. Phase
  15 inherits the per-job `timeout-minutes: 45` and the yq-extraction of `VERSION` / `config.yaml version` /
  `BUILD_FROM.<arch>`.
- `Makefile` (existing) — `update-version` target (lines 173-188) is the closest analogue for a per-addon target that
  reads build.yaml + invokes an `internal/` script. Phase 15's `install-provider` target mirrors this pattern.
- `internal/validate-versions.sh` lines 109-124 — whitespace-tolerant `VERSION:` extraction; both the Makefile target
  and the hermetic verifier reuse the same regex.
- `terraform-bridge/contract.VersionHandshake` — already declared with `BridgeVersion` + `SchemaVersion` +
  `MinProviderVersion` + `MaxProviderVersion`; the test-bridge-fixture emits a subset (only `bridge_version`), the real
  Bridge emits the full struct.
- `terraform-bridge/cmd/bridge/version.go` — compile-time `BridgeVersion` wired via ldflags; the `/v1/version` handler
  reads it via constructor injection.
- `internal/check-version-tags.sh` line 36-38 — auto-discovers `terraform-bridge/` and
  `terraform-provider-homeassistant/` via the existing `[ -f config.yaml ] && [ -f build.yaml ]` test; no hook changes
  needed for Phase 15.
- `internal/verify-bridge-scaffold.sh` + `internal/verify-bridge-no-token-leak.sh` (Phase 10) — structural template for
  `verify-install-provider.sh`'s hermetic shell verifier; same exit-gate discipline.

### Established Patterns

- **Thin wrapper workflow pattern** — established by `build-meridian.yml` and Phase 8's reusable template. The wrapper
  file is ~25 lines (name, `on:`, `jobs.build.uses`, `permissions:`, `with: addon-name`, `secrets:`).
  `build-terraform-bridge.yml` follows this pattern exactly.
- **Standalone Go module for CI test fixtures** — established by `tools/test-bridge-fixture/`. Pattern:
  `tools/<name>/go.mod` with `module <name>` + `go 1.25` and NO `require` block, so the fixture cannot be pulled into
  the Bridge's or Provider's `go test` graph.
- **Background-process pattern with PID capture via `$GITHUB_ENV`** — used by `test-install-provider.yml` for the
  in-workflow fixture daemon. PID is written to env so the cleanup step (`if: always()`) can kill it.
- **Whitespace-tolerant YAML extraction** — `^[[:space:]]*VERSION:` is the repo convention for `build.yaml` parsing.
  Used by `internal/validate-versions.sh`, the Makefile `install-provider` target, and the hermetic verifier.
- **Pre-existing-version contract struct fields stay untouched across phases** — established by
  `contract.VersionHandshake`: new handlers populate only the field(s) they own and the JSON encoder emits the rest as
  empty strings.
- **3-file versioning + cross-artifact sync** — Bridge + Provider share X.Y.Z via `internal/validate-versions.sh`. Phase
  15 does NOT bump versions; it gates releases on CI.

### Integration Points

- **Live Bridge at `:8124`** on the host — not exercised by Phase 15's CI (the fixture substitutes). Phase 15's E2E
  workflow runs the fixture on `127.0.0.1:18224` only.
- **OpenTofu CLI** — installed via `opentofu/setup-opentofu@v1` in the E2E workflow; `tofu init -input=false` +
  `tofu plan -input=false` against a `dev_overrides`-installed Provider.
- **GitHub Actions runners** — `ubuntu-latest` for all Phase 15 workflows. No self-hosted runners, no special hardware.
- **Bridge `internal/version/version.go`** (Phase 11) — `SchemaVersion`, `MinProviderVersion`, `MaxProviderVersion`
  semver constants. The current `/v1/version` handler reads from this package (post-Phase-15 evolution).
- **`make update-version ADDON=terraform-bridge VERSION=X.Y.Z`** — `internal/update-version.py` creates the
  `terraform-bridge/vX.Y.Z` AND `terraform-provider-homeassistant/vX.Y.Z` tags atomically (TOFU-05 enforces the sync).
  The `build-terraform-bridge.yml` and `test-terraform-provider.yml` workflows both trigger on those tags.

</code_context>

<specifics>

## Specific Ideas

- **`/v1/version` is unauthenticated on purpose** — the PROV-03 Provider handshake happens BEFORE any bearer token is
  issued (the Provider has no token until the user runs `tofu init` with a configured bridge_token). Mounting
  `/v1/version` under the auth subroute would create a chicken-and-egg deadlock.
- **Test-bridge-fixture reads Bridge `build.yaml`, not Provider `build.yaml`** — both share the same version via TOFU-05
  (`internal/validate-versions.sh:104-124` enforces sync), so reading the Bridge's is equivalent. The Bridge's
  `build.yaml` is the canonical source.
- **`opentofu/setup-opentofu@v1` is the only viable OpenTofu action** — `hashicorp/setup-tofu` does not exist
  (Terraform's action installs Terraform, not OpenTofu). Community action uses the official OpenTofu release tarball.
- **`make install-provider` uses `$(DESTDIR)$(HOME)` not `${DESTDIR}${HOME}`** — Make variable expansion is
  left-to-right, so `${DESTDIR}${HOME}` would expand `DESTDIR` first then `HOME`, producing the same string but with
  subtle quoting differences. The Makefile uses the `$()` form to match the `update-version` target's pattern.
- **Test Bridge fixture smoke test** — `GET /v1/version` → `{"bridge_version":"0.1.0"}`, `/unknown` → 404. The Plan 02
  verifier tests this locally; Plan 03's E2E workflow validates it in CI.
- **Pre-commit config fix (Phase 10 regression)** is committed separately from feature work per the `fix(pre-commit)`
  convention. This keeps the regression fix auditable in its own commit rather than bundled with Phase 15's features.

### Post-Phase-15 evolution (recorded for audit trail)

- **Phase 11 (`9158869 feat(11-01): GET /v1/info (BRIDGE-10) + GET /v1/version (BRIDGE-01) + planning docs`) rewrote
  `terraform-bridge/internal/httpapi/handlers/version.go`** to add `SchemaVersion`, `MinProviderVersion`,
  `MaxProviderVersion` fields. Plan 03's `NewVersionHandler` was renamed to `Version`. The struct moved from a stub to a
  fully-realized `contract.VersionHandshake` with the four Bridge-reported fields. The fixture continues to emit only
  `bridge_version` (handshake compares that one field today).
- **Phase 11 also added `BRIDGE-01` (`GET /v1/version`) as a Phase 11 deliverable.** Phase 15's Plan 03 had shipped the
  endpoint as a Phase 15 deliverable, but Phase 11's later work superseded the implementation. The on-disk file is now
  Phase 11's version; the Phase 15 commits exist as orphans in git's object DB.
- **The orphaned commits `5d7027b`, `04b7557`, `22e614f`, `12256e3`, `1e214d8`, `e07f60c`, `339456a`, `2226a00` are NOT
  reachable from current `main` HEAD `56ba9fd`.** A future audit may want to either replay them onto main (cherry-pick)
  or rely on the on-disk state (which has already been reconciled with Phase 11+).

</specifics>

<deferred>

## Deferred Ideas

- **aarch64 cross-compile for the Bridge** — out of scope for v1.3. The Bridge's multi-stage `golang:1.25-alpine` →
  `ghcr.io/home-assistant/amd64-base:3.24` build has not been cross-compiled. Post-v1.3 deferral per Plan 15-02 Task 1's
  `D-10`.
- **golangci-lint step in `test-terraform-provider.yml`** — Phase 8 deferred the decision to v1.4 (PROJECT.md
  §"Deferred"). Adding it here would force a new linter config that Phase 8 deliberately deferred. Plan 15-02 Task 2's
  `D-16` records the deliberate omission.
- **Multi-arch Bridge builds** — out of scope for the repo (per PROJECT.md §"Out of Scope"); Phase 15 verifies amd64
  only.
- **`-race` flag on `go test ./...`** — the Provider is a single-process plugin; race detection adds 2-5x runtime for no
  benefit on this codebase. Plan 15-02 Task 2's `D-16`.
- **TLS on the test Bridge fixture** — fixture is HTTP-only, matching the Phase 1 Open Q-7 decision ("plain HTTP on
  Tailscale for Phase 1"). Plan 15-03 Task 2's `D-22` notes the deliberate omission.
- **Pre-existing-version contract struct fields beyond D-20's `VersionHandshake`** — the four-field struct covers the
  current handshake need. If a future phase needs more (e.g., `actor_token_fp`, `grace_expires_at`), it's a struct
  extension deferred to that phase.
- **Tag trigger for `test-install-provider.yml`** — the E2E workflow does NOT tag-trigger (`workflow_dispatch` is
  enough). Tag pushes to `terraform-provider-homeassistant/v*` are already gated by Plan 02's
  `test-terraform-provider.yml`; this E2E is a superset. Plan 15-03 Task 3's `D-29`.
- **Replaying orphaned Phase 15 commits onto current main** — outside Phase 15's scope; the on-disk state already
  reflects the integrated post-Phase-11 evolution. A future cherry-pick or `git rebase --onto` would address this if
  desired.

</deferred>

---

_Phase: 15-ci-hardening-provider-install-workflow_ _Context gathered: 2026-09-05_
