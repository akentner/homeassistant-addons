"""monitor.sh: the kernel-log replay limit of the remote script and the SYNC markers."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

MONITOR_SH = Path(__file__).resolve().parent.parent / "monitor.sh"
needs_sh = pytest.mark.skipif(shutil.which("sh") is None, reason="sh not installed")


def kmsg_filter_source() -> str:
    text = MONITOR_SH.read_text(encoding="utf-8")
    match = re.search(r"^kmsg_filter\(\) \{\n.*?^\}\n", text, re.S | re.M)
    assert match, "kmsg_filter not found in monitor.sh"
    return match.group(0)


def run_filter(lines: list[str], cutoff: int) -> list[str]:
    script = f"cutoff={cutoff}\n{kmsg_filter_source()}\nkmsg_filter\n"
    proc = subprocess.run(["sh", "-c", script], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True)
    return proc.stdout.splitlines()


@needs_sh
def test_old_lines_are_dropped_as_kmsg_and_kerr() -> None:
    out = run_filter(["3,1,1000000,-;old I/O error", "6,2,9000000,-;new info"], cutoff=5_000_000)
    assert out == ["KMSG 6,2,9000000,-;new info"]


@needs_sh
def test_new_error_lines_still_yield_kmsg_and_kerr() -> None:
    out = run_filter(["3,5,9000000,-;EXT4-fs error", "6,6,9000001,-;blk_update_request: I/O error"], cutoff=5_000_000)
    assert out == [
        "KMSG 3,5,9000000,-;EXT4-fs error",
        "KERR 3,5,9000000,-;EXT4-fs error",
        "KMSG 6,6,9000001,-;blk_update_request: I/O error",
        "KERR 6,6,9000001,-;blk_update_request: I/O error",
    ]


@needs_sh
def test_continuation_lines_follow_their_message() -> None:
    lines = ["6,1,1000000,-;old", " SUBSYSTEM=usb", "6,2,9000000,-;new", " DEVICE=+usb:1"]
    assert run_filter(lines, cutoff=5_000_000) == ["KMSG 6,2,9000000,-;new", "KMSG  DEVICE=+usb:1"]


@needs_sh
def test_line_exactly_at_the_cutoff_is_kept() -> None:
    assert run_filter(["6,1,5000000,-;edge"], cutoff=5_000_000) == ["KMSG 6,1,5000000,-;edge"]


def test_cutoff_is_derived_from_uptime_and_replay_seconds() -> None:
    text = MONITOR_SH.read_text(encoding="utf-8")
    assert 'REPLAY_SECONDS="${REPLAY_SECONDS:-300}"' in text
    assert "cutoff=$(( ${up%.*} * 1000000 - '\"$REPLAY_SECONDS\"' * 1000000 ))" in text


def test_sync_markers_are_mirrored_into_the_state_file() -> None:
    text = MONITOR_SH.read_text(encoding="utf-8")
    assert "SAMPLE*|DISK*|DSTATE*|PROBE*|BOOT*|KERR*|SYNC*)" in text
    assert text.index('log "SYNC start"') < text.index('log "SYNC done"')
