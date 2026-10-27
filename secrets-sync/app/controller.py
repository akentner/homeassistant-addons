"""Interface between the web layer and the supervisor (see docs/SPEC.md, "Web <-> engine").

The web layer only reads state.json and calls this controller. Implemented by ss-core
(app/engine/supervisor.py); web tests use a fake.
"""

from __future__ import annotations

from typing import Any, Protocol


class Controller(Protocol):
    def trigger_sync(self) -> bool:
        """Request an immediate sync. Returns False if rate limited (min interval 60 s) or one is running."""
        ...

    def preview(self) -> dict[str, Any]:
        """Dry run: fetch all providers, return {"added": [...], "removed": [...], "changed": [...],
        "errors": [...]} as key NAMES vs. the current secrets.yaml. Writes nothing."""
        ...
