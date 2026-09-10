# Phase 4: Scaffold + Ingress Validation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents. Decisions are captured in
> CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-27 **Phase:** 04-scaffold-ingress-validation **Areas discussed:** Phase-4-Config-Schema, Base Image +
Python, Mermaid Integration

---

## Phase-4-Config-Schema

### Config Options Format

| Option                        | Description                                                                           | Selected |
| ----------------------------- | ------------------------------------------------------------------------------------- | -------- |
| Einfacher String              | `docs_path: /share/docs` — simpel, direkt testbar; Phase 5 migriert auf Listen-Format |          |
| Schon Namespace-Listen-Format | `directories: [{name, path}]` — Phase-5-kompatibel ab Tag 1                           | ✓        |
| Hartcodierter Pfad            | Fester Testpfad im Dockerfile, kein Config-Feld                                       |          |

**User's choice:** Schon Namespace-Listen-Format **Notes:** User bevorzugt von Anfang an das vollständige Schema, keine
Migration nötig.

### generate_nginx.py Scope

| Option                       | Description                                                                                   | Selected |
| ---------------------------- | --------------------------------------------------------------------------------------------- | -------- |
| Volle Phase-5-Logik          | generate_nginx.py mit Landing Page, Namespace-Validierung, Multi-Namespace — alles in Phase 4 | ✓        |
| Vereinfachte Phase-4-Version | Erstes Element der Liste, kein Landing Page, Phase 5 erweitert                                |          |

**User's choice:** Volle Phase-5-Logik **Notes:** User bestätigte bewusst, dass Phase 4 den vollen MULTI-Umfang
(MULTI-01..06) implementiert.

### Scope-Bestätigung Phase 4 vs. Phase 5

| Option                          | Description                                                                          | Selected |
| ------------------------------- | ------------------------------------------------------------------------------------ | -------- |
| Ja, so soll es sein             | Phase 4: volle Implementierung. Phase 5: End-to-End-Test + HA-Options-UI-Validierung | ✓        |
| Nein, MULTI in Phase 5 behalten | Phase 4 nur Datenmodell, Phase 5 volle Logik                                         |          |

**User's choice:** Ja — Phase 4 liefert volle Implementierung inkl. MULTI-Logik.

---

## Base Image + Python

| Option                            | Description                                                                     | Selected |
| --------------------------------- | ------------------------------------------------------------------------------- | -------- |
| amd64-base-python:3.12-alpine3.20 | Wie phone-logger. Konsistent. generate_nginx.py läuft nativ. nginx via apk add. | ✓        |
| amd64-base + Python installieren  | Alpine-Base + apk add python3 nginx. Mehr Kontrolle, mehr Setup.                |          |
| amd64-base (kein Python)          | generate_nginx.py als Shell-Heredoc. Weniger Abhängigkeiten.                    |          |

**User's choice:** `amd64-base-python:3.12-alpine3.20` **Notes:** Konsistenz mit phone-logger-Pattern war
ausschlaggebend.

---

## Mermaid Integration

| Option                               | Description                                                                                 | Selected |
| ------------------------------------ | ------------------------------------------------------------------------------------------- | -------- |
| doneEach-Hook, fallback dokumentiert | `mermaid.run()` in doneEach. Leward-Plugin als dokumentierter Fallback wenn Test scheitert. | ✓        |
| Leward/mermaid-docsify v2.0.1 direkt | Erprobtes Plugin, zusätzlicher curl im Dockerfile.                                          |          |

**User's choice:** doneEach-Hook primär, Fallback dokumentiert **Notes:** INGRESS-05 ist die primäre Anforderung.
Fallback nur bei empirischem Scheitern.

---

## Claude's Discretion

- Exakte nginx.conf Template-Struktur (über INGRESS-04 hinaus)
- `_docsify/` Verzeichnisname und Platzierung im nginx root
- `build.yaml` base image Version-Tag (aktuelle alpine3.20-Variante)
- `DOCS.md` Struktur und Konfigurationsbeschreibungen
- `repository.yaml` Eintrag für neues Add-on

## Deferred Ideas

- Git-Felder (`git_pull`, `git_pull_interval`) → Phase 6
- SSH-Key-Handling für private Repos → v1.2
- Per-namespace Docsify Theme-Anpassung → v1.2
- Multi-arch Builds → Out of scope
