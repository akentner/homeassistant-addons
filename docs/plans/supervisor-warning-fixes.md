# Plan: Supervisor-Warnungen beheben

Stand: 2026-11-04. Status: implementiert auf `fix/supervisor-manifest-warnings`; App-Updates folgen nach Merge und
Image-Builds.

## Ziel und Befund

Eigene Apps sollen beim Store-Reload ohne Mapping- und Options-Warnungen geladen werden. Bestehende Dateien,
Container-Pfade, Zugriffsrechte und konfigurierte Secrets müssen erhalten bleiben.

Die Nextgen-Diagnose zeigte keine ERROR-/CRITICAL-Einträge im geprüften Acht-Stunden-Zeitraum. Core läuft mit 2026.10.4.
Die relevanten Meldungen entstanden beim Store-Reload und bestanden bereits vor dem UI-Push.

| Priorität | Befund                                                                                              | Maßnahme                                                              |
| --------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| P0        | Lokaler Manifest-Validator kennt aktuelle Mapping-Typen unvollständig und prüft nur Objekt-Einträge | Validator zuerst erweitern                                            |
| P1        | Secrets Sync kombiniert `config`, `addon_config` und `all_addon_configs`                            | Konfliktfreie aktuelle Typen mit expliziten bisherigen Pfaden         |
| P1        | Sechs SOPS-Defaults fehlen im Schema                                                                | Unterstützte Optionen korrekt typisieren                              |
| P2        | Phone Logger, Gatus, LiteLLM und Coding Assistants verwenden Legacy-Mappings                        | Typen migrieren; Pfade und Rechte erhalten                            |
| P2        | Auch Authentik und Markdown Renderer verwenden alte Mapping-Typen                                   | Im selben Repo-Audit berücksichtigen                                  |
| P3        | LiteLLM meldet alte `providers`-/`models`-Optionen                                                  | Gespeicherte Altoptionen kontrolliert bereinigen                      |
| Separat   | Fremd-Apps und fremde Test-Konfigurationen erzeugen Warnungen                                       | Zuständigen Repositories zuordnen                                     |
| Separat   | `build.yaml` ist laut Supervisor veraltet                                                           | Eigene Migration planen; aktuelle Drei-Dateien-Versionierung beachten |

## 1. Validator und Regressionstests

Datei: `internal/validate-addon-config.py`; neue Tests bei den internen Validator-Tests anlegen.

- Aktuelle Typen ergänzen: `homeassistant_config`, `app_config`, `all_app_configs`, `local_apps`.
- Objektform und Kurzform wie `share:rw` validieren, einschließlich Typ und Schreib-/Lesemodus.
- Unbekannte Typen, ungültige Einträge, leere oder doppelte explizite Mount-Ziele erkennen.
- Konflikte zwischen `config` und den aktuellen Konfigurations-Mappings erkennen.
- Kombinationen eines aktuellen Typs mit seinem Legacy-Alias erkennen.
- Legacy-Typen verständlich melden; aktuelle Manifeste müssen die modernen Typen verwenden.
- Rekursiv prüfen, dass Options-Defaults vom Schema abgedeckt sind. Listen und verschachtelte Schemas beachten; ein
  bewusst offenes Schema bleibt ein eigener, ausdrücklich zu behandelnder Fall.

Abnahme: Ein Fixture mit der heutigen Secrets-Sync-Konfiguration reproduziert die fehlenden SOPS-Felder und den
Mapping-Konflikt. Korrigierte Fixtures bestehen; bestehende gültige Manifeste werden nicht fälschlich abgewiesen.

## 2. Secrets Sync zuerst korrigieren

Dateien: `secrets-sync/config.yaml`, Konfigurationsdokumentation, Übersetzungen und passende Regressionstests.

Geplante Mounts in Langform:

| Neuer Typ              | Expliziter Container-Pfad | Zugriff |
| ---------------------- | ------------------------- | ------- |
| `homeassistant_config` | `/config`                 | rw      |
| `app_config`           | `/addon_config`           | rw      |
| `all_app_configs`      | `/addon_configs`          | ro      |

Damit entfällt der Legacy-Konflikt, während `SS_SECRETS_FILE`, AGE-/SSH-Schlüsselpfade und der Usage-Scanner ihre
bisherigen Pfade behalten. Vor einem Live-Update die tatsächlichen Bind-Mounts und Dateimetadaten prüfen. Das bislang
ignorierte App-Konfigurations-Mapping kann erstmals wirksam werden: vorhandene Schlüssel dürfen dadurch nicht unbemerkt
verdeckt werden. Falls nötig, eine explizite Datenmigration vorbereiten, ohne Schlüsselinhalte auszugeben.

Schema unter `sops` vervollständigen:

- `source`: Auswahl `file|git`; bisheriges Standardverhalten `file` erhalten.
- `git_url`, `git_branch`, `git_path`, `git_username`: passende optionale String-Felder; SSH-SCP-Adressen müssen neben
  HTTPS und SSH-URLs weiter funktionieren. Die bestehende Provider-Validierung bleibt erhalten.
- `git_token`: optionales Passwortfeld; bestehende `!secret`-Referenzen und leere Defaults weiter unterstützen.
- Bestehende `file`-/`flatten_separator`-Felder und gespeicherte Optionen nicht entfernen.

Abnahme: Defaults und bestehende File-/Git-Konfigurationen bestehen die Supervisor-Optionsvalidierung. Keine
`Unknown option`-Meldungen für die sechs SOPS-Felder. Schreiben der Secrets, Lesen verschlüsselter Dateien, Zugriff auf
AGE-/Deploy-Key-Dateien und Scannen der App-Konfigurationen funktionieren unter den erhaltenen Pfaden.

## 3. Weitere eigene Mappings migrieren

| App               | Änderung                                | Pfad-Invariante                                                   |
| ----------------- | --------------------------------------- | ----------------------------------------------------------------- |
| Phone Logger      | `addon_config` → `app_config`           | `/addon_config`, rw                                               |
| Gatus             | `addon_config` → `app_config`           | `/addon_config`, rw; vorhandene Konfiguration und Crontab lesbar  |
| LiteLLM           | `addon_config` → `app_config`           | `/addon_config`, rw; DB-/Modellkonfiguration bleibt verfügbar     |
| Authentik         | `addon_config` → `app_config`           | `/addon_config`, rw                                               |
| Coding Assistants | `addons` → `local_apps`                 | `/addons`, rw                                                     |
| Coding Assistants | `all_addon_configs` → `all_app_configs` | `/addon_configs`, rw; `/homeassistant` unverändert                |
| Markdown Renderer | `config` → `homeassistant_config`       | Tatsächlich genutzten bisherigen `/config`-Pfad explizit erhalten |

Dokumentation und Tests aktualisieren, die Mapping-Typen oder Mount-Pfade prüfen. Keine neue Umbenennung von
Container-Verzeichnissen in diesem Fix. Pro App ein prüfbarer Commit mit Manifest, Doku und Versionsanpassung.

## 4. Gespeicherte Altoptionen getrennt bereinigen

LiteLLM nutzt laut `run.sh` inzwischen DB-basierte Modellverwaltung; `providers` und `models` gehören nicht mehr zum
Manifest-Schema. Sie nicht als wirkungslose Schema-Felder wieder einführen, nur um Warnungen zu verstecken.

Zuerst die gespeicherten Optionen und die DB-basierte Modellkonfiguration gegen den installierten Stand prüfen. Eine
geschützte Rückfallkopie vorbereiten. Danach ausschließlich bestätigte Altoptionen entfernen; aktive Optionen, Secrets
und DB-Einträge erhalten. Nicht mit den Mapping-Änderungen vermischen.

`backup_hint` von HA MCP und die ungültige Testdatei aus dem fremden Repository separat dokumentieren. Fremde
Repository-Dateien nicht lokal umschreiben: Der nächste Store-Reload könnte diese Änderungen wieder ersetzen.

## 5. Validierung, Versionierung und Rollout

1. Validator-Fixtures und die Tests der betroffenen Apps ausführen; Secrets Sync einschließlich Engine und SOPS/Git.
2. Aktuelle und korrigierte Manifeste zusätzlich mit dem auf Nextgen installierten Supervisor-Validator vergleichen.
   Dabei keine echten Secret-Werte in Logs oder Test-Fixtures übernehmen.
3. `make validate-addons`, `make validate-versions` und die relevanten Pre-commit-Prüfungen ausführen.
4. Für reine Manifest-/Schema-/Dokumentationsänderungen den jeweils nächsten freien Subpatch verwenden, ausschließlich
   über `make update-version ADDON=… VERSION=X.Y.Z-N NO_TAG=yes NO_PUSH=yes`. Falls Programmlogik für eine Migration
   nötig wird, die Versionierung gemäß den Repository-Regeln neu bewerten. Upstream-Binaries nicht nebenbei ändern.
5. Commits und PR gegen den aktuellen `main` vorbereiten, damit inzwischen erfolgte Änderungen erhalten bleiben. CI und
   Image-Builds müssen vor dem Live-Update erfolgreich sein.
6. Zuerst Secrets Sync kontrolliert aktualisieren. Tatsächliche Mounts, Dateien, Secrets-/Git-Zugriff und die
   Supervisor-Warnungen prüfen. Danach die übrigen Apps einzeln aktualisieren.
7. Für den Vergleich nur neue Logs ab dem Rollout-Zeitpunkt auswerten. Fremde Warnungen getrennt zählen.
8. Rückfall: vorheriges Image/Manifest und geschützte Optionskopie bereithalten. Datenpfade beibehalten; kein pauschaler
   Core-/Supervisor-Neustart als Teil dieses Plans.

## Fertig-Kriterien

- Keine eigenen Legacy-Mapping- oder Mapping-Konflikt-Warnungen beim Store-Reload.
- Keine unbekannten SOPS-Optionen bei Secrets Sync.
- Bisherige Container-Pfade, Rechte und vorhandene Dateien sind nachweislich erhalten.
- Validator-Tests verhindern eine erneute Kombination inkompatibler Mappings und unvollständiger Options-Schemas.
- Verbleibende Fremd- und `build.yaml`-Warnungen sind ausdrücklich zugeordnet und separat nachverfolgt.

## Referenzen

- [Aktuelle HA-App-Konfiguration: Ordner und Mount-Pfade](https://contributors.home-assistant.io/apps/reference/configuration/#folders)
- [Supervisor: Mapping-Konflikte und Migrationen](https://github.com/home-assistant/supervisor/blob/main/supervisor/apps/validate.py)
- [Supervisor: aktuelle und veraltete Mapping-Typen](https://github.com/home-assistant/supervisor/blob/main/supervisor/apps/const.py)
- Lokale Evidenz: `secrets-sync/config.yaml`, `internal/validate-addon-config.py`, `litellm/run.sh` und die am
  2026-11-04 gelesenen Nextgen-Supervisor-Logs.

## Umsetzungsstand

- Sieben Manifeste korrigiert und ausschließlich per Versionstool als Subpatch vorbereitet: Secrets Sync 0.7.0-1, Phone
  Logger 1.0.6-1, Gatus 5.38.0-1, LiteLLM 1.108.0-1, Coding Assistants 1.1.0-1, Authentik 2026.8.5-1 und Markdown
  Renderer 1.1.0-24. Ausgangspunkt ist der aktuelle `main`, unabhängig vom UI-Branch.
- Der installierte Nextgen-Supervisor validiert alle korrigierten Manifeste ohne Warnung. Der unveränderte
  Secrets-Sync-Vergleichsstand erzeugt neun Warnungen.
- Secrets Sync: `/addon_config` ist derzeit nicht gemountet und enthält keine Schlüsseldateien im Container. Die neuen
  Mappings erhalten die bisherigen Ziele und Rechte und aktivieren diesen fehlenden Mount.
- LiteLLM: `models` und `providers` auf Nextgen mit geschützter Optionskopie bereinigt. Die übrigen Optionen sind
  unverändert; die App bleibt gestoppt. Reproduzierbares Werkzeug: `internal/cleanup-litellm-options.py`.
- Der gemeinsame Manifest-/Validator-Commit hält den Zwischenstand konsistent: Der strengere Validator würde die noch
  unveränderten Legacy-Manifeste gezielt ablehnen.
- Manifest-/Bereinigungs-Regressionstests und CI-Anbindung ergänzt. Die vollständigen Secrets-Sync-Tests bestehen.
- Paket-Rollout und neue Mounts sind noch nicht live: erst nach Merge und erfolgreichen Image-Builds aktualisieren.
