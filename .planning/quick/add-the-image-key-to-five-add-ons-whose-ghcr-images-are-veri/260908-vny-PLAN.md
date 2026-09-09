---
quick_id: 260908-vny
phase: quick-260908-vny
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - gatus/config.yaml
  - markdown-renderer/config.yaml
  - phone-logger/config.yaml
  - meridian/config.yaml
  - terraform-bridge/config.yaml
  - internal/check-version-tags.sh
  - .github/RELEASE.md
autonomous: true
must_haves:
  truths:
    - All five add-ons declare a top-level `image:` whose value is `ghcr.io/akentner/homeassistant-addons/{arch}-<slug>`
      with `<slug>` equal to the directory name with hyphens replaced by underscores.
    - Every advertised `config.yaml` version still resolves to an anonymously pullable GHCR manifest (HTTP 200) for the
      `amd64` arch these five add-ons build.
    - No version string changed in any `config.yaml`, `build.yaml` or `README.md` anywhere in the repo.
    - "`LOCAL_BUILD_ADDONS` in `internal/check-version-tags.sh` holds exactly one entry, `iac-runner`."
    - The `is_local_build` helper and the `image:`-key drift guard inside the enforcement loop are still present and
      still enforce the tag requirement when an allowlisted add-on gains an `image:` key.
    - "The rationale comment block above `LOCAL_BUILD_ADDONS` names `authentik` as the sole remaining add-on that
      publishes ghcr.io images without an `image:` key, states no numeric plural of others, and still carries the
      `260908-pfq-PLAN.md` pointer. Asserted against the key-less set derived from the nine manifests, not read from the
      prose."
    - "Every `.github/RELEASE.md` section assertion resolves its section by real ATX heading with fenced code blocks
      excluded, so a hash-leading line inside a fence cannot truncate the slice being asserted."

    - "`.github/RELEASE.md` states the ghcr-404-on-update consequence only for add-ons that carry an `image:` key, and
      names the local-build failure mode separately for the two that do not."
    - "`make validate-versions`, `make validate-addons` and `make lint` all exit 0."
  artifacts:
    - gatus/config.yaml
    - markdown-renderer/config.yaml
    - phone-logger/config.yaml
    - meridian/config.yaml
    - terraform-bridge/config.yaml
    - internal/check-version-tags.sh
    - .github/RELEASE.md
  key_links:
    - "config.yaml `image:` value <-> `.github/workflows/_build-template.yml` publish target
      `${IMAGE_BASE}/${arch}-${slug}:${CONFIG_VERSION}` where slug is computed by `tr '-' '_'` and CONFIG_VERSION is
      `config.yaml`'s full subpatch-suffixed version. The manifest key and the CI publish target must name the same
      repository or the Supervisor pulls a path that was never pushed."
    - "terraform-bridge gaining `image:` <-> its removal from `LOCAL_BUILD_ADDONS`. Both must land in the same commit; a
      commit that has the key but not the removal makes the drift guard warn on every push."
    - ".github/RELEASE.md's new image-source column <-> the actual presence/absence of a top-level `image:` key in the
      nine `config.yaml` files. The column is the lookup the rewritten 404 rationale points at."
---

<objective>
Let the HA Supervisor pull prebuilt ghcr images for five add-ons instead of rebuilding them locally, then make the two
places that encode "built locally, never pulled" tell the truth again.

Purpose: `gatus`, `markdown-renderer`, `phone-logger`, `meridian` and `terraform-bridge` all publish images to
`ghcr.io/akentner/homeassistant-addons` from their build workflows, but none declares a top-level `image:` key — so the
Supervisor ignores the published image and burns minutes rebuilding the Dockerfile on every install and update. Adding
the key flips them to pull. That in turn falsifies `terraform-bridge`'s membership in the `LOCAL_BUILD_ADDONS` pre-push
allowlist, and falsifies `.github/RELEASE.md`'s blanket claim that skipping the version-file push "produces exactly the
404" for every tag-trigger-disabled add-on.

Output: five one-line manifest additions, a one-line allowlist deletion plus a corrected rationale comment, and a
RELEASE.md rewrite of the split table, the "Why the split" framing and the "What this means operationally" paragraph.
</objective>

<execution_context> @$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@.planning/STATE.md

Files to read before editing:

- `coding-assistants/config.yaml` — reference for the `image:` key format and its position (line 11, directly after the
  `arch:` list, immediately before `url:`).
- `network-tools/config.yaml` — second reference (line 7, directly after `slug:`). The two references disagree on
  position; both sit between `slug:` and `url:`, and `coding-assistants`' position is the one all five targets can
  reproduce identically because all five have an `arch:` list immediately followed by `url:`.
- `internal/check-version-tags.sh` — lines 51-94 hold the rationale comment, the `LOCAL_BUILD_ADDONS` array and
  `is_local_build`; lines 118-141 hold the drift guard inside the enforcement loop.
- `.github/RELEASE.md` — the split table plus "Why the split" and "What this means operationally" live at lines 31-73;
the two `LOCAL_BUILD_ADDONS` descriptions live at lines 106-118 (release step 2) and 143-159 (manual repair).
</context>

<environment_facts> Grounded on this host before planning — do not re-derive, do not contradict:

- `make validate-versions`, `make validate-addons`, `python3 internal/validate-addon-config.py` and `make lint` all exit
  0 on the current tree. `make lint` is the full `pre-commit run --all-files` and includes
  `internal/verify-bridge-scaffold.sh` + `internal/verify-bridge-no-token-leak.sh`, which run real `docker build`s of
  `terraform-bridge` (both passed; the whole run takes several minutes). `docker info` succeeds on this host.
- The locally installed `yq` is **python-yq (kislyuk) 4.1.2**, not mikefarah/go-yq, so `yq eval --unsafe '.version'` —
  the form documented in `CLAUDE.md` and used in CI — **fails here with an argparse error**. Read `config.yaml` values
  with `python3 -c "import yaml; ..."` instead; that is what `make validate-addons` itself does, and `yaml.safe_load`
  handles every add-on `config.yaml` in this repo (no custom tags in add-on manifests).
- Anonymous GHCR manifest lookups return HTTP 200 today for all five targets at their current `config.yaml` versions:
  `gatus` 5.36.0-11, `markdown-renderer` 1.1.0-23, `phone-logger` 1.0.6-0, `meridian` 1.66.0-0, `terraform-bridge`
  0.3.0-0. All five build `amd64` only.
- `build.yaml` VERSION values (must not change): gatus 5.36.0, markdown-renderer 1.1.0, phone-logger 1.0.6, meridian
  1.66.0, terraform-bridge 0.3.0. README badges match each.
- Add-ons currently lacking a top-level `image:` key: authentik, gatus, iac-runner, markdown-renderer, meridian,
  phone-logger, terraform-bridge (7). After this change only **authentik** and **iac-runner** lack it.
- `internal/validate-addon-config.py` validates `arch`/`startup`/`boot` enums and does not reject unknown top-level
  keys, so adding `image:` cannot fail it. `internal/validate-versions.sh` reads `^version:` from `config.yaml` and is
  unaffected by a new key.
- Editing `terraform-bridge/config.yaml` makes the two `files: ^terraform-bridge/.*$` pre-commit hooks fire on commit;
  both need a working Docker daemon.
- Prettier (`proseWrap: always`, `printWidth: 120`) and markdownlint run over **all** tracked markdown including
  `.planning/**`. A prettier reflow of edited markdown — this plan file included — is expected; re-run the gate after
  the hook rewrites files and let the second run be the verdict. </environment_facts>

<scope_boundaries> Deliberately **not** touched by this item:

- `authentik` and `iac-runner` get no `image:` key. `authentik/**` belongs to sibling batch item `260908-vnz`; there is
  zero file overlap with this plan, hence `depends_on: []`.
- No version bump anywhere. `config.yaml`, `build.yaml` and `README.md` versions stay byte-identical — a bump would
  advertise a version whose ghcr tag does not exist yet, which is the exact 404 this repo's tooling exists to prevent.
- `.github/workflows/build-*.yml` tag-trigger states stay as they are. This item changes what the Supervisor pulls, not
  what CI builds.
- `README.md` (lines 158-162) and `AGENTS.md` (lines 104-108) describe the allowlist generically without naming its
  members, so they stay true after the membership shrinks. No edit.
- The `iac-runner` allowlist entry, the `is_local_build` helper and the drift guard stay.

Known-stale claims recorded but **not** fixed here (out of the sections this item scopes; candidate follow-up):
`.github/RELEASE.md` line 84 says "The seven callers carry the comment", but only six workflow files contain
`tag-trigger temporarily disabled` (authentik, coding-assistants, gatus, markdown-renderer, meridian, phone-logger).
Line 54's "all seven" is a historical statement about the state at commit `287c79f` and reads correctly as history.

Plan-time capability hook dispositions (all four ran; none produced work):

- `api-coverage`: detector on this item's scope returned `{"detected":false}`. No external API integration — a manifest
  key pointing at a container registry is not an API surface. Checkpoint skipped, no `COVERAGE.md`.
- `assumption-delta`: detector returned `{"detected":false}`. No singular→plural / required→optional / derived→chosen
  transition; the allowlist goes plural→singular, which is not an identity-model change. Advisory, skipped.
- `schema-gate`: no Payload/Prisma/Drizzle/Supabase/TypeORM path in scope. Skipped silently.
- `security`: active — see `<threat_model>`. ASVS L1, blocking threshold `high`. </scope_boundaries>

<tasks>

<task type="tracer">
  <name>Task 1: Prove the image key end-to-end on gatus only</name>
  <files>gatus/config.yaml</files>
  <precondition>`https://ghcr.io` is reachable from this host — the anonymous manifest probe below is the only guard
  that the key being added points at an image that actually exists. If the probe cannot run, halt; do not commit an
  unverified `image:` key.</precondition>
  <reversibility rating="reversible">One added manifest line; deleting the line restores local building.</reversibility>
  <action>Add exactly one new top-level line to `gatus/config.yaml`:
  `image: "ghcr.io/akentner/homeassistant-addons/{arch}-gatus"`, at column 0, double-quoted, placed immediately before
  the existing `url:` line — i.e. directly after the `arch:` list including its commented-out entries. That is the same
  position `coding-assistants/config.yaml` uses. Leave `{arch}` as the literal placeholder text; the Supervisor
  substitutes it. Change nothing else in the file: not `version:`, not `arch:`, not the commented arch entries. Do this
  for gatus alone first, so the insertion point and the registry invariant are proven against one file before the same
  edit is repeated four times.</action>
  <verify>

```bash
python3 - <<'PY'
import yaml
d = yaml.safe_load(open('gatus/config.yaml'))
assert d['image'] == 'ghcr.io/akentner/homeassistant-addons/{arch}-gatus', d.get('image')
assert d['version'] == '5.36.0-11', d['version']
assert d['arch'] == ['amd64'], d['arch']
print('gatus manifest OK')
PY

ACC='application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json'
ACC="$ACC, application/vnd.docker.distribution.manifest.v2+json"
ACC="$ACC, application/vnd.docker.distribution.manifest.list.v2+json"
R=akentner/homeassistant-addons/amd64-gatus
V=$(python3 -c "import yaml;print(yaml.safe_load(open('gatus/config.yaml'))['version'])")
T=$(curl -sf "https://ghcr.io/token?scope=repository:$R:pull&service=ghcr.io" \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
C=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $T" -H "Accept: $ACC" \
    "https://ghcr.io/v2/$R/manifests/$V")
echo "gatus $V -> http $C"
test "$C" = 200

python3 internal/validate-addon-config.py
make validate-addons
make validate-versions
pre-commit run --files gatus/config.yaml
```

  </verify>
  <done>`gatus/config.yaml` carries the `image:` key at the coding-assistants position, its version is still 5.36.0-11,
  the anonymous GHCR probe returns 200 for that version, and the addon-config / addons / versions validators plus the
  scoped pre-commit run all exit 0. Committed as
  `feat(gatus): declare ghcr image so the Supervisor pulls instead of building`.</done>
</task>

<task type="auto">
  <name>Task 2: Repeat for the remaining four and drop terraform-bridge from LOCAL_BUILD_ADDONS</name>
  <files>markdown-renderer/config.yaml, phone-logger/config.yaml, meridian/config.yaml, terraform-bridge/config.yaml,
  internal/check-version-tags.sh</files>
  <precondition>Task 1 is committed and its GHCR probe returned 200, so the insertion position and the probe command
  are already proven. A working Docker daemon is required: committing `terraform-bridge/config.yaml` fires the
  `verify-bridge-scaffold` and `verify-bridge-no-token-leak` pre-commit hooks, both of which `docker build` the
  bridge.</precondition>
  <reversibility rating="reversible">Four added manifest lines and one deleted array element; each reverts
  independently.</reversibility>
  <action>Apply the Task 1 edit verbatim to the four remaining manifests, each with its own underscore slug:
  `markdown-renderer/config.yaml` gets `image: "ghcr.io/akentner/homeassistant-addons/{arch}-markdown_renderer"`,
  `phone-logger/config.yaml` gets `{arch}-phone_logger`, `meridian/config.yaml` gets `{arch}-meridian`, and
  `terraform-bridge/config.yaml` gets `{arch}-terraform_bridge`. Same column 0, same double quotes, same position
  immediately before each file's `url:` line. Touch no version, no arch list, no options block.

Then in `internal/check-version-tags.sh`, delete the single array element naming the bridge add-on from
`LOCAL_BUILD_ADDONS`, leaving `iac-runner` as the only member. Do not reformat the array, do not touch `is_local_build`,
and do not touch the drift-guard block inside the enforcement loop that warns when an allowlisted add-on declares an
`image:` key and then enforces the tag requirement anyway. Add no comment, marker or token of any kind between
`LOCAL_BUILD_ADDONS=(` and its closing `)` — the array body must contain nothing but the one remaining add-on name,
because an acceptance criterion below reads exactly that region.

Also correct the one factual claim in the rationale comment above the array that this edit falsifies: the sentence
beginning "Why this is an explicit allowlist and not a test for a missing `image:` key" currently asserts a plural count
of further add-ons that lack the key while publishing ghcr.io images. After this change only `authentik` does. Rewrite
that clause to name `authentik` in the singular, together with its single build workflow, and state no count of others
at all — the verify block below hard-fails on any surviving numeric-plural claim about key-less add-ons, so a merely
re-worded but still-counting sentence is rejected. Keep the reasoning (inferring the rule from the key's absence would
cement a missing-key bug behind a guard that stopped complaining), keep the `.planning/quick/...` pointer to the prior
plan, and do not name the add-on being removed anywhere in the comment. Do not trust this prose for the membership fact:
the verify block derives the key-less set from the nine manifests and asserts its exact contents.

These five files land in one commit on purpose: the moment `terraform-bridge/config.yaml` has the key while the
allowlist still lists it, every push prints the drift warning.</action> <verify>

```bash
python3 - <<'PY'
import yaml
want = {
    'gatus': ('gatus', '5.36.0-11'),
    'markdown-renderer': ('markdown_renderer', '1.1.0-23'),
    'phone-logger': ('phone_logger', '1.0.6-0'),
    'meridian': ('meridian', '1.66.0-0'),
    'terraform-bridge': ('terraform_bridge', '0.3.0-0'),
}
base = 'ghcr.io/akentner/homeassistant-addons/{arch}-'
for addon, (slug, version) in want.items():
    d = yaml.safe_load(open(f'{addon}/config.yaml'))
    assert d.get('image') == base + slug, (addon, d.get('image'))
    assert d['version'] == version, (addon, 'version changed', d['version'])
build = {'gatus': '5.36.0', 'markdown-renderer': '1.1.0', 'phone-logger': '1.0.6',
         'meridian': '1.66.0', 'terraform-bridge': '0.3.0'}
for addon, version in build.items():
    got = yaml.safe_load(open(f'{addon}/build.yaml'))['args']['VERSION']
    assert got == version, (addon, 'build.yaml VERSION changed', got)
print('five manifests keyed, no version moved')
PY

ACC='application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json'
ACC="$ACC, application/vnd.docker.distribution.manifest.v2+json"
ACC="$ACC, application/vnd.docker.distribution.manifest.list.v2+json"
for a in gatus markdown-renderer phone-logger meridian terraform-bridge; do
  s=$(printf '%s' "$a" | tr '-' '_')
  R="akentner/homeassistant-addons/amd64-$s"
  V=$(python3 -c "import yaml,sys;print(yaml.safe_load(open(sys.argv[1]))['version'])" "$a/config.yaml")
  T=$(curl -sf "https://ghcr.io/token?scope=repository:$R:pull&service=ghcr.io" \
      | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
  C=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $T" -H "Accept: $ACC" \
      "https://ghcr.io/v2/$R/manifests/$V")
  printf '%-20s %-12s http=%s\n' "$a" "$V" "$C"
  test "$C" = 200 || exit 1
done

# Array region only: the closing paren bounds it, so the rationale comment above is excluded.
ARR=$(sed -n '/^LOCAL_BUILD_ADDONS=(/,/^)/p' internal/check-version-tags.sh)
printf '%s\n' "$ARR" | grep -cE '^[[:space:]]+[a-z0-9._-]+$' | grep -qx 1
printf '%s\n' "$ARR" | grep -q 'iac-runner'
# <!-- planner-discipline-allow: terraform-bridge -->
if printf '%s\n' "$ARR" | grep -q 'terraform-bridge'; then echo 'FAIL: still allowlisted'; exit 1; fi

grep -q 'is_local_build()' internal/check-version-tags.sh
grep -q 'LOCAL_BUILD_ADDONS but its config.yaml declares' internal/check-version-tags.sh
grep -q 'Enforcing the tag requirement despite the allowlist entry' internal/check-version-tags.sh

# Derive the key-less set from the manifests and assert its exact contents. This is the
# fact the rationale comment claims, so it is asserted, not echoed.
KEYLESS=$(for d in */; do
  [ -f "$d/config.yaml" ] && [ -f "$d/build.yaml" ] || continue
  grep -qE '^image:[[:space:]]*[^[:space:]]' "$d/config.yaml" || printf '%s\n' "${d%/}"
done | sort | paste -sd' ')
echo "key-less add-ons: [$KEYLESS]"
test "$KEYLESS" = "authentik iac-runner" \
  || { echo "FAIL: key-less set is not exactly authentik + iac-runner"; exit 1; }

# Rationale comment block directly above the array. Bounded by the contiguous run of
# comment lines that precedes LOCAL_BUILD_ADDONS=( , so the array body and the code
# above the block are both excluded; blank lines do not break the run.
RAT=$(awk '/^#/ { buf = buf $0 "\n"; next }
           /^[[:space:]]*$/ { next }
           /^LOCAL_BUILD_ADDONS=\(/ { print buf; exit }
           { buf = "" }' internal/check-version-tags.sh)
printf '%s\n' "$RAT" | grep -q 'authentik' \
  || { echo "FAIL: rationale does not name the sole remaining key-less publisher"; exit 1; }
printf '%s\n' "$RAT" | grep -q '260908-pfq-PLAN.md' \
  || { echo "FAIL: prior-plan pointer dropped from the rationale"; exit 1; }
if printf '%s\n' "$RAT" | grep -qiE '(two|three|four|five|six|seven|eight|nine|ten|[0-9]+) other add-ons'; then
  echo "FAIL: rationale still claims a numeric plural of other key-less add-ons"; exit 1
fi
echo 'rationale comment OK'

shellcheck -e SC1091 -e SC2034 internal/check-version-tags.sh
bash -n internal/check-version-tags.sh
python3 internal/validate-addon-config.py
make validate-addons
make validate-versions
```

  </verify>
  <done>All five manifests carry the correct underscore-slug `image:` value, all five versions and all five `build.yaml`
  VERSION values are unchanged, all five anonymous GHCR probes return 200, `LOCAL_BUILD_ADDONS` contains exactly one
  element and it is `iac-runner`, the removed name appears nowhere inside the array region, `is_local_build` and both
  drift-guard message lines survive, the derived key-less set asserts equal to exactly `authentik iac-runner`, the
  rationale comment block above the array names `authentik`, still carries the `260908-pfq-PLAN.md` pointer and matches
  no numeric-plural claim about other key-less add-ons (`rationale comment OK` printed), and
  shellcheck / `bash -n` / the three validators exit 0. Committed as
  `feat(addons): declare ghcr image for 4 add-ons; drop terraform-bridge from LOCAL_BUILD_ADDONS`.</done>
</task>

<task type="auto">
  <name>Task 3: Retire the stale 404 rationale in RELEASE.md</name>
  <files>.github/RELEASE.md</files>
  <action>Three edits, then the full gate run.

First, the split table under "## Tag schema": add a fourth column headed `Supervisor image source`. Its value is
`ghcr pull` for coding-assistants, gatus, markdown-renderer, meridian, network-tools, phone-logger and terraform-bridge,
and `local build` for authentik and iac-runner. Keep all nine rows, keep both existing columns and keep the bold markers
on the three active tag triggers. Add one sentence directly under the table explaining that the new column reports
whether the add-on's `config.yaml` declares a top-level `image:` key, and that this axis is independent of the
tag-trigger split in the two columns to its left.

Second, "### Why the split": keep both commit-quoted bullets verbatim — they are historical fact and still accurate. Add
a short closing paragraph stating that the tag-trigger split is a historical CI decision and must not be read as the
pull-versus-local-build split, which is the new column's axis; conflating the two is what made the operational paragraph
below wrong.

Third, "### What this means operationally": keep the true parts — that for the six tag-trigger-disabled add-ons a tag
push alone builds nothing, and that step 2's push to `main` is the only thing that fires the build via the `paths:`
filter. Then split the consequence by image source instead of asserting one outcome for all six. State that the ghcr
404-on-update is the consequence only for add-ons whose `config.yaml` declares an `image:` key, because those are the
ones the Supervisor pulls; name `authentik` and `iac-runner` as the two that declare no `image:` key, so the Supervisor
builds them locally from their `Dockerfile` and a missing ghcr tag cannot produce a pull 404 for them — their failure
mode is a local build against whatever `main` holds. Do not delete the 404 warning; it must stay prominent for the
pulling add-ons. Keep the closing network-tools / terraform-bridge / iac-runner double-build paragraph unchanged.

Fourth, both `LOCAL_BUILD_ADDONS` descriptions — step 2 of "## Standard release flow" and the closing paragraph of "##
Manual repair" — must match the new single-entry membership: say that the allowlist now holds exactly one add-on,
`iac-runner`, and keep the existing pointer that the array in `internal/check-version-tags.sh` is the source of truth
for current membership. Keeping the pointer is deliberate: it is what stops this prose from silently going stale the
next time membership changes.

Prettier reflows this file (`proseWrap: always`, 120 columns). Write the prose, let the hook rewrite it, then re-run the
gate.</action> <verify>

```bash
pre-commit run prettier --files .github/RELEASE.md || pre-commit run prettier --files .github/RELEASE.md
pre-commit run markdownlint-cli2 --files .github/RELEASE.md

python3 - <<'PY'
import re

lines = open('.github/RELEASE.md').read().splitlines()
ATX = re.compile(r'^(#{1,6})[ \t]\S')
FENCE = re.compile(r'^\s*(`{3,}|~{3,})')

# Collect real ATX headings only. A '#'-leading line inside a fenced block is shell
# comment text, not document structure: RELEASE.md's Patch-flow fence already holds
# one, and this task adds prose to sections that may gain more. Bounding a section on
# a raw newline-plus-hash would silently truncate the slice and turn every token
# assertion below into a false negative.
heads, fence = [], None
for i, ln in enumerate(lines):
    f = FENCE.match(ln)
    if f:
        tok = f.group(1)[0]
        fence = tok if fence is None else (None if fence == tok else fence)
        continue
    if fence is None:
        m = ATX.match(ln)
        if m:
            heads.append((i, len(m.group(1)), ln))

def section(prefix):
    hit = [(i, lvl) for i, lvl, ln in heads if ln.startswith(prefix)]
    assert len(hit) == 1, f'heading {prefix!r} matched {len(hit)} headings, want exactly 1'
    start, level = hit[0]
    # End at the next heading of the same or shallower level, so a newly added
    # subheading extends the section instead of truncating it.
    end = next((i for i, lvl, _ in heads if i > start and lvl <= level), len(lines))
    return '\n'.join(lines[start:end])

ops = section('### What this means operationally')
for token in ('image:', 'authentik', 'iac-runner', '404', 'locally'):
    assert token in ops, f'operationally section missing {token!r}'

why = section('### Why the split')
assert '287c79f' in why and '60e7835' in why, 'commit citations lost'

flow = section('## Standard release flow')
assert 'LOCAL_BUILD_ADDONS' in flow and 'iac-runner' in flow, 'step 2 allowlist text not updated'
assert 'source of truth' in flow, 'source-of-truth pointer dropped from step 2'

repair = section('## Manual repair')
assert 'LOCAL_BUILD_ADDONS' in repair and 'iac-runner' in repair, 'manual-repair allowlist text not updated'

schema = section('## Tag schema')
rows = [ln for ln in schema.splitlines() if ln.lstrip().startswith('|')]
named = [ln for ln in rows if 'authentik' in ln]
assert named, 'split table row for authentik not found'
assert len(named[0].split('|')) == 6, f'table is not 4 columns: {named[0]!r}'
for addon in ('coding-assistants', 'gatus', 'iac-runner', 'markdown-renderer', 'meridian',
              'network-tools', 'phone-logger', 'terraform-bridge'):
    assert any(addon in ln for ln in rows), f'split table row missing for {addon}'
print('RELEASE.md checks passed')
PY

make validate-versions
make validate-addons
make lint
```

  </verify>
  <done>The split table has a fourth `Supervisor image source` column with all nine rows classified, "Why the split"
  keeps both commit citations plus a paragraph separating the tag-trigger axis from the image-source axis, the
  operational section scopes the 404 to `image:`-carrying add-ons and names authentik and iac-runner as locally built,
  both `LOCAL_BUILD_ADDONS` descriptions name `iac-runner` as the sole member while keeping the source-of-truth
  pointer, the python assertion block prints `RELEASE.md checks passed`, and `make validate-versions`,
  `make validate-addons` and `make lint` all exit 0. Committed as
  `docs(release): scope the 404 rationale to image-pulling add-ons`.</done>
</task>

</tasks>

<threat_model>

## Trust Boundaries

| Boundary                     | Description                                                                                                                                                     |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| HA Supervisor -> ghcr.io     | The `image:` key moves five add-ons from "build the in-repo Dockerfile locally" to "fetch a remote OCI artifact". A remote, mutable-tag artifact crosses in.    |
| repo docs -> operator action | `.github/RELEASE.md` is what an operator follows when cutting a release. Softening a warning there changes real push behaviour on a live HA host.               |
| pre-push hook -> `origin`    | `internal/check-version-tags.sh` is the last gate before a version bump reaches `main`. Its allowlist decides whether the ghcr-tag-existence check runs at all. |

## STRIDE Threat Register

| Threat ID | Category               | Component                                   | Severity | Disposition | Mitigation Plan                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| --------- | ---------------------- | ------------------------------------------- | -------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T-vny-01  | Tampering              | `image:` in five `config.yaml`              | high     | mitigate    | The reference is confined to the repo owner's own namespace `ghcr.io/akentner/homeassistant-addons` and resolves to the `config.yaml` version tag that `_build-template.yml` publishes from a `main` commit. Task 2 additionally restores the pre-push tag-existence guard for terraform-bridge by removing it from `LOCAL_BUILD_ADDONS`, re-establishing the commit -> tag -> image-tag correspondence for that add-on. No version is bumped, so no new tag surface is advertised. |
| T-vny-02  | Denial of Service      | HA install/update path for the five add-ons | high     | mitigate    | Tasks 1 and 2 assert an anonymous GHCR manifest HTTP 200 for each advertised `config.yaml` version _before_ committing, and assert every `config.yaml`/`build.yaml` version is byte-identical to its pre-change value. Advertising a version whose tag was never built is the only way this change can brick an update, and both halves of that are gated.                                                                                                                          |
| T-vny-03  | Information disclosure | `.github/RELEASE.md` operational guidance   | medium   | mitigate    | The rewrite keeps the 404 warning prominent for `image:`-carrying add-ons and states the local-build failure mode separately, with the new table column as the lookup. The python assertion in Task 3 fails if the operational section loses `404`, `image:`, `authentik` or `iac-runner`, so the warning cannot be silently deleted instead of scoped.                                                                                                                             |
| T-vny-04  | Elevation of privilege | `internal/check-version-tags.sh`            | medium   | mitigate    | Only array membership changes. Task 2's criteria assert `is_local_build()` and both drift-guard message lines still exist and that the array region holds exactly one element, so the guard cannot be widened into an unconditional bypass while looking edited-as-intended.                                                                                                                                                                                                        |
| T-vny-05  | Spoofing               | anonymous, unauthenticated GHCR pull        | low      | accept      | The images are intentionally public so the Supervisor can pull without credentials; GHCR serves them over TLS from the owner's namespace. HA's `image:` key has no digest-pinning syntax (it is an `{arch}` placeholder plus an implicit version tag), so digest pinning is unavailable at this layer and is not a gap this item can close.                                                                                                                                         |
| T-vny-06  | Repudiation            | release audit trail for terraform-bridge    | low      | accept      | Net improvement, not a risk: removing the add-on from the allowlist re-enables the tag-existence requirement, so a bridge version reaching `main` must again have a named tag. No new repudiation surface.                                                                                                                                                                                                                                                                          |
| T-vny-SC  | Tampering              | npm / pip / cargo installs                  | low      | accept      | This item installs no packages and adds no dependency, so the package-legitimacy gate has no input. The container-image supply chain that _is_ in scope is covered by T-vny-01.                                                                                                                                                                                                                                                                                                     |

Both `high` threats carry disposition `mitigate` with mitigations implemented inside this plan's tasks, satisfying the
configured blocking threshold (`security_block_on: high`, ASVS level 1). </threat_model>

<verification>
Whole-item gate, run from the repo root after Task 3:

- `make validate-versions` exits 0.
- `make validate-addons` exits 0.
- `make lint` exits 0 (allow one prettier-rewrite pass, then re-run; the run includes two Docker-backed terraform-bridge
  hooks and takes several minutes).
- The Task 2 python block re-run: five manifests keyed with the right underscore slugs, no version moved.
- The Task 2 GHCR loop re-run: five HTTP 200s.
- The Task 3 python block re-run: `RELEASE.md checks passed`.
- `git status --short` shows exactly the seven declared files as modified and nothing else.
</verification>

<success_criteria>

- gatus, markdown-renderer, phone-logger, meridian and terraform-bridge each declare
  `image: "ghcr.io/akentner/homeassistant-addons/{arch}-<slug>"` with the underscore slug, at the coding-assistants
  position (immediately before `url:`).
- Every one of those five versions still resolves to an anonymously pullable GHCR manifest.
- Not one version string moved in any `config.yaml`, `build.yaml` or `README.md`.
- `LOCAL_BUILD_ADDONS` holds exactly `iac-runner`; `is_local_build` and the drift guard are intact.
- The rationale comment above the array states no numeric plural of other key-less add-ons and names `authentik` as the
  only one; the derived key-less set asserts equal to exactly `authentik iac-runner`.
- `.github/RELEASE.md` scopes the ghcr 404 consequence to `image:`-carrying add-ons, classifies all nine add-ons by
  image source in the split table, and describes `LOCAL_BUILD_ADDONS` as a single-entry allowlist while keeping the
  array as the documented source of truth.
- authentik and iac-runner are untouched.
- Three atomic commits, one per task. </success_criteria>

<output>
Create `.planning/quick/add-the-image-key-to-five-add-ons-whose-ghcr-images-are-veri/260908-vny-SUMMARY.md` when done.
</output>
