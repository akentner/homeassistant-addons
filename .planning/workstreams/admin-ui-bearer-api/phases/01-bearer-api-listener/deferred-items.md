# Deferred Items: Phase 01 (bearer-api-listener)

## `make build-addon` needs Docker buildx (found in 01-06)

- **What:** The `build-addon` target in `Makefile` passes `--progress=plain` to `docker build`. Only the BuildKit
  builder (the buildx plugin) accepts that flag. On a host without buildx, docker 29 falls back to the legacy builder
  and fails with `unknown flag: --progress` (exit 125) before the build starts.
- **Impact:** You cannot run `make build-addon` on such a host. In 01-06 the five images were built with the exact
  command from `make -n build-addon`, minus that one flag. Build args and the `local/<addon>:<config version>` tag
  were unchanged.
- **Options (repo tooling, outside this phase):** install the buildx plugin on the dev host, or drop
  `--progress=plain` from the target (or pass it only when `docker buildx version` succeeds).
- **Status:** open; not fixed in this phase (scope boundary: pre-existing tooling, unrelated to the listener).
