# Phase 21: cups-print-server-addon-airprint-mdns-fixes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-26
**Phase:** 21-cups-print-server-addon-airprint-mdns-fixes
**Areas discussed:** Fork-Umfang, Avahi-Reflector-Fix, Hostname-Stabilität, Sofort-Maßnahme jetzt

---

## Fork-Umfang

| Option | Description | Selected |
|--------|-------------|----------|
| Eigenständiges Add-on mit Options | Neues Add-on im 4-Datei-Pattern, eigener Slug, HA-Options/Schema für Avahi/Hostname/Drucker | ✓ |
| Drop-in-Replacement | Gleicher Slug wie f1c878cb_cups, nur Avahi-Fix gepatcht, weiterhin keine Options | |
| Minimal-Patch als eigenes Add-on | Eigener Slug, aber ohne Options/Schema — nur hardcoded Fix | |

**User's choice:** Eigenständiges Add-on mit Options.

---

| Option | Description | Selected |
|--------|-------------|----------|
| avahi_reflector (bool) | enable-reflector=yes/no umschaltbar | ✓ |
| avahi_hostname (str) | Fester expliziter Hostname für Avahi/cupsd | ✓ |
| printer_uri / printer_name | Drucker-URI und Name als Option | ✓ (später zu Liste erweitert) |
| log_level | Standard-Option für Debug-Logging | ✓ |

**User's choice:** Alle vier gewählt (multiSelect).

---

| Option | Description | Selected |
|--------|-------------|----------|
| cups | Kurz, passend zu bestehenden Ordnernamen (gatus/, phone-logger/, meridian/) | ✓ |
| cups-airprint | Expliziter Fokus auf AirPrint/mDNS im Namen | |

**User's choice:** cups.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Ein Drucker (empfohlen) | printer_uri/printer_name als einzelne String-Options, deckt aktuellen Use-Case | |
| Mehrere Drucker von Anfang an | Liste von Drucker-Objekten, mehr Aufwand, aber zukunftssicher | ✓ |

**User's choice:** Mehrere Drucker von Anfang an.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Liste von Objekten (empfohlen) | printers: [{name, uri, enabled}], HA-Schema-Listen, lpadmin-Registrierung pro Eintrag | ✓ |
| Kommagetrennte Strings | Parallele Index-basierte String-Listen | |

**User's choice:** Liste von Objekten.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Kein Upstream-Tracking (empfohlen) | Kein .upstream.yaml — kein Source-Tarball zum Tracken | |
| MaxWinterstein/homeassistant-addons als Upstream | Aktuell installierter Fork als Tracking-Basis | |
| zajac-grzegorz/homeassistant-addon-cups-airprint als Upstream | Ursprungs-Repo statt Fork | |

**User's choice (free text):** "Cups als Upstream?" → Claude erklärte den Unterschied zwischen GitHub-Tag-Tracking (phone-logger/gatus-Pattern) und Alpine-apk-Paketbezug; Rückfrage des Nutzers führte zur finalen Entscheidung.

**Notes:** Finale Entscheidung nach Rückfrage: kein `.upstream.yaml`, stattdessen Eintrag in `internal/base-image-config.yaml` (Alpine-Base-Image-Pattern wie `gatus`/`meridian`/`network-tools`) — der bestehende `base-image-update.yml`-Workflow bumpt den Add-on-Subpatch bei Alpine-Versionssprüngen. Das ist eine Näherung (reagiert auf Alpine-Versionswechsel, nicht direkt auf einzelne CUPS-Releases), aber der einzige im Repo vorhandene automatische Mechanismus ohne eigenen Tarball-Download.

---

## Avahi-Reflector-Fix

| Option | Description | Selected |
|--------|-------------|----------|
| Reflector standardmäßig aus (empfohlen) | enable-reflector=no Default, avahi_reflector Option zum Re-Aktivieren | ✓ |
| Reflector an, Slot-Limit/Timeout erhöht | Root Cause bleibt, nur Symptom gemildert | |
| Watchdog statt Fix | Log-Monitoring statt Ursachenbehebung | |

**User's choice (free text):** "Wofür braucht Avahi den Reflector?" → Claude erklärte Zweck (Cross-Namespace-Bridging) und Nebeneffekt (Legacy-Unicast-Slot-Tabelle), Nutzer bestätigte danach die empfohlene Option.

**Notes:** host_network:true macht den Bridging-Zweck des Reflectors überflüssig; die Slot-Tabelle bleibt aber aktiv und ist die bestätigte Root Cause.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Nein, nicht nötig (empfohlen) | enable-reflector=no eliminiert diesen Fehlermodus komplett | ✓ |
| Ja, generisches Log-Monitoring | Watchdog für andere, unbekannte Avahi-Probleme | |

**User's choice:** Nein, nicht nötig.

---

| Option | Description | Selected |
|--------|-------------|----------|
| run.sh generiert avahi-daemon.conf aus Template (empfohlen) | bashio::config-basierte Generierung, analog gatus/generate_config.py | ✓ |
| Statische avahi-daemon.conf, nur reflector-Zeile gesed't | Weniger Code, weniger konsistent mit Repo-Pattern | |

**User's choice:** run.sh generiert aus Template.

---

**User's freeform follow-up:** "Gibt es vllt. noch andere Avahi/Bonjour Best Practices, die man evtl. noch einbauen könnte" → Claude schlug IPv6-Deaktivierung vor (direkt durch DIAGNOSIS.md-Rohdaten motiviert: IPv6-ULA-Resolution), sowie `host-name-from-machine-id=no` (fällt mit dem Hostname-Bereich zusammen) und minimale Avahi-Publishing-Hygiene (nicht übernommen). Nutzer bestätigte IPv6-Deaktivierung als zusätzliche, konfigurierbare Entscheidung.

**Notes:** Neue Option `avahi_use_ipv6` (bool, Default no) in die Decisions aufgenommen.

---

## Hostname-Stabilität

| Option | Description | Selected |
|--------|-------------|----------|
| Fester expliziter Hostname über Option (empfohlen) | avahi_hostname setzt host-name= in avahi-daemon.conf UND Container-Hostname | ✓ (in modifizierter Form) |
| Nur Avahi host-name fixieren, Container-Hostname unverändert | cupsd könnte weiterhin alten Namen nutzen | |
| Root Cause des Konflikts klären statt Workaround | Untersuchung vor Fix | |

**User's choice (free text):** "Ich neige dazu, den empfohlenen Weg zu gehen. Noch zu klären: gibt es evtl. Probleme mit dem Supervisor, wenn man diesen Weg geht?"

**Notes:** Claude klärte, dass Avahi's `host-name=` unabhängig vom echten Kernel/Docker-Hostnamen ist — keine Notwendigkeit, den Supervisor-verwalteten Container-Hostnamen anzufassen, kein zusätzliches Capability nötig, `cupsd` übernimmt den Avahi-Hostnamen automatisch über die Avahi-Client-API. Damit reduzierte sich die finale Entscheidung auf reines Avahi-Config-Tuning (kein Container-Hostname-Change) — Nutzer bestätigte danach.

---

## Sofort-Maßnahme jetzt

| Option | Description | Selected |
|--------|-------------|----------|
| Nur kurzfristiger Neustart jetzt, getrennt vom Add-on-Bau | Sofortmaßnahme außerhalb der Phase | |
| Kein Sofort-Fix, direkt zum neuen Add-on | Fokus komplett auf Fork | |
| Neustart + Deployment als Teil dieser Phase | Beides im Scope | |

**User's choice (free text):** "Das Addon wurde mittlerweile schon neu gestartet, der Fehler besteht nicht mehr" — Sofortmaßnahme bereits erledigt, außerhalb dieser Diskussion. Keine der drei Optionen trifft mehr direkt zu; Restart-Bedarf entfällt.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Ja, Teil der Phase (empfohlen) | Rollout/Ablösung von f1c878cb_cups gehört zum Scope | ✓ |
| Nein, nur Code/Build — Rollout separat | Installation manuell danach | |

**User's choice:** Ja, Teil der Phase.

**Notes:** Zusatz per Freitext: aktuelle Live-CUPS-Konfiguration von f1c878cb_cups soll als Migrationshilfe ausgelesen und am Ende als Vorschlag für die `printers`-Option ausgegeben werden (Textausgabe, keine automatische Migration).

---

## Claude's Discretion

- Exakte HA-Schema-Syntax für die `printers`-Listen-Option (z.B. `list(match(...))?` vs. verschachteltes `schema`-Objekt).
- Default-Wert für `avahi_hostname` (z.B. `"cups"` vs. slug-abgeleitet) — nicht explizit vom Nutzer vorgegeben.
- Default von `enabled` im `printers`-Objekt (angenommen: `true`).

## Deferred Ideas

None — alle im Gespräch aufgeworfenen Zusatzfragen (IPv6, Supervisor-Hostname-Risiko, Migrations-Vorschlag) wurden direkt innerhalb des Phase-Scopes gelöst, nicht auf spätere Phasen verschoben.
