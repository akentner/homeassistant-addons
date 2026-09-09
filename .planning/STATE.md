---
gsd_state_version: "1.0"
milestone: v1.3
milestone_name: opentofu-bridge
current_phase: 17
current_phase_name: Git Integration + Apply Job System
current_plan: 7
status: Ready to plan
stopped_at: "Completed 17-07-PLAN.md (Phase 17 code-complete: 8/8 plans)"
last_updated: "2026-09-08T20:33:37.811Z"
state_head: 1bcdd9aeb7b5418decca114a6dda29aafed9937a
progress:
  total_phases: 7
  completed_phases: 2
  total_plans: 15
  completed_plans: 15
  percent: 29
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-31)

**Core value:** Any upstream release is automatically reflected in the add-on within 24 hours — zero manual version
tracking. **Current focus:** Phase 17 — Git Integration + Apply Job System

## Milestone v1.0 — COMPLETE

All 3 phases shipped. Archived to `.planning/milestones/v1.0-ROADMAP.md`.

| Phase | Name                 | Status   | Completed  |
| ----- | -------------------- | -------- | ---------- |
| 1     | Quality Fixes        | Complete | 2026-04-03 |
| 2     | Auto-Update Workflow | Complete | 2026-04-04 |
| 3     | Meridian Add-on      | Complete | 2026-04-04 |

## Milestone v1.1 — COMPLETE

Roadmap: 3 phases (4-6). All phases complete.

| Phase | Name                             | Status   | Completed  |
| ----- | -------------------------------- | -------- | ---------- |
| 4     | Scaffold + Ingress Validation    | Complete | 2026-06-27 |
| 5     | Multi-Namespace + Dynamic Config | Complete | 2026-06-27 |
| 6     | Git Integration                  | Complete | 2026-06-28 |

## Milestone v1.2 — PLANNED

Roadmap: 1 phase (8), 4 plans in 4 waves. Source: GitHub Actions audit 2026-08-30. Requirements CI-01..CI-10.

| Phase | Name            | Status  | Completed |
| ----- | --------------- | ------- | --------- |
| 8     | CI/CD Hardening | Planned | —         |

Plans are strictly serial: 08-01, 08-02 and 08-03 all modify `.github/workflows/_build-template.yml`, so only one may
write per wave. 08-04 documents the end state and therefore runs last.

| Plan  | Wave | Blocked on user                                                              |
| ----- | ---- | ---------------------------------------------------------------------------- |
| 08-01 | 1    | no                                                                           |
| 08-02 | 2    | approval for an image-overwriting verification build; PR #39/#40 disposition |
| 08-03 | 3    | **yes** — Cloudflare service token + Access app + 2 GitHub secrets           |
| 08-04 | 4    | no                                                                           |

## Milestone v1.3 opentofu-bridge — PLANNING

Roadmap: 7 phases (9-15), 46 requirements mapped. Source: `research/SUMMARY.md` + `REQUIREMENTS.md`. Status: roadmap
approved; Phase 9 ready to plan. v1.3 runs in parallel with v1.2 Phase 8 gap-closure by explicit user decision.

| Phase | Name                                                   | Status                                 | Completed                                                                                                                                                 |
| ----- | ------------------------------------------------------ | -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 9     | Bridge Foundation + Token Rotation Spike               | Complete                               | 2026-08-31 (plans 01-04; H-1 + §10 transcripts in `spike-transcripts/`)                                                                                   |
| 10    | Auth Layer + Structured Logging + Healthcheck          | Complete                               | 2026-08-31 (plans 01-03; live-HA verify deferred to Phase 14)                                                                                             |
| 11    | Bridge Read API                                        | Complete (code + unit tests)           | 2026-09-02 (plans 01-02; 16 new tests; live-HA verification deferred to Phase 14)                                                                         |
| 12    | Bridge Write API + Critical-Addon Safety + Concurrency | SHIPPED (12-01 + 12-02 + 12-03 landed) | 2026-09-04 (5 atomic commits: feat(12-01), feat(12-02)×2, feat(12-03), test(12-03); all 10 reqs operational end-to-end; race-clean; build/vet/gofmt pass) |
| 13    | Provider + Resource + Data Sources + Schema Handshake  | Not started                            | —                                                                                                                                                         |
| 14    | Real-HA End-to-End Verification + Operator Docs        | Not started                            | —                                                                                                                                                         |
| 15    | CI Hardening + Provider Install Workflow               | Not started                            | —                                                                                                                                                         |

Phase dependency graph enforces: 9 → 10 → 11 → 12 → 13 → 14 → 15 (strictly serial). The empirical SUPERVISOR_TOKEN
rotation spike (H-1 from PITFALLS) was the first deliverable of Phase 9; it is the lowest-confidence item blocking the
rest. Spike ran 2026-08-31 → `token_unchanged`; Phase 10 auth already implements defensive re-read-per-call (see
`internal/supervisor/client.go:84-91` — `RoundTrip → t.tokenFn()` reads `os.Getenv("SUPERVISOR_TOKEN")` on every
outbound request). D-18 RESOLVED with defensive design; conservative re-verification deferred (see Todos).

**v1.3 closure status:** 6 of 7 phases shipped end-to-end (`terraform-bridge/v0.3.0` + Provider `v0.3.0`). Phase 15
release cut pending v1.2 Phase 8 gap-closure Cloudflare-setup prerequisite (mechanically ready). Milestone closure call:
`gsd-complete-milestone v1.3` after Phase 15 release.

## Milestone v1.4 iac-runner — PLANNING

Roadmap: 4 phases (16-19), ~32 requirements. Source: conversation 2026-09-06 (research skipped). Continues in parallel
with v1.3 (Phase 15 release) and v1.2 (Phase 8 gap-closure).

| Phase | Name                                                      | Status      | Completed |
| ----- | --------------------------------------------------------- | ----------- | --------- |
| 16    | iac-runner Scaffold + Auth + State Backends + Healthcheck | In Progress | —         |
| 17    | Git Integration + Apply Job System                        | In Progress | —         |
| 18    | MQTT Discovery + HA Sensoren + Buttons                    | Planned     | —         |
| 19    | E2E Verification + DOCS + Operator Runbook                | Planned     | —         |

Phase dependency graph: 16 → 17 → 18 → 19 (strictly serial in initial plan; 17 + 18 are conceptually independent and may
parallelize after Phase 16 stabilises the contracts).

## Current Position

Current Plan: 7 Total Plans in Phase: 8

Phase: 17 (Git Integration + Apply Job System) — EXECUTING COMPLETE (7 atomic commits landed on main; live-HA empirical
exercise deferred to operator runtime as documented in 14-VERIFICATION.md — preflight returns 1 in this env: no tofu, no
Provider binary, /healthz unreachable). OPS-04 surface delivered: `tools/test-addon/` (5 files) +
`internal/verify-bridge-e2e/` (_lib.sh + 00-happy-path.sh + 12 error-code scenarios + 99-cleanup) +
`terraform-bridge/{README.md, DOCS.md}` rewrite. Bridge 0.2.0 == Provider 0.2.0 (TOFU-05 unchanged — CF-11 honored).
**v1.3 Phase 15** (CI hardening + provider install workflow) is mechanically ready but blocked on v1.2 Phase 8
gap-closure Cloudflare-setup prerequisite.

**v1.4 Phase 16** Plan 01 (iac-runner Scaffold + Auth) is COMPLETE (3 atomic commits: 0fa09fb scaffold, bb00c4f auth
package + version + contract, 4df2d95 main.go + signals + handlers + router). 24 files (5 scaffold + 18 Go source + 1
root README). All Phase 16 acceptance criteria pass: `go build / vet / test ./...` exit 0 from `iac-runner/`; 20 unit
tests pass (11 token + 9 bind); `python3 internal/validate-addon-config.py iac-runner` exits 0; binary prints `dev` for
`-version`; root `README.md` updated with iac-runner entry between `network-tools` and `gatus`. AUTHR-01..04 + OBS-01
marked complete in `.planning/REQUIREMENTS.md`. Live-HA empirical verification (token issuance + rotation + bind gate +
/healthz against a real HA host) deferred to Phase 19.

**v1.4 Phase 16** Plan 02 (Log scrubbing + /data/keys/ validator + state backends r2/s3/local + real /healthz) is
COMPLETE (2 atomic commits: 10e5dd2 SEC-02 slog.Handler scrubber + SEC-01 keys validator + STBK-01..05 backend
interface + r2/s3/local impls + factory, 96a4a12 main.go wiring + real /healthz + router signature extension). 14 files
(3 new packages logging/keys/statebackend + healthz handler/test + main.go + router). All Plan 02 acceptance criteria
pass: 21 new unit tests (6 scrubbing + 7 validator + 5 factory + 3 healthz) on top of Plan 01's 20 = 41 total tests
passing; `go build / vet / test ./...` exit 0; SEC-01 + SEC-02 + STBK-01..05 marked complete in
`.planning/REQUIREMENTS.md`. The Plan 01 /healthz stub with `tofu_on_path:true + keys_chmod_600:true` placeholders is
replaced with real `exec.LookPath("tofu")`

- `validator.Validate()` probes; 200 + HealthResponse on both-pass, 503 + empty body (Content-Length: 0)

on either fail. `statebackend.Factory.New` returns ErrUnsupported for any value outside r2/s3/local. Live-HA empirical
verification deferred to Phase 19.

**v1.4 Phase 17** — 3 of 8 plans complete (17-01, 17-02, 17-03). Plan 03 (`internal/git`) is COMPLETE: 7 atomic commits
on main (3 RED + 3 GREEN + 1 docs), 5 new files (1757 insertions), 35 test functions (75 PASS lines incl. table
sub-cases) passing under `-race`. `RepoConfig` + `Error`/`Classify` + `Manager` (WorkTree / IsCloned / EnsureCloned /
Clone / CloneAll / Pull) with an injectable `CommandRunner` and clock — no test spawns a real git process. Ships GIT-02
(clone-if-absent, skip-if-present, 3-attempt 1s/5s backoff that never blocks startup), GIT-03 (SSH-keyed pull, deploy
key + `IdentitiesOnly` + pinned `known_hosts` + `BatchMode`, ref-vs-fast-forward semantics) and GIT-04 (ordered stderr →
`git_*` classifier with an Options-field hint and no raw stderr). **The D-10/D-12 contradiction is resolved in favor of
D-10** per GIT-03/SC-3: a pinned repo re-lands on its `ref` on pull, and D-12 fires only when a caller sets `ff_only`
against a pinned repo. GIT-02/03/04 are NOT yet marked complete in `REQUIREMENTS.md` — the shared-ID gate correctly
blocks them until 17-06, 17-07 and 17-08 also finish. `go build / vet / test ./...` exit 0; verification ran inside
`golang:1.25-alpine` because the dev host has no `go` on PATH (see `17-.../deferred-items.md`).

## Accumulated Context

### Key Decisions (v1.3)

| Decision                                                                                                                                                                                                                                                                                                                                                       | Rationale                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 7 phases, not 10 — vertical slices, not horizontal layers                                                                                                                                                                                                                                                                                                      | Each phase produces a deployable, verifiable artifact; collapse read+write API into one phase was rejected (loses safety gate before write)                                                                                                                                                                                                                                                                                                  |
| Empirical SUPERVISOR_TOKEN rotation spike is Phase 9, not later                                                                                                                                                                                                                                                                                                | H-1 is the lowest-confidence item; designing auth on top of unverified token behavior risks rework (per PITFALLS research)                                                                                                                                                                                                                                                                                                                   |
| Per-slug mutex goes in Phase 12, not Phase 13                                                                                                                                                                                                                                                                                                                  | Defense-in-depth for cross-host concurrent applies must exist BEFORE Provider surfaces destructive ops; STATE-03 paired with write endpoints                                                                                                                                                                                                                                                                                                 |
| Real-HA E2E gets its own phase (14), not folded into Provider (13)                                                                                                                                                                                                                                                                                             | Phase-8 pattern: empirical verification against live HA host deserves its own validation gate; docs written from observed behavior, not theory                                                                                                                                                                                                                                                                                               |
| Phase 15 (CI + install-provider) is intentionally thin                                                                                                                                                                                                                                                                                                         | The CI work is substantial (new build workflow, new test workflow, install verification); TOFU-04 is the single REQ-ID; non-req deliverables carry the weight                                                                                                                                                                                                                                                                                |
| `homeassistant_addon_repository` deferred to v1.4 (per existing decision)                                                                                                                                                                                                                                                                                      | PROJECT.md + REQUIREMENTS.md both record this; do NOT re-add in any v1.3 phase                                                                                                                                                                                                                                                                                                                                                               |
| **Two-layer AUTH-05 masking (Plan 02):** slog.Handler wrapper scrubs every record + chi middleware strips Authorization from r.Header before request-log snapshot                                                                                                                                                                                              | D-10 layered defense — if the slog scrubber ever regresses, the chi middleware still prevents leakage. Both proven by unit tests. Phase 10 plan 02 commits.                                                                                                                                                                                                                                                                                  |
| **/healthz probe (Plan 02):** real /supervisor/ping call with 2s context deadline, no caching. 503 body always empty (Content-Length: 0)                                                                                                                                                                                                                       | D-07 freshness > p99 reduction at this poll cadence. D-08 prevents internal-state leak on health-check failure. Phase 10 plan 02 commits.                                                                                                                                                                                                                                                                                                    |
| **verify-script adaptation (Plan 02):** positive-control assertions rewritten to parse `bridge.token.issued` JSON and assert actor_token_fp == SHA-256[8](plaintext) instead of comparing against FAKE_TOKEN (the supervisor token the bridge never logs)                                                                                                      | Plan-adaptation deviation. Adding a BRIDGE_TOKEN env override to TokenStore would be an out-of-scope architectural change; same invariants proven without it. Documented in 10-02-SUMMARY §Deviations.                                                                                                                                                                                                                                       |
| **Phase 10 H-1 implementation: re-read-per-call, NOT cache-at-startup (Plan 02 → client.go)** — `internal/supervisor/client.go:84-91` `RoundTrip → t.tokenFn()` reads `os.Getenv("SUPERVISOR_TOKEN")` on every outbound request. Empirical spike (2026-08-31) showed token unchanged; per-call re-read is the defensive default for unknown rotation behavior. | Earlier 09-SUMMARY.md text said "Phase 10 may cache at startup (cheap default)" — that was an aspirational design note, NOT what shipped. The shipped Phase 10 RoundTrip pattern is already conservative: re-read per call costs O(1) and makes the design robust to a future Supervisor change that introduces per-add-on token rotation. Plan 03's signals.go SIGHUP handler remains the natural hook for explicit force-re-read commands. |
| **2026-09-02 conservative decision: ASSUME SUPERVISOR_TOKEN MAY rotate** — empirically verified unchanged 2026-08-31 on haos-op3050-1, but the live system is now treated as if the token could rotate at any restart. Re-verification deferred to a low-risk window.                                                                                          | User decision 2026-09-02: live-system conservatism wins over empirical single-shot result. Phase 10 design (re-read per call) already meets the assumption; no code change required. To be re-verified later via `internal/spike-h1-token-rotation.sh` against a maintenance-window host.                                                                                                                                                    |
| **AUTH-04 grace file format (Plan 03):** /data/bridge-token.grace is a 2-line plaintext format (hex64 + RFC3339) instead of JSON — keeps Plan 01's readGraceFile parser unchanged; D-13 per-request expiry semantics means the file becomes inert without background goroutines                                                                                | Plan-adaptation choice. JSON would have been equally correct on disk but required rewiring the reader AND adding a JSON-path through Plan 01's already-committed code. Text format respects the existing reader and locks the security invariant (no plaintext ever) more defensively.                                                                                                                                                       |
| **AUTH-04 rotate write order (Plan 03):** TokenStore.Rotate writes the new primary hash BEFORE writing the grace file. If the grace write fails, the old token still authenticates against the new hash; on-disk primary state is always consistent                                                                                                            | Failure-mode lockdown. Reversing the order would leave a window where the new token authenticates against /data/bridge-token but the old token does not — exactly the scenario D-02/D-12 are designed to prevent. Cost of writing primary first is one extra renamed file; cost of reversal is a window of forced 401s on a still-valid token.                                                                                               |
| **D-03 timestamp pair (Plan 03):** RotateResponse.GraceExpiresAt and OldTokenValidUntil are byte-identical RFC3339 strings — duplicated on purpose so Provider consumers can pick whichever schema field name they prefer without an extra hop                                                                                                                 | Provider-side ergonomics. PROV-03 / PROV-05 reference these fields from Phase 13's resource shape; duplication costs zero on the wire (~70 bytes) and removes a constant from the Provider's schema mapping table.                                                                                                                                                                                                                           |

### Key Decisions (v1.4)

| Decision                                                                                                                                                                                                                | Rationale                                                                                                                                                                                                                                                                    |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| New milestone v1.4, not Phase 16 in v1.3                                                                                                                                                                                | v1.3 = "opentofu-bridge" (manage HA add-ons declaratively); v1.4 = "iac-runner" (apply IaC to homelab servers). Different runtime semantics (HTTP service vs long-running executor), different auth needs, different state model. Name + scope don't fit a single milestone. |
| Bearer-auth pattern reused from `terraform-bridge` (crypto/rand + SHA-256 + ConstantTimeCompare + chmod 600)                                                                                                            | Already proven and validated in v1.3 Phase 10. Two HA add-ons can share an auth primitive; only the listener port and the Tailscale-bind config differ.                                                                                                                      |
| Multi-backend state (r2 default + s3 + local) instead of single backend                                                                                                                                                 | User already has Cloudflare R2 in use; R2's S3-compatible API supports `use_lockfile = true` (no DynamoDB required). User explicitly asked for "R2 als Default, aber S3 und lokal trotzdem unterstützen".                                                                    |
| SSH deploy keys in `/data/keys/{repo}.key` (chmod 600 enforced at startup) instead of Options-Field base64                                                                                                              | Personal/private deployment; per-repo SSH keys are too long for the HA Options UI; matches `terraform-bridge`'s `/data/initial-token` pattern (file-on-volume instead of config).                                                                                            |
| Manual REST trigger only (`POST /v1/plan`, `POST /v1/apply`), no webhook in v1.4                                                                                                                                        | Webhook-Auto-Rollout deferred to v1.5. Manual trigger = implicit human approval gate; auto-rollout needs a deliberate design pass (approval flow, secrets-in-CI, etc.).                                                                                                      |
| HA entities via MQTT Discovery (`homeassistant_api: true` + `services: ["mqtt:need"]`) instead of WebSocket-Custom-Component                                                                                            | MQTT Discovery is the standard HA add-on integration path; no custom integration install needed. WebSocket-based approach would require a Custom-Component in HA Core (more setup, less portable).                                                                           |
| 4 phases (16–19), not 7 like v1.3                                                                                                                                                                                       | Concerns group more naturally: scaffold/auth/state → git/apply-jobs → MQTT/HA → E2E/docs. 17 + 18 are independent and may parallelize after Phase 16 stabilises the contracts.                                                                                               |
| RESEARCH skipped for v1.4                                                                                                                                                                                               | Scope clear from conversation; patterns reused from existing repo add-ons (`terraform-bridge` for HTTP/auth/Go, `markdown-renderer` for git integration). Research would re-validate what is already decided.                                                                |
| **Two-layer SEC-02 masking (Plan 02):** slog.Handler scrubber (Authorization, Bearer, token, password, key, secret) + chi middleware stripping Authorization from r.Header.Clone() before slog                          | Same D-10 layered-defense pattern as terraform-bridge Phase 10 AUTH-05. If either layer regresses, the other still prevents credential leakage. Both proven by unit tests.                                                                                                   |
| **/healthz 2s probe budget (Plan 02):** real exec.LookPath("tofu") + validator.Validate() under context.WithTimeout; 503 body always empty (Content-Length: 0); failure reason slog.Warn'd server-side only             | Same D-07/D-08 pattern as terraform-bridge Phase 10 OPS-03. Future per-request probes (Phase 17 may add tofu version probe + remote-state reachability) plug into the 2s budget slot without changing the handler signature.                                                 |
| **`keys` package independent of `auth`/`statebackend`'s `Backend`:** validator imports statebackend.Backend (read CredentialFiles()) but statebackend has NO inbound dependency on auth or keys                         | Defense-in-depth layering — the credential validator stands alone, can't accidentally couple into the bearer-auth flow, and is unit-tested with a fakeBackend without dragging in any of auth's state.                                                                       |
| **SEC-01 fail-fast on missing / wrong-mode keys at startup (Plan 02):** validator.Validate() called in main.go BEFORE token store init; failure → os.Exit(1) with 'keys_validation_failed' audit record                 | AGENTS.md "Live Systems" rule: no degraded mode for credential safety. Restart + `chmod 600 <file>` is the only remediation; the operator sees the failing path in the startup log line.                                                                                     |
| **Plan 02 `r2-account-id` file (not Options field):** the Cloudflare account ID is plaintext (non-sensitive), but its file-on-volume location still gets chmod-600-validated by the keys validator for defense-in-depth | Same pattern as `/data/keys/{repo}.key` for SSH deploy keys (Phase 17 will reuse this). File-on-volume matches terraform-bridge's `/data/initial-token` precedent; HA Options UI is too narrow for the account ID string.                                                    |

### Research Flags (v1.4 — open questions for implementation)

- **IRUN-H-1: OpenTofu S3-backend lockfile semantics on Cloudflare R2** — MEDIUM confidence; R2 supports S3-compatible
  PUT/GET/DELETE but native object-lock semantics are non-standard. **Verify empirically in Phase 16 spike** by running
  `tofu apply` against R2 with `use_lockfile = true` and observing that a second concurrent apply blocks (not errors
  with 403). Output: spike result documented in `16-SUMMARY.md`. If R2 lockfile does not behave as expected, fall back
  to: (a) use only the local backend by default and offer R2 as a sync-only (no-lock) backend, or (b) add an external
  lock service. **Do not** silently drop locking.

- **IRUN-H-2: MQTT Discovery button-press semantics for `button.*` entities in HA Core 2026.x** — LOW confidence; HA
  Core has been deprecating/reworking `button.*` entities across releases. **Verify in Phase 18 spike** that
  `button.iac_runner_run_apply` published via MQTT Discovery actually surfaces in the HA UI and that pressing it invokes
  the Add-on's subscribed MQTT command topic. If button.* is unavailable, fall back to `switch.*` or expose the trigger
  as a `rest_command` automation that calls `POST /v1/apply`.

### Research Flags (open questions for implementation — must resolve before/during Phase 9)

- **H-1: SUPERVISOR_TOKEN rotation across Supervisor restart** — LOW confidence; **must verify empirically in Phase 9
  spike** (before designing token refresh logic in Phase 10). Output: spike result documented in `09-SUMMARY.md`.

- **PITFALLS §10: HA backup integration with `addon_config` mount** — MEDIUM confidence; **verify in Phase 9 spike**.
  Affects whether the secondary state-copy mitigation in STATE-01 actually works.

- **Open Q-1 (deferred to v1.4): `homeassistant_addon_repository`** — confirmed out of scope; do NOT add mid-milestone.

- **Open Q-2 (resolved in FEATURES.md): `TypeMap<String>` for options in Phase 1** — Phase 13 uses static
  TypeMap<String> with server-side validation via `/options/validate`; dynamic typed schema is Phase 2.

- **Open Q-4 (resolved): `pwned` secrets surface as Provider warning** — not error; surfaced in Phase 13 Update flow.

- **Open Q-5 (resolved): `start = true` default** — Phase 13 schema; opt-out documented in `DOCS.md`.

- **Open Q-7 (resolved): plain HTTP on Tailscale for Phase 1** — TLS termination deferred; AUTH-07 binds `0.0.0.0:8124`
  with Tailscale-interface detection at startup.

- **Open Q-8 (resolved): `UseStateForUnknown()` default** — applied to `state` attribute in Phase 13.

### Todos

#### v1.4 (new)

- [ ] Phase 16: **Capture IRUN-H-1 spike transcript** — verify OpenTofu S3-backend lockfile semantics on Cloudflare R2
      before designing STBK-05

- [ ] Phase 18: **Capture IRUN-H-2 spike transcript** — verify `button.*` MQTT-Discovery semantics in HA Core 2026.x
      before designing MQTT-05/06

#### v1.3 (carried forward)

- [ ] **Conservative H-1 re-verification** — Empirical spike (2026-08-31) showed `SUPERVISOR_TOKEN` unchanged across
      Supervisor restart. Per user decision 2026-09-02 we now ASSUME the token MAY rotate. Phase 10's design is already
      defensive (re-read-per-call via `internal/supervisor/client.go:84-91`). When a lower-risk window arises
      (maintenance window, non-production host), RE-run `internal/spike-h1-token-rotation.sh` against a live host to
      confirm the assumption. Do NOT re-run during normal operation — `ha supervisor restart` disrupts every add-on.

- [x] Phase 9: **Capture H-1 spike transcript** — `internal/spike-h1-token-rotation.sh` committed (e29f5cd); executed
      against haos-op3050-1 on 2026-08-31 with explicit per-call authorization for Supervisor restart; transcript at
      `spike-transcripts/h1-20260831T153943Z.log`; pasted verbatim into `09-SUMMARY.md`; D-18 RESOLVED
      (`token_unchanged`)

- [x] Phase 9: **Capture §10 spike transcript** — `internal/spike-pitfalls10-backup-addon-config.sh` committed
      (6f254d5); executed against haos-op3050-1 on 2026-08-31 with explicit per-call authorization for `ha backups new`;
      transcript at `spike-transcripts/pitfalls10-20260831T153403Z.log`; pasted verbatim into `09-SUMMARY.md`; D-19
      RESOLVED (`addon_config_backed_up`)

- [x] Phase 9: Extend `internal/validate-versions.sh` to enforce Bridge `build.yaml` == Provider `build.yaml` semver —
      done in 09-02 (`d0d516d`)

- [x] Phase 9: Scaffold `terraform-bridge/` 4-file pattern + `terraform-provider-homeassistant/` Go module — done in
      09-01 + 09-02

- [x] Phase 11: **Plan 11-01 drafted + verified** — `/.planning/phases/11-bridge-read-api/11-01-PLAN.md` (899 lines):
      tracer-first task builds `/v1/info` (BRIDGE-10, no-auth, `uptime_seconds` since `func main()` start) +
      `/v1/version` (BRIDGE-01, auth-required handshake for PROV-03); introduces `internal/version` package for shared
      semver constants; adds `terraform-bridge/internal/supervisor/testing.go` (NOT `_test.go`) so cross-package handler
      tests can use `WithBaseURLForTest` / `TokenFnForTest` helpers; 11 files touched

- [x] Phase 11: **Plan 11-02 drafted + verified** — `/.planning/phases/11-bridge-read-api/11-02-PLAN.md` (1059 lines):
      V1/V2 fallback machinery in `supervisor.Client` + `/v1/addons` (BRIDGE-02) + `/v1/addons/{slug}/info` (BRIDGE-03);
      `ErrNotFound` sentinel mapped to literal `{"error_code":"not_found"}` per BRIDGE-03; relaxed fallback treats
      V2-403+V1-404 as `ErrNotFound` too; 4 new tests (V2-success, V2-403-then-V1-200, V2/V1 happy-path 200,
      V2-403-then-V1-404); 7 files touched

- [x] Phase 11: **Plan 11-01 executed** — 7 files created (supervisor/client_test.go, supervisor/testing.go,
      version/version.go, handlers/info.go + info_test.go, handlers/version_test.go, router_test.go) + 5 modified
      (supervisor/client.go, contract/types.go, handlers/version.go, router.go, cmd/bridge/main.go); 6 new tests + go
      build / vet / test / gofmt all green; 1 Rule-1 auto-fix (body-drain order in GetSupervisorInfo);
      `11-01-SUMMARY.md` written (328 lines). Staged but uncommitted.

- [x] Phase 11: **Plan 11-02 executed** — 4 files created (handlers/addons.go + addons_test.go, handlers/addon_info.go +
      addon_info_test.go) + 3 modified (supervisor/client.go, supervisor/client_test.go, router.go); 10 new tests +
      all-green pipeline; `11-02-SUMMARY.md` written (27.5 KB). Staged but uncommitted.

- [ ] **Phase 11 commit + push (awaiting user approval)** — staged set: 16 new files + 8 modified. Two atomic commits
      planned per plan (`feat(11-01): GET /v1/info + /v1/version (BRIDGE-10, BRIDGE-01)` and
      `feat(11-02): supervisor V1/V2 fallback + GET /v1/addons + /v1/addons/{slug}/info (BRIDGE-02, BRIDGE-03)`). Live
      curl tests against 192.168.178.3:8124 require rebuilding the Bridge image + redeploying on the HA host. Pre-commit
      `validate-versions.sh` is not impacted (Bridge version unchanged).

- [x] Phase 11: **3 atomic commits landed** — a6f1c36 docs(STATE): Phase 9 sync + Phase 11 in-progress tracking (1 file,
      62+/18-); 9158869 feat(11-01): GET /v1/info + /v1/version + planning docs (14 files, 1684+/10-); 40548c4
      feat(11-02): V1/V2 fallback + /v1/addons + /v1/addons/{slug}/info + planning docs (9 files, 1921+/0-). Build +
      vet + gofmt clean. Branch main is at 40548c4. Pre-commit validate-versions.sh did not fire (Bridge version
      unchanged).

- [ ] **STATE.md stale-on-deliverable (post-commit sync pending user approval)** — Phase 11 is shipped but the STATE.md
      update reflecting "Phase 11 complete" is unstaged in the working tree. Per user instruction "3 Commits: state +
      feat(11-01) + feat(11-02)" we did not add a 4th commit for the doc-sync; it remains for the user to commit or
      amend. Until then STATE.md still reports "Phase 11 in-progress" on the committed HEAD, which is inaccurate.

### Blockers

- **Phase 8 gap-closure (`08-05-GAP-PLAN.md`) remains blocked** on user Cloudflare setup (Q-02 from 08-CONTEXT). v1.3
  Phase 9-15 runs in parallel per explicit user decision.

## Performance Metrics

| Phase                                                  | Plan   | Duration | Tasks    | Files |
| ------------------------------------------------------ | ------ | -------- | -------- | ----- |
| 06                                                     | 01     | 19 min   | 3        | 4     |
| 06                                                     | 02     | 36 min   | 3        | 9     |
| Phase 08 P01                                           | 2 min  | 3 tasks  | 5 files  |
| Phase 08 P02                                           | 15     | 3 tasks  | 5 files  |
| Phase 08 P04                                           | 25     | 4 tasks  | 5 files  |
| Phase 09 P01                                           | 40     | 3 tasks  | 15 files |
| Phase 09 P02                                           | 458s   | 3 tasks  | 8 files  |
| Phase 9 P3                                             | 9min   | 3 tasks  | 5 files  |
| Phase 09 P04                                           | 25min  | 4 tasks  | 3 files  |
| Phase 10 P01                                           | 35min  | 3 tasks  | 11 files |
| Phase 10 P02                                           | 25min  | 3 tasks  | 11 files |
| Phase 10 P02                                           | 25min  | 3 tasks  | 11 files |
| Phase 10-auth-layer-structured-logging-healthcheck P03 | 4 min  | 3 tasks  | 6 files  |
| Quick 260902-sa1 (State Sync)                          | ~5min  | 1 task   | 1 file   |
| Phase 16 P01                                           | 17 min | 3 tasks  | 24 files |
| Phase 16 P02                                           | 18     | 2 tasks  | 14 files |
| Phase 16 P03                                           | 5 min  | 2 tasks  | 6 files  |
| **Per-Plan Metrics:**                                  |

| Plan         | Duration | Tasks   | Files   |
| ------------ | -------- | ------- | ------- |
| Phase 17 P03 | 21 min   | 3 tasks | 6 files |
| Phase 17 P04 | 12 min   | 3 tasks | 8 files |
| Phase 17 P05 | 25 min   | 3 tasks | 5 files |
| Phase 17 P06 | 19 min   | 3 tasks | 8 files |
| Phase 17 P08 | 10 min   | 3 tasks | 7 files |
| Phase 17 P07 | 25 min   | 4 tasks | 8 files |

## Quick Tasks Completed

| #             | Description                                                                                   | Date       | Commit  | Directory                                                                                                                 |
| ------------- | --------------------------------------------------------------------------------------------- | ---------- | ------- | ------------------------------------------------------------------------------------------------------------------------- |
| 260404-ksc    | Add Claude and GSD best-practice entries to .gitignore                                        | 2026-04-04 | a0a9402 | [260404-ksc-add-claude-and-gsd-best-practice-entries](./quick/260404-ksc-add-claude-and-gsd-best-practice-entries/)       |
| 260404-o5b    | Simplify meridian Dockerfile to single-stage npm + oauth polling run.sh                       | 2026-04-04 | 19af0b3 | [quick/260404-o5b-meridian-dockerfile-vereinfachen-mehrstu](./quick/260404-o5b-meridian-dockerfile-vereinfachen-mehrstu/) |
| 260404-rsj    | Meridian Ingress nginx reverse proxy fuer path rewriting                                      | 2026-04-04 | 9407184 | [quick/260404-rsj-meridian-ingress-nginx-reverse-proxy-fue](./quick/260404-rsj-meridian-ingress-nginx-reverse-proxy-fue/) |
| 260404-s1t    | Meridian: expose all upstream config options in config.yaml and run.sh                        | 2026-04-04 | 3ed58d3 | [quick/260404-s1t-meridian-alle-upstream-config-optionen-i](./quick/260404-s1t-meridian-alle-upstream-config-optionen-i/) |
| 260502-0kw    | coding-assistants: make args and env optional in mcp_servers schema                           | 2026-05-02 | 1f17a3b | [quick/260502-0kw-coding-assistants-config-yaml-make-args-](./quick/260502-0kw-coding-assistants-config-yaml-make-args-/) |
| 260507-vjm    | Integriere MCP2ZigBee2MQTT in coding-assistants                                               | 2026-05-07 | 0afa2db | [quick/260507-vjm-integriere-mcp2zigbee2mqtt-in-coding-ass](./quick/260507-vjm-integriere-mcp2zigbee2mqtt-in-coding-ass/) |
| 260507-w85    | coding-assistants: dedizierter zigbee2mqtt Config-Block mit auto-MCP-Registrierung            | 2026-05-07 | e4d1bc4 | [quick/260507-w85-coding-assistants-dedizierter-zigbee2mqt](./quick/260507-w85-coding-assistants-dedizierter-zigbee2mqt/) |
| 260628-eqo3yb | network-tools: Icon + Flap-Detection (disconnect_threshold, consecutive_failures)             | 2026-06-28 | 7f53c82 | [quick/260628-eqo3yb-network-tools-icon-flap-detection](./quick/260628-eqo3yb-network-tools-icon-flap-detection/)         |
| 260901-na1    | Fix 6 pre-existing lint failures on main (EOF, shellcheck, prettier, actionlint, 2 real bugs) | 2026-09-01 | 87dc714 | [quick/260901-na1-fix-6-pre-existing-lint-failures-on-main](./quick/260901-na1-fix-6-pre-existing-lint-failures-on-main/) |
| 260908-pfp    | Add .github/workflows/build-iac-runner.yml via _build-template.yml                            | 2026-09-08 | a4ca23f | /home/akentner/Projects/homeassistant-addons/.planning/quick/add-a-build-workflow-for-the-iac-runner-add-on-there-is-curr |
| 260908-pfq    | Scope the pre-push release-tag check to non-allowlisted add-ons                               | 2026-09-08 | 812f028 | /home/akentner/Projects/homeassistant-addons/.planning/quick/make-the-pre-push-version-tag-hook-stop-demanding-a-release  |
| 12            | Stop prettier breaking the broken-windows ledger (.prettierignore + canonical table)          | 2026-09-08 | 1bcdd9a | —                                                                                                                         |
| 260908-vnz | Fix the authentik add-on build: adapt Dockerfile and run.sh to upstream 2026.8.1's single Rust binary with allinone subcommand | 2026-09-09 | dc544d1 | .planning/quick/fix-the-authentik-add-on-build-which-fails-in-ci-with-failed |
| 260909-rlj | Dispatch builds after automated version bumps (GITHUB_TOKEN pushes trigger no workflows) + BUILD_DATE fallback for dispatch-triggered runs | 2026-09-09 | 6fbe7a4 | .planning/quick/stage-1-2-urgent-land-first-one-commit-make-automated-versio |
| 260909-rlk | Image-availability guard: internal/verify-image-availability.sh + 4x-daily scheduled workflow, proving the Supervisor pull invariant with a three-way ghcr probe and two anti-silent-pass safeguards | 2026-09-09 | a2b66fc | .planning/quick/stage-3-add-a-ci-guard-that-turns-the-silent-live-breaking-i |

## Session Continuity

**Resume file:** None

**Stopped at:** Completed 17-07-PLAN.md (Phase 17 code-complete: 8/8 plans)

Last session: 2026-09-08T12:37:49.668Z DOCS.md + README + pre-commit config) Resume file: None

---

_State initialized: 2026-04-04_ _Milestone v1.0 archived: 2026-04-04_ _Milestone v1.1 roadmap written: 2026-06-27_
_Milestone v1.2 (Phase 8, CI/CD Hardening) planned: 2026-08-30 from a GitHub Actions audit — 4 plans, requirements
CI-01..CI-10, nothing executed yet_ _Milestone v1.3 opentofu-bridge roadmap written: 2026-08-31 — 7 phases (9-15), 46
requirements mapped across TOFU/AUTH/BRIDGE/PROV/STATE/LIFE/OPS — 6 of 7 phases shipped (9, 10, 11, 12, 13, 14); Phase
15 mechanically ready, blocked on v1.2 Phase 8 gap-closure Cloudflare-setup prerequisite_ _Milestone v1.4 iac-runner
roadmap planned: 2026-09-06 — 4 phases (16-19), ~32 requirements across AUTHR/STBK/SEC/GIT/RUN/MQTT/OBS — research
skipped; Phase 16 ready to plan_

## Decisions

- [Phase 17]: D-10 wins over D-12 for POST /v1/repos/{name}/pull; D-12 survives only as an explicit ff_only-vs-pinned
  conflict guard — GIT-03 and ROADMAP SC-3 both word the endpoint as "runs git pull --ff-only (or the configured ref)",
  which is D-10. Making D-12 unconditional would leave a pinned repo with no way to update at all. Reverting to strict
  D-12 is a one-line change documented in manager.go.
- [Phase 17]: git stderr classifier consults "repository not found"/"authentication failed" BEFORE gits generic "Could
  not read from remote repository" line — GitHub emits both lines together for an unauthorized repo; the plan rule order
  would have returned git_ssh_handshake and sent the operator to check a deploy key that is fine.
- [Phase 17]: safe.directory guard runs once from NewManager; its failure is surfaced via SafeDirectoryWarning() rather
  than swallowed or made fatal — ROADMAP SC-2 requires startup to proceed, but silently discarding the failure would
  hide a real /data ownership misconfiguration behind unrecognized git errors.
- [Phase 17]: git.allow_default_branch_commits enabled in .planning/config.json — Sequential-mode dispatch instructed
  staying on main and the project already uses git.branching_strategy none with 17-01/17-02 committed directly on main;
  the flag is the documented escape hatch for the executor protected-branch assertion.
- [Phase 17]: GIT-03/SC-3 statuses override the plan sample: git_ssh_handshake + git_unauthorized are 403 and
  git_non_fast_forward is 409, not a blanket 502
- [Phase 17]: The optional ff_only request body defaults to false, implementing 17-03's D-10/D-12 resolution: a bare
  pull on a pinned repo re-lands on its ref; only an explicit true triggers the 400 refusal
- [Phase 17]: handlers.statusForCode is the single error_code to HTTP status table for all five Phase 17 endpoints;
  17-08 must call writeError/writeGitError instead of choosing a status
- [Phase 17]: auditRedactions is the single emission point for the SEC-03 redaction.audit record and is silent on a
  zero-redaction page; 17-08's GetRun calls it exactly once per response
- [Phase 17]: 17-08: GetRun calls 17-06's auditRedactions (not an inline slog record) as the single SEC-03 emission
  point — The plan sketched a second emission point under a different record name (iac_runner.redaction.audit vs
  redaction.audit), which would have broken the exactly-once contract and left ROADMAP SC-10 unmet while looking
  satisfied. WINDOWS.md entry 1 is now fixed.
- [Phase 17]: 17-08: NewRouter appends the three Phase 17 dependencies after the Phase 16 arguments; main.go passes nil
  with a TODO(17-07) — Appending (not reordering) keeps the RUN-01 /v1/version mount and the auth gate provably
  untouched. The nils are the deliberate plan boundary: 17-08 owns the router mount, 17-07 owns the startup wiring, and
  go build ./... exiting 0 is a Task 3 acceptance criterion.
- [Phase 17]: 17-08: read-handler error bodies use contract.ErrCodeApplyFailed (500) and contract.ErrCodeRunInvalidDir
  (400) instead of the plan's off-taxonomy "internal" literal — D-19/D-20 require a real ErrCode* value on every
  4xx/5xx, and statusForCode("internal") would have fallen through to 502 — disagreeing with the status the handler
  wrote. run_invalid_dir is the request-shape slot 17-06 already established.
- [Phase 17]: runs_retention_hours <= 0 is clamped to the 24h default at startup with a runs_retention_invalid warning —
  17-04's tickInterval floors the cadence at 1 minute and starts normally for retention=0, and Rotate(0) treats every
  terminal run as expired — so trusting a hand-edited /data/options.json would delete all finished runs on the first
  tick.
- [Phase 17]: The iac-runner/v0.2.0-0 git tag is intentionally outstanding — no tag created, nothing pushed — Pushing
  the tag fires the build-iac-runner image workflow while the v1.2 Phase 8 Cloudflare prerequisite is still open.
  Release command left for the operator: make update-version ADDON=iac-runner VERSION=0.2.0-0 (no NO_* flags).
- [Phase 17]: No backend-credential env projection was invented for the tofu child process — internal/jobq/exec.go
  attributes the export to 17-07 but no Phase 17 requirement covers it and nothing in the repo implements it.
  Credential-env minimality is therefore trivially satisfied (empty); designing which variables to project belongs to
  Phase 19 SC-3's three-backend matrix.
