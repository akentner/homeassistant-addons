"""Backup routes (contract C10/C12, D-14): list, create and download auth.db backups."""

from __future__ import annotations

from typing import Any

from app.web.server import Download, Request, Router


def register(router: Router, ctx: Any) -> None:
    def list_backups(_req: Request) -> dict[str, Any]:
        return {"backups": ctx.backups.list()}

    def create_backup(req: Request) -> tuple[int, dict[str, Any]]:
        req.body()  # must be an object (or empty); the reason is always "manual"
        with ctx.lock:
            return 201, {"backup": ctx.backups.create("manual")}

    def download_backup(req: Request) -> Download:
        path = ctx.backups.path_for(req.params["name"])
        return Download(path.name, "application/vnd.sqlite3", path.read_bytes())

    router.add("GET", "/api/backups", list_backups)
    router.add("POST", "/api/backups", create_backup)
    router.add("GET", "/api/backups/{name}", download_backup)
