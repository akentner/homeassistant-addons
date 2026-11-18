"""The only module that talks to the Home Assistant Supervisor (MRP-07, D-02 to D-04).

It uses the Supervisor's TCP API (`http://supervisor`) with the add-on token. Every request passes an allow-list of
four `(method, path)` pairs before any network I/O; the transport ignores proxy environment variables, never follows a
redirect and sends the token as an unredirected header. The transport lives in one private method
(`SupervisorClient._send`), so a Unix-socket transport can replace it later without touching the callers.

Each sent request writes exactly one log line `supervisor {METHOD} {template}: {status}` with the path template, never
the filled path, the request body or the response body. Supervisor messages embed full store URLs; `mask_text` masks
them before they reach a log line or a state file.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping

from app.gitops import sanitize
from app.urls import mask_hash

SUPERVISOR_BASE = "http://supervisor"
TOKEN_ENVS = ("SUPERVISOR_TOKEN", "HASSIO_TOKEN")
ALLOWED = frozenset(
    {
        ("GET", "/store/repositories"),
        ("POST", "/store/repositories"),
        ("DELETE", "/store/repositories/{slug}"),
        ("POST", "/store/reload"),
    }
)
SLUG_RE = re.compile(r"[0-9a-f]{8}")  # always fullmatch: `^...$` would accept a trailing newline
TIMEOUTS: dict[tuple[str, str], float] = {
    ("GET", "/store/repositories"): 30,
    ("POST", "/store/repositories"): 180,  # synchronous: the Supervisor clones before it answers
    ("DELETE", "/store/repositories/{slug}"): 60,
    ("POST", "/store/reload"): 300,  # pulls every store repository before it answers
}
MAX_BODY = 1 << 20
REFUSAL_MARKER = "used by installed apps"
DUPLICATE_ERROR_KEY = "store_repository_already_added_error"
REFUSAL_CODES = ("not_allowed", "invalid_slug", "token_missing", "invalid_body")

LOG = logging.getLogger("mrp.supervisor")
# /repo/{owner}/{repo}/{32 hex}: owner and repo are runs without `/`, whitespace or quotes
_STORE_PATH_RE = re.compile(r"(/repo/[^/\s'\"]+/[^/\s'\"]+/)([0-9a-fA-F]{32})(?![0-9a-fA-F])")


class SupervisorRefused(Exception):
    """A call the client refuses before any network I/O; `code` is one of REFUSAL_CODES."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CallResult:
    """Outcome of one request. `status` 0 means no HTTP answer (`message` is `timeout` or `unreachable`)."""

    ok: bool
    status: int
    data: Any = None
    error_key: str | None = None
    message: str = ""

    @property
    def duplicate(self) -> bool:
        return self.status == 409 and self.error_key == DUPLICATE_ERROR_KEY

    @property
    def in_use(self) -> bool:
        return self.status == 400 and REFUSAL_MARKER in self.message

    @property
    def not_found(self) -> bool:
        return self.status == 404


def read_token(environ: Mapping[str, str]) -> str:
    """The first non-empty Supervisor token of the container environment, stripped; empty when there is none."""
    for name in TOKEN_ENVS:
        value = environ.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def store_slug(url: str) -> str:
    """The Supervisor's repository identity of a store URL (same formula as the Supervisor and the fake)."""
    return hashlib.sha1(url.lower().encode("utf-8")).hexdigest()[:8]


def mask_text(text: str, limit: int = 300) -> str:
    """Supervisor text with every `/repo/{owner}/{repo}/{hash}` masked, as one sanitized line of at most `limit`."""
    if not isinstance(text, str):
        return ""
    masked = _STORE_PATH_RE.sub(lambda m: m.group(1) + mask_hash(m.group(2)), text)
    return sanitize(masked, limit)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A 3xx comes back as an error result: the token must never travel to another location."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _parse(status: int, raw: bytes) -> CallResult:
    """The Supervisor envelope; anything else (plain-text 401/403, empty, non-JSON) is a failure with the status."""
    try:
        doc = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, ValueError):
        doc = None
    if not isinstance(doc, dict):
        return CallResult(False, status)
    result = doc.get("result")
    if result == "ok" and 200 <= status < 300:
        return CallResult(True, status, doc.get("data"))
    if result == "error":
        key = doc.get("error_key")
        message = doc.get("message")
        return CallResult(
            False,
            status,
            error_key=key if isinstance(key, str) else None,
            message=mask_text(message) if isinstance(message, str) else "",
        )
    return CallResult(False, status)


class SupervisorClient:
    """Allow-listed Supervisor client. One request per call: no caching, no retries."""

    def __init__(self, token: str, *, base: str = SUPERVISOR_BASE, log: logging.Logger | None = None) -> None:
        self._token = token if isinstance(token, str) else ""
        self._base = base.rstrip("/")
        self._log = log or LOG
        # ProxyHandler({}) ignores http_proxy/HTTP_PROXY from the container environment
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def __repr__(self) -> str:
        return f"SupervisorClient(base={self._base!r})"

    def _refuse(self, code: str) -> SupervisorRefused:
        self._log.warning("supervisor call refused: %s", code)
        return SupervisorRefused(code)

    def call(
        self, method: str, template: str, *, slug: str | None = None, body: dict | None = None
    ) -> CallResult:
        """Validate against the allow-list (before any I/O), send one request and parse the answer."""
        if (method, template) not in ALLOWED:
            raise self._refuse("not_allowed")
        path = template
        if "{slug}" in template:
            if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
                raise self._refuse("invalid_slug")
            path = template.replace("{slug}", slug)
        if not self._token:
            raise self._refuse("token_missing")
        wants_body = (method, template) == ("POST", "/store/repositories")
        if wants_body != isinstance(body, dict):
            raise self._refuse("invalid_body")
        data = json.dumps(body).encode("utf-8") if body is not None else None
        result = self._send(method, path, data, TIMEOUTS[(method, template)])
        outcome = str(result.status) if result.status else result.message
        level = logging.INFO if 200 <= result.status < 300 else logging.WARNING
        self._log.log(level, "supervisor %s %s: %s", method, template, outcome)
        return result

    def _send(self, method: str, path: str, data: bytes | None, timeout: float) -> CallResult:
        """The transport: one HTTP request; never raises for network failures, never uses the exception text."""
        request = urllib.request.Request(self._base + path, data=data, method=method)
        request.add_unredirected_header("Authorization", "Bearer " + self._token)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with self._opener.open(request, timeout=timeout) as response:
                return _parse(response.status, response.read(MAX_BODY))
        except urllib.error.HTTPError as exc:
            try:
                raw = exc.read(MAX_BODY)
            except (OSError, http.client.HTTPException):
                raw = b""
            finally:
                exc.close()
            return _parse(exc.code, raw)
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                return CallResult(False, 0, message="timeout")
            return CallResult(False, 0, message="unreachable")
        except TimeoutError:
            return CallResult(False, 0, message="timeout")
        except (http.client.HTTPException, OSError, ValueError):
            return CallResult(False, 0, message="unreachable")

    def list_repositories(self) -> CallResult:
        return self.call("GET", "/store/repositories")

    def add_repository(self, url: str) -> CallResult:
        return self.call("POST", "/store/repositories", body={"repository": url})

    def remove_repository(self, slug: str) -> CallResult:
        return self.call("DELETE", "/store/repositories/{slug}", slug=slug)

    def reload_store(self) -> CallResult:
        return self.call("POST", "/store/reload")
