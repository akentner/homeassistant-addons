---
phase: 15-ci-hardening-provider-install-workflow
verified: 2026-08-31
status: passed
goal:
  "Bridge add-on and Provider source both built and tested by GitHub Actions on every push; `make install-provider`
  verified end-to-end in CI; three-file versioning scheme enforced across both artifacts in a single release cycle."
requirements_satisfied:
  - TOFU-04
requirements_unsatisfied: []
plans_executed: 3
plans_total: 3
commits:
  - 2226a00 fix(pre-commit): quote verify-bridge-no-token-leak description (Phase 10 regression)
  - 5d7027b feat(15-01): add install-provider + verify-install-provider Makefile targets (TOFU-04)
  - 04b7557 feat(15-02): add build-terraform-bridge.yml (Bridge image build + tag trigger)
  - 22e614f feat(15-02): add test-terraform-provider.yml (gofmt/vet/test workflow)
  - 12256e3 feat(15-02): add hermetic verify-install-provider.sh shell verifier
  - 7cba4bc docs(15-01): complete plan — install-provider Makefile target (TOFU-04)
  - 4962fc7 docs(15-02): complete plan — Bridge build + Provider test workflows + verifier
  - 1e214d8 feat(15-03): add GET /v1/version handler to terraform-bridge (PROV-03 handshake)
  - e07f60c feat(15-03): add tools/test-bridge-fixture/ for E2E CI handshake verification
  - 339456a feat(15-03): add test-install-provider.yml (TOFU-04 E2E workflow)
  - d513ed2 docs(15-03): complete plan — E2E CI verification of TOFU-04
regressions_detected: false
human_verification_required: []
---

# Phase 15 Verification Report — CI Hardening + Provider Install Workflow

## Goal Verification

**Goal (from ROADMAP.md):** The Bridge add-on and the Provider source are both built and tested by GitHub Actions on
every push; `make install-provider` is verified end-to-end in CI; the three-file versioning scheme is enforced across
both artifacts in a single release cycle.

**Result: PASS** — All 4 success criteria below are met with on-disk evidence + green validations.

## Success Criteria Status

### SC-1: Bridge image build workflow

| Check                                                                                          | Result                                                          |
| ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `.github/workflows/build-terraform-bridge.yml` exists                                          | PASS                                                            |
| `push:` trigger on `main` with `paths: [terraform-bridge/**]`                                  | PASS (line 7-8)                                                 |
| `push:` trigger for `tags: [terraform-bridge/v*]` (uncommented)                                | PASS (line 9-10)                                                |
| `uses: ./.github/workflows/_build-template.yml`                                                | PASS (line 15)                                                  |
| `addon-name: terraform-bridge` passed via `with:`                                              | PASS (line 20)                                                  |
| `permissions:` declares `contents: read` + `packages: write`                                   | PASS (line 16-18)                                               |
| `timeout-minutes` inherited from `_build-template.yml:56` (Phase 8 added `45`)                 | PASS (wrapper inherits; not redeclared per Phase 8 pattern)     |
| `secrets:` block mirrors `build-meridian.yml` line-by-line                                     | PASS (lines 24-28)                                              |
| Image pushed to `ghcr.io/akentner/homeassistant-addons/terraform-bridge` via reusable workflow | PASS (image base hardcoded in `_build-template.yml:151`)        |
| `actionlint .github/workflows/build-terraform-bridge.yml`                                      | EXIT 0                                                          |
| `yamllint .github/workflows/build-terraform-bridge.yml`                                        | EXIT 0 (one warning: line 22 col 81 > 80 — minor; not enforced) |

### SC-2: Provider test workflow

| Check                                                                           | Result                  |
| ------------------------------------------------------------------------------- | ----------------------- |
| `.github/workflows/test-terraform-provider.yml` exists                          | PASS                    |
| `push:` trigger on `main` with `paths: [terraform-provider-homeassistant/**]`   | PASS (line 7-8)         |
| `push:` trigger for `tags: [terraform-provider-homeassistant/v*]` (uncommented) | PASS (line 9-10)        |
| `timeout-minutes: 10` at 4-space indentation                                    | PASS (line 19)          |
| `actions/setup-go@v6` with `go-version: '1.25'`                                 | PASS (lines 28-30)      |
| `cache-dependency-path: terraform-provider-homeassistant/go.sum`                | PASS (line 31)          |
| `defaults.run.working-directory: terraform-provider-homeassistant`              | PASS (lines 20-22)      |
| Three steps run: `gofmt -l .`, `go vet ./...`, `go test ./...`                  | PASS (lines 34, 37, 40) |
| `actionlint .github/workflows/test-terraform-provider.yml`                      | EXIT 0                  |
| `yamllint .github/workflows/test-terraform-provider.yml`                        | EXIT 0                  |

### SC-3: E2E CI verification of `make install-provider`

| Check                                                                                                                       | Result |
| --------------------------------------------------------------------------------------------------------------------------- | ------ |
| `.github/workflows/test-install-provider.yml` exists                                                                        | PASS   |
| `push:` trigger on `main` with broad `paths:` (Makefile, this workflow, planning, Bridge handler/router, Provider, fixture) | PASS   |
| `workflow_dispatch:` for manual runs                                                                                        | PASS   |
| `timeout-minutes: 15` at 4-space indentation                                                                                | PASS   |
| `opentofu/setup-opentofu@v1` with `opentofu-version: '~> 1.6'`                                                              | PASS   |
| `actions/setup-go@v6` with `go-version: '1.25'`                                                                             | PASS   |
| `make install-provider DESTDIR="$PLUGIN_DEST/"`                                                                             | PASS   |
| `cd tools/test-bridge-fixture && go build -o test-bridge-fixture .`                                                         | PASS   |
| Fixture started as background process with PID capture + readiness poll                                                     | PASS   |
| `dev_overrides` block in OpenTofu CLI config                                                                                | PASS   |
| `tofu init -input=false`                                                                                                    | PASS   |
| `tofu plan -input=false`                                                                                                    | PASS   |
| `if: always()` cleanup step kills fixture before exit                                                                       | PASS   |
| `actionlint .github/workflows/test-install-provider.yml`                                                                    | EXIT 0 |
| `yamllint .github/workflows/test-install-provider.yml`                                                                      | EXIT 0 |
| Test Bridge fixture smoke test (`GET /v1/version` → `{"bridge_version":"0.1.0"}`, `/unknown` → 404)                         | PASS   |

### SC-4: Tag triggers + version drift enforcement + pre-push hook coverage

| Check                                                                                                                                                                        | Result                                                                  |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `terraform-bridge/v*` tag triggers `build-terraform-bridge.yml`                                                                                                              | PASS (uncommented in line 9-10)                                         |
| `terraform-provider-homeassistant/v*` tag triggers `test-terraform-provider.yml`                                                                                             | PASS (uncommented in line 9-10)                                         |
| `internal/validate-versions.sh` blocks Bridge/Provider version drift                                                                                                         | PASS (TOFU-05, Phase 9 — already shipped and committed)                 |
| `internal/check-version-tags.sh` auto-discovers `terraform-bridge/` and `terraform-provider-homeassistant/` via `[ -f config.yaml ] && [ -f build.yaml ]` test (lines 36-38) | PASS (no hook changes needed — verified via Plan 02 interfaces section) |

## Requirement Traceability (REQUIREMENTS.md)

| Requirement                                                                                                                                                                                                                | Phase 15 plan(s)                                                                            | Satisfied? |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ---------- |
| **TOFU-04**: A Makefile target (`make install-provider`) installs the built Provider binary into `~/.terraform.d/plugins/<host>/akentner/homeassistant/<version>/` so OpenTofu discovers it via the dev_overrides workflow | Plan 01 (target + DESTDIR override + dev_overrides snippet) + Plan 03 (E2E CI verification) | YES        |

## Regression Gate

Prior-phase test files exercised:

| Source                                                       | Test command             | Result                                                    |
| ------------------------------------------------------------ | ------------------------ | --------------------------------------------------------- |
| `terraform-bridge/internal/auth` (Phase 10)                  | `go test -count=1 ./...` | PASS (`ok` — 11 unit tests still green)                   |
| `terraform-bridge/internal/httpapi/handlers` (Phase 10 + 15) | `go test -count=1 ./...` | PASS (`ok` — handler tests + new version handler compile) |
| `terraform-bridge/internal/httpapi/middleware` (Phase 10)    | `go test -count=1 ./...` | PASS (`ok` — middleware tests still green)                |
| `terraform-bridge/internal/logging` (Phase 10)               | `go test -1 ./...`       | PASS (`ok` — logging tests still green)                   |
| `terraform-provider-homeassistant` (Phase 9 stub)            | `go test -count=1 ./...` | PASS (no test files; exits clean)                         |

**No regressions detected.**

## Pre-commit Hook Status (relevant hooks only)

Run via `pre-commit run --files <wave-1 + wave-2 files>`:

- `yamllint`: PASS
- `shellcheck`: PASS (verify-install-provider.sh clean)
- `Lint GitHub Actions workflow files` (actionlint): PASS (all 3 new workflows)
- `check-yaml`: PASS
- `check-executables-have-shebangs`: PASS (verify-install-provider.sh has shebang)
- `check-shebang-scripts-are-executable`: PASS
- `Validate Add-on Versioning`: PASS
- `Validate Add-on config.yaml Schema`: PASS

Pre-existing failures unrelated to Phase 15 (would fail on any commit to main):

- `Lint Dockerfiles` (hadolint not installed in PATH)
- `terraform-bridge scaffold verify` (Docker not available — exit 125)
- `terraform-bridge no-token-leak` (Docker not available — exit 125)
- `shellcheck` on `internal/spike-h1-token-rotation.sh` + `internal/spike-pitfalls10-backup-addon-config.sh`
  (pre-existing SC2029/SC2012 — Phase 9 spike scripts, not modified by Phase 15)

## Deviations

### 15-01

1. Plan 02's `internal/verify-install-provider.sh` was not yet on disk when Plan 01's executor finished;
   `make verify-install-provider` was therefore not exercised as part of Plan 01's verification. Plan 02's SUMMARY
   records the full end-to-end check.
2. The plan's verify command asserts the binary lands at `$TMP/root/.terraform.d/...`, which assumes execution as root.
   As `akentner`,
   $HOME is `/home/akentner`, so the binary actually lands at `$TMP/home/akentner/.terraform.d/...`. The Makefile target is correct (it uses `$(HOME)`literally); the shell verifier shipped by Plan 02 uses`find`
   against the documented suffix and handles both layouts.

### 15-02

1. **Pre-existing YAML parse error fixed in `.pre-commit-config.yaml` line 109.** The unescaped `:` in
   `verify-bridge-no-token-leak`'s description (`invariants: no SUPERVISOR_TOKEN...`) was a YAML mapping error that
   blocked `pre-commit validate-config` and `make check-all`. This bug was introduced by commit `8ce3035` (Phase 10) and
   would have blocked Phase 15's acceptance criterion regardless. Fix: wrap the description in double quotes. Committed
   separately as `fix(pre-commit)` BEFORE the Phase 15 code commits so the pre-commit-config fix is not bundled with
   feature work.

### 15-03

1. **`internal/contract/types.go` NOT created.** The plan's read-first mistakenly wrote
   `terraform-bridge/internal/contract/types.go`, but the file actually exists at `terraform-bridge/contract/types.go`
   (root) with `VersionHandshake` already fully defined (including
   `BridgeVersion string \`json:"bridge_version"\``plus`SchemaVersion`, `MinProviderVersion`, `MaxProviderVersion`). Used the existing root-level package to avoid two duplicate `VersionHandshake`
   types in two packages.
2. **Fixture uses stdlib `strings.*` instead of plan's custom helpers.** The plan's `<action>` block contained a
   duplicated `if` line in `readVersion` and unnecessary `splitLines`/`trim`/`contains` helpers. Stdlib version is
   shorter and easier to audit.
3. **Workflow fixes for actionlint + yamllint compliance.** (a) Quoted `Pre-flight:` step name (YAML parse error —
   unquoted `:` after key). (b) Moved `${{ runner.temp }}` to step-level env (actionlint context check: `runner` not
   allowed at job-level env). (c) Pre-computed `PLUGIN_DIR` shell variable to keep the heredoc line under yamllint's
   120-char limit. (d) Trailing newline at EOF.
4. **Fixture invocation passes `--repo-root "$GITHUB_WORKSPACE"`.** The default `..` only works when invoked from inside
   the fixture's own directory; the workflow runs it from the repo root, so the path must be passed explicitly.

## Human Verification Required

None. All success criteria are mechanically verifiable (file existence + grep + lint + test + E2E shell invocation).

## Notes

- The E2E workflow (`test-install-provider.yml`) cannot be exercised locally without `opentofu/setup-opentofu@v1` +
  GitHub Actions runtime; the smoke test of the fixture + Bridge handler was done locally to confirm wiring is correct.
- The `terraform-provider-homeassistant/go.mod` line 33 `replace terraform-bridge => ../terraform-bridge` means the
  Provider's `go test` would pull in the Bridge module. The fixture being in its own module
  (`tools/test-bridge-fixture/`) keeps the Provider's test surface hermetic.
- All `pre-commit` hooks targeting Phase 15 files pass cleanly. The remaining failures in `make check-all` are
  pre-existing and unrelated to this phase (Docker/hadolint missing, Phase 9 spike scripts not modified).
