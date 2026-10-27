from __future__ import annotations

import pytest

from app.providers.base import ProviderError
from app.providers.bitwarden import Provider, sanitise

ITEMS = [
    {"type": 1, "name": "MQTT Broker: main-1", "revisionDate": "2026-10-01T10:00:00Z",
     "notes": "login note",
     "login": {"username": "mqtt-user", "password": "s3cr3t", "uris": [{"uri": "mqtt://a"}, {"uri": "mqtt://b"}]},
     "fields": [{"name": "API Key", "value": "key-123", "type": 1}, {"name": "empty", "value": ""}]},
    {"type": 2, "name": "ssh [deploy] key", "notes": "-----BEGIN KEY-----\nabc\n",
     "revisionDate": "2026-10-02T10:00:00Z"},
    {"type": 2, "name": "cert.pem", "notes": "pem-content"},
    {"type": 2, "name": "empty note", "notes": ""},
    {"type": 3, "name": "card"},
    {"type": 4, "name": "identity"},
]


def test_sanitise_legacy():
    assert sanitise("MQTT Broker: main-1") == "mqtt_broker_main_1"
    assert sanitise("a [b]{c}#d*e!f|g>h") == "a_b_c_d_e_f_g_h"
    assert sanitise("x?y&z,u%v@w") == "x_y_z_u_v_w"
    assert sanitise("__a   b__") == "_a_b_"


def test_fetch_maps_items(fake_bw, bw_cfg):
    fake_bw.set_items(ITEMS)
    provider = Provider(bw_cfg)
    snap = provider.fetch()
    assert snap.secrets == {
        "mqtt_broker_main_1_username": "mqtt-user",
        "mqtt_broker_main_1_password": "s3cr3t",
        "mqtt_broker_main_1_notes": "login note",
        "mqtt_broker_main_1_uri_1": "mqtt://a",
        "mqtt_broker_main_1_uri_2": "mqtt://b",
        "mqtt_broker_main_1_api_key": "key-123",
    }
    assert set(snap.files) == {"bitwarden/ssh_deploy_key.txt", "bitwarden/cert.pem"}
    assert snap.files["bitwarden/cert.pem"] == b"pem-content"
    assert snap.revision == "2026-10-02T10:00:00Z"
    assert provider.notices == [("info", "item_skipped", "2 card/identity items skipped")]


def test_auth_flow_and_no_secrets_in_argv(fake_bw, bw_cfg):
    fake_bw.set_items([])
    Provider(bw_cfg).fetch()
    assert fake_bw.cmds() == ["status", "config", "status"][:1] + ["config", "login", "unlock", "sync", "list"]
    joined = " ".join(" ".join(c["argv"]) for c in fake_bw.calls)
    for value in ("csecret-value", "master-pw-value", "cid", "SESSION123"):
        assert value not in joined
    unlock = next(c for c in fake_bw.calls if c["argv"][0] == "unlock")
    assert unlock["argv"] == ["unlock", "--passwordenv", "BW_PASSWORD", "--raw"]
    assert next(c for c in fake_bw.calls if c["argv"][0] == "sync")["session_ok"]


def test_second_fetch_reuses_session(fake_bw, bw_cfg):
    fake_bw.set_items([])
    provider = Provider(bw_cfg)
    provider.fetch()
    before = len(fake_bw.calls)
    provider.fetch()
    assert fake_bw.cmds()[before:] == ["status", "sync", "list"]


def test_server_change_relogs(fake_bw, bw_cfg):
    fake_bw.set_items([])
    Provider(bw_cfg).fetch()
    bw_cfg["server_url"] = "https://other.example.org/"
    Provider(bw_cfg).fetch()
    cmds = fake_bw.cmds()
    assert "logout" in cmds
    assert [c["argv"] for c in fake_bw.calls if c["argv"][0] == "config"][-1] == [
        "config", "server", "https://other.example.org"]


def test_org_and_collection_filters(fake_bw, bw_cfg):
    fake_bw.set_items([])
    bw_cfg.update(organization_id="org1", collection_id="col1")
    Provider(bw_cfg).fetch()
    listed = next(c for c in fake_bw.calls if c["argv"][0] == "list")
    assert listed["argv"] == ["list", "items", "--organizationid", "org1", "--collectionid", "col1"]


def test_reauth_on_expired_session(fake_bw, bw_cfg):
    fake_bw.set_items(ITEMS)
    provider = Provider(bw_cfg)
    provider.fetch()
    fake_bw.expire_once()
    snap = provider.fetch()
    assert snap.secrets
    assert fake_bw.cmds().count("unlock") == 2


@pytest.mark.parametrize("cmd,code", [("login", "bw_auth_failed"), ("unlock", "bw_unlock_failed"),
                                      ("sync", "bw_sync_failed"), ("list", "bw_list_failed")])
def test_error_codes_and_stderr_not_forwarded(fake_bw, bw_cfg, cmd, code):
    fake_bw.set_items([])
    fake_bw.fail(cmd, code=1, stderr="boom csecret-value master-pw-value")
    with pytest.raises(ProviderError) as exc:
        Provider(bw_cfg).fetch()
    assert exc.value.code == code
    assert "csecret-value" not in str(exc.value) and "master-pw-value" not in str(exc.value)


def test_login_failure_names_server_but_no_secrets(fake_bw, bw_cfg):
    fake_bw.set_items([])
    fake_bw.fail("login", code=1, stderr="client_id or client_secret is incorrect csecret-value")
    with pytest.raises(ProviderError) as exc:
        Provider(bw_cfg).fetch()
    assert exc.value.code == "bw_auth_failed"
    assert str(bw_cfg["server_url"]) in str(exc.value) and "server_url" in str(exc.value)
    assert "csecret-value" not in str(exc.value)


def test_wrong_credentials(fake_bw, bw_cfg, monkeypatch):
    monkeypatch.setenv("BW_PASSWORD", "nope")
    with pytest.raises(ProviderError) as exc:
        Provider(bw_cfg).fetch()
    assert exc.value.code == "bw_unlock_failed"


def test_timeout(fake_bw, bw_cfg):
    fake_bw.set_items([])
    fake_bw.fail("sync", sleep=5)
    with pytest.raises(ProviderError) as exc:
        Provider(bw_cfg, timeout=1).fetch()
    assert exc.value.code == "bw_timeout"


def test_invalid_json(fake_bw, bw_cfg):
    fake_bw.fail("raw")
    fake_bw.set_items([])
    with pytest.raises(ProviderError) as exc:
        Provider(bw_cfg).fetch()
    assert exc.value.code == "bw_invalid_json"


def test_missing_binary(bw_cfg, monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(ProviderError) as exc:
        Provider(bw_cfg).fetch()
    assert exc.value.code == "bw_not_found"


def test_key_collision_names_items_not_values(fake_bw, bw_cfg):
    fake_bw.set_items([
        {"type": 1, "name": "a b", "login": {"password": "value-one"}},
        {"type": 1, "name": "a-b", "login": {"password": "value-two"}},
    ])
    with pytest.raises(ProviderError) as exc:
        Provider(bw_cfg).fetch()
    assert exc.value.code == "key_collision"
    assert "a_b_password" in str(exc.value) and "value-" not in str(exc.value)


def test_note_file_collision(fake_bw, bw_cfg):
    fake_bw.set_items([{"type": 2, "name": "n 1", "notes": "x"}, {"type": 2, "name": "n-1", "notes": "y"}])
    with pytest.raises(ProviderError) as exc:
        Provider(bw_cfg).fetch()
    assert exc.value.code == "key_collision"


def test_note_name_cannot_escape_dir(fake_bw, bw_cfg):
    fake_bw.set_items([{"type": 2, "name": "../../etc/passwd", "notes": "x"}])
    snap = Provider(bw_cfg).fetch()
    (path,) = snap.files
    assert path.startswith("bitwarden/") and ".." not in path.split("/") and path.count("/") == 1


def test_validate(bw_cfg, monkeypatch):
    for name in ("BW_CLIENTID", "BW_CLIENTSECRET", "BW_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    codes = {p.code for p in Provider(bw_cfg).validate(bw_cfg)}
    assert codes == {"bw_missing_client_id", "bw_missing_client_secret", "bw_missing_master_password"}
    monkeypatch.setenv("BW_CLIENTID", "x")
    monkeypatch.setenv("BW_CLIENTSECRET", "x")
    monkeypatch.setenv("BW_PASSWORD", "x")
    assert Provider(bw_cfg).validate(bw_cfg) == []
    bad = dict(bw_cfg, server_url="ftp://x", notes_dir="../x", key_style="new")
    assert {p.code for p in Provider(bad).validate(bad)} == {
        "bw_invalid_server_url", "bw_invalid_notes_dir", "bw_unsupported_key_style"}
