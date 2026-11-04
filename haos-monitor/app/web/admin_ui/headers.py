"""Security headers for every response of the admin-UI skeleton.

The CSP is a default, not yet a promise: whether HA's ingress frame lets it through unchanged is recorded by spike item
S9 (PD-07). Consumers can pass `csp=None` to `make_server` to switch it off. No frame-blocking header is ever sent
because HA frames the page; CSP `frame-ancestors` replaces it.
"""

from __future__ import annotations

DEFAULT_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'self'"
)


def security_headers(kind: str, csp: str | None) -> dict[str, str]:
    """Headers for a response of `kind` ("html", "static" or "api"); the CSP only goes on html and static."""
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "same-origin",
    }
    if kind in ("html", "static") and csp is not None:
        headers["Content-Security-Policy"] = csp
    return headers
