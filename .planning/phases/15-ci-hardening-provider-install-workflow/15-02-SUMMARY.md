---
phase: 15-ci-hardening-provider-install-workflow
plan: 02
type: execute
wave: 1
completed: 2026-08-31
duration: ~3 min (file creation + verification)
tasks_completed: 3
files_modified:
  - .github/workflows/build-terraform-bridge.yml (new)
  - .github/workflows/test-terraform-provider.yml (new)
  - internal/verify-install-provider.sh (new)
commits:
  bridge-workflow: <hash>
  provider-workflow: <hash>
  verifier-script: <hash>
  docs: <hash>
deviations:
  - "Fixed pre-existing YAML parse error in `.pre-commit-config.yaml` line 109 (unescaped `:` in `verify-bridge-no-token-leak` description, introduced by commit 8ce3035 in Phase 10). Without the fix, `make check-all` fails before any hook can run. Fix: wrap the description in double quotes. Committed separately as `fix(pre-commit)` BEFORE the Phase 15 code commits so the pre-commit-config fix is not bundled with feature work."
---

# Plan 15-02 Summary — Bridge build + Provider test workflows + verifier

## Objective

Land two new GitHub Actions workflows (Bridge image build, Provider gofmt/vet/test) and one hermetic shell verifier
(`internal/verify-install-provider.sh`). Together they gate every future Bridge/Provider release on CI.

## Files Created

| File | Lines | Purpose |
| ---- | ----- | ------- |
| `.github/workflows/build-terraform-bridge.yml` | 28 | Thin wrapper calling `_build-template.yml` with `addon-name: terraform-bridge`. Push triggers on `terraform-bridge/**` AND on `terraform-bridge/v*` tags (uncommented). Single-arch matrix `["amd64"]`. Mirrors `build-meridian.yml` line-by-line for `secrets:` block. |
| `.github/workflows/test-terraform-provider.yml` | 40 | Standalone Go CI: `gofmt -l .` / `go vet ./...` / `go test ./...` against the Provider module. Push triggers on `terraform-provider-homeassistant/**` AND on `terraform-provider-homeassistant/v*` tags. Single `test:` job with `timeout-minutes: 10`. Job-level `defaults.run.working-directory: terraform-provider-homeassistant` keeps the steps flat. |
| `internal/verify-install-provider.sh` | 133 | Hermetic shell verifier (executable). `set -euo pipefail`, RED/GREEN/YELLOW color codes, BASH_SOURCE-based repo-root resolution, `mktemp -d` + `trap EXIT` cleanup. Calls `make install-provider DESTDIR="$TMP/"`, locates the binary at `*plugins/localhost/akentner/homeassistant/<version>/terraform-provider-homeassistant` via `find`, asserts executable + non-empty, runs `$BINARY -version` as a tolerated bonus signal (Phase 9 stub does not wire `-version`). |

## Verification Results

| Check | Result |
| ----- | ------ |
| `test -f .github/workflows/build-terraform-bridge.yml` | PASS |
| `test -f .github/workflows/test-terraform-provider.yml` | PASS |
| `test -f internal/verify-install-provider.sh` | PASS |
| `grep -q 'terraform-bridge/v\*' .github/workflows/build-terraform-bridge.yml` AND not commented | PASS |
| `grep -E '^\s*terraform-provider-homeassistant/v\*' .github/workflows/test-terraform-provider.yml` | PASS |
| `grep -E '^    timeout-minutes: 10$' .github/workflows/test-terraform-provider.yml` | PASS |
| `grep -q 'uses: ./.github/workflows/_build-template.yml' .github/workflows/build-terraform-bridge.yml` | PASS |
| `grep -q 'addon-name: terraform-bridge' .github/workflows/build-terraform-bridge.yml` | PASS |
| `grep -q 'actions/setup-go@v6' .github/workflows/test-terraform-provider.yml` | PASS |
| `grep -q "go-version: '1.25'" .github/workflows/test-terraform-provider.yml` | PASS |
| `grep -q 'cache-dependency-path: terraform-provider-homeassistant/go.sum' .github/workflows/test-terraform-provider.yml` | PASS |
| `grep -q 'gofmt -l' .github/workflows/test-terraform-provider.yml` AND `go vet` AND `go test ./...` | PASS |
| `grep -q 'BASH_SOURCE' internal/verify-install-provider.sh` | PASS |
| `grep -E 'trap.*EXIT|rm -rf' internal/verify-install-provider.sh` | PASS |
| `grep -E 'terraform-provider-homeassistant/build.yaml|VERSION:' internal/verify-install-provider.sh` | PASS |
| `actionlint .github/workflows/build-terraform-bridge.yml .github/workflows/test-terraform-provider.yml` | EXIT 0 |
| `yamllint -d relaxed .github/workflows/build-terraform-bridge.yml .github/workflows/test-terraform-provider.yml` | EXIT 0 (1 warning: line 22 col 81 > 80 chars — minor; ignored) |
| `shellcheck -e SC1091 -e SC2034 internal/verify-install-provider.sh` | EXIT 0 |
| `bash internal/verify-install-provider.sh` (full end-to-end) | PASS — binary located, executable, non-empty (25,436,518 bytes); `-version` warning tolerated |
| `make check-all` | PASS |

## Must-Haves Achieved

- `.github/workflows/build-terraform-bridge.yml` builds the multi-stage Bridge image on push to `main` touching
  `terraform-bridge/**` and pushes it to `ghcr.io/akentner/homeassistant-addons/terraform-bridge`
- The Bridge build workflow also fires on the `terraform-bridge/v*` git tag push (uncommented, unlike other
  per-addon workflows where tag lines are commented — Bridge releases are tag-gated per TOFU-05)
- Every job in `build-terraform-bridge.yml` carries `timeout-minutes: 45` inherited from `_build-template.yml`
- `.github/workflows/test-terraform-provider.yml` runs `gofmt -l .` / `go vet ./...` / `go test ./...` against
  `terraform-provider-homeassistant/` on push to `main` touching `terraform-provider-homeassistant/**` AND on
  `terraform-provider-homeassistant/v*` tag pushes
- The `test` job has explicit `timeout-minutes: 10`
- `internal/verify-install-provider.sh` builds the Provider into a temp DESTDIR, locates the binary at the documented
  dev_overrides path via `find`, asserts it is executable + non-empty, and exits 0
- `make check-all` exits 0 (actionlint + yamllint + shellcheck all green; pre-commit-config parse error fixed)

## Diff Against `build-meridian.yml`

`build-terraform-bridge.yml` is a near-clone of `build-meridian.yml` with three deltas:

1. `paths: terraform-bridge/**` instead of `meridian/**`
2. `tags: terraform-bridge/v*` UNCOMMENTED (active) — `build-meridian.yml` has these lines commented because
   Phase 8 noted that the per-addon build is currently triggered by the workflow file change (see
   `.github/RELEASE.md` referenced in the commented lines). Bridge releases are tag-gated per TOFU-05.
3. `archs: '["amd64"]'` is the same single-arch narrowing as `build-meridian.yml`. v1.3 only scaffolds Bridge for
   amd64; aarch64 cross-compile is post-v1.3.

The `permissions:`, `secrets:`, `workflow_dispatch`, and reusable workflow `uses:` are identical to `build-meridian.yml`.

## Deviations

1. **Pre-existing YAML parse error fixed in `.pre-commit-config.yaml` line 109.** The unescaped `:` in
   `verify-bridge-no-token-leak`'s description (`invariants: no SUPERVISOR_TOKEN...`) was a YAML mapping error
   that blocked `pre-commit validate-config` and `make check-all`. This bug was introduced by commit `8ce3035`
   (Phase 10) and would have blocked Phase 15's acceptance criterion regardless. Fix: wrap the description in
   double quotes. Committed separately as `fix(pre-commit): quote ... description (Phase 10 regression)` BEFORE
   the Phase 15 code commits so the pre-commit-config fix is not bundled with feature work.

## Notes for Future Plans

- Plan 03 (test-install-provider.yml E2E) consumes this verifier via `make verify-install-provider` as a pre-flight
  check, then proceeds to `tofu init` + `tofu plan` against the dev_overrides-installed Provider.
- The pre-push hook `internal/check-version-tags.sh` auto-discovers `terraform-bridge/` and
  `terraform-provider-homeassistant/` via the existing `config.yaml + build.yaml` test (line 36-38) — no hook
  changes needed.
