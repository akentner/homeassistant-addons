# Phase 20: litellm-addon - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-19
**Phase:** 20-litellm-addon
**Areas discussed:** Audit-Fixes B1-B5 (Blocker), H1-H6 (High), M1-M7 (Medium), L1-L5 (Low) + 10 Open Questions aus Design-Doc + 4 spezifische Design-Aspekte

---

## Audit: Repo-Convention-Compliance

Der existierende Design-Doc (`.planning/phases/20-litellm-addon/PLAN.md`) wurde extern erstellt und gegen die
tatsächlichen Repo-Konventionen, Validierungs-Skripte, Pre-Commit-Hooks und alle existierenden Add-ons
geprüft. **11 Pflicht-Fixes** identifiziert + **4 Nice-to-have**-Polish-Items.

| Option | Description | Selected |
|--------|-------------|----------|
| Alle 11 Fixes in CONTEXT.md übernehmen | User-Directive "alle Kriterien erfüllen" | ✓ |
| Nur Blocker, High offen halten | Konservativer Approach | |
| Punkt-für-Punkt-Diskussion | 11 Runden Review | |

**User's choice:** Direktive "Stelle sicher, dass alle Kriterien und Best Practises erfüllt sind" → alle Fixes
als Decisions in CONTEXT.md aufgenommen (Audit-Default).
**Notes:** User kann nach Review einzelne Decisions revidieren bevor `/gsd-plan-phase 20`.

---

## Blocker B1: Dockerfile `BUILD_FROM`-Default vs. `build.yaml`-Mismatch

| Option | Description | Selected |
|--------|-------------|----------|
| `ARG BUILD_FROM=…python:3.13-debian-trixie` (Design) | Builder-Stage passt, Runtime-Stage-Mismatch bei fehlendem `--build-arg` | |
| `ARG BUILD_FROM=…debian:trixie` (matches build.yaml) | Konsistent mit authentik/iac-runner-Präzedenz | ✓ |

**User's choice:** Fix D-02 in CONTEXT.md — `BUILD_FROM`-Default korrigiert zu `ghcr.io/home-assistant/amd64-base-debian:trixie`.
**Notes:** Audit-Korrektur; latent bug wenn jemand `docker build` ohne `--build-arg BUILD_FROM=...` ausführt.

---

## Blocker B2: `LITELLM_VERSION` Build-Arg wird vom Auto-Update nicht synchronisiert

| Option | Description | Selected |
|--------|-------------|----------|
| Streichen, `VERSION` direkt verwenden | Sauberste Lösung, kein separater Build-Arg | |
| `update-version.py` um generische `secondary_args` erweitern | Code-Änderung im Versions-Script | |
| `auto-update.yml` post-processing (sed-Replacement) | Auto-Update-Workflow ergänzt `LITELLM_VERSION = VERSION` nach `update-version.py` | ✓ |

**User's choice:** Fix D-30 in CONTEXT.md — `auto-update.yml` setzt `LITELLM_VERSION` nach `update-version.py`.
**Notes:** Vermeidet Code-Änderung in `update-version.py` (Single-Purpose bleibt erhalten). Trade-off: leichte
Kopplung zwischen Workflow und Build-Arg-Name; akzeptabel für ein Add-on.

---

## Blocker B3: Models-Schema Regex verbietet `/`

| Option | Description | Selected |
|--------|-------------|----------|
| `match(^[a-zA-Z0-9._:-]{1,128}$)` (Design) | Konservativ, aber bricht LiteLLM-Cross-Provider-Routing | |
| `match(^[a-zA-Z0-9._:/+-]{1,256}$)` (Audit-Fix) | Erlaubt `bedrock/anthropic.claude-…`, `openai/gpt-4o`, `azure/gpt-4` | ✓ |

**User's choice:** Fix D-26 in CONTEXT.md — Regex um `/` und `+` erweitert, Length-Limit auf 256.
**Notes:** Notwendig für LiteLLM-Pfad-Syntax (Provider-Routing).

---

## Blocker B4: Dockerfile OCI-Label-Block fehlt komplett

| Option | Description | Selected |
|--------|-------------|----------|
| Nur `CMD ["/run.sh"]` (Design, abgeschnitten) | HADOLINT-DL3006-Verletzung möglich; HA-Spec nicht erfüllt | |
| Vollständiger OCI-Label-Block (authentik-Präzedenz Zeile 78-103) | Konsistent mit allen anderen Add-ons | ✓ |

**User's choice:** Fix D-06 in CONTEXT.md — vollständiger Label-Block (`io.hass.name`, `org.opencontainers.image.*`).
**Notes:** HA-Add-on-Spec verlangt Labels; `hadolint` würde fehlende Labels flaggen.

---

## Blocker B5: run.sh Signal-Trap fehlt

| Option | Description | Selected |
|--------|-------------|----------|
| Kein `trap` (Design) | HA Supervisor SIGTERM killed Container sofort → in-flight Requests gekappt | |
| SIGTERM (30s drain) + SIGHUP (log-reopen) — authentik/iac-runner-Präzedenz | Konsistent mit Repo-Konventionen | ✓ |

**User's choice:** Fix D-10 in CONTEXT.md — Signal-Trap am Anfang von run.sh.
**Notes:** Phase-9/10/16-etabliert in terraform-bridge/iac-runner; alle neueren Add-ons haben es.

---

## High H1: `LITELLM_LOG` Env-Var nicht aus `log_level` gemappt

| Option | Description | Selected |
|--------|-------------|----------|
| `LOG_LEVEL=$(bashio::config 'log_level')` ohne Export (Design) | LiteLLM läuft auf Default-Log-Level | |
| Mapping `bashio::log_level → LITELLM_LOG` + `export LITELLM_LOG="${LOG_LEVEL^^}"` | Korrekte Log-Level-Propagation | ✓ |

**User's choice:** Fix D-19 in CONTEXT.md — bashio → LiteLLM-Log-Level-Mapping.
**Notes:** LiteLLM respektiert `LITELLM_LOG` (DEBUG/INFO/WARNING/ERROR). Mapping:
debug→DEBUG, info→INFO, warning→WARNING, error→ERROR. Bash `^^` für uppercase-Konvertierung.

---

## High H2: `LITELLM_SALT_KEY` Env-Var im Design nur als Kommentar

| Option | Description | Selected |
|--------|-------------|----------|
| `# (analogous for salt_key)` (Design Zeile 342) | Unvollständig — LiteLLM braucht beide Keys | |
| Vollständige analoge Implementierung: `/data/.litellm_salt_key`, chmod 600, `export LITELLM_SALT_KEY=...` | Konsistent mit Master-Key-Lifecycle | ✓ |

**User's choice:** Fix D-12 in CONTEXT.md — vollständige analoge Salt-Key-Implementierung.
**Notes:** Salt-Key wird für Token-Hashing in LiteLLM verwendet; muss analog zu Master-Key persistiert werden.

---

## High H3: LiteLLM-Config-Synthese ist nicht spezifiziert

| Option | Description | Selected |
|--------|-------------|----------|
| `bashio::var.json | jq -r '… transform …'` (Design Zeile 397-399) | jq-Filter nur angedeutet; JSON→YAML-Konvertierung nicht-trivial | |
| Python-Helper `litellm/generate_config.py` (phone-logger-Präzedenz) | Konsistent mit bestehendem Muster; Python bereits im LiteLLM-Wheelhouse | ✓ |

**User's choice:** Fix D-17 in CONTEXT.md — Python-Helper statt bash+jq-Transform.
**Notes:** phone-logger-Präzedenz für `generate_config.py`; Python 3.13 ist bereits Runtime für LiteLLM —
keine zusätzliche apt-Abhängigkeit. jq-Transform wäre fragil bei nested-dict-Modellen-Liste.

---

## High H4: `password?` Schema + `!secret` Interaktion unbestätigt

| Option | Description | Selected |
|--------|-------------|----------|
| Direkt in LITELLM-04-Plan umsetzen (Design Q8) | Risiko: Schema-Parser könnte `!secret`-Default + `password?` ablehnen | |
| Empirischer Spike vor LITELLM-04 als Block auf kritischen Pfad | Bestätigt Interaktion vor Implementierung | ✓ |

**User's choice:** Fix D-35 in CONTEXT.md — `internal/spike-litellm-secret-schema.sh` als Pre-Plan-Spike.
**Notes:** Verhindert kostspieligen Rollback wenn Schema-Parser strikter ist als erwartet. Ergebnis
dokumentiert in DOCS.md (Master-Key-Sektion).

---

## High H5: Kein `health_check:` in config.yaml

| Option | Description | Selected |
|--------|-------------|----------|
| Kein health_check (Design) | HA Supervisor zeigt Add-on als "started" auch bei hängendem Prozess | |
| `health_check: { endpoint: http://localhost:4000/health/liveliness, interval: 30, timeout: 5 }` | HA Supervisor pollt aktiv; Failed → "unhealthy" | ✓ |

**User's choice:** Fix D-23 in CONTEXT.md — health_check-Block mit `/health/liveliness`-Endpoint.
**Notes:** LiteLLM 1.39+ hat `/health/liveliness` (Prozess-lebend) + `/health/readiness` (DB-verbunden).
Liveness vs. Readiness Trade-off: liveness ist hier passender (HA will wissen "Container hängt nicht").

---

## High H6: Backup-Integration für `/data/postgresql` unklar

| Option | Description | Selected |
|--------|-------------|----------|
| `map: [{ type: addon_config, ... }]` (Design) | Sichert nur `/addon_config`, NICHT `/data/postgresql` | |
| `map: [{ type: addon_config, ... }, { type: backup, read_only: false }]` | HA Supervisor sichert automatisch `/data` (postgres + Keys + Config) | ✓ |

**User's choice:** Fix D-24 in CONTEXT.md — `map: backup:rw` für `/data`-Backup.
**Notes:** Trade-off: HA macht nur File-Level-Backup (kein `pg_dump`) — Restore kann inkonsistent sein.
Akzeptabel für Home-Use; explizit in DOCS.md dokumentieren.

---

## Medium M1: Kein `WORKDIR` in Stage 1/2

| Option | Description | Selected |
|--------|-------------|----------|
| Kein `WORKDIR` (Design) | hadolint DL3045-Warnung | |
| `WORKDIR /` am Anfang Stage 2 | hadolint-konform | ✓ |

**User's choice:** Fix D-05 in CONTEXT.md — `WORKDIR /` in Stage 2.
**Notes:** Stage 1 braucht keinen WORKDIR (kein COPY), Stage 2 schon.

---

## Medium M2: Kein `--no-cache-dir` bei `pip install`

| Option | Description | Selected |
|--------|-------------|----------|
| `pip install --no-index --find-links=/wheels …` (Design) | hadolint DL3042-Warnung | |
| `pip install --no-cache-dir --no-index --find-links=/wheels …` | hadolint-konform + kleinere Image | ✓ |

**User's choice:** Fix D-04 in CONTEXT.md — `--no-cache-dir` hinzugefügt.
**Notes:** Reduziert Image-Größe + hadolint-konform.

---

## Medium M3: `bashio::var.json | jq` Syntax fehlerhaft

| Option | Description | Selected |
|--------|-------------|----------|
| `bashio::var.json log_level "..." | jq` (Design) | jq-Filter unvollständig, Models-Liste fehlt | |
| Python-Helper `litellm/generate_config.py` (H3) | Saubere Lösung, Konsistenz mit phone-logger | ✓ |

**User's choice:** Fix D-17 in CONTEXT.md — Python-Helper ersetzt bash+jq komplett.
**Notes:** H3 und M3 hängen zusammen; Python-Helper löst beide.

---

## Medium M4: `models`-Provider-Liste hartkodiert auf 6

| Option | Description | Selected |
|--------|-------------|----------|
| `list(openai|anthropic|google|azure|ollama|bedrock)` (Design) | HA-Schema-Validation; schließt viele Provider aus | |
| `str?` mit Validierung in `generate_config.py` | Flexibler; akzeptiert LiteLLM's 100+ Provider | ✓ |

**User's choice:** Fix D-26 in CONTEXT.md — `provider: "str?"` (frei).
**Notes:** Validierung wandert in `generate_config.py` (das ohnehin Python-LiteLLM-Konfiguration
kennt); Trade-off: HA-UI akzeptiert ungültige Provider-Namen, Validation-Fehler erscheinen erst beim
Container-Start.

---

## Medium M5: `image:`-Feld in config.yaml fehlt (optional)

| Option | Description | Selected |
|--------|-------------|----------|
| Kein `image:` (authentik/iac-runner-Präzedenz) | `build.yml` auto-generiert Image-Tag | |
| `image: "ghcr.io/akentner/homeassistant-addons/{arch}-litellm"` | Konsistent mit 7 von 9 Add-ons | ✓ |

**User's choice:** Fix D-22 in CONTEXT.md — `image:`-Feld explizit gesetzt.
**Notes:** build.yml überschreibt das beim Build, aber explizit zu setzen ist robuster.

---

## Medium M6: `make release`-Pfad nicht dokumentiert

| Option | Description | Selected |
|--------|-------------|----------|
| Nur Auto-Update erwähnt (Design) | Manueller Override-Pfad unklar | |
| DOCS.md dokumentiert `make release ADDON=litellm VERSION=X.Y.Z` | Operator-Override-Pfad klar | ✓ |

**User's choice:** Fix D-31 in CONTEXT.md — `make release`-Pfad in DOCS.md.
**Notes:** Auto-Update ist Normalfall; manueller Override nur für Notfälle.

---

## Medium M7: CHANGELOG.md nicht erwähnt

| Option | Description | Selected |
|--------|-------------|----------|
| Keine CHANGELOG-Erwähnung (Design) | Auto-Update-Workflow generiert sie, aber Design sagt nichts | |
| DOCS.md erwähnt, dass CHANGELOG.md vom Auto-Update gepflegt wird | Klare Erwartung an Operator | ✓ |

**User's choice:** In CONTEXT.md als etabliertes Verhalten dokumentiert; keine Aktion nötig.
**Notes:** CHANGELOG.md wird vom Auto-Update-Workflow automatisch beim ersten Bump angelegt.

---

## Low L1: panel_icon / panel_title

| Option | Description | Selected |
|--------|-------------|----------|
| Kein panel_icon (Design) | HA-Sidebar zeigt nur Add-on-Name | |
| `panel_icon: mdi:brain`, `panel_title: "LiteLLM"` | Konsistent mit gatus/markdown-renderer-Präzedenz | (Discretion) |

**User's choice:** Agent's Discretion — vorgeschlagen in CONTEXT.md, kann bei Implementierung ergänzt werden.

---

## Low L2: `prometheus_multiproc_dir`-Frage

| Option | Description | Selected |
|--------|-------------|----------|
| Open lassen (Design Q6) | Unklar ob LiteLLM multiprocess metrics braucht | |
| Single-Worker-Annahme → nicht nötig | LiteLLM wird mit `uvicorn` (default 1 worker) gestartet | ✓ |

**User's choice:** In CONTEXT.md als Out-of-Scope-Bestätigung dokumentiert.
**Notes:** Falls in Zukunft `--workers > 1` gewünscht, muss `PROMETHEUS_MULTIPROC_DIR` gesetzt werden
(authentik-Präzedenz Zeile 84-86).

---

## Low L3: `password?` + `!secret` als Spike

| Option | Description | Selected |
|--------|-------------|----------|
| Inline in LITELLM-04-Plan (Design) | Spike verzögert nicht; Risiko unbekannt | |
| `internal/spike-litellm-secret-schema.sh` als Pre-Plan-Spike | Bestätigt Interaktion empirisch | ✓ |

**User's choice:** Fix D-35 in CONTEXT.md — als Pre-Plan-Skript.
**Notes:** H4 + L3 sind dasselbe Issue; in CONTEXT.md zusammengeführt.

---

## Low L4: `make validate-addons` Auto-Discovery

| Option | Description | Selected |
|--------|-------------|----------|
| Manuell in Makefile eintragen | Überflüssig — `for addon_dir in */` deckt `litellm/` ab | |
| Auto-Discovery | ✓ | ✓ |

**User's choice:** Keine Aktion nötig — `litellm/` wird automatisch erkannt.

---

## Low L5: `LOCAL_BUILD_ADDONS`-Allowlist

| Option | Description | Selected |
|--------|-------------|----------|
| `litellm` zur Allowlist hinzufügen | Würde ghcr.io-Publish überspringen (falsch) | |
| Nicht hinzufügen | `litellm` wird via ghcr.io publisht (korrekt) | ✓ |

**User's choice:** Keine Aktion nötig — `litellm` ist NICHT auf der Allowlist (default).

---

## the agent's Discretion

- `litellm/generate_config.py` Python-Logik im Detail (phone-logger-Präzedenz als Vorlage)
- `panel_icon` (`mdi:brain`) + `panel_title` (`LiteLLM`) für Ingress
- Zusätzliche `LITELLM_*`-Env-Vars (z.B. `LITELLM_PROXY_BATCH_TIMEOUT`, `LITELLM_PROXY_MAX_REQUEST_SIZE`)
- Verifier-Bash-Struktur (welche `docker run`-Flags, welche Assertions)
- Image-Size-Threshold in `verify-litellm-scaffold.sh` (Vorschlag: ≤ 500 MiB)

## Deferred Ideas

- Master-Key Rotation Endpoint (POST /key/rotate mit 24h Grace) — v1.6+
- Cloudflare-Fronted Public-Surface — explizit out-of-scope per User-Decision 2026-09-19
- Multi-Arch-Builds (aarch64, armv7) — PROJECT.md Out-of-Scope
- SQLite-Fallback — Doppel-Code-Pfad nicht wert
- OAuth/PKCE-Flow für HA-Auth — nur relevant bei Public-Surface
- Web-basiertes Admin-UI — LiteLLM-Swagger-UI sufficient
- HA-WebSocket-Custom-Integration für LiteLLM-Status — Custom-Component-Aufwand
- Per-Provider-Default-Models — Trade-off User-Confusion vs. Out-of-Box
- TLS-Termination im Add-on (Caddy/Traefik) — separate Add-on-Lösung
- Prisma-Migration-Step in run.sh — empirische Verifikation in Phase 20-E2E
