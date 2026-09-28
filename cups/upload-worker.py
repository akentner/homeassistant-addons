#!/usr/bin/env python3
"""Poll /data/paperless_upload/incoming for PDFs produced by the cups-pdf
queue and upload each one to a paperless-ngx instance's REST API.

Deliberately structured like cups/print-history-poller.py (this add-on's
established background-worker shape): a standalone script, started as a
backgrounded process from run.sh, a `while True` poll loop wrapped in a
broad `except Exception` per document so one malformed document never kills
the loop for the rest, plain `print(f"INFO: ...", flush=True)` /
`print(f"WARNING: ...", flush=True)` as the entire logging convention (no
logging module anywhere in this add-on -- background processes' stdout is
not redirected in run.sh, so this reaches `docker logs`/`ha apps logs`
automatically).

Design (see .planning/phases/22-cups-paperless-ngx-pdf-document-upload/
22-CONTEXT.md D-01/D-05/D-07/D-09..D-15 and this phase's 22-01-PLAN.md for
the full rationale):
  - cupsd's own cups-pdf queue writes every job's PDF flat into incoming/
    (D-05 -- a single shared outbox directory, no per-user subdirectories,
    since this headless container has no meaningful per-user home-directory
    concept).
  - A best-effort PostProcess hook (see generate_config.py's
    build_paperless_postprocess_hook) writes a same-basename `.json` sidecar
    next to each PDF carrying the job's derived title (D-10/D-12/D-13). This
    worker reads that sidecar, falling back to a timestamp-based title
    (D-11) when it is missing or malformed -- the upload must never be
    skipped just because a title could not be recovered.
  - Each PDF (+ its sidecar, if present) is atomically moved into
    processing/ before an upload attempt, then to sent/ on success.
  - On failure, a companion `<basename>.retry.json` state file (attempts +
    next_attempt_at, a FIXED interval per D-09 -- not exponential, matching
    this add-on's stated preference for simple/predictable behavior over
    cleverness) is written atomically alongside the PDF in processing/, and
    the document is retried on a later poll cycle once next_attempt_at has
    passed. Once `attempts` reaches `retry_count`, the PDF + sidecar (if
    present) move to failed/ (never deleted) and exactly one WARNING line
    is emitted (D-15).
  - The worker does its own gating on paperless_upload.enabled: when
    disabled (the shipped default, D-07), this process logs one INFO line
    and exits immediately, writing nothing at all under /data.
"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

OUTBOX_ROOT = Path("/data/paperless_upload")
INCOMING = OUTBOX_ROOT / "incoming"
PROCESSING = OUTBOX_ROOT / "processing"
SENT = OUTBOX_ROOT / "sent"
FAILED = OUTBOX_ROOT / "failed"
OPTIONS_PATH = Path("/data/options.json")

POLL_INTERVAL_SECONDS = 20
PAPERLESS_ENDPOINT = "/api/documents/post_document/"
TITLE_MAX_LENGTH = 128
# Suffix for the retry-state sidecar -- distinct from the title sidecar
# (`.json`) written by the PostProcess hook, so the two never collide.
RETRY_STATE_SUFFIX = ".retry.json"


def load_options() -> dict:
    """Read /data/options.json directly -- duplicated (not imported) from
    generate_config.py's own load_options(), matching this codebase's
    established convention of fully standalone worker scripts (see
    print-history-poller.py, which has no shared module either)."""
    if not OPTIONS_PATH.exists():
        return {}
    with open(OPTIONS_PATH) as f:
        return json.load(f)


def load_paperless_config(options: dict) -> dict | None:
    """Return the paperless_upload config dict, or None when disabled.

    Mirrors generate_config.py's own build_cups_pdf_conf fail-safe default
    (D-07) -- this worker independently gates on the same option, since it
    runs as a fully separate OS process with no shared state.
    """
    upload = options.get("paperless_upload") or {}
    if not bool(upload.get("enabled", False)):
        return None
    return upload


def read_title(pdf_path: Path) -> str:
    """Return the sidecar's recorded title, or a timestamp fallback (D-11).

    Never raises, never skips the upload for a missing/malformed sidecar
    (D-13) -- mirrors print-history-poller.py's load_last_seen_job_id()
    try/except-and-degrade-gracefully shape.
    """
    sidecar_path = pdf_path.with_suffix(".json")
    title = None
    if sidecar_path.exists():
        try:
            title = json.loads(sidecar_path.read_text()).get("title")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(
                f"WARNING: could not read sidecar {sidecar_path}: {exc} -- falling back to "
                "timestamp title",
                flush=True,
            )
    if not title:
        title = f"Scan_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    # D-14: trim + length-cap only, regardless of source -- title is a plain
    # API string, never a filename, so no filesystem sanitization is needed.
    return str(title).strip()[:TITLE_MAX_LENGTH]


def retry_state_path(pdf_path: Path) -> Path:
    """Return `<basename>.retry.json` for `pdf_path` -- lives alongside the
    PDF in processing/ while retries are outstanding, distinct from the
    `.json` title sidecar."""
    return pdf_path.parent / (pdf_path.stem + RETRY_STATE_SUFFIX)


def load_retry_state(pdf_path: Path) -> dict | None:
    """Return the parsed retry-state dict, or None if absent/malformed.

    A malformed/unreadable state file is treated as "no prior attempts" --
    conservative (one extra retry at worst) rather than raising and killing
    the poll cycle.
    """
    state_path = retry_state_path(pdf_path)
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            f"WARNING: could not read retry state {state_path}: {exc} -- treating as no "
            "prior attempts",
            flush=True,
        )
        return None


def save_retry_state(pdf_path: Path, attempts: int, next_attempt_at: datetime) -> None:
    """Atomically persist retry state -- same temp-file + `.replace()` idiom
    as print-history-poller.py's save_last_seen_job_id()."""
    state_path = retry_state_path(pdf_path)
    tmp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps({"attempts": attempts, "next_attempt_at": next_attempt_at.isoformat()})
    )
    tmp_path.replace(state_path)


def is_due(pdf_path: Path) -> bool:
    """Return True if `pdf_path` has no retry state yet (never attempted) or
    its `next_attempt_at` has already passed."""
    state = load_retry_state(pdf_path)
    if state is None:
        return True
    try:
        next_attempt_at = datetime.fromisoformat(state["next_attempt_at"])
    except (KeyError, ValueError):
        return True
    return datetime.now(timezone.utc) >= next_attempt_at


def upload_document(pdf_path: Path, config: dict) -> bool:
    """Attempt one upload of `pdf_path` to paperless-ngx.

    Returns True on a 2xx response, False on any exception or non-2xx
    response. Never raises -- callers treat both outcomes as ordinary
    control flow, not exceptional.
    """
    url = str(config.get("url", "") or "").rstrip("/")
    token = str(config.get("token", "") or "")
    timeout = int(config.get("timeout", 30) or 30)
    title = read_title(pdf_path)

    try:
        with pdf_path.open("rb") as fh:
            response = requests.post(
                f"{url}{PAPERLESS_ENDPOINT}",
                headers={"Authorization": f"Token {token}"},
                files={"document": (pdf_path.name, fh, "application/pdf")},
                data={"title": title},
                timeout=timeout,
            )
    except requests.RequestException as exc:
        print(
            f"WARNING: paperless-ngx upload request failed for {pdf_path.name}: {exc}",
            flush=True,
        )
        return False

    if 200 <= response.status_code < 300:
        print(
            f"INFO: uploaded {pdf_path.name} to paperless-ngx (title={title!r}, "
            f"response={response.text.strip()[:200]!r})",
            flush=True,
        )
        return True

    print(
        f"WARNING: paperless-ngx upload for {pdf_path.name} returned HTTP "
        f"{response.status_code}: {response.text.strip()[:200]!r}",
        flush=True,
    )
    return False


def attempt_and_route(pdf_path: Path, config: dict, prior_attempts: int) -> None:
    """Attempt one upload of a document already sitting in processing/, then
    route it to sent/, back into processing/ (with updated retry state), or
    failed/ depending on the outcome and `retry_count`.

    `prior_attempts` is the number of attempts already recorded in this
    document's retry state (0 for a brand-new document with no state file
    yet). Wrapped in its own try/except by the caller (poll_once) so one
    malformed document never kills the loop for every other queued
    document.
    """
    sidecar_path = pdf_path.parent / (pdf_path.stem + ".json")
    retry_path = retry_state_path(pdf_path)

    if upload_document(pdf_path, config):
        if sidecar_path.exists():
            sidecar_path.unlink()
        if retry_path.exists():
            retry_path.unlink()
        pdf_path.replace(SENT / pdf_path.name)
        return

    attempts = prior_attempts + 1
    retry_count = int(config.get("retry_count", 5) or 5)
    retry_delay = int(config.get("retry_delay", 60) or 60)

    if attempts >= retry_count:
        pdf_path.replace(FAILED / pdf_path.name)
        if sidecar_path.exists():
            sidecar_path.replace(FAILED / sidecar_path.name)
        if retry_path.exists():
            retry_path.unlink()
        # D-15: exactly one WARNING-level line per exhausted-retry document --
        # this literal template exists at exactly one call site (this one)
        # so it is never duplicated across the codebase.
        print(
            f"WARNING: paperless-ngx upload exhausted after {retry_count} attempts for "
            f"{pdf_path.name} -- moved to failed/, see failed/{pdf_path.name}",
            flush=True,
        )
    else:
        next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
        save_retry_state(pdf_path, attempts, next_attempt_at)
        print(
            f"INFO: paperless-ngx upload attempt {attempts}/{retry_count} failed for "
            f"{pdf_path.name} -- retrying at {next_attempt_at.isoformat()}",
            flush=True,
        )


def process_new_document(pdf_path: Path, config: dict) -> None:
    """Move a brand-new document from incoming/ into processing/, then
    attempt its first upload."""
    sidecar_path = pdf_path.parent / (pdf_path.stem + ".json")
    processing_pdf = PROCESSING / pdf_path.name
    processing_sidecar = PROCESSING / sidecar_path.name

    pdf_path.replace(processing_pdf)
    if sidecar_path.exists():
        sidecar_path.replace(processing_sidecar)

    attempt_and_route(processing_pdf, config, prior_attempts=0)


def process_due_retry(pdf_path: Path, config: dict) -> None:
    """Re-attempt a document already sitting in processing/ whose
    next_attempt_at has passed."""
    state = load_retry_state(pdf_path) or {}
    prior_attempts = int(state.get("attempts", 0) or 0)
    attempt_and_route(pdf_path, config, prior_attempts=prior_attempts)


def poll_once(config: dict) -> None:
    """Scan incoming/ for brand-new documents, and processing/ for documents
    whose retry backoff has elapsed."""
    for pdf_path in sorted(INCOMING.glob("*.pdf")):
        try:
            process_new_document(pdf_path, config)
        except Exception as exc:  # noqa: BLE001 -- must never crash this loop
            print(f"WARNING: failed to process {pdf_path.name}: {exc}", flush=True)

    for pdf_path in sorted(PROCESSING.glob("*.pdf")):
        # A document with no retry state at all here means a prior run
        # crashed mid-attempt (before any state was written) -- is_due()
        # already treats "no state file" as due immediately, so it is
        # retried rather than left stuck forever.
        if not is_due(pdf_path):
            continue
        try:
            process_due_retry(pdf_path, config)
        except Exception as exc:  # noqa: BLE001 -- must never crash this loop
            print(f"WARNING: failed to retry {pdf_path.name}: {exc}", flush=True)


def main() -> None:
    options = load_options()
    config = load_paperless_config(options)
    if config is None:
        print("INFO: paperless_upload.enabled is false -- upload-worker exiting", flush=True)
        return

    for stage_dir in (INCOMING, PROCESSING, SENT, FAILED):
        stage_dir.mkdir(parents=True, exist_ok=True)

    print("INFO: paperless-ngx upload worker started", flush=True)
    while True:
        try:
            poll_once(config)
        except Exception as exc:  # noqa: BLE001 -- must never crash this loop
            print(f"WARNING: upload-worker poll cycle failed: {exc}", flush=True)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
