"""s6 longrun `fetchlog`: records the last fetch per (repository, user) from the access-log sink (D-20, D-21, D-22).

Run as `python3 -m app.fetchlog` by root, without the container environment: it reads only `log_level` from the
options and never uses the upstream credential. It owns the datagram socket /run/mrp-fetch/fetch.sock (directory
root:lighttpd 0710, socket root:lighttpd 0620), which the piped access logger `app/fetchsink.py` (uid lighttpd) sends
`{owner} {repo} {hash}` to. Datagrams are untrusted (the CGI runs as the same uid): only the strict format is
accepted, and a hash counts only when access.json maps it to that repository. The map is rebuilt on a file signature
change through the non-destructive locked read (`app.accessread`), never `AccessStore.load()`.

This service is the only writer of /data/last-fetch.json (`app.lastfetch`). A fetch is logged as
`fetch: {user} → {owner}/{repo}` at info level, at most once per access hash per 60 s; the file is written at each
logged fetch, when unwritten newer values are 60 s old, and on SIGTERM/SIGINT. No access hash and no raw datagram is
ever logged or written; throttle state lives in memory only.
"""

from __future__ import annotations

import argparse
import grp
import logging
import os
import re
import signal
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

from app.access import HASH_RE, USER_RE, AccessStore
from app.accessread import AccessUnavailable, file_signature, read_entries_safe
from app.jsonio import utc_timestamp
from app.lastfetch import LastFetchRecord, read_last_fetch, write_last_fetch
from app.logsetup import setup_logging
from app.options import OptionsError, load_options, parse_repository
from app.paths import Paths

SOCKET_DIR = Path("/run/mrp-fetch")
SOCKET_PATH = SOCKET_DIR / "fetch.sock"
SOCKET_GROUP = "lighttpd"
DATAGRAM_RE = re.compile(r"^([A-Za-z0-9._-]+) ([A-Za-z0-9._-]+) ([0-9a-f]{32})$")
MAX_DATAGRAM = 256
LOG_INTERVAL = 60

LOG = logging.getLogger("mrp.fetchlog")
_UNSEEN = object()  # first lookup always builds the map

Pairs = set[tuple[str, str]]


def _group_gid(group: str) -> int:
    return grp.getgrnam(group).gr_gid


def bind_socket(
    path: Path | str = SOCKET_PATH,
    group: str = SOCKET_GROUP,
    gid_lookup: Callable[[str], int] | None = None,
    change_owner: bool | None = None,
) -> socket.socket:
    """Bind the datagram socket: parent root:<group> 0710, socket root:<group> 0620, 1 s receive timeout.

    Ownership changes only as root (`change_owner` defaults to euid 0); the group is looked up by name.
    """
    path = Path(path)
    parent = path.parent
    if change_owner is None:
        change_owner = os.geteuid() == 0
    parent.mkdir(exist_ok=True)
    gid = -1
    if change_owner:
        gid = (gid_lookup or _group_gid)(group)
        os.chown(parent, 0, gid)
    os.chmod(parent, 0o710)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        old = os.umask(0o177)
        try:
            sock.bind(str(path))
        finally:
            os.umask(old)
        if change_owner:
            os.chown(path, 0, gid)
        os.chmod(path, 0o620)
        sock.settimeout(1.0)  # wake up for SIGTERM and the periodic write
    except BaseException:
        sock.close()
        raise
    return sock


def parse_datagram(data: bytes) -> tuple[str, str, str] | None:
    """(owner, repo, hash) for a well-formed datagram, None for anything else."""
    if not isinstance(data, bytes) or len(data) > MAX_DATAGRAM:
        return None
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        return None
    match = DATAGRAM_RE.fullmatch(text)
    if match is None:
        return None
    owner, repo, hash_ = match.groups()
    return owner, repo, hash_


class AccessMap:
    """hash -> (stored repository, user), rebuilt only when the access.json signature changes."""

    def __init__(self, paths: Paths, log: logging.Logger) -> None:
        self.paths = paths
        self.log = log
        self.store = AccessStore(paths, log)
        self._seen: Any = _UNSEEN
        self._error_seen: Any = _UNSEEN
        self._map: dict[str, tuple[str, str]] = {}
        self._pairs: Pairs | None = set()

    def _refresh(self) -> None:
        try:
            signature = file_signature(self.paths.access_file)
        except OSError:
            signature = ("stat-failed",)
        if signature == self._seen:
            return
        # the signature from before the read: an edit made during it is picked up at the next lookup
        self._seen = signature
        try:
            entries = read_entries_safe(self.store)
        except AccessUnavailable:
            self._map, self._pairs = {}, None
            if signature != self._error_seen:
                # content-free on purpose: the file holds hashes
                self.log.error("access.json is unavailable (unreadable, invalid or newer schema); fetches not recorded")
                self._error_seen = signature
            return
        self._error_seen = _UNSEEN
        mapping: dict[str, tuple[str, str]] = {}
        pairs: Pairs = set()
        for entry in entries:
            repository, user, hash_ = entry.get("repository"), entry.get("user"), entry.get("hash")
            if not isinstance(repository, str):
                continue
            try:
                parse_repository(repository)
            except (TypeError, ValueError):
                continue
            if not isinstance(user, str) or not USER_RE.fullmatch(user):
                continue
            pairs.add((repository.lower(), user))
            if isinstance(hash_, str) and HASH_RE.fullmatch(hash_):
                mapping[hash_] = (repository, user)
        self._map, self._pairs = mapping, pairs

    def lookup(self, owner: str, repo: str, hash_: str) -> tuple[str, str] | None:
        """(stored repository, user) when the hash belongs to `owner/repo` (case-insensitive), else None."""
        self._refresh()
        found = self._map.get(hash_)
        if found is None or found[0].lower() != f"{owner}/{repo}".lower():
            return None
        return found

    def pairs(self) -> Pairs | None:
        """(repository.lower(), user) of every valid entry; None while access.json is unavailable."""
        self._refresh()
        return None if self._pairs is None else set(self._pairs)


class FetchRecorder:
    """Last fetch per (repository, user) in memory, persisted through `write_last_fetch` (single writer)."""

    def __init__(self, paths: Paths, log: logging.Logger, clock: Callable[[], float] = time.time) -> None:
        self.paths = paths
        self.log = log
        self.clock = clock
        self.records: dict[tuple[str, str], LastFetchRecord] = read_last_fetch(paths)
        self._logged: dict[str, float] = {}  # access hash -> time of its last log line; memory only, never written
        self._dirty = False
        self._last_write: float | None = None

    def record(self, repository: str, user: str, hash_: str, pairs: Pairs | None = None) -> bool:
        """Record a fetch now; True when it was logged (and written), False when throttled (written later).

        `pairs` is the current set of (repository.lower(), user) used for pruning at the write; None prunes nothing.
        """
        now = self.clock()
        self.records[(repository.lower(), user)] = LastFetchRecord(repository, user, utc_timestamp(now))
        last = self._logged.get(hash_)
        if last is not None and now - last < LOG_INTERVAL:
            self._dirty = True
            return False
        self._logged[hash_] = now
        self._dirty = True
        self._write(pairs, now)
        self.log.info("fetch: %s → %s", user, repository)
        return True

    def tick(self, pairs: Pairs | None) -> None:
        """Write unwritten newer values once the last write is at least LOG_INTERVAL old."""
        now = self.clock()
        self._logged = {h: t for h, t in self._logged.items() if now - t < LOG_INTERVAL}
        if self._dirty and (self._last_write is None or now - self._last_write >= LOG_INTERVAL):
            self._write(pairs, now)

    def flush(self, pairs: Pairs | None) -> None:
        """Write unwritten values now (shutdown)."""
        if self._dirty:
            self._write(pairs, self.clock())

    def _write(self, pairs: Pairs | None, now: float) -> None:
        if pairs is not None:
            self.records = {key: rec for key, rec in self.records.items() if key in pairs}
        try:
            write_last_fetch(self.paths, self.records.values())
        except OSError as exc:
            self.log.error("last-fetch write failed (%s); retrying later", type(exc).__name__)
            self._last_write = now
            return
        self._dirty = False
        self._last_write = now


def make_handler(access_map: AccessMap, recorder: FetchRecorder) -> Callable[[bytes], None]:
    """Datagram -> record; malformed, unknown and foreign datagrams are dropped without a trace."""

    def handle(data: bytes) -> None:
        parsed = parse_datagram(data)
        if parsed is None:
            return
        owner, repo, hash_ = parsed
        found = access_map.lookup(owner, repo, hash_)
        if found is None:
            return
        recorder.record(found[0], found[1], hash_, pairs=access_map.pairs())

    return handle


def serve_forever(
    sock: socket.socket,
    stop: threading.Event,
    handle: Callable[[bytes], None],
    tick: Callable[[], None],
) -> None:
    """Receive until `stop` is set; `tick()` after every datagram or receive timeout. Errors logged by type only."""
    while not stop.is_set():
        try:
            data: bytes | None = sock.recv(MAX_DATAGRAM + 1)
        except TimeoutError:
            data = None
        except OSError as exc:
            LOG.error("fetch socket receive failed (%s)", type(exc).__name__)
            stop.wait(1.0)
            data = None
        if data is not None:
            try:
                handle(data)
            except Exception as exc:
                LOG.error("fetch record failed (%s)", type(exc).__name__)
        try:
            tick()
        except Exception as exc:
            LOG.error("last-fetch tick failed (%s)", type(exc).__name__)


def main(argv: list[str] | None = None, paths: Paths | None = None, socket_path: Path | str = SOCKET_PATH) -> int:
    parser = argparse.ArgumentParser(
        prog="app.fetchlog",
        description="Record the last fetch per repository user from the lighttpd access-log sink.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.parse_args(argv)
    paths = paths or Paths.default()
    try:
        options = load_options(paths.options_file)
    except OptionsError as exc:
        setup_logging("info")
        LOG.error("%s", exc)
        return 1
    # keep only what this service needs; the credential is not used here
    log_level = options.log_level
    del options
    setup_logging(log_level)

    stop = threading.Event()

    def _stop(*_: Any) -> None:
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _stop)

    try:
        sock = bind_socket(socket_path)
    except (OSError, KeyError) as exc:
        LOG.error("fetch log socket setup failed (%s)", type(exc).__name__)
        return 1
    access_map = AccessMap(paths, LOG)
    recorder = FetchRecorder(paths, LOG)
    LOG.info("fetch log listening")
    try:
        serve_forever(sock, stop, make_handler(access_map, recorder), lambda: recorder.tick(access_map.pairs()))
    finally:
        recorder.flush(access_map.pairs())
        sock.close()
        try:
            Path(socket_path).unlink()
        except FileNotFoundError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
