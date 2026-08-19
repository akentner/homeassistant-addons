# Home Assistant Add-on: Authentik

[![Release][release-shield]][release] ![Project Stage][project-stage-shield] ![Project Maintenance][maintenance-shield]

Open-source Identity Provider — SSO, OAuth2/OIDC, LDAP, SAML, and more.

## About

[Authentik][authentik] is a self-hosted identity provider that supports modern authentication standards. Use it as a
central SSO hub for Home Assistant, Grafana, Nextcloud, or any OAuth2/OIDC-compatible service.

This add-on bundles PostgreSQL and Valkey (Redis-compatible) inside the container — no external database add-ons
required. Data is persisted in the HA add-on storage directory.

## Features

- SSO via OAuth2 / OIDC / SAML / LDAP / SCIM
- Built-in user management and group policies
- Flow engine for custom authentication logic (MFA, enrollment, recovery)
- Bundled PostgreSQL and Valkey — no external dependencies
- Data persistence across restarts via HA add-on storage

## Important Notes

**Direct port access required.** Authentik is not served through HA Ingress because OAuth2/OIDC flows require stable
callback URLs. Access the web interface via `http://<ha-ip>:9000`.

**Set a stable external URL in authentik** after first login: _System → Settings → Authentik Settings → "Authentik
URL"_. This is required for OAuth2 redirects to work correctly.

**HTTPS recommended.** Put authentik behind a reverse proxy (nginx, Traefik, Caddy) with a valid TLS certificate for
production use.

## First Start

1. Install the add-on and click **Start**
2. Open `http://<ha-ip>:9000` in your browser
3. Complete the initial setup wizard
4. Configure your desired authentication flows and providers

## Configuration

See [DOCS.md][docs] for all configuration options.

[authentik]: https://goauthentik.io
[docs]: https://github.com/akentner/homeassistant-addons/blob/main/authentik/DOCS.md
[release-shield]: https://img.shields.io/badge/version-v2026.8.0-blue.svg
[release]: https://github.com/goauthentik/authentik/releases/tag/version%2F2026.5.3
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-orange.svg
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
