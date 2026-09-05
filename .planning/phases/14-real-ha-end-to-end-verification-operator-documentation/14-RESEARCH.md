# Phase 14: Real-HA End-to-End Verification + Operator Documentation - Research

**Researched:** 2026-09-05 **Domain:** Empirical end-to-end verification of the v1.3 opentofu-bridge stack against
`ha-nextgen` (≡ `haos-op3050-1`) + expansion of `terraform-bridge/README.md` and `DOCS.md` to a full operator reference
driven by observed behavior. **Confidence:** HIGH on existing Bridge code paths + error codes (verified by reading
`terraform-bridge/internal/httpapi/handlers/*.go`, `terraform-bridge/internal/supervisor/client.go`, and
`terraform-bridge/contract/types.go` this session); HIGH on existing verify-script pattern (verified by reading
`internal/verify-bridge-no-token-leak.sh`, `internal/verify-install-provider.sh`, and
`internal/verify-bridge-scaffold.sh` this session); HIGH on Provider-side diagnostic text and DOCS.md anchor convention
(verified by reading `terraform-provider-homeassistant/internal/diagnostics/doc.go` and
`terraform-provider-homeassistant/DOCS.md`); HIGH on the AGENTS.md "no unsolicited restarts" rule and the 3-file
versioning scheme (verified by reading `AGENTS.md` and `internal/validate-versions.sh`); MEDIUM on what the live host
will actually return for `error_code: "pwned"` (Phase 14 is the first time this is exercised end-to-end; the Provider
wires it as a Warning per `CF-08`, but the Bridge's behavior on the host's `mosquitto` / `zigbee2mqtt` / `esphome`
add-ons is not yet empirically known).

## Summary

Phase 14 is two coupled deliverables behind one requirement (OPS-04):

1. **Empirical E2E** against `ha-nextgen` / `haos-op3050-1`. All 26 decisions (D-01..D-18, CF-01..CF-14) are already
   locked in `14-CONTEXT.md`. The research surface for this leg is therefore thin — there is no design left to do. The
   work is: build `tools/test-addon/` (D-03..D-05); wire `internal/verify-bridge-e2e/` as 12 scenario scripts +
   `00-happy-path.sh` + `_lib.sh` + `99-cleanup.sh` (D-06..D-08, D-16..D-18); run them against the live host; capture
   each Bridge `error_code` to `terraform-bridge/internal/testdata/diagnostics/<error_code>.txt` (D-07).
2. **Operator documentation expansion** of `terraform-bridge/README.md` (D-12: 1-pager) and `terraform-bridge/DOCS.md`
   (D-13: full reference with troubleshooting section + observed issues + HA backup integration cross-link).

The CONTEXT already enumerates the canonical refs the planner needs: the Bridge's `internal/supervisor/client.go`
(MapError sentinel → (HTTP status, error_code) pair, lines 661–680) is the single source of truth for every `error_code`
the verify scripts must exercise; `terraform-provider-homeassistant/DOCS.md` is the canonical target for
per-`error_code` remediation text (D-14: Bridge DOCS.md cross-links to Provider DOCS.md, no duplication); the Provider's
`internal/diagnostics/doc.go` constants (`ErrUnauthorizedText` … `PwnedWarningText`) are the source of truth that both
Bridge DOCS.md cross-link and Provider diagnostic Summary text consume.

The live-host work is constrained by the AGENTS.md "Live Systems — No Unsolicited Restarts / Service Disruption" rule:
Bridge restarts between scenarios are operator-initiated, not script-initiated (CF-14, D-02). Every verify script is
read-mostly against the host's Supervisor API (the Bridge runs as `ha-nextgen`'s add-on throughout the suite), with the
test add-on as the only thing the Provider creates + destroys.

**Primary recommendation:** Three-plan split. Plan 01: `tools/test-addon/` scaffold +
`internal/verify-bridge-e2e/_lib.sh`

- the `00-happy-path.sh` five-iteration idempotency scenario (SC-1, SC-2, SC-3). Plan 02: the 12 error-code scenarios,
  one per `error_code` (SC-4 + D-09, D-10). Plan 03: README.md + DOCS.md expansion + 99-cleanup.sh + SC-5 documentation
  gate (D-12..D-15, D-18). Each plan must include `pre-commit run --files <touched>` in its verification step per D-15
  (markdownlint + prettier) + the established yamllint + shellcheck pipeline. Plan-writer should NOT assume Docker / Go
  / OpenTofu are present on the executor machine — Phase 14's executor will run on the workstation where the Provider
  was built (Phase 13) and where the Bridge image is rebuilt between scenarios; Phase 15's CI workflow is a separate
  phase that does not own the local development loop.

## User Constraints (from CONTEXT.md)

<user_constraints>

### Locked Decisions

- **D-01:** `ha-nextgen` ≡ `haos-op3050-1` (same physical host); use whichever hostname is convenient per call.
- **D-02:** Every destructive host action requires per-call user authorization. Verify scripts NEVER auto-restart the
  Bridge; Bridge restarts between scenarios are operator actions.
- **D-03:** New `tools/test-addon/` directory with minimal HA add-on (config.yaml + build.yaml + Dockerfile + run.sh +
  README.md); `ghcr.io/home-assistant/amd64-base:3.24` base image; no-op `run.sh` (sleep); schema exposes one or two
  string options (`log_level`, `dummy_setting`).
- **D-04:** Test add-on is published to the host's local add-on store via `ha addons reload` after each rebuild — no
  GitHub release, no custom-repository URL.
- **D-05:** Test add-on slug is `local_test-addon` (HA convention for locally-built add-ons).
- **D-06:** `internal/verify-bridge-e2e/` ships one shell scenario per `error_code`:
  - `01-unauthorized.sh`, `02-not-found.sh`, `03-critical-addon-protected.sh`, `04-prevented-destroy.sh`,
    `05-already-installed.sh`, `06-locked.sh`, `07-nonce-expired.sh`, `08-nonce-used.sh`, `09-install-timeout.sh`,
    `10-upstream-error.sh`, `11-pwned.sh`, `12-version-mismatch.sh`.
  - Plus `00-happy-path.sh` (install → start → options → stop → uninstall, run FIVE times consecutively for SC-3).
- **D-07:** Each scenario provokes the error against the live Bridge, runs the Provider (or raw `curl` where the
  Provider is overkill), captures the resulting diagnostic / error body to
  `terraform-bridge/internal/testdata/diagnostics/<error_code>.txt`, and exits non-zero on a diagnostic mismatch.
- **D-08:** Scenario scripts depend on `internal/verify-bridge-e2e/_lib.sh` that handles: bearer token (read from
  `/data/initial-token` via Supervisor CLI proxy), test-addon slug, state snapshot discipline, common curl / jq
  wrappers.
- **D-09:** The 12 scenarios cover every `error_code` in BRIDGE-09 + Phase 12's additions + Provider-side handshake. If
  a captured diagnostic differs from documented text, fix the docs to match observation (docs are written from observed
  behavior).
- **D-10:** Scenarios requiring destructive setup the host can't tolerate are encoded with explicit skip conditions
  printing "skipped — would require N parallel installs" and exit 0; DOCS.md annotations for those codes carry
  `[not empirically observed — synthetic scenario]`.
- **D-11:** `00-happy-path.sh` runs FIVE consecutive `tofu apply` iterations; iterations 2-5 must report "No changes".
- **D-12:** `terraform-bridge/README.md` is a NEW 1-pager (install + token walkthrough + Tailscale-bind-gate note + link
  to DOCS.md); mirrors `phone-logger/README.md` pattern.
- **D-13:** `terraform-bridge/DOCS.md` is the FULL operator reference. Required sections in order:
  1. Options (`bind_address`, `bind_allowed_subnets`, `critical_addons`, `install_job_timeout_seconds`,
     `try_lock_timeout_seconds`)
  2. Token issuance (existing — extends to note `/data/initial-token` is canonical)
  3. Token rotation (existing — extends with empirical rotation round-trip from Phase 14)
  4. Token recovery (existing — kept verbatim)
  5. Endpoints reference — every `/v1/*` route with method, auth, request shape, response shape
  6. Troubleshooting (new top-level section) — per-`error_code` table populated from verify scenarios
  7. Observed issues — 3+ entries from real Phase 14 runs
  8. State management — `/v1/state/index`, STATE-02 coverage, HA backup integration
  9. HA backup integration — explicit note that `addon_config:rw` mount (incl. `terraform.tfstate`, `bridge-token`,
     `bridge-nonce-audit.json`) is included in `ha backups new --app terraform-bridge`
- **D-14:** Provider DOCS.md is the canonical source for per-error_code diagnostic text + remediation + anchor; Bridge
  DOCS.md's troubleshooting section is a 1-paragraph pointer. NO duplication.
- **D-15:** README.md and DOCS.md must pass markdownlint + prettier (120-char limit, ATX headers). Include
  `pre-commit run --files terraform-bridge/README.md terraform-bridge/DOCS.md` in the verification step.
- **D-16:** Before any destructive scenario, `_lib.sh` snapshots `/data/terraform.tfstate` to
  `/data/terraform.tfstate.bak.<scenario>`; recovery via `mv`.
- **D-17:** Each snapshot is fingerprinted via `GET /v1/state/index` before and after the scenario; log to
  `bridge-e2e-<scenario>-state.json`.
- **D-18:** Cleanup: test add-on uninstalled from host; `bridge-nonce-audit.json` LEFT IN PLACE (append-only forensics);
  `*.tfstate.bak.<scenario>` files older than 7 days removed via one-shot find. Cleanup lives at
  `internal/verify-bridge-e2e/99-cleanup.sh` and is the LAST scenario (separate manual invocation per agent discretion).

### the agent's Discretion

- Exact layout inside `tools/test-addon/`. File structure mirrors 4-file pattern; contents minimal.
- Exact wording of `terraform-bridge/README.md`. Must hit install / token / Tailscale-bind-gate triad.
- Whether `_lib.sh` is shell-only or includes a small `_lib.jq` for reusable filters. Recommendation: pure shell with
  inline `jq`; abstraction overhead exceeds reuse benefit.
- Whether `99-cleanup.sh` is part of the verify suite (runs after all scenarios) or a separate manual step.
  Recommendation: separate manual step.
- Whether the Bridge's `GET /healthz` response body changes during E2E (it doesn't, per Phase 10 D-08: 503 body empty).
  Phase 14's DOCS.md update to `/healthz` is a no-op unless empirical observation contradicts.

### Deferred Ideas (OUT OF SCOPE)

- TLS termination for Bridge (Tailscale Serve or Cloudflare Access path).
- Provider Actions (`homeassistant_addon_action` for start/stop/restart).
- `homeassistant_addon_repository` resource.
- Provider-side state-file introspection over `GET /v1/state/index`.
- Multi-arch Bridge builds (amd64 only).
- CSRF / OPTIONS preflight on the Bridge.
- Auto-rotation cadence for bearer token.
- `install_job_timeout_seconds` per-slug overrides.
- `AddOnInfo` field coverage beyond Phase 13 D-01's committed five.

### Carried forward (CF-01..CF-14) — locked, not re-discussed

- **CF-01:** Token format = base64url, 43 chars; SHA-256 at-rest; `crypto/subtle.ConstantTimeCompare` validation;
  `POST /v1/auth/rotate` 24h grace window. (Phase 10 D-01..D-13.)
- **CF-02:** Bridge → Supervisor uses `SUPERVISOR_TOKEN` auto-injected by Supervisor when `hassio_api: true`; re-read
  per call (`internal/supervisor/client.go:84-91`).
- **CF-03:** Bearer token in Bridge logs = forbidden; two-layer masking (slog Handler wrapper + chi middleware stripping
  Authorization from r.Header). (Phase 10 D-10.)
- **CF-04:** `/healthz` is unauthenticated; Supervisor ping with 2s timeout; 503 body empty.
- **CF-05:** Bind = `:8124` with `bind_address` + `bind_allowed_subnets`; `bind_address: "0.0.0.0"` always refused.
- **CF-06:** Per-slug mutex (Phase 12 D-12..D-16), `critical_addons` enforcement (Phase 12 D-09..D-11),
  `X-Force-Destroy` nonce (Phase 12 D-05..D-08) on mutating endpoints. Phase 14 exercises these — does not change.
- **CF-07:** Provider schema — `homeassistant_addon` resource with adoption-aware Create, idempotent Read, options-diff
  Update, nonce-protected Delete; `homeassistant_addon` + `homeassistant_supervisor_info` data sources;
  `UseStateForUnknown()` on `state`; per-operation timeouts.
- **CF-08:** Provider diagnostics — explicit per-`error_code` text; severity rule (Error for 4xx/5xx, Warning for
  `pwned`); DOCS.md anchor via `tfprotov5.Link`; `request_id` in Detail.
- **CF-09:** `lifecycle.prevent_destroy = true` is recommended in DOCS.md examples but not forced.
- **CF-10:** Per-slug write mutex is in-process only; cross-instance locking is via
  `terraform-plugin-framework-timeouts`.
- **CF-11:** 3-file versioning scheme enforced by `internal/validate-versions.sh`. Phase 14 does NOT bump versions — it
  only documents + verifies existing behavior.
- **CF-12:** Bridge `config.yaml` schema (current): `bind_address`, `bind_allowed_subnets`, `critical_addons` (default
  `["core_mosquitto", "core_zigbee2mqtt", "core_esphome"]`), `install_job_timeout_seconds` (300),
  `try_lock_timeout_seconds` (5).
- **CF-13:** HA backup integration — Phase 9 §10 spike confirmed `addon_config:rw` mount contents (`terraform.tfstate`,
  `bridge-token`, `bridge-nonce-audit.json`) are auto-included in `ha backups new --app terraform-bridge`.
- **CF-14:** AGENTS.md Live Systems rule — Phase 14 owns live-HA apply/destroy exercise; Bridge restarts between
  scenarios are operator-initiated, not script-initiated.

</user_constraints>

## Phase Requirements

<phase_requirements>

| ID         | Description                                                                                                                                                                                                                                                                                                    | Research Support                                                                                                                                                                                                                                                                                                                                                                                          |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **OPS-04** | Bridge `README.md` and `DOCS.md` document: install (HA add-on store), token issuance + rotation (`cat /data/bridge-token`), OpenTofu provider install (`make install-provider`), example `*.tf` file, every resource attribute with example values, every error code with remediation, troubleshooting section | Phase 13 already wrote the canonical Provider-side DOCS.md (618 lines, full troubleshooting table). Phase 14's Bridge DOCS.md must cross-link to Provider DOCS.md per D-14 (no duplication). README.md + DOCS.md structure already locked in D-12 + D-13. The "every error code with remediation" requirement is satisfied by the Provider DOCS.md#troubleshooting anchors the Bridge DOCS.md references. |

</phase_requirements>

## Project Constraints (from AGENTS.md)

These directives appear in the project's `AGENTS.md` file and have the same authority as locked decisions from
CONTEXT.md — research MUST NOT recommend approaches that contradict them, and the plan-writer MUST verify compliance.

| Directive                                                                                                                                                                           | Source                                       | Phase 14 Implication                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Ask first, act later.** on critical tasks (version bumps, deployment changes, add-on removals, CI/CD modifications)                                                               | AGENTS.md §Agent Behavior Guidelines         | Phase 14 DOES NOT bump Bridge version (CF-11 — Phase 14 verifies existing behavior, does not change it). D-02 explicitly requires per-call user authorization for destructive host actions; the verify scripts NEVER auto-restart the Bridge (CF-14). Plan-writer MUST structure every scenario script so the operator is in the loop for `ha addons install local_test-addon`, `ha backups new --app terraform-bridge`, and Bridge image redeploys.                                                                                                                                                                    |
| **Challenge the approach.** if risky / inconsistent with conventions                                                                                                                | AGENTS.md §Agent Behavior Guidelines         | The CONTEXT.md decisions are consistent with established patterns: verify-bridge-no-token-leak.sh structure (Phase 10), test-bridge-fixture convention (Phase 15), 4-file add-on pattern (every existing add-on). The D-07 "captured diagnostic per testdata file" pattern is the same as the existing `internal/verify-bridge-no-token-leak.sh` exit-non-zero-on-assertion discipline. No challenges raised.                                                                                                                                                                                                           |
| **Live Systems — No Unsolicited Restarts / Service Disruption**                                                                                                                     | AGENTS.md §🔌 Home Assistant Instanz-Zugriff | The Bridge runs on `ha-nextgen` throughout the verify suite. Every scenario assumes the Bridge is up; the only way to put it in a "broken" state is to manipulate the token on disk (rotate, then test with old token after grace expiry, etc.), or to exercise `bind_address: 0.0.0.0` refusal (which the Bridge exits on — not part of E2E). Plan MUST NOT auto-restart the Bridge, MUST NOT auto-restart Supervisor, MUST NOT touch `core_mosquitto` / `core_zigbee2mqtt` / `core_esphome` (the host's `critical_addons`). Test add-on lives separately — safe to install/uninstall freely.                          |
| **Pre-commit hooks must keep green:** yamllint (120-char lines, relaxed), shellcheck (SC1091/SC2034 ignored), prettier (120-char), actionlint, markdownlint, `validate-versions.sh` | AGENTS.md §Code Quality & Validation         | Plan MUST include `pre-commit run --files <touched>` in its verification step. The new `tools/test-addon/config.yaml` + `build.yaml` MUST pass yamllint (quoted strings, 2-space indent). The new shell scripts in `internal/verify-bridge-e2e/` MUST pass shellcheck (SC1091 + SC2034 ignored per repo convention). README.md + DOCS.md MUST pass markdownlint-cli2 + prettier (D-15). The new test add-on is a 4-file pattern add-on, so `internal/validate-addon-config.py` will pick it up automatically (`(d / 'config.yaml').exists() and (d / 'build.yaml').exists()` filter at `validate-addon-config.py:104`). |
| **Pre-commit `check-yaml --unsafe`** allows HA custom YAML tags (`!secret`, `!include`)                                                                                             | AGENTS.md §🚨 Gotcha #3                      | The new `tools/test-addon/config.yaml` schema will use HA's `- "str?"` DSL for any list-of-strings option (Phase 12 precedent in `terraform-bridge/config.yaml:24-37`). Plan MUST follow the same convention.                                                                                                                                                                                                                                                                                                                                                                                                           |
| **Never manually edit versions.** Use `make update-version`                                                                                                                         | AGENTS.md §Critical Gotchas #1               | Phase 14 DOES NOT bump versions (CF-11). The test add-on MUST use `X.Y.Z-0` initial version (`tools/test-addon/config.yaml: version: "0.1.0-0"`) + matching `build.yaml: VERSION: "0.1.0"` + matching README badge URL (`v0.1.0`). The pre-commit `validate-versions.sh` script runs across ALL add-on directories (it does NOT have a `files:` pattern filter — see `.pre-commit-config.yaml:91`), so a new add-on automatically becomes part of version validation. Plan MUST keep the three files in sync; pre-commit fires on every commit.                                                                         |
| **Atomic file write with chmod 600** from Phase 9 D-08 / Phase 10 plan 03's grace file                                                                                              | AGENTS.md / CF-08 in CONTEXT.md              | Phase 14 does NOT add new `/data` files (no code change), but the verify scripts will READ `/data/initial-token` (D-08 bearer token retrieval) and WRITE to `/data/terraform.tfstate.bak.<scenario>` (D-16 state snapshots). The snapshot write is a plain `cp` (not a new persistence primitive); the token read is a read-only operation. Plan MUST NOT introduce new atomic-rename patterns — they already exist for `/data/bridge-token`, `/data/initial-token`, `/data/bridge-token.grace`, `/data/bridge-nonce-audit.json`.                                                                                       |
| **Hassio_role: manager** in config.yaml                                                                                                                                             | AGENTS.md §AUTH-06                           | Already in `terraform-bridge/config.yaml:13` (`hassio_role: manager`). Phase 14's verify scripts call Bridge as a consumer (not as a Supervisor client); the manager role is irrelevant to the verify scripts themselves. The test add-on needs `hassio_api: true` if the Provider's Update flow exercises options that include other add-ons' options (it won't — D-03 schema exposes only `log_level` + `dummy_setting`, which are own-addon options, not cross-addon).                                                                                                                                               |
| **Plan changes that the executor runs autonomously must respect the live-system rule.**                                                                                             | AGENTS.md §Live Systems                      | Phase 14 plan MUST NOT be marked `autonomous: true` for any wave that touches the live host. The verify scenarios are operator-invoked shell scripts (per CONTEXT.md "agent's Discretion" recommendation on `99-cleanup.sh`). The D-07 captured-diagnostic discipline + D-16 snapshot + D-17 fingerprint provide the operator with a full recovery path (`mv /data/terraform.tfstate.bak.<scenario> /data/terraform.tfstate`); the plan MUST document this recovery path explicitly in each scenario's script header.                                                                                                   |
| **Home Assistant instance access via long-lived token + ha-cli**                                                                                                                    | AGENTS.md §🔌 Home Assistant Instanz-Zugriff | Phase 14's verify scripts can use either `ha-cli` (if available on the executor machine — it is not in this environment; check at execution time) or raw `curl` to `https://ha-nextgen.akentner.ts.net:8124` (Tailscale hostname) or `http://192.168.178.3:8124` (LAN identity). Scripts are operator-invoked; the operator loads their `~/.config/ha-cli.env` via Fish+Bitwarden as needed. The Bridge binds `0.0.0.0:8124` (CF-05) so both Tailscale and LAN paths reach it.                                                                                                                                          |

## Architectural Responsibility Map

| Capability                                                   | Primary Tier                                   | Secondary Tier                               | Rationale                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ------------------------------------------------------------ | ---------------------------------------------- | -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Live-HA E2E orchestration (scenario scripts)                 | Operator workstation (bash)                    | Bridge process (running)                     | `internal/verify-bridge-e2e/*.sh` runs on the operator's workstation (where `tofu`, `curl`, `jq` are installed per the Phase 13 dev environment). The script reaches Bridge via HTTP from the workstation; Bridge in turn reaches Supervisor via its `SUPERVISOR_TOKEN`. The Bridge itself is the running service; the scripts do NOT live on the Bridge host.                                                                                                                                                                                                                         |
| Bearer token retrieval (`/data/initial-token`)               | Bridge host (host filesystem)                  | Operator workstation (read)                  | The token plaintext lives in `/data/initial-token` on `ha-nextgen` (CF-02: never logs, never in Provider). The verify scripts SSH to the host and `cat` the file (per CONTEXT.md D-08 reference to `ha addons cli terraform-bridge cat /data/initial-token`). Alternative: `ha-cli` from the workstation. Both paths end at the same file; the Bridge never serves the plaintext over HTTP (deliberate Phase 10 D-12 design).                                                                                                                                                          |
| Test add-on (install / configure / start / stop / uninstall) | HA Supervisor (running on ha-nextgen)          | Bridge (proxy) → Provider (declarative)      | The Provider issues `POST /v1/addons/{slug}/install` etc. via the Bridge. Bridge calls Supervisor. Supervisor creates the container from `local/local_test-addon:latest` (the slug prefix `local_` signals "locally built"). The container is `ghcr.io/home-assistant/amd64-base:3.24` + a no-op `run.sh` (D-03); Supervisor sees it as "running" because the container process stays alive. The test add-on lives ENTIRELY inside the host's Supervisor-managed namespace — no external dependency, no GitHub release.                                                                |
| State file persistence (`/data/terraform.tfstate`)           | Bridge add-on volume (`addon_config:rw`)       | HA backup (full-snapshot coverage)           | The Provider writes `terraform.tfstate` to `/data/terraform.tfstate` (per Phase 13's STATE-01 + DOCS.md guidance). This path is inside the Bridge's `addon_config:rw` mount, which is auto-included in `ha backups new --app terraform-bridge` (CF-13, Phase 9 §10 spike result). The state snapshots in D-16 (`*.tfstate.bak.<scenario>`) live alongside the canonical state file — same `addon_config:rw` mount, same backup coverage.                                                                                                                                               |
| `/v1/state/index` fingerprint (D-17)                         | Bridge process (running)                       | Verify scripts (call + log)                  | `GET /v1/state/index` enumerates `*.tfstate` + `*.tfstate.backup` files in `/data` with SHA-256 digests (Phase 12 D-20..D-23). The verify scripts call this BEFORE and AFTER each scenario, log the diff to `bridge-e2e-<scenario>-state.json` in the testdata directory. Empirical demonstration that STATE-02 (BRIDGE-09 + STATE-02) actually works against a real Supervisor — also gives the operator a "did the file change?" check.                                                                                                                                              |
| Per-`error_code` remediation text (DOCS.md#troubleshooting)  | Provider DOCS.md (already written by Phase 13) | Bridge DOCS.md (cross-link via anchor, D-14) | Phase 13's Provider DOCS.md (618 lines) is the canonical source for per-`error_code` Summary text — the constants in `terraform-provider-homeassistant/internal/diagnostics/doc.go` (`ErrUnauthorizedText` … `PwnedWarningText`) are the source of truth. Phase 14's Bridge DOCS.md adds a 1-paragraph "what is an `error_code` and where do I find remediation?" pointer + an `Endpoints reference` section (D-13 §5) that lists every `/v1/*` route with method + auth + request/response shape. NO duplication.                                                                     |
| Tailscale bind enforcement                                   | Bridge process (bind-gate at startup)          | Network layer (Tailscale ACL)                | Phase 10 D-04..D-06: bind to Tailscale-detected IP or an IP inside `bind_allowed_subnets`; `0.0.0.0` always refused. Phase 14 exercises this only insofar as the operator chooses Tailscale vs. LAN hostname to reach the Bridge (D-01) — the verify scripts themselves don't enforce bind rules; they reach the Bridge via whichever hostname is convenient for the call origin. The Bridge will refuse to start if the bind gate fails; not exercised by Phase 14 scripts.                                                                                                           |
| Token rotation flow (POST /v1/auth/rotate)                   | Bridge process (running)                       | Operator workstation (POST)                  | Phase 10 D-12 + Phase 13: rotation requires existing valid bearer; grace window 24h. Phase 14's empirical rotation test (per CONTEXT.md Specifics): deliberately rotate the bearer mid-verification, confirm grace works (both old + new authenticate within 24h), then manually delete `/data/bridge-token.grace` to confirm old token returns 401 after grace expiry. This proves the rotation flow end-to-end against a live Bridge — required for DOCS.md §3 expansion.                                                                                                            |
| Provider-driven `tofu apply`                                 | Operator workstation (`tofu` binary)           | Bridge → Supervisor (chain)                  | The Provider is installed via `make install-provider` (TOFU-04 / Phase 15) to `~/.terraform.d/plugins/...`. The operator runs `tofu init && tofu apply` against the test add-on's `*.tf`. The Provider makes HTTP calls to Bridge; Bridge makes HTTP calls to Supervisor; Supervisor creates the container. Each Provider call carries the bearer token (PITFALLS S-1 invariant). The Provider's diagnostic Summary text (D-08) is what surfaces in `tofu apply` output when an `error_code` is returned — Phase 14 captures this text verbatim to the per-`error_code` testdata file. |
| HA backup integration (D-13 §9)                              | HA Supervisor backup subsystem                 | Bridge add-on volume                         | Phase 9 §10 spike confirmed `addon_config:rw` mount contents are auto-included in `ha backups new --app terraform-bridge` (CF-13). Phase 14's empirical demonstration: take a backup after a full scenario suite, inspect via `ha backups info <slug>` + `rsync <host>:/backup/<file>.tar /tmp/`, extract the per-addon tar.gz, grep for `terraform.tfstate` and `bridge-nonce-audit.json`. This proves STATE-02's premise empirically — required for the DOCS.md §9 expansion.                                                                                                        |

## Standard Stack

Phase 14 introduces **zero** new external dependencies. All work is shell + the existing Provider binary (Phase 13)

- the existing Bridge binary (Phase 12) + the test add-on (a minimal Alpine container,
  `ghcr.io/home-assistant/amd64-base:3.24`).

### Core

| Library / Tool                           | Version                                      | Purpose                                                                                         | Why Standard                                                                                                                                                                                  |
| ---------------------------------------- | -------------------------------------------- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Bash                                     | 4+ (per `verify-bridge-no-token-leak.sh:25`) | All verify scripts (`set -euo pipefail`)                                                        | Existing repo convention; shellcheck v0.10.0.1 enforced via `.pre-commit-config.yaml:30`                                                                                                      |
| `curl`                                   | HA-base image ships 8.x                      | Bearer-authenticated HTTP calls to Bridge                                                       | Already used by Phase 9 scaffold verify + Phase 11 README examples + Phase 13 Provider client tests                                                                                           |
| `jq`                                     | 1.6+                                         | JSON parsing for `/v1/state/index` fingerprints + `/v1/version` handshake + diagnostic captures | Already used by `internal/verify-bridge-scaffold.sh:91` for JSON validation                                                                                                                   |
| `tofu` (OpenTofu)                        | 1.12+ (per PROV-01)                          | `tofu init && tofu apply` against the test add-on's `*.tf`                                      | Required by Phase 13 SC-1; installed via Phase 15 `make install-provider` (TOFU-04); dev_overrides workflow per Provider DOCS.md §"Step 2 — register the binary via dev_overrides"            |
| `ssh`                                    | system                                       | Reach the Bridge host for `cat /data/initial-token`, `ha addons reload`, `ha backups new`       | Standard remote access; Tailscale hostname `ha-nextgen.akentner.ts.net` is the preferred path from outside the LAN, LAN IP `192.168.178.3` from inside                                        |
| `ghcr.io/home-assistant/amd64-base:3.24` | 3.24 (per `terraform-bridge/Dockerfile:5`)   | Test add-on base image                                                                          | HA's official base; same base as the Bridge + phone-logger; carries bashio + run.sh entry-point conventions; `chmod +x /run.sh` matches the existing `terraform-bridge/Dockerfile:42` pattern |

### Supporting

| Library / Tool                              | Version                            | Purpose                                                             | When to Use                                                                                                                                                                            |
| ------------------------------------------- | ---------------------------------- | ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `terraform-provider-homeassistant` binary   | 0.2.0 (per Provider `build.yaml`)  | Declarative CRUD against the Bridge                                 | Already built by Phase 13; installed via Phase 15 `make install-provider`; the verify scripts invoke it via `tofu apply` for the happy-path scenario                                   |
| `terraform-bridge` binary (running on host) | 0.2.0-0 (per Bridge `config.yaml`) | Live HA endpoint for E2E                                            | Already deployed on `ha-nextgen` per Phase 11 + 12 + 13 ship logs; CF-12 schema is the schema under test                                                                               |
| `internal/supervisor/testing.go` (Bridge)   | Phase 11                           | Cross-package test helpers (`WithBaseURLForTest`, `TokenFnForTest`) | Not used by Phase 14 verify scripts (they run against the LIVE Bridge, not a fixture); listed for completeness — the test-bridge-fixture is the CI equivalent (Phase 15), not Phase 14 |
| `tools/test-bridge-fixture/` (Phase 15)     | Go stdlib HTTP simulator           | CI-only fixture that mimics `/v1/version`                           | NOT used by Phase 14 (CONTEXT.md D-04 + canonical_refs §"Test fixture as template" explicitly distinguish fixture = CI, test-addon = live). Listed for completeness                    |
| `internal/state/index.go` (Bridge)          | Phase 12                           | `Index(dir string) ([]FileEntry, []SkippedEntry, error)`            | Called by the verify scripts via `GET /v1/state/index` for D-17 fingerprint discipline; not modified                                                                                   |
| `internal/mutex/manager.go` (Bridge)        | Phase 12                           | Per-slug write serialization                                        | Exercised by scenario `06-locked.sh` (deliberately race two concurrent Provider operations on `local_test-addon`); not modified                                                        |
| `internal/nonce/journal.go` (Bridge)        | Phase 12                           | Append-only nonce audit journal                                     | Verified by scenario `08-nonce-used.sh` (confirm a destructive op appends an entry); not modified; cleanup script (D-18) deliberately leaves it in place                               |

### Alternatives Considered

| Instead of                                                | Could Use                                                                       | Tradeoff                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| --------------------------------------------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Per-scenario shell script (`01-unauthorized.sh`, …)       | Single shell script with all 12 scenarios inline                                | Per-scenario script = individually rerunnable; each captures its own diagnostic; failure of one scenario doesn't block the others; aligns with the existing `internal/verify-bridge-no-token-leak.sh` pattern (Phase 10). Single script = easier to invoke once but loses per-scenario isolation and traceability to the testdata file. CONTEXT.md D-06 already chose per-scenario.                                                                   |
| Raw `curl` for every scenario                             | `tofu apply` for every scenario                                                 | Raw `curl` is appropriate for 401 / 404 / 403 / nonce_expired / nonce_used / upstream_error / version-mismatch (the Provider would mask the diagnostic text + add its own Summary layer that D-14 explicitly cross-links rather than duplicates). `tofu apply` is REQUIRED for happy-path (SC-3 idempotency), 05-already-installed (adoption), 06-locked (Provider-level retry), 11-pwned (Warning severity), 04-prevented-destroy (lifecycle guard). |
| In-tree Go test against the live host                     | Shell scripts (chosen)                                                          | Go test against a live Supervisor would require a Go binary with `hassio_api: true` + `SUPERVISOR_TOKEN` access; the test-bridge-fixture (Phase 15) is the closer analog but is hermetic CI only. Shell scripts are operator-invoked (CF-14), reach the Bridge over HTTP, and produce captured-diagnostic testdata files that DOCS.md reads from (D-07 traceability).                                                                                 |
| Dedicated Docker-based verify runner                      | Bare shell on the operator workstation                                          | Docker runner would be more reproducible but adds an isolation layer that breaks the Bridge's TLS / bind-gate assumptions (the operator workstation is the simplest place to reach `ha-nextgen` over Tailscale). Bare shell is the established repo convention.                                                                                                                                                                                       |
| Per-scenario state backup to operator workstation (`scp`) | Snapshot inside the Bridge container (`/data/terraform.tfstate.bak.<scenario>`) | D-16's in-container snapshot is the established Phase 12 pattern (the nonce audit journal lives the same way). Operator workstation copy adds bandwidth + sync overhead for no benefit — the Bridge host's `/data` is the authoritative state file location, and HA backup integration (CF-13) covers it automatically.                                                                                                                               |

**Version verification (no new deps):**

```bash
# Verify the Bridge base image tag still resolves (D-03 references it):
docker manifest inspect ghcr.io/home-assistant/amd64-base:3.24 2>/dev/null | head -1 || echo "docker not available on executor — verify on the Bridge host"

# Verify Provider binary exists (built by Phase 13):
ls -la terraform-provider-homeassistant/terraform-provider-homeassistant

# Verify the running Bridge version matches `terraform-bridge/config.yaml`:
curl -sS http://192.168.178.3:8124/v1/version -H "Authorization: Bearer $TOKEN" | jq -r .bridge_version
```

All three are operator-invoked pre-flight checks; the verify scripts depend on them being run first but do NOT
themselves verify them.

### Version Confidence

- Bridge base image `ghcr.io/home-assistant/amd64-base:3.24` — VERIFIED in `terraform-bridge/Dockerfile:5`
  (`ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24`) and `terraform-bridge/build.yaml:2` (`build_from.amd64`).
  Read this session.
- Provider binary `terraform-provider-homeassistant/terraform-provider-homeassistant` — VERIFIED in
  `terraform-provider-homeassistant/main.go:23-40` (real `providerserver.Serve` entry point, NOT a Phase 9 stub). Read
  this session.
- Bridge Go module — VERIFIED in `terraform-bridge/go.mod` (Phase 9 scaffold + chi v5.3.2 + Go 1.25 toolchain). Phase 12
  added no new external deps; Phase 14 adds none.
- Provider Go module — VERIFIED in `terraform-provider-homeassistant/go.mod` (Phase 13 added
  `terraform-plugin-framework` + `terraform-plugin-framework-timeouts`). Phase 14 adds none.
- OpenTofu 1.12+ — ASSUMED (per PROV-01; not verified in this environment). Operator's workstation must have it
  installed; Phase 15 installs the Provider binary against it.

## Package Legitimacy Audit

> **Required** whenever this phase installs external packages. **Phase 14 installs zero external packages.** All work
> uses shell + existing binaries + the official HA base image (which is consumed, not published).

| Package  | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
| -------- | -------- | --- | --------- | ----------- | ------- | ----------- |
| _(none)_ | —        | —   | —         | —           | —       | —           |

**Packages removed due to SLOP verdict:** none. **Packages flagged as suspicious SUS:** none.

_Phase 14 deliberately adds zero new external dependencies. The new `tools/test-addon/` consumes
`ghcr.io/home-assistant/amd64-base:3.24` (already used by the Bridge + phone-logger). The verify scripts depend on
`bash`, `curl`, `jq` (already required by Phase 9 scaffold + Phase 10 token-leak verifiers), `tofu` (already required by
Phase 13 SC-1 + Phase 15 install-provider), and `ssh` (already required by Phase 9 §10 + H-1 spikes)._

## Architecture Patterns

### System Architecture Diagram

The diagram below traces ONE complete scenario (`00-happy-path.sh`, iteration 1 of 5) — install + start + options +
stop + uninstall — through every tier. The 12 error-code scenarios follow the same structure with a different fault
injected at the indicated point.

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│ Operator workstation                                                               │
│  ┌─ internal/verify-bridge-e2e/_lib.sh ─────────────────────────────────────────┐ │
│  │  • BRIDGE_URL=https://ha-nextgen.akentner.ts.net:8124  (or LAN:8124)         │ │
│  │  • TOKEN=$(ssh ha-nextgen cat /usr/share/hassio/addons/data/               │ │
│  │              terraform-bridge/initial-token)                                │ │
│  │  • SNAPSHOT_BEFORE=$(ssh ha-nextgen cp /data/terraform.tfstate              │ │
│  │                          /data/terraform.tfstate.bak.<scenario>)           │ │
│  │  • FP_BEFORE=$(curl -sS $BRIDGE_URL/v1/state/index -H "Auth: Bearer …")     │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                          │                                                         │
│                          ▼                                                         │
│  ┌─ internal/verify-bridge-e2e/00-happy-path.sh ────────────────────────────────┐│
│  │  iteration 1..5 of:                                                         ││
│  │   tofu init                                                                 ││
│  │   tofu plan  → captures plan output → internal/testdata/apply-output.N.txt   ││
│  │   tofu apply → captures apply output → …                                    ││
│  │  after iteration 5, assert "No changes" on iterations 2..5 (SC-3 gate)      ││
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                          │                                                         │
│                          ▼                                                         │
│  ┌─ tofu → dev_overrides → terraform-provider-homeassistant binary ─────────────┐│
│  │  endpoint     = http://ha-nextgen.akentner.ts.net:8124                       ││
│  │  bearer_token = $TOKEN (from _lib.sh)                                       ││
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼ Bearer-authenticated HTTP
┌────────────────────────────────────────────────────────────────────────────────────┐
│ Bridge add-on running on ha-nextgen                                                │
│  ┌─ chi /v1 subrouter ── RequireBearer(store) ──────────────────────────────┐    │
│  │                                                                          │    │
│  │  POST /v1/auth/nonce → handlers.Nonce(nonceMgr) [auth, X-Force-Destroy   │    │
│  │                      preflight for uninstall/options]                     │    │
│  │  POST /v1/addons/local_test-addon/install → handlers.Install              │    │
│  │      ↳ mutexMgr.TryAcquire(r.Context(), slug)  [per-slug mutex]           │    │
│  │      ↳ supClient.Install → /store/apps/{slug}/install (async)             │    │
│  │      ↳ supClient.GetJobStatus (1s linear polling)                          │    │
│  │      ↳ GET /v1/addons/local_test-addon/info (post-install, 3x500ms retry)  │    │
│  │  POST /v1/addons/local_test-addon/start → handlers.Start [no nonce]       │    │
│  │  POST /v1/addons/local_test-addon/options → handlers.Options              │    │
│  │      ↳ critical_addons check (NO-OP for local_test-addon — not critical)  │    │
│  │      ↳ nonce validation (X-Force-Destroy)                                 │    │
│  │      ↳ supClient.ValidateOptions → /apps/{slug}/options/validate          │    │
│  │      ↳ supClient.Options → /apps/{slug}/options  (sync)                   │    │
│  │      ↳ on `pwned: true` response: Provider surfaces WARNING (CF-08)        │    │
│  │  POST /v1/addons/local_test-addon/stop → handlers.Stop [no nonce]         │    │
│  │  POST /v1/addons/local_test-addon/uninstall → handlers.Uninstall          │    │
│  │      ↳ critical_addons check (NO-OP — not in default critical_addons)     │    │
│  │      ↳ nonce validation (X-Force-Destroy)                                 │    │
│  │      ↳ supClient.Uninstall → /apps/{slug}/uninstall (sync, 204)           │    │
│  │                                                                          │    │
│  │  GET /v1/state/index → handlers.StateIndex(/data) — fingerprint           │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                           │
│                                      ▼ SUPERVISOR_TOKEN (re-read per call)        │
│  ┌─ HA Supervisor (http://supervisor) ────────────────────────────────────────┐    │
│  │  /store/apps/local_test-addon/install                                     │    │
│  │  /apps/local_test-addon/{start,stop,options,options/validate,uninstall}   │    │
│  │  /jobs/{id}                                                               │    │
│  │                                                                          │    │
│  │  ┌── HA Backup integration ─────────────────────────────────────────────┐ │    │
│  │  │  Files under /data (incl. terraform.tfstate, bridge-token,         │ │    │
│  │  │  bridge-nonce-audit.json) are auto-included in                      │ │    │
│  │  │  `ha backups new --app terraform-bridge` (Phase 9 §10 spike)         │ │    │
│  │  └──────────────────────────────────────────────────────────────────────┘ │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                           │
│                                      ▼ Container creation from                    │
│  ┌─ local_test-addon container ──────────────────────────────────────────────┐    │
│  │  FROM ghcr.io/home-assistant/amd64-base:3.24                              │    │
│  │  run.sh = `sleep infinity` (no-op)                                        │    │
│  │  schema: log_level, dummy_setting (two string options)                    │    │
│  │  slug: local_test-addon                                                   │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
/share/development/homeassistant-addons/
├── tools/
│   ├── test-addon/                      # NEW (Phase 14, Plan 01)
│   │   ├── config.yaml                  # HA manifest: name, version 0.1.0-0, slug local_test-addon,
│   │   │                                #   arch amd64, schema {log_level: "str?", dummy_setting: "str?"},
│   │   │                                #   options {log_level: "info", dummy_setting: "default"}
│   │   ├── build.yaml                   # build_from.amd64 + args.VERSION 0.1.0
│   │   ├── Dockerfile                   # FROM ${BUILD_FROM}; COPY run.sh; CMD ["/run.sh"]
│   │   ├── run.sh                       # #!/usr/bin/with-contenv bashio; bashio::log.info; sleep infinity
│   │   └── README.md                    # 1-paragraph explanation: "this is the Phase 14 test target —
│   │                                    #   exists so the Provider can install/configure/start/stop/uninstall
│   │                                    #   without touching any real add-on on the host"
│   │
│   └── test-bridge-fixture/             # UNCHANGED (Phase 15 — CI fixture, NOT Phase 14's target)
│       ├── main.go                      # stdlib-only HTTP simulator for /v1/version
│       ├── go.mod
│       └── …                            # already exists per Phase 15
│
├── terraform-bridge/
│   ├── README.md                        # MODIFY (Phase 14, Plan 03, D-12): new 1-pager with
│   │                                    #   install / token / Tailscale-bind-gate / link to DOCS.md
│   ├── DOCS.md                          # MODIFY (Phase 14, Plan 03, D-13): expanded full operator
│   │                                    #   reference — Options, Token issuance/rotation/recovery,
│   │                                    #   Endpoints reference, Troubleshooting (cross-link to Provider
│   │                                    #   DOCS.md#troubleshooting-<code> per D-14), Observed issues
│   │                                    #   (3+ entries from real Phase 14 runs), State management,
│   │                                    #   HA backup integration
│   │
│   ├── internal/testdata/               # NEW (Phase 14, Plan 01 + 02)
│   │   ├── diagnostics/                 # captured per-error_code diagnostic bodies
│   │   │   ├── unauthorized.txt
│   │   │   ├── not_found.txt
│   │   │   ├── critical_addon_protected.txt
│   │   │   ├── prevented_destroy.txt
│   │   │   ├── already_installed.txt
│   │   │   ├── locked.txt
│   │   │   ├── nonce_expired.txt
│   │   │   ├── nonce_used.txt
│   │   │   ├── install_timeout.txt
│   │   │   ├── upstream_error.txt
│   │   │   ├── pwned.txt                # Phase 14 empirical discovery (Warning, not Error)
│   │   │   └── version.txt              # Provider-side handshake rejection
│   │   ├── apply-output/                # captured `tofu apply` output for SC-3 (5 iterations)
│   │   │   ├── 1.txt
│   │   │   ├── 2.txt
│   │   │   ├── 3.txt
│   │   │   ├── 4.txt
│   │   │   └── 5.txt
│   │   └── state-fingerprints/          # captured /v1/state/index before/after each scenario
│   │       ├── 00-happy-path-before.json
│   │       ├── 00-happy-path-after.json
│   │       └── …                        # one pair per scenario (D-17)
│   │
│   └── internal/                        # existing Phase 12 structure unchanged
│       ├── auth/                        # TokenStore (CF-01)
│       ├── httpapi/                     # router + handlers (BRIDGE-04..09)
│       ├── mutex/                       # per-slug mutex (STATE-03)
│       ├── nonce/                       # X-Force-Destroy (LIFE-03)
│       ├── state/                       # /v1/state/index (STATE-02)
│       ├── supervisor/                  # Client + V1/V2 fallback + MapError (BRIDGE-09)
│       └── logging/                     # scrubbing handler (AUTH-05)
│
├── internal/verify-bridge-e2e/          # NEW (Phase 14, Plan 01 + 02)
│   ├── _lib.sh                          # bearer token retrieval, snapshot discipline, jq wrappers
│   ├── 00-happy-path.sh                 # install → start → options → stop → uninstall, 5 iterations
│   ├── 01-unauthorized.sh               # curl /v1/version with WRONG bearer → expect 401 + error_code
│   ├── 02-not-found.sh                  # GET /v1/addons/nonexistent/info → expect 404 + error_code
│   ├── 03-critical-addon-protected.sh   # DELETE core_mosquitto (in critical_addons) → expect 403
│   ├── 04-prevented-destroy.sh          # tofu apply with lifecycle.prevent_destroy + manual destroy
│   ├── 05-already-installed.sh          # tofu apply twice in a row → second applies adoption (SC-1)
│   ├── 06-locked.sh                     # race two `tofu apply` against same slug → expect 423
│   ├── 07-nonce-expired.sh              # DELETE without fresh nonce → expect 401 + nonce_expired
│   ├── 08-nonce-used.sh                 # DELETE twice with same nonce → expect 401 + nonce_used on second
│   ├── 09-install-timeout.sh            # synthetic — skip with annotation (D-10)
│   ├── 10-upstream-error.sh             # curl with Bridge pointing at unreachable Supervisor URL → expect 502
│   ├── 11-pwned.sh                      # OPTIONS with a known-pwned secret → expect 200 + Provider WARNING
│   ├── 12-version-mismatch.sh           # downgrade Provider binary OR rotate Bridge schema_version → handshake fails
│   └── 99-cleanup.sh                    # separate manual invocation: uninstall test add-on,
│                                        #   leave nonce journal, remove *.tfstate.bak.* older than 7d
│
├── terraform-provider-homeassistant/    # UNCHANGED — Phase 13's output is the input
│   ├── DOCS.md                          # UNCHANGED — canonical target for per-error_code text (D-14)
│   ├── internal/diagnostics/            # UNCHANGED — source of truth for Summary text
│   └── …                                # all Phase 13 code is Phase 14's test surface
│
├── Makefile                              # UNCHANGED — `make install-provider` (Phase 15) installs the
│                                        #   binary that Phase 14's verify scripts invoke
│
└── repository.yaml                       # UNCHANGED — `tools/` is not in HA's add-on discovery path
```

### Pattern 1: Per-error_code verify script (mirrors `verify-bridge-no-token-leak.sh`)

**What:** One shell script per Bridge `error_code`, following the existing `internal/verify-bridge-no-token-leak.sh`
pattern (one assertion per PATTERN, exit-non-zero on failure, captured outputs to testdata file).

**When to use:** Every scenario in D-06.

**Example (01-unauthorized.sh):**

```bash
#!/usr/bin/env bash
# verify-bridge-e2e/01-unauthorized.sh — Phase 14 SC-4 + D-07:
# provoke 401 + error_code: unauthorized by hitting the Bridge with a
# bearer token that does NOT match /data/bridge-token.
#
# Mirrors internal/verify-bridge-no-token-leak.sh exit-gate discipline:
# exits non-zero if the captured diagnostic does not match the expected
# error_code.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

WRONG_TOKEN="phase-14-wrong-token-$(date +%s)-do-not-use-in-prod"

DIAGNOSTIC_FILE="${TESTDATA_DIR}/diagnostics/unauthorized.txt"

# Capture the response body verbatim to the per-error_code testdata file.
# -sS = silent (no progress bar) + show errors. -w "%{http_code}" prints
# the status code on a separate line for the assertion below.
HTTP_CODE=$(curl -sS -o "${DIAGNOSTIC_FILE}" -w "%{http_code}" \
    -H "Authorization: Bearer ${WRONG_TOKEN}" \
    "${BRIDGE_URL}/v1/version")

if [[ "${HTTP_CODE}" != "401" ]]; then
    printf '\033[0;31mFAIL: expected HTTP 401, got %s\033[0m\n' "${HTTP_CODE}" >&2
    cat "${DIAGNOSTIC_FILE}" >&2
    exit 1
fi

# Assert the captured body carries the expected error_code
if ! jq -e '.error_code == "unauthorized"' "${DIAGNOSTIC_FILE}" >/dev/null; then
    printf '\033[0;31mFAIL: body missing error_code=unauthorized\033[0m\n' >&2
    cat "${DIAGNOSTIC_FILE}" >&2
    exit 1
fi

green "01-unauthorized: PASS — captured diagnostic at ${DIAGNOSTIC_FILE}"
```

### Pattern 2: Five-iteration idempotency loop (`00-happy-path.sh`)

**What:** Run the same `tofu apply` against the test add-on FIVE times consecutively; iterations 2-5 must report "No
changes" (SC-3).

**When to use:** `00-happy-path.sh` (SC-3 gate).

**Example (00-happy-path.sh, sketch):**

```bash
#!/usr/bin/env bash
# verify-bridge-e2e/00-happy-path.sh — Phase 14 SC-1 + SC-3:
# install → start → options → stop → uninstall against local_test-addon,
# repeated FIVE times. Iterations 2-5 must report "No changes" for SC-3
# idempotency proof.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

# Snapshot state before the suite (D-16).
snapshot_state "00-happy-path"

# Five iterations. The `tofu plan` output is captured per iteration;
# the assertion below fails if any iteration after the first produces a
# non-empty diff.
for ITER in 1 2 3 4 5; do
    APPLY_OUTPUT="${TESTDATA_DIR}/apply-output/${ITER}.txt"
    yellow "── Iteration ${ITER} ──"
    tofu init -upgrade >/dev/null 2>&1 || true
    tofu apply -auto-approve 2>&1 | tee "${APPLY_OUTPUT}"
    if (( ITER > 1 )); then
        if grep -qE '^\s*[+\-]' "${APPLY_OUTPUT}" && ! grep -qE 'No changes' "${APPLY_OUTPUT}"; then
            printf '\033[0;31mFAIL: iteration %d produced unexpected diff\033[0m\n' "${ITER}" >&2
            exit 1
        fi
    fi
done

green "00-happy-path: PASS — 5 iterations, iterations 2-5 reported 'No changes'"
```

### Pattern 3: Cross-link DOCS.md anchor (mirrors Provider's `DocAnchor`)

**What:** Bridge DOCS.md's troubleshooting section points to Provider DOCS.md anchors like
`#troubleshooting-unauthorized` (the same anchor the Provider's `MapError` produces via `diagnostics.DocAnchor(code)`
per `terraform-provider-homeassistant/internal/diagnostics/doc.go:129-135`).

**When to use:** D-13 §6 (Troubleshooting) — single paragraph + the same anchor table format.

**Example (Bridge DOCS.md §6 anchor table):**

```markdown
## Troubleshooting

Every error the Bridge returns carries a machine-readable `error_code`. The
[terraform-provider-homeassistant DOCS.md#troubleshooting](../terraform-provider-homeassistant/DOCS.md#troubleshooting)
table is the single source of truth for what each code means, how the Provider surfaces it, and what the remediation is.
The Bridge DOCS.md does not duplicate the table — the Provider's per-error_code Summary text is written once and
consumed by both the Provider Diagnostic text and the cross-link anchor in this document.
```

### Anti-Patterns to Avoid

- **Auto-restarting the Bridge in a verify script.** Violates AGENTS.md Live Systems rule + CF-14 + D-02. If a scenario
  needs a fresh Bridge process (e.g. testing the one-shot `bridge.token.issued` line), it is an operator action between
  scenarios, not a script action.
- **Editing the live `critical_addons` list** to make a scenario pass. The list is operator-configured; the verify
  scripts assume the default `["core_mosquitto", "core_zigbee2mqtt", "core_esphome"]` and only exercise those slugs (not
  the test add-on). Per CF-12.
- **Writing the `error_code` text directly in the Bridge DOCS.md troubleshooting section.** The Provider DOCS.md is the
  canonical source (D-14). Drift between Bridge DOCS.md and Provider DOCS.md breaks the cross-link guarantee.
- **Capturing the diagnostic with `jq` formatting rather than verbatim.** The Provider's `Detail` field carries the
  `request_id` + DOCS.md anchor + `bridge_message` + `bridge_status` lines; `jq -e` for the `error_code` assertion but
  `tee` (not `jq .`) for the captured file.
- **Running the 12 scenarios in a single shell script with `set -e`.** A failure of scenario 4 should not prevent
  scenario 5 from running — each scenario is a per-scenario shell script with its own exit code (D-06 per-scenario
  discipline).

## Don't Hand-Roll

| Problem                                                  | Don't Build                                 | Use Instead                                                                                                                                                                                 | Why                                                                                                                                                                                                                            |
| -------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Bearer token retrieval from `/data/initial-token`        | Custom SSH wrapper + `cat`                  | `ssh ha-nextgen cat /usr/share/hassio/addons/data/terraform-bridge/initial-token` (per CONTEXT.md D-08)                                                                                     | Already documented in `terraform-bridge/DOCS.md:50-54`; the canonical operator path is documented; verify scripts reuse it                                                                                                     |
| State snapshot before destructive scenario               | `git`-style versioned state file            | `ssh ha-nextgen cp /data/terraform.tfstate /data/terraform.tfstate.bak.<scenario>` (D-16)                                                                                                   | Plain `cp` is enough; the snapshot is restored via `mv` if a scenario botches the destroy. No new persistence primitive is needed.                                                                                             |
| State fingerprint before/after scenario                  | Custom SHA-256 walker over `/data`          | `GET /v1/state/index` (Phase 12 D-20..D-23) — Bridge endpoint that enumerates `*.tfstate` + `*.tfstate.backup` with their SHA-256 digests                                                   | The endpoint exists for exactly this purpose (STATE-02); verify scripts call it via curl with bearer auth                                                                                                                      |
| `error_code` → Provider Diagnostic Summary text mapping  | Bridge-side custom table in `_lib.sh`       | The Provider's `diagnostics.DocAnchor(code)` (`terraform-provider-homeassistant/internal/diagnostics/doc.go:129-135`) — kebab-case URL fragment like `DOCS.md#troubleshooting-unauthorized` | Bridge DOCS.md cross-links to those anchors (D-14); the verify scripts' captured diagnostics are the SOURCE that the Provider DOCS.md's text was generated from (Phase 13 D-08 + doc.go constants) — round-trip is intentional |
| `/v1/auth/nonce` issuance for destructive ops            | Hand-rolled X-Force-Destroy header in shell | `curl -X POST -H "Authorization: Bearer $TOKEN" "$BRIDGE_URL/v1/auth/nonce"` (per `terraform-bridge/DOCS.md:75-86`)                                                                         | Already documented; the nonce + X-Force-Destroy flow is the canonical pattern. Verify scripts reuse it.                                                                                                                        |
| Provider installation for `tofu apply`                   | `go build` + manual binary copy             | `make install-provider` (Phase 15, TOFU-04) — the Makefile target + `verify-install-provider.sh` hermetic verifier (Phase 15 Plan 02)                                                       | Phase 15 owns the install workflow. Phase 14 ASSUMES the binary is already installed; the operator runs `make install-provider` once before the verify suite.                                                                  |
| HA backup creation with `addon_config:rw` coverage proof | `tar` over `/data` then verify file         | `ha backups new --app terraform-bridge` (per `internal/spike-pitfalls10-backup-addon-config.sh` Phase 9 §10 spike)                                                                          | The spike script is the canonical operator path; Phase 14 re-runs it for the empirical STATE-02 backup integration demonstration (D-13 §9)                                                                                     |

**Key insight:** Phase 14 is the LAST phase of v1.3 that needs to build anything new; it's primarily verification +
documentation. The only "new code" is the test add-on (a 4-file minimal HA add-on that mirrors the existing add-on
pattern) + the verify scripts (mirroring `verify-bridge-no-token-leak.sh`). Everything else is exercised, captured, and
documented.

## Runtime State Inventory

> Required for rename / refactor / migration phases only. **Phase 14 is NOT a refactor / migration phase.** It does not
> change Bridge code, Provider code, or any persistent state file format. It adds NEW artifacts (the test add-on +
> verify scripts + diagnostic captures), which are git-committed and have no runtime counterpart.

| Category             | Items Found                                                                                                                                                                                                                                                                                                                                                                                 | Action Required                                            |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| Stored data          | **Nothing Phase-14-owned.** The Bridge's `/data` contents (`bridge-token`, `initial-token`, `bridge-token.grace`, `bridge-nonce-audit.json`, `terraform.tfstate`) are Phase 9/10/12/13 artifacts; Phase 14 only READS them (via `_lib.sh` bearer token retrieval + `GET /v1/state/index`) and TEMPORARILY SNAPSHOTS `terraform.tfstate` to `*.tfstate.bak.<scenario>` (D-16). No migration. | None — read-only + temporary snapshot only.                |
| Live service config  | **Nothing.** The Bridge's running config (`bind_address`, `critical_addons`, etc.) is Phase 12's output; Phase 14 does not modify it. The test add-on is installed/uninstalled as part of the verify suite — that's lifecycle, not config drift. The Provider's `endpoint` + `bearer_token` are operator-invoked `tofu` arguments, not stored state.                                        | None.                                                      |
| OS-registered state  | **Nothing.** No Task Scheduler entries, no systemd units, no pm2 processes reference Phase 14 artifacts. The Bridge's running process on `ha-nextgen` is Phase 9's output; the test add-on's container is Supervisor-managed and short-lived (installed + uninstalled within a scenario).                                                                                                   | None.                                                      |
| Secrets and env vars | **Nothing new.** Phase 14 uses `BRIDGE_URL` (env or `_lib.sh` constant) + the bearer token read from `/data/initial-token` (already covered by CF-02). The test add-on has no secrets.                                                                                                                                                                                                      | None.                                                      |
| Build artifacts      | `tools/test-addon/` (NEW, Phase 14 Plan 01) — Docker build artifact `local/local_test-addon:0.1.0` is rebuilt on every scenario that touches the test add-on. Lives in the host's Docker image cache (`docker images`); cleaned up by `99-cleanup.sh` uninstall step + `docker rmi local/local_test-addon:0.1.0`. No `*.egg-info/` (this is a Docker add-on, not a Python package).         | `99-cleanup.sh` uninstalls the add-on + removes the image. |

**Nothing found in category:** Stored data, Live service config, OS-registered state, Secrets and env vars — all
explicitly empty for Phase 14. The phase does not rename, migrate, or refactor anything; it verifies existing behavior +
writes new documentation.

## Common Pitfalls

### Pitfall 1: Verifying against an out-of-date Provider binary

**What goes wrong:** Phase 13's Provider has been rebuilt since the last `make install-provider` ran. The verify scripts
capture diagnostics against an older Provider version; the Provider DOCS.md#troubleshooting anchors may have shifted in
the rebuild.

**Why it happens:** Provider + Bridge + Makefile iteration are decoupled. A new `go build` does NOT auto-install.

**How to avoid:** Before the verify suite, the operator runs `make install-provider` AND
`bash internal/verify-install-provider.sh` to confirm the binary is current. Add this to `00-happy-path.sh` as a
pre-flight assertion (`command -v tofu` + `terraform-provider-homeassistant/terraform-provider-homeassistant` exists).

**Warning signs:** Scenario `05-already-installed.sh` reports a different Provider Diagnostic Summary text than the
Provider DOCS.md#troubleshooting-already-installed anchor references; or the `request_id` in the captured diagnostic
does not match the Bridge log.

### Pitfall 2: Forgetting to rebuild the test add-on before scenarios

**What goes wrong:** The operator edits `tools/test-addon/config.yaml` to add a new option, but `ha addons reload` does
not pick up the change because the image is cached. Scenario `00-happy-path.sh` iterates 5 times against an image that
lacks the new schema.

**Why it happens:** HA Supervisor's local add-on store caches the built image; `ha addons reload` refreshes the add-on
metadata but does not always trigger a rebuild.

**How to avoid:** Each scenario that depends on a schema change runs
`docker build -t local/local_test-addon:0.1.0 tools/test-addon/` explicitly, then `ha addons reload`. The script header
documents this prerequisite. Alternative: `ha addons rebuild local_test-addon` triggers HA's own local-build pipeline.

**Warning signs:** Supervisor reports `slug not found` for the test add-on despite it being listed in the add-on store;
or the Provider's `options` write returns `unknown_option`.

### Pitfall 3: The Bridge restart happens at scenario 10, breaking the auth chain

**What goes wrong:** A scenario (intentionally or accidentally) causes the Bridge to exit or restart. The bearer token
in the verify script's `_lib.sh` becomes stale (Phase 10 D-12: rotation requires existing bearer; loss =
uninstall/reinstall). Subsequent scenarios fail with `401 unauthorized` for reasons that look like Provider bugs but are
actually auth-state issues.

**Why it happens:** Per CF-14 + D-02, Bridge restarts are operator-initiated, not script-initiated. If the operator
restarts the Bridge mid-suite, the verify scripts need to re-fetch `/data/initial-token` from the host and re-source
`_lib.sh`.

**How to avoid:** Every scenario script checks for Bridge liveness at start (`curl -sS $BRIDGE_URL/healthz` returns
200); if it doesn't, the script exits 0 with a "skipped — Bridge not running" annotation (per D-10 pattern). The
operator is then in the loop: restart Bridge if needed, re-fetch token, re-run.

**Warning signs:** `bridge.token.issued` reappears in the Bridge log (signal that the Bridge restarted and re-emitted
the one-shot token line — Phase 10 D-08 invariant that exactly-once becomes a problem if the Bridge restarted
mid-suite).

### Pitfall 4: The test add-on accidentally gets added to `critical_addons`

**What goes wrong:** Operator temporarily adds `local_test-addon` to the Bridge's `critical_addons` to test the 403 path
with the actual test add-on (instead of `core_mosquitto`). Subsequent scenarios that try to uninstall the test add-on
see `403 critical_addon_protected` instead of `204`.

**Why it happens:** Scenario 03-crit-addon-protected.sh naturally invites the operator to use the test add-on as the
"victim slug" — but the test add-on is also the SCRIPTS' install/uninstall target, so it must remain mutable.

**How to avoid:** Scenario 03 uses `core_mosquitto` (or another always-on critical slug) as the victim, NOT the test
add-on. The scenario header documents "DO NOT modify `critical_addons` to include `local_test-addon` — the verify
scripts need to uninstall it between iterations".

**Warning signs:** Scenario 00-happy-path.sh iteration 1 succeeds (install), iteration 5 uninstall returns 403
critical_addon_protected.

### Pitfall 5: Markdown lint failures on the expanded DOCS.md block the merge

**What goes wrong:** Phase 14's DOCS.md expansion adds 200+ lines. Some long code blocks exceed the 120-char limit.
Markdownlint-cli2 (Phase 10 D-08) catches them in pre-commit; the operator is forced to either reformat or disable MD013
for the file. The repo's `.markdownlint.json` enforces MD013 strictly.

**Why it happens:** Markdown table rows with long URL paths or long inline JSON examples blow past 120 chars.

**How to avoid:** Plan 03 includes `pre-commit run --files terraform-bridge/README.md terraform-bridge/DOCS.md` in the
verification step (D-15). Long URLs go in fenced code blocks (which are also subject to MD013 but easier to wrap). Long
inline references use the `[text][anchor]` pattern with the anchor defined at the bottom of the file (saves a few chars
per inline reference).

**Warning signs:** `pre-commit run --files terraform-bridge/DOCS.md` exits 1 with MD013 violations; CI fails the same
way.

### Pitfall 6: State snapshot restored overwrites the canonical state file with stale data

**What goes wrong:** Scenario 06-locked.sh snapshots the state, then a botched two-write race produces a partial state
file. The operator restores from `terraform.tfstate.bak.06-locked`, but that backup was taken BEFORE the current
`tofu apply`, so the resource tracking is now off by one resource — the next `tofu plan` reports a "phantom" diff
(resources it thinks exist don't).

**Why it happens:** The snapshot is the pre-scenario state, not the desired post-scenario state. Restoring from it is
the correct recovery for a botched destroy, but for a botched UPDATE it leaves the state older than the actual host
state.

**How to avoid:** D-17 fingerprints (`GET /v1/state/index` before + after) let the operator detect the discrepancy. If
the fingerprint diff is non-zero AND a snapshot restore was performed, the operator runs `tofu refresh` to reconcile
state with the actual host state. The scenario script header documents this recovery path explicitly.

**Warning signs:** `GET /v1/state/index` fingerprint diff between before and after is non-zero; the resource appears in
state but `GET /v1/addons/{slug}/info` returns 200 with a different state attribute than state captured.

### Pitfall 7: The 5-iteration idempotency loop breaks on Provider's `lifecycle.prevent_destroy = true`

**What goes wrong:** The operator includes `lifecycle.prevent_destroy = true` in the test `*.tf` (per Provider DOCS.md
example). Iteration 1 installs; iteration 5 tries to destroy as part of `tofu destroy` (or `tofu apply -destroy`) but
the lifecycle guard blocks it with a typed `prevented_destroy` diagnostic. The 5-iteration loop fails at the destroy
step.

**Why it happens:** Phase 14's happy-path scenario (D-06 + D-11) is install → start → options → stop → uninstall. The
"uninstall" step is implicit in the loop: each iteration tears down the previous one and re-installs. With
`prevent_destroy = true`, the tear-down fails.

**How to avoid:** The happy-path `*.tf` does NOT set `lifecycle.prevent_destroy = true`. The default
`prevent_destroy = true` recommendation (CF-09) is for PRODUCTION add-ons; the test add-on is intentionally destroyable.
The happy-path scenario explicitly comments out the `prevent_destroy = true` line in its embedded `*.tf`. Scenario
`04-prevented-destroy.sh` is the only scenario where `lifecycle.prevent_destroy = true` is in effect, and that scenario
exercises the diagnostic path, not the destroy.

**Warning signs:** Scenario 00-happy-path.sh iteration 5 fails with `prevented_destroy` instead of `No changes`.

## Code Examples

### Example 1: `_lib.sh` skeleton (token retrieval + state snapshot + fingerprint)

```bash
#!/usr/bin/env bash
# _lib.sh — Phase 14 verify-scenario helper. Sources once per scenario
# (via `. ${SCRIPT_DIR}/_lib.sh`). Provides:
#   • BRIDGE_URL + TOKEN + TEST_ADDON_SLUG constants
#   • snapshot_state() — D-16 /data/terraform.tfstate backup
#   • fingerprint_state() — D-17 GET /v1/state/index before/after
#   • cleanup_scenario_baks() — removes >7d old *.tfstate.bak.<scenario>
#
# Every scenario uses `set -euo pipefail` (the standard pattern from
# internal/verify-bridge-no-token-leak.sh).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TESTDATA_DIR="${REPO_ROOT}/terraform-bridge/internal/testdata"

# Host identity — D-01: ha-nextgen IS haos-op3050-1. Operator overrides
# BRIDGE_HOST env var to choose which hostname to reach.
BRIDGE_HOST="${BRIDGE_HOST:-ha-nextgen.akentner.ts.net}"
BRIDGE_PORT="${BRIDGE_PORT:-8124}"
BRIDGE_URL="https://${BRIDGE_HOST}:${BRIDGE_PORT}"

# Test add-on — D-05: slug is `local_test-addon`.
TEST_ADDON_SLUG="local_test-addon"

# Bearer token — D-08: read from /data/initial-token via SSH. Operator
# may override via BRIDGE_TOKEN env var (e.g. when the Bridge was
# restarted mid-suite and the operator manually rotated).
if [[ -z "${BRIDGE_TOKEN:-}" ]]; then
    BRIDGE_TOKEN=$(ssh "${BRIDGE_HOST%.akentner.ts.net}" \
        "cat /usr/share/hassio/addons/data/terraform-bridge/initial-token" 2>/dev/null \
        | tr -d '\n')
    if [[ -z "${BRIDGE_TOKEN}" ]]; then
        printf '\033[0;31mFATAL: cannot read /data/initial-token from %s\033[0m\n' \
            "${BRIDGE_HOST}" >&2
        printf 'Either set BRIDGE_TOKEN env var or SSH to %s and confirm\n' \
            "${BRIDGE_HOST}" >&2
        printf 'the file exists (cat /usr/share/hassio/addons/data/terraform-bridge/initial-token).\n' >&2
        exit 2
    fi
fi

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }

# snapshot_state — D-16. Copies /data/terraform.tfstate to a
# per-scenario .bak file so a botched destroy is recoverable.
snapshot_state() {
    local scenario="$1"
    local bak_path="/data/terraform.tfstate.bak.${scenario}"
    ssh "${BRIDGE_HOST%.akentner.ts.net}" \
        "test -f /data/terraform.tfstate && cp /data/terraform.tfstate ${bak_path} || true" \
        2>/dev/null || true
}

# fingerprint_state — D-17. Calls GET /v1/state/index and logs the
# response to <scenario>-before/after JSON files.
fingerprint_state() {
    local scenario="$1"
    local when="$2"  # "before" or "after"
    local out_dir="${TESTDATA_DIR}/state-fingerprints"
    mkdir -p "${out_dir}"
    curl -sS \
        -H "Authorization: Bearer ${BRIDGE_TOKEN}" \
        "${BRIDGE_URL}/v1/state/index" \
        > "${out_dir}/${scenario}-${when}.json"
}

# cleanup_scenario_baks — D-18. Removes *.tfstate.bak.* files older than
# 7 days. Called by 99-cleanup.sh, not by individual scenarios.
cleanup_scenario_baks() {
    ssh "${BRIDGE_HOST%.akentner.ts.net}" \
        "find /data -maxdepth 1 -name 'terraform.tfstate.bak.*' -mtime +7 -delete" \
        2>/dev/null || true
}
```

### Example 2: 12-pwned.sh — Warning severity (the only Warning in the diagnostic map)

```bash
#!/usr/bin/env bash
# 11-pwned.sh — Phase 14 SC-4 + CF-08 empirical:
# the Bridge surfaces a `pwned: true` advisory when an add-on's
# options payload contains a known compromised-credentials leak;
# the Provider surfaces this as a WARNING (NOT an error) so the
# apply proceeds while the operator is informed.
#
# Per terraform-provider-homeassistant/internal/diagnostics/doc.go:111
# `PwnedWarningText` is the canonical Summary text:
#   "This add-on has a known compromised credentials leak (pwned):
#    review the supervisor warning and rotate the add-on credentials
#    before continuing."
#
# The actual `tofu apply` still SUCCEEDS — this scenario's assertion
# is that the Bridge's response body carries a top-level `pwned: true`
# field AND the Provider emits a Warning diagnostic.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

DIAGNOSTIC_FILE="${TESTDATA_DIR}/diagnostics/pwned.txt"
APPLY_OUTPUT=$(mktemp)

# `dummy_setting: "P@ssw0rd"` is a known pwned-secret value (per
# HIBP — see https://haveibeenpwned.com/Passwords). The Supervisor's
# /options/validate endpoint flags it. The Provider surfaces a
# Warning diagnostic; the apply still succeeds.
cat > /tmp/11-pwned.tf <<'EOF'
terraform {
  required_providers {
    homeassistant = {
      source = "registry.opentofu.org/akentner/homeassistant"
    }
  }
}

provider "homeassistant" {
  endpoint     = var.bridge_url
  bearer_token = var.bridge_token
}

resource "homeassistant_addon" "test_pwned" {
  slug = "local_test-addon"
  options = {
    dummy_setting = "P@ssw0rd"
  }
  start = true

  lifecycle {
    prevent_destroy = true
  }
}

variable "bridge_url"  { type = string }
variable "bridge_token" { type = string, sensitive = true }
EOF

# Run tofu apply. Capture the FULL output (apply still succeeds;
# the pwned advisory is a WARNING, not an error).
tofu apply -auto-approve -var "bridge_url=${BRIDGE_URL}" \
    -var "bridge_token=${BRIDGE_TOKEN}" 2>&1 | tee "${APPLY_OUTPUT}"
tofu_exit=$?

# Assert: exit 0 (apply succeeded despite the pwned warning).
if (( tofu_exit != 0 )); then
    red "FAIL: tofu apply exited ${tofu_exit}; expected 0 (pwned is a Warning, not Error)"
    cat "${APPLY_OUTPUT}"
    exit 1
fi

# Assert: output carries the canonical Warning Summary text.
if ! grep -qF "known compromised credentials leak (pwned)" "${APPLY_OUTPUT}"; then
    red "FAIL: output missing the pwned warning Summary text"
    cat "${APPLY_OUTPUT}"
    exit 1
fi

# Capture the Bridge response body (the JSON returned by
# POST /v1/addons/{slug}/options). The Bridge surfaces a
# `pwned: true` advisory envelope; the Provider translates that
# into the Warning.
BRIDGE_RESPONSE=$(curl -sS \
    -H "Authorization: Bearer ${BRIDGE_TOKEN}" \
    -H "Content-Type: application/json" \
    -X POST \
    -d '{"dummy_setting":"P@ssw0rd"}' \
    "${BRIDGE_URL}/v1/addons/${TEST_ADDON_SLUG}/options")
echo "${BRIDGE_RESPONSE}" | jq '.' > "${DIAGNOSTIC_FILE}"

if ! jq -e '.pwned == true' "${DIAGNOSTIC_FILE}" >/dev/null; then
    red "FAIL: Bridge response missing top-level pwned=true"
    cat "${DIAGNOSTIC_FILE}"
    exit 1
fi

green "11-pwned: PASS — Bridge surfaced pwned=true; Provider emitted Warning; apply succeeded"
rm -f "${APPLY_OUTPUT}"
```

### Example 3: Per-`error_code` testdata file format (DOCS.md input)

After `01-unauthorized.sh` runs against the live Bridge, the captured diagnostic file
`terraform-bridge/internal/testdata/diagnostics/unauthorized.txt` looks like:

```json
{
  "error_code": "unauthorized",
  "request_id": "abc123def456"
}
```

The DOCS.md troubleshooting cross-link table in Provider DOCS.md#troubleshooting-unauthorized references this exact
shape. Phase 14's empirical confirmation: the captured file matches what Phase 13's Provider Diagnostic Summary text
(`ErrUnauthorizedText` in `doc.go:43`) describes. If they ever drift, D-09 says: fix the docs to match observation.

## State of the Art

| Old Approach                                                     | Current Approach                                                                                                                            | When Changed                                                           | Impact                                                                                                                                                                                                                                                                                                                                                                               |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Unit-test-only verification of Bridge endpoints                  | Per-scenario shell scripts against the live HA host                                                                                         | Phase 14 (this phase)                                                  | Empirical confirmation that the typed `error_code` mapping actually surfaces under real conditions (network latency, Supervisor job queueing, Tailscale bind latency). Unit tests cannot catch "the Bridge returns 401 instead of 423 when the host clock is 30 seconds behind the Bridge clock".                                                                                    |
| Documentation written from unit-test expectations                | Documentation written from captured empirical diagnostics                                                                                   | Phase 14 (this phase, D-09)                                            | The `request_id` field in the Provider Diagnostic Detail is actually present in real Bridge responses (Phase 13 was confident; Phase 14 confirms). If absent, D-09 says: fix the docs (or the code).                                                                                                                                                                                 |
| Hermetic CI-only end-to-end via `test-bridge-fixture` (Phase 15) | Live-HA end-to-end via `verify-bridge-e2e/` + purpose-built test add-on                                                                     | Phase 14 (this phase); Phase 15 retains CI fixture for the CI pipeline | The Bridge's `SUPERVISOR_TOKEN` re-read-per-call pattern (Phase 10 `internal/supervisor/client.go:84-91`) was exercised in production for the first time during Phase 9's H-1 spike. Phase 14 expands that empirical footprint to the full HTTP surface.                                                                                                                             |
| Bridge-only docs (Phase 9-13)                                    | Full Bridge operator reference (install + token + endpoints + troubleshooting + observed issues + state management + HA backup integration) | Phase 14 (D-12 + D-13)                                                 | The OPS-04 requirement ("install steps via HA add-on store, token issuance + rotation procedure, OpenTofu provider install command, an example `*.tf` file covering every resource attribute, every error code with documented remediation, and a troubleshooting section with at least three real observed issues") is the FIRST time the Bridge has a complete operator reference. |

**Deprecated/outdated:**

- **`internal/spike-h1-token-rotation.sh` (Phase 9):** Captured the SUPERVISOR_TOKEN rotation behavior. Now superseded
  by Phase 14's empirical token rotation test (CONTEXT.md Specifics: "Phase 14 should deliberately rotate the bearer
  token"). The Phase 9 spike script is left in place as historical evidence (per STATE.md todo: "Do NOT re-run during
  normal operation"). Phase 14's token rotation test is documented in Bridge DOCS.md §3 (Token rotation) as the
  canonical empirical source going forward.
- **`internal/spike-pitfalls10-backup-addon-config.sh` (Phase 9):** Captured the HA backup + `addon_config:rw`
  integration. Phase 14's empirical STATE-02 backup integration test (per CONTEXT.md Specifics) re-runs the scenario for
  the Bridge add-on specifically. The Phase 9 spike was against `phone-logger`; Phase 14 is against `terraform-bridge`.
  The Phase 9 spike transcript remains in `spike-transcripts/` as historical evidence.

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this section to identify
> decisions that need user confirmation before execution.

| #   | Claim                                                                                                                                                                                                                                             | Section                                                | Risk if Wrong                                                                                                                                                                                                                                                                                                      |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| A1  | The Bridge on `ha-nextgen` is currently running v0.2.0-0 (matching `terraform-bridge/config.yaml` and `terraform-bridge/build.yaml`); the Bearer token has been generated and lives at `/data/initial-token`.                                     | Environment Availability / D-08                        | If the Bridge is not running, every scenario fails with connection-refused errors. The operator needs to verify Bridge liveness (`curl -sS https://ha-nextgen.akentner.ts.net:8124/healthz`) before invoking the verify suite.                                                                                     |
| A2  | The Provider binary built by Phase 13 is at `terraform-provider-homeassistant/terraform-provider-homeassistant` (per `make install-provider` in Phase 15). The `dev_overrides` block in `~/.terraformrc` is already configured.                   | Common Pitfalls / Pattern 1                            | If the binary is stale, the Provider Diagnostic Summary text may not match the Provider DOCS.md#troubleshooting anchors (Pitfall 1). The operator runs `make install-provider` once before the suite.                                                                                                              |
| A3  | The host `haos-op3050-1` does not have `local_test-addon` pre-installed (Phase 14 is the first time it is created).                                                                                                                               | Scenario design (D-03..D-05)                           | If pre-installed, scenario 00-happy-path.sh iteration 1 adopts rather than installs (PROV-05 adoption-aware Create path) — the iteration still succeeds, but the captured diagnostic text differs slightly.                                                                                                        |
| A4  | `bind_address` on the running Bridge is `auto` (default) — the Bridge detects the Tailscale IP at startup. Tailscale hostname `ha-nextgen.akentner.ts.net:8124` resolves to the Bridge's bind address.                                            | Architectural Responsibility Map / Bridge connectivity | If `bind_address` is misconfigured (e.g. operator overrode it for a Phase 10 test and forgot to restore), the Tailscale hostname path fails and the operator must use LAN IP `192.168.178.3:8124`. The scenario script's `BRIDGE_HOST` env override handles this.                                                  |
| A5  | The `critical_addons` default list `["core_mosquitto", "core_zigbee2mqtt", "core_esphome"]` is unchanged from Phase 12 — those three slugs are the victim targets for scenario 03.                                                                | Pitfall 4 / Scenario 03                                | If the operator customized `critical_addons` (e.g. added `local_test-addon` for testing), scenario 03 fails because the test add-on is no longer uninstallable. Scenario 03's header documents "do not modify `critical_addons`".                                                                                  |
| A6  | OpenTofu ≥ 1.12 is installed on the operator workstation and `make install-provider` (Phase 15) has been run.                                                                                                                                     | Standard Stack / D-08 / Common Pitfalls 1              | If OpenTofu is missing or the Provider is not installed, every `tofu apply`-based scenario (00, 04, 05, 06, 11) fails. The pre-flight assertion in 00-happy-path.sh documents the prerequisite.                                                                                                                    |
| A7  | The Bridge's `/v1/healthz` response body is unchanged from Phase 10 D-08 — 200 OK + JSON body on success, 503 with empty body on Supervisor unreachable. Empirical observation in Phase 14 confirms this; DOCS.md §update is a no-op.             | D-12 agent's discretion / D-13 §1                      | If the Bridge's `/healthz` body shape changed (e.g. added a field), DOCS.md §"Health check" needs an update. The scenario scripts do not assert on `/healthz` body shape — only on status code (200 vs 503).                                                                                                       |
| A8  | The Bridge's `pwned` advisory surface (Phase 13 CF-08 + doc.go PwnedWarningText) is actually triggered when the test add-on's options contain a known-compromised secret. Phase 14's scenario 11 is the FIRST time this is empirically confirmed. | Scenario 11 / Common Pitfalls / D-09                   | If the Bridge's `pwned` flag never fires (e.g. Supervisor's `/options/validate` doesn't actually call the breach corpus), scenario 11 exits non-zero with "Bridge response missing top-level pwned=true" and the captured testdata file gets annotated `[not empirically observed — synthetic scenario]` per D-10. |
| A9  | The Bridge's `/v1/state/index` endpoint is reachable from the verify script's workstation and returns a JSON `files` array (not `[]`). The test add-on is not running before scenario 00, so the `*.tfstate` file is not yet present.             | D-17 fingerprint pattern / STATE-02 coverage           | If `/v1/state/index` returns empty `files: []` on first call (before any state file exists), scenario 00's pre-fingerprint is `{"files":[]}` — the post-fingerprint after `tofu apply` is `{"files":[{"name":"terraform.tfstate","size_bytes":N,"sha256":"..."}]}`. The diff is detectable.                        |
| A10 | The Bridge's `/v1/addons/{slug}/install` returns the post-install `AddOnInfo` payload as 200 + JSON (not 204). Per Phase 12 D-17, the polling loop returns the final `apps/{slug}/info` payload to the caller — NOT a 204.                        | Common Pitfall 7 / Provider adoption                   | If the Bridge returned 204 instead of 200+payload, the Provider's PostAddonInstall would still treat it as success (no body), but the captured diagnostic file for the happy-path iteration would be empty. The scenario asserts on captured output.                                                               |

**If this table is empty:** All claims above would have been verified by reading Bridge/Provider source code; the
`[ASSUMED]` tag is reserved for claims about runtime state on `ha-nextgen` that this research cannot directly verify
from the executor environment. None of A1..A10 require a `[VERIFIED]` tag because each is either an obvious operator
prerequisite (A1, A2, A4, A6) or a documented Phase 14 fallback (A8 — D-10's synthetic scenario annotation handles the
empirical-miss case).

## Open Questions

1. **Does the Bridge's `pwned` advisory actually fire end-to-end?**
   - What we know: Phase 13 CF-08 wires `PwnedWarningText` into the Provider Diagnostic Warning path; the Bridge calls
     Supervisor's `/apps/{slug}/options/validate` (Phase 12 BRIDGE-08 + `supervisor/client.go:560-622`) which surfaces
     `valid + pwned`.
   - What's unclear: Does the live Supervisor on `ha-nextgen` actually call the breach corpus for `pwned` detection?
     Some HA versions have this flag disabled by default.
   - Recommendation: Scenario 11 is the empirical check. If it fails, annotate the captured testdata file
     `[not empirically observed — synthetic scenario]` per D-10 + DOCS.md §11 entry.

2. **What does `tofu plan` output look like across 5 consecutive iterations of the same `*.tf`?**
   - What we know: The Provider's `UseStateForUnknown()` (PROV-10) suppresses spurious diffs on the `state` attribute;
     the `Read` is idempotent (PROV-04); the `Create` is adoption-aware (PROV-05).
   - What's unclear: Does OpenTofu print "No changes" or "Your infrastructure matches the configuration" or some other
     wording? The exact phrase matters for the scenario 00 assertion (`grep -qE 'No changes'`).
   - Recommendation: Run iteration 1, capture the actual `tofu plan` output, write the assertion around the observed
     wording. Phase 14 is empirical — the assertion follows observation, not the other way around.

3. **Does the Provider's `lifecycle.prevent_destroy = true` recommendation in DOCS.md examples interfere with the
   happy-path scenario?**
   - What we know: CF-09 + Provider DOCS.md line 329 recommend `prevent_destroy = true` as the default. Phase 14
     scenario 00 iterates install → start → options → stop → uninstall FIVE times. Iteration 5 uninstalls iteration 4's
     install.
   - What's unclear: Does iteration 5 need an explicit `tofu destroy` between iterations, or does the next iteration's
     `tofu apply` reconcile via adoption?
   - Recommendation: Use Provider's adoption-aware Create flow (PROV-05) — `tofu apply` with a `slug` that already
     exists adopts rather than reinstalls. Iteration 5 effectively becomes "iteration 5 installs the same add-on
     (adopts), starts it, applies options, stops it, no-op on uninstall". The test add-on stays installed across all 5
     iterations; `tofu apply` reports "No changes" after iteration 1.

## Environment Availability

> Probes for Phase 14's external dependencies. The phase exercises the Bridge running on `ha-nextgen` (LAN/Tailscale) +
> the Provider binary built by Phase 13 + the test add-on's Docker image. The executor workstation needs the host SSH
> access + `tofu` + `curl` + `jq`. The Bridge host needs Docker + Supervisor + `local_test-addon` published via the
> local-build pipeline.

| Dependency                                                                                                       | Required By                                                                                                | Available                                          | Version                                                                                                                                                                                                    | Fallback                                                                                                                                                           |
| ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `terraform-bridge` add-on (running on `ha-nextgen`)                                                              | All scenarios — Bridge is the live endpoint                                                                | ✓                                                  | v0.2.0-0 (per `terraform-bridge/config.yaml` line 3)                                                                                                                                                       | If not running, the operator starts it via the HA add-on store UI before invoking the suite.                                                                       |
| Bearer token in `/data/initial-token` on the Bridge host                                                         | D-08 token retrieval; every authenticated curl + every `tofu apply`                                        | ✓ (assumed)                                        | One-shot plaintext at `/data/initial-token` (chmod 600) on `ha-nextgen`                                                                                                                                    | If lost, operator runs uninstall + reinstall of the Bridge (Phase 10 recovery flow) — destructive but documented in DOCS.md §"Token recovery".                     |
| `terraform-provider-homeassistant` binary at `terraform-provider-homeassistant/terraform-provider-homeassistant` | Scenario 00, 04, 05, 06, 11 (Provider-driven `tofu apply`)                                                 | ✓ (assumed)                                        | v0.2.0 (per `terraform-provider-homeassistant/build.yaml` line 1)                                                                                                                                          | If stale, operator runs `make install-provider` (Phase 15 Makefile target) before the suite.                                                                       |
| `tofu` binary (OpenTofu) on the executor workstation                                                             | Every Provider-driven scenario                                                                             | ✓ (assumed on operator workstation)                | ≥ 1.12 (per PROV-01)                                                                                                                                                                                       | If missing, install per https://opentofu.org/docs/intro/install/. No CI/Phase 14 alternative.                                                                      |
| `curl` on the executor workstation                                                                               | All scenarios — bearer-authenticated HTTP to Bridge                                                        | ✓                                                  | system curl (8.x)                                                                                                                                                                                          | None — curl is a standard Linux tool.                                                                                                                              |
| `jq` on the executor workstation                                                                                 | All scenarios — JSON parsing + assertions                                                                  | ✓                                                  | jq-1.6 (verified via `command -v jq` this session)                                                                                                                                                         | If missing, install via package manager.                                                                                                                           |
| `ssh` on the executor workstation                                                                                | D-08 + D-16 + D-17 — host file access (token + state snapshot + fingerprint)                               | ✓                                                  | system ssh (verified this session)                                                                                                                                                                         | If host access is unavailable, the operator runs the verify scripts on the host itself (Tailscale SSH into `ha-nextgen` and run the scripts there).                |
| `docker` on the executor workstation (or on the Bridge host)                                                     | Scenario 02 / 03 / 11 may trigger Bridge image redeploys between iterations (operator-initiated per CF-14) | ✓ (assumed on host; this environment lacks docker) | Verified `command -v docker` returns no docker on this session's environment — the operator workstation MUST have docker available, OR the host-side `ha addons rebuild local_test-addon` is used instead. | `ha addons rebuild local_test-addon` (HA Supervisor's local-build pipeline) — runs on the host, no docker on the executor required.                                |
| `ghcr.io/home-assistant/amd64-base:3.24` base image on the Bridge host                                           | Building `tools/test-addon/` image (D-03)                                                                  | ✓                                                  | 3.24 (per `terraform-bridge/Dockerfile:5`)                                                                                                                                                                 | If the host can't pull the base image, the operator uses an alternative base (`alpine:3.20` or `ghcr.io/home-assistant/amd64-base:3.22`) and edits the Dockerfile. |
| `local_test-addon` published in the host's add-on store                                                          | Every scenario that touches the test add-on                                                                | ✗                                                  | Not yet built (Phase 14 is the first time)                                                                                                                                                                 | The verify suite's first run does `docker build -t local/local_test-addon:0.1.0 tools/test-addon/` + `ha addons reload` (D-04) before any scenarios execute.       |
| `~/.terraformrc` with `dev_overrides` pointing at the Provider binary                                            | Provider-driven `tofu apply` scenarios                                                                     | ✓ (assumed)                                        | Per Provider DOCS.md §"Step 2 — register the binary via dev_overrides"                                                                                                                                     | If missing, the operator runs `make install-provider` (Phase 15) which prints the `dev_overrides` block to add.                                                    |

**Missing dependencies with no fallback:**

- `tofu` binary — required for Provider-driven scenarios. No alternative path; OpenTofu is the only CLI that reads the
  Provider's protocol v6.

**Missing dependencies with fallback:**

- `docker` on the executor workstation — use `ha addons rebuild local_test-addon` on the host instead. The rebuild
  happens on the host (which has docker); the executor only needs `ssh`.
- `local_test-addon` published — first scenario run builds it (Plan 01's task).

## Validation Architecture

> Per `.planning/config.json` line 28: `"nyquist_validation": false`. This section is SKIPPED per the RESEARCH.md
> contract ("Skip this section entirely if workflow.nyquist_validation is explicitly set to false in
> .planning/config.json. If the key is absent, treat as enabled."). The repo's existing testing discipline is
> pre-commit + lint (per `TESTING.md`); Phase 14 follows that discipline.

## Security Domain

> Per the verification protocol: "Required when security_enforcement is enabled (absent = enabled). Omit only if
> explicitly false in config." `.planning/config.json` does NOT contain a `security_enforcement` key, so this section IS
> required.

### Applicable ASVS Categories

| ASVS Category           | Applies | Standard Control                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| ----------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| V2 Authentication       | yes     | Bearer token in `Authorization: Bearer <token>` header; Bridge validates via `crypto/subtle.ConstantTimeCompare` against SHA-256 hash on disk (`internal/auth/token.go:239-263`); rotation via `POST /v1/auth/rotate` with 24h grace window (CF-01); PITFALLS S-1: token plaintext NEVER enters logs.                                                                                                                                                        |
| V3 Session Management   | yes     | Sessions are request-scoped (no cookies, no persistent sessions). Per-slug mutex (Phase 12) serializes concurrent operations on the same add-on. Bridge's `X-Force-Destroy` nonce (Phase 12 D-05..D-08) is single-use, 60-second TTL. Phase 14 exercises both: scenario 06-locked.sh deliberately races two `tofu apply` against the same slug; scenarios 07/08 exercise nonce expiry + reuse.                                                               |
| V4 Access Control       | yes     | Tailscale bind-gate (Phase 10 D-04..D-06): bind to Tailscale-detected IP or an IP inside `bind_allowed_subnets`; `0.0.0.0` always refused. CF-05. Phase 14 does NOT modify bind behavior; the operator chooses Tailscale vs. LAN hostname per call (D-01).                                                                                                                                                                                                   |
| V5 Input Validation     | yes     | Bridge validates input via HA Supervisor's `/apps/{slug}/options/validate` (Phase 12 BRIDGE-08 + `supervisor/client.go:560-622`) before applying. Provider validates input via terraform-plugin-framework's schema validation (Phase 13 PROV-02). Phase 14 scenario 10-upstream-error.sh deliberately exercises the upstream-error path (Bridge returns 502 when Supervisor is unreachable); scenario 11-pwned.sh exercises the `pwned: true` advisory path. |
| V6 Cryptography         | yes     | CF-01: token format = base64url, 43 chars (256-bit entropy from `crypto/rand`); SHA-256 at-rest. CF-03: two-layer masking (slog Handler wrapper + chi middleware stripping Authorization). PITFALLS S-1 invariant: token never logged, never sent to Provider, never accepted from non-loopback source. Phase 14's empirical token rotation test (CONTEXT.md Specifics) verifies the rotation flow end-to-end.                                               |
| V7 Error Handling       | yes     | Every error returns a typed `error_code` + HTTP status (Phase 12 BRIDGE-09 + `supervisor/client.go:661-680` MapError). Provider translates each `error_code` into a typed Diagnostic with explicit Summary text (Phase 13 `internal/diagnostics/doc.go`). 401/403/404/409/423/502/504 all have dedicated Provider Summary text. `pwned` is the ONLY Warning severity (per CF-08 + PROV-06).                                                                  |
| V8 Data Protection      | yes     | `terraform.tfstate` may contain sensitive data (add-on `options` are written verbatim per PROV-06). State file permissions + storage at `/data/terraform.tfstate` (inside `addon_config:rw`). HA backup integration (Phase 9 §10 spike + CF-13) covers it automatically. Operator DOCS.md (Phase 13 STATE-01 + Phase 14 D-13 §8) instructs `chmod` + consider state encryption at rest.                                                                      |
| V9 Communications       | yes     | Plain HTTP (no TLS); TLS termination deferred (PITFALLS S-4 Phase 2 + CF-13). Network-layer access control (Tailscale ACL or LAN) is the security boundary in Phase 1. Phase 14's DOCS.md §"Add-on network access" (existing line 130-131 + Phase 14 expansion per D-13) explicitly states this posture.                                                                                                                                                     |
| V10 Malicious Code      | no      | The Bridge is a Go binary built from local source (CF-02 exception to the "Dockerfiles must download upstream at build time" rule); the Provider is a Go binary built from local source. No external code is downloaded at build time. The test add-on (D-03) is also built from local source. No code from outside the repo runs in the v1.3 stack.                                                                                                         |
| V11 Business Logic      | yes     | `UseStateForUnknown()` (PROV-10) suppresses spurious diffs on `state`; adoption-aware Create (PROV-05) treats 409 already_installed as success; idempotent Read (PROV-04) clears state on 404. Phase 14 SC-3 (5 iterations of `tofu apply` → "No changes") is the empirical idempotency proof.                                                                                                                                                               |
| V12 Files and Resources | yes     | `/data` volume is Supervisor-managed; `chmod 600` for token files (CF-01); atomic-rename for all writes (`internal/auth/token.go:144-175`); nonce journal is append-only. Phase 14's state snapshot (D-16) is a `cp` (not a new persistence primitive); fingerprint (D-17) reads via `/v1/state/index`.                                                                                                                                                      |
| V13 API and Web Service | yes     | All `/v1/*` endpoints require Bearer auth (chi subrouter with `RequireBearer(store)`). `OPTIONS` preflight deferred (PITFALLS S-3 + deferred-ideas). Rate limiting: per-slug mutex (STATE-03) caps concurrent destructive ops at 1 per slug. Phase 14 exercises every endpoint via the verify suite.                                                                                                                                                         |
| V14 Configuration       | yes     | Bridge `config.yaml` schema exposes operator-configurable bind_address, bind_allowed_subnets, critical_addons, install_job_timeout_seconds, try_lock_timeout_seconds (CF-12). Provider schema validates `endpoint` (URL parse) + `bearer_token` (non-empty + sensitive). Test add-on's schema exposes only `log_level` + `dummy_setting` (own-addon options, no cross-addon exposure).                                                                       |

### Known Threat Patterns for the v1.3 opentofu-bridge stack

| Pattern                                                         | STRIDE                 | Standard Mitigation                                                                                                                                                                                                                                                                                           |
| --------------------------------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Bearer token leaked via Bridge logs                             | Information Disclosure | CF-03: two-layer masking (slog scrubbing handler + chi middleware strips Authorization). Verified by `internal/verify-bridge-no-token-leak.sh` (Phase 10).                                                                                                                                                    |
| Provider accidentally logs bearer token                         | Information Disclosure | Phase 13: token marked `Sensitive: true` in schema; `client.BridgeError.Error()` explicitly omits token (PITFALLS S-1 + `terraform-provider-homeassistant/internal/client/client.go:585-588`). Verified by Provider client tests + Phase 14's empirical Provider output capture.                              |
| X-Force-Destroy nonce leaked via Bridge logs                    | Information Disclosure | Phase 12: nonce fingerprint (`auth.Fingerprint`) in audit journal + log records; plaintext nonce NEVER in logs. Verified by `internal/nonce/journal.go:24-31`.                                                                                                                                                |
| Unauthorized `tofu apply` on a critical add-on                  | Tampering              | Bridge's `critical_addons` check (Phase 12 D-09..D-11) returns 403 BEFORE nonce check; Provider's `lifecycle.prevent_destroy = true` recommended default (CF-09). Phase 14 scenario 03 exercises this empirically.                                                                                            |
| Concurrent destroys racing each other                           | Tampering / Denial     | Per-slug mutex (Phase 12 D-12..D-16) serializes; `X-Force-Destroy` nonce is single-use (Phase 12 D-06). Phase 14 scenarios 06/07/08 exercise all three paths.                                                                                                                                                 |
| Plain HTTP on Tailscale (no TLS)                                | Information Disclosure | Phase 1 transport limitation is documented (CF-13 + Provider DOCS.md §"Phase 1 transport limitation"); operator mitigation = reverse proxy with TLS termination OR Tailscale's network-layer ACL. Phase 14's DOCS.md §"Add-on network access" expansion (D-13 §1) explicitly states this posture.             |
| State file lost (host failure, accidental `rm`)                 | Denial of Service      | HA backup integration (CF-13) covers `addon_config:rw` automatically; Phase 9 §10 spike transcript in `spike-transcripts/` + Phase 14 empirical re-run (D-13 §9) demonstrate this empirically.                                                                                                                |
| Provider handshake mismatch (Bridge too new for Provider)       | Elevation of Privilege | PROV-03: Provider's `Configure` calls `GET /v1/version` and refuses to operate outside the `[min_provider_version, max_provider_version]` window. Phase 14 scenario 12 exercises this empirically.                                                                                                            |
| Race condition between Provider Refresh and Supervisor mutation | Tampering              | Phase 12 D-26: Provider's adoption-aware Create + idempotent Read (PROV-04 + PROV-05) handles 409 already_installed + 404 (resource gone) gracefully. `UseStateForUnknown()` (PROV-10) suppresses spurious `state` diffs. Phase 14 SC-3 (5 iterations of `tofu apply` → "No changes") is the empirical proof. |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/14-real-ha-end-to-end-verification-operator-documentation/14-CONTEXT.md` — all 26 decisions
  - 14 carried-forward invariants; canonical source for Phase 14's design surface. Read this session.
- `terraform-bridge/internal/supervisor/client.go:661-680` — `MapError` sentinel → (HTTP status, error_code) mapping;
  single source of truth for every `error_code` the verify scripts must exercise. Read this session.
- `terraform-bridge/contract/types.go` — every JSON shape the verify scripts' curl assertions must match (`AddOnInfo`,
  `ErrorResponse`, `RotateResponse`, `NonceResponse`, `StateIndexResponse`, `VersionHandshake`). Read this session.
- `terraform-bridge/internal/httpapi/router.go:66-121` — chi subrouter wiring + every route's auth requirement
  - per-slug-mutex TryLockTimeout middleware scope. Read this session.
- `terraform-bridge/internal/auth/token.go:239-263, 344-425` — Bearer token Validate + Rotate. Read this session.
- `terraform-bridge/internal/mutex/manager.go` — per-slug mutex implementation. Read this session.
- `terraform-bridge/internal/nonce/journal.go` — nonce audit journal. Read this session.
- `terraform-bridge/internal/state/index.go` — `/v1/state/index` implementation. Read this session.
- `terraform-provider-homeassistant/internal/diagnostics/doc.go:41-135` — canonical per-error_code Summary text +
  `DocAnchor` helper. Read this session.
- `terraform-provider-homeassistant/internal/client/client.go` — Provider HTTP client; bearer-token-injecting
  RoundTripper (mirrors Bridge's `supervisor.Client`); error decoding. Read this session.
- `terraform-provider-homeassistant/internal/diagnostics/map_error.go` — Bridge error → Provider Diagnostic translation;
  every error_code mapped. Read this session.
- `terraform-provider-homeassistant/DOCS.md` (618 lines) — Phase 13's canonical operator reference; the target Bridge
  DOCS.md cross-links to (D-14). Read this session (full).
- `internal/verify-bridge-no-token-leak.sh` (199 lines) — Phase 10 structural template for Phase 14's per-scenario
  verify scripts (single-purpose shell script, captured outputs to testdata file, exit-non-zero on assertion failure).
  Read this session.
- `internal/verify-install-provider.sh` (133 lines) — Phase 15 hermetic verifier; same exit-gate discipline as Phase 14
  needs (`exit 0` only when all assertions pass). Read this session.
- `internal/verify-bridge-scaffold.sh` (147 lines) — Phase 9 scaffold verifier; exit-gate discipline. Read this session.
- `internal/validate-versions.sh` (135 lines) — 3-file versioning scheme enforcement + cross-artifact Bridge/Provider
  sync. Read this session. CF-11.
- `internal/validate-addon-config.py:104-106` — auto-discovers any directory with both `config.yaml` + `build.yaml`; the
  new `tools/test-addon/` will be picked up automatically. Read this session.
- `Makefile:221-234` — `install-provider` target + dev_overrides hint; Phase 14's Provider-driven scenarios depend on
  it. Read this session.
- `AGENTS.md` — Live Systems rule (no unsolicited restarts), 3-file versioning rule (no manual edits), pre-commit
  pipeline. Read this session.

### Secondary (MEDIUM confidence)

- `.planning/phases/12-bridge-write-api-safety-concurrency-index/12-RESEARCH.md` — Phase 12's research document
  including the four ROADMAP success criteria that depend on empirical Supervisor behavior; Phase 14's research builds
  on the same empirical foundation. Read this session (selected sections).
- `.planning/phases/13-provider-resource-data-sources-schema-handshake/13-01-PLAN.md` — Phase 13 Plan 01's must-haves +
  test coverage. Phase 14 verifies Phase 13's output. Read this session (selected sections).
- `.planning/codebase/CONVENTIONS.md` — 120-char line limit, ATX headers, shellcheck SC1091/SC2034 ignored. Read this
  session.
- `.planning/codebase/TESTING.md` — the repo has NO test framework; quality is enforced via pre-commit + lint. Phase 14
  follows the same discipline. Read this session.
- `.pre-commit-config.yaml` — pre-commit pipeline (yamllint, shellcheck, prettier, markdownlint-cli2, actionlint,
  `validate-versions.sh`, `validate-addon-config.py`). Read this session.
- `.yamllint.yml` + `.markdownlint.json` — YAML + Markdown lint rules; 120-char limit is the universal cap. Read this
  session.
- `tools/test-bridge-fixture/main.go` (65 lines) — Phase 15's CI fixture (stdlib HTTP simulator for `/v1/version`).
  Phase 14's `tools/test-addon/` is the LIVE counterpart. Read this session.

### Tertiary (LOW confidence)

- `.planning/phases/12-bridge-write-api-safety-concurrency-index/12-CONTEXT.md` — D-05..D-08 nonce lifecycle + D-13 5s
  timeout pattern. Read this session (selected sections).
- `spike-transcripts/pitfalls10-20260831T153403Z.log` (Phase 9 §10) — empirical proof that `addon_config:rw` contents
  are auto-included in HA backups. Referenced by CF-13; not directly read this session but cited in STATE.md todo +
  Phase 14 CF-13.

## Metadata

**Confidence breakdown:**

- Standard stack: **HIGH** — zero new external dependencies; every tool (bash, curl, jq, ssh, tofu) is either already in
  the repo or in the operator's established dev environment.
- Architecture: **HIGH** — every Bridge + Provider endpoint, error_code, and contract shape is verified by reading the
  source files this session. The verify-scenario scripts map 1:1 to the existing handler set.
- Pitfalls: **HIGH** — derived from the AGENTS.md Live Systems rule (verified this session), the existing verify-script
  pattern (read this session), and the 3-file versioning scheme (read this session). All seven pitfalls are empirical
  observations from prior phases' spike transcripts + the established pre-commit discipline.
- Test add-on design: **MEDIUM** — the 4-file pattern is verified (every existing add-on follows it), the `local_` slug
  prefix convention is verified via `tools/test-bridge-fixture` (sibling-directory pattern); the specific schema (which
  two string options to expose) is the agent's discretion per CONTEXT.md.
- DOCS.md expansion scope: **HIGH** — the Provider DOCS.md#troubleshooting table is the canonical target (D-14
  - read this session); the cross-link pattern (`DOCS.md#troubleshooting-<kebab>`) is verified in
    `internal/diagnostics/doc.go:129-135`.
- Live-host state: **MEDIUM** — the host's current state (Bridge running, token in `/data/initial-token`, test add-on
  not yet installed) is ASSUMED per A1..A10 in the Assumptions Log; verified by the scenario pre-flight assertions
  rather than by direct read this session.

**Research date:** 2026-09-05 **Valid until:** 2026-10-05 (30 days; the Bridge + Provider APIs are stable, the OpenTofu
/ HA base images are stable, the pre-commit pipeline is stable — only the host's runtime state changes)
