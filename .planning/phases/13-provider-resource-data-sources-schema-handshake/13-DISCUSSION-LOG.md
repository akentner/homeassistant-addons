# Phase 13: Provider + Resource + Data Sources + Schema Handshake - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents. Decisions are captured in
> CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-04 **Phase:** 13-provider-resource-data-sources-schema-handshake **Milestone:** v1.3 opentofu-bridge
**Areas discussed:** hostname-Quelle, Adoption-aware Create, Diagnostic messages, DOCS.md Struktur

---

## hostname-Quelle

| Option               | Description                                                                                                                    | Selected |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------ | -------- |
| AddOnInfo erweitern  | contract.AddOnInfo bekommt `Hostname string` Feld (1 Zeile). Bridge-`/v1/addons/{slug}/info` reicht Supervisor-Wert 1:1 durch. | ✓        |
| Aus slug ableiten    | Provider leitet `hostname` aus slug ab (z.B. `addons-<slug>`). Keine Bridge-/Contract-Änderung.                                |          |
| Aus Schema entfernen | Provider-Schema lässt `hostname` weg. PROV-02 wird partiell geändert.                                                          |          |

**User's choice:** AddOnInfo erweitern **Notes:** Sauberster Match mit Supervisor-Wirklichkeit. PROV-02 behält
`hostname` als Computed-attribute.

### Follow-up: leerer hostname

| Option                  | Description                                                                                                           | Selected |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------- | -------- |
| Leerstring durchreichen | Wenn Supervisor leeres `hostname` zurückgibt, ist das Provider-Attribut auch leer. Konsistent mit Terraform/OpenTofu. | ✓        |
| Aus slug fallback       | Provider fällt im Read-Pfad auf slug zurück. Immer non-null.                                                          |          |
| Warning diagnostic      | Provider emittiert eine Warning beim Plan, wenn `hostname` leer ist.                                                  |          |

**User's choice:** Leerstring durchreichen

### Follow-up: weitere Supervisor-Felder

| Option                        | Description                                                                                                          | Selected |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------- | -------- |
| Nur hostname                  | Nur `hostname` ergänzen. Phase-13 bleibt fokussiert.                                                                 |          |
| hostname + ingress_url        | `hostname` + `ingress_url` (für Cloudflare-Tunnel).                                                                  |          |
| AddOnInfo: alles durchreichen | Alle fehlenden Supervisor-Felder (`hostname`, `dns`, `ingress_url`, `ingress_entry`, `webui_url`) einmalig ergänzen. | ✓        |

**User's choice:** AddOnInfo: alles durchreichen

### Follow-up: SchemaVersion-Bump

| Option             | Description                                                                                                                       | Selected |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------- | -------- |
| Kein Bump (1.0.0)  | Additive Änderung ohne Breaking Impact — kein Signal nötig. Provider-Configure-Log zeigt klarer, dass neue Felder verfügbar sind. | ✓        |
| MINOR-Bump (1.1.0) | Informativ: signalisiert additive Felder. Bridge-Build nötig.                                                                     |          |
| MAJOR-Bump (2.0.0) | Zu strikt für additive Änderung — würde alte Provider künstlich blockieren.                                                       |          |

**User's choice:** Kein Bump (1.0.0)

---

## Adoption-aware Create

| Option                    | Description                                                                       | Selected |
| ------------------------- | --------------------------------------------------------------------------------- | -------- |
| Nur POST install          | Provider ruft nur `POST /install`. Bridge handhabt 409 intern. Einfachster Code.  |          |
| GET info zuerst           | Provider ruft `GET info` zuerst. 200 → adoptieren; 404 → POST install. Race-frei. | ✓        |
| POST zuerst, GET-Fallback | Provider ruft `POST /install` zuerst. Bei 409 Fallback auf `GET info`.            |          |

**User's choice:** GET info zuerst

### Follow-up: start follow-up

| Option                | Description                                                                                                      | Selected |
| --------------------- | ---------------------------------------------------------------------------------------------------------------- | -------- |
| Immer wenn nötig      | Wenn `start = true` und `started = false`, rufe `POST /start`. Konsistent: User erwartet "apply → add-on läuft". | ✓        |
| Nur bei echtem Create | Start follow-up nur bei echtem Create; bei Adoption wird started übernommen.                                     |          |
| Kein follow-up        | Create endet nach POST install. User muss separat Update triggern.                                               |          |

**User's choice:** Immer wenn nötig

### Follow-up: Options-Mismatch

| Option         | Description                                                                                 | Selected |
| -------------- | ------------------------------------------------------------------------------------------- | -------- |
| Nur Create     | Adoption nur auf Slug + ggf. start. Options-Mismatch erfordert zweiten apply.               |          |
| Inline-Update  | Bei Adoption: wenn `options` ≠ existing, rufe `POST /options`. Konvergent auf ersten apply. | ✓        |
| Force recreate | Adoption mit Options-Mismatch → force recreate. Riskanter.                                  |          |

**User's choice:** Inline-Update

### Follow-up: Boot-Mismatch

| Option             | Description                                                                          | Selected |
| ------------------ | ------------------------------------------------------------------------------------ | -------- |
| boot inline update | Boot-Drift bei Adoption erkennen und `POST /options` mit `boot: <desired>` aufrufen. | ✓        |
| boot dokumentieren | Provider setzt boot nur beim ersten Create. DOCS.md verweist auf HA UI.              |          |
| Ignorieren         | Provider kümmert sich nicht um boot-Drift.                                           |          |

**User's choice:** boot inline update

### Follow-up: 423 locked Handling

| Option                                    | Description                                                | Selected |
| ----------------------------------------- | ---------------------------------------------------------- | -------- |
| terraform-plugin-framework-timeouts retry | Retry-Loop innerhalb des Timeouts. Standard-Pattern.       | ✓        |
| Kein Retry                                | Direkter Diagnostic; User macht `terraform apply` nochmal. |          |
| Custom Backoff                            | Exponential Backoff (1s, 2s, 4s, ... bis max 30s).         |          |

**User's choice:** terraform-plugin-framework-timeouts retry

---

## Diagnostic messages

| Option           | Description                                                                                                                         | Selected |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------- | -------- |
| Pro error_code   | Pro Bridge error_code ein expliziter Diagnostic-Text (z.B. `critical_addon_protected` → Handlungsanweisung). Klare Aktion pro Code. | ✓        |
| Generisch + Code | Generic-Template "Bridge returned <error_code>" + error_code im Attribute.                                                          |          |
| Hybrid           | Wichtige Codes explizit; Rest generisch.                                                                                            |          |

**User's choice:** Pro error_code

### Follow-up: Severity

| Option                   | Description                                                                         | Selected |
| ------------------------ | ----------------------------------------------------------------------------------- | -------- |
| Error + pwned = Warning  | Alle 4xx/5xx = Error; nur `pwned` aus ValidateOptions = Warning (PROV-06 explizit). | ✓        |
| Nach Code differenzieren | Transient (locked, install_timeout, upstream_error) = Warning; permanent = Error.   |          |
| Alles Error              | Maximale Striktness; User entscheidet via lifecycle.                                |          |

**User's choice:** Error + pwned = Warning

### Follow-up: Diagnostic URLs

| Option                | Description                                                                                      | Selected |
| --------------------- | ------------------------------------------------------------------------------------------------ | -------- |
| Troubleshooting-URL   | Jeder Diagnostic bekommt `DOCS.md#troubleshooting-<error_code>` URL angehängt. IDE-Klickbarkeit. | ✓        |
| error_code als Detail | Nur error_code als Diagnostic-Detail. Keine URL.                                                 |          |
| Beides                | error_code + URL.                                                                                |          |

**User's choice:** Troubleshooting-URL

### Follow-up: Request-ID Sichtbarkeit

| Option              | Description                                                                                               | Selected |
| ------------------- | --------------------------------------------------------------------------------------------------------- | -------- |
| request_id sichtbar | `request_id` aus Bridge-ErrorResponse in den Diagnostic aufnehmen. User kann in Bridge-Logs nachschlagen. | ✓        |
| request_id intern   | Nur in Provider-Logs.                                                                                     |          |
| Kein request_id     | Provider ignoriert.                                                                                       |          |

**User's choice:** request_id sichtbar

---

## DOCS.md Struktur

| Option                | Description                                                                                 | Selected |
| --------------------- | ------------------------------------------------------------------------------------------- | -------- |
| Provider-DOCS separat | `terraform-provider-homeassistant/DOCS.md` als eigene Datei. Konsistent mit Add-on-Pattern. | ✓        |
| In Bridge-DOCS        | Section "Provider Usage" in `terraform-bridge/DOCS.md`.                                     |          |
| Beides (verlinkt)     | Provider-DOCS primär; Bridge verlinkt drauf.                                                |          |

**User's choice:** Provider-DOCS separat

### Follow-up: DOCS-Sektionen

| Option                          | Description                                                                       | Selected |
| ------------------------------- | --------------------------------------------------------------------------------- | -------- |
| Provider + Resource + Data      | Provider-Konfiguration; Resource-Referenz; beide Data-Sources. Pflicht-Sektionen. |          |
| Plus Examples + prevent_destroy | Plus vollständiges Beispiel; prevent_destroy prominent.                           |          |
| Plus Troubleshooting            | Plus Troubleshooting-Sektion mit per-error_code Ankern.                           | ✓        |

**User's choice:** Plus Troubleshooting

### Follow-up: prevent_destroy Framing

| Option                | Description                                                                                               | Selected |
| --------------------- | --------------------------------------------------------------------------------------------------------- | -------- |
| Immer im Beispiel     | Jedes Resource-Beispiel hat `prevent_destroy = true`. Strikt.                                             |          |
| Featured + opt-out    | Featured "Recommended Safety Configuration"-Sektion.                                                      |          |
| Im Beispiel + Hinweis | Beispiel zeigt prevent_destroy; zusätzliche Notiz zum Auskommentieren + vorsichtigem `terraform destroy`. | ✓        |

**User's choice:** Im Beispiel + Hinweis

### Follow-up: Troubleshooting-Layout

| Option              | Description                                                                                               | Selected |
| ------------------- | --------------------------------------------------------------------------------------------------------- | -------- |
| Tabelle pro Code    | Pro error_code eine Tabelle mit Spalten: HTTP-Status, Bridge-Bedingung, Beispiel-Diagnostic, Remediation. | ✓        |
| Pro Code Subsection | H3-Subsection pro Code.                                                                                   |          |
| Fließtext + Tabelle | Fließtext-Erklärung + Code-Tabelle am Ende.                                                               |          |

**User's choice:** Tabelle pro Code

### Follow-up: Install-Anleitung

| Option               | Description                                                                        | Selected |
| -------------------- | ---------------------------------------------------------------------------------- | -------- |
| Vollständig in DOCS  | `make install-provider`, dev_overrides, `tofu init`, `tofu plan` — self-contained. | ✓        |
| Verweis auf Makefile | DOCS.md verweist; Makefile ist single source of truth.                             |          |
| Quickstart nur       | DOCS.md ist rein Usage; Installation in INSTALL.md/README.md.                      |          |

**User's choice:** Vollständig in DOCS

---

## the agent's Discretion

- Exact internal package layout inside `terraform-provider-homeassistant/`
- Exact shape of the Provider's `Client` struct (mirrors Bridge's `supervisor.Client` style)
- Whether `request_id` lives in `Detail` as raw text or as a separate framework field
- Exact wording per `error_code` Diagnostic text
- Whether Provider emits a single combined diagnostic per Bridge response or one per failed operation
- Whether `homeassistant_supervisor_info` data source exposes a `bridge_version` field (redundant with `/v1/version`)

## Deferred Ideas

- **`homeassistant_addon_repository` resource** (FEATURES.md OQ-1) — deferred to v1.4.
- **`pwned` field as Computed attribute** — currently PROV-06 surfaces as Warning only; attribute exposure is Phase 14+.
- **Provider-side `lifecycle.prevent_destroy` enforcement** — LIFE-02 leaves it opt-in; enforced behavior is a Phase 14+
  refinement if needed.
- **Provider-side `terraform state list`-style introspection over `GET /v1/state/index`** — STATE-02 makes the index
  available; no Provider CLI command consumes it yet.
- **CSRF / OPTIONS preflight on Bridge** (PITFALLS S-3) — deferred per Phase 12 CONTEXT §"Deferred Ideas".
- **`install_job_timeout_seconds` overrides per-add-on** — single global for Phase 12/13; per-slug overrides become real
  if slow add-ons emerge in Phase 14.

## Cross-Phase Coordination

- **Reuse from Phase 12:** `supervisor.Client` pattern, contract type conventions, slog key convention, error body shape
  with `error_code` / `request_id`. Provider mirrors these via the `replace` directive.
- **Reuse from Phase 11:** `contract.VersionHandshake` + `/v1/version` shape for Configure handshake;
  `contract.AddOnInfo` for Read path; `internal/version/version.go` for the schema-version policy.
- **Reuse from Phase 10:** Bearer-token-injecting Transport pattern (Bridge's `tokenInjectingTransport`); 401 body shape
  (`{"error_code": "unauthorized"}`); two-layer log masking.
- **Reuse from Phase 9:** `map: addon_config:rw` mount (state file persistence in HA backups); Provider's DOCS.md
  installation section references this so operators know `terraform.tfstate` is backed up.

## Open items for downstream agents

- Phase 13 **planner** must verify that the Provider's `create = 10m` timeout ≥ Bridge's `install_job_timeout_seconds`
  default of 300s (5min) so slow installs don't trip Provider-side before Bridge-side completes. If a real-world install
  exceeds 10min in Phase 14, the Provider default must increase or the user must override via
  `timeouts { create = ... }`.
- Phase 13 **planner** must ensure `bearer_token` Provider argument is marked `Sensitive: true` so it doesn't leak into
  state files or plan output (PITFALLS S-1 invariant).
- Phase 13 **planner** must verify that the data source `homeassistant_supervisor_info` returns enough fields to be
  useful in `lifecycle.precondition` blocks (PROV-12) — at minimum `bridge_version` and `supervisor_version` (already in
  `/v1/info` body via `contract.BridgeInfo`).
- Phase 13 **executor** must commit `contract.AddOnInfo` struct extension (D-01) atomically across the
  `terraform-bridge/contract/types.go` and `terraform-provider-homeassistant/internal/client/` decoder sites — a single
  atomic commit that exercises `go build ./...` from BOTH module roots confirms the contract is still in sync.
- Phase 14 **planner** (next phase) will reference 13-CONTEXT.md §"the agent's Discretion" + §"Deferred Ideas" for
  real-HA verification scope and to know that `homeassistant_addon_repository` is out of scope.
