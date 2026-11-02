"""Maintenance services (D-04, D-11, D-14): guarded resets, cache clearing and the test publish.

Every destructive service checks the typed phrase first, writes an auth.db backup before the first change and runs under
ctx.lock. The only ntfy-owned database this process ever writes is cache.db (DELETE FROM messages), never auth.db.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import urllib.error
import urllib.request
from typing import Any, Callable

from app import bootstrap
from app.contract import NTFY_PORT, RESET_PHRASES, TOPIC_RE, ApiError
from app.ntfycli import NtfyCliError

log = logging.getLogger(__name__)

ATTACHMENT_ID_RE = re.compile(r"^[A-Za-z0-9]{1,64}$")
MAX_MESSAGE = 512
DEFAULT_MESSAGE = "ntfy admin GUI test"
HttpCall = Callable[[str, dict[str, str], bytes], "tuple[int, bytes]"]


def _confirm(key: str, typed: Any) -> None:
    if not isinstance(typed, str) or typed != RESET_PHRASES[key]:
        raise ApiError("confirmation_required", f'type "{RESET_PHRASES[key]}" to confirm')


def reset_acls(ctx: Any, confirm: str) -> dict[str, Any]:
    _confirm("acls", confirm)
    with ctx.lock:
        ctx.db.ensure_supported()
        backup = ctx.backups.create("reset-acls")
        ctx.cli.access_reset()
        ctx.origins.clear_acls()
        return {"done": True, "backup": backup}


def _clear_messages(cache_db: Any) -> int:
    if not cache_db.is_file():
        return 0
    try:
        conn = sqlite3.connect(str(cache_db), timeout=5)
        try:
            has_table = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='messages'").fetchone()
            if has_table is None:
                raise ApiError("ntfy_error", "cache database has no messages table")
            deleted = conn.execute("DELETE FROM messages").rowcount
            conn.commit()
            return max(int(deleted), 0)
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise ApiError("ntfy_error", f"cannot clear cache: {type(exc).__name__}") from exc


def _clear_attachments(directory: Any) -> int:
    if not directory.is_dir():
        return 0
    removed = 0
    for entry in directory.iterdir():
        if not ATTACHMENT_ID_RE.match(entry.name) or entry.is_symlink() or not entry.is_file():
            continue
        try:
            entry.unlink()
            removed += 1
        except OSError:
            log.warning("cannot remove attachment file")
    return removed


def clear_cache(ctx: Any, confirm: str) -> dict[str, Any]:
    _confirm("cache", confirm)
    with ctx.lock:
        ctx.db.ensure_supported()
        backup = ctx.backups.create("clear-cache")
        messages = _clear_messages(ctx.paths.cache_db)
        attachments = _clear_attachments(ctx.paths.attachment_dir)
        return {"done": True, "backup": backup, "messages_deleted": messages, "attachments_deleted": attachments}


def reset_everything(ctx: Any, confirm: str) -> dict[str, Any]:
    _confirm("everything", confirm)
    if not ctx.options.admin_password:
        raise ApiError("conflict", "admin_password option is empty: the admin could not be recreated")
    with ctx.lock:
        ctx.db.ensure_supported()
        backup = ctx.backups.create("reset-everything")
        for user in ctx.db.list_users():
            if user["name"] in ("*", "everyone") or user.get("role") == "anonymous":
                continue
            try:
                ctx.cli.user_delete(user["name"])
            except NtfyCliError as exc:
                if exc.code != "not_found":
                    raise
        ctx.cli.access_reset()
        ctx.origins.clear_all()
        bootstrap.apply_options(ctx)
        if not ctx.db.has_user(ctx.options.admin_user):
            raise ApiError("ntfy_error", "admin user was not recreated after the reset")
        return {"done": True, "backup": backup}


def _http_post(url: str, headers: dict[str, str], body: bytes) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=5) as resp:  # noqa: S310
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def publish_test(ctx: Any, topic: str, message: str | None = None, *, http: HttpCall | None = None) -> dict[str, Any]:
    if not isinstance(topic, str) or not TOPIC_RE.match(topic):
        raise ApiError("bad_request", "invalid topic")
    if message is not None and not isinstance(message, str):
        raise ApiError("bad_request", "message must be a string")
    text = (message or DEFAULT_MESSAGE)[:MAX_MESSAGE]
    send = http or _http_post
    admin = ctx.options.admin_user
    with ctx.lock:
        ctx.db.ensure_supported()
        if not ctx.db.has_user(admin):
            raise ApiError("conflict", "admin user does not exist")
        token = ctx.cli.token_add(admin, label="gui-test", expires="2m")
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Title": "ntfy admin GUI",
                "Content-Type": "text/plain; charset=utf-8",
            }
            try:
                status, data = send(f"http://127.0.0.1:{NTFY_PORT}/{topic}", headers, text.encode("utf-8"))
            except OSError:  # URLError, timeout, connection refused: report as a failed publish, not a 500
                status, data = 0, b""
        finally:
            try:
                ctx.cli.token_remove(admin, token)
            except Exception:  # noqa: BLE001 - cleanup must never mask the result; the token expires in 2 minutes
                log.warning("cannot remove test token")
    msg_id = None
    try:
        parsed = json.loads(data.decode("utf-8"))
        if isinstance(parsed, dict) and isinstance(parsed.get("id"), str):
            msg_id = parsed["id"]
    except (ValueError, UnicodeDecodeError, AttributeError):
        pass
    return {"ok": 200 <= status < 300, "status": status, "id": msg_id}
