"""Piped lighttpd access logger: forwards successful upload-pack POSTs to the `fetchlog` service (D-20).

lighttpd starts it as `accesslog.filename = "|exec /usr/bin/python3 -I .../app/fetchsink.py"`, so it runs as user
`lighttpd` and reads one access record ("%m %U %>s") per line on stdin. Under `python3 -I` the add-on package is not
importable: this file uses the standard library only and imports nothing from `app.*`.

Every record carries an access hash (404 probes included), so it never prints anything: stdout and stderr go to
/dev/null before the first line is read, every error is swallowed per line, and only the lines
`POST /repo/{owner}/{repo}/{32 hex}/git-upload-pack 200` become one datagram `{owner} {repo} {hash}` on a
non-blocking AF_UNIX socket. When the receiver is down or its buffer is full the record is dropped; the forwarder keeps
reading to the end of input so lighttpd keeps serving git. The optional single argument is the socket path.
"""

from __future__ import annotations

import os
import re
import socket
import sys

LINE_RE = re.compile(r"^POST /repo/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)/([0-9a-f]{32})/git-upload-pack 200$")
SOCKET_PATH = "/run/mrp-fetch/fetch.sock"


# Annotations are never evaluated (postponed), so `BinaryIO` needs no typing import: stdlib os/re/socket/sys only.
def main(argv: list[str] | None = None, stream: BinaryIO | None = None) -> int:  # noqa: F821
    try:
        devnull = open(os.devnull, "w", encoding="ascii")
        sys.stdout = devnull
        sys.stderr = devnull
        args = sys.argv[1:] if argv is None else list(argv)
        path = args[0] if len(args) == 1 else SOCKET_PATH
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.setblocking(False)
        source = sys.stdin.buffer if stream is None else stream
        for raw in source:
            try:
                match = LINE_RE.match(raw.decode("ascii", "replace").rstrip("\r\n"))
                if match:
                    sock.sendto(" ".join(match.groups()).encode("ascii"), path)
            except Exception:  # receiver down, buffer full, bad bytes: drop the record, say nothing
                continue
    except SystemExit:
        raise
    except BaseException:  # never let a traceback (which could quote a line) reach lighttpd's stderr
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
