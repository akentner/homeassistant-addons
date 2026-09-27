# Home Assistant Add-on: Network Tools

[![Release][release-shield]][release] [![License][license-shield]][license]

Network diagnostics and ARP-based host detection for Home Assistant.

## Features

- **arping-based host detection** — ARP-Ping per Host, MAC verification, reachability tracking, enriched attributes (RTT
  min/avg/max/stddev, packet loss, hostname, error)
- **mDNS/DNS-SD service monitor** — generic per-service health checks (AirPrint, AirPlay, SMB, etc.) with configurable
  filter, interval, and HA MQTT discovery. One binary_sensor per monitor; full diagnostic info in JSON attributes.
- **Hostname-stability detection** — tracks the mDNS-advertised hostname across polls per monitor; a numeric
  `sensor.networktools_mdns_<slug>_hostname_changes` (`state_class: total_increasing`) increments whenever avahi renames
  a service between checks, surfacing a rename-loop bug a single poll cannot see.
- **Periodic scanning** — configurable interval (default: 30s), results served via REST
- **Network tools** — nmap, ping, dig, traceroute, avahi-browse, avahi-resolve available in container
- **host_network mode** — full Layer-2 access for ARP packets and mDNS multicast

## Quick Start

1. Add this repository to Home Assistant
2. Install _Network Tools_
3. Configure `mdns_monitors` (e.g. for CUPS-AirPrint) and/or `arping_hosts` (for Layer-2 host detection)
4. Set `interface` to your LAN interface (e.g. `eth0`)
5. Start the add-on

## REST API

Scan results available at the ingress endpoint:

```http
GET /arping_scan.json
GET /mdns_scan.json
```

See [DOCS.md](DOCS.md) for full configuration reference and HA integration examples.

## Manual HA Integration Test

- [ ] ARPing binary sensor `binary_sensor.networktools_arping_<mac>` appears in HA after
      `mosquitto_sub -t 'homeassistant/binary_sensor/networktools_arping_+/config' -v`
- [ ] mDNS binary sensor `binary_sensor.networktools_mdns_<slug>` appears in HA after
      `mosquitto_sub -t 'homeassistant/binary_sensor/networktools_mdns_+/config' -v`
- [ ] mDNS binary sensor reads `ON` / `OFF`; full diagnostic (state text, service_name, address, last_check, error)
      lives in `attributes`
- [ ] When `avahi-browse -artp _ipp._tcp` returns no results, mDNS binary sensor flips to `OFF`
- [ ] When ARPing host is unreachable for `disconnect_threshold` consecutive cycles, the binary sensor flips to `OFF`
- [ ] mDNS hostname-stability sensor `sensor.networktools_mdns_<slug>_hostname_changes` appears in HA after
      `mosquitto_sub -t 'homeassistant/sensor/networktools_mdns_+_hostname_changes/config' -v`
- [ ] When the mDNS-advertised hostname for a monitor changes between two polls (avahi rename-loop), the
      `hostname_change_count` sensor value increments by 1 on the next successful (`online`) poll

<!-- Badge Links -->

[release-shield]: https://img.shields.io/badge/version-v0.5.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v0.5.0
[license-shield]: https://img.shields.io/badge/license-MIT-green.svg
[license]: https://github.com/akentner/homeassistant-addons/blob/main/LICENSE
