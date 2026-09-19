# Phase 20: litellm-addon - Context

**Gathered:** 2026-09-19
**Status:** Ready for planning

<domain>

## Phase Boundary

Neues HA-Add-on `litellm/`, das LiteLLM (OpenAI-kompatibler API-Gateway) + PostgreSQL (State-Store für virtual keys,
spend logs, model definitions) in einem einzigen Container bündelt. Primär LAN/Tailscale auf Port 4000 + Ingress für
Swagger UI in HA UI. Master-Key + per-Provider API-Keys via `!secret`-Auflösung mit Auto-Gen-Fallback in `/data/.<keyfile>`.

Diese Phase liefert konkret:

- `litellm/{config.yaml, build.yaml, Dockerfile, run.sh, README.md, DOCS.md, .upstream.yaml}` — 4-File-Pattern
  + `.upstream.yaml` (gatus-Präzedenz)
- Multi-Stage Dockerfile: `python:3.13-slim-bookworm`-Builder → HA-debian-trixie-Basis + postgres apt + LiteLLM pip wheels
- run.sh: bash-sequential — postgres `pg_ctl` start → `pg_isready` wait → user/db create → `pg_ctl reload` →
  LiteLLM-Config-Synthese → `exec litellm`. Signal-Trap (SIGTERM-Drain + SIGHUP-Reopen) wie authentik/iac-runner
- Master/Salt-Key-Lifecycle: `!secret` → `/data/.<keyfile>` (chmod 600) → `openssl rand -hex 32` auto-gen (one-time
  `bashio::log.notice`)
- Provider-Keys (`openai_api_key`, `anthropic_api_key`, …) via `!secret` only — kein Auto-Gen (Operator muss liefern)
- Postgres-Tuning: `shared_buffers=64MB`, `max_connections=20`, `log_min_duration_statement=1000` als Default;
  `effective_cache_size=256MB` + `work_mem=4MB` hardcoded; operator-override via Options + `pg_reload_conf` für
  SIGHUP-reloadbare Settings; `max_connections` benötigt Restart (in DOCS.md dokumentiert)
- `models: []` Schema mit `name` (LiteLLM-Pfad-Syntax erlaubt `/`), `provider` (Liste 6 hartkodiert + `str?`-Fallback),
  `api_base?`, `api_key?` (per-model-override), `model_name?` (Upstream-Alias), `litellm_params?` (Pass-Through)
- `health_check: { endpoint: http://localhost:4000/health/liveliness, interval: 30, timeout: 5 }`
- `map: [{ type: addon_config, ... }, { type: backup:rw, ... }]` — `/data/postgresql`, `/data/.litellm_*_key`,
  `/data/litellm_config.yaml` in HA-Backup eingeschlossen
- Auto-Update via `.upstream.yaml` (`BerriAI/litellm`, `version_pattern: sync`) → täglich 06:00 UTC
- LAN-Primary (direct Port 4000) + Ingress (Swagger UI HTML only — kein WebSocket-Streaming)
- DOCS.md mit Operator-Runbook (HA-Conversation-Konfiguration, Master-Key-Retrieval, Postgres-Reset, Troubleshooting)
- README.md + Root-README-Eintrag mit Shield-Badges (3-File-Versionierung aligned)
- Verifier-Skripte: `verify-litellm-scaffold.sh`, `verify-litellm-no-secret-leak.sh`, `verify-litellm-postgres-reset.sh`
- Spike-Skript: `spike-litellm-secret-schema.sh` (empirische Validierung `password?` + `!secret`-Interaktion)

**Was diese Phase NICHT ist:** Multi-Arch-Builds (PROJECT.md Out-of-Scope — beide Hosts x86_64), Cloudflare-Fronted
(`litellm.akentner.de` — explizit out-of-scope per User-Decision 2026-09-19), SQLite-Fallback, OAuth/PKCE-Flow,
Web-basiertes Admin-UI (LiteLLM-Swagger-UI reicht), HA-WebSocket-Custom-Integration (LiteLLM ist passiver
API-Server — kein MQTT-Discovery nötig), Splitting in `litellm` + `litellm-postgres`-Geschwister-Add-ons.

</domain>

<decisions>

## Implementation Decisions

### Image Build

- **D-01:** Multi-Stage-Dockerfile: Stage 1 `python:3.13-slim-bookworm AS litellm-builder` macht `pip wheel`
  (kein HA-Base-Image nötig — Builder-Stage wird nicht ausgeliefert; authentik-Präzedenz mit `ghcr.io/goauthentik/server`).
  Stage 2 `FROM ${BUILD_FROM}` mit `BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:trixie` (HA-Base, debian-Familie).
  — **Reversibility:** one-way — Image-Switch nach Release wäre breaking für HA-Store-Cache.
- **D-02:** `ARG BUILD_FROM`-Default im Dockerfile MUSS mit `build.yaml` übereinstimmen (Audit-Fix B1).
  `ghcr.io/home-assistant/amd64-base-debian:trixie`. Default-ARG-Wert ist nur Fallback für `docker build` ohne
  `--build-arg`; `make build-addon` und `build.yml` setzen den Wert korrekt.
- **D-03:** Stage 2 installiert `postgresql` + `postgresql-client` + `curl` + `jq` + `bash` + `libssl3` + `libffi8`
  via `apt-get install -y --no-install-recommends` (authentik-Pattern Zeile 15-25).
- **D-04:** Stage 2 kopiert Wheels von Stage 1 und installiert via
  `pip install --no-cache-dir --no-index --find-links=/wheels "litellm[proxy]==${LITELLM_VERSION}"`
  (Audit-Fix M2: `--no-cache-dir` für hadolint DL3042).
- **D-05:** Stage 2 beginnt mit `WORKDIR /` (Audit-Fix M1: hadolint DL3045).
- **D-06:** Vollständiger OCI-Label-Block am Ende (Audit-Fix B4):
  `io.hass.name`, `io.hass.arch`, `io.hass.type=addon`, `io.hass.version`, `maintainer`,
  `org.opencontainers.image.{title,description,vendor,authors,licenses,url,source,documentation,created,revision,version}`.
- **D-07:** Build-Args in `build.yaml`:
  ```yaml
  build_from:
    amd64: "ghcr.io/home-assistant/amd64-base-debian:trixie"
  args:
    VERSION: "0.1.0"
    LITELLM_VERSION: "1.40.0"
  ```
  Zwei Versionen bewusst — `VERSION` ist die Add-on-Versions-Pinnummer (3-File-Versionierung), `LITELLM_VERSION`
  ist die Upstream-LiteLLM-Version für pip-pin.
- **D-08:** Subpatch `-N` in `config.yaml` deckt Add-on-only-Änderungen (Dockerfile, run.sh, Schema) ab;
  SemVer `X.Y.Z`-Bump aligniert mit LiteLLM-Upstream-Release via `.upstream.yaml` (siehe D-22).

### run.sh (Bash-Sequential mit Signal-Trap)

- **D-09:** Shebang `#!/usr/bin/with-contenv bashio` mit `# shellcheck shell=bash` (authentik-Präzedenz).
  `set -e`. Variable-Export-Pattern: assign first, then `export` (CONVENTIONS.md Zeile 80-88).
- **D-10:** Signal-Trap SIGTERM (30s Drain) + SIGHUP (log-reopen) am Anfang von run.sh (Audit-Fix B5,
  authentik/iac-runner-Präzedenz).
- **D-11:** Master-Key-Lifecycle: `bashio::config 'master_key'` → wenn leer, `/data/.litellm_master_key` lesen →
  wenn immer noch leer, `bashio::log.notice "Generating master_key — copy from this log to secrets.yaml"`
  + `openssl rand -hex 32` generieren + `sk-` Prefix + persistieren in `/data/.litellm_master_key` chmod 600 +
  `export LITELLM_MASTER_KEY="${MASTER_KEY}"` (Audit: log-once-Muster, authentik-Präzedenz für `.pg_password`).
- **D-12:** Salt-Key vollständig analog zu Master-Key mit `/data/.litellm_salt_key` (Audit-Fix H2 — Design-Kommentar
  "analogous for salt_key" reicht nicht).
- **D-13:** Postgres-Setup: `find /usr/lib/postgresql/*/bin` zur Versions-Detektion, `initdb` nur wenn
  `/data/postgresql/PG_VERSION` fehlt, `pg_hba.conf`-Eintrag `host litellm litellm 127.0.0.1/32 md5`,
  `pg_ctl start -o '-h 127.0.0.1' -l /data/postgresql.log`, `until pg_isready -h 127.0.0.1` (authentik-Pattern).
- **D-14:** Postgres-User/DB-Create nur wenn `pg_roles WHERE rolname='litellm'` nichts liefert — idempotent
  über Restarts. Passwort aus `/data/.pg_password` (chmod 600, `tr -dc 'A-Za-z0-9'` head 40).
- **D-15:** Postgres-Tuning-Conf `/data/postgresql/litellm-tuning.conf` mit operator-überschreibbaren Settings
  (`shared_buffers`, `log_min_duration_statement`; `max_connections` benötigt Restart → DOCS.md dokumentiert).
  Hardcoded via `include_if_exists`: `effective_cache_size=256MB`, `work_mem=4MB`.
- **D-16:** `pg_ctl reload` nach tuning.conf-Schreiben — SIGHUP-reloadable Settings greifen sofort.
- **D-17:** LiteLLM-Config-Synthese via Python-Helper `litellm/generate_config.py` (Audit-Fix H3, phone-logger-
  Präzedenz für `generate_config.py`). Liest `/data/options.json`, transformiert HA-nested-dict-Schema → LiteLLM-YAML,
  schreibt `/data/litellm_config.yaml`. Python ist bereits im LiteLLM-Wheelhouse vorhanden — keine zusätzliche
  apt-Abhängigkeit.
- **D-18:** LiteLLM-Start: `export DATABASE_URL="postgresql://litellm:${PG_PASS}@127.0.0.1:5432/litellm"` +
  `exec litellm --config /data/litellm_config.yaml`. `exec` macht LiteLLM zu PID1.
- **D-19:** Log-Level-Mapping: `bashio::log_level` → `LITELLM_LOG` (`debug`→`DEBUG`, `info`→`INFO`,
  `warning`→`WARNING`, `error`→`ERROR`); `export LITELLM_LOG="${LOG_LEVEL^^}"` (Audit-Fix H1).

### config.yaml Schema

- **D-20:** Pflicht-Felder laut `internal/validate-addon-config.py` Zeile 22:
  `name`, `version`, `slug`, `description`, `arch`, `startup`, `boot`. Plus `init: false`, `arch: [amd64]`,
  `startup: application`, `boot: manual`, `host_network: false`.
- **D-21:** `ingress: true` + `ingress_port: 4000` + `ports: { 4000/tcp: 4000 }` + `ports_description`
  (LAN-Primary + Ingress-Dual).
- **D-22:** `image: "ghcr.io/akentner/homeassistant-addons/{arch}-litellm"` (Audit-Fix M5 — 7 von 9 Add-ons
  haben `image:`; konsistent mit gatus/meridian-Präzedenz; `build.yml` überschreibt das beim Build, aber
  explizit setzen ist robuster).
- **D-23:** `health_check: { endpoint: http://localhost:4000/health/liveliness, interval: 30, timeout: 5 }`
  (Audit-Fix H5 — HA Supervisor pollt Add-on-Health; ohne Block zeigt HA "started" auch bei hängendem Prozess).
- **D-24:** `map: [{ type: addon_config, read_only: false, path: /addon_config }, { type: backup, read_only: false }]`
  (Audit-Fix H6 — Backup-Integration für `/data/postgresql`, Master-/Salt-Keys, LiteLLM-Config; `map: backup`
  deckt das gesamte `/data`).
- **D-25:** Options-Block:
  - `log_level: "info"` mit `schema: list(debug|info|warning|error)?`
  - `master_key: !secret litellm_master_key` mit `schema: password?`
  - `salt_key: !secret litellm_salt_key` mit `schema: password?`
  - `providers: { openai_api_key: !secret openai_api_key, anthropic_api_key: !secret anthropic_api_key,
    google_api_key: !secret google_api_key, azure_api_key: !secret azure_api_key }` mit
    `schema: password?` je Provider
  - `models: []` Default mit Schema-Items (siehe D-26)
  - `postgres: { shared_buffers: "64MB", max_connections: 20, log_min_duration_statement: 1000 }` mit
    `schema: str?/int(5,200)?/int(0,60000)?`
- **D-26:** `models`-Schema-Items (Audit-Fix B3 — Slash erlauben für LiteLLM-Pfad-Syntax):
  ```yaml
  models:
    - name: "match(^[a-zA-Z0-9._:/+-]{1,256}$)"   # erlaubt bedrock/anthropic.claude-…
      provider: "str?"                            # frei statt hartkodiert auf 6 (Audit-Fix M4)
      api_base: "url?"
      api_key: "password?"                        # per-model-override des Provider-Keys
      model_name: "str?"                          # Upstream-Alias
      litellm_params: "str?"                      # Pass-Through für rpm/tpm/etc.
  ```
- **D-27:** HA-Conversation-Integration in HA-Core `configuration.yaml`:
  ```yaml
  openai_conversation:
    api_base: !secret litellm_api_base        # http://litellm:4000/v1 (HA-Supervisor-DNS) oder LAN-IP
    api_key: !secret litellm_master_key
  ```
  Der interne DNS-Hostname `litellm:4000` ist HA-OS-versionsspezifisch (Audit-Open-Question Q2) — DOCS.md
  dokumentiert beide URLs (HA-Supervisor-DNS und LAN/Tailscale-IP).

### Auto-Update

- **D-28:** `.upstream.yaml` (gatus-Präzedenz, `version_pattern: sync`):
  ```yaml
  upstream:
    repository: "BerriAI/litellm"
    version_pattern: "v*"
    version_strip: "^v"

  addon:
    version_pattern: "sync"
  ```
- **D-29:** Auto-Update-Workflow `.github/workflows/auto-update.yml` ist bereits implementiert
  (täglich 06:00 UTC) und deckt `.upstream.yaml` mit `sync` automatisch ab. **Kein neuer Workflow nötig**
  (Audit-Open-Question Q1 gelöst: unified `.github/workflows/build.yml` auto-discovered Add-ons bereits).
- **D-30:** Beim Auto-Update-Bump werden `config.yaml` (`X.Y.Z-0`), `build.yaml` (`VERSION: X.Y.Z`,
  `LITELLM_VERSION: X.Y.Z`) und `README.md` (`vX.Y.Z`) synchronisiert. `LITELLM_VERSION` muss manuell
  mit `VERSION` identisch sein — entweder (a) `update-version.py` um generische `secondary_args`-Logik
  erweitern oder (b) `auto-update.yml` post-proc. **Audit-B2 Fix:** Option (b) — `auto-update.yml` setzt
  `LITELLM_VERSION` nach `update-version.py` auf den neuen `VERSION`-Wert (sed-Replacement). Vermeidet
  Redundanz im `update-version.py`-Code.
- **D-31:** `make release ADDON=litellm VERSION=X.Y.Z` ist der manuelle Override-Pfad (Audit-Fix M6) und
  wird in DOCS.md dokumentiert.

### Verifier und Spike-Skripte

- **D-32:** `internal/verify-litellm-scaffold.sh` — baut Image, prüft Image-Größe ≤ 500 MiB, OCI-Labels
  vorhanden, `/health/liveliness` antwortet 200 nach Container-Start.
- **D-33:** `internal/verify-litellm-no-secret-leak.sh` — Master-Key-Plaintext erscheint genau einmal im
  Log, kein `LITELLM_MASTER_KEY`/`LITELLM_SALT_KEY`/Provider-Key-Plaintext in `docker logs`, keine
  `password`-Substrings in JSON-Log-Records.
- **D-34:** `internal/verify-litellm-postgres-reset.sh` — Postgres-Reset-Prozedur aus DOCS.md funktioniert
  end-to-end: Stop → `/data/postgresql` löschen → Start → DB neu initialisiert + User/DB angelegt.
- **D-35:** `internal/spike-litellm-secret-schema.sh` (Audit-Fix H4) — empirische Validierung der
  `password?`-Schema + `!secret`-Default-Interaktion auf einem Test-Add-on vor LITELLM-04-Ausführung.
  Ergebnis dokumentiert in DOCS.md (Master-Key-Sektion).

### Out-of-Scope-Bestätigungen (aus User-Diskussion + PROJECT.md)

- Multi-Arch-Builds (aarch64, armv7) — `arch: [amd64]` only; beide Hosts x86_64
- Cloudflare-Fronted `litellm.akentner.de` — LAN-Primary, kein Public-Surface nötig (User-Decision 2026-09-19)
- Splitting in `litellm` + `litellm-postgres` — Single-Image ist explizite User-Entscheidung
- HA-Ingress-WebSocket-Streaming — Direct-Port handled Streaming; Ingress nur für Swagger-UI-HTML
- HA-WebSocket-Custom-Integration — `homeassistant_api: true` weggelassen; LiteLLM ist passiver API-Server
- SQLite-Fallback — PostgreSQL ist mandatory
- OAuth/PKCE-Flow für HA-Auth — Master-Key-Bearer reicht für LAN
- Web-Admin-UI — LiteLLM-Swagger-UI ist sufficient
- `prometheus_multiproc_dir` — nur relevant bei `uvicorn --workers > 1`; Single-Worker, daher nicht nötig
  (Audit-Fix L2)

### the agent's Discretion

- Genaue `litellm/generate_config.py`-Logik (Python-Helper, phone-logger-Präzedenz) — welche Felder transformiert
  werden, wie `models: []` in LiteLLM-YAML konvertiert wird
- Welche `LITELLM_*`-Env-Vars zusätzlich zu `LITELLM_MASTER_KEY`/`LITELLM_SALT_KEY`/`DATABASE_URL`/`LITELLM_LOG`
  gesetzt werden (z.B. `LITELLM_PROXY_BATCH_TIMEOUT`, `LITELLM_PROXY_MAX_REQUEST_SIZE`)
- `panel_icon` + `panel_title` (Audit-Fix L1 — Vorschlag: `mdi:brain` + `LiteLLM`)
- Exakte Verifier-Bash-Struktur (welche `docker run`-Flags, welche Assertions)
- Ob `/data/.pg_password` und Master/Salt-Key-Files zusätzlich zu `map: backup` in eine separate `secrets:`
  Mount verschoben werden sollen (Trade-off: Komplexität vs. Defense-in-Depth)

### Folded Todos

Keine — `cross_reference_todos` lieferte 0 Matches für Phase 20.

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase-Boundary + Decisions (HIGH confidence)

- `.planning/phases/20-litellm-addon/PLAN.md` — User-erstellter Design-Doc mit 10 must_haves + 10 requirements;
  Quelle der meisten Design-Entscheidungen. **Wichtig:** Die hier in CONTEXT.md dokumentierten Decisions (D-01..D-35)
  sind Audit-Korrekturen des Design-Docs; das PLAN.md bleibt als historische Quelle.
- `.planning/ROADMAP.md` §"Phases" — Phase 20 ist Post-v1.4; keine Roadmap-Section vorhanden. Phase gehört
  zu einem neuen Milestone (v1.5 litellm-addon, nicht im ROADMAP erfasst).

### Add-on-Manifest-Anforderungen (HIGH confidence)

- `internal/validate-addon-config.py` Zeile 9-22 — `VALID_ARCH`, `VALID_STARTUP`, `VALID_BOOT`, `VALID_MAP_TYPES`,
  `REQUIRED_FIELDS`. Pflicht-Felder für jedes Add-on: `name`, `version`, `slug`, `description`, `arch`,
  `startup`, `boot`. `map.type` muss in `VALID_MAP_TYPES` sein (enthält `backup`).
- `.planning/codebase/CONVENTIONS.md` Zeile 144-153 — 3-File-Versioning: `config.yaml` (`X.Y.Z-N`),
  `build.yaml` (`X.Y.Z`), `README.md` (`vX.Y.Z`).
- `.planning/codebase/CONVENTIONS.md` Zeile 158-170 — Datei-Naming: Add-on-spezifisch (kebab-case + `slug`),
  Python `snake_case`, Shell `run.sh` (fixed).
- `.planning/codebase/CONVENTIONS.md` Zeile 174-191 — Dockerfile-Konventionen: HA-Base-Images, OCI-Label-Block,
  Upstream-Download-Pattern.

### 4-File-Pattern + Upstream-Auto-Update (HIGH confidence)

- `authentik/{config.yaml, Dockerfile, run.sh, .upstream.yaml, build.yaml, README.md}` — Multi-Service-in-One-
  Container-Präzedenz (PostgreSQL + Valkey + Authentik in einem Image). Konkret: `init: false`, `host_network: false`,
  `arch: [amd64]`, bash-sequential start, postgres `pg_ctl` + `pg_isready`, persistente Secrets in `/data/.<keyfile>`.
- `gatus/{config.yaml, .upstream.yaml}` — Upstream-Tracking mit `version_pattern: sync`, Ingress-Pattern
  (`panel_icon`, `panel_title`).
- `iac-runner/{config.yaml, Dockerfile, build.yaml}` — `host_network: true`, `homeassistant_api: true`,
  `services: ["mqtt:need"]` (für Phase 18); Signal-Trap (SIGTERM/SIGHUP).

### Versionierung + Auto-Update-Mechanik (HIGH confidence)

- `.github/workflows/auto-update.yml` — täglich 06:00 UTC, serialisiert via `concurrency.group: addon-version-bump`,
  ruft `internal/update-version.py` mit `--no-tag`, prependet Release-Notes zu `CHANGELOG.md`, dispatched
  `.github/workflows/build.yml` per `workflow_dispatch`.
- `.github/workflows/build.yml` — unified Builder, auto-discovers Add-ons via `config.yaml`+`build.yaml`+
  `Dockerfile`-Triple, nutzt `_build-template.yml`.
- `.github/workflows/_build-template.yml` Zeile 72-108 — resolved `VERSION` aus `build.yaml args.VERSION` und
  `CONFIG_VERSION` aus `config.yaml version`; image tag = `CONFIG_VERSION`.
- `.github/workflows/verify-image-availability.yml` — vier Mal täglich anonymous pull-Probe gegen ghcr.io.
- `internal/check-version-tags.sh` Zeile 92-94 — `LOCAL_BUILD_ADDONS=("iac-runner")` allowlist. `litellm` ist
  NICHT auf der Liste (wird via ghcr.io publisht).
- `internal/validate-versions.sh` — pre-commit-Hook für 3-File-Version-Sync.
- `internal/update-version.py` — kanonischer Pfad für Versions-Bumps (`make update-version`).

### Validierungs- und Build-Mechanik (HIGH confidence)

- `internal/validate-dockerfile-args.sh` — prüft ARG-before-FROM-Scope in allen Dockerfiles. `litellm/Dockerfile`
  MUSS die Regel erfüllen (alle in FROM referenzierten ARGs vor dem ersten FROM deklarieren).
- `internal/validate-addon-config.py` — pre-commit-Hook für config.yaml-Schema.
- `.pre-commit-config.yaml` Zeile 113-117 — `validate-dockerfile-args` Hook ist scoped auf
  `phone-logger|meridian|iac-runner`. Für `litellm` muss der Scope erweitert werden, wenn `validate-dockerfile-args.sh`
  auf das litellm-Dockerfile angewendet werden soll (Default-Discovery via `find . -maxdepth 2 -name Dockerfile`
  deckt `litellm/` bereits ab).
- `.pre-commit-config.yaml` Zeile 53-69 — hadolint mit `--ignore DL3008,DL3018,DL3059,DL4006,DL3016`.
  `make docker-build-check` hat STRENGERE Regeln (DL3006 zusätzlich).
- `.pre-commit-config.yaml` Zeile 87-90 — gitleaks pre-commit-Hook (kein Geheimnis-Leak in Staged-Diff).

### Established Patterns (HIGH confidence)

- **Multi-Service-in-One-Container via bash-sequential** (authentik/run.sh Zeile 1-119) — postgres `pg_ctl` start
  → `pg_isready` wait → final service via `exec runuser -u <user> -- <binary>` (PID1).
- **Konfigurations-Synthese via Python-Helper** (phone-logger/generate_config.py) — transformiert
  `/data/options.json` (HA-Schema) in App-native YAML.
- **Persistentes Secret in `/data/.<keyfile>`** (authentik: `.pg_password`, `.secret_key`) — generiert mit
  `tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 40`, chmod 600, idempotent über Restarts.
- **Signal-Trap** (authentik, iac-runner/cmd/runner/signals.go, terraform-bridge/cmd/bridge/signals.go) —
  SIGTERM 30s drain + SIGHUP log-reopen.
- **`with-contenv bashio`-Shebang** (authentik, iac-runner, terraform-bridge, coding-assistants) — für
  Add-ons mit bashio-Konfiguration.
- **Variable-Export-Pattern** (CONVENTIONS.md Zeile 80-88) — assign first, then `export`.
- **`/data`-Default-Volume** (authentik, iac-runner) — HA-Supervisor mountet `/data` automatisch;
  `map: addon_config` ist optional für `/addon_config`-Sharing.
- **OCI-Label-Block** (authentik/Dockerfile Zeile 78-103) — alle HA-Add-ons haben den vollständigen Block am
  Dockerfile-Ende.

### Externe Referenzen (MEDIUM confidence — müssen bei Implementierung verifiziert werden)

- Home Assistant Add-on Schema — https://developers.home-assistant.io/docs/add-ons/configuration
- LiteLLM Configuration Reference — https://docs.litellm.ai/docs/proxy/configs
- LiteLLM Environment Variables — https://docs.litellm.ai/docs/proxy/envs
- LiteLLM Health endpoints — `/health/liveliness`, `/health/readiness` (LiteLLM 1.39+)
- Debian Trixie PostgreSQL version — prüfen ob PG 15 (default) oder PG 16+ verfügbar (Audit-Open-Question Q7).
  Falls PG 16+ nötig: PGDG apt repo (`apt.postgresql.org`) als Fallback.

</canonical_refs>

<code_context>

## Existing Code Insights

### Reusable Assets

- **`authentik/run.sh`** (119 Zeilen) — Multi-Service-in-One-Container Bash-Template. Konkret für litellm
  wiederverwendbar: `pg_ctl start -o '-h 127.0.0.1'`, `pg_isready -h 127.0.0.1`, User/DB-Create idempotent via
  `pg_roles WHERE rolname=...`, `pg_ctl reload`, persistente Secrets in `/data/.<keyfile>`.
- **`authentik/Dockerfile`** (77 + LABEL-Block Zeilen 78-103) — Multi-Stage-Pattern mit `ARG BUILD_FROM` BEFORE
  first FROM, `ARG VERSION` in jeder Stage re-deklariert, apt-get-Pattern, OCI-Label-Block.
- **`authentik/config.yaml`** — Multi-Service-Manifest-Shape: `init: false`, `host_network: false`,
  `arch: [amd64]`, `ports: { 9000/tcp: 9000 }`, `ports_description`, `map: [{ type: addon_config, ... }]`.
- **`gatus/.upstream.yaml`** — Upstream-Tracking-Template: `repository`, `version_pattern: v*`,
  `version_strip: ^v`, `addon.version_pattern: sync`.
- **`gatus/config.yaml`** — Ingress-Manifest-Shape: `panel_icon`, `panel_title`, `ingress: true`, `ingress_port`,
  `map: addon_config`.
- **`iac-runner/config.yaml`** — `host_network: true`, `homeassistant_api: true`, `services: ["mqtt:need"]`,
  `ports: { 8125/tcp: 8125 }`, `ports_description` (für Tailscale-Bind-Gate-Präzedenz — irrelevant für litellm).
- **`phone-logger/generate_config.py`** — Konfigurations-Transformations-Pattern: liest `/data/options.json`,
  strukturelle Transformation, schreibt App-native YAML.
- **`gatus/Dockerfile`** Zeile 55-69 — Upstream-Binary-Download-Pattern mit `alpine:3.20 AS gatus-cli-source`
  als Builder-Stage (auch nicht-HA-Base akzeptabel).
- **HA-Base-Images** (`ghcr.io/home-assistant/amd64-base-debian:trixie`) — von authentik erfolgreich verwendet
  für Multi-Service-Container; konsistenter Präzedenz-Pfad für litellm.

### Established Patterns

- **4-File-Pattern + `.upstream.yaml`** — `config.yaml`, `build.yaml`, `Dockerfile`, `run.sh`, `README.md`,
  `DOCS.md`, `.upstream.yaml` in jedem Add-on-Verzeichnis.
- **3-File-Versioning** — pre-commit-Hook `validate-versions.sh` enforced; `make update-version` ist der
  einzige kanonische Pfad.
- **`build.yaml` `args.VERSION`** — wird sowohl in `Dockerfile` (Build-Arg) als auch in `update-version.py`
  (sync mit `config.yaml` + `README.md`) verwendet.
- **`map: addon_config` mountet `/addon_config`** — vom Operator beschreibbares Konfigurations-Verzeichnis;
  `/data` ist HA-Default und benötigt kein `map`-Eintrag.
- **`map: backup` deckt `/data` automatisch** — HA Supervisor sichert alle `/data`-Inhalte.
- **HA-Supervisor-DNS** — Add-ons erreichen einander via `<slug>:port` (z.B. `http://litellm:4000/v1`).
  Empirische Verifikation erforderlich für HA-OS-Version auf `haos-op3050-1`.
- **bashio-Konfiguration** — `bashio::config 'key'`, `bashio::config 'key' 'default'`,
  `bashio::config.true 'key'`, `bashio::log.{info,notice,warning,error,fatal}`, `bashio::var.json`.

### Integration Points

- **HA Conversation Integration** (`openai_conversation:` in HA-Core `configuration.yaml`) — neuer Consumer;
  nutzt `api_base: !secret litellm_api_base` + `api_key: !secret litellm_master_key`.
- **Tailscale** — falls `pve`-Ollama als Model-Provider genutzt wird, muss Tailscale auf HA-OS-Host erreichbar
  sein (Audit-Open-Question Q3 — Operator-Voraussetzung, in DOCS.md dokumentieren).
- **HA Backup Integration** — `map: backup:rw` aktiviert automatischen Backup von `/data`-Inhalten in
  HA-Snapshots.
- **Auto-Update-Workflow** — `.upstream.yaml` triggert täglich `.github/workflows/auto-update.yml`; dieses
  ruft `internal/update-version.py` + prependet CHANGELOG.md + dispatched `build.yml`.
- **`verify-image-availability.yml`** — vier Mal täglich anonymous pull-Probe; fängt stale Images ab.

</code_context>

<specifics>

## Specific Ideas

- **LiteLLM-Pfad-Syntax für Model-Namen** — `bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0`,
  `openai/gpt-4o`, `azure/gpt-4` etc. Der HA-Schema-Regex MUSS `/` und `:` erlauben (D-26). Ohne diese
  Erlaubnis funktionieren die meisten Cross-Provider-Routes nicht via HA-UI.
- **Auto-Update-Workflow-Post-Processing für `LITELLM_VERSION`** — D-30 verlangt, dass `auto-update.yml`
  nach `update-version.py` zusätzlich `LITELLM_VERSION` auf den neuen `VERSION`-Wert setzt (sed).
  Vermeidet Code-Änderung in `update-version.py` (welcher Single-Purpose bleiben soll).
- **Master-Key-One-Time-Log als UX-Kompromiss** — `bashio::log.notice` mit Plaintext-Key erleichtert
  Operator-Workflow (kopieren → in `secrets.yaml` einfügen → restart); Trade-off ist akzeptabel für
  LAN-Primary-Deployment (Audit-Open-Question Q9). Alternative File-Only wäre restriktiver aber
  umständlicher.
- **`models[].provider` als `str?`** statt hartkodierter Liste — flexibler für LiteLLM's breites
  Provider-Ökosystem; Validierung in `generate_config.py` statt im HA-Schema (Audit-Fix M4).
- **Postgres-Reset-Prozedur** — DOCS.md muss beschreiben: Add-on stoppen → `/data/postgresql` löschen →
  Add-on starten → `initdb` läuft neu → Master-Key bleibt unverändert (separate Datei). Spend-Logs und
  virtual keys gehen verloren (Acceptable; HA-Backup ermöglicht Restore).
- **Backup-Frequenz-Konfiguration** — `map: backup:rw` nutzt HA-Default-Backup-Schedule; keine
  zusätzliche Konfiguration im Add-on nötig.
- **Verifizierungs-Reihenfolge** — Verifier-Skripte (D-32, D-33, D-34) werden in der letzten Phase
  geschrieben (LITELLM-09 / Phase 20-E2E), nicht in den Scaffold-Plans. Spike-Skript (D-35) wird vor
  LITELLM-04 als Block auf den kritischen Pfad gesetzt.
- **Image-Size-Threshold** — `verify-litellm-scaffold.sh` prüft ≤ 500 MiB. authentik-Image ist ~1 GB
  (postgres + valkey + authentik); 500 MiB ist konservative Schätzung für postgres + liteLLM.

### Post-decision refinements worth noting

- **`postgres.log_min_duration_statement=1000`** filtert Queries >1s. Bei LiteLLM mit vielen kleinen
  Inserts (spend logs) kann das遮logging zu aggressiv sein — DOCS.md empfiehlt `0` (alle loggen) für
  Debugging.
- **Master-Key Rotation** — D-11/D-12 unterstützen KEINE Rotation (nur first-start-auto-gen). Rotation
  wäre ein eigenes Feature (POST /key/rotate Endpoint + Old-Key-Grace) — explizit out-of-scope für v1.5.
- **HA-Backup-Konflikt mit `map: backup`** — Postgres-Cluster kann bei laufendem Add-on inkonsistent
  gesichert werden. HA Supervisor macht keinen `pg_dump` — nur File-Level-Backup. Akzeptabel für
  Home-Use (Restore aus Backup = möglicher Konsistenz-Verlust, aber kein Datenverlust-Horror).

</specifics>

<deferred>

## Deferred Ideas

- **Master-Key Rotation Endpoint** (v1.6+) — `POST /key/rotate` mit 24h Grace analog zu terraform-bridge.
  Aktuell nur first-start-auto-gen.
- **Cloudflare-Fronted Public-Surface** (`litellm.akentner.de` + CF Tunnel + CF Access) — explizit
  out-of-scope per User-Decision 2026-09-19. Falls öffentliches Exposure später gewünscht: TLS-Termination
  + OAuth/PKCE-Flow erforderlich.
- **Multi-Arch-Builds** (aarch64, armv7) — PROJECT.md Out-of-Scope. Falls Raspberry-Pi-Hosts hinzukommen:
  builder-stage-Anpassung + arch-spezifische apt-Repos.
- **SQLite-Fallback** für Hosts ohne ausreichend Disk für PostgreSQL — würde doppelten Code-Pfad
  bedeuten (Schema-Migrationen, generate_config.py-Logik); Trade-off nicht wert.
- **OAuth/PKCE-Flow für HA-Auth** — würde die `master_key`-Bearer-Auth ersetzen; relevant nur bei
  Public-Surface.
- **Web-basiertes Admin-UI** — LiteLLM-Swagger-UI ist sufficient; Custom-Panel würde Phase-Scope
  sprengen.
- **HA-WebSocket-Custom-Integration** für LiteLLM-Status-Entities (z.B. `litellm.spend_today`) —
  erfordert Custom-Component in HA Core; nicht der Standard-Add-on-Pfad.
- **Per-Provider-Default-Models** — `models: []` ist leer; könnte mit sinnvollen Defaults
  (z.B. `[{"name": "gpt-4o-mini", "provider": "openai"}]`) vorbefüllt werden, falls `openai_api_key`
  gesetzt ist. Trade-off: User-Confusion vs. Out-of-Box-Funktion.
- **TLS-Termination innerhalb des Add-ons** — Reverse-Proxy (Caddy/Traefik) als separate Add-on-Lösung
  für Public-Surface; aktuell LAN-Primary mit Tailscale-Verschlüsselung.
- **Prisma-Migration-Step in run.sh** — falls LiteLLM-Updates manuelle Migration erfordern (Audit-Q5),
  könnte run.sh `prisma migrate deploy` vor `exec litellm` ausführen. Empirische Verifikation in
  Phase 20-E2E (LITELLM-09).

</deferred>

---

*Phase: 20-litellm-addon*
*Context gathered: 2026-09-19*
