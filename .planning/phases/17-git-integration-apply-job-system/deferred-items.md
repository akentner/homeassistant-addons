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
