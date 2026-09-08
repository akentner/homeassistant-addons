---
quick_id: "260908-pfp"
slug: "add-a-build-workflow-for-the-iac-runner-add-on-there-is-curr"
description:
  "Add .github/workflows/build-iac-runner.yml modelled on build-terraform-bridge.yml, delegating to _build-template.yml
  — no build workflow for iac-runner exists, so the pushed tag iac-runner/v0.2.1 triggered nothing and no image was ever
  published"
date: "2026-09-08"
status: planned
type: execute
autonomous: true
depends_on: []
files_modified:
  - .github/workflows/build-iac-runner.yml
  - .github/RELEASE.md

must_haves:
  truths:
    - "A push to `main` touching `iac-runner/**` dispatches `_build-template.yml` with the iac-runner inputs — asserted
      structurally against the parsed YAML, never by triggering a real run"
    - "A push of an `iac-runner/v*` tag dispatches the same build via a LIVE `on.push.tags` glob — not a commented-out
      one (the structural verifier's negative control on `build-authentik.yml` proves it distinguishes the two, which a
      grep cannot)"
    - "`pre-commit run actionlint --all-files` exits 0 (baseline was verified green at plan time, so any failure is
      attributable to this change)"
    - "The caller job carries NO `timeout-minutes` — GitHub forbids that key on a `jobs.<id>.uses` reusable-workflow
      call. The Phase-8 explicit-timeout rule is satisfied by `_build-template.yml`'s `timeout-minutes: 45`, which every
      existing caller relies on and none overrides"
    - "The published image name is produced solely by the template's slug step
      (`ghcr.io/akentner/homeassistant-addons/amd64-iac_runner:<config.yaml version>`) — the caller re-implements no
      naming logic"
    - "`.github/RELEASE.md`'s tag-trigger table has one row per `build-*.yml` file and each row agrees with that file's
      real `on.push.tags` key, including the pre-existing omission of `terraform-bridge`"
    - "No git tag is pushed and no real build is triggered as part of verification — publishing an image is explicitly
      out of scope for this plan"
  artifacts:
    - path: ".github/workflows/build-iac-runner.yml"
      provides: "per-addon build caller delegating to the shared reusable template, with a live tag trigger"
      contains: "uses: ./.github/workflows/_build-template.yml"
    - path: ".github/RELEASE.md"
      provides: "tag-trigger status table updated with iac-runner (active) and the missing terraform-bridge row"
      contains: "| iac-runner"
  key_links:
    - from: ".github/workflows/build-iac-runner.yml (jobs.build.uses)"
      to: ".github/workflows/_build-template.yml"
      via: "workflow_call — the caller contributes only inputs + secrets; all QEMU/Buildx/GHCR/notify logic stays put"
      pattern: "\\./\\.github/workflows/_build-template\\.yml"
    - from: ".github/workflows/build-iac-runner.yml (with.archs)"
      to: "iac-runner/config.yaml (arch) + iac-runner/build.yaml (build_from.amd64)"
      via:
        "matrix arch fan-out — an arch in `archs` with no matching `build_from.<arch>` makes the template's BUILD_FROM
        resolve empty and hard-fail its own guard"
      pattern: '\["amd64"\]'
    - from: ".github/workflows/build-iac-runner.yml (with.addon-name)"
      to: "the iac-runner/ directory name"
      via:
        "the template uses addon-name for build.yaml/config.yaml lookup AND for the underscore image slug (iac-runner ->
        iac_runner)"
      pattern: "addon-name: iac-runner"
    - from: ".github/workflows/build-iac-runner.yml (secrets:)"
      to: ".github/scripts/notify-ha.sh (via the template)"
      via: "HA_BASE_URL / HA_WEBHOOK_ID / CF_ACCESS_CLIENT_ID / CF_ACCESS_CLIENT_SECRET pass-through"
      pattern: "HA_WEBHOOK_ID"
---

<objective>
Create `.github/workflows/build-iac-runner.yml`. `iac-runner` is the only add-on directory in the repo carrying a
`config.yaml` + `build.yaml` + `Dockerfile` with no matching `build-<addon>.yml` caller, which is why the
`iac-runner/v0.2.1` tag (present on origin at `455920f`) fired nothing and no image was ever published.

Purpose: give iac-runner the same automated build path every other add-on in the repo already has, so a commit under
`iac-runner/**` or an `iac-runner/v*` tag publishes `ghcr.io/akentner/homeassistant-addons/amd64-iac_runner`.

Output: one new workflow caller file, structurally identical to `build-terraform-bridge.yml`, plus a corrective edit to
the `.github/RELEASE.md` tag-trigger documentation.

Observation for the batch merge, not a scope change: `iac-runner/config.yaml` has no `image:` key, so the HA Supervisor
builds this add-on locally and never pulls the ghcr image — which is the premise of sibling item `260908-pfq`.
`terraform-bridge` is exact precedent for that combination (no `image:` key, live tag trigger, published ghcr image), so
adding the workflow is consistent with existing repo practice. A reviewer may still ask whether iac-runner should gain
an `image:` key; that question belongs to `260908-pfq`, not here. </objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
@.github/workflows/build-terraform-bridge.yml
@.github/workflows/_build-template.yml
@.actionlint.yml
@iac-runner/config.yaml
@iac-runner/build.yaml
@.github/RELEASE.md

Everything below was verified against the real repo during planning, not assumed:

- **`timeout-minutes` is NOT legal on the caller job — proven, not recalled.** The request asked for "explicit
  `timeout-minutes` on every job (the Phase-8 pattern)". That is impossible in this file. Every existing `build-*.yml`
  caller uses `jobs.build.uses:` (reusable-workflow call) and none carries `timeout-minutes`. The proposed file was run
  through the repo's own pinned actionlint (v1.7.3, via pre-commit) both without and with the key; with it, actionlint
  fails:

  ```text
  .github/workflows/build-iac-runner.yml:15:5: when a reusable workflow is called with "uses", "timeout-minutes" is
  not available. only following keys are allowed: "name", "uses", "with", "secrets", "needs", "if", and "permissions"
  in job "build" [syntax-check]
  ```

  Note the allowed-key list is narrower than GitHub's docs suggest — no `strategy`, no `concurrency` in this actionlint
  version. The explicit-timeout convention therefore lives one level down in `_build-template.yml`
  (`timeout-minutes: 45`, with a comment justifying it against measured QEMU wall time), which is where the Phase-8 rule
  is already satisfied for every add-on. The task action forbids the key and the verifier asserts its absence so a
  future well-meaning edit cannot reintroduce it.

- **The local `yq` is the Python jq-wrapper (`kislyuk/yq`), not Go `mikefarah/yq`.** `yq eval '...' file` fails locally
  with an argparse error. The workflows themselves use Go-`yq` syntax because GitHub runners ship it. All local
  verification in this plan therefore uses `python3` + PyYAML (both confirmed present) instead of `yq`.
- **In YAML 1.1 the workflow's `on:` key parses as boolean `True`.** `yaml.safe_load()` on a workflow returns top-level
  keys `['name', True, 'jobs']`. The verifiers index `wf[True]`; indexing `wf['on']` would raise `KeyError` and produce
  a criterion that can never pass.
- **`_build-template.yml` does not match the `build-*.yml` glob** (it starts with an underscore), so the verifiers need
  no special-case filter when iterating callers.
- **`pre-commit run actionlint --all-files` was run at plan time and passed**, using pre-commit's own pinned actionlint
  v1.7.3 environment. No local `actionlint` binary exists (`make lint-actions` would fail with command-not-found), so
  the plan uses the pre-commit path.
- **Both verify blocks were executed verbatim during planning, red and green.** Task 1's verifier reports OK on
  `build-terraform-bridge.yml` and fails on `build-authentik.yml` with `on.push.tags lacks live authentik/v* glob` — the
  negative control proving it detects a commented-out trigger, which no grep can. Task 2's verifier fails on the current
  tree with `terraform-bridge has a build workflow but no RELEASE.md table row`. Both were then run against a scratch
  copy of `.github/` containing the exact file Task 1 describes plus the exact RELEASE.md edits Task 2 describes, and
  both printed OK and exited 0.
- **Heredoc bodies in the verify blocks below start at column 0 deliberately — do not re-indent them.**
  `python3 - <<'PY'` with an indented body dies immediately with `IndentationError: unexpected indent` at line 1. Each
  shell invocation is also kept on a single line, `&&`-joined, so the block can be pasted and run verbatim.
- **Line-length budget:** `.yamllint.yml` warns past 120 chars. The longest line in `build-terraform-bridge.yml` is 113
  (its `addon-description`). The description chosen below yields a 111-char line; the add-on's full `config.yaml`
  description would have yielded 124 and is deliberately shortened, matching how terraform-bridge's workflow already
  carries a short-form description that differs from its `config.yaml` text.
- **`.planning/**` is ignored by markdownlint-cli2 but NOT by prettier** (`.prettierignore` is empty, hook is
`types: [markdown]`), so prettier formats this PLAN.md too.
</context>

<tasks>

<task type="tracer">
  <name>Task 1: End-to-end build path for iac-runner — trigger through template to ghcr</name>
  <files>.github/workflows/build-iac-runner.yml</files>
  <action>
    Create the file as a structural clone of `.github/workflows/build-terraform-bridge.yml` with only the add-on
    identity swapped. Concretely: `name: Build IaC Runner`; `on.push.branches: [main]`; `on.push.paths:
    ["iac-runner/**"]`; a LIVE `on.push.tags: ["iac-runner/v*"]` (uncommented — the disabled-tag-trigger comment pattern
    used by authentik/gatus/meridian/phone-logger/markdown-renderer/coding-assistants must NOT be copied, since a dead
    trigger is the exact defect being fixed); `workflow_dispatch:`; one job `build` whose body is `uses:
    ./.github/workflows/_build-template.yml`, `permissions: {contents: read, packages: write}`, a `with:` block
    (`addon-name: iac-runner`, `addon-display-name: "IaC Runner"` matching config.yaml `name`, `addon-description:
    "Bearer-authenticated OpenTofu runner for homelab IaC with R2/S3/local state backends"`, `archs: '["amd64"]'`
    matching config.yaml `arch`), and a `secrets:` block forwarding all four of HA_BASE_URL, HA_WEBHOOK_ID,
    CF_ACCESS_CLIENT_ID, CF_ACCESS_CLIENT_SECRET.

    Do NOT add `timeout-minutes` to the `build` job — actionlint rejects that key on a reusable-workflow caller (exact
    error quoted in the context above); the timeout already exists in `_build-template.yml`. Do NOT re-derive the image
    name, version, `BUILD_FROM`, or any build step in this file: the template resolves all of that from
    `iac-runner/build.yaml` and `iac-runner/config.yaml`, and the underscore slug step turns `iac-runner` into
    `amd64-iac_runner` on its own. Do NOT add a leading file comment; no existing caller has one. Keep every line at or
    under 120 characters.

  </action>
  <precondition>
    `pre-commit run actionlint --all-files` exits 0 on the unmodified tree (verified green at plan time), so a post-change
    failure is attributable to this file.
  </precondition>
  <verify>
    <automated>
cd /home/akentner/Projects/homeassistant-addons &&
pre-commit run actionlint --all-files &&
pre-commit run yamllint --files .github/workflows/build-iac-runner.yml &&
python3 - iac-runner <<'PY'
import sys, yaml
addon = sys.argv[1]
wf = yaml.safe_load(open(f".github/workflows/build-{addon}.yml"))
tpl = yaml.safe_load(open(".github/workflows/_build-template.yml"))
cfg = yaml.safe_load(open(f"{addon}/config.yaml"))
errs = []
def need(cond, msg):
    if not cond:
        errs.append(msg)
trig = wf[True]["push"]  # YAML 1.1: the `on:` key parses as boolean True
need("main" in trig["branches"], "on.push.branches lacks main")
need(f"{addon}/**" in trig["paths"], f"on.push.paths lacks {addon}/**")
need(f"{addon}/v*" in trig.get("tags", []), f"on.push.tags lacks live {addon}/v* glob")
need("workflow_dispatch" in wf[True], "no workflow_dispatch trigger")
job = wf["jobs"]["build"]
need(job["uses"] == "./.github/workflows/_build-template.yml", "does not delegate to _build-template.yml")
need(job["with"]["addon-name"] == addon, "with.addon-name mismatch")
need(yaml.safe_load(job["with"]["archs"]) == cfg["arch"], "with.archs != config.yaml arch list")
need(job["permissions"] == {"contents": "read", "packages": "write"},
     "permissions not exactly contents:read+packages:write")
need("timeout-minutes" not in job, "timeout-minutes is illegal on a `uses:` caller job")
need(isinstance(tpl["jobs"]["build"].get("timeout-minutes"), int),
     "_build-template.yml build job lacks timeout-minutes")
for s in ("HA_BASE_URL", "HA_WEBHOOK_ID", "CF_ACCESS_CLIENT_ID", "CF_ACCESS_CLIENT_SECRET"):
    need(s in job.get("secrets", {}), f"secrets.{s} not forwarded")
print("\n".join(f"FAIL: {e}" for e in errs) or f"OK: build-{addon}.yml matches the caller contract")
sys.exit(1 if errs else 0)
PY
    </automated>
  </verify>
  <done>
    `.github/workflows/build-iac-runner.yml` exists; the actionlint and yamllint hooks pass; the structural verifier
    prints `OK: build-iac-runner.yml matches the caller contract` and exits 0. No tag was pushed and no build was
    triggered.
  </done>
</task>

<task type="auto">
  <name>Task 2: Correct the RELEASE.md tag-trigger documentation</name>
  <files>.github/RELEASE.md</files>
  <action>
    `.github/RELEASE.md:32` currently asserts the `<addon>/v*` tag trigger is commented out for every add-on but
    network-tools, and the table at lines 35-43 lists only seven add-ons. That is already wrong — `terraform-bridge` has
    a live tag trigger and no table row — and Task 1 makes it wronger. Make three edits:

    1. **The bolded clause at line 32.** Extend the trailing name list so it reads network-tools, terraform-bridge and
       iac-runner. The substring `commented out for all add-ons except` MUST survive verbatim — the verifier anchors on
       it to locate the clause, and a reword like "active only for …" makes the check report `cannot locate the
       tag-trigger clause`. Note the clause wraps across lines 32-33, so the words "except" and "network-tools" are on
       different lines; edit accordingly.
    2. **Two new table rows**, both with `paths:` = active and the tag column formatted exactly like the existing
       network-tools row (`**active**`): one for `iac-runner`, one for `terraform-bridge`, placed to keep the column
       alphabetical. The `terraform-bridge` row closes a pre-existing documentation gap opportunistically — call it out
       in the commit body so the batch reviewer is not surprised by an unrequested row.
    3. **The "built twice" sentence** in "What this means operationally", which claims only network-tools is affected.
       It is now true of three add-ons; name all three. Keep the sentence's explanation of why (the tag-triggered leg is
       the one that pulls `build.yaml:args.VERSION`) and keep the words "built twice" in it — the verifier anchors on
       that phrase.

    Leave the "Why the split" subsection and "Re-enabling a tag trigger" steps alone — do not restate the commit
    rationale or renumber anything.

  </action>
  <verify>
    <automated>
cd /home/akentner/Projects/homeassistant-addons &&
pre-commit run prettier --files .github/RELEASE.md;
pre-commit run prettier --files .github/RELEASE.md &&
python3 - <<'PY'
import re, sys, pathlib, yaml
md = pathlib.Path(".github/RELEASE.md").read_text()
# Parse the tag-trigger table into {addon: tag-column}.
rows = {}
for line in md.splitlines():
    if not line.startswith("|"):
        continue
    c = [x.strip() for x in line.strip("|").split("|")]
    if len(c) != 3 or c[0] == "Add-on" or set(c[0]) <= set("- "):
        continue
    rows[c[0]] = c[2]
errs = []
# Compare each documented row against the caller's REAL on.push.tags key. This is
# the assertion a grep cannot make: it reads the parsed trigger, not the file text,
# so a commented-out block counts as disabled. `_build-template.yml` does not match
# the glob, so it needs no filtering. No count is hardcoded anywhere.
for wf in sorted(pathlib.Path(".github/workflows").glob("build-*.yml")):
    addon = wf.name[len("build-"):-len(".yml")]
    live = bool(yaml.safe_load(wf.read_text())[True]["push"].get("tags"))
    if addon not in rows:
        errs.append(f"{addon} has a build workflow but no RELEASE.md table row")
        continue
    if ("active" in rows[addon].lower()) != live:
        errs.append(f"{addon}: table and workflow disagree on tag-trigger state")
live_addons = sorted(a for a in rows if "active" in rows[a].lower())
# Both prose checks are positive-only and derive their expectations from the table,
# so no literal has to be absent from anywhere. Whitespace is flattened first: the
# clause wraps across lines 32-33, so an unflattened match could never fire.
flat = re.sub(r"\s+", " ", md)
for label, pattern in (
    ("tag-trigger clause", r"commented out for all add-ons except ([^*]+)\*\*"),
    ("built-twice sentence", r"([^.]*built twice[^.]*)"),
):
    m = re.search(pattern, flat)
    if not m:
        errs.append(f"cannot locate the {label} in RELEASE.md")
        continue
    for a in live_addons:
        if a not in m.group(1):
            errs.append(f"{label} omits live-trigger add-on {a!r}: {m.group(1)!r}")
print("\n".join(f"FAIL: {e}" for e in errs) or
      "OK: RELEASE.md table and prose match every build-*.yml trigger state")
sys.exit(1 if errs else 0)
PY
    </automated>
  </verify>
  <done>
    The RELEASE.md table has exactly one row per `build-*.yml` file in `.github/workflows/` (no more, no fewer), each
    row's tag column agrees with that workflow's actual `on.push.tags` key, and both the line-32 clause and the
    "built twice" sentence name every add-on whose tag trigger is live. The verifier prints
    `OK: RELEASE.md table and prose match every build-*.yml trigger state` and exits 0.

    The prettier hook exits 0 on its second invocation — the first is expected to reformat table alignment and exit 1,
    which is the hook auto-fixing rather than a defect; commit the reformatted file. This is why the verify block runs
    prettier twice, the first time with `;` instead of `&&`.

  </done>
</task>

</tasks>

<threat_model>

## Trust Boundaries

| Boundary                                | Description                                                                       |
| --------------------------------------- | --------------------------------------------------------------------------------- |
| git push (tag or branch) → Actions      | A ref push by anyone with repo write access starts a credentialed build           |
| Actions runner → ghcr.io                | The run holds `packages: write` via `secrets.GITHUB_TOKEN` and can publish        |
| Actions runner → Home Assistant webhook | `HA_BASE_URL` + `HA_WEBHOOK_ID` + a Cloudflare Access service token leave the run |

## STRIDE Threat Register

ASVS level 1; disposition threshold: `high` and above must be mitigated.

| Threat ID       | Category               | Component                                  | Severity | Disposition | Mitigation Plan                                                                                                                                                                                                                                                                                                              |
| --------------- | ---------------------- | ------------------------------------------ | -------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T-pfp-01        | Elevation of Privilege | `jobs.build.permissions`                   | high     | mitigate    | Pin the caller job to exactly `contents: read` + `packages: write`. No `id-token`, no `contents: write`, no `actions: write`. Task 1's verifier asserts the permissions map is exactly that pair, so a widened scope fails verification.                                                                                     |
| T-pfp-02        | Tampering              | `on.push.tags: iac-runner/v*`              | medium   | accept      | Any `iac-runner/v*` tag push publishes and overwrites the `:latest` tag. A tag push requires repo write access and `push` events never fire from forks, so the actor set equals the maintainer set. The re-tag/`:latest`-overwrite hazard is the documented `287c79f` rationale in RELEASE.md and is unchanged by this item. |
| T-pfp-03        | Information Disclosure | `secrets:` HA\_\* / CF_ACCESS\_\*          | medium   | transfer    | The caller only forwards the four secrets to `_build-template.yml`; it defines no `run:` step and never echoes them. Masking and curl hygiene stay with the template and `.github/scripts/notify-ha.sh`, both untouched here.                                                                                                |
| T-pfp-04        | Spoofing               | third-party action references              | low      | accept      | This file references no `uses:` action other than the local reusable workflow. Every `docker/*` and `actions/*` pin lives in `_build-template.yml` and is not modified.                                                                                                                                                      |
| T-pfp-05        | Denial of Service      | runner-time consumption on trigger fan-out | low      | accept      | Both triggers can fire for one release (commit + tag), matching the intentional double-build documented for network-tools. Capped by the template's `timeout-minutes: 45`; single-arch `amd64` build measured ~3 min for comparable add-ons.                                                                                 |
| T-pfp-SC        | Tampering              | npm/pip/cargo installs                     | low      | accept      | This item installs no packages — one YAML workflow caller plus Markdown edits. No dependency is added at any layer, so no package-legitimacy gate applies and no `[ASSUMED]`/`[SUS]` checkpoint is required.                                                                                                                 |
| </threat_model> |

<verification>
Run from the repo root; all commands are local and publish nothing:

1. `pre-commit run actionlint --all-files` — exits 0 (was green before this change).
2. `pre-commit run yamllint --files .github/workflows/build-iac-runner.yml` — exits 0.
3. Task 1's structural verifier — prints `OK: build-iac-runner.yml matches the caller contract`.
4. Task 2's table/prose cross-check — prints `OK: RELEASE.md table and prose match every build-*.yml trigger state`.
5. `pre-commit run prettier --files .github/RELEASE.md` — second run exits 0 (first may auto-reformat and exit 1).
6. `make validate-addons` — still passes (unchanged; iac-runner already satisfied the required-file check).

Both verify blocks are pasteable verbatim: heredoc bodies sit at column 0 and each shell invocation is on one
`&&`-joined line. Re-indenting a heredoc body breaks it with `IndentationError` at line 1.

Explicitly NOT verified here, by instruction: no `git push` of any tag, no `workflow_dispatch`, no real build.
Correctness of the workflow is established by actionlint plus the parsed-YAML structural assertions, never by grepping
for a trigger string. </verification>

<success_criteria>

- `.github/workflows/build-iac-runner.yml` exists and delegates to `_build-template.yml` with iac-runner inputs.
- The `iac-runner/v*` tag trigger is live, and the verifier's negative-control behaviour proves "live" is actually being
  measured rather than pattern-matched.
- `with.archs` equals `iac-runner/config.yaml`'s `arch` list, and every arch in it has a `build_from` entry in
  `iac-runner/build.yaml`.
- The caller job has no `timeout-minutes`; `_build-template.yml`'s build job still has one.
- actionlint, yamllint and prettier all pass.
- `.github/RELEASE.md` documents every `build-*.yml` file — one table row each, agreeing with that file's real
  `on.push.tags` key — and its two trigger-state prose claims name every live-trigger add-on. </success_criteria>

<follow_up> Not part of this plan — surface to the developer after merge:

The `iac-runner/v0.2.1` tag already exists on origin (`refs/tags/iac-runner/v0.2.1` → `455920f`). Adding the workflow
does NOT retroactively fire it; GitHub only evaluates triggers for new ref pushes. To publish an image from that exact
tag the developer must either run the workflow via `workflow_dispatch` (safest — no tag surgery, builds from the
dispatched ref) or delete and re-push the tag. Both are deliberate manual acts and are excluded from this plan's
verification because either one publishes an image.

Sibling item `260908-pfo` bumps `iac-runner/config.yaml` to `0.2.1-1`. Once this workflow is on `main`, that bump's push
fires the `paths:` trigger and publishes `amd64-iac_runner:0.2.1-1` — the intended outcome. No hard dependency exists in
either direction: this plan touches only `.github/workflows/` and `.github/RELEASE.md`, `260908-pfo` touches only
`iac-runner/config.yaml`, and `260908-pfq` touches only `internal/check-version-tags.sh`. Zero file overlap across all
three. </follow_up>

<output>
Create `.planning/quick/add-a-build-workflow-for-the-iac-runner-add-on-there-is-curr/260908-pfp-SUMMARY.md` when done.
</output>
