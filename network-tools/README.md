# Home Assistant Add-on: Network Tools

[![Release][release-shield]][release] [![License][license-shield]][license]

Network diagnostics and ARP-based host detection for Home Assistant.

## Features

- **arping-based host detection** — ARP-Ping per Host, MAC verification, reachability tracking
- **mDNS/DNS-SD service monitor** — generic per-service health checks (AirPrint, AirPlay, SMB, etc.)
  with configurable filter, interval, and HA MQTT discovery
- **Periodic scanning** — configurable interval (default: 30s), results served via REST
- **Network tools** — nmap, ping, dig, traceroute, avahi-browse, avahi-resolve available in container
- **host_network mode** — full Layer-2 access for ARP packets and mDNS multicast

## Quick Start

1. Add this repository to Home Assistant
2. Install _Network Tools_
3. Configure `arping_hosts` with your hosts' IPs and MACs
4. Set `interface` to your LAN interface (e.g. `eth0`)
5. Start the add-on

## REST API

Scan results available at the ingress endpoint:

```http
GET /arping_scan.json
```

See [DOCS.md](DOCS.md) for full configuration reference and HA integration examples.

## Manual HA Integration Test

- [ ] ARPing sensors appear in HA after
      `mosquitto_sub -t 'homeassistant/binary_sensor/networktools_arping_+/config' -v`
- [ ] mDNS binary sensor `binary_sensor.networktools_mdns_<slug>_available` appears in HA
- [ ] mDNS state sensor `sensor.networktools_mdns_<slug>_state` reflects `online|offline|unknown`
- [ ] mDNS last-check sensor `sensor.networktools_mdns_<slug>_last_check` updates within one interval
- [ ] When `avahi-browse -artp _ipp._tcp` returns no results, mDNS state flips to `offline`

<!-- Badge Links -->

[release-shield]: https://img.shields.io/badge/version-v0.3.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v0.3.0
[license-shield]: https://img.shields.io/badge/license-MIT-green.svg
[license]: https://github.com/akentner/homeassistant-addons/blob/main/LICENSE
