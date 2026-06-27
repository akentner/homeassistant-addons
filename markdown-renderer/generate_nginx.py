#!/usr/bin/env python3
"""Generate nginx.conf + per-namespace index.html from HA options.json.

Reads /data/options.json with shape:

    {
      "directories": [{"name": str, "path": str}, ...],
      "kroki_url": "https://kroki.io"
    }

Validates namespace names, writes /tmp/nginx.conf and a per-namespace
/tmp/docroots/<name>/index.html plus a landing page at /tmp/landing/index.html.

The generated index.html sets Docsify basePath from window.location.pathname
at page-load time (so .md XHRs resolve correctly under HA Ingress) and ships
inline mermaid + Kroki dispatcher plugins that target fenced code blocks.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

# Paths — these mirror the runtime layout built by the Dockerfile.
OPTIONS_PATH = Path("/data/options.json")
NGINX_CONF_PATH = Path("/tmp/nginx.conf")
DOCROOTS_DIR = Path("/tmp/docroots")
LANDING_DIR = Path("/tmp/landing")
APP_DIR = Path("/app")
ASSETS_DIR = APP_DIR / "_docsify"  # served by nginx at /_docsify/

# Regex for namespace name validation (per MULTI-05 + DOCS.md documentation):
#   - starts with lowercase letter or digit
#   - contains lowercase letters, digits, hyphens
#   - 1-63 chars
NAME_RE = __import__("re").compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
RESERVED_NAMES = {"_docsify", "api", "data", "share", "config", "media"}

DEFAULT_KROKI_URL = "https://kroki.io"

# Per-namespace Docsify index.html template.
# {name} / {name_display} / {kroki_url} are filled in at render time via .format().
# The mermaid + Kroki plugins are inlined so the page works without any extra
# vendored plugin file. Script tags reference ../_docsify/ (relative path)
# because each index.html lives one level below the nginx web root.
INDEX_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{name_display}</title>
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <link rel="stylesheet" href="../_docsify/themes/vue.css">
  <script>
    // Docsify global config. basePath derived from window.location.pathname
    // so .md fetches resolve correctly under HA Ingress prefix.
    window.$docsify = window.$docsify || {{}};
    window.$docsify.basePath = window.location.pathname.replace(/\\/?$/, '/');
    window.$docsify.name = {name_json};
    window.$docsify.homepage = 'README.md';
    // Mermaid renderer plugin: rewrites fenced ```mermaid blocks and triggers
    // mermaid.run() after each Docsify page render (INGRESS-05).
    window.$docsify.plugins = (window.$docsify.plugins || []).concat([
      function mermaidHook(hook) {{
        hook.afterEach(function (html) {{
          return html.replace(
            /<p><code class="language-mermaid">([\\s\\S]*?)<\\/code><\\/p>/g,
            '<pre class="mermaid">$1</pre>'
          );
        }});
        hook.doneEach(function () {{
          if (window.mermaid) {{
            window.mermaid.run();
          }}
        }});
      }}
    ]);
    // Inject Kroki URL so the Kroki dispatcher plugin below can read it.
    window.MARKDOWN_RENDERER = {{ krokiUrl: {kroki_url_json} }};
  </script>
</head>
<body>
  <div id="app">Loading {name_display}...</div>
  <script src="../_docsify/docsify.min.js"></script>
  <script src="../_docsify/mermaid.min.js"></script>
  <script>
    if (window.mermaid) {{
      window.mermaid.initialize({{ startOnLoad: false, securityLevel: 'loose' }});
    }}
    // Kroki dispatcher plugin: convert non-mermaid fenced code blocks to <img>
    // tags pointing at <kroki_url>/<format>/svg/<base64-deflate source>.
    // Uses browser-native CompressionStream (deflate) + btoa (base64) - no
    // external library required. On fetch failure, the original <pre><code>
    // block is preserved (KROKI-05 graceful degradation).
    (function () {{
      var krokiUrl = (window.MARKDOWN_RENDERER && window.MARKDOWN_RENDERER.krokiUrl) || '{default_kroki_url}';
      function toFlateBase64(str) {{
        return new Promise(function (resolve, reject) {{
          try {{
            var cs = new CompressionStream('deflate');
            var writer = cs.writable.getWriter();
            writer.write(new TextEncoder().encode(str));
            writer.close();
            var chunks = [];
            cs.readable.pipeTo(new WritableStream({{
              write: function (c) {{ chunks.push(c); }}
            }})).then(function () {{
              var bin = new Uint8Array(chunks.reduce(function (a, c) {{ return a + c.length; }}, 0));
              var off = 0;
              chunks.forEach(function (c) {{ bin.set(c, off); off += c.length; }});
              var binStr = '';
              for (var i = 0; i < bin.length; i++) {{
                binStr += String.fromCharCode(bin[i]);
              }}
              resolve(btoa(binStr));
            }}).catch(reject);
          }} catch (e) {{ reject(e); }}
        }});
      }}
      function plugin(hook) {{
        hook.doneEach(function () {{
          var blocks = document.querySelectorAll('pre>code[class^="language-"]:not(.language-mermaid)');
          blocks.forEach(function (code) {{
            var lang = (code.className.match(/language-([\\w-]+)/) || [])[1];
            if (!lang) {{ return; }}
            var src = code.textContent;
            toFlateBase64(src).then(function (b64) {{
              var img = document.createElement('img');
              img.src = krokiUrl + '/' + lang + '/svg/' + b64;
              img.alt = lang + ' diagram';
              img.loading = 'lazy';
              var pre = code.parentNode;
              if (pre && pre.parentNode) {{
                pre.parentNode.replaceChild(img, pre);
              }}
            }}).catch(function (err) {{
              console.warn('Kroki render failed for', lang, err);
            }});
          }});
        }});
      }}
      window.$docsify = window.$docsify || {{}};
      window.$docsify.plugins = (window.$docsify.plugins || []).concat([plugin]);
    }})();
  </script>
</body>
</html>
"""

# Landing page template — one card per namespace.
# {cards} is filled in with one <a class="card">...</a> per namespace entry.
LANDING_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Markdown Renderer</title>
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0; padding: 2rem; background: #fafafa; color: #2c3e50; }}
    h1 {{ font-weight: 300; margin-bottom: 2rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
             gap: 1rem; max-width: 1200px; }}
    .card {{ display: block; padding: 1.5rem; background: #fff; border-radius: 8px;
             box-shadow: 0 2px 4px rgba(0,0,0,0.08); text-decoration: none; color: inherit;
             transition: transform 0.15s, box-shadow 0.15s; }}
    .card:hover {{ transform: translateY(-2px);
                   box-shadow: 0 4px 12px rgba(0,0,0,0.12); }}
    .card h2 {{ margin: 0 0 0.5rem; font-size: 1.25rem; color: #2c3e50; }}
    .card p {{ margin: 0; color: #7f8c8d; font-family: monospace; font-size: 0.875rem; }}
  </style>
</head>
<body>
  <h1>Markdown Renderer</h1>
  <div class="grid">
{cards}
  </div>
</body>
</html>
"""

LANDING_CARD_TEMPLATE = """    <a href="/{name}/" class="card">
      <h2>{name}</h2>
      <p>{path}</p>
    </a>"""

# Per-namespace nginx location block (one entry per namespace).
# Renders the trailing-slash redirect (per INGRESS-04 + nginx semantics) plus
# the alias serving /tmp/docroots/<name>/. try_files falls back to index.html
# so SPA route refreshes work.
NGINX_NAMESPACE_BLOCK_TEMPLATE = """
    location = /{name} {{ return 301 /{name}/; }}
    location /{name}/ {{
      alias {docroots}/{name}/;
      try_files $uri $uri/ /index.html;
    }}"""


def _render_nginx(namespaces: list[dict]) -> str:
    """Render nginx.conf from the namespace list."""
    blocks = "\n".join(
        NGINX_NAMESPACE_BLOCK_TEMPLATE.format(name=ns["name"], docroots=DOCROOTS_DIR)
        for ns in namespaces
    )
    return f"""worker_processes 1;
error_log /dev/stderr warn;
pid /tmp/nginx.pid;

events {{
  worker_connections 512;
}}

http {{
  access_log /dev/stdout combined;
  client_max_body_size 32m;
  absolute_redirect off;

  server {{
    listen 8099;
    server_name localhost;

    # Vendored Docsify + Mermaid assets (relative path from any namespace root)
    location /_docsify/ {{
      alias {ASSETS_DIR}/;
    }}

    # Landing page at Ingress root (lists all configured namespaces)
    location = / {{
      root {LANDING_DIR};
      try_files /index.html =404;
    }}
    location / {{
      root {LANDING_DIR};
      try_files /index.html =404;
    }}
{blocks}
  }}
}}
"""


def _render_landing(namespaces: list[dict]) -> str:
    """Render the landing-page index.html with one card per namespace."""
    cards = "\n".join(
        LANDING_CARD_TEMPLATE.format(name=ns["name"], path=ns["path"])
        for ns in namespaces
    )
    return LANDING_HTML_TEMPLATE.format(cards=cards)


def _render_namespace_index(namespace: dict, kroki_url: str) -> str:
    """Render the Docsify index.html for a single namespace."""
    name = namespace["name"]
    # JSON-encode name + kroki_url so they survive inside an inline <script>.
    name_json = json.dumps(name)
    kroki_url_json = json.dumps(kroki_url)
    return INDEX_HTML_TEMPLATE.format(
        name=name,
        name_display=name,
        name_json=name_json,
        kroki_url_json=kroki_url_json,
        default_kroki_url=DEFAULT_KROKI_URL,
    )


def _validate_namespaces(directories: list) -> list[dict]:
    """Validate each namespace entry; raises SystemExit on any error."""
    valid: list[dict] = []
    for entry in directories:
        name = entry.get("name", "")
        path = entry.get("path", "")
        if not isinstance(name, str) or not isinstance(path, str):
            print(
                f"ERROR: directory entry must have string 'name' and 'path', got: {entry}",
                flush=True,
            )
            sys.exit(1)
        if not name:
            print(f"ERROR: directory name cannot be empty (path={path!r})", flush=True)
            sys.exit(1)
        if not NAME_RE.match(name):
            print(
                f"ERROR: directory name {name!r} must match {NAME_RE.pattern}",
                flush=True,
            )
            sys.exit(1)
        if name in RESERVED_NAMES:
            print(
                f"ERROR: directory name {name!r} is reserved (one of {sorted(RESERVED_NAMES)})",
                flush=True,
            )
            sys.exit(1)
        valid.append({"name": name, "path": path})
    # Check duplicate names
    seen: set[str] = set()
    for ns in valid:
        if ns["name"] in seen:
            print(f"ERROR: duplicate directory name {ns['name']!r}", flush=True)
            sys.exit(1)
        seen.add(ns["name"])
    return valid


def _write_minimal_nginx(reason: str) -> None:
    """Write a fallback nginx.conf that only serves /_docsify/ and a 503."""
    NGINX_CONF_PATH.parent.mkdir(parents=True, exist_ok=True)
    NGINX_CONF_PATH.write_text(
        f"""worker_processes 1;
error_log /dev/stderr warn;
pid /tmp/nginx.pid;
events {{ worker_connections 512; }}
http {{
  access_log /dev/stdout combined;
  absolute_redirect off;
  server {{
    listen 8099;
    server_name localhost;
    location /_docsify/ {{ alias {ASSETS_DIR}/; }}
    location / {{ return 503 'Markdown Renderer: {reason}\\n'; }}
  }}
}}
"""
    )


def main() -> int:
    """Entry point: read options, generate nginx.conf + index.html files."""
    if not OPTIONS_PATH.exists():
        print(
            f"WARNING: {OPTIONS_PATH} not found, writing minimal /tmp/nginx.conf",
            flush=True,
        )
        _write_minimal_nginx("no options.json mounted from HA Supervisor")
        return 0

    with OPTIONS_PATH.open() as f:
        options = json.load(f)

    directories = options.get("directories", [])
    kroki_url = options.get("kroki_url", DEFAULT_KROKI_URL).rstrip("/") or DEFAULT_KROKI_URL

    if not isinstance(directories, list):
        print(f"ERROR: 'directories' must be a list, got {type(directories).__name__}", flush=True)
        return 1

    if not directories:
        print(
            "WARNING: no directories configured, writing minimal /tmp/nginx.conf",
            flush=True,
        )
        _write_minimal_nginx("no directories configured")
        return 0

    namespaces = _validate_namespaces(directories)

    # Fresh output dirs each run — eliminates stale entries after config changes.
    for d in (DOCROOTS_DIR, LANDING_DIR):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    # Per-namespace index.html
    for ns in namespaces:
        ns_dir = DOCROOTS_DIR / ns["name"]
        ns_dir.mkdir(parents=True, exist_ok=True)
        (ns_dir / "index.html").write_text(_render_namespace_index(ns, kroki_url))

    # Landing page
    (LANDING_DIR / "index.html").write_text(_render_landing(namespaces))

    # nginx.conf
    NGINX_CONF_PATH.write_text(_render_nginx(namespaces))

    # Validate the generated config with nginx -t (best-effort: skip if nginx
    # binary is unavailable, e.g. during local dry-run without the add-on image).
    try:
        result = subprocess.run(
            ["nginx", "-t", "-c", str(NGINX_CONF_PATH)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"ERROR: nginx -t failed:\n{result.stderr}", flush=True)
            return 1
    except FileNotFoundError:
        print(
            "WARNING: nginx binary not found, skipping config validation",
            flush=True,
        )

    print(
        f"Generated nginx config for {len(namespaces)} namespace(s) at "
        f"{NGINX_CONF_PATH} (kroki_url={kroki_url})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
