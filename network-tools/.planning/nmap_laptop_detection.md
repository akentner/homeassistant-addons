# nmap-basierte Laptop-Erkennung — Projektdokumentation

**Zweck:** Zuverlässige Erkennung der Notebooks `lap-aleken-tux1` (Linux) und `aleken-w10-lap2` (Windows) per nmap
ARP-Scan, als Alternative zur unzuverlässigen Fritzbox-TR-064-Erkennung.

**Stand:** 2026-06-27 — Konzept validiert, Script lauffähig, HA-Integration ausstehend.

---

## 1. Problem

`device_tracker.lap_aleken_tux1_fritz_enp57s0u1u4` (Fritzbox-TR-064) liefert falsche/verzögerte Werte → der Sensor
`sensor.officealex22_dockingstation_active_device` meldet manchmal das falsche Notebook.

Bisheriger Workaround: Ping-basierte `binary_sensor` — funktioniert, ist aber fragil (Tailscale blockt ICMP, DHCP-IPs
können sich ändern).

## 2. Lösung: nmap ARP-Scan mit MAC-Match

Statt IP-basierter Erkennung → **Layer-2-Erkennung per MAC** über `nmap -sn -PR`. Gründe:

- **MAC ist stabil**, IP nicht (DHCP kann zuweisen wie es will)
- **ARP funktioniert auch wenn ICMP geblockt ist** (Tailscape, Firewall)
- **Dell-Dock-Logik** braucht MAC-Match (Dock hat pro Host andere MAC)
- **Layer-2 = schnellste Erkennung**, kein Router-Roundtrip wie bei TR-064

## 3. Erkannte Geräte (MAC-Mapping)

| MAC                 | Gerät                | Schnittstelle                                     | Sichtbar wenn                    |
| ------------------- | -------------------- | ------------------------------------------------- | -------------------------------- |
| `74:78:27:98:90:EE` | lap-aleken-tux1 LAN  | `enp57s0u1u4` (Dell-Dock USB-C / TB4 Passthrough) | im Dock oder Kabel               |
| `68:54:5A:5D:28:CA` | lap-aleken-tux1 WLAN | `wlan0`                                           | WLAN an (auch parallel zum Dock) |
| `AC:1A:3D:AD:8D:07` | aleken-w10-lap2 LAN  | USB-Ethernet via Dell-Dock                        | im Dock                          |
| `C4:3D:1A:89:3E:83` | aleken-w10-lap2 WLAN | (5 GHz über fritz-rep-terrace22)                  | per WLAN                         |

**Wichtige Erkenntnisse aus dem Test:**

1. **Dell-Dock hat pro Host eine andere MAC** — Dell-Docks machen MAC-Passthrough für Tux-Laptop (TB4) aber Dock-eigene
   MAC für Win-Laptop (USB-Ethernet). Das heißt: man kann nicht "Dock-MAC" pauschal tracken, sondern muss die
   Host-spezifischen MACs kennen.

2. **WLAN bleibt parallel aktiv** beim Andocken — der Laptop hat dann sowohl LAN- als auch WLAN-MAC im Netz sichtbar.

3. **`CC:48:3A:A8:A8:DE` (aus secrets.yaml) ist veraltet** — vermutlich alte MAC von einem anderen Notebook. Wird
   ignoriert.

4. **STP-Topology-Changes beim Andocken** verursachen manchmal 30s ARP-Cache-Verlust beim Switch — Scan muss retries
   haben.

5. **Tux-Laptop im Dock zeigt seine eigene MAC** (`74:78:27:98:90:EE`), Dell-Dock ist transparent. Diese MAC ist im
   Fritzbox-Entity `device_tracker.lap_aleken_tux1_fritz_enp57s0u1u4` hinterlegt — dort steht sie richtig, der Tracker
   selbst ist nur unzuverlässig.

## 4. Erkennungs-Logik (für HA-Templates)

```
binary_sensor.officealex22_lap_aleken_tux1_lan:
    an wenn 74:78:27:98:90:EE im Scan

binary_sensor.officealex22_lap_aleken_tux1_wifi:
    an wenn 68:54:5A:5D:28:CA im Scan UND NICHT officealex22_lap_aleken_tux1_lan
    # LAN gewinnt vor WLAN (deine Regel)

binary_sensor.officealex22_aleken_w10_lap2_lan:
    an wenn AC:1A:3D:AD:8D:07 im Scan

binary_sensor.officealex22_aleken_w10_lap2_wifi:
    an wenn C4:3D:1A:89:3E:83 im Scan UND NICHT officealex22_aleken_w10_lap2_lan

sensor.officealex22_dockingstation_active_device:
    wenn tux_lan ODER tux_wifi:
        → "lap-aleken-tux1"
    sonst wenn win_lan ODER win_wifi:
        → "aleken-w10-lap2"
    sonst:
        → unavailable
```

## 5. Architektur

```
┌────────────────────────────────────────────────────────┐
│ Sidecar-Container (oder Host mit host_network: true)  │
│   - Python-Script nmap_laptop_scan.py                  │
│   - liest nmap_laptop_hosts.json                       │
│   - nmap -sn -PR alle 60s                              │
│   - schreibt /config/www/nmap_laptop_scan.json         │
│     (oder NFS-Mount falls extern)                      │
└────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────┐
│ Home Assistant                                         │
│   command_line sensor (30s Intervall)                  │
│     liest /config/www/nmap_laptop_scan.json           │
│                         │                              │
│                         ▼                              │
│   template binary_sensor (4x):                         │
│     - officealex22_lap_aleken_tux1_lan                 │
│     - officealex22_lap_aleken_tux1_wifi                │
│     - officealex22_aleken_w10_lap2_lan                 │
│     - officealex22_aleken_w10_lap2_wifi                │
│                         │                              │
│                         ▼                              │
│   template sensor.officealex22_dockingstation_active_  │
│   device                                               │
└────────────────────────────────────────────────────────┘
```

## 6. Container-Problem

**HA-Core und SSH-Add-on laufen im Container** (IP `172.30.33.12/23`, veth-Pair `eth0@if29`). ARP-Anfragen Richtung
`192.168.178.0/24` gehen nicht raus.

**Lösung:** Eigenes Sidecar-Container oder HA-Host direkt mit `network_mode: host` (oder `host_network: true` bei
HA-Add-ons).

### Optionen für den Sidecar

1. **HA SSH-Add-on auf host_network umstellen** — einfachster Weg, du bist schon eingeloggt
2. **Eigener Docker-Container** mit `network_mode: host` und Python + nmap
3. **Proxmox LXC** mit echtem LAN-Zugriff
4. **NAS / andere Linux-Maschine** mit Zugriff auf das Subnetz

### Minimaler Sidecar (Beispiel)

```dockerfile
FROM alpine:latest
RUN apk add --no-cache nmap python3
COPY nmap_laptop_scan.py /scan.py
COPY nmap_laptop_hosts.json /hosts.json
ENTRYPOINT ["python3", "/scan.py", "--loop", "60", "--output", "/shared/nmap_scan.json"]
```

```yaml
# docker-compose.yml
services:
  nmap-scanner:
    build: .
    network_mode: host
    volumes:
      - /path/to/ha/config/www:/shared:rw # HA kann die JSON lesen
    restart: unless-stopped
```

## 7. Script: `nmap_laptop_scan.py`

Lokation: `/homeassistant/scripts/nmap_laptop_scan.py` (siehe auch im Repo).

**Verwendung:**

```bash
# Einmaliger Test
python3 nmap_laptop_scan.py --once --output /tmp/scan.json

# Daemon (alle 60s)
python3 nmap_laptop_scan.py --loop 60 --output /config/www/nmap_laptop_scan.json

# Hilfe
python3 nmap_laptop_scan.py --help
```

**Kommandozeilen-Optionen:**

| Flag            | Default                             | Bedeutung                                |
| --------------- | ----------------------------------- | ---------------------------------------- |
| `--once`        | -                                   | Einmaliger Scan, dann exit               |
| `--loop N`      | 60                                  | Alle N Sekunden scannen (Endlosschleife) |
| `--subnet CIDR` | `192.168.178.0/24`                  | Subnetz                                  |
| `--output PATH` | `/config/www/nmap_laptop_scan.json` | Output-Datei                             |
| `--hosts PATH`  | neben Script                        | JSON-Datei mit MAC→Label Map             |
| `-v`            | -                                   | Debug-Logging                            |

**Output-Format (JSON):**

```json
{
  "scan_timestamp": "2026-06-27T19:00:00+00:00",
  "scan_ok": true,
  "error": null,
  "subnet": "192.168.178.0/24",
  "total_devices": 63,
  "found_macs": {
    "68:54:5A:5D:28:CA": "192.168.178.108",
    "74:78:27:98:90:EE": "192.168.178.141"
  },
  "matched": {
    "68:54:5A:5D:28:CA": {
      "ip": "192.168.178.108",
      "label": "lap-aleken-tux1 WLAN (wlan0)"
    },
    "74:78:27:98:90:EE": {
      "ip": "192.168.178.141",
      "label": "lap-aleken-tux1 LAN (enp57s0u1u4)"
    }
  },
  "hosts_known": 4,
  "hosts_matched": 2,
  "devices": [
    {"ip": "...", "mac": "...", "vendor": "...", "hostname": "..."},
    ...
  ]
}
```

## 8. Hosts-Datei: `nmap_laptop_hosts.json`

```json
{
  "74:78:27:98:90:EE": "lap-aleken-tux1 LAN (enp57s0u1u4)",
  "68:54:5A:5D:28:CA": "lap-aleken-tux1 WLAN (wlan0)",
  "AC:1A:3D:AD:8D:07": "aleken-w10-lap2 LAN (Dell-Dock)",
  "C4:3D:1A:89:3E:83": "aleken-w10-lap2 WLAN"
}
```

MACs werden case-insensitiv behandelt (immer upper-case intern).

## 9. HA-Integration (ausstehend)

Nach erfolgreichem Sidecar-Test müssen folgende HA-Pakete erstellt/aktualisiert werden:

### Neu: `packages/system/network/nmap_laptop_scan.yaml`

```yaml
# command_line sensor liest die JSON
command_line:
  - sensor:
      unique_id: sensor.officealex22_nmap_laptop_scan
      name: "Schreibtisch nmap Laptop Scan"
      command: "cat /config/www/nmap_laptop_scan.json"
      scan_interval: 30
      value_template: "{{ value_json.scan_timestamp }}"
      json_attributes:
        - scan_ok
        - error
        - total_devices
        - found_macs
        - matched
        - hosts_known
        - hosts_matched
        - devices
      device_class: timestamp
```

### Update: `packages/areas/officealex22/officealex22_notebooks.yaml`

Vier `binary_sensor` für die einzelnen MAC-Matches, ein `sensor` für `active_device`.

### Update: `packages/areas/officealex22/officealex22_area.yaml`

Evidence-Liste um die neuen Sensoren erweitern.

## 10. Offene Punkte / TODOs

- [ ] Sidecar-Container bauen (lokal auf Notebook, Docker)
- [ ] NFS/Syncthing zwischen Sidecar und HA-Config einrichten
- [ ] sudoers im Sidecar-Container konfigurieren (nmap braucht root/sudo für ARP)
- [ ] HA-YAML-Pakete bauen (siehe Abschnitt 9)
- [ ] Alte `binary_sensor.officealex22_ping_aleken_w10_lap2_lan` Definition fehlt im Repo — war Referenz ohne Definition
- [ ] `device_tracker.lap_aleken_tux1_fritz_enp57s0u1u4` als Fallback behalten
- [ ] Test: Tux im Dock mit Win im WLAN (Gegenprobe zur Logik)
- [ ] Gatus als Co-Monitor? (Latenz/Verfügbarkeit der Notebooks)

## 11. Lokales Setup für dich (Notebook)

```bash
# 1. Repo clonen oder kopieren
mkdir -p ~/nmap-scanner && cd ~/nmap-scanner

# 2. Script + Hosts-File rüberkopieren
cp /homeassistant/scripts/nmap_laptop_scan.py .
cp /homeassistant/scripts/nmap_laptop_hosts.json .

# 3. Test (einmalig, mit Output nach /tmp)
python3 nmap_laptop_scan.py --once --output /tmp/scan.json

# 4. Erwartete MACs prüfen
cat /tmp/scan.json | jq '.matched'

# 5. Sidecar-Container bauen (siehe oben)
docker build -t nmap-scanner .
docker run -d --network=host --restart=unless-stopped \
  -v ~/nmap-scanner:/app:ro \
  -v /path/to/ha/config/www:/shared:rw \
  nmap-scanner
```

## 12. Quellen / Referenzen

- Bestehende Doku: `/homeassistant/docs/network_scan.md`
- Bestehende Scripts: `/homeassistant/scripts/network_scan.py`, `/homeassistant/scripts/scan_apple_devices.sh`
- sudo-Setup: `/homeassistant/docs/sudo_setup.md`
- HA-Integration `nmap_tracker`: https://www.home-assistant.io/integrations/nmap_tracker
- Aktuelle betroffene Dateien:
  - `/homeassistant/packages/areas/officealex22/officealex22_notebooks.yaml`
  - `/homeassistant/packages/areas/officealex22/officealex22_area.yaml`
  - `/homeassistant/packages/areas/officealex22/officealex22_lights.yaml`
  - `/homeassistant/secrets.yaml` (alte Win-MAC `hosts_aleken_w10_lap_mac` ist veraltet)
