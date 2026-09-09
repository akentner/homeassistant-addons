---
quick_id: 260909-rlk
stage: 3
verified: 2026-09-09T20:45:00Z
status: human_needed
score: 7/8 must-haves verified
covered_files:
  - .github/workflows/verify-image-availability.yml
  - .planning/quick/stage-3-add-a-ci-guard-that-turns-the-silent-live-breaking-i/260909-rlk-PLAN.md
  - .planning/quick/stage-3-add-a-ci-guard-that-turns-the-silent-live-breaking-i/260909-rlk-SUMMARY.md
  - Makefile
  - internal/verify-image-availability.sh
covered_digest: "v1:sha256:6f2c6aaed232ee5b66c4550cfa3e05f6193245f9fd90d8cf8fae7ed9963ab87b"
behavior_unverified: 1
overrides_applied: 0
behavior_unverified_items:
  - truth: "If any declared image/arch pair loses its anonymously-pullable manifest for the exact `version:` in config.yaml, the next scheduled run turns red, emits `::error::` annotations, and posts to the HA webhook."
    test: >-
      Two of the three conjuncts are behaviorally proven locally (see Observable Truth 3). The third
      — the `if: failure()` HA webhook delivery — has never executed, because the workflow has never
      run on GitHub. Trigger it: `gh workflow run verify-image-availability.yml -f grace-minutes=0`
      to confirm the green path (self-test step green, scan step green, step summary table rendered
      from `--summary-file "$GITHUB_STEP_SUMMARY"`, `grace-minutes` dispatch input reaching the
      script). Then confirm the red path once, e.g. by dispatching from a scratch branch whose
      `gatus/config.yaml` carries an unpublished `version:`: the job must go red, the
      `::error::` annotations must appear in the Actions UI, and the `Notify HA — image availability
      check failed` step must run and post to the HA webhook.
    expected: >-
      Green run: both steps pass, markdown summary table present. Red run: job fails with exit 1,
      one `::error::` annotation per violating pair, and the notify step runs (notify-ha.sh always
      exits 0, so it cannot mask the job failure).
    why_human: >-
      A GitHub-runner-only behavior. `if: failure()` step dispatch, `$GITHUB_STEP_SUMMARY` writes,
      `github.event.inputs['grace-minutes']` resolution, and the HA/Cloudflare-Access secrets all
      exist only inside a real Actions run. No local probe can exercise them, and grep cannot prove
      an untriggered workflow fires.
human_verification:
  - test: >-
      Dispatch `.github/workflows/verify-image-availability.yml` once green
      (`gh workflow run verify-image-availability.yml -f grace-minutes=0`), then once red from a
      scratch branch carrying an unpublished `version:` in one add-on's config.yaml.
    expected: >-
      Green: self-test step and scan step both pass; the job summary shows the 11-row availability
      table. Red: job exit 1, `::error::` annotations visible as annotations, and the
      `Notify HA — image availability check failed` step executes and posts to the HA webhook.
    why_human: "Actions-runtime behavior — the workflow has never run; `if: failure()`, step summary and secrets are not locally reachable."
advisory:
  - finding: >-
      `parse_archs`' block-form opener is `/^arch:[ \t]*$/`, so the YAML-legal shape
      `arch:  # active build targets` (trailing comment on the key line) yields ZERO active archs.
      For an add-on that also declares `image:`, that produces a FALSE violation (exit 1);
      `python3 yaml.safe_load` parses the same file as `{'arch': ['amd64']}`. Not present in the
      repo today, and the implementation matches the plan's literal spec ("only optional whitespace
      after the colon"), so this is a spec-level narrowness, not a deviation.
    category: other
    reason: >-
      Fails LOUD (exit 1 with a legible message), never silent, so it cannot cause the failure mode
      this guard exists to prevent. Resolution: widen the awk opener to tolerate a trailing comment
      (`/^arch:[ \t]*(#.*)?$/`). Raised because the guard's whole value is that people trust it, and
      a false red erodes that as surely as a false green.
    evidence_status: "reproduced (temp full clone, `arch:  # active build targets only` on gatus -> exit 1 zero-active-archs violation)"
  - finding: >-
      The plan and SUMMARY both ship `inconclusive -> exit 2` and `image:`-present-with-zero-active-archs
      `-> exit 1` as "accept, UNPROVEN", on the stated premise that "there is no offline
      fault-injection path in scope". That premise is factually too strong: a 12-line `curl` shim
      earlier on `PATH` returning `503` exercises the entire retry-then-give-up path offline in
      under a minute, and commenting out an add-on's only active arch in a throwaway clone reaches
      the zero-arch branch. Both branches are now behaviorally proven (see Observable Truth 4 and
      the Behavioral Spot-Checks table).
    category: other
    reason: >-
      No action needed on the code — both branches behave exactly as specified. The correction is to
      the reasoning: the branches were reachable all along. Worth recording so the next person does
      not inherit "this cannot be tested" as fact.
    evidence_status: "reproduced (PATH curl shim -> 503; exit 2 on --probe, scan and --self-test; exactly 3 attempts, 1s+2s backoff)"
  - finding: >-
      The plan's own remediation note for the unproven `inconclusive` branch ("Anyone editing
      `probe_manifest`'s retry logic gets no gate feedback — re-read the exit contract instead")
      lives only in `.planning/quick/.../260909-rlk-PLAN.md` and the SUMMARY. The script header
      documents the exit contract but nowhere states that any branch of it lacks a gate. The reader
      the warning is addressed to is someone editing `probe_manifest` — who will be in
      `internal/verify-image-availability.sh`, not in a quick-batch planning artifact.
    category: other
    reason: >-
      Now largely moot (both branches proven above), but the durable fix is a two-line comment above
      `probe_manifest`'s retry loop rather than a planning-artifact table.
    evidence_status: "reproduced (grep: no gate/unproven/untested marker anywhere in the script body)"
---

# Quick 260909-rlk: ghcr Image-Availability Guard — Verification Report

**Item Goal:** A CI guard that turns a silent, live-breaking failure into a loud one. INVARIANT: for
every add-on whose `config.yaml` declares a top-level `image:` key, an anonymously-pullable manifest
must exist at that image repository for the exact `version:` string in `config.yaml`, for every
active arch in its `arch:` list.

**Verified:** 2026-09-09T20:45:00Z
**Status:** human_needed
**Re-verification:** No — initial verification
**Commits verified:** `9fc295d`, `d4c6630`, `a2b66fc` (merge `64a3cce`); base `440e030`; all four objects present.

## Headline

The guard works, and it works for the right reason. I did not take the green scan as evidence — I
broke the repo in throwaway clones and confirmed the guard goes red, and I broke the network with a
`PATH` shim and confirmed the guard refuses to guess. **Both branches the plan shipped as
deliberately UNPROVEN are now behaviorally proven**, and the one truth I could not close is the one
nobody could close locally: the workflow has never run on GitHub, so the `if: failure()` HA webhook
leg has never executed.

Everything the requester asked me to check independently came back correct, including the two
properties that would have been real defects if wrong: the guard reads the registry path from the
`image:` VALUE (a typo'd key turns it red rather than silently agreeing), and it reads no credential
anywhere (so it cannot certify an image only pullable WITH credentials).

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Bare run on a full clone probes all 8 declared pairs and exits 0 | ✓ VERIFIED | Bare `./internal/verify-image-availability.sh` (default 45-min window, no flags): 8 `✓`, 3 `⊘`, one `✅` aggregate, exit 0. Same under `--grace-minutes 0`. `make verify-images` exit 0. |
| 2 | Three-way classification proven in all three directions against a third-party control image, in its own step, BEFORE the scan | ✓ VERIFIED | `--self-test` exit 0 with 3 `✓` (requester-measured; independently re-derived from `run_self_test`, `internal/verify-image-availability.sh:895-919`). Workflow: `Self-test the ghcr probe` at line 64, `Scan all add-ons` at line 67 — strictly before. Additionally proven load-bearing: under an injected 503 the self-test goes red on all three directions and exits 2, so a broken classifier halts the job before any scan runs. |
| 3 | A lost manifest turns the next scheduled run red, emits `::error::`, and posts to the HA webhook | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Two of three conjuncts behaviorally PROVEN, which is more than the SUMMARY claimed: in a full clone I set `gatus/config.yaml` to `version: "9.9.9-gsd-verifier"`, committed, and ran the **scan** path (not `--probe`) — exit 1, `❌` line, `::error::` annotation under `GITHUB_ACTIONS=1`, and the remediation block naming the exact reference. The third conjunct — the `if: failure()` webhook post — has never executed: the workflow has never run. Wiring is correct (`.github/workflows/verify-image-availability.yml:85-103` -> `.github/scripts/notify-ha.sh`; env contract matches `notify-ha.sh:44-62,80`; `NOTIFY_EVENT: finished` matches the values `_build-template.yml` already uses). Routed to human verification. |
| 4 | A network blip, a shallow clone, a failed self-test, or a bad argument exits 2 — never reported as a broken add-on, but still a failing job | ✓ VERIFIED | All four exercised. **Network blip:** `PATH` curl shim returning 503 -> exit 2 on `--probe`, on the scan path, and on `--self-test`; exactly 3 attempts in 3.035s (1s+2s backoff); scan wording is explicit — "This is NOT a report that any add-on is broken". **Shallow clone:** exit 2 (below). **Failed self-test:** exit 2. **Bad argument:** `--nope` -> 2, `--addon no-such-addon` -> 2, `--grace-minutes abc` -> 2. This closes the plan's first "accept, UNPROVEN" branch. |
| 5 | A bump pushed minutes before a run is not reported broken: each add-on has its own grace window dated from git history | ✓ VERIFIED | `--grace-minutes 999999 --addon gatus` -> `⊘ gatus: version '5.36.0-11' landed 121666 minute(s) ago, inside the 999999-minute grace window`, zero passes, exit 0. Per-add-on by construction: `version_age_minutes` (`:497-511`) runs `git log -1 --format=%ct -S"$version" -- "$addon/config.yaml"`, scoped to that add-on's own file. Not from the cron schedule anywhere. |
| 6 | A run that grace-skipped everything cannot look green-and-clean | ✓ VERIFIED | **Safeguard 1:** real `git clone --depth 1` -> bare scan exit 2 with a 6-line legible refusal; `--addon`, `--summary-file` and even `--grace-minutes 0` also exit 2, while `--help`, `--self-test`, `--dry-run` and `--probe` all exit 0. Zero curl calls made before the refusal. **Age-independent:** I amended the shallow HEAD to a committer date of 2025-01-01 (age 888330 min, far outside any window) — still exit 2. The refusal derives solely from `git rev-parse --is-shallow-repository` (`:513-534`), never from a timestamp. **Safeguard 2:** `--addon authentik` -> `⊘` skip + `⚠️ no image was verified in this run: 1 add-on(s) were skipped and not a single manifest was probed`, zero `✓`, exit 0. Same for `iac-runner` and `tools/test-addon`. |
| 7 | The probe authenticates with nothing but the anonymous ghcr pull token | ✓ VERIFIED | Code-level, comment-stripped body (whole-line AND trailing comments removed): 0 hits for `GITHUB_TOKEN`, `GH_TOKEN`, `CR_PAT`, `REGISTRY_PASSWORD`, `docker login`, `--user`, `netrc`, `Authorization: Basic`, `PASSWORD`, `SECRET`. The **only** environment variable the script reads at all is `GITHUB_ACTIONS` (annotation gating). Exactly one `Authorization` header exists (`:329`), carrying the token just fetched anonymously from `ghcr.io/token`. Exactly two curl call sites, both `https://ghcr.io/...`, neither with `-L`/`--location`; no `set -x`; no `yq`. Workflow grants `contents: read` and nothing else — zero `packages:` keys. Empirically: the logging shim shows the 403 path makes ONE call (token endpoint only) and the 404 path TWO (token + manifest), with no retry on either — 404 and 403 are treated as answers, as specified. |
| 8 | `make check-all` stays entirely offline and deterministic; the probe is reachable only via `make verify-images` / `make verify-images-self-test` | ✓ VERIFIED | `make check-all` exit 0. Under a logging `curl` shim it made **zero** curl calls of any kind. `make -n check-all` expansion: 0 references to `verify-image-availability`/`verify-images`, 0 references to `ghcr.io`; it invokes only `validate-dockerfile-args.sh` and `validate-versions.sh`. `git diff 440e030..HEAD -- Makefile` touches the `check-all` line not at all (`Makefile:265` byte-identical). Both new targets present (`:105`, `:109`) and on `.PHONY` (`:4`). |

**Score:** 7/8 truths verified (1 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `internal/verify-image-availability.sh` | 755, probe + scan + modes | ✓ VERIFIED | 980 lines, git mode `100755`, `#!/usr/bin/env bash`, `set -euo pipefail`. `shellcheck` with no `-e` flags: clean. All 8 documented modes/flags behave per the exit contract. |
| `.github/workflows/verify-image-availability.yml` | 4x-daily schedule, self-test before scan, two failure channels | ✓ VERIFIED | 103 lines. `cron: "30 2,8,14,20 * * *"`; `workflow_dispatch` with `grace-minutes` (string, default `"45"`); `permissions: contents: read` only; `concurrency` with `cancel-in-progress: false`; `timeout-minutes: 10`; `runs-on: ubuntu-latest`; `actions/checkout@v7` + `fetch-depth: 0`; self-test step (64) before scan step (67); `if: failure()` notify step (86). `yamllint -c .yamllint.yml` clean. No tabs, no `${{ vars. }}`. |
| `Makefile`: two targets + `.PHONY` | present, neither in `check-all` | ✓ VERIFIED | `verify-images` and `verify-images-self-test` at `:105`/`:109`, both on `.PHONY:4`, both exit 0. Preceded by a 7-line comment recording why they are excluded from `check-all`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `config.yaml` `image:` VALUE | registry path probed | `parse_image` (`:426-430`), never a re-slugged dir name | ✓ VERIFIED | **Proven behaviorally, not by reading.** I changed gatus's `image:` to `...{arch}-gattus` (a typo) in a throwaway clone. The guard went RED: `❌ gatus ghcr.io/.../amd64-gattus:5.36.0-11 is not anonymously pullable ... (HTTP 403)`, exit 1. A re-derived slug would have probed `amd64-gatus` and passed. Also confirmed an *indented* `image:` sub-key under `options:` does NOT satisfy the anchored parse. |
| `config.yaml` `version:` | OCI tag asked for | `parse_version` (`:433-437`) | ✓ VERIFIED | Same string the builder publishes: `_build-template.yml:78` sets `CONFIG_VERSION=$(yq eval '.version' .../config.yaml)` and `:176` pushes `.../{arch}-{slug}:${{ steps.meta.outputs.CONFIG_VERSION }}`. Subpatch included (`5.36.0-11` probed, not `5.36.0`). |
| `--self-test` step | scan step | workflow step order | ✓ VERIFIED | Line 64 < line 67. Fail-closed: a red self-test exits 2, the scan step is skipped, and `if: failure()` still fires. |
| `actions/checkout@v7` + `fetch-depth: 0` | `git log -S` grace lookup | `require_full_history` (`:513-534`) | ✓ VERIFIED | The trap is real and I measured it: in the depth-1 clone `git log -1 --format=%ct -S"$version"` returned `1788985623` for gatus, meridian AND phone-logger — identical to HEAD's `%ct`. The refusal preempts it deterministically. |
| `if: failure()` | `.github/scripts/notify-ha.sh` | `NOTIFY_PAYLOAD` env | ⚠️ WIRED, NOT EXECUTED | Statically correct: all four secrets, `NOTIFY_EVENT: finished` (matches `notify-ha.sh:44` and `_build-template.yml:188`), `NOTIFY_DELIVERY_ID` = run id + run number, and a payload carrying repository, run URL, `job.status` and trigger. `notify-ha.sh` never parses the payload and always exits 0 (`:49,86,96,115`), so it can neither reject nor mask the failure. Never executed — see Truth 3. |
| `check-all` | must NOT gain `verify-images` | Makefile | ✓ VERIFIED | Line unchanged in the diff; expansion contains no reference; zero network calls. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Real repo, nonexistent tag -> `missing` | `--probe 'ghcr.io/home-assistant/{arch}-base' --probe-version 0.0.0-gsd-verifier-absent` | `❌ ... no manifest at this tag (HTTP 404); this version was never published` | ✓ PASS (exit 1) |
| Nonexistent repo -> `denied` | `--probe 'ghcr.io/home-assistant/{arch}-base-gsd-verifier-nope' --probe-version latest` | `❌ ... ghcr refused an anonymous pull token (HTTP 403) ... ghcr does not tell an anonymous caller whether it is missing or private` | ✓ PASS (exit 1) |
| **`denied` does not overclaim** | inspect both `denied` messages + remediation | Message says ghcr "does not tell an anonymous caller whether it is missing or private"; remediation says "BOTH need checking: that the package exists at all, and that its visibility is public". No claim either way. | ✓ PASS |
| Non-ghcr reference refused, not requested | `--probe 'https://evil.example.com/x?ghcr.io/a'` | `❌ uninterpretable image reference ...` | ✓ PASS (exit 1) |
| `docker.io` reference refused | `--probe 'docker.io/library/{arch}-alpine'` | refused | ✓ PASS (exit 1) |
| Shell-metachar injection refused | `--probe 'ghcr.io/a;curl evil.example.com'` | refused, no request made | ✓ PASS (exit 1) |
| **Scan path detects a real violation** | inject `version: "9.9.9-gsd-verifier"` in a full clone, `--grace-minutes 0 --addon gatus` | `❌` + `::error::` + remediation + `🚫` aggregate | ✓ PASS (exit 1) |
| **Typo'd `image:` key detected** | inject `{arch}-gattus`, scan | red (403 denied) | ✓ PASS (exit 1) |
| **Zero active archs -> exit 1** (plan: UNPROVEN) | comment out gatus's only `- amd64`, scan | `❌ gatus: declares image ... but its 'arch:' list has no active entries` | ✓ PASS (exit 1) |
| **`inconclusive` -> exit 2** (plan: UNPROVEN) | `PATH` curl shim returning 503 | `⚠️` + `🚫 ... NOT a report that any add-on is broken`; 3 attempts, 3.035s | ✓ PASS (exit 2) |
| Unparseable `version:` with `image:` present | blank the version line, scan | `❌ ... no parseable top-level 'version:' key` | ✓ PASS (exit 1) |
| Shallow clone refusal, all scan entrypoints | bare / `--addon` / `--summary-file` / `--grace-minutes 0` | exit 2 each, zero curl calls | ✓ PASS |
| Shallow clone: non-history modes unaffected | `--help` / `--self-test` / `--dry-run` / `--probe` | exit 0 each | ✓ PASS |
| Shallow refusal is age-independent | amend shallow HEAD to 2025-01-01 (age 888330 min), scan | still exit 2 | ✓ PASS |
| Shallow `--dry-run` == full-clone `--dry-run` | `diff` shallow vs working tree | **byte-identical**, 8 lines each | ✓ PASS |
| Safeguard 2 fires | `--addon authentik` | `⊘` + `⚠️ ... it checked nothing`, 0 passes | ✓ PASS (exit 0) |
| `--dry-run` makes no network call | run under logging curl shim | 8 lines, **0 curl calls** | ✓ PASS |
| `check-all` makes no network call | `make check-all` under logging curl shim | exit 0, **0 curl calls** | ✓ PASS |
| 404 is not retried | count calls on the 404 path | 2 calls (token + manifest) | ✓ PASS |
| 403 is not retried | count calls on the 403 path | 1 call (token endpoint only) | ✓ PASS |
| No token in the summary file | grep `bearer\|eyJ\|"token"\|authorization` | 0 hits | ✓ PASS |
| `make verify-images` / `-self-test` | both targets | exit 0 / exit 0 | ✓ PASS |

### Parser Verification (the three hard shapes, plus adversarial ones)

The requester flagged the parser as the place where a wrong implementation silently narrows what is
checked. All requested assertions hold, and the adversarial shapes I added also hold.

| Shape | Add-on / fixture | Expected | Actual | Status |
|-------|------------------|----------|--------|--------|
| Block form, 4-space indent | `network-tools/config.yaml:9-10` (confirmed via `cat -A`) | resolves | `· network-tools .../amd64-network_tools:0.5.0-1` | ✓ |
| Commented `# - aarch64` entries inert | `gatus` (4 commented) | ONLY `amd64` | 1 line, `amd64` only | ✓ |
| Commented entries inert | `meridian` (4 commented) | ONLY `amd64` | 1 line, `amd64` only | ✓ |
| Two active archs | `coding-assistants` | TWO lines | `amd64` + `aarch64` | ✓ |
| No `image:` key | `authentik` | nothing | 0 lines (and `⊘` skip in scan) | ✓ |
| No `image:` key | `iac-runner` | nothing | 0 lines | ✓ |
| No `image:` key, depth 3 | `tools/test-addon` | nothing | 0 lines, and discovered (so it skips visibly) | ✓ |
| Inline flow form (c) | `arch: [amd64, aarch64]` injected | 2 lines | 2 lines | ✓ |
| Inline flow, mixed quoting | `arch: ["amd64", 'aarch64']` injected | 2 lines | 2 lines | ✓ |
| Quoted block entry | `- "amd64"` injected | 1 line | 1 line | ✓ |
| Indented (non-top-level) `image:` | `options:` / `  image: ghcr.io/evil/...` injected | must NOT satisfy | 0 lines | ✓ |
| Trailing comment on `arch:` key | `arch:  # active build targets` injected | (unspecified) | 0 archs -> false violation, exit 1 | ⚠️ see Advisory 1 |

Add-on discovery finds exactly the 10 real `config.yaml` files; no stray file under `.gsd/`,
`.planning/` or `network-tools/.planning/` is reachable at `-maxdepth 3`.

### Requirements Coverage

Not applicable — quick-batch item, no `requirements:` IDs declared in the plan frontmatter and no
`REQUIREMENTS.md` mapping for stage 3.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | `TBD` / `FIXME` / `XXX` | — | **None.** Zero debt markers in either new file. |
| — | — | `TODO` / `HACK` / `PLACEHOLDER` | — | **None.** |
| — | — | "not implemented" / "coming soon" | — | **None.** |
| `internal/verify-image-availability.sh` | 927-929 | `--probe` `missing` remediation prints `make release ADDON=${ref##*/} VERSION=...`, yielding a nonsense add-on name in probe mode (e.g. `ADDON=amd64-base`) | ℹ️ Info | Cosmetic and confined to `--probe`, a developer-facing mode. The scan path passes the real add-on directory name and is correct. |
| `internal/verify-image-availability.sh` | 762-772 | Safeguard 2 prints the `✅ ... passed` aggregate immediately BEFORE the `⚠️ ... it checked nothing` warning | ℹ️ Info | Plan-specified (exit stays 0, warning glyph printed) and both lines are adjacent, so a human reads it correctly. Flagged only because a CI grep keyed on `✅` alone would read green. |

No stubs. Every code path is real and reachable — I reached all of them, including the two the plan
declared unreachable.

## On the Executor's WINDOWS.md Disposition

**Asked:** the executor did not record the two unproven branches in `.planning/WINDOWS.md`, reasoning
that the ledger blocks `/gsd-ship` and blocking a ship on risk the plan explicitly accepted with
recorded rationale would be wrong. Do I agree, and does the SUMMARY document them findably?

**I agree with the outcome, disagree with one premise, and the question is now largely moot.**

1. **Moot, because both branches are proven.** `inconclusive -> exit 2` and
   `image:`-present-with-zero-active-archs `-> exit 1` both behave exactly as specified — I
   exercised both (Behavioral Spot-Checks). There is no residual risk left to record, so the correct
   ledger state is "no entry", which is where the executor landed.

2. **The premise is wrong, and that is the substantive correction.** The plan asserts "there is no
   offline fault-injection path in scope" for the `inconclusive` branch. There is: a 12-line `curl`
   shim earlier on `PATH` returning `503`. It took under a minute and proved the retry count (3),
   the backoff (1s+2s = 3.035s), the exit code (2, not 1), and the wording ("NOT a report that any
   add-on is broken"). The zero-arch branch is equally reachable by commenting out one line in a
   throwaway clone. Calling these untestable, and writing that into two artifacts, is the kind of
   claim that hardens into fact — the next person editing `probe_manifest` will believe they cannot
   get feedback, when they can. **That is worth fixing in the artifacts even though the code is
   correct.**

3. **The ship-blocking argument was weaker than stated, though it did not matter.** `WINDOWS.md`
   already carries `open_count: 2` (entries 2 and 3, both pre-existing and unrelated to this item),
   so `/gsd-ship` is blocked regardless. And entry 4 — `kind: unrun-verify`, recorded and closed
   13 minutes later by sibling item `260909-rlj` for a near-identical "verified only under X,
   Y remains CI-verified only" situation — is direct precedent in this very ledger that such a note
   is recordable and cheap to clear. So "it would block the ship" was not the real reason to omit
   them; "they are accepted, reasoned trade-offs, not defects" was, and that reason stands on its
   own.

4. **Findability: adequate for a GSD reader, NOT for the code reader the warning names.** The
   SUMMARY has an explicit `## Accepted Unproven Branches` section and the plan has the
   `<coverage>` table — both good, both discoverable to anyone reading the item's artifacts. But
   the plan's own instruction is addressed to "anyone editing `probe_manifest`'s retry logic", and
   that person will be inside `internal/verify-image-availability.sh`. The script header documents
   the exit contract thoroughly and says nothing about any branch lacking a gate; a grep of the
   whole script for `unproven`/`untested`/`no gate` returns nothing. The durable fix is a two-line
   comment above the retry loop, not a table in `.planning/quick/`. Recorded as Advisory 3.

## Gaps Summary

**No gaps.** No must-have failed, no artifact is missing or stubbed, no key link is unwired, and no
blocker-severity anti-pattern exists. Every item the requester asked me to verify independently came
back correct, including all three of the properties whose failure would have been a real defect:

- The `denied` verdict does **not** overclaim — both the message and the remediation state that ghcr
  cannot distinguish missing from private for anonymous callers, and that both need checking.
- The registry path comes from the `image:` **VALUE** — proven by making the guard go red on a
  typo'd key, not by reading the code.
- No credential is read anywhere — the only environment variable the script touches is
  `GITHUB_ACTIONS`, and the workflow grants no `packages:` scope.

The single open item is not a gap in the code: it is that this workflow has never run. Two of the
three conjuncts of Truth 3 are proven locally; the `if: failure()` HA webhook delivery is a
GitHub-runner-only behavior that no local probe can reach. One dispatched run — one green, ideally
one red from a scratch branch — closes it.

Three advisory items are recorded in the frontmatter: one genuine (if narrow) parser fragility on a
YAML shape not present in the repo, which fails loud rather than silent; and two documentation
corrections about the "unproven" framing.

---

_Verified: 2026-09-09T20:45:00Z_
_Verifier: Claude (gsd-verifier)_
