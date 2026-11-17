# Home Assistant Add-on: Marketplace Repo Proxy

[![Release][release-shield]][release] ![Project Stage][project-stage-shield] ![Project Maintenance][maintenance-shield]

Makes private GitHub add-on repositories installable from the Home Assistant store.

## About

The Home Assistant add-on store (and HACS) cannot add repositories that need authentication, so add-ons from private
GitHub repositories cannot be installed. This add-on is planned as a small proxy: it holds the access credentials,
fetches the private repository and serves it as a plain git repository under a hashed, unguessable URL. The store then
adds that URL like any public repository. Access can optionally be restricted to the internal HA add-on network.

**Status: scaffold.** No proxy service exists yet; see [GOAL.md][goal] for the goal, scope and open questions.

It is our own code, not an upstream wrapper (see [DOCS.md][docs]).

## Configuration

Only `log_level` exists so far. See [DOCS.md][docs].

[docs]: DOCS.md
[goal]: GOAL.md
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-orange.svg
[release-shield]: https://img.shields.io/badge/version-v0.1.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v0.1.0
