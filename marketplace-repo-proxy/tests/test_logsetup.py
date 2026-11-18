"""Secret-safe logging (app.logsetup, D-08, D-17): registered secrets scrubbed, 32-hex hashes masked, SHAs intact."""

from __future__ import annotations

import base64
import io
import logging

import pytest

from app.access import new_hash
from app.logsetup import Redactor, SafeFormatter, mask_hashes, setup_logging

TOKEN = "SENTINEL-" + "PAT-" + "0001"
B64 = base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()
HEADER = "Authorization: Basic " + B64


@pytest.fixture
def emit():
    """A logger wired like setup_logging (SafeFormatter plus redactor filter) writing into a buffer."""
    redactor = Redactor()
    redactor.register([TOKEN, HEADER, B64])
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(SafeFormatter("%(levelname)s %(name)s: %(message)s", redactor))
    handler.addFilter(redactor)
    logger = logging.getLogger("mrp.test.logsetup")
    logger.handlers[:] = [handler]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    yield logger, buffer, redactor
    logger.handlers[:] = []


def test_registered_token_is_scrubbed(emit):
    logger, buffer, _ = emit
    logger.info("token is %s", TOKEN)
    logger.info("plain %s", "text")
    out = buffer.getvalue()
    assert TOKEN not in out
    assert "INFO mrp.test.logsetup: token is ***" in out
    assert "plain text" in out


def test_base64_header_form_is_scrubbed(emit):
    logger, buffer, _ = emit
    logger.warning("git env http.extraHeader=%s", HEADER)
    logger.warning("bare %s", B64)
    out = buffer.getvalue()
    assert B64 not in out and TOKEN not in out
    assert out.count("***") == 2


def test_short_values_are_not_registered():
    redactor = Redactor()
    redactor.register(["abc", "", None, TOKEN])  # type: ignore[list-item]
    assert redactor.scrub("abc and abcd") == "abc and abcd"
    assert redactor.scrub(f"x {TOKEN} y") == "x *** y"


def test_four_char_value_is_registered():
    redactor = Redactor()
    redactor.register(["wxyz"])
    assert redactor.scrub("a wxyz b") == "a *** b"


def test_standalone_hash_is_masked(emit):
    logger, buffer, _ = emit
    hash_ = new_hash()
    logger.info("path /srv/git/access/example-org/addons/%s/info/refs", hash_)
    out = buffer.getvalue()
    assert hash_ not in out
    assert f"/addons/{hash_[:4]}…/info/refs" in out


def test_mask_hashes_keeps_40_hex_sha():
    sha = new_hash() + new_hash()[:8]
    assert len(sha) == 40
    assert mask_hashes(f"commit {sha} done") == f"commit {sha} done"


def test_commit_sha_passes_through_the_formatter(emit):
    logger, buffer, _ = emit
    sha = new_hash() + new_hash()[:8]
    logger.info("fetched %s", sha)
    assert sha in buffer.getvalue()


def test_traceback_is_scrubbed(emit):
    logger, buffer, _ = emit
    hash_ = new_hash()
    try:
        raise RuntimeError(f"fetch failed with {HEADER} for {hash_}")
    except RuntimeError:
        logger.exception("sync error")
    out = buffer.getvalue()
    assert "Traceback" in out and "RuntimeError" in out
    assert TOKEN not in out and B64 not in out and hash_ not in out
    assert f"{hash_[:4]}…" in out


def test_setup_logging_installs_safe_handler():
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    try:
        redactor = setup_logging("warning")
        assert root.level == logging.WARNING
        assert len(root.handlers) == 1
        handler = root.handlers[0]
        assert isinstance(handler.formatter, SafeFormatter)
        assert redactor in handler.filters
        redactor.register([TOKEN])
        assert handler.formatter.format(
            logging.LogRecord("mrp", logging.ERROR, __file__, 1, "x %s", (TOKEN,), None)
        ).endswith("x ***")
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
