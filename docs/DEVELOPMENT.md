# Development Guidelines

## Versioning Rules

### Fritz!Box Call Monitor to MQTT Add-on

**WICHTIG**: Die Versionierung folgt einem spezifischen Schema für bessere Add-on-Verwaltung.

#### Versionsformat pro Datei

| Datei | Format | Beispiel | Zweck |
|-------|--------|----------|-------|
| `config.yaml` | `X.Y.Z-N` | `1.3.1-0` | Add-on Version mit Subpatch |
| `build.yaml` | `X.Y.Z` | `1.3.1` | Upstream Binary Version |
| `README.md` | `vX.Y.Z` | `v1.3.1` | Badge Display Version |

#### Regeln

1. **config.yaml**:
   - ✅ **IMMER** Subpatch-Format verwenden: `"X.Y.Z-N"`
   - ✅ Neue Upstream-Versionen starten mit `-0`
   - ✅ Add-on-Fixes inkrementieren: `-1`, `-2`, etc.

2. **build.yaml**:
   - ✅ Nur Upstream-Version ohne Subpatch: `"X.Y.Z"`
   - ✅ Entspricht der Docker-Image-Version

3. **README.md**:
   - ✅ Badge zeigt Hauptversion: `version-vX.Y.Z`
   - ✅ Release-Link zeigt Hauptversion: `tree/vX.Y.Z`

#### Beispiel einer korrekten Versionierung

```yaml
# config.yaml
version: "1.3.1-0"

# build.yaml
VERSION: "1.3.1"

# README.md
[release-shield]: https://img.shields.io/badge/version-v1.3.1-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v1.3.1
```

#### Warum diese Struktur?

- **Upstream-Sync**: Add-on-Version folgt Upstream mit `-0` Reset
- **Add-on-Fixes**: Lokale Fixes können inkrementiert werden
- **Klarheit**: Eindeutige Trennung zwischen Add-on und Binary-Version
- **Wartbarkeit**: Bessere Versionskontrolle und Update-Management

## Auto-Update-System

Das Add-on verwendet `version_pattern: "sync"` in `.upstream.yaml`, wodurch:

- Neue Upstream-Versionen automatisch erkannt werden
- Die config.yaml entsprechend aktualisiert wird
- Der Subpatch automatisch auf `-0` zurückgesetzt wird

## Pre-commit Validierung

Ein pre-commit Hook validiert automatisch:

- Korrekte Versionierung in allen Dateien
- Konsistenz zwischen den Versionsangaben
- Einhaltung des Subpatch-Formats
