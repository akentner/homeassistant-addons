---
quick_id: "260628-eqo3yb"
slug: "network-tools-icon-flap-detection"
status: complete
date: "2026-06-28"
---

# Summary: network-tools — Icon + Flap-Detection

## Was erledigt wurde

### T1: Icon (network-tools/icon.png)

128×128 PNG mit PIL generiert. Radar-Theme: dunkler Hintergrund (#0d1117), Radar-Sweep in Grün, konzentrische Ringe in
Cyan/Teal, Host-Knoten mit Verbindungslinien zum Zentrum, Glow-Effekt.

### T2: config.yaml

`disconnect_threshold: 3` in `options` und `schema` ergänzt.

### T3+T4: arping_scan.py — Flap-Detection + State-Persistenz

- `STATE_FILE = Path("/data/state/arping_state.json")` — neuer Speicherort
- `load_state()` / `save_state()` — atomisches Lesen/Schreiben mit `.tmp`-Pattern
- `scan(options, state)` — nimmt jetzt State als Parameter
- Pro Host: `consecutive_failures` inkrementiert bei FAIL, reset bei OK
- `effective_reachable` bleibt True solange `consecutive_failures < threshold`
- MQTT publiziert `effective_reachable` (nicht raw `reachable`)
- Attributes: `consecutive_failures`, `disconnect_threshold`, `last_raw_reachable`
- `hosts_reachable` im Scan-Summary zählt jetzt `effective_reachable`

## Dateien geändert

- `network-tools/icon.png` (neu)
- `network-tools/config.yaml` (+`disconnect_threshold`)
- `network-tools/arping_scan.py` (+flap-detection, +state-persistenz)

## Lint

`make lint` — alle Checks grün (19/19 Passed)
