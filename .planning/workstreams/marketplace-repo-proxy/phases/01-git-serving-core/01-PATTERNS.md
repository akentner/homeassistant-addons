# Phase 1: Git serving core - Pattern Map

**Mapped:** 2026-11-17
**Files analyzed:** 27 (new + modified, per RESEARCH "Recommended Project Structure")
**Analogs found:** 21 / 27

All analog paths below are git-tracked (checked with `git ls-files`).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
| --- | --- | --- | --- | --- |
| `marketplace-repo-proxy/config.yaml` (mod) | config | - | `ntfy/config.yaml`, `secrets-sync/config.yaml` | exact |
| `marketplace-repo-proxy/translations/en.yaml` (mod) | config | - | `ntfy/translations/en.yaml` | exact |
| `marketplace-repo-proxy/Dockerfile` (mod) | config | build | `ntfy/Dockerfile` | role-match (no CMD, adds rootfs) |
| `marketplace-repo-proxy/run.sh` (mod) | utility | oneshot | existing scaffold `run.sh` | partial |
| `marketplace-repo-proxy/DOCS.md`, `CHANGELOG.md` (mod) | docs | - | `ntfy/DOCS.md` | exact |
| `rootfs/etc/lighttpd/marketplace-repo-proxy.conf` | config | request-response | `marketplace-repo-proxy/SPIKE.md` (server section) | no repo analog |
| `rootfs/etc/s6-overlay/s6-rc.d/{init,lighttpd,sync}/*`, `user-bundles.d/...` | config | service lifecycle | none in repo (RESEARCH Pattern 1) | no analog |
| `app/__init__.py` | module | - | `ntfy/app/__init__.py` | exact |
| `app/paths.py` | model | - | `ntfy/app/contract.py` `Paths` (lines 47-80) | exact |
| `app/options.py` | model | file-I/O | `ntfy/app/contract.py` `load_options` (lines 98-120, 194-205) | exact |
| `app/access.py` | store | CRUD, file-I/O | `ntfy/app/origins.py` `OriginStore` | exact |
| `app/status.py` | store | file-I/O (single writer) | `ntfy/app/origins.py` `_save` (lines 139-158); `secrets-sync/app/engine/state.py` | role-match |
| `app/gitops.py` | service | subprocess | `ntfy/app/ntfycli.py` (CLI wrapper + error codes) | role-match |
| `app/sync.py` | service | event loop | `secrets-sync/app/main.py` + `engine/supervisor.py` | role-match |
| `app/init.py` | service | oneshot / transform | `ntfy/app/bootstrap.py`, `ntfy/app/render_config.py` | role-match |
| `app/urls.py` | utility | transform | none | no analog |
| `app/logsetup.py` | utility | - | `secrets-sync/app/main.py` `setup_logging` (lines 20-26) + `engine/redact.py` | exact |
| `app/cli.py` | controller | CLI | `secrets-sync/app/main.py` `main` (argparse, lines 51-70) | role-match |
| `tests/conftest.py` | test | - | `ntfy/tests/conftest.py` | exact |
| `tests/test_access.py` etc. | test | - | `ntfy/tests/test_origins.py` | exact |
| `tests/` git fixture helper | test | file-I/O | none (local bare repo fixture) | no analog |
| `internal/verify-marketplace-repo-proxy.sh` | test (integration) | docker | `internal/verify-ntfy-scaffold.sh` + `internal/verify-secrets-sync-no-secret-leak.sh` | exact |
| `.github/workflows/lint.yml` (mod) | config (CI) | - | `ntfy` job, lines 259-294 | exact |

## Pattern Assignments

### `marketplace-repo-proxy/config.yaml` (config)

**Analogs:** `ntfy/config.yaml` lines 28-56, `secrets-sync/config.yaml` lines 25-69.
Keep existing scaffold keys (`init: false`, `ports: 8080/tcp: null`, `image:`). Version via `make update-version` only.

Schema syntax to copy (ntfy lines 43-48):

```yaml
  admin_password: "password"
  baseline_users:
    - username: "match(^[a-zA-Z0-9_][-_.+@a-zA-Z0-9]{0,63}$)"
      password: "password"
      topic: "match(^[-_a-zA-Z0-9*]{0,64}$)"
  attachment_total_size_limit: "match(^[0-9]+[KMGkmg]?$)?"   # trailing ? = optional
```

Apply to D-16: `github_token: password`, `sync_interval: "int(5,)"`, `public_url: "url?"` (or `str?`),
`repositories: [{repository: "match(^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$)", branch: "str?"}]`, `register_local: bool`,
`api_enabled: bool`, `log_level: "list(debug|info|warning|error)"` (already present). Defaults in `options:` like
`secrets-sync/config.yaml` lines 25-34 (`synthetic_keys: []` style for an empty list).

### `marketplace-repo-proxy/translations/en.yaml` (config)

**Analog:** `ntfy/translations/en.yaml` lines 1-30 — `configuration: <key>: {name, description}`, description wraps
at 120 chars with continuation indent of 6 spaces. One entry per D-16 option; `github_token` description must state
"Contents: read-only fine-grained PAT".

### `marketplace-repo-proxy/Dockerfile` (config, build)

**Analog:** `ntfy/Dockerfile`. Copy:

```dockerfile
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM ${BUILD_FROM}
RUN apk add --no-cache python3 ...          # here: git git-daemon lighttpd python3 (git-http-backend ships in git-daemon on Alpine; verify)
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/ntfy-gui                        # here: /opt/marketplace-repo-proxy
COPY app/ ./app/
COPY run.sh /run.sh
RUN chmod +x /run.sh
```

Deviation: no `CMD` (s6-overlay supervises longruns, RESEARCH Pattern 1), add `COPY rootfs/ /`. Local `docker build`
before commit (CLAUDE.md).

### `rootfs/etc/s6-overlay/...` (no repo analog)

No add-on in this repo uses s6-rc services. Use the literal files from RESEARCH.md "Pattern 1" (prototype-verified):
`user-bundles.d/user/contents.d/<name>` (not `s6-rc.d/user`), `init` oneshot with `dependencies.d/base`,
`lighttpd` run as `#!/bin/sh` (no `with-contenv`, keeps env clean for D-17), `sync` run as
`#!/command/with-contenv sh`.

### `rootfs/etc/lighttpd/marketplace-repo-proxy.conf` (no repo analog)

Copy verbatim from `marketplace-repo-proxy/SPIKE.md` section "Server: lighttpd + git http-backend" (D-01, D-04), with
`GIT_PROJECT_ROOT=/srv/git/access` via `setenv.set-environment`.

### `app/paths.py` (model)

**Analog:** `ntfy/app/contract.py` lines 47-80 — frozen dataclass derived from one data dir, env override for tests:

```python
@dataclass(frozen=True)
class Paths:
    data_dir: Path
    options_file: Path
    ...
    @classmethod
    def for_dir(cls, data_dir: Path | str, options_file: Path | str | None = None) -> "Paths":
        base = Path(data_dir)
        return cls(data_dir=base, options_file=Path(options_file) if options_file else base / "options.json", ...)

    @classmethod
    def from_env(cls) -> "Paths":
        return cls.for_dir(os.environ.get("NTFY_DATA_DIR", "/data"), os.environ.get("NTFY_OPTIONS") or None)
```

Here: `data_dir`, `access_file`, `status_file`, `trigger_file`, `repos_root=/srv/git/repos`,
`access_root=/srv/git/access`, `lock_file=/run/marketplace-repo-proxy/access.lock`. The test-only upstream override
(D-18) belongs in the same `from_env` style (env var, e.g. `MRP_UPSTREAM_BASE`), never in options.

### `app/options.py` (model, file-I/O)

**Analog:** `ntfy/app/contract.py` lines 98-120 (`OptionsError`, frozen `Options` dataclass with
`field(default="", repr=False)` for secrets) and lines 194-205:

```python
def load_options(path: Path | str) -> Options:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    except (OSError, ValueError) as exc:
        raise OptionsError(f"cannot read options: {type(exc).__name__}") from exc
    if not isinstance(data, dict):
        raise OptionsError("options must be a JSON object")
    return parse_options(data)
```

`github_token: str = field(default="", repr=False)` is mandatory (keeps the PAT out of reprs/logs, D-17). Error
messages carry only the exception type, never content.

### `app/access.py` (store, CRUD)

**Analog:** `ntfy/app/origins.py` (whole file, ~160 lines read). Copy:

- Module docstring stating the contract + corrupt-file behaviour (lines 1-5).
- `SCHEMA = 1`, `_empty()`, regex validators (`TOKEN_ID_RE`, lines 25-45) -> here `HASH_RE = ^[0-9a-f]{32}$`,
  `USER_RE`, sources `("gui", "api", "system")`.
- `_valid_document()` shape check (lines 48-70).
- Cross-process lock + reload-on-change (lines 79-117): `threading.RLock` + `fcntl.flock` on a lock file, `_signature()`
  via `(st_ino, st_mtime_ns, st_size)`, `_refresh()` inside `_txn()`. Lock path per RESEARCH is
  `/run/marketplace-repo-proxy/access.lock` instead of `<file>.lock`.
- Corrupt file -> rename to `.corrupt`, start empty, log without content (lines 121-137).
- Atomic write (lines 139-158):

```python
fd, tmp = tempfile.mkstemp(dir=self._path.parent, prefix=".origins-", suffix=".tmp")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        os.fchmod(handle.fileno(), 0o600)
        json.dump(self._doc, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, self._path)
    self._sig = self._signature()
except BaseException:
    try:
        os.unlink(tmp)
    except OSError:
        pass
    raise
```

Hash generation: `secrets.token_hex(16)` (stdlib, /dev/urandom). Reconcile (symlink tree rebuild, D-06) has no
analog; write it to a temp dir + rename or remove-all-then-create at init.

### `app/status.py` (store, single writer)

Reuse the same atomic-write helper (extract `atomic_write_json(path, doc)` into one function shared by `access.py`
and `status.py`, as RESEARCH "Interface Contracts" names it). Secondary analog: `secrets-sync/app/engine/state.py`
(around line 117, `os.replace(tmp, self.path)`). No lock (single writer).

### `app/gitops.py` (service, subprocess)

**Analog:** `ntfy/app/ntfycli.py` (wraps an external CLI and maps failures to stable codes, cf.
`ntfy/app/contract.py` `CLI_ERROR_TO_API`, codes `exists|not_found|invalid|other`). Here codes are D-14
(`ok|auth_failed|not_found|no_repository_yaml`). Env per D-8: `GIT_CONFIG_COUNT/KEY_0/VALUE_0`, passed as `env=` to
`subprocess.run`, plus `GIT_TERMINAL_PROMPT=0`; never put the token in argv. Stderr must go through the redactor
before logging.

### `app/sync.py` (service loop)

**Analog:** `secrets-sync/app/main.py` lines 51-70 + `secrets-sync/app/engine/supervisor.py`:

```python
cfg = load_config()
redactor = Redactor()
setup_logging(cfg.log_level, redactor)
supervisor = Supervisor(cfg, redactor=redactor)
log.info("Secrets Sync %s starting (providers: %s)", ...)
if args.once:
    supervisor.run_once(); return 0
for sig in (signal.SIGTERM, signal.SIGINT):
    signal.signal(sig, lambda *_: supervisor.stop())
supervisor.run_forever()
```

Keep `--once` (useful for tests and the verify script). Loop waits on interval OR trigger-file presence (D-12).
`redactor.register([opts.github_token, basic_auth_b64])` before the first fetch.

### `app/logsetup.py` (utility)

**Analog:** `secrets-sync/app/main.py` lines 20-26 and `secrets-sync/app/engine/redact.py` (Redactor `logging.Filter`,
`MIN_LEN = 4`, scrub longest first). Copy both; `ntfy/app/gui.py` line 32 shows the `LEVELS` dict mapping for
`log_level`. Add a hash scrubber (32-hex regex -> masked) for D-17.

### `app/cli.py` and `app/init.py`

`argparse.ArgumentParser` + `def main(argv: list[str] | None = None) -> int` + `sys.exit(main())` guard, as in
`secrets-sync/app/main.py` lines 51-55 and repo Python conventions (CLAUDE.md). `init.py` analog for the
"render config at start" role: `ntfy/app/render_config.py` (atomic `os.replace(tmp, paths.server_yml)`, line 55).

### `tests/conftest.py` and `tests/test_*.py`

**Analog:** `ntfy/tests/conftest.py` (verbatim, rename `NTFY_DIR`):

```python
TESTS_DIR = Path(__file__).resolve().parent
NTFY_DIR = TESTS_DIR.parent
for entry in (str(NTFY_DIR), str(TESTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)
```

Test style: `ntfy/tests/test_origins.py` — plain functions with `tmp_path`, `pytest.raises(ValueError)` for bad input,
reopen store from disk to prove persistence. Git fixture: build a local bare upstream with `git init --bare` in
`tmp_path` (no repo analog; skip with `pytest.importorskip`-style guard if `git` is missing).

### `internal/verify-marketplace-repo-proxy.sh` (integration test)

**Analogs:** `internal/verify-ntfy-scaffold.sh` (structure) and `internal/verify-secrets-sync-no-secret-leak.sh`
(sentinel leak scan). Copy:

- Header (ntfy lines 1-6): purpose, manual invocation, "do not run it in two worktrees at the same time" (D-23),
  `set -euo pipefail`, `PREFIX` / `WORK` env overrides.
- `fail()`, `yget()` (PyYAML with `!` tag tolerance, lines 15-28), `cleanup` trap removing root-owned data through the
  image (lines 30-38), `wait_for` helper.
- Build from build.yaml (lines 74-78):

```bash
docker build \
    --build-arg BUILD_FROM="$(yget "${ADDON_DIR}/build.yaml" build_from.amd64)" \
    --build-arg VERSION="$(yget "${ADDON_DIR}/build.yaml" args.VERSION)" \
    -t "${IMAGE_TAG}" "${ADDON_DIR}"
```

- options.json written via `python3 -I` + `json.dump` (lines 82-88) with a `SENTINEL` token.
- HTTP probe via `docker exec ... curl -s --path-as-is -w '\n%{http_code}'` (`gui()` helper) -> reuse for the
  404/403/200 matrix from SPIKE "Observed responses".
- Leak scan (secrets-sync lines 13-80): `SENTINELS=(...)`, collect `docker logs`, data files, `ps -eo args`, and
  `/proc/<lighttpd pid>/environ`; `check <label> <haystack>` with `grep -qF`. Add: full-hash grep in logs.
- Output style: `echo "==> step"`, `echo "✓ ..."`, `echo "✗ ..."`.

### `.github/workflows/lint.yml` (CI)

**Analog:** `ntfy` job lines 259-294. Append a `marketplace-repo-proxy` job at the end (comment "Appended on purpose ...
line-anchored zizmor deferrals"), `actions/checkout@v7` with `persist-credentials: false`, `setup-python@v7` 3.12,
`pip install 'pytest==9.1.1'`, `python -m pytest marketplace-repo-proxy/tests -q`. Git is present on ubuntu runners.

## Shared Patterns

### Secret hygiene (D-17)
**Sources:** `secrets-sync/app/engine/redact.py` (Redactor filter), `ntfy/app/contract.py` (`field(repr=False)`),
`internal/verify-secrets-sync-no-secret-leak.sh` (sentinel scan). Apply to all `app/*` modules and the verify script.

### Atomic JSON write + flock
**Source:** `ntfy/app/origins.py` lines 99-158. Apply to `access.py`, `status.py`, init's reconcile.

### Path contract
**Source:** `ntfy/app/contract.py` `Paths` lines 47-80. Every module takes `Paths`, tests use `Paths.for_dir(tmp_path)`.

### Logging
**Source:** `secrets-sync/app/main.py` lines 20-26 (stdout handler, one format, level from options).

## No Analog Found

| File | Role | Data Flow | Reason |
| --- | --- | --- | --- |
| `rootfs/etc/s6-overlay/**` | config | lifecycle | No add-on in repo uses s6-rc services; use RESEARCH Pattern 1 literals |
| `rootfs/etc/lighttpd/marketplace-repo-proxy.conf` | config | request-response | No lighttpd in repo; use SPIKE.md config |
| `app/urls.py` | utility | transform | Store URL building/masking is new |
| symlink reconcile (in `access.py`/`init.py`) | service | file-I/O | No symlink-tree code in repo |
| `app/gitops.py` git env/fetch | service | subprocess | Only loose analog (ntfycli); follow RESEARCH Code Examples |
| local upstream git fixture (tests + verify) | test | file-I/O | No git fixtures in repo |

## Metadata

**Analog search scope:** `ntfy/`, `secrets-sync/`, `haos-monitor/`, `internal/`, `.github/workflows/lint.yml`,
`marketplace-repo-proxy/`
**Files scanned:** ~25
**Pattern extraction date:** 2026-11-17
