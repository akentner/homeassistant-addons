---
quick_id: "260628-eqo3yb"
slug: "network-tools-icon-flap-detection"
description: "network-tools: Icon + Flap-Detection"
date: "2026-06-28"
status: planned
---

# Quick Task: network-tools — Icon + Flap-Detection

## Goal

1. Fancy icon (128×128 PNG) für das network-tools Add-on erstellen
2. Flap-Detection in arping_scan.py einbauen — State erst auf OFF wenn X mal hintereinander FAIL
3. Neue Config-Option `disconnect_threshold` + Attributes im MQTT-Payload

## Must-Haves

- [ ] `network-tools/icon.png` existiert (128×128 PNG, mit PIL generiert)
- [ ] `config.yaml` enthält `disconnect_threshold: int` (default 3) in options + schema
- [ ] State-Datei `/data/state/arping_state.json` wird gelesen/geschrieben
- [ ] Attributes enthalten `consecutive_failures`, `disconnect_threshold`, `last_raw_reachable`
- [ ] MQTT publiziert erst OFF nach `disconnect_threshold` aufeinanderfolgenden FAILs
- [ ] `pre-commit` / `make lint` läuft durch

## Tasks

### T1: Icon erstellen

- Python-Skript (einmalig) mit PIL: dunkler Hintergrund, Radar-Sweep, Netzwerk-Knoten
- Ausgabe: `network-tools/icon.png` (128×128 RGBA→RGB PNG)

### T2: config.yaml erweitern

Zu `options` hinzufügen:

```yaml
disconnect_threshold: 3
```

Zu `schema` hinzufügen:

```yaml
disconnect_threshold: int
```

### T3: arping_scan.py — Flap-Detection

**State-Format** (`/data/state/arping_state.json`):

```json
{
  "192.168.178.1": {
    "consecutive_failures": 0,
    "effective_reachable": true,
    "last_raw_reachable": true
  }
}
```

**State-Key**: IP-Adresse (eindeutig pro Host-Config-Eintrag)

**Logik per Host**:

```
raw_reachable = arping_host(ip)
if raw_reachable:
    state[ip].consecutive_failures = 0
    state[ip].effective_reachable = True
else:
    state[ip].consecutive_failures += 1
    if state[ip].consecutive_failures >= threshold:
        state[ip].effective_reachable = False
    # else: effective_reachable bleibt unverändert (kein Flap)
state[ip].last_raw_reachable = raw_reachable
```

**Neue Felder in result**:

- `effective_reachable: bool`
- `consecutive_failures: int`

**MQTT**: publiziert `effective_reachable` statt `reachable` als State

**Attributes** (`_build_attributes`):

- `consecutive_failures: int`
- `disconnect_threshold: int`
- `last_raw_reachable: bool`

### T4: State laden/speichern

```python
STATE_FILE = Path("/data/state/arping_state.json")

def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}

def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.rename(STATE_FILE)
```

### T5: main() anpassen

```python
def main() -> None:
    options = load_options()
    setup_logging(options.get("log_level", "info"))
    state = load_state()
    data = scan(options, state)
    save_state(state)
    write_output(data)
    publish_mqtt(data, options)
```

## Files Changed

- `network-tools/icon.png` (neu)
- `network-tools/config.yaml`
- `network-tools/arping_scan.py`

## Out of Scope

- Dockerfile / Abhängigkeiten (PIL nicht im Container nötig — Icon wird lokal generiert)
- Logo-Animation, SVG-Format
- Änderungen an run.sh oder nginx.conf
