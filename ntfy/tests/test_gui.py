"""Tests for app.gui: the NTFY_GUI_CSP environment switch."""

from __future__ import annotations

import pytest

from app.gui import csp_from_env
from app.web.admin_ui import DEFAULT_CSP


def test_csp_defaults_to_the_skeleton_policy() -> None:
    assert csp_from_env({}) == DEFAULT_CSP


def test_csp_strict_is_the_skeleton_policy() -> None:
    assert csp_from_env({"NTFY_GUI_CSP": "strict"}) == DEFAULT_CSP


def test_csp_off_disables_the_header() -> None:
    assert csp_from_env({"NTFY_GUI_CSP": "off"}) is None


@pytest.mark.parametrize("value", ["", "OFF", "none", "relaxed", "default-src *"])
def test_csp_rejects_any_other_value(value: str) -> None:
    with pytest.raises(ValueError):
        csp_from_env({"NTFY_GUI_CSP": value})
