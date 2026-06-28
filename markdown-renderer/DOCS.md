# Markdown Renderer Add-on - Configuration

## Options

### `directories` (required, list of objects)

Each entry configures one namespace served as an isolated Docsify SPA under `/<name>/`. Names must match
`^[a-z0-9][a-z0-9-]{0,62}$` and may not collide with reserved paths.

| Field             | Type    | Description                                                               |
| ----------------- | ------- | ------------------------------------------------------------------------- |
| name              | string  | URL namespace (lowercase letters, digits, hyphens)                        |
| path              | string  | Absolute path to the directory containing `.md` files                     |
| git_pull          | bool    | Run `git pull --ff-only` at startup before nginx starts (default `false`) |
| git_pull_interval | int     | Periodic pull interval in seconds; `0` = disabled (default `0`)           |
| git_url           | string? | Optional HTTPS or `file://` URL for first-time clone of an empty path     |
| css               | string? | Optional inline CSS injected into the namespace SPA                       |
| css_url           | string? | Optional `https://` URL to an external stylesheet                         |
| plugins           | list?   | Optional Docsify plugin extensions (see [Plugins](#plugins))              |

See the [Git Sync](#git-sync) section below for details on the three git fields.

### `kroki_url` (optional, string)

URL of the Kroki service used to render non-Mermaid diagram formats (PlantUML, GraphViz, BlockDiag, D2, Excalidraw,
etc.). Defaults to `https://kroki.io`. Use a self-hosted instance URL (e.g. `http://local-kroki:8000`) for fully-offline
rendering.

### `debug` (optional, bool)

When `true`, the add-on dumps the effective configuration to the container log at startup:

- The generated `nginx.conf` (with the resolved `mime.types` include)
- Every generated `index.html` (per-namespace + landing page)
- The vendored `_docsify/` asset list (path, byte size, short sha256) — useful when the browser blocks a script/style
  with a MIME-type or 404 error
- `nginx -V` output (binary path, version, compiled modules)

Every line is prefixed with `[debug]` so it is easy to grep or mute in the HA Supervisor log. Defaults to `false` — turn
it on temporarily when filing a bug report, then turn it off again so the log stays quiet.

## Volumes

The add-on mounts three writable volumes so configured namespaces can read Markdown content from anywhere on the HA host
filesystem:

| Volume | Path inside container | Purpose                |
| ------ | --------------------- | ---------------------- |
| share  | `/share`              | User-shared media/data |
| config | `/config`             | HA configuration       |
| media  | `/media`              | HA media library       |

## Multi-Namespace Behavior

Configure any number of Markdown directories in `directories:` — each becomes an isolated Docsify SPA under `/<name>/`.
The add-on displays a landing page at `/` listing every configured namespace as a clickable card with the namespace name
and the configured path.

Landing page cards regenerate automatically on every add-on restart — change the `directories:` list in the HA add-on
options, restart the add-on, and the new landing page reflects the new config. There is no separate "apply" step.

### Namespace Name Rules

Each `name` must:

- Be non-empty
- Match the regex `^[a-z0-9][a-z0-9-]{0,62}$` (lowercase letters, digits, hyphens; max 63 characters)
- Not collide with reserved names: `_docsify`, `api`, `data`, `share`, `config`, `media`

If a name violates any rule, the add-on refuses to start with a clear error in the HA Supervisor log naming the bad name
(e.g. `ERROR: namespace name 'bad/name' must match ^[a-z0-9][a-z0-9-]{0,62}$`). Duplicate names in the `directories:`
list are also rejected (`ERROR: duplicate directory name 'docs'`).

With an empty `directories:` list, the add-on stays running but serves a 503 page with body
`Markdown Renderer: no directories configured`. This makes the failure mode obvious without crashing the container.

### Reading from /share, /config, /media

The `map:` declaration in `config.yaml` mounts all three writable volumes so namespaces can read Markdown content from
anywhere on the HA host filesystem. A typical multi-source configuration:

```yaml
directories:
  - name: docs
    path: /share/docs # user-shared documents
  - name: runbooks
    path: /config/runbooks # HA configuration directory
  - name: photos
    path: /media/photos # HA media library
kroki_url: https://kroki.io
```

No additional setup is required — just put `.md` files in the configured paths on the HA host and they will appear in
the add-on.

## Per-Namespace CSS

Each namespace can override or extend the Docsify Vue theme with two optional fields:

```yaml
directories:
  - name: docs
    path: /config/docs
    css: |
      /* Inline CSS - injected as <style id="mr-namespace-css"> after the Vue theme */
      .markdown-section { background: #fafafa; }
      h1 { border-bottom: 2px solid #42b983; }
    css_url: https://fonts.googleapis.com/css2?family=Inter&display=swap
```

- `css` is inlined into the generated `index.html` as `<style id="mr-namespace-css">`. Empty / omitted means no
  inline style block.
- `css_url` must be `https://...` (plain `http://` is rejected). Empty / omitted means no `<link>` tag.

Both can be combined; the inlined CSS overrides the linked stylesheet because it appears later in document order.

Size limit: 100KB inline triggers a startup warning (the generated `index.html` is shipped on every page load);
500KB is a hard limit that aborts startup with a clear error.

## Plugins

Docsify plugins hook into Docsify's render lifecycle. The add-on ships Mermaid rendering out of the box; the
`plugins` field lets you add your own (or replace Mermaid behavior). Each entry is one of:

```yaml
directories:
  - name: docs
    path: /config/docs
    plugins:
      # Inline plugin - a function literal that pushes into $docsify.plugins.
      - name: word-count
        code: |
          function(hook) {
            hook.afterEach(function(html) {
              console.log('[word-count]', html.split(/\s+/).length, 'words');
              return html;
            });
          }
      # External plugin - loaded as <script src="..."> before Docsify. The plugin
      # is responsible for calling ``window.$docsify.plugins.push(...)`` itself.
      - name: external-plugin
        url: https://example.com/my-docsify-plugin.js
```

Each entry has a `name` (used for log messages) and exactly ONE of:

- `code` - inline JavaScript. The value is inserted verbatim into a `<script>` block before `docsify.min.js` AND
  appended to a `$docsify.plugins.concat([...])` call after Mermaid setup, so the function is auto-registered.
- `url` - external `https://` URL. Loaded via `<script src=...>`; the script must register itself.

Setting both or neither is rejected at startup. URLs must use `https://`. The 100KB warn / 500KB hard
size limits from the CSS section also apply to inline plugin code.

Heuristic syntax check: `generate_nginx.py` runs the user's `code` through Python's `compile()` to catch obvious
typos. JS-only features (arrow functions, `async`/`await`, `const`/`let`, spread, generator functions, plain
`function` keyword) are detected and the check is skipped - real syntax errors surface in the Browser console.

## Validation Status

All 6 multi-namespace requirements (MULTI-01..06) and all 5 git-sync requirements (GIT-01..05) have been verified
end-to-end inside a running container by the scripts:

- `.planning/phases/05-multi-namespace-dynamic-config/verify-multi-namespace.sh` (35 assertions, MULTI-01..06)
- `.planning/phases/06-git-integration/verify-git-integration.sh` (18 assertions, GIT-01..05)

To re-run the empirical verification locally:

```bash
make build-addon ADDON=markdown-renderer    # build local/markdown-renderer:1.1.0 (if not already built)
bash .planning/phases/05-multi-namespace-dynamic-config/verify-multi-namespace.sh
bash .planning/phases/06-git-integration/verify-git-integration.sh
```

Both scripts exit 0 with `ALL VERIFICATIONS PASSED` on success.

## Git Sync

Each `directories[]` entry can optionally pull its content from a git repository. Git sync is non-blocking: any git
failure is logged as a warning but the locally cached Markdown is still served (GIT-05 contract).

### Schema fields

| Field               | Type    | Default | Description                                                           |
| ------------------- | ------- | ------- | --------------------------------------------------------------------- |
| `git_pull`          | bool    | `false` | Run `git pull --ff-only` at startup before nginx starts (GIT-01)      |
| `git_pull_interval` | int     | `0`     | Periodic pull interval in seconds; `0` = disabled (GIT-04)            |
| `git_url`           | string? | `""`    | Optional HTTPS or `file://` URL for first-time clone of an empty path |

### Startup pull

When `git_pull: true` and the configured `path` is already a git repository, the add-on runs `git pull --ff-only` at
startup before nginx starts (GIT-01). The pulled content is immediately visible in the browser on first load.

### Periodic sync

When `git_pull_interval > 0`, one background loop in `run.sh` (started after the startup pull) runs
`python3 /app/_git_sync.py --periodic` every 5 seconds; the script iterates each namespace whose own `git_pull_interval`
has elapsed since its last successful pull (GIT-04, D-08). State is in-memory only — the first periodic iteration after
a restart pulls every configured namespace once (D-09).

### First-time clone

When the configured `path` is not yet a git repository AND `git_url` is set AND either `git_pull` or `git_pull_interval`
is enabled, the add-on runs `git clone <git_url> <path>` once at startup (D-02). Single attempt only — clones that fail
(auth error, typo, unreachable host) log a `WARNING:` and the add-on continues. Note: `git clone` requires the
destination directory to be empty; if you pre-populated the path with your own content, clear it before enabling
`git_pull`.

### Failure handling

All git errors are non-blocking (GIT-05):

- `git pull` failures log `WARNING: git pull failed for <path>: <git stderr>` and continue.
- `git clone` failures log `WARNING: git clone failed for <git_url> -> <path>: <git stderr>` and continue.
- The add-on serves whatever locally cached Markdown exists, even if every git remote is unreachable.

Git 2.35.2+ refuses to operate on repos owned by a different UID by default; the add-on runs
`git config --global --add safe.directory '*'` before any git invocation to bypass this (GIT-02).

### Verifier

The script `.planning/phases/06-git-integration/verify-git-integration.sh` empirically verifies all five GIT-01..05
requirements end-to-end inside a running `local/markdown-renderer:1.1.0` container with no live Home Assistant required.
It uses local `file://` URLs and bind-mounted source repos to exercise startup pull, periodic pull, the
no-invocation-when-disabled case, the graceful-failure case, and the first-time clone case in 5 scenarios (18 assertions
total).

### Scope notes

SSH key authentication for private repositories is planned for v1.2; v1.1 supports HTTPS public repositories and local
`file://` URLs only.

## Example Configuration

```yaml
directories:
  - name: docs
    path: /share/docs
  - name: runbooks
    path: /config/runbooks
kroki_url: https://kroki.io
```

## Notes

- Vendored Docsify 4.13.1 + Mermaid 11.15.0 UMD - no CDN requests. Ingress basePath is derived from
  `window.location.pathname` automatically.
- PlantUML, GraphViz, BlockDiag, D2, and 20+ other diagram formats are rendered via Kroki. Configure `kroki_url` in the
  add-on options (default `https://kroki.io`, the public web service). If Kroki is unreachable for a specific diagram
  the original code block remains visible.
