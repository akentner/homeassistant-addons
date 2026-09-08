# IaC Runner — Operator Documentation

## Overview

Bearer-authenticated OpenTofu/Terraform runner for homelab IaC against R2/S3/local state backends. The runner exposes a
JSON-over-HTTP API on port 8125 (distinct from `terraform-bridge`'s 8124). Phase 16 shipped the authentication,
state-backend configuration, and healthcheck surface; Phase 17 adds SSH-keyed git integration and the OpenTofu job
system (`/v1/repos/{name}/pull`, `/v1/plan`, `/v1/apply`, `/v1/runs/{id}`, `/v1/runs`).

## Install

1. In the HA UI: **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and add
   `https://github.com/akentner/homeassistant-addons`.
2. Search for **IaC Runner** in the Add-on Store, click it, then **Install**.
3. Start the add-on. The first start generates a fresh bearer token (see First-time setup below).

## First-time setup

1. On the HA host shell, retrieve the freshly generated bearer from the add-on log:
   `sudo ha addons logs iac-runner | grep iac_runner.token.issued` The log line carries a 3+3-char preview (`preview`)
   and the `actor_token_fp` (SHA-256[8] hex) for correlation. **The plaintext token itself appears ONLY in this single
   log line** — subsequent restarts do NOT re-emit it.
2. For production use, copy the value into your CI's `IAC_RUNNER_BEARER` secret. The token file
   `/data/initial-iac-runner-token` (chmod 600) is written exactly once and contains the plaintext; operators SHOULD
   delete this file after configuring CI so the plaintext is not stored on disk any longer than necessary.
3. If you configured any entries under the `repos` Option, drop the matching SSH deploy key for each repo at
   `/data/keys/<repo-name>.key` (chmod 600) and your `known_hosts` at `/data/keys/known_hosts` (chmod 600). The
   deploy-key filename MUST match `<repo-name>.key` exactly — the runner joins it onto `/data/keys/` and passes it to
   `ssh -i` via `GIT_SSH_COMMAND`, together with `StrictHostKeyChecking=yes` and
   `UserKnownHostsFile=/data/keys/known_hosts`, so an unlisted host key surfaces as `git_ssh_handshake` rather than a
   silent trust-on-first-use accept.

   Both files are presence-checked at startup and any gap is named in the `repos_loaded` log record's `key_issues`
   field; a missing key is NOT fatal (the affected repo's clone fails, every other repo still works). Any file that DOES
   exist under `/data/keys/` must be chmod 600 and owned by the add-on's UID or the runner refuses to start (SEC-01) —
   there is no degraded mode.

   Generate a key pair and pin the host key like this:

   ```bash
   ssh-keygen -t ed25519 -N "" -C "iac-runner homelab" -f homelab.key
   ssh-keyscan github.com >> known_hosts
   # copy homelab.key + known_hosts into /data/keys/ and chmod 600 both;
   # add homelab.key.pub as a read-only deploy key on the repo
   ```

## Configuration

See `iac-runner/config.yaml` for the full schema. Every option is documented below with an example.

### `bind_address`

Default: `"auto"`. The address the runner binds to.

- `"auto"` (default): auto-detect the first `tailscale*` interface in `/sys/class/net` and bind to its IPv4 address.
  Recommended for Tailscale-only deployments.
- Explicit IP (e.g. `"100.64.0.1"`): bind to this specific IP. Accepted only if it belongs to a `tailscale*` interface
  OR falls inside one of the configured `bind_allowed_subnets`.
- `"0.0.0.0"`: **ALWAYS REFUSED** at startup regardless of `bind_allowed_subnets`. The runner exits with status 1 and a
  clear error message naming the refused value.

### `bind_allowed_subnets`

Default: `[]` (empty). List of CIDR strings (e.g. `["10.0.0.0/8", "192.168.0.0/16"]`). An explicit `bind_address` is
accepted if it falls inside one of these subnets OR belongs to a Tailscale interface. The `bind_allowed_subnets` does
NOT override the `0.0.0.0` refusal.

### `state_backend`

Default: `"r2"`. Selects the Terraform state backend. One of `"r2"`, `"s3"`, `"local"`.

- `state_backend: "r2"` (default): Cloudflare R2 via the S3-compatible API. Endpoint is constructed from
  `/data/keys/r2-account-id`. Uses `use_lockfile = true` (no DynamoDB required).
- `state_backend: "s3"`: any S3-compatible endpoint supplied via `s3_endpoint`. Uses `use_lockfile = true` (no DynamoDB
  required).
- `state_backend: "local"`: state stored at `/data/terraform.tfstate`. No external credentials required. Lock is
  file-based at `/data/terraform.tfstate.lock` (HA backup covers both files automatically).

Any other value is rejected at the HA Supervisor UI level (the `config.yaml` schema uses `list(match(^(r2|s3|local)$))`)
AND at runtime by `statebackend.New` (returns `ErrUnsupported`).

### `r2_bucket`

Required when `state_backend: "r2"`. The R2 bucket name (e.g. `"homelab-iac-state"`). The runner constructs the endpoint
as `https://<account_id>.r2.cloudflarestorage.com`; `<account_id>` is read from `/data/keys/r2-account-id`.

### `s3_endpoint`, `s3_bucket`, `s3_region`

Required when `state_backend: "s3"`. The S3-compatible endpoint URL (e.g. `"https://s3.amazonaws.com"`), bucket name,
and region (e.g. `"us-east-1"`).

### `repos`

Default: `[]` (empty). List of dicts; each entry has `name`, `url`, `branch`, `ref`. The HA Supervisor schema in
`iac-runner/config.yaml` regex-validates `name` (`^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$`) and `url` (SSH only,
`^(git@|ssh://).+$`); the runner re-validates every entry at startup and refuses to start on a malformed or duplicated
entry, because a silently-dropped repo would surface much later as an inexplicable `run_unknown_repo`.

Each entry is cloned into `/data/repos/<name>/` at startup. `branch` defaults to `main` when empty. A non-empty `ref`
pins the checkout to that commit or tag and takes precedence over `branch`.

Example (one repo tracking a branch):

```yaml
repos:
  - name: homelab
    url: git@github.com:akentner/homelab-infra.git
    branch: main
    ref: "" # empty = fast-forward pull on `branch`
```

Example (two repos, one pinned to a tag):

```yaml
repos:
  - name: homelab
    url: git@github.com:akentner/homelab-infra.git
  - name: docs
    url: git@github.com:akentner/homelab-docs.git
    branch: main
    ref: "v1.2.3"
```

### `max_parallel_jobs`

Default: `4`. Range: `1..32`. Integer. Maximum number of concurrent tofu jobs the runner will start (RUN-06). When this
many jobs are already in flight, `POST /v1/plan` and `POST /v1/apply` return `HTTP 503` + `Retry-After: 30` with
`error_code: "apply_capacity_exhausted"` — they do NOT silently queue, so back-pressure is visible to the caller instead
of showing up as an unexplained delay. Raise it when several repos need to plan in parallel; lower it when one homelab
server cannot safely host many concurrent state-locking tofu processes.

Jobs for the SAME repo are serialized by a per-repo mutex regardless of this value: a second apply on the same repo is
accepted with `202` and waits its turn (RUN-06). Only cross-repo jobs actually run in parallel.

### `apply_timeout_minutes`

Default: `60`. Range: `5..1440`. Integer. Per-job wall-clock cap covering the WHOLE command sequence (`tofu init` +
`tofu plan`, or `tofu init` + `tofu apply`) — a budget for the job, not for each process. At expiry the runner sends
`SIGTERM` so tofu can release its state lock; if the process is still alive 10s later it is `SIGKILL`ed and the run is
recorded as `failed` with `error_code: "apply_timeout"` (`plan_timeout` for a plan). The per-repo mutex and the
`max_parallel_jobs` slot are released regardless of which signal landed.

### `runs_retention_hours`

Default: `24`. Range: `1..720`. Integer. How long a run directory lives under `/data/runs/` before it is deleted. The
runner reclaims once at boot (`runs_rotated_at_boot`) and then on a background ticker every `runs_retention_hours / 4`
(default 6h, floored at 1 minute). `queued` and `running` runs are never deleted regardless of age — their writer still
holds an open descriptor on `output.log`.

Worst-case disk footprint is roughly `max_parallel_jobs x average-run-size x retention-hours`; size `/data` accordingly.
A value of `0` in a hand-edited `/data/options.json` is rejected at startup and replaced by the default 24h (logged as
`runs_retention_invalid`), because `0` would mean "delete every finished run on the next tick".

## State backend credential files

The runner reads credential files from `/data/keys/` (chmod 600 required, current process UID ownership required). On
startup, **non-conforming files cause startup failure** (exit 1) with a clear error message naming the offending file —
there is no degraded mode.

### R2 backend required files

| File                       | Mode | Notes                                                        |
| -------------------------- | ---- | ------------------------------------------------------------ |
| `/data/keys/r2-access.key` | 0600 | R2 access key ID (e.g. `AKIAEXAMPLE`)                        |
| `/data/keys/r2-secret.key` | 0600 | R2 secret access key (40+ chars base64)                      |
| `/data/keys/r2-account-id` | 0600 | Cloudflare account ID (32-char hex, plaintext non-sensitive) |

### S3 backend required files

| File                       | Mode | Notes                |
| -------------------------- | ---- | -------------------- |
| `/data/keys/s3-access.key` | 0600 | S3 access key ID     |
| `/data/keys/s3-secret.key` | 0600 | S3 secret access key |

### Local backend required files

None. The local backend uses `/data/terraform.tfstate` (no external credentials).

## HTTP API

The runner exposes the following endpoints on port 8125:

| Method | Path              | Auth   | Description                                                                               |
| ------ | ----------------- | ------ | ----------------------------------------------------------------------------------------- |
| GET    | `/`               | none   | Placeholder JSON with `runner_version`, `status`, `msg`                                   |
| GET    | `/healthz`        | none   | 200 + JSON when tofu on PATH AND `/data/keys/` chmod-600 passes; 503 empty body otherwise |
| POST   | `/v1/auth/rotate` | Bearer | Issue a new bearer token; for 24h both old and new authenticate                           |
| GET    | `/v1/version`     | Bearer | Returns runner + schema + min/max supported OpenTofu versions                             |

The Phase 17 job surface:

| Method | Path                    | Auth   | Description                                               |
| ------ | ----------------------- | ------ | --------------------------------------------------------- |
| POST   | `/v1/repos/{name}/pull` | Bearer | Fast-forward pull (or ref checkout) on one repo           |
| POST   | `/v1/plan`              | Bearer | Submit a `tofu plan` job; 202 + `Location: /v1/runs/{id}` |
| POST   | `/v1/apply`             | Bearer | Submit a `tofu apply` job; 202 + `Location`               |
| GET    | `/v1/runs/{id}`         | Bearer | One run with paginated, secret-redacted output            |
| GET    | `/v1/runs`              | Bearer | Recent runs, newest-first, with `?repo=` / `?status=`     |

### `/healthz` (no auth)

```bash
curl http://<runner-host>:8125/healthz
```

Returns 200 + JSON when BOTH checks pass:

```json
{
  "status": "ok",
  "tofu_on_path": true,
  "keys_chmod_600": true,
  "runner_version": "0.1.0"
}
```

Returns 503 with empty body when EITHER check fails (tofu binary missing from PATH, or any file under `/data/keys/` is
not chmod 600 owned by the current process UID). The 503 body is intentionally empty to avoid leaking internal state.

### `POST /v1/auth/rotate` (Bearer required)

```bash
curl -X POST -H "Authorization: Bearer <token>" http://<runner-host>:8125/v1/auth/rotate
```

Returns 200 + JSON:

```json
{
  "new_token": "...",
  "grace_expires_at": "2026-09-07T17:39:00Z",
  "old_token_valid_until": "2026-09-07T17:39:00Z"
}
```

The `new_token` plaintext appears in this response exactly once. After rotation, BOTH the old and the new token
authenticate for 24 hours (the grace window); after 24h the old token stops authenticating. Grace state persists in
`/data/iac-runner-token.grace` (chmod 600) and survives restart.

### `GET /v1/version` (Bearer required)

```bash
curl -H "Authorization: Bearer <token>" http://<runner-host>:8125/v1/version
```

Returns 200 + JSON:

```json
{
  "runner_version": "0.1.0",
  "schema_version": "1.0.0",
  "min_supported_opentofu": "1.6.0",
  "max_supported_opentofu": "1.999.0"
}
```

`schema_version` follows semver; bump MAJOR on every breaking change to the /v1/* HTTP API surface.

### `POST /v1/repos/{name}/pull`

Fast-forward pull (or ref checkout) on the named repo using `/data/keys/<name>.key` + `/data/keys/known_hosts`.

Auth: required. Request body: optional — a bare POST, an empty body and `{}` are all equivalent. `{"ff_only": true}`
explicitly demands fast-forward semantics; an unknown field is a 400 rather than a silently ignored flag.

A repo with an empty `ref` is pulled with `--ff-only`. A repo pinned via `ref` is fetched and re-landed on that ref
(`mode: "ref"`), so a pinned repo can still be refreshed; asking for `ff_only: true` on a pinned repo is the one genuine
contradiction and is refused with `git_ref_pull_incompatible`.

Response 200:

```json
{ "name": "homelab", "mode": "ff-only", "head": "abc1234567890abcdef1234567890abcdef12345" }
```

`mode` is `ff-only` or `ref`; `head` is the commit the working tree ended up on, so a no-op pull is distinguishable from
a real advance.

Errors: `run_unknown_repo` (404), `run_invalid_dir` (400 — malformed body), `git_ref_pull_incompatible` (400),
`git_ssh_handshake` / `git_unauthorized` (403), `git_non_fast_forward` (409), `git_clone_missing` / `git_ref_not_found`
(404), `git_dns_failure` / `git_clone_failed` (502).

```bash
curl -sS -X POST -H "Authorization: Bearer $IAC_RUNNER_BEARER" \
    http://<runner-host>:8125/v1/repos/homelab/pull
```

### `POST /v1/plan`

Submit a `tofu plan` job. Returns 202 + `Location: /v1/runs/{id}` immediately; `tofu init -input=false -no-color` and
`tofu plan -no-color -input=false -out=/data/runs/{run_id}/plan.tfplan` then run in a background worker.

Auth: required.

Request body: `{"repo": "<name>", "dir": "<subpath>"}`. `dir` is relative to `/data/repos/<name>/`; omitting it (or
passing `""`) means the repo root. Absolute paths, `..` segments and null bytes are rejected. An unknown field is a 400.

Response 202:

```json
{ "run_id": "ABC2345XYZ6789AB", "status": "queued" }
```

The `Location` header is a relative path (`/v1/runs/{id}`), not an absolute URL, so it resolves correctly whether the
add-on is reached directly or through the HA ingress proxy.

Errors: `run_invalid_dir` (400), `run_unknown_repo` (404), `git_clone_missing` (404 — the startup clone for that repo
failed; see the log for `git_clone_failed`), `run_tofu_not_found` (503), `apply_capacity_exhausted` (503 +
`Retry-After: 30`).

```bash
curl -sS -X POST -H "Authorization: Bearer $IAC_RUNNER_BEARER" \
    -H "Content-Type: application/json" \
    -d '{"repo":"homelab","dir":"envs/prod"}' \
    http://<runner-host>:8125/v1/plan
```

### `POST /v1/apply`

Submit a `tofu apply` job. Returns 202 + `Location: /v1/runs/{id}`; `tofu init` then
`tofu apply -no-color -input=false -auto-approve` run in a background worker. When the newest succeeded plan run for the
same `(repo, dir)` still has its `plan.tfplan` on disk **and was built against the commit the working tree is on now**,
that file is passed to `apply`; otherwise the apply runs inline (planning as part of the apply). Both modes are
supported by design.

A saved plan is used **at most once**, and only while it is still current:

- The plan run records the working tree's `HEAD` at plan time. A `POST /v1/repos/{name}/pull` (or any other commit
  change) between plan and apply makes the artifact ineligible, and the apply falls back to the inline mode instead of
  applying the previous revision's changes. The skip is logged as `jobq.plan_artifact_stale` with both SHAs.
- A successful apply consumes the artifact: `plan.tfplan` is deleted and the plan run's `plan_file` is cleared. A second
  apply with no intervening plan therefore runs inline rather than re-submitting a plan tofu has already applied (which
  tofu would reject as stale).
- When the commit cannot be determined at all (git could not answer), the artifact is skipped —
  `jobq.plan_freshness_unknown` — because an inline apply is the only safe default.

Auth: required. Request body and response: identical to `/v1/plan`.

Errors: the same set as `/v1/plan`. Additionally, the run itself can terminate with `apply_timeout` / `plan_timeout`
(the `apply_timeout_minutes` kill-chain fired), `apply_already_running` (another job held the per-repo lock longer than
`apply_timeout_minutes`) or `apply_failed` (tofu exited non-zero). Those codes appear in the run's `error_code` field,
not in the 202 response.

```bash
curl -sS -X POST -H "Authorization: Bearer $IAC_RUNNER_BEARER" \
    -H "Content-Type: application/json" \
    -d '{"repo":"homelab","dir":"envs/prod"}' \
    http://<runner-host>:8125/v1/apply
```

### `GET /v1/runs/{id}`

Return one run with paginated, secret-redacted output.

Auth: required. Query: `?page=<n>` (default 1), `?page_size=<n>` (default 100, max 1000). An unparseable value falls
back to the default rather than 400ing — a client walking pages should get the first page, not an error to decode.

Response 200:

```json
{
  "run_id": "ABC2345XYZ6789AB",
  "repo": "homelab",
  "dir": "envs/prod",
  "kind": "plan",
  "status": "succeeded",
  "exit_code": 0,
  "started_at": "2026-09-08T12:23:14Z",
  "finished_at": "2026-09-08T12:23:41Z",
  "output_lines": ["Initializing the backend...", "No changes. Your infrastructure matches the configuration."],
  "page": 1,
  "page_size": 100,
  "total_lines": 2
}
```

`status` is one of `queued`, `running`, `succeeded`, `failed`, `interrupted`. `exit_code` is `null` for a queued or
running run (never `0`, which would read as success). `finished_at` and `error_code` are omitted while absent.
`output_lines` are redacted at read time (see Output redaction below).

Errors: `run_unknown_id` (404 — the id is not 16 base32 characters), `run_not_found` (404 — well-formed id, no such
run), `apply_failed` (500 — a real filesystem failure; the detail stays in the add-on log).

```bash
curl -sS -H "Authorization: Bearer $IAC_RUNNER_BEARER" \
    "http://<runner-host>:8125/v1/runs/ABC2345XYZ6789AB?page=1&page_size=100"
```

### `GET /v1/runs`

List the most recent runs, newest-first by `started_at`.

Auth: required. Query: `?repo=<name>`, `?status=<queued|running|succeeded|failed|interrupted>`, `?limit=<n>` (default
20, max 100). An unknown `?repo=` yields an empty list rather than a 404 — "a repo with no runs" and "a repo nobody
configured" are the same answer to this question.

Response 200: `runs` is an array of the `GET /v1/runs/{id}` fields MINUS `output_lines` / `page` / `page_size` /
`total_lines` — listing 20 runs must not read 20 output logs. Fetch output per-run via `GET /v1/runs/{id}`.

```json
{ "runs": [], "count": 0, "limit": 20 }
```

Errors: `run_invalid_dir` (400 — `?status=` is not one of the five enum values; the message lists the valid values),
`apply_failed` (500 — a real filesystem failure).

```bash
curl -sS -H "Authorization: Bearer $IAC_RUNNER_BEARER" \
    "http://<runner-host>:8125/v1/runs?repo=homelab&status=interrupted&limit=50"
```

## error_code reference

Every 4xx/5xx body is `{"error_code": "<stable>", "message": "<human>"}` with an optional `request_id`. The `error_code`
is the contract — clients branch on it; `message` is human-readable, carries the operator-facing hint as its last
clause, and may be reworded between releases. New codes are additive: an older client will see codes it does not know,
so treat an unrecognized code as a generic failure rather than a parse error.

| error_code                  | HTTP                       | Meaning                                                                              |
| --------------------------- | -------------------------- | ------------------------------------------------------------------------------------ |
| `git_ssh_handshake`         | 403                        | SSH could not authenticate: deploy key missing/wrong, or host key not in known_hosts |
| `git_unauthorized`          | 403                        | The deploy key exists but has no access to the repo                                  |
| `git_non_fast_forward`      | 409                        | The local branch has diverged from the configured branch                             |
| `git_ref_not_found`         | 404                        | The configured `ref` does not exist on the remote                                    |
| `git_clone_missing`         | 404                        | No working tree at `/data/repos/<name>/` — the startup clone failed                  |
| `git_ref_pull_incompatible` | 400                        | `ff_only: true` was requested for a repo pinned via `ref`                            |
| `git_dns_failure`           | 502                        | The repo URL's hostname did not resolve                                              |
| `git_clone_failed`          | 502                        | Clone exhausted its 3 attempts, or an unclassified git failure (see the log)         |
| `run_unknown_repo`          | 404                        | `repo` / `{name}` is not in the `repos` Options list                                 |
| `run_unknown_id`            | 404                        | `{id}` is not 16 characters from the base32 alphabet (A-Z, 2-7)                      |
| `run_not_found`             | 404                        | `{id}` is well-formed but no such run exists                                         |
| `run_invalid_dir`           | 400                        | Malformed request body, a `dir` that is absolute / has `..`, or a bad `?status=`     |
| `run_tofu_not_found`        | 503                        | The `tofu` binary is missing from the image (`/healthz` reports `tofu_on_path`)      |
| `run_capacity_exhausted`    | 503                        | Reserved taxonomy slot; not emitted — see `apply_capacity_exhausted`                 |
| `apply_capacity_exhausted`  | 503 + `Retry-After: 30`    | Every `max_parallel_jobs` slot is in use; the request is refused, not queued         |
| `apply_already_running`     | run `error_code`           | Another job held the per-repo lock longer than `apply_timeout_minutes`               |
| `apply_timeout`             | run `error_code` (504 map) | `apply_timeout_minutes` expired during an apply; SIGTERM then SIGKILL                |
| `plan_timeout`              | run `error_code` (504 map) | Same, during a plan                                                                  |
| `apply_failed`              | 500 / run `error_code`     | tofu exited non-zero, or an unclassified server-side failure                         |
| `unauthorized`              | 401                        | Missing or invalid bearer token                                                      |

The four codes marked `run error_code` are terminal states of a run, not responses to the submitting request: the submit
already answered 202, so they surface in the `error_code` field of `GET /v1/runs/{id}`. The `(504 map)` note records the
status they would carry if a future endpoint ever returns them directly.

## Output redaction

`tofu` stdout/stderr is captured line-by-line to `/data/runs/{run_id}/output.log` (JSONL, one object per line) and
redacted at READ time, not write time: the raw log stays intact for post-mortem inside the container, and every line
served over HTTP is redacted by construction. The patterns are R2/AWS access keys (20-char upper-alnum), AWS secret keys
(40-char base64-ish) and SSH private-key headers (`-----BEGIN`).

Each `GET /v1/runs/{id}` emits one `redaction.audit` log record for the page it served, carrying the run id and the
number of redactions applied — so an operator can tell "nothing was redacted" from "redaction never ran". Grep the
add-on log for `redaction.audit` to audit it.

## Startup and shutdown records

The runner logs one structured JSON record per startup step. Grep these to diagnose a boot:

| Record                         | Meaning                                                                          |
| ------------------------------ | -------------------------------------------------------------------------------- |
| `bind_resolved`                | The bind IP was accepted (`bind_ip`, `allowed_subnets`)                          |
| `state_backend_ready`          | Backend, endpoint, bucket, region, `use_lockfile`                                |
| `keys_validated`               | `/data/keys/` passed the chmod-600 + ownership check                             |
| `repos_loaded`                 | Repo count + names + `key_issues` + the three int Options as the runner saw them |
| `git_clone_succeeded`          | Startup clone landed (`repo`, `attempts`)                                        |
| `git_clone_skipped`            | The working tree already existed; nothing was fetched                            |
| `git_clone_failed`             | All 3 attempts failed (1s/5s backoff); startup continues anyway                  |
| `runs_swept_interrupted`       | N runs left `running` by a previous container became `interrupted`               |
| `runs_rotated_at_boot`         | N run directories older than `runs_retention_hours` were reclaimed at boot       |
| `runs_retention_started`       | The retention ticker is armed (`runs_dir`, `retention_hours`)                    |
| `jobq_ready`                   | The job queue is up (`max_parallel_jobs`, `apply_timeout_minutes`)               |
| `iac_runner.token.issued`      | First start only — the plaintext bearer preview + token file path                |
| `listening`                    | The HTTP listener is bound                                                       |
| `shutdown_initiated`           | SIGTERM received; the 30s budget is split 25s HTTP drain + 5s job drain          |
| `runs_retention_stopped`       | The retention ticker goroutine was stopped                                       |
| `jobq_drain_deadline_exceeded` | A job was still in flight after the 5s drain budget (its own timeout owns it)    |
| `shutdown_complete`            | Clean exit                                                                       |

On `SIGHUP` the runner emits `iac_runner.log_reopen` and keeps running; the process never restarts itself.

## State backend use_lockfile semantics

For R2 and S3 backends, the runner invokes `tofu` with `use_lockfile = true` so locking uses the native S3 object-lock
semantics (no DynamoDB required). For the local backend, locking is file-based at `/data/terraform.tfstate.lock`. HA
Supervisor's backup integration covers both files automatically.

Apply fails fast with HTTP 423 (`locked`) when another apply holds the lock. The `use_lockfile` semantics for R2 were
verified empirically in Phase 16 (IRUN-H-1 spike result documented in `16-SUMMARY.md`).

## Log scrubbing

The runner's structured JSON logger (stdlib `log/slog`) wraps every record through a key-name scrubber
(case-insensitive). Values for the keys `Authorization`, `Bearer`, `token`, `password`, `key`, `secret` are replaced
with `"<redacted>"` before serialization. A unit test asserts the invariant; `chi` middleware additionally strips the
`Authorization` request header from the per-request log snapshot.
