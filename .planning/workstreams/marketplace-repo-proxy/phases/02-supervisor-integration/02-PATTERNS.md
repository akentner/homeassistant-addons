# Phase 2: Supervisor integration - Pattern Map

**Mapped:** 2026-11-18
**Files analyzed:** 19 (new + modified)
**Analogs found:** 18 / 19

All paths are relative to the repository root and git-tracked. Phase 1 code in `marketplace-repo-proxy/` is the
primary analog source; the only external analog is `secrets-sync/app/engine/reload.py` (stdlib Supervisor call).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `marketplace-repo-proxy/app/supervisor.py` (NEW) | service (HTTP client) | request-response | `secrets-sync/app/engine/reload.py` (lines 9-36) | role-match |
| `marketplace-repo-proxy/app/registration.py` (NEW) | service | event-driven (after cycle, request queue) | `marketplace-repo-proxy/app/sync.py` `run_cycle` / `SyncService` | role-match |
| `marketplace-repo-proxy/app/supervisor_state.py` (NEW, or inside registration.py) | store (single writer) | file-I/O | `marketplace-repo-proxy/app/status.py` `StatusWriter` (lines 57-125) | exact |
| `marketplace-repo-proxy/app/sync.py` (MOD) | service loop | event-driven | itself: `wait_reason` (185-194), `run_cycle_once` (196-204), `main` (235-278) | exact |
| `marketplace-repo-proxy/app/access.py` (MOD) | store | CRUD, file-I/O | itself: `RESERVED_USERS` (32), `add` (152-200), `revoke` (202-220) | exact |
| `marketplace-repo-proxy/app/cli.py` (MOD) | controller (CLI) | request file write | itself: `_parser` (39-68), `_sync` (138-145), `_dispatch` (155-166) | exact |
| `marketplace-repo-proxy/app/paths.py` (MOD) | model | - | itself: `Paths._build` (lines 27-39 in file, `trigger_file`) | exact |
| `marketplace-repo-proxy/app/urls.py` (reuse) | utility | transform | itself: `internal_base`, `store_url`, `masked_store_url` | exact |
| `marketplace-repo-proxy/app/logsetup.py` (reuse) | utility | - | `HASH_TOKEN_RE`, `Redactor.register`, `mask_hashes` | exact |
| `marketplace-repo-proxy/tests/fake_supervisor.py` (NEW) | test fixture | request-response | `marketplace-repo-proxy/tests/test_sync.py` `_Unauthorized` + `ThreadingHTTPServer` (194-213); `tests/upstream.py` (module style) | role-match |
| `marketplace-repo-proxy/tests/test_supervisor.py` (NEW) | test | - | `marketplace-repo-proxy/tests/test_sync.py` (1-40, 204-216) | role-match |
| `marketplace-repo-proxy/tests/test_registration.py` (NEW) | test | - | `marketplace-repo-proxy/tests/test_sync.py` + `tests/test_access.py` | role-match |
| `marketplace-repo-proxy/tests/test_cli.py`, `test_sync.py`, `test_access.py` (MOD) | test | - | themselves | exact |
| `internal/verify-marketplace-repo-proxy.sh` (MOD) | integration test | docker | itself: containers (12-30, 181-187, 307-311), needles (516-539), env checks (601-606) | exact |
| `marketplace-repo-proxy/config.yaml` (MOD) | config | - | `coding-assistants/config.yaml` lines 6-7 (`hassio_api`/`hassio_role`) | exact |
| `marketplace-repo-proxy/rootfs/etc/s6-overlay/s6-rc.d/sync/run` (unchanged, verify) | config | - | already `with-contenv` (token reaches sync only) | exact |
| `marketplace-repo-proxy/DOCS.md`, `README.md`, `CHANGELOG.md` (MOD) | docs | - | themselves (DOCS `## Contracts` 163-282, `register_local` row line 40; CHANGELOG `## [0.1.0-1]`) | exact |
| `marketplace-repo-proxy/translations/en.yaml`, `de.yaml` (MOD) | config | - | themselves (`register_local` at en.yaml:23) | exact |
| Live E2E plan (MRP-11, host runbook) | procedure | - | none in code | no analog |

## Pattern Assignments

### `marketplace-repo-proxy/app/supervisor.py` (service, request-response)

**Analog:** `secrets-sync/app/engine/reload.py` lines 9-36 (only stdlib Supervisor client in the Python code base).

```python
import logging
import os
import urllib.error
import urllib.request

URL = "http://supervisor/addons/self/options/config"
SKIPPED = "skipped"  # not running under a Supervisor (no SUPERVISOR_TOKEN)

def supervisor_reload() -> str | None:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return SKIPPED
    req = urllib.request.Request(URL, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - fixed internal URL
            resp.read(0)
            return None if resp.status == 200 else f"http_{resp.status}"
    except urllib.error.HTTPError as exc:
        return f"http_{exc.code}"
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return type(exc).__name__
```

Copy: lazy token read from `os.environ` (D-03), `SKIPPED` when no token, result codes `http_<n>` / exception class name
(never the exception text), fixed timeout. Extend per RESEARCH Pattern 1 (02-RESEARCH.md ~lines 456-500): `ALLOWED`
set of `(method, template)`, `SLUG_RE.fullmatch` (not `^...$`, Phase 1 WR-02), opener via
`urllib.request.build_opener(urllib.request.ProxyHandler({}), <no-redirect handler>)`, injected transport/base URL for
the fake. Logging per D-04: method + template + code only, logger name `mrp.supervisor` (Phase 1 convention
`logging.getLogger("mrp.sync")`, sync.py:40). Never log the request body (contains the full store URL).

### `marketplace-repo-proxy/app/registration.py` (service, event-driven)

**Analog:** `marketplace-repo-proxy/app/sync.py`.

Per-repository loop, one failure never ends the pass (sync.py:119-125):

```python
for spec in options.repositories:
    if stop is not None and stop.is_set():
        break
    try:
        outcome = _sync_one(paths, options, upstream, spec)
    except Exception as exc:  # one broken repository must not end the cycle for the others
        outcome = Outcome("fetch_failed", f"internal error: {type(exc).__name__}", spec.branch)
```

Outcome dataclass (sync.py:58-65) — `refs_changed` is the reload-gate input (D-08):

```python
@dataclass
class Outcome:
    status: str
    ...
    refs_changed: bool = False
```

Registration gate D-07: only `status == "ok"` (sync.py:97-99 distinguishes `no_repository_yaml`). Local user via
`AccessStore(paths).add(spec.slug, "local", source="system", specs=options.repositories)` (access.py:152-200);
`AccessError("user_exists")` means already present -> read with `AccessStore.get(repository, "local")` (access.py:131).
Internal URL: `store_url(internal_base(socket.gethostname()), owner, name, hash_)` (urls.py:14-19; hostname as in
cli.py:182). Logs use `masked_store_url` (urls.py:22-23). Clock/sleep injection like `SyncService.__init__`
(sync.py:159-179: `clock=time.monotonic`, `wall=time.time`) for the rate-limited reload gate.

Request queue (rotate/remove from CLI): mirror the trigger-file contract, unlink-before-handle so new requests survive
(sync.py:196-198):

```python
# Unlink before the cycle: a request created while it runs must survive and cause one more cycle
self.paths.trigger_file.unlink(missing_ok=True)
```

### `marketplace-repo-proxy/app/supervisor_state.py` (store, file-I/O, single writer)

**Analog:** `marketplace-repo-proxy/app/status.py` `StatusWriter` (lines 57-125).

```python
def _write(self) -> None:
    self._doc["updated"] = utc_timestamp()
    self._doc["repositories"] = list(self._entries.values())
    self._paths.status_file.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(self._paths.status_file, self._doc)

def snapshot(self) -> dict:
    return copy.deepcopy(self._doc)
```

Seeded from the previous file at construction (status.py:35-56 `_previous_entries` / `_carry`) so leftovers (D-10)
survive restarts. Document carries `"schema": SCHEMA`. Atomic write via `app/jsonio.py:12-30` (mode 0600, fsync,
rename, dir fsync); read via `read_json` (jsonio.py:50-56, returns None when missing, ValueError on bad JSON).
Content rule: slug + masked URL only, never a full hash (verify needles check it, see below).

### `marketplace-repo-proxy/app/paths.py` (model)

**Analog:** itself, `Paths` dataclass + `_build`:

```python
            run_dir=run_dir,
            lock_file=run_dir / "access.lock",
            trigger_file=run_dir / "sync.request",
            gitconfig_file=gitconfig_file,
```

Add fields (e.g. `supervisor_state_file=data_dir / "supervisor.json"`, `supervisor_requests_dir=run_dir /
"supervisor.requests"`) to the dataclass and `_build`; `default()` / `under()` need no change. No env overrides
(docstring of `default()`).

### `marketplace-repo-proxy/app/sync.py` (modify)

- `wait_reason` (185-194): add the new wake-up reasons (request queue non-empty, pending reload due) next to
  `trigger_file.exists()`; each new reason must be added to `REASONS` in `app/status.py` (`begin_cycle` raises
  `ValueError` on unknown reasons, status.py:109-113).
- `run_cycle_once` (196-204): call registration after `run_cycle` inside the `try`, before `end_cycle`.
- `main` (252-253): register the Supervisor token with the redactor next to the PAT:
  `redactor.register(secret_forms(options.github_token))` -> also `redactor.register([os.environ.get("SUPERVISOR_TOKEN", "")])`
  (Redactor ignores values shorter than 4, logsetup.py:13,24-28).
- `run_cycle` returns nothing today; registration needs per-repo `status` + `refs_changed` (read from
  `writer.snapshot()` or return the outcomes).

### `marketplace-repo-proxy/app/access.py` (modify)

```python
SOURCES = ("gui", "api", "system", "cli")
RESERVED_USERS = frozenset({"local"})  # Phase 2's system user; only source "system" may use these labels
...
        if user.lower() in RESERVED_USERS and source != "system":
            raise AccessError("user_reserved")
```

Extend the reservation to `local.*` (retired labels, D-09/D-11) with a helper `is_reserved(user)`; add the same check
to `revoke` (202-220, currently none) with a `source`/`system` flag so the CLI cannot revoke reserved labels.
Error codes stay short snake_case strings (`AccessError(code)`, access.py:39-45).

### `marketplace-repo-proxy/app/cli.py` (modify)

Subcommand pattern (`_parser` 39-68, `commands.add_parser(...)`), error output `_error(code)` -> `error: <code>` on
stderr, exit 1 (71-73). Request-file write, copy `_sync` (138-145):

```python
def _sync(paths: Paths) -> int:
    if not paths.run_dir.is_dir():
        paths.run_dir.mkdir(parents=True, exist_ok=True)
        paths.run_dir.chmod(0o700)
    atomic_write_json(paths.trigger_file, {})
    print("sync requested", flush=True)
    return 0
```

`mrp local status|rotate|remove [--revoke-old]` writes one JSON file into the requests dir and returns; `status` reads
`supervisor.json` via `read_json`. Update `EPILOG` (20-37; the "no in-place rotation" note now has an exception for
`local`). Must never import `app.supervisor` (RESEARCH ~line 600; add a static test).

### `marketplace-repo-proxy/tests/fake_supervisor.py` (test fixture)

**Analog:** `marketplace-repo-proxy/tests/test_sync.py` lines 194-213 plus module style of `tests/upstream.py`
(docstring, `from __future__ import annotations`, placeholder identity, no network).

```python
class _Unauthorized(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(401)
        ...
    def log_message(self, *_: object) -> None:
        return

server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Unauthorized)
threading.Thread(target=server.serve_forever, daemon=True).start()
...
finally:
    server.shutdown()
    server.server_close()
```

Add `do_POST`/`do_DELETE`, bearer check, Supervisor envelope `{"result": "ok"|"error", "data": ..., "message": ...}`,
409 duplicate (RESEARCH ~line 326), add-clones-URL behaviour (D-13: use `git ls-remote` against the URL with
`tests/upstream.py:git_env()`), configurable refusal for DELETE, and a `__main__` entry so the verify container can run
it (`python3 -m` / script on port 80 under alias `supervisor`). Tests import it like `from upstream import ...`
(test_sync.py:17; `tests/` is on sys.path via conftest).

### `marketplace-repo-proxy/tests/test_supervisor.py`, `test_registration.py` (tests)

**Analog:** `marketplace-repo-proxy/tests/test_sync.py` header (1-40): module docstring stating "never a real
Supervisor", `_ticking_clock` autouse fixture patching `status.utc_timestamp`, tokens built at runtime
(`"sentinel" + "-pat-" + ...`, test_sync.py:37-39) so no token-shaped literal is committed. Use `Paths.under(tmp_path)`
and `caplog` to assert no token / full hash in logs (pattern of `test_token_never_reaches_status_or_log`, 204-216).

### `internal/verify-marketplace-repo-proxy.sh` (modify)

- Names from `PREFIX` (lines 16-20): add `SUPERVISOR="${PREFIX}-supervisor"`; reuse `SUPERVISOR_SENTINEL` (line 22) as
  the fake's expected bearer token.
- Container start on the verify net, copy `docker run -d --name ... --network "${NET}"` (187, 307-311); fake needs
  `--network-alias supervisor` so `http://supervisor` resolves inside the proxy.
- Proxy already gets `-e "SUPERVISOR_TOKEN=${SUPERVISOR_SENTINEL}"` (310); keep the lighttpd/watch env checks (601-606).
- Waits: `wait_for` / `wait_field` helpers (60-101); add a reader for `/data/supervisor.json` like `field_of` (72-83).
- Needles: `NEEDLES_HASH` (516-539) must include the `local` user hashes; extend the `status.json` scan (~570) to
  `supervisor.json` and the fake Supervisor's own log. Output `ok`/`fail` one-liners (31-32); cleanup via `trap
  cleanup EXIT` (48-58) must also remove the fake container.

### `marketplace-repo-proxy/config.yaml` (config)

**Analog:** `coding-assistants/config.yaml` lines 6-7:

```yaml
hassio_api: true
hassio_role: manager
```

Insert after `init: false` (line 6). Version bump only via `make update-version ADDON=marketplace-repo-proxy
VERSION=0.1.0` with subpatch `-2` (D-18/D-21), never by hand.

### Docs and translations

- `DOCS.md` line 40: drop "**No effect yet**" from the `register_local` row; add `### /data/supervisor.json` under
  `## Contracts` in the style of `### /data/status.json` (213-275); extend `## Security notes` (283) with the manager
  role and token handling; `## Managing users` (95) gets `mrp local ...`.
- `CHANGELOG.md`: new `## [0.1.0-2] - <date>` with `### Added` / `### Changed`, as `[0.1.0-1]` (line 6).
- `translations/en.yaml` / `de.yaml`: update `register_local` description (en.yaml:23).
- Markdown 120-char limit, prettier `proseWrap: always`.

## Shared Patterns

### Atomic JSON + timestamps
**Source:** `marketplace-repo-proxy/app/jsonio.py` 12-30, 50-61. **Apply to:** supervisor state, request files, CLI.

### Secret hygiene in logs
**Source:** `marketplace-repo-proxy/app/logsetup.py` 13-14 (`HASH_TOKEN_RE`), 22-36 (`Redactor`), 44-46
(`mask_hashes`), 60-68 (`setup_logging`). **Apply to:** all new modules. Full store URLs are masked by
`SafeFormatter` already; still log `masked_store_url` explicitly. Register `SUPERVISOR_TOKEN` with the redactor.

### Error codes, not messages
**Source:** `AccessError(code)` (access.py:39-45), `_error(code)` (cli.py:71-73), `http_<n>` /
`type(exc).__name__` (reload.py:31-36). **Apply to:** Supervisor client results, CLI, supervisor.json entries.

### Locking
**Source:** `AccessStore.locked()` (access.py:84-104, flock on `run_dir/access.lock`, reentrant). **Apply to:** every
change of the `local` entry (add new / retire old) during rotation.

### Single writer per JSON file
**Source:** `StatusWriter` docstring (status.py:57-58). **Apply to:** `supervisor.json` is written by the sync process
only; the CLI only writes request files.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| MRP-11 live E2E plan (host runbook, `autonomous: false`) | procedure | manual | No prior live-host E2E plan in this workstream; follow D-14 to D-17 and RESEARCH directly |

## Metadata

**Analog search scope:** `marketplace-repo-proxy/app`, `marketplace-repo-proxy/tests`, `internal/`, other add-ons'
Python Supervisor callers (`secrets-sync`, `admin-ui`, `haos-monitor`), add-on `config.yaml` files.
**Files scanned:** ~25
**Pattern extraction date:** 2026-11-18
