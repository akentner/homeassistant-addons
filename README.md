# Home Assistant Add-ons by akentner

Home Assistant Add-ons with automated upstream monitoring and version bumping via GitHub Actions.

This repository hosts production add-ons for [Home Assistant Supervisor][ha-supervisor]. Each add-on ships with:

- A strict `config.yaml` schema validated by `scripts/validate-addon-config.py`
- A `build.yaml` that pins the Docker base image and the add-on version
- A `.upstream.yaml` (where applicable) that points the auto-update workflow at the upstream project
- A Dockerfile that vendors runtime assets where possible (no CDN dependency at runtime)

Add-on documentation: <https://developers.home-assistant.io/docs/add-ons>

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL
pre-filled.][ha-add-repo-badge]][ha-add-repo]

## Add-ons

### [Markdown Renderer](./markdown-renderer)

![Supports amd64 Architecture][amd64-shield]

_Renders Markdown directories as Docsify SPAs through Home Assistant Ingress, with optional git-based sync._

Renders Markdown directories as Docsify SPAs through Home Assistant Ingress. Multiple namespaces are served as isolated
SPAs under a single add-on, each with vendored Mermaid + Kroki renderer support. Optional per-namespace `git_pull` keeps
content fresh from a remote without manual intervention.

**Features:**

- Multi-namespace Docsify serving through a single HA Ingress panel
- Vendored Docsify 4.13 + Mermaid 11 JS — no runtime CDN dependency
- Per-namespace optional git pull at startup and on a configurable background interval
- Mermaid diagrams render in fenced ` ```mermaid ` blocks; PlantUML (and other Kroki formats) in fenced code blocks
  route to the configured `kroki_url` (defaults to <https://kroki.io>)
- Invalid namespace names fail-fast at startup with a clear log message

### [Phone Logger](./phone-logger)

![Supports amd64 Architecture][amd64-shield]

_Phone logging and adapter integration for Home Assistant._

Flexible input → resolver → output adapter pipeline for Home Assistant. Drop-in replacement for the legacy Fritz!Box
call monitor workflow, backed by an upstream project that this repository tracks via auto-update.

**Features:**

- Flexible configuration of input, resolver, and output adapters
- Strict, Home Assistant-compliant schema
- Data persistence via the add-on volume

### [Meridian Claude Max Proxy](./meridian)

![Supports amd64 Architecture][amd64-shield]

_Exposes a local Anthropic-compatible API on port 3456 backed by a Claude Max subscription._

Drop-in replacement for `api.anthropic.com` on your local network. Lets Home Assistant automations call Claude through
the standard Anthropic SDK using a Claude Max subscription instead of per-token API keys.

**Features:**

- Local Anthropic-compatible API proxy backed by Claude Max
- Configurable port (default: 3456)
- Automatic upstream version tracking

### [Network Tools](./network-tools)

![Supports amd64 Architecture][amd64-shield]

_Network diagnostics and ARP-based host detection for Home Assistant._

Layer-2 host detection via `arping`, plus `nmap`, `dig`, `ping`, and `traceroute` for manual diagnostics. Scans a
configurable host list at a configurable interval and exposes results through a REST endpoint that integrates with Home
Assistant via a REST sensor.

**Features:**

- ARP-based host detection with MAC verification and reachability tracking
- Configurable scan interval (default: 30s); configurable `disconnect_threshold` for flapping suppression
- `host_network: true` for full Layer-2 access (raw ARP packets)
- REST endpoint at `/arping_scan.json` consumable by the [REST integration][ha-rest-integration]

### [Gatus](./gatus)

![Supports amd64 Architecture][amd64-shield]

_Automated status and uptime monitoring with a beautiful dashboard._

Wraps the upstream [TwiN/gatus][gatus-upstream] image with a Home Assistant-compliant schema. Tracks upstream releases
daily and bumps the add-on version when a new release ships.

**Features:**

- Endpoint health monitoring with configurable HTTP/TCP/ICMP probes
- Configurable alert destinations (Slack, Discord, email, …)
- Themeable status page served as a Docsify-like SPA

### [Authentik](./authentik)

![Supports amd64 Architecture][amd64-shield]

_Open-source Identity Provider — SSO, OAuth2/OIDC, LDAP, SAML, and more._

Self-hosted identity provider with a built-in user management UI, flow engine for MFA/enrollment/recovery, and support
for every major authentication standard. Ships with bundled PostgreSQL and Valkey (Redis-compatible) — no external
database add-ons required.

**Features:**

- SSO via OAuth2 / OIDC / SAML / LDAP / SCIM
- Built-in user management and group policies
- Flow engine for custom authentication logic (MFA, enrollment, recovery)
- Bundled PostgreSQL and Valkey — no external dependencies
- Automatic migrations on startup

**Note:** Authentik is not served via HA Ingress. Access via `http://<ha-ip>:9000` and configure a reverse proxy with
TLS for production use.

### [Coding Assistants](./coding-assistants)

![Supports amd64 and aarch64 Architectures][amd64-shield] ![Supports amd64 and aarch64 Architectures][aarch64-shield]

_Terminal with Claude Code, OpenCode, and GitHub Copilot CLI — accessible via SSH and web terminal._

Pre-alpha developer add-on that bundles Claude Code, OpenCode, and the GitHub Copilot CLI into a single container
exposed via SSH and a web terminal. Designed for Home Assistant OS / Supervised installations where installing these
tools on the host is not practical.

**Status:** Pre-alpha — APIs and configuration may change without notice.

## Repository Conventions

- **Three-file versioning scheme** — every add-on keeps `config.yaml` (with subpatch `X.Y.Z-N`), `build.yaml` (no
  subpatch, just `X.Y.Z`), and README badges (base `vX.Y.Z`) in sync. Use `make update-version ADDON=foo VERSION=1.2.3`
  to bump; manual edits will fail the `validate-versions.sh` pre-commit hook.
- **Auto-update for upstream wrappers** — add-ons that wrap an upstream project carry a `.upstream.yaml` and participate
  in the daily `Auto Update` GitHub Actions workflow. The workflow bumps `build.yaml` and `config.yaml` to the latest
  upstream release and adds the release notes to `CHANGELOG.md`.
- **Vendored assets over CDNs** — runtime JS/CSS (Docsify, Mermaid, etc.) is downloaded at image build time and shipped
  inside the container. No CDN requests at runtime — required for ingress isolation and air-gapped installs.

## Development

### Adding a New Add-on

1. Create the directory: `mkdir my-addon`
2. Add the required files: `config.yaml`, `build.yaml`, `Dockerfile`, `run.sh`, `README.md`
3. Add `.upstream.yaml` only if the add-on wraps an upstream project
4. Run `make init` once to install development tooling
5. Run `make validate-addons` to verify the new add-on schema
6. Update this README with the new add-on entry

### Local Tooling

```bash
# One-time setup
make init

# Lint all files (pre-commit hooks)
make lint

# Validate add-on configs
make validate-addons

# Run every check
make check-all

# Bump an add-on's version (NEVER edit versions manually)
make update-version ADDON=markdown-renderer VERSION=1.1.0-4
```

### Auto-Update System

The repository includes an automated system that monitors upstream repositories for new releases and bumps the
corresponding add-ons. See [docs/AUTO_UPDATE_GUIDE.md](./docs/AUTO_UPDATE_GUIDE.md) for the full architecture and
operational guide.

### Code Quality

This repository uses automated linting enforced by pre-commit hooks and GitHub Actions:

- **YAML** — [yamllint][yamllint] for configuration files
- **Shell** — [shellcheck][shellcheck] for `run.sh` and helper scripts
- **Markdown** — [markdownlint-cli2][markdownlint-cli2] for `*.md` files
- **GitHub Actions** — [actionlint][actionlint] for `.github/workflows/*.yml`
- **Dockerfiles** — [hadolint][hadolint] for `Dockerfile` best practices
- **Versioning** — `scripts/validate-versions.sh` enforces the three-file scheme

## Documentation

- [Auto-Update System Guide](./docs/AUTO_UPDATE_GUIDE.md) — architecture and operations for the daily update workflow
- [Versioning & Release Workflow](./docs/DEVELOPMENT.md) — three-file scheme rationale and `make update-version`
- [Home Assistant Add-on Development][ha-addons-docs] — official documentation

[ha-supervisor]: https://developers.home-assistant.io/docs/add-ons
[ha-add-repo-badge]: https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg
[ha-add-repo]:
  https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fakentner%2Fhomeassistant-addons
[ha-rest-integration]: https://www.home-assistant.io/integrations/rest/
[ha-addons-docs]: https://developers.home-assistant.io/docs/add-ons
[gatus-upstream]: https://github.com/TwiN/gatus
[markdownlint-cli2]: https://github.com/DavidAnson/markdownlint-cli2
[actionlint]: https://github.com/rhysd/actionlint
[hadolint]: https://github.com/hadolint/hadolint
[shellcheck]: https://github.com/koalaman/shellcheck
[yamllint]: https://github.com/adrienverge/yamllint

<!-- Architecture shields -->

[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
