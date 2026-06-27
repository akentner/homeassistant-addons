# Network Tools Add-on

[![Version](https://img.shields.io/badge/version-v0.1.0-blue)](https://github.com/akentner/homeassistant-addons)
[![Architecture](https://img.shields.io/badge/arch-amd64-lightgrey)](https://github.com/akentner/homeassistant-addons)

Network diagnostics and ARP-based host detection for Home Assistant.

## Features

- **arping-based host detection** — ARP-Ping per Host, MAC verification, reachability tracking
- **Periodic scanning** — configurable interval (default: 30s), results served via REST
- **Network tools** — nmap, ping, dig, traceroute available in container
- **host_network mode** — full Layer-2 access for ARP packets

## Quick Start

1. Add this repository to Home Assistant
2. Install _Network Tools_
3. Configure `arping_hosts` with your hosts' IPs and MACs
4. Set `interface` to your LAN interface (e.g. `eth0`)
5. Start the add-on

## REST API

Scan results available at the ingress endpoint:

```
GET /arping_scan.json
```

See [DOCS.md](DOCS.md) for full configuration reference and HA integration examples.
