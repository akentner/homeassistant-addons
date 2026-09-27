#!/usr/bin/env python3
"""Poll cupsd for newly-completed print jobs and append one JSONL record
per job to /data/print-history.jsonl.

Deliberately lightweight (a periodic `lpstat -W completed -o` poll, NOT a
CUPS notifier/subscription/D-Bus listener, which would be disproportionate
for a single-printer home setup). State (the last-seen CUPS job id) is
persisted to /data/print-history-state.json so a restart never replays
already-recorded jobs.

Empirically confirmed during this feature's design (live test against
this add-on's own base image): lpstat's text output cannot reliably
distinguish a canceled job from a normal completion -- a job explicitly
canceled while queued showed `Alerts: none` in `lpstat -l`'s output,
identical to what an ordinary success can also show. No IPP query client
(e.g. ipptool) is present in this image to ask cupsd for the job's real
`job-state` attribute instead. `final_state` is therefore always recorded
as "completed" (CUPS's own `-W completed` filter already groups
completed/canceled/aborted jobs together). `title`/`page_count` are also
not exposed by any CLI text tool available here for a completed job, so
both are always recorded as null. See cups/DOCS.md's Print History
section for these documented limitations.
"""

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HISTORY_PATH = Path("/data/print-history.jsonl")
STATE_PATH = Path("/data/print-history-state.json")
POLL_INTERVAL_SECONDS = 20

# Matches one line of `lpstat -W completed -o`'s short-form listing: the
# first field is always "<printer>-<job-id>". CUPS's own job ids are
# always numeric and always the LAST hyphen-separated component, so a
# single rightmost split is unambiguous even when the printer's own name
# contains hyphens (confirmed against CUPS's own naming convention, not a
# guess -- see module docstring).
JOB_TOKEN_RE = re.compile(r"^(?P<printer>.+)-(?P<jobid>\d+)$")


def query_completed_jobs() -> list[tuple[str, int, str]] | None:
    """Return (printer, job_id, user) tuples for every job CUPS currently
    reports as completed/canceled/aborted (CUPS's own -W completed filter
    groups all three). Returns None -- not an empty list -- on any
    failure to reach cupsd, so callers can tell "no jobs" apart from
    "could not ask" (e.g. cupsd not up yet at add-on boot)."""
    try:
        result = subprocess.run(
            ["lpstat", "-W", "completed", "-o"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"WARNING: lpstat invocation failed: {exc}", flush=True)
        return None

    if result.returncode != 0:
        print(
            f"WARNING: lpstat -W completed -o exited {result.returncode}: "
            f"{result.stderr.strip()}",
            flush=True,
        )
        return None

    jobs: list[tuple[str, int, str]] = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        match = JOB_TOKEN_RE.match(fields[0])
        if not match:
            continue
        jobs.append((match.group("printer"), int(match.group("jobid")), fields[1]))
    return jobs


def load_last_seen_job_id() -> int | None:
    """Return the persisted last-seen job id, or None if no state file
    exists yet (first-ever run -- see establish_baseline())."""
    if not STATE_PATH.exists():
        return None
    try:
        data = json.loads(STATE_PATH.read_text())
        return int(data["last_seen_job_id"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"WARNING: could not read {STATE_PATH}: {exc} -- treating as first run", flush=True)
        return None


def save_last_seen_job_id(job_id: int) -> None:
    """Atomically persist `job_id` -- write to a temp file then rename, so
    a container killed mid-write never leaves a half-written state file
    behind."""
    tmp_path = STATE_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps({"last_seen_job_id": job_id}))
    tmp_path.replace(STATE_PATH)


def append_history(printer: str, job_id: int, user: str) -> None:
    """Append one JSONL record for a newly-observed completed job.

    `timestamp` is this poller's OWN wall-clock time at the moment it
    first observed the job (not a parse of CUPS's own textual completion
    date, which is locale-dependent and not reliably parseable). At this
    poller's 20s interval the delta from actual completion is negligible
    for a simple home-use history log. See module docstring for why
    `title`/`page_count` are always null and `final_state` is always
    "completed".
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "printer": printer,
        "job_id": job_id,
        "user": user or None,
        "title": None,
        "page_count": None,
        "final_state": "completed",
    }
    with HISTORY_PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")
        f.flush()


def poll_once(last_seen_job_id: int) -> int:
    """Run one poll cycle. Returns the new last-seen job id (unchanged if
    the poll failed or found nothing new)."""
    jobs = query_completed_jobs()
    if jobs is None:
        return last_seen_job_id

    new_jobs = sorted((j for j in jobs if j[1] > last_seen_job_id), key=lambda j: j[1])
    for printer, job_id, user in new_jobs:
        append_history(printer, job_id, user)
        print(f"INFO: recorded completed job {printer}-{job_id} (user={user})", flush=True)

    if new_jobs:
        last_seen_job_id = new_jobs[-1][1]
        save_last_seen_job_id(last_seen_job_id)
    return last_seen_job_id


def establish_baseline() -> int | None:
    """First-ever run (no state file): baseline to the CURRENT max
    completed job id WITHOUT emitting history lines for jobs that already
    existed before this poller started -- a forward-only history, not a
    retroactive backfill. Returns None (retry next cycle) if cupsd could
    not be reached yet."""
    jobs = query_completed_jobs()
    if jobs is None:
        return None
    baseline = max((job_id for _, job_id, _ in jobs), default=0)
    save_last_seen_job_id(baseline)
    print(f"INFO: first run -- baselining at job id {baseline} (no retroactive backfill)", flush=True)
    return baseline


def main() -> None:
    last_seen_job_id = load_last_seen_job_id()
    while last_seen_job_id is None:
        last_seen_job_id = establish_baseline()
        if last_seen_job_id is None:
            time.sleep(POLL_INTERVAL_SECONDS)

    while True:
        try:
            last_seen_job_id = poll_once(last_seen_job_id)
        except Exception as exc:  # noqa: BLE001 -- must never crash this loop
            print(f"WARNING: print-history poll cycle failed: {exc}", flush=True)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
