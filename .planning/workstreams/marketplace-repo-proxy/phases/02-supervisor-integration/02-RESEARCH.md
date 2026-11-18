# Phase 2: Supervisor integration - Research

**Researched:** 2026-11-18
**Domain:** Home Assistant Supervisor store API (manager role), Python stdlib HTTP client, s6 service integration,
fake-Supervisor test harness, live E2E on the production host
**Confidence:** HIGH for the Supervisor contract (read from source at the spike commit and diffed against the
`2026.11.0` release tag), HIGH for Phase 1 integration points (read this session), MEDIUM for the E2E runbook (CLI
command names verified from `home-assistant/cli` 6.0.0 source; the production host's CLI/Supervisor versions were not
probed, by instruction)

Sources for every Supervisor claim: `home-assistant/supervisor` at commit `e610ca8` (2026-11-16, the spike commit). The
files `supervisor/api/store.py`, `supervisor/store/__init__.py`, `supervisor/store/git.py`,
`supervisor/store/repository.py`, `supervisor/api/middleware/security.py` and `supervisor/apps/utils.py` are
byte-identical at tag `2026.11.0` (diffed this session), so the store contract below holds for the released Supervisor.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Manifest and Supervisor client (MRP-07)
- **D-01:** `config.yaml` gets `hassio_api: true` and `hassio_role: manager` (SPIKE "Decisions": manager role in v1).
  No other API permission keys (`homeassistant_api`, `auth_api`, `docker_api`, `host_network`, ...) are added.
- **D-02:** Exactly one Supervisor client module. It holds an allow-list of `(method, path)` and refuses everything
  else before any network I/O: `GET /store/repositories`, `POST /store/repositories`,
  `DELETE /store/repositories/{slug}` (slug restricted to the Supervisor's repository-slug shape), `POST /store/reload`.
  No other module talks to the Supervisor.
- **D-03:** `SUPERVISOR_TOKEN` is read only by the process that makes Supervisor calls and never reaches lighttpd or
  access-watch (both already run under plain `#!/bin/sh` without the container environment). It never appears in logs,
  `status.json`, `access.json`, exceptions or test output.
- **D-04:** Every Supervisor call is logged (method, allow-listed path template, result/status code) without the token
  and without a full access hash. Store URLs in these log lines are masked like the startup log (Phase 1 D-17/D-27).

#### Self-registration (MRP-08)
- **D-05:** One system user per configured repository: user label `local`, `source: "system"` (Phase 1 already reserves
  the label and the source: `access.py` `RESERVED_USERS`, D-25). The hash is a normal random 128-bit access hash.
- **D-06:** When `register_local` is true and `GET /store/repositories` does not list the `local` user's internal store
  URL, the proxy adds it with `POST /store/repositories`. The internal URL uses the add-on's own hostname, as the
  Phase 1 startup log does.
- **D-07:** Registration only for repositories whose last sync is `ok` (a valid bare repository with `repository.yaml`),
  because the Supervisor clones the URL during the add and a failed first clone raises a resolution issue (SPIKE
  "Supervisor source findings", Boot).

#### Store reload (MRP-09)
- **D-08:** After a sync cycle in which at least one repository's refs changed, the proxy calls `POST /store/reload`.
  At most one reload per sync interval, also when manual "sync now" triggers run cycles more often. A failed reload is
  logged and retried no earlier than the next cycle that is allowed to reload.

#### Rotation and removal of the `local` user (MRP-10)
- **D-09:** Rotation: create the new hash, add the new internal URL to the store first, then try to remove the old store
  repository. Removal: try to remove the store repository. In both cases a refusal by the Supervisor (installed add-ons
  still use the repository, `StoreError ... used by installed apps`) is reported, never forced, and never retried in a
  loop. The proxy never calls anything that uninstalls add-ons.
- **D-10:** A leftover (old URL still registered because the Supervisor refused) is recorded in a machine-readable place
  that the Phase 3 GUI can show (registration status, MRP-13), and logged at warning level.
- **D-11:** The old access entry (and its symlink) of a rotated `local` user: SPIKE says "the old URL stops working right
  away" for rotations. For the `local` user this would break the leftover store repository's updates for still-installed
  add-ons. **Not decided here — see Open questions Q-2.**

#### Tests (manager brief)
- **D-12:** No test talks to a real Supervisor. pytest uses a fake Supervisor (stdlib HTTP server or injected
  transport); `internal/verify-marketplace-repo-proxy.sh` runs a fake Supervisor container on the verify network. The
  fake records every request so tests can prove the allow-list (only the four calls, nothing else) and the token's
  absence from lighttpd's process tree and from logs.
- **D-13:** The fake Supervisor should behave like the real one where it matters: the add call clones the URL
  (`git clone --depth 1`, as SPIKE "Clone") and rejects an invalid repository; removal can be configured to refuse with
  the "used by installed apps" error.

#### Live E2E (MRP-11, manager brief)
- **D-14:** The live E2E is its own plan, `autonomous: false`, last in the phase. It runs on the production host
  (named only "production host" in every file and commit message) through the `ha` wrapper (SSH); tests never touch it.
- **D-15:** There is a checkpoint before **every** action on the host; the user approves each one through the manager.
  Sequence: add the store repository (via the proxy's self-registration) → install a test add-on from it → change
  upstream → update visible in the store (proves MRP-09 without waiting for the 3-hour Supervisor reload) → full
  cleanup (test add-on uninstalled, store repository removed, proxy configuration back to its prior state).
- **D-16:** No restart of Home Assistant Core or the Supervisor without explicit approval. A refused removal during
  cleanup is the expected MRP-10 behaviour while the test add-on is installed; cleanup order is uninstall first, then
  remove the store repository.
- **D-17:** Evidence written to the plan SUMMARY contains no hostnames, IPs, access hashes, tokens, e-mail addresses or
  person names; store URLs are masked.

#### Release and docs
- **D-18:** Subpatch bump to `0.1.0-2` at the end of the phase through
  `make update-version ADDON=marketplace-repo-proxy VERSION=0.1.0-2 NO_TAG=yes` (never by hand). CHANGELOG.md gets
  `## [0.1.0-2] - <date>`. No tag in the plan; the manager tags after the squash merge onto `main` (Phase 1 D-32).
- **D-19:** DOCS.md documents `register_local` (now effective), self-registration, store reload, rotation/removal of the
  `local` user and the leftover report, and replaces "No effect yet". Whether DOCS.md/README.md need an explicit warning
  about `hassio_role: manager` and the security rating is a research item (manager brief); the recommendation is in
  Open questions Q-4.

#### Repository rules (CLAUDE.md)
- **D-20:** HA base image only. Any Dockerfile change is verified with a local `docker build` before commit.
- **D-21:** Versions only via `make update-version`.
- **D-22:** Docker verify scripts must not run in two worktrees at the same time.
- **D-23:** Public repository: no hostnames, IPs, e-mail addresses, person names or tokens in files or commit messages.

### Claude's Discretion
- Which process makes the Supervisor calls. SPIKE: the token "stays in the `gui`/`sync` processes". A natural choice is
  the sync service (it already runs `with-contenv` and knows when refs changed); requests from the CLI (and later the
  GUI) could reach it through a request file like the Phase 1 sync trigger. The planner decides, within D-02/D-03.
- HTTP client (stdlib `urllib.request` is enough; no new Python package), timeouts, response parsing.
- How to detect "refs changed" (compare the fetched branch tip before/after per repository).
- Where the registration state lives (`status.json` extension or a new `/data/supervisor.json`), within D-10, and its
  field names. It is a contract the Phase 3 GUI consumes, so it is documented like the Phase 1 contracts.
- How the operator triggers rotation/removal of the `local` user in Phase 2 (no GUI yet), for example a new `mrp`
  subcommand that is allowed to act on `local` only through the Supervisor-aware path.
- How the verify script provides the fake Supervisor (container with network alias `supervisor`, or a test-only base-URL
  override via environment like the Phase 1 upstream override; an override must not be reachable through add-on
  options).
- Wave layout, as long as the E2E plan is last and the bump happens once at the end of the code work.

### Open Questions (from CONTEXT.md, not decided; answered as recommendations in "Open Questions" below)
- **Q-1** E2E install source and order · **Q-2** old `local` URL after rotation · **Q-3** removal triggers ·
  **Q-4** manager-role warning · **Q-5** E2E test repository

### Deferred Ideas (OUT OF SCOPE)
- Registration status view and leftover display in the GUI (Phase 3, MRP-13).
- Phase 1 review findings WR-01, WR-04, IN-01 to IN-07 (user decision 2026-11-18).
- Manual sync trigger via `stdin` (Phase 1 D-29).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MRP-07 | `hassio_api: true`, `hassio_role: manager`; one Supervisor client module with an allow-list (`GET/POST /store/repositories`, `DELETE /store/repositories/{slug}`, `POST /store/reload`) | Role matrix (manager needed, `hassio_api` needed too), exact paths (V1 root, not `/v2`), slug shape `^[0-9a-f]{8}$`, envelope + non-JSON 401/403, urllib hardening (no proxy, no redirect) — sections "Supervisor store API contract", Pattern 1 |
| MRP-08 | `local` system user per repository; internal URL added when `register_local` and missing | Hostname = `socket.gethostname()` = `{repo-hash}-marketplace-repo-proxy` (verified formula); `POST` is synchronous and clones; 409 = already present; match by slug `sha1(url.lower())[:8]` or `source`, never by `url` — Pattern 2 |
| MRP-09 | `POST /store/reload` after a sync that changed refs, at most once per interval | "Changed" must compare the served `head` against the carried `status.json` head (bare repos are rebuilt per container start); reload is blocking and pulls every store repository; rate limiter with pending flag — Pattern 3, Pitfall 1 |
| MRP-10 | Rotation/removal add-first, refusal reported, never forced | Exact refusal: HTTP 400, message `Can't remove '<source>'. It's used by installed apps` (contains the full URL); retired `local.<slug>` entry keeps serving (Q-2); leftovers in `/data/supervisor.json`; request queue for the CLI — Pattern 4 |
| MRP-11 | Live E2E with cleanup | `ha` CLI mapping, test add-on minimum, update visibility via `update_available`, job conditions that block add/reload, cleanup order, Q-1 options — section "Live E2E runbook" |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Ask first on critical tasks (version bumps, CI/CD, deployment); push back on risky plans.
- Local `docker build` before committing any Dockerfile change (this phase should need none; see Standard Stack).
- No `Co-Authored-By` or AI attribution in commits or PR descriptions.
- One add-on per branch, stage by path (`git add marketplace-repo-proxy/ internal/ ...`), never `git add -A`.
- In this worktree write only workstream files under `.planning/`; `STATE.md`/`ROADMAP.md` at the repository root of
  `.planning/` only in the main worktree.
- Docker verify scripts must not run in two worktrees at the same time.
- Versions only through `make update-version` (3-file sync); `config.yaml` carries the subpatch.
- HA base images only; no bundled upstream source (not applicable: own code, `admin-ui`/`haos-monitor`-style exception
  is documented for this add-on in DOCS.md).
- Linting: YAML 2-space/120 chars, Markdown 120 chars (prettier `proseWrap: always`), shellcheck with SC1091/SC2034
  ignored, Python conventions (module docstring, type hints, `pathlib`, `argparse` with `RawDescriptionHelpFormatter`,
  `if __name__ == "__main__": sys.exit(main())`, `flush=True` in containerized prints).
- Start work through GSD commands; public repository: no hostnames, IPs, e-mail addresses, person names or tokens.
- User-level: code/comments/commits in English; never touch Home Assistant hosts directly outside approved E2E steps.

## Summary

The Supervisor's store API is small, stable and fully readable from source. All four allow-listed calls live on the V1
root (`http://supervisor/store/...`); `/store.*` is reachable only with `hassio_api: true` **and**
`hassio_role: manager` (the default role allows only `/.+/info`). `POST /store/repositories` is synchronous: it clones
the URL (`git clone --depth 1`), validates `repository.yaml`, persists the URL and re-reads the store before it answers
`{"result":"ok","data":{}}`; a duplicate gets HTTP 409 with `error_key: store_repository_already_added_error`.
`DELETE /store/repositories/{slug}` refuses a repository used by installed add-ons with HTTP 400 and the message
`Can't remove '<full source URL>'. It's used by installed apps` — the message carries the full store URL including the
access hash, so the proxy must mask every Supervisor error text before it logs or stores it. `POST /store/reload` pulls
**every** store repository (GitHub ones too) and only returns when all pulls are done; it notifies Core with a
`STORE_RELOADED` WebSocket event, which is what makes the update visible within minutes.

Two findings change the plan beyond the SPIKE. First, "refs changed" cannot be taken from the bare-repository snapshot
alone: `/srv/git` lives in the container filesystem, so the first cycle after every add-on start reports
`refs_changed: true` and would trigger a store reload on every restart. The reliable signal is "served `head` differs
from the `head` carried in `/data/status.json`". Second, Supervisor `main` (after the `2026.11.0` release) adds a per-add-on
Unix socket (`SUPERVISOR_SOCKET=/run/supervisor/api/supervisor.sock`) and a `supervisor_api_tcp` flag; the TCP API with
`SUPERVISOR_TOKEN` stays the default "until late in the deprecation cycle". Phase 2 should use TCP (the production host
runs a release without the add-on socket) and keep the transport in one function so a socket transport can be added
later.

The security rating drops by exactly one point: base 5, +2 (no ingress, no published port, no host network), AppArmor
default 0, unsigned 0, manager −1 → **6** (Phase 1 manifest: **7**). DOCS.md should carry a security note (Q-4: yes).

**Primary recommendation:** Put the Supervisor client (`app/supervisor.py`, allow-list + transport) and the
registration/reload/rotation logic (`app/registration.py`) into the existing `sync` process, driven after each cycle and
by a request-file queue that `mrp local ...` writes; persist registration state and leftovers in a new single-writer
contract `/data/supervisor.json`; test against one stdlib fake Supervisor module reused by pytest (in-process) and the
verify script (container with network alias `supervisor`).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Supervisor API calls (allow-list, token) | `sync` s6 service (Python, `with-contenv`) | — | Only process with the container env besides init; already the single writer of `status.json`; knows when heads change (D-03) |
| `local` system user (hash, symlink) | `/data/access.json` via `AccessStore` | `access-watch` (reconciles links) | Existing multi-process-safe writer (RLock + flock); no new writer API needed |
| Registration/leftover state | `/data/supervisor.json` (new contract) | `status.json` unchanged | Single writer (`sync`), read by CLI now and the Phase 3 GUI later (D-10) |
| Operator actions (rotate/remove/status) | `mrp` CLI → request file in `/run/marketplace-repo-proxy/` | `sync` executes | CLI must never call the Supervisor (D-02/D-03), though `docker exec` gives it the token env |
| Store add/remove/reload | Home Assistant Supervisor (external) | Core (update entities via WS event) | The proxy only asks; refusal is final (D-09) |
| Serving the store URL | lighttpd + `git http-backend` (unchanged) | — | No token, no change in Phase 2 |
| Tests | pytest (in-process fake) / verify script (fake container) | — | D-12/D-13 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `urllib.request` / `http.client` | Alpine `python3` in `amd64-base:3.24` (already in the image) | Supervisor HTTP client | No new package (CONTEXT discretion); full control over proxies and redirects |
| Python stdlib `http.server.ThreadingHTTPServer` | same | Fake Supervisor (pytest and verify) | D-12; no dependency; the verify image already has `python3` and `git` |
| Python stdlib `hashlib` | same | `sha1(url.lower()).hexdigest()[:8]` store slug | Same formula as the Supervisor [VERIFIED: supervisor@e610ca8 supervisor/store/utils.py:9-12] |

Existing test toolchain (unchanged): `pytest==9.1.1`, `pyyaml==6.0.3` (CI job `marketplace-repo-proxy` in
`.github/workflows/lint.yml`, Python 3.12) [VERIFIED: .github/workflows/lint.yml:297-317, read this session].

**No Dockerfile change is needed** (no new apk package, no new file outside `app/` and `rootfs/`, which are already
copied). If the planner adds an s6 service or touches `rootfs/`, the image changes but the Dockerfile does not; the
verify script builds the image anyway.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| TCP `http://supervisor` + `Authorization: Bearer $SUPERVISOR_TOKEN` | Unix socket `$SUPERVISOR_SOCKET` (no token) | Socket only exists on Supervisor builds after `2026.11.0` [VERIFIED: socket env absent at tag 2026.11.0 `supervisor/docker/app.py` environment, present on `main`]; production host not probed. Socket mode is 0600 root [VERIFIED: supervisor@e610ca8 supervisor/api/sockets.py:77-78], so lighttpd (`lighttpd` user) could not use it. Recommend: TCP now, socket as a deferred follow-up (Open question Q-6) |
| Supervisor calls inside `sync` | New s6 longrun `registrar` with the token, `sync` stripped of it | Separates PAT holder from manager-token holder, decouples rotation latency from long fetches; costs IPC (registrar must read `status.json`) and a new service. `sync` already holds the token today (`with-contenv`) and git children never inherit it (envs are built from scratch, `app/gitops.py:28-35,79-96`) |
| Network alias `supervisor` for the verify fake | Test-only base-URL env override | Alias exercises the production code path unchanged and adds no override surface (Phase 1 needed `MRP_TEST_UPSTREAM_BASE` only because GitHub cannot be aliased) |

**Installation:** none.

## Package Legitimacy Audit

No external packages are installed in this phase (stdlib only; test pins unchanged).

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| — | — | — | — | — | — | — |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Supervisor store API contract

All verbatim quotes from `home-assistant/supervisor@e610ca8` (identical at `2026.11.0` for the files named above).

### Routes, base URL, auth, envelope

- Routes are registered for every API version on the root app [VERIFIED: supervisor/api/__init__.py:1099-1117]:
  `web.post("/store/reload", api_store.reload)`, `web.get("/store/repositories", api_store.repositories_list)`,
  `web.post("/store/repositories", api_store.add_repository)`,
  `web.delete("/store/repositories/{repository}", api_store.remove_repository)`. V2 is a sub-app "mounted at /v2",
  feature-flagged (`FeatureFlag.SUPERVISOR_V2_API`) [VERIFIED: supervisor/api/__init__.py:114-131,182]. **Use the root
  paths, never `/v2`.**
- Base URL `http://supervisor` (port 80) [ASSUMED: standard add-on convention; not in the files read].
- Token headers accepted [VERIFIED: supervisor/api/utils.py:99-112, supervisor/const.py:116-117]: `X-Supervisor-Token`,
  legacy `X-Hassio-Key`, or `Authorization` (value after the last space: `supervisor_token.split(" ")[-1]`). Use
  `Authorization: Bearer <token>`.
- The container env carries both `SUPERVISOR_TOKEN` and `HASSIO_TOKEN` with the same value
  [VERIFIED: supervisor@2026.11.0 supervisor/docker/app.py:235-240, `ENV_TOKEN: self.app.supervisor_token,
  ENV_TOKEN_OLD: self.app.supervisor_token`; names `ENV_TOKEN = "SUPERVISOR_TOKEN"`, `ENV_TOKEN_OLD = "HASSIO_TOKEN"`
  in supervisor/docker/const.py:168-169]. The redactor and the verify `/proc` scans must cover **both** names.
- Success envelope: `{"result": "ok", "data": <dict|list>}`; a handler returning `None` gives `"data": {}`
  [VERIFIED: supervisor/api/utils.py:190-198,339-344 `{JSON_RESULT: RESULT_OK, JSON_DATA: data or {}}`].
- Error envelope (JSON): `{"result": "error", "message": ..., ["error_key": ..., "extra_fields": {...}]}`, default HTTP
  400 [VERIFIED: supervisor/api/utils.py:291-336; constants `JSON_RESULT = "result"`, `JSON_MESSAGE = "message"`,
  `JSON_ERROR_KEY = "error_key"`, `JSON_EXTRA_FIELDS = "extra_fields"`, `RESULT_ERROR = "error"`, `RESULT_OK = "ok"`
  in supervisor/const.py:102-110].
- **Non-JSON errors:** missing token → `HTTPUnauthorized` (401), invalid token / missing role / missing `hassio_api`
  → `HTTPForbidden` (403), filtered path → `HTTPBadRequest` (400), raised in middleware
  [VERIFIED: supervisor/api/middleware/security.py:298-302,364-376,447-462]. aiohttp renders these as plain text, not
  the envelope [ASSUMED: aiohttp default for `web_exceptions`]. The client must parse a non-JSON body as an error with
  the status code only.
- A Supervisor not in a valid API state answers 400 with `System is not ready with state: ...`
  [VERIFIED: supervisor/api/middleware/security.py:318-321]: transient, retry next cycle.

### Role check (Q: does `hassio_api` alone suffice?)

`check_principal_access` for an add-on [VERIFIED: supervisor/api/middleware/security.py:447-462]:

```text
if patterns.api_bypass.match(request.path): return
if principal.access_hassio_api:
    if patterns.role_access[principal.hassio_role].match(request.path): return
    _LOGGER.warning("%s no role for %s", request.path, principal.slug)
else:
    _LOGGER.warning("%s missing API permission for %s", principal.slug, request.path)
raise HTTPForbidden
```

- `ROLE_DEFAULT` allows only `r"|/.+/info"`; `ROLE_MANAGER` includes `r"|/store.*"` (plus `/addons/<slug>/...` except
  `security`, `/backups.*`, `/core/.+`, `/homeassistant/.+`, `/host/.+`, `/os/(?!datadisk/wipe|ssh/authorized_keys).+`,
  `/supervisor/.+`, `/docker/.+`, `/mounts.*`, `/network/.+` and more) [VERIFIED: supervisor/api/middleware/security.py:123-171].
- Result: `hassio_api: true` without a role → 403 on every `/store/...` call; `hassio_role: manager` without
  `hassio_api` → 403 ("missing API permission"). **Both keys are required** (D-01 is correct).
- Valid roles: `ROLE_ALL = [ROLE_DEFAULT, ROLE_HOMEASSISTANT, ROLE_BACKUP, ROLE_MANAGER, ROLE_ADMIN]`, manifest default
  `vol.Optional(ATTR_HASSIO_ROLE, default=ROLE_DEFAULT)`, `vol.Optional(ATTR_HASSIO_API, default=False)`
  [VERIFIED: supervisor/const.py:485-491; supervisor/apps/validate.py:523-524].

### `GET /store/repositories`

Returns a list over `self.sys_store.all`, each item [VERIFIED: supervisor/api/store.py:163-173,348-354]:

```python
{ATTR_SLUG: repository.slug, ATTR_NAME: repository.name, ATTR_SOURCE: repository.source,
 ATTR_URL: repository.url, ATTR_MAINTAINER: repository.maintainer}
```

- `slug`: `sha1(source.lower())[:8]` for custom repositories; builtins have fixed slugs (`core`, `local`, `a0d7b954`,
  `5c53de3b`, `d5369777`) [VERIFIED: supervisor/store/utils.py:9-12, supervisor/store/const.py:24-45].
- `source`: the URL string as added (after `.strip()`) [VERIFIED: supervisor/store/repository.py:40,
  supervisor/store/validate.py:22-25].
- `url`: **from the served `repository.yaml`** (`self.data.get(ATTR_URL, self.source)`), `name` and `maintainer` too
  (default `"unknown"`) [VERIFIED: supervisor/store/repository.py:89-102]. **Never match the proxy's entries by `url`**;
  match by `slug` (what the Supervisor itself uses for duplicates) and confirm with `source`.
- The response contains every registered URL in full (capabilities). Never log it; keep only the proxy's own slugs.

### `POST /store/repositories`

- Body `{"repository": "<url>"}`, validated by `SCHEMA_ADD_REPOSITORY = vol.Schema({vol.Required(ATTR_REPOSITORY):
  vol.All(str, validate_repository)})` [VERIFIED: supervisor/api/store.py:71-73]. `validate_repository` strips, matches
  `RE_REPOSITORY`, then `vol.Url()` [VERIFIED: supervisor/store/validate.py:20-35]. The proxy's
  `http://<host>:8080/repo/<o>/<r>/<hash>` passes (SPIKE live run).
- **Synchronous:** `await asyncio.shield(self.sys_store.add_repository(...))` [VERIFIED: supervisor/api/store.py:364-368].
  `_add_repository` → `Repository.create` → duplicate check by slug → `repository.load()` (clone when the folder is
  missing) → `validate()` (repository.yaml with `name`) → store, `save_data()`, `data.update()`, `_read_apps()`
  [VERIFIED: supervisor/store/__init__.py:153-253]. The answer comes after the clone and the store refresh. `shield`
  means a client timeout does **not** cancel the add: on timeout, re-`GET` before retrying.
- Job conditions on the add: `INTERNET_SYSTEM`, `SUPERVISOR_UPDATED`, `OS_SUPPORTED`, `HOME_ASSISTANT_CORE_SUPPORTED`;
  failure → `StoreJobError` [VERIFIED: supervisor/store/__init__.py:143-152]; the clone itself also needs
  `FREE_SPACE` and `INTERNET_SYSTEM` [VERIFIED: supervisor/store/git.py:141-145]. A pending Supervisor update blocks
  registration (E2E pitfall).
- Responses:

  | Case | HTTP | Body |
  |------|------|------|
  | Added | 200 | `{"result":"ok","data":{}}` |
  | Duplicate (same slug) | 409 | `error_key: "store_repository_already_added_error"`, `message: "Can't add {url}, already in the store"`, `extra_fields: {"url": ...}` [VERIFIED: supervisor/exceptions.py:2133-2142; tests/api/test_store.py:133-145] |
  | Schema-invalid URL | 400 | humanized voluptuous message [VERIFIED: supervisor/api/utils.py:347-360] |
  | Clone failed | 400 | message from the exception chain, i.e. git's `CommandError` text (contains the URL) [VERIFIED: supervisor/store/git.py:209-216; supervisor/utils/__init__.py:82-90]; the failed folder is removed, **no resolution issue** on the API path (`issue_on_error=False`) [VERIFIED: supervisor/store/__init__.py:170-183] |
  | No valid `repository.yaml` | 400 | `"{url} is not a valid app repository"` [VERIFIED: supervisor/store/__init__.py:236-240] |
  | Job condition failed | 400 | `StoreJobError` message |

  Every 400 message can contain the full URL with the hash: mask before logging or storing (Pitfall 3).

### `DELETE /store/repositories/{repository}`

- Path parameter is the **slug** (`request.match_info["repository"]`); unknown slug → 404 envelope
  `"Repository {slug} does not exist in the store"` [VERIFIED: supervisor/api/store.py:103-112;
  tests/api/test_store.py:546-561].
- Refusal [VERIFIED: supervisor/store/__init__.py:262-266]:

  ```python
  if repository.slug in (app.repository for app in self.sys_apps.installed):
      raise StoreError(
          f"Can't remove '{repository.source}'. It's used by installed apps",
  ```

  `StoreError` is a plain `HassioError`, not an `APIError` [VERIFIED: supervisor/exceptions.py:2101-2103], so
  `api_process` takes the generic branch: `_LOGGER.exception("Unexpected error during API call: %s", err)`, Sentry
  capture, HTTP **400** with that message and **no** `error_key` [VERIFIED: supervisor/api/utils.py:184-188]. Detect
  the refusal by `status == 400` and the substring `It's used by installed apps`. Sentry events are dropped unless the
  user enabled diagnostics [VERIFIED: supervisor/misc/filter.py:67-69 `if not coresys.config.diagnostics ... return
  None`].
- Success → 200 `{"result":"ok","data":{}}`; the Supervisor deletes its clone folder and the URL from its `store.json`
  [VERIFIED: supervisor/store/__init__.py:267-273; supervisor/store/git.py:302-319].
- Builtins → `StoreInvalidAppRepo("Can't remove built-in repositories!")` (400). The allow-list slug pattern
  `^[0-9a-f]{8}$` excludes `core`/`local` but not the three hex builtins: only ever delete slugs the proxy computed from
  its own URLs.

### `POST /store/reload`

- `await asyncio.shield(self.sys_store.reload())` [VERIFIED: supervisor/api/store.py:182-185]: blocking until every
  repository has been pulled. Job conditions: `SUPERVISOR_UPDATED`, `OS_SUPPORTED`, `HOME_ASSISTANT_CORE_SUPPORTED`
  [VERIFIED: supervisor/store/__init__.py:92-100].
- It pulls **all** repositories (`self.all.copy()`), errors per repository are logged and swallowed
  (`return_exceptions=True`), so the call returns 200 even when the proxy's repository failed to pull; updated
  repositories are re-read and Core gets `WSEvent.STORE_RELOADED` "so add-on update entities pick up the newly loaded
  store data" [VERIFIED: supervisor/store/__init__.py:101-141].
- Per-repository pull: `ls-remote --heads`, `fetch --update-shallow --depth 1`, compare, `reset --hard` only when
  changed; needs `FREE_SPACE` + `INTERNET_SYSTEM`; skipped with a warning when the repository lock is held
  [VERIFIED: supervisor/store/git.py:218-300]. An `ls-remote` failure (proxy down, revoked hash) only logs a warning; a
  fetch failure after a successful `ls-remote` raises a `CORRUPT_REPOSITORY` issue [VERIFIED: supervisor/store/git.py:239-299].
- The Supervisor's own cadence: `RUN_RELOAD_APPS = 10800` [VERIFIED: supervisor/misc/tasks.py:38,79].
- The Supervisor logs the full URL at info level on every clone/pull (`"Cloning app %s repository from %s"`,
  `"Update app %s repository from %s"`) [VERIFIED: supervisor/store/git.py:199,235]. Document: the Supervisor log shows
  registered store URLs.

### Hostname and store URL identity

- Container hostname = `self.app.hostname` unless the add-on uses the host UTS namespace
  [VERIFIED: supervisor/docker/app.py:719-720]; `hostname` = `self.slug.replace("_", "-")`
  [VERIFIED: supervisor/apps/model.py:253-255]; add-on slug = `f"{repository}_{app[ATTR_SLUG]}"`
  [VERIFIED: supervisor/store/data.py:241] where `repository` is the store slug (8 hex for this repository, `local` for
  local add-ons). Manifest slug `marketplace_repo_proxy` [VERIFIED: marketplace-repo-proxy/config.yaml:5].
  → `{repo-hash}-marketplace-repo-proxy` (repository install) and `local-marketplace-repo-proxy` (local copy).
  `socket.gethostname()` (Phase 1 `app/cli.py:270`, `app/init.py:80`) returns exactly that; `/addons/self/info` is not
  needed. The DNS name is registered under the same hostname [VERIFIED: supervisor/docker/app.py:759-762].
- Store identity = `sha1(url.lower())[:8]` of the full URL string. Any change of host, port, path, hash, query or
  `#branch` is a different store repository.

## Architecture Patterns

### System Architecture Diagram

```text
                   upstream (GitHub)                                 Home Assistant Supervisor
                         │ fetch (PAT)                                  ▲   │ clone/pull smart HTTP
                         ▼                                              │   ▼
 ┌──────────────────────────── sync process (with-contenv) ─────────────┼───────────────┐   lighttpd :8080
 │ wait loop: interval | sync.request | supervisor request | reload due │               │   (no token)
 │   │                                                                  │               │       ▲
 │   ├─ run_cycle ──► status.json (head, refs, status)                  │               │       │ /srv/git/access
 │   │       └─ head_changed? (new head != carried head) ─┐             │               │       │
 │   ├─ registration pass (after every cycle) ◄───────────┘             │               │
 │   │     for each repo with status ok and register_local:            │               │
 │   │       ensure `local` entry (AccessStore, source system) ─────────┼──► access.json ┼──► access-watch
 │   │       GET /store/repositories ── slug present? ── no ─► POST ────┘               │      (reconcile links)
 │   ├─ reload gate: changed && (never reloaded || interval elapsed) ─► POST /store/reload
 │   │       else reload_pending = true (handled when the gate opens)  │
 │   └─ request queue (/run/.../supervisor.requests/*.json from mrp)    │
 │         rotate: retire `local`→`local.<slug>`, add new `local`, POST new, DELETE old slug
 │         remove: DELETE slug; refusal → leftover (never retried in a loop)
 │   all calls ─► app/supervisor.py (allow-list → transport) ─► http://supervisor
 │   results ─► /data/supervisor.json (registration, reload, leftovers, request results)
 └──────────────────────────────────────────────────────────────────────────────────────┘
        ▲ request file                       │ read
   mrp local rotate|remove|status (docker exec; never calls the Supervisor)
```

### Recommended Project Structure

```text
marketplace-repo-proxy/
├── app/
│   ├── supervisor.py       # NEW: the only Supervisor client (allow-list, transport, envelope parsing, masking)
│   ├── registration.py     # NEW: local user, register, reload gate, rotate/remove, leftovers, request queue
│   ├── supervisor_state.py # NEW (or inside registration.py): /data/supervisor.json writer (single writer: sync)
│   ├── sync.py             # CHANGED: call registration after each cycle; wait loop gets request/reload reasons
│   ├── access.py           # CHANGED: reserved labels `local` and `local.*`; revoke of reserved labels blocked for CLI
│   ├── cli.py              # CHANGED: `mrp local status|rotate|remove [--revoke-old]`; never imports supervisor.py
│   ├── paths.py            # CHANGED: supervisor_state_file, supervisor_requests_dir
│   └── logsetup.py         # unchanged (already masks standalone 32-hex runs)
├── tests/
│   ├── fake_supervisor.py  # NEW: stdlib fake, importable by pytest and runnable as a script in the verify container
│   ├── test_supervisor.py  # NEW: client allow-list, envelope, hardening
│   ├── test_registration.py# NEW: register, reload gate, rotation/removal, leftovers, queue
│   └── test_cli.py, test_sync.py, test_access.py (extended)
├── config.yaml             # hassio_api: true, hassio_role: manager
└── DOCS.md, README.md, CHANGELOG.md, translations/{en,de}.yaml
internal/verify-marketplace-repo-proxy.sh  # extended: fake Supervisor container (alias `supervisor`)
```

### Pattern 1: Allow-listed client with a hardened stdlib transport

**What:** One module owns every Supervisor request. The allow-list is checked against `(method, template)` and the
parameter regex before a URL is even built; the token is read lazily from `os.environ["SUPERVISOR_TOKEN"]`; the opener
ignores proxy env vars and refuses redirects.
**When to use:** Every Supervisor call (D-02).

```python
# Pattern sketch (stdlib only); names are suggestions, not a contract
import json, re, urllib.error, urllib.request

ALLOWED = {
    ("GET", "/store/repositories"),
    ("POST", "/store/repositories"),
    ("DELETE", "/store/repositories/{slug}"),
    ("POST", "/store/reload"),
}
SLUG_RE = re.compile(r"[0-9a-f]{8}")  # use fullmatch (Phase 1 WR-02: `^...$` accepts a trailing newline)

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # never follow: the token must not travel elsewhere
        return None

def _opener() -> urllib.request.OpenerDirector:
    # ProxyHandler({}) ignores http_proxy/HTTP_PROXY from the container environment
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

def call(method: str, template: str, *, slug: str | None = None, body: dict | None = None,
         base: str = "http://supervisor", token: str | None = None, timeout: float = 30.0):
    if (method, template) not in ALLOWED:
        raise SupervisorRefused("not_allowed")            # before any I/O
    path = template
    if "{slug}" in template:
        if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
            raise SupervisorRefused("invalid_slug")
        path = template.replace("{slug}", slug)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_unredirected_header("Authorization", "Bearer " + (token or _token()))
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with _opener().open(req, timeout=timeout) as resp:
            return _parse(resp.status, resp.read())
    except urllib.error.HTTPError as exc:                  # 4xx/5xx: envelope or plain text
        return _parse(exc.code, exc.read())
```

Return a small result object `(ok, status, data, error_key, message)` where `message` has already passed the masking
function (Pattern 5). Log one line per call: `supervisor GET /store/repositories: 200` (template, never the filled URL
with a hash; the slug is not secret but keep the template for D-04).

### Pattern 2: Registration pass (MRP-08)

After every cycle, for each configured repository with `status == "ok"` (D-07; `no_repository_yaml` is excluded) and
`register_local` true:

1. Ensure the `local` entry exists: `AccessStore.add(spec.slug, "local", source="system", specs=options.repositories)`
   (catch `user_exists`). The hash then persists in `/data/access.json` across restarts and backups.
2. Build `url = store_url(internal_base(socket.gethostname()), owner, name, hash)` and
   `slug = sha1(url.lower())[:8]`.
3. `GET /store/repositories` once per pass (not per repository). Present when an item has `slug == slug` (confirm
   `source == url`). If present → record `registered`.
4. Missing → `POST` with a long timeout (≥120 s: clone + store re-read). 200 or 409 → `registered`. Any other result →
   `failed` with masked message; retry at the next cycle (a cycle is ≥5 minutes apart). Log at warning only when the
   state changes, to avoid a warning every cycle for a persistent failure.

Do not reload after a registration: the add already cloned the current head.

### Pattern 3: Reload gate (MRP-09)

- **Changed** = for a repository with a success status, the new `head` differs from the `head` the `StatusWriter`
  carried from the previous `status.json` (or the branch changed), and a previous head existed. First-ever syncs and
  container restarts with an unchanged upstream do not count. (Phase 1's `refs_changed` stays as is in `status.json`; it
  is `true` on every first cycle after a container start, see Pitfall 1.)
- Gate state in memory: `last_reload_at` (monotonic, `None` at start), `reload_pending`. When a cycle changed something:
  if `last_reload_at is None or now - last_reload_at >= interval_seconds` → `POST /store/reload` (timeout ≥300 s: it
  pulls every repository), set `last_reload_at = now` whatever the result (D-08: a failed reload waits for the next
  allowed window); else set `reload_pending = True`.
- The wait loop returns a `reload` reason when `reload_pending` and the window opened, so a change seen during a busy
  window is not lost even if no further cycle runs. Persist `last_requested`/`last_result` in `supervisor.json` for the
  GUI.
- Only reload when the repository is registered (otherwise the reload cannot help); skip silently when
  `register_local` is false and no proxy URL is in the store.

### Pattern 4: Rotation and removal through a request queue (MRP-10)

- **CLI → sync:** `mrp local rotate <owner/repo>` / `mrp local remove <owner/repo> [--revoke-old]` write
  `/run/marketplace-repo-proxy/supervisor.requests/<id>.json` atomically (`{"id", "action", "repository", "created"}`;
  dir 0700, files 0600). The sync wait loop polls the directory like `sync.request`, validates action and repository
  (configured, or known from `supervisor.json`/`access.json`), executes, deletes the file and stores the result under
  `requests` in `supervisor.json`. The CLI waits up to ~30 s for its id and prints the outcome, otherwise `queued`
  (a running fetch can delay execution up to the git timeout).
- **Rotate:** under the access lock, rename the current `local` entry to `local.<oldslug>` (keeps hash, `source:
  system`) and add a new `local` entry; reconcile (both links exist). `POST` the new URL. Only if that returns 200/409:
  `DELETE` the old slug. 200 or 404 → revoke `local.<oldslug>` (old URL 404 from the next request) and drop the
  leftover. 400 with `It's used by installed apps` → leftover `{repository, store_slug, user: "local.<oldslug>",
  masked_url, since, reason: "in_use"}`, warning log, no automatic retry. Any other error → leftover with
  `reason: "error"`. If the `POST` fails, keep the old registration untouched and report.
- **Remove:** `DELETE` the current slug; 200/404 → revoke `local` and stop registering this repository only if
  `register_local` is false or the repository is no longer configured (Q-3); with `register_local` true and the
  repository configured, refuse with `register_local_enabled` (otherwise the next cycle re-adds a new URL). Refusal →
  leftover, entry kept.
- **Leftover resolution without a retry loop:** every registration pass already has the `GET` list; a leftover slug that
  is no longer listed (the operator removed it in the UI after uninstalling the add-ons) is dropped and its retired
  entry revoked. An explicit `mrp local remove`/`rotate` retry is the only path that calls `DELETE` again.
- **Reserved labels:** extend Phase 1's `RESERVED_USERS` check to `local` and `local.*` for every non-system source, and
  refuse `mrp users revoke <repo> local` (`user_reserved`; point to `mrp local remove`). Today
  `AccessStore.revoke` has no reserved check [VERIFIED: marketplace-repo-proxy/app/access.py:202-220], so a CLI revoke
  would silently orphan the registered store repository.

### Pattern 5: Masking Supervisor text

Supervisor messages embed full URLs (`Can't add {url}, already in the store`, `Can't remove '{source}'...`,
`{url} is not a valid app repository`, git command lines). Before a message reaches a log or `supervisor.json`:
replace every `/repo/<owner>/<repo>/<32hex>` with the masked form (`urls.mask_hash`), then pass it through
`gitops.sanitize`-style length/line limits. `logsetup.SafeFormatter` already masks standalone 32-hex runs
[VERIFIED: marketplace-repo-proxy/app/logsetup.py:13-14,44-56 `HASH_TOKEN_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])")`];
it is the second line of defence for logs only, not for files. Register the token value in the `Redactor` at startup
(both env names).

### `/data/supervisor.json` contract (recommended)

Single writer: the sync process (atomic replace, mode 0600, like `status.json` [VERIFIED:
marketplace-repo-proxy/app/jsonio.py:12-30]). Contains no full hash and no full URL (slug and masked URL only).

```json
{
  "schema": 1,
  "updated": "2026-11-18T12:00:00Z",
  "register_local": true,
  "hostname": "{repo-hash}-marketplace-repo-proxy",
  "supervisor": {"last_contact": "...Z", "last_status": 200, "last_error": null},
  "reload": {"last_requested": "...Z", "last_result": "ok", "pending": false},
  "repositories": [
    {"repository": "example-org/private-addons", "registration": "registered",
     "store_slug": "0a1b2c3d", "masked_url": "http://{host}:8080/repo/example-org/private-addons/3f9c…",
     "registered_at": "...Z", "last_checked": "...Z", "message": ""}
  ],
  "leftovers": [
    {"repository": "example-org/private-addons", "store_slug": "4e5f6a7b", "user": "local.4e5f6a7b",
     "masked_url": "...", "since": "...Z", "reason": "in_use", "message": "masked supervisor text"}
  ],
  "requests": [{"id": "...", "action": "rotate", "repository": "...", "result": "refused", "finished": "...Z"}]
}
```

`registration` values: `registered`, `pending` (not synced ok yet), `disabled` (`register_local` false), `failed`.
Keep `requests` to the last 20. Document it in DOCS.md "Contracts" like `status.json` (field table).

### Anti-Patterns to Avoid

- **Matching by `url` field:** that is the served `repository.yaml` `url`, not the store URL.
- **Deleting a slug from the `GET` list:** only delete slugs computed from the proxy's own URLs and recorded in
  `supervisor.json`.
- **`urllib.request.urlopen` with defaults:** honours `http_proxy` and follows redirects with the `Authorization`
  header added by `add_header`.
- **CLI calling the Supervisor directly:** `docker exec` processes inherit the container env (token included); D-02/D-03
  still require that only the sync process uses it. Test statically that `app/cli.py` never imports `app.supervisor`.
- **Logging Supervisor responses or exceptions verbatim:** they carry full store URLs.
- **Reload per cycle:** each reload pulls every store repository including GitHub ones.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic JSON state | new writer | `app.jsonio.atomic_write_json` | fsync + dir fsync, mode 0600, already reviewed (WR-05) |
| `local` entry and links | direct file edits | `AccessStore.add/revoke` + `reconcile_tree` | lock discipline, link rebuild, hash rules |
| Request trigger polling | inotify/threads | the existing 1 s poll in `SyncService.wait_reason` | already tested, coalescing semantics |
| Hash masking | new regex per call | `urls.mask_hash`, `logsetup.mask_hashes` | consistent `abcd…` format the verify script greps |
| Store slug | guessing from `GET` | `hashlib.sha1(url.lower().encode()).hexdigest()[:8]` | identical to `get_hash_from_repository` |
| HTTP | `requests`/`aiohttp` | stdlib `urllib` (Pattern 1) | no new package, no supply chain |

## Common Pitfalls

### Pitfall 1: Reload storm on every add-on start
**What goes wrong:** `refs_changed` is true in the first cycle after every container start.
**Why:** `/srv/git` is container filesystem (`Paths.default()` → `Path("/srv/git")`
[VERIFIED: marketplace-repo-proxy/app/paths.py:41-46]); `ref_snapshot` returns `{}` for a missing repository
[VERIFIED: marketplace-repo-proxy/app/gitops.py:272-275], so `changed = ref_snapshot(repo_dir) != before` is true
[VERIFIED: marketplace-repo-proxy/app/sync.py:86-94]. The Supervisor recreates the container on add-on restart
[ASSUMED: DockerApp stop removes the container]. Note `docker restart` in the verify script keeps the container
filesystem, so it hides this.
**How to avoid:** compare `head` with the carried `status.json` head (Pattern 3). Test: a fresh `Paths` tree with a
`status.json` from a "previous run" and the same upstream head → no reload.

### Pitfall 2: Refused removal is HTTP 400 without `error_key`
**What goes wrong:** code waits for a dedicated error key or 409.
**How to avoid:** classify `status == 400 and "used by installed apps" in message`; everything else non-2xx is an error.
The fake must reproduce exactly this (D-13).

### Pitfall 3: Full store URLs in Supervisor error messages
**What goes wrong:** a log line or `supervisor.json` gets `Can't remove 'http://.../<32hex>'...`.
**How to avoid:** Pattern 5; the verify script greps `docker logs` and `supervisor.json` with the hash needles after a
forced refusal.

### Pitfall 4: Registration blocked by Supervisor job conditions
**What goes wrong:** `POST /store/repositories` or `/store/reload` returns 400 when the Supervisor is outdated, the OS or
Core is unsupported, or it thinks it is offline (`INTERNET_SYSTEM`).
**How to avoid:** treat as transient (`failed`, retry next cycle, warning once). E2E pre-check:
`ha supervisor info` shows no pending update.

### Pitfall 5: Hostname change makes a second store repository
**What goes wrong:** switching between a local copy and the repository install, or restoring the add-on under another
repository, registers a second URL; the old one points at a container that no longer exists.
**How to avoid:** store `hostname` in `supervisor.json`; when it differs from the current one, log a warning naming the
stale slug and leave removal to the operator (never delete it automatically: add-ons may be installed from it).

### Pitfall 6: CLI revoke/hand edit of the `local` entry
**What goes wrong:** the entry disappears, the next pass creates a new `local` hash and URL, the old store repository
becomes a silent dead leftover.
**How to avoid:** reserved-label guard in the CLI (Pattern 4); the registration pass detects proxy-shaped slugs it
recorded earlier that are no longer backed by an access entry and records them as leftovers (`reason: "orphaned"`).

### Pitfall 7: Supervisor pull of a revoked URL
**What goes wrong:** after a leftover's entry is revoked, each 3-hourly reload logs `ls-remote` warnings; a fetch failure
after a successful `ls-remote` raises a `CORRUPT_REPOSITORY` issue.
**How to avoid:** keep the retired entry serving while the leftover exists (Q-2 recommendation); revoke only after the
store repository is gone.

### Pitfall 8: Token via a second env name
**What goes wrong:** `/proc/*/environ` scans only look for the `SUPERVISOR_TOKEN` sentinel; `HASSIO_TOKEN` carries the
same value in production.
**How to avoid:** verify script sets both names to the sentinel; the needle file covers the value, which catches both.

### Pitfall 9: Options with the PAT on a command line (E2E)
**What goes wrong:** `ha addons options ... --options '{...github_token...}'` puts the PAT into argv and shell history.
**How to avoid:** the operator edits options (adding the test repository, later removing it) in the HA UI only.

## Code Examples

### Fake Supervisor core (stdlib, shared by pytest and verify)

```python
# tests/fake_supervisor.py — pattern sketch; run as a script in the verify container, imported by pytest
import hashlib, json, re, subprocess, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REFUSAL = "Can't remove '{source}'. It's used by installed apps"   # supervisor/store/__init__.py:262-266
DUPLICATE = "Can't add {url}, already in the store"                  # supervisor/exceptions.py:2137
NOT_FOUND = "Repository {slug} does not exist in the store"          # supervisor/api/store.py:107-110
ROUTES = {("GET", "/store/repositories"), ("POST", "/store/repositories"), ("POST", "/store/reload")}
DELETE_RE = re.compile(r"/store/repositories/([^/]+)")

def store_slug(url: str) -> str:
    return hashlib.sha1(url.lower().encode()).hexdigest()[:8]

class FakeState:
    def __init__(self, token, clone=None, in_use_file=None):
        self.token, self.lock = token, threading.Lock()
        self.requests = []   # (method, path, auth) — auth is "ok" | "missing" | "wrong", never the token
        self.repos = {"core": {...}, "local": {...}}   # builtins for realism
        self.clone = clone or git_clone_depth1          # pytest injects a callable; verify uses real git
        self.in_use_file = in_use_file                  # verify toggles refusal by writing slugs to this file

class Handler(BaseHTTPRequestHandler):
    def _auth(self) -> str:
        value = self.headers.get("Authorization", "")
        if not value: return "missing"
        return "ok" if value.split(" ")[-1] == self.server.state.token else "wrong"
    # GET/POST/DELETE: record, 401 text if missing, 403 text if wrong, 404 text for any other path,
    # then the real semantics: POST clones (`git clone --depth 1`) and checks repository.yaml|yml|json with `name`,
    # 409 envelope on duplicate slug, DELETE 404/400-refusal/200, reload re-fetches every custom repo and records heads.
```

Verify container (network alias, real clone through the proxy):

```bash
docker run -d --name "${PREFIX}-supervisor" --network "${NET}" --network-alias supervisor \
    -v "${PWD}/${ADDON_DIR}/tests/fake_supervisor.py:/opt/fake/fake_supervisor.py:ro" \
    -e FAKE_SUPERVISOR_TOKEN="${SUPERVISOR_SENTINEL}" \
    --entrypoint python3 "${IMAGE_TAG}" -I /opt/fake/fake_supervisor.py --port 80 --state-dir /tmp/fake
docker run -d --name "${PROXY}" --hostname "${PROXY}" --network "${NET}" ... \
    -e "SUPERVISOR_TOKEN=${SUPERVISOR_SENTINEL}" -e "HASSIO_TOKEN=${SUPERVISOR_SENTINEL}" "${IMAGE_TAG}"
```

The fake image is the proxy image (has `python3` and `git`), like the Phase 1 upstream fixture.

## Live E2E runbook (MRP-11) — mapping for the plan

Every step is a checkpoint (D-15). CLI names from `home-assistant/cli` 6.0.0 [VERIFIED: cmd/store.go,
cmd/store_repositories_add.go, cmd/store_repositories_delete.go, cmd/store_reload.go, cmd/store_apps_install.go,
cmd/apps.go, cmd/apps_uninstall.go, cmd/apps_info.go, cmd/apps_update.go]: `ha store` (repositories + apps),
`ha store add <url>`, `ha store delete <slug>` (alias `remove`), `ha store reload`, `ha store apps install <slug>`
(alias `ha store addons install`), `ha apps info|update|uninstall <slug>` (alias `ha addons ...`). The host's CLI
version was not probed; the `addons` aliases work on older CLIs too [ASSUMED]. Add `--raw-json` and filter with `jq` so
no full URL reaches the evidence.

| Step | Action (who) | Evidence (masked) |
|------|--------------|-------------------|
| 0 Pre-check (read-only) | `ha supervisor info --raw-json \| jq '.data \| {version, update_available, diagnostics}'`; `ha store --raw-json \| jq '[.data.repositories[].slug]'`; `ha addons info <proxy-slug> --raw-json \| jq '.data \| {version, state}'` | Supervisor not outdated (Pitfall 4); diagnostics flag noted (a refused removal reaches Sentry only with diagnostics on); proxy version |
| 1 Test repository (human-action, Q-5) | private repo in the PAT's scope with `repository.yaml` + one add-on | none in files |
| 2 Proxy config (human-action) | add the test repo to `repositories` in the HA UI, keep `register_local: true`, restart | proxy log: `sync ...: ok`, `registered` (masked) |
| 3 Store visible | `ha store --raw-json \| jq '.data.repositories[] \| {slug, name}'`; `ha store --raw-json \| jq '[.data.addons[] \| select(.repository=="<slug>") \| .slug]'` | slug present, test add-on listed (criterion 1) |
| 4 Install | `ha store addons install <slug>_<test-addon>` (local build) | `ha addons info ... \| jq '.data \| {version, version_latest, update_available}'` |
| 5 Upstream change (human-action) | bump `version` in the test add-on's `config.yaml`, push | commit time |
| 6 Update visible | wait for the next proxy cycle (or `mrp sync` if docker exec is available); **do not run `ha store reload` manually** | proxy log `store reload: ok` timestamp; `update_available: true`, `version_latest` new; minutes, not 3 h (criterion 2) |
| 7 Refusal probe (optional, MRP-10 live) | `mrp local remove <repo>` while installed (needs docker exec; skip if unavailable) | `refused`, leftover recorded, add-on still installed |
| 8 Cleanup | `ha addons uninstall <slug>_<test-addon>` → remove the test repo from `repositories` in the UI, restart → `mrp local remove <repo>` or `ha store delete <slug>` → `ha store` check → `ha resolution info` shows no issue for the slug | slug gone, no issue, proxy options as before |

Notes:
- `ha store delete` is the operator fallback when `docker exec` into the proxy is not available on the host
  (`mrp` needs a shell with Docker access, which the SSH add-on only has with protection mode off) [ASSUMED].
- A store slug removed via the proxy or `ha store delete` also removes the Supervisor's clone folder
  [VERIFIED: supervisor/store/git.py:302-319]; nothing else to clean on the Supervisor side. The test add-on's locally
  built image is removed by uninstall unless shared [VERIFIED: supervisor/apps/manager.py:266-279].
- Minimal test add-on: `repository.yaml` with `name`; add-on folder with `config.yaml` (`name`, `version`, `slug`,
  `description`, `arch: [amd64]` — required keys [VERIFIED: supervisor/apps/validate.py:457-463]), `boot: manual`,
  `startup: once`, `init: false`, and a one-line `Dockerfile` `FROM ghcr.io/home-assistant/amd64-base:3.24` (no
  `image:` → local build; `build.yaml` is deprecated [VERIFIED: supervisor/apps/build.py:67]). Never start it. The host
  must be amd64 because the proxy itself is amd64-only.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| TCP API with `SUPERVISOR_TOKEN` only | Per-add-on Unix socket `SUPERVISOR_SOCKET=/run/supervisor/api/supervisor.sock`; TCP kept while `supervisor_api_tcp` defaults to `True` ("Flipped to False late in the deprecation cycle, before the TCP API is removed") | Supervisor PR #7463, merged 2026-11-09, after `2026.11.0` | Phase 2 TCP works on current and next releases; plan a socket transport before the default flips (Q-6) [VERIFIED: supervisor@e610ca8 supervisor/apps/const.py:44-45, supervisor/docker/app.py:242-248] |
| `/addons/...` store paths | `/store/apps/...` on `/v2` (feature-flagged); repository routes unchanged and shared | 2026 | Allow-list uses root `/store/repositories` and `/store/reload` |
| `build.yaml` for local builds | `FROM` in the Dockerfile | recent | Test add-on needs no `build.yaml` |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Base URL is `http://supervisor` on port 80 | Store API contract | Every call fails; trivially visible in the first E2E step |
| A2 | aiohttp renders middleware 401/403/400 as plain text | Store API contract | Low: client handles both JSON and text |
| A3 | Supervisor recreates the add-on container on restart (fresh `/srv/git`) | Pitfall 1 | None for the recommended design (head comparison works either way) |
| A4 | Production host runs Supervisor `2026.11.0` or a build with `supervisor_api_tcp` defaulting to `True` | State of the Art, Q-6 | If TCP were already off, `SUPERVISOR_TOKEN` would be missing and registration would fail; pre-check step 0 shows the version |
| A5 | Older `ha` CLIs accept the `addons` aliases and `store add/delete` | E2E runbook | Command names differ; check `ha store --help` in step 0 |
| A6 | `mrp` via `docker exec` on the production host needs an SSH add-on with protection mode off | E2E runbook | Steps 6/7 fall back to waiting for the interval and `ha store delete` |
| A7 | `rating_security` uses the manifest `ports` (publishing 8080 in the UI does not change the rating) | Q-4 | Docs wording only |

## Open Questions

1. **Q-1 E2E install source.** Recommend (a): after the squash merge, CI publishes `0.1.0-2` from `main`
   (`push: branches: [main]`, `!internal/**` excluded [VERIFIED: .github/workflows/build.yml:9-40]); the production
   host updates the repository-installed proxy; hostname `{repo-hash}-marketplace-repo-proxy` is the real identity, so
   the E2E proves the decided setup (SPIKE "Decisions"). Consequence: MRP-11 is verified after the merge; a defect found
   there ships as `0.1.0-3`. Option (b), a local add-on copy before the merge: copy the add-on folder to the host's
   local add-ons share, **remove `image:`** from the copy (otherwise the Supervisor tries to pull a `0.1.0-2` image that
   does not exist yet), local build on the host; slug `local_marketplace_repo_proxy`, hostname
   `local-marketplace-repo-proxy`, its own `/data` (new `local` hash), so the registered store URL is different and must
   be removed in cleanup; if the repository-installed proxy also runs with the same repositories and
   `register_local: true`, both register (duplicate add-on entries in the store) — stop one. The plan must work for
   both: derive every slug from the proxy's own `supervisor.json`/log, never hard-code the hostname.
2. **Q-2 old `local` URL after rotation.** Recommend: keep serving it as `local.<oldslug>` while the store repository
   is a leftover; revoke when the `DELETE` succeeds, returns 404, or the slug disappears from `GET`. Offer
   `--revoke-old` for the leak case (cuts updates for still-installed add-ons, uninstalls nothing). Mark as assumption.
3. **Q-3 removal triggers.** Confirm the planner assumption: no automatic removal. `register_local: false` stops
   adding; removing a repository from `repositories` leaves its store repository with a dead URL (links exist only for
   configured repositories [VERIFIED: marketplace-repo-proxy/app/access.py:254-284]), which makes the Supervisor log
   pull warnings every reload. DOCS.md tells the operator to run `mrp local remove <repo>` (works for unconfigured
   repositories via `supervisor.json`) or `ha store delete <slug>`.
4. **Q-4 manager-role warning.** Yes. Rating from `rating_security` [VERIFIED: supervisor/apps/utils.py:26-96]:
   start 5; AppArmor: manifest default `apparmor: True` [VERIFIED: supervisor/apps/validate.py:513] and no shipped
   profile → `SECURITY_DEFAULT`, ±0; no ingress, no host network, no published manifest port → +2; `signed` is always
   `False` [VERIFIED: supervisor/apps/model.py:855-857] → 0; `hassio_role == ROLE_MANAGER` → −1. Phase 1: **7**,
   Phase 2: **6** (Phase 3 ingress keeps the +2). DOCS.md "Security notes": what manager allows (add-on control except
   security settings, backups, Core/host/OS/Supervisor endpoints, Docker/mount/network config, store), why the proxy
   needs it (`/store.*` is manager-only), the mitigations (four allow-listed calls checked before any I/O, token only in
   the sync process, never in lighttpd/access-watch, every call logged without secrets), the rating (6 instead of 7),
   and that the Supervisor log shows registered store URLs. README.md: one line pointing to it.
5. **Q-5 E2E test repository.** Needs: private repository readable by the configured fine-grained PAT (add it to the
   token's selected repositories), `repository.yaml` with `name`, one trivial add-on as above, a version-bump commit
   pushed by the user. `checkpoint:human-action`; the name never appears in files.
6. **Q-6 (new) Unix-socket transport.** The TCP API is deprecated upstream but still the default. Recommend: TCP in
   Phase 2, transport isolated in `app/supervisor.py`, and a deferred item "socket transport + `supervisor_api_tcp:
   false`" before the default flips. Needs user confirmation.
7. **Q-7 (new) Allow-list vs. refusal noise.** A refused `DELETE` makes the Supervisor log a traceback with the full
   URL and, with diagnostics on, send a Sentry event. A pre-check via `GET /store` (installed add-ons per repository)
   would avoid it but is outside D-02's four calls. Recommend: keep D-02; the refusal happens only on explicit operator
   actions, never in a loop.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | verify script | ✓ | 29.9.3 | — |
| uv | pytest runner | ✓ | installed | `python3 -m pytest` with pins |
| git | tests, fixtures | ✓ | 2.56.1 | — |
| python3 (host) | verify helpers (`yget`, JSON) | ✓ | 3.14.10 | — |
| jq, yq, gh | helpers | ✓ | installed | — |
| Production host (`ha` via SSH) | MRP-11 only | not probed (instruction) | — | none; E2E plan checkpoints |

Existing suite: `222 passed in 4.37s` (run this session).

## Validation Architecture

(`workflow.nyquist_validation` is `false` in `.planning/config.json`; included because the orchestrator asked.)

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (+ PyYAML 6.0.3), Python 3.12 in CI |
| Config file | none (`tests/conftest.py` sets `sys.path`) |
| Quick run command | `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests -q` |
| Full suite command | quick run + `bash internal/verify-marketplace-repo-proxy.sh` + `make validate-addons validate-versions && python3 internal/validate-addon-config.py` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MRP-07 | Allow-list refuses other method/path/slug before I/O (fake records nothing); `Authorization: Bearer`; no proxy, no redirect; envelope and text errors; token never in exceptions/logs | unit | `... pytest marketplace-repo-proxy/tests/test_supervisor.py -q` | ❌ Wave 0 |
| MRP-07 | `config.yaml` has `hassio_api: true`, `hassio_role: manager`, none of `homeassistant_api`, `auth_api`, `docker_api`, `host_network`, `full_access` | static | verify step (0) + `test_options.py` | partial |
| MRP-07 | `cli.py` never imports `app.supervisor`; only `sync` imports it | static | `test_cli.py` | ❌ |
| MRP-08 | Register when missing and synced ok; skip present (slug), `no_repository_yaml`, `register_local: false`; 409 = registered; `local` hash stable across runs | unit + docker | `test_registration.py`; verify: fake lists the proxy URL, fake clone has the fixture `name` | ❌ |
| MRP-09 | Reload after head change; none on first sync or restart with same head; ≤1 per interval (fake clock); pending reload fires when window opens; failed reload waits | unit + docker | `test_registration.py`; verify: one `POST /store/reload` after upstream commit + `mrp sync`, a second commit + `mrp sync` within 5 min → still one | ❌ |
| MRP-10 | Rotate add-first (POST before DELETE in fake log); refusal → leftover, retired entry served, warning, no retry next cycle; success/404 → revoke; remove; reserved-label guards; leftover vanishes when slug gone | unit + docker | `test_registration.py`, `test_cli.py`, `test_access.py`; verify: in-use file → refusal → old URL 200, then clear → `mrp local rotate` retry → old URL 404 | ❌ |
| MRP-07/D-03 | Sentinel token (both env names) absent from lighttpd/access-watch env, `docker logs`, `status.json`, `supervisor.json`; present in sync env (positive control); fake saw `auth: ok` only | docker | `bash internal/verify-marketplace-repo-proxy.sh` | extend |
| MRP-11 | Live E2E | manual | plan checkpoints | n/a |

### Sampling Rate
- **Per task commit:** quick run command.
- **Per wave merge:** quick run + verify script (not in two worktrees at once).
- **Phase gate:** full suite green before `/gsd-verify-work`; MRP-11 evidence from the E2E plan.

### Wave 0 Gaps
- [ ] `marketplace-repo-proxy/tests/fake_supervisor.py` — shared fake (in-process and container entry point)
- [ ] `marketplace-repo-proxy/tests/test_supervisor.py` — client contract
- [ ] `marketplace-repo-proxy/tests/test_registration.py` — registration, reload gate, rotation, queue
- [ ] Verify script: fake container, `HASSIO_TOKEN` sentinel, new sections; static check for the two manifest keys

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (outbound) | Supervisor token as bearer, read from env only in the sync process |
| V3 Session Management | no | — |
| V4 Access Control | yes | Allow-list of four `(method, path)` pairs, slug `fullmatch`, own-slug-only deletes, request files in a 0700 root dir, reserved labels |
| V5 Input Validation | yes | Supervisor responses parsed defensively (JSON or text, type checks on `slug`/`source`); request-file action/repository validated |
| V6 Cryptography | yes | `secrets.token_hex(16)` for new `local` hashes (existing), `hashlib.sha1` only for the Supervisor's identifier (not a security use) |
| V7 Error handling and logging | yes | One log line per call (template + status), masking of Supervisor text, redactor for both token env values |
| V14 Configuration | yes | Manifest permission minimal (D-01), no proxy/redirect following |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Manager token reaches lighttpd/CGI | Elevation of privilege | `#!/bin/sh` services, `/proc/*/environ` scans for both env names |
| Token sent to a proxy or redirect target | Information disclosure | `ProxyHandler({})`, no-redirect handler, `add_unredirected_header` |
| Full store URL in logs/state via Supervisor messages | Information disclosure | Pattern 5 masking + verify greps after a forced refusal |
| Confused deputy: CLI/GUI requests trigger arbitrary Supervisor calls | Elevation of privilege | Request files carry only `action` + `repository`, validated in sync; client allow-list |
| Deleting someone else's store repository | Tampering | Delete only slugs recorded from the proxy's own URLs |
| Uninstalling add-ons | Tampering / DoS | No endpoint outside the allow-list; refusal never forced |
| Reload storm against the Supervisor and GitHub | Denial of service | Head-based change detection, one reload per interval |
| Stale leftover keeps an old URL alive | Information disclosure | Retired entries visible in `supervisor.json`; `--revoke-old` escape hatch |

## Sources

### Primary (HIGH confidence)
- `home-assistant/supervisor@e610ca8` (raw files fetched this session): `supervisor/api/store.py`,
  `supervisor/api/__init__.py`, `supervisor/api/utils.py`, `supervisor/api/middleware/security.py`,
  `supervisor/api/sockets.py`, `supervisor/store/__init__.py`, `supervisor/store/git.py`, `supervisor/store/repository.py`,
  `supervisor/store/utils.py`, `supervisor/store/validate.py`, `supervisor/store/const.py`, `supervisor/store/data.py`,
  `supervisor/exceptions.py`, `supervisor/const.py`, `supervisor/apps/utils.py`, `supervisor/apps/model.py`,
  `supervisor/apps/validate.py`, `supervisor/apps/const.py`, `supervisor/apps/app.py`, `supervisor/apps/build.py`,
  `supervisor/docker/app.py`, `supervisor/docker/const.py`, `supervisor/misc/tasks.py`, `supervisor/misc/filter.py`,
  `supervisor/utils/sentry.py`, `supervisor/utils/__init__.py`, `tests/api/test_store.py`,
  `tests/store/test_custom_repository.py`; diff against tag `2026.11.0`
- Supervisor PR #7463 description (per-app Unix sockets, `supervisor_api_tcp`)
- `home-assistant/cli@6.0.0` `cmd/store*.go`, `cmd/apps*.go`
- This repository: `marketplace-repo-proxy/app/*.py`, `tests/*`, `rootfs/etc/s6-overlay/*`, `config.yaml`,
  `Dockerfile`, `DOCS.md`, `internal/verify-marketplace-repo-proxy.sh`, `.github/workflows/{build,lint}.yml`

### Secondary / Tertiary
- None used.

## Metadata

**Confidence breakdown:**
- Supervisor contract: HIGH — read from source, cross-checked with Supervisor tests, identical at the release tag
- Architecture: HIGH — built on Phase 1 code read this session; design choices are recommendations within discretion
- Pitfalls: HIGH for 1-4, 8; MEDIUM for 5-7, 9 (operational)
- E2E runbook: MEDIUM — CLI verified at 6.0.0, host versions not probed

**Research date:** 2026-11-18
**Valid until:** 2026-12-18 (Supervisor socket migration is moving; re-check `SUPERVISOR_API_TCP_DEFAULT` before the
next phase)
