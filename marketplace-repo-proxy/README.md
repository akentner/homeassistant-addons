# Home Assistant Add-on: Marketplace Repo Proxy

[![Release][release-shield]][release] ![Project Stage][project-stage-shield] ![Project Maintenance][maintenance-shield]

Makes private GitHub add-on repositories installable from the Home Assistant store.

## About

The Home Assistant add-on store (and HACS) cannot add repositories that need authentication, so add-ons from private
GitHub repositories cannot be installed. This add-on is a small proxy: it holds the access credentials, fetches the
private repository and serves it as a plain git repository under a hashed, unguessable URL. The store then adds that URL
like any public repository. Access can optionally be restricted to the internal HA add-on network.

**Status: experimental.** The add-on syncs the configured private repositories with a read-only GitHub token and serves
them read-only under per-user store URLs on the internal Home Assistant network. Users are managed with the `mrp`
command inside the container. A management page, self-registration in the local store, a provisioning API and documented
public URLs follow in later versions; see [GOAL.md][goal] for the goal and scope.

It is our own code, not an upstream wrapper (see [DOCS.md][docs]).

## Configuration

Options, store URLs, user management, sync status and security notes are described in [DOCS.md][docs].

[docs]: DOCS.md
[goal]: GOAL.md
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-orange.svg
[release-shield]: https://img.shields.io/badge/version-v0.1.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v0.1.0
