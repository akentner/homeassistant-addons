---
quick_id: 260909-rlk
stage: 3
type: execute
autonomous: true
depends_on: []
files_modified:
  - internal/verify-image-availability.sh
  - .github/workflows/verify-image-availability.yml
  - Makefile

estimate:
  tokens: 62000
  raw_tokens: 62000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "A bare `./internal/verify-image-availability.sh` on a full clone probes all 8 declared image/arch pairs against ghcr.io and exits 0 — the invariant holds today and the guard is green on adoption."
    - "The probe's three-way classification (ok / missing:404 / denied) is proven in all three directions against a third-party control image, in its own workflow step, BEFORE the scan runs — so a green scan is only meaningful because the self-test passed."
    - "If any declared image/arch pair loses its anonymously-pullable manifest for the exact `version:` in config.yaml, the next scheduled run turns red, emits `::error::` annotations, and posts to the HA webhook."
    - "A network blip, a shallow clone, a failed self-test, or a bad argument exits 2 — never reported as a broken add-on, but still a failing job, because a guard that cannot run is not guarding."
    - "A bump pushed minutes before a scheduled run is not reported as broken: each add-on has its own grace window dated from git history, not from the cron schedule."
    - "A run that grace-skipped everything cannot look green-and-clean: a shallow clone is refused outright, and `passes==0 && skips>0` prints the warning glyph."
    - "The probe authenticates with nothing but the anonymous ghcr pull token, so it can never pass on an image that is only pullable WITH credentials — which is exactly what the Supervisor cannot do."
    - "`make check-all` stays entirely offline and deterministic; the registry probe is reachable only via `make verify-images` / `make verify-images-self-test`."
  artifacts:
    - internal/verify-image-availability.sh
    - .github/workflows/verify-image-availability.yml
    - "Makefile: `verify-images` + `verify-images-self-test` targets and their `.PHONY` entries"
  key_links:
    - "config.yaml `image:` VALUE -> registry path. Never the directory name re-slugged: a re-derived slug would silently agree with a typo'd `image:` key and mask the exact bug that breaks the pull."
    - "config.yaml `version:` -> OCI tag. This is the same string `_build-template.yml:78` reads as `CONFIG_VERSION` and pushes as the image tag (`_build-template.yml:168`), and the same string the Supervisor asks ghcr for."
    - "`--self-test` workflow step ordered BEFORE the scan step."
    - "`actions/checkout@v7` + `fetch-depth: 0` -> the grace window's `git log -S` lookup. Without full history every add-on is grace-skipped (measured: see Task 2 evidence)."
    - "`if: failure()` -> `.github/scripts/notify-ha.sh` with `NOTIFY_PAYLOAD`. That script never parses the payload and always exits 0, so it can neither reject nor mask the job failure."
    - "`check-all` recipe must NOT gain `verify-images` — a bypassed check devalues the four legitimate offline checks beside it."
---

<objective>
Turn the silent, live-breaking image-availability failure into a loud one.

INVARIANT: for every add-on whose `config.yaml` declares a top-level `image:` key, an ANONYMOUSLY-PULLABLE
manifest must exist at that image repository for the exact `version:` string in `config.yaml`, for every
ACTIVE arch in its `arch:` list.

Why it is live-breaking: when `image:` is present the HA Supervisor pulls with no credentials instead of
building locally, so a missing manifest makes the add-on uninstallable and un-updatable — and nothing in the
repo notices.

Purpose: a scheduled guard that fails loudly on a violated invariant, refuses to run rather than lie when it
cannot check reliably, and cannot report success without having checked anything.

Output: `internal/verify-image-availability.sh`, `.github/workflows/verify-image-availability.yml`, two
Makefile targets.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
</execution_context>

<context>
@./CLAUDE.md
@.planning/STATE.md

# Vocabulary, parser precedent, and the set -e traps this script must not fall into
@internal/check-version-tags.sh

# The `mapfile < <(...)` precedent (line 89) and the addon auto-discovery pattern
@internal/validate-versions.sh

# The failure-notification contract: raw JSON in, never parsed, always exit 0
@.github/scripts/notify-ha.sh

# CONFIG_VERSION (line 78) is the string pushed as the OCI tag (line 168) — the tag this guard must ask for
@.github/workflows/_build-template.yml

# Scheduled-workflow precedent: concurrency group with cancel-in-progress: false + rationale comment
@.github/workflows/auto-update.yml

# CI lints shellcheck with NO -e flags (line 94-95) and installs the LATEST actionlint (line 60-66)
@.github/workflows/lint.yml
</context>

<ground_truth>
Every fact in this block was measured against the live repo and live ghcr.io on 2026-09-09. Do not re-derive
it, and do not "fix" the guard into failing — the incident that motivated it has been remediated.

## The 8 image/arch pairs (all currently HTTP 200)

| add-on            | active archs    | image template                                                     | version    |
| ----------------- | --------------- | ------------------------------------------------------------------ | ---------- |
| coding-assistants | amd64, aarch64  | `ghcr.io/akentner/homeassistant-addons/{arch}-coding_assistants`    | 1.0.0-2    |
| gatus             | amd64           | `ghcr.io/akentner/homeassistant-addons/{arch}-gatus`                | 5.36.0-11  |
| markdown-renderer | amd64           | `ghcr.io/akentner/homeassistant-addons/{arch}-markdown_renderer`    | 1.1.0-23   |
| meridian          | amd64           | `ghcr.io/akentner/homeassistant-addons/{arch}-meridian`             | 1.68.0-0   |
| network-tools     | amd64           | `ghcr.io/akentner/homeassistant-addons/{arch}-network_tools`        | 0.5.0-1    |
| phone-logger      | amd64           | `ghcr.io/akentner/homeassistant-addons/{arch}-phone_logger`         | 1.0.6-0    |
| terraform-bridge  | amd64           | `ghcr.io/akentner/homeassistant-addons/{arch}-terraform_bridge`     | 0.3.0-0    |

`gatus` and `meridian` each carry four commented-out arch entries (`# - aarch64`, `# - armhf`, `# - armv7`,
`# - i386`) which are inert and must NOT be probed. `network-tools` indents its `arch:` list with FOUR spaces
(`network-tools/config.yaml:9-10`), not two.

## The 3 add-ons with no `image:` key — deliberate skips, never failures

`authentik`, `iac-runner`, `tools/test-addon`. They have no top-level `image:` key, so the Supervisor builds
them locally and never pulls them. The image-key rule skips all three automatically; no allowlist is needed.
(`authentik`'s and `iac-runner`'s keys are a deliberate follow-up, blocked until CI has published an image.)

## The ghcr three-state probe — all three directions measured

The 403 occurs at the TOKEN endpoint, not the manifest endpoint:

| repo path (after stripping `ghcr.io/`)      | tag                          | token | manifest | verdict                 |
| ------------------------------------------- | ---------------------------- | ----- | -------- | ----------------------- |
| `home-assistant/amd64-base`                 | `latest`                     | 200   | 200      | ok                      |
| `home-assistant/amd64-base`                 | `0.0.0-gsd-selftest-absent`  | 200   | 404      | missing:404             |
| `home-assistant/amd64-base-gsd-selftest-absent` | `latest`                 | 403   | (none)   | denied                  |

`token 200 + manifest 200` = ok. `token 200 + manifest 404` = version never published. `token 403/401` = not
anonymously pullable, and this is AMBIGUOUS between a missing package and a private package because ghcr does
not distinguish them for anonymous callers — the message must NOT claim to know which.

The token response body is `{"token":"..."}`. Extract with `grep -o '"token":"[^"]*"'` then `cut -d'"' -f4`:
field-order independent, no JSON parser needed. The pattern requires a literal `"` immediately before `token`,
so a `"access_token":"..."` field cannot false-match.

## The shallow-clone trap — measured, and worse than "finds nothing"

In a depth-1 clone the single grafted commit has no parent, so it appears to have introduced every string in
the tree. Measured in a `git clone --depth 1 file://...` of this repo:

`git log -1 --format=%ct -S"$version" -- "$addon/config.yaml"` returned the HEAD commit's committer date —
the SAME timestamp — for all 7 add-ons, which at the time of measurement was 42 minutes old. Inside the
45-minute default grace window. Every add-on was grace-skipped, so the guard would have exited 0 having
probed NOTHING.

This is worse than finding nothing: it is time-dependent. The silent pass only occurs while HEAD is younger
than the grace window — i.e. in the minutes right after a bump, the single most dangerous moment. Two
measurements of the SAME mechanism, minutes apart, disagree: at a 42-minute-old HEAD every add-on was
grace-skipped and the guard exited 0 having probed nothing; re-measured at a 63-minute-old HEAD — outside the
45-minute window — the silent pass did NOT occur. Identical input, identical code, opposite verdict, decided
only by the clock.

That is the whole argument for Safeguard 1. An intermittent failure is bad; an intermittent failure whose
failure mode is a GREEN check is the worst kind, because the green runs teach you to trust it. So the refusal
must be deterministic (exit 2 on shallow) rather than left to the `passes==0 && skips>0` warning, which fires
only in the 42-minute case. Both safeguards are mandatory; both fire on this same input.

## Confirmed local toolchain

`shellcheck`, `yamllint`, `pre-commit`, `curl`, `git`, `awk`, `make` are on PATH. `actionlint` is NOT — reach
it through `pre-commit run actionlint` (pinned v1.7.3).
</ground_truth>

<coverage>
## API Coverage — ghcr.io OCI Distribution v2 (+ GitHub Packages REST, rejected)

Full coverage by default. Opt-outs are explicit, reasoned decisions.

| capability                                  | decision  | reason |
| ------------------------------------------- | --------- | ------ |
| `GET /token?scope=repository:R:pull`        | INTEGRATE | |
| `GET /v2/{repo}/manifests/{tag}`            | INTEGRATE | |
| `GET /v2/{repo}/tags/list`                  | OPT-OUT   | the invariant is about one exact version, not tag enumeration; adds a second failure surface for no signal |
| `GET /v2/{repo}/blobs/{digest}`             | OPT-OUT   | manifest existence is the precondition the Supervisor's pull fails on; pulling layers would cost bandwidth and prove nothing extra |
| `GET /v2/` (registry base / version probe)  | OPT-OUT   | `--self-test` already proves reachability in all three directions against a real repo; a base-endpoint ping is a fourth network dependency proving less |
| `GET /v2/{repo}/referrers/{digest}`         | OPT-OUT   | not needed — no attestation/SBOM invariant in scope |
| `DELETE /v2/{repo}/manifests/{ref}`         | OPT-OUT   | explicitly out of scope: a read-only guard must never mutate the registry, and `permissions: contents: read` makes it impossible |
| GitHub Packages REST (`/user/packages/...`) | OPT-OUT   | would need a `read:packages` PAT and reports *owner-visible* package state, not anonymous pullability — the exact property the invariant is about. Using it would make the guard pass on a private package the Supervisor still cannot pull. |

## Unproven exit-contract branches — named, not silently shipped

Two branches of the exit contract ship without a gate that exercises them. Both are accepted. Both are
recorded HERE so no later reader assumes the exit contract is fully tested, and so the next person to touch
either branch knows it has no gate behind it.

| branch | why no gate exercises it | disposition |
| ------ | ------------------------ | ----------- |
| `inconclusive` -> exit 2 (transport failure / 5xx / 429, still undecided after 3 attempts) | there is no offline fault-injection path in scope; every gate makes real calls to a healthy ghcr.io, so the retry-then-give-up path is never entered | accept, UNPROVEN. The property it defends — a network blip is never reported as a broken add-on — holds by construction only. Anyone editing `probe_manifest`'s retry logic gets no gate feedback; re-read the exit contract instead. |
| `image:` present with ZERO active archs -> exit 1 | unreachable in this repo: all 7 image-declaring add-ons were measured to have >=1 active arch, and no fixture add-on is in scope | accept, UNPROVEN. Because a false positive here turns CI red for a CORRECT repo, the condition must be exactly `image:` present AND the parsed arch list empty. Never "arch list empty" alone — that is also true of the 3 no-`image:` add-ons, which must `⊘` skip and are gated. |
</coverage>

<assumption_delta_decision>
Signal: `chosen` — a derived value becomes a declared one.

The repo has two competing sources for an add-on's registry path: the declared `image:` value in
`config.yaml`, and the directory name re-slugged (`-` -> `_`, per `_build-template.yml:107`). They agree
today, which is precisely why the divergence is invisible.

**Decision: `promote`.** The declared `image:` VALUE is promoted to the single source of truth for the
registry path this guard probes; the directory-derived slug is demoted to a build-time-only concern of
`_build-template.yml`. Rationale: a re-derived slug would silently agree with a typo'd `image:` key and mask
exactly the bug that breaks the pull. The same promotion applies to `arch:` — read from `config.yaml`, not
from the per-add-on `archs:` workflow input, which item `260909-rln` (Stage 6) is about to delete anyway.

Companion invariant test (accepted, and it is Task 2's `--dry-run` fixture): the resolved image/arch/tag set
is asserted against an independently authored ground-truth list, so a future parser regression or a silent
source-of-truth swap goes red immediately.
</assumption_delta_decision>

<tasks>

<task type="tracer">
  <name>Task 1: End-to-end ghcr probe — one image/arch pair, three-way classification, proven in all three directions</name>
  <files>internal/verify-image-availability.sh</files>
  <precondition>ghcr.io is reachable anonymously from this host and `shellcheck` is on PATH (both confirmed 2026-09-09). If ghcr.io is unreachable, halt — the acceptance gates make live calls and there is no offline substitute for them.</precondition>
  <action>
Create `internal/verify-image-availability.sh`, mode 755, first line `#!/usr/bin/env bash`, then
`set -euo pipefail`.

This task builds the thin vertical slice: ONE image/arch pair resolved from a template, probed against
ghcr.io, classified into one of three states, printed with this repo's output vocabulary, and exited with the
right code. Wire that whole path end to end. Do not build the multi-add-on scan yet — that is Task 2.

Script header comment block. Explain the invariant (a top-level `image:` key means the Supervisor pulls with
no credentials, so a missing manifest makes the add-on uninstallable and un-updatable), and the three
distinguishable ghcr states with the exact measured evidence from `<ground_truth>`, including that the 403
occurs at the token endpoint and is AMBIGUOUS between missing and private.

`probe_manifest <repo_path> <tag>` — the one function this whole task exists to get right:
  - `repo_path` is the image reference with the leading `ghcr.io/` stripped.
  - Resolve a token from `https://ghcr.io/token?scope=repository:$repo_path:pull&service=ghcr.io`, capturing
    the body and the HTTP status.
  - Extract the token with `grep -o '"token":"[^"]*"'` piped to `cut -d'"' -f4`. Under `set -euo pipefail` a
    non-matching `grep` aborts the script, so this assignment — and EVERY other `grep`/`cut` pipeline
    assignment in the file — needs a trailing `|| var=""`.
  - Empty token => classify `denied`. Report both: that the package is not anonymously pullable, and that
    ghcr cannot tell an anonymous caller whether it is missing or private. Do not assert which.
  - Otherwise request `https://ghcr.io/v2/$repo_path/manifests/$tag` with `Authorization: Bearer <token>` and
    an `Accept` header listing all four of: OCI image index, docker distribution manifest list v2, OCI image
    manifest, docker distribution manifest v2. An index-only Accept header would 404 a single-arch image that
    is genuinely present.
  - manifest 200 => `ok`. manifest 404 => `missing`. Anything else (5xx, 429, curl transport failure) =>
    `inconclusive`.
  - Retries: 3 attempts with 1s/2s/4s backoff, `--connect-timeout 10 --max-time 30` per attempt, matching
    `notify-ha.sh:32-36`. Retry ONLY on transport failure, 5xx, or 429. A 404 and a 403 are answers, not
    blips — never retry them.
  - curl must not follow HTTP redirects. `notify-ha.sh:38-41` documents why in this repo: following the
    redirect fetches an auth-proxy page that returns 200, and the caller reports success while nothing real
    was reached. The same hazard applies to a hijacked or proxied registry host.
  - The bearer token must never be echoed, written to a summary, or otherwise printed. Workflow logs on a
    public repo are world-readable.
  - No credential is read from the environment anywhere in this script. The only `Authorization` header it
    ever sends is the anonymous pull token it just fetched. This is not a convenience — an authenticated
    probe would return 200 for a package that is only pullable WITH credentials, which is precisely what the
    Supervisor cannot do, and the guard would pass on a broken add-on.

`resolve_ref <template> <arch> <version>` — substitute the arch placeholder with `${template//\{arch\}/$arch}`
(parameter expansion, not an `echo | sed` pipeline: CI's shellcheck runs with NO `-e` flags and SC2001 is only
excluded for workflow files). If the template contains no arch placeholder it is a legal single-arch HA image
reference: use it verbatim and probe it once.

Validate every reference before it becomes a URL. Accept only `ghcr.io/` followed by characters from
`[A-Za-z0-9._/-]`, anchored at the start. Anything else is an uninterpretable `config.yaml` — print the
cross-mark line and set the violation exit. A `config.yaml` value flows straight into a curl URL, so a stray
`@`, `?`, `;`, or whitespace must be refused, not requested.

`--probe TEMPLATE --probe-version V [--probe-arch A]` mode: resolve one reference (`--probe-arch` defaults to
`amd64`), probe it, print the result, exit 0 for `ok`, 1 for `missing` or `denied`, 2 for `inconclusive`.

`--self-test` mode: prove the probe in ALL THREE directions against `ghcr.io/home-assistant/{arch}-base` — a
third-party control image that is public, permanent, and already a `build_from` dependency of every add-on in
this repo, so the self-test never depends on this repo's own possibly-broken packages. Assert exactly:
  - `home-assistant/amd64-base` : `latest` classifies `ok`
  - `home-assistant/amd64-base` : `0.0.0-gsd-selftest-absent` classifies `missing`
  - `home-assistant/amd64-base-gsd-selftest-absent` : `latest` classifies `denied`
Print one check-mark line per direction that passed and one cross-mark line per direction that did not. Exit 0
only if all three matched; exit 2 otherwise, because a probe that cannot classify correctly cannot be trusted
to guard anything.

`-h` / `--help` prints usage and exits 0. An unrecognised argument prints usage to stderr and exits 2.

Output vocabulary — match `internal/check-version-tags.sh` exactly:
  - `✓` pass (`check-version-tags.sh:150`)
  - `⊘` deliberate skip, always with a visible reason (`:137`)
  - `❌` violation, with a remediation block (`:159`)
  - `🚫` aggregate failure (`:178`)
  - `✅` aggregate success (`setup-hooks.sh` precedent)
  - `⚠️` inconclusive (new; same glyph as the drift warning at `:129`)
  - `·` dry-run (new)

Every status line starts with its glyph at column 1, followed by a single space — the same layout as
`check-version-tags.sh:137/150/159`. Acceptance gates count glyphs anchored at column 1, so an indented
status line reads as a missing one.

Under GitHub Actions only (`GITHUB_ACTIONS` set and non-empty), additionally emit an `::error::` line for each
violation so it becomes an annotation. Locally that would just be noise, so gate it on the variable.

Emit it from the ONE shared violation-reporting path — the same code that prints the cross-mark line — so
EVERY mode that can report a violation participates in the annotation channel: `--probe`, `--self-test` and
Task 2's full scan alike. Do not special-case it into the scan. That is not cosmetic. This item mandates TWO
failure channels: these `::error::` annotations, and Task 3's `if: failure()` notify step. The repo is green,
so no scheduled run will ever walk the violation path, which makes `--probe` the ONLY way an acceptance gate
can prove the annotation channel exists at all. A violation that prints a cross-mark but no annotation has
silently dropped one of the two mandated channels with every other gate still passing.

Shell hygiene, because CI's shellcheck has NO `-e` flags while pre-commit excludes SC1091 and SC2034 — the
stricter form is the one to satisfy:
  - Quote every expansion (SC2086).
  - Never `local x=$(cmd)` — declare on one line, assign on the next (SC2155).
  - Declare no variable you do not use; SC2034 is excluded in pre-commit but NOT in CI. (A throwaway
    prototype of this parser tripped exactly this on an unused `local`.)
  - `if cmd; then`, never testing `$?` afterwards (SC2181).
  - `${arr[*]+"${arr[*]}"}` for any array that can be empty under `set -u`, the guard
    `notify-ha.sh:81` uses.
  - Call any function that can return non-zero as `if ! fn; then ... fi`, never bare —
    `check-version-tags.sh:79-84` documents this `set -e` trap.
  - No shell tracing enabled anywhere in the file.
  - Document the hazards above freely in comments, INCLUDING trailing comments on the same line as code. The
    acceptance gates strip trailing comments as well as whole-line ones before running their negative greps,
    so a line like `curl -sS ... # never add -L: see notify-ha.sh:38-41` or `# no GITHUB_TOKEN is read here`
    explains itself without tripping the gate that forbids the real thing.
  - Parse YAML with `grep`/`sed`/`awk` only. The YAML query CLI is unusable here for two independent reasons
    documented at `check-version-tags.sh:121-126`: HA `config.yaml` files carry custom tags that require its
    unsafe mode, and the build installed on this host has no `eval` subcommand at all.
  </action>
  <verify>
    <automated>
cd "$(git rev-parse --show-toplevel)" &&
S=internal/verify-image-availability.sh &&
test -x "$S" &&
head -1 "$S" | grep -qx '#!/usr/bin/env bash' &&
grep -q 'set -euo pipefail' "$S" &&
shellcheck "$S" &&
STRIP=$(mktemp) && sed -E 's/[[:space:]]#.*$//' "$S" | grep -vE '^[[:space:]]{0,}#' > "$STRIP" &&
test "$(grep -cE '(^|[^-[:alnum:]])yq([^-[:alnum:]]|$)' "$STRIP")" -eq 0 &&
test "$(grep -c 'GITHUB_TOKEN' "$STRIP")" -eq 0 &&
test "$(grep -cE 'docker login|--password' "$STRIP")" -eq 0 &&
test "$(grep -cE '(^|[[:space:]])(-L|--location)([[:space:]]|$)' "$STRIP")" -eq 0 &&
test "$(grep -c 'set -x' "$STRIP")" -eq 0 &&
rm -f "$STRIP" &&
OUT=$("$PWD/$S" --self-test); rc=$?; printf '%s\n' "$OUT" &&
test "$rc" -eq 0 &&
test "$(printf '%s\n' "$OUT" | grep -c '^✓')" -eq 3 &&
test "$(printf '%s\n' "$OUT" | grep -c '❌')" -eq 0 &&
"$PWD/$S" --probe 'ghcr.io/home-assistant/{arch}-base' --probe-version latest --probe-arch amd64 &&
{ "$PWD/$S" --probe 'ghcr.io/home-assistant/{arch}-base' --probe-version 0.0.0-gsd-selftest-absent --probe-arch amd64; test $? -eq 1; } &&
{ "$PWD/$S" --probe 'ghcr.io/home-assistant/{arch}-base-gsd-selftest-absent' --probe-version latest --probe-arch amd64; test $? -eq 1; } &&
{ GITHUB_ACTIONS=1 "$PWD/$S" --probe 'ghcr.io/home-assistant/{arch}-base' --probe-version 0.0.0-gsd-selftest-absent --probe-arch amd64 2>&1 || true; } | grep -q '::error::' &&
test "$({ env -u GITHUB_ACTIONS "$PWD/$S" --probe 'ghcr.io/home-assistant/{arch}-base' --probe-version 0.0.0-gsd-selftest-absent --probe-arch amd64 2>&1 || true; } | grep -c '::error::')" -eq 0 &&
{ "$PWD/$S" --probe 'https://evil.example.com/x?ghcr.io/a' --probe-version 1.0.0 --probe-arch amd64; test $? -eq 1; } &&
{ "$PWD/$S" --no-such-flag >/dev/null 2>&1; test $? -eq 2; } &&
"$PWD/$S" --help >/dev/null &&
echo TASK1_GATES_PASS
    </automated>
  </verify>
  <done>
`shellcheck` with no `-e` flags is clean. `--self-test` prints exactly 3 check-mark lines, no cross-marks, and
exits 0 — proving `ok`, `missing:404` and `denied` are each detected against a third-party control image.
`--probe` exits 0 in the positive direction and 1 in BOTH negative directions. A reference that is not a
plain `ghcr.io/...` path is refused with exit 1 rather than requested. An unknown flag exits 2. The
comment-stripped script (whole-line AND trailing comments removed) contains no YAML-CLI invocation, no
environment credential, no redirect-following flag, and no shell tracing.

Both halves of the annotation channel are proven on the `--probe` violation path: with `GITHUB_ACTIONS=1` a
violation emits an `::error::` line, and with `GITHUB_ACTIONS` unset it emits none. This is the only gate on
the first of the item's two mandated failure channels, because a green repo never walks the scan's violation
path.

Shipped UNPROVEN and recorded as such in `<coverage>`: the `inconclusive` -> exit 2 branch. No gate here
exercises it; there is no offline fault-injection path in scope.
  </done>
  <reversibility rating="reversible">A new standalone script wired into nothing yet; deleting the file fully reverts it.</reversibility>
</task>

<task type="auto">
  <name>Task 2: Expand to the full scan — config.yaml parser, per-add-on grace window, and the two anti-silent-pass safeguards</name>
  <files>internal/verify-image-availability.sh</files>
  <precondition>The working tree is a NON-shallow clone: `git rev-parse --is-shallow-repository` must print `false` (confirmed 2026-09-09). In a shallow clone the full-scan and grace-window gates below cannot be evaluated at all — that is the trap this task implements a refusal for.</precondition>
  <action>
Expand Task 1's proven slice into the repo-wide scan. Task 1's `probe_manifest` is unchanged; everything here
feeds it.

Add-on discovery: find every `config.yaml` at depth 2 or 3 from the repo root, excluding the live HA `config/`
directory. Depth 3 is required for `tools/test-addon/config.yaml` — the same reasoning
`validate-versions.sh:83-88` records. Sort the results so output order is stable.

Never pipe into a `while` loop: the counters would live in a subshell and be silently lost. Feed every loop
from process substitution or `mapfile`, as `validate-versions.sh:89` and `check-version-tags.sh:175` do.

`config.yaml` parsing — `grep`/`sed`/`awk` only, for the reasons in Task 1:
  - `image:` — anchored at column 1 and requiring a non-blank value, so an indented sub-key, a commented
    `# image:` line, or an empty value cannot satisfy it. `image` is a top-level key in the HA add-on
    manifest, so the anchor is exact (`check-version-tags.sh:121-127`). No `image:` key => `⊘` skip with the
    reason that the Supervisor builds this add-on locally and never pulls it. This is what makes `authentik`,
    `iac-runner` and `tools/test-addon` skip automatically, with no allowlist to go stale.
  - Derive the registry path from the `image:` VALUE. Never re-slug the directory name: that would silently
    agree with a typo'd `image:` key and mask exactly the bug that breaks the pull.
  - `version:` — anchored at column 1, tolerant of quoted and unquoted values, `head -1`. This is the same
    string `_build-template.yml:78` reads as `CONFIG_VERSION` and pushes as the OCI tag at
    `_build-template.yml:168`, subpatch suffix included.
  - `arch:` — the parser must handle THREE shapes:
      (a) Block form with 2-space indent (7 add-ons).
      (b) Block form with 4-space indent (`network-tools/config.yaml:9-10`).
      (c) Inline flow form `arch: [amd64, aarch64]` — split on comma, trim whitespace and quotes.
    Implement the block form in `awk`: a line matching `^arch:` with only optional whitespace after the colon
    opens the block; a line matching leading-whitespace + `-` + a bare token closes as an entry; a line
    starting at column 1 with a character that is neither whitespace nor `#` ends the block. An indented
    commented entry never matches the entry pattern because the character after the indent is `#`, not `-` —
    which is why `gatus` and `meridian` must yield ONLY `amd64` despite their four commented-out arch lines.
  - `image:` present but no parseable `version:` => uninterpretable `config.yaml`, exit 1.
  - `image:` present with ZERO active archs => violation, exit 1. The add-on declares a pulled image that no
    host arch can ever pull, so its store entry is unusable. Unreachable today; keep it as a real gate rather
    than a silent skip.

Per-add-on grace window — and this is the central design point. The false-alarm defence is NOT the cron
schedule, because humans push bumps at arbitrary times. It is a window dated from history:
`git log -1 --format=%ct -S"$version" -- "$addon/config.yaml"` gives the commit that introduced the current
version string. If that is younger than the window, `⊘` skip with a visible reason naming both the measured
age and the window, and count it as a grace skip. Default 45 minutes: the measured worst-case build is 13m28s
for aarch64 under QEMU, plus queue time. Override with `--grace-minutes N`.

`--grace-minutes 0` disables the window entirely: no add-on is ever grace-skipped, whatever its measured age.
The acceptance gates use it wherever they assert a pass COUNT, because the default window makes such a gate
time-coupled — a version string introduced under 45 minutes before the gate runs turns a pass into a skip and
the count fails. That is not hypothetical here: sibling items in this batch commit to this repo while these
gates may be running.

SAFEGUARD 1 — refuse to run on a shallow clone, on the paths that actually consult git history. If
`git rev-parse --is-shallow-repository` prints `true`, print the aggregate-failure glyph with an explanation
and exit 2, before any config parsing or network call on that path.

Scope the refusal precisely — it belongs where the grace lookup lives, NOT at the top of `main`. It applies to
the grace-window paths: the bare scan, `--addon NAME`, `--summary-file PATH`, `--grace-minutes N`. It does NOT
apply to `--help`, `--dry-run`, `--self-test` or `--probe`, which keep their normal exit codes in a shallow
clone because none of them reads `git log -S`: `--help` prints usage, `--dry-run` resolves from the working
tree alone, and `--self-test` / `--probe` talk only to the registry. A `--help` that exited 2 in a shallow
checkout would be plainly wrong, and Task 1's gates depend on `--help` and `--self-test` exiting 0. Record
the measured mechanism in a comment: in a depth-1 clone the single grafted commit has no parent, so it appears
to have introduced every string in the tree, and the `git log -S` lookup returns the HEAD commit's date for
EVERY add-on. Measured in this repo: all 7 add-ons reported the same 42-minute age, inside the default window,
so every one was grace-skipped and the guard would have exited 0 having probed nothing. Note that this is
time-dependent — it only bites while HEAD is younger than the window, i.e. in the minutes right after a bump,
the most dangerous moment — which is why the refusal is deterministic instead of relying on Safeguard 2. This
is the guard's own version of the bug it exists to catch.

SAFEGUARD 2 — warn when `passes == 0 && skips > 0`, where skips counts both grace skips and no-image skips.
Print the warning glyph and state plainly that the guard reported success without checking any image. Exit
code stays 0: the invariant is not violated, but the run must not look green-and-clean.

`--dry-run`: resolve and print one middle-dot line per add-on/arch pair, with no network call at all, no git
history read, and NO grace window applied — every declared image/arch pair is printed regardless of how
recently its version string landed. That is what keeps the 8-line fixture reproducible immediately after a
version bump, and it is why `--dry-run` is exempt from Safeguard 1's shallow-clone refusal. This is
the parser regression check. Format each line as the glyph at column 1, a space, the add-on directory name, a
space, then the fully resolved reference with its tag. Print NOTHING else in this mode — no header line, no
aggregate line, no skip lines — because the fixture gate asserts the total line count is exactly 8. Put that
expected 8-line output in the script header as a documented fixture.

`--addon NAME` restricts the scan to one add-on directory. An unknown name exits 2 (bad argument), not 0 —
a typo'd name must not look like a clean run.

`--summary-file PATH` writes a markdown summary (a heading, one table row per probed pair with its verdict,
then the aggregate line) suitable for `$GITHUB_STEP_SUMMARY`. The bearer token must never appear in it.

Aggregate output and the exit contract:
  - 0 = invariant holds. Print `✅` with the count of pairs verified anonymously pullable.
  - 1 = at least one violation, or an uninterpretable `config.yaml`. Print `🚫`.
  - 2 = the guard could not run reliably: shallow clone, ghcr unreachable after retries, self-test failed, or
    bad arguments. Print `🚫` with distinct wording. A network blip is never reported as a broken add-on, but
    it still fails — a guard that cannot run is not guarding.

Every violation gets a remediation block in the style of `check-version-tags.sh:164-173`: name the exact
missing reference, and give the concrete next step (re-run the add-on's build workflow, or push the
`<addon>/v<version>` tag that triggers it). For a `denied` verdict the remediation must state that ghcr does
not distinguish missing from private for anonymous callers and that BOTH the package's existence and its
visibility need checking.

Keep the whole file clean under `shellcheck` with no `-e` flags — the same hygiene list as Task 1.
  </action>
  <verify>
    <automated>
cd "$(git rev-parse --show-toplevel)" &&
S="$PWD/internal/verify-image-availability.sh" &&
shellcheck "$S" &&
test "$(git rev-parse --is-shallow-repository)" = false &&
DRY=$("$S" --dry-run) && printf '%s\n' "$DRY" &&
test "$(printf '%s\n' "$DRY" | wc -l)" -eq 8 &&
printf '%s\n' "$DRY" | sed -E 's/.*(ghcr\.io[^:[:space:]]+):.*/\1/' | sort > /tmp/rlk_got.txt &&
printf '%s\n' \
 'ghcr.io/akentner/homeassistant-addons/aarch64-coding_assistants' \
 'ghcr.io/akentner/homeassistant-addons/amd64-coding_assistants' \
 'ghcr.io/akentner/homeassistant-addons/amd64-gatus' \
 'ghcr.io/akentner/homeassistant-addons/amd64-markdown_renderer' \
 'ghcr.io/akentner/homeassistant-addons/amd64-meridian' \
 'ghcr.io/akentner/homeassistant-addons/amd64-network_tools' \
 'ghcr.io/akentner/homeassistant-addons/amd64-phone_logger' \
 'ghcr.io/akentner/homeassistant-addons/amd64-terraform_bridge' | sort > /tmp/rlk_want.txt &&
diff -u /tmp/rlk_want.txt /tmp/rlk_got.txt &&
test "$(printf '%s\n' "$DRY" | grep -cE 'authentik|iac-runner|test-addon')" -eq 0 &&
for a in coding-assistants gatus markdown-renderer meridian network-tools phone-logger terraform-bridge; do
  v=$(grep -E '^version:' "$a/config.yaml" | head -1 | sed -E 's/^version:[[:space:]]*"?([^"]+)"?.*/\1/');
  s="-$(printf '%s' "$a" | tr '-' '_'):$v";
  tot=$(printf '%s\n' "$DRY" | awk -v a="$a" '$2==a' | wc -l);
  hit=$(printf '%s\n' "$DRY" | awk -v a="$a" -v s="$s" '$2==a && substr($NF,length($NF)-length(s)+1)==s' | wc -l);
  test "$tot" -ge 1 && test "$hit" -eq "$tot" || { echo "TAG_MISMATCH $a want suffix $s"; exit 1; };
done &&
SC=$(mktemp -d) && git clone --quiet --depth 1 "file://$PWD" "$SC/repo" &&
test "$(git -C "$SC/repo" rev-parse --is-shallow-repository)" = true &&
cp internal/verify-image-availability.sh "$SC/repo/internal/" &&
{ ( cd "$SC/repo" && ./internal/verify-image-availability.sh >/tmp/rlk_shallow.log 2>&1 ); test $? -eq 2; } &&
cat /tmp/rlk_shallow.log &&
{ ( cd "$SC/repo" && ./internal/verify-image-availability.sh --help >/dev/null 2>&1 ); test $? -eq 0; } &&
{ ( cd "$SC/repo" && ./internal/verify-image-availability.sh --self-test >/dev/null 2>&1 ); test $? -eq 0; } &&
{ ( cd "$SC/repo" && ./internal/verify-image-availability.sh --dry-run >/tmp/rlk_shallow_dry.log 2>&1 ); test $? -eq 0; } &&
test "$(wc -l < /tmp/rlk_shallow_dry.log)" -eq "$(printf '%s\n' "$DRY" | wc -l)" &&
rm -rf "$SC" &&
W=$("$S" --addon authentik); test $? -eq 0 && printf '%s\n' "$W" &&
test "$(printf '%s\n' "$W" | grep -c '⚠')" -ge 1 &&
test "$(printf '%s\n' "$W" | grep -c '⊘')" -ge 1 &&
test "$(printf '%s\n' "$W" | grep -c '^✓')" -eq 0 &&
{ "$S" --addon no-such-addon >/dev/null 2>&1; test $? -eq 2; } &&
FULL=$("$S" --grace-minutes 0 --summary-file /tmp/rlk_summary.md); rc=$?; printf '%s\n' "$FULL" &&
test "$rc" -eq 0 &&
test "$(printf '%s\n' "$FULL" | grep -c '^✓')" -eq 8 &&
test "$(printf '%s\n' "$FULL" | grep -c '❌')" -eq 0 &&
test "$(printf '%s\n' "$FULL" | grep -c '⚠')" -eq 0 &&
test "$(printf '%s\n' "$FULL" | grep -c '✅')" -eq 1 &&
test -s /tmp/rlk_summary.md &&
G=$("$S" --grace-minutes 999999 --addon gatus); test $? -eq 0 && printf '%s\n' "$G" &&
test "$(printf '%s\n' "$G" | grep -c '⊘')" -eq 1 &&
test "$(printf '%s\n' "$G" | grep -c '^✓')" -eq 0 &&
echo TASK2_GATES_PASS
    </automated>
  </verify>
  <done>
`--dry-run` prints exactly 8 lines, no network. The version-free reference set diffs clean against the
independently authored ground truth: `gatus` and `meridian` yield ONLY `amd64` (their commented arch lines are
inert), `network-tools` resolves despite its 4-space indent, `coding-assistants` yields TWO lines, and
`authentik`, `iac-runner` and `tools/test-addon` yield nothing. Pairing is gated per line, not per output:
EVERY dry-run line for a given add-on ends with that add-on's own `-<slug>:<version>` suffix, compared as a
literal string, so a parser bug that attaches one add-on's version or image path to another's line goes red
even though both strings are still present somewhere in the output.

A shallow clone exits 2 before probing on the scan path, while `--help`, `--self-test` and `--dry-run` still
exit 0 there — the refusal is scoped to the paths that read `git log -S`. The shallow `--dry-run` yields the
SAME line count as the full-clone one, which is the direct proof that it consults no history at all (asserted
against the full-clone count rather than a hardcoded 8, so the gate does not also depend on committed state). `--addon authentik` exits 0 with the warning glyph and zero passes. An unknown
`--addon` exits 2. A full scan with `--grace-minutes 0` exits 0 with 8 check-marks, no cross-marks, no
warning, one aggregate-success line, and a non-empty summary file — the pass count is asserted with the
window disabled so it cannot flip to a skip because of when a version bump happened to land. A
999999-minute window turns a pass into a visible grace skip, proving the window is load-bearing rather than
decorative.

Shipped UNPROVEN and recorded as such in `<coverage>`: the `image:`-present-with-zero-active-archs -> exit 1
branch. No add-on in this repo can reach it, so it goes out untested on a path that returns exit 1.
  </done>
  <reversibility rating="reversible">Still a standalone script with no CI or Makefile wiring.</reversibility>
</task>

<task type="auto">
  <name>Task 3: Wire it into CI — scheduled workflow with self-test-before-scan, and Makefile targets kept out of check-all</name>
  <files>.github/workflows/verify-image-availability.yml, Makefile</files>
  <precondition>`pre-commit` is on PATH and its hook environments are installed (`actionlint` is NOT available standalone on this host — `pre-commit run actionlint` supplies the pinned v1.7.3). Tasks 1 and 2 are complete: this task's gates invoke the finished script.</precondition>
  <action>
Create `.github/workflows/verify-image-availability.yml`.

Triggers: `schedule` with cron `30 2,8,14,20 * * *`, plus `workflow_dispatch` with a `grace-minutes` input
(string, not required, default `45`). Comment why the schedule lands at `:30`: top-of-hour crons on GitHub
routinely slip 5-15 minutes, and every other scheduled workflow in this repo already sits on the hour
(`auto-update.yml` at 06:00, `base-image-update.yml` at 07:00).

`permissions:` grants read access to repository contents and nothing else. In particular grant no
registry-scope permission — the probe must be anonymous, because an authenticated probe would return 200 for
an image that is only pullable WITH credentials, which is exactly what the Supervisor cannot do. State that
in a comment; it is a correctness property, not a least-privilege nicety.

`timeout-minutes: 10`. `runs-on: ubuntu-latest` — `.actionlint.yml` allows no other label.

A `concurrency:` group WITHOUT cancellation: set `cancel-in-progress: false` explicitly, following
`auto-update.yml:22-23`. A cancelled run renders grey, and grey is precisely the state nobody notices.
Comment that rationale inline.

Steps, in this order:
  1. `actions/checkout@v7` with `fetch-depth: 0`. This is MANDATORY, not an optimisation: the grace window
     reads `git log -S` over history, and on the default shallow checkout every add-on reports the HEAD
     commit's date, gets grace-skipped, and the guard passes green having probed nothing (see the measured
     evidence in the script header). The script refuses to run in that state, so a shallow checkout turns the
     job red rather than falsely green — but the correct fix is full history.
  2. A step named exactly `Self-test the ghcr probe` running the script with `--self-test`. This is its OWN
     step and it runs BEFORE the scan, so a green scan is only meaningful because the self-test passed.
  3. A step named exactly `Scan all add-ons` running the script with the resolved grace-minutes value and
     `--summary-file "$GITHUB_STEP_SUMMARY"`. Resolve the value from the dispatch input with a shell default
     so the scheduled path (where the input is empty) still gets 45.
  4. An `if: failure()` step calling `./.github/scripts/notify-ha.sh` with `HA_BASE_URL`, `HA_WEBHOOK_ID`,
     `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET` from secrets, plus `NOTIFY_EVENT`,
     `NOTIFY_DELIVERY_ID` (run id + run number, as `_build-template.yml:179` does), and a `NOTIFY_PAYLOAD`
     JSON object carrying at least the repository, the workflow run URL, the job conclusion, and the trigger.
     That script never parses the payload and always exits 0 (`notify-ha.sh:35-36`), so it can neither reject
     nor mask the job failure. Comment that this is the second of two failure channels — the first is the
     `::error::` annotations the script emits plus GitHub's automatic scheduled-failure email to the workflow
     author. Both channels are mandated. This step is the gate on the notify channel; the annotation channel
     is gated in Task 1 on the `--probe` violation path, since a green repo never walks the scan's.

Use no repository or environment configuration variables anywhere: `.actionlint.yml` declares an EMPTY
`config-variables:` list, so any such reference is flagged. Recording THAT rationale in a comment is safe:
the acceptance gate strips whole-line and trailing YAML comments before asserting, and it asserts on the
`${{ vars. }}` expression form rather than the bare `vars.` token — so naming the thing you are avoiding
does not count as using it. The same holds for the `cancel-in-progress: true` and `packages:` gates. Keep to constructs already present in this repo's
existing workflows — `actionlint` runs twice against this file, pinned to v1.7.3 by pre-commit and at the
LATEST release by `lint.yml:61-66`, and both must pass. YAML must be 2-space indented with sequences indented,
lines under 120 characters, LF endings, no tabs, and no trailing whitespace (`.yamllint.yml`).

Then edit `Makefile`:
  - Append `verify-images` and `verify-images-self-test` to the single `.PHONY` line at `Makefile:4`.
  - Add both targets immediately after the `validate-versions` target (`Makefile:94-96`), matching its shape:
    a `## ` help comment on the target line, an `@echo` banner, then the script invocation. Recipes use TABS.
  - Do NOT add either target to `check-all` (`Makefile:250`) — leave that line byte-identical. Every current
    `check-all` member is offline, deterministic, and fails only for something in your own working tree. A
    registry probe breaks all three properties and would turn `check-all` red because of somebody else's
    failed build. A bypassed check is worse than no check, because it also devalues the four legitimate ones
    beside it. Record that reasoning as a comment above the new targets.

Do not touch `.github/RELEASE.md` or `docs/AUTO_UPDATE_GUIDE.md` — documentation for this guard belongs to
batch item `260909-rlm` (Stage 5), which owns those files.
  </action>
  <verify>
    <automated>
cd "$(git rev-parse --show-toplevel)" &&
W=.github/workflows/verify-image-availability.yml &&
test -f "$W" &&
yamllint -c .yamllint.yml "$W" &&
pre-commit run actionlint --files "$W" &&
pre-commit run yamllint --files "$W" &&
WS=$(mktemp) && sed -E 's/[[:space:]]#.*$//' "$W" | grep -vE '^[[:space:]]{0,}#' > "$WS" &&
test "$(grep -c 'cron: "30 2,8,14,20' "$WS")" -ge 1 &&
test "$(grep -c 'fetch-depth: 0' "$WS")" -ge 1 &&
test "$(grep -c 'actions/checkout@v7' "$WS")" -ge 1 &&
test "$(grep -c 'timeout-minutes: 10' "$WS")" -ge 1 &&
test "$(grep -c 'workflow_dispatch' "$WS")" -ge 1 &&
test "$(grep -c 'contents: read' "$WS")" -ge 1 &&
test "$(grep -c 'cancel-in-progress: false' "$WS")" -ge 1 &&
test "$(grep -c 'cancel-in-progress: true' "$WS")" -eq 0 &&
test "$(grep -cE '^[[:space:]]{0,}packages:' "$WS")" -eq 0 &&
test "$(grep -cE '\$\{\{[[:space:]]{0,}vars\.' "$WS")" -eq 0 &&
test "$(grep -c 'notify-ha.sh' "$WS")" -ge 1 &&
test "$(grep -c 'if: failure()' "$WS")" -ge 1 &&
test "$(grep -cP '\t' "$W")" -eq 0 &&
A=$(grep -n 'Self-test the ghcr probe' "$WS" | head -1 | cut -d: -f1) &&
B=$(grep -n 'Scan all add-ons' "$WS" | head -1 | cut -d: -f1) &&
test -n "$A" && test -n "$B" && test "$A" -lt "$B" &&
rm -f "$WS" &&
test "$(grep -c '^verify-images:' Makefile)" -eq 1 &&
test "$(grep -c '^verify-images-self-test:' Makefile)" -eq 1 &&
grep -E '^\.PHONY:' Makefile | grep -qE '(^|[[:space:]])verify-images-self-test([[:space:]]|$)' &&
grep -E '^\.PHONY:' Makefile | grep -qE '(^|[[:space:]])verify-images([[:space:]]|$)' &&
test "$(grep -E '^check-all:' Makefile | grep -c 'verify-images')" -eq 0 &&
git diff --unified=0 -- Makefile | grep -E '^[-+]check-all:' | wc -l | grep -qx 0 &&
make verify-images-self-test &&
make verify-images &&
shellcheck internal/verify-image-availability.sh &&
pre-commit run --files internal/verify-image-availability.sh "$W" Makefile &&
echo TASK3_GATES_PASS
    </automated>
  </verify>
  <done>
The workflow lints clean under both `yamllint -c .yamllint.yml` and the pinned `actionlint`, uses no
configuration variables and no tabs, and carries the `:30` four-times-daily cron, `workflow_dispatch`,
`contents: read` with no registry-scope permission, `timeout-minutes: 10`, a concurrency group that does not
cancel, `actions/checkout@v7` with `fetch-depth: 0`, and an `if: failure()` notify step. The
`Self-test the ghcr probe` step appears strictly before the `Scan all add-ons` step. Both Makefile targets
exist, both are on `.PHONY`, the `check-all` line is untouched in the diff and contains no reference to them,
and `make verify-images` plus `make verify-images-self-test` both exit 0 against the live registry.
`pre-commit run --files` is clean across all three touched files.
  </done>
  <reversibility rating="reversible">Deleting the workflow file and reverting the two Makefile hunks fully removes the guard; nothing else depends on it.</reversibility>
</task>

</tasks>

<threat_model>
ASVS level 1, blocking threshold: high.

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| repo working tree -> shell parser | `config.yaml` `image:` and `version:` values, writable by anyone with repo write access, become parts of an outbound URL |
| GitHub Actions runner -> ghcr.io | untrusted remote HTTP responses (status codes, token JSON) cross here and decide the job's verdict |
| workflow job -> HA webhook | `HA_BASE_URL` / `HA_WEBHOOK_ID` / `CF_ACCESS_*` secrets cross out of the job on failure |
| workflow job -> public Actions log | everything the script prints is world-readable on a public repo |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-rlk-01 | Tampering | `resolve_ref` / `probe_manifest` URL construction | medium | mitigate | Validate every resolved reference against an anchored `ghcr.io/[A-Za-z0-9._/-]+` allowlist and refuse (exit 1) otherwise, so a stray `@`, `?`, `;` or whitespace in a `config.yaml` value cannot redirect the probe to another host. curl never follows redirects (the `notify-ha.sh:38-41` lesson). Every expansion double-quoted. Gated in Task 1 by the `https://evil.example.com/...` probe asserting exit 1. |
| T-rlk-02 | Information Disclosure | ghcr bearer token vs. public Actions log | high | mitigate | The token is never echoed, never written to the summary file, and no shell tracing is enabled anywhere (Task 1 gate greps the comment-stripped file for tracing). Residual: the token is briefly visible in the process argv on the runner — accepted at L1, since it is an anonymous, pull-only, short-lived token that grants nothing the guard did not already have anonymously. |
| T-rlk-03 | Spoofing | authenticated probe masking a private package | high | mitigate | No credential is read from the environment and no registry-scope permission is granted in the workflow. An authenticated probe would return 200 for an image only pullable WITH credentials — precisely what the Supervisor cannot do — and the guard would pass on a broken add-on. Gated in Task 1 by the comment-stripped negative greps, and in Task 3 by asserting no registry permission in the workflow. |
| T-rlk-04 | Repudiation | a green run that checked nothing | high | mitigate | Two safeguards, both mandatory and both provably fired by the same measured input: deterministic exit 2 on a shallow clone (before any parsing or network call), and the warning glyph when `passes==0 && skips>0`. Plus the self-test as its own workflow step BEFORE the scan, so a green scan is only meaningful because the classifier was just proven in all three directions. Gated in Task 2 (shallow clone exits 2; `--addon authentik` warns with zero passes) and Task 3 (step ordering by line number). |
| T-rlk-05 | Denial of Service | ghcr rate limiting / transient 5xx reported as a broken add-on | medium | mitigate | Three attempts with 1s/2s/4s backoff and per-attempt `--connect-timeout 10 --max-time 30`; retry only on transport failure, 5xx or 429; a 404 and a 403 are answers and are never retried. Anything still undecided classifies inconclusive and exits 2, so a network blip is never reported as a broken add-on — but it still fails, because a guard that cannot run is not guarding. |
| T-rlk-06 | Elevation of Privilege | registry mutation from CI | low | mitigate | The registry write surface is opted out of entirely (see `<coverage>`: no DELETE, no push), and `permissions: contents: read` makes it unreachable even if code were added. |
| T-rlk-07 | Information Disclosure | HA webhook secrets in the `if: failure()` step | low | accept | Boundary already owned by `.github/scripts/notify-ha.sh`, whose documented contract (never parses the payload, always exits 0, never follows redirects) is unchanged by this item. The `NOTIFY_PAYLOAD` carries only repository, run URL, conclusion and trigger — no add-on credentials, no registry token. |
| T-rlk-SC | Tampering | npm/pip/cargo installs | low | accept | No package-manager install anywhere in scope: the script uses only `bash`, `curl`, `git`, `grep`/`sed`/`awk`, all preinstalled on `ubuntu-latest`. The single third-party action is `actions/checkout@v7`, already used by every workflow in this repo. No `[ASSUMED]`/`[SUS]` package exists, so no legitimacy checkpoint is required. |
</threat_model>

<verification>
Cross-task checks, run once all three tasks are done:

1. `shellcheck internal/verify-image-availability.sh` — no `-e` flags, clean. CI's form
   (`lint.yml:94-95`) is stricter than pre-commit's; satisfy the stricter one.
2. `./internal/verify-image-availability.sh --self-test` — 3 check-marks, exit 0.
3. `./internal/verify-image-availability.sh --dry-run | wc -l` — exactly 8.
4. `./internal/verify-image-availability.sh --grace-minutes 0` — 8 check-marks, exit 0. The window is
   disabled so the count is reproducible no matter how recently a version bump landed. The invariant holds
   today; a red result here means the guard is wrong, not the repo.
5. `make verify-images && make verify-images-self-test` — both exit 0.
6. `make check-all` — still exits 0 and makes no network call to ghcr.io.
7. `pre-commit run --all-files` — clean across all three touched files.

Then commit as one atomic commit. Suggested message:
`feat(quick): add ghcr image-availability guard (script + scheduled workflow + make targets)`
</verification>

<success_criteria>
- The invariant is enforced for all 8 declared image/arch pairs and only those 8; `authentik`, `iac-runner`
  and `tools/test-addon` skip visibly rather than fail, with no allowlist that can go stale.
- Detection is proven, not assumed: because the repo is green today, the `--probe` negative directions and the
  three-direction `--self-test` against a third-party control image are the load-bearing evidence, and both
  are gated.
- The guard cannot report success without having checked something: shallow clone exits 2 deterministically,
  and `passes==0 && skips>0` warns.
- The guard cannot report a broken add-on for a network blip: inconclusive is exit 2, distinct from exit 1.
- The registry path comes from the `image:` VALUE, never from a re-slugged directory name.
- `make check-all` remains offline and deterministic.
</success_criteria>

<output>
No SUMMARY file — quick-batch item. Report back with the commit SHA, the actual `--dry-run` output, the
`--self-test` output, and the full-scan output.
</output>
