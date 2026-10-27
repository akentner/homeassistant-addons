from __future__ import annotations

import json
import logging

import pytest
from test_engine_supervisor import FakeProvider, SCHEMA, check, make, secrets, state

from app.engine.config import load_config
from app.engine.synthetic import SyntheticError, apply

REAL = {"db_user": "ha", "db_password": "p@ss/w:rd", "host": "db.local", "empty": "", "a-b": "dash"}


def render(template, real=None, name="x"):
    return apply(REAL if real is None else real, [(name, template)])[name]


def code_of(template, real=None):
    with pytest.raises(SyntheticError) as exc:
        render(template, real)
    return exc.value.code


# ---------------------------------------------------------------- rendering


def test_dsn_use_case():
    out = render("postgresql://{{ db_user | urlquote }}:{{ db_password | urlquote }}@{{ host }}:5432/ha")
    assert out == "postgresql://ha:p%40ss%2Fw%3Ard@db.local:5432/ha"


def test_urlquote_reserved_chars():
    assert render("{{ v | urlquote }}", {"v": "a/b@c:d e?f#g&h=ä"}) == "a%2Fb%40c%3Ad%20e%3Ff%23g%26h%3D%C3%A4"


@pytest.mark.parametrize("template,expected", [
    ("{{ host | substr(0, 2) }}", "db"),
    ("{{ host | substr(3) }}", "local"),
    ("{{ host | substr(-5) }}", "local"),
    ("{{ host | substr(-5, 2) }}", "lo"),
    ("{{ host | substr(-100, 2) }}", "db"),
    ("{{ host | substr(100) }}", ""),
    ("{{ host | substr(2, 100) }}", ".local"),
    ("{{ host | substr(2, 0) }}", ""),
    ("{{ host | substr(2, -3) }}", ""),
    ("{{ host | substr(0, length=2) }}", "db"),
    ("{{ empty | substr(0, 5) }}", ""),
])
def test_substr_edges(template, expected):
    assert render(template) == expected


def test_default_filter_and_undefined_inside_default():
    assert render("{{ nope | default('fallback') }}") == "fallback"
    assert render("{{ secrets['nope'] | default('fb') }}") == "fb"
    assert render("{{ empty | default('fb', boolean=true) }}") == "fb"
    assert render("{{ host | default('fb') }}") == "db.local"


def test_misc_filters_and_syntax():
    assert render("{{ host | upper }}-{{ host | length }}") == "DB.LOCAL-8"
    assert render("{{ '  x ' | trim | capitalize }}{{ 'a b' | title }}") == "XA B"
    assert render("{{ host | replace('.', '_') }}") == "db_local"
    assert render("{{ ['a', 'b'] | join('-') }}") == "a-b"
    assert render("{{ host | b64encode | b64decode }}") == "db.local"
    assert render("{{ secrets['a-b'] }}") == "dash"  # non identifier keys via secrets[...]
    assert render("{% if host == 'db.local' and not empty %}yes{% elif host %}mid{% else %}no{% endif %}") == "yes"
    assert render("{{ 'a' ~ host + '!' }}") == "adb.local!"
    assert render("{{ 'x' if empty else 'y' }}") == "y"
    assert render("{{ 'db' in ['db', 'x'] }}") == "True"


def test_no_chaining_between_synthetic_keys():
    with pytest.raises(SyntheticError) as exc:
        apply(REAL, [("one", "{{ host }}"), ("two", "{{ one }}")])
    assert exc.value.code == "synthetic_undefined" and "'one'" in str(exc.value)
    with pytest.raises(SyntheticError) as exc:
        apply(REAL, [("one", "{{ host }}"), ("two", "{{ secrets['one'] }}")])
    assert exc.value.code == "synthetic_undefined"


def test_undefined_key_names_only():
    with pytest.raises(SyntheticError) as exc:
        apply(REAL, [("dsn", "{{ missing_key }}")])
    assert exc.value.code == "synthetic_undefined"
    assert str(exc.value) == "synthetic key 'dsn': references an undefined key (key 'missing_key')"
    assert code_of("{{ secrets['nope'] }}") == "synthetic_undefined"
    assert code_of("{{ missing | length }}") == "synthetic_undefined"


def test_collision_with_real_key():
    with pytest.raises(SyntheticError) as exc:
        apply(REAL, [("host", "x")])
    assert exc.value.code == "synthetic_collision" and "'host'" in str(exc.value)


def test_returns_only_synthetic_and_does_not_mutate():
    real = dict(REAL)
    assert apply(real, [("n", "{{ host }}")]) == {"n": "db.local"}
    assert real == REAL
    assert apply(real, []) == {}


# ---------------------------------------------------------------- forbidden constructs


@pytest.mark.parametrize("template", [
    "{% for i in [1] %}x{% endfor %}",
    "{% set a = 1 %}{{ a }}",
    "{% macro m() %}x{% endmacro %}{{ m() }}",
    "{% import 'x' as y %}",
    "{% include 'x' %}",
    "{% extends 'x' %}",
    "{% block b %}x{% endblock %}",
    "{% filter upper %}x{% endfilter %}",
    "{% call m() %}x{% endcall %}",
    "{{ ''.__class__ }}",
    "{{ host.upper }}",
    "{{ host.upper() }}",
    "{{ host['upper'] }}",
    "{{ secrets.host }}",
    "{{ secrets }}",
    "{{ secrets | length }}",
    "{{ host[0] }}",
    "{{ 'a' * 3 }}",
    "{{ 2 ** 8 }}",
    "{{ 5 % 2 }}",
    "{{ 5 // 2 }}",
    "{{ 5 - 2 }}",
    "{{ 5 / 2 }}",
    "{{ +5 }}",
    "{{ range(3) }}",
    "{{ lipsum() }}",
    "{{ dict(a=1) }}",
    "{{ {'a': 1} }}",
    "{{ host | urlencode }}",
    "{{ host | e }}",
    "{{ host | tojson }}",
    "{{ host | attr('x') }}",
    "{{ host | unknown }}",
    "{{ host | shquote }}",
    "{{ host | d('x') }}",
    "{{ host | join(attribute='x') }}",
    "{{ host is defined }}",
    "{% if host is string %}x{% endif %}",
    "{{ host | substr(*[1]) }}",
    "{{ host | replace(**{'a': 'b'}) }}",
    "{{ cycler }}",
    "{{ self }}",
])
def test_forbidden(template):
    assert code_of(template) in {"synthetic_forbidden", "synthetic_undefined"}
    if "cycler" not in template and "self" not in template and "lipsum" not in template and "range" not in template:
        assert code_of(template) == "synthetic_forbidden"


def test_globals_unavailable_even_if_allowed_by_ast():
    # names like range/dict/lipsum pass the name rule but resolve to nothing
    assert code_of("{{ range }}") == "synthetic_undefined"
    assert code_of("{{ lipsum }}") == "synthetic_undefined"


def test_syntax_error():
    assert code_of("{{ host ") == "synthetic_syntax"
    assert code_of("{% if %}") == "synthetic_syntax"


def test_runtime_error_is_generic():
    assert code_of("{{ host | b64decode }}") == "synthetic_error"
    assert code_of("{{ 1 + host }}") == "synthetic_error"
    assert code_of("{{ host | substr('x') }}") == "synthetic_error"


# ---------------------------------------------------------------- limits


def test_output_limit():
    big = {"v": "a" * 40000}
    assert len(render("{{ v }}", big)) == 40000
    assert code_of("{{ v }}{{ v }}", big) == "synthetic_too_large"
    assert code_of("{{ v | replace('a', 'bb') }}", big) == "synthetic_too_large"
    assert code_of("{{ v | replace('', 'xxxxxxxxxxxxxxxxxxxx') | replace('', 'yyyyyyyyyyyyyyyyyyyy') }}",
                   {"v": "a" * 60000}) == "synthetic_too_large"


def test_config_template_limits(tmp_path):
    def cfg(entries):
        opts = tmp_path / "o.json"
        opts.write_text(json.dumps({"providers": ["bitwarden"], "synthetic_keys": entries}))
        return load_config({"SS_OPTIONS": str(opts)})

    ok = cfg([{"name": "a", "template": "{{ x }}"}, {"name": "_b1", "template": "y"}])
    assert ok.synthetic_keys == (("a", "{{ x }}"), ("_b1", "y")) and ok.problems == ()
    assert cfg([]).synthetic_keys == ()
    for entries, code in [
        ([{"name": "1bad", "template": "x"}], "synthetic_invalid_name"),
        ([{"name": "a-b", "template": "x"}], "synthetic_invalid_name"),
        ([{"name": "a" * 129, "template": "x"}], "synthetic_invalid_name"),
        ([{"name": "a", "template": "x"}, {"name": "a", "template": "y"}], "synthetic_invalid_name"),
        ([{"name": "a", "template": "x" * 2049}], "synthetic_template_too_long"),
        ([{"name": "a", "template": ""}], "config_invalid"),
        ([{"name": "a"}], "config_invalid"),
        (["str"], "synthetic_invalid_name"),
    ]:
        assert [p.code for p in cfg(entries).problems] == [code], entries
    assert len(cfg([{"name": "a", "template": "x" * 2048}]).synthetic_keys) == 1
    bad = cfg([{"name": "a", "template": "SECRET-TEMPLATE-TEXT" * 200}])
    assert "SECRET-TEMPLATE-TEXT" not in " ".join(p.message for p in bad.problems)


# ---------------------------------------------------------------- supervisor


def sup_with(tmp_path, defs, secrets_=None, **over):
    prov = FakeProvider("bitwarden", secrets_ or {"db_user": "ha", "db_password": "p@ss/w:rd", "host": "db"})
    sup = make(tmp_path, {"bitwarden": prov}, **over)
    object.__setattr__(sup.cfg, "synthetic_keys", tuple(defs))
    return sup, prov


DSN = ("dsn", "pg://{{ db_user | urlquote }}:{{ db_password | urlquote }}@{{ host }}/ha")


def test_cycle_writes_synthetic_key(tmp_path):
    sup, _ = sup_with(tmp_path, [DSN])
    assert sup.run_once() == "ok"
    assert secrets(sup)["dsn"] == "pg://ha:p%40ss%2Fw%3Ard@db/ha"
    data = state(sup)
    check(data, SCHEMA)
    assert data["items"] == 4 and data["keys"]["synthetic"] == ["dsn"] and "dsn" in data["keys"]["names"]
    assert "dsn" in data["keys"]["added"]


def test_no_synthetic_block_without_defs(tmp_path):
    sup, _ = sup_with(tmp_path, [])
    sup.run_once()
    assert "synthetic" not in state(sup)["keys"]


def test_synthetic_diff_on_change(tmp_path):
    sup, prov = sup_with(tmp_path, [DSN])
    sup.run_once()
    prov.secrets["host"] = "db2"
    sup.run_once()
    keys = state(sup)["keys"]
    assert sorted(keys["changed"]) == ["dsn", "host"] and keys["added"] == []


def test_synthetic_counts_for_shrink_guard(tmp_path):
    sup, prov = sup_with(tmp_path, [DSN], secrets_={f"k{i}": "v" for i in range(6)} | {"db_user": "u",
                         "db_password": "p", "host": "h"})
    sup.run_once()  # 10 items incl. synthetic
    prov.secrets = {"db_user": "u", "db_password": "p", "host": "h"}  # 4 items incl. synthetic < 50%
    assert sup.run_once() == "degraded" and state(sup)["error_code"] == "shrink_guard"


def test_error_is_fatal_like_collision(tmp_path):
    sup, prov = sup_with(tmp_path, [DSN])
    sup.run_once()
    old = sup.cfg.secrets_file.read_bytes()
    prov.secrets = {"db_user": "u", "host": "h"}  # db_password gone -> undefined
    assert sup.run_once() == "degraded"
    data = state(sup)
    assert data["error_code"] == "synthetic_undefined"
    assert data["events"][0]["code"] == "synthetic_undefined" and "'dsn'" in data["events"][0]["message"]
    assert sup.cfg.secrets_file.read_bytes() == old


def test_error_without_prior_write_is_error(tmp_path):
    sup, _ = sup_with(tmp_path, [("db_user", "x")])
    assert sup.run_once() == "error"
    assert state(sup)["error_code"] == "synthetic_collision" and not sup.cfg.secrets_file.exists()


def test_preview_includes_synthetic(tmp_path):
    sup, prov = sup_with(tmp_path, [DSN])
    sup.run_once()
    prov.secrets["host"] = "db9"
    out = sup.preview()
    assert out["changed"] == ["dsn", "host"] and out["synthetic"] == ["dsn"] and out["errors"] == []
    assert "p%40ss" not in json.dumps(out)
    sup2, _ = sup_with(tmp_path / "b", [("x", "{{ nope }}")])
    out = sup2.preview()
    assert out["errors"][0]["code"] == "synthetic_undefined" and "nope" in out["errors"][0]["message"]


def test_leak_sentinel_never_surfaces(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    sentinel = "SENTINEL-d9f3a1-secret"
    real = {"db_password": sentinel, "host": "h"}
    failing = [
        ("t1", "{{ db_password | substr('x') }}"),                 # runtime error with the value as input
        ("t2", "{{ secrets[db_password] }}"),                      # value used as lookup key
        ("t3", "{{ db_password | b64decode }}"),
        ("t4", "{{ db_password.__class__ }}"),
        ("t5", "{{ db_password }}{{ undefined_thing }}"),
        ("t6", "{{ db_password | replace('', 'y' * 3) }}"),
        ("t7", "{{ db_password ~ '"),                              # syntax error containing the value name
        ("t8", "{{ " + "db_password | upper | " * 1 + "nofilter }}"),
    ]
    blobs = []
    for i, entry in enumerate(failing):
        sup, _ = sup_with(tmp_path / f"s{i}", [entry], secrets_=real)
        sup.run_once()
        sup.preview()
        blobs.append(sup.cfg.state_file.read_text())
        blobs.append(sup.state.render().__repr__())
    # a succeeding template whose value is later logged by a failing cycle must be scrubbed too
    sup, prov = sup_with(tmp_path / "ok", [("good", "<{{ db_password }}>")], secrets_=real)
    sup.run_once()
    blobs.append(sup.cfg.state_file.read_text())
    assert sentinel not in caplog.text and all(sentinel not in b for b in blobs)
    with pytest.raises(SyntheticError) as exc:
        apply(real, [("t", "{{ db_password | substr('x') }}")])
    assert sentinel not in str(exc.value) and sentinel not in repr(exc.value.args)
    assert exc.value.__cause__ is None and exc.value.__suppress_context__
