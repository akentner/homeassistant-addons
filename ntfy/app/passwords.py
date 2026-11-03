"""Guard against placeholder passwords in the options (they must never become real accounts).

An unresolved `!secret` reference, an empty value, the username itself or a very short value is almost always a
placeholder that was meant to be replaced; creating the account with it would leave a weak credential behind (2026-11-03
incident). The reason strings never contain the password.
"""

from __future__ import annotations

MIN_LENGTH = 8


def password_problem(username: str, password: str) -> str | None:
    """Return why `password` must not be used for `username`, or None when it is acceptable."""
    if not password:
        return "password is empty"
    if password.lstrip().startswith("!secret"):
        return "password is an unresolved !secret reference"
    if password.strip().lower() == username.strip().lower():
        return "password equals the username"
    if len(password) < MIN_LENGTH:
        return f"password is shorter than {MIN_LENGTH} characters"
    return None
