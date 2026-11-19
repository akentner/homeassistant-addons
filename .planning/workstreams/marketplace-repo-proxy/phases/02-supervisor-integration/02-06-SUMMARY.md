---
phase: 02-supervisor-integration
plan: 06
subsystem: docs
tags: [docs, release, supervisor, store-registration, contract, security]
status: complete

requires:
  - phase: 02-supervisor-integration
    provides: "02-01 to 02-04: Registrar, SupervisorClient, supervisor.json (D-28/D-29), store reload, mrp local status|remove|rotate, leftovers; 02-05: green container proof"
provides:
  - "DOCS.md `## Store registration` (Self-registration, Store reload, Rotating the local URL, Removing the store repository, Leftovers)"
  - "DOCS.md `### /data/supervisor.json` with `#### Phase 3 interface` (D-29), `#### Registration status` (D-28) and `#### All fields`; `### Supervisor requests`"
  - "DOCS.md manager-role security note (D-26), TCP API limitation (Q-6), reserved `local`/`local.*` labels"
  - "translations en/de: `register_local` described as effective"
  - "README pointer to DOCS.md#security-notes; CHANGELOG `## [0.1.0-2] - 2026-11-19`"
  - "config.yaml `version: \"0.1.0-2\"` via make update-version ... NO_TAG=yes, no tag"
affects: [02-07, phase-3-gui]

actuals:
  tokens: 13519
  tasks: 3
  commits: 3
plan_head_before: 948ba1e22dbf55da77bf26703bd72c160e03d776
plan_head_after: 0c98a1766afef1f54d5f33f5b833125c16793613

tech-stack:
  added: []
  patterns:
    - "Contract docs written from the code as built: field table from SupervisorStateWriter, message templates from registration_message, precedence from registration_value"

key-files:
  created: []
  modified:
    - marketplace-repo-proxy/DOCS.md
    - marketplace-repo-proxy/translations/en.yaml
    - marketplace-repo-proxy/translations/de.yaml
    - marketplace-repo-proxy/README.md
    - marketplace-repo-proxy/CHANGELOG.md
    - marketplace-repo-proxy/config.yaml

key-decisions:
  - "DOCS state that later starts carry the last recorded facts of supervisor.json (in_store, error, slug); only the first start shows every repository as missing, because SupervisorStateWriter seeds from the previous file"
  - "DOCS state that a hostname change is reported as orphaned only while /data stays; a fresh install with a new /data knows nothing about the old store repository"
  - "DOCS state that removing a store repository in Home Assistant while register_local is true makes the next sync add it again"
  - "README pointer uses an inline link so the existing link definitions stay unchanged"

patterns-established: []

requirements-completed: []

duration: 7min
completed: 2026-11-19
---

# Phase 2 Plan 06: Phase 2 docs and the 0.1.0-2 release Summary

**DOCS.md now explains self-registration, the store reload, `mrp local rotate --yes` with the D-11 warning, removal,
the four leftover reasons and the manager role (rating 7 -> 6). It also pins the `/data/supervisor.json` contract for
Phase 3, with the D-29 `repositories` interface and the fixed D-28 values and precedence. The add-on is bumped to
`0.1.0-2` through `make update-version ... NO_TAG=yes`, in a commit of its own and without a tag.**

## Performance

- **Duration:** about 7 min
- **Started:** 2026-11-18T23:55:45Z
- **Completed:** 2026-11-19T00:02:44Z (UTC)
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- **Translations:** `register_local` (en/de) now says that the add-on adds the internal store URL after the first
  successful sync and that turning it off removes nothing. `api_enabled` keeps its "later version" note.
- **DOCS.md, `## Overview` and `## Options`:** self-registration is listed as part of this version. The `register_local`
  row describes the behaviour, and "No effect yet" is left only for `api_enabled`.
- **DOCS.md, `## Store registration`:**
    - a command table for `mrp local status|rotate|remove`, the `status` output format and the 30-second wait /
      `queued: {id}`
    - `### Self-registration`: the `local` system user, registration after the first `ok` sync, the log line, automatic
      registration after the update, `register_local: false`, error states, hostname-change behaviour
    - `### Store reload`: once per `sync_interval`, deferred and persisted reloads, failed reloads stay owed, the reload
      pulls every store repository
    - `### Rotating the local URL`: the warning box (D-11), `--yes` / `confirmation_required` (D-31), add first, then the
      revoke, then the DELETE, all outputs and error codes, the 5-step reinstall procedure
    - `### Removing the store repository`: `register_local_enabled`, refusals become leftovers, D-27 (nothing is removed
      automatically), removal in the HA UI or with `ha store delete`
    - `### Leftovers`: a table of `in_use`, `error`, `interrupted` and `orphaned` with meaning and fix, plus the
      unconfigured case
- **DOCS.md, `## Managing users`:** `local` and `local.*` are reserved (`user_reserved`), with pointers to `mrp local`.
- **DOCS.md, `## Contracts`:**
    - `### /data/supervisor.json` has the single-writer, atomic and 0600 rules and says there is no key order.
    - `#### Phase 3 interface` has the structure, the order, the 11 message templates as built and a two-repository
      example.
    - `#### Registration status` has the four value rows, the 11-row mapping table and the precedence
      `error` > `leftover` > `registered` > `missing`.
    - `#### All fields` has a full placeholder example and a table of every field.
    - `### Supervisor requests` describes the internal queue.
- **DOCS.md, `## Security notes`:** the manager-role item has the role scope, the four allow-listed calls, where the
  token is used, logging, the rating 6 instead of 7, the Supervisor log exposure and the traceback/Sentry note.
  `supervisor.json` is added to the 0600 file list.
- **DOCS.md, `## Limitations` and `## Development`:** the TCP API note (Q-6), the local-only scope and the fake
  Supervisor in the verify script.
- **README.md:** the status paragraph names self-registration and the store reload. One line points to
  `DOCS.md#security-notes` (manager role). The badges are unchanged (`v0.1.0`).
- **CHANGELOG.md:** `## [0.1.0-2] - 2026-11-19` sits directly above `## [0.1.0-1]` with Added and Changed. It says that
  `register_local` now registers automatically after the update.
- **config.yaml:** `version: "0.1.0-2"`, set by `make update-version`. build.yaml (`0.1.0`) and the README badge are
  unchanged.

## Verification

| Command | Result |
| ------- | ------ |
| Task 1 translation gate (`uv run --no-project --with pyyaml==6.0.3 python3 -c ...`) | `translations ok`, exit 0 |
| Task 1 docs gate (`bash -c 'f=marketplace-repo-proxy/DOCS.md; ...'`) | `docs-phase2-complete`, exit 0 |
| `grep -c '^## Store registration'` / `grep -c '^### /data/supervisor.json'` on DOCS.md | 1 / 1 |
| IP/e-mail grep over DOCS.md and both translations | no output |
| `grep -cE '/repo/[^ ]*[0-9a-f]{32}' marketplace-repo-proxy/DOCS.md` | 0 |
| `pre-commit run --files` DOCS.md, en.yaml, de.yaml | all Passed or Skipped (prettier reflowed DOCS.md once before the commit) |
| Task 2 release-notes gate | `release-notes-ok`, exit 0 |
| `pre-commit run --files marketplace-repo-proxy/README.md marketplace-repo-proxy/CHANGELOG.md` | exit 0 |
| `grep -cE '^## \[0\.1\.0-2\] - [0-9]{4}-[0-9]{2}-[0-9]{2}$'` CHANGELOG / next heading | 1 / `## [0.1.0-1] - 2026-11-18` |
| `./internal/update-version.py marketplace-repo-proxy 0.1.0-2 --dry-run --no-tag` | `Would update config.yaml: 0.1.0-1 → 0.1.0-2`, `No changes needed` for build.yaml and README.md, `Would update 1/3 files` (as expected) |
| `make update-version ADDON=marketplace-repo-proxy VERSION=0.1.0-2 NO_TAG=yes` | `Updated 1/3 files`, validation passed |
| Task 3 gates | `bump-ok`, `bump-commit-ok` |
| `git show -U0 --format= HEAD -- marketplace-repo-proxy/config.yaml` | exactly `-version: "0.1.0-1"` / `+version: "0.1.0-2"` |
| `git tag -l 'marketplace-repo-proxy/v0.1.0-2'` | no output |
| `make validate-addons validate-versions` | exit 0 |
| `pre-commit run markdownlint-cli2 --files` DOCS.md, README.md, CHANGELOG.md | Passed |
| `uv run --no-project --with pytest==9.1.1 --with pyyaml==6.0.3 python3 -m pytest marketplace-repo-proxy/tests -q` | 436 passed |
| Privacy grep over each staged diff (IP, e-mail, 32-hex) | no output for all three commits |

No Docker run was needed (docs and the version only).

## Task Commits

1. **Task 1: translations and DOCS.md** - `724c8e5` (docs)
2. **Task 2: README pointer and CHANGELOG 0.1.0-2** - `6744deb` (docs)
3. **Task 3: bump to 0.1.0-2** - `0c98a17` (chore, config.yaml only)

## Files Created/Modified

- `marketplace-repo-proxy/DOCS.md`: Overview, Options row, `## Store registration`, Managing users, the
  `supervisor.json` contract, Supervisor requests, Security notes, Limitations, Development.
- `marketplace-repo-proxy/translations/en.yaml`, `de.yaml`: `register_local` description.
- `marketplace-repo-proxy/README.md`: status paragraph and the manager-role pointer.
- `marketplace-repo-proxy/CHANGELOG.md`: `## [0.1.0-2] - 2026-11-19`.
- `marketplace-repo-proxy/config.yaml`: `version: "0.1.0-2"` (through make).

## Deviations from Plan

### Code differs from the plan text (the code wins; the docs follow the code)

**1. Every repository is `missing` only on the first start, not at every start**
- **Plan text:** the file is written at every start before the first Supervisor call, "so every repository is `missing`
  until checked".
- **As built:** `SupervisorStateWriter` seeds `in_store`, `error`, `store_slug` and the other facts from the previous
  file (`_carry`). A later start therefore keeps the last recorded value until the next check.
- **Docs:** "On the first start every repository is `missing`; later starts keep the last recorded facts until the next
  check." The mapping row "First start, before any registration -> `missing`" is unchanged.

**2. A hostname change is reported as `orphaned` only while `/data` stays**
- **Plan text:** switching between a local copy and this repository's install gives a second store repository that is
  reported as an `orphaned` leftover.
- **As built:** `_report_orphaned` compares the slug recorded in the previous `supervisor.json`. A fresh install has its
  own new `/data` with a new `local` hash, so it does not know the old store repository and cannot report it.
- **Docs:** the `orphaned` report is described for a hostname change while `/data` stays (for example a restored
  backup). For a fresh install, the docs tell the operator to remove the old store repository in the store.

**3. Removing the store repository in the HA UI: when the next sync cleans up**
- **Plan text:** removing it in the Supervisor UI or with `ha store delete` also works, and the proxy cleans up its own
  state at the next sync.
- **As built:** `_resolve_gone` drops leftovers and unconfigured repositories whose slug is gone and revokes their
  labels. A configured repository with `register_local: true` is added again by the next pass.
- **Docs:** both effects are stated, with the hint to set `register_local: false` first.

**4. Additions found in the code and documented**
- Rotation error codes `register_local_disabled`, `not_registered`, `add_failed`, `remove_failed` and
  `store_list_unavailable`.
- Removal error codes `not_registered`, `store_list_unavailable` and `remove_failed`.
- The 30-second wait and `queued: {id}`.
- `mrp local remove` also revokes the `local` URL it removes, so turning `register_local` back on later gives a new URL.
- `mrp users url {owner/repo} local` prints the full `local` URL.
- The `mrp local status` output format.
- The invalid-request warning text.

**5. README pointer uses an inline link**
- The plan says to leave the link definitions unchanged. The pointer is the inline link
  `[security notes in DOCS.md](DOCS.md#security-notes)`, so no link definition was added or changed.

### Not run

- `git ls-remote --tags origin refs/tags/marketplace-repo-proxy/v0.1.0-2` (Task 3 acceptance criterion) was not run.
  The binding rules for this run forbid real GitHub access. This plan created no tag and pushed nothing, and
  `git tag -l` is empty.

---

**Total deviations:** 4 documentation corrections where the code differs from the plan text, 1 formatting choice and
1 check not run because of a rule. No product code changed.

## Known Stubs

None.

## Threat Flags

None. Docs and the version only. T-02-29 to T-02-33 and T-02-47 are mitigated as planned:

- placeholder-only examples, with the privacy and 32-hex greps empty and gitleaks passing
- the manager-role note
- the bump through make with a dry run, config.yaml only and no tag
- the automatic-registration note in the CHANGELOG and DOCS
- the rotation warning box, the Phase 3 interface and the registration status parts

## Issues Encountered

- Two docs-gate misses before the Task 1 commit: the phrase "no updates until" was split across a line break, and the
  word "rating" was missing. Both were reworded and the gate then passed.
- Prettier reflowed DOCS.md (nested list indent, table widths). It was re-run until the hooks were clean.

## User Setup Required

None.

## Next Phase Readiness

- The squash merge of 02-01 to 02-06 can follow. The manager tags `marketplace-repo-proxy/v0.1.0-2` on `main`.
- Plan 07 (live E2E) runs against the CI image `0.1.0-2`. DOCS.md describes the expected log lines (`registered as`,
  `store reload: ok`, the leftover lines) and the cleanup order (uninstall first, then `mrp local remove`).
- Phase 3 builds its registration view against `#### Phase 3 interface` and `#### Registration status` in DOCS.md.

## Self-Check: PASSED

- All six modified files exist, and DOCS.md contains `### /data/supervisor.json`.
- Commits `724c8e5`, `6744deb` and `0c98a17` are ancestors of HEAD.
