---
quick_id: 260909-rlk
stage: 3
status: complete
subsystem: ci-guards
tags: [ghcr, image-availability, scheduled-workflow, supervisor-pull, anti-silent-pass]

requires:
  - internal/check-version-tags.sh (output vocabulary, config.yaml parser precedent, set -e traps)
  - internal/validate-versions.sh (mapfile process-substitution pattern, depth-3 add-on discovery)
  - .github/scripts/notify-ha.sh (never-parses-payload / always-exit-0 failure-notification contract)
  - .github/workflows/_build-template.yml (CONFIG_VERSION -> OCI tag, the tag this guard asks for)
  - .github/workflows/auto-update.yml (scheduled-workflow concurrency precedent)
provides:
  - internal/verify-image-availability.sh (three-state ghcr probe + repo-wide scan + --self-test + --dry-run fixture)
  - .github/workflows/verify-image-availability.yml (four-times-daily scheduled guard, self-test-before-scan)
  - "Makefile: verify-images + verify-images-self-test targets"
affects:
  - Makefile (.PHONY line + two new targets; check-all deliberately untouched)

tech-stack:
  added: []
  patterns:
    - anonymous-only registry probe as a correctness condition, not least-privilege hygiene
    - three-state classification (ok / missing / denied) with a fourth inconclusive state on a distinct exit code
    - self-test-before-scan ordering so a green scan is only meaningful because the classifier was just proven
    - deterministic refusal (exit 2) instead of a best-effort warning where the failure mode would be a green check

key-files:
  created:
    - internal/verify-image-availability.sh
    - .github/workflows/verify-image-availability.yml
  modified:
    - Makefile

decisions:
  - The registry path is read from the config.yaml `image:` VALUE, never from the directory name re-slugged; a re-derived slug would agree with a typo'd key and mask the exact bug that breaks the pull.
  - A single Accept header carrying all four media types (OCI index, docker manifest list v2, OCI manifest, docker manifest v2) rather than four separate headers — the registry spec expects one comma-separated header, and an index-only header would 404 a genuinely present single-arch image.
  - The dispatch input keeps its hyphenated name `grace-minutes` and is read as `github.event.inputs['grace-minutes']`; verified clean under actionlint v1.7.3 AND v1.7.12, so no rename was needed.
  - `--summary-file` APPENDS rather than truncates, because `$GITHUB_STEP_SUMMARY` is shared with other steps in the job.
  - A template without an `{arch}` placeholder is probed ONCE, not once per declared arch — it is a legal single-arch HA image reference.
  - `.claude/` is pruned in add-on discovery alongside `config/`: agent worktrees hold full working-tree copies. Structurally unreachable at maxdepth 3 today, kept as cheap insurance.

metrics:
  duration: 19 min
  completed: 2026-09-09

actuals:
  tokens: 11519
  tasks: 3
  commits: 3
plan_head_before: 440e030207fccd25117441446b7240c1292549a6
---

# Quick 260909-rlk: ghcr Image-Availability Guard Summary

A scheduled guard that turns the silent, live-breaking image-availability failure into a loud one: for every add-on
declaring a top-level `image:` key, an anonymously-pullable manifest must exist at the exact `version:` in
`config.yaml`, for every active arch — proven by a probe that is itself proven in all three directions before it is
trusted, and that refuses to run rather than lie when it cannot check reliably.

## What Shipped

| Artifact                                            | Role                                                                                 |
| --------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `internal/verify-image-availability.sh`             | 980-line guard: token+manifest probe, three-state classifier, repo-wide scan, modes  |
| `.github/workflows/verify-image-availability.yml`   | Scheduled 4x daily at `:30`, self-test step BEFORE scan step, `if: failure()` notify |
| `Makefile`                                          | `verify-images`, `verify-images-self-test` — both on `.PHONY`, neither in `check-all` |

Three atomic commits:

| Task | Name                                                     | Commit    |
| ---- | -------------------------------------------------------- | --------- |
| 1    | End-to-end ghcr probe, three-way classification (tracer)  | `9fc295d` |
| 2    | Full scan, grace window, two anti-silent-pass safeguards  | `d4c6630` |
| 3    | Scheduled workflow + Makefile targets                     | `a2b66fc` |

## Verification Results

All three task gate suites pass, plus the plan's seven cross-task checks. Every gate was re-run against the FINAL
file state, not only against the state at its own commit.

| Check                                                          | Result                                                     |
| -------------------------------------------------------------- | ---------------------------------------------------------- |
| `shellcheck` (no `-e` flags, the stricter CI form)              | clean                                                      |
| `--self-test`                                                   | 3 check-marks, 0 cross-marks, exit 0                       |
| `--dry-run \| wc -l`                                            | exactly 8, diffs clean against the ground-truth list       |
| `--grace-minutes 0`                                             | 8 check-marks, 0 cross-marks, 0 warnings, 1 `✅`, exit 0    |
| `make verify-images` / `make verify-images-self-test`           | both exit 0 against the live registry                      |
| `make check-all`                                                | exit 0, and zero ghcr.io requests — still offline          |
| `pre-commit run --all-files`                                    | clean (ran as part of `make check-all`)                    |
| `yamllint -c .yamllint.yml` + actionlint v1.7.3 **and** v1.7.12 | clean under all three                                      |

### The load-bearing evidence

The repo is GREEN — all 8 image/arch pairs return HTTP 200 — so a passing scan proves nothing by itself. What proves
detection works:

- **`--self-test`, all three directions against the third-party control image `ghcr.io/home-assistant/amd64-base`:**
  `latest` → `ok`, `0.0.0-gsd-selftest-absent` → `missing`, and `…-base-gsd-selftest-absent:latest` → `denied`. All
  three classified as expected against live ghcr.
- **Both negative `--probe` directions exit 1**, and an uninterpretable reference
  (`https://evil.example.com/x?ghcr.io/a`) is refused with exit 1 rather than requested.
- **Both halves of the annotation channel:** with `GITHUB_ACTIONS=1` a violation emits `::error::`; with the variable
  unset it emits none. This is the only gate on the first of the two mandated failure channels, because a green repo
  never walks the scan's violation path.

### Both safeguards fire on the same measured input

- **Safeguard 1 (shallow clone → exit 2):** verified against a real `git clone --depth 1 file://…` of this worktree.
  The scan path exits 2 with the explanation; `--help`, `--self-test` and `--dry-run` still exit 0 there, and the
  shallow `--dry-run` produces the SAME line count as the full-clone one — direct proof it reads no history at all.
- **Safeguard 2 (`passes == 0 && skips > 0`):** `--addon authentik` exits 0 with the `⊘` skip and the `⚠️` warning
  and zero passes.
- **The grace window is load-bearing, not decorative:** `--grace-minutes 999999 --addon gatus` turns a pass into a
  visible grace skip (`version '5.36.0-11' landed 121648 minute(s) ago, inside the 999999-minute grace window`).

### The 8-line `--dry-run` fixture, reproduced exactly

```
· coding-assistants ghcr.io/akentner/homeassistant-addons/amd64-coding_assistants:1.0.0-2
· coding-assistants ghcr.io/akentner/homeassistant-addons/aarch64-coding_assistants:1.0.0-2
· gatus ghcr.io/akentner/homeassistant-addons/amd64-gatus:5.36.0-11
· markdown-renderer ghcr.io/akentner/homeassistant-addons/amd64-markdown_renderer:1.1.0-23
· meridian ghcr.io/akentner/homeassistant-addons/amd64-meridian:1.68.0-0
· network-tools ghcr.io/akentner/homeassistant-addons/amd64-network_tools:0.5.0-1
· phone-logger ghcr.io/akentner/homeassistant-addons/amd64-phone_logger:1.0.6-0
· terraform-bridge ghcr.io/akentner/homeassistant-addons/amd64-terraform_bridge:0.3.0-0
```

`gatus` and `meridian` yield ONLY `amd64` (their four commented-out arch lines stay inert), `network-tools` resolves
despite its 4-space list indent, `coding-assistants` yields two lines, and `authentik` / `iac-runner` /
`tools/test-addon` yield nothing — skipped by the image-key rule itself, with no allowlist that can go stale.

Pairing is gated per line, not per output: every dry-run line for an add-on ends with that add-on's own
`-<slug>:<version>` suffix compared as a literal string, so a parser bug that attached one add-on's version to
another's line would still go red.

## Deviations from Plan

None affecting behaviour. Three implementation choices the plan left open, resolved and recorded:

1. **Accept header shape.** The plan said "an `Accept` header listing all four of…". Implemented as ONE
   comma-separated header rather than four separate `-H Accept:` flags — the OCI distribution spec expects a single
   comma-separated header, and it removes any dependence on how a registry merges repeated headers.
2. **Glyph constants introduced per task.** `GLYPH_SKIP` and `GLYPH_DRY` were omitted from the Task 1 commit and
   added in Task 2 when the scan first used them. CI's shellcheck does not exclude SC2034, so declaring them unused
   in Task 1 would have failed the Task 1 gate on its own `shellcheck` line.
3. **`--dry-run` skips add-ons with no parseable `version:`** rather than reporting a violation. The
   zero-active-archs and unparseable-version violations belong to the scan path only, because `--dry-run` must print
   nothing but its 8 fixture lines.

No auto-fixes under deviation Rules 1-3 were needed; no architectural decision (Rule 4) arose.

## Accepted Unproven Branches

The plan pre-dispositioned both of these as `accept, UNPROVEN` in its `<coverage>` block. They ship without a gate
that exercises them, recorded here so no later reader assumes the exit contract is fully tested:

| Branch                                                     | Why no gate exercises it                                                                                          |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `inconclusive` → exit 2 (transport failure / 5xx / 429)     | No offline fault-injection path in scope; every gate makes real calls to a healthy ghcr.io, so the retry-then-give-up path is never entered. Anyone editing `probe_manifest`'s retry logic gets NO gate feedback — re-read the exit contract instead. |
| `image:` present with ZERO active archs → exit 1            | Unreachable in this repo: all 7 image-declaring add-ons have ≥1 active arch. The condition is exactly `image:` present AND the parsed arch list empty — never "arch list empty" alone, which is also true of the three no-`image:` add-ons that must `⊘` skip (and are gated). |

These are deliberate, reasoned trade-offs with recorded rationale, not defects left behind, so they are **not**
appended to `.planning/WINDOWS.md` — that ledger blocks `/gsd-ship`, and blocking a ship on a risk the plan
explicitly accepted would be wrong. No stubs, no skipped tests, and no unrun `<verify>` blocks exist in this item:
every gate in all three tasks was executed against the live registry.

## Known Stubs

None. Every code path is real and wired. The seven `placeholder` matches in the script all refer to the `{arch}`
substitution placeholder — implemented functionality, not a stub.

## Threat Flags

None. Every trust boundary this item crosses was already in the plan's `<threat_model>`: `config.yaml` → curl URL
(T-rlk-01, mitigated by the anchored `ghcr.io/[A-Za-z0-9._/-]+` allowlist and no redirect-following), bearer token
vs. public Actions log (T-rlk-02), authenticated-probe spoofing (T-rlk-03, mitigated on both sides — the script reads
no credential and the workflow grants no registry scope), green-run-that-checked-nothing (T-rlk-04, both safeguards),
ghcr rate limiting (T-rlk-05), registry mutation (T-rlk-06, no write surface and `contents: read`), and HA webhook
secrets (T-rlk-07, boundary unchanged and owned by `notify-ha.sh`). No package-manager install anywhere in scope.

## Notes for the Next Person

- **Do not add a registry credential to make anything "more reliable".** An authenticated probe returns 200 for an
  image only pullable WITH credentials — exactly what the Supervisor cannot do — so a credentialed guard would
  certify a broken add-on as healthy. Both sides are gated: the script's comment-stripped negative greps, and the
  workflow's absence of any `packages:` scope.
- **Do not add `verify-images` to `check-all`.** Every current `check-all` member is offline, deterministic, and
  fails only for something in your own working tree. A check people learn to bypass also devalues the four
  legitimate offline checks beside it.
- **`fetch-depth: 0` in the workflow is mandatory, not an optimisation.** Without full history the grace lookup
  returns HEAD's date for every add-on, grace-skips all of them, and the guard exits 0 having probed nothing. The
  script now refuses that state deterministically, so a shallow checkout turns the job red rather than falsely
  green — but full history is the actual fix.
- **The `denied` verdict is genuinely ambiguous.** ghcr does not distinguish a missing package from a private one
  for anonymous callers, and the 403 arrives at the TOKEN endpoint, not the manifest endpoint. Messages must not
  claim to know which — they currently say both need checking.
- `authentik` and `iac-runner` are skipped because they declare no `image:` key. Their keys are a deliberate
  follow-up, blocked until CI has published an image for them; when either gains the key it starts being enforced
  automatically, with no allowlist to update.
- Documentation for this guard belongs to batch item `260909-rlm` (Stage 5); `.github/RELEASE.md` and
  `docs/AUTO_UPDATE_GUIDE.md` were deliberately not touched.

## Self-Check: PASSED

| Claim                                             | Verified                                |
| ------------------------------------------------- | --------------------------------------- |
| `internal/verify-image-availability.sh` exists     | FOUND, mode 755, 980 lines              |
| `.github/workflows/verify-image-availability.yml`  | FOUND, 103 lines                        |
| `Makefile` carries both targets on `.PHONY`        | FOUND, `check-all` byte-identical       |
| Commit `9fc295d`                                   | FOUND                                   |
| Commit `d4c6630`                                   | FOUND                                   |
| Commit `a2b66fc`                                   | FOUND                                   |
| `commits: 3` measured, not narrated                | `rev-list --count 440e030..HEAD` = 3    |
