# AGENTS.md - AI Agent Guide for Home Assistant Add-ons Repository

This guide helps AI coding agents understand the structure, conventions, and workflows specific to this Home Assistant
add-ons repository.

## 🤖 Agent Behavior Guidelines

Before taking action on critical tasks (version bumps, deployment changes, add-on removals, CI/CD modifications):

- **Ask first, act later.** If the intent or scope is unclear, ask a clarifying question before making changes.
- **Challenge the approach.** If the user's plan seems risky, inconsistent with conventions, or likely to cause
  problems, say so — even if it contradicts what was asked.

For trivial changes (docs, formatting, comments), proceed directly without asking.

## 🏗️ Architecture Overview

**What this is:** A Home Assistant add-ons repository with automated upstream version monitoring. Currently hosts the
following production add-ons: **Phone Logger** and **Meridian Claude Max Proxy**.

**Key structural decision:** Each add-on lives in its own directory with:

- `config.yaml` - Home Assistant add-on manifest (defines options, schema, Docker settings)
- `build.yaml` - Docker build configuration with upstream version tracking
- `Dockerfile` - Container image definition
- `run.sh` - Startup script for the add-on process
- `.upstream.yaml` - Auto-update configuration (monitors external GitHub repos for releases)
- `DOCS.md` - User-facing configuration documentation

**Why this structure:** Allows for independent, scalable management of multiple add-ons with automated version bumping.
The `.upstream.yaml` enables daily automatic checks for upstream releases and parallel updates.

## 🔑 Critical Versioning Scheme

**IMPORTANT: This project uses a unique 3-file versioning system that MUST be kept in sync.**

| File               | Format    | Example   | Rule                                                      |
| ------------------ | --------- | --------- | --------------------------------------------------------- |
| `config.yaml`      | `X.Y.Z-N` | `1.7.3-0` | **Always** use subpatch format with dash-separated number |
| `build.yaml`       | `X.Y.Z`   | `1.7.3`   | Upstream binary version, NO subpatch                      |
| `README.md` badges | `vX.Y.Z`  | `v1.7.3`  | Display version with `v` prefix in badges/links           |

**Versioning rules:**

- **Subpatch (`-N`) bumps** are for changes that don't touch the add-on's program logic:
  - Dockerfile changes (new/changed apk packages, base-image bumps, build-arg tweaks)
  - ConfigFlow-only changes (YAML schema / option order / default values / DOCS+README copy)
  - Forcing a new version rollout (e.g. when HA Supervisor caches the previous one and doesn't surface an "update
    available" badge)
- **SemVer (`X.Y.Z`) bumps** are for program-logic changes:
  - Upstream binary or library updates
  - Add-on's own scripts (Python, shell) — new features, refactors, bug fixes in behavior
  - When SemVer changes, the subpatch **resets to `-0`**
- Use `make update-version ADDON=<name> VERSION=<x.y.z>` — never edit versions manually
- **Validation is enforced by pre-commit hook:** `internal/validate-versions.sh` checks all three files match

**Worked examples** (network-tools):

| Bump                  | Why                                                                      | Category      |
| --------------------- | ------------------------------------------------------------------------ | ------------- |
| `0.2.3-1` → `0.3.0-0` | New `mdns_scan.py` + tests + verify script                               | Program logic |
| `0.3.0-0` → `0.3.0-1` | `avahi-utils` → `avahi-tools` (Alpine package rename)                    | Dockerfile    |
| `0.3.0-1` → `0.4.0-0` | Collapse 3 mDNS entities → 1 binary sensor + arping attribute enrichment | Program logic |

**Why this design:** Separates upstream version tracking (build.yaml) from add-on-specific patches (config.yaml
subpatch). Enables automated upstream sync while allowing local bug fixes without breaking the sync mechanism.

## ⚙️ Auto-Update System

**How it works:**

1. Each add-on has `.upstream.yaml` defining GitHub repository to monitor
2. GitHub Actions workflow runs daily at 6:00 UTC
3. For each add-on: fetches latest release, compares versions
4. On new version: automatically updates `build.yaml` and `config.yaml`, creates commit
5. Updates run in parallel with independent error handling (one failure doesn't block others)

**Example `.upstream.yaml`:**

```yaml
upstream:
  repository: "owner/project-name"
  version_pattern: "v*" # Match tags like v1.0.0
  version_strip: "^v" # Remove v prefix from version

addon:
  version_pattern: "sync" # Use same version as upstream (auto-increment subpatch to -0)
```

**When adding new add-ons:** Include `.upstream.yaml` with proper repository configuration. Without it, the add-on won't
participate in auto-updates.

## 🛠️ Developer Workflows

### Version Updates (Manual)

```bash
# Update an add-on to version 1.7.2
make update-version ADDON=<addon-name> VERSION=1.7.2

# With GitHub release verification
make update-version ADDON=<addon-name> VERSION=1.7.2 CHECK_RELEASE=yes

# Skip tag creation (e.g. for emergency patches; tag must be created separately)
make update-version ADDON=<addon-name> VERSION=1.7.2 NO_TAG=yes

# Dry-run (shows what would change without modifying files)
./internal/update-version.py <addon-name> 1.7.2 --dry-run
```

**What this does:** Python script (`internal/update-version.py`) updates `config.yaml`, `build.yaml`, and the README
badge, then **creates and pushes the `v<version>` git tag** by default. The tag is required because
`.github/workflows/build.yml` only builds Docker images on `git push` of a `v*` tag. Without the tag, the HA supervisor
sees the new version in the store but the image at `ghcr.io` does not exist → 404 → "Unknown error, see supervisor
logs".

A pre-push hook (`internal/check-version-tags.sh`, installed by `make init`) verifies that any addon whose
`config.yaml`/`build.yaml` is being pushed has a matching `v<version>` tag locally or on origin. Bypass with
`git push --no-verify` only in emergencies.

Always run this for version bumps — never manually edit versions.

### Code Quality & Validation

```bash
# One-time development setup (installs all linters)
make init

# Run all pre-commit hooks (YAML, shell, markdown, GitHub Actions, versioning)
pre-commit run --all-files

# Quick lint checks
make lint                    # Runs yamllint, shellcheck, markdownlint
make validate-addons        # Validates add-on configs
```

**Pre-commit hooks enforce:**

- YAML syntax and style (via yamllint)
- Shell script correctness (via shellcheck, ignoring SC1091 for sourcing)
- Markdown formatting (via markdownlint-cli2)
- GitHub Actions workflow syntax (via actionlint)
- Version consistency across the three version files (custom hook)

## 📋 Project Conventions

### File Naming & Location Conventions

- Add-on-specific logic: keep in `{addon-name}/` directory
- Global utilities: place in `internal/` (Python for complex logic, shell for simple tasks)
- Documentation: `README.md` for user docs, `DOCS.md` for configuration reference, `DEVELOPMENT.md` for developer
  guidelines
- GitHub Workflows: stored in `.github/workflows/` (currently only `lint.yml`)

### Configuration Standards

- All user-facing configuration in add-on `config.yaml` with `options` section defining defaults
- Schema section validates configuration types (string, int, bool, list)
- Use descriptive names with underscores: `mqtt_broker`, `port`, `log_level`
- YAML files: always quoted strings for versions and sensitive values

## 🔗 Integration Points

### Home Assistant Integration

- Add-ons communicate with HA Supervisor via config volume mounts
- Home Assistant provides MQTT broker (`core-mosquitto`) automatically
- Add-on discovery via `repository.yaml` (defines repository name, URL, maintainer)

### External Dependencies

- Build relies on external Docker images defined in `Dockerfile`
- GitHub Actions for CI/CD (no external service dependencies for workflow execution)

### Linting & CI/CD Pipeline

- Pre-commit hooks run before every commit (enforce consistency locally)
- GitHub Actions (`lint.yml`) runs on push to main/develop and on PRs
- Workflow caches Python/Node dependencies and pre-commit environments for speed

## 📝 Common Editing Scenarios

### Adding a new add-on

1. Create directory: `{addon-name}/`
2. Add required files: `config.yaml`, `build.yaml`, `Dockerfile`, `run.sh`, `README.md`, `.upstream.yaml`
3. Update root `README.md` to list new add-on
4. Version in `config.yaml` should be `X.Y.Z-0` format
5. Run `make validate-addons` to verify config structure

### Updating an add-on to a new upstream release

1. **Don't edit versions manually.** Use: `make update-version ADDON=<addon-name> VERSION=X.Y.Z`
2. Script automatically updates all three version files and badges
3. Pre-commit hook validates consistency before commit

### Fixing a bug in the add-on (not upstream)

1. Make code changes in `{addon-name}/` (shell, Dockerfile, etc.)
2. Increment subpatch: manually edit `config.yaml` version from `1.7.3-0` to `1.7.3-1` (don't change `build.yaml`)
3. Pre-commit hook validates this is correct
4. Commit normally

### Adding markdown documentation

- Use `markdownlint-cli2` formatting rules (enforced by pre-commit)
- Max line length: 120 characters (enforced by `.markdownlint.json`)
- Use standard GitHub markdown syntax

## 🚨 Critical Gotchas

1. **Never manually edit versions.** Use `make update-version` script. The three-file sync is enforced by validation, so
   manual changes will fail pre-commit.

2. **Subpatch always resets to -0 on upstream update.** When upstream releases new version, the automation sets subpatch
   back to `-0`. This is intentional—local fixes are temporary.

3. **YAML special tags:** Pre-commit uses `check-yaml --unsafe` to allow Home Assistant custom YAML tags (like
   `!secret`, `!include`). Normal YAML validators would fail on these.

4. **Shell script sourcing:** shellcheck ignores `SC1091` (can't follow source). Add-ons often source files from other
   directories, so this warning is disabled globally.

5. **Auto-update parallel execution:** Updates run independently (`fail-fast: false`). One failing add-on doesn't block
   others, but issues are created per add-on.

## 🔌 Home Assistant Instanz-Zugriff

Aktive Live-Verbindung: `ha-nextgen` (`https://ha-nextgen.akentner.de`), 4112 Entities, Long-Lived-Token in
`~/.config/ha-cli.env`, geladen via Fish+Bitwarden. Werkzeuge: REST-API, WebSocket-API, `ha`-Supervisor-CLI, Skills
`~/.opencode/skills/home-assistant/` und `~/.opencode/skills/integrations/`.

**Details, offene Punkte, Konventionen:** siehe `.agents/memory/ha-access.md`.

**Vor `ha supervisor`/`ha core update`/Backup-Operationen:** prüfen, welche Instanz der Supervisor-Endpoint der `ha`-CLI
tatsächlich erreicht (`ha info` zeigt nur Host-Daten, kein Endpoint-Flag gesetzt).

## 🧰 Installierte Skills

Detaillierte Inventur mit Zweck und Mechanik: siehe `.agents/memory/installed-skills.md`.

Kurzfassung:

- `wrangler` (Cloudflare offiziell, Projekt-Skill) — Cloudflare Workers/Tunnel-CLI, KV/R2/D1/DO/Containers/Queues
- `home-assistant-best-practices` (Projekt-Skill) — HA-Automation/Dashboard-Hilfe
- `home-assistant`, `integrations` (global in `~/.opencode/skills/`) — HA-Verbindungsaufbau + Integrations-Diagnose

Verwaltung via `npx skills` (`find`/`add`/`list`/`update`/`remove`). **Im Skill nachschauen, statt aus Erinnerung** —
viele Skills erzwingen aktuelle Doku statt vortrainiertem Wissen.

## 📚 Key Files to Understand First

- **`README.md`** - Project overview and add-on list
- **`Makefile`** - Command definitions for common workflows
- **`docs/DEVELOPMENT.md`** - Detailed versioning rules and rationale
- **`docs/AUTO_UPDATE_GUIDE.md`** - Auto-update system architecture
- **`internal/validate-versions.sh`** - Pre-commit version validation logic
- **`internal/update-version.py`** - Automated version update tool
- **`.pre-commit-config.yaml`** - All linting tools and rules
- **`phone-logger/config.yaml`** - Example add-on manifest structure
