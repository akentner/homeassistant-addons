"""Manifest rules of the management page: ingress keys, the gui and fetchlog s6 services, the appended access-log
lines of the lighttpd config, import and environment hygiene, the BUILD_VERSION block of the Dockerfile (D-02, D-03,
D-06, D-07, D-19, D-20, D-22, D-24, D-30)."""

from __future__ import annotations

import ast
import os
from pathlib import Path

import yaml

from app.web import service

ADDON_DIR = Path(__file__).resolve().parent.parent
APP = ADDON_DIR / "app"
GUI_SVC = ADDON_DIR / "rootfs/etc/s6-overlay/s6-rc.d/gui"
BUNDLE = ADDON_DIR / "rootfs/etc/s6-overlay/user-bundles.d/user/contents.d/gui"
FETCHLOG_SVC = ADDON_DIR / "rootfs/etc/s6-overlay/s6-rc.d/fetchlog"
FETCHLOG_BUNDLE = ADDON_DIR / "rootfs/etc/s6-overlay/user-bundles.d/user/contents.d/fetchlog"
LIGHTTPD_CONF = ADDON_DIR / "rootfs/etc/lighttpd/marketplace-repo-proxy.conf"
ACCESSLOG_LINES = [
    'server.modules += ("mod_accesslog")',
    'accesslog.filename = "|exec /usr/bin/python3 -I /opt/marketplace-repo-proxy/app/fetchsink.py"',
    'accesslog.format = "%m %U %>s"',
]
VERSION_PATH = "/opt/marketplace-repo-proxy/BUILD_VERSION"


class _Loader(yaml.SafeLoader):
    pass


_Loader.add_multi_constructor("!", lambda loader, suffix, node: None)


def load_yaml(path: Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)


def test_config_ingress_and_ports() -> None:
    config = load_yaml(ADDON_DIR / "config.yaml")
    assert config["ingress"] is True
    assert config["ingress_port"] == 8099
    assert set(config["ports"]) == {"8080/tcp"}


def test_gui_service_files() -> None:
    assert (GUI_SVC / "type").read_text(encoding="utf-8").strip() == "longrun"
    run = (GUI_SVC / "run").read_text(encoding="utf-8").splitlines()
    assert run[0] == "#!/bin/sh"
    assert any("python3 -m app.gui" in line for line in run)
    code = [line for line in run[1:] if not line.lstrip().startswith("#")]
    assert not any("with-contenv" in line for line in code)
    for name in ("run", "finish"):
        assert os.access(GUI_SVC / name, os.X_OK), name
    for marker in (GUI_SVC / "dependencies.d/init", BUNDLE):
        assert marker.is_file() and marker.stat().st_size == 0, marker


def _lighttpd_lines() -> list[str]:
    return LIGHTTPD_CONF.read_text(encoding="utf-8").splitlines()


def test_lighttpd_access_log_goes_only_into_the_fetch_sink() -> None:
    lines = _lighttpd_lines()
    code = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
    assert code[-3:] == ACCESSLOG_LINES
    assert lines[-4].startswith("# ") and "fetch sink" in lines[-4]
    assert lines.count('server.breakagelog = "/dev/null"') == 1
    # the Phase 1 module line stays untouched; the access-log module is added with +=
    assert lines.count('server.modules = ("mod_rewrite", "mod_alias", "mod_setenv", "mod_cgi")') == 1
    assert sum("accesslog.filename" in line for line in code) == 1


def test_lighttpd_access_log_format_has_no_query_request_line_client_or_header() -> None:
    for line in _lighttpd_lines():
        for placeholder in ("%r", "%q", "%h", "%{"):
            assert placeholder not in line, (placeholder, line)


def test_fetchlog_service_files() -> None:
    assert (FETCHLOG_SVC / "type").read_text(encoding="utf-8").strip() == "longrun"
    run = (FETCHLOG_SVC / "run").read_text(encoding="utf-8").splitlines()
    assert run[0] == "#!/bin/sh"
    assert any("python3 -m app.fetchlog" in line for line in run)
    code = [line for line in run[1:] if not line.lstrip().startswith("#")]
    assert not any("with-contenv" in line for line in code)
    for name in ("run", "finish"):
        assert os.access(FETCHLOG_SVC / name, os.X_OK), name
    finish = (FETCHLOG_SVC / "finish").read_text(encoding="utf-8").splitlines()
    assert finish[0] == "#!/bin/sh" and "sleep 3" in finish
    for marker in (FETCHLOG_SVC / "dependencies.d/init", FETCHLOG_BUNDLE):
        assert marker.is_file() and marker.stat().st_size == 0, marker


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_registration_imports_only_app_paths() -> None:
    app_imports = [name for name in _imports(APP / "web/registration.py") if name.split(".")[0] == "app"]
    assert app_imports == ["app.paths"]


def test_gui_modules_never_read_the_environment() -> None:
    for rel in ("gui.py", "web/service.py", "web/server.py"):
        tree = ast.parse((APP / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "os":
                assert node.attr not in ("environ", "getenv", "environb"), rel
            if isinstance(node, ast.ImportFrom) and node.module == "os":
                assert not {a.name for a in node.names} & {"environ", "getenv", "environb"}, rel


def test_dockerfile_build_version_block() -> None:
    lines = (ADDON_DIR / "Dockerfile").read_text(encoding="utf-8").splitlines()
    args = [i for i, line in enumerate(lines) if line.strip() == "ARG BUILD_VERSION"]
    assert len(args) == 1
    assert not any(line.strip().startswith("ARG BUILD_VERSION=") for line in lines)
    last_copy = max(i for i, line in enumerate(lines) if line.startswith("COPY "))
    assert args[0] > last_copy
    writes = [
        line for line in lines[args[0] + 1 :] if line.startswith("RUN ") and "${BUILD_VERSION}" in line
        and VERSION_PATH in line
    ]
    assert len(writes) == 1
    text = "\n".join(lines)
    config_version = str(load_yaml(ADDON_DIR / "config.yaml")["version"])
    build_version = str(load_yaml(ADDON_DIR / "build.yaml")["args"]["VERSION"])
    assert config_version not in text
    assert build_version not in text
    assert str(service.VERSION_FILE) == VERSION_PATH
