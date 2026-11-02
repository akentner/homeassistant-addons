"""Tests for internal/sync-admin-ui.py against a fake repository (real lib/skeleton copied into tmp_path)."""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "internal" / "sync-admin-ui.py"
LIB = "admin-ui/app/web/static/lib"
SKELETON = "admin-ui/app/web/skeleton"
LIB_COPY = "app/web/static/vendor/admin-ui"
SKELETON_COPY = "app/web/admin_ui"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")

spec = importlib.util.spec_from_file_location("sync_admin_ui", SCRIPT)
assert spec and spec.loader
sync = importlib.util.module_from_spec(spec)
sys.modules["sync_admin_ui"] = sync
spec.loader.exec_module(sync)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    shutil.copytree(REPO / LIB, tmp_path / LIB, ignore=IGNORE)
    shutil.copytree(REPO / SKELETON, tmp_path / SKELETON, ignore=IGNORE)
    for name in ("fakeaddon", "otheraddon"):
        (tmp_path / name / "app" / "web").mkdir(parents=True)
        (tmp_path / name / "config.yaml").write_text("name: x\n")
        (tmp_path / name / "app" / "__init__.py").write_text("")
        (tmp_path / name / "app" / "web" / "__init__.py").write_text("")
    return tmp_path


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--root", str(repo), *args], capture_output=True, text=True, timeout=60
    )


def bump(repo: Path, version: str) -> None:
    (repo / LIB / "VERSION").write_text(version + "\n")


def test_tree_hash_deterministic_and_sensitive(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    for root, order in ((a, ("x.txt", "y/z.txt")), (b, ("y/z.txt", "x.txt"))):
        for rel in order:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(rel)
    assert sync.tree_hash(a) == sync.tree_hash(b)
    base = sync.tree_hash(a)
    (a / "LIB.stamp").write_text("ignored")
    (a / "__pycache__").mkdir()
    (a / "__pycache__" / "m.pyc").write_bytes(b"1")
    (a / "m.pyc").write_bytes(b"1")
    assert sync.tree_hash(a) == base
    (a / "x.txt").write_text("changed")
    assert sync.tree_hash(a) != base
    (a / "x.txt").write_text("x.txt")
    assert sync.tree_hash(a) == base
    (a / "x.txt").rename(a / "x2.txt")
    assert sync.tree_hash(a) != base
    (a / "x2.txt").rename(a / "x.txt")
    (a / "extra.txt").write_text("")
    assert sync.tree_hash(a) != base


def test_tree_hash_rejects_symlinks(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("x")
    (tmp_path / "link.txt").symlink_to(tmp_path / "f.txt")
    with pytest.raises(sync.SyncError):
        sync.tree_hash(tmp_path)
    other = tmp_path / "d"
    other.mkdir()
    (other / "inner").mkdir()
    (other / "dirlink").symlink_to(other / "inner")
    with pytest.raises(sync.SyncError):
        sync.tree_hash(other)


def test_fresh_sync_creates_copies_stamps_and_lock(repo: Path) -> None:
    result = run(repo, "--addon", "fakeaddon")
    assert result.returncode == 0, result.stderr
    version = (repo / LIB / "VERSION").read_text().strip()
    for part, src in ((LIB_COPY, LIB), (SKELETON_COPY, SKELETON)):
        stamp = (repo / "fakeaddon" / part / "LIB.stamp").read_text()
        assert re.fullmatch(rf"version {re.escape(version)}\nsha256 [0-9a-f]{{64}}\n", stamp)
        assert sync.tree_hash(repo / "fakeaddon" / part) == stamp.split()[-1] == sync.tree_hash(repo / src)
        for path in (repo / src).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                assert (repo / "fakeaddon" / part / path.relative_to(repo / src)).read_bytes() == path.read_bytes()
    assert re.fullmatch(r"version \S+\nlib [0-9a-f]{64}\nskeleton [0-9a-f]{64}\n", (repo / "admin-ui/lib.lock").read_text())
    check = run(repo, "--check")
    assert check.returncode == 0, check.stdout


def test_second_sync_is_idempotent(repo: Path) -> None:
    run(repo, "--addon", "fakeaddon")
    files = sorted(p for p in (repo / "fakeaddon").rglob("*") if p.is_file())
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}
    lock_before = (repo / "admin-ui/lib.lock").read_bytes()
    result = run(repo, "--addon", "fakeaddon")
    assert result.returncode == 0 and "up to date" in result.stdout and "UPDATED" not in result.stdout
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files} == before
    assert (repo / "admin-ui/lib.lock").read_bytes() == lock_before


def test_stale_destination_files_are_removed(repo: Path) -> None:
    run(repo, "--addon", "fakeaddon")
    stale = repo / "fakeaddon" / LIB_COPY / "stale.mjs"
    stale.write_text("x")
    assert run(repo, "--check").returncode == 1
    assert run(repo, "--addon", "fakeaddon").returncode == 0
    assert not stale.exists() and run(repo, "--check").returncode == 0


@pytest.mark.parametrize("kind", ["file", "stamp-hash", "version-file", "skeleton-file", "stamp-garbage"])
def test_tampered_copy_fails(repo: Path, kind: str) -> None:
    run(repo, "--addon", "fakeaddon")
    lib, skel = repo / "fakeaddon" / LIB_COPY, repo / "fakeaddon" / SKELETON_COPY
    if kind == "file":
        target = next(p for p in sorted(lib.glob("*.mjs")))
        target.write_text(target.read_text() + "\n// edit\n")
    elif kind == "stamp-hash":
        stamp = lib / "LIB.stamp"
        stamp.write_text(re.sub(r"sha256 \w{64}", "sha256 " + "0" * 64, stamp.read_text()))
    elif kind == "version-file":
        (lib / "VERSION").write_text("9.9.9\n")
    elif kind == "skeleton-file":
        (skel / "extra.py").write_text("x = 1\n")
    else:
        (lib / "LIB.stamp").write_text("garbage\n")
    result = run(repo, "--check")
    assert result.returncode == 1
    assert "fakeaddon" in result.stdout and "tampered" in result.stdout


def test_source_edit_without_sync_is_stale_lock(repo: Path) -> None:
    run(repo, "--addon", "fakeaddon")
    (repo / LIB / "api.mjs").write_text((repo / LIB / "api.mjs").read_text() + "\n// edit\n")
    result = run(repo, "--check")
    assert result.returncode == 1 and "lock" in result.stdout and "stale" in result.stdout


def test_missing_lock_fails(repo: Path) -> None:
    assert run(repo, "--check").returncode == 1


def test_same_version_different_hash_fails(repo: Path) -> None:
    run(repo, "--addon", "fakeaddon")
    (repo / LIB / "api.mjs").write_text((repo / LIB / "api.mjs").read_text() + "\n// edit\n")
    assert run(repo).returncode == 0  # refresh the lock only
    result = run(repo, "--check")
    assert result.returncode == 1 and "same version" in result.stdout and "different hash" in result.stdout


def test_behind_warns_and_strict_fails(repo: Path) -> None:
    run(repo, "--addon", "fakeaddon")
    bump(repo, "9.9.0")
    assert run(repo).returncode == 0
    warn = run(repo, "--check")
    assert warn.returncode == 0 and "WARN" in warn.stdout and "behind" in warn.stdout
    strict = run(repo, "--check", "--strict")
    assert strict.returncode == 1 and "behind" in strict.stdout
    assert run(repo, "--all").returncode == 0
    assert run(repo, "--check", "--strict").returncode == 0


def test_ahead_fails(repo: Path) -> None:
    bump(repo, "9.9.0")
    run(repo, "--addon", "fakeaddon")
    bump(repo, "0.0.1")
    assert run(repo).returncode == 0
    result = run(repo, "--check")
    assert result.returncode == 1 and "ahead" in result.stdout


def test_consumers_can_differ_and_addon_updates_only_named(repo: Path) -> None:
    run(repo, "--addon", "fakeaddon", "--addon", "otheraddon")
    initial = (repo / LIB / "VERSION").read_text().strip()
    bump(repo, "9.9.0")
    assert run(repo, "--addon", "fakeaddon").returncode == 0
    assert "version 9.9.0" in (repo / "fakeaddon" / LIB_COPY / "LIB.stamp").read_text()
    assert f"version {initial}" in (repo / "otheraddon" / LIB_COPY / "LIB.stamp").read_text()
    result = run(repo, "--check")
    assert result.returncode == 0 and "otheraddon" in result.stdout and "behind" in result.stdout


@pytest.mark.parametrize("name", ["../x", "admin-ui", "Foo", "ghost", "noconfig", "a/b", ".hidden"])
def test_unsafe_names_exit_2_and_write_nothing(repo: Path, name: str) -> None:
    (repo / "noconfig").mkdir()
    result = run(repo, "--addon", name)
    assert result.returncode == 2
    assert not (repo / "admin-ui/lib.lock").exists()
    assert not list(repo.rglob("LIB.stamp"))


def test_one_bad_name_blocks_all_writes(repo: Path) -> None:
    assert run(repo, "--addon", "fakeaddon", "--addon", "Bad").returncode == 2
    assert not list(repo.rglob("LIB.stamp")) and not (repo / "admin-ui/lib.lock").exists()


def test_check_with_addon_or_all_is_usage_error(repo: Path) -> None:
    assert run(repo, "--check", "--addon", "fakeaddon").returncode == 2
    assert run(repo, "--check", "--all").returncode == 2
    assert run(repo, "--strict").returncode == 2


def test_symlink_in_source_is_refused(repo: Path) -> None:
    (repo / LIB / "link.mjs").symlink_to(repo / LIB / "api.mjs")
    assert run(repo, "--addon", "fakeaddon").returncode == 2
    assert not (repo / "fakeaddon" / LIB_COPY).exists()


def test_symlink_in_destination_is_refused(repo: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    run(repo, "--addon", "fakeaddon")
    outside = tmp_path_factory.mktemp("outside")
    (outside / "secret.txt").write_text("x")
    (repo / "fakeaddon" / LIB_COPY / "leak").symlink_to(outside)
    assert run(repo, "--addon", "fakeaddon").returncode == 2
    assert (outside / "secret.txt").exists()
    assert run(repo, "--check").returncode == 2


# --- fake-consumer proof of the copy path (PD-02, PD-10) ---------------------------------------------------------

SPECIFIER = re.compile(r"""(?:from\s+|import\s*\(?\s*)["'](\.{1,2}/[^"']+)["']""")


def test_copied_lib_is_self_contained(repo: Path) -> None:
    run(repo, "--addon", "fakeaddon")
    lib = (repo / "fakeaddon" / LIB_COPY).resolve()
    modules = list(lib.rglob("*.mjs"))
    assert modules
    for module in modules:
        for spec_ in SPECIFIER.findall(module.read_text(encoding="utf-8")):
            target = (module.parent / spec_).resolve()
            assert target.is_file(), f"{module.name} imports missing {spec_}"
            target.relative_to(lib)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_copied_modules_import_under_node(repo: Path) -> None:
    run(repo, "--addon", "fakeaddon")
    lib = repo / "fakeaddon" / LIB_COPY
    script = (
        "const [a, b] = process.argv.slice(1);"
        "Promise.all([import(a), import(b)]).then(([x, y]) => {"
        " if (typeof x.get !== 'function' && Object.keys(x).length === 0) process.exit(3);"
        " if (typeof y.html !== 'function') process.exit(4); process.exit(0); })"
        ".catch(e => { console.error(e); process.exit(5); });"
    )
    result = subprocess.run(
        ["node", "-e", script, (lib / "api.mjs").as_uri(), (lib / "vendor/preact-htm.mjs").as_uri()],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_copied_skeleton_imports_as_consumer_package(repo: Path) -> None:
    run(repo, "--addon", "fakeaddon")
    code = (
        "import sys, threading, http.client, tempfile\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from app.web.admin_ui import Router, StaticFiles, make_server, ApiError\n"
        "r = Router(); r.add('GET', '/api/x', lambda req: {'ok': True})\n"
        "srv = make_server(r, StaticFiles(tempfile.mkdtemp()), 0, host='127.0.0.1')\n"
        "threading.Thread(target=srv.serve_forever, daemon=True).start()\n"
        "c = http.client.HTTPConnection('127.0.0.1', srv.server_address[1], timeout=5)\n"
        "c.request('GET', '/api/x'); print(c.getresponse().status); srv.shutdown(); srv.server_close()\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(repo / "fakeaddon")], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "403"
