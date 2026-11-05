"""GET /api/overview behind the ingress gate: shape, degradation, strict slugs, error codes, no key leak."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

import pytest

from app.web.admin_ui import ERROR_STATUS
from app.web.server import Sources, build_router, make_server
from conftest import INGRESS, REAL_STATUS_SH, _ts, write_hosts, write_log

KEYS = {"slug", "name", "host", "status", "error", "incidents"}


def sources(env: dict[str, Path]) -> Sources:
    return Sources(env["hosts_file"], env["logdir"], env["status_sh"], env["env_file"])


def start(serve: Any, env: dict[str, Path], status_sh: Path | None = None) -> Any:
    src = sources(env)
    if status_sh is not None:
        src = Sources(src.hosts_file, src.logdir, status_sh, src.env_file)
    return serve(make_server(src, 0, host="127.0.0.1", ingress_remote="127.0.0.1"))


def overview(client: Any) -> tuple[int, Any]:
    status, _resp, body = client.call("GET", "/api/overview", INGRESS)
    return status, json.loads(body)


def two_hosts(env: dict[str, Path]) -> None:
    write_hosts(
        env["hosts_file"],
        [
            "good\tGood\t192.0.2.1\t22222\tSHA256:goodfp\tED25519",
            "stale\tStale\t192.0.2.2\t22222\tinvalid\t",
        ],
    )
    write_log(env["logdir"], "good", incidents=[f"start GOODMARK {i}" for i in range(12)])
    write_log(env["logdir"], "stale", age=900, incidents=["start STALEMARK"])


def test_two_hosts_in_file_order_with_own_incidents(serve: Any, env: dict[str, Path]) -> None:
    two_hosts(env)
    status, data = overview(start(serve, env))
    assert status == 200
    assert [h["slug"] for h in data["hosts"]] == ["good", "stale"]
    good, stale = data["hosts"]
    assert set(good) == KEYS and set(stale) == KEYS
    assert good["status"]["problem"] == 0 and good["status"]["key_fp"] == "SHA256:goodfp"
    assert stale["status"]["problem"] == 1 and stale["status"]["r_age"] == 1
    assert stale["status"]["key_fp"] == "invalid"
    assert len(good["incidents"]) == 10
    assert all("GOODMARK" in line for line in good["incidents"])
    assert good["incidents"][-1].endswith("GOODMARK 11")
    assert [line.split(" INCIDENT ")[1] for line in stale["incidents"]] == ["start STALEMARK"]


def test_failing_status_script_degrades_one_host_only(serve: Any, env: dict[str, Path], tmp_path: Path) -> None:
    two_hosts(env)
    wrapper = tmp_path / "wrap.sh"
    wrapper.write_text(f'#!/bin/sh\n[ "$1" = stale ] && exit 1\nexec "{REAL_STATUS_SH}" "$1"\n')
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    status, data = overview(start(serve, env, wrapper))
    assert status == 200
    good, stale = data["hosts"]
    assert good["error"] is None and good["status"]["problem"] == 0
    assert stale["status"] is None and stale["error"] == "status_failed"
    assert stale["incidents"] and "STALEMARK" in stale["incidents"][0]


def test_missing_log_gives_no_incidents(serve: Any, env: dict[str, Path]) -> None:
    (env["logdir"] / "ha_backup.log").unlink()
    status, data = overview(start(serve, env))
    assert status == 200 and data["hosts"][0]["incidents"] == []


def test_hostile_slug_line_is_not_listed_or_touched(serve: Any, env: dict[str, Path], tmp_path: Path) -> None:
    marker = tmp_path / "touched"
    write_hosts(
        env["hosts_file"],
        [f"x;touch {marker}\tevil\t1.1.1.1", "../up\tevil\t1.1.1.1", "ha_backup\tha-backup\t192.0.2.9"],
    )
    status, data = overview(start(serve, env))
    assert status == 200 and [h["slug"] for h in data["hosts"]] == ["ha_backup"]
    assert not marker.exists()


def test_unreadable_hosts_file_is_a_stable_503(serve: Any, env: dict[str, Path], tmp_path: Path) -> None:
    secret_dir = tmp_path / "secret-location"
    src = Sources(secret_dir / "hosts", env["logdir"], env["status_sh"], env["env_file"])
    client = serve(make_server(src, 0, host="127.0.0.1", ingress_remote="127.0.0.1"))
    status, _resp, body = client.call("GET", "/api/overview", INGRESS)
    assert status == 503
    data = json.loads(body)
    assert data["error"] == "hosts_unavailable"
    assert "secret-location" not in body.decode()
    assert ERROR_STATUS["hosts_unavailable"] == 503


def test_empty_hosts_file_is_an_empty_list(serve: Any, env: dict[str, Path]) -> None:
    env["hosts_file"].write_text("")
    status, data = overview(start(serve, env))
    assert status == 200 and data["hosts"] == []


def test_hostile_content_is_json_text(serve: Any, env: dict[str, Path]) -> None:
    write_hosts(env["hosts_file"], ["ha_backup\t<b>x</b>\t192.0.2.9"])
    write_log(env["logdir"], "ha_backup", incidents=["start <script>alert(1)</script>"])
    _status, data = overview(start(serve, env))
    assert data["hosts"][0]["name"] == "<b>x</b>"
    assert "<script>alert(1)</script>" in data["hosts"][0]["incidents"][0]


def test_no_key_material_in_any_response(serve: Any, env: dict[str, Path], tmp_path: Path) -> None:
    sentinel = "SENTINEL-KEY-BODY-do-not-leak"
    (tmp_path / "monitor_key_ha_backup").write_text(sentinel)
    (tmp_path / "options.json").write_text(json.dumps({"hosts": [{"ssh_private_key": sentinel, "name": "x"}]}))
    client = start(serve, env)
    status, _resp, body = client.call("GET", "/api/overview", INGRESS)
    assert status == 200 and sentinel.encode() not in body
    data = json.loads(body)
    assert set(data) == {"now_ms", "hosts"} and set(data["hosts"][0]) == KEYS
    assert "ssh_private_key" not in body.decode() and "comment" not in body.decode()
    for path in ("/", "/static/vendor/admin-ui/base.css"):
        _s, _r, page = client.call("GET", path, INGRESS)
        assert sentinel.encode() not in page


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "HEAD"])
def test_other_methods_are_405(serve: Any, env: dict[str, Path], method: str) -> None:
    status, _resp, body = start(serve, env).call(method, "/api/overview", INGRESS)
    assert status == 405
    if method != "HEAD":
        assert json.loads(body)["error"] == "method_not_allowed"


def test_unknown_path_is_404(serve: Any, env: dict[str, Path]) -> None:
    status, _resp, body = start(serve, env).call("GET", "/api/nope", INGRESS)
    assert status == 404 and json.loads(body)["error"] == "not_found"


def test_query_parameters_are_ignored(serve: Any, env: dict[str, Path], tmp_path: Path) -> None:
    client = start(serve, env)
    _s, _r, plain = client.call("GET", "/api/overview", INGRESS)
    _s, _r, noisy = client.call("GET", "/api/overview?host=../../etc/passwd&slug=x", INGRESS)
    assert [h["slug"] for h in json.loads(noisy)["hosts"]] == ["ha_backup"]
    assert json.loads(plain)["hosts"][0]["slug"] == "ha_backup"


def test_router_lists_exactly_one_gated_route(env: dict[str, Path]) -> None:
    router = build_router(sources(env))
    assert router.routes() == [("GET", "/api/overview")]
    assert router.is_public("GET", "/api/overview") is False


@pytest.mark.parametrize("path", ["/api/overview", "//api/overview", "/api/overview/", "/api/%6Fverview"])
@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"])
def test_nothing_succeeds_without_ingress(serve: Any, env: dict[str, Path], method: str, path: str) -> None:
    status, _resp, _body = start(serve, env).call(method, path)
    assert status == 403


def test_now_ms_comes_from_the_server_clock(env: dict[str, Path]) -> None:
    from app.web.admin_ui import Request

    router = build_router(sources(env), clock=lambda: 1234.5)
    handler, _params = router.match("GET", "/api/overview")
    result = handler(Request(method="GET", path="/api/overview"))
    assert result["now_ms"] == 1234500


def test_overview_passes_syncing_through(serve: Any, env: dict[str, Path]) -> None:
    two_hosts(env)
    with (env["logdir"] / "stale.log.state").open("a", encoding="utf-8") as fh:
        fh.write(f"{_ts(800)} SYNC start\n")
    _status, data = overview(start(serve, env))
    good, stale = data["hosts"]
    assert good["status"]["syncing"] is False
    assert stale["status"]["syncing"] is False  # the start marker is older than ten minutes: normal verdict
    assert stale["status"]["problem"] == 1
    with (env["logdir"] / "good.log.state").open("a", encoding="utf-8") as fh:
        fh.write(f"{_ts(10)} SYNC start\n")
    _status, data = overview(start(serve, env))
    assert data["hosts"][0]["status"]["syncing"] is True and data["hosts"][0]["status"]["problem"] == 0


def test_addon_slug_and_version_are_added_when_known(serve: Any, env: dict[str, Path]) -> None:
    two_hosts(env)
    info = {"slug": "a1b2c3d4_haos_monitor", "version": "0.7.3-0"}
    client = serve(make_server(sources(env), 0, host="127.0.0.1", ingress_remote="127.0.0.1", addon_info=lambda: info))
    status, data = overview(client)
    assert status == 200
    assert (data["addon_slug"], data["addon_version"]) == ("a1b2c3d4_haos_monitor", "0.7.3-0")


def test_addon_keys_are_absent_when_unknown(serve: Any, env: dict[str, Path]) -> None:
    two_hosts(env)
    _status, data = overview(start(serve, env))
    assert set(data) == {"now_ms", "hosts"}
