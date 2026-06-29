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

import hashlib
import json
import re
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
ASSETS_DIR = APP_DIR / "_static"  # served by nginx at /_static/ and /<ns>/_static/
# Temp dirs nginx needs to write during request handling. We point them all
# at /tmp/nginx-tmp/ so ``nginx -t`` succeeds in non-root dev environments
# (the default /var/lib/nginx/* paths require root + write access).
NGINX_TMP_DIR = Path("/tmp/nginx-tmp")
NGINX_CLIENT_BODY_TMP = NGINX_TMP_DIR / "client_body"
NGINX_PROXY_TMP = NGINX_TMP_DIR / "proxy"
NGINX_FASTCGI_TMP = NGINX_TMP_DIR / "fastcgi"
NGINX_UWSGI_TMP = NGINX_TMP_DIR / "uwsgi"
NGINX_SCGI_TMP = NGINX_TMP_DIR / "scgi"

# Namespace-name validation (per MULTI-05 + 04-RESEARCH.md section 5):
#   - starts with lowercase letter or digit
#   - contains lowercase letters, digits, hyphens
#   - 1-63 chars total (DNS-label friendly)
VALID_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
# Backwards-compatible alias for the regex constant.
NAME_RE = VALID_NAME_RE

# Names that conflict with nginx location paths, vendored assets, or HA
# Supervisor's ingress / config / share / media volumes. Promoting to a
# frozenset so it is hashable and immutable for the duration of the run.
# Names that conflict with nginx location paths, vendored assets, or HA
# Supervisor's ingress / config / share / media volumes. Promoting to a
# frozenset so it is hashable and immutable for the duration of the run.
# ``_static`` is reserved because nginx exposes both ``/_static/`` (global)
# and ``/<ns>/_static/`` (per-namespace) location blocks that serve the
# vendored Docsify + Mermaid assets. A user namespace named ``static`` or
# ``_static`` would have its Markdown shadowed by vendored files (and any
# nested directory under it would have its first segment remapped to the
# vendored asset path).
RESERVED_NAMES = frozenset({"_static", "api", "data", "share", "config", "media"})

DEFAULT_KROKI_URL = "https://kroki.io"

# Per-namespace Docsify index.html template.
# {name} / {name_display} / {kroki_url} are filled in at render time via .format().
# The mermaid + Kroki plugins are inlined so the page works without any extra
# vendored plugin file. Script tags reference ``_static/`` (relative path)
# because nginx exposes the vendored assets under both ``/_static/`` (global)
# and ``/<ns>/_static/`` (per-namespace). When the browser is at
# ``/api/hassio_ingress/<token>/<ns>/``, a relative ``_static/foo`` resolves
# to ``/api/hassio_ingress/<token>/<ns>/_static/foo`` which is exactly the
# nginx per-namespace static location. This sidesteps the SPA-fallback trap
# where requests like ``/docs/_docsify/docsify.min.js`` matched the broader
# ``location /docs/`` and returned the HTML bootstrapper instead of the JS.
# Declared as a raw string so JS regex backslashes (``\s``, ``\/``, ``\w``)
# round-trip unchanged and Python 3.14+ does not emit a SyntaxWarning for
# the old ``\\/`` escape. ``{{`` / ``}}`` are still doubled so ``.format()``
# emits the literal braces the generated HTML needs.
INDEX_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{name_display}</title>
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <base href="./">
  <script>
    // Expose basePath to Docsify so its .md fetches resolve against the
    // namespace root rather than the deep URL. Computed from
    // ``window.location.pathname`` by stripping any doubled namespace
    // segments (HA Dashboard iframe preloads can produce paths like
    // ``/.../docs/docs/``).
    var __MR_PATH__ = window.location.pathname;
    var __MR_NS__ = {name_json};
    var __MR_TAG__ = '/' + __MR_NS__ + '/';
    var __MR_IDX__ = __MR_PATH__.indexOf(__MR_TAG__);
    var __MR_BASE__;
    if (__MR_IDX__ >= 0) {{
      __MR_BASE__ = __MR_PATH__.substring(0, __MR_IDX__ + __MR_TAG__.length);
    }} else if (__MR_PATH__.length >= __MR_NS__.length &&
               __MR_PATH__.substring(__MR_PATH__.length - __MR_NS__.length) === __MR_NS__) {{
      __MR_BASE__ = __MR_PATH__ + '/';
    }} else if (/\.[^\/]+$/.test(__MR_PATH__)) {{
      __MR_BASE__ = __MR_PATH__.replace(/\/[^\/]+$/, '/');
    }} else {{
      __MR_BASE__ = __MR_PATH__;
    }}
    window.$docsify = window.$docsify || {{}};
    window.$docsify.basePath = __MR_BASE__;
  </script>
  <link rel="stylesheet" href="_static/themes/vue.css">
{css_url_html}
{css_inline_html}
  <script>
    window.$docsify.name = {name_json};
    window.$docsify.homepage = 'README.md';
    // Mermaid renderer plugin. Three phases:
    //   1. afterEach: rewrite Docsify's ``<pre v-pre data-lang="mermaid"><code
    //      class="lang-mermaid">`` into ``<pre class="mermaid">`` so mermaid
    //      picks them up on its next .run() call. Docsify 4.x renders fenced
    //      code blocks with the ``lang-`` prefix (``<code class="lang-foo">``)
    //      - NOT ``language-foo`` as marked.js' default `langPrefix` would
    //      produce. The previous ``language-mermaid`` selector matched zero
    //      blocks under Docsify 4.x and the resulting silence (no error, no
    //      log, no rendered SVG) was nearly impossible to diagnose from the
    //      Browser DevTools console alone.
    //   2. doneEach: defer one animation frame so Docsify has committed the
    //      DOM, then call mermaid.run with the explicit node list
    //      (Mermaid 11+ returns a Promise; older versions take no args
    //      and ignore the option).
    //   3. After a successful render, mark nodes with ``data-processed`` so
    //      subsequent doneEach calls do not re-render the same diagrams.
    //
    // All three phases log to ``console`` with the ``[markdown-renderer]``
    // prefix so the Browser DevTools console makes it obvious which logs
    // came from this plugin (helpful when the rendered diagram itself
    // looks wrong and you need to know what input mermaid got).
    window.$docsify.plugins = (window.$docsify.plugins || []).concat([
      function mermaidHook(hook) {{
        hook.afterEach(function (html) {{
          var beforeCount = (html.match(/class="lang-mermaid"/g) || []).length;
          var replaced = html.replace(
            /<pre[^>]*>\s*<code class="lang-mermaid">([\s\S]*?)<\/code>\s*<\/pre>/g,
            '<pre class="mermaid">$1</pre>'
          );
          var afterCount = (replaced.match(/<pre class="mermaid">/g) || []).length;
          if (beforeCount > 0) {{
            console.log('[markdown-renderer] mermaid: found', beforeCount,
              'lang-mermaid block(s), replaced', afterCount);
          }} else if (/```mermaid/i.test(html) || /mermaid/i.test(html)) {{
            // Defensive log: the HTML mentions ``mermaid`` but our lang-
            // prefix regex did not match. Without this log, a future
            // Docsify upgrade that changes the class prefix would silently
            // break rendering and the only console evidence would be the
            // missing "found N block(s)" line. Log the first 200 chars of
            // any <code> tag we can find so the operator can confirm the
            // mismatch at a glance instead of re-running with debug flags.
            var codeSample = (html.match(/<code[^>]*>/) || ['<none>'])[0];
            console.warn('[markdown-renderer] mermaid: HTML mentions ' +
              '"mermaid" but no lang-mermaid block was matched - the ' +
              'first <code> tag we see is:', codeSample);
          }}
          return replaced;
        }});
        hook.doneEach(function () {{
          requestAnimationFrame(function () {{
            var nodes = document.querySelectorAll(
              'pre.mermaid:not([data-processed])'
            );
            if (nodes.length === 0) return;
            if (!window.mermaid) {{
              console.error('[markdown-renderer] mermaid.run() called but ' +
                'window.mermaid is undefined - did the script load fail?');
              return;
            }}
            console.log('[markdown-renderer] mermaid.run() scanning, found',
              nodes.length, 'unprocessed node(s)');
            try {{
              // Build the Mermaid run-options object step-by-step so the
              // template can be safely fed through Python's str.format().
              // A literal JS object literal here would be parsed by
              // str.format as a format field and raise KeyError - so we
              // assign each key separately.
              var mermaidOpts = {{}};
              mermaidOpts.nodes = Array.prototype.slice.call(nodes);
              var result = window.mermaid.run(mermaidOpts);
              // Mermaid 11+ returns a Promise; older versions return void.
              // We swallow either into a unified handler.
              if (result && typeof result.then === 'function') {{
                result.then(function () {{
                  nodes.forEach(function (n) {{
                    n.setAttribute('data-processed', 'true');
                  }});
                  console.log('[markdown-renderer] mermaid: rendered',
                    nodes.length, 'diagram(s)');
                }}).catch(function (err) {{
                  console.error('[markdown-renderer] mermaid error:', err);
                }});
              }} else {{
                // No Promise - assume synchronous success. Mark processed
                // optimistically (mermaid also sets data-processed internally,
                // so our :not([data-processed]) filter is doubly safe).
                nodes.forEach(function (n) {{
                  n.setAttribute('data-processed', 'true');
                }});
                console.log('[markdown-renderer] mermaid: dispatched',
                  nodes.length, 'diagram(s) (sync API)');
              }}
            }} catch (e) {{
              console.error(
                '[markdown-renderer] mermaid.run() threw synchronously:', e);
            }}
          }});
        }});
      }}
    ]);
    // Inject Kroki URL so the Kroki dispatcher plugin below can read it.
    // We assign the key separately to keep the template str.format()-safe
    // (a literal JS object literal here would be mis-parsed as a format
    // field by Python; see the mermaid.run() block below for the same
    // workaround).
    window.MARKDOWN_RENDERER = {{}};
    window.MARKDOWN_RENDERER.krokiUrl = {kroki_url_json};
  </script>
{plugin_scripts_html}
</head>
<body>
  <div id="app">Loading {name_display}...</div>
  <script src="_static/docsify.min.js"></script>
  <script src="_static/mermaid.min.js"></script>
  <script>
    if (window.mermaid) {{
      // Assign the init options one key at a time so str.format() does
      // not try to parse the object literal as a format field.
      var mermaidInit = {{}};
      mermaidInit.startOnLoad = false;
      mermaidInit.securityLevel = 'loose';
      window.mermaid.initialize(mermaidInit);
      // Mermaid 11.x does NOT expose a version field on ``mermaidAPI`` -
      // we previously logged ``version: unknown`` here which made the log
      // line look like an error to operators. Log the configuration that
      // we actually applied (startOnLoad + securityLevel read back from
      // ``getConfig()``) so the console entry stays informative without
      // implying broken-ness.
      //
      // Build a small ``readConfigField()`` helper instead of inlining the
      // ``&&`` chain, because the chain's falsy short-circuit (e.g.
      // ``startOnLoad === false`` is falsy) would silently rewrite a real
      // ``false`` value into the ``(unreadable)`` fallback - so operators
      // would see ``(unreadable)`` even when the value was read fine.
      var mermaidCfg = (window.mermaid && window.mermaid.mermaidAPI &&
        window.mermaid.mermaidAPI.getConfig &&
        typeof window.mermaid.mermaidAPI.getConfig === 'function'
        ? window.mermaid.mermaidAPI.getConfig() : null);
      console.log('[markdown-renderer] mermaid.initialize: done (startOnLoad=',
        (mermaidCfg && 'startOnLoad' in mermaidCfg) ? String(mermaidCfg.startOnLoad) : '(unreadable)',
        ', securityLevel=',
        (mermaidCfg && 'securityLevel' in mermaidCfg) ? mermaidCfg.securityLevel : '(unreadable)', ')');
    }} else {{
      console.error('[markdown-renderer] mermaid.min.js loaded but window.mermaid is undefined');
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
          // Whitelist of languages the Kroki dispatcher forwards. Every
          // other fenced code block (``js``, ``bash``, ``json``, ``yaml``,
          // ``python``, ``css``, ...) is left untouched so Prism syntax
          // highlighting and copy/paste still work as expected.
          //
          // We use an EXPLICIT whitelist instead of "match anything but
          // mermaid" for two reasons:
          //   1. Docsify 4.x emits ``<code class="lang-foo">`` for every
          //      fenced block. A broad ``[class^="lang-"]`` selector would
          //      intercept source code too and try to send it to Kroki,
          //      which only renders diagrams. Non-diagram languages get a
          //      4xx response or a useless image of an error message.
          //   2. Keeping an explicit list lets DOCS.md stay
          //      authoritative: changing this set is a deliberate code
          //      change reviewed alongside the docs.
          //
          // The list mirrors Kroki's documented diagram formats at
          // https://kroki.io/#diagrams (subset that supports ``.svg``
          // output and ``deflate + base64`` source). Mermaid is on the
          // list but explicitly excluded via the second selector - the
          // mermaid plugin handles mermaid and runs first.
          var KROKI_LANGS = [
            'plantuml', 'c4plantuml', 'salt', 'wireviz', 'pikchr',
            'svgbob', 'd2', 'graphviz', 'dot',
            'blockdiag', 'seqdiag', 'actdiag', 'nwdiag',
            'packetdiag', 'rackdiag',
            'ditaa', 'erd', 'excalidraw', 'nomnoml',
            'vega', 'vega-lite', 'wavedrom', 'bpmn', 'structurizr',
          ];
          // Build the selector from the whitelist so adding a new
          // language only requires editing the array above. The
          // ``.lang-mermaid`` exclusion remains so the mermaid plugin
          // stays the single owner of mermaid rendering even if a future
          // operator adds ``mermaid`` to KROKI_LANGS by mistake.
          var krokiSelector = 'pre>code.lang-' +
            KROKI_LANGS.join(', pre>code.lang-') +
            ':not(.lang-mermaid)';
          var blocks = document.querySelectorAll(krokiSelector);
          blocks.forEach(function (code) {{
            var classes = code.className.split(/\s+/);
            var lang = null;
            for (var i = 0; i < classes.length; i++) {{
              if (classes[i].indexOf('lang-') === 0) {{
                lang = classes[i].substring(5);
                break;
              }}
            }}
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
{plugin_registration_html}
</body>
</html>
"""

# Landing page template — one card per namespace.
# {cards} is filled in with one <a class="card">...</a> per namespace entry.
# Card hrefs are rewritten at runtime from window.location.pathname so they
# resolve correctly under HA Ingress (which prefixes every request with
# /api/hassio_ingress/<token>/). A literal "/{name}/" would 404 because HA strips
# the prefix before forwarding to the container — same reason Docsify sets
# basePath from window.location.pathname (INGRESS-02 in 04-CONTEXT.md).
# Declared as a raw string so JS regex backslashes like ``\/`` are not
# interpreted as Python escapes (would emit a SyntaxWarning on Python 3.14+
# under -W error::SyntaxWarning). Raw strings still let ``{{`` / ``}}``
# through unchanged; ``.format()`` converts them to the literal braces the
# generated HTML needs.
LANDING_HTML_TEMPLATE = r"""<!DOCTYPE html>
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
  <script>
    // Rewrite every card href to include the current request path prefix
    // (HA Ingress serves this add-on at /api/hassio_ingress/<token>/ — the
    // prefix is stripped server-side, so the container sees "/" but the
    // browser URL still contains the prefix). Without this, clicking a
    // card navigates to https://<ha-host>/<name>/ instead of the correct
    // /api/hassio_ingress/<token>/<name>/.
    //
    // The landing page is always served at the ingress root ("/"), so
    // ``window.location.pathname`` is the full ingress prefix. We just
    // normalise trailing slashes and prepend it to each relative card
    // href (``/docs/`` -> ``/api/hassio_ingress/<token>/docs/``).
    document.addEventListener('DOMContentLoaded', function () {{
      var prefix = window.location.pathname.replace(/\/?$/, '/');
      document.querySelectorAll('a.card').forEach(function (a) {{
        var href = a.getAttribute('href');
        if (href && href.charAt(0) === '/') {{
          a.setAttribute('href', prefix + href.replace(/^\/+/, ''));
        }}
      }});
    }});
  </script>
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
# the location that serves the configured Markdown directory (mounted from
# /config, /share or /media on the HA host) with a fallback to the generated
# Docsify SPA bootstrapper for SPA-style route refreshes. try_files order:
#   1. $uri       - serve the requested file from the configured path
#                   verbatim (e.g. /docs/README.md -> /config/docs/README.md).
#                   A missing file short-circuits to ``=404`` so nginx does
#                   NOT try directory autoindex (which would 403 because
#                   autoindex is off by default) and does NOT redirect into
#                   the wrong ``location /`` block when the fallback arm is
#                   a bare URI starting with ``/``.
#   2. @docsify_{name} - named-location redirect to the generated SPA
#                   bootstrapper. Using a named location instead of a bare
#                   URI fallback keeps nginx inside the namespace and
#                   avoids the cross-location redirect bug that served the
#                   landing page for every namespace URL.
# Why a named location instead of the bootstrapper file path? Nginx's
# ``try_files`` interprets the final arm as an internal URI, not a
# filesystem path. A bare ``/tmp/.../index.html`` starts with ``/`` so
# nginx re-enters location matching - and the bare ``location /``
# (landing page) won, serving the wrong page for any non-existent
# namespace path (e.g. /docs/missing.md). The named location ``@docsify``
# below is configured to serve the bootstrapper with no further matching.
#
# Three locations per namespace, ordered by prefix specificity:
#   1. ``/<ns>/_static/`` - vendored Docsify + Mermaid assets (longest
#      prefix, must match FIRST so requests like
#      /docs/_static/docsify.min.js resolve to /app/_static/docsify.min.js
#      and never fall into the broader ``/<ns>/`` block's SPA fallback).
#   2. ``/<ns>/``        - user Markdown files + SPA bootstrapper.
#   3. ``@docsify_<ns>`` - named-location SPA fallback (see above).
NGINX_NAMESPACE_BLOCK_TEMPLATE = """
    location = /{name} {{ return 301 /{name}/; }}
    location /{name}/_static/ {{
      alias {assets_dir}/;
      add_header Cache-Control "no-store" always;
    }}
    location /{name}/ {{
      alias {source_path}/;
      try_files $uri @docsify_{name};
      add_header Cache-Control "no-store" always;
    }}
    location @docsify_{name} {{
      root {docroots}/{name};
      try_files /index.html =404;
      add_header Cache-Control "no-store" always;
    }}"""


def validate_namespace(name: str) -> None:
    """Validate a single namespace name. Raises ValueError on any rule violation.

    Rules (per MULTI-05 + 04-RESEARCH.md section 5):
      1. Must be a non-empty string.
      2. Must match ``VALID_NAME_RE`` (``^[a-z0-9][a-z0-9-]{0,62}$``).
      3. Must not be in ``RESERVED_NAMES`` (conflicts with nginx paths,
         vendored assets, or HA Supervisor volumes).

    Reserved-name check runs BEFORE the regex check so that users who
    accidentally pick a reserved name like ``_static`` get the more
    actionable "reserved" error instead of a regex mismatch (which would
    confuse them about why their name is rejected — it does start with a
    letter after all).
    """
    if not isinstance(name, str):
        raise ValueError(
            f"namespace name must be a string, got {type(name).__name__}"
        )
    if not name:
        raise ValueError("namespace name cannot be empty")
    if name in RESERVED_NAMES:
        raise ValueError(
            f"namespace name {name!r} is reserved "
            f"(conflicts with {sorted(RESERVED_NAMES)} paths)"
        )
    if not VALID_NAME_RE.match(name):
        raise ValueError(
            f"namespace name {name!r} must match {VALID_NAME_RE.pattern}"
        )


# Size limits for inline user content (CSS and plugin code). Inline
# content goes through generate_nginx.py, is substituted into the
# generated index.html via Python str.format(), and is shipped on every
# page load - so very large blobs hurt both add-on startup time and
# every browser visit. We warn at 100KB to surface accidental
# copy-paste of huge CSS frameworks and hard-cap at 500KB to prevent
# abuse (the cap is generous: the entire Docsify source tree is
# under 100KB, so a 500KB inline payload is almost certainly a
# mistake).
INLINE_WARN_BYTES = 100 * 1024
INLINE_HARD_LIMIT_BYTES = 500 * 1024


def _validate_https_url(value: str, *, field: str, namespace: str) -> None:
    """Reject any URL whose scheme is not ``https://``.

    Self-hosted add-ons run inside the user's home network and we have
    no use-case for plain http (no credentials in the URL, no
    localhost-only dev server - both are uncommon and easy to
    misconfigure). https-only keeps the attack surface narrow and
    matches what Home Assistant's own front-end enforces for
    user-supplied URLs.
    """
    if not value.startswith("https://"):
        raise ValueError(
            f"{field} for namespace {namespace!r} must start with 'https://', "
            f"got: {value!r}"
        )


def _check_size(value: str, *, field: str, namespace: str) -> None:
    """Warn at 100KB inline, hard-reject at 500KB inline."""
    n = len(value.encode("utf-8"))
    if n > INLINE_HARD_LIMIT_BYTES:
        raise ValueError(
            f"{field} for namespace {namespace!r} is {n} bytes, exceeds the "
            f"{INLINE_HARD_LIMIT_BYTES}-byte hard limit. Split into multiple "
            f"namespaces or move the content to an external file/url."
        )
    if n > INLINE_WARN_BYTES:
        print(
            f"WARNING: {field} for namespace {namespace!r} is {n} bytes "
            f"(>{INLINE_WARN_BYTES} soft limit); consider moving to a "
            f"css_url / external file for faster page loads",
            flush=True,
        )


def _validate_user_plugins(raw_plugins, *, namespace: str) -> list[dict]:
    """Validate the per-namespace ``plugins`` list.

    Rules:
      - Must be a list of dicts.
      - Each entry has a required ``name`` (str) and exactly ONE of
        ``code`` (str) or ``url`` (str) - both set is a configuration
        error (ambiguous registration order). Exactly one missing is
        also an error (nothing to register).
      - ``code`` is rough syntax-checked with Python's compile() so we
        catch obvious typos (missing brace, bad indent). JS-only
        features (arrow functions, async/await, const/let) are skipped
        because the Python parser cannot read them - those errors
        surface at runtime in the Browser console.
      - ``url`` must start with ``https://``.
      - Per-plugin size limit mirrors the CSS limit (100KB warn /
        500KB hard).
    """
    if raw_plugins is None:
        return []
    if not isinstance(raw_plugins, list):
        raise ValueError(
            f"'plugins' for namespace {namespace!r} must be a list, "
            f"got {type(raw_plugins).__name__}"
        )

    validated: list[dict] = []
    for idx, entry in enumerate(raw_plugins):
        if not isinstance(entry, dict):
            raise ValueError(
                f"plugins[{idx}] for namespace {namespace!r} must be a dict, "
                f"got: {entry!r}"
            )
        name = entry.get("name", "")
        url = entry.get("url")
        code = entry.get("code")

        if not isinstance(name, str) or not name:
            raise ValueError(
                f"plugins[{idx}] for namespace {namespace!r} must have a "
                f"non-empty string 'name'"
            )
        if url is not None and not isinstance(url, str):
            raise ValueError(
                f"plugins[{idx}] '{name}' for namespace {namespace!r}: "
                f"'url' must be a string when set"
            )
        if code is not None and not isinstance(code, str):
            raise ValueError(
                f"plugins[{idx}] '{name}' for namespace {namespace!r}: "
                f"'code' must be a string when set"
            )

        has_url = url is not None and url != ""
        has_code = code is not None and code != ""

        if has_url and has_code:
            raise ValueError(
                f"plugin {name!r} for namespace {namespace!r}: specify exactly "
                f"one of 'url' or 'code' (not both - the registration order "
                f"would be ambiguous)"
            )
        if not has_url and not has_code:
            raise ValueError(
                f"plugin {name!r} for namespace {namespace!r}: must specify "
                f"one of 'url' or 'code'"
            )

        if has_url:
            _validate_https_url(url, field=f"plugin '{name}' url", namespace=namespace)
        if has_code:
            _check_size(code, field=f"plugin '{name}' code", namespace=namespace)
            # Heuristic JS-syntax check. Python's compile() can parse a
            # subset of JS but rejects ``function(hook) { ... }`` (the
            # ``function`` keyword and brace block are not Python syntax)
            # and arrow functions, ``async``/``await``, ``const``/``let``,
            # spread operators, generator functions. We skip the check
            # when ANY of those JS-only constructs are detected - the
            # Browser console will surface real syntax errors at load
            # time, so a permissive server-side check is acceptable.
            js_only = re.search(
                r"\b(async|await|const|let|=>|function\b|function\s*\*|\.\.\.)",
                code,
            )
            if not js_only:
                try:
                    compile(code, f"<plugin {name}>", "exec")
                except SyntaxError as e:
                    raise ValueError(
                        f"plugin {name!r} for namespace {namespace!r} has a "
                        f"syntax error at line {e.lineno}: {e.msg}"
                    ) from e

        validated.append({"name": name, "url": url, "code": code})

    return validated


def _validate_user_css(raw_css, *, namespace: str) -> str | None:
    """Validate inline CSS. Empty/None is fine. Size limits apply."""
    if raw_css is None:
        return None
    if not isinstance(raw_css, str):
        raise ValueError(
            f"'css' for namespace {namespace!r} must be a string, "
            f"got {type(raw_css).__name__}"
        )
    if raw_css == "":
        return None
    _check_size(raw_css, field="css", namespace=namespace)
    return raw_css


def _validate_user_css_url(raw_url, *, namespace: str) -> str | None:
    """Validate an external CSS URL. Empty/None is fine. Must be https."""
    if raw_url is None:
        return None
    if not isinstance(raw_url, str):
        raise ValueError(
            f"'css_url' for namespace {namespace!r} must be a string, "
            f"got {type(raw_url).__name__}"
        )
    if raw_url == "":
        return None
    _validate_https_url(raw_url, field="css_url", namespace=namespace)
    return raw_url


def validate_directories(directories: list) -> list[dict]:
    """Validate the full ``directories`` list and return a list of validated entries.

    Each entry must be a dict with string ``name`` and ``path`` fields.
    Optional ``css``/``css_url`` add per-namespace styling; optional
    ``plugins`` extends Docsify with custom hooks (Mermaid rendering is
    one such plugin, but users can add their own).

    Duplicate names are rejected. Empty list is allowed (caller handles
    the "no namespaces configured" case separately). Prints a summary
    line via ``flush=True`` for observability, mirroring
    ``phone-logger/generate_config.py``.
    """
    if not isinstance(directories, list):
        raise ValueError(
            f"'directories' must be a list, got {type(directories).__name__}"
        )

    validated: list[dict] = []
    seen: set[str] = set()
    for entry in directories:
        if not isinstance(entry, dict):
            raise ValueError(
                f"directory entry must be a dict with 'name' and 'path', got: {entry!r}"
            )
        name = entry.get("name", "")
        path = entry.get("path", "")
        if not isinstance(name, str) or not isinstance(path, str):
            raise ValueError(
                f"directory entry must have string 'name' and 'path', got: {entry!r}"
            )
        validate_namespace(name)
        if name in seen:
            raise ValueError(f"duplicate directory name {name!r}")
        seen.add(name)

        # Per-namespace user content. Each validator raises ValueError on
        # any rule violation (bad type, bad URL scheme, code XOR url,
        # size limits) with a message that names the namespace so the
        # operator can find the offending entry in their YAML.
        css = _validate_user_css(entry.get("css"), namespace=name)
        css_url = _validate_user_css_url(entry.get("css_url"), namespace=name)
        plugins = _validate_user_plugins(entry.get("plugins"), namespace=name)

        validated.append({
            "name": name,
            "path": path,
            "css": css,
            "css_url": css_url,
            "plugins": plugins,
        })

    print(
        f"Validated {len(validated)} namespace(s): "
        f"{', '.join(ns['name'] for ns in validated) or '(none)'}",
        flush=True,
    )
    return validated


def render_namespace_blocks(namespaces: list[dict]) -> str:
    """Render the per-namespace nginx location blocks as a single string.

    Each namespace produces EXACT 6 lines (trailing-slash redirect +
    per-namespace static block + Markdown block with ``try_files`` SPA
    fallback + named-location fallback). The output is later interpolated
    into ``NGINX_TEMPLATE`` via ``str.format(namespace_blocks=...)``.

    Exposed as a public helper so unit tests (and the manual fixture check in
    the plan's verify block) can assert on per-ns block shape directly.

    The ``source_path`` kwarg points nginx at the actual Markdown directory
    (mounted from /config, /share, /media on the HA host) so it can serve
    the real .md files directly. ``assets_dir`` is the vendored Docsify +
    Mermaid path (``/app/_static/``) - exposed under both ``/_static/`` and
    ``/<ns>/_static/`` so the same files can be served from either URL
    shape (the per-namespace form matches the relative ``_static/...`` href
    the generated index.html emits).
    """
    return "\n".join(
        NGINX_NAMESPACE_BLOCK_TEMPLATE.format(
            name=ns["name"],
            docroots=DOCROOTS_DIR,
            source_path=ns["path"],
            assets_dir=ASSETS_DIR,
        )
        for ns in namespaces
    )


def _render_nginx(namespaces: list[dict]) -> str:
    """Render the full nginx.conf from the namespace list."""
    blocks = render_namespace_blocks(namespaces)
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

  # Pull in the distro-shipped MIME map so .css -> text/css and
  # .js -> application/javascript. Without this, nginx searches for
  # mime.types next to the main config (/tmp/mime.types) — does not
  # exist because we run with `-c /tmp/nginx.conf` — and falls back
  # to text/plain, which browsers reject under strict MIME checking
  # (scripts/styles fail to load, Docsify stalls at "Loading...").
  # ``types_hash_bucket_size`` MUST come before ``include mime.types`` —
  # nginx hashes the type map at config-load time.
  types_hash_bucket_size 1024;
  include /etc/nginx/mime.types;
  default_type application/octet-stream;

  # Relocate all nginx temp directories under /tmp so ``nginx -t`` works in
  # non-root dev environments (avoids the default /var/lib/nginx/* paths
  # that require write access for nginx's own mkdir()).
  client_body_temp_path {NGINX_CLIENT_BODY_TMP};
  proxy_temp_path       {NGINX_PROXY_TMP};
  fastcgi_temp_path     {NGINX_FASTCGI_TMP};
  uwsgi_temp_path       {NGINX_UWSGI_TMP};
  scgi_temp_path        {NGINX_SCGI_TMP};

  server {{
    listen 8099;
    server_name localhost;

    # Vendored Docsify + Mermaid assets. Exposed at /_static/ for any URL
    # that resolves to the global static location (e.g. the landing page
    # or any future path outside a configured namespace). Each namespace
    # ALSO has its own /<ns>/_static/ location above (rendered by
    # NGINX_NAMESPACE_BLOCK_TEMPLATE), so relative ``_static/...`` hrefs
    # in the generated index.html always resolve to a vendored asset.
    # ``Cache-Control: no-store`` prevents HA's service worker
    # (``sw-modern.js``) from caching the SPA bootstrapper HTML under the
    # same key as the vendored assets - that mix-up causes the Browser to
    # serve HTML when requesting ``docsify.min.js`` and Docsify stalls at
    # 'Loading...' forever.
    location /_static/ {{
      alias {ASSETS_DIR}/;
      add_header Cache-Control "no-store" always;
    }}

    # Landing page at Ingress root (lists all configured namespaces)
    # Cache-Control: no-store so HA's service worker cannot poison the
    # browser cache by serving the SPA HTML in response to vendored
    # asset requests (e.g. /_static/docsify.min.js). See b395eae for
    # the full trace.
    location = / {{
      root {LANDING_DIR};
      try_files /index.html =404;
      add_header Cache-Control "no-store" always;
    }}
    location / {{
      root {LANDING_DIR};
      try_files /index.html =404;
      add_header Cache-Control "no-store" always;
    }}
{blocks}
  }}
}}
"""


def render_landing_html(namespaces: list[dict]) -> str:
    """Render the landing-page index.html with one card per namespace."""
    cards = "\n".join(
        LANDING_CARD_TEMPLATE.format(name=ns["name"], path=ns["path"])
        for ns in namespaces
    )
    return LANDING_HTML_TEMPLATE.format(cards=cards)


# Backwards-compatible alias for callers that imported the private name.
_render_landing = render_landing_html


def _render_namespace_css_link(css_url: str | None) -> str:
    """Render a <link rel='stylesheet'> for an external CSS URL, or empty."""
    if not css_url:
        return ""
    return f'  <link rel="stylesheet" href="{css_url}">'


def _render_namespace_css_inline(css: str | None) -> str:
    """Render an inline <style> block for per-namespace CSS, or empty.

    The CSS is wrapped in a uniquely-id'd <style> element so future
    per-namespace CSS plugins can target it without colliding with the
    Vue theme or other add-on stylesheets.
    """
    if not css:
        return ""
    return f'  <style id="mr-namespace-css">\n{css}\n  </style>'


def _render_namespace_plugin_scripts(plugins: list[dict]) -> str:
    """Render <script> tags for the per-namespace plugins.

    Inline-code plugins get a ``<script>{code}</script>`` block (the
    code itself defines a function and calls
    ``$docsify.plugins.push(...)`` or similar). URL plugins get a
    ``<script src="{url}"></script>`` and must register themselves
    once loaded - the user is responsible for that contract.

    Both forms are emitted in declaration order so URL plugins load
    first (a network roundtrip) before any inline code runs.
    """
    parts = []
    for p in plugins:
        if p["url"]:
            parts.append(f'  <script src="{p["url"]}"></script>')
        elif p["code"]:
            # Strip a trailing semicolon so the inline <script> tag is
            # a clean function expression even if the user wrote a
            # trailing ";" by reflex.
            code = p["code"]
            if code.rstrip().endswith(";"):
                code = code.rstrip()[:-1]
            parts.append(f"  <script>\n{code}\n  </script>")
    return "\n".join(parts)


def _render_namespace_plugin_registration(plugins: list[dict]) -> str:
    """Render the per-namespace $docsify.plugins.concat([...]) block.

    Only inline-code plugins are registered here - URL plugins push
    themselves once their script has loaded. We accumulate a comma-
    separated list of user-supplied function literals. The wrapping
    block is omitted entirely when there are no inline plugins so the
    generated index.html stays minimal.
    """
    inline = [p["code"] for p in plugins if p["code"]]
    if not inline:
        return ""
    # Strip trailing ";" per entry so the concat list parses cleanly.
    cleaned = []
    for code in inline:
        code = code.rstrip()
        if code.endswith(";"):
            code = code[:-1]
        cleaned.append(code)
    entries = ",\n    ".join(cleaned)
    return (
        "  <script>\n"
        "    // Per-namespace inline plugins (from add-on config)\n"
        "    window.$docsify = window.$docsify || {};\n"
        "    window.$docsify.plugins = (window.$docsify.plugins || []).concat([\n"
        f"    {entries},\n"
        "    ]);\n"
        "  </script>"
    )


def _render_namespace_index(namespace: dict, kroki_url: str) -> str:
    """Render the Docsify index.html for a single namespace.

    Injects the validated per-namespace ``css``, ``css_url`` and
    ``plugins`` (if any) into the template. Validators in
    ``validate_directories()`` guarantee that ``css`` is a string or
    None, ``css_url`` starts with https:// or is None, and every
    plugin entry has exactly one of ``code``/``url`` set.
    """
    name = namespace["name"]
    plugins = namespace.get("plugins") or []
    css_url_html = _render_namespace_css_link(namespace.get("css_url"))
    css_inline_html = _render_namespace_css_inline(namespace.get("css"))
    plugin_scripts_html = _render_namespace_plugin_scripts(plugins)
    plugin_registration_html = _render_namespace_plugin_registration(plugins)
    # JSON-encode name + kroki_url so they survive inside an inline
    # <script> (backslash, double-quote and unicode characters must be
    # escaped).
    name_json = json.dumps(name)
    kroki_url_json = json.dumps(kroki_url)
    plugins_json = json.dumps(plugins)
    return INDEX_HTML_TEMPLATE.format(
        name=name,
        name_display=name,
        name_json=name_json,
        kroki_url_json=kroki_url_json,
        default_kroki_url=DEFAULT_KROKI_URL,
        css_url_html=css_url_html,
        css_inline_html=css_inline_html,
        plugin_scripts_html=plugin_scripts_html,
        plugin_registration_html=plugin_registration_html,
        plugins_json=plugins_json,
    )


def _validate_namespaces(directories: list) -> list[dict]:
    """Internal wrapper that translates ``ValueError`` into ``SystemExit(1)``.

    Kept as a thin shell around ``validate_directories`` so existing callers
    (and the plan-01 verification path) continue to see ``SystemExit`` on
    validation failure. The public ``validate_directories`` raises
    ``ValueError``; ``main()`` catches it and returns ``1`` for clean error
    propagation through run.sh.
    """
    try:
        return validate_directories(directories)
    except ValueError as err:
        print(f"ERROR: {err}", flush=True)
        sys.exit(1)


def _ensure_nginx_tmp_dirs() -> None:
    """Create nginx temp dirs so the master process can start in non-root envs.

    Without this, ``nginx -c /tmp/nginx.conf`` aborts with
    ``nginx: [emerg] mkdir() "/tmp/nginx-tmp/client_body" failed`` because the
    master process tries to create its temp directories as a non-root user.
    Idempotent: existing dirs are left alone.
    """
    for tmp_dir in (
        NGINX_CLIENT_BODY_TMP,
        NGINX_PROXY_TMP,
        NGINX_FASTCGI_TMP,
        NGINX_UWSGI_TMP,
        NGINX_SCGI_TMP,
    ):
        tmp_dir.mkdir(parents=True, exist_ok=True)


def _write_minimal_nginx(reason: str) -> None:
    """Write a fallback nginx.conf that only serves /_static/ and a 503."""
    NGINX_CONF_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Create nginx temp directories (same as the happy-path branch does) so the
    # master process can start without ``nginx: [emerg] mkdir()`` errors when
    # no namespaces are configured or no options.json was mounted.
    _ensure_nginx_tmp_dirs()
    NGINX_CONF_PATH.write_text(
        f"""worker_processes 1;
error_log /dev/stderr warn;
pid /tmp/nginx.pid;
events {{ worker_connections 512; }}
http {{
  access_log /dev/stdout combined;
  absolute_redirect off;
  types_hash_bucket_size 1024;
  include /etc/nginx/mime.types;
  default_type application/octet-stream;
  client_body_temp_path {NGINX_CLIENT_BODY_TMP};
  proxy_temp_path       {NGINX_PROXY_TMP};
  fastcgi_temp_path     {NGINX_FASTCGI_TMP};
  uwsgi_temp_path       {NGINX_UWSGI_TMP};
  scgi_temp_path        {NGINX_SCGI_TMP};
  server {{
    listen 8099;
    server_name localhost;
    location /_static/ {{ alias {ASSETS_DIR}/; add_header Cache-Control "no-store" always; }}
    location / {{ return 503 'Markdown Renderer: {reason}\\n'; add_header Cache-Control "no-store" always; }}
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
    debug = bool(options.get("debug", False))

    # ``validate_directories`` raises ``ValueError`` for any structural or
    # semantic problem (non-list, empty name, regex mismatch, reserved name,
    # duplicate name, missing fields). Translate into a clean return-1 so
    # run.sh (and HA Supervisor) see a non-zero exit code without an
    # uncaught traceback.
    try:
        namespaces = validate_directories(directories)
    except ValueError as err:
        print(f"ERROR: {err}", flush=True)
        return 1

    if not namespaces:
        print(
            "WARNING: no directories configured, writing minimal /tmp/nginx.conf",
            flush=True,
        )
        _write_minimal_nginx("no directories configured")
        return 0

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
    (LANDING_DIR / "index.html").write_text(render_landing_html(namespaces))

    # nginx.conf
    NGINX_CONF_PATH.write_text(_render_nginx(namespaces))

    # Pre-create nginx temp directories so ``nginx -t`` succeeds in non-root
    # environments (avoids the default /var/lib/nginx/* mkdir failure). The
    # add-on container runs as root and would work without this, but creating
    # the dirs up-front keeps both the runtime and the local verify path green.
    _ensure_nginx_tmp_dirs()

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

    if debug:
        _dump_debug(namespaces, kroki_url)

    return 0


def _dump_debug(namespaces: list[dict], kroki_url: str) -> None:
    """Log effective options, generated files, vendored assets and nginx build.

    Activated by the ``debug: true`` add-on option. Every line is prefixed with
    ``[debug]`` so the HA Supervisor log can be filtered easily. Intentionally
    opt-in: the dump is verbose and may include Markdown titles / Kroki URLs
    that some operators do not want in shared logs.

    Logs:

      1. Effective options (sanitized — never includes ``/data`` or env vars).
      2. Generated ``/tmp/nginx.conf`` (resolved template).
      3. Each generated ``index.html`` (Landing + one per namespace).
      4. Vendored ``_static/`` asset list (relative path, byte size, sha256
         prefix). Useful when the browser reports a MIME / 404 error on a
         specific asset — the dump makes it obvious whether the file shipped
         at all and whether its content matches a known sha.
      5. ``nginx -V`` (binary path, version, compiled modules).
    """

    def debug(msg: str) -> None:
        """Print a ``[debug]``-prefixed line. Local helper so the prefix is
        applied consistently and the lambda does not shadow anything."""
        print(f"[debug] {msg}", flush=True)

    debug(f"effective options: namespaces={[ns['name'] for ns in namespaces]} "
          f"kroki_url={kroki_url}")

    if NGINX_CONF_PATH.exists():
        debug(f"--- BEGIN {NGINX_CONF_PATH} ---")
        debug(NGINX_CONF_PATH.read_text().rstrip())
        debug(f"--- END {NGINX_CONF_PATH} ---")

    landing = LANDING_DIR / "index.html"
    if landing.exists():
        debug(f"--- BEGIN {landing} ---")
        debug(landing.read_text().rstrip())
        debug(f"--- END {landing} ---")

    for ns in namespaces:
        idx = DOCROOTS_DIR / ns["name"] / "index.html"
        if idx.exists():
            debug(f"--- BEGIN {idx} ---")
            debug(idx.read_text().rstrip())
            debug(f"--- END {idx} ---")

    if ASSETS_DIR.exists():
        debug(f"--- vendored assets in {ASSETS_DIR}/ ---")
        for asset in sorted(ASSETS_DIR.rglob("*")):
            if asset.is_file():
                rel = asset.relative_to(ASSETS_DIR)
                size = asset.stat().st_size
                digest = hashlib.sha256(asset.read_bytes()).hexdigest()[:12]
                debug(f"  {rel}  {size} bytes  sha256:{digest}…")
    else:
        debug(f"WARNING: vendored asset dir {ASSETS_DIR} does not exist")

    try:
        result = subprocess.run(
            ["nginx", "-V"], capture_output=True, text=True
        )
        debug(f"--- nginx -V ---\n{result.stdout.rstrip()}\n{result.stderr.rstrip()}")
    except FileNotFoundError:
        debug("nginx binary not found, skipping `nginx -V`")

    debug("dump complete")


if __name__ == "__main__":
    sys.exit(main())
