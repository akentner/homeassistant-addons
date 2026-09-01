---
phase: 15-ci-hardening-provider-install-workflow
plan: 01
type: execute
wave: 1
completed: 2026-08-31
duration: ~5 min (file edit + verification)
tasks_completed: 1
files_modified:
  - Makefile
commits:
  code: <hash>
  docs: <hash>
deviations:
  - "Plan 02's `internal/verify-install-provider.sh` was not yet on disk when Plan 01's executor finished; `make
    verify-install-provider` was therefore not exercised as part of Plan 01's verification. Plan 02's SUMMARY records
    the full end-to-end check."
  - "The plan's verify command asserts the binary lands at `$TMP/root/.terraform.d/...`, which assumes execution as
    root. As `akentner`, $HOME is `/home/akentner`, so the binary actually lands at
    `$TMP/home/akentner/.terraform.d/...`. The Makefile target is correct (it uses `$(HOME)` literally); the shell
    verifier shipped by Plan 02 uses `find` against the documented suffix and handles both layouts."
---

# Plan 15-01 Summary — install-provider Makefile target

## Objective (TOFU-04)

Ship the `make install-provider` target: build `terraform-provider-homeassistant` from local source and install the
binary to `${DESTDIR}${HOME}/.terraform.d/plugins/localhost/akentner/homeassistant/<version>/` so OpenTofu discovers it
via `dev_overrides`. The target MUST honor a `DESTDIR` override so Plan 03's CI workflow can run it in a hermetic temp
directory without polluting the runner's home directory.

Also add a `verify-install-provider` wrapper that invokes the hermetic shell verifier Plan 02 lands.

## Files Modified

| File     | Lines | Change                                                                                                             |
| -------- | ----- | ------------------------------------------------------------------------------------------------------------------ |
| Makefile | +30   | `.PHONY:` list extended (line 4); `install-provider:` + `verify-install-provider:` recipes appended after line 219 |

## Verification Results

| Check                                                                                                                        | Result                                                                   |
| ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `grep -E '^\.PHONY:.*install-provider' Makefile` returns 1 line                                                              | PASS                                                                     |
| `grep -E 'DESTDIR.*HOME.*plugins/localhost/akentner/homeassistant' Makefile` returns 1 line                                  | PASS                                                                     |
| `grep -E 'grep -E.*VERSION:' Makefile` matches                                                                               | PASS (whitespace-tolerant regex per `internal/validate-versions.sh:114`) |
| `grep -q 'dev_overrides' Makefile`                                                                                           | PASS                                                                     |
| `make -n install-provider DESTDIR=/tmp/x` shows expected recipe                                                              | PASS                                                                     |
| `make install-provider DESTDIR=$(mktemp -d)` produces an executable binary                                                   | PASS (25,436,518 bytes)                                                  |
| Binary located at `$TMP${HOME}/.terraform.d/plugins/localhost/akentner/homeassistant/0.1.0/terraform-provider-homeassistant` | PASS                                                                     |
| `actionlint .github/workflows/*`                                                                                             | PASS (no workflows modified by this plan)                                |
| `yamllint .github/workflows/*`                                                                                               | PASS                                                                     |
| `shellcheck -e SC1091 -e SC2034 internal/verify-install-provider.sh`                                                         | PASS (executed during Plan 02 finalize)                                  |
| `make check-all` exits 0                                                                                                     | PASS                                                                     |

## Must-Haves Achieved

- `make install-provider` builds the Provider from `terraform-provider-homeassistant/` source and copies the binary to
  `${HOME}/.terraform.d/plugins/localhost/akentner/homeassistant/<version>/`
- `make install-provider DESTDIR=/tmp/foo` honors the override so the same target is reusable inside CI without touching
  the host `~/.terraform.d`
- `make install-provider` reads the Provider version from `terraform-provider-homeassistant/build.yaml` at invocation
  time (whitespace-tolerant regex — mirrors `internal/validate-versions.sh:114`)
- The target emits a `dev_overrides { "akentner/homeassistant" = "<path>" }` CLI config snippet that names the same
  `<version>` directory it just populated
- The target fails fast (exit 1) if `terraform-provider-homeassistant/build.yaml` is missing
- `make check-all` exits 0

## Deviations

1. **Plan 02 verifier was not yet present** when Plan 01's verification ran. Plan 02 lands
   `internal/verify-install-provider.sh`, which `make verify-install-provider` calls. The wrapper target was added as
   specified but was not exercised end-to-end until Plan 02 finalized. Plan 02's SUMMARY records the full round-trip.
2. **Verify-command `$HOME` mismatch for non-root users.** The plan's automated verify command asserts the binary lands
   at `$TMP/root/.terraform.d/...` — that path is correct when running as root (CI), but the recipe uses `$(HOME)`
   literally, so as `akentner` the binary lands at `$TMP/home/akentner/.terraform.d/...`. The Makefile target is
   correct; the shell verifier (Plan 02) uses `find` against the documented suffix and handles both layouts, so this is
   not a functional bug — just an artifact of the plan's verify command being written from a root-runner perspective.

## Notes for Future Plans

- Plan 03 (`test-install-provider.yml`) consumes this target via `make install-provider DESTDIR=<tmp>` and exercises the
  full `tofu init` + `tofu plan` round-trip against the installed dev_overrides Provider. The plan's E2E workflow needs
  `opentofu/setup-opentofu@v1` — Plan 03 handles that.
