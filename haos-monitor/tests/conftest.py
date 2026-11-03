"""pytest path setup (`import app...` resolves to haos-monitor/app), fixtures and helpers for the GUI server tests.

Run pytest per add-on, never together with admin-ui/tests: both define a package named `app`.
"""

from __future__ import annotations

import http.client
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest

TESTS_DIR = Path(__file__).resolve().parent
ADDON_DIR = TESTS_DIR.parent

for entry in (str(ADDON_DIR), str(TESTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

INGRESS = {"X-Ingress-Path": "/api/hassio_ingress/abc"}
REAL_STATUS_SH = ADDON_DIR / "status.sh"
FIXTURE_FP = "SHA256:abcDEF123+/="
FIXTURE_TYPE = "ED25519"


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


def write_hosts(path: Path, lines: list[str] | None = None) -> Path:
    """Write a hosts file; the default is the one-host fixture (six tab-separated columns, as run.sh writes them)."""
    if lines is None:
        lines = [f"ha_backup\tha-backup\t192.0.2.9\t22222\t{FIXTURE_FP}\t{FIXTURE_TYPE}"]
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


def _ts(age_s: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=age_s)).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_log(
    logdir: Path,
    slug: str,
    *,
    age: float = 1,
    up: float = 5000.5,
    io_full: float = 0.0,
    sda: int = 0,
    mmc: int = 0,
    dstate: list[str] | None = None,
    kerr: list[str] | None = None,
    incidents: list[str] | None = None,
    ports: tuple[str, str, str, str, str] = ("ok", "open", "open", "open", "open"),
) -> Path:
    """Write `<slug>.log` and `<slug>.log.state` in the real monitor.sh format, newest sample `age` seconds old."""
    logdir.mkdir(parents=True, exist_ok=True)
    state: list[str] = []
    state.append(f"{_ts(age + 20)} BOOT up={up - 20:.2f}")
    state.append(
        f'{_ts(age)} SAMPLE up={up:.2f} load="0.50 0.40 0.30 1/200 999" '
        f'io_some="some avg10=1.50 avg60=0.00 avg300=0.00 total=0" '
        f'io_full="full avg10={io_full:.2f} avg60=0.00 avg300=0.00 total=0" '
        f'mem_full="full avg10=0.00 avg60=0.00 avg300=0.00 total=0"'
    )
    state.append(f"{_ts(age)} DISK sda inflight={sda}")
    state.append(f"{_ts(age)} DISK mmcblk1 inflight={mmc}")
    for index, entry in enumerate(dstate or []):
        state.append(f"{_ts(age)} DSTATE {100 + index} {entry}")
    for index, message in enumerate(kerr or []):
        # KERR <prio>,<seq>,<usec since boot>,-;<message>
        usec = int((up - 5) * 1_000_000)
        state.append(f"{_ts(age)} KERR 3,{index + 1},{usec},-;{message}")
    state.append(f"{_ts(age)} PROBE ping={ports[0]} 22222={ports[1]} 1883={ports[2]} 8123={ports[3]} 4357={ports[4]}")
    log = list(state)
    for line in incidents or []:
        log.append(f"{_ts(age)} INCIDENT {line}")
    log_path = logdir / f"{slug}.log"
    log_path.write_text("".join(f"{line}\n" for line in log), encoding="utf-8")
    (logdir / f"{slug}.log.state").write_text("".join(f"{line}\n" for line in state), encoding="utf-8")
    return log_path


def now_ms() -> int:
    return int(time.time() * 1000)


@pytest.fixture
def env(tmp_path: Path) -> dict[str, Path]:
    """One host `ha_backup` with a fresh, healthy log; paths of the real status.sh, hosts file and logs."""
    hosts = write_hosts(tmp_path / "hosts")
    logdir = tmp_path / "logs"
    write_log(logdir, "ha_backup")
    return {
        "hosts_file": hosts,
        "logdir": logdir,
        "status_sh": REAL_STATUS_SH,
        "env_file": tmp_path / "missing.env",
    }
