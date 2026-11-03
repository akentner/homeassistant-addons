"""Bounded backward scan for the last INCIDENT lines."""

from __future__ import annotations

from pathlib import Path

from app.incidents import last_incidents

TS = "2026-11-02T10:00:00Z"


def line(kind: str, n: int | str = "") -> str:
    return f"{TS} INCIDENT {kind} {n}".rstrip()


def write(path: Path, lines: list[str], *, newline: bool = True) -> Path:
    path.write_bytes(("\n".join(lines) + ("\n" if newline else "")).encode("utf-8"))
    return path


def test_newest_ten_oldest_first(tmp_path: Path) -> None:
    lines = [line("change", i) for i in range(25)]
    got = last_incidents(write(tmp_path / "l", lines))
    assert got == lines[-10:]


def test_fewer_than_ten_all_returned(tmp_path: Path) -> None:
    lines = [f"{TS} SAMPLE x", line("start"), f"{TS} KMSG y", line("end")]
    assert last_incidents(write(tmp_path / "l", lines)) == [lines[1], lines[3]]


def test_none_and_missing_file(tmp_path: Path) -> None:
    assert last_incidents(write(tmp_path / "l", [f"{TS} SAMPLE x"])) == []
    assert last_incidents(tmp_path / "missing") == []
    assert last_incidents(tmp_path) == []  # a directory
    assert last_incidents(write(tmp_path / "empty", [], newline=False)) == []


def test_marker_needs_surrounding_spaces(tmp_path: Path) -> None:
    lines = [f"{TS} NOINCIDENT x", f"{TS} KMSG about INCIDENT", f"{TS} INCIDENTAL", line("start")]
    assert last_incidents(write(tmp_path / "l", lines)) == [lines[3]]


def test_old_incidents_below_a_flood_are_found(tmp_path: Path) -> None:
    head = [line("start", i) for i in range(3)]
    flood = [f"{TS} KMSG " + "x" * 80 for _ in range(2000)]
    assert last_incidents(write(tmp_path / "l", head + flood), block=512) == head


def test_recent_incidents_do_not_read_the_whole_file(tmp_path: Path, monkeypatch) -> None:
    flood = [f"{TS} KMSG " + "x" * 80 for _ in range(5000)]
    recent = [line("change", i) for i in range(10)]
    path = write(tmp_path / "l", flood + recent)
    size = path.stat().st_size
    read = 0
    real_open = open

    class Counting:
        def __init__(self, fh):
            self.fh = fh

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.fh.close()

        def read(self, n):
            nonlocal read
            data = self.fh.read(n)
            read += len(data)
            return data

        def __getattr__(self, name):
            return getattr(self.fh, name)

    monkeypatch.setattr("builtins.open", lambda p, mode="r": Counting(real_open(p, mode)))
    assert last_incidents(path, block=1024) == recent
    assert read < size // 10


def test_line_straddling_a_block_boundary_is_whole(tmp_path: Path) -> None:
    lines = [f"{TS} KMSG " + "y" * 37 for _ in range(30)]
    target = line("start", "z" * 50)
    lines.insert(15, target)
    for block in range(7, 80):
        assert last_incidents(write(tmp_path / "l", lines), block=block) == [target], block


def test_first_line_of_the_file_is_found(tmp_path: Path) -> None:
    lines = [line("start"), f"{TS} KMSG a", f"{TS} KMSG b"]
    assert last_incidents(write(tmp_path / "l", lines), block=16) == [lines[0]]
    assert last_incidents(write(tmp_path / "one", [line("end")], newline=False)) == [line("end")]


def test_no_trailing_newline_and_crlf(tmp_path: Path) -> None:
    path = tmp_path / "l"
    path.write_bytes(f"{line('start')}\r\n{line('end')}".encode())
    assert last_incidents(path) == [line("start"), line("end")]


def test_each_line_is_cut_to_400_characters(tmp_path: Path) -> None:
    long = f"{TS} INCIDENT start " + "q" * 900
    got = last_incidents(write(tmp_path / "l", [long]))
    assert len(got[0]) == 400 and got[0] == long[:400]
    assert len(last_incidents(write(tmp_path / "l2", [long]), max_line=50)[0]) == 50


def test_invalid_utf8_and_control_characters(tmp_path: Path) -> None:
    path = tmp_path / "l"
    path.write_bytes(f"{TS} INCIDENT start a\xff\x1b[31mb\x07\tc\n".encode("latin-1"))
    (got,) = last_incidents(path)
    assert "\x1b" not in got and "\x07" not in got and "\t" in got
    assert "�" in got


def test_max_scan_stops_the_scan(tmp_path: Path) -> None:
    old = [line("start", i) for i in range(3)]
    flood = [f"{TS} KMSG " + "x" * 80 for _ in range(500)]
    path = write(tmp_path / "l", old + flood)
    assert last_incidents(path, block=256, max_scan=4096) == []
    assert last_incidents(path, block=256, max_scan=path.stat().st_size) == old


def test_script_markup_is_returned_verbatim(tmp_path: Path) -> None:
    hostile = f"{TS} INCIDENT start kmsg=[<script>alert(1)</script>]"
    assert last_incidents(write(tmp_path / "l", [hostile])) == [hostile]
