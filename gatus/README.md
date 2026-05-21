# Home Assistant Add-on: Gatus

[![Release][release-shield]][release] ![Project Stage][project-stage-shield] ![Project Maintenance][maintenance-shield]

Automated status and uptime monitoring with a beautiful dashboard.

## About

[Gatus][gatus] is a developer-oriented health dashboard that monitors your services and notifies you when they go down.
It supports HTTP, ICMP, TCP, and DNS checks with configurable conditions, alerting via 40+ providers (Slack, Discord,
PagerDuty, email, etc.), and persistent storage.

This add-on runs Gatus behind HA Ingress — no port exposure required. The dashboard is accessible directly from the Home
Assistant sidebar.

## Features

- HTTP, ICMP, TCP, and DNS endpoint monitoring
- Configurable check intervals and conditions
- 40+ alerting providers (Slack, Discord, Teams, PagerDuty, email, and more)
- Prometheus metrics endpoint (optional)
- Persistent SQLite storage (optional)
- HA Ingress integration — no firewall rules needed

## Configuration

Place your Gatus endpoint configuration in `/addon_config/config.yaml` inside the add-on data directory. The add-on
merges operational settings (port, storage, metrics) from the HA options — do not set `web:` in your config file, it
will be overridden.

### Minimal example `/addon_config/config.yaml`

```yaml
endpoints:
  - name: Home Assistant
    url: http://homeassistant.local:8123
    interval: 1m
    conditions:
      - "[STATUS] == 200"

  - name: Router
    url: icmp://192.168.1.1
    interval: 30s
    conditions:
      - "[CONNECTED] == true"
```

See [DOCS.md][docs] for full configuration reference and alerting examples.

[docs]: DOCS.md
[gatus]: https://github.com/TwiN/gatus
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[project-stage-shield]: https://img.shields.io/badge/project%20stage-production-green.svg
[release-shield]: https://img.shields.io/badge/version-v5.36.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v5.36.0
