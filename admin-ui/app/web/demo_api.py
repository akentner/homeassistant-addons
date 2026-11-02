"""Demo API of the blueprint add-on (tracer: health only; plan 26-02 completes it)."""

from __future__ import annotations

from .skeleton import Request, Router


def register(router: Router, *, version: str, lib_version: str) -> None:
    def health(_req: Request) -> dict[str, str]:
        return {"status": "ok", "addon_version": version, "lib_version": lib_version}

    router.add("GET", "/api/health", health)
