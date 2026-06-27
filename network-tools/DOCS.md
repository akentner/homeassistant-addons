# Network Tools — Konfiguration

## Optionen

### `arping_hosts`

Liste der Hosts, die per ARP-Ping überwacht werden.

| Feld    | Typ    | Pflicht | Beschreibung                                     |
| ------- | ------ | ------- | ------------------------------------------------ |
| `label` | string | ja      | Anzeigename                                      |
| `ip`    | string | ja      | IP-Adresse des Hosts                             |
| `mac`   | string | nein    | Erwartete MAC — wird mit ARP-Antwort abgeglichen |

### `interface`

Netzwerk-Interface für ARP-Pakete. Standard: `eth0`.

Mit `host_network: true` sieht der Container alle Host-Interfaces. Mögliche Werte: `eth0`, `enp3s0`, etc.

### `interval`

Scan-Intervall in Sekunden. Standard: `30`. Minimum empfohlen: `10`.

### `port`

TCP-Port auf dem nginx die REST API bereitstellt. Standard: `8080`. Ändern wenn ein anderer Add-on oder Dienst Port 8080
belegt (z.B. auf `8082`). Der `ingress_port` in config.yaml muss mit diesem Wert übereinstimmen — bei Änderung beide
anpassen.

### `log_level`

Log-Verbosity: `debug` | `info` | `warning` | `error`. Standard: `info`.

---

## REST API

Der Add-on stellt die Scan-Ergebnisse auf Port 8080 bereit (HA Ingress).

### `GET /arping_scan.json`

Letztes Scan-Ergebnis als JSON:

```json
{
  "scan_timestamp": "2026-06-27T20:00:00+00:00",
  "scan_ok": true,
  "interface": "eth0",
  "hosts_total": 2,
  "hosts_reachable": 1,
  "results": [
    {
      "label": "tux1-lan",
      "ip": "192.168.178.141",
      "expected_mac": "74:78:27:98:90:EE",
      "reachable": true,
      "mac": "74:78:27:98:90:EE",
      "mac_match": true,
      "rtt_ms": 0.8
    }
  ]
}
```

---

## HA Integration (command_line sensor)

```yaml
command_line:
  - sensor:
      unique_id: sensor.network_tools_arping_scan
      name: "Network Tools Arping Scan"
      command: "curl -sf http://localhost:8080/arping_scan.json"
      scan_interval: 30
      value_template: "{{ value_json.scan_timestamp }}"
      json_attributes:
        - scan_ok
        - hosts_total
        - hosts_reachable
        - results
```

---

## Tools im Container

Folgende Tools sind im Container verfügbar (via `docker exec` oder HA Terminal):

| Tool         | Paket      | Verwendung              |
| ------------ | ---------- | ----------------------- |
| `arping`     | arping     | ARP-Ping zu einem Host  |
| `nmap`       | nmap       | Netzwerk-Scan           |
| `ping`       | busybox    | ICMP-Ping (via busybox) |
| `dig`        | bind-tools | DNS-Lookup              |
| `traceroute` | traceroute | Netzwerkpfad-Analyse    |
