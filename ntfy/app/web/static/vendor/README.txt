Vendored UI runtime (D-16: no CDN, no npm, no build step)

Package:        htm 3.1.1 (published 2022-04-26), preact standalone ES module
Source URL:     https://cdn.jsdelivr.net/npm/htm@3.1.1/preact/standalone.module.js
Upstream file:  preact/standalone.module.js
Local name:     preact-htm.mjs (content unchanged, only the file name differs)
Size:           13194 bytes
sha256:         72284e8e9079c87817145df1110f74e8a2aa040b2fc384922e18dfcb46fc1fd7

Licences:
  htm     Apache-2.0  LICENSE-htm.txt     (https://cdn.jsdelivr.net/npm/htm@3.1.1/LICENSE)
  preact  MIT         LICENSE-preact.txt  (https://cdn.jsdelivr.net/npm/preact@10.29.8/LICENSE)

The bundled Preact version is 10.x; the minified file does not state the exact version.

Exports used by the app: html, render, useState, useEffect, useMemo, useRef, useCallback.

Update procedure:
  1. Download the new standalone.module.js of the wanted htm version to a scratch directory.
  2. Compare it with the vendored file, review the changes and the new licences.
  3. Replace preact-htm.mjs, update size, version, URL and sha256 here and the SHA256 constant in
     ntfy/tests/test_frontend_static.py.
  4. Run: uv run --with pytest python3 -m pytest ntfy/tests -q
