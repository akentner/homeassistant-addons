# Phase 14: Real-HA End-to-End Verification + Operator Documentation - Context

**Gathered:** 2026-09-05 **Status:** Ready for planning **Milestone:** v1.3 opentofu-bridge

<domain>

## Phase Boundary

Exercise the Bridge + Provider stack end-to-end against the live Home Assistant host (`ha-nextgen` ≡ `haos-op3050-1`,
192.168.178.3 on LAN) using a purpose-built test add-on, then expand `terraform-bridge/README.md` and `DOCS.md` to a
full operator reference built from observed behavior — including a per-`error_code` remediation table populated by
deliberate failure scenarios.

Specifically this phase delivers:

- A new `tools/test-addon/` directory with a minimal HA add-on (config.yaml, build.yaml, Dockerfile, run.sh) that the
  Provider can install / configure / start / stop / uninstall repeatedly without touching any real add-on on the host.
- A new `internal/verify-bridge-e2e/` directory with one shell scenario per `error_code` (mirroring
  `internal/verify-bridge-no-token-leak.sh` style); each scenario provokes the error against the live Bridge, captures
  the resulting Provider diagnostic verbatim to `terraform-bridge/internal/testdata/diagnostics/<error_code>.txt`, and
  exits non-zero on a diagnostic mismatch.
- Empirical verification of the five success criteria from `ROADMAP.md` Phase 14:
  1. `make install-provider` end-to-end works against the live Bridge
  2. Drift behavior observed (`options` change → Update; `state` refresh → no-op via `UseStateForUnknown()`; 404 →
     recreate plan)
  3. Idempotency proven (five consecutive `tofu apply` → "No changes" after first)
  4. Every Bridge `error_code` produces the documented Provider diagnostic
  5. `terraform-bridge/README.md` (new 1-page install + token walkthrough) and `terraform-bridge/DOCS.md` (expanded full
     operator reference) are complete with three+ observed troubleshooting issues.
- `terraform-provider-homeassistant/DOCS.md` receives minor updates only — the file is already 618 lines and the
  Phase-13 troubleshooting table is the canonical source. Phase 14's contribution is to flag any empirically observed
  behavior that diverges from the table.

**What this phase is NOT:** TLS termination (Phase 2+), Provider Actions (`start`/`stop`/`restart` as a separate
resource — v1.4 deferred per REQUIREMENTS.md), `homeassistant_addon_repository` resource (v1.4 deferred), multi-arch
builds, CI workflow changes (Phase 15 owns those — TOFU-04). Phase 14 exercises what exists; it does not add new
capabilities.

</domain>

<decisions>

## Implementation Decisions

### Live host identity (Area 1)

- **D-01:** `ha-nextgen` and `haos-op3050-1` (192.168.178.3) are the same physical host — `ha-nextgen` is the Tailscale
  hostname, `haos-op3050-1` is the LAN identity. Phase 14 uses whichever hostname is convenient per call: Tailscale
  hostname (`ha-nextgen.akentner.ts.net:8124` style) when reaching from outside the LAN, LAN IP when the call originates
  from inside the household network. **No separate "production" host** — the LAN/Tailscale dual identity is the same
  box. — **Reversibility:** `reversible` — hostname choice per call doesn't change any contract.
- **D-02:** Per AGENTS.md "Live Systems — No Unsolicited Restarts / Service Disruption" rule, every destructive
  operation against the host requires explicit per-call user authorization. Phase 14's verify scripts therefore **never
  auto-restart the Bridge** — they exercise the Bridge as a running service via the HTTP API only. Bridge restarts (for
  image redeploys during iteration) are operator actions between scenarios, not script actions.

### Test add-on design (Area 2)

- **D-03:** A new directory `tools/test-addon/` (sibling of `tools/test-bridge-fixture/`) hosts the minimal HA add-on
  used for the install / configure / start / stop / uninstall exercises. Files: `config.yaml`, `build.yaml`,
  `Dockerfile`, `run.sh`, plus a `README.md` explaining its purpose. The add-on is intentionally trivial — a
  `ghcr.io/home-assistant/amd64-base:3.24` image with a no-op `run.sh` that just sleeps so Supervisor sees the add-on as
  "running" but the container does nothing observable. The add-on's schema exposes one or two string options
  (`log_level`, `dummy_setting`) so Update / pwned-warning scenarios have something to vary.
- **D-04:** The test add-on is published to the host's local add-on store via `ha addons reload` after each rebuild. No
  GitHub release, no custom-repository URL — `tools/test-addon/build.yaml` is consumed by HA's local-build pipeline via
  the same path every add-on in this repo follows. This keeps Phase 14 hermetic to the repo; no external dependency. —
  **Reversibility:** `reversible` — directory rename or removal.
- **D-05:** The test add-on's slug is `local_test-addon` (HA's convention for locally-built add-ons prefixed with
  `local_`). This avoids collision with any real add-on on the host and signals "this is the test target" to anyone
  looking at the host's add-on list.

### Verify-script structure (Area 3)

- **D-06:** Phase 14 ships `internal/verify-bridge-e2e/` with one shell scenario per `error_code` (mirroring
  `internal/verify-bridge-no-token-leak.sh`'s style and structure). Each scenario is named for its `error_code`:
  `01-unauthorized.sh`, `02-not-found.sh`, `03-critical-addon-protected.sh`, `04-prevented-destroy.sh`,
  `05-already-installed.sh`, `06-locked.sh`, `07-nonce-expired.sh`, `08-nonce-used.sh`, `09-install-timeout.sh`,
  `10-upstream-error.sh`, `11-pwned.sh`, `12-version-mismatch.sh`. Total: 12 scenarios + 1 `00-happy-path.sh` that
  exercises the canonical install → start → options → stop → uninstall cycle.
- **D-07:** Each scenario script provokes the error against the live Bridge, runs the Provider (or raw `curl` where
  Provider is overkill), captures the resulting diagnostic / error body to
  `terraform-bridge/internal/testdata/diagnostics/<error_code>.txt`, and exits non-zero if the captured diagnostic does
  not match the expected error_code / HTTP status. The captured file is the source DOCS.md reads from when building the
  troubleshooting table — keeps the docs traceable to the empirical observation.
- **D-08:** Scenario scripts depend on a helper `internal/verify-bridge-e2e/_lib.sh` that handles:
  - The Bridge's bearer token (read from `/data/initial-token` on the host via the Supervisor CLI proxy)
  - The test-addon slug (`local_test-addon`)
  - The state snapshot discipline (see Area 5)
  - Common curl / jq wrappers This avoids each scenario re-implementing token retrieval or jq pipelines.

### Error-code coverage matrix (Area 4)

- **D-09:** The 12 scenarios in D-06 cover every error code in BRIDGE-09 + Phase 12's additions + Provider-side
  handshake. The Provider DOCS.md troubleshooting table (Phase 13 D-14) is the canonical target — Phase 14's
  contribution is empirical confirmation that the documented diagnostics match real behavior. If a scenario's captured
  diagnostic differs from the documented text, **fix the docs to match the observation**, not the other way around (the
  docs are written from observed behavior per Phase 14's purpose).
- **D-10:** Scenarios that would require destructive setup the host can't tolerate (e.g., repeatedly exhausting
  Supervisor's `install` job slots to trigger `install_timeout`) are encoded with explicit skip conditions that print
  "skipped — would require N parallel installs" and exit 0. The DOCS.md troubleshooting entry for those codes is then
  annotated `[not empirically observed — synthetic scenario]`. This honors SC-5's "every error code" without forcing
  unsafe operations.
- **D-11:** The happy-path scenario (`00-happy-path.sh`) is run **five consecutive times** in a single execution to
  prove idempotency (SC-3): each run after the first must report `No changes`. The 5-iteration run is the script's exit
  gate; if iteration 2-5 reports drift, the script fails with the offending diff. — **Reversibility:** `reversible` —
  internal test discipline.

### Operator documentation structure (Area 5)

- **D-12:** `terraform-bridge/README.md` is a **new 1-page HA add-on store listing**: what the add-on does, three
  install steps, three first-time-token retrieval steps, one sentence on Tailscale bind-gate, link to DOCS.md for the
  full reference. Mirrors the existing repo pattern (`phone-logger/README.md` is a 1-page summary;
  `phone-logger/DOCS.md` is the full reference). README.md has no error-code remediation — that lives in DOCS.md.
- **D-13:** `terraform-bridge/DOCS.md` is the **full operator reference**. Required sections, in order:
  1. Options (`bind_address`, `bind_allowed_subnets`, `critical_addons`, `install_job_timeout_seconds`,
     `try_lock_timeout_seconds` — pulled from current `config.yaml` schema)
  2. Token issuance (existing — extends to note that `/data/initial-token` is the canonical source)
  3. Token rotation (existing — extends with the empirical rotation round-trip from Phase 14)
  4. Token recovery (existing — kept verbatim)
  5. Endpoints reference — every `/v1/*` route with method, auth, request shape, response shape (new; pulled from the
     Phase 11/12/13 contract types)
  6. **Troubleshooting** (new top-level section) — the per-`error_code` table populated from the verify scenarios (D-06,
     D-07). Anchors like `#troubleshooting-critical-addon-protected` back the Provider DOCS.md diagnostic URLs.
  7. Observed issues — three+ entries from real Phase-14 runs (e.g., "Bridge returned 401 after `claude login` rotated
     token — fix: provider re-init with new token" if that surfaces, or similar).
  8. State management — `/v1/state/index`, `STATE-02` coverage, HA backup integration per Phase 9 §10 spike.
  9. HA backup integration — explicitly note that `addon_config:rw` mount (incl. `terraform.tfstate`, `bridge-token`) is
     included in `ha backups new --app terraform-bridge` per the Phase 9 §10 empirical result.
- **D-14:** The Provider DOCS.md troubleshooting section already covers every error_code with text + remediation +
  anchor. Phase 14 does **not** duplicate this in Bridge DOCS.md — it cross-links via the anchor pattern instead. Bridge
  DOCS.md's troubleshooting section is a 1-paragraph "what is an error_code and where do I find remediation?" pointer to
  the Provider DOCS.md#troubleshooting table. The Provider DOCS.md table is the single source of truth for the
  user-facing diagnostic text. — **Reversibility:** `costly` — Provider DOCS.md is the published contract per Phase 13
  D-15.
- **D-15:** README.md and DOCS.md must pass the repo's existing markdownlint + prettier pipeline (120-char limit, ATX
  headers, etc.). The expansion is large enough that a markdownlint pre-commit pass before commit is mandatory; the
  planner / executor must include `pre-commit run --files terraform-bridge/README.md terraform-bridge/DOCS.md` in the
  verification step.

### State safety during E2E exercises (Area 6)

- **D-16:** Before any destructive scenario, `_lib.sh` snapshots `/data/terraform.tfstate` to
  `/data/terraform.tfstate.bak.<scenario>` so a botched destroy is recoverable via `mv`. State backup is per-scenario
  (not global) so the recovery point is the most recent successful state.
- **D-17:** Each snapshot is **fingerprinted** via `GET /v1/state/index` before and after the scenario. This serves
  three purposes: (a) demonstrates STATE-02 coverage empirically; (b) gives the operator a quick "did the file change?"
  check; (c) writes a `bridge-e2e-<scenario>-state.json` log line into the testdata directory for post-mortem debugging.
  — **Reversibility:** `reversible`.
- **D-18:** Cleanup at the end of Phase 14: the test add-on is uninstalled from the host, the bridge-nonce-audit journal
  (Phase 12 D-05) is left in place (it's append-only forensics; deleting it would erase the audit trail), and
  `*.tfstate.bak.<scenario>` files older than 7 days are removed via a one-shot find. The cleanup script lives at
  `internal/verify-bridge-e2e/99-cleanup.sh` and is the last scenario in the suite.

### Carried forward from REQUIREMENTS.md + Phase 9/10/11/12/13 CONTEXT (locked, not re-discussed)

- **CF-01:** Token format = base64url, 43 chars; SHA-256 at-rest; `crypto/subtle.ConstantTimeCompare` validation;
  `POST /v1/auth/rotate` 24h grace window. (Phase 10 D-01..D-13.)
- **CF-02:** Bridge → Supervisor uses `SUPERVISOR_TOKEN` auto-injected by Supervisor when `hassio_api: true` is set;
  re-read per call (`internal/supervisor/client.go:84-91`). Token never logged, never sent to Provider, never accepted
  from non-loopback source. (Phase 9 D-18 + Phase 10.)
- **CF-03:** Bearer token in Bridge logs = forbidden; two-layer masking (slog Handler wrapper + chi middleware stripping
  Authorization from r.Header). (Phase 10 D-10.)
- **CF-04:** `/healthz` is unauthenticated; Supervisor ping with 2s timeout; 503 body empty. (Phase 10 D-07..D-08.)
- **CF-05:** Bind = `:8124` with `bind_address` + `bind_allowed_subnets` enforcement; `bind_address: "0.0.0.0"` always
  refused. (Phase 10 D-04..D-06.)
- **CF-06:** Bridge exposes the per-slug mutex (Phase 12 D-12..D-16), `critical_addons` enforcement (Phase 12
  D-09..D-11), and `X-Force-Destroy` nonce (Phase 12 D-05..D-08) on the mutating endpoints. Phase 14 exercises these —
  does not change them.
- **CF-07:** Provider schema (Phase 13) — `homeassistant_addon` resource with adoption-aware Create, idempotent Read,
  options-diff Update, nonce-protected Delete; `homeassistant_addon` and `homeassistant_supervisor_info` data sources;
  `UseStateForUnknown()` on `state`; per-operation timeouts (`create = 10m`, `update = 2m`, `delete = 5m`).
- **CF-08:** Provider diagnostics — explicit per-`error_code` text (Phase 13 D-08); severity rule (Phase 13 D-09);
  troubleshooting URL via tfprotov5.Link (Phase 13 D-10); `request_id` in Detail (Phase 13 D-11). The Provider DOCS.md
  troubleshooting table is the canonical source.
- **CF-09:** `lifecycle.prevent_destroy = true` is recommended in DOCS.md examples but not forced. (Phase 13 D-15.)
- **CF-10:** Per-slug write mutex is in-process only; cross-instance locking is via
  `terraform-plugin-framework-timeouts`. (Phase 12 D-14 + Phase 13 CF-15.)
- **CF-11:** 3-file versioning scheme (Bridge `config.yaml` X.Y.Z-N, build.yaml X.Y.Z, README badges vX.Y.Z) is enforced
  by `internal/validate-versions.sh` and is not re-discussed in Phase 14. Phase 14 does NOT bump versions — it only
  documents and verifies existing behavior. (AGENTS.md §"Critical Gotchas #1".)
- **CF-12:** Bridge `config.yaml` schema (current) — `bind_address`, `bind_allowed_subnets`, `critical_addons` (default
  `["core_mosquitto", "core_zigbee2mqtt", "core_esphome"]`), `install_job_timeout_seconds` (300),
  `try_lock_timeout_seconds` (5). Phase 14 documents these — does not change them.
- **CF-13:** HA backup integration — Phase 9 §10 spike confirmed `addon_config:rw` mount contents (incl.
  `terraform.tfstate`, `bridge-token`, `bridge-nonce-audit.json`) are auto-included in
  `ha backups new --app terraform-bridge`. Phase 14's STATE-02 coverage demonstration (D-17) references this finding.
- **CF-14:** AGENTS.md §"Live Systems — No Unsolicited Restarts / Service Disruption" — Phase 14 owns the live-HA
  apply/destroy exercise; Bridge restarts between scenarios are operator-initiated, not script-initiated.

### the agent's Discretion

- Exact layout inside `tools/test-addon/` — the file structure mirrors the 4-file pattern but the contents are minimal.
  Agent chooses the dummy schema options (one or two string fields; what they actually do is irrelevant — the add-on
  ignores them).
- Exact wording of the README.md 1-pager — must hit the install / token / Tailscale-bind-gate triad; prose is the
  agent's call.
- Whether the verify-script helper `_lib.sh` is shell-only or includes a small jq library file (`_lib.jq`) for reusable
  filters — agent's call. Recommendation: keep it pure shell with `jq` invocations inline; the scenarios are short
  enough that abstraction overhead exceeds reuse benefit.
- Whether `internal/verify-bridge-e2e/99-cleanup.sh` is part of the verify suite (runs after all scenarios) or a
  separate manual step. Recommendation: separate manual step; `99-cleanup.sh` is destructive and should require explicit
  invocation.
- Whether the Bridge's `GET /healthz` response body changes during E2E (it doesn't, per Phase 10 D-08: 503 body empty).
  Phase 14's DOCS.md update to the `/healthz` section is a no-op unless empirical observation contradicts.

### Folded Todos

None — `gsd-tools todo.match-phase 14` returned zero matches. Nothing from the existing backlog is being silently
dropped.

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements traceability (HIGH confidence)

- `.planning/REQUIREMENTS.md` §"OPS — Operations" OPS-04 — the single Phase-14 requirement: operator documentation
  covering install, token issuance + rotation, OpenTofu provider install, example `*.tf`, every error code with
  remediation, troubleshooting section
- `.planning/ROADMAP.md` §"Phase 14: Real-HA End-to-End Verification + Operator Documentation" — five success criteria
  (SC-1..SC-5) the phase must satisfy; SC-5 is the docs gate

### Prior phases (locked, not re-discussed)

- `.planning/phases/13-provider-resource-data-sources-schema-handshake/13-CONTEXT.md` — Provider schema + diagnostics
  - DOCS.md structure (Phase 14 inherits all Phase 13 decisions verbatim; D-08..D-14 in this CONTEXT reference Phase
    13's CF-01..CF-16)
- `.planning/phases/12-bridge-write-api-safety-concurrency-index/12-CONTEXT.md` — Bridge write API + critical_addons +
  per-slug mutex + X-Force-Destroy nonce (Phase 14 exercises these — D-06..D-10 reference Phase 12's D-01..D-26)
- `.planning/phases/10-auth-layer-structured-logging-healthcheck/10-CONTEXT.md` — token format, two-layer masking,
  /healthz, bind-gate (Phase 14 inherits all Phase 10 decisions verbatim)
- `.planning/phases/09-bridge-foundation-token-rotation-spike/09-CONTEXT.md` §"D-08" (`map: addon_config:rw`) and
  §"D-10..D-13" (logging baseline) — confirms the HA backup integration that CF-13 references

### Existing documentation (the canonical target for the expansion)

- `terraform-bridge/DOCS.md` (131 lines, current skeleton) — the file Phase 14 expands. Sections to keep (token
  issuance, rotation, recovery, health check, logs, network access) and sections to add (endpoints reference,
  troubleshooting, observed issues, state management, HA backup integration) per D-13
- `terraform-provider-homeassistant/DOCS.md` (618 lines, current comprehensive) — the canonical source for
  per-error_code diagnostic text + remediation. Phase 14 cross-links rather than duplicates (D-14)
- `terraform-bridge/README.md` (currently a placeholder or absent) — the file Phase 14 writes as a 1-pager (D-12)

### Repo conventions (HIGH confidence)

- `.planning/codebase/CONVENTIONS.md` — 120-char line limit for Markdown; YAML 2-space indent; snake_case option names;
  quoted strings for versions and sensitive values
- `.pre-commit-config.yaml` — markdownlint-cli2 + prettier + shellcheck + yamllint. Phase 14's doc expansion must pass
  markdownlint (D-15 mandates a pre-commit pass)
- `.markdownlint.json` — MD013 (120-char), ATX headers, 4-space list indent
- `.yamllint.yml` — Phase 14's new `tools/test-addon/config.yaml` + `build.yaml` must pass

### Bridge implementation as template (HIGH confidence)

- `terraform-bridge/internal/httpapi/router.go` — chi router with the `/v1` auth subrouter (every Phase-14 endpoint
  exercise inherits auth via this pattern)
- `terraform-bridge/contract/types.go` — every endpoint response shape (AddOnInfo, VersionHandshake, ErrorResponse,
  NonceResponse, StateIndexResponse, JobStatus). Phase 14's "endpoints reference" section pulls from these structs
  verbatim
- `terraform-bridge/internal/supervisor/client.go` — V2/V1 fallback pattern; the empirical verification exercises every
  method (Install, Uninstall, Start, Stop, Options, GetJobStatus, ValidateOptions, GetAddonInfo, ListAddons,
  GetSupervisorInfo)
- `terraform-bridge/internal/auth/token.go` — atomic-write-with-chmod-600 + grace file pattern (referenced by D-13's
  token-issuance section expansion)
- `terraform-bridge/internal/mutex/manager.go` (Phase 12) — per-slug mutex; Phase 14 exercises the `locked` error_code
  by deliberately racing two concurrent operations on the test add-on slug
- `terraform-bridge/internal/nonce/journal.go` (Phase 12) — append-only audit journal; Phase 14 verifies a destructive
  operation actually appends an entry
- `terraform-bridge/internal/state/index.go` (Phase 12) — STATE-02 index; Phase 14's D-17 uses it for state
  fingerprinting

### Phase 9 spike artifacts (HIGH confidence)

- `spike-transcripts/h1-20260831T153943Z.log` — SUPERVISOR_TOKEN rotation behavior (D-18 RESOLVED, conservative
  re-verification deferred per STATE.md todos)
- `spike-transcripts/pitfalls10-20260831T153403Z.log` — HA backup integration with `addon_config:rw` (D-19 RESOLVED;
  CF-13 in this CONTEXT references this)
- `internal/spike-h1-token-rotation.sh`, `internal/spike-pitfalls10-backup-addon-config.sh` — the two spike scripts.
  Phase 14 does NOT re-run these (per STATE.md todo: "Do NOT re-run during normal operation"); references them only as
  historical evidence

### Test fixture as template (HIGH confidence)

- `tools/test-bridge-fixture/` (Phase 15) — stdlib-only HTTP simulator that serves the Bridge contract on `:8124`. Phase
  14's `tools/test-addon/` is the **live** counterpart: a real HA add-on consumed by the live Bridge during Phase 14's
  verification. The verify-script helper (`_lib.sh`) is informed by the fixture's pattern (per-scenario isolation,
  captured-diagnostic discipline) but does not share code with the fixture (the fixture is for hermetic CI; Phase 14 is
  for live verification)
- `internal/verify-bridge-no-token-leak.sh` (Phase 10) — the structural template for Phase 14's verify scenarios: shell
  script per check, captures stdout/stderr to a testdata file, exits non-zero on assertion failure

### Verification scripts (HIGH confidence)

- `internal/verify-install-provider.sh` (Phase 15) — hermetic shell verifier; same exit-gate discipline as Phase 14
  needs (`exit 0` only when all assertions pass)
- `Makefile` §"`install-provider`" target (Phase 15) — the target Phase 14's SC-1 invokes end-to-end

### Live hosts (HIGH confidence)

- `ha-nextgen` — Tailscale hostname; current live Bridge host per AGENTS.md §"Home Assistant Instanz-Zugriff"
- `haos-op3050-1` / `192.168.178.3` — LAN identity of the same host
- `lxc-haos-104`, `hassio-n2plus` — other Tailscale-reachable hosts; **NOT** Phase 14's target per D-01

### Live-system constraints (per AGENTS.md)

- AGENTS.md §"Home Assistant Instanz-Zugriff" — Long-Lived-Token in `~/.config/ha-cli.env`, loaded via Fish+Bitwarden.
  Phase 14's verify scripts can use `ha-cli` or raw `curl`; the scripts are operator-invoked, not autonomous
- AGENTS.md §"Vor `ha supervisor`/`ha core update`/Backup-Operationen" — Phase 14's D-16..D-18 state-safety discipline
  honors this rule (no unsolicited backups; explicit operator invocation)

</canonical_refs>

<code_context>

## Existing Code Insights

### Reusable Assets

- `tools/test-bridge-fixture/` (Phase 15) — the structural template for `tools/test-addon/`. Both are "purpose-built
  test infrastructure that lives in this repo" — the fixture is hermetic (CI), the test-addon is live (Phase 14). Phase
  14 reuses the **convention** (sibling-of-addons directory, own README explaining purpose) but ships live code.
- `internal/verify-bridge-no-token-leak.sh` (Phase 10) — the structural template for Phase 14's verify scenarios.
  Single-purpose shell script, exit-non-zero on assertion failure, captures outputs to testdata files.
- `internal/verify-install-provider.sh` (Phase 15) — exit-gate discipline (hermetic, runs to completion, single exit
  code).
- `terraform-bridge/internal/testdata/` — exists as a directory pattern (Phase 10 may have started it for
  redaction-assertion test data); Phase 14 extends it with `diagnostics/<error_code>.txt` per D-07.
- `terraform-bridge/internal/auth/token.go` — atomic-write-with-chmod-600 pattern; Phase 14's DOCS.md expansion
  references this for the "what does the Bridge write to /data?" question.
- `terraform-bridge/internal/state/index.go` — STATE-02 endpoint; Phase 14's D-17 uses it for state fingerprinting.

### Established Patterns

- **Per-scenario shell scripts** — established by `internal/verify-bridge-no-token-leak.sh` (Phase 10) and the Phase 6
  verify-git-integration.sh scenarios. Phase 14 follows the same pattern: one file per check, captured outputs in
  testdata, exit-gate on assertion.
- **4-file add-on pattern** — established repo convention. `tools/test-addon/` follows it verbatim (config.yaml,
  build.yaml, Dockerfile, run.sh) even though the add-on is trivial. Consistency > minimalism.
- **Pre-commit pipeline** — markdownlint + prettier + shellcheck + yamllint. Phase 14's doc expansion + new shell
  scripts must pass on every commit. D-15 mandates `pre-commit run --files` before committing README.md / DOCS.md.
- **3-file versioning + cross-artifact sync** — Bridge + Provider share X.Y.Z via `internal/validate-versions.sh`. Phase
  14 does NOT bump versions (CF-11); the existing versions stay stable through Phase 14's verification.

### Integration Points

- **Live Bridge at `:8124`** on ha-nextgen — Phase 14 exercises every endpoint via curl. Auth via bearer token from
  `/data/initial-token` (read via `ha addons cli terraform-bridge cat /data/initial-token` or
  `cat /usr/share/hassio/addons/data/terraform-bridge/initial-token` on the host shell).
- **HA Supervisor add-on store** — `tools/test-addon/` is published via the standard local-build path;
  `ha addons reload` picks up the rebuild; the slug `local_test-addon` is visible in the HA UI.
- **Live Supervisor `/supervisor/ping`** — Phase 14's `/healthz` exercise; 200 if reachable, 503 if not. Empirical
  observation during the verification.
- **Live Supervisor `/jobs/{id}` polling** — Phase 14's `00-happy-path.sh` walks an install through to completion;
  Bridge's Phase 12 D-17 polling loop is exercised end-to-end (1s ticks, install_job_timeout_seconds budget).
- **HA backup integration** — `ha backups new --app terraform-bridge` after Phase 14 exercises a full scenario suite;
  the backup's contents are inspected via the HA UI or `ha backups list` + `ha backups info` to confirm
  `addon_config:rw` content (incl. `terraform.tfstate`, `bridge-token`, `bridge-nonce-audit.json`) is captured.
  Empirical proof of STATE-02's premise.
- **`/v1/state/index`** — Phase 14's D-17 calls this before and after each scenario to fingerprint state. Confirms
  STATE-02 works against a real Bridge against a real Supervisor.

</code_context>

<specifics>

## Specific Ideas

- **`ha-nextgen` is `haos-op3050-1`** — Phase 14 collapses the "which host" question. D-01 documents this; planners can
  use either hostname per call without flagging it as a different machine.
- **The test add-on's `run.sh` should be a no-op sleep** — Supervisor's "running" state just needs the container process
  to stay alive. A `sleep infinity` in `run.sh` (with bashio setup that doesn't error out) is sufficient. Anything more
  elaborate risks accidentally testing the test add-on's own behavior instead of the Bridge.
- **`00-happy-path.sh` runs five iterations of `tofu apply` in a row** — the idempotency proof per SC-3. The script
  captures the full `tofu plan` / `tofu apply` output to `internal/testdata/apply-output.<iteration>.txt` for the "no
  changes after first" assertion.
- **`internal/testdata/diagnostics/<error_code>.txt`** is the canonical source for DOCS.md's troubleshooting table text
  — Phase 14's DOCS.md expansion should include a generator step (or manual copy with provenance comment) so each
  troubleshooting row carries a "captured from <scenario>.sh on YYYY-MM-DD" footnote. If the diagnostic ever changes,
  the row is regenerated from the new testdata file.
- **The empirical rotation test** — Phase 14 should deliberately rotate the bearer token (`POST /v1/auth/rotate`)
  mid-verification and confirm the grace window works: both old and new tokens authenticate within 24h; old token
  returns 401 after grace expiry (or by manually deleting `/data/bridge-token.grace` and re-trying). This proves the
  rotation flow end-to-end against a live Bridge.
- **The empirical STATE-02 backup integration test** — Phase 14 should run a scenario that creates a state file via
  `tofu apply`, takes an `ha backups new --app terraform-bridge`, inspects the backup, and confirms the state file is
  inside. This proves the §10 spike result hasn't regressed.
- **README.md should NOT repeat DOCS.md content** — it's a 1-page summary for the HA add-on store. Three steps to
  install + three steps to retrieve the token + a link to DOCS.md. Anything more is in DOCS.md.
- **The "observed issues" section of DOCS.md** is the most operator-valuable artifact — it's where Phase 14's empirical
  work pays off. Three entries minimum (per SC-5), each one a real failure that the verify suite hit during development.
  Examples of likely candidates:
  - "Bearer token returned 401 immediately after Bridge restart" — fix: provider re-init with new token if rotation
    happened (Phase 10 D-12 says rotation requires existing bearer; loss = uninstall/reinstall).
  - "State file shows drift after `tofu refresh` even though nothing changed" — fix: this is `UseStateForUnknown()`
    working; no action needed, but the diff output confuses new operators.
  - "`tofu apply` hangs at 'installing...' for >10 minutes" — fix: increase the `create` timeout; large add-ons dominate
    the budget. Each entry has the same shape: Symptom → Root cause → Fix → Reference.

</specifics>

<deferred>

## Deferred Ideas

- **TLS termination for Bridge** (PITFALLS S-4 Phase 2) — Tailscale Serve or Cloudflare Access path; out of Phase 14
  scope per REQUIREMENTS.md §"Out of Scope". Phase 14's DOCS.md acknowledges plain-HTTP-on-Tailscale as the current
  posture (existing text in DOCS.md line 130-131).
- **Provider Actions (`homeassistant_addon_action` for start/stop/restart)** — v1.4 deferred per REQUIREMENTS.md. Phase
  14's happy-path scenario exercises the start/stop via the resource lifecycle (`start = true`), not via a separate
  Action; that's sufficient for v1.3.
- **`homeassistant_addon_repository` resource** — v1.4 deferred. Phase 14 publishes `tools/test-addon/` via the standard
  local-build path; the Provider does not manage the add-on store itself.
- **Provider-side state-file introspection over `GET /v1/state/index`** — Phase 13 deferred; Phase 14's D-17 uses the
  endpoint for verification but does not add a Provider-side CLI command.
- **Multi-arch Bridge builds** — out of scope for the repo (per PROJECT.md §"Out of Scope"); Phase 14 verifies amd64
  only, which is the only build configuration.
- **CSRF / OPTIONS preflight on the Bridge** — Phase 12 deferred (PITFALLS S-3); Phase 14's E2E exercises
  nonce-protected destroys, not OPTIONS preflight.
- **Auto-rotation cadence for bearer token** — Phase 9 deferred-ideas; Phase 14's DOCS.md rotation section documents
  manual rotation only.
- **`install_job_timeout_seconds` per-slug overrides** — Phase 12 deferred; Phase 14 exercises the global default
  (300s).
- **`AddOnInfo` field coverage beyond D-01's five fields** — Phase 13 D-01 commits to the current five; if Phase 14
  surfaces another missing field, it's a one-line struct extension deferred to a later phase.

### Reviewed Todos (not folded)

None — `gsd-tools todo.match-phase 14` returned zero matches. Nothing from the existing backlog was considered.

</deferred>

---

_Phase: 14-real-ha-end-to-end-verification-operator-documentation_ _Context gathered: 2026-09-05_
