from __future__ import annotations

import os
import stat

import pytest
import yaml

from app.engine import writer
from app.engine.writer import UnsafePathError, WriteError, safe_relpath, write_files, write_secrets

NASTY = {
    "quote": 'he said "hi" and \'bye\'',
    "newline": "line1\nline2\r\nline3\ttab",
    "colon": "a: b # not a comment",
    "unicode": "äöü € 日本語 😀",
    "special_breaks": "a\u2028b\u2029c\x85d\x7fe",
    "yamlish": "- [x] {y: z} !!python/object &a *a | > %",
    "numeric": "0123",
    "bool": "yes",
    "null": "null",
    "empty": "",
    "backslash": "C:\\dir\\file \\n",
    "yes": "key looks like a bool",
    "123": "numeric key",
}


def test_escaping_roundtrip(tmp_path):
    target = tmp_path / "secrets.yaml"
    assert write_secrets(target, NASTY) is True
    assert yaml.safe_load(target.read_text(encoding="utf-8")) == NASTY
    assert target.read_text().startswith("# managed by Secrets Sync - do not edit\n")


def test_sorted_keys_and_mode(tmp_path):
    target = tmp_path / "secrets.yaml"
    write_secrets(target, {"b": "2", "a": "1"})
    lines = target.read_text().splitlines()[1:]
    assert lines == ['"a": "1"', '"b": "2"']
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_identical_content_skips_write_and_fixes_mode(tmp_path):
    target = tmp_path / "secrets.yaml"
    write_secrets(target, {"a": "1"})
    target.chmod(0o644)
    assert write_secrets(target, {"a": "1"}) is False
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert not (tmp_path / "secrets.yaml.bak").exists()


def test_backup_of_previous(tmp_path):
    target = tmp_path / "secrets.yaml"
    write_secrets(target, {"a": "1"})
    old = target.read_bytes()
    write_secrets(target, {"a": "2"})
    bak = tmp_path / "secrets.yaml.bak"
    assert bak.read_bytes() == old
    assert stat.S_IMODE(bak.stat().st_mode) == 0o600


def test_atomic_failure_keeps_old_file(tmp_path, monkeypatch):
    target = tmp_path / "secrets.yaml"
    write_secrets(target, {"a": "1"})
    old = target.read_bytes()

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(writer.os, "replace", boom)
    with pytest.raises(WriteError) as exc:
        write_secrets(target, {"a": "2"})
    assert exc.value.code == "write_failed"
    assert target.read_bytes() == old
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []


def test_verify_failure_never_touches_target(tmp_path, monkeypatch):
    target = tmp_path / "secrets.yaml"
    write_secrets(target, {"a": "1"})
    old = target.read_bytes()
    monkeypatch.setattr(writer, "render_secrets", lambda s: "a: [broken\n")
    with pytest.raises(WriteError) as exc:
        write_secrets(target, {"a": "2"})
    assert exc.value.code == "yaml_verify_failed"
    assert target.read_bytes() == old


def test_lone_surrogate_rejected(tmp_path):
    with pytest.raises(WriteError):
        write_secrets(tmp_path / "s.yaml", {"a": "\ud800"})
    assert not (tmp_path / "s.yaml").exists()


def test_symlink_target_refused(tmp_path):
    real = tmp_path / "real"
    real.write_text("x")
    link = tmp_path / "secrets.yaml"
    link.symlink_to(real)
    with pytest.raises(WriteError):
        write_secrets(link, {"a": "1"})
    assert real.read_text() == "x"


@pytest.mark.parametrize("rel", ["", "/etc/passwd", "../x", "a/../b", "a/..", "a\\b", "a//b", "./a", "a/./b", "a\0b"])
def test_unsafe_paths_rejected(rel):
    with pytest.raises(UnsafePathError):
        safe_relpath(rel)


def test_safe_path_ok():
    assert safe_relpath("bitwarden/a b.txt") == ("bitwarden", "a b.txt")


def test_write_files_manifest_and_cleanup(tmp_path):
    base, manifest = tmp_path / "files", tmp_path / "data" / "files.manifest.json"
    res = write_files(base, manifest, {"bw/a.txt": b"A", "bw/sub/b.txt": b"B"})
    assert sorted(res.written) == ["bw/a.txt", "bw/sub/b.txt"]
    assert stat.S_IMODE((base / "bw/a.txt").stat().st_mode) == 0o600
    (base / "unknown.txt").write_text("mine")
    res = write_files(base, manifest, {"bw/a.txt": b"A"})
    assert res.written == [] and res.removed == ["bw/sub/b.txt"]
    assert not (base / "bw/sub").exists()
    assert (base / "unknown.txt").read_text() == "mine"


def test_write_files_unmanaged_existing_not_overwritten(tmp_path):
    base, manifest = tmp_path / "files", tmp_path / "files.manifest.json"
    base.mkdir()
    (base / "a.txt").write_text("user content")
    res = write_files(base, manifest, {"a.txt": b"managed"})
    assert res.skipped == ["a.txt"]
    assert (base / "a.txt").read_text() == "user content"


def test_write_files_refuses_symlink_components(tmp_path):
    base = tmp_path / "files"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (base / "dir").symlink_to(outside)
    with pytest.raises(UnsafePathError):
        write_files(base, tmp_path / "m.json", {"dir/x.txt": b"x"})
    assert list(outside.iterdir()) == []
    (base / "dir").unlink()
    (base / "link.txt").symlink_to(outside / "t.txt")
    with pytest.raises(UnsafePathError):
        write_files(base, tmp_path / "m.json", {"link.txt": b"x"})
    assert not (outside / "t.txt").exists()


def test_write_files_traversal_rejected(tmp_path):
    with pytest.raises(UnsafePathError):
        write_files(tmp_path / "files", tmp_path / "m.json", {"../evil": b"x"})
    assert not (tmp_path / "evil").exists()


def test_tampered_manifest_never_deletes_outside(tmp_path):
    base = tmp_path / "files"
    base.mkdir()
    victim = tmp_path / "victim.txt"
    victim.write_text("keep")
    manifest = tmp_path / "m.json"
    manifest.write_text('{"version": 1, "files": {"../victim.txt": "x"}}')
    write_files(base, manifest, {})
    assert victim.read_text() == "keep"


def test_corrupt_manifest_is_ignored(tmp_path):
    base, manifest = tmp_path / "files", tmp_path / "m.json"
    manifest.write_text("{not json")
    res = write_files(base, manifest, {"a.txt": b"A"})
    assert res.written == ["a.txt"]
    assert os.path.exists(manifest)
