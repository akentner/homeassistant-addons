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
    processing/ before an upload attempt, then to sent/ on success. On
    failure it currently moves straight to failed/ -- retry/backoff across
    multiple poll cycles is added in a later revision of this worker
    (tracked via a `<basename>.retry.json` state file living alongside the
    PDF in processing/).
  - The worker does its own gating on paperless_upload.enabled: when
    disabled (the shipped default, D-07), this process logs one INFO line
    and exits immediately, writing nothing at all under /data.
"""

import json
import sys
import time
from datetime import datetime
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


def process_document(pdf_path: Path, config: dict) -> None:
    """Move `pdf_path` (+ its sidecar, if present) into processing/, attempt
    one upload, then move to sent/ or failed/.

    Wrapped in its own try/except by the caller (poll_once) so one
    malformed document never kills the loop for every other queued
    document.
    """
    sidecar_path = pdf_path.with_suffix(".json")
    processing_pdf = PROCESSING / pdf_path.name
    processing_sidecar = PROCESSING / sidecar_path.name

    pdf_path.replace(processing_pdf)
    if sidecar_path.exists():
        sidecar_path.replace(processing_sidecar)

    if upload_document(processing_pdf, config):
        if processing_sidecar.exists():
            processing_sidecar.unlink()
        processing_pdf.replace(SENT / processing_pdf.name)
    else:
        # No retry/backoff yet at this revision -- move straight to
        # failed/. failed/ documents are never deleted (sidecar preserved
        # alongside, so a human triaging failed/ later still has the
        # recovered title).
        processing_pdf.replace(FAILED / processing_pdf.name)
        if processing_sidecar.exists():
            processing_sidecar.replace(FAILED / processing_sidecar.name)
        print(
            f"WARNING: paperless-ngx upload failed for {processing_pdf.name} -- moved to "
            "failed/",
            flush=True,
        )


def poll_once(config: dict) -> None:
    """Scan incoming/ for new documents and process each one."""
    for pdf_path in sorted(INCOMING.glob("*.pdf")):
        try:
            process_document(pdf_path, config)
        except Exception as exc:  # noqa: BLE001 -- must never crash this loop
            print(f"WARNING: failed to process {pdf_path.name}: {exc}", flush=True)


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
