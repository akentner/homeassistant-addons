---
phase: quick-260910-vh7
plan: 01
subsystem: ci-security
tags: [github-actions, supply-chain, secrets, verification, opencode]
status: complete
requires:
  - .github/workflows/opencode.yml (pre-existing, comment-triggered)
  - zizmor.yml + .pre-commit-config.yaml security hooks (from quick-260910-u0m)
provides:
  - author_association trust gate on the opencode job
  - immutable exact-tag pin for anomalyco/opencode/github
  - internal/verify-opencode-gate.py (truth-table verifier, run by hand)
  - docs/DEVELOPMENT.md pinning exception + zizmor blind-spot record
affects:
  - .github/workflows/opencode.yml
  - docs/DEVELOPMENT.md
tech-stack:
  added: []
  patterns:
    - "Extract the expression under test out of the live file, never a copy pasted into the test"
    - "Anti-silent-pass controls: detectability control + positive control + grammar guard"
key-files:
  created:
    - internal/verify-opencode-gate.py
  modified:
    - .github/workflows/opencode.yml
    - docs/DEVELOPMENT.md
decisions:
  - "Trusted set is exactly OWNER/MEMBER/COLLABORATOR; CONTRIBUTOR denied because renovate[bot] already reports it here"
  - "Exact-tag pin @v1.18.30 as a documented exception to the floating-major policy (upstream publishes no major tag)"
  - "The zizmor unpinned-uses relaxation is left untouched; its ref-pin blind spot is recorded as an open follow-up"
  - "The verifier is deliberately NOT wired into pre-commit or make check-all — named deferral, not an oversight"
metrics:
  duration: ~35 min
  completed: 2026-09-10
actuals:
  tokens: 15500
  tasks: 2
  commits: 2
plan_head_before: 9dfca294b1874113270b630611668272809d71fe
---

# Quick Task 260910-vh7: Harden opencode.yml — author gate + immutable action pin

Closed two compounding live exposures on a PUBLIC repository: the `opencode` job's `if:` gated only on the comment
**body**, so any GitHub account could comment `/oc` and start a job holding `MINIMAX_API_KEY`, and that job handed the
secret to `anomalyco/opencode/github@latest` — a ref its upstream owner could repoint at will. The gate is now ANDed
with `author_association in {OWNER, MEMBER, COLLABORATOR}`, the action is pinned to the immutable tag `@v1.18.30`, and
`internal/verify-opencode-gate.py` proves the gate's 72-row truth table by evaluating the expression read out of the
workflow file — not by checking that the file parses.

## Commits

| Task | Commit    | Description                                                             |
| ---- | --------- | ----------------------------------------------------------------------- |
| 1    | `a3aca04` | author_association gate + `internal/verify-opencode-gate.py` (red-first) |
| 2    | `73898a4` | `@v1.18.30` exact-tag pin + two `docs/DEVELOPMENT.md` paragraphs         |

`git diff --stat 9dfca29..HEAD` — three files, exactly the three the plan authorized. `zizmor.yml` untouched.

```text
 .github/workflows/opencode.yml   |  25 ++-
 docs/DEVELOPMENT.md              |  17 ++
 internal/verify-opencode-gate.py | 448 +++++++++++++++++++++++++++++++++++++++
 3 files changed, 487 insertions(+), 3 deletions(-)
```

## `make check-all` baseline, captured BEFORE any edit

`make check-all` → **EXIT=0** on the untouched tree at `9dfca29`. There is therefore no pre-existing failure set to
carry forward: the post-change criterion is the strict one, `make check-all` must still exit 0. It does (see
Verification below). Full baseline transcript:

```text
🔍 Running lint checks...
✅ Validating add-on configurations...
pre-commit run --all-files
🔍 Validating add-on versions...
🔍 Validating Dockerfile ARG scope...
./internal/validate-versions.sh
./internal/validate-dockerfile-args.sh
Validating authentik/...
Found add-ons: authentik coding-assistants gatus iac-runner markdown-renderer meridian network-tools phone-logger terraform-bridge tools/test-addon

Validating authentik...
   config.yaml: 2026.8.2-0
   build.yaml:  2026.8.2
   README.md:   2026.8.2

Validating coding-assistants...
   config.yaml: 1.0.0-2
   build.yaml:  1.0.0
   README.md:   1.0.0

Validating gatus...
   config.yaml: 5.36.0-11
   build.yaml:  5.36.0
   README.md:   5.36.0

Validating iac-runner...
   config.yaml: 0.2.1-1
   build.yaml:  0.2.1
   README.md:   0.2.1

Validating markdown-renderer...
   config.yaml: 1.1.0-23
   build.yaml:  1.1.0
   README.md:   1.1.0

Validating meridian...
   config.yaml: 1.69.0-0
   build.yaml:  1.69.0
   README.md:   1.69.0

Validating network-tools...
   config.yaml: 0.5.0-1
   build.yaml:  0.5.0
   README.md:   0.5.0

Validating phone-logger...
   config.yaml: 1.0.6-0
   build.yaml:  1.0.6
   README.md:   1.0.6

Validating terraform-bridge...
   config.yaml: 0.3.0-0
   build.yaml:  0.3.0
✅ authentik/ validation passed
Validating coding-assistants/...
   README.md:   0.3.0

Validating tools/test-addon...
   config.yaml: 0.1.0-0
   build.yaml:  0.1.0
   README.md:   0.1.0


Cross-artifact check (TOFU-05):
   terraform-bridge/build.yaml: 0.3.0
   terraform-provider-homeassistant/build.yaml: 0.3.0
[0;32mVersion validation passed for all add-ons![0m
✅ coding-assistants/ validation passed
Validating gatus/...
✅ gatus/ validation passed
Validating iac-runner/...
✅ iac-runner/ validation passed
Validating markdown-renderer/...
✅ markdown-renderer/ validation passed
Validating meridian/...
yamllint.................................................................✅ meridian/ validation passed
Validating network-tools/...
✅ network-tools/ validation passed
Validating phone-logger/...
✅ phone-logger/ validation passed
Validating terraform-bridge/...
✅ terraform-bridge/ validation passed
Passed
trim trailing whitespace.................................................Passed
fix end of files.........................................................Passed
check yaml...............................................................Passed
check for added large files..............................................Passed
check for case conflicts.................................................Passed
check for merge conflicts................................................Passed
check that executables have shebangs.....................................Passed
check that scripts with shebangs are executable..........................Passed
mixed line ending........................................................Passed
shellcheck...............................................................OK: All Dockerfiles pass ARG-before-FROM check.
Passed
prettier.................................................................Passed
markdownlint-cli2........................................................Passed
Lint GitHub Actions workflow files.......................................Passed
Lint Dockerfiles.........................................................Passed
pretty format json.......................................................Passed
Detect hardcoded secrets.................................................Passed
Audit GitHub Actions workflows (zizmor)..................................Passed
Validate Dockerfile ARG-before-FROM scope................................Passed
Validate Add-on Versioning...............................................Passed
Validate Add-on config.yaml Schema.......................................Passed
terraform-bridge scaffold verify.........................................Passed
terraform-bridge no-token-leak...........................................Passed
```

## Task 1 — red-first: the verifier fails on the unchanged workflow

The verifier was written first and run against the **untouched** `.github/workflows/opencode.yml`. It exits **1** with
`A2 denial` failing on 30 rows — five untrusted `author_association` values × the six trigger-shaped bodies — while all
three anti-silent-pass controls pass. That is the evidence that the harness tests something: a verifier whose first run
was already green proves nothing.

```text
workflow: .github/workflows/opencode.yml   job: opencode
gate expression under test:
contains(github.event.comment.body, ' /oc') ||
startsWith(github.event.comment.body, '/oc') ||
contains(github.event.comment.body, ' /opencode') ||
startsWith(github.event.comment.body, '/opencode')

author_association       comment body                 file if:  pre-change verdict
------------------------------------------------------------------------------------
COLLABORATOR             '/oc'                        True      True       parity
COLLABORATOR             '/opencode'                  True      True       parity
COLLABORATOR             'please /oc run the tests'   True      True       parity
COLLABORATOR             'see /opencode'              True      True       parity
COLLABORATOR             '/OC'                        True      True       parity
COLLABORATOR             '/october is a month'        True      True       parity
COLLABORATOR             'refactor this'              False     False      parity
COLLABORATOR             '' (empty)                   False     False      parity
COLLABORATOR             'nothing/oc'                 False     False      parity
CONTRIBUTOR              '/oc'                        True      True       ALLOWED — HOLE
CONTRIBUTOR              '/opencode'                  True      True       ALLOWED — HOLE
CONTRIBUTOR              'please /oc run the tests'   True      True       ALLOWED — HOLE
CONTRIBUTOR              'see /opencode'              True      True       ALLOWED — HOLE
CONTRIBUTOR              '/OC'                        True      True       ALLOWED — HOLE
CONTRIBUTOR              '/october is a month'        True      True       ALLOWED — HOLE
CONTRIBUTOR              'refactor this'              False     False      denied
CONTRIBUTOR              '' (empty)                   False     False      denied
CONTRIBUTOR              'nothing/oc'                 False     False      denied
FIRST_TIMER              '/oc'                        True      True       ALLOWED — HOLE
FIRST_TIMER              '/opencode'                  True      True       ALLOWED — HOLE
FIRST_TIMER              'please /oc run the tests'   True      True       ALLOWED — HOLE
FIRST_TIMER              'see /opencode'              True      True       ALLOWED — HOLE
FIRST_TIMER              '/OC'                        True      True       ALLOWED — HOLE
FIRST_TIMER              '/october is a month'        True      True       ALLOWED — HOLE
FIRST_TIMER              'refactor this'              False     False      denied
FIRST_TIMER              '' (empty)                   False     False      denied
FIRST_TIMER              'nothing/oc'                 False     False      denied
FIRST_TIME_CONTRIBUTOR   '/oc'                        True      True       ALLOWED — HOLE
FIRST_TIME_CONTRIBUTOR   '/opencode'                  True      True       ALLOWED — HOLE
FIRST_TIME_CONTRIBUTOR   'please /oc run the tests'   True      True       ALLOWED — HOLE
FIRST_TIME_CONTRIBUTOR   'see /opencode'              True      True       ALLOWED — HOLE
FIRST_TIME_CONTRIBUTOR   '/OC'                        True      True       ALLOWED — HOLE
FIRST_TIME_CONTRIBUTOR   '/october is a month'        True      True       ALLOWED — HOLE
FIRST_TIME_CONTRIBUTOR   'refactor this'              False     False      denied
FIRST_TIME_CONTRIBUTOR   '' (empty)                   False     False      denied
FIRST_TIME_CONTRIBUTOR   'nothing/oc'                 False     False      denied
MANNEQUIN                '/oc'                        True      True       ALLOWED — HOLE
MANNEQUIN                '/opencode'                  True      True       ALLOWED — HOLE
MANNEQUIN                'please /oc run the tests'   True      True       ALLOWED — HOLE
MANNEQUIN                'see /opencode'              True      True       ALLOWED — HOLE
MANNEQUIN                '/OC'                        True      True       ALLOWED — HOLE
MANNEQUIN                '/october is a month'        True      True       ALLOWED — HOLE
MANNEQUIN                'refactor this'              False     False      denied
MANNEQUIN                '' (empty)                   False     False      denied
MANNEQUIN                'nothing/oc'                 False     False      denied
MEMBER                   '/oc'                        True      True       parity
MEMBER                   '/opencode'                  True      True       parity
MEMBER                   'please /oc run the tests'   True      True       parity
MEMBER                   'see /opencode'              True      True       parity
MEMBER                   '/OC'                        True      True       parity
MEMBER                   '/october is a month'        True      True       parity
MEMBER                   'refactor this'              False     False      parity
MEMBER                   '' (empty)                   False     False      parity
MEMBER                   'nothing/oc'                 False     False      parity
NONE                     '/oc'                        True      True       ALLOWED — HOLE
NONE                     '/opencode'                  True      True       ALLOWED — HOLE
NONE                     'please /oc run the tests'   True      True       ALLOWED — HOLE
NONE                     'see /opencode'              True      True       ALLOWED — HOLE
NONE                     '/OC'                        True      True       ALLOWED — HOLE
NONE                     '/october is a month'        True      True       ALLOWED — HOLE
NONE                     'refactor this'              False     False      denied
NONE                     '' (empty)                   False     False      denied
NONE                     'nothing/oc'                 False     False      denied
OWNER                    '/oc'                        True      True       parity
OWNER                    '/opencode'                  True      True       parity
OWNER                    'please /oc run the tests'   True      True       parity
OWNER                    'see /opencode'              True      True       parity
OWNER                    '/OC'                        True      True       parity
OWNER                    '/october is a month'        True      True       parity
OWNER                    'refactor this'              False     False      parity
OWNER                    '' (empty)                   False     False      parity
OWNER                    'nothing/oc'                 False     False      parity

PASS  A1 parity
FAIL  A2 denial — 30 untrusted rows allowed: [('CONTRIBUTOR', '/oc'), ('CONTRIBUTOR', '/opencode'), ('CONTRIBUTOR', 'please /oc run the tests'), ('CONTRIBUTOR', 'see /opencode'), ('CONTRIBUTOR', '/OC')]
PASS  A3 detectability control
PASS  A4 positive control
PASS  A5 grammar guard

FAIL: A2 denial
EXIT=1
```

## Task 1 — post-edit: the same verifier passes

After applying the author clause (Verified Candidate Content, verbatim, comments included), the same command exits
**0**. Note the `pre-change` column is unchanged across both runs — the control still sees the hole, which is what
makes the `file if:` column's flip to `False` meaningful rather than an artifact of a broken evaluator.

```text
workflow: .github/workflows/opencode.yml   job: opencode
gate expression under test:
(github.event.comment.author_association == 'OWNER' ||
github.event.comment.author_association == 'MEMBER' ||
github.event.comment.author_association == 'COLLABORATOR') &&
(contains(github.event.comment.body, ' /oc') ||
startsWith(github.event.comment.body, '/oc') ||
contains(github.event.comment.body, ' /opencode') ||
startsWith(github.event.comment.body, '/opencode'))

author_association       comment body                 file if:  pre-change verdict
------------------------------------------------------------------------------------
COLLABORATOR             '/oc'                        True      True       parity
COLLABORATOR             '/opencode'                  True      True       parity
COLLABORATOR             'please /oc run the tests'   True      True       parity
COLLABORATOR             'see /opencode'              True      True       parity
COLLABORATOR             '/OC'                        True      True       parity
COLLABORATOR             '/october is a month'        True      True       parity
COLLABORATOR             'refactor this'              False     False      parity
COLLABORATOR             '' (empty)                   False     False      parity
COLLABORATOR             'nothing/oc'                 False     False      parity
CONTRIBUTOR              '/oc'                        False     True       denied
CONTRIBUTOR              '/opencode'                  False     True       denied
CONTRIBUTOR              'please /oc run the tests'   False     True       denied
CONTRIBUTOR              'see /opencode'              False     True       denied
CONTRIBUTOR              '/OC'                        False     True       denied
CONTRIBUTOR              '/october is a month'        False     True       denied
CONTRIBUTOR              'refactor this'              False     False      denied
CONTRIBUTOR              '' (empty)                   False     False      denied
CONTRIBUTOR              'nothing/oc'                 False     False      denied
FIRST_TIMER              '/oc'                        False     True       denied
FIRST_TIMER              '/opencode'                  False     True       denied
FIRST_TIMER              'please /oc run the tests'   False     True       denied
FIRST_TIMER              'see /opencode'              False     True       denied
FIRST_TIMER              '/OC'                        False     True       denied
FIRST_TIMER              '/october is a month'        False     True       denied
FIRST_TIMER              'refactor this'              False     False      denied
FIRST_TIMER              '' (empty)                   False     False      denied
FIRST_TIMER              'nothing/oc'                 False     False      denied
FIRST_TIME_CONTRIBUTOR   '/oc'                        False     True       denied
FIRST_TIME_CONTRIBUTOR   '/opencode'                  False     True       denied
FIRST_TIME_CONTRIBUTOR   'please /oc run the tests'   False     True       denied
FIRST_TIME_CONTRIBUTOR   'see /opencode'              False     True       denied
FIRST_TIME_CONTRIBUTOR   '/OC'                        False     True       denied
FIRST_TIME_CONTRIBUTOR   '/october is a month'        False     True       denied
FIRST_TIME_CONTRIBUTOR   'refactor this'              False     False      denied
FIRST_TIME_CONTRIBUTOR   '' (empty)                   False     False      denied
FIRST_TIME_CONTRIBUTOR   'nothing/oc'                 False     False      denied
MANNEQUIN                '/oc'                        False     True       denied
MANNEQUIN                '/opencode'                  False     True       denied
MANNEQUIN                'please /oc run the tests'   False     True       denied
MANNEQUIN                'see /opencode'              False     True       denied
MANNEQUIN                '/OC'                        False     True       denied
MANNEQUIN                '/october is a month'        False     True       denied
MANNEQUIN                'refactor this'              False     False      denied
MANNEQUIN                '' (empty)                   False     False      denied
MANNEQUIN                'nothing/oc'                 False     False      denied
MEMBER                   '/oc'                        True      True       parity
MEMBER                   '/opencode'                  True      True       parity
MEMBER                   'please /oc run the tests'   True      True       parity
MEMBER                   'see /opencode'              True      True       parity
MEMBER                   '/OC'                        True      True       parity
MEMBER                   '/october is a month'        True      True       parity
MEMBER                   'refactor this'              False     False      parity
MEMBER                   '' (empty)                   False     False      parity
MEMBER                   'nothing/oc'                 False     False      parity
NONE                     '/oc'                        False     True       denied
NONE                     '/opencode'                  False     True       denied
NONE                     'please /oc run the tests'   False     True       denied
NONE                     'see /opencode'              False     True       denied
NONE                     '/OC'                        False     True       denied
NONE                     '/october is a month'        False     True       denied
NONE                     'refactor this'              False     False      denied
NONE                     '' (empty)                   False     False      denied
NONE                     'nothing/oc'                 False     False      denied
OWNER                    '/oc'                        True      True       parity
OWNER                    '/opencode'                  True      True       parity
OWNER                    'please /oc run the tests'   True      True       parity
OWNER                    'see /opencode'              True      True       parity
OWNER                    '/OC'                        True      True       parity
OWNER                    '/october is a month'        True      True       parity
OWNER                    'refactor this'              False     False      parity
OWNER                    '' (empty)                   False     False      parity
OWNER                    'nothing/oc'                 False     False      parity

PASS  A1 parity
PASS  A2 denial
PASS  A3 detectability control
PASS  A4 positive control
PASS  A5 grammar guard

PASS: all 5 assertions hold over 72 fixture rows.
EXIT=0
```

## What the verifier actually asserts

| Assertion                | Content                                                                                                       |
| ------------------------ | ------------------------------------------------------------------------------------------------------------- |
| A1 parity                | For OWNER/MEMBER/COLLABORATOR × all 9 bodies, the file expression equals the pre-change body-only expression. |
| A2 denial                | For the five untrusted values × all 9 bodies, the file expression is false.                                    |
| A3 detectability control | `PRE_CHANGE_EXPRESSION` is TRUE for `NONE` + `/oc`. False here ⇒ exit 3 as broken, never a pass.               |
| A4 positive control      | The file expression is TRUE for `OWNER` + `/oc` — the gate did not shut everything off.                       |
| A5 grammar guard         | `fromJSON(...)` raises `UnsupportedConstruct`. A silent `false`/`true` here ⇒ exit 3 as broken.                |

Design properties that carry the load:

- **The expression comes from the file.** `yaml.safe_load(...)["jobs"]["opencode"]["if"]`; a missing key path is exit 2,
  not a skipped assertion. Removing the author clause from the workflow turns the check red (threat `T-vh7-06`).
- **No silent defaults anywhere.** An unmodelled token, an unmodelled function, an unmodelled context path and an
  unmodelled mixed-type comparison all raise. The evaluator can never report a gate as closed merely because it failed
  to parse it.
- **Fixtures are full synthetic `github.event.comment` mappings** (id, body, author_association, user, html_url), so no
  context path can resolve by accident.
- **Case-insensitivity is modelled, not assumed away.** `==`, `contains()` and `startsWith()` all compare with
  `casefold()`, matching GitHub — which is why `/OC` is a triggering body in the table.

The 72-row table encodes the body clause's **pre-existing looseness truthfully**: `startsWith(body, '/oc')` matches
`/october is a month`, and all four alternatives are case-insensitive. Those rows read `true` for trusted authors
because that is what the workflow does today. Tightening the body match was explicitly out of scope; the table does not
pretend it was fixed.

## Task 2 — the pin and the two documentation paragraphs

`uses:` is now `anomalyco/opencode/github@v1.18.30`, confirmed by the plan's own probe:

```text
$ yq -r '.jobs.opencode.steps[] | select(.name == "Run opencode") | .uses' .github/workflows/opencode.yml
anomalyco/opencode/github@v1.18.30
```

`docs/DEVELOPMENT.md` gained two paragraphs:

1. **`### Action Pinning`** — the exact-tag pin recorded as a reasoned exception to the floating-major policy: upstream
   publishes no major tag (`git/ref/tags/v1` and `git/ref/tags/v1.18` both 404), `@latest` was mutable and the secret is
   already in the job environment, an exact tag is the only immutable non-SHA option, Renovate's `github-actions`
   manager still raises bumps against exact tags, and if upstream ever publishes a major tag the pin should go back to
   `@v1`. It also names `internal/verify-opencode-gate.py` as the guard on the workflow's other half.
2. **`### Why zizmor.yml relaxes the pinning audit`** — the blind spot: a `ref-pin` policy is satisfied by *any*
   symbolic ref, and `latest` is one, so this file passed the `unpinned-uses` audit for its whole life while carrying a
   mutable ref. The audit that exists to catch this class did not catch it. The relaxation is deliberately left
   untouched; narrowing it is an open follow-up.

## Verification

| # | Check                                                                          | Result                                       |
| - | ------------------------------------------------------------------------------ | -------------------------------------------- |
| 1 | `python3 internal/verify-opencode-gate.py`                                     | exit 0, 72 rows, A1–A5 pass                  |
| 2 | pre-edit run of the same command                                               | exit 1 on A2 (transcript above)              |
| 3 | `pre-commit run yamllint --files .github/workflows/opencode.yml`               | Passed                                       |
| 4 | `pre-commit run actionlint --files .github/workflows/opencode.yml`              | Passed                                       |
| 5 | `pre-commit run zizmor --files .github/workflows/opencode.yml`                  | Passed                                       |
| 6 | `yq` reports `uses:` as `anomalyco/opencode/github@v1.18.30`                    | exact match                                  |
| 7 | `git diff --stat` touches only the three authorized files (`zizmor.yml` clean)  | confirmed                                    |
| 8 | `make check-all`                                                                | **EXIT=0**, identical to the baseline, offline |

`pre-commit run prettier --files docs/DEVELOPMENT.md` and `markdownlint-cli2` both pass. Both new commits went through
the full hook set including `gitleaks` and `zizmor`.

## Deviations from Plan

**1. [prettier auto-rewrap] `docs/DEVELOPMENT.md` line wrapping adjusted by the hook**

- **Found during:** Task 2
- **Issue:** The first added paragraph was hand-wrapped one word short of prettier's 120-column `proseWrap: always`
  target, so the hook rewrote one line boundary and reported `files were modified by this hook`.
- **Fix:** Accepted the hook's rewrap and re-ran; prettier and markdownlint then both pass. No prose changed.
- **Files modified:** `docs/DEVELOPMENT.md`
- **Commit:** `73898a4`

**2. [tokenizer tightening] `-` removed from the identifier character class**

- **Found during:** Task 1
- **Issue:** The first draft let `-` be part of a context-path word, so a subtraction operator would have been absorbed
  into an identifier instead of surfacing.
- **Fix:** Dropped `-` from the word charset, so a `-` is now an unmodelled character and raises — which is the correct
  fail-loud behavior for an unmodelled operator.
- **Files modified:** `internal/verify-opencode-gate.py`
- **Commit:** `a3aca04`

Nothing else deviated. No architectural (Rule 4) decision arose, no authentication gate was hit, and no
package-manager install was attempted — the verifier's only import beyond the stdlib is `yaml`, already relied on by
`internal/validate-addon-config.py`.

## Deferrals and open follow-ups

**1. The verifier is intentionally NOT wired into `.pre-commit-config.yaml` or `make check-all`.**
This is a named deferral with a reason, not an oversight. `.pre-commit-config.yaml` and the `Makefile` were both listed
under the plan's hard out-of-scope boundary, so the check is run by hand:
`python3 internal/verify-opencode-gate.py`. Promoting it to a hook is the follow-up. Until that happens, nothing
automatically re-runs the truth table, so a future edit that removes the author clause would not be caught at commit
time — only by someone running the verifier. That is the whole cost of the deferral, stated plainly.

**2. The `zizmor.yml` `unpinned-uses: policies: {"*": ref-pin}` relaxation accepts a mutable `latest` ref.**
Open follow-up (threat `T-vh7-05`, disposition `accept`). `ref-pin` requires only *some* symbolic ref, and `latest` is
symbolic, so the audit that exists to catch mutable refs never flagged this workflow. Left untouched here per the
user's explicit choice of the narrower option; recorded in `docs/DEVELOPMENT.md` so it is not lost. Narrowing it would
mean per-repository policies or an explicit deny for `latest` / `main` / `master`.

**3. Residual risk, accepted explicitly.** Any OWNER/MEMBER/COLLABORATOR can still start an agent run, and the body
match stays loose enough that `/october …` from such an author triggers it. Both sit inside the trust boundary this
change establishes.

## Known Stubs

None. The verifier has no placeholder assertions, no skipped tests and no unrun `<verify>` steps — every check in the
Verification table above was executed and its output is recorded here.

## Threat Flags

None. No new network endpoint, auth path, file-access pattern or schema change at a trust boundary was introduced; the
change only narrows an existing one. The four `high` threats in the plan's register (`T-vh7-01` spoofing/EoP,
`T-vh7-02` tampering, `T-vh7-03` information disclosure, `T-vh7-06` trusted-set drift) are all mitigated as planned.

## Self-Check: PASSED

All three code artifacts exist on disk (`internal/verify-opencode-gate.py` with mode 0755,
`.github/workflows/opencode.yml`, `docs/DEVELOPMENT.md`). Both commit hashes (`a3aca04`, `73898a4`) resolve in
`git log --all`. `git diff --stat 9dfca29..HEAD -- zizmor.yml` is empty — `zizmor.yml` is provably untouched.
`python3 internal/verify-opencode-gate.py` re-run at self-check time: exit 0.
