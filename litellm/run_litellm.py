#!/usr/bin/env python3
"""Litellm proxy wrapper that allows HA ingress framing.

Background: HA Supervisor's ingress embeds add-on UIs in iframes.
The browser checks the inner frame's Content-Security-Policy
`frame-ancestors` directive. Litellm 1.101.0's proxy_server.py
hardcodes `frame-ancestors 'none'` in ProxyServer.setup_csp_headers()
(no upstream config knob, no env var override). Litellm exports
the FastAPI `app` instance from `litellm.proxy.proxy_server` but
no `ProxyServer` class — so a subclass override isn't possible.
The cleanest hook is an HTTP middleware on `app` that rewrites
`frame-ancestors` on every response when $INGRESS_ORIGIN is set.

Pattern: setup_csp_headers runs at import-time; our middleware
runs after on every response and overwrites the header.

Usage:
    export INGRESS_ORIGIN="https://ha-nextgen.akentner.de"
    python3 /app/run_litellm.py

INGRESS_ORIGIN is the bare HA origin (no trailing slash, no path).
"""
import os
import re

import uvicorn
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


uvicorn.run(app, host="0.0.0.0", port=4000, log_level="info")
