---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: opentofu-bridge
status: Phase 11 complete (code + tests + 3 atomic commits; live-HA verification deferred to Phase 14)
last_updated: "2026-09-02T20:00:00.000Z"
progress:
  total_phases: 7
  completed_phases: 4
  total_plans: 10
  completed_plans: 8
  percent: 57
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-31)

**Core value:** Any upstream release is automatically reflected in the add-on within 24 hours — zero manual version
tracking. **Current focus:** Phase 15 — ci-hardening-provider-install-workflow `08-05-GAP-PLAN.md` remains ready to run
whenever Cloudflare setup lands.

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

| Phase | Name                                                   | Status                                 | Completed                                                     |
| ----- | ------------------------------------------------------ | -------------------------------------- | ------------------------------------------------------------- |
| 9     | Bridge Foundation + Token Rotation Spike               | Complete                               | 2026-08-31 (plans 01-04; H-1 + §10 transcripts in `spike-transcripts/`) |
| 10    | Auth Layer + Structured Logging + Healthcheck          | Complete                               | 2026-08-31 (plans 01-03; live-HA verify deferred to Phase 14) |
| 11    | Bridge Read API                                        | Complete (code + unit tests)           | 2026-09-02 (plans 01-02; 16 new tests; live-HA verification deferred to Phase 14) |
| 12    | Bridge Write API + Critical-Addon Safety + Concurrency | Not started                            | —                                                             |
| 13    | Provider + Resource + Data Sources + Schema Handshake  | Not started                            | —                                                             |
| 14    | Real-HA End-to-End Verification + Operator Docs        | Not started                            | —                                                             |
| 15    | CI Hardening + Provider Install Workflow               | Not started                            | —                                                             |

Phase dependency graph enforces: 9 → 10 → 11 → 12 → 13 → 14 → 15 (strictly serial). The empirical SUPERVISOR_TOKEN
rotation spike (H-1 from PITFALLS) was the first deliverable of Phase 9; it is the lowest-confidence item blocking the
rest. Spike ran 2026-08-31 → `token_unchanged`; Phase 10 auth already implements defensive re-read-per-call (see
`internal/supervisor/client.go:84-91` — `RoundTrip → t.tokenFn()` reads `os.Getenv("SUPERVISOR_TOKEN")` on every
outbound request). D-18 RESOLVED with defensive design; conservative re-verification deferred (see Todos).

## Current Position

Phase: 11 of 3 (ci-hardening-provider-install-workflow) (Bridge Read API) Last activity: 2026-09-02 -- Phase 11 SHIPPED:
3 atomic commits landed on main (docs(STATE), feat(11-01), feat(11-02)); 14+9 file changes with full canary-test
coverage (11 supervisor + 7 handlers + 1 router-level test); build/vet/gofmt clean; live-HA curl verification against
192.168.178.3:8124 still deferred to Phase 14 (requires Bridge image rebuild + redeploy + token recovery).

## Accumulated Context

### Key Decisions (v1.3)

| Decision                                                                                                                                                                                                                                                                        | Rationale                                                                                                                                                                                                                                                                                                                                      |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 7 phases, not 10 — vertical slices, not horizontal layers                                                                                                                                                                                                                       | Each phase produces a deployable, verifiable artifact; collapse read+write API into one phase was rejected (loses safety gate before write)                                                                                                                                                                                                    |
| Empirical SUPERVISOR_TOKEN rotation spike is Phase 9, not later                                                                                                                                                                                                                 | H-1 is the lowest-confidence item; designing auth on top of unverified token behavior risks rework (per PITFALLS research)                                                                                                                                                                                                                     |
| Per-slug mutex goes in Phase 12, not Phase 13                                                                                                                                                                                                                                   | Defense-in-depth for cross-host concurrent applies must exist BEFORE Provider surfaces destructive ops; STATE-03 paired with write endpoints                                                                                                                                                                                                   |
| Real-HA E2E gets its own phase (14), not folded into Provider (13)                                                                                                                                                                                                              | Phase-8 pattern: empirical verification against live HA host deserves its own validation gate; docs written from observed behavior, not theory                                                                                                                                                                                                 |
| Phase 15 (CI + install-provider) is intentionally thin                                                                                                                                                                                                                          | The CI work is substantial (new build workflow, new test workflow, install verification); TOFU-04 is the single REQ-ID; non-req deliverables carry the weight                                                                                                                                                                                  |
| `homeassistant_addon_repository` deferred to v1.4 (per existing decision)                                                                                                                                                                                                       | PROJECT.md + REQUIREMENTS.md both record this; do NOT re-add in any v1.3 phase                                                                                                                                                                                                                                                                 |
| **Two-layer AUTH-05 masking (Plan 02):** slog.Handler wrapper scrubs every record + chi middleware strips Authorization from r.Header before request-log snapshot                                                                                                               | D-10 layered defense — if the slog scrubber ever regresses, the chi middleware still prevents leakage. Both proven by unit tests. Phase 10 plan 02 commits.                                                                                                                                                                                    |
| **/healthz probe (Plan 02):** real /supervisor/ping call with 2s context deadline, no caching. 503 body always empty (Content-Length: 0)                                                                                                                                        | D-07 freshness > p99 reduction at this poll cadence. D-08 prevents internal-state leak on health-check failure. Phase 10 plan 02 commits.                                                                                                                                                                                                      |
| **verify-script adaptation (Plan 02):** positive-control assertions rewritten to parse `bridge.token.issued` JSON and assert actor_token_fp == SHA-256[8](plaintext) instead of comparing against FAKE_TOKEN (the supervisor token the bridge never logs)                       | Plan-adaptation deviation. Adding a BRIDGE_TOKEN env override to TokenStore would be an out-of-scope architectural change; same invariants proven without it. Documented in 10-02-SUMMARY §Deviations.                                                                                                                                         |
| **Phase 10 H-1 implementation: re-read-per-call, NOT cache-at-startup (Plan 02 → client.go)** — `internal/supervisor/client.go:84-91` `RoundTrip → t.tokenFn()` reads `os.Getenv("SUPERVISOR_TOKEN")` on every outbound request. Empirical spike (2026-08-31) showed token unchanged; per-call re-read is the defensive default for unknown rotation behavior. | Earlier 09-SUMMARY.md text said "Phase 10 may cache at startup (cheap default)" — that was an aspirational design note, NOT what shipped. The shipped Phase 10 RoundTrip pattern is already conservative: re-read per call costs O(1) and makes the design robust to a future Supervisor change that introduces per-add-on token rotation. Plan 03's signals.go SIGHUP handler remains the natural hook for explicit force-re-read commands. |
| **2026-09-02 conservative decision: ASSUME SUPERVISOR_TOKEN MAY rotate** — empirically verified unchanged 2026-08-31 on haos-op3050-1, but the live system is now treated as if the token could rotate at any restart. Re-verification deferred to a low-risk window.                                                                                | User decision 2026-09-02: live-system conservatism wins over empirical single-shot result. Phase 10 design (re-read per call) already meets the assumption; no code change required. To be re-verified later via `internal/spike-h1-token-rotation.sh` against a maintenance-window host. |
| **AUTH-04 grace file format (Plan 03):** /data/bridge-token.grace is a 2-line plaintext format (hex64 + RFC3339) instead of JSON — keeps Plan 01's readGraceFile parser unchanged; D-13 per-request expiry semantics means the file becomes inert without background goroutines | Plan-adaptation choice. JSON would have been equally correct on disk but required rewiring the reader AND adding a JSON-path through Plan 01's already-committed code. Text format respects the existing reader and locks the security invariant (no plaintext ever) more defensively.                                                         |
| **AUTH-04 rotate write order (Plan 03):** TokenStore.Rotate writes the new primary hash BEFORE writing the grace file. If the grace write fails, the old token still authenticates against the new hash; on-disk primary state is always consistent                             | Failure-mode lockdown. Reversing the order would leave a window where the new token authenticates against /data/bridge-token but the old token does not — exactly the scenario D-02/D-12 are designed to prevent. Cost of writing primary first is one extra renamed file; cost of reversal is a window of forced 401s on a still-valid token. |
| **D-03 timestamp pair (Plan 03):** RotateResponse.GraceExpiresAt and OldTokenValidUntil are byte-identical RFC3339 strings — duplicated on purpose so Provider consumers can pick whichever schema field name they prefer without an extra hop                                  | Provider-side ergonomics. PROV-03 / PROV-05 reference these fields from Phase 13's resource shape; duplication costs zero on the wire (~70 bytes) and removes a constant from the Provider's schema mapping table.                                                                                                                             |

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

- [ ] **Conservative H-1 re-verification** — Empirical spike (2026-08-31) showed `SUPERVISOR_TOKEN` unchanged across
      Supervisor restart. Per user decision 2026-09-02 we now ASSUME the token MAY rotate. Phase 10's design is already
      defensive (re-read-per-call via `internal/supervisor/client.go:84-91`). When a lower-risk window arises
      (maintenance window, non-production host), RE-run `internal/spike-h1-token-rotation.sh` against a live host to
      confirm the assumption. Do NOT re-run during normal operation — `ha supervisor restart` disrupts every add-on.

- [x] Phase 9: **Capture H-1 spike transcript** — `internal/spike-h1-token-rotation.sh` committed (e29f5cd); executed
      against haos-op3050-1 on 2026-08-31 with explicit per-call authorization for Supervisor restart; transcript at
      `spike-transcripts/h1-20260831T153943Z.log`; pasted verbatim into `09-SUMMARY.md`; D-18 RESOLVED (`token_unchanged`)

- [x] Phase 9: **Capture §10 spike transcript** — `internal/spike-pitfalls10-backup-addon-config.sh` committed
      (6f254d5); executed against haos-op3050-1 on 2026-08-31 with explicit per-call authorization for `ha backups new`;
      transcript at `spike-transcripts/pitfalls10-20260831T153403Z.log`; pasted verbatim into `09-SUMMARY.md`;
      D-19 RESOLVED (`addon_config_backed_up`)

- [x] Phase 9: Extend `internal/validate-versions.sh` to enforce Bridge `build.yaml` == Provider `build.yaml` semver —
      done in 09-02 (`d0d516d`)

- [x] Phase 9: Scaffold `terraform-bridge/` 4-file pattern + `terraform-provider-homeassistant/` Go module — done in
      09-01 + 09-02

- [x] Phase 11: **Plan 11-01 drafted + verified** — `/.planning/phases/11-bridge-read-api/11-01-PLAN.md` (899 lines):
      tracer-first task builds `/v1/info` (BRIDGE-10, no-auth, `uptime_seconds` since `func main()` start) +
      `/v1/version` (BRIDGE-01, auth-required handshake for PROV-03); introduces `internal/version` package for
      shared semver constants; adds `terraform-bridge/internal/supervisor/testing.go` (NOT `_test.go`) so
      cross-package handler tests can use `WithBaseURLForTest` / `TokenFnForTest` helpers; 11 files touched

- [x] Phase 11: **Plan 11-02 drafted + verified** — `/.planning/phases/11-bridge-read-api/11-02-PLAN.md` (1059 lines):
      V1/V2 fallback machinery in `supervisor.Client` + `/v1/addons` (BRIDGE-02) + `/v1/addons/{slug}/info`
      (BRIDGE-03); `ErrNotFound` sentinel mapped to literal `{"error_code":"not_found"}` per BRIDGE-03; relaxed
      fallback treats V2-403+V1-404 as `ErrNotFound` too; 4 new tests (V2-success, V2-403-then-V1-200, V2/V1
      happy-path 200, V2-403-then-V1-404); 7 files touched

- [x] Phase 11: **Plan 11-01 executed** — 7 files created (supervisor/client_test.go, supervisor/testing.go,
      version/version.go, handlers/info.go + info_test.go, handlers/version_test.go, router_test.go) + 5 modified
      (supervisor/client.go, contract/types.go, handlers/version.go, router.go, cmd/bridge/main.go); 6 new tests +
      go build / vet / test / gofmt all green; 1 Rule-1 auto-fix (body-drain order in GetSupervisorInfo); `11-01-SUMMARY.md`
      written (328 lines). Staged but uncommitted.

- [x] Phase 11: **Plan 11-02 executed** — 4 files created (handlers/addons.go + addons_test.go, handlers/addon_info.go +
      addon_info_test.go) + 3 modified (supervisor/client.go, supervisor/client_test.go, router.go); 10 new tests +
      all-green pipeline; `11-02-SUMMARY.md` written (27.5 KB). Staged but uncommitted.

- [ ] **Phase 11 commit + push (awaiting user approval)** — staged set: 16 new files + 8 modified. Two atomic commits
      planned per plan (`feat(11-01): GET /v1/info + /v1/version (BRIDGE-10, BRIDGE-01)` and
      `feat(11-02): supervisor V1/V2 fallback + GET /v1/addons + /v1/addons/{slug}/info (BRIDGE-02, BRIDGE-03)`).
      Live curl tests against 192.168.178.3:8124 require rebuilding the Bridge image + redeploying on the HA host.
      Pre-commit `validate-versions.sh` is not impacted (Bridge version unchanged).

- [x] Phase 11: **3 atomic commits landed** — a6f1c36 docs(STATE): Phase 9 sync + Phase 11 in-progress tracking
      (1 file, 62+/18-); 9158869 feat(11-01): GET /v1/info + /v1/version + planning docs (14 files, 1684+/10-);
      40548c4 feat(11-02): V1/V2 fallback + /v1/addons + /v1/addons/{slug}/info + planning docs (9 files,
      1921+/0-). Build + vet + gofmt clean. Branch main is at 40548c4. Pre-commit validate-versions.sh did not
      fire (Bridge version unchanged).

- [ ] **STATE.md stale-on-deliverable (post-commit sync pending user approval)** — Phase 11 is shipped but the
      STATE.md update reflecting "Phase 11 complete" is unstaged in the working tree. Per user instruction "3
      Commits: state + feat(11-01) + feat(11-02)" we did not add a 4th commit for the doc-sync; it remains for
      the user to commit or amend. Until then STATE.md still reports "Phase 11 in-progress" on the committed
      HEAD, which is inaccurate.

### Blockers

- **Phase 8 gap-closure (`08-05-GAP-PLAN.md`) remains blocked** on user Cloudflare setup (Q-02 from 08-CONTEXT). v1.3
  Phase 9-15 runs in parallel per explicit user decision.

## Performance Metrics

| Phase                                                  | Plan  | Duration | Tasks    | Files |
| ------------------------------------------------------ | ----- | -------- | -------- | ----- |
| 06                                                     | 01    | 19 min   | 3        | 4     |
| 06                                                     | 02    | 36 min   | 3        | 9     |
| Phase 08 P01                                           | 2 min | 3 tasks  | 5 files  |
| Phase 08 P02                                           | 15    | 3 tasks  | 5 files  |
| Phase 08 P04                                           | 25    | 4 tasks  | 5 files  |
| Phase 09 P01                                           | 40    | 3 tasks  | 15 files |
| Phase 09 P02                                           | 458s  | 3 tasks  | 8 files  |
| Phase 9 P3                                             | 9min  | 3 tasks  | 5 files  |
| Phase 09 P04                                           | 25min | 4 tasks  | 3 files  |
| Phase 10 P01                                           | 35min | 3 tasks  | 11 files |
| Phase 10 P02                                           | 25min | 3 tasks  | 11 files |
| Phase 10 P02                                           | 25min | 3 tasks  | 11 files |
| Phase 10-auth-layer-structured-logging-healthcheck P03 | 4 min | 3 tasks  | 6 files  |
| Quick 260902-sa1 (State Sync)                           | ~5min | 1 task   | 1 file   |

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

## Session Continuity

Last session: 2026-09-02T20:00:00.000Z (Phase 11 SHIPPED — 3 atomic commits on main: docs(STATE), feat(11-01),
feat(11-02); 25 files committed total; tests green; STATE.md doc-sync pending user approval as 4th commit) Next
step: optional 4th commit for STATE.md doc-sync, then Phase 12 planning Resume file: None

---

_State initialized: 2026-04-04_ _Milestone v1.0 archived: 2026-04-04_ _Milestone v1.1 roadmap written: 2026-06-27_
_Milestone v1.2 (Phase 8, CI/CD Hardening) planned: 2026-08-30 from a GitHub Actions audit — 4 plans, requirements
CI-01..CI-10, nothing executed yet_ _Milestone v1.3 opentofu-bridge roadmap written: 2026-08-31 — 7 phases (9-15), 46
requirements mapped across TOFU/ AUTH/BRIDGE/PROV/STATE/LIFE/OPS — Phase 9 ready to plan_
