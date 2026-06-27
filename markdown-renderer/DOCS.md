# Markdown Renderer Add-on - Configuration

## Options

### `directories` (required, list of objects)

Each entry configures one namespace served as an isolated Docsify SPA under `/<name>/`. Names must match
`^[a-z0-9][a-z0-9-]{0,62}$` and may not collide with reserved paths.

| Field | Type   | Description                                           |
| ----- | ------ | ----------------------------------------------------- |
| name  | string | URL namespace (lowercase letters, digits, hyphens)    |
| path  | string | Absolute path to the directory containing `.md` files |

### `kroki_url` (optional, string)

URL of the Kroki service used to render non-Mermaid diagram formats (PlantUML, GraphViz, BlockDiag, D2, Excalidraw,
etc.). Defaults to `https://kroki.io`. Use a self-hosted instance URL (e.g. `http://local-kroki:8000`) for fully-offline
rendering.

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

## Validation Status

All 6 multi-namespace requirements (MULTI-01..06) have been verified end-to-end by the script
`.planning/phases/05-multi-namespace-dynamic-config/verify-multi-namespace.sh`. To re-run the empirical verification
locally:

```bash
make build-addon ADDON=markdown-renderer    # build local/markdown-renderer:1.0.0 (if not already built)
bash .planning/phases/05-multi-namespace-dynamic-config/verify-multi-namespace.sh
```

The script exits 0 with `ALL VERIFICATIONS PASSED` on success.

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
