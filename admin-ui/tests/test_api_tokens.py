"""Tests for the bearer token verifiers: option token validation (D-07, D-11) and the no-token refusal (D-08).

Every token value is generated at test time; none of them is a real credential."""

from __future__ import annotations

import http.server
import secrets

import pytest

from app.web.skeleton import Router
from app.web.skeleton.api import make_api_server
from app.web.skeleton.tokens import OPTION_TOKEN_MIN_LENGTH, OptionToken


def _valid_option_token() -> str:
    return "opt-" + secrets.token_hex(OPTION_TOKEN_MIN_LENGTH)


def _printable(length: int) -> str:
    """A printable ASCII value of exactly `length` characters (URL-safe alphabet, never a space)."""
    return secrets.token_urlsafe(length)[:length]


# --- OptionToken (D-07, D-11) ---


def test_option_token_rejects_missing_values() -> None:
    for value in (None, "", 42):
        with pytest.raises(ValueError):
            OptionToken(value)  # type: ignore[arg-type]


def test_option_token_rejects_non_printable_or_non_ascii() -> None:
    base = _valid_option_token()
    for value in (base + " x", base + "\tx", base + "ä", base + "\nx", " " + base, base + " "):
        with pytest.raises(ValueError):
            OptionToken(value)


def test_option_token_minimum_length_boundary() -> None:
    # D-11: the minimum the user decided on 2026-11-17; also binds ntfy Phase 25
    assert OPTION_TOKEN_MIN_LENGTH == 16
    short = _printable(15)
    assert len(short) == 15
    with pytest.raises(ValueError):
        OptionToken(short)
    exact = _printable(16)
    assert len(exact) == 16
    assert OptionToken(exact).verify(exact) is True


def test_option_token_messages_never_contain_the_value() -> None:
    base = _valid_option_token()
    rejected = [_printable(15), _printable(8), base + " x", base + "\tx", base + "ä", base + "\nx"]
    for value in rejected:
        assert len(value) >= 3
        with pytest.raises(ValueError) as info:
            OptionToken(value)
        message = str(info.value)
        assert value not in message


def test_option_token_verify() -> None:
    value = _valid_option_token()
    token = OptionToken(value)
    assert token.verify(value) is True
    assert token.verify("wrong-" + secrets.token_hex(OPTION_TOKEN_MIN_LENGTH)) is False
    assert token.verify(value[:-1]) is False
    assert token.verify(value + "ä") is False
    assert token.verify(None) is False  # type: ignore[arg-type]
    assert token.verify(value.encode("ascii")) is False  # type: ignore[arg-type]


def test_option_token_repr_and_state_hide_the_value() -> None:
    value = _valid_option_token()
    token = OptionToken(value)
    assert value not in repr(token)
    assert not hasattr(token, "__dict__")
    assert OptionToken.__slots__ == ("_digest",)
    assert isinstance(token._digest, bytes)
    assert len(token._digest) == 32


# --- No token, no API (D-08) ---


def test_no_token_never_binds(monkeypatch: pytest.MonkeyPatch) -> None:
    def _never_bind(self: http.server.HTTPServer) -> None:
        pytest.fail("a socket was bound without a usable token")

    # Every server class of the skeleton inherits HTTPServer.server_bind, so this covers any subclass
    monkeypatch.setattr(http.server.HTTPServer, "server_bind", _never_bind)
    router = Router()
    router.add("GET", "/api/ping", lambda req: {"ok": True})
    for verifier in (None, object()):
        with pytest.raises(ValueError):
            make_api_server(router, 0, verifier, bind="127.0.0.1")  # type: ignore[arg-type]
