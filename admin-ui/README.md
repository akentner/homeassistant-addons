# Home Assistant Add-on: Admin UI Blueprint

[![Release][release-shield]][release] ![Project Stage][project-stage-shield] ![Project Maintenance][maintenance-shield]

Blueprint for ingress admin GUIs: a demo page, a shared browser lib and a Python server skeleton.

## About

This add-on is the reference implementation of the admin-UI blueprint. It serves a small demo GUI behind Home Assistant
ingress and no port is published: the server answers only to the Supervisor ingress proxy. The shared lib (Preact
components, API client, themes) and the server skeleton are copied into other add-ons; the rules and the lib reference
live in [DOCS.md][docs].

It is marked experimental (`stage: experimental`): a blueprint and a demo, not for production use. All data shown is
fake and lives in memory only.

## Features

- Component gallery: badges, toasts, dialogs with type-to-confirm, copy fields, tables and tabs
- Token view in light and dark, and a German and English language switcher
- Sample CRUD against a fake API of the Python skeleton, including error states
- Rules checklist: every rule with the test or review that enforces it
- Spike page for the Home Assistant theme and layout integration, with a copy-as-JSON result block

## Security notes

- The GUI answers only to the Home Assistant ingress proxy, including static files and read requests.
- No port is published, so the gate cannot be reached around ingress.
- Only fake data is served, and the add-on has no options and no access to Home Assistant or its secrets.
- The add-on does not start at boot (`boot: manual`) and is visible to non-admin users (`panel_admin: false`): it is a
  demo that has to be started on purpose, and it exposes nothing that needs admin rights.

## Documentation

The blueprint rules, the lib reference, the sync workflow and the integration facts are in [DOCS.md][docs].

[docs]: DOCS.md
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-orange.svg
[release-shield]: https://img.shields.io/badge/version-v0.3.1-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v0.3.1
