from __future__ import annotations

import json
import logging
import stat
import threading
import time
from pathlib import Path

import pytest
import yaml

from app.engine.config import Config
from app.engine.supervisor import Supervisor
from app.providers.base import Problem, ProviderError, Snapshot

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "docs" / "state.schema.json").read_text())


def check(value, schema, root=SCHEMA, path="$"):
    """Minimal JSON-schema validator for the subset used by state.schema.json."""
    if "$ref" in schema:
        schema = root["$defs"][schema["$ref"].rsplit("/", 1)[1]]
    if "const" in schema:
        assert value == schema["const"], path
    if "enum" in schema:
        assert value in schema["enum"], f"{path}: {value}"
    types = schema.get("type")
    if types:
        types = [types] if isinstance(types, str) else types
        py = {"string": str, "integer": int, "boolean": bool, "object": dict, "array": list, "null": type(None)}
        assert any(isinstance(value, py[t]) and not (t == "integer" and isinstance(value, bool)) for t in types), \
            f"{path}: {value!r} not {types}"
    if isinstance(value, (int, float)) and "minimum" in schema:
        assert value >= schema["minimum"], path
    if isinstance(value, dict):
        for req in schema.get("required", []):
            assert req in value, f"{path}: missing {req}"
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            assert set(value) <= set(props), f"{path}: extra {set(value) - set(props)}"
        for k, v in value.items():
            if k in props:
                check(v, props[k], root, f"{path}.{k}")
            elif isinstance(schema.get("additionalProperties"), dict):
                check(v, schema["additionalProperties"], root, f"{path}.{k}")
    if isinstance(value, list):
        if "maxItems" in schema:
            assert len(value) <= schema["maxItems"]
        for i, v in enumerate(value):
            if "items" in schema:
                check(v, schema["items"], root, f"{path}[{i}]")


class FakeProvider:
    def __init__(self, name, secrets=None, files=None, error=None, problems=None):
        self.name = name
        self.secrets = secrets or {}
        self.files = files or {}
        self.error = error
        self.problems = problems or []
        self.notices = []

    def validate(self, cfg):
        return self.problems

    def fetch(self):
        if self.error:
            raise self.error
        return Snapshot(secrets=dict(self.secrets), files=dict(self.files), revision="r1")


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now


def make(tmp_path, providers, clock=None, **over):
    cfg = Config(providers=tuple(providers), interval=over.pop("interval", 300),
                 collision_policy=over.pop("collision_policy", "error"),
                 shrink_guard_percent=over.pop("shrink_guard_percent", 50), log_level="info",
                 provider_cfg={}, secrets_file=tmp_path / "config" / "secrets.yaml",
                 files_dir=tmp_path / "config" / "files", state_file=tmp_path / "data" / "state.json",
                 data_dir=tmp_path / "data", port=0, version="0.1.0", problems=over.pop("problems", ()),
                 usage_scan=over.pop("usage_scan", "off"), check_interval=over.pop("check_interval", 0),
                 addon_configs_dir=over.pop("addon_configs_dir", tmp_path / "addon_configs"))
    return Supervisor(cfg, providers=providers, clock=clock or Clock(), probe_versions=False,
                      reloader=over.pop("reloader", lambda: "skipped"))


def state(sup):
    data = json.loads(sup.cfg.state_file.read_text())
    check(data, SCHEMA)
    return data


def secrets(sup):
    return yaml.safe_load(sup.cfg.secrets_file.read_text())


def test_happy_path(tmp_path):
    sup = make(tmp_path, {"bitwarden": FakeProvider("bitwarden", {"a": "1", "b": "2"})})
    assert sup.run_once() == "ok"
    assert secrets(sup) == {"a": "1", "b": "2"}
    assert stat.S_IMODE(sup.cfg.secrets_file.stat().st_mode) == 0o600
    data = state(sup)
    assert data["status"] == "ok" and data["items"] == 2 and data["keys"]["added"] == ["a", "b"]
    assert data["providers"]["bitwarden"]["status"] == "ok"
    assert data["providers"]["sops"]["status"] == "disabled"
    assert data["events"][0]["code"] == "sync_ok" and data["versions"] == {"addon": "0.1.0"}
    assert data["age_seconds"] == 0 and data["stale"] is False


def test_diff_and_unchanged_cycle(tmp_path):
    prov = FakeProvider("bitwarden", {"a": "1", "b": "2"})
    sup = make(tmp_path, {"bitwarden": prov})
    sup.run_once()
    prov.secrets = {"a": "changed", "c": "3"}
    sup.run_once()
    keys = state(sup)["keys"]
    assert (keys["added"], keys["removed"], keys["changed"]) == (["c"], ["b"], ["a"])
    events = len(state(sup)["events"])
    sup.run_once()  # nothing changed: no new event, diff retained
    data = state(sup)
    assert len(data["events"]) == events and data["keys"]["added"] == ["c"]


def test_key_collision_writes_nothing(tmp_path):
    sup = make(tmp_path, {"bitwarden": FakeProvider("bitwarden", {"a": "value-1"}),
                          "sops": FakeProvider("sops", {"a": "value-2"})})
    assert sup.run_once() == "error"
    assert not sup.cfg.secrets_file.exists()
    data = state(sup)
    assert data["error_code"] == "key_collision"
    assert "bitwarden" in data["events"][0]["message"] and "sops" in data["events"][0]["message"]


def test_collision_after_success_keeps_last_file(tmp_path):
    a, b = FakeProvider("bitwarden", {"a": "1"}), FakeProvider("sops", {"b": "2"})
    sup = make(tmp_path, {"bitwarden": a, "sops": b})
    sup.run_once()
    b.secrets = {"a": "x"}
    assert sup.run_once() == "degraded"
    assert secrets(sup) == {"a": "1", "b": "2"}


def test_provider_collision_error_is_fatal(tmp_path):
    a = FakeProvider("bitwarden", {"a": "1"})
    sup = make(tmp_path, {"bitwarden": a})
    sup.run_once()
    a.error = ProviderError("key_collision", "key 'a' produced by items 'x' and 'y'")
    assert sup.run_once() == "degraded"
    assert state(sup)["error_code"] == "key_collision"
    assert secrets(sup) == {"a": "1"}


def test_priority_policy(tmp_path):
    sup = make(tmp_path, {"bitwarden": FakeProvider("bitwarden", {"a": "1"}),
                          "sops": FakeProvider("sops", {"a": "2"})}, collision_policy="priority")
    assert sup.run_once() == "ok"
    assert secrets(sup) == {"a": "1"}
    assert any(e["code"] == "key_shadowed" for e in state(sup)["events"])


def test_shrink_guard_and_force(tmp_path):
    prov = FakeProvider("bitwarden", {f"k{i}": "v" for i in range(10)})
    sup = make(tmp_path, {"bitwarden": prov})
    sup.run_once()
    prov.secrets = {"k0": "v"}
    assert sup.run_once() == "degraded"
    assert state(sup)["error_code"] == "shrink_guard" and len(secrets(sup)) == 10
    assert sup.run_once(force=True) == "ok"
    assert secrets(sup) == {"k0": "v"}


def test_zero_items_blocked(tmp_path):
    prov = FakeProvider("bitwarden", {"a": "1"})
    sup = make(tmp_path, {"bitwarden": prov})
    sup.run_once()
    prov.secrets = {}
    assert sup.run_once(force=True) == "degraded"
    assert secrets(sup) == {"a": "1"}


def test_guard_cleared_when_cycle_passes(tmp_path):
    prov = FakeProvider("bitwarden", {f"k{i}": "v" for i in range(10)})
    sup = make(tmp_path, {"bitwarden": prov})
    sup.run_once()
    prov.secrets = {"k0": "v"}
    sup.run_once()
    prov.secrets = {f"k{i}": "v" for i in range(9)}
    assert sup.run_once() == "ok"
    assert state(sup)["error_code"] is None


def test_provider_failure_keeps_last_good_in_memory(tmp_path):
    a, b = FakeProvider("bitwarden", {"a": "1"}), FakeProvider("sops", {"b": "2"})
    sup = make(tmp_path, {"bitwarden": a, "sops": b})
    sup.run_once()
    b.error = ProviderError("sops_failed")
    a.secrets = {"a": "new"}
    assert sup.run_once() == "degraded"
    assert secrets(sup) == {"a": "new", "b": "2"}
    data = state(sup)
    assert data["providers"]["sops"]["status"] == "degraded" and data["providers"]["sops"]["items"] == 1
    assert data["error_code"] == "sops_failed"
    b.error = None
    assert sup.run_once() == "ok"


def test_provider_failure_after_restart_writes_nothing(tmp_path):
    a, b = FakeProvider("bitwarden", {"a": "1"}), FakeProvider("sops", {"b": "2"})
    sup = make(tmp_path, {"bitwarden": a, "sops": b})
    sup.run_once()
    old = sup.cfg.secrets_file.read_bytes()
    b.error = ProviderError("sops_failed")
    a.secrets = {"a": "new"}
    restarted = make(tmp_path, {"bitwarden": a, "sops": b})
    assert restarted.run_once() == "degraded"  # last success is known from state.json
    assert sup.cfg.secrets_file.read_bytes() == old


def test_never_succeeded_is_error(tmp_path):
    err = ProviderError("bw_auth_failed", "login rejected")
    sup = make(tmp_path, {"bitwarden": FakeProvider("bitwarden", error=err)})
    assert sup.run_once() == "error"
    data = state(sup)
    assert any("bw_auth_failed: login rejected" in e["message"] for e in data["events"])
    assert data["providers"]["bitwarden"]["status"] == "error" and data["error_code"] == "bw_auth_failed"
    assert data["last_success_at"] is None and data["age_seconds"] is None


def test_validate_problems_skip_provider(tmp_path):
    prov = FakeProvider("bitwarden", {"a": "1"}, problems=[Problem("bw_missing_client_id", "not set")])
    sup = make(tmp_path, {"bitwarden": prov})
    assert sup.run_once() == "error"
    problems = state(sup)["providers"]["bitwarden"]["problems"]
    assert problems == [{"code": "bw_missing_client_id", "message": "not set", "severity": "error"}]


def test_unexpected_exception_is_contained(tmp_path):
    class Boom(FakeProvider):
        def fetch(self):
            raise RuntimeError("secret-value-123 in message")

    sup = make(tmp_path, {"bitwarden": Boom("bitwarden")})
    assert sup.run_once() == "error"
    text = sup.cfg.state_file.read_text()
    assert "secret-value-123" not in text and "provider_internal_error" in text


def test_bad_config_stays_error_and_keeps_state(tmp_path):
    from app.providers.base import Problem as P

    sup = make(tmp_path, {}, problems=(P("config_invalid", "option 'interval' bad"),))
    assert sup.run_once() == "error"
    assert state(sup)["error_code"] == "config_invalid"


def test_files_written_and_removed(tmp_path):
    prov = FakeProvider("bitwarden", {"a": "1"}, files={"bw/note.txt": b"hello"})
    sup = make(tmp_path, {"bitwarden": prov})
    sup.run_once()
    assert (sup.cfg.files_dir / "bw" / "note.txt").read_bytes() == b"hello"
    prov.files = {}
    sup.run_once()
    assert not (sup.cfg.files_dir / "bw" / "note.txt").exists()


def test_unsafe_file_path_blocks_cycle(tmp_path):
    prov = FakeProvider("bitwarden", {"a": "1"}, files={"../evil": b"x"})
    sup = make(tmp_path, {"bitwarden": prov})
    assert sup.run_once() == "error"
    assert state(sup)["error_code"] == "unsafe_path"
    assert not sup.cfg.secrets_file.exists() and not (tmp_path / "config" / "evil").exists()


def test_write_failure_is_reported(tmp_path, monkeypatch):
    prov = FakeProvider("bitwarden", {"a": "1"})
    sup = make(tmp_path, {"bitwarden": prov})
    sup.run_once()
    prov.secrets = {"a": "2"}
    from app.engine import writer

    real = writer.os.replace

    def replace(src, dst):
        if str(dst).endswith("secrets.yaml"):
            raise OSError("full")
        real(src, dst)

    monkeypatch.setattr(writer.os, "replace", replace)
    assert sup.run_once() == "degraded"
    assert state(sup)["error_code"] == "write_failed" and secrets(sup) == {"a": "1"}


def test_backoff_and_interval(tmp_path):
    clock = Clock()
    prov = FakeProvider("bitwarden", {"a": "1"})
    sup = make(tmp_path, {"bitwarden": prov}, clock, interval=300)
    sup.run_once()
    assert sup._next_at - clock() == 300
    prov.error = ProviderError("x")
    delays = []
    for _ in range(6):
        sup.run_once()
        delays.append(sup._next_at - clock())
    assert delays == [30, 60, 120, 240, 300, 300]
    prov.error = None
    sup.run_once()
    assert sup._next_at - clock() == 300


def test_stale_flag_and_age(tmp_path):
    clock = Clock()
    sup = make(tmp_path, {"bitwarden": FakeProvider("bitwarden", {"a": "1"})}, clock, interval=100)
    sup.run_once()
    clock.now += 201
    sup.state.save()
    data = state(sup)
    assert data["age_seconds"] == 201 and data["stale"] is True


def test_trigger_sync_rate_limit(tmp_path):
    clock = Clock()
    sup = make(tmp_path, {"bitwarden": FakeProvider("bitwarden", {"a": "1"})}, clock)
    sup.run_once()
    assert sup.trigger_sync() is False  # last attempt just now
    clock.now += 11
    assert sup.trigger_sync() is True
    assert sup.trigger_sync() is False  # already pending


def test_trigger_sync_forced_through_loop(tmp_path):
    clock = Clock()
    prov = FakeProvider("bitwarden", {f"k{i}": "v" for i in range(10)})
    sup = make(tmp_path, {"bitwarden": prov}, clock)
    sup.run_once()
    prov.secrets = {"k0": "v"}
    clock.now += 11
    done = threading.Event()
    real = sup.run_once

    def spy(force=False):
        status = real(force=force)
        if force:
            done.set()
            sup.stop()
        return status

    sup.run_once = spy  # type: ignore[method-assign]
    thread = threading.Thread(target=sup.run_forever)
    thread.start()
    deadline = time.time() + 10
    while sup._last_attempt <= clock.now - 11 and time.time() < deadline:  # wait for the loop's first cycle
        time.sleep(0.01)
    time.sleep(0.2)
    clock.now += 11
    assert sup.trigger_sync(force=True)
    thread.join(10)
    assert done.is_set() and secrets(sup) == {"k0": "v"}


def test_preview_names_only(tmp_path):
    prov = FakeProvider("bitwarden", {"a": "old", "b": "2"})
    sup = make(tmp_path, {"bitwarden": prov})
    sup.run_once()
    prov.secrets = {"a": "new-value", "c": "3"}
    before = sup.cfg.secrets_file.read_bytes()
    out = sup.preview()
    assert out == {"added": ["c"], "removed": ["b"], "changed": ["a"], "errors": []}
    assert "new-value" not in json.dumps(out)
    assert sup.cfg.secrets_file.read_bytes() == before
    prov.error = ProviderError("x")
    assert sup.preview()["errors"][0]["code"] == "x"


def test_state_survives_restart(tmp_path):
    sup = make(tmp_path, {"bitwarden": FakeProvider("bitwarden", {"a": "1"})})
    sup.run_once()
    again = make(tmp_path, {"bitwarden": FakeProvider("bitwarden", {"a": "1"})})
    assert again.state.items == 1 and again.state.events and again.state.status == "starting"
    again.state.save()
    assert state(again)["status"] == "starting"


def test_no_values_in_logs_or_state(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    secret_vals = {"mqtt_pw": "Tr0ub4dor&3-unique", "token": "zzz-marker-two-unique"}
    prov = FakeProvider("bitwarden", secret_vals)
    sup = make(tmp_path, {"bitwarden": prov, "sops": FakeProvider("sops", {"mqtt_pw": "dup-unique-value"})})
    sup.run_once()  # collision
    prov2 = FakeProvider("sops", error=ProviderError("sops_failed", "decrypt failed for Tr0ub4dor&3-unique"))
    sup2 = make(tmp_path / "second", {"bitwarden": prov, "sops": prov2})
    sup2.run_once()
    sup2.preview()
    blob = caplog.text + sup.cfg.state_file.read_text() + sup2.cfg.state_file.read_text()
    for value in (*secret_vals.values(), "dup-unique-value"):
        assert value not in blob


def test_provider_notice_is_emitted_when_cycle_fails(tmp_path):
    prov = FakeProvider("bitwarden", {})
    prov.notices = [("warning", "bw_filter_empty", "filter matched no items")]
    sup = make(tmp_path, {"bitwarden": prov})
    assert sup.run_once() == "error"
    data = state(sup)
    assert data["error_code"] == "shrink_guard"
    assert any(e["code"] == "bw_filter_empty" for e in data["events"])


def test_usage_scan_reports_missing_unused_and_never_values(tmp_path):
    cfgdir = tmp_path / "config"
    (cfgdir / "packages").mkdir(parents=True)
    (cfgdir / "packages" / "mqtt.yaml").write_text("pw: !secret a\nother: !secret gone\n")
    sup = make(tmp_path, {"bitwarden": FakeProvider("bitwarden", {"a": "value-aaa", "b": "value-bbb"})},
               usage_scan="config")
    assert sup.run_once() == "ok"
    data = state(sup)
    usage = data["usage"]
    assert usage["enabled"] is True and usage["roots"] == ["config"]
    assert usage["used"]["a"]["refs"] == [{"file": "packages/mqtt.yaml", "line": 1}]
    assert list(usage["missing"]) == ["gone"] and usage["unused"] == ["b"]
    assert any(e["code"] == "secret_missing" and "gone" in e["message"] for e in data["events"])
    assert "value-aaa" not in json.dumps(data) and "value-bbb" not in json.dumps(data)


def test_usage_scan_off_by_default_and_event_not_repeated(tmp_path):
    clock = Clock()
    sup = make(tmp_path, {"bitwarden": FakeProvider("bitwarden", {"a": "1"})}, clock=clock)
    sup.run_once()
    assert state(sup)["usage"] == {"enabled": False}
    cfgdir = tmp_path / "config"
    (cfgdir / "x.yaml").write_text("k: !secret gone\n")
    sup2 = make(tmp_path / "second", {"bitwarden": FakeProvider("bitwarden", {"a": "1"})}, clock=clock,
                usage_scan="config")
    (tmp_path / "second" / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "second" / "config" / "x.yaml").write_text("k: !secret gone\n")
    sup2.run_once()
    clock.now += 100
    sup2.run_once()
    clock.now += 100
    sup2.run_once()
    assert [e["code"] for e in state(sup2)["events"]].count("secret_missing") == 1


class Reloader:
    def __init__(self, result=None):
        self.calls = 0
        self.result = result

    def __call__(self):
        self.calls += 1
        return self.result


def test_supervisor_reload_only_when_key_names_change(tmp_path):
    prov = FakeProvider("bitwarden", {"a": "1"})
    rl = Reloader()
    sup = make(tmp_path, {"bitwarden": prov}, reloader=rl)
    sup.run_once()
    assert rl.calls == 1  # first write adds keys
    assert any(e["code"] == "supervisor_reload" for e in state(sup)["events"])
    prov.secrets = {"a": "changed"}
    sup.run_once()
    assert rl.calls == 1  # value change only: no reload
    prov.secrets = {"a": "changed", "b": "2"}
    sup.run_once()
    assert rl.calls == 2


def test_supervisor_reload_retried_once_after_throttle_window(tmp_path):
    clock = Clock()
    rl = Reloader()
    sup = make(tmp_path, {"bitwarden": FakeProvider("bitwarden", {"a": "1"})}, clock=clock, reloader=rl)
    sup.run_once()
    sup._retry_reload(clock.now + 10)
    assert rl.calls == 1
    sup._retry_reload(clock.now + 70)
    assert rl.calls == 2
    sup._retry_reload(clock.now + 200)
    assert rl.calls == 2


def test_supervisor_reload_failure_is_only_a_warning(tmp_path):
    sup = make(tmp_path, {"bitwarden": FakeProvider("bitwarden", {"a": "1"})}, reloader=Reloader("http_403"))
    assert sup.run_once() == "ok"
    events = state(sup)["events"]
    assert any(e["code"] == "supervisor_reload_failed" and e["level"] == "warning" for e in events)
