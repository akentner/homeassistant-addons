#!/usr/bin/env python3
"""Host-side probe for cups/upload-worker.py's paperless-ngx upload classification (CR-01).

Starts a stdlib HTTP server on 127.0.0.1 as a stand-in paperless-ngx and drives the REAL
`upload_document()` / `attempt_and_route()` of the worker (real `requests`, real redirects) against
scripted answers. It proves that:

  - an HTTP 3xx answer is never followed (exactly one request reaches the stub, and it is the POST)
    and is reported as a failed attempt, so the document follows retry -> failed/ and is never
    recorded in sent/;
  - the redirect WARNING names the Location target (path only) and never echoes the token;
  - a document counts as sent only for HTTP 200 with a non-empty JSON-string task id; JSON objects,
    HTML, empty bodies, blank task ids and non-200 2xx answers are failed attempts.

Needs a host python3 with `requests` installed. It is a manual tool and is NOT wired into
pre-commit or `make check-all`. `--worker PATH` points the probe at another copy of the worker
(for example `git show <rev>:cups/upload-worker.py > old.py`) to prove the probe fails against a
defective worker instead of passing vacuously.

Exit codes: 0 all checks passed; 1 at least one check failed.
"""

import argparse
import contextlib
import importlib.util
import io
import shutil
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any

API_PATH = "/api/documents/post_document/"
LOGIN_HTML = b"<html>login</html>"
TOKEN = "probe-token-xyz"
DEFAULT_WORKER = Path(__file__).resolve().parent.parent / "cups" / "upload-worker.py"

FAILURES: list[str] = []


def check(ok: bool, label: str) -> None:
    """Record and print one PASS/FAIL line."""
    if ok:
        print(f"PASS: {label}", flush=True)
    else:
        FAILURES.append(label)
        print(f"FAIL: {label}", flush=True)


class StubState:
    """Scripted answer for the next POST plus a record of every request seen."""

    def __init__(self) -> None:
        self.status = 200
        self.location: str | None = None
        self.body = b""
        self.content_type = "application/json"
        self.requests: list[tuple[str, str]] = []
        self.lock = threading.Lock()

    def script(
        self,
        status: int,
        location: str | None = None,
        body: bytes = b"",
        content_type: str = "application/json",
    ) -> None:
        with self.lock:
            self.status = status
            self.location = location
            self.body = body
            self.content_type = content_type
            self.requests.clear()


def make_handler(state: StubState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 -- silence request log
            return

        def _drain(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)

        def _answer(self, status: int, content_type: str, body: bytes, location: str | None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if location is not None:
                self.send_header("Location", location)
            self.end_headers()
            self.wfile.write(body)

        def _handle(self) -> None:
            self._drain()
            with state.lock:
                state.requests.append((self.command, self.path))
                status, location = state.status, state.location
                body, content_type = state.body, state.content_type
            if self.command == "POST" and self.path == API_PATH:
                self._answer(status, content_type, body, location)
            else:
                self._answer(200, "text/html", LOGIN_HTML, None)

        do_GET = _handle
        do_POST = _handle
        do_PUT = _handle
        do_DELETE = _handle
        do_HEAD = _handle

    return Handler


def load_worker(path: Path) -> ModuleType:
    """Import the worker by file path (its name contains a hyphen)."""
    spec = importlib.util.spec_from_file_location("upload_worker_under_test", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load worker from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call_upload(worker: ModuleType, pdf: Path, config: dict) -> tuple[bool, str]:
    """Run upload_document() capturing stdout; return (result, output)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = worker.upload_document(pdf, config)
    return bool(result), buf.getvalue()


def make_pdf(directory: Path, name: str = "doc.pdf") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    pdf = directory / name
    pdf.write_bytes(b"%PDF-1.4\n%probe\n")
    return pdf


def run_route(
    worker: ModuleType, state: StubState, base: Path, config: dict
) -> tuple[Path, Path, str]:
    """Run attempt_and_route() once with SENT/FAILED redirected into temp dirs.

    Returns (sent_dir, failed_dir, captured_output).
    """
    sent, failed, processing = base / "sent", base / "failed", base / "processing"
    for directory in (sent, failed):
        directory.mkdir(parents=True, exist_ok=True)
    pdf = make_pdf(processing)
    old_sent, old_failed = worker.SENT, worker.FAILED
    worker.SENT, worker.FAILED = sent, failed
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            worker.attempt_and_route(pdf, config, prior_attempts=0)
    finally:
        worker.SENT, worker.FAILED = old_sent, old_failed
    return sent, failed, buf.getvalue()


def check_redirect_matrix(worker: ModuleType, state: StubState, config: dict, tmp: Path) -> None:
    for status in (301, 302, 303, 307, 308):
        state.script(status, location="/login/")
        pdf = make_pdf(tmp / f"redirect-{status}")
        result, output = call_upload(worker, pdf, config)
        label = f"HTTP {status} redirect"
        check(result is False, f"{label}: upload_document() returns False")
        check(
            state.requests == [("POST", API_PATH)],
            f"{label}: exactly one request (the POST), no follow-up; saw {state.requests}",
        )
        check(
            str(status) in output and "redirect" in output.lower() and "/login/" in output,
            f"{label}: WARNING names status, 'redirect' and /login/",
        )
        check(TOKEN not in output, f"{label}: token absent from output")


def check_malformed_location(worker: ModuleType, state: StubState, config: dict, tmp: Path) -> None:
    """WR-09: an unparseable Location must not make upload_document() raise."""
    state.script(302, location="http://[::1/x")
    pdf = make_pdf(tmp / "redirect-malformed")
    try:
        result, output = call_upload(worker, pdf, config)
    except ValueError as exc:
        check(False, f"malformed Location: upload_document() raised {exc!r}")
        return
    check(result is False, "malformed Location: upload_document() returns False")
    check(
        "WARNING" in output and "upload request failed" in output and TOKEN not in output,
        "malformed Location: a 'request failed' WARNING is printed and the token stays out of it",
    )
    route_config = dict(config, retry_count=1, retry_delay=1)
    _, failed, route_output = run_route(worker, state, tmp / "route-malformed", route_config)
    check(any(failed.glob("*.pdf")), "malformed Location routing: PDF ends in failed/ (counted, not retried forever)")
    check("upload exhausted" in route_output, "malformed Location routing: 'upload exhausted' WARNING printed")


def check_redirect_routing(worker: ModuleType, state: StubState, config: dict, tmp: Path) -> None:
    state.script(302, location="/login/")
    route_config = dict(config, retry_count=1, retry_delay=1)
    sent, failed, output = run_route(worker, state, tmp / "route-302", route_config)
    check(any(failed.glob("*.pdf")), "302 routing: PDF ends in failed/")
    check(not any(sent.iterdir()), "302 routing: sent/ is empty")
    check(
        sum(1 for line in output.splitlines() if "upload exhausted" in line) == 1,
        "302 routing: exactly one 'upload exhausted' WARNING (D-15)",
    )


TASK_ID_BODY = b'"11111111-2222-3333-4444-555555555555"'

# (label, status, content type, body, expected upload_document() result)
BODY_CASES: tuple[tuple[str, int, str, bytes, bool], ...] = (
    ("200 with task-id JSON string", 200, "application/json", TASK_ID_BODY, True),
    ("200 with JSON object", 200, "application/json", b'{"task_id": "abc"}', False),
    ("200 with HTML login page", 200, "text/html", LOGIN_HTML, False),
    ("200 with empty body", 200, "application/json", b"", False),
    ("200 with empty JSON string", 200, "application/json", b'""', False),
    ("200 with whitespace-only JSON string", 200, "application/json", b'"   "', False),
    ("202 with task-id JSON string", 202, "application/json", TASK_ID_BODY, False),
    ("204 with empty body", 204, "application/json", b"", False),
)


def check_body_matrix(worker: ModuleType, state: StubState, config: dict, tmp: Path) -> None:
    for index, (label, status, content_type, body, expected) in enumerate(BODY_CASES):
        state.script(status, body=body, content_type=content_type)
        pdf = make_pdf(tmp / f"body-{index}")
        result, output = call_upload(worker, pdf, config)
        check(result is expected, f"{label}: upload_document() returns {expected}")
        check(TOKEN not in output, f"{label}: token absent from output")
        if status == 200 and not expected:
            check(
                "not a task id" in output,
                f"{label}: WARNING states the body is not a task id",
            )


def check_body_routing(worker: ModuleType, state: StubState, config: dict, tmp: Path) -> None:
    route_config = dict(config, retry_count=1, retry_delay=1)

    state.script(200, body=TASK_ID_BODY)
    sent, failed, _ = run_route(worker, state, tmp / "route-ok", route_config)
    check(any(sent.glob("*.pdf")), "valid task id routing: PDF ends in sent/")
    check(not any(failed.iterdir()), "valid task id routing: failed/ is empty")

    state.script(200, body=b'{"detail": "not a task id"}')
    sent, failed, output = run_route(worker, state, tmp / "route-bad", route_config)
    check(any(failed.glob("*.pdf")), "rejected 200 body routing: PDF ends in failed/")
    check(not any(sent.iterdir()), "rejected 200 body routing: sent/ is empty")
    check(
        sum(1 for line in output.splitlines() if "upload exhausted" in line) == 1,
        "rejected 200 body routing: exactly one 'upload exhausted' WARNING (D-15)",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe cups/upload-worker.py redirect handling and success classification."
    )
    parser.add_argument(
        "--worker",
        type=Path,
        default=DEFAULT_WORKER,
        help="path to the upload-worker.py under test (default: the repo's cups/upload-worker.py)",
    )
    args = parser.parse_args()

    worker = load_worker(args.worker)
    state = StubState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    config = {"url": f"http://127.0.0.1:{server.server_address[1]}", "token": TOKEN, "timeout": 5}

    tmp = Path(tempfile.mkdtemp(prefix="verify-cups-upload-worker-"))
    try:
        check_redirect_matrix(worker, state, config, tmp)
        check_redirect_routing(worker, state, config, tmp)
        check_malformed_location(worker, state, config, tmp)
        check_body_matrix(worker, state, config, tmp)
        check_body_routing(worker, state, config, tmp)
    finally:
        server.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)

    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED", flush=True)
        return 1
    print("ALL CHECKS PASSED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
