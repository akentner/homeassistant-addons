# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

Home Assistant Add-ons repository with automated upstream version monitoring. Currently contains two add-ons:

- **fritz-callmonitor2mqtt**: Bridges FRITZ!Box call monitor to MQTT
- **phone-logger**: Python-based call logging with adapter architecture

## Development Commands

```bash
make init              # One-time setup: Python venv, pre-commit, linting tools, actionlint
make lint              # Run all pre-commit hooks
make validate-addons   # Check add-on structure (required files, YAML validity)
make validate-versions # Check 3-file version sync
make check-all         # All checks combined
make fix               # Auto-fix whitespace, EOF, line endings

# Update a specific add-on version
make update-version ADDON=fritz-callmonitor2mqtt VERSION=1.7.4
# Or directly:
./scripts/update-version.py fritz-callmonitor2mqtt 1.7.4 [--check-release] [--dry-run]
```

## Critical: 3-File Versioning Scheme

Every add-on maintains versions across exactly 3 files that must stay in sync. This is enforced by pre-commit hooks
(`scripts/validate-versions.sh`):

| File                             | Format                    | Example   |
| -------------------------------- | ------------------------- | --------- |
| `config.yaml`                    | `X.Y.Z-N` (with subpatch) | `1.7.3-0` |
| `build.yaml` (as `args.VERSION`) | `X.Y.Z` (no subpatch)     | `1.7.3`   |
| `README.md` (shield badges)      | `vX.Y.Z` in badge URLs    | `v1.7.3`  |

**Never edit versions manually.** Always use `make update-version` or `scripts/update-version.py`. The subpatch suffix
in config.yaml resets to `-0` when upstream version changes; increment it (e.g., `-1`, `-2`) for add-on-only fixes.

## Add-on Structure

Every add-on directory must contain:

```text
addon-name/
├── config.yaml        # Home Assistant manifest + options schema
├── build.yaml         # Docker build config with VERSION arg
├── Dockerfile         # Container definition
├── run.sh             # Startup script (uses bashio for HA config)
├── README.md          # User docs with version shield badges
├── DOCS.md            # Configuration reference
└── .upstream.yaml     # Auto-update: upstream repo + version pattern
```

## Auto-Update System

`.upstream.yaml` in each add-on directory configures automated version tracking via GitHub Actions (daily at 6:00 UTC).
The `version_pattern: "sync"` in the addon section means the add-on version follows upstream exactly.

## YAML Parsing Caveat

Home Assistant config.yaml files use custom tags (e.g., `!secret`). Always parse with `--unsafe` flag when using `yq`:

```bash
yq eval --unsafe '.version' fritz-callmonitor2mqtt/config.yaml
```

## Linting Configuration

- YAML: 2-space indent, 120-char line limit (`.yamllint.yml`)
- Markdown: ATX headers, 120-char limit, 4-space list indent (`.markdownlint.json`)
- Shell: shellcheck with SC1091 and SC2034 ignored (`.pre-commit-config.yaml`)
- Actions: relaxed shellcheck rules for workflows (`.actionlint.yml`)

<!-- GSD:project-start source:PROJECT.md -->

## Project

**Home Assistant Add-ons Repository**

A Home Assistant Add-ons repository providing containerized wrappers for upstream applications. The repository does not
contain application source code — Dockerfiles download upstream release artifacts at build time. Each add-on provides a
`config.yaml` manifest, Dockerfile, and `run.sh` entrypoint that bridges HA configuration (via bashio/options.json) to
the application. Currently hosts `fritz-callmonitor2mqtt` (FRITZ!Box → MQTT bridge) and `phone-logger` (call logging
with adapter architecture). A third add-on, `meridian` (Claude Max → local API proxy), is in active development.

**Core Value:** Any upstream release is automatically reflected in the add-on within 24 hours — zero manual version
tracking.

### Constraints

- **Tech stack**: HA base images (`ghcr.io/home-assistant/`) only — no generic Alpine/Python/Node base images for add-on
  containers
- **Pattern consistency**: New add-ons must follow the established 4-file pattern (config.yaml, build.yaml, Dockerfile,
  run.sh) + `.upstream.yaml`
- **No bundled source**: Dockerfiles must download upstream code at build time, not copy local source
- **Meridian auth**: `claude login` requires interactive terminal — handled via HA terminal add-on, not automation
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Summary

## Languages

- **Go** — `fritz-callmonitor2mqtt` upstream binary; compiled externally, downloaded as a release artifact during Docker
- **Python 3.12** — `phone-logger` upstream source downloaded at build time; add-on provides `generate_config.py` as the
- **Bash** — `run.sh` in both add-ons (executed via `bashio`), `scripts/validate-versions.sh`, `scripts/setup-hooks.sh`
- **Python 3** — `scripts/update-version.py`, `scripts/fix-markdown-lines.py` (stdlib only, no external deps)

## Runtime

- `fritz-callmonitor2mqtt`: Alpine 3.22 via `ghcr.io/home-assistant/amd64-base:3.22`
- `phone-logger`: Alpine 3.20 + Python 3.12 via `ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20`
- `uv` — installed via `COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv`
- Dependencies installed from upstream `uv.lock` with `uv sync --frozen --no-dev --no-install-project`
- Runtime invocation: `uv run --no-dev python ...`
- Both add-ons currently build for `amd64` only (other arches commented out in `config.yaml` / `build.yaml`)

## Frameworks & Key Libraries

- `bashio` — HA utility library available in all HA base images; used in both `run.sh` files for reading add-on config
- `lxml`, `libxml2`, `libxslt` — XML/HTML parsing (build deps installed via apk, then removed)
- `json` — stdlib, reads `/data/options.json`
- `yaml` (PyYAML) — writes config to `/tmp/phone-logger-config.yaml`; available from upstream's uv.lock

## Build Tools

- Both Dockerfiles use multi-stage-style `ARG BUILD_FROM` / `FROM ${BUILD_FROM}` pattern
- `fritz-callmonitor2mqtt` Dockerfile: downloads a `.tar.gz` release from GitHub at build time via `curl`
- `phone-logger` Dockerfile: downloads upstream source tarball from GitHub tags at build time via `curl | tar`
- `fritz-callmonitor2mqtt`: installs `curl`, `tar`
- `phone-logger`: installs build deps (`gcc`, `musl-dev`, `libxml2-dev`, `libxslt-dev`, `python3-dev`, `tzdata`, `curl`,

## Development Tooling

| Tool                | Version  | Purpose             | Config file               |
| ------------------- | -------- | ------------------- | ------------------------- |
| `yamllint`          | 1.35.1   | YAML lint           | `.yamllint.yml`           |
| `shellcheck-py`     | 0.10.0.1 | Shell script lint   | `.pre-commit-config.yaml` |
| `prettier`          | 3.1.0    | Markdown formatting | `.prettierrc.yaml`        |
| `actionlint`        | 1.7.3    | GitHub Actions lint | `.actionlint.yml`         |
| `markdownlint-cli2` | latest   | Markdown lint       | `.markdownlint.json`      |

## Configuration

- YAML: 2-space indent, 120-char line limit, relaxed base (`.yamllint.yml`)
- Markdown: 120-char line limit (`.markdownlint.json`)
- Shell: `SC1091` and `SC2034` ignored globally; `SC2086`, `SC2129`, `SC2001` ignored for Actions workflows
- Prettier: configured via `.prettierrc.yaml`

## Key Observations

- There is no Node.js `package.json` or lockfile in this repo; Node.js is only used in CI (`markdownlint-cli2`)
- Python source code in this repo is limited to three scripts: `scripts/update-version.py`,
- The Go binary for `fritz-callmonitor2mqtt` is fully external; this repo only packages it into a HA add-on
- `uv` is the single tool for both local dev setup and container dependency installation; no `pip` / `pipenv` / `poetry`
- All container base images come from `ghcr.io/home-assistant/` — HA-specific, not generic Alpine or Python images
- `bashio` is a critical runtime dependency but not declared anywhere in this repo; it is baked into the HA base images
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

## Summary

## Line Length

- YAML: configured as warning (not error) in `.yamllint.yml`
- Markdown: enforced as error in `.markdownlint.json` (`MD013`)
- Prettier: `printWidth: 120` in `.prettierrc.yaml`
- Python scripts use the same 120-char limit by convention (no explicit config, no Black/Ruff in use)

## YAML Conventions

- Indentation: 2 spaces (`indent-sequences: true`)
- Line length: max 120, level `warning`
- No document start separator (`---` not required)
- Space required after `#` in comments
- Max 0 empty lines at start, max 1 at end
- No trailing spaces
- No tabs — enforced by CI check in `.github/workflows/lint.yml`
- Brackets/braces: 0 min spaces inside, 1 max spaces inside
- Line endings: LF only (CRLF forbidden, enforced by CI)

## Shell Script Conventions

- `SC1091` — "Not following: source" (sourcing from external paths is common in HA add-ons)
- `SC2034` — "appears unused" (variables exported for child processes)
- In GitHub Actions workflows additionally: `SC2086`, `SC2129`, `SC2001` (see `.actionlint.yml`)
- `run.sh` for fritz-callmonitor2mqtt: `#!/usr/bin/with-contenv bashio` with `# shellcheck shell=bash`
- `run.sh` for phone-logger: `#!/bin/sh` (POSIX shell, minimal)
- Scripts in `scripts/`: `#!/bin/bash` with `set -e`

## Markdown Conventions

- Max line length: 120 characters (applied to body text, code blocks, and headings)
- `proseWrap: always` — prettier wraps prose at 120 chars
- ATX-style headings (inferred from markdownlint defaults)
- H1 for document title
- H2 for major sections
- H3 for subsections with tables

## Python Conventions

- Module-level docstring (triple-quoted) on every script:
- Type hints on function signatures:
- `pathlib.Path` for all file paths (not `os.path`)
- `argparse` for CLI argument parsing with `formatter_class=argparse.RawDescriptionHelpFormatter`
- Guard `if __name__ == '__main__': sys.exit(main())`
- Explicit `flush=True` on print statements in containerized scripts
- `re.MULTILINE` flag when using `re.sub` / `re.search` on file content

## Versioning Conventions

| File                                     | Format    | Example   |
| ---------------------------------------- | --------- | --------- |
| `{addon}/config.yaml`                    | `X.Y.Z-N` | `1.7.3-0` |
| `{addon}/build.yaml` (as `args.VERSION`) | `X.Y.Z`   | `1.7.3`   |
| `{addon}/README.md` (shield badges)      | `vX.Y.Z`  | `v1.7.3`  |

- Never edit versions manually — use `make update-version ADDON=name VERSION=X.Y.Z`
- Subpatch (`-N`) resets to `-0` on upstream version change; increment for add-on-only fixes
- Enforced by pre-commit hook `scripts/validate-versions.sh` and by `make validate-versions`

## File Naming

## Dockerfile Conventions

## Import Organization (Python)

## Pre-commit Hook Summary

| Hook                 | Tool                    | Config                         |
| -------------------- | ----------------------- | ------------------------------ |
| YAML lint            | yamllint v1.35.1        | `.yamllint.yml`                |
| Trailing whitespace  | pre-commit-hooks v6.0.0 | (built-in)                     |
| End-of-file fixer    | pre-commit-hooks v6.0.0 | (built-in)                     |
| YAML syntax check    | pre-commit-hooks v6.0.0 | `--unsafe` flag                |
| Large file check     | pre-commit-hooks v6.0.0 | max 1000KB                     |
| Case conflict check  | pre-commit-hooks v6.0.0 | (built-in)                     |
| Merge conflict check | pre-commit-hooks v6.0.0 | (built-in)                     |
| Shebang checks       | pre-commit-hooks v6.0.0 | (built-in)                     |
| Line ending fix      | pre-commit-hooks v6.0.0 | `--fix=lf`                     |
| Shell lint           | shellcheck v0.10.0.1    | `-e SC1091 -e SC2034`          |
| Markdown format      | prettier v3.1.0         | `.prettierrc.yaml`             |
| GitHub Actions lint  | actionlint v1.7.3       | `.actionlint.yml`              |
| JSON format          | pre-commit-hooks v6.0.0 | `--indent=2`                   |
| Version consistency  | local script            | `scripts/validate-versions.sh` |

## Key Observations

- The `fail_fast: false` setting in `.pre-commit-config.yaml` means all hooks run even when earlier ones fail
- shellcheck is run twice: once via pre-commit (for `.sh` files) and again standalone in CI for all shell scripts
- Hadolint for Dockerfiles is disabled (commented out in `.pre-commit-config.yaml` and absent from CI workflow)
- The version validation hook only triggers on `fritz-callmonitor2mqtt/` file changes (the `files:` pattern in
- Python scripts use `uv tool install` for tool management — there is no `requirements.txt` for dev tools, only
- No commit message format is enforced (commit-msg hook install is best-effort: `|| true`)
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

## Summary

## Add-on Container Pattern

## Configuration Bridge

- Uses `bashio::config` calls inside a `#!/usr/bin/with-contenv bashio` script
- Maps each option directly to a namespaced environment variable (e.g., `FRITZ_CALLMONITOR_FRITZBOX_HOST`)
- Handles YAML arrays by iterating with index-based `bashio::config` calls and building comma-separated strings
- `exec`s the pre-compiled Go binary at `/opt/fritz-callmonitor2mqtt/fritz-callmonitor2mqtt`
- A thin `sh` script that runs `generate_config.py` first, then `exec`s the Python application
- `generate_config.py` reads `/data/options.json`, performs structural transformation (HA nested-dict schema → AppConfig
- The application reads its config from the path set in `PHONE_LOGGER_CONFIG`
- This two-stage approach exists because phone-logger's AppConfig expects lists of adapter objects while HA's schema

## Adapter Architecture (phone-logger)

- **input_adapters**: Sources of call events (e.g., `fritz_callmonitor` via TCP port 1012, `rest` via HTTP)
- **resolver_adapters**: Lookup/enrichment of phone numbers (e.g., `json_file`, `sqlite`, `msn`, `tellows`,
- **output_adapters**: Consumers of processed call events (e.g., `call_log`, `webhook`, `mqtt`)

## Upstream Binary Download Pattern

- **fritz-callmonitor2mqtt**: Downloads a pre-compiled Go binary tarball from GitHub Releases via `curl`; selects
- **phone-logger**: Downloads the upstream Python source tarball from GitHub Releases via `curl | tar xz`; installs

## Auto-Update System

- `upstream.repository`: the GitHub repo to watch (e.g., `akentner/fritz-callmonitor2mqtt`)
- `upstream.version_pattern`: git tag glob pattern (`v*`)
- `upstream.version_strip`: regex to strip tag prefix (`^v`)
- `addon.version_pattern: sync`: signals add-on version tracks upstream exactly

## 3-File Version Synchronization

| File                  | Format                 | Role                                                        |
| --------------------- | ---------------------- | ----------------------------------------------------------- |
| `{addon}/config.yaml` | `X.Y.Z-N`              | HA manifest version (subpatch suffix for add-on-only fixes) |
| `{addon}/build.yaml`  | `X.Y.Z`                | Docker build arg `VERSION` used in Dockerfile curl URL      |
| `{addon}/README.md`   | `vX.Y.Z` in badge URLs | Shield badge and release link                               |

## CI / Quality Gates

- pre-commit hooks (yamllint, trailing-whitespace, shellcheck, prettier for Markdown, actionlint)
- yamllint standalone
- actionlint
- shellcheck
- markdownlint-cli2
- Custom add-on structure validation (checks for required files, valid `config.yaml`, valid `.upstream.yaml`)
- YAML tab/CRLF detection

## Data Persistence

- fritz-callmonitor2mqtt: mounts to `/opt/fritz-callmonitor2mqtt/data`
- phone-logger: mounts to `/addon_config`

## Key Observations

- The configuration bridge is the most complex add-on-specific logic; each add-on solves this differently (env vars via
- The `generate_config.py` transform is the single choke-point for translating between HA schema conventions and
- phone-logger exposes an ingress port (8080) for HA ingress panel; fritz-callmonitor2mqtt does not use ingress
- Both add-ons are currently `amd64`-only in practice (other architectures commented out in `build.yaml`/`config.yaml`)
- The upstream source is always fetched at build time; there is no local copy of upstream code in this repository
- `uv` is used in phone-logger's container to manage Python deps and run the application; not used in CI for the add-on
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and
execution context stay in sync.

Use these entry points:

- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.

## Milestone Branch Convention

Every milestone is developed on a dedicated branch `milestone/vX.Y` and squash-merged into `main` upon completion.

When `/gsd:new-milestone` is invoked:

1. Create branch: `git checkout -b milestone/vX.Y`
2. Push to origin: `git push -u origin milestone/vX.Y`
3. All milestone development happens on this branch

When the milestone is complete (`/gsd:complete-milestone`):

```bash
git checkout main
git merge --squash milestone/vX.Y
git commit -m "feat(vX.Y): <milestone summary>"
git tag vX.Y
git push origin main --tags
```

<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile. This section is managed by
> `generate-claude-profile` -- do not edit manually.

<!-- GSD:profile-end -->
