"""Helpers and the `serve` fixture for the management page tests (kept out of conftest.py, which Phase 2 may edit).

Test modules import them with `from guihelpers import INGRESS, Client, serve, ...`; a fixture imported into a test
module is discovered by pytest.
"""

from __future__ import annotations

import http.client
import json
import threading
from typing import Any, Callable, Iterator

import pytest

from app.paths import Paths

INGRESS = {"X-Ingress-Path": "/api/hassio_ingress/abc"}


class Client:
    def __init__(self, port: int) -> None:
        self.port = port

    def call(
        self, method: str, path: str, headers: dict[str, str] | None = None, body: bytes | None = None
    ) -> tuple[int, Any, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, resp, data
        finally:
            conn.close()


@pytest.fixture
def serve() -> Iterator[Callable[..., Client]]:
    """Factory: serve(server) runs an already built server on its free port in a thread and returns a Client."""
    servers: list[Any] = []

    def start(server: Any) -> Client:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        servers.append((server, thread))
        return Client(server.server_address[1])

    yield start
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def write_options(
    paths: Paths, repositories: list[dict[str, Any]], public_url: str = "", github_token: str = ""
) -> None:
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {"github_token": github_token, "repositories": repositories, "log_level": "info"}
    if public_url:
        doc["public_url"] = public_url
    paths.options_file.write_text(json.dumps(doc), encoding="utf-8")


def _write(path: Any, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(doc, bytes):
        path.write_bytes(doc)
    elif isinstance(doc, str):
        path.write_text(doc, encoding="utf-8")
    else:
        path.write_text(json.dumps(doc), encoding="utf-8")


def write_status(paths: Paths, doc: Any) -> None:
    """dict -> JSON; str or bytes -> written as is (corrupt-file cases)."""
    _write(paths.status_file, doc)


def write_supervisor(paths: Paths, doc: Any) -> None:
    """Phase 2's /data/supervisor.json: dict -> JSON; str or bytes -> written as is (corrupt-file cases)."""
    _write(paths.data_dir / "supervisor.json", doc)
