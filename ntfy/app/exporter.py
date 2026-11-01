"""Export schema 1 (contract C11, D-09): one versioned document rendered as JSON or YAML.

No token value ever enters the document; password hashes only with include_hashes. The anonymous user appears only as
`everyone` inside `acl`. Output order is deterministic so two exports of the same state are byte-identical.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.contract import SUPPORTED_AUTH_SCHEMA, AuthReader, db_user_to_api, iso_utc
from app.origins import OriginStore

SCHEMA_VERSION = 1


def _is_anonymous(row: dict[str, Any]) -> bool:
    return row.get("role") == "anonymous" or row["name"] in ("*", "everyone")


def build_export(
    db: AuthReader,
    origins: OriginStore,
    *,
    include_hashes: bool,
    auth_default_access: str,
    now: float,
) -> dict[str, Any]:
    users: list[dict[str, Any]] = []
    for row in db.list_users(include_hash=include_hashes):
        if _is_anonymous(row):
            continue
        entry: dict[str, Any] = {
            "name": row["name"],
            "role": row["role"],
            "tier": row["tier"],
            "origin": origins.get_user(row["name"]),
        }
        if include_hashes:
            entry["password_hash"] = row.get("pass_hash", "")
        users.append(entry)
    users.sort(key=lambda u: u["name"])

    acl: list[dict[str, Any]] = []
    for rule in db.list_acl():
        user = db_user_to_api(rule["user"])
        acl.append(
            {
                "user": user,
                "topic": rule["topic"],
                "permission": rule["permission"],
                "origin": origins.get_acl(user, rule["topic"]),
            }
        )
    acl.sort(key=lambda r: (r["user"], r["topic"]))

    tokens: list[dict[str, Any]] = []
    for tok in db.list_tokens():
        expires = int(tok["expires"])
        tokens.append(
            {
                "user": tok["user"],
                "label": tok["label"],
                "expires": iso_utc(expires) if expires else None,
                "origin": origins.get_token(tok["user"], tok["token_id"]),
            }
        )
    tokens.sort(key=lambda t: (t["user"], t["label"], t["expires"] or ""))

    return {
        "schema": SCHEMA_VERSION,
        "generated_at": iso_utc(now),
        "source": {"addon": "ntfy", "auth_schema": SUPPORTED_AUTH_SCHEMA},
        "server": {"auth_default_access": auth_default_access},
        "users": users,
        "acl": acl,
        "tokens": tokens,
    }


def to_json(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


# --- minimal deterministic YAML emitter (PyYAML is not part of the image) --------------------------------------------

_PLAIN_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return json.dumps(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"unsupported value type: {type(value).__name__}")


def _key(key: Any) -> str:
    text = str(key)
    return text if _PLAIN_KEY_RE.match(text) else json.dumps(text, ensure_ascii=False)


def _emit(value: Any, indent: int) -> list[str]:
    """Lines for a mapping or list at the given indentation (never a bare scalar)."""
    pad = "  " * indent
    lines: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, dict) and item:
                lines.append(f"{pad}{_key(key)}:")
                lines.extend(_emit(item, indent + 1))
            elif isinstance(item, list) and item:
                lines.append(f"{pad}{_key(key)}:")
                lines.extend(_emit(item, indent + 1))
            else:
                lines.append(f"{pad}{_key(key)}: {_inline(item)}")
    else:
        for item in value:
            if isinstance(item, dict) and item:
                inner = _emit(item, indent + 1)
                lines.append(f"{pad}- {inner[0].lstrip()}")
                lines.extend(inner[1:])
            elif isinstance(item, list) and item:
                inner = _emit(item, indent + 1)
                lines.append(f"{pad}- {inner[0].lstrip()}")
                lines.extend(inner[1:])
            else:
                lines.append(f"{pad}- {_inline(item)}")
    return lines


def _inline(value: Any) -> str:
    if isinstance(value, dict):
        return "{}"
    if isinstance(value, list):
        return "[]"
    return _scalar(value)


def to_yaml(doc: dict[str, Any]) -> str:
    return "\n".join(_emit(doc, 0)) + "\n"
