# Home Assistant Add-on: ntfy

[![Release][release-shield]][release] ![Project Stage][project-stage-shield] ![Project Maintenance][maintenance-shield]

Self-hosted push notification server with an admin GUI for users, ACLs and tokens.

## About

[ntfy][ntfy] sends push notifications to your phone or desktop through simple HTTP requests. This add-on runs the
upstream server and adds an ingress-only admin GUI in the Home Assistant sidebar. The server listens on port 8000 inside
the Home Assistant network (`72a005f5-ntfy:8000`).

See [DOCS.md][docs] for the configuration reference.

[docs]: DOCS.md
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[ntfy]: https://github.com/binwiederhier/ntfy
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-orange.svg
[release-shield]: https://img.shields.io/badge/version-v2.36.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v2.36.0
