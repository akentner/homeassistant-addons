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

| Tool           | Paket        | Verwendung              |
| -------------- | ------------ | ----------------------- |
| `arping`       | arping       | ARP-Ping zu einem Host  |
| `nmap`         | nmap         | Netzwerk-Scan           |
| `ping`         | busybox      | ICMP-Ping (via busybox) |
| `dig`          | bind-tools   | DNS-Lookup              |
| `traceroute`   | traceroute   | Netzwerkpfad-Analyse    |
| `avahi-browse` | avahi-tools  | mDNS/DNS-SD-Suche       |
| `avahi-resolve`| avahi-tools  | mDNS-Hostname-Auflösung |

---

## mDNS-Monitor

Zusätzlich zum ARPing-Scan kann der Add-on beliebige mDNS-/DNS-SD-Dienste im LAN überwachen — z.B. einen
CUPS-AirPrint-Drucker (Erkennung des Klassikers „CUPS läuft, aber iOS-Geräte finden ihn nicht"), AirPlay-
Empfänger, Chromecast, SMB-Shares, HTTP-Dienste. Der Check funktioniert ausschließlich über echtes mDNS
(via `avahi-browse`); ein bloßer TCP-Portcheck auf 631 ist explizit nicht ausreichend.

### `mdns_monitors`

Liste von Monitoren. Jeder Monitor läuft unabhängig als eigener Hintergrund-Loop und publiziert
ein eigenes Set aus State-Topic, Details-Topic und Last-Check-Topic sowie HA-Discovery-Entities
(Binary Sensor + 2 Sensoren). Eine Liste erlaubt es, mehrere Drucker / Dienste parallel zu
überwachen, ohne mehrere Container zu betreiben.

| Feld            | Typ           | Pflicht | Beschreibung                                                            |
| --------------- | ------------- | ------- | ----------------------------------------------------------------------- |
| `name`          | string        | ja      | Eindeutiger Bezeichner — wird Teil der Entity-IDs und MQTT-Topics       |
| `enabled`       | bool          | ja      | Monitor ein-/ausschalten (deaktivierte Monitore werden übersprungen)    |
| `service_types` | list[string]  | ja      | Zu überwachende DNS-SD-Service-Typen (siehe Tabelle unten)              |
| `filter`        | list[string]  | nein    | Case-insensitive Substring-Filter gegen Name/Host/IP (any-match, leer = alle) |
| `interval`      | int           | ja      | Prüfintervall in Sekunden (10–3600, Default 60)                         |
| `timeout`       | int           | ja      | Timeout für `avahi-browse` / `avahi-resolve` in Sekunden (1–60, Default 10) |
| `topic_prefix`  | string        | nein    | MQTT-Topic-Präfix für State/Details/Last-Check (Default: `homeassistant/monitor/networktools_mdns_<slug>`) |
| `device_name`   | string        | nein    | Anzeigename im HA-Device-Block (Default: `name`)                        |

#### Unterstützte Service-Typen (Auswahl)

| Type                    | Zweck                                |
| ----------------------- | ------------------------------------ |
| `_ipp._tcp`             | IPP-Drucker (AirPrint, klassisch)    |
| `_ipps._tcp`            | IPP over TLS                         |
| `_printer._tcp`         | Legacy BSD-LPR                       |
| `_airplay._tcp`         | AirPlay                              |
| `_raop._tcp`            | AirPlay Remote Audio Output Protocol  |
| `_googlecast._tcp`      | Chromecast / Google Cast             |
| `_spotify-connect._tcp` | Spotify Connect                      |
| `_smb._tcp`             | SMB/CIFS-Fileshares                  |
| `_http._tcp`            | HTTP-Dienste                         |
| `_homekit._tcp`         | HomeKit Accessory Protocol           |
| `_hap._tcp`             | HomeKit Accessory Protocol (neu)     |

Eigene Typen (z.B. `_ipp._udp`, `_workstation._tcp`) können als Strings in `service_types` ergänzt
werden — die Validierung ist bewusst `list(str)`, kein Enum.

### Beispielkonfiguration

```yaml
mdns_monitors:
    - name: "brother_airprint"
      enabled: true
      service_types:
          - "_ipp._tcp"
          - "_ipps._tcp"
      filter:
          - "Brother"
          - "192.168.178.50"
      interval: 60
      timeout: 10
      topic_prefix: "homeassistant/monitor/brother_airprint"
      device_name: "Brother HL-L3270CDW"
    - name: "homepod"
      enabled: true
      service_types:
          - "_airplay._tcp"
      filter:
          - "Wohnzimmer"
      interval: 120
      timeout: 10
```

### MQTT-Topics (pro Monitor)

| Topic                                       | Payload                                | Retain | QoS |
| ------------------------------------------- | -------------------------------------- | ------ | --- |
| `<prefix>/state`                            | `online` / `offline` / `unknown`       | ja     | 1   |
| `<prefix>/details`                          | JSON (siehe unten)                     | ja     | 0   |
| `<prefix>/last_check`                       | ISO-Timestamp                          | ja     | 0   |
| `homeassistant/binary_sensor/.../config`     | HA-Discovery (retain)                  | ja     | 0   |
| `homeassistant/sensor/.../state/config`     | HA-Discovery (retain)                  | ja     | 0   |
| `homeassistant/sensor/.../last_check/config` | HA-Discovery (retain)                 | ja     | 0   |
| `network-tools/arping/availability`         | `online` / `offline` (geteilt mit ARPing) | ja  | 0   |

`<prefix>` ist standardmäßig `homeassistant/monitor/networktools_mdns_<slug>`. `network-tools/arping/availability`
ist ein geteiltes Last-Will-Topic — der gesamte Container hat **eine** LWT-Subscription, die sowohl
den ARPing- als auch den mDNS-Loop abdeckt.

### JSON-Details-Schema

```json
{
    "name": "brother_airprint",
    "state": "online",
    "timestamp": "2026-08-22T12:00:00+00:00",
    "service_type": "_ipp._tcp",
    "service_name": "Brother HL-L3270CDW series",
    "hostname": "brother.local",
    "address": "192.168.178.50",
    "port": 631,
    "txt_records": ["txtvers=1", "rp=printers/Brother"],
    "error": null,
    "duration_ms": 1234,
    "filter": ["Brother"],
    "service_types_scanned": ["_ipp._tcp", "_ipps._tcp"]
}
```

### Zustands-Klassifikation

| Zustand                   | Bedingung                                                            | MQTT-State | Binary-Sensor |
| ------------------------- | -------------------------------------------------------------------- | ---------- | ------------- |
| `online`                  | Dienst angekündigt **und** per `avahi-resolve` auflösbar              | `online`   | ON            |
| `announced_unresolved`    | Dienst angekündigt, Hostname nicht auflösbar                          | `offline`  | OFF           |
| `not_found`               | Kein passender Dienst in diesem Check                                 | `offline`  | OFF           |
| `error`                   | avahi-browse fehlgeschlagen oder Timeout                              | `unknown`  | OFF           |

### Firewall / Multicast-Anforderungen

Der Check funktioniert nur, wenn Multicast-Pakete zwischen Container und LAN fließen können. Da der
Add-on `host_network: true` nutzt, ist das in der Regel gegeben. Sicherstellen:

- UDP 5353 (mDNS) ist nicht durch eine Firewall zwischen Container-Host und LAN blockiert.
- Die Multicast-Adresse `224.0.0.251` ist erreichbar (IPv4-mDNS) bzw. `ff02::fb` (IPv6).
- WLAN-APs / Switches mit „AP Isolation" oder „Client Isolation" blockieren Multicast zwischen
  Clients. In diesem Fall funktioniert AirPrint auch für iOS-Geräte nicht — der Check wird
  korrekt `not_found` melden, was genau das gewünschte Frühsignal ist.
- Der Host hat mindestens ein Interface im Ziel-LAN (nicht `lo`, nicht das Container-Bridge-Device).

Es ist **kein** Portmapping für UDP 5353 erforderlich — `host_network: true` greift die Pakete
bereits am LAN-Interface ab.

### Manuelle Tests

```bash
# 1. Direkter mDNS-Browse — was sieht der Container?
docker exec -it <addon_container> avahi-browse -artp _ipp._tcp

# 2. Letztes Scan-Ergebnis lesen
curl http://localhost:18080/mdns_scan.json

# 3. MQTT-Topics manuell subscriben
mosquitto_sub -h core-mosquitto -t 'homeassistant/monitor/#' -v
mosquitto_sub -h core-mosquitto -t 'homeassistant/binary_sensor/networktools_mdns_+/config' -v
```

### Typische Fehlerbilder

| Symptom                                            | Ursache / Lösung                                                  |
| -------------------------------------------------- | ----------------------------------------------------------------- |
| `state: not_found` obwohl iOS druckt               | Multicast vom Container geblockt — Firewall / AP Isolation prüfen |
| `state: announced_unresolved` dauerhaft            | `avahi-resolve` schlägt fehl — DNS-Auflösung des `.local`-Hosts prüfen |
| `state: error` mit `error: avahi-browse failed`    | Binary fehlt im Container — `avahi-tools` muss installiert sein    |
| HA zeigt Entities als `unavailable`                | `mqtt_enabled` im Add-on fehlt oder Broker nicht erreichbar       |
| Discovery-Configs erscheinen nicht in HA           | `mqtt_discovery_prefix` falsch — Default ist `homeassistant`       |
| Filter greift nicht                                | Filter ist Substring-Match — exakten Hostnamen oder IP prüfen    |

