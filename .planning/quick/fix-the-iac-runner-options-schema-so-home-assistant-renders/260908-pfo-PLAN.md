---
quick_id: 260908-pfo
phase: quick
plan: 260908-pfo
type: execute
wave: 1
depends_on: []
files_modified:
  - iac-runner/config.yaml
  - iac-runner/DOCS.md
  - .planning/REQUIREMENTS.md
autonomous: true
requirements:
  - STBK-01
user_setup:
  - service: home-assistant
    why:
      "The corrected picker only renders after the Supervisor re-reads the add-on manifest; the repo change alone cannot
      be observed in the UI."
    dashboard_config:
      - task: "Reload the add-on store, then update the local iac-runner add-on to 0.2.1-1"
        location:
          "Settings -> Add-ons -> Add-on Store -> three-dot menu -> Check for updates, then iac-runner -> Update"
      - task:
          "Open the iac-runner Configuration tab and confirm the state_backend picker offers exactly r2 / s3 / local"
        location: "Settings -> Add-ons -> IaC Runner -> Configuration"

estimate:
  tokens: 20000
  raw_tokens: 20000
  tasks: 2
  confidence: low

must_haves:
  truths:
    - "The HA add-on Configuration page renders exactly three selectable state_backend values: r2, s3, local — none of
      the three regex-fragment artifacts the operator saw in the screenshot."
    - "The documented default value r2 is actually schema-valid. It is not today: the HA options validator splits the
      body of list(...) on the pipe character, so the currently accepted set is three regex fragments and the literal r2
      matches none of them."
    - "state_backend stays constrained to exactly three literals — validation is not widened. HA enforces the
      enumeration and iac-runner/internal/statebackend/factory.go:25 independently returns ErrUnsupported for anything
      else."
    - "bind_address validation is byte-identical before and after. Its bare match(...) regex legitimately contains a
      pipe and must not be touched (terraform-bridge/config.yaml:32 ships the identical string)."
    - "internal/validate-versions.sh passes with the stable X.Y.Z-N triple config 0.2.1-1 / build 0.2.1 / README v0.2.1."
    - "No live (non-historical) reference to the nested list/match form survives under iac-runner/ or in
      .planning/REQUIREMENTS.md, so a later verification pass cannot 'restore' the bug."
  artifacts:
    - "iac-runner/config.yaml — schema.state_backend line and the version line"
    - "iac-runner/DOCS.md — the state_backend section's schema sentence"
    - ".planning/REQUIREMENTS.md — the STBK-01 bullet"
  key_links:
    - "config.yaml schema.state_backend -> /data/options.json -> opts.StateBackend -> statebackend.New at
      iac-runner/cmd/runner/main.go:167 (widening the schema would push an unvalidated string into the backend factory)"
    - "config.yaml version -> internal/validate-versions.sh stable-format branch -> iac-runner/build.yaml args.VERSION +
      iac-runner/README.md badge (the 3-file scheme this bump deliberately edits by hand)"
    - "iac-runner/DOCS.md:79 + .planning/REQUIREMENTS.md:264 -> the two live prose copies of the broken string; leaving
      them is how this fix gets reverted by a future gap-closure pass"
---

<objective>
Make the Home Assistant add-on Configuration page render the `state_backend` picker correctly, and record the
change as an add-on-only subpatch release.

`iac-runner/config.yaml:35` currently reads `schema.state_backend: "list(match(^(r2|s3|local)$))"`. The HA options
validator splits the body of `list(...)` on the pipe character before any regex is considered, so the nested
`match(...)` is never evaluated as a regex. The operator's screenshot of the Configuration page confirms the
consequence: three bogus radio options reading `match(^(r2`, `s3` and `local)$)`. The documented default `r2` is
therefore not even a selectable value.

Every other add-on in this repo already uses plain literals inside `list(...)` — `authentik/config.yaml:34`,
`coding-assistants/config.yaml:69`, `gatus/config.yaml:36-37`, `meridian/config.yaml:40`,
`network-tools/config.yaml:75`, `phone-logger/config.yaml:107`. `iac-runner` is the only outlier.

Purpose: restore a usable Options UI for the state backend without weakening validation, and stop the broken pattern
from being re-introduced from the two prose copies that still document it. Output: a corrected `list(...)` enumeration,
a `0.2.1-1` subpatch version, and two prose references brought in line. </objective>

<execution_context> @~~/.claude/gsd-core/workflows/execute-plan.md @~~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md

@iac-runner/config.yaml @terraform-bridge/config.yaml </context>

<constraints>
Validation is NOT lost by dropping the nested regex. `list(...)` constrains the value to exactly the enumerated
literals by itself, and `iac-runner/internal/statebackend/factory.go:25` returns `ErrUnsupported` for any other
value, which `iac-runner/cmd/runner/main.go:175` turns into a `state_backend_init_failed` record plus
`os.Exit(1)`. Two independent layers survive this edit.

Do NOT add a trailing `?` to the new `list(...)`. The field is currently required and must stay required; a `?` would
silently make it optional. `meridian/config.yaml:51` is the shape to match.

Do NOT touch `bind_address` (`iac-runner/config.yaml:32`). Its bare `match(^auto$|^(...)$)?` keeps its pipe inside the
regex, which the HA validator handles correctly, and `terraform-bridge/config.yaml:32` ships the identical string.

Do NOT route the version edit through `internal/update-version.py`. It always writes `X.Y.Z-0` and has no increment
flag, so it cannot express a subpatch. This single manual version edit is explicitly user-approved and is a deliberate,
one-time exception to the repo's "never edit versions manually" rule.

Do NOT change `iac-runner/build.yaml` (`args.VERSION` and `RUNNER_VERSION` both stay `"0.2.1"`) or
`iac-runner/README.md` (badges stay `v0.2.1`). Only the `config.yaml` subpatch moves.

Do NOT touch any Go source. There is no `go` binary on this host, so nothing under `iac-runner/cmd/` or
`iac-runner/internal/` can be compile-verified. `iac-runner/cmd/runner/main.go:28` carries a stale doc comment quoting
the old schema string; it is knowingly left alone and reported as a follow-up rather than edited blind.

Do NOT touch `.planning/ROADMAP.md` or the Phase 16/17 `*-PLAN.md` files. They also quote the old string but are
historical execution records, not live specs. </constraints>

<tasks>

<task type="tracer">
  <name>Task 1: Fix the state_backend enumeration and bump to the 0.2.1-1 subpatch</name>
  <files>iac-runner/config.yaml</files>
  <reversibility rating="reversible">
    Two lines in one YAML file; `git revert` restores it. One caveat: if the operator has already installed
    0.2.1-1, prefer bumping forward to 0.2.1-2 over reverting the version line — the Supervisor caches the
    installed version and handles a version going backwards poorly.
  </reversibility>
  <action>
    Two edits in one file, landing in ONE commit.

    Edit A — line 35. Replace the whole scalar so the `state_backend` schema enumerates the three literals
    directly instead of wrapping a regex that the HA validator never evaluates. The resulting line must be
    exactly `  state_backend: "list(r2|s3|local)"` — two leading spaces, double-quoted to stay consistent with
    every other scalar in this file's `schema:` block, and with NO trailing `?` (see constraints).

    Edit B — line 3. Set the `version` field to the string `"0.2.1-1"`. This is an add-on-only subpatch under the
    repo's 3-file scheme: the base semver is unchanged, so `build.yaml` and `README.md` are correct as-is and
    must not be edited. Perform this edit directly in the file; do not invoke `internal/update-version.py` (see
    constraints).

    Leave every other line byte-identical, `bind_address` on line 32 above all.

  </action>
  <verify>
    <automated>python3 -c "import yaml,sys; d=yaml.safe_load(open('iac-runner/config.yaml')); sys.exit(0 if d['schema']['state_backend']=='list(r2|s3|local)' and d['version']=='0.2.1-1' else 1)"</automated>
    <automated>grep -Fq 'bind_address: "match(^auto$|^(([0-9]{1,3}\\.){3}[0-9]{1,3})$)?"' iac-runner/config.yaml</automated>
    <automated>./internal/validate-versions.sh</automated>
    <automated>python3 internal/validate-addon-config.py iac-runner</automated>
  </verify>
  <acceptance_criteria>
    1. The YAML round-trip check above exits 0 — it proves the file still parses AND that both target values
       landed. `python3 -c "import yaml; print(yaml.__version__)"` reports 6.0.3 on this host, so PyYAML is
       available. (No `!secret` tags exist in this file, so `safe_load` is correct here; the `--unsafe`
       caveat in CLAUDE.md applies to `yq` on HA core configs, not to this manifest.)
    2. The byte-exact `bind_address` grep exits 0. The `\\.` in the pattern is intentional — the raw file bytes
       contain a doubled backslash inside the double-quoted YAML scalar (confirmed with `cat -A`), and single
       quotes in the shell pass it through unchanged. This is the BLOCKING criterion for T-PFO-02.
    3. `./internal/validate-versions.sh` exits 0 and prints `Version validation passed for all add-ons!`. Its
       stable-format branch matches `^([0-9]+\.[0-9]+\.[0-9]+)-([0-9]+)$`, so `-1` is an accepted subpatch; it
       then compares base `0.2.1` against `build.yaml` `0.2.1` and the README badge `v0.2.1`.
    4. `python3 internal/validate-addon-config.py iac-runner` exits 0 and prints
       `Add-on config validation passed.` (it passed on the pre-change baseline too, so this is a
       no-regression check — the script does not inspect `schema:` strings at all).
    5. BEFORE staging, the changed-file set under `iac-runner/` is exactly `iac-runner/config.yaml`. This is
       what proves `build.yaml` and `README.md` were left alone. Capture `git`'s own status first rather than
       burying it in a substitution:
       ```bash
       NAMES=$(git diff --name-only -- iac-runner) || exit 1
       test "$NAMES" = "iac-runner/config.yaml"
       ```
       The pre-change baseline has no tracked modifications under `iac-runner/`, so this compares against a
       clean starting point.
    6. BEFORE staging, NO diff body line outside the two intended fields changed. Stated as a zero-match gate
       rather than an exact line count: every changed body line must mention `version:` or `state_backend:`,
       and the residue must be empty.
       ```bash
       DIFF=$(git diff -U0 -- iac-runner/config.yaml) || exit 1
       ! printf '%s\n' "$DIFF" | grep '^[+-][^+-]' | grep -vE 'version:|state_backend:' | grep -q .
       ```
       `git` runs on its own line so a `git` failure aborts instead of being masked by a later `grep` status.
       `^[+-][^+-]` deliberately excludes the `---`/`+++` headers, whose second character is also `-`/`+`.
       This is the criterion that catches a collateral `bind_address` edit even if criterion 2's byte-exact
       grep were somehow satisfied.
  </acceptance_criteria>
  <done>
    `iac-runner/config.yaml` enumerates the three state backends as plain literals, carries version `0.2.1-1`,
    still parses, still passes both repo validators, and has changed in exactly two lines with `bind_address`
    byte-identical.
  </done>
</task>

<task type="auto">
  <name>Task 2: Retire the two live prose copies of the broken string and run the full gate</name>
  <files>iac-runner/DOCS.md, .planning/REQUIREMENTS.md</files>
  <reversibility rating="reversible">One sentence and one bullet; both are prose, no runtime effect.</reversibility>
  <action>
    Two one-line prose corrections, then the repo-wide gate.

    Edit A — `iac-runner/DOCS.md:79`. The sentence in the `state_backend` section tells the operator the schema
    uses the nested form. Update the quoted schema string in that sentence to the corrected enumeration so the
    user-facing reference matches what shipped. Keep the rest of the sentence, including the clause crediting
    `statebackend.New` / `ErrUnsupported` as the runtime layer — that part is accurate and is the
    defense-in-depth claim this plan relies on. Respect the repo's 120-char Markdown limit and let prettier
    re-wrap if the line grows.

    Edit B — `.planning/REQUIREMENTS.md:264`. The STBK-01 bullet quotes the same broken string as the
    requirement text. Update the quoted string there too. This matters beyond tidiness: STBK-01 is marked `[x]`
    complete, so a later verification or gap-closure pass reading it as the spec would flag the corrected
    `config.yaml` as non-compliant and revert this fix.

    Then run `make lint`. Read the acceptance criteria before interpreting a non-zero exit — the prettier hook
    is an auto-fixer and a run that reformats a Markdown file exits 1 even when nothing is actually wrong.

    Deliberately out of scope, report both in the SUMMARY instead of editing them: the stale Go doc comment at
    `iac-runner/cmd/runner/main.go:28`, and the historical copies in `.planning/ROADMAP.md` and the Phase 16/17
    `*-PLAN.md` files.

  </action>
  <verify>
    <automated>! grep -rFn 'list(match(' iac-runner/ --include='*.yaml' --include='*.md'</automated>
    <automated>! grep -Fn 'list(match(' .planning/REQUIREMENTS.md</automated>
    <automated>grep -Fq 'list(r2|s3|local)' iac-runner/DOCS.md && grep -Fq 'list(r2|s3|local)' .planning/REQUIREMENTS.md</automated>
    <automated>make lint</automated>
    <automated>make validate-versions</automated>
  </verify>
  <acceptance_criteria>
    1. `! grep -rFn 'list(match(' iac-runner/ --include='*.yaml' --include='*.md'` exits 0, i.e. the grep finds
       nothing. Scope is deliberate and region-limited: `--include` confines the walk to YAML and Markdown, so
       the knowingly-untouched Go comment at `main.go:28` cannot fail this gate. Pre-change counts are exactly
       1 in `iac-runner/config.yaml` and 1 in `iac-runner/DOCS.md`, so this reaching zero is a real signal.
       <!-- planner-discipline-allow: list(match( -->
       The literal appears in this plan's prose only. This PLAN.md lives under
       `.planning/quick/`, which is outside both grep scopes above, so the gate is not self-invalidating.
    2. `! grep -Fn 'list(match(' .planning/REQUIREMENTS.md` exits 0 (pre-change count is exactly 1, at line
       264). `.planning/ROADMAP.md` also holds one copy and is intentionally NOT in scope, which is why this
       gate names one file rather than recursing over `.planning/`.
    3. Both positive greps for the corrected enumeration succeed, proving the sentences were rewritten rather
       than deleted.
    4. `make lint` exits 0. It runs `pre-commit run --all-files`. Expect a possible first-run exit 1: the
       `prettier` hook is `types: [markdown]` and auto-fixes in place, as do `trailing-whitespace` and
       `end-of-file-fixer`. If that happens, re-stage the reformatted files and re-run until it exits 0 — do
       not treat the first non-zero exit as a failure by itself. Note that prettier is scoped to Markdown, so
       it can never rewrite `iac-runner/config.yaml`; a config.yaml change appearing after a lint run would be
       a genuine problem.
    5. After any lint auto-fix, `git diff --name-only -- iac-runner` still lists at most
       `iac-runner/config.yaml` and `iac-runner/DOCS.md` and nothing else under `iac-runner/`.
    6. `make validate-versions` exits 0. It is re-run here because the `validate-versions` pre-commit hook is
       `always_run: true` and will fire on the commit regardless of which files are staged.
    7. Commit message names the two concerns, e.g.
       `fix(iac-runner): render state_backend picker correctly + 0.2.1-1 subpatch`.
  </acceptance_criteria>
  <done>
    No live YAML or Markdown reference to the nested form remains under `iac-runner/` or in
    `.planning/REQUIREMENTS.md`; `make lint` and `make validate-versions` both exit 0; the only files changed
    under `iac-runner/` are `config.yaml` and `DOCS.md`.
  </done>
</task>

</tasks>

<threat_model> ASVS level 1. Blocking threshold: `high` — any `high` or above must be mitigated by an acceptance
criterion in this plan, not deferred.

## Trust Boundaries

| Boundary                                              | Description                                                                                 |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| HA operator -> Supervisor Options UI                  | Operator-supplied config crosses into the add-on. This schema is the first validation gate. |
| /data/options.json -> runner process                  | `main.go` parses the file into `Options`; a hand-edited file bypasses the UI gate entirely. |
| Options value -> OpenTofu backend selection           | `opts.StateBackend` selects which remote state store and which credential files are used.   |
| config.yaml version -> Supervisor artifact resolution | The 3-file version scheme decides which build the Supervisor considers current.             |

## STRIDE Threat Register

| Threat ID       | Category               | Component                                                            | Severity | Disposition | Mitigation Plan                                                                                                                                                                                                                                                                                                                                    |
| --------------- | ---------------------- | -------------------------------------------------------------------- | -------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T-PFO-01        | Tampering              | `schema.state_backend` in `iac-runner/config.yaml`                   | medium   | mitigate    | The replacement narrows rather than widens: `list(r2                                                                                                                                                                                                                                                                                               | s3  | local)`accepts exactly three literals, whereas the broken nested form accepts the three regex fragments and rejects`r2`. Second, independent layer is untouched — `statebackend.New`returns`ErrUnsupported` (`internal/statebackend/factory.go:25`) and `main.go:175`fails fast with`state_backend_init_failed`+`os.Exit(1)`. Task 1 criterion 1 pins the exact accepted set. |
| T-PFO-02        | Tampering              | `schema.bind_address` (adjacent line 32)                             | high     | mitigate    | `bind_address` is the network-exposure gate for the JSON API on 8125 with `host_network: true`; a collateral edit while working on line 35 could widen who can reach it. Task 1 criterion 2 is a byte-exact grep of the whole scalar, backed by criteria 5-6 proving only two lines of the file changed at all. BLOCKING per the `high` threshold. |
| T-PFO-03        | Tampering              | 3-file version scheme (`config.yaml` vs `build.yaml` vs `README.md`) | low      | mitigate    | A hand-edited version bypasses `internal/update-version.py`, so drift is the risk. `internal/validate-versions.sh` is the gate, is `always_run: true` in pre-commit, and is asserted in both tasks. The `-1` subpatch is inside its stable-format branch; base `0.2.1` must still equal `build.yaml`.                                              |
| T-PFO-04        | Elevation of Privilege | Backend credential selection via `state_backend`                     | low      | accept      | The edited fields carry no secrets. R2/S3 credentials live in `/data/keys/*` and are separately `chmod 600`-validated at startup by the `keys` validator (SEC-01 fail-fast). Nothing in this change touches that path.                                                                                                                             |
| T-PFO-05        | Information Disclosure | `iac-runner/DOCS.md` prose                                           | low      | accept      | The corrected sentence documents a schema constraint only. No endpoint, token, key path or credential is added or revealed.                                                                                                                                                                                                                        |
| T-PFO-SC        | Tampering              | npm/pip/cargo installs                                               | low      | accept      | Not applicable to this change: no package-manager install, no `Dockerfile` edit, no dependency or base-image change. Nothing enters the build graph, so the Package Legitimacy Gate has no packages to audit.                                                                                                                                      |
| </threat_model> |

<verification>
Full offline gate, in order:

```bash
python3 -c "import yaml,sys; d=yaml.safe_load(open('iac-runner/config.yaml')); sys.exit(0 if d['schema']['state_backend']=='list(r2|s3|local)' and d['version']=='0.2.1-1' else 1)"
grep -Fq 'bind_address: "match(^auto$|^(([0-9]{1,3}\\.){3}[0-9]{1,3})$)?"' iac-runner/config.yaml
! grep -rFn 'list(match(' iac-runner/ --include='*.yaml' --include='*.md'
! grep -Fn 'list(match(' .planning/REQUIREMENTS.md
make validate-versions
python3 internal/validate-addon-config.py iac-runner
make lint
```

No Go toolchain is required or invoked — this host has no `go` binary, and nothing in this plan touches Go source.

<human-check>
The observable truth ("the picker offers exactly r2 / s3 / local") lives on the live HA instance and cannot be
proven from the repo. After the commit lands, the operator reloads the add-on store, updates the local
`iac-runner` add-on to 0.2.1-1, opens its Configuration tab, and confirms the `state_backend` control offers
exactly `r2`, `s3` and `local` — with `r2` selectable, which it is not today. This is a post-merge operator
action, not a blocking gate; the plan stays `autonomous: true`.

Note that `iac-runner/config.yaml` has no `image:` key, so the Supervisor builds this add-on locally and the update does
not depend on a ghcr artifact or on the outstanding `iac-runner/v0.2.1` tag. </human-check> </verification>

<success_criteria>

- `iac-runner/config.yaml:35` reads `  state_backend: "list(r2|s3|local)"` — no nested regex, no trailing `?`.
- `iac-runner/config.yaml:3` reads `version: "0.2.1-1"`; `build.yaml` still carries `VERSION: "0.2.1"` and
  `RUNNER_VERSION: "0.2.1"`; `README.md` still carries the `version-v0.2.1-blue` badge.
- `bind_address` is byte-identical to its pre-change value and to `terraform-bridge/config.yaml:32`.
- `iac-runner/DOCS.md` and `.planning/REQUIREMENTS.md` STBK-01 both quote the corrected enumeration.
- `make validate-versions`, `python3 internal/validate-addon-config.py iac-runner` and `make lint` all exit 0.
- Exactly three files changed, in one atomic commit. </success_criteria>

<output>
Create `.planning/quick/fix-the-iac-runner-options-schema-so-home-assistant-renders/260908-pfo-SUMMARY.md` when
done. Record in it: the two out-of-scope stale references left behind (`iac-runner/cmd/runner/main.go:28` and
`.planning/ROADMAP.md`), and whether `make lint` needed a prettier re-run.
</output>
