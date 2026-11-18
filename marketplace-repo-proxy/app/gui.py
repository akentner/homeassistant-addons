"""s6 longrun `gui`: the management page on ingress port 8099 (D-06).

Run as `python3 -m app.gui`. The service runs without the container environment, so it never sees the upstream token
or the Supervisor token (D-07): it keeps an options copy whose credential is empty and reads no environment variable,
so nothing in production can move the port or the ingress peer. stdout and stderr are wrapped so every 32-hex run
(an access hash) is masked before anything, a skeleton traceback included, reaches the add-on log.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, TextIO

from app.logsetup import mask_hashes, setup_logging
from app.options import OptionsError
from app.paths import Paths
from app.web.admin_ui import INGRESS_REMOTE, serve
from app.web.server import make_server
from app.web.service import GuiService, load_gui_config

LOG = logging.getLogger("mrp.gui")

GUI_PORT = 8099


class MaskedStream:
    """Text stream that masks access hashes in everything written and delegates the rest to the wrapped stream."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    def write(self, text: str) -> int:
        return self._stream.write(mask_hashes(text))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def main(
    argv: list[str] | None = None,
    paths: Paths | None = None,
    port: int = GUI_PORT,
    ingress_remote: str = INGRESS_REMOTE,
) -> int:
    parser = argparse.ArgumentParser(
        prog="app.gui",
        description="Serve the management page on the ingress port.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.parse_args(argv)
    if not isinstance(sys.stdout, MaskedStream):
        sys.stdout = MaskedStream(sys.stdout)
    if not isinstance(sys.stderr, MaskedStream):
        sys.stderr = MaskedStream(sys.stderr)
    paths = paths or Paths.default()
    try:
        config = load_gui_config(paths)
    except OptionsError as exc:
        setup_logging("info")
        LOG.error("%s", exc)
        return 1
    setup_logging(config.options.log_level)
    server = make_server(GuiService(paths, config), port, ingress_remote=ingress_remote)
    LOG.info("management page listening on port %d", port)
    serve(server)
    return 0


if __name__ == "__main__":
    sys.exit(main())
