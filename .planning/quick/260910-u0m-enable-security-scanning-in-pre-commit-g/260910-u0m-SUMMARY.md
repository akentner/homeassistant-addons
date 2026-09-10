---
phase: quick-260910-u0m
plan: 01
subsystem: infra
tags: [gitleaks, zizmor, pre-commit, hadolint, secret-scanning, github-actions, supply-chain]

requires:
  - phase: 17-git-integration-apply-job-system
    provides: the iac-runner redaction/scrubbing test fixtures whose synthetic credential shapes are the eight baseline gitleaks findings
provides:
  - gitleaks secret-scanning pre-commit hook (rev v8.30.1), proven to fail on a planted control
  - .gitleaks.toml extending the default ruleset with two path-and-rule-scoped allowlist blocks
  - offline zizmor GitHub Actions audit hook (zizmor==1.30.1), still blocking for new findings
  - zizmor.yml with a narrow unpinned-uses ref-pin policy and 25 per-finding deferral entries
  - discovery-driven docker-build-check covering all 9 add-ons instead of a stale 3-name list
  - docs/DEVELOPMENT.md '## Security Scanning' section stating what is and is not covered
affects: [08-cicd-hardening, any-future-addon, any-future-workflow-change]

actuals:
  tokens: 10914
  tasks: 3
  commits: 4
plan_head_before: 1a8406f14256481e174d962f6a5ac0650410abc6

tech-stack:
  added: [gitleaks v8.30.1 (pre-commit golang hook), zizmor 1.30.1 (pre-commit local python hook)]
  patterns:
    - "Prove a gate can fail before believing it passes: every new hook ships with a planted control and a recorded non-zero exit"
    - "Per-finding line-anchored deferrals instead of blanket silencing, so a gate stays red for new findings"
    - "Discovery over enumeration: add-on lists are computed from the filesystem, never written down"

key-files:
  created: [.gitleaks.toml, zizmor.yml]
  modified: [.pre-commit-config.yaml, Makefile, docs/DEVELOPMENT.md]

key-decisions:
  - "The plan's AWS-access-key-id negative control does NOT work: gitleaks v8.30.1 misses the bare AKIA shape in file/diff mode (0/10 draws). Substituted a GitHub PAT shape (ghp_ + 36), which hits 10/10 and is also the more relevant shape for this repo's GHCR tokens."
  - "The plan's Step 6 allowlist control was a false pass — the r2Hex* literals passed the staged-diff hook even with the allowlists stripped. Replaced with a paired control in which the path is the only variable: allowlisted path passes, non-allowlisted path carrying the identical literals fails."
  - "unpinned-uses shipped as the NARROW form (config.policies '*': ref-pin), not as an outright disable — zizmor 1.30.1 accepted it and all 22 findings cleared."
  - "zizmor ignore entries match on the BASENAME of the workflow file; full paths are silently non-matching. Verified empirically across four entry forms."
  - "tools/test-addon (a depth-2 add-on) is out of docker-build-check's coverage by D-02's definition. Reported as a follow-up rather than widening the shared idiom."

patterns-established:
  - "Negative control per gate: a hook that has only ever printed Passed is not verified, and a rc!=0 must be attributed to the right cause (the first attempt here returned rc=1 because pre-commit refused an unstaged config, not because of a detection)."
  - "Load-bearing allowlist proof: hold config and scan mode fixed and vary only the allowlisted attribute, so a pass cannot be explained by the rule simply not firing."

requirements-completed:
  - QUICK-260910-u0m-a
  - QUICK-260910-u0m-b
  - QUICK-260910-u0m-c
  - QUICK-260910-u0m-d
  - QUICK-260910-u0m-e

duration: 18min
completed: 2026-09-10
status: complete
---

# Quick 260910-u0m: Enable Security Scanning in Pre-commit Summary

**Two offline pre-commit gates — gitleaks on the staged diff and zizmor on the workflows — both shipped with a planted
control proving they exit non-zero, plus a hadolint target that now checks all nine add-ons instead of three names, one
of which had not existed for months.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-09-10T19:57:14Z
- **Completed:** 2026-09-10T20:15Z
- **Tasks:** 3 of 3
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- **Secret scanning exists and is proven to fire.** A planted `ghp_`-shaped literal makes `pre-commit run gitleaks`
  exit 1 (3 of 3 random draws). The full-history baseline of 8 findings is down to 0, and stripping the allowlists back
  out returns exactly those 8 — so the config narrows rather than disarms.
- **The GitHub Actions workflows are audited offline on every commit and in CI, and the audit still bites.** 49
  findings surfaced on the first run; 22 cleared through the narrow pinning policy, 27 are deferred per-finding, and a
  newly injected `${ }` interpolation still makes the hook exit non-zero.
- **`make docker-build-check` went from 3 hardcoded names (one non-existent) to 9 discovered add-ons**, naming each in
  its output, and immediately surfaced one previously invisible hadolint finding.
- **`make check-all` exits 0 and was measured offline** — with every HTTP/HTTPS/SOCKS proxy pointed at a dead local
  port *and* `GH_TOKEN`/`GITHUB_TOKEN` set, it still exits 0 with both new hooks passing.

## Task Commits

1. **Task 1 (tracer): gitleaks end-to-end** — `5d2963a` (feat)
2. **Task 2: zizmor hook, offline and blocking** — `a39f4b2` (feat)
3. **Task 3 Step 1: discovery-driven docker-build-check** — `16cf8df` (fix)
4. **Task 3 Step 2: `## Security Scanning` documentation** — `6b678c9` (docs)

Measured: `git rev-list --count 1a8406f..HEAD` = **4**.

## Files Created/Modified

- `.gitleaks.toml` (created) — `[extend] useDefault = true` plus exactly 2 path-and-rule-scoped `[[allowlists]]` blocks
- `zizmor.yml` (created) — narrow `unpinned-uses` ref-pin policy + 25 line-anchored per-finding deferral entries
- `.pre-commit-config.yaml` — new `# Security scanning` section with both hooks, placed before the custom-validation block
- `Makefile` — `docker-build-check` discovery loop (+4/-3 lines)
- `docs/DEVELOPMENT.md` — new `## Security Scanning` H2 at line 90, plus one cross-reference line in `## Pre-commit Validation`

---

## 1. Negative controls — both hooks observed FAILING

### 1a. gitleaks negative control (D-01)

The plan's specified shape **did not work**. Recorded rather than papered over:

| Planted shape | Mode | Draws detected |
| --- | --- | --- |
| `AKIA` + 16 random `[A-Z0-9]` (plan's shape) | dir / staged-diff | **0 / 10** |
| `ghp_` + 36 random `[A-Za-z0-9]` (substituted) | dir / staged-diff | **10 / 10** |

The `aws-access-token` rule **is** present in the v8.30.1 default ruleset — `--enable-rule aws-access-token` is
accepted, while `--enable-rule this-rule-does-not-exist` fails with
`FTL Requested rule this-rule-does-not-exist not found in rules` — it simply does not match that shape in file or diff
scan mode. The substituted `github-pat` shape is also the more apt control for this repository, whose named secrets
include GHCR tokens.

**A first attempt returned rc=1 for the wrong reason** and was rejected rather than banked:

```text
[ERROR] Your pre-commit configuration is unstaged.
`git add .pre-commit-config.yaml` to fix this.
```

That is pre-commit refusing to run, not a detection. Re-run with the config staged, the hook output is:

```text
Detect hardcoded secrets.................................................Failed
- hook id: gitleaks
- exit code: 1

○
    │╲
    │ ○
    ○ ░
    ░    gitleaks

Finding:     GHCR_TOKEN=REDACTED
Secret:      REDACTED
RuleID:      github-pat
Entropy:     4.831687
File:        .gitleaks-negative-control.tmp
Line:        1
Fingerprint: .gitleaks-negative-control.tmp:github-pat:1

10:03PM INF 0 commits scanned.
10:03PM INF scanned ~3215 bytes (3.21 KB) in 25.8ms
10:03PM WRN leaks found: 1
```

**`NEGATIVE_CONTROL_OK rc=1`**, reproduced on 3 of 3 independent random draws. Working tree residue afterwards:
`TREE_CLEAN_OK`.

### 1b. zizmor negative control

Probe: one extra step appended to `.github/workflows/lint.yml` interpolating
`${ github.event.head_commit.message }` into a `run:` block.

```text
Audit GitHub Actions workflows (zizmor)..................................Failed
- hook id: zizmor
- exit code: 14

INFO zizmor: 🌈 zizmor v1.30.1
 INFO audit: zizmor: 🌈 completed .github/workflows/lint.yml
error[template-injection]: code injection via template expansion
   --> .github/workflows/lint.yml:176:30
    |
176 |         run: echo "probe ${{ github.event.head_commit.message }}"
    |         --- this run block   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ may expand into attacker-controllable code
    |
    = note: audit confidence → High
    = note: this finding has an auto-fix
    = help: audit documentation → https://docs.zizmor.sh/audits/#template-injection

9 findings (5 ignored, 3 suppressed, 1 unsafe fixes): 0 informational, 0 low, 0 medium, 1 high
```

**`ZIZMOR_NEGATIVE_CONTROL_OK rc=1`** (zizmor exit code 14). Note `9 findings (5 ignored, 3 suppressed, ...)`: the 5
pre-existing `lint.yml` findings were correctly deferred while the **new** one still failed the hook — which is the
whole point of per-finding ignores over a blanket silencer. Probe reverted byte-identical (sha256 match) and
`git status --porcelain -- .github/` is empty (`SCOPE_HELD_OK`).

## 2. gitleaks history scan and allowlist scoping

| Scan | Config | Result |
| --- | --- | --- |
| Baseline, before this task | none | **8 leaks** |
| History, container v8.30.1 | `.gitleaks.toml` in place | **0 leaks**, `history_scan_rc=0` |
| History, **hook's own** v8.30.1 binary | `.gitleaks.toml` in place | **0 leaks**, rc=0 |
| History, **hook's own** binary | allowlist blocks stripped, `[extend]` kept | **8 leaks**, rc=1 |

The container image is v8.30.1 — the same version as the hook pin — so the plural `[[allowlists]]` form parses and the
positive control is valid. The fourth row is the load-bearing half: with the two blocks removed the baseline 8 return
exactly, at exactly the paths and rule ids the blocks are scoped to.

**`targetRules` was accepted** by the hook's gitleaks. No downgrade to path-only scoping was needed, no config-parse
error was emitted, and `DBG extending config with default config` appears in the debug log confirming `[extend]` took
effect.

### Authoritative rule ids (taken from the scan, not from the plan's reading)

| Path | Lines | Rule ids |
| --- | --- | --- |
| `iac-runner/internal/runs/redact_test.go` | 10, 122, 123 | `generic-api-key` |
| `iac-runner/internal/runs/redact_test.go` | 43 | `private-key` |
| `iac-runner/internal/runs/output_test.go` | 353 | `private-key` |
| `iac-runner/internal/logging/scrubbing_handler_test.go` | 29 | `generic-api-key` |
| `.planning/phases/17-git-integration-apply-job-system/17-REVIEW.md` | 314 | `generic-api-key` |
| `.planning/phases/14-real-ha-end-to-end-verification-operator-documentation/14-02-PLAN.md` | 374 | `curl-auth-header` |

Block one therefore scopes to `generic-api-key` + `private-key`; block two to `generic-api-key` + `curl-auth-header`.
No literal is reproduced here (D-08) — findings are named by path, line, constant name and rule id only.

### Allowlist control (replaces the plan's Step 6, which was a false pass)

The plan's Step 6 — append comment-prefixed copies of the `r2Hex*` constant lines and require exit 0 — **passed even
with the allowlists stripped out**, and so proved nothing. A second attempt (in-place re-emission of the two real
`const` lines via a whitespace edit) also passed with allowlists stripped. Both were rejected.

The shipped control holds config, scan mode and literal fixed and varies **only the path**:

| Arm | Path carrying the literals | Result |
| --- | --- | --- |
| 1 | `iac-runner/internal/runs/redact_test.go` (allowlisted) | **Passed**, rc=0 |
| 2 | `.gl-allowlist-control.tmp` (not allowlisted) | **Failed**, rc=1 |

Arm 2 output:

```text
Detect hardcoded secrets.................................................Failed
- hook id: gitleaks
- exit code: 1

○
    │╲
    │ ○
    ○ ░
    ░    gitleaks

Finding:     r2HexAccessKey = "REDACTED"
Secret:      REDACTED
RuleID:      generic-api-key
Entropy:     3.976410
File:        .gl-allowlist-control.tmp
Line:        1
Fingerprint: .gl-allowlist-control.tmp:generic-api-key:1

Finding:     r2HexSecret    = "REDACTED"
Secret:      REDACTED
RuleID:      generic-api-key
Entropy:     3.982913
File:        .gl-allowlist-control.tmp
Line:        2
Fingerprint: .gl-allowlist-control.tmp:generic-api-key:2

10:06PM INF 0 commits scanned.
10:06PM INF scanned ~3301 bytes (3.30 KB) in 26.9ms
10:06PM WRN leaks found: 2
```

The entropies (`3.976410`, `3.982913`) match the history-scan findings for lines 122 and 123 exactly, confirming the
same two literals in both arms. `ALLOWLIST_CONTROL_OK`. Both arms fully reverted:
`FIXTURE_BYTE_IDENTICAL_OK`, `TREE_CLEAN_OK`.

## 3. zizmor — first run verbatim, and what shipped

**Exit code: 14** (findings, graded by severity). pre-commit invoked zizmor in **3 batches**, hence three summary
lines:

```text
45 findings (14 suppressed, 14 unsafe fixes): 0 informational, 4 low, 7 medium, 20 high
28 findings (15 suppressed, 5 unsafe fixes): 0 informational, 5 low, 1 medium, 7 high
8 findings (3 suppressed, 2 unsafe fixes): 0 informational, 1 low, 1 medium, 3 high
```

81 total, 32 suppressed, **49 reported**. By audit:

| Audit | Severity band | Count | Disposition |
| --- | --- | --- | --- |
| `unpinned-uses` | error | 22 | **Cleared** by the narrow ref-pin policy |
| `template-injection` | error x7, warning x4 | 11 | Deferred (9 entries; two locations reported twice) |
| `artipacked` | help | 8 | Deferred |
| `excessive-permissions` | warning | 5 | Deferred |
| `cache-poisoning` | error | 1 | Deferred |
| `adhoc-packages` | help | 1 | Deferred |
| `self-repository` | help | 1 | Deferred |

### Which findings survived into `zizmor.yml` as deferrals (27 findings, 25 entries)

| # | Audit | Severity | Location |
| --- | --- | --- | --- |
| 1 | `adhoc-packages` | help | `.github/workflows/lint.yml:58:11` |
| 2 | `artipacked` | help | `.github/workflows/_build-template.yml:70:9` |
| 3 | `artipacked` | help | `.github/workflows/auto-update.yml:51:9` |
| 4 | `artipacked` | help | `.github/workflows/base-image-update.yml:35:9` |
| 5 | `artipacked` | help | `.github/workflows/build.yml:61:9` |
| 6 | `artipacked` | help | `.github/workflows/lint.yml:22:9` |
| 7 | `artipacked` | help | `.github/workflows/test-install-provider.yml:28:9` |
| 8 | `artipacked` | help | `.github/workflows/test-terraform-provider.yml:24:9` |
| 9 | `artipacked` | help | `.github/workflows/verify-image-availability.yml:48:9` |
| 10 | `cache-poisoning` | error | `.github/workflows/test-terraform-provider.yml:28:9` |
| 11 | `excessive-permissions` | warning | `.github/workflows/lint.yml:1:1` |
| 12 | `excessive-permissions` | warning | `.github/workflows/lint.yml:16:3` |
| 13 | `excessive-permissions` | warning | `.github/workflows/lint.yml:160:3` |
| 14 | `excessive-permissions` | warning | `.github/workflows/test-install-provider.yml:19:3` |
| 15 | `excessive-permissions` | warning | `.github/workflows/test-terraform-provider.yml:14:3` |
| 16 | `self-repository` | help | `.github/workflows/build.yml:198:11` |
| 17 | `template-injection` | error | `.github/workflows/_build-template.yml:77:50` |
| 18 | `template-injection` | error | `.github/workflows/_build-template.yml:81:52` |
| 19 | `template-injection` | error | `.github/workflows/_build-template.yml:83:82` |
| 20 | `template-injection` | error | `.github/workflows/_build-template.yml:90:51` (reported twice) |
| 21 | `template-injection` | error | `.github/workflows/_build-template.yml:94:46` |
| 22 | `template-injection` | error | `.github/workflows/_build-template.yml:116:37` |
| 23 | `template-injection` | warning | `.github/workflows/_build-template.yml:83:51` (reported twice) |
| 24 | `template-injection` | warning | `.github/workflows/_build-template.yml:87:59` |
| 25 | `template-injection` | warning | `.github/workflows/_build-template.yml:98:46` |

After the config, `pre-commit run zizmor --all-files` exits **0** with **0** remaining finding headers. The
blanket-silencing gate (comments stripped, then grep for `severity|persona|remap|\|\| true`) returns **0** — no
`--min-severity`, no persona downgrade, no `remap`, no `|| true`, and no `disable: true` for any audit.

### Which pinning-relaxation form shipped, and why the other was not used

**Shipped: the narrow form.**

```yaml
unpinned-uses:
  config:
    policies:
      "*": ref-pin
```

zizmor 1.30.1 **accepted** it — no config-parse error — and all 22 `unpinned-uses` findings disappeared, which also
proves a root `zizmor.yml` is discovered (no move to `.github/zizmor.yml` was needed, and no flag was added to the hook
entry to work around discovery). **`disable: true` was therefore never used**: the plan's fallback was conditional on
zizmor rejecting the narrower key or still reporting on floating-major refs, and neither happened. The narrow form is
strictly better — `ref-pin` still requires *some* symbolic pin, so a bare `@main` or a missing ref remains an error,
whereas a disable would have made the audit inert. Justification is the repo's own policy at `docs/DEVELOPMENT.md`
`### Action Pinning` (lines 174-188), cited in a comment in `zizmor.yml`.

### Ignore-entry form (determined empirically, not guessed)

Tested against the `self-repository` finding at `build.yml:198:11`:

| Entry form | Suppressed? |
| --- | --- |
| `build.yml:198:11` (basename + line + col) | yes |
| `build.yml:198` | yes |
| `build.yml` | yes |
| `.github/workflows/build.yml:198:11` (full path) | **no** |

Full paths are silently non-matching. The narrowest accepted form — `basename:line:col` — is what shipped, and the
basename-matching caveat is recorded in `zizmor.yml`'s header comment so nobody "fixes" the entries into full paths.

### Verbatim first-run output (complete, ANSI escape sequences stripped)

```text
Audit GitHub Actions workflows (zizmor)..................................Failed
- hook id: zizmor
- exit code: 14

INFO zizmor: 🌈 zizmor v1.30.1
 INFO audit: zizmor: 🌈 completed .github/workflows/_build-template.yml
 INFO audit: zizmor: 🌈 completed .github/workflows/auto-update.yml
 INFO audit: zizmor: 🌈 completed .github/workflows/lint.yml
 INFO audit: zizmor: 🌈 completed .github/workflows/opencode.yml
help[artipacked]: credential persistence through GitHub Actions artifacts
  --> .github/workflows/_build-template.yml:70:9
   |
70 |       - uses: actions/checkout@v7
   |         ^^^^^^^^^^^^^^^^^^^^^^^^^ does not set persist-credentials: false
   |
   = note: audit confidence → Low
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#artipacked

error[template-injection]: code injection via template expansion
  --> .github/workflows/_build-template.yml:77:50
   |
76 |         run: |
   |         --- this run block
77 |           VERSION=$(yq eval '.args.VERSION' "${{ inputs.addon-name }}/build.yaml")
   |                                                  ^^^^^^^^^^^^^^^^^ may expand into attacker-controllable code
   |
   = note: audit confidence → High
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#template-injection

error[template-injection]: code injection via template expansion
  --> .github/workflows/_build-template.yml:81:52
   |
76 |         run: |
   |         --- this run block
...
81 |           CONFIG_VERSION=$(yq eval '.version' "${{ inputs.addon-name }}/config.yaml")
   |                                                    ^^^^^^^^^^^^^^^^^ may expand into attacker-controllable code
   |
   = note: audit confidence → High
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#template-injection

warning[template-injection]: code injection via template expansion
  --> .github/workflows/_build-template.yml:83:51
   |
76 |         run: |
   |         --- this run block
...
83 |           BUILD_FROM=$(yq eval ".build_from.\"${{ matrix.arch }}\" // \"\"" "${{ inputs.addon-name }}/build.yaml")
   |                                                   ^^^^^^^^^^^ may expand into attacker-controllable code
   |
   = note: audit confidence → Medium
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#template-injection

error[template-injection]: code injection via template expansion
  --> .github/workflows/_build-template.yml:83:82
   |
76 |         run: |
   |         --- this run block
...
83 |           BUILD_FROM=$(yq eval ".build_from.\"${{ matrix.arch }}\" // \"\"" "${{ inputs.addon-name }}/build.yaml")
   |                                                                                  ^^^^^^^^^^^^^^^^^ may expand into attacker-controllable code
   |
   = note: audit confidence → High
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#template-injection

warning[template-injection]: code injection via template expansion
  --> .github/workflows/_build-template.yml:83:51
   |
76 |         run: |
   |         --- this run block
...
83 |           BUILD_FROM=$(yq eval ".build_from.\"${{ matrix.arch }}\" // \"\"" "${{ inputs.addon-name }}/build.yaml")
   |                                                   ^^^^^^^^^^^ may expand into attacker-controllable code
   |
   = note: audit confidence → Medium
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#template-injection

warning[template-injection]: code injection via template expansion
  --> .github/workflows/_build-template.yml:87:59
   |
76 |         run: |
   |         --- this run block
...
87 |             *)       echo "::error::unsupported arch '${{ matrix.arch }}'"; exit 1 ;;
   |                                                           ^^^^^^^^^^^ may expand into attacker-controllable code
   |
   = note: audit confidence → Medium
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#template-injection

error[template-injection]: code injection via template expansion
  --> .github/workflows/_build-template.yml:90:51
   |
76 |         run: |
   |         --- this run block
...
90 |             echo "::error::no args.VERSION in ${{ inputs.addon-name }}/build.yaml"
   |                                                   ^^^^^^^^^^^^^^^^^ may expand into attacker-controllable code
   |
   = note: audit confidence → High
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#template-injection

error[template-injection]: code injection via template expansion
  --> .github/workflows/_build-template.yml:90:51
   |
76 |         run: |
   |         --- this run block
...
90 |             echo "::error::no args.VERSION in ${{ inputs.addon-name }}/build.yaml"
   |                                                   ^^^^^^^^^^^^^^^^^ may expand into attacker-controllable code
   |
   = note: audit confidence → High
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#template-injection

warning[template-injection]: code injection via template expansion
  --> .github/workflows/_build-template.yml:98:46
   |
76 |         run: |
   |         --- this run block
...
98 |             echo "::error::no build_from.${{ matrix.arch }} in ${{ inputs.addon-name }}/build.yaml"
   |                                              ^^^^^^^^^^^ may expand into attacker-controllable code
   |
   = note: audit confidence → Medium
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#template-injection

error[template-injection]: code injection via template expansion
  --> .github/workflows/_build-template.yml:94:46
   |
76 |         run: |
   |         --- this run block
...
94 |             echo "::error::no version in ${{ inputs.addon-name }}/config.yaml"
   |                                              ^^^^^^^^^^^^^^^^^ may expand into attacker-controllable code
   |
   = note: audit confidence → High
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#template-injection

error[template-injection]: code injection via template expansion
   --> .github/workflows/_build-template.yml:116:37
    |
116 |         run: echo "slug=$(echo '${{ inputs.addon-name }}' | tr '-' '_')" >> "$GITHUB_OUTPUT"
    |         --- this run block          ^^^^^^^^^^^^^^^^^ may expand into attacker-controllable code
    |
    = note: audit confidence → High
    = note: this finding has an auto-fix
    = help: audit documentation → https://docs.zizmor.sh/audits/#template-injection

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/_build-template.yml:70:15
   |
70 |       - uses: actions/checkout@v7
   |               ^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

error[unpinned-uses]: unpinned action reference
   --> .github/workflows/_build-template.yml:146:15
    |
146 |         uses: docker/setup-qemu-action@v4
    |               ^^^^^^^^^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
    |
    = note: audit confidence → High
    = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

error[unpinned-uses]: unpinned action reference
   --> .github/workflows/_build-template.yml:149:15
    |
149 |         uses: docker/setup-buildx-action@v4
    |               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
    |
    = note: audit confidence → High
    = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

error[unpinned-uses]: unpinned action reference
   --> .github/workflows/_build-template.yml:152:15
    |
152 |         uses: docker/login-action@v4
    |               ^^^^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
    |
    = note: audit confidence → High
    = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

error[unpinned-uses]: unpinned action reference
   --> .github/workflows/_build-template.yml:161:15
    |
161 |         uses: docker/build-push-action@v7
    |               ^^^^^^^^^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
    |
    = note: audit confidence → High
    = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

help[artipacked]: credential persistence through GitHub Actions artifacts
  --> .github/workflows/auto-update.yml:51:9
   |
51 |         - name: Checkout repository
   |  _________^
52 | |         uses: actions/checkout@v7
   | |_________________________________^ does not set persist-credentials: false
   |
   = note: audit confidence → Low
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#artipacked

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/auto-update.yml:52:15
   |
52 |         uses: actions/checkout@v7
   |               ^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

help[artipacked]: credential persistence through GitHub Actions artifacts
  --> .github/workflows/lint.yml:22:9
   |
22 |         - name: Checkout repository
   |  _________^
23 | |         uses: actions/checkout@v7
   | |_________________________________^ does not set persist-credentials: false
   |
   = note: audit confidence → Low
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#artipacked

warning[excessive-permissions]: overly broad permissions
   --> .github/workflows/lint.yml:1:1
    |
  1 | / name: Lint
  2 | |
  3 | | on:
  4 | |   push:
...   |
173 | |             exit 1
174 | |           fi
    | |_____________^ default permissions used due to no permissions: block
    |
    = note: audit confidence → Medium
    = help: audit documentation → https://docs.zizmor.sh/audits/#excessive-permissions

warning[excessive-permissions]: overly broad permissions
   --> .github/workflows/lint.yml:16:3
    |
 16 | /   lint:
 17 | |     runs-on: ubuntu-latest
 18 | |     # Observed 37-45s. 15 minutes covers a full pre-commit environment
 19 | |     # rebuild when the Python/Node caches miss.
...   |
158 | |           echo "✅ Common issues check passed"
    | |                                              ^
    | |                                              |
    | |______________________________________________this job
    |                                                default permissions used due to no permissions: block
    |
    = note: audit confidence → Medium
    = help: audit documentation → https://docs.zizmor.sh/audits/#excessive-permissions

warning[excessive-permissions]: overly broad permissions
   --> .github/workflows/lint.yml:160:3
    |
160 | /   lint-results:
161 | |     needs: lint
162 | |     runs-on: ubuntu-latest
163 | |     # Reporting job: echoes a verdict and exits. Seconds, not minutes.
...   |
173 | |             exit 1
174 | |           fi
    | |             ^
    | |             |
    | |_____________this job
    |               default permissions used due to no permissions: block
    |
    = note: audit confidence → Medium
    = help: audit documentation → https://docs.zizmor.sh/audits/#excessive-permissions

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/lint.yml:23:15
   |
23 |         uses: actions/checkout@v7
   |               ^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/lint.yml:26:15
   |
26 |         uses: actions/setup-python@v7
   |               ^^^^^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/lint.yml:31:15
   |
31 |         uses: actions/setup-node@v6
   |               ^^^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/lint.yml:36:15
   |
36 |         uses: actions/cache@v5
   |               ^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/lint.yml:44:15
   |
44 |         uses: actions/cache@v5
   |               ^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

help[adhoc-packages]: ad-hoc installation of packages
  --> .github/workflows/lint.yml:58:11
   |
52 |         run: |
   |         --- this step
...
58 |           npm install -g markdownlint-cli2@0.23.2
   |           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ installs a package outside of a lockfile
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#adhoc-packages

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/opencode.yml:28:15
   |
28 |         uses: actions/checkout@v7
   |               ^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/opencode.yml:33:15
   |
33 |         uses: anomalyco/opencode/github@latest
   |               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

45 findings (14 suppressed, 14 unsafe fixes): 0 informational, 4 low, 7 medium, 20 high
 INFO zizmor: 🌈 zizmor v1.30.1
 INFO audit: zizmor: 🌈 completed .github/workflows/base-image-update.yml
 INFO audit: zizmor: 🌈 completed .github/workflows/build.yml
 INFO audit: zizmor: 🌈 completed .github/workflows/test-install-provider.yml
 INFO audit: zizmor: 🌈 completed .github/workflows/verify-image-availability.yml
help[artipacked]: credential persistence through GitHub Actions artifacts
  --> .github/workflows/base-image-update.yml:35:9
   |
35 |         - name: Checkout repository
   |  _________^
36 | |         uses: actions/checkout@v7
   | |_________________________________^ does not set persist-credentials: false
   |
   = note: audit confidence → Low
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#artipacked

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/base-image-update.yml:36:15
   |
36 |         uses: actions/checkout@v7
   |               ^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/base-image-update.yml:39:15
   |
39 |         uses: actions/setup-python@v7
   |               ^^^^^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

help[artipacked]: credential persistence through GitHub Actions artifacts
  --> .github/workflows/build.yml:61:9
   |
61 |         - uses: actions/checkout@v7
   |  _________^
62 | |         with:
63 | |           # The derivation diffs two commits, so the full history is required.
64 | |           fetch-depth: 0
...  |
69 | |       # and never text spliced into a command line. That also makes the body
70 | |       # extractable and executable locally, which is how it is gate-tested.
   | |___________________________________________________________________________^ does not set persist-credentials: false
   |
   = note: audit confidence → Low
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#artipacked

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/build.yml:61:15
   |
61 |       - uses: actions/checkout@v7
   |               ^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

help[self-repository]: use GitHub's dedicated self-repository syntax
   --> .github/workflows/build.yml:198:11
    |
194 |     name: ${{ matrix.addon }} (${{ matrix.arch }})
    |     ---------------------------------------------- this job
...
198 |     uses: ./.github/workflows/_build-template.yml
    |           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ use '$/...' instead of './...'
    |
    = note: audit confidence → High
    = note: this finding has an auto-fix
    = help: audit documentation → https://docs.zizmor.sh/audits/#self-repository

help[artipacked]: credential persistence through GitHub Actions artifacts
  --> .github/workflows/test-install-provider.yml:28:9
   |
28 |         - name: Checkout repository
   |  _________^
29 | |         uses: actions/checkout@v7
   | |_________________________________^ does not set persist-credentials: false
   |
   = note: audit confidence → Low
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#artipacked

warning[excessive-permissions]: overly broad permissions
   --> .github/workflows/test-install-provider.yml:19:3
    |
 19 | /   test-install-provider:
 20 | |     runs-on: ubuntu-latest
 21 | |     # Build + install + fixture start + tofu init + tofu plan + teardown.
 22 | |     # Measured locally: ~20s for build/install/fixture, ~10s for tofu init
...   |
114 | |         run: |
115 | |           if [ -n "$FIXTURE_PID" ]; then kill "$FIXTURE_PID" 2>/dev/null || true; fi
    | |                                                                                     ^
    | |                                                                                     |
    | |_____________________________________________________________________________________this job
    |                                                                                       default permissions used due to no permissions: block
    |
    = note: audit confidence → Medium
    = help: audit documentation → https://docs.zizmor.sh/audits/#excessive-permissions

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/test-install-provider.yml:29:15
   |
29 |         uses: actions/checkout@v7
   |               ^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/test-install-provider.yml:32:15
   |
32 |         uses: actions/setup-go@v7
   |               ^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/test-install-provider.yml:37:15
   |
37 |         uses: opentofu/setup-opentofu@v2
   |               ^^^^^^^^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

help[artipacked]: credential persistence through GitHub Actions artifacts
  --> .github/workflows/verify-image-availability.yml:48:9
   |
48 |         - name: Check out the repository with full history
   |  _________^
49 | |         uses: actions/checkout@v7
50 | |         with:
51 | |           # MANDATORY, not an optimisation. The grace window reads git history
...  |
62 | |       # meaningful because the classifier was just proven to distinguish all
63 | |       # three ghcr states against a third-party control image.
   | |______________________________________________________________^ does not set persist-credentials: false
   |
   = note: audit confidence → Low
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#artipacked

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/verify-image-availability.yml:49:15
   |
49 |         uses: actions/checkout@v7
   |               ^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

28 findings (15 suppressed, 5 unsafe fixes): 0 informational, 5 low, 1 medium, 7 high
 INFO zizmor: 🌈 zizmor v1.30.1
 INFO audit: zizmor: 🌈 completed .github/workflows/test-terraform-provider.yml
help[artipacked]: credential persistence through GitHub Actions artifacts
  --> .github/workflows/test-terraform-provider.yml:24:9
   |
24 |         - name: Checkout repository
   |  _________^
25 | |         uses: actions/checkout@v7
   | |_________________________________^ does not set persist-credentials: false
   |
   = note: audit confidence → Low
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#artipacked

warning[excessive-permissions]: overly broad permissions
  --> .github/workflows/test-terraform-provider.yml:14:3
   |
14 | /   test:
15 | |     runs-on: ubuntu-latest
16 | |     # Provider module is ~5000 LOC including indirect deps; gofmt/vet/test
17 | |     # finish in seconds on a warm cache. 10 minutes covers a clean Go module
...  |
39 | |       - name: go test
40 | |         run: go test ./...
   | |                           ^
   | |                           |
   | |___________________________this job
   |                             default permissions used due to no permissions: block
   |
   = note: audit confidence → Medium
   = help: audit documentation → https://docs.zizmor.sh/audits/#excessive-permissions

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/test-terraform-provider.yml:25:15
   |
25 |         uses: actions/checkout@v7
   |               ^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

error[unpinned-uses]: unpinned action reference
  --> .github/workflows/test-terraform-provider.yml:28:15
   |
28 |         uses: actions/setup-go@v7
   |               ^^^^^^^^^^^^^^^^^^^ action is not pinned to a hash (required by blanket policy)
   |
   = note: audit confidence → High
   = help: audit documentation → https://docs.zizmor.sh/audits/#unpinned-uses

error[cache-poisoning]: runtime artifacts potentially vulnerable to a cache poisoning attack
  --> .github/workflows/test-terraform-provider.yml:28:9
   |
 3 | / on:
 4 | |   push:
 5 | |     branches:
 6 | |       - main
...  |
10 | |       - "terraform-provider-homeassistant/v*"
11 | |   workflow_dispatch:
   | |____________________- generally used when publishing artifacts generated at runtime
...
28 |           uses: actions/setup-go@v7
   |           ^^^^^^^^^^^^^^^^^^^^^^^^^ omitting `cache` enables caching
   |
   = note: audit confidence → Low
   = note: this finding has an auto-fix
   = help: audit documentation → https://docs.zizmor.sh/audits/#cache-poisoning

8 findings (3 suppressed, 2 unsafe fixes): 0 informational, 1 low, 1 medium, 3 high
```

## 4. docker-build-check coverage

Live-computed expected count: **9**. Named in the output: **9**. Missing: **0**.

```text
🐳 Checking Dockerfile correctness (no full build required)...
  Running hadolint (full ruleset, including DL3006 ARG-before-FROM)...
  Checking authentik...
authentik/Dockerfile:15 DL3008 warning: Pin versions in apt get install. Instead of `apt-get install <package>` use `apt-get install <package>=<version>`
  Checking coding-assistants...
  Checking gatus...
  Checking iac-runner...
  Checking markdown-renderer...
  Checking meridian...
  Checking network-tools...
  Checking phone-logger...
  Checking terraform-bridge...
❌ 1 Dockerfile(s) failed hadolint check.
make: *** [Makefile:120: docker-build-check] Fehler 1
```

`make` exits 2 because of the hadolint finding below. That is a true report, not a gate failure:
`docker-build-check` is **not** a member of `check-all` (`Makefile:268`), so a red result here blocks no commit and no
CI job (D-09).

### hadolint findings on the seven newly covered Dockerfiles — FOLLOW-UP, not suppressed

Exactly one finding, verbatim:

```text
authentik/Dockerfile:15 DL3008 warning: Pin versions in apt get install. Instead of `apt-get install <package>` use `apt-get install <package>=<version>`
```

The other eight (`coding-assistants`, `gatus`, `iac-runner`, `markdown-renderer`, `meridian`, `network-tools`,
`phone-logger`, `terraform-bridge`) each exit 0 under the target's four ignores.

Worth knowing for the follow-up: **`DL3008` is ignored by the `hadolint` pre-commit hook but not by
`docker-build-check`** — that asymmetry is precisely why this finding was invisible until now. Per D-09 the
`--ignore` list was **not** extended and `authentik/Dockerfile` was **not** edited.

Note also that `coding-assistants` — the Dockerfile the objective flagged for `curl | bash` installers and unpinned
`latest` downloads — exits 0 here, because `DL3016` (unpinned `npm install -g`) is one of the four pre-existing
ignores and hadolint has no rule for `curl | bash` at all. Its coverage gap is a rule-coverage gap, not a target gap.

## 5. `make check-all` — green and measured offline

| Run | Result |
| --- | --- |
| `make check-all` | **rc=0**, both new hooks `Passed` |
| `make check-all` with `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` -> `127.0.0.1:1` **and** `GH_TOKEN`/`GITHUB_TOKEN` set | **rc=0**, 0 failed hooks |

The second row is the substantive one: it proves `--offline` overrides token presence (D-05) and that no `check-all`
member reaches the network at run time. The only matches for
`connection refused|could not resolve|network|timeout|proxy` in that run are four occurrences of the string
`network-tools` (an add-on name).

## Decisions Made

See `key-decisions` in the frontmatter. The two that change what a future reader should believe:

1. **The plan's negative-control shape was wrong for this gitleaks version, and the plan's allowlist control was a
   false pass.** Both were replaced with controls that were measured to discriminate. This is the D-01 mechanism doing
   exactly its job: had either been accepted at face value, this task would have shipped a "verified" gate on the
   strength of two tests that could not fail.
2. **The narrow pinning relaxation shipped**, so `unpinned-uses` remains a live audit rather than a disabled one.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The specified gitleaks negative-control shape cannot fail the hook**

- **Found during:** Task 1 Step 5
- **Issue:** The plan specifies an `AKIA` + 16-uppercase-alphanumeric literal as the planted control. gitleaks v8.30.1
  does not flag that shape in file or staged-diff scan mode — 0 detections across 10 random draws, reproduced with the
  hook's own binary, with the container image, and with no config present at all. Accepting the initial run would have
  recorded a disarmed-looking gate as verified.
- **Fix:** Diagnosed the miss (rule present but non-matching, confirmed via `--enable-rule` accepting
  `aws-access-token` while rejecting a bogus id), then measured candidate shapes and substituted `ghp_` + 36
  alphanumerics — 10/10 detections, and the most relevant shape for this repo's GHCR tokens. Recorded in `key-decisions`,
  in `docs/DEVELOPMENT.md` as a standing coverage caveat, and in section 1a above.
- **Files modified:** none (control is runtime-only); the caveat is documented in `docs/DEVELOPMENT.md`
- **Verification:** `pre-commit run gitleaks` exits 1 on 3 of 3 independent draws; tree clean afterwards
- **Committed in:** `5d2963a` / documented in `6b678c9`

**2. [Rule 1 - Bug] The specified allowlist control passes with the allowlists removed**

- **Found during:** Task 1 Step 6
- **Issue:** Step 6 appends comment-prefixed copies of the `r2Hex*` constant lines to the allowlisted fixture and
  requires exit 0. It does exit 0 — but so does the identical run with both `[[allowlists]]` blocks stripped out of
  `.gitleaks.toml`. The control could not distinguish "the allowlist works" from "the rule never fires here", the same
  class of false pass as deviation 1. A second variant (in-place whitespace re-emission of the two real `const` lines)
  had the same defect.
- **Fix:** Replaced with a paired control that holds config, scan mode and literals fixed and varies only the path:
  the identical two literals pass on their allowlisted path and fail (rc=1, both findings, matching entropies) on a
  non-allowlisted path. Additionally proved load-bearing at the history level through the hook's own binary: 0 leaks
  with the blocks, exactly the baseline 8 without them.
- **Files modified:** none (control is runtime-only)
- **Verification:** arm 1 rc=0, arm 2 rc=1; `FIXTURE_BYTE_IDENTICAL_OK`, `TREE_CLEAN_OK`
- **Committed in:** `5d2963a`

**3. [Rule 3 - Blocking] First negative-control run failed for the wrong reason**

- **Found during:** Task 1 Step 5
- **Issue:** `pre-commit run gitleaks` returned rc=1 with
  `[ERROR] Your pre-commit configuration is unstaged.` — pre-commit refusing to run, which the plan's gate
  (`test "$RC" -ne 0`) would have scored as `NEGATIVE_CONTROL_OK`.
- **Fix:** Staged `.pre-commit-config.yaml` and `.gitleaks.toml` first, confirmed the hook runs clean on the real
  staged diff (rc=0), and only then planted the control. Both the false pass and the cause are recorded in section 1a.
- **Files modified:** none
- **Verification:** clean-diff run rc=0 with `Passed`, then planted-control run rc=1 with a `github-pat` finding
- **Committed in:** `5d2963a`

---

**Total deviations:** 3 auto-fixed (2x Rule 1, 1x Rule 3)
**Impact on plan:** No scope creep — all three are corrections to the plan's *verification* design, not to its
deliverables. Every locked decision D-01 through D-09 was honored; D-01 is in fact the reason deviations 1-3 were
caught rather than banked. Nothing under `.github/` was edited or committed, no `--ignore` code was added, no
Dockerfile or workflow was touched, and nothing from `<out_of_scope>` was started.

## Issues Encountered

- **The built gitleaks binary reports `version is set by build process`** instead of `8.30.1`, because pre-commit's Go
  build does not inject the version ldflags. Version identity therefore rests on the pinned `rev: v8.30.1` source ref,
  plus behavioural agreement with the v8.30.1 container image (both produce the identical 8-finding baseline with the
  identical entropies). Not a blocker; worth knowing before anyone tries to assert the version from `--version`.
- **`pre-commit` batches hook invocations**, so zizmor printed three separate run summaries rather than one. The
  headline count is the sum (81 total / 32 suppressed / 49 reported), not any single summary line.

## Known Stubs

None. No placeholder, hardcoded-empty or TODO value was introduced.

## Follow-ups (reported, deliberately not started)

1. **Highest value: a scheduled `trivy image` scan of the nine published GHCR images with SARIF upload into GitHub Code
   Scanning.** That is where the CVEs actually live — this repository holds no upstream application source, so nothing
   local can find them. Belongs to the still-open **Phase 8 "CI/CD Hardening"**. Explicitly out of scope here.
2. **The 27 deferred zizmor findings**, `template-injection` in `_build-template.yml` first (7 error-severity sites
   interpolating `${ inputs.* }` straight into `run:` blocks), then `opencode.yml`'s comment-triggered secret hand-off
   to a mutable action ref. Every entry in `zizmor.yml` is a deferral, not a disposition. Phase 8.
3. **`authentik/Dockerfile:15 DL3008`** — the one hadolint finding the widened target surfaced. Either pin the apt
   package versions or add `DL3008` to `docker-build-check`'s ignores *with a stated reason*; do not add it silently,
   since the whole point of that target is to run stricter than the pre-commit hook.
4. **`tools/test-addon` is invisible to both `docker-build-check` and `validate-addons`.** It carries `config.yaml`,
   `build.yaml`, `Dockerfile` and `run.sh`, and `internal/validate-versions.sh` *does* discover it
   (`Found add-ons: ... tools/test-addon`), but the shared `for addon_dir in */` idiom only sees depth-1 directories.
   Widening it was declined here because D-02 forbids inventing a new discovery mechanism and the plan defines an
   add-on as a top-level directory. Low urgency: `hadolint` on `tools/test-addon/Dockerfile` currently exits 0. The
   real defect is that the repo has **two** disagreeing definitions of "add-on".
5. **Re-verify the gitleaks controls on any pin bump.** The AWS-shape miss shows that default-ruleset coverage changes
   between versions without notice. `docs/DEVELOPMENT.md` now says so.

## Next Phase Readiness

Both gates are live, offline, and demonstrated capable of failing. `make check-all` is green. Phase 8 "CI/CD
Hardening" now has a concrete, enumerated, per-location worklist (follow-up 2) that did not exist before this task,
plus two independent gates that will keep new instances of the same defects from landing while that work is pending.

## Self-Check: PASSED

| Claim | Check | Result |
| --- | --- | --- |
| `.gitleaks.toml` created | file exists | FOUND |
| `zizmor.yml` created | file exists | FOUND |
| `5d2963a` (Task 1) | `git log` | FOUND |
| `a39f4b2` (Task 2) | `git log` | FOUND |
| `16cf8df` (Task 3 Step 1) | `git log` | FOUND |
| `6b678c9` (Task 3 Step 2) | `git log` | FOUND |
| Commit count | `git rev-list --count 1a8406f..HEAD` | 4, matches `actuals.commits` |
| D-08 compliance | `gitleaks dir` on this SUMMARY, not allowlisted | `no leaks found` |

---

_Quick task: 260910-u0m_
_Completed: 2026-09-10_
