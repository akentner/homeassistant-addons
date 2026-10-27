from __future__ import annotations

import json
import threading
import time

import pytest
from test_engine_supervisor import Clock, FakeProvider, check, make, SCHEMA, state

from app.engine import supervisor as sup_mod
from app.engine.config import load_config
from app.providers.base import ProviderError, Snapshot


class CheckProvider(FakeProvider):
    """Provider with a cheap change probe; `token` is what check() returns and what fetch() reports."""

    def __init__(self, name="sops", secrets=None, token="a" * 40):
        super().__init__(name, secrets or {"a": "1"})
        self.token = token
        self.check_error: ProviderError | None = None
        self.checks = 0

    def check(self):
        self.checks += 1
        if self.check_error:
            raise self.check_error
        return self.token

    def fetch(self):
        snap = super().fetch()
        snap.check_token = self.token
        return snap


def mk(tmp_path, provider, clock=None, **over):
    over.setdefault("check_interval", 60)
    return make(tmp_path, {provider.name: provider}, clock, **over)


# ---------------------------------------------------------------- config


def _cfg(tmp_path, options):
    opts = tmp_path / "options.json"
    opts.write_text(json.dumps(options))
    return load_config({"SS_OPTIONS": str(opts)})


@pytest.mark.parametrize("raw,expected", [(None, 60), (0, 0), (30, 30), (45, 45), (3600, 3600), (1, 30), (29, 30)])
def test_check_interval_values(tmp_path, raw, expected):
    options = {"providers": ["bitwarden"]}
    if raw is not None:
        options["check_interval"] = raw
    cfg = _cfg(tmp_path, options)
    assert cfg.check_interval == expected and cfg.problems == ()


@pytest.mark.parametrize("raw", [-1, 3601, "x", True, 1.5])
def test_check_interval_invalid(tmp_path, raw):
    cfg = _cfg(tmp_path, {"providers": ["bitwarden"], "check_interval": raw})
    assert cfg.check_interval == 60
    assert [p.code for p in cfg.problems] == ["config_invalid"]


# ---------------------------------------------------------------- state block


def test_disabled_block(tmp_path):
    sup = mk(tmp_path, CheckProvider(), check_interval=0)
    sup.run_once()
    assert state(sup)["check"] == {"enabled": False, "interval": 0, "last_check_at": None, "result": None}


def test_enabled_block_validates(tmp_path):
    sup = mk(tmp_path, CheckProvider())
    sup.run_once()
    data = state(sup)
    assert data["check"] == {"enabled": True, "interval": 60, "last_check_at": None, "result": None,
                             "error_code": None, "triggered_syncs": 0}
    sup.run_check()
    data = state(sup)
    check(data, SCHEMA)
    assert data["check"]["result"] == "unchanged" and data["check"]["last_check_at"] is not None


# ---------------------------------------------------------------- probing


def test_unchanged_does_not_trigger(tmp_path):
    clock = Clock()
    prov = CheckProvider()
    sup = mk(tmp_path, prov, clock)
    sup.run_once()
    clock.now += 100
    sup.run_check()
    assert prov.checks == 1 and sup._pending is False
    assert state(sup)["check"]["triggered_syncs"] == 0


def test_change_triggers_early_cycle(tmp_path):
    clock = Clock()
    prov = CheckProvider()
    sup = mk(tmp_path, prov, clock)
    sup.run_once()
    prov.token = "b" * 40
    clock.now += 100
    sup.run_check()
    data = state(sup)
    assert data["check"]["result"] == "changed" and data["check"]["triggered_syncs"] == 1
    assert sup._pending is True
    ev = [e for e in data["events"] if e["code"] == "source_changed"]
    assert len(ev) == 1 and ev[0]["provider"] == "sops" and "b" * 12 in ev[0]["message"]
    assert "b" * 13 not in ev[0]["message"]
    sup.run_once()  # the early cycle stores the new token
    clock.now += 100
    sup.run_check()
    assert state(sup)["check"]["result"] == "unchanged"


def test_first_probe_without_stored_token_only_records(tmp_path):
    clock = Clock()
    prov = CheckProvider(token="")  # fetch reports no token
    sup = mk(tmp_path, prov, clock)
    sup.run_once()
    prov.token = "c" * 40
    clock.now += 100
    sup.run_check()
    assert sup._pending is False and state(sup)["check"]["result"] == "unchanged"
    prov.token = "d" * 40
    clock.now += 100
    sup.run_check()
    assert sup._pending is True


def test_change_respects_manual_gap(tmp_path):
    clock = Clock()
    prov = CheckProvider()
    sup = mk(tmp_path, prov, clock)
    sup.run_once()
    prov.token = "b" * 40
    clock.now += 5  # last attempt less than 10 s ago
    sup.run_check()
    data = state(sup)
    assert sup._pending is False and data["check"]["triggered_syncs"] == 0
    clock.now += 60
    sup.run_check()  # retried at the next probe, event is not repeated
    assert sup._pending is True
    assert len([e for e in state(sup)["events"] if e["code"] == "source_changed"]) == 1


def test_change_does_not_bypass_backoff_or_guard(tmp_path):
    clock = Clock()
    prov = CheckProvider(secrets={f"k{i}": "v" for i in range(10)})
    sup = mk(tmp_path, prov, clock)
    sup.run_once()
    prov.token = "b" * 40
    prov.secrets = {"k0": "v"}
    clock.now += 100
    sup.run_check()
    assert sup._pending is True
    assert sup.run_once() == "degraded"  # guard still applies to the early cycle
    assert len(sup.cfg.secrets_file.read_text().splitlines()) == 11
    clock.now += 100
    prov.token = "c" * 40
    sup.run_check()
    assert sup._pending is False  # in backoff: the scheduled retry handles it
    assert state(sup)["check"]["triggered_syncs"] == 1


def test_check_failure_is_isolated(tmp_path):
    clock = Clock()
    prov = CheckProvider()
    sup = mk(tmp_path, prov, clock)
    sup.run_once()
    next_at, status = sup._next_at, sup.state.status
    prov.check_error = ProviderError("git_auth_failed", "https://user:tok@example.org failed")
    for _ in range(3):
        clock.now += 100
        sup.run_check()
    data = state(sup)
    assert data["check"]["result"] == "error" and data["check"]["error_code"] == "git_auth_failed"
    assert data["status"] == status == "ok" and sup._fails == 0 and sup._next_at == next_at
    events = [e for e in data["events"] if e["code"] == "check_failed"]
    assert len(events) == 1 and "example.org" not in events[0]["message"] and "tok" not in events[0]["message"]
    prov.check_error = ProviderError("git_timeout")
    sup.run_check()
    assert len([e for e in state(sup)["events"] if e["code"] == "check_failed"]) == 2
    prov.check_error = None
    sup.run_check()
    assert state(sup)["check"]["result"] == "unchanged" and state(sup)["check"]["error_code"] is None
    assert sup.cfg.secrets_file.exists()


def test_unexpected_check_exception_is_contained(tmp_path):
    prov = CheckProvider()
    sup = mk(tmp_path, prov)
    sup.run_once()
    prov.check_error = RuntimeError("secret-xyz")  # type: ignore[assignment]
    sup.run_check()
    text = sup.cfg.state_file.read_text()
    assert "secret-xyz" not in text and "check_internal_error" in text


def test_provider_without_check_is_unsupported(tmp_path):
    sup = mk(tmp_path, FakeProvider("bitwarden", {"a": "1"}))
    sup.run_once()
    sup.run_check()
    assert state(sup)["check"]["result"] == "unsupported" and sup._pending is False


def test_check_none_token_is_unsupported(tmp_path):
    prov = CheckProvider(token=None)  # type: ignore[arg-type]
    prov.fetch = lambda: Snapshot(secrets={"a": "1"})  # type: ignore[method-assign]
    sup = mk(tmp_path, prov)
    sup.run_once()
    sup.run_check()
    assert state(sup)["check"]["result"] == "unsupported"


def test_interval_zero_never_probes(tmp_path):
    prov = CheckProvider()
    sup = mk(tmp_path, prov, check_interval=0)
    sup.run_once()
    assert sup._next_probe is None
    sup.run_check()
    assert prov.checks == 0 and state(sup)["check"]["enabled"] is False


# ---------------------------------------------------------------- loop


def test_loop_probes_and_stops(tmp_path, monkeypatch):
    monkeypatch.setattr(sup_mod, "MANUAL_MIN_GAP", 0)
    prov = CheckProvider()
    sup = mk(tmp_path, prov, time.time, check_interval=1, interval=300)
    syncs = []
    real = sup.run_once

    def spy(force=False):
        syncs.append(time.time())
        return real(force=force)

    sup.run_once = spy  # type: ignore[method-assign]
    thread = threading.Thread(target=sup.run_forever)
    thread.start()
    deadline = time.time() + 10
    while prov.checks < 1 and time.time() < deadline:
        time.sleep(0.05)
    assert prov.checks >= 1 and len(syncs) == 1  # probed long before the 300 s interval
    prov.token = "e" * 40
    deadline = time.time() + 10
    while len(syncs) < 2 and time.time() < deadline:
        time.sleep(0.05)
    assert len(syncs) == 2  # early cycle after the change
    sup.stop()
    thread.join(5)
    assert not thread.is_alive()
