---
phase: 09-bridge-foundation-token-rotation-spike
plan: 02
subsystem: infra
tags: [go, terraform-plugin-framework, version-sync, replace-directive, providerserver]
provides:
  - "terraform-provider-homeassistant/ Go module (terraform-provider-homeassistant; Go 1.25; terraform-plugin-framework
    v1.19.0) compiling against the Bridge via `replace terraform-bridge => ../terraform-bridge`"
  - "Barebones providerserver.Serve() entrypoint that imports contract.VersionHandshake as a package-level `var _` so
    any future drift in shared contract types fails `go build`"
  - "terraform-provider-homeassistant/build.yaml VERSION carrier (Provider has no Docker image / arch list / build_from)"
  - "internal/validate-versions.sh cross-artifact check (TOFU-05): when both Bridge and Provider build.yaml exist, their
    VERSION fields must match exactly"
  - "internal/update-version.py atomic Bridge+Provider bump (TOFU-03): `make update-version ADDON=terraform-bridge
    VERSION=X.Y.Z` updates Bridge config/build/README AND Provider build.yaml in one call; Provider receives no README,
    no config.yaml, no git tag"
affects:
  - "Phase 13 (Provider + Resource + Data + Handshake) — fills in providerserver.Configure(), homeassistant_addon
    resource, and the two data sources without changing directory layout"
  - "Phase 15 (CI + Provider Install Workflow) — uses update-version.py's atomic bump before each tagged release"
  - "All later plans that touch internal/validate-versions.sh or internal/update-version.py"

# Dependency graph
requires:
  - phase: 09-bridge-foundation-token-rotation-spike (plan 01)
    provides: terraform-bridge/ Go module + terraform-bridge/contract/types.go shared types + replace target path
provides:
  - "terraform-provider-homeassistant/{go.mod, go.sum, main.go} — Go 1.25 module with `replace terraform-bridge =>
    ../terraform-bridge`; barebones providerserver.Serve() against stub provider"
  - 'terraform-provider-homeassistant/build.yaml — bare VERSION: "0.2.0" carrier (current sync target with Bridge)'
  - "internal/validate-versions.sh — extended with # ── Cross-artifact Bridge/Provider sync (TOFU-05) block: exits 1
    when the two build.yaml VERSION fields diverge, exits 0 when either file is missing"
  - "internal/update-version.py — extended with Provider-bump branch: when addon_name == 'terraform-bridge', also
    updates terraform-provider-homeassistant/build.yaml's VERSION using the existing update_build_yaml helper"
key-decisions:
  - "Contract package moved from terraform-bridge/internal/contract to terraform-bridge/contract (commit b7e4519): Go's
    internal/ rule blocks any module from importing even with `replace`, so the path is no-internal. Package name
    'contract' is unchanged"
  - "Provider uses providerserver.Serve(ctx, newProvider, providerserver.ServeOpts{Address: ...}) — Address is mandatory
    in v1.19.0; the plan's two-argument form was an older SDK shape"
  - "providerserver.ProviderFunc wrapper does not exist in v1.19.0 — newProvider is passed directly as func()
    provider.Provider"
  - "SchemaRequest is a value type, not a pointer (v1.19.0 API)"
  - "SchemaResponse uses schema.Schema{} with Attributes/Blocks maps, not provider.SchemaType with Resources/DataSources
    maps — the plan's literal block was based on an older SDK shape"
  - "validate-versions.sh anchored its grep to '^[[:space:]]*VERSION:' (same fix Wave 1 applied) because
    terraform-bridge/build.yaml has VERSION: nested under args:"
  - "Provider build.yaml stays intentionally bare (just VERSION) — Provider has no Docker image, no arch list, no
    build_from. Phase 15's CI workflow builds the binary via Go directly"
  - "update-version.py keeps total_files = 3 (Bridge's 3-file bump accounting is unchanged); the Provider bump is
    reported with its own bullet but does not increment the success counter"
  - "If Provider bump fails (permission error, missing field), update-version.py exits 1 BEFORE the git tag is created —
    atomicity guarantees Bridge and Provider can never be left in a tagged-but-divergent state"

# Tech tracking
tech-stack:
  added:
    - "github.com/hashicorp/terraform-plugin-framework v1.19.0 (Provider framework; protocol v6)"
    - "github.com/hashicorp/terraform-plugin-framework-timeouts v0.5.0 (transitive)"
    - "github.com/fatih/color v1.18.0 (transitive)"
  patterns:
    - "Shared-contract-via-replace: Provider's go.mod requires terraform-bridge v0.0.0-00010101000000-000000000000 and
      `replace terraform-bridge => ../terraform-bridge`. The v0.0.0-... placeholder is what Go's tooling emits for a
      replace target"
    - "Barebones stubProvider for Phase 9: provider.Provider embedded in stubProvider{} with empty Schema() returning
      zero-value schema.Schema{}. Phase 13's Configure() and resource registrations attach here without changing the
      package layout"
    - "Conditional cross-artifact check: both `validate-versions.sh` and `update-version.py` guard with `[[ -f ... ]] &&
      [[ -f ... ]]` so pre-Phase-9 repositories that migrate forward without the Provider don't fail pre-commit"

# Metrics
duration: 30min
started: 2026-08-31T14:52:00Z
completed: 2026-08-31T15:05:00Z
tasks: 3
files_modified: 6
commits: 4 (1 refactor + 3 feat)
---

# Phase 9 Plan 2: Provider Scaffold + Bridge/Provider Version Sync

**`terraform-provider-homeassistant/` scaffolds as a Go 1.25 module that compiles against the Bridge via `replace`, plus
`internal/validate-versions.sh` (TOFU-05 cross-artifact check) and `internal/update-version.py` (TOFU-03 atomic bump)
keep the Bridge and Provider on one release cycle in a single `make update-version` invocation.**

## Accomplishments

- **Provider Go module compiles against the Bridge.** `terraform-provider-homeassistant/go.mod` declares
  `module terraform-provider-homeassistant`, `go 1.25.0`, requires `terraform-plugin-framework v1.19.0`,
  `terraform-plugin-framework-timeouts v0.5.0`, and `terraform-bridge v0.0.0-00010101000000-000000000000` with
  `replace terraform-bridge => ../terraform-bridge`. `go build ./...` exits 0; `go vet ./...` exits 0; `go mod tidy` is
  idempotent.
- **Contract package moved out of internal/.** `terraform-bridge/contract/types.go` now lives at the top level of
  terraform-bridge (commit `b7e4519`). Go's internal/ rule blocks any module from importing even with a `replace`
  directive, so this realigns the directory layout with CONTEXT D-03's "exposed as a non-internal package path". No
  Bridge source files import `contract`, so the move has no blast radius inside terraform-bridge/.
- **providerserver.Serve() with stub provider.** `main.go` calls
  `providerserver.Serve(ctx, newProvider, providerserver.ServeOpts{Address: "registry.terraform.io/akentner/homeassistant"})`
  against a `stubProvider` embedding `provider.Provider`. The current Phase-9 stub will be replaced by Phase 13 Plan
  01's real `internal/provider.Provider` implementation; the package layout and the contract drift-detector remain.
- **Contract-drift detector at compile time.** A package-level `var _ contract.VersionHandshake` declaration (originally
  `var _ contract.VersionHandshake`; Phase 13 expanded to `tfprovider.New()` consuming `contract.VersionHandshake`)
  ensures any future shape change in `terraform-bridge/contract/types.go` fails the Provider's `go build`.
- **TOFU-05 cross-artifact check live.** `internal/validate-versions.sh` runs an additional block after the per-addon
  loop. When both `terraform-bridge/build.yaml` and `terraform-provider-homeassistant/build.yaml` exist, the script
  extracts `VERSION:` from each (anchored to `^[[:space:]]*VERSION:` so it matches nested args: indentation) and exits 1
  with a `[TOFU-05] Version mismatch: ...` message on divergence. The check is conditional: if either file is missing,
  pre-Phase-9 repositories are not blocked.
- **TOFU-03 atomic bump live.** `internal/update-version.py` extended with an `if addon_name == "terraform-bridge":`
  branch in `main()` that reuses the existing `update_build_yaml` helper to touch
  `terraform-provider-homeassistant/build.yaml`'s `VERSION:` field with the same X.Y.Z as the Bridge. The Provider bump
  fires AFTER the Bridge's 3-file block but BEFORE the git tag is created, so a failed Provider write exits 1 with no
  tag.
- **No Provider-side tag, README, or config.yaml.** The Provider receives no `<addon>/v<version>` tag (only the Bridge
  does), no `README.md` (the existing `update_readme_md` is never called against the Provider directory), and no
  `config.yaml` (it is not a separate Home Assistant add-on). The Provider is a co-located Go module that follows the
  Bridge's release cycle.
- **Baseline version set to 0.2.0.** Both `terraform-bridge/build.yaml:VERSION` and
  `terraform-provider-homeassistant/build.yaml:VERSION` are at `0.2.0` (the current release target after Phase 13 landed
  its own Provider implementation). `make validate-versions` exits 0 with both files at the same value.

## Task Commits

1. **Task 1 (refactor): move contract package out of internal/** — `b7e4519` (refactor) — 1 file moved
2. **Task 1 (feat): scaffold terraform-provider-homeassistant Go module** — `f527c0e` (feat) — 3 files, 197 insertions
3. **Task 2: cross-artifact version sync in validate-versions.sh + Provider build.yaml** — `c883779` (feat) — 2 files,
   23 insertions
4. **Task 3: atomic Bridge+Provider bump in update-version.py** — `6939e57` (feat) — 1 file modified

## Files Created/Modified

### Created

- **`terraform-provider-homeassistant/go.mod`** (33 lines) — `module terraform-provider-homeassistant`; `go 1.25.0`;
  direct requires for `terraform-plugin-framework v1.19.0` and `terraform-plugin-framework-timeouts v0.5.0`; indirect
  require for `github.com/fatih/color v1.18.0`; placeholder
  `require terraform-bridge v0.0.0-00010101000000-000000000000`; `replace terraform-bridge => ../terraform-bridge`
  block.
- **`terraform-provider-homeassistant/go.sum`** (99 lines) — populated by `go mod tidy` against the framework +
  transitive deps.
- **`terraform-provider-homeassistant/main.go`** (65 lines) — `package main`; `Version = "0.0.0"` constant (Phase 13
  bump);
  `providerserver.Serve(ctx, newProvider, providerserver.ServeOpts{Address: "registry.terraform.io/akentner/homeassistant"})`;
  `newProvider() provider.Provider` factory (Phase 13 returns `tfprovider.New()`).
- **`terraform-provider-homeassistant/build.yaml`** (1 line) — `VERSION: "0.2.0"` carrier. No `build_from`, no `args`,
  no `arch` — the Provider is built by Phase 15's CI workflow via `go build` directly, not the per-addon Docker builder.

### Modified

- **`terraform-bridge/internal/contract/types.go` → `terraform-bridge/contract/types.go`** — directory move, package
  name `contract` unchanged, no source changes (commit `b7e4519`). No terraform-bridge internal package imported the
  contract package, so the move has no blast radius.
- **`internal/validate-versions.sh`** — added a `# ── Cross-artifact Bridge/Provider sync (TOFU-05)` block after the
  per-addon `for` loop (around L100, before the final exit). The block reads `VERSION:` from both build.yaml files
  (anchored to `^[[:space:]]*VERSION:`), appends a `[TOFU-05]` error to `GLOBAL_ERRORS` on mismatch, and the
  pre-existing final exit code propagates correctly. Diff is purely additive — `git diff` shows no removed lines.
- **`internal/update-version.py`** — added the `if addon_name == "terraform-bridge":` branch in `main()` AFTER the
  3-file Bridge block but BEFORE `tag_ok = create_and_push_tag(...)`. Reuses
  `update_build_yaml(provider_dir, new_version, dry_run=args.dry_run)`; reports `Co-located Provider bumped: ...` on
  success; exits 1 on failure to preserve atomicity (no tag is created if the Provider write fails).

## Verification Notes

- `cd terraform-provider-homeassistant && go build ./...` — exits 0.
- `cd terraform-provider-homeassistant && go vet ./...` — exits 0.
- `cd terraform-provider-homeassistant && go mod tidy` — idempotent (no diff on second run).
- `bash internal/validate-versions.sh` — exits 0 with both build.yaml at `0.2.0`.
- `bash internal/validate-versions.sh` after `echo 'VERSION: "0.99.9"' > terraform-provider-homeassistant/build.yaml` —
  exits 1 with `[TOFU-05] Version mismatch: terraform-bridge '0.2.0' != terraform-provider-homeassistant '0.99.9'`
  (verify path exercised at Task 2 commit time; restored to baseline afterwards).
- `./internal/update-version.py terraform-bridge 0.99.9 --dry-run` — prints `Would update` for both files; no writes.
- `./internal/update-version.py terraform-bridge 0.99.9 --no-tag --no-push` — writes Bridge config/build/README +
  Provider build.yaml; Provider receives no README and no tag.
- `make validate-versions` — exits 0.

## Deviations from Plan

- **Plan called for `providerserver.Serve(ctx, providerFunc, opts)`;** v1.19.0 makes `Address` mandatory so the actual
  call signature is `providerserver.Serve(ctx, newProvider, providerserver.ServeOpts{Address: ...})`. This was
  discovered during the Task 1 verify step.
- **Plan called for `providerserver.ProviderFunc` wrapper type;** v1.19.0 has no such wrapper. `newProvider` (a plain
  `func() provider.Provider`) is passed directly.
- **Plan called for `SchemaRequest` pointer and `provider.SchemaType{Resources: ..., DataSources: ...}`;** v1.19.0 uses
  a value-typed `SchemaRequest` and `schema.Schema{}` with `Attributes` / `Blocks` maps. Phase 9 ships an empty
  `Schema()` method returning `provider.SchemaResponse{Schema: schema.Schema{}}`; Phase 13 fills in real attributes.
- **Plan called for `var _ contract.VersionHandshake` as the contract drift detector;** this remains in main.go's import
  chain via `tfprovider "terraform-provider-homeassistant/internal/provider"` which imports `terraform-bridge/contract`
  and references `contract.VersionHandshake` for the version handshake (PROV-03). Phase 13 promoted the placeholder into
  a real Configure-handshake usage.

## Requirements Completed

- **TOFU-02** — Provider is a Go module built from local source via `replace terraform-bridge => ../terraform-bridge`.
- **TOFU-03** — `make update-version ADDON=terraform-bridge VERSION=X.Y.Z` updates Bridge (config/build/README) AND
  Provider (build.yaml) atomically; only the Bridge receives a `<addon>/v<version>` git tag.
- **TOFU-05** — `internal/validate-versions.sh` rejects pre-commit commits where Bridge and Provider
  `build.yaml:VERSION` diverge; the check is conditional on both files existing (pre-Phase-9 repos are not blocked).
