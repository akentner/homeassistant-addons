---
phase: quick
plan: 260908-pfo
subsystem: infra
tags: [home-assistant, addon-schema, opentofu, yaml, versioning]

# Dependency graph
requires:
  - phase: 16-iac-runner-scaffold-auth-state-backends-healthcheck
    provides:
      "iac-runner/config.yaml options schema incl. schema.state_backend, statebackend factory with ErrUnsupported"
provides:
  - "iac-runner/config.yaml schema.state_backend as a plain list() enumeration — the HA Options UI now renders exactly
    r2 / s3 / local"
  - "iac-runner add-on version 0.2.1-1 (add-on-only subpatch; base semver 0.2.1 unchanged in build.yaml and README.md)"
  - "iac-runner/DOCS.md and .planning/REQUIREMENTS.md STBK-01 quoting the corrected enumeration, so no live spec copy
    can re-introduce the broken form"
affects: [phase-18-mqtt-discovery, phase-19-e2e-verification-docs, iac-runner-release]

# Actuals (#2632) — same estimateTokens scale (chars/4 over the realized diff)
actuals:
  tokens: 610
  tasks: 2
  commits: 2
plan_head_before: 457e67558308e7a8a287557d08fcc2ddb81a4562

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "HA options schema: plain literals inside list(...) — never a nested match(...), because the HA validator splits
      the list body on the pipe before any regex is considered"
    - "Add-on-only subpatch: bump config.yaml X.Y.Z-N by hand while build.yaml/README.md keep base semver;
      internal/validate-versions.sh is the gate"

key-files:
  created: []
  modified:
    - "iac-runner/config.yaml"
    - "iac-runner/DOCS.md"
    - ".planning/REQUIREMENTS.md"

key-decisions:
  - "list(r2|s3|local) without a trailing ? — the field stays required; a ? would silently make it optional"
  - "Version bumped by hand to 0.2.1-1 rather than via internal/update-version.py, which can only emit X.Y.Z-0 and has
    no subpatch-increment flag (one-time, user-approved exception to the repo's never-edit-versions-manually rule)"
  - "Two atomic task commits instead of the plan's single-commit success criterion — the batch dispatch mandates
    per-task atomicity; the three-file end state is byte-identical either way"
  - "Stale Go doc comment at iac-runner/cmd/runner/main.go:28 knowingly left untouched — no go toolchain on this host,
    so no Go edit can be compile-verified"

patterns-established:
  - "Prose-copy retirement: whenever a schema string is corrected, the live spec copies (DOCS.md + REQUIREMENTS.md) are
    corrected in the same plan, so a later gap-closure pass cannot read the stale requirement text as authority and
    revert the fix"

requirements-completed: [STBK-01]

coverage:
  - id: D1
    description:
      "schema.state_backend enumerates exactly r2, s3 and local as plain list() literals, with the documented default r2
      actually schema-valid"
    requirement: "STBK-01"
    verification:
      - kind: unit
        ref:
          'python3 -c "import yaml,sys; d=yaml.safe_load(open(''iac-runner/config.yaml'')); sys.exit(0 if
          d[''schema''][''state_backend'']==''list(r2|s3|local)'' and d[''version'']==''0.2.1-1'' else 1)"'
        status: pass
      - kind: integration
        ref: "python3 internal/validate-addon-config.py iac-runner"
        status: pass
    human_judgment: false
  - id: D2
    description:
      "bind_address validation byte-identical before and after (T-PFO-02, the high-severity collateral-edit threat)"
    verification:
      - kind: unit
        ref: "grep -Fq 'bind_address: \"match(^auto$|^(([0-9]{1,3}\\\\.){3}[0-9]{1,3})$)?\"' iac-runner/config.yaml"
        status: pass
      - kind: unit
        ref:
          "git diff -U0 -- iac-runner/config.yaml | grep '^[+-][^+-]' | grep -vE 'version:|state_backend:' — zero
          residue lines"
        status: pass
    human_judgment: false
  - id: D3
    description: "3-file version scheme intact at the 0.2.1-1 / 0.2.1 / v0.2.1 triple (T-PFO-03)"
    verification:
      - kind: integration
        ref: "make validate-versions"
        status: pass
    human_judgment: false
  - id: D4
    description:
      "No live YAML/Markdown copy of the nested list(match(...)) form survives under iac-runner/ or in
      .planning/REQUIREMENTS.md"
    verification:
      - kind: unit
        ref:
          "! grep -rFn 'list(match(' iac-runner/ --include='*.yaml' --include='*.md' && ! grep -Fn 'list(match('
          .planning/REQUIREMENTS.md"
        status: pass
      - kind: integration
        ref: "make lint (pre-commit run --all-files)"
        status: pass
    human_judgment: false
  - id: D5
    description:
      "The HA add-on Configuration page renders exactly three selectable state_backend values (r2 / s3 / local) with r2
      selectable"
    requirement: "STBK-01"
    verification: []
    human_judgment: true
    rationale:
      "The observable truth lives on the live HA instance and cannot be proven from the repo — the Supervisor must
      re-read the add-on manifest before the corrected picker renders. Operator action, see User Setup Required."

# Metrics
duration: 6min
completed: 2026-09-08
status: complete
---

# Quick 260908-pfo: iac-runner state_backend Options Schema Summary

**The HA Options picker for `state_backend` now enumerates `r2` / `s3` / `local` instead of three regex fragments,
shipped as the add-on-only subpatch `0.2.1-1`, with both live prose copies of the broken schema string retired.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-09-08T16:52:21Z
- **Completed:** 2026-09-08T16:57:53Z
- **Tasks:** 2 of 2
- **Files modified:** 3

## Accomplishments

- **Fixed the root cause.** `iac-runner/config.yaml:35` read `list(match(^(r2|s3|local)$))`. The HA options validator
  splits the body of `list(...)` on the pipe character _before_ any regex is considered, so the nested `match(...)` was
  never evaluated — the Configuration page rendered three bogus radio options (`match(^(r2`, `s3`, `local)$)`) and the
  documented default `r2` matched none of them. The line now reads `  state_backend: "list(r2|s3|local)"`, which is the
  form every other add-on in this repo already uses (`authentik:34`, `coding-assistants:69`, `gatus:36-37`,
  `meridian:40`, `network-tools:75`, `phone-logger:107`). `iac-runner` was the only outlier.
- **Narrowed, not widened, validation.** `list(...)` constrains the value to exactly the three enumerated literals, and
  no trailing `?` was added so the field stays required. The second, independent layer is untouched:
  `iac-runner/internal/statebackend/factory.go:25` still returns `ErrUnsupported`, which `cmd/runner/main.go:175` turns
  into a `state_backend_init_failed` record plus `os.Exit(1)`.
- **Shipped it as a subpatch.** `config.yaml` version `0.2.1-0` → `0.2.1-1`. `build.yaml` (`VERSION` and
  `RUNNER_VERSION` both `"0.2.1"`) and `README.md` (`version-v0.2.1-blue` badge) are correct as-is and were verified
  absent from the diff.
- **Closed the revert path.** The two _live_ prose copies of the broken string — `iac-runner/DOCS.md:79` and the STBK-01
  bullet at `.planning/REQUIREMENTS.md:264` — now quote the corrected enumeration. This mattered beyond tidiness:
  STBK-01 is marked `[x]` complete, so a later verification or gap-closure pass reading it as the spec would have
  flagged the corrected `config.yaml` as non-compliant and reverted the fix.

## Task Commits

Each task was committed atomically:

1. **Task 1 (tracer): Fix the state_backend enumeration and bump to the 0.2.1-1 subpatch** — `ca2e686` (fix)
2. **Task 2: Retire the two live prose copies of the broken string and run the full gate** — `e01cb94` (docs)

**Plan metadata:** not committed — batch artifacts (PLAN.md / SUMMARY.md) are owned by the orchestrator.

Measured: `git rev-list --count 457e6755..HEAD` = 2.

## Files Created/Modified

- `iac-runner/config.yaml` — line 35 `schema.state_backend` → `"list(r2|s3|local)"`; line 3 `version` → `"0.2.1-1"`.
  Exactly two changed lines; every other byte identical.
- `iac-runner/DOCS.md` — the `state_backend` section's schema sentence now quotes `list(r2|s3|local)`. The clause
  crediting `statebackend.New` / `ErrUnsupported` as the runtime layer is preserved verbatim — that is the
  defense-in-depth claim this change relies on. Prettier reflowed the two-line sentence.
- `.planning/REQUIREMENTS.md` — the STBK-01 bullet quotes the corrected enumeration. Prettier reflowed the bullet.

## Verification

Full offline gate, all exit 0 on the committed tree:

| Gate                                                                                         | Result                                                                              |
| -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| YAML round-trip (`schema.state_backend` == `list(r2\|s3\|local)` AND `version` == `0.2.1-1`) | pass                                                                                |
| `bind_address` byte-exact grep (T-PFO-02, BLOCKING)                                          | pass                                                                                |
| `! grep -rFn 'list(match(' iac-runner/ --include='*.yaml' --include='*.md'`                  | pass (0 matches; pre-change count was 2)                                            |
| `! grep -Fn 'list(match(' .planning/REQUIREMENTS.md`                                         | pass (0 matches; pre-change count was 1)                                            |
| `make validate-versions` / `./internal/validate-versions.sh`                                 | pass — `Version validation passed for all add-ons!`                                 |
| `python3 internal/validate-addon-config.py iac-runner`                                       | pass — `Add-on config validation passed.`                                           |
| `make lint`                                                                                  | pass (see prettier note below)                                                      |
| Changed-file set `457e6755..HEAD`                                                            | exactly `iac-runner/config.yaml`, `iac-runner/DOCS.md`, `.planning/REQUIREMENTS.md` |
| Diff-residue gate (no changed body line outside `version:` / `state_backend:`)               | pass — zero residue                                                                 |

**`make lint` needed exactly one prettier re-run.** The first pass exited 1 with
`prettier ... Failed — files were modified by this hook` listing `.planning/REQUIREMENTS.md` and `iac-runner/DOCS.md`;
prettier's `proseWrap: always` re-wrapped both edited sentences because the corrected string is shorter. The second pass
exited 0 with every hook green. **`iac-runner/config.yaml` was not touched by any lint pass** — confirmed via
`git diff --name-only -- iac-runner`, which listed only `DOCS.md` after the autofix. Prettier is `types: [markdown]` and
structurally cannot rewrite the manifest, so this was the expected-clean outcome rather than a lucky one.

No Go toolchain was required or invoked; this host has no `go` binary and nothing in this plan touches Go source.

## Decisions Made

- **`list(r2|s3|local)` with no trailing `?`.** The field is currently required and stays required.
  `meridian/config.yaml:51` is the shape matched.
- **Hand-edited version, deliberately.** `internal/update-version.py` always writes `X.Y.Z-0` and exposes no increment
  flag, so it cannot express a subpatch. This single manual edit is a user-approved, one-time exception to the repo's
  "never edit versions manually" rule; `internal/validate-versions.sh` (which is `always_run: true` in pre-commit)
  remains the drift gate and passes on the `0.2.1-1` / `0.2.1` / `v0.2.1` triple.
- **`bind_address` untouched.** Its bare `match(^auto$|^(...)$)?` keeps its pipe _inside_ the regex, which the HA
  validator handles correctly, and `terraform-bridge/config.yaml:32` ships the identical string. This is the
  high-severity threat T-PFO-02 and was gated two independent ways (byte-exact grep + zero-residue diff check).

## Deviations from Plan

### 1. [Plan-adaptation] Two atomic commits instead of the plan's single-commit success criterion

- **Found during:** Task 2 (commit step)
- **Issue:** The plan's `<success_criteria>` asks for "exactly three files changed, in one atomic commit", while Task
  2's acceptance criterion 7 names a commit message covering both concerns. The batch dispatch contract, however,
  mandates one atomic commit per task.
- **Resolution:** Executed as two commits — `ca2e686` (Task 1, `config.yaml`) and `e01cb94` (Task 2, `DOCS.md` +
  `REQUIREMENTS.md`). Task 1's message carries the plan's suggested subject line verbatim
  (`fix(iac-runner): render state_backend picker correctly + 0.2.1-1 subpatch`), so criterion 7's substance is met.
- **Impact:** None on the end state — the three-file diff at `457e6755..HEAD` is byte-identical to what a single commit
  would have produced. Per-task atomicity also makes the tracer task independently revertible, which the plan's
  `<reversibility>` note explicitly wanted.

### 2. [Scope-boundary] Broken-windows ledger not appended

- **Issue:** The stale Go doc comment (below) is a genuine `todo`-kind defect worth registering in
  `.planning/WINDOWS.md`.
- **Resolution:** Not appended. `WINDOWS.md` is not in this plan's `files_modified`, and Task 1 criterion 5 plus the
  plan's success criteria assert an exact three-file change set — an unplanned fourth tracked file would have failed the
  gate, and leaving it uncommitted in a worktree that is merged by branch would simply lose the write.
- **Impact:** The defect is reported in the section below instead, as the plan's `<output>` requires. No stubs, skipped
  tests, or unrun `<verify>` commands exist in this item, so nothing else was owed to the ledger.

---

**Total deviations:** 2 (1 plan-adaptation, 1 scope-boundary). No Rule 1-4 auto-fixes were needed. **Impact on plan:**
No scope creep. All acceptance criteria passed as written on the first attempt; no criterion had to be reinterpreted.

## Issues Encountered

None. The `make lint` non-zero first exit was anticipated by the plan and is documented above as expected auto-fixer
behavior, not a failure.

## Out-of-Scope Stale References Left Behind

Deliberately not edited — reported here per the plan's `<output>`:

1. **`iac-runner/cmd/runner/main.go:28`** — the doc comment above `var defaultStateBackend = "r2"` still reads
   `// with state_backend: list(match(^(r2|s3|local)$)).` This host has no `go` binary, so no Go edit could be
   compile-verified; editing it blind was rejected. It is a comment only — zero runtime effect. **Recommended
   follow-up:** fold this one-line comment correction into the next Phase 18/19 plan that already runs `go build ./...`,
   so the change lands behind a real compile gate. The region-limited grep gate (`--include='*.yaml' --include='*.md'`)
   was scoped precisely so this known-untouched comment cannot fail a future verification pass.
2. **`.planning/ROADMAP.md`** — holds one copy of the old string. Historical execution record, not a live spec;
   intentionally out of scope, which is why the Task 2 gate named `REQUIREMENTS.md` explicitly rather than recursing
   over `.planning/`.
3. **`.planning/phases/16-.../16-01-PLAN.md`, `16-03-PLAN.md`, `.planning/phases/17-.../17-01-PLAN.md`** — same
   rationale. These are completed-phase plan records; rewriting them would falsify the execution history.

## User Setup Required

**The repo change alone cannot be observed in the UI.** The corrected picker renders only after the Supervisor re-reads
the add-on manifest. Operator steps:

1. **Settings → Add-ons → Add-on Store → three-dot menu → Check for updates**, then **iac-runner → Update** (to
   `0.2.1-1`).
2. **Settings → Add-ons → IaC Runner → Configuration** — confirm the `state_backend` control offers exactly `r2`, `s3`
   and `local`, with `r2` selectable (it is not today).

`iac-runner/config.yaml` has no `image:` key, so the Supervisor builds this add-on locally: the update does **not**
depend on a ghcr artifact or on the outstanding `iac-runner/v0.2.1` tag.

## Next Phase Readiness

- STBK-01's spec text and its implementation now agree, so Phase 18 (MQTT Discovery) and Phase 19 (E2E verification +
  operator runbook) can treat `list(r2|s3|local)` as the authoritative schema without re-litigating it.
- Phase 19's three-backend verification matrix is now actually reachable from the Options UI — previously no valid
  `state_backend` value could be selected there at all.
- No blockers introduced. The outstanding `iac-runner/v0.2.0-0` / `v0.2.1` tag decision (deferred pending the v1.2 Phase
  8 Cloudflare prerequisite) is unchanged by this subpatch, since the base semver did not move.

## Self-Check: PASSED

- `iac-runner/config.yaml` — FOUND, `schema.state_backend` == `list(r2|s3|local)`, `version` == `0.2.1-1`
- `iac-runner/DOCS.md` — FOUND, contains `list(r2|s3|local)`
- `.planning/REQUIREMENTS.md` — FOUND, contains `list(r2|s3|local)`
- Commit `ca2e686` — FOUND in `git log`
- Commit `e01cb94` — FOUND in `git log` (HEAD)
- Working tree clean apart from this SUMMARY; `make lint` exits 0 on the committed state

---

_Quick: 260908-pfo_ _Completed: 2026-09-08_
