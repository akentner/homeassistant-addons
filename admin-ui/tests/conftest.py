"""pytest path setup (`import app...` resolves to admin-ui/app) and an in-process ingress-gated server fixture."""

from __future__ import annotations

import http.client
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest

TESTS_DIR = Path(__file__).resolve().parent
ADMIN_UI_DIR = TESTS_DIR.parent

for entry in (str(ADMIN_UI_DIR), str(TESTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

INGRESS = {"X-Ingress-Path": "/api/hassio_ingress/abc"}


class Client:
    def __init__(self, port: int) -> None:
        self.port = port

    def call(
        self, method: str, path: str, headers: dict[str, str] | None = None, body: bytes | None = None
    ) -> tuple[int, Any, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, resp, data
        finally:
            conn.close()


@pytest.fixture
def serve() -> Iterator[Callable[..., Client]]:
    """Factory: serve(router, static, ingress_remote="127.0.0.1") starts a server on a free port and returns a Client."""
    servers: list[Any] = []

    def start(router: Any, static: Any, ingress_remote: str = "127.0.0.1") -> Client:
        from app.web.skeleton import make_server

        server = make_server(router, static, 0, ingress_remote=ingress_remote, host="127.0.0.1")
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        servers.append((server, thread))
        return Client(server.server_address[1])

    yield start
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
