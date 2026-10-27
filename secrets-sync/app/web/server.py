"""Web UI and JSON API of Secrets Sync (see docs/SPEC.md, "Web <-> engine").

Reads the state file on every request and talks to the supervisor only through the Controller
protocol. Pages use relative links only (Home Assistant ingress prefix) and no external assets.
"""

from __future__ import annotations

import html
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app.controller import Controller

INGRESS_REMOTE = "172.30.32.2"
MAX_EVENTS = 50
MAX_KEYS = 500

_CSS = """
:root{color-scheme:light dark;--bg:#fafafa;--fg:#1c1c1c;--card:#fff;--bd:#d8d8d8;--mut:#666;
--ok:#1a7f37;--warn:#9a6700;--err:#cf222e;--acc:#0969da}
@media(prefers-color-scheme:dark){:root{--bg:#161616;--fg:#e6e6e6;--card:#212121;--bd:#3a3a3a;--mut:#9a9a9a;
--ok:#3fb950;--warn:#d29922;--err:#f85149;--acc:#58a6ff}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif}
h1{font-size:20px;margin:0 0 12px}h2{font-size:15px;margin:0 0 8px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:8px;padding:12px;margin:0 0 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}
.k{color:var(--mut);font-size:12px}.badge{font-weight:600}
.ok{color:var(--ok)}.degraded,.stale,.starting,.warning{color:var(--warn)}.error{color:var(--err)}
table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:4px 8px;border-bottom:1px solid var(--bd)}
code{font-family:ui-monospace,monospace;font-size:12px;word-break:break-all}
button{background:var(--acc);color:#fff;border:0;border-radius:6px;padding:6px 14px;margin-right:8px;cursor:pointer}
button:disabled{opacity:.5}pre{white-space:pre-wrap;word-break:break-all;margin:8px 0 0}
"""

_JS = """
async function act(url, label) {
  const out = document.getElementById('result');
  out.textContent = label + ' ...';
  try {
    const r = await fetch(url, {method: 'POST'});
    const t = await r.text();
    out.textContent = r.status + ' ' + t;
    if (url.startsWith('api/sync') && r.ok) { setTimeout(() => location.reload(), 3000); }
  } catch (e) { out.textContent = 'request failed'; }
}
"""


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def read_state(path: Path) -> dict[str, Any]:
    """Return the parsed state, or {} when missing, partial or not a JSON object."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _is_stale(state: dict[str, Any]) -> bool:
    if state.get("stale") is True:
        return True
    age, interval = state.get("age_seconds"), state.get("interval")
    if isinstance(age, int) and isinstance(interval, int) and not isinstance(age, bool):
        return age > 2 * interval
    return False


def health(state: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    status = state.get("status") if isinstance(state.get("status"), str) else "starting"
    stale = _is_stale(state)
    body = {
        "status": status,
        "age_seconds": state.get("age_seconds"),
        "stale": stale,
        "items": state.get("items"),
        "error_code": state.get("error_code"),
    }
    return (200 if status == "ok" and not stale else 503), body


def _keys_list(names: Any) -> str:
    items = [str(n) for n in _as_list(names)]
    if not items:
        return '<span class="k">-</span>'
    shown = "".join(f"<code>{_e(n)}</code> " for n in items[:MAX_KEYS])
    more = f' <span class="k">+{len(items) - MAX_KEYS} more</span>' if len(items) > MAX_KEYS else ""
    return shown + more


def render_page(state: dict[str, Any]) -> str:
    status = state.get("status") if isinstance(state.get("status"), str) else "starting"
    code, _ = health(state)
    shown_status = "stale" if status == "ok" and code == 503 else status
    versions = _as_dict(state.get("versions"))
    keys = _as_dict(state.get("keys"))

    def stat(label: str, value: Any) -> str:
        return f'<div><div class="k">{_e(label)}</div><div>{_e(value) if value not in (None, "") else "-"}</div></div>'

    parts = [
        "<h1>Secrets Sync</h1>",
        '<div class="card"><div class="grid">',
        f'<div><div class="k">Status</div><div class="badge {_e(shown_status)}">{_e(shown_status)}</div></div>',
        stat("Last sync", state.get("last_success_at")),
        stat("Last attempt", state.get("last_attempt_at")),
        stat("Next sync", state.get("next_sync_at")),
        stat("Items", state.get("items")),
        stat("Error", state.get("error_code")),
        stat("Version", versions.get("addon")),
        stat("bw", versions.get("bw")),
        stat("sops", versions.get("sops")),
        "</div></div>",
        '<div class="card"><button type="button" onclick="act(\'api/sync\',\'Sync\')">Sync now</button>'
        '<button type="button" onclick="act(\'api/preview\',\'Preview\')">Preview</button>'
        '<pre id="result"></pre></div>',
    ]

    rows = []
    for name, prov in sorted(_as_dict(state.get("providers")).items()):
        prov = _as_dict(prov)
        pstatus = prov.get("status") if isinstance(prov.get("status"), str) else "unknown"
        problems = "<br>".join(
            f"{_e(_as_dict(p).get('severity'))}: <code>{_e(_as_dict(p).get('code'))}</code> "
            f"{_e(_as_dict(p).get('message'))}"
            for p in _as_list(prov.get("problems"))
        )
        rows.append(
            f"<tr><td>{_e(name)}</td><td class=\"{_e(pstatus)}\">{_e(pstatus)}</td><td>{_e(prov.get('items'))}</td>"
            f"<td>{_e(prov.get('last_success_at'))}</td><td>{_e(prov.get('error_code'))}</td><td>{problems}</td></tr>"
        )
    body = "".join(rows) or '<tr><td colspan="6" class="k">no providers reported yet</td></tr>'
    parts.append(
        '<div class="card"><h2>Providers</h2><table><tr><th>Provider</th><th>Status</th><th>Items</th>'
        f"<th>Last success</th><th>Error</th><th>Problems</th></tr>{body}</table></div>"
    )

    parts.append(
        '<div class="card"><h2>Keys</h2><table>'
        f"<tr><th>Added</th><td>{_keys_list(keys.get('added'))}</td></tr>"
        f"<tr><th>Removed</th><td>{_keys_list(keys.get('removed'))}</td></tr>"
        f"<tr><th>Changed</th><td>{_keys_list(keys.get('changed'))}</td></tr>"
        f"<tr><th>All ({len(_as_list(keys.get('names')))})</th><td>{_keys_list(keys.get('names'))}</td></tr>"
        "</table></div>"
    )

    ev_rows = []
    for ev in _as_list(state.get("events"))[:MAX_EVENTS]:
        ev = _as_dict(ev)
        level = ev.get("level") if isinstance(ev.get("level"), str) else ""
        ev_rows.append(
            f"<tr><td>{_e(ev.get('at'))}</td><td class=\"{_e(level)}\">{_e(level)}</td>"
            f"<td><code>{_e(ev.get('code'))}</code></td><td>{_e(ev.get('message'))}</td></tr>"
        )
    ev_body = "".join(ev_rows) or '<tr><td colspan="4" class="k">no events</td></tr>'
    parts.append(
        '<div class="card"><h2>Events</h2><table><tr><th>Time</th><th>Level</th><th>Code</th><th>Message</th></tr>'
        f"{ev_body}</table></div>"
    )

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Secrets Sync</title><style>{_CSS}</style></head><body>{''.join(parts)}"
        f"<script>{_JS}</script></body></html>"
    )


def make_handler(
    controller: Controller, state_path: Path, ingress_only: bool = True, ingress_remote: str = INGRESS_REMOTE
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "SecretsSync"
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - quiet, no query strings logged
            return

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: Any) -> None:
            self._send(code, json.dumps(payload, sort_keys=True).encode(), "application/json; charset=utf-8")

        def _is_ingress(self) -> bool:
            if not ingress_only:
                return True
            return self.client_address[0] == ingress_remote and bool(self.headers.get("X-Ingress-Path"))

        def do_GET(self) -> None:  # noqa: N802
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/health":
                code, body = health(read_state(state_path))
                self._json(code, body)
            elif path == "/api/status.json":
                self._json(200, read_state(state_path))
            elif path == "/":
                if ingress_only and not self._is_ingress():
                    # Page is meant for ingress; the optional TCP port exposes only the JSON endpoints.
                    self._json(403, {"error": "ingress_only"})
                    return
                self._send(200, render_page(read_state(state_path)).encode(), "text/html; charset=utf-8")
            else:
                self._json(404, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            parts = urllib.parse.urlsplit(self.path)
            if parts.path not in ("/api/sync", "/api/preview"):
                self._json(404, {"error": "not_found"})
                return
            if not self._is_ingress():
                self._json(403, {"error": "ingress_only"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(min(length, 65536))
            try:
                if parts.path == "/api/preview":
                    self._json(200, controller.preview())
                    return
                force = urllib.parse.parse_qs(parts.query).get("force") == ["1"]
                started = bool(controller.trigger_sync(force=force))
            except Exception:  # noqa: BLE001 - never leak exception text, it may carry provider output
                self._json(500, {"error": "internal_error"})
                return
            if started:
                self._json(202, {"started": True})
            else:
                self._json(429, {"started": False, "error": "rate_limited"})

    return Handler


def make_server(
    controller: Controller,
    state_path: Path | str,
    port: int,
    ingress_only: bool = True,
    host: str = "0.0.0.0",
    ingress_remote: str = INGRESS_REMOTE,
) -> ThreadingHTTPServer:
    handler = make_handler(controller, Path(state_path), ingress_only, ingress_remote)
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def serve(controller: Controller, state_path: Path | str, port: int, ingress_only: bool = True) -> None:
    """Blocking; run in a thread by app/main.py."""
    make_server(controller, state_path, port, ingress_only).serve_forever()
