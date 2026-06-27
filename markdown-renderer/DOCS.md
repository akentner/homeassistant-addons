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
