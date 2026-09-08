# Deferred Items — Phase 17

Out-of-scope discoveries logged during execution. Not fixed (scope boundary rule).

## Pre-existing gofmt drift in iac-runner (found during 17-03)

`gofmt -l` reports these files as unformatted. None were touched by 17-03 and all predate this plan (Phase 16 / 17-01 /
17-02):

- `iac-runner/internal/auth/token.go`
- `iac-runner/internal/httpapi/handlers/healthz_test.go`
- `iac-runner/internal/httpapi/router.go`
- `iac-runner/internal/keys/validator_test.go`
- `iac-runner/internal/logging/scrubbing_handler_test.go`
- `iac-runner/cmd/runner/version.go`

`iac-runner/internal/git/` is gofmt-clean. A `gofmt -w ./...` sweep plus a gofmt pre-commit hook would be a reasonable
follow-up plan; it is deliberately not bundled here because it would touch six files across four packages that this plan
has no other reason to modify.

## No Go toolchain on the development host (found during 17-03)

`go` is not on PATH on this machine, so build/vet/test verification ran inside the `golang:1.25-alpine` image (the same
base `iac-runner/Dockerfile` builds with) with the host module cache mounted. Two consequences worth recording:

- `go test -race` needs cgo plus a C toolchain, which the base image lacks; the race run installs `gcc musl-dev` in the
  throwaway container.
- `internal/httpapi/handlers.TestHealthzBothPass` probes for a `tofu` binary via `exec.LookPath` and fails inside a bare
  toolchain container. This is an environment artifact, not a regression: with a stub `tofu` on PATH the suite is fully
  green. Consider making that test skip when `tofu` is absent (`t.Skip`) so the suite is hermetic.

## hadolint DL3003 in iac-runner/Dockerfile (found by the Wave 2 post-merge gate)

`make lint` fails with exit 1 on a single finding:

```
iac-runner/Dockerfile:40 DL3003 warning: Use WORKDIR to switch to a directory
```

The offending `cd /tmp && \` sits inside the OpenTofu download `RUN` of the `tofu` build stage, introduced by 17-01
(commit `81b0f54`). It is the only remaining `make lint` failure in the phase — every other hook passes.

Assigned to **17-07**, which already lists `iac-runner/Dockerfile` in `files_modified` and must run a local
`docker build` for its other Dockerfile work anyway (project CLAUDE.md: no untested Dockerfile changes). The fix is to
replace the in-`RUN` `cd /tmp` with a `WORKDIR /tmp` before that `RUN` (and restore the prior workdir afterwards if any
later instruction in the stage depends on it), then re-run `make lint` to confirm a clean exit.

## Secondary `*_VERSION` build args drift silently (found during 17-07)

`internal/update-version.py` rewrites exactly three fields: `config.yaml` `version`, `build.yaml` `args.VERSION`, and
the `README.md` shield/release links. It does NOT know about additional `args.<X>_VERSION` entries, and
`internal/validate-versions.sh` does not check them either (its grep is anchored on `^[[:space:]]*VERSION:`).

Two add-ons already carry drifted secondary args:

- `iac-runner/build.yaml` had `RUNNER_VERSION: "0.1.0"` against `VERSION: "0.2.0"` — the ldflags-injected
  `runner_version` reported by `/v1/version`, `/healthz` and the `starting` record would have been a version behind the
  add-on. Fixed by hand in 17-07 (the field has no supported tool path).
- `terraform-bridge/build.yaml` has `BRIDGE_VERSION: "0.1.0"` against `VERSION: "0.3.0"`. NOT touched — out of scope for
  Phase 17, and whether those two are meant to be in lock-step is a terraform-bridge decision.

Follow-up worth a small plan: teach `update-version.py` to rewrite sibling `args.*_VERSION` entries (opt-in per add-on,
or only when the sibling currently equals the outgoing `VERSION`), and extend `validate-versions.sh` to flag the
mismatch so it cannot recur silently.

## Backend credentials never reach the tofu child process (found during 17-07)

`internal/jobq/exec.go:91-93` passes `os.Environ()` to the tofu child and its comment states the backend credentials are
"the backend credentials 17-07 exports (AWS_ACCESS_KEY_ID and friends)". Nothing in the repository exports them:
`statebackend.Backend` offers `CredentialFiles()` (consumed only by the SEC-01 keys validator) but no env projection,
`run.sh` exports nothing, and `main.go` sets no variables. So the tofu child inherits the plain container environment.

Security-wise this is the conservative direction — the minimum credential env is literally empty, no `/data/keys/`
content is projected into a spawned process, and the process-spawn surface is limited to the pinned `tofu` binary
resolved once via `exec.LookPath` (`jobq.New`) plus `git` invoked with an explicit `GIT_SSH_COMMAND`. Functionally it
means `tofu init` against the r2/s3 backends cannot authenticate unless the operator's own IaC repo supplies credentials
another way.

No Phase 17 requirement covers the projection (the STBK requirements landed in Phase 16; the GIT, RUN, SEC-03 and OBS
requirements do not mention it), and ROADMAP Phase 19 SC-3 is the state-backend matrix that will exercise it end-to-end
against a real R2 bucket. Left to Phase 19 to design deliberately (which variables, read from which `/data/keys/` file,
scrubbed from which logs) rather than guessed at here.
