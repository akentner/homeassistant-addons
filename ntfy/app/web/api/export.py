"""GET /api/export (contract C10/C11, D-09): the schema-1 state document as a JSON or YAML download."""

from __future__ import annotations

import logging
from typing import Any

from app import exporter
from app.contract import ApiError
from app.web.server import Download, Request, Router

audit = logging.getLogger("ntfy.audit")
FORMATS = {
    "json": ("ntfy-state.json", "application/json; charset=utf-8", exporter.to_json),
    "yaml": ("ntfy-state.yaml", "application/yaml; charset=utf-8", exporter.to_yaml),
}


def register(router: Router, ctx: Any) -> None:
    def export(req: Request) -> Download:
        fmt = req.arg("format")
        fmt = "json" if fmt is None else fmt
        if fmt not in FORMATS:
            raise ApiError("bad_request", "format must be json or yaml")
        hashes = req.arg("include_hashes")
        hashes = "0" if hashes is None else hashes
        if hashes not in ("0", "1"):
            raise ApiError("bad_request", "include_hashes must be 0 or 1")
        ctx.db.ensure_supported()
        doc = exporter.build_export(
            ctx.db,
            ctx.origins,
            include_hashes=hashes == "1",
            auth_default_access=ctx.options.auth_default_access,
            now=ctx.clock(),
        )
        if hashes == "1":
            audit.warning("export with password hashes")
        filename, content_type, render = FORMATS[fmt]
        return Download(filename, content_type, render(doc).encode("utf-8"))

    router.add("GET", "/api/export", export)
