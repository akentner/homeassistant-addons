# Fehlerbericht: HA Coding Assistant Container

Erstellt: 2026-05-02 (alpha10) Aktualisiert: 2026-05-02 (alpha11, Cross-Referenz mit Claude Code Analyse) System: Home
Assistant Coding Assistant Add-on Zweck: Übergabe an konfigurierende KI zur Behebung der Defizite

---

## Überblick

Der Container läuft und ist grundsätzlich funktionsfähig. Es fehlen jedoch mehrere kritische Konfigurationskomponenten,
die in `AGENTS.md` als verfügbar dokumentiert sind, aber tatsächlich nicht funktionieren.

Beide KI-Systeme (OpenCode + Claude Code) haben den Container unabhängig analysiert. Die Ergebnisse wurden abgeglichen —
Überschneidungen sind in einer eigenen Sektion zusammengefasst.

---

## Überschneidungen (beide KIs bestätigt)

### Ü1: `ha` CLI nicht nutzbar — SUPERVISOR_TOKEN / Berechtigungen

Beide KIs haben dieses Problem unabhängig gefunden, auf unterschiedlichen Container-Versionen:

- **Claude (alpha10):** `SUPERVISOR_TOKEN` nicht injiziert → `unauthorized`
- **OpenCode (alpha11):** Token jetzt gesetzt, aber `hassio_role` zu niedrig → `forbidden`

**Root Cause:** Fehlendes bzw. zu niedrig konfiguriertes `hassio_role` im Add-on `config.yaml`. **Fix:**
`hassio_role: manager` setzen (statt `default`).

---

### Ü2: MCP-Server nicht konfiguriert

Beide KIs stellen fest, dass kein MCP-Server in den KI-Tools eingetragen ist, obwohl der ha-mcp Add-on läuft und die URL
in `/homeassistant/.env` vorhanden ist.

- **Claude:** Findet zusätzlich einen defekten `hass-mcp`-Eintrag (Command-Binary fehlt) in alpha10 — in alpha11
  bereinigt.
- **OpenCode:** `mcpServers: {}` in beiden Tools (alpha11).

**Fix:** HA MCP Server in beiden Tools eintragen (URL aus `$HA_MCP_URL`):

Claude Code (`/homeassistant/.claudecode/settings.json`):

```json
{
  "mcpServers": {
    "homeassistant": {
      "type": "sse",
      "url": "<HA_MCP_URL aus .env>"
    }
  }
}
```

OpenCode (`/data/.config/opencode/opencode.json`):

```json
{
  "mcp": {
    "homeassistant": {
      "type": "sse",
      "url": "<HA_MCP_URL aus .env>"
    }
  }
}
```

---

### Ü3: `lovelace-sync` nicht lauffähig

- **Claude (alpha10):** Tool nicht im PATH erreichbar
- **OpenCode (alpha11):** Im PATH (`/homeassistant/bin`), aber crasht mit
  `ModuleNotFoundError: No module named 'websockets'`

**Fix:** Python-Paket `websockets` systemweit installieren.

---

### Ü4: `HA_TOKEN` / `ha-api` Stabilität

- **Claude (alpha10):** Token leer in `options.json`, `.env` als manueller Workaround
- **OpenCode (alpha11):** In alpha11 behoben — `$HA_TOKEN` in `.env` gesetzt, `ha-api` funktioniert

**Status:** ✅ In alpha11 behoben.

---

## OpenCode-spezifische Findings (nicht in Claude-Analyse)

### O1: `/homeassistant/bin` shadowed System-Tools (MITTEL)

`/homeassistant/bin` steht an **Position 1 im PATH** und überschreibt `/usr/local/bin`:

| Tool            | Aktiv via PATH                         | System-Version            | Unterschied        |
| --------------- | -------------------------------------- | ------------------------- | ------------------ |
| `ha-api`        | `/homeassistant/bin/ha-api` (veraltet) | `/usr/local/bin/ha-api`   | Fehlt 1 Suchpfad   |
| `ha-ws`         | `/homeassistant/bin/ha-ws`             | `/usr/local/bin/ha-ws`    | Identisch          |
| `lovelace-sync` | `/homeassistant/bin/lovelace-sync`     | nicht in `/usr/local/bin` | Nur deprecated Ort |

**Fix:** `/homeassistant/bin` ans Ende des PATH verschieben oder deprecated Duplikate entfernen.

---

## Claude-spezifische Findings (nicht in OpenCode-Analyse)

### C1: `fff-mcp` installiert, aber nicht als MCP-Server registriert (MITTEL)

`/usr/local/bin/fff-mcp` ✅ vorhanden und ausführbar (in alpha11 verifiziert), aber in keiner KI-Konfiguration als
MCP-Server eingetragen.

`AGENTS.md` dokumentiert: _"`fff-mcp` — fast file search MCP server (register in Claude Code / OpenCode config)"_

**Fix:** In beide KI-Konfigurationen eintragen:

Claude Code:

```json
"fff": { "command": "fff-mcp", "args": ["/homeassistant"] }
```

OpenCode:

```json
"fff": { "type": "stdio", "command": "fff-mcp", "args": ["/homeassistant"] }
```

---

### C2: `options.json` unterstützt `mcp_servers` — wird nicht genutzt (MINOR)

`/data/options.json` enthält `"mcp_servers": []` — das Add-on hat also einen eingebauten Mechanismus, MCP-Server zu
konfigurieren, der aber leer ist. Unklar, ob dieser Mechanismus die KI-Tool-Configs automatisch befüllen soll.

**Klärungsbedarf:** Soll `mcp_servers` in `options.json` die MCP-Konfiguration für Claude Code und OpenCode automatisch
setzen? Falls ja, wäre das der korrekte Weg.

---

## Gesamtübersicht (alpha11)

| #   | Problem                                     | Quelle   | Status                   | Schwere   |
| --- | ------------------------------------------- | -------- | ------------------------ | --------- |
| Ü1  | `ha` CLI: `hassio_role` zu niedrig          | beide    | ⚠️ Token da, `forbidden` | KRITISCH  |
| Ü2  | MCP-Server nicht konfiguriert               | beide    | ❌ offen                 | KRITISCH  |
| Ü3  | `lovelace-sync` crasht (`websockets` fehlt) | beide    | ⚠️ teilweise             | MITTEL    |
| Ü4  | `$HA_TOKEN` Stabilität                      | beide    | ✅ behoben               | ~~MINOR~~ |
| O1  | `/homeassistant/bin` shadowed System-Tools  | OpenCode | ⚠️ offen                 | MITTEL    |
| C1  | `fff-mcp` nicht als MCP registriert         | Claude   | ❌ offen                 | MITTEL    |
| C2  | `options.json` `mcp_servers` ungenutzt      | Claude   | ❓ unklar                | MINOR     |

---

## Was funktioniert

- `ha-api` (REST-Calls: states, services, history) ✅
- `ha-ws` (WebSocket-Calls: entities, areas) ✅
- `ha-check-logs`, `ha-check-repairs` ✅ (neu in alpha11)
- `sqlite3` auf `/homeassistant/home-assistant_v2.db` ✅
- Alle Standard-Shell-Tools (git, rg, fd, jq, yq, bat, eza, ...) ✅
- Python3, uv, node, bun ✅
- `gh` (GitHub CLI) ✅
- `fff-mcp` Binary ✅ (installiert, nur nicht registriert)

---

## Kontext

- HA Version: 2026.4.4
- OpenCode Version: 1.14.31
- Claude Code Version: 2.1.126
- Arbeitsverzeichnis: `/homeassistant` (HA config, live)
- Persistenter Storage: `/data`
- HA URL intern: `http://homeassistant:8123`
- HA URL extern: `https://ha-nextgen.akentner.de`

---
