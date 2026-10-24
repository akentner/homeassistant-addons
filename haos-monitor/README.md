# Home Assistant Add-on: HAOS Monitor

[![Release][release-shield]][release]

Diagnostic add-on for one or more HAOS hosts. Connects via SSH, appends kernel log and I/O stall indicators to
`/share/haos-monitor/<slug>.log`, serves a status JSON for Gatus and publishes MQTT discovery entities.

Own code, not an upstream wrapper (see the exception in [DOCS.md](DOCS.md)). Built locally by the Supervisor.

[release-shield]: https://img.shields.io/badge/version-v0.2.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v0.2.0
