"""Fake Home Assistant Supervisor store API for pytest and the verify script; never a real Supervisor.

Imported by pytest (`serve` runs it in-process) and run as a script in the verify container (`main`). Stdlib only:
the proxy image has git and python3 but no PyYAML. Behaviour copied from the Supervisor where it matters (D-13): the
four store routes with the exact paths, plain-text 401/403 from the auth middleware, the JSON envelope, the store slug
`sha1(url.lower())[:8]`, a synchronous add that clones the URL (`git clone --depth 1`) and needs a repository file with
a `name`, the 409 duplicate, the 400 "used by installed apps" refusal and the 404 for an unknown slug.

Every request is recorded as `{"method", "path", "auth", "status"}` (plus `"slug"` for POST/DELETE); `auth` is `ok`,
`missing` or `wrong`, never the token. Store URLs (`source`) stay in memory: nothing with a URL or the token is ever
written to disk or stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

# Messages as in the Supervisor source (supervisor/exceptions.py, store/__init__.py, api/store.py)
DUPLICATE_ERROR_KEY = "store_repository_already_added_error"
DUPLICATE = "Can't add {url}, already in the store"
REFUSAL = "Can't remove '{source}'. It's used by installed apps"
NOT_FOUND = "Repository {slug} does not exist in the store"
BUILTIN = "Can't remove built-in repositories!"
INVALID_REPOSITORY = "{url} is not a valid app repository"
INVALID_URL = "expected a URL for dictionary value @ data['repository']"
RE_REPOSITORY = re.compile(r"^(?P<url>[^#\s]+)(?:#(?P<branch>[\w\-./]+))?$")  # supervisor/store/validate.py
REPOSITORIES = "/store/repositories"
RELOAD = "/store/reload"
GIT_TIMEOUT = 120
BUILTINS = {
    "core": {"slug": "core", "name": "Official apps", "source": "core", "url": "", "maintainer": "Home Assistant"},
    "local": {"slug": "local", "name": "Local apps", "source": "local", "url": "", "maintainer": "you"},
}


def store_slug(url: str) -> str:
    return hashlib.sha1(url.lower().encode("utf-8")).hexdigest()[:8]


def _git_env() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    }


def _repository_name(directory: Path) -> str | None:
    """`name` of repository.yaml/.yml (first `name:` line, quotes stripped) or repository.json."""
    for filename in ("repository.yaml", "repository.yml"):
        path = directory / filename
        if path.is_file():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("name:"):
                    name = line[len("name:") :].strip().strip("'\"")
                    return name or None
            return None
    path = directory / "repository.json"
    if path.is_file():
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return None
        name = doc.get("name") if isinstance(doc, dict) else None
        return name if isinstance(name, str) and name else None
    return None


def git_clone_depth1(url: str) -> str:
    """Clone like the Supervisor's first load; returns the repository name, raises ValueError like the Supervisor."""
    match = RE_REPOSITORY.match(url)
    clone_url, branch = (match.group("url"), match.group("branch")) if match else (url, None)
    with tempfile.TemporaryDirectory(prefix="fake-supervisor-") as tmp:
        target = Path(tmp) / "repository"
        args = ["git", "clone", "--depth", "1", "-q"]
        if branch:
            args += ["--branch", branch]
        try:
            proc = subprocess.run(
                [*args, clone_url, str(target)],
                env=_git_env(),
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise ValueError(f"git clone of {url} timed out") from None
        if proc.returncode != 0:
            # The Supervisor answers with git's command error, which names the URL
            raise ValueError(f"Can't clone {url}: git clone exited with {proc.returncode}")
        name = _repository_name(target)
        if not name:
            raise ValueError(INVALID_REPOSITORY.format(url=url))
        return name


def _ls_remote_head(source: str) -> str | None:
    match = RE_REPOSITORY.match(source)
    url = match.group("url") if match else source
    try:
        proc = subprocess.run(
            ["git", "ls-remote", url, "HEAD"],
            env=_git_env(),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return proc.stdout.split()[0]


class FakeState:
    """Store content and request log of one fake Supervisor."""

    def __init__(
        self,
        token: str,
        *,
        clone: Callable[[str], str] | None = None,
        in_use_file: Path | str | None = None,
        state_dir: Path | str | None = None,
    ) -> None:
        self.token = token
        self.clone = clone or git_clone_depth1
        self.in_use_file = Path(in_use_file) if in_use_file else None
        self.state_dir = Path(state_dir) if state_dir else None
        self.lock = threading.Lock()
        self.requests: list[dict[str, Any]] = []
        self.repos: dict[str, dict[str, Any]] = {slug: dict(item) for slug, item in BUILTINS.items()}
        self.in_use: set[str] = set()
        self.reloads = 0
        self.heads: dict[str, str | None] = {}
        if self.state_dir is not None:
            self.state_dir.mkdir(parents=True, exist_ok=True)

    def record(self, entry: dict[str, Any]) -> None:
        with self.lock:
            self.requests.append(entry)
            if self.state_dir is not None:
                with (self.state_dir / "requests.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry, sort_keys=True) + "\n")

    def save(self) -> None:
        """store.json: slugs, names, reload count and heads; never a source URL."""
        if self.state_dir is None:
            return
        with self.lock:
            doc = {
                "repositories": [{"slug": r["slug"], "name": r["name"]} for r in self.repos.values()],
                "reloads": self.reloads,
                "heads": dict(self.heads),
            }
        path = self.state_dir / "store.json"
        tmp = path.with_name(".store.json.tmp")
        tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def is_in_use(self, slug: str) -> bool:
        if slug in self.in_use:
            return True
        if self.in_use_file is not None:
            try:
                lines = self.in_use_file.read_text(encoding="utf-8").split()
            except OSError:
                return False
            return slug in lines
        return False

    def custom(self) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(r) for slug, r in self.repos.items() if slug not in BUILTINS]


class _Handler(BaseHTTPRequestHandler):
    server_version = "FakeSupervisor/1"
    protocol_version = "HTTP/1.1"

    @property
    def state(self) -> FakeState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, *_: object) -> None:  # no output: paths may carry slugs, bodies carry URLs
        return

    def _auth(self) -> str:
        value = self.headers.get("Authorization", "")
        if not value:
            return "missing"
        return "ok" if value.split(" ")[-1] == self.state.token else "wrong"

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length > 0 else b""

    def _send(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _text(self, status: int, text: str) -> int:
        self._send(status, text.encode("utf-8"), "text/plain; charset=utf-8")
        return status

    def _json(self, status: int, doc: dict[str, Any]) -> int:
        self._send(status, json.dumps(doc).encode("utf-8"), "application/json")
        return status

    def _ok(self, data: Any = None) -> int:
        return self._json(200, {"result": "ok", "data": {} if data is None else data})

    def _error(self, status: int, message: str, error_key: str | None = None, extra: dict | None = None) -> int:
        doc: dict[str, Any] = {"result": "error", "message": message}
        if error_key:
            doc["error_key"] = error_key
        if extra:
            doc["extra_fields"] = extra
        return self._json(status, doc)

    def _handle(self) -> None:
        method, path = self.command, self.path
        body = self._body()
        entry: dict[str, Any] = {"method": method, "path": path, "auth": self._auth()}
        if method in ("POST", "DELETE"):
            entry["slug"] = None
        if entry["auth"] == "missing":
            entry["status"] = self._text(401, "401: Unauthorized")
        elif entry["auth"] == "wrong":
            entry["status"] = self._text(403, "403: Forbidden")
        elif method == "GET" and path == REPOSITORIES:
            entry["status"] = self._ok([dict(r) for r in self.state.repos.copy().values()])
        elif method == "POST" and path == REPOSITORIES:
            entry["status"] = self._add(body, entry)
        elif method == "POST" and path == RELOAD:
            entry["status"] = self._reload()
        elif method == "DELETE" and path.startswith(REPOSITORIES + "/") and "/" not in path[len(REPOSITORIES) + 1 :]:
            slug = path[len(REPOSITORIES) + 1 :]
            entry["slug"] = slug
            entry["status"] = self._delete(slug)
        elif path in (REPOSITORIES, RELOAD) or path.startswith(REPOSITORIES + "/"):
            entry["status"] = self._text(405, "405: Method Not Allowed")
        else:
            entry["status"] = self._text(404, "404: Not Found")
        self.state.record(entry)
        if entry["status"] == 200 and method in ("POST", "DELETE"):
            self.state.save()

    def _add(self, body: bytes, entry: dict[str, Any]) -> int:
        try:
            doc = json.loads(body.decode("utf-8")) if body else None
        except (UnicodeDecodeError, ValueError):
            doc = None
        url = doc.get("repository") if isinstance(doc, dict) else None
        if not isinstance(url, str):
            return self._error(400, "required key not provided @ data['repository']")
        url = url.strip()
        match = RE_REPOSITORY.match(url)
        parts = urlsplit(match.group("url")) if match else None
        if parts is None or parts.scheme not in ("http", "https", "git", "ssh") or not parts.netloc:
            return self._error(400, INVALID_URL)
        slug = store_slug(url)
        entry["slug"] = slug
        if slug in self.state.repos:
            return self._error(409, DUPLICATE.format(url=url), DUPLICATE_ERROR_KEY, {"url": url})
        try:
            name = self.state.clone(url)
        except ValueError as exc:
            return self._error(400, str(exc))
        with self.state.lock:
            if slug in self.state.repos:
                return self._error(409, DUPLICATE.format(url=url), DUPLICATE_ERROR_KEY, {"url": url})
            self.state.repos[slug] = {"slug": slug, "name": name, "source": url, "url": url, "maintainer": "unknown"}
        return self._ok()

    def _delete(self, slug: str) -> int:
        repo = self.state.repos.get(slug)
        if repo is None:
            return self._error(404, NOT_FOUND.format(slug=slug))
        if slug in BUILTINS:
            return self._error(400, BUILTIN)
        if self.state.is_in_use(slug):
            return self._error(400, REFUSAL.format(source=repo["source"]))  # plain StoreError: no error_key
        with self.state.lock:
            self.state.repos.pop(slug, None)
            self.state.heads.pop(slug, None)
        return self._ok()

    def _reload(self) -> int:
        heads = {repo["slug"]: _ls_remote_head(repo["source"]) for repo in self.state.custom()}
        with self.state.lock:
            self.state.heads.update(heads)
            self.state.reloads += 1
        self.state.save()
        return self._ok()

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def do_DELETE(self) -> None:
        self._handle()

    def do_PUT(self) -> None:
        self._handle()

    def do_PATCH(self) -> None:
        self._handle()

    def do_HEAD(self) -> None:
        self._handle()


def _server(state: FakeState, host: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), _Handler)
    server.daemon_threads = True
    server.state = state  # type: ignore[attr-defined]
    return server


def serve(state: FakeState, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    """Start serving in a daemon thread; the caller shuts it down (`shutdown()`, `server_close()`)."""
    server = _server(state, host, port)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fake_supervisor",
        description="Fake Supervisor store API for tests (token from FAKE_SUPERVISOR_TOKEN).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--state-dir", type=Path, default=None)
    parser.add_argument("--in-use-file", type=Path, default=None)
    args = parser.parse_args(argv)
    token = os.environ.get("FAKE_SUPERVISOR_TOKEN", "").strip()
    if not token:
        print("FAKE_SUPERVISOR_TOKEN is empty", file=sys.stderr, flush=True)
        return 2
    state = FakeState(token, in_use_file=args.in_use_file, state_dir=args.state_dir)
    server = _server(state, args.host, args.port)
    state.save()  # readiness marker: the socket is bound
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
