# Home Assistant Add-on: CUPS

[![Release][release-shield]][release] ![Project Stage][project-stage-shield] ![Project Maintenance][maintenance-shield]

Share printers via CUPS with AirPrint/mDNS discovery that actually keeps working.

## About

This add-on shares one or more printers via CUPS, advertised over mDNS/DNS-SD for AirPrint discovery. It was forked from
the third-party `f1c878cb_cups` add-on after diagnosing a specific Avahi reflector slot-exhaustion bug that silently
broke AirPrint discovery over time (see `DIAGNOSIS.md` in this repository's `cups/` working notes for the full
investigation). The fixes for that bug — and two related mDNS reliability issues — are baked in as this add-on's shipped
defaults, not left as something an operator has to discover and configure.

## Features

- AirPrint-compatible printer sharing via CUPS, one or more printers configurable from a single options list
- Avahi mDNS reflector disabled by default (`avahi_reflector: false`) — prevents the legacy-unicast slot-exhaustion bug
  that this add-on exists to fix
- Fixed, stable mDNS hostname (`avahi_hostname`) independent of the container's transient hostname across restarts
- IPv6 mDNS resolution disabled by default (`avahi_use_ipv6: false`) — avoids resolving to an unreachable/unrouted IPv6
  ULA address for clients that can't use it
- Multiple printers configurable from a single `printers` options list

## Configuration

### Minimal example

```yaml
avahi_reflector: false
avahi_hostname: "cups"
avahi_use_ipv6: false
printers:
  - name: "office-printer"
    uri: "ipp://192.168.1.50:631/ipp/print"
    enabled: true
log_level: "info"
```

See [DOCS.md][docs] for the full options reference and design rationale.

[docs]: DOCS.md
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-yellow.svg
[release-shield]: https://img.shields.io/badge/version-v0.1.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v0.1.0
