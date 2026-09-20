#!/usr/bin/env python3
"""Litellm proxy wrapper that allows HA ingress framing.

Background: HA Supervisor's ingress embeds add-on UIs in iframes.
The browser checks the inner frame's Content-Security-Policy
`frame-ancestors` directive. Litellm 1.101.0's proxy_server.py
hardcodes `frame-ancestors 'none'` in ProxyServer.setup_csp_headers()
(no upstream config knob, no env var override). Litellm exports
the FastAPI `app` instance from `litellm.proxy.proxy_server` but
no `ProxyServer` class — so a subclass override isn't possible.
The cleanest hook is HTTP middleware on `app` that rewrites
`frame-ancestors` on every response when $INGRESS_ORIGIN is set.

Two middleware are wired (in order, both no-ops when their env
vars are empty):

  1. CSP-override: rewrites `frame-ancestors 'none'` →
     `frame-ancestors 'self' <INGRESS_ORIGIN>`. Fixes the
     "Refused to display in a frame because an ancestor
     violates the CSP directive: frame-ancestors 'none'" error.

  2. Root-redirect: rewrites GET / (the litellm proxy root)
     to redirect to /ui (the modern Litellm UI). Without this,
     HA's ingress shows the legacy Swagger UI at /, which has
     static asset paths at `/swagger/...` that get mangled by
     the ingress proxy (404 / text/plain MIME mismatch on
     swagger-ui-bundle.js). /ui is the modern UI which has
     proper reverse-proxy-aware asset paths.

Usage:
    export INGRESS_ORIGIN="https://ha-nextgen.akentner.de"
    python3 /app/run_litellm.py

INGRESS_ORIGIN is the bare HA origin (no trailing slash, no path).
"""
import os
import re

import uvicorn
from fastapi.responses import RedirectResponse
from litellm.proxy.proxy_server import app

INGRESS_ORIGIN = os.environ.get("INGRESS_ORIGIN", "").strip()


if INGRESS_ORIGIN:
    @app.middleware("http")
    async def csp_ingress_override(request, call_next):
        response = await call_next(request)
        existing = response.headers.get("Content-Security-Policy")
        if existing:
            response.headers["Content-Security-Policy"] = re.sub(
                r"frame-ancestors [^;]+",
                f"frame-ancestors 'self' {INGRESS_ORIGIN}",
                existing,
            )
        return response


# Root redirect: GET / → /ui (only when INGRESS_ORIGIN is set,
# otherwise direct-port users get the upstream default which is
# the Swagger UI at /). 307 preserves the request method for
# relative links from the redirected page. URL is RELATIVE
# ("ui", no leading slash) — an absolute path ("/ui") would
# resolve against the browser's origin (e.g.
# https://ha-nextgen.akentner.de/ui) and miss the
# /api/hassio_ingress/litellm/ ingress prefix → 404 from HA.
# Relative resolution against the current URL keeps the
# ingress path: https://ha-nextgen.akentner.de/api/hassio_ingress/
# litellm/ui.
if INGRESS_ORIGIN:
    @app.middleware("http")
    async def root_redirect_to_ui(request, call_next):
        if request.url.path in ("/", ""):
            return RedirectResponse(url="ui", status_code=307)
        return await call_next(request)


uvicorn.run(
    app,
    host="0.0.0.0",
    port=4000,
    log_level="info",
    # HA Supervisor ingress proxies over the internal Docker HTTP
    # network and forwards X-Forwarded-Proto: https. Without
    # proxy_headers=True uvicorn (and therefore Litellm) ignores
    # that header and sees the request as plain http://, which
    # makes Litellm's UI render iframe src as
    # http://ha-nextgen.akentner.de/ui/ — browsers then block it
    # as mixed content (parent page is https://, iframe is http://).
    # Trusting proxy headers fixes the scheme Litellm uses for
    # absolute-URL generation in its UI.
    proxy_headers=True,
)
