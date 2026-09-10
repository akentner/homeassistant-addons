---
phase: quick-260910-vyh
plan: 01
subsystem: repo-tooling
status: complete
tags: [pre-commit, security-guard, hadolint, makefile, add-on-discovery, documentation]

requires:
  - ".github/workflows/opencode.yml job-level author gate (shipped by quick-260910-vh7)"
  - "internal/verify-opencode-gate.py (72-row truth table, shipped by quick-260910-vh7)"
provides:
  - "pre-commit hook `verify-opencode-gate` — the opencode author gate is now an enforced invariant, not a comment"
  - "make docker-build-check covers tools/test-addon/Dockerfile under the strict hadolint ruleset"
  - "all four add-on discovery sites name the definition they implement and cross-reference the other"
affects:
  - ".pre-commit-config.yaml"
  - "Makefile"
  - "internal/validate-versions.sh"
  - "internal/validate-addon-config.py"

tech-stack:
  added: []
  patterns:
    - "pre-commit `repo: local` + `language: system` + `pass_filenames: false` for a whole-repo invariant prover"
    - "`files:`-scoped guard hook rather than `always_run` when the verifier reads exactly one file"
    - "glob widening (`*/ tools/*/`) as the repo's third use of the explicit-`tools/`-pass discovery idiom"

key-files:
  created: []
  modified:
    - ".pre-commit-config.yaml"
    - "Makefile"
    - "internal/validate-versions.sh"
    - "internal/validate-addon-config.py"

decisions:
  - "Scope verify-opencode-gate with `files:` (opencode.yml + the verifier itself), NOT `always_run: true` — the verifier reads exactly one file, so that file changing is the complete trigger set."
  - "Accept that DELETING .github/workflows/opencode.yml does not fire the hook: pre-commit passes no deleted paths, and a deleted workflow cannot be triggered, so there is nothing left to guard. `always_run: true` would exit 2 on an unreadable workflow and make a legitimate removal permanently red."
  - "Widen docker-build-check with the `*/ tools/*/` glob rather than porting the find-based depth-2 shape, because the recipe concatenates the loop variable with `Dockerfile` and strips a trailing slash — a find list has no trailing slash and would look for `tools/test-addonDockerfile`."
  - "Keep the two add-on definitions separate and name them at all four sites instead of unifying them; unification would either strip the fixture from version/config validation or falsely advertise it as a shipped add-on."
  - "Replace the plan's literal `test $EC -eq 1` gate for docker-build-check with a differential assertion against the HEAD-baseline Makefile, because GNU Make exits 2 for any failed recipe."

metrics:
  duration_minutes: 10
  completed: 2026-09-10

actuals:
  tokens: 1500
  tasks: 3
  commits: 3

plan_head_before: 240662155214fbe7e90d4b425efed1235fb208c7
---

# Phase quick-260910-vyh Plan 01: Close the docker-build-check coverage gap Summary

Three holes closed with three atomic commits: the opencode author gate is now enforced by pre-commit (proven red on two
independent tamper shapes), `make docker-build-check` applies its strict hadolint ruleset to the nested `tools/test-addon`
fixture, and all four add-on discovery sites now name which of the repo's two deliberate definitions they implement.

## What Shipped

| Task | Commit | Files | Outcome |
| ---- | ------ | ----- | ------- |
| 1 — wire the opencode gate verifier into pre-commit (VYH-A) | `01cd85b` | `.pre-commit-config.yaml` (+27) | `verify-opencode-gate` hook, `language: system`, `pass_filenames: false`, two-path `files:` regex, 27-line WHY comment |
| 2 — widen docker-build-check hadolint discovery (VYH-B + part of VYH-C) | `9304245` | `Makefile` (+21/-1) | `for addon_dir in */ tools/*/` + 20-line definition comment above the target |
| 3 — name the definition at all four discovery sites (VYH-C) | `1423b3c` | `Makefile`, `internal/validate-versions.sh`, `internal/validate-addon-config.py` (+28) | comment-only; each site names its definition and cross-references the other |

### Task 1 — the security regression guard

`internal/verify-opencode-gate.py` proves the truth table of the job-level `if:` over 72 fixture rows but nothing ran it.
It now runs from pre-commit whenever `.github/workflows/opencode.yml` or the verifier itself changes.

Adversarial verification, all six steps green:

| Step | Assertion | Result |
| ---- | --------- | ------ |
| 0 | `pre-commit validate-config` silent; `yamllint` on the config | Passed |
| 1 | hook fires and Passes on the untampered gate, exit 0 | Passed |
| 2 | `--files README.md` → `(no files to check)Skipped`, exit 0 | Skipped as designed |
| 3 | tamper A (author clause deleted) → `Failed`, `FAIL A2 denial — 30 untrusted rows allowed` | red, A1/A3/A4/A5 still PASS |
| 4 | tamper B (`CONTRIBUTOR` promoted) → `Failed`, `FAIL A2 denial — 6 untrusted rows allowed` | red, A1/A3/A4/A5 still PASS |
| 5 | `git hash-object` = `bb9d1162327da41f894504f96d3d257ebd74c0ed`, `git status --porcelain` empty | restored byte-identical |
| 6 | `pre-commit run --all-files verify-opencode-gate` → `Passed`, not `Skipped` | CI path reaches the hook |

Because A1 (parity), A3 (detectability control), A4 (positive control) and A5 (grammar guard) stayed PASS under both
tamper shapes, the redness is attributable to the denial invariant, not to a crash. The whole cycle ran inside a single
shell with an `EXIT` trap performing `git checkout --` plus a `cmp`-guarded fallback restore, so no window existed in
which a tampered security workflow could have been staged. The Task 1 commit stages only `.pre-commit-config.yaml`.

Live confirmation of the scoping in the real commits: all three commits printed
`Verify opencode.yml comment-trigger author gate......(no files to check)Skipped`, because none of them touched the two
guarded paths.

### Task 2 — the lint-coverage guard

`docker-build-check` runs hadolint with DL3008 and DL3006 **not** suppressed, which is stricter than the pre-commit
`hadolint` hook (which suppresses DL3008). It discovered only depth-1 directories, so the fixture never received that
ruleset. One two-token glob change fixed it:

```make
for addon_dir in */ tools/*/; do \
```

Measured effect — set equality by `diff`, so a missing or an extra add-on fails loudly by name:

- 10 `Checking` lines: `authentik`, `coding-assistants`, `gatus`, `iac-runner`, `markdown-renderer`, `meridian`,
  `network-tools`, `phone-logger`, `terraform-bridge`, `tools/test-addon`.
- hadolint finding set still exactly `authentik/Dockerfile:15 DL3008` (diff-asserted against a one-line expectation file).
- `❌ 1 Dockerfile(s) failed hadolint check.` unchanged.
- `hadolint --ignore DL3018 --ignore DL3059 --ignore DL4006 --ignore DL3016 tools/test-addon/Dockerfile` exits 0 — the
  coverage widened without importing a new failure.
- `tools/test-bridge-fixture/` has no `config.yaml` and is correctly skipped by the `[ -f ... ]` guards.

### Task 3 — the anti-misdiagnosis deliverable

The four sites now each state their own definition, so a reader landing on any one of them learns why the others differ
without opening the other three. All four carry the `two deliberate definitions` family marker.

| Site | Definition named | Population |
| ---- | ---------------- | ---------- |
| `Makefile` above `validate-addons:` | `is a shipped add-on` | 9 top-level |
| `Makefile` above `docker-build-check:` | `must pass Dockerfile linting` | 10 incl. `tools/test-addon` |
| `internal/validate-versions.sh` (depth-2 block) | `must pass version validation` | 10 incl. `tools/test-addon` |
| `internal/validate-addon-config.py` (`else:` branch) | `must pass config-schema validation` | 10 incl. `tools/test-addon` |

Behaviour proven unchanged in kind: `make validate-addons` still reports exactly the 9 shipped names,
`internal/validate-versions.sh` still prints the same 10 in the same order, `internal/validate-addon-config.py` still
exits 0, `make docker-build-check` still reports 10. The `git diff -U0` for both `internal/` scripts contains comment
lines only (asserted by filtering `+`/`-` lines down to non-comment, non-blank and requiring an empty result).

## Verification

Whole-plan gate, all green:

- `make check-all` → exit 0.
- `make docker-build-check` → 10 Dockerfiles, set-equal to the expectation.
- `.github/workflows/opencode.yml` → `git status --porcelain` empty, blob `bb9d1162327da41f894504f96d3d257ebd74c0ed`.
- Three atomic commits; committed file set is exactly the four planned files — no `.planning/` path in any of them.
- `git rev-list --count 2406621..HEAD` = 3.

**Offline confirmed by composition, not by assertion:** the new hook declares no `additional_dependencies`, so pre-commit
resolves and fetches nothing; `internal/verify-opencode-gate.py` imports only `argparse`, `sys`, `pathlib`, `typing` and
`yaml`, contains no `urllib`/`requests`/`socket`/`http` call, and its only URL-shaped string is the fixture constant
`https://example.invalid/comment/1`. Every `check-all` member (`lint`, `validate-addons`, `validate-versions`,
`validate-dockerfiles`) remains a local script.

## Deviations from Plan

### 1. [Rule 1 — plan-gate defect] `make docker-build-check` exits 2, not 1

- **Found during:** Task 2 verification.
- **Issue:** the plan's `<verify>` asserted `test "$EC" -eq 1` and `<critical_context>` recorded the HEAD baseline as
  "exit 1". GNU Make 4.4.1 exits **2** for any failed recipe; the recipe's own `exit 1` is what produces make's
  `*** [Makefile:140: docker-build-check] Fehler 1` message, which is not make's own exit status. Measured directly
  against `git show HEAD:Makefile` via `make -f`: exit **2** at the unmodified baseline as well. So the gate was red at
  HEAD for the wrong reason and could never have gone green.
- **Fix:** replaced the literal with a differential assertion — the post-change exit code must equal the exit code of the
  HEAD-baseline Makefile (2 == 2). This is strictly stronger than the literal because it detects a change in exit *kind*
  rather than matching a hardcoded number. The two substantive invariants the gate existed for are unchanged and still
  asserted: the hadolint finding set is diff-equal to `authentik/Dockerfile:15 DL3008`, and the
  `❌ 1 Dockerfile(s) failed hadolint check.` line is present.
- **Files modified:** none — verification-only correction.
- **Recorded in:** `.planning/WINDOWS.md` (kind `deviation`).

### 2. [Rule 3 — blocking] comment length had to fit the gate's `grep -B` window

- **Found during:** Task 2 verification (`g1`/`g2` greps failed on the first draft).
- **Issue:** the plan's gates read the comment through `grep -B 20 '^docker-build-check:'` and
  `grep -B 12 '^validate-addons:'`. My first `docker-build-check` comment was 28 lines, so the paragraph carrying
  `two deliberate definitions` and `must pass Dockerfile linting` fell outside the 20-line window and the gate reported
  a missing comment that was in fact present.
- **Fix:** compressed the `docker-build-check` comment to exactly 20 lines and authored the `validate-addons` comment at
  exactly 12, retaining every mandated content element (definition name, why-wider/why-depth-1 rationale, the
  `two deliberate definitions` marker, the DL3008/DL3006 stricter-ruleset reason, the glob-not-find trailing-slash
  contract, and the unclosed `internal/validate-dockerfile-args.sh:64` boundary). No content was dropped, only tightened.
- **Files modified:** `Makefile` (within Task 2 and Task 3 before commit).

No other deviations. No authentication gates. No architectural (Rule 4) decisions required.

## Out-of-Scope Boundaries Held

Nothing on the plan's forbidden list was touched. Explicitly verified:

- No rename of `internal/`, `docs/` or `tools/`; no naming convention introduced. Exclusion still works by absence of
  marker files.
- The two add-on definitions were **named**, not unified.
- `authentik/Dockerfile:15 DL3008` left open; no `--ignore` list extended anywhere; no Dockerfile edited.
- `.github/workflows/**` unchanged — `opencode.yml` was tampered transiently in Task 1 only and restored byte-identical.
- `internal/verify-opencode-gate.py` logic untouched (its path appears only in the hook's `files:` regex).
- `zizmor.yml`, the `unpinned-uses` relaxation, the 27 pre-existing zizmor deferrals, trivy/govulncheck/CodeQL/SBOM/
  SECURITY.md: all untouched.
- The ARG-before-FROM depth asymmetry at `internal/validate-dockerfile-args.sh:64` was **recorded, not closed** — the
  `docker-build-check` comment states it as a known boundary with the file:line, and notes that closing it would change
  `make check-all` via `validate-dockerfiles`.

## Known Stubs

None. The added lines contain no `TODO`, `FIXME`, `placeholder`, `XXX` or `HACK` marker, no skipped test, and every
`<verify>` block in the plan was executed.

## Threat Model Coverage

All `mitigate` dispositions in the plan's register were applied:

- **T-vyh-01** (tampering the workflow during verification) — backup `cp`, per-shape `git checkout --`, `cmp`-guarded
  fallback, `EXIT` trap, asserted blob hash, empty `git status --porcelain`, both tamper scripts `sys.exit` on anchor
  drift rather than writing a guess, and a Task 1 commit that staged only `.pre-commit-config.yaml`.
- **T-vyh-02** (future gate-widening edits) — the whole point of the hook; proven red on two independent shapes.
- **T-vyh-07** (`CONTRIBUTOR` reported by `renovate[bot]`) — tamper shape B is exactly this regression and it fails closed.
- **T-vyh-SC** (package-manager tampering) — not applicable by construction: no install performed, `language: system`
  with no `additional_dependencies`, so pre-commit fetched nothing.

No new threat surface was introduced: no network endpoint, no auth path, no file-access pattern change, no schema change
at a trust boundary.

## Self-Check: PASSED

- `.pre-commit-config.yaml` — FOUND, contains `id: verify-opencode-gate`
- `Makefile` — FOUND, contains `for addon_dir in */ tools/*/`
- `internal/validate-versions.sh` — FOUND, contains `must pass version validation`
- `internal/validate-addon-config.py` — FOUND, contains `must pass config-schema`
- Commit `01cd85b` — FOUND
- Commit `9304245` — FOUND
- Commit `1423b3c` — FOUND
