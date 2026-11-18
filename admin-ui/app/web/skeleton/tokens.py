"""Bearer token verifiers of the admin-UI skeleton: only SHA-256 digests are kept and compared in constant time; token
values are never logged, printed or put into messages."""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import os
import re
import secrets
import stat
import tempfile
import threading
from pathlib import Path
from typing import Protocol

# Floor for operator-chosen option tokens, decided by the user (D-11); also binding for ntfy Phase 25
OPTION_TOKEN_MIN_LENGTH = 16


class TokenVerifier(Protocol):
    """Anything that can tell whether a presented bearer token is valid."""

    def verify(self, presented: str) -> bool: ...


class OptionToken:
    """Token from an add-on `password` option; only its SHA-256 digest is kept in memory.

    The value must be printable ASCII without spaces (0x21..0x7E) and at least OPTION_TOKEN_MIN_LENGTH characters long;
    it is never stripped or normalised, and no error message contains it."""

    __slots__ = ("_digest",)

    def __init__(self, value: str | None) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError("option token missing: the API stays off")
        if not all("\x21" <= char <= "\x7e" for char in value):
            raise ValueError("option token must be printable ASCII without spaces")
        if len(value) < OPTION_TOKEN_MIN_LENGTH:
            raise ValueError(f"option token shorter than {OPTION_TOKEN_MIN_LENGTH} characters")
        self._digest = hashlib.sha256(value.encode("ascii")).digest()

    def verify(self, presented: str) -> bool:
        try:
            candidate = hashlib.sha256(presented.encode("ascii")).digest()
        except (UnicodeEncodeError, AttributeError):
            return False
        # Equal-length digests: no TypeError on non-ASCII input and no length leak
        return hmac.compare_digest(candidate, self._digest)

    def __repr__(self) -> str:
        return "OptionToken(<redacted>)"


# The only accepted hash file content: one line, algorithm prefix plus 64 lowercase hex digits
_HASH_LINE = re.compile(r"sha256 ([0-9a-f]{64})\n?")


def _new_token() -> str:
    """256 random bits as 43 URL-safe characters."""
    return secrets.token_urlsafe(32)


def _write_hash(path: Path, digest: bytes) -> None:
    """Atomically replace `path` with the single line 'sha256 <hex>'; mode 0600, the plaintext is never written."""
    # The temporary file is created with mode 0600 in the target directory, so os.replace stays on one file system
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="ascii", newline="\n") as handle:
            handle.write(f"sha256 {digest.hex()}\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
    # Best effort: the hash is already in `path`, so raising here would lose the plaintext of the token on disk
    # (lockout) or leave memory and disk out of step; the file content itself was fsynced above
    with contextlib.suppress(OSError):
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


class GeneratedToken:
    """Generated API token (D-06): 256 random bits, only its SHA-256 is stored, in a 0600 file.

    The first start (file absent) creates a token; its plaintext is available exactly once through take_plaintext() and
    is lost on restart by design. rotate() replaces the token at runtime and returns the new plaintext once; a failed
    write keeps the old token valid. An unreadable or malformed file, and a path that is not a regular file (a symlink,
    a directory, a FIFO), raise ValueError and are left untouched: a token is never replaced on its own, and loose
    permissions are tightened to 0600 only on a valid file. Nothing here prints or logs."""

    def __init__(self, path: Path, digest: bytes, plaintext: str | None) -> None:
        # Internal: instances come from load_or_create
        self._path = path
        self._digest = digest
        self._pending = plaintext
        self._lock = threading.Lock()

    @classmethod
    def load_or_create(cls, path: str | os.PathLike[str]) -> GeneratedToken:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # One open, no symlink followed (a dangling one included), no block on a FIFO; the mode is not touched yet
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            plaintext = _new_token()
            digest = hashlib.sha256(plaintext.encode("ascii")).digest()
            _write_hash(path, digest)
            return cls(path, digest, plaintext)
        except OSError:
            # Messages name neither the path nor any content; `from None` keeps the OSError (with the path) out
            raise ValueError("API token file is unreadable or a symlink: fix or delete it and restart") from None
        try:
            mode = os.fstat(fd).st_mode
            if not stat.S_ISREG(mode):
                raise ValueError("API token path is not a regular file: delete it and restart")
            # A valid file has 72 bytes, so 128 bytes are enough to reject anything longer
            with os.fdopen(fd, "rb", closefd=False) as handle:
                data = handle.read(128)
            try:
                match = _HASH_LINE.fullmatch(data.decode("ascii"))
            except UnicodeDecodeError:
                match = None
            if match is None:
                # The message names no file content; recovery is deleting the file (A6)
                raise ValueError("API token file is malformed: delete it and restart to create a new token")
            # Tightened only once the content is valid, through the fd: never the target of a swapped-in path
            if stat.S_IMODE(mode) & 0o077:
                os.fchmod(fd, 0o600)
        except OSError:
            raise ValueError("API token file is unreadable: fix or delete it and restart") from None
        finally:
            os.close(fd)
        return cls(path, bytes.fromhex(match.group(1)), None)

    @property
    def path(self) -> Path:
        return self._path

    def take_plaintext(self) -> str | None:
        """The plaintext of a freshly created token, once; afterwards None."""
        with self._lock:
            plaintext, self._pending = self._pending, None
            return plaintext

    def rotate(self) -> str:
        """Replace the token; returns the new plaintext (the one time it is available) and clears a pending one."""
        with self._lock:
            plaintext = _new_token()
            digest = hashlib.sha256(plaintext.encode("ascii")).digest()
            # Raises only while the old hash is still on disk, before the swap: the old token stays valid
            _write_hash(self._path, digest)
            self._digest = digest
            self._pending = None
            return plaintext

    def verify(self, presented: str) -> bool:
        digest = self._digest  # one read: a concurrent rotate swaps the reference, never a half-written value
        try:
            candidate = hashlib.sha256(presented.encode("ascii")).digest()
        except (UnicodeEncodeError, AttributeError):
            return False
        return hmac.compare_digest(candidate, digest)

    def __repr__(self) -> str:
        return f"GeneratedToken(path={str(self._path)!r})"
