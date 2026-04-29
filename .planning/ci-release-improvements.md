# Plan: CI — Docker Build & GitHub Release Workflows

**Status:** Backlog — implement after coding-assistants addon is functional **Reference:** magnusoverli/opencode
`.github/workflows/`

## Ziel

Zwei Lücken gegenüber vergleichbaren Addon-Repos schließen:

1. **Pre-built Docker Images** auf GHCR — HA zieht fertiges Image statt lokal zu bauen
2. **GitHub Releases** automatisch bei Tag-Push erstellen

## Scope

Betrifft alle Addons: `fritz-callmonitor2mqtt`, `phone-logger`, `meridian`, `coding-assistants`

---

## Task 1: Docker Build Workflow

**Trigger:** Tag-Push `v*` (z.B. `v1.7.4`) **oder** manuell mit `addon` + `version` Input

**Logik:**

- Tag-Format: `<addon-slug>-v<version>` (z.B. `meridian-v1.37.3`)
- Alternativ: ein Workflow pro Addon, getriggert durch tag-pattern `meridian-v*` etc.
- Build mit `docker/build-push-action`, Base-Image aus `build.yaml` lesen
- Push nach `ghcr.io/akentner/homeassistant-addons/<addon>:<version>` + `:latest`
- Layer-Cache via `type=gha`

**Fragen zu klären:**

- Ein Workflow für alle Addons (matrix) oder ein Workflow pro Addon?
- Tag-Format: `<addon>-v<version>` oder `v<version>` mit `addon` Input?
- `aarch64` auch bauen? Aktuell alles amd64-only in config.yaml/build.yaml.

**config.yaml Änderung:** `image: ghcr.io/akentner/homeassistant-addons/{arch}-<addon>` ergänzen (sonst baut HA weiter
lokal — das `image:`-Feld ist der Trigger für Pull vs. Build)

---

## Task 2: GitHub Release Workflow

**Trigger:** Gleicher Tag wie Docker Build

**Logik:**

- Version aus Tag extrahieren
- `CHANGELOG.md` im Addon-Verzeichnis parsen (Abschnitt für diese Version)
- GitHub Release mit `softprops/action-gh-release` erstellen
- Release-Body = extrahierter Changelog-Abschnitt

**Voraussetzung:** Jedes Addon-Verzeichnis braucht eine `CHANGELOG.md` (aktuell nicht vorhanden — muss beim ersten
Release angelegt werden)

---

## Abhängigkeiten / Reihenfolge

1. Tag-Format festlegen (Entscheidung: pro-Addon-Prefix vs. Matrix-Input)
2. Docker Workflow implementieren + testen (manueller Dispatch)
3. `image:` in config.yaml aller Addons ergänzen
4. Release Workflow implementieren
5. CHANGELOG.md Konvention einführen (Keep a Changelog Format)

---

## Nicht übernehmen aus magnusoverli

- Beta-Release-Pipeline (`beta-v*`) — kein Bedarf
- `check-hab-update.yaml` — unser `auto-update.yml` ist vollständiger
- `update-version-shield.sh` / pre-commit hook — unser `update-version.py` deckt das ab
