# Secrets Sync - Spec (v0.1)

Contract between the implementation agents. Change it only via the control agent. Machine-readable parts:
`app/providers/base.py`, `app/controller.py`, `docs/state.schema.json`, `docs/state.example.json`.

## Purpose

Sync secrets from pluggable providers (`bitwarden`, `sops`) into `/config/secrets.yaml` (+ optional files). Own code (no
upstream), amd64 only, base `ghcr.io/home-assistant/amd64-base:3.24`, slug `secrets_sync`, python3 stdlib at runtime (+
PyYAML from apk), version `0.1.0-0` (manual, via `make update-version`).

## Security rules (hard requirements, tested)

1. Secrets only via env vars / files, never in argv. Bitwarden: `BW_CLIENTID`, `BW_CLIENTSECRET`,
   `bw unlock --passwordenv BW_PASSWORD`.
2. YAML values are emitted as double-quoted scalars via `json.dumps(v, ensure_ascii=False)`. Every write is verified by
   a PyYAML `safe_load` round trip (parsed dict == input dict) before the rename.
3. Secret values are never logged, at any level, including exceptions and tool stderr. Log key names only. Subprocess
   stderr is not forwarded verbatim; map it to an error code.
4. File paths from providers are relative, below `FILES_DIR`; reject empty, absolute, `..` segments, backslashes and
   anything that resolves outside `FILES_DIR`. Mode 600, atomic write, no symlink following.
5. Never exit on error. Backoff + retry (30 s doubling to `interval`), keep the last good `secrets.yaml`, expose the
   error in state.json. Only a bad addon-level config may stay in state `error` while the process keeps serving.
6. Duplicate key across providers or within one snapshot = error `key_collision` naming both sources; nothing is written
   for that cycle.
7. No secret values in state.json, API responses, HTML or events.

## Layout and ownership (disjoint)

```text
secrets-sync/
  config.yaml build.yaml Dockerfile run.sh translations/ README.md DOCS.md CHANGELOG.md   ss-package
  docs/SPEC.md docs/state.*.json                                                         control
  app/main.py                      entry: load env config, start supervisor + web          ss-core
  app/controller.py                Controller protocol                                      control
  app/engine/                      config, merge, writer, guard, state, supervisor          ss-core
  app/providers/base.py            contract                                                 control
  app/providers/bitwarden.py       ss-core
  app/providers/sops.py            ss-sops
  app/web/                         server.py (+ templates/static, no external assets)       ss-web
  tests/engine tests/bitwarden     ss-core      tests/sops   ss-sops      tests/web   ss-web
  internal/ (repo root) verify-secrets-sync-*.sh, validators, CI lists                   ss-package
```

`app/main.py` calls `app.web.server.serve(controller, state_path, port, ingress_only=True)` (blocking, run in a thread
by main) and `app.engine.supervisor.Supervisor(config)`. Provider registry: `app/engine/config.py` maps name -> module
(`app.providers.<name>.Provider` class `Provider(cfg: Mapping)`).

## Runtime paths and environment (set by `run.sh`, read by `app/engine/config.py`)

| Variable                   | Default                 | Meaning                                                               |
| -------------------------- | ----------------------- | --------------------------------------------------------------------- |
| `SS_OPTIONS`               | `/data/options.json`    | HA options (python reads it directly; run.sh only checks and `exec`s) |
| `SS_SECRETS_FILE`          | `/config/secrets.yaml`  | target                                                                |
| `SS_FILES_DIR`             | `/config/secrets_files` | base for provider files                                               |
| `SS_STATE_FILE`            | `/data/state.json`      | state contract, written atomically                                    |
| `SS_DATA_DIR`              | `/data`                 | manifest (`files.manifest.json`), bw data dir                         |
| `SS_PORT`                  | `8099`                  | web                                                                   |
| `BW_*`                     | -                       | passed through from options by run.sh (secrets only via env)          |
| `SS_AGE_KEY_FILE`          | `/addon_config/age.key` | sops age key (mode 600, not an option)                                |
| `BITWARDENCLI_APPDATA_DIR` | `/data/bw`              | isolated bw state                                                     |

Rule: run.sh maps option secrets to env vars; python reads non-secret options from `options.json`.

## Options (config.yaml; flat, no unions)

```yaml
options:
  providers: ["bitwarden"] # list(bitwarden|sops), order = priority when collision_policy: priority
  interval: 300 # int(60,86400)
  collision_policy: "error" # list(error|priority)
  shrink_guard_percent: 30 # int(1,100); refuse write if items drop by more than this vs. last write
  log_level: "info" # list(debug|info|warning|error), never changes value logging
  bitwarden:
    server_url: "https://bitwarden.com" # url
    client_id: "" # password
    client_secret: "" # password
    master_password: "" # password
    organization_id: "" # str?   restricts to org items
    collection_id: "" # str?
    key_style: "legacy" # list(legacy)  (reserved for more styles)
    notes_dir: "bitwarden" # str    secure-note files below FILES_DIR
  sops:
    file: "/config/secrets.sops.yaml" # str
    flatten_separator: "_" # str
```

Both blocks are always present in `options` (HA cannot mark a dict key optional; `key?:` is read literally), with empty
defaults; `validate()` reports missing parts as `Problem`s (shown in UI/state), the add-on keeps running.

## Engine semantics

- Cycle: for each enabled provider -> `validate` (problems with severity error => provider `error`, skipped) -> `fetch`
  -> collect. Providers that fail keep their last good contribution **only if** we hold it in memory; after restart a
  failed provider means the cycle is `degraded` and **nothing is written** (never write a partial merge that drops a
  provider's keys).
- Merge: dict union; collision => `key_collision` (policy `error`) or the earlier provider in `providers` wins (policy
  `priority`, event `key_shadowed` with names only).
- Guard: 0 items or `items < last_items * (1 - shrink_guard_percent/100)` => no write, status `degraded`, error_code
  `shrink_guard`. Cleared automatically when a later cycle passes (a deliberate large removal needs one
  `POST /api/sync?force=1`, ingress only).
- Write: sorted keys, header comment `# managed by Secrets Sync - do not edit`, temp file in same dir, round-trip
  verify, fsync file + dir, copy previous to `secrets.yaml.bak`, rename, chmod 600. Skip the write if content is
  byte-identical.
- Files: written atomically below `SS_FILES_DIR`, tracked in `files.manifest.json`; files in the manifest but no longer
  in any snapshot are deleted; unknown files are never touched.
- State: `docs/state.schema.json`. `status`: `ok` all providers ok and written; `degraded` guard / partial / collision /
  provider error with a still valid last file; `error` nothing ever written successfully or unusable config; `starting`
  before the first cycle. `stale` = `age_seconds > 2*interval`.
- Timeouts: every subprocess/network call has a timeout (bw 60 s, sops 30 s). Re-auth: on `bw` locked/expired
  (`not logged in`, `Vault is locked`) re-login + unlock once per cycle.
- Min interval 60 s, also for `trigger_sync` (manual sync allowed when the last attempt is older than 10 s).

## Bitwarden provider

- `bw config server <url>` (only when changed), `bw login --apikey` (env), `bw unlock --passwordenv BW_PASSWORD --raw`
  -> session string kept in process memory and passed as env `BW_SESSION` to child calls. Per cycle: `bw sync`, then
  `bw list items --organizationid <id> [--collectionid <id>]` (or all items when unset).
- Key naming (`key_style: legacy`): `name` = item name sanitised: `tr '?:&,%@-' ' '`, then `tr '[]{}#*!|> ' '_'`,
  squeeze `_`, lowercase. Login items: `<name>_username`, `<name>_password`, `<name>_notes` (if notes), `<name>_uri_<N>`
  (1-based), custom fields `<name>_<sanitised field name>`. Secure notes (type 2) with a non-empty note become files:
  relative path = sanitised name (+ `.txt` if no extension) below `notes_dir`; they do not become secrets. SSH-key items
  (type 5): `<name>_public_key` always (no fingerprint); `<name>_private_key` only when the item has a custom field
  `secrets_sync_export_private_key` = `true` (case-insensitive). Cards/identities are ignored (event `item_skipped` with
  count only).
- `fetch()` returns a Snapshot; any non-zero `bw` exit maps to a `ProviderError` code (`bw_auth_failed`,
  `bw_unlock_failed`, `bw_sync_failed`, `bw_list_failed`, `bw_timeout`, `bw_invalid_json`).
- Tests use a fake `bw` script on `PATH` (no network).

## SOPS provider

- `sops -d --output-type yaml <file>` -> stdout parsed in memory with PyYAML `safe_load`; env
  `SOPS_AGE_KEY_FILE=<SS_AGE_KEY_FILE>`. Never a temp file, never `--output`.
- Pre-checks (no decrypt): age key exists, is a regular file, mode `0600` or stricter (else `sops_key_permissions`);
  target file exists; parsed YAML has a top-level `sops` mapping (else `sops_not_encrypted`).
- Mapping: top-level scalar keys 1:1; nested mappings flattened with `flatten_separator`; lists and non-scalars =>
  problem `sops_unsupported_value` (key name only); scalar values are converted with `str()` (bool -> `true`/`false`).
- `revision` = file mtime (epoch string). Interface stays open for a future git source (not in v0.1).

## Web <-> engine

The web layer reads `SS_STATE_FILE` only (re-read on every request, tolerate a missing/partial file => `starting` page)
and calls `Controller`. Ingress only for POST: require header `X-Ingress-Path` (set by Supervisor) and `Remote` address
`172.30.32.2`; GET `/api/health` and `/api/status.json` also work over the optional 8099/tcp.

| Route              | Method | Result                                                                                                                                                                                     |
| ------------------ | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `/`                | GET    | HTML page: status, last sync, items, next sync, versions, per-provider status, key names with added/removed/changed, events, "Sync now", "Preview" (relative links only - ingress prefix!) |
| `/api/status.json` | GET    | the full state.json                                                                                                                                                                        |
| `/api/health`      | GET    | `{"status","age_seconds","stale","items","error_code"}`; **200** if `status=="ok"` and not stale, else **503**                                                                             |
| `/api/sync`        | POST   | 202 `{"started":true}` / 429 rate limited; `?force=1` lifts the shrink guard once                                                                                                          |
| `/api/preview`     | POST   | `Controller.preview()` JSON (key names only)                                                                                                                                               |

Gatus example: `[STATUS] == 200`, `[BODY].age_seconds < 900`. HTML is escaped (no raw interpolation), no external
fonts/scripts/CDN, works under any ingress prefix, light/dark.

## Definition of done (per agent)

pytest green (`python3 -m pytest tests/<area>`), `make lint` clean for owned files, small commits on `feat/secrets-sync`
staged by path, no `Co-Authored-By`, no hand-edited versions.

## Decisions (control, after first agent round)

- `Controller.trigger_sync(force: bool = False)`; manual sync rate limit is 10 s (the 60 s minimum applies to
  `interval`).
- `GET /` is ingress only (403 otherwise); the optional TCP port serves only `/api/health` and `/api/status.json`.
- Provider `fetch()` raises `ProviderError` for unsupported values / flatten collisions (no partial snapshots).
- Files present in `SS_FILES_DIR` but not in the manifest are never overwritten (`file_unmanaged`, degraded).
- `run.sh` exports `SS_ADDON_VERSION`. First run replaces an existing `secrets.yaml` (previous one kept as `.bak`).
- Child processes of the sops provider do not inherit `BW_*` variables.

## Secret usage (0.2)

- `app/engine/usage.py` scans `*.yaml|*.yml` below `/config` (and, for `usage_scan: all`, `/addon_configs`) for
  `!secret <key>`. Scope follows HA: nearest `secrets.yaml` in the folder or a parent; references that resolve to a
  nested secrets.yaml do not count. Skips hidden dirs, `custom_components`, `deps`, `node_modules`, `backups`,
  `__pycache__`, `secrets_files`, symlinks, files > 1 MiB; limits 20000 files / 20 s (`truncated`).
- `state.json` `usage` (optional): `enabled`, `roots`, `scanned_at`, `files_scanned`, `truncated`, `used`/`missing` (key
  -> `count`, up to 20 `refs` of `file`+`line`), `unused` (key names). Names and positions only.
- Runs at the end of each cycle, at most every 60 s; never raises; event `secret_missing` (warning) while keys are
  missing.

## SOPS git source and change check (0.3)

### Options (flat additions, defaults keep today's behaviour)

```yaml
options:
  check_interval: 60 # int(0,3600); seconds between cheap change checks, 0 = off, 1..29 are raised to 30
  sops:
    source: "file" # list(file|git)
    file: "/config/secrets.sops.yaml" # used when source: file
    flatten_separator: "_"
    git_url: "" # str?  ssh (git@host:org/repo.git, ssh://...) or https://...; no credentials inside the URL
    git_branch: "main" # str
    git_path: "secrets.sops.yaml" # str   path of the encrypted file inside the repo
    git_username: "x-access-token" # str   https only
    git_token: "" # password  https only; run.sh exports it as SS_GIT_TOKEN, never argv/URL
```

`source: git` ignores `file`. `validate()` reports `sops_git_missing_url`, `sops_git_url_credentials` (userinfo in URL),
`sops_git_url_scheme` (only `ssh`, `git@host:path`, `https` allowed), `sops_git_path_invalid` (empty, absolute, `..`,
backslash, NUL), `sops_git_missing_token` is NOT an error (public repos), `sops_git_branch_invalid` (empty or starts
with `-`).

### Git access (`app/providers/gitsource.py`, owned by ss-sops; used by `sops.py` and its `check()`)

- Binaries `git` + `ssh` (Alpine `git`, `openssh-client`). All calls: argv list, timeout 60 s (`ls-remote` 20 s), stderr
  dropped, URL/branch after `--`. Env: `GIT_TERMINAL_PROMPT=0`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`,
  `GIT_ALLOW_PROTOCOL=ssh:https` (overridable by env `SS_GIT_ALLOW_PROTOCOL`, used by tests with `file`), `HOME` = data
  dir, no `BW_*`. Hooks off (`-c core.hooksPath=/dev/null`), `-c protocol.ext.allow=never`.
- **SSH** (URL is ssh): key `SS_GIT_DEPLOY_KEY` (default `/addon_config/deploy_key`, regular file, mode 0600 else
  `git_key_permissions`; missing => `git_key_missing`). `GIT_SSH_COMMAND` =
  `ssh -i <key> -o IdentitiesOnly=yes -o BatchMode=yes -o UserKnownHostsFile=<kh> -o StrictHostKeyChecking=<mode>`: if
  `/addon_config/known_hosts` exists it is used with `yes`, otherwise `<data>/known_hosts` with `accept-new` (trust on
  first use, persisted).
- **HTTPS**: if `SS_GIT_TOKEN` is set, `GIT_ASKPASS=<app>/bin/git-askpass` (prints `git_username` for the username
  prompt, else the token, read from env `SS_GIT_USERNAME` / `SS_GIT_TOKEN`). The token never appears in argv, URL, logs
  or state.
- Cache: shallow clone `--depth 1 --single-branch --branch <b>` into `<data>/git/<sha1(url+branch)[:12]>`; later cycles
  `git fetch --depth 1 origin <b>` + `git reset --hard FETCH_HEAD` + `git clean -fdx`. A broken cache (any fetch/reset
  failure) is deleted and re-cloned once per cycle.
- File resolution: `git_path` joined to the clone, `Path.resolve()` must stay inside the clone, no symlink components,
  must be a regular file (else `git_path_invalid` / `git_file_missing`). The file is then handled exactly like
  `source: file` (`sops -d` of that path, same pre-checks and flattening). Decrypted data never touches disk.
- `revision` = first 12 chars of the checked-out commit SHA.
- Error codes (stable, no stderr): `git_binary_missing`, `git_timeout`, `git_auth_failed` (permission denied / 401 / 403
  pattern in the dropped stderr is only used to pick the code), `git_clone_failed`, `git_fetch_failed`,
  `git_ref_not_found` (branch missing), `git_exec_failed`, plus the key codes above.

### Change check (engine + `Provider.check()`)

- `Provider.check() -> str | None` (see `providers/base.py`): cheap probe returning an opaque token. SOPS+git:
  `git ls-remote -- <url> refs/heads/<branch>` => the commit SHA (`git_ref_not_found` if empty). SOPS+file and
  Bitwarden: not implemented (never probed).
- Engine: the supervisor remembers per provider the token seen at its last successful `fetch` (for git: the SHA that was
  checked out; the provider exposes it as `Snapshot.revision`'s full form via `check`-compatible token field
  `Snapshot.check_token`, new optional field, default `""`). Every `check_interval` seconds (only if
  `check_interval > 0` and at least one enabled provider implements `check`) the supervisor calls `check()` for those
  providers; when a token differs from the stored one it starts a normal cycle early (same path as `trigger_sync`,
  honours the 10 s manual gap and backoff). The regular `interval` sync stays as a fallback and always fetches.
- A failing check never changes `status`, never counts as a failure for the backoff and never writes anything; it is
  recorded in `state.check` (`result: error`, `error_code`) and, once per distinct code, as event `check_failed`
  (warning, no URL). A detected change emits event `source_changed` (info, provider name + short revisions only).
- `state.json` `check`: see `state.schema.json` (`enabled`, `interval`, `last_check_at`, `result`
  `unchanged|changed|error|unsupported`, `error_code`, `triggered_syncs`). When disabled:
  `{"enabled": false, "interval": 0, "last_check_at": null, "result": null}`.
- Web: ingress page shows "Change check" (interval, last check, result) and the git revision per provider; `/api/health`
  is unchanged.
- Privacy: URL, branch, path, token and SHAs of unrelated repos are never logged at info level; log lines carry provider
  name and short revision only. Tests assert that no token / key content appears in logs, state or events.

## Synthetic keys (0.4)

Keys composed from other keys with a tiny sandboxed Jinja template, e.g. a database DSN from separate user/password
keys. Runs in the engine after `merge`, before the shrink guard and the write, so it is provider independent.

### Option

```yaml
options:
  synthetic_keys: [] # list of {name, template}; HA schema: synthetic_keys: [{name: "str", template: "str"}]
  # - name: "db_dsn"
  #   template: "postgresql://{{ db_user | urlquote }}:{{ db_password | urlquote }}@db:5432/ha"
```

- `name`: `^[A-Za-z_][A-Za-z0-9_]{0,127}$`, unique among synthetic keys; config problem (severity error, code
  `synthetic_invalid_name`) otherwise. A name that already exists as a real key => cycle error `synthetic_collision`
  (key names in the message, never silently overridden; independent of `collision_policy`).
- `template`: max 2048 chars (`synthetic_template_too_long`), non-empty.
- Config: `Config.synthetic_keys: tuple[tuple[str, str], ...] = ()` (name, template), order as configured.

### Rendering (`app/engine/synthetic.py`, `apply(secrets, defs) -> dict[str, str]`)

- `jinja2.sandbox.ImmutableSandboxedEnvironment`, `StrictUndefined`, `autoescape=False`, no loader, `env.globals`
  emptied (no `range`, `dict`, `lipsum`, `cycler`, `joiner`, `namespace`), no extensions.
- Context: `secrets` (read-only mapping of all real merged keys) and every real key whose name is a valid identifier as
  a direct variable. Synthetic keys do **not** see each other (no chaining, no ordering problems).
- Allowed syntax (checked on the parsed AST before rendering, anything else => `synthetic_forbidden`): output
  `{{ ... }}`, text, `{% if/elif/else %}`, names, constants, `secrets[...]` subscripts, filters (whitelist),
  comparisons, boolean ops, `+` and `~`, conditional expressions, list/tuple literals. Forbidden: `for`, `set`, macros,
  `call`, `filter` blocks, `import`/`include`/`extends`/`block`, attribute access to anything but the whitelisted
  filters, calls other than filters, and binary `*`, `**`, `%`, `//`.
- Filter whitelist (everything else => `synthetic_forbidden`): `lower`, `upper`, `trim`, `replace`, `default`, `length`,
  `join`, `capitalize`, `title`, `b64encode`, `b64decode`, plus own filters `substr(start, length=None)` (Python slice
  semantics, negative start allowed, never raises on out-of-range), `urlquote` (`urllib.parse.quote(v, safe="")`;
  Jinja's own `urlencode` keeps `/` and is therefore NOT offered), `shquote` not offered.
- Limits: output <= 65536 chars (`synthetic_too_large`), rendered value is converted with `str()`; template syntax error
  => `synthetic_syntax`; undefined variable/key => `synthetic_undefined` (message: synthetic key name + referenced key
  name only); any other exception => `synthetic_error`. **Messages are built by us from the error class and names; never
  from Jinja's message text or any rendered/input value.**
- Any synthetic error is a cycle error like `key_collision`: nothing is written, last good file stays, status `degraded`
  (or `error` if never written), event with the code and the synthetic key name.

### State and UI

- `state.json` `keys.synthetic` (optional, sorted names) = synthetic keys in the written set; they are part of
  `keys.names`, `items` and the shrink guard count. Added/removed/changed diffs work as for real keys.
- Preview (`/api/preview`) includes synthetic keys. Ingress page marks them (e.g. a "synthetic" badge). Values never.
- Usage scan unchanged (a synthetic key is a normal key in `secrets.yaml`).
- Packaging: Alpine `py3-jinja2` (tests use `jinja2` via `uv run --with`). Docs: examples (DSN, URL with `urlquote`,
  `substr`, `default`), the forbidden list, error codes.

### Synthetic keys in the UI (0.4.3)

- `state.json` `synthetic` (list, see schema): per configured key `name`, `template` (configuration text, never a
  value), `refs` (key names the template mentions), `status` `ok|pending|error` and `error_code`. Parse problems
  (`synthetic_syntax`, `synthetic_forbidden`, `synthetic_unavailable`) are reported from `synthetic.inspect()` at the
  start of every cycle, independent of provider results; render problems (`synthetic_undefined`, `synthetic_too_large`,
  ...) are attached to the failing key. `pending` = parsed, but the cycle ended before rendering.
- The ingress page renders the card; it is omitted when the list is empty or absent. Templates are therefore also in
  `/api/status.json`: never put a literal secret into a template.

### Shrink guard override in the UI (0.4.4)

- On `shrink_guard` the supervisor stores `state.guard` = `{new_items, last_items, removed, added, changed}` (key names,
  diff against the last written set or the current `secrets.yaml`); reset to `null` at the start of every cycle.
- The ingress page shows the card only while `error_code == "shrink_guard"` and `guard` is an object: removed keys in
  red, an "Apply anyway" button (confirm dialog with the count) that POSTs `api/sync?force=1`.

## Web UI redesign (0.5)

Static shell + JavaScript, data only from JSON. Owner: ss-web (`app/web/*`, `tests/web`). No engine changes.

### Delivery

- `GET /` (ingress only) returns a **static** HTML shell without any state data (no `render_page(state)` interpolation).
  Assets, also ingress only, always **relative** URLs (ingress prefix!): `static/app.css`, `static/app.js` served with
  correct `Content-Type`, `Cache-Control: no-cache`, path whitelist (no traversal, no directory listing, 404 otherwise).
  Optional TCP port keeps serving only `/api/health` and `/api/status.json`.
- JS fetches `api/status.json` (relative) on load, every **15 s** and on demand ("Refresh" button, after `Sync now` /
  `Apply anyway` / `Preview`: re-fetch after 3 s and again after 10 s). Pause polling while the tab is hidden
  (`visibilitychange`), refresh immediately when it becomes visible again. A failed fetch shows a small "offline / last
  update TIME" hint and keeps the old data. Missing blocks (older state files) never throw.
- Rendering uses `createElement`/`textContent` only (never `innerHTML` with data). The existing escaping guarantees
  stay: key names, templates, messages are data, never markup. No external fonts/scripts/CDN. Works under any ingress
  prefix, light/dark (`prefers-color-scheme`), phone width.
- `POST api/sync`, `api/sync?force=1`, `api/preview` unchanged (preview result shown in a closable panel, key names
  only).
- Small persistence in `localStorage` (selected tab) wrapped in try/catch; the URL hash (`#keys`, `#synthetic`,
  `#usage`, `#events`) selects a tab as well.

### Layout

1. **Topbar**, `position: sticky; top: 0; height: 56px` (same height as the HA drawer header), full width: the key-chain
   icon (inline SVG, the mdi `key-chain` path used for `panel_icon`) + title "Secrets Sync"; badges: status (colour by
   status, `stale` when ok but stale), items, last sync (relative, full timestamp in `title`), version; right side
   buttons: Sync now, Preview, Refresh (+ small "updated hh:mm:ss" / spinner). On narrow screens badges wrap into a
   horizontal scroll, never overflow the page.
2. **General** card: last attempt, next sync, error code, bw/sops versions, change check (enabled/interval/last/result,
   triggered syncs). The **shrink guard card** (removed/added/changed key names, "Apply anyway" with confirm) appears
   directly under the topbar only while `error_code == shrink_guard` and `guard` is an object.
3. **Providers** table (status, items, revision, last success, error, problems).
4. **Tabs** (`role=tablist`, keyboard accessible, counts in the labels where cheap):
   - **Keys**: search box (substring, case-insensitive, instant), sections Added / Removed / Changed (only when
     non-empty) and "All keys (n)"; synthetic keys carry the "synthetic" badge; cap rendered rows (500) with "+N more".
   - **Synthetic keys**: name, template (monospace), keys it uses, status (`ok`, parsed not rendered yet, error code).
     Empty state text when none configured.
   - **Key usage**: search box; summary line (files scanned, truncated, scanned at); lists Missing (red), Unused, Used
     (count + `file:line` refs, collapsed by default per key); disabled state text when `usage.enabled` is false.
   - **Events**: newest first with time, level colour, code, message (cap 100).
5. Keep behaviour of the old page: all texts remain English; guard confirm text "Remove N keys from secrets.yaml?".

### Tests

- Python (pytest): shell has no state data and references only relative assets; asset route whitelist/content types/404
  for traversal; ingress-only for `/` and assets; `/api/status.json` unchanged; XSS payloads in the JSON must not be
  rendered as markup (JS tests below); old `render_page`/`_render_*` code removed with their tests replaced.
- JS: keep rendering logic in `static/app.js` as small pure functions (`filterKeys`, `relTime`, `statusBadge`,
  `buildGuardCard`... returning DOM nodes via an injected `document`) so they can be unit tested with `node --test`
  (`tests/web/js/*.test.mjs`); the pytest suite runs them via `subprocess` and skips when `node` is missing. Node is in
  the add-on image anyway. Include tests: XSS strings in key names/templates/messages end up as text, missing blocks,
  search filtering, tab selection from hash, guard card only for shrink_guard.
- Manual check by the agent: run the server against `docs/state.example.json` plus a guard variant and report that the
  page renders (a headless screenshot is welcome if a browser is available; do not install system packages).
