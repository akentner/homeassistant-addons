# Home Assistant Add-on: Meridian Claude Max Proxy

[![Release][release-shield]][release] ![Project Stage][project-stage-shield] ![Project Maintenance][maintenance-shield]

Expose a local Anthropic-compatible API on port 3456, backed by your Claude Max subscription.

## About

This add-on runs [Meridian][meridian], a local proxy that translates Anthropic API calls to Claude Max requests. It
allows any tool that speaks the Anthropic API (Cursor, Continue, custom scripts) to use your Claude Max subscription
without additional API costs.

**Requirements:**

- An active Claude Max subscription
- Initial authentication via `claude login` (one-time setup; credentials persist across restarts)

## First-Time Setup

Before starting the add-on, you must authenticate with Anthropic:

1. Install the **Terminal & SSH** add-on from the Home Assistant add-on store
2. Open the terminal
3. Run: `docker exec -it $(docker ps -qf name=meridian) sh`
4. Inside the container run: `claude login`
5. Complete the OAuth flow in your browser
6. Restart the Meridian add-on

After authentication, credentials are stored in `/data/.claude` and persist across container restarts.

## Usage

Once running, the proxy is available at `http://<ha-host>:3456`.

Compatible with any Anthropic API client — set the base URL to `http://<ha-host>:3456/v1`.

[meridian]: https://github.com/rynfar/meridian
[release-shield]: https://img.shields.io/badge/version-v1.45.3-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v1.45.3
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[project-stage-shield]: https://img.shields.io/badge/project%20stage-production-green.svg
