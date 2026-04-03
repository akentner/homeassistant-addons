# Coding Conventions

_Last updated: 2026-04-03_

## Summary

This repository enforces conventions through a layered pre-commit system: YAML linting via yamllint, shell script
checking via shellcheck, Markdown formatting via prettier, GitHub Actions linting via actionlint, and a custom version
consistency validator. All rules are configured in `.pre-commit-config.yaml` and corresponding config files at the
repository root. The 120-character line limit is the universal rule applied across YAML, Markdown, and Python.

## Line Length

**Universal limit: 120 characters** applied across all file types.

- YAML: configured as warning (not error) in `.yamllint.yml`
- Markdown: enforced as error in `.markdownlint.json` (`MD013`)
- Prettier: `printWidth: 120` in `.prettierrc.yaml`
- Python scripts use the same 120-char limit by convention (no explicit config, no Black/Ruff in use)

## YAML Conventions

**Config:** `.yamllint.yml` (extends `relaxed` profile)

**Rules:**

- Indentation: 2 spaces (`indent-sequences: true`)
- Line length: max 120, level `warning`
- No document start separator (`---` not required)
- Space required after `#` in comments
- Max 0 empty lines at start, max 1 at end
- No trailing spaces
- No tabs — enforced by CI check in `.github/workflows/lint.yml`
- Brackets/braces: 0 min spaces inside, 1 max spaces inside
- Line endings: LF only (CRLF forbidden, enforced by CI)

**Home Assistant custom tags:** YAML files may use `!secret`, `!include`, and other HA-specific tags. Always parse with
`--unsafe` flag:

```bash
yq eval --unsafe '.version' fritz-callmonitor2mqtt/config.yaml
```

Pre-commit uses `check-yaml --unsafe` for the same reason.

**Quoted strings:** Use quotes for versions and sensitive values in YAML:

```yaml
version: "1.7.3-0"
VERSION: "1.7.3"
```

**Configuration option naming:** Use snake_case with logical prefix grouping:

```yaml
# Good: group by subsystem with underscore prefix
mqtt_broker: "core-mosquitto"
mqtt_port: 1883
fritzbox_host: "fritz.box"
pbx_country_code: "49"
app_log_level: "info"
```

## Shell Script Conventions

**Linter:** shellcheck v0.10.0.1 via `shellcheck-py`

**Ignored rules:**

- `SC1091` — "Not following: source" (sourcing from external paths is common in HA add-ons)
- `SC2034` — "appears unused" (variables exported for child processes)
- In GitHub Actions workflows additionally: `SC2086`, `SC2129`, `SC2001` (see `.actionlint.yml`)

**Shebang conventions:**

- `run.sh` for fritz-callmonitor2mqtt: `#!/usr/bin/with-contenv bashio` with `# shellcheck shell=bash`
- `run.sh` for phone-logger: `#!/bin/sh` (POSIX shell, minimal)
- Scripts in `scripts/`: `#!/bin/bash` with `set -e`

**Variable export pattern** (used in `fritz-callmonitor2mqtt/run.sh`):

```bash
FRITZ_CALLMONITOR_FRITZBOX_HOST=$(bashio::config 'fritzbox_host')
export FRITZ_CALLMONITOR_FRITZBOX_HOST
```

Assign first, then export — never inline export. Variable naming convention: `ADDON_PREFIX_SECTION_KEY` in
SCREAMING_SNAKE_CASE.

**Executable scripts:** All `.sh` files must have shebang lines and must be executable (enforced by
`check-executables-have-shebangs` and `check-shebang-scripts-are-executable` hooks).

## Markdown Conventions

**Formatter:** prettier v3.1.0 via `mirrors-prettier`

**Linter:** markdownlint-cli2 (in CI), markdownlint-cli (local pre-commit uses prettier for formatting)

**Rules:**

- Max line length: 120 characters (applied to body text, code blocks, and headings)
- `proseWrap: always` — prettier wraps prose at 120 chars
- ATX-style headings (inferred from markdownlint defaults)

**Header structure convention** (observed in `README.md`, `DOCS.md`):

- H1 for document title
- H2 for major sections
- H3 for subsections with tables

**Shield badge pattern** (required in each add-on `README.md` for version tracking):

```markdown
[release-shield]: https://img.shields.io/badge/version-v1.7.3-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v1.7.3
```

## Python Conventions

**Style:** No explicit formatter (no Black, Ruff, isort, or flake8 config found). Code in the repo follows PEP 8
conventions manually.

**Observed patterns** in `scripts/update-version.py` and `phone-logger/generate_config.py`:

- Module-level docstring (triple-quoted) on every script:
  ```python
  """
  Short description.
  More detail if needed.
  """
  ```
- Type hints on function signatures:
  ```python
  def update_config_yaml(addon_dir: Path, new_version: str, dry_run: bool = False) -> Tuple[bool, str, str]:
  ```
- `pathlib.Path` for all file paths (not `os.path`)
- `argparse` for CLI argument parsing with `formatter_class=argparse.RawDescriptionHelpFormatter`
- Guard `if __name__ == '__main__': sys.exit(main())`
- Explicit `flush=True` on print statements in containerized scripts
- `re.MULTILINE` flag when using `re.sub` / `re.search` on file content

**Shebang:** `#!/usr/bin/env python3`

## Versioning Conventions

This is the most strictly enforced convention in the repository. Three files must always be in sync per add-on.

| File                                     | Format    | Example   |
| ---------------------------------------- | --------- | --------- |
| `{addon}/config.yaml`                    | `X.Y.Z-N` | `1.7.3-0` |
| `{addon}/build.yaml` (as `args.VERSION`) | `X.Y.Z`   | `1.7.3`   |
| `{addon}/README.md` (shield badges)      | `vX.Y.Z`  | `v1.7.3`  |

**Rules:**

- Never edit versions manually — use `make update-version ADDON=name VERSION=X.Y.Z`
- Subpatch (`-N`) resets to `-0` on upstream version change; increment for add-on-only fixes
- Enforced by pre-commit hook `scripts/validate-versions.sh` and by `make validate-versions`

## File Naming

**Add-on files:** Fixed names — `config.yaml`, `build.yaml`, `Dockerfile`, `run.sh`, `README.md`, `DOCS.md`,
`.upstream.yaml`

**Add-on directories:** kebab-case matching upstream project name: `fritz-callmonitor2mqtt`, `phone-logger`

**Scripts:** kebab-case `.sh` for shell, snake_case `.py` for Python: `validate-versions.sh`, `update-version.py`,
`fix-markdown-lines.py`

**GitHub Actions workflows:** kebab-case: `lint.yml`

**Documentation:** SCREAMING_SNAKE_CASE for top-level guides: `README.md`, `CLAUDE.md`, `AGENTS.md`, `DOCS.md`

## Dockerfile Conventions

**Base images:** `ghcr.io/home-assistant/{arch}-base:{version}` (official HA base images)

**Label block:** Standardized OCI + HA label block at the bottom using `ARG`-injected values:

```dockerfile
ARG BUILD_ARCH
ARG BUILD_DATE
# ... etc
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.type="addon" \
    maintainer="akentner (https://github.com/akentner)"
```

**Build pattern:** Prefer downloading pre-built upstream binaries/sources rather than building from source where
possible (reduces image build time and complexity).

## Import Organization (Python)

```python
# Standard library
import re
import sys
import argparse
from pathlib import Path
from typing import Tuple

# Third-party (after blank line)
import yaml
```

## Pre-commit Hook Summary

All hooks run via `pre-commit run --all-files` (or automatically on `git commit`):

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
  `.pre-commit-config.yaml` is add-on-specific — must be updated when adding new add-ons)
- Python scripts use `uv tool install` for tool management — there is no `requirements.txt` for dev tools, only
  `requirements-lint.txt` generated at CI runtime via `pip freeze`
- No commit message format is enforced (commit-msg hook install is best-effort: `|| true`)
