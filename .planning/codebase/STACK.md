# Technology Stack

_Last updated: 2026-04-03_

## Summary

This repository is a Home Assistant Add-ons repository hosting two add-ons: `fritz-callmonitor2mqtt` (a pre-compiled Go
binary downloaded at image build time) and `phone-logger` (a Python application managed via `uv`). Both add-ons run as
Docker containers on Alpine Linux base images provided by the Home Assistant project. Development tooling is entirely
Python-based (pre-commit, yamllint, shellcheck-py) and managed locally via `uv tool install`.

## Languages

**Primary (add-on runtime):**

- **Go** — `fritz-callmonitor2mqtt` upstream binary; compiled externally, downloaded as a release artifact during Docker
  build. No Go source lives in this repo.
- **Python 3.12** — `phone-logger` upstream source downloaded at build time; add-on provides `generate_config.py` as the
  sole Python file in this repo.

**Scripting / glue:**

- **Bash** — `run.sh` in both add-ons (executed via `bashio`), `scripts/validate-versions.sh`, `scripts/setup-hooks.sh`
- **Python 3** — `scripts/update-version.py`, `scripts/fix-markdown-lines.py` (stdlib only, no external deps)

## Runtime

**Containers:**

- `fritz-callmonitor2mqtt`: Alpine 3.22 via `ghcr.io/home-assistant/amd64-base:3.22`
- `phone-logger`: Alpine 3.20 + Python 3.12 via `ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20`

**Python Package Manager (phone-logger container):**

- `uv` — installed via `COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv`
- Dependencies installed from upstream `uv.lock` with `uv sync --frozen --no-dev --no-install-project`
- Runtime invocation: `uv run --no-dev python ...`

**Target Architectures:**

- Both add-ons currently build for `amd64` only (other arches commented out in `config.yaml` / `build.yaml`)

## Frameworks & Key Libraries

**Home Assistant Add-on Framework:**

- `bashio` — HA utility library available in all HA base images; used in both `run.sh` files for reading add-on config
  (`bashio::config`, `bashio::log.*`). Invoked via shebang `#!/usr/bin/with-contenv bashio`.

**phone-logger upstream dependencies (managed in upstream repo, installed via uv.lock):**

- `lxml`, `libxml2`, `libxslt` — XML/HTML parsing (build deps installed via apk, then removed)

**generate_config.py dependencies (phone-logger add-on):**

- `json` — stdlib, reads `/data/options.json`
- `yaml` (PyYAML) — writes config to `/tmp/phone-logger-config.yaml`; available from upstream's uv.lock

## Build Tools

**Docker:**

- Both Dockerfiles use multi-stage-style `ARG BUILD_FROM` / `FROM ${BUILD_FROM}` pattern
- `fritz-callmonitor2mqtt` Dockerfile: downloads a `.tar.gz` release from GitHub at build time via `curl`
- `phone-logger` Dockerfile: downloads upstream source tarball from GitHub tags at build time via `curl | tar`

**apk (Alpine Package Manager):**

- `fritz-callmonitor2mqtt`: installs `curl`, `tar`
- `phone-logger`: installs build deps (`gcc`, `musl-dev`, `libxml2-dev`, `libxslt-dev`, `python3-dev`, `tzdata`, `curl`,
  `tar`), then removes build deps after `uv sync`

## Development Tooling

**Task Runner:** `make` — `Makefile` at repo root; primary developer interface

**Dependency & Tool Installer:** `uv` — used locally to install pre-commit and other Python tools
(`uv tool install pre-commit`, `uv tool install yamllint`, `uv tool install shellcheck-py`)

**Pre-commit:** `pre-commit` >= 3.0.0 — enforces all linting and version validation on commit

**Linters / Formatters:**

| Tool                | Version  | Purpose             | Config file               |
| ------------------- | -------- | ------------------- | ------------------------- |
| `yamllint`          | 1.35.1   | YAML lint           | `.yamllint.yml`           |
| `shellcheck-py`     | 0.10.0.1 | Shell script lint   | `.pre-commit-config.yaml` |
| `prettier`          | 3.1.0    | Markdown formatting | `.prettierrc.yaml`        |
| `actionlint`        | 1.7.3    | GitHub Actions lint | `.actionlint.yml`         |
| `markdownlint-cli2` | latest   | Markdown lint       | `.markdownlint.json`      |

**CI Platform:** GitHub Actions — single workflow at `.github/workflows/lint.yml`

**Dev Container:** `ghcr.io/home-assistant/devcontainer:3-addons` — VS Code devcontainer definition at
`.devcontainer/devcontainer.json`

## Configuration

**Linting rules:**

- YAML: 2-space indent, 120-char line limit, relaxed base (`.yamllint.yml`)
- Markdown: 120-char line limit (`.markdownlint.json`)
- Shell: `SC1091` and `SC2034` ignored globally; `SC2086`, `SC2129`, `SC2001` ignored for Actions workflows
- Prettier: configured via `.prettierrc.yaml`

**Version management:** 3-file versioning scheme enforced by `scripts/validate-versions.sh` as a pre-commit hook. Never
edit versions manually — use `make update-version ADDON=<name> VERSION=<x.y.z>`.

## Key Observations

- There is no Node.js `package.json` or lockfile in this repo; Node.js is only used in CI (`markdownlint-cli2`)
- Python source code in this repo is limited to three scripts: `scripts/update-version.py`,
  `scripts/fix-markdown-lines.py`, and `phone-logger/generate_config.py`
- The Go binary for `fritz-callmonitor2mqtt` is fully external; this repo only packages it into a HA add-on
- `uv` is the single tool for both local dev setup and container dependency installation; no `pip` / `pipenv` / `poetry`
  in use
- All container base images come from `ghcr.io/home-assistant/` — HA-specific, not generic Alpine or Python images
- `bashio` is a critical runtime dependency but not declared anywhere in this repo; it is baked into the HA base images
