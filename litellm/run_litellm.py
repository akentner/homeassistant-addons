#!/usr/bin/env python3
"""Litellm proxy wrapper that allows HA ingress framing.

Background: HA Supervisor's ingress embeds add-on UIs in iframes.
The browser checks the inner frame's Content-Security-Policy
`frame-ancestors` directive to decide if the embedding is allowed.
Litellm 1.101.0's ProxyServer.setup_csp_headers() hardcodes
`frame-ancestors 'none'` (see litellm/proxy/proxy_server.py in the
1.101.0 tag), which blocks ALL framing — direct port access still
works (browser tabs, HA Conversation API calls), but HA's
sidebar ingress iframe is rejected by the browser with:

  Refused to display 'https://ha-nextgen.akentner.de/' in a frame
  because an ancestor violates the following Content Security
  Policy directive: "frame-ancestors 'none'"

Fix: subclass ProxyServer, override setup_csp_headers() with a
middleware that rewrites `frame-ancestors` to
`frame-ancestors 'self' <INGRESS_ORIGIN>` when INGRESS_ORIGIN is
set. If INGRESS_ORIGIN is empty, fall through to the parent
class's setup_csp_headers() (preserves the original 'none' CSP).

INGRESS_ORIGIN should be the bare HA origin (no trailing slash,
no path), e.g. `https://ha-nextgen.akentner.de` — the ingress
adds `/api/hassio_ingress/litellm/...` itself, so the frame-ancestor
check uses the embedding page's origin.

Usage (from run.sh):
    export INGRESS_ORIGIN="https://ha-nextgen.akentner.de"
    python3 /app/run_litellm.py
"""
import os
import re

from litellm.proxy.proxy_server import ProxyServer

INGRESS_ORIGIN = os.environ.get("INGRESS_ORIGIN", "").strip()


class HAIngressProxy(ProxyServer):
    """Subclass that overrides setup_csp_headers to allow HA ingress framing."""

    def setup_csp_headers(self):
        if not INGRESS_ORIGIN:
            super().setup_csp_headers()
            return

        @self.app.middleware("http")
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


proxy = HAIngressProxy(config="/data/litellm_config.yaml")
proxy.run()
