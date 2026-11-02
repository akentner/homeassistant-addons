# Home Assistant Add-on: ntfy

[![Release][release-shield]][release] ![Project Stage][project-stage-shield] ![Project Maintenance][maintenance-shield]

Self-hosted push notification server with an admin GUI for users, ACLs and tokens.

## About

[ntfy][ntfy] sends push notifications to your phone or desktop through simple HTTP requests. This add-on runs the
upstream server and adds an ingress-only admin GUI in the Home Assistant sidebar. The server listens on port 8000 inside
the Home Assistant network (`72a005f5-ntfy:8000`); the GUI is not reachable from the LAN.

## Features

- Users, ACL rules (including `everyone` and wildcards), a topic x user matrix and tokens, managed in the GUI
- Live data in ntfy's own `auth.db` under `/data`, so it is part of Home Assistant backups
- Baseline users from the options (same fields as the old "ntfy Server" add-on), applied additively and never deleted
- Origin markers (`gui`, `options`) for users, rules and tokens
- Effective-rights lookup, random topic generator, health page with test publish
- Backups of `auth.db`, reset actions with typed confirmation, state export (schema 1)
- Bridge network, ntfy on a fixed container port, no `host_network`

## Security notes

- The GUI answers only to the Home Assistant ingress proxy, including static files and read requests.
- Passwords reach the ntfy CLI only through the environment and secrets are never logged.
- Token values are hidden in lists and revealed per row on demand. ntfy stores tokens in clear text, so `auth.db` and
  its backups contain password hashes and clear-text tokens.
- Add-on options, and therefore Home Assistant backups, contain the admin and baseline passwords in clear text.
- Port 8000 is not published on the host by default; map one only if a client needs it.

## Configuration

Set `base_url`, `admin_user` and `admin_password`, start the add-on and open the sidebar panel. See [DOCS.md][docs] for
all options, the migration from the old add-on and the behaviour of baseline entries.

## Credits

Upstream project: [ntfy][ntfy] by Philipp C. Heckel, licensed under Apache-2.0 and GPLv2. The icon comes from the
upstream repository. This repository does not bundle ntfy source; the release binary is downloaded at build time.

[docs]: DOCS.md
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[ntfy]: https://github.com/binwiederhier/ntfy
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-orange.svg
[release-shield]: https://img.shields.io/badge/version-v2.36.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v2.36.0
