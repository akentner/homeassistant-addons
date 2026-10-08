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
    processing/ before an upload attempt, then to sent/ on success. Success
    means HTTP 200 with the consumption-task id as a non-empty JSON string
    (paperless-ngx's documented answer); redirects are never followed.
  - On failure, a companion `<basename>.retry.json` state file (attempts +
    next_attempt_at, a FIXED interval per D-09 -- not exponential, matching
    this add-on's stated preference for simple/predictable behavior over
    cleverness) is written atomically alongside the PDF in processing/, and
    the document is retried on a later poll cycle once next_attempt_at has
    passed. Once `attempts` reaches `retry_count`, the PDF + sidecar (if
    present) move to failed/ (never deleted) and exactly one WARNING line
    is emitted (D-15). A same-named collision on the final move into
    sent/ or failed/ (e.g. after cupsd's own job-ID counter resets across a
    container restart) is disambiguated with a timestamp+pid suffix and
    logged, rather than silently overwriting an already-retained document.
  - The worker does its own gating on paperless_upload.enabled: when
    disabled (the shipped default, D-07), this process logs one INFO line
    and exits immediately, writing nothing at all under /data.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

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
        parsed = None
        try:
            parsed = json.loads(sidecar_path.read_text())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(
                f"WARNING: could not read sidecar {sidecar_path}: {exc} -- falling back to "
                "timestamp title",
                flush=True,
            )
        if isinstance(parsed, dict):
            title = parsed.get("title")
        elif parsed is not None:
            print(
                f"WARNING: sidecar {sidecar_path} is not a JSON object "
                f"({type(parsed).__name__}) -- falling back to timestamp title",
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


def _disambiguation_suffix() -> str:
    """Return a UTC-timestamp+pid suffix used to disambiguate a colliding
    sent/failed destination filename (WR-05)."""
    return f"-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}-{os.getpid()}"


def unique_destination(dest_dir: Path, name: str, tag: str | None = None) -> Path:
    """Return `dest_dir / name`, disambiguated with a suffix if that path
    already exists on disk.

    Never silently overwrites an already-retained document via
    `Path.replace()`'s rename-clobber semantics (WR-05) -- a same-named
    collision (most plausibly caused by cupsd's own job-ID counter resetting
    across a container restart) is instead renamed and logged.
    """
    candidate = dest_dir / name
    if not candidate.exists():
        return candidate
    if tag is None:
        tag = _disambiguation_suffix()
    stem = Path(name).stem
    suffix = Path(name).suffix
    disambiguated = dest_dir / f"{stem}{tag}{suffix}"
    print(
        f"WARNING: destination {candidate} already exists -- moving to "
        f"{stem}{tag}{suffix} instead to avoid silently overwriting an already-retained "
        "document (WR-05)",
        flush=True,
    )
    return disambiguated


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
        parsed = json.loads(state_path.read_text())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            f"WARNING: could not read retry state {state_path}: {exc} -- treating as no "
            "prior attempts",
            flush=True,
        )
        return None
    if not isinstance(parsed, dict):
        print(
            f"WARNING: retry state {state_path} is not a JSON object "
            f"({type(parsed).__name__}) -- treating as no prior attempts",
            flush=True,
        )
        return None
    return parsed


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


def _safe_redirect_target(location: str) -> str:
    """Return a log-safe rendering of a redirect `Location` header value.

    Keeps scheme, host[:port] and path only; query string, fragment and userinfo
    (SSO redirects commonly carry state or credentials there) are dropped. A
    relative Location yields the path only. A malformed value yields a placeholder.
    Capped at 200 characters.
    """
    location = (location or "").strip()
    if not location:
        return "(no Location header)"
    try:
        parts = urlsplit(location)
    except ValueError:
        # Malformed value (e.g. unbalanced IPv6 bracket); never let logging raise
        return "(malformed Location header)"
    host = parts.netloc.rsplit("@", 1)[-1]
    if parts.scheme and host:
        target = f"{parts.scheme}://{host}{parts.path}"
    else:
        target = parts.path or "/"
    return target[:200]


def _is_task_id_body(response: requests.Response) -> bool:
    """Return True when the response body is a non-empty JSON string.

    paperless-ngx answers an accepted upload with HTTP 200 and the consumption
    task id as a bare JSON string (`Response(async_task.id)`). The id format is
    deliberately not pattern-checked: it is a Celery implementation detail.
    """
    try:
        parsed = response.json()
    except ValueError:
        return False
    return isinstance(parsed, str) and bool(parsed.strip())


def upload_document(pdf_path: Path, config: dict) -> bool:
    """Attempt one upload of `pdf_path` to paperless-ngx.

    Returns True only on HTTP 200 whose body is a non-empty JSON string (the
    consumption-task id); False on any exception, any 3xx redirect, any other
    2xx or any other non-2xx response. Redirects are never followed (CR-01): a
    followed redirect could land on a login page that answers 2xx and record a
    document as delivered that paperless-ngx never received. Never raises --
    callers treat both outcomes as ordinary control flow, not exceptional.
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
                allow_redirects=False,
            )
    except (requests.RequestException, ValueError) as exc:
        # ValueError: requests parses the Location header even with allow_redirects=False
        # and raises it unwrapped for malformed values (e.g. "http://[::1/x") -- WR-09
        print(
            f"WARNING: paperless-ngx upload request failed for {pdf_path.name}: {exc}",
            flush=True,
        )
        return False

    if 300 <= response.status_code < 400:
        print(
            f"WARNING: paperless-ngx upload for {pdf_path.name} returned HTTP "
            f"{response.status_code} redirect to "
            f"{_safe_redirect_target(response.headers.get('Location', ''))} -- redirects are "
            "not followed; set paperless_upload.url to the final address",
            flush=True,
        )
        return False

    if response.status_code == 200 and not _is_task_id_body(response):
        print(
            f"WARNING: paperless-ngx upload for {pdf_path.name} returned HTTP 200 but the "
            f"response body is not a task id: {response.text.strip()[:200]!r}",
            flush=True,
        )
        return False

    if response.status_code == 200:
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
        pdf_path.replace(unique_destination(SENT, pdf_path.name))
        return

    attempts = prior_attempts + 1
    retry_count = int(config.get("retry_count", 5) or 5)
    retry_delay = int(config.get("retry_delay", 60) or 60)

    if attempts >= retry_count:
        # Share one collision_tag across the PDF and its sidecar (when both
        # collide) so a human triaging failed/ later can still correlate a
        # colliding pair by their identical disambiguation suffix (WR-05).
        collision_tag = _disambiguation_suffix() if (FAILED / pdf_path.name).exists() else None
        pdf_path.replace(unique_destination(FAILED, pdf_path.name, tag=collision_tag))
        if sidecar_path.exists():
            sidecar_path.replace(unique_destination(FAILED, sidecar_path.name, tag=collision_tag))
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
        #
        # is_due() is called INSIDE this same per-document try/except as
        # process_due_retry() (not before it) so a malformed *.retry.json
        # can never abort the scan for every alphabetically-later document
        # (CR-01).
        try:
            if not is_due(pdf_path):
                continue
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
