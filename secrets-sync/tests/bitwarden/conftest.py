"""Fake `bw` CLI on PATH, driven by files in a state directory (no network)."""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FAKE_BW = r'''#!__PY__
import json, os, sys, time
d = os.environ["FAKE_BW_DIR"]
args = sys.argv[1:]

def load(name, default):
    try:
        return json.load(open(os.path.join(d, name)))
    except FileNotFoundError:
        return default

def save(name, value):
    json.dump(value, open(os.path.join(d, name), "w"))

state = load("state.json", {"status": "unauthenticated", "serverUrl": None})
calls = load("calls.json", [])
calls.append({"argv": args, "has_session": "BW_SESSION" in os.environ,
              "session_ok": os.environ.get("BW_SESSION") == "SESSION123"})
save("calls.json", calls)
cmd = args[0] if args else ""
fail = load("fail.json", {})
if cmd in fail:
    f = fail[cmd]
    time.sleep(f.get("sleep", 0))
    if f.get("code"):
        sys.stderr.write(f.get("stderr", ""))
        sys.exit(f["code"])
if os.path.exists(os.path.join(d, "expire_once")) and cmd in ("sync", "list"):
    os.remove(os.path.join(d, "expire_once"))
    state["status"] = "locked"
    save("state.json", state)
    sys.stderr.write("Vault is locked.")
    sys.exit(1)
if cmd == "--version":
    print("2025.10.0")
elif cmd == "status":
    st = state["status"]
    if st == "unlocked" and os.environ.get("BW_SESSION") != "SESSION123":
        st = "locked"
    print(json.dumps({"serverUrl": state["serverUrl"], "status": st}))
elif cmd == "logout":
    state["status"] = "unauthenticated"
    save("state.json", state)
elif cmd == "config":
    if state["status"] != "unauthenticated":
        sys.stderr.write("Logout required before server config update.")
        sys.exit(1)
    state["serverUrl"] = args[2]
    save("state.json", state)
elif cmd == "login":
    if os.environ.get("BW_CLIENTID") != "cid" or os.environ.get("BW_CLIENTSECRET") != "csecret-value":
        sys.stderr.write("Invalid API Key; csecret-value leaked on purpose")
        sys.exit(1)
    state["status"] = "locked"
    save("state.json", state)
elif cmd == "unlock":
    name = args[args.index("--passwordenv") + 1]
    if os.environ.get(name) != "master-pw-value":
        sys.stderr.write("Invalid master password.")
        sys.exit(1)
    state["status"] = "unlocked"
    save("state.json", state)
    print("SESSION123")
elif cmd == "sync":
    if state["status"] != "unlocked" or os.environ.get("BW_SESSION") != "SESSION123":
        sys.stderr.write("Vault is locked.")
        sys.exit(1)
    print("Syncing complete.")
elif cmd == "list":
    if state["status"] != "unlocked":
        sys.stderr.write("Vault is locked.")
        sys.exit(1)
    print(json.dumps(load("items.json", [])) if "raw" not in fail else "not json")
else:
    sys.exit(2)
'''


class FakeBw:
    def __init__(self, path: Path) -> None:
        self.dir = path

    def set_items(self, items: list) -> None:
        (self.dir / "items.json").write_text(json.dumps(items))

    def fail(self, cmd: str, **kw) -> None:
        data = self._read("fail.json", {})
        data[cmd] = kw
        (self.dir / "fail.json").write_text(json.dumps(data))

    def clear_fail(self) -> None:
        (self.dir / "fail.json").unlink(missing_ok=True)

    def expire_once(self) -> None:
        (self.dir / "expire_once").write_text("1")

    def _read(self, name: str, default):
        try:
            return json.loads((self.dir / name).read_text())
        except FileNotFoundError:
            return default

    @property
    def calls(self) -> list:
        return self._read("calls.json", [])

    def cmds(self) -> list[str]:
        return [c["argv"][0] for c in self.calls]


@pytest.fixture
def fake_bw(tmp_path, monkeypatch) -> FakeBw:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = bindir / "bw"
    script.write_text(FAKE_BW.replace("__PY__", sys.executable))
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    state = tmp_path / "fakebw"
    state.mkdir()
    monkeypatch.setenv("PATH", f"{bindir}:/usr/bin:/bin")
    monkeypatch.setenv("FAKE_BW_DIR", str(state))
    monkeypatch.setenv("BW_CLIENTID", "cid")
    monkeypatch.setenv("BW_CLIENTSECRET", "csecret-value")
    monkeypatch.setenv("BW_PASSWORD", "master-pw-value")
    monkeypatch.setenv("BITWARDENCLI_APPDATA_DIR", str(tmp_path / "bwdata"))
    return FakeBw(state)


BW_CFG = {
    "server_url": "https://vault.example.org",
    "client_id": "",
    "client_secret": "",
    "master_password": "",
    "organization_id": "",
    "collection_id": "",
    "key_style": "legacy",
    "notes_dir": "bitwarden",
}


@pytest.fixture
def bw_cfg() -> dict:
    return dict(BW_CFG)
