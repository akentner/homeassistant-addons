---
phase: 01-git-serving-core
plan: 06
subsystem: docs
tags: [docs, translations, contracts, changelog, spike, release, version-bump]

requires:
  - phase: 01-git-serving-core
    provides: "01-01..01-05: sync service, status.json, trigger file, access store, mrp CLI, access-watch, startup log, verify script (documented from the code as built)"
provides:
  - "translations/en.yaml and new translations/de.yaml for every config.yaml schema key incl. repositories.fields.repository|branch"
  - "DOCS.md: Overview, Options, Store URLs, Managing users, Sync and status, Contracts (access.json, status.json, sync trigger), Security notes, Limitations, Development"
  - "README.md status text without 'scaffold'; CHANGELOG.md section [0.1.0-1] - 2026-11-18"
  - "SPIKE.md corrections (D-30): git git-daemon lighttpd, global cgi.assign pitfall, server.breakagelog in the config block"
  - "config.yaml version 0.1.0-1 via make update-version NO_TAG=yes, description without '(scaffold)' (D-24, D-31)"
affects: [02-supervisor-integration, 03-management-page, 04-provisioning-api, 05-public-exposure]

actuals:
  tokens: 8900
  tasks: 4
  commits: 4
plan_head_before: 6837dde1d08652dc636b5d2a2b8050cc12e117c4
plan_head_after: aa0aae2a86059e1167e5359eda4957b52a2ceea9

tech-stack:
  added: []
  patterns:
    - "Contract docs are written from the modules (status.py, access.py, cli.py, paths.py, sync.py); field tables list every field with type"
    - "Forward links to sections that a later task adds are kept as plain text until that task, so markdownlint MD051 passes per commit"

key-files:
  created:
    - marketplace-repo-proxy/translations/de.yaml
  modified:
    - marketplace-repo-proxy/translations/en.yaml
    - marketplace-repo-proxy/DOCS.md
    - marketplace-repo-proxy/README.md
    - marketplace-repo-proxy/CHANGELOG.md
    - marketplace-repo-proxy/SPIKE.md
    - marketplace-repo-proxy/config.yaml

key-decisions:
  - "01-06: DOCS.md describes the access-watch service as its own s6 longrun (as built in 01-03), not as a thread in sync (RESEARCH sketch)"
  - "01-06: the interim user commands are documented with the container name addon_{repo-hash}_marketplace_repo_proxy and hostname {repo-hash}-marketplace-repo-proxy"

patterns-established:
  - "Release per phase: CHANGELOG versioned section first, bump commit (config.yaml only) last, no tag on the feature branch"

requirements-completed: [MRP-01, MRP-02, MRP-04]

coverage:
  - id: D1
    description: "Every config.yaml schema key has a name and description in translations/en.yaml and translations/de.yaml"
    requirement: MRP-01
    verification:
      - kind: other
        ref: "uv run --no-project --with pyyaml==6.0.3 python3 -c '<schema keys minus translation keys>' -> translations complete"
        status: pass
    human_judgment: false
  - id: D2
    description: "DOCS.md documents options, store URLs, mrp user management and the six status codes"
    requirement: MRP-01
    verification:
      - kind: other
        ref: "Task 1 grep gate -> docs-usage-complete; Managing users / Store URLs headings 1 each; stdin 0; public_url 3"
        status: pass
    human_judgment: true
    rationale: "Grep gates prove presence of terms; whether an operator can follow the docs is a reading judgment"
  - id: D3
    description: "access.json, status.json and sync trigger contracts plus security notes documented for Phases 3-4"
    requirement: MRP-04
    verification:
      - kind: other
        ref: "Task 2 grep gate -> contracts-documented; pre-commit run --files on the five doc files -> all Passed"
        status: pass
    human_judgment: false
  - id: D4
    description: "CHANGELOG [0.1.0-1] section on top, README status updated with badges unchanged"
    requirement: MRP-02
    verification:
      - kind: other
        ref: "Task 2 gate (CHANGELOG top section, README badge, version files untouched, make validate-versions)"
        status: pass
    human_judgment: false
  - id: D5
    description: "SPIKE.md corrected per D-30 with the Decisions section byte-identical"
    verification:
      - kind: other
        ref: "Task 3 gate -> spike-corrected; pre-commit run --files marketplace-repo-proxy/SPIKE.md -> 0 Failed"
        status: pass
    human_judgment: false
  - id: D6
    description: "config.yaml 0.1.0-1 via make update-version NO_TAG=yes, new description, bump commit holds only config.yaml, no tag"
    verification:
      - kind: other
        ref: "Task 4 gates -> bump-ok, bump-commit-ok; git ls-remote --tags origin refs/tags/marketplace-repo-proxy/v0.1.0-1 -> empty"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-11-18
status: complete
---

# Phase 1 Plan 06: Operator docs, contracts, spike corrections and 0.1.0-1 release Summary

**DOCS.md now covers options, store URLs, `mrp` user management, sync status codes, the `access.json` /
`status.json` / `sync.request` contracts and security notes; en/de translations cover every option; SPIKE.md names
`git-daemon`, the global `cgi.assign` pitfall and `server.breakagelog`; config.yaml is `0.1.0-1` through
`make update-version ... NO_TAG=yes`, with no tag anywhere.**

## Performance

- **Duration:** about 6 min (excluding reading)
- **Started:** 2026-11-18T14:20:48Z
- **Completed:** 2026-11-18T14:26Z
- **Tasks:** 4
- **Files modified:** 7 (1 created, 6 modified)

## Accomplishments

- `translations/en.yaml` uses the RESEARCH text for all seven keys, with `repositories.fields.repository|branch`;
  `register_local` and `api_enabled` say "Takes effect in a later version". New `translations/de.yaml` mirrors it in
  German in the `secrets-sync` style.
- DOCS.md sections: Overview, Repository exception (kept), Options (table incl. list fields, "no effect yet", users and
  hashes never in options, example), Store URLs (format, hostname, masked startup log incl. `public_url`, query
  tolerance, `#branch`, URL as identity, unpublished port, no TLS), Managing users (`docker exec ... mrp users
  add|list|url|revoke`, `mrp sync`, `mrp reconcile`, error codes, rotation with reinstall, hand edit applied within
  about a second, `local` reserved, no standard-input trigger), Sync and status (six codes with meaning and fix, last
  good state kept), Contracts (access.json fields and write rules incl. `cli` source and newer-schema refusal;
  status.json every field with type; sync trigger), Security notes, Limitations, Development (verify script, one
  worktree at a time).
- README.md: "Status: experimental" paragraph describing what Phase 1 does and what follows; Configuration points to
  DOCS.md; badges and link definitions unchanged (`v0.1.0`).
- CHANGELOG.md: `## [0.1.0-1] - 2026-11-18` directly above `## [0.1.0-0]` with `### Added` and `### Changed`.
- SPIKE.md: `apk add git git-daemon lighttpd`, package sentence, Image bullet with `git-daemon`, second-pitfall paragraph
  for `cgi.assign`, `server.breakagelog = "/dev/null"` with a one-line comment after `server.groupname`. Decisions
  section byte-identical.
- config.yaml: `version: "0.1.0-1"` (tool), new `description` (hand edit, D-31), `stage: "experimental"` kept.

## Task Commits

1. **Task 1: translations and DOCS.md usage** - `ff99df8` (docs)
2. **Task 2: contracts, security notes, README, CHANGELOG [0.1.0-1]** - `770c4b9` (docs)
3. **Task 3: SPIKE.md corrections** - `fb7070d` (docs, `docs(marketplace-repo-proxy): correct spike server findings`)
4. **Task 4: bump to 0.1.0-1** - `aa0aae2` (chore, `chore(marketplace-repo-proxy): bump to 0.1.0-1`, config.yaml only)

## Verification Results

| Command | Result |
| --- | --- |
| Translation completeness (`uv run ... pyyaml==6.0.3 python3 -c ...`) | `translations complete` |
| Task 1 docs gate | `docs-usage-complete`; `## Managing users` 1, `## Store URLs` 1, `fields:` in de.yaml 1, `stdin` 0, `public_url` 3 |
| `pre-commit run --files` on DOCS.md, README.md, CHANGELOG.md, en.yaml, de.yaml | all Passed (prettier, markdownlint, yamllint, gitleaks, validators) |
| Task 2 contracts gate | `contracts-documented`; `Status: scaffold` 0; `[0.1.0-1]` heading 1, directly above `[0.1.0-0]`; IP/e-mail grep empty |
| Task 3 spike gate | `spike-corrected`; `git-daemon` 3, `breakagelog` 1, `works only as a global setting` 1; pre-commit 0 Failed |
| `./internal/update-version.py marketplace-repo-proxy 0.1.0-1 --dry-run --no-tag` | `Would update config.yaml: 0.1.0-0 → 0.1.0-1`, build.yaml and README.md no changes, `Would update 1/3 files` (as expected) |
| `make update-version ADDON=marketplace-repo-proxy VERSION=0.1.0-1 NO_TAG=yes` | exit 0, 1/3 files updated, validation passed |
| Task 4 gates | `bump-ok`, `bump-commit-ok` |
| `git tag -l 'marketplace-repo-proxy/v0.1.0-1'` / `git ls-remote --tags origin refs/tags/marketplace-repo-proxy/v0.1.0-1` | both empty |
| `make validate-addons validate-versions` | exit 0 |
| `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests -q` | 207 passed |
| Staged-diff leak grep (e-mail, `ghp_`, `github_pat_`, IPv4, 32-hex) before every commit | no hits |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Forward links to `#contracts` in the Task 1 commit**

- **Found during:** Task 1
- **Issue:** markdownlint MD051 failed on `[Contracts](#contracts)`, because the section is added in Task 2.
- **Fix:** Task 1 named "Contracts" as plain text; Task 2 turned the three mentions into links when it added the
  section.
- **Files modified:** `marketplace-repo-proxy/DOCS.md`
- **Commits:** `ff99df8`, `770c4b9`

**2. [Plan wording] Order of the changed lines in the bump diff**

- **Found during:** Task 4 acceptance
- **Issue:** the criterion expects the four changed lines in the order `-version:`, `+version:`, `-description:`,
  `+description:`. `description:` is line 2 and `version:` line 3 of config.yaml, so git prints one hunk:
  `-description:`, `-version:`, `+description:`, `+version:`. No ordering of an unchanged key layout can produce the
  stated order.
- **Resolution:** the substance holds: exactly four changed lines, only `version:` and `description:`. Key order in
  config.yaml was not changed to satisfy the wording.
- **Note:** the diff was written to the session scratchpad instead of `/tmp/mrp-bump.diff` (environment rule for
  temporary files); content identical.

### Code-wins notes (docs follow the code, per plan rule)

- access-watch is its own s6 longrun (01-03), not a thread inside sync (RESEARCH sketch); DOCS.md says "applied
  within about a second" without naming a thread.
- `no_repository_yaml` counts as a success code in `status.py` (`SUCCESS_CODES`): the mirror is updated and served,
  `last_success`/`head`/`addons` move forward. DOCS.md says so.
- `run.sh` still exists and is the body of the s6 oneshot `init`; the CHANGELOG `### Changed` bullet says that instead
  of "replaced by s6 services" alone.
- `mrp reconcile` exists in the CLI and is listed in DOCS.md next to the plan's commands.
- Repository URLs in `access.json` are matched case-insensitively, user labels exactly; hashes are unique across the
  file (`hash_conflict` for a given `--hash` already in use).

**Total deviations:** 1 auto-fixed (blocking lint), 1 plan-wording mismatch documented. **Impact:** none on content
or on the release; every other acceptance criterion passes literally.

## Issues Encountered

- A Task 3 gate run that used `mktemp -d` plus `rm -rf` was blocked by a safety check; the same gate ran with fixed
  files in the session scratchpad and printed `spike-corrected`.

## Known Stubs

None.

## Threat Flags

None. Documentation and a version bump only; no new endpoint, auth path or file access. T-01-28/29/30/35/36/37 are
mitigated as planned (placeholder-only docs with leak greps and gitleaks, security notes, docs from code, dry run plus
`NO_TAG=yes`, tag checks local and on origin, Decisions section byte-identical).

## Next Phase Readiness

- All six Phase 1 plans have summaries; phase completion and the squash merge into `main` belong to the orchestrator
  and the manager (tag after the merge, D-32).

## Self-Check: PASSED

- Files exist: `marketplace-repo-proxy/translations/de.yaml`, `translations/en.yaml`, `DOCS.md`, `README.md`,
  `CHANGELOG.md`, `SPIKE.md`, `config.yaml`.
- Commits `ff99df8`, `770c4b9`, `fb7070d`, `aa0aae2` are ancestors of HEAD; no tag `marketplace-repo-proxy/v0.1.0-1`
  locally or on origin.
