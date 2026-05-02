# Fehlerbericht: HA Coding Assistant Container

Erstellt: 2026-05-02 (alpha10) Aktualisiert: 2026-05-02 (alpha11, Cross-Referenz mit OpenCode-Analyse) System: Home
Assistant Coding Assistant Add-on Zweck: Übergabe an konfigurierende KI zur Behebung der Defizite

---

## Überblick

Der Container läuft und ist grundsätzlich funktionsfähig. Es fehlen jedoch mehrere Konfigurationskomponenten, die in
`CLAUDE.md` / `AGENTS.md` als verfügbar dokumentiert sind, aber tatsächlich nicht funktionieren.

> **Hinweis für die konfigurierende KI:** `/homeassistant/bin` gilt als **deprecated** und soll nicht im Container-PATH
> stehen. Alle CLI-Tools (`ha-api`, `ha-ws`, `lovelace-sync`, `ha-check-logs`, `ha-check-repairs`) müssen nativ im
> Container unter `/usr/local/bin` installiert sein. Keine neuen Tools in `/homeassistant/bin` ablegen — stattdessen
> immer nativ installieren.

Beide KI-Systeme (Claude Code + OpenCode) haben den Container unabhängig analysiert:

- **Claude Code** auf alpha10 und alpha11
- **OpenCode** auf alpha11

---

## Überschneidungen (beide KIs bestätigt)

### Ü1 — `ha` CLI nicht nutzbar: `hassio_role` zu niedrig (KRITISCH)

Das HA Supervisor CLI (`ha`) schlägt auf allen Befehlen fehl.

- **alpha10 (Claude):** `SUPERVISOR_TOKEN` nicht injiziert → `unauthorized`
- **alpha11 (beide):** Token jetzt gesetzt (112 Zeichen), aber
  `Error: forbidden: insufficient permissions or invalid token`

`ha info` und `ha banner` funktionieren (read-only, keine Auth nötig). Alle anderen Befehle — insbesondere
`ha core check` und `ha core info` — schlagen fehl.

**Root Cause:** Das Addon-Manifest (`config.yaml`) setzt `hassio_role: default`, was zu eingeschränkten
Supervisor-Berechtigungen führt.

**Erwartetes Verhalten laut CLAUDE.md:**

```bash
ha core check --no-progress --raw-json   # Config-Validierung
ha core check                            # vor jedem Commit
ha-api call homeassistant reload_all     # Reload
```

**Fix:** Im Addon-Manifest setzen:

```yaml
hassio_role: manager
```

---

### Ü2 — MCP-Server nicht vollständig konfiguriert (KRITISCH)

Der ha-mcp Add-on läuft und ist erreichbar (`http://81f33d0f-ha-mcp:9583/...`), aber der Eintrag fehlt in der
OpenCode-Konfiguration und ist für Claude Code nur im Projektkontext vorhanden, nicht global.

**alpha11-Zustand:**

- Claude Code Projekt `/homeassistant`: `ha-mcp` ✅ konfiguriert (HTTP-Remote)
- Claude Code global: leer `{}`
- OpenCode (`opencode.jsonc`): `ha-mcp` auf `enabled: false`

**Fix Claude Code** — in `.claudecode/.claude.json` global:

```json
"mcpServers": {
  "ha-mcp": {
    "type": "http",
    "url": "http://81f33d0f-ha-mcp:9583/private_..."
  }
}
```

**Fix OpenCode** — in `/data/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "ha-mcp": {
      "type": "sse",
      "url": "http://81f33d0f-ha-mcp:9583/private_..."
    }
  }
}
```

Die URL sollte dynamisch aus `$HA_MCP_URL` (in `.env` gesetzt) bezogen werden, damit sie bei Addon-Neustarts nicht
veraltet.

---

### Ü3 — `lovelace-sync` und `ha-ws` crashen: `websockets` fehlt (MITTEL)

Beide Python-Tools brechen mit identischem Fehler ab:

```
ModuleNotFoundError: No module named 'websockets'
```

Betroffen:

- `/homeassistant/bin/lovelace-sync`
- `/homeassistant/bin/ha-ws`

`ha-ws` ist auch unter `/usr/local/bin/ha-ws` verlinkt und in der CLAUDE.md als vollwertiges Tool dokumentiert. Mit
`source .env` lässt es sich starten, bricht dann aber sofort ab.

**Fix:** Systemweite Installation:

```bash
pip3 install websockets
# oder: uv pip install websockets --system
```

---

### Ü4 — `HA_TOKEN` nicht über Addon-Optionen konfiguriert (MINOR)

`/data/options.json` hat `"ha_token": ""` → `/etc/profile.d/00-coding-assistants.sh` setzt `export HA_TOKEN=''`.

**Aktueller Workaround:** `/homeassistant/.env` enthält ein manuell gepflegtes Long-Lived Access Token. `ha-api` lädt
diese Datei selbst und funktioniert dadurch. `ha-ws` und `lovelace-sync` benötigen ebenfalls ein gesetztes `$HA_TOKEN`.

**Risiko:** Die `.env`-Datei ist gitignored und nicht persistent wenn der Container neu gebaut wird.

**Fix:** Token in der Addon-UI eintragen, sodass `options.json` es enthält und `00-coding-assistants.sh` es korrekt
exportiert.

---

## Claude-Code-spezifische Findings

### C1 — `fff-mcp` installiert, aber nirgendwo registriert (MITTEL)

`/usr/local/bin/fff-mcp` ✅ vorhanden und funktionsfähig. `CLAUDE.md`/`AGENTS.md` dokumentiert explizit:

> _"`fff-mcp` — fast file search MCP server (register in Claude Code / OpenCode config)"_

Aber weder in Claude Code noch in OpenCode ist ein Eintrag vorhanden.

**Fix Claude Code** — Projekteintrag in `.claudecode/.claude.json`:

```json
"fff": {
  "command": "fff-mcp",
  "args": ["/homeassistant"]
}
```

**Fix OpenCode** — in `opencode.jsonc`:

```json
"fff": {
  "type": "stdio",
  "command": "fff-mcp",
  "args": ["/homeassistant"]
}
```

---

### C2 — `/homeassistant/bin` deprecated: Tools nicht nativ installiert (MITTEL)

`/homeassistant/bin` ist ein deprecated Verzeichnis und soll **nicht** im PATH stehen. Die Tools sollen nativ im
Container unter `/usr/local/bin` liegen.

**Aktueller Zustand in alpha11:**

- `/homeassistant/bin` steht an Position 1 im PATH → wird noch benötigt, weil Tools dort fehlen
- `ha-api` ✅ nativ in `/usr/local/bin`
- `ha-ws` ✅ nativ in `/usr/local/bin`
- `lovelace-sync` ❌ nur in `/homeassistant/bin`, fehlt in `/usr/local/bin`
- `ha-check-logs` ❌ nur in `/homeassistant/scripts/bin`, fehlt in `/usr/local/bin`
- `ha-check-repairs` ❌ nur in `/homeassistant/scripts/bin`, fehlt in `/usr/local/bin`

**Fix:**

1. `lovelace-sync`, `ha-check-logs`, `ha-check-repairs` nativ in `/usr/local/bin` installieren
2. `/homeassistant/bin` und `/homeassistant/scripts/bin` aus dem PATH entfernen

---

### C3 — `options.json` `mcp_servers`-Feld ungenutzt (MINOR)

`/data/options.json` enthält `"mcp_servers": []` — das Addon hat also einen eingebauten Mechanismus zur
MCP-Konfiguration. Dieser ist leer.

**Klärungsbedarf:** Soll `mcp_servers` in `options.json` die MCP-Konfiguration für Claude Code und OpenCode automatisch
generieren? Falls das die vorgesehene Schnittstelle ist, wäre das der korrekte Weg statt manueller Einträge in
`.claude.json` und `opencode.jsonc`.

---

## Gesamtübersicht (alpha11)

| #   | Problem                                                | Quelle | Status                   | Schwere  |
| --- | ------------------------------------------------------ | ------ | ------------------------ | -------- |
| Ü1  | `ha` CLI: `hassio_role` zu niedrig                     | beide  | ⚠️ Token da, `forbidden` | KRITISCH |
| Ü2  | MCP-Server nicht vollständig konfiguriert              | beide  | ⚠️ teilweise             | KRITISCH |
| Ü3  | `lovelace-sync` + `ha-ws` crashen (`websockets` fehlt) | beide  | ❌ offen                 | MITTEL   |
| Ü4  | `HA_TOKEN` nicht in `options.json`                     | beide  | ⚠️ Workaround `.env`     | MINOR    |
| C1  | `fff-mcp` nicht als MCP registriert                    | Claude | ❌ offen                 | MITTEL   |
| C2  | `lovelace-sync`/`ha-check-*` nicht nativ installiert   | Claude | ❌ offen                 | MITTEL   |
| C3  | `options.json` `mcp_servers` ungenutzt                 | Claude | ❓ unklar                | MINOR    |

**Behoben seit alpha10:**

- ~~`SUPERVISOR_TOKEN` nicht injiziert~~ → Token wird gesetzt, `hassio_role` bleibt offen
- ~~Defekte Symlinks / PATH fehlte für Tools~~ → `/homeassistant/bin` und `scripts/bin` im PATH als Workaround, soll
  durch native Installation ersetzt werden
- ~~Defekter `hass-mcp`-Eintrag in globaler MCP-Config~~ → entfernt ✅

---

## Was funktioniert

| Tool / Feature                              | Status                                             |
| ------------------------------------------- | -------------------------------------------------- |
| `ha-api` (REST-Calls)                       | ✅ funktioniert (lädt `.env` selbst)               |
| `ha-ws` (WebSocket)                         | ❌ crasht (`websockets` fehlt)                     |
| `lovelace-sync`                             | ❌ crasht (`websockets` fehlt)                     |
| `ha-check-logs`, `ha-check-repairs`         | ⚠️ nur via deprecated `/homeassistant/scripts/bin` |
| `ha-mcp` MCP-Server                         | ✅ erreichbar, antwortet                           |
| `fff-mcp` Binary                            | ✅ installiert, nicht registriert                  |
| `sqlite3` auf HA-Datenbank                  | ✅                                                 |
| `git`, `gh`, `lazygit`, `tig`               | ✅                                                 |
| `rg`, `fd`, `fzf`, `bat`, `eza`, `jq`, `yq` | ✅                                                 |
| `python3`, `uv`, `node`, `bun`              | ✅                                                 |
| `tmux`, `zoxide`, `yazi`                    | ✅                                                 |

---

## Kontext

- HA Version: 2026.4.4
- Claude Code Version: 2.1.126
- OpenCode Version: 1.14.31
- Arbeitsverzeichnis: `/homeassistant` (HA config, live)
- Persistenter Storage: `/data`
- HA URL intern: `http://homeassistant:8123`
- HA URL extern: `https://ha-nextgen.akentner.de`
