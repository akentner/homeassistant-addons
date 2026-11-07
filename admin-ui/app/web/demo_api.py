"""Demo API of the blueprint add-on: in-memory CRUD, every stable error state, slow, whoami and echo."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from .skeleton import ERROR_STATUS, ApiError, Request, Router, ingress_user, register_error_code

# Demo-only code that shows how an add-on extends the stable table
register_error_code("teapot", 418)

MAX_NAME = 40
MAX_NOTE = 200
MAX_SLOW_MS = 2000
DEFAULT_SLOW_MS = 800

# Patched by tests so the slow endpoint does not really wait
_sleep: Callable[[float], None] = time.sleep


def _now_ms() -> int:
    return int(time.time() * 1000)


class _Store:
    def __init__(self, clock: Callable[[], int]) -> None:
        self.lock = threading.Lock()
        self.clock = clock
        self.counter = 0
        self.items: dict[str, dict[str, Any]] = {}
        for name, note, locked in (
            ("alpha", "First sample item", False),
            ("beta", "Second sample item", False),
            ("locked", "Protected: cannot be changed or deleted", True),
        ):
            self.add(name, note, locked)

    def add(self, name: str, note: str, locked: bool = False) -> dict[str, Any]:
        self.counter += 1
        item = {
            "id": str(self.counter),
            "name": name,
            "note": note,
            "locked": locked,
            "created": self.clock(),
        }
        self.items[item["id"]] = item
        return item

    def name_taken(self, name: str, exclude_id: str | None = None) -> bool:
        lowered = name.lower()
        return any(i["name"].lower() == lowered and i["id"] != exclude_id for i in self.items.values())


def _clean_name(value: Any) -> str:
    if not isinstance(value, str):
        raise ApiError("bad_request", "name must be a string")
    name = value.strip()
    if not 1 <= len(name) <= MAX_NAME:
        raise ApiError("bad_request", f"name must be 1-{MAX_NAME} characters")
    return name


def _clean_note(value: Any) -> str:
    if not isinstance(value, str):
        raise ApiError("bad_request", "note must be a string")
    if len(value) > MAX_NOTE:
        raise ApiError("bad_request", f"note must be at most {MAX_NOTE} characters")
    return value


def register(
    router: Router,
    *,
    version: str,
    lib_version: str,
    clock: Callable[[], int] = _now_ms,
    slug: Callable[[], str | None] = lambda: None,
) -> None:
    store = _Store(clock)

    def health(_req: Request) -> dict[str, str]:
        body = {"status": "ok", "addon_version": version, "lib_version": lib_version}
        addon_slug = slug()
        if addon_slug:  # unknown (no token, direct run): the key stays out and the GUI hides the info link
            body["addon_slug"] = addon_slug
        return body

    def list_items(_req: Request) -> dict[str, Any]:
        with store.lock:
            return {"items": [dict(i) for i in store.items.values()]}

    def create_item(req: Request) -> tuple[int, dict[str, Any]]:
        body = req.body()
        name = _clean_name(body.get("name"))
        note = _clean_note(body.get("note", ""))
        with store.lock:
            if store.name_taken(name):
                raise ApiError("conflict", "an item with this name already exists")
            return 201, dict(store.add(name, note))

    def update_item(req: Request) -> dict[str, Any]:
        body = req.body()
        with store.lock:
            item = store.items.get(req.params["id"])
            if item is None:
                raise ApiError("not_found", "item not found")
            if item["locked"]:
                raise ApiError("protected", "this item is protected")
            name = _clean_name(body["name"]) if "name" in body else item["name"]
            note = _clean_note(body["note"]) if "note" in body else item["note"]
            if store.name_taken(name, exclude_id=item["id"]):
                raise ApiError("conflict", "an item with this name already exists")
            item["name"], item["note"] = name, note
            return dict(item)

    def delete_item(req: Request) -> None:
        body = req.body()
        confirm = body.get("confirm", req.arg("confirm"))
        with store.lock:
            item = store.items.get(req.params["id"])
            if item is None:
                raise ApiError("not_found", "item not found")
            if item["locked"]:
                raise ApiError("protected", "this item is protected")
            if confirm != item["name"]:
                raise ApiError("confirmation_required", "type the item name to confirm")
            del store.items[item["id"]]

    def fail(req: Request) -> Any:
        code = req.params["code"]
        if code == "boom":
            raise RuntimeError("demo failure with secret detail")
        if code not in ERROR_STATUS:
            raise ApiError("not_found", "unknown error code")
        raise ApiError(code, f"demo error: {code}")

    def slow(req: Request) -> dict[str, Any]:
        raw = req.arg("ms")
        try:
            wanted = DEFAULT_SLOW_MS if raw is None else int(raw)
        except ValueError as exc:
            raise ApiError("bad_request", "ms must be an integer") from exc
        waited = max(0, min(wanted, MAX_SLOW_MS))
        _sleep(waited / 1000)
        return {"ok": True, "waited_ms": waited}

    def whoami(req: Request) -> dict[str, Any]:
        # Only the requesting viewer's own identity; values are never logged
        return {"user": ingress_user(req.headers)}

    def echo(req: Request) -> dict[str, Any]:
        return {"echo": req.body()}

    router.add("GET", "/api/health", health)
    router.add("GET", "/api/items", list_items)
    router.add("POST", "/api/items", create_item)
    router.add("PUT", "/api/items/{id}", update_item)
    router.add("DELETE", "/api/items/{id}", delete_item)
    router.add("GET", "/api/fail/{code}", fail)
    router.add("GET", "/api/slow", slow)
    router.add("GET", "/api/whoami", whoami)
    router.add("POST", "/api/echo", echo)
