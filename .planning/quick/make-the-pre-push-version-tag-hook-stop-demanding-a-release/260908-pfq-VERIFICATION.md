---
phase: quick-260908-pfq
verified: 2026-09-08T18:20:00Z
status: passed
score: 12/12 must-haves verified
covered_files:
  - ".github/RELEASE.md"
  - ".planning/quick/make-the-pre-push-version-tag-hook-stop-demanding-a-release/260908-pfq-PLAN.md"
  - ".planning/quick/make-the-pre-push-version-tag-hook-stop-demanding-a-release/260908-pfq-SUMMARY.md"
  - ".planning/quick/make-the-pre-push-version-tag-hook-stop-demanding-a-release/deferred-items.md"
  - "AGENTS.md"
  - "README.md"
  - "docs/UPDATE_VERSION.md"
  - "internal/check-version-tags.sh"
  - "internal/setup-hooks.sh"
covered_digest: "v1:sha256:77a2e3ae31eaa2decf8e72533ff9a0b1f3b8834a0f9d31f62d5205539f78dd2b"
behavior_unverified: 0
overrides_applied: 0
---

# Quick 260908-pfq: Pre-push version-tag hook — Verification Report

**Item goal:** Stop `internal/check-version-tags.sh` from demanding a release tag for the two add-ons the Supervisor
builds locally, via an explicit two-entry allowlist (`iac-runner`, `terraform-bridge`) — not the inferred "no `image:`
key" rule — keeping `primary_tag`/`legacy_tag` enforcement intact everywhere else, making the skip visible, guarding
against allowlist drift, and re-installing the hook so the change takes effect.

**Verified:** 2026-09-08T18:20:00Z **Status:** passed **Re-verification:** No — initial verification

## Verification instrument — rebuilt, not reused

The plan's harness was defective (it copied the hook into the clone once; `git commit -am` tracked it and every later
`git checkout -B ... origin/main` restored the pre-edit copy, so cases B–F silently tested the unmodified script). I did
**not** reuse the executor's patched copy at `/tmp/akentner/vt-hook-fixture.sh`. I wrote an independent harness at
`/tmp/akentner/claude-1000/-home-akentner-Projects-homeassistant-addons/bf0ae4e4-15b0-4003-bbbc-2d5648c38475/scratchpad/verify-hook.sh`
with a **structural** fix rather than a procedural one: the script under test lives **outside the clone working tree**
and is invoked as `bash "$HOOK"` with cwd inside the clone. No `git` operation inside the clone can therefore swap the
script being executed — the class of defect is eliminated, not merely patched.

I also strengthened three cases beyond the plan's assertions:

- Case A/E now require the attributing failure line (`<addon>: no matching tag ...`), not just `404 on update`.
- Case E additionally requires the exact expected tag name `authentik/v99.99.99-0`.
- Cases E and F additionally require **no `⊘` line anywhere in the output**, so a block cannot be credited to
  enforcement when it was really a skip plus an unrelated failure.

**The RED control is itself the isolation proof.** Because the change is committed on `main`, the clone's checked-out
tree contains the _edited_ hook. The RED run pointed `HOOK` at `git show a4ca23f:internal/check-version-tags.sh` and
still reproduced the pre-edit behaviour (B and F FAIL). Had the harness been executing the clone's tree copy, RED would
have come back all-PASS. It did not — so the harness demonstrably runs the script I selected.

| Run   | Hook under test                                                | Result                                                                           |
| ----- | -------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| RED   | `a4ca23f:internal/check-version-tags.sh` (pre-edit, 114 lines) | A, C, D, E PASS; **B, F FAIL**; exit 1 — reproduces the plan's recorded baseline |
| GREEN | `HEAD:internal/check-version-tags.sh` (current, 184 lines)     | **all six PASS** + 3 extra assertions PASS; exit 0                               |

B and F flip FAIL→PASS as a direct consequence of the hook edit, with A, C, D, E fixed at PASS on both sides. The cases
genuinely discriminate; a false "all six PASS" of the kind the original defect produced is ruled out.

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                                                                                        | Status     | Evidence                                                                                                                                                                                                                                                                                                  |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Case B: allowlisted pair at untagged `99.99.99-0` → exit 0, exactly two skip lines, each containing `built locally by the Supervisor`                                        | ✓ VERIFIED | GREEN run: `PASS B ... (exit 0)`, `PASS B exactly 2 skip lines`. RED: exit 1, 0 skip lines. No tag for `99.99.99-0` exists or could, so the pass can only originate in the new skip branch                                                                                                                |
| 2   | Case E: `authentik` (keyless, **not** allowlisted) at untagged `99.99.99-0` → still exit 1 with the `404 on update` rationale                                                | ✓ VERIFIED | GREEN: exit 1 with `❌ authentik: no matching tag for version '99.99.99-0' (expected authentik/v99.99.99-0)` + `404 on update`, and **no `⊘` in the output** — the block is attributable to the enforcement path, not an early exit or a skip                                                             |
| 3   | Case F (drift guard): allowlisted `iac-runner` declaring `image:` at an untagged version → warning naming `LOCAL_BUILD_ADDONS`, then still exit 1 with the `404` rationale   | ✓ VERIFIED | GREEN: exit 1 + `LOCAL_BUILD_ADDONS` + `iac-runner: no matching tag` + `404 on update`, and **no `⊘`** — it warns and falls through to enforcement, it does not skip. RED lacked the `LOCAL_BUILD_ADDONS` needle                                                                                          |
| 4   | Case A: `network-tools` (declares `image:`) untagged → still exit 1 (ghcr-404 protection unchanged)                                                                          | ✓ VERIFIED | GREEN and RED both `PASS A ... (exit 1)` with `network-tools: no matching tag`                                                                                                                                                                                                                            |
| 5   | Cases C and D: `coding-assistants` resolves via the untouched `primary_tag` and `legacy_tag` paths, both exit 0                                                              | ✓ VERIFIED | GREEN: `tag coding-assistants/v1.0.0-2 exists` (C) and `legacy format` (D), both exit 0; identical on RED                                                                                                                                                                                                 |
| 6   | All six fixture cases PASS and the harness exits 0                                                                                                                           | ✓ VERIFIED | Independent harness, GREEN exit 0, 9 PASS lines (6 cases + 3 added assertions); RED exit 1 as the discriminating control                                                                                                                                                                                  |
| 7   | `shellcheck -e SC1091 -e SC2034` on both scripts exits 0                                                                                                                     | ✓ VERIFIED | Run directly: exit 0. Also `shellcheck` hook `Passed` inside `pre-commit`                                                                                                                                                                                                                                 |
| 8   | Installed `.git/hooks/pre-push` is byte-identical to the source and executable                                                                                               | ✓ VERIFIED | `diff` against `internal/check-version-tags.sh` produced **no output**; `test -x` passed; `grep -c primary_tag` = **8** installed vs 8 source (was 0); mtime `2026-09-08 19:09` (was 2026-08-31 23:30)                                                                                                    |
| 9   | Installer integrity: re-evaluating `setup-hooks.sh`'s own `GIT_ROOT`/`HOOK_TARGET`/`HOOK_SOURCE` lines resolves both correctly, and the probe fails if `GIT_ROOT` is deleted | ✓ VERIFIED | Positive: `HOOK_SOURCE=[.../internal/check-version-tags.sh]`, `HOOK_TARGET=[.../.git/hooks/pre-push]` → PASS. Negative control (`GIT_ROOT=` line stripped): `HOOK_SOURCE=[/internal/check-version-tags.sh]` → FAIL as designed. `bash -n` parses clean. The probe discriminates; it is not a rubber stamp |
| 10  | The real repository gains no git tag and pushes nothing                                                                                                                      | ✓ VERIFIED | `git tag -l '*/v*' \| wc -l` = **39** before, during both harness runs (before=39 after=39), and after all verification. Total tags 46 unchanged. All fixture work confined to `mktemp -d`, removed afterwards. No `git tag`/`git push` issued                                                            |
| 11  | `built locally by the Supervisor` present (whitespace-normalised) in all six touched files                                                                                   | ✓ VERIFIED | Normalised `grep -F` returned OK for all six: both scripts + `docs/UPDATE_VERSION.md`, `.github/RELEASE.md`, `README.md`, `AGENTS.md`                                                                                                                                                                     |
| 12  | `pre-commit run --files` over the six touched paths exits 0                                                                                                                  | ✓ VERIFIED | Exit 0, no residual diff on a clean re-run. `shellcheck`, `prettier`, `markdownlint-cli2`, `Validate Add-on Versioning`, `Validate Add-on config.yaml Schema` all `Passed`                                                                                                                                |

**Score:** 12/12 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact                         | Expected                                                         | Status     | Details                                                                                                                                                                                                                                                                                                                                                                                                   |
| -------------------------------- | ---------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `internal/check-version-tags.sh` | `LOCAL_BUILD_ADDONS`, `is_local_build`, skip branch, drift guard | ✓ VERIFIED | Array at L75-78 (exactly `iac-runner`, `terraform-bridge`, one per line); 24-line comment L51-74 covering why-on / why-off / why-not-inferred / stale-name limitation, pointing at the PLAN; `is_local_build` L86-94 uses the full `if [[ ]]; then return 0; fi` form, not `&&`; skip+drift branch L118-141, placed after the empty-version guard (L116) and upstream of the `primary_tag` comment (L143) |
| `internal/setup-hooks.sh`        | worktree-safe hook path + install summary naming the exception   | ✓ VERIFIED | L29 `HOOK_TARGET="$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-push"`; L25 `GIT_ROOT` and L30 `HOOK_SOURCE` deliberately unchanged; summary L54-57 names `LOCAL_BUILD_ADDONS` and keeps the pinned phrase inside a single `echo` string                                                                                                                                             |
| `docs/UPDATE_VERSION.md`         | `## Pre-push hook` states the allowlist exception                | ✓ VERIFIED | Names both current members, states the removal criterion (`image:` key), and documents warn-and-enforce in one sentence                                                                                                                                                                                                                                                                                   |
| `.github/RELEASE.md`             | both unconditional-refusal assertions scoped                     | ✓ VERIFIED | Release-step-2 sentence and the `## Manual repair` "every modified `config.yaml`" sentence both scoped to non-allowlisted add-ons                                                                                                                                                                                                                                                                         |
| `README.md`                      | Repository Conventions bullet scoped                             | ✓ VERIFIED | "A pre-push hook enforces that any bumped version has a matching tag" now carries the `LOCAL_BUILD_ADDONS` exception                                                                                                                                                                                                                                                                                      |
| `AGENTS.md`                      | pre-push bullet names the allowlist                              | ✓ VERIFIED | Adds the exception plus an explicit "Do not reinstate an unconditional tag requirement; check that allowlist first"                                                                                                                                                                                                                                                                                       |

All six artifacts are substantive, wired (the two scripts are executed by the harness; the hook is the installed
`.git/hooks/pre-push`), and — for the docs — reference `LOCAL_BUILD_ADDONS` as the single source of truth rather than
duplicating the member list in four places.

### Key Link Verification

| From                             | To                                         | Via                                                                       | Status  | Details                                                                                                                                                                                                                                                            |
| -------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `LOCAL_BUILD_ADDONS` array       | enforce-vs-skip decision                   | `is_local_build "$addon_dir"` as an `if` condition (L121)                 | ✓ WIRED | Case B (member → skip) and case E (`authentik`, keyless non-member → enforce) prove both arms. Membership is explicit; absence of `image:` grants nothing — 7 of 9 add-ons are keyless yet only the 2 array entries skip                                           |
| allowlist entry gaining `image:` | drift guard                                | `grep -qE '^image:[[:space:]]*[^[:space:]]'` (L128) → warn, no `continue` | ✓ WIRED | Case F: warning printed, control falls through to the tag check, exit 1, no `⊘`. The `else` arm (L137-140) is the only path that `continue`s                                                                                                                       |
| new branch                       | untouched `primary_tag`/`legacy_tag` block | insertion sits upstream at L118-141; block begins L143                    | ✓ WIRED | `git diff --numstat a4ca23f..HEAD` = **70 insertions / 0 deletions**; 0 diff lines match `primary_tag\|legacy_tag\|tag_exists\|build_version=\|config_version=`. A pure-insertion diff is git's own proof that every original line survives unchanged and in order |
| `internal/setup-hooks.sh`        | `.git/hooks/pre-push`                      | `cp` (not symlink) — inert until reinstalled                              | ✓ WIRED | Reinstall confirmed: empty `diff`, executable bit set, `primary_tag` count 0 → 8, mtime moved from 2026-08-31 to 2026-09-08 19:09                                                                                                                                  |

### Behavioral Spot-Checks

| Behavior                                       | Command                                                                                                         | Result                                                                                                                              | Status                |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| Six-case fixture suite vs current hook         | `HOOK=hook-current.sh bash verify-hook.sh`                                                                      | 9 PASS, exit 0, tags 39=39                                                                                                          | ✓ PASS                |
| Same suite vs pre-edit hook (RED control)      | `HOOK=hook-preedit.sh bash verify-hook.sh`                                                                      | A/C/D/E PASS, B/F FAIL, exit 1                                                                                                      | ✓ PASS (expected RED) |
| shellcheck, repo ignore set                    | `shellcheck -e SC1091 -e SC2034 <both scripts>`                                                                 | exit 0                                                                                                                              | ✓ PASS                |
| Installed hook currency                        | `diff "$(git rev-parse --path-format=absolute --git-common-dir)/hooks/pre-push" internal/check-version-tags.sh` | empty                                                                                                                               | ✓ PASS                |
| Installer integrity probe + negative control   | `eval` of the script's own assignment lines                                                                     | PASS / FAIL-as-designed                                                                                                             | ✓ PASS                |
| Drift regex against 9 realistic `image:` forms | `grep -qE '^image:[[:space:]]*[^[:space:]]'`                                                                    | matches unquoted/double/single-quoted/extra-space; rejects `# image:`, indented sub-key, `image:` bare, `image: ` blank, `myimage:` | ✓ PASS                |
| `pre-commit run --files` over six paths        | `pre-commit run --files ...`                                                                                    | exit 0                                                                                                                              | ✓ PASS                |
| `set -e` safety of `is_local_build` non-match  | cases A, C, D, E all traverse the non-match arm                                                                 | full 404 message emitted and loop completed — no premature abort                                                                    | ✓ PASS                |

The drift regex probe (T-pfq-04, the false-negative-→-silent-skip risk) confirms every realistic _top-level_ `image:`
form is caught. The two non-matching YAML-adjacent forms are correct: an indented `  image:` is a sub-key, not the
top-level manifest key, and a blank value declares no image.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact                                                                                                                                                             |
| ---- | ---- | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| —    | —    | none    | —        | No `TBD`/`FIXME`/`XXX` in any of the six modified files; no `TODO`/`HACK`/`PLACEHOLDER` in any added diff line; no hardcoded-empty or unwired data path introduced |

Scope hygiene also checked: `git diff --name-only a4ca23f..HEAD` lists exactly the six `files_modified` — no add-on
`config.yaml`, `build.yaml` or add-on `README.md` version touched, and no fixture script added to `internal/` (the
harness stayed in a scratchpad outside the repo).

### Independently re-derived grounding facts

Confirmed against the working tree rather than taken from the plan:

- Add-ons declaring `^image:`: exactly `coding-assistants` and `network-tools`. Keyless: the other seven
  (`markdown-renderer`, `iac-runner`, `terraform-bridge`, `gatus`, `meridian`, `authentik`, `phone-logger`). This is
  what makes the allowlist-vs-inferred-rule decision load-bearing — the inferred rule would have exempted seven.
- Pre-edit script 114 lines, current 184 lines (= +70, matching the numstat).
- Real-repo `*/v*` tag count 39, unchanged throughout.

### Gaps Summary

None. Every must-have resolved to VERIFIED against executed evidence rather than inspection. The regression fence (cases
A, C, D, E) holds identically before and after the edit, and the two cases the item exists to change (B, F) flip only as
a consequence of the edit — proven through an instrument rebuilt from scratch with the plan's harness defect designed
out rather than patched around.

Not a gap, recorded for the record: `.planning/WINDOWS.md` remains un-writable via `gsd-tools windows append` ("Ledger
table region could not be located"). Pre-existing repo-level defect, correctly logged to `deferred-items.md` instead of
hand-editing cross-phase state. Outside this item's six files.

---

_Verified: 2026-09-08T18:20:00Z_ _Verifier: Claude (gsd-verifier)_
