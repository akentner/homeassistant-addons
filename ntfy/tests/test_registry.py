"""Registry, parity and frontend-API drift tests (plan 24-11, task 1).

Proves that contract.ROUTES, the registered backend routes and the frontend call sites agree, and that Python and
JS share the same constants and topic-matching results.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app import contract
from app.web.api import register_all
from app.web.server import Router
from helpers.ctx import make_context

STATIC = Path(__file__).resolve().parents[1] / "app" / "web" / "static"
JS_TESTS = Path(__file__).resolve().parent / "js"
HELPER_METHODS = {"get": "GET", "post": "POST", "put": "PUT", "patch": "PATCH", "del": "DELETE"}

# helper("literal" ...), also template literals; request("METHOD", "literal"); buildUrl(...) is a GET download link
CALL_RE = re.compile(r"(?<![\w.])(get|post|put|patch|del)\(\s*([\"'`])((?:(?!\2)[^\\])*)\2")
REQUEST_RE = re.compile(r"(?<![\w.])request\(\s*[\"']([A-Z]+)[\"']\s*,\s*([\"'`])((?:(?!\2)[^\\])*)\2")
BUILDURL_RE = re.compile(r"(?<![\w.])buildUrl\(\s*([\"'`])((?:(?!\1)[^\\])*)\1")


_CTX: list = []


@pytest.fixture(autouse=True)
def _ctx(tmp_path: Path) -> None:
    _CTX.clear()
    _CTX.append(make_context(tmp_path))


def _call_sites() -> list[tuple[str, str, bool]]:
    """(method, literal prefix, dynamic) for every API call in app.mjs and views/*.mjs."""
    sites: list[tuple[str, str, bool]] = []
    for path in [STATIC / "app.mjs", *sorted((STATIC / "views").glob("*.mjs"))]:
        text = path.read_text(encoding="utf-8")
        found = [(HELPER_METHODS[m.group(1)], m.group(3)) for m in CALL_RE.finditer(text)]
        found += [(m.group(1), m.group(3)) for m in REQUEST_RE.finditer(text)]
        found += [("GET", m.group(2)) for m in BUILDURL_RE.finditer(text)]
        for method, literal in found:
            prefix = literal.split("${", 1)[0]
            sites.append((method, prefix.lstrip("/").removeprefix("api/"), "${" in literal))
    return sites


def _pattern_matches(pattern: str, method: str, route_method: str, prefix: str, dynamic: bool) -> bool:
    if method != route_method:
        return False
    segments = pattern.removeprefix("/api/")
    if dynamic:
        # `reset/${kind}` or `users/${name}`: the literal prefix must be the start of the pattern or of a concrete path
        return segments.startswith(prefix) or segments.split("{", 1)[0].startswith(prefix)
    want = prefix.split("/")
    have = segments.split("/")
    return len(want) == len(have) and all(h.startswith("{") or h == w for h, w in zip(have, want))


def test_registered_routes_equal_contract() -> None:
    router = Router()
    register_all(router, _CTX[0])
    routes = router.routes()
    assert len(routes) == len(set(routes)), "duplicate route registered"
    assert set(routes) == {(r.method, r.pattern) for r in contract.ROUTES}


def test_contract_routes_have_no_duplicates() -> None:
    keys = [(r.method, r.pattern) for r in contract.ROUTES]
    assert len(keys) == len(set(keys))


def test_every_frontend_call_has_a_route() -> None:
    sites = _call_sites()
    assert len(sites) >= 20, "call-site scan found suspiciously few calls"
    for method, prefix, dynamic in sites:
        assert any(
            _pattern_matches(r.pattern, method, r.method, prefix, dynamic) for r in contract.ROUTES
        ), f"frontend calls {method} {prefix!r} but no route exists"


def test_every_route_is_called_by_the_frontend() -> None:
    sites = _call_sites()
    unused = [
        f"{r.method} {r.pattern}"
        for r in contract.ROUTES
        if not any(_pattern_matches(r.pattern, m, r.method, p, d) for m, p, d in sites)
    ]
    assert not unused, f"routes without a frontend call site: {unused}"


def test_health_publish_only_from_health_view() -> None:
    for path in [STATIC / "app.mjs", *sorted((STATIC / "views").glob("*.mjs"))]:
        has_call = "health/publish" in path.read_text(encoding="utf-8")
        assert has_call == (path.name == "health.mjs"), path.name


def test_topic_cases_python_parity() -> None:
    cases = json.loads((JS_TESTS / "topic_cases.json").read_text(encoding="utf-8"))
    assert len(cases) >= 10
    for case in cases:
        assert contract.topic_match(case["pattern"], case["topic"]) is case["match"], case


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_constants_equal_python() -> None:
    url = (STATIC / "lib" / "model.mjs").as_uri()
    script = (
        f"import * as m from '{url}';"
        "console.log(JSON.stringify({r: m.RESET_PHRASES, p: m.PERMISSIONS, o: m.ORIGINS}));"
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30, check=True
    ).stdout
    js = json.loads(out)
    assert js["r"] == contract.RESET_PHRASES
    assert tuple(js["p"]) == contract.PERMISSIONS
    assert tuple(js["o"]) == contract.ORIGINS


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_topic_match_equals_python_for_cross_product() -> None:
    patterns = ["*", "pub*", "a_b*", "a*b*", "x", "*x", "_a", "A*", "ha_topic"]
    topics = ["x", "pub1", "PUB1", "a_bz", "aXbz", "ha_topic", "hatopic", "Ax", "_a", "other", "xx"]
    url = (STATIC / "lib" / "model.mjs").as_uri()
    script = (
        f"import {{ matchTopic }} from '{url}';"
        f"const p={json.dumps(patterns)}, t={json.dumps(topics)};"
        "console.log(JSON.stringify(p.flatMap(a => t.map(b => [a, b, matchTopic(a, b)]))));"
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30, check=True
    ).stdout
    for pattern, topic, js_result in json.loads(out):
        assert contract.topic_match(pattern, topic) is js_result, (pattern, topic)
