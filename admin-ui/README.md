# Home Assistant Add-on: Admin UI Blueprint

[![Release][release-shield]][release] ![Project Stage][project-stage-shield] ![Project Maintenance][maintenance-shield]

Blueprint for ingress admin GUIs: a demo page, a shared browser lib and a Python server skeleton.

## About

This add-on is the reference implementation of the admin-UI blueprint. It serves a small demo GUI behind Home Assistant
ingress and no port is published: the server answers only to the Supervisor ingress proxy. The shared lib (Preact
components, API client, themes) and the server skeleton are copied into other add-ons; the rules and the lib reference
live in [DOCS.md][docs].

## Security notes

- The GUI answers only to the Home Assistant ingress proxy, including static files and read requests.
- The add-on does not start at boot (`boot: manual`) and has no options.

[docs]: DOCS.md
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-orange.svg
[release-shield]: https://img.shields.io/badge/version-v0.1.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v0.1.0
