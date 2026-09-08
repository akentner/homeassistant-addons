# 17-01 Summary — iac-runner Phase 17 Options + tofu runtime

## Schema variant shipped

Shipped the **`str?` (optional) variant** of the `repos` schema — the plan's first choice.

```yaml
repos:
  - name: "match(^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$)"
    url: "match(^(git@|ssh://).+$)"
    branch: "str?"
    ref: "str?"
```

`python3 internal/validate-addon-config.py iac-runner` exited 0, confirming Supervisor's schema parser accepts the shape
(required `name` + `url`, optional `branch` / `ref` — the markdown-renderer pattern that empirically survives
Supervisor's optional-list-of-dict-with-mixed-optional-required quirk).

The fallback `str` variant was not needed.

## Pinned TOFU_VERSION

Pinned to **`1.10.6`** — the plan's primary target. No 404 encountered during execution (the build would have surfaced
it; deferred to CI since the local environment has no Docker daemon). The pin sits inside the
`internal/version/version.go` window (>= `1.6.0`, < `1.999.0`).

## Docker build binary assertion

**Deferred to CI.** Local environment has no `docker` daemon, so
`docker run --rm --entrypoint sh <image> -c 'tofu version && git --version && ssh -V'` was not executed. Per the plan's
contingency: "run `make docker-build-check` instead and record in the SUMMARY that the binary-presence assertion is
deferred to CI — do NOT mark the task done on a skipped build without recording it." Recorded.

CI will exercise the binary-presence assertion on the next `build-iac-runner.yml` run. If the tofu release asset 404s,
the contingency in the plan applies — bump to the newest available `v1.x.y` tag and re-record the pinned version here.

## Files changed

| File                     | Change                                                                                                                                                                                                                                                                                 |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `iac-runner/config.yaml` | +4 Options entries (repos, max_parallel_jobs, apply_timeout_minutes, runs_retention_hours); +4 schema entries                                                                                                                                                                          |
| `iac-runner/Dockerfile`  | +`ARG TOFU_VERSION=1.10.6` before first FROM; +new `FROM alpine:3.22 AS tofu` stage (pinned download + SHA256SUMS verify + `tofu version` build-time smoke test); +`RUN apk add --no-cache git openssh-client` + `COPY --from=tofu /usr/local/bin/tofu /usr/bin/tofu` in runtime stage |

## Verification

- `python3 internal/validate-addon-config.py iac-runner` — exit 0
- `./internal/validate-dockerfile-args.sh iac-runner/Dockerfile` — exit 0
- `yamllint iac-runner/config.yaml` — not installed locally
- `hadolint iac-runner/Dockerfile` — not installed locally
- Docker build / `tofu version` smoke test — deferred to CI

## Commit

`feat(17-01): iac-runner Phase 17 Options + tofu runtime` (81b0f54)
