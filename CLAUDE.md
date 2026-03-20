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
