# Codebase Structure

**Analysis Date:** 2026-04-03

## Directory Layout

```
homeassistant-addons/
├── fritz-callmonitor2mqtt/   # Add-on: FRITZ!Box call monitor → MQTT bridge
├── phone-logger/             # Add-on: Python-based call logging with adapters
├── scripts/                  # Repository-level tooling (version management, validation)
├── docs/                     # Developer documentation
├── .github/workflows/        # GitHub Actions CI (lint.yml)
├── .devcontainer/            # VS Code devcontainer for HA add-on development
├── .planning/codebase/       # GSD codebase analysis documents (not committed)
├── repository.yaml           # HA add-on repository manifest (name, url, maintainer)
├── Makefile                  # Developer task runner
├── .pre-commit-config.yaml   # Pre-commit hooks (YAML, shell, markdown, versions)
├── .yamllint.yml             # YAML lint rules (2-space indent, 120-char limit)
├── .markdownlint.json        # Markdown lint rules (ATX headers, 4-space list indent)
├── .actionlint.yml           # GitHub Actions lint config
├── .prettierrc.yaml          # Prettier config for markdown formatting
└── .gitignore                # Ignores .env, .idea/, .vscode/
```

## Add-on Directory Structure (canonical pattern)

Every add-on follows this exact layout. Both current add-ons conform to it.

```
addon-name/
├── config.yaml         # HA manifest: name, version (X.Y.Z-N), slug, arch, options schema
├── build.yaml          # Docker build: build_from base image + VERSION arg (X.Y.Z)
├── Dockerfile          # Container build (downloads upstream binary or source)
├── run.sh              # Startup script (reads HA options, exports env vars, starts app)
├── README.md           # User docs with version shield badges (vX.Y.Z in badge URLs)
├── DOCS.md             # Configuration reference
└── .upstream.yaml      # Auto-update config: upstream GitHub repo + version pattern
```

**Required files** (enforced by CI and `make validate-addons`): `config.yaml`, `Dockerfile`, `run.sh`.

**Additional file in phone-logger only:**

- `generate_config.py` — transforms `options.json` (HA format) into AppConfig YAML for the upstream app.

## Directory Purposes

**`fritz-callmonitor2mqtt/`:**

- Purpose: Bridges FRITZ!Box call monitor TCP port (1012) to MQTT
- Implementation: Downloads pre-compiled Go binary from upstream GitHub releases at build time
- Startup: `run.sh` uses `bashio::config` to read each HA option and export as env vars, then exec's the binary
- Key files: `fritz-callmonitor2mqtt/config.yaml`, `fritz-callmonitor2mqtt/build.yaml`, `fritz-callmonitor2mqtt/run.sh`,
  `fritz-callmonitor2mqtt/Dockerfile`

**`phone-logger/`:**

- Purpose: Call logging with adapter architecture (Fritz, REST, Tellows, SQLite, MQTT, webhooks)
- Implementation: Downloads Python source tarball from upstream GitHub at build time, installs deps via `uv`
- Startup: `run.sh` calls `generate_config.py` to translate `options.json` → AppConfig YAML, then runs
  `python -m src.main`
- Key files: `phone-logger/config.yaml`, `phone-logger/run.sh`, `phone-logger/generate_config.py`,
  `phone-logger/Dockerfile`

**`scripts/`:**

- Purpose: Repository-level developer tooling
- Key files:
  - `scripts/update-version.py` — updates version across all 3 required files atomically
  - `scripts/validate-versions.sh` — checks 3-file version sync (runs as pre-commit hook)
  - `scripts/fix-markdown-lines.py` — markdown line-length fixer
  - `scripts/setup-hooks.sh` — installs pre-commit hooks

**`docs/`:**

- Purpose: Extended developer documentation
- Key files:
  - `docs/DEVELOPMENT.md` — development setup guide
  - `docs/AUTO_UPDATE_GUIDE.md` — explains the upstream auto-update system

**`.github/workflows/`:**

- Purpose: CI pipeline
- Key files:
  - `.github/workflows/lint.yml` — runs YAML lint, shellcheck, markdownlint, actionlint, add-on config validation, and
    version validation on push/PR to main

**`.devcontainer/`:**

- Purpose: VS Code devcontainer using `ghcr.io/home-assistant/devcontainer:3-addons`, maps add-ons into the HA
  supervisor for live testing
- Key files: `.devcontainer/devcontainer.json`

## Key File Locations

**Repository Root:**

- `repository.yaml` — HA add-on repository registration (name, URL, maintainer)
- `Makefile` — all developer task entry points
- `.pre-commit-config.yaml` — enforces YAML lint, shellcheck, prettier (markdown), actionlint, validate-versions

**Versioning:**

- `{addon}/config.yaml` — `version: "X.Y.Z-N"` (with subpatch suffix)
- `{addon}/build.yaml` — `args.VERSION: "X.Y.Z"` (no subpatch, used as Docker build arg)
- `{addon}/README.md` — shield badge URLs contain `version-vX.Y.Z`
- `scripts/validate-versions.sh` — enforces consistency of the above 3 files

**Upstream Auto-Update:**

- `{addon}/.upstream.yaml` — declares `upstream.repository` (GitHub slug) and `addon.version_pattern: "sync"`

## Naming Conventions

**Directories:**

- Add-on slug as directory name: `fritz-callmonitor2mqtt`, `phone-logger` (kebab-case, matches `slug` in `config.yaml`)

**Files:**

- Shell scripts: `run.sh` (always this exact name), `setup-hooks.sh`
- Python scripts: `snake_case.py` (`update-version.py`, `generate_config.py`, `fix-markdown-lines.py`)
- YAML manifests: lowercase (`config.yaml`, `build.yaml`)
- Documentation: `UPPER_SNAKE.md` for repo-level (`README.md`, `DOCS.md`, `CLAUDE.md`, `AGENTS.md`)
- Hidden config: dotfile prefix (`.upstream.yaml`, `.yamllint.yml`)

## Where to Add New Code

**New add-on:**

- Create `{addon-slug}/` at repo root
- Required files: `config.yaml` (version `X.Y.Z-0`), `build.yaml` (VERSION `X.Y.Z`), `Dockerfile`, `run.sh`,
  `README.md`, `DOCS.md`, `.upstream.yaml`
- Optional but expected: `generate_config.py` if the upstream app uses a different config format than HA options
- Register in `repository.yaml` if needed (not required — HA discovers by directory)

**New version update script logic:**

- Add to `scripts/update-version.py` following the existing 3-file pattern

**New CI check:**

- Add a step to `.github/workflows/lint.yml`
- Add the corresponding pre-commit hook to `.pre-commit-config.yaml`

**New developer documentation:**

- Place in `docs/` as `TOPIC_GUIDE.md` or `TOPIC.md`

## Special Directories

**`.planning/`:**

- Purpose: GSD codebase analysis and planning documents
- Generated: Yes (by GSD map-codebase / plan-phase commands)
- Committed: No (not in .gitignore explicitly, but treated as ephemeral workspace)

**`.devcontainer/`:**

- Purpose: Reproducible HA add-on development environment (VS Code)
- Generated: No
- Committed: Yes

**`.github/`:**

- Purpose: GitHub Actions workflows
- Generated: No
- Committed: Yes

**`.claude/`:**

- Purpose: Claude Code project-level memory/context files
- Generated: Partially (memory written by Claude)
- Committed: Partially

---

_Structure analysis: 2026-04-03_
