"""Strict hosts file reader: valid lines load, hostile or malformed ones are skipped, never raised."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.hosts import HostsUnavailable, load_hosts, valid_slug


def write(path: Path, content: bytes | str) -> Path:
    path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    return path


def test_valid_lines_of_every_width_load(tmp_path: Path) -> None:
    f = write(
        tmp_path / "h",
        "a\tHost A\t192.0.2.1\t22222\tSHA256:xyz\tED25519\nb\tHost B\t192.0.2.2\t22\n\tskip\n"
        "c\tHost C\t192.0.2.3\n",
    )
    hosts = load_hosts(f)
    assert [tuple(h) for h in hosts] == [
        ("a", "Host A", "192.0.2.1"),
        ("b", "Host B", "192.0.2.2"),
        ("c", "Host C", "192.0.2.3"),
    ]
    assert all(len(h) == 3 for h in hosts)  # the fingerprint columns are never parsed here


HOSTILE = [
    "",
    "A",
    "a b",
    "a.b",
    "a/b",
    "a;id",
    "a$b",
    "a`b`",
    "a\n",
    "a\r",
    "ä",
    "../etc/passwd",
    "a" * 129,
]


@pytest.mark.parametrize("slug", HOSTILE)
def test_hostile_slugs_are_skipped(tmp_path: Path, slug: str) -> None:
    assert not valid_slug(slug)
    f = write(tmp_path / "h", f"{slug}\tname\thost\nok\tn\th\n")
    assert [h.slug for h in load_hosts(f)] == ["ok"]


def test_slug_length_limit_is_inclusive() -> None:
    assert valid_slug("a" * 128)
    assert not valid_slug("a" * 129)
    assert not valid_slug(None)


def test_short_and_blank_lines_are_skipped(tmp_path: Path) -> None:
    f = write(tmp_path / "h", "\n\none\ntwo\tname\n  \n\nok\tn\th\n")
    assert [h.slug for h in load_hosts(f)] == ["ok"]


def test_duplicate_slug_keeps_the_first(tmp_path: Path) -> None:
    f = write(tmp_path / "h", "a\tfirst\th1\na\tsecond\th2\nb\tx\ty\n")
    assert [(h.slug, h.name) for h in load_hosts(f)] == [("a", "first"), ("b", "x")]


def test_control_characters_are_removed_and_lengths_capped(tmp_path: Path) -> None:
    f = write(tmp_path / "h", "a\tna\x07m\x1be\th\x00o\x7fst\nb\t" + "n" * 300 + "\t" + "h" * 400 + "\nc\t\tx\n")
    hosts = load_hosts(f)
    assert (hosts[0].name, hosts[0].host) == ("name", "host")
    assert len(hosts[1].name) == 200 and len(hosts[1].host) == 255
    assert hosts[2].name == "c"  # an empty name falls back to the slug


def test_crlf_line_endings_are_tolerated(tmp_path: Path) -> None:
    f = write(tmp_path / "h", "a\tname\thost\r\n")
    assert [tuple(h) for h in load_hosts(f)] == [("a", "name", "host")]


def test_invalid_utf8_does_not_raise(tmp_path: Path) -> None:
    f = write(tmp_path / "h", b"a\tna\xffme\thost\n")
    hosts = load_hosts(f)
    assert len(hosts) == 1 and hosts[0].slug == "a"


def test_empty_file_is_an_empty_list(tmp_path: Path) -> None:
    assert load_hosts(write(tmp_path / "h", "")) == []


def test_missing_file_raises_without_path(tmp_path: Path) -> None:
    missing = tmp_path / "secret-dir" / "nope"
    with pytest.raises(HostsUnavailable) as info:
        load_hosts(missing)
    assert "secret-dir" not in str(info.value)


def test_directory_instead_of_file_raises(tmp_path: Path) -> None:
    with pytest.raises(HostsUnavailable):
        load_hosts(tmp_path)
