"""Runs status.sh for one host and turns its JSON line into a strictly whitelisted, sanitised object.

status.sh is the single producer shared by the status endpoint, the metrics endpoint, MQTT and the incident marker,
so the GUI cannot drift from Gatus. It is spawned as an argv list (no shell) with an environment the caller builds,
under a timeout and an output cap. Nothing it prints is trusted: only the whitelisted keys survive, coerced by type.
"""

from __future__ import annotations

import json
import math
import os
import re
import selectors
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from .hosts import valid_slug

NUMBER_FIELDS = (
    "age",
    "up",
    "load1",
    "io_some10",
    "io_full10",
    "mem_full10",
    "sda_inflight",
    "mmc_inflight",
    "dstate",
    "probe_age",
    "ping",
    "p22222",
    "p1883",
    "p8123",
    "p4357",
    "problem",
    "r_age",
    "r_io",
    "r_sda",
    "r_dstate",
    "r_kmsg",
    "kmsg_errors",
)
TEXT_FIELDS = ("reasons", "dstate_tasks", "kmsg_last", "key_fp", "key_type")

MAX_OUTPUT = 65536
DEFAULT_TIMEOUT = 10.0
TEXT_LIMITS = {"reasons": 128, "dstate_tasks": 4000, "kmsg_last": 200}
FP_RE = re.compile(r"[A-Za-z0-9+/:=_-]{0,128}")
KEY_TYPE_RE = re.compile(r"[A-Za-z0-9_-]{0,32}")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


class StatusError(Exception):
    """status.sh failed or printed something unusable. The message never carries script output or paths."""


def _kill(proc: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)  # the script runs in its own session: awk, tail and friends die with it
    except OSError:
        pass
    try:
        proc.kill()
    except OSError:
        pass


def _run(argv: list[str], env: dict[str, str], timeout: float) -> bytes:
    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            shell=False,
            close_fds=True,
            start_new_session=True,
        )
    except OSError as exc:
        raise StatusError("status script could not be started") from exc
    assert proc.stdout is not None
    fd = proc.stdout.fileno()
    deadline = time.monotonic() + timeout
    chunks: list[bytes] = []
    total = 0
    try:
        with selectors.DefaultSelector() as sel:
            sel.register(fd, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise StatusError("status script timed out")
                if not sel.select(remaining):
                    continue
                data = os.read(fd, 65536)
                if not data:
                    break
                total += len(data)
                if total > MAX_OUTPUT:
                    raise StatusError("status output too large")
                chunks.append(data)
        try:
            code = proc.wait(timeout=max(deadline - time.monotonic(), 0.05))
        except subprocess.TimeoutExpired as exc:
            raise StatusError("status script timed out") from exc
    except StatusError:
        _kill(proc)
        raise
    finally:
        proc.stdout.close()
        _kill_if_running(proc)
    if code != 0:
        raise StatusError("status script failed")
    return b"".join(chunks)


def _kill_if_running(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None:
        _kill(proc)
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-finite number: {name}")


def _number(value: Any) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return -1
    if isinstance(value, float) and not math.isfinite(value):
        return -1
    return value


def _text(field: str, value: Any) -> str:
    if not isinstance(value, str):
        return ""
    if field == "key_fp":
        return value if FP_RE.fullmatch(value) else ""
    if field == "key_type":
        return value if KEY_TYPE_RE.fullmatch(value) else ""
    return _CONTROL_RE.sub("", value)[: TEXT_LIMITS[field]]


def parse_status(raw: bytes) -> dict[str, Any]:
    """Validate the raw status.sh output and return the whitelist object."""
    if not raw.strip():
        raise StatusError("status output empty")
    try:
        data = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError) as exc:
        raise StatusError("status output invalid") from exc
    if not isinstance(data, dict):
        raise StatusError("status output is not an object")
    result: dict[str, Any] = {name: _number(data.get(name)) for name in NUMBER_FIELDS}
    for name in TEXT_FIELDS:
        result[name] = _text(name, data.get(name))
    return result


def read_status(
    slug: str, *, status_sh: Path | str, env: dict[str, str], timeout: float = DEFAULT_TIMEOUT
) -> dict[str, Any]:
    """Run `status.sh <slug>` and return the whitelist object. ValueError for an invalid slug (nothing is spawned)."""
    if not valid_slug(slug):
        raise ValueError("invalid slug")
    return parse_status(_run([str(status_sh), slug], dict(env), timeout))
