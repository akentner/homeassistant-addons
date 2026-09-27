---
quick_id: "260927-vbk"
subsystem: infra
tags: [cups, home-assistant-addon, branding, logging, print-history, jsonl]

# Actuals (#2632) / commit ledger (#3968)
actuals:
  tokens: 9100
  tasks: 3
  commits: 3
plan_head_before: 405268b6b66c7b4a328e03b5129880814bed04de
plan_head_after: e4c5ed60e2a2bafae231ce1f5337a137429c950d

key-files:
  created:
    - cups/logo.png
    - cups/print-history-poller.py
  modified:
    - cups/icon.png
    - cups/config.yaml
    - cups/run.sh
    - cups/generate_config.py
    - cups/Dockerfile
    - cups/DOCS.md
    - cups/translations/en.yaml
    - cups/translations/de.yaml
    - internal/verify-cups-scaffold.sh

duration: ~2h
completed: 2026-09-27
status: complete
---

# Quick Task 260927-vbk: CUPS Branding, Log Passthrough, and Print History Summary

**Official OpenPrinting/cups icon+logo banner, quieter `log_level` default with cupsd error/access-log passthrough into the add-on's own log output, and a JSONL print-job history persisted to `/data` — plus two pre-existing bugs (a non-retrying `cupsctl` call and a Supervisor-dependent `bashio::config` read) discovered and fixed while proving the log-level feature empirically against a real container.**

## Performance

- **Duration:** ~2h (most of it spent diagnosing and fixing timing races / a pre-existing bug uncovered while proving T2 empirically via Docker)
- **Tasks:** 3/3 completed
- **Files modified:** 11 (2 new: `cups/logo.png`, `cups/print-history-poller.py`; 9 modified)

## Accomplishments

- `cups/icon.png` replaced with the official OpenPrinting/cups 128x128 mark (removes the old placeholder black "C"); `cups/logo.png` (new, 250x100 RGBA, centered/undistorted) added. `cups/DOCS.md`'s attribution line corrected to cite `OpenPrinting/cups` instead of the archived `apple/cups`. Resolves the open todo `.planning/todos/pending/2026-09-26-cups-add-on-brand-icon-nachliefern.md`.
- `cups/config.yaml`'s `log_level` default changed `info` → `warning`. `cups/run.sh` now backgrounds `tail -F /var/log/cups/error_log` unconditionally and `tail -F /var/log/cups/access_log` additionally only at `debug` — cupsd's own file-based logs are now visible in `ha apps logs`/`docker logs`, which nothing surfaced before. Shutdown trap extended to kill both tail processes.
- `cups/print-history-poller.py` (new): polls `lpstat -W completed -o` every ~20s, tracks the last-seen CUPS job id in `/data/print-history-state.json`, appends one JSON line per newly-completed job to `/data/print-history.jsonl`. First-ever run baselines to the current max job id without backfilling. Backgrounded by `run.sh`; shutdown trap extended again to kill it too. `cups/Dockerfile`'s `COPY` line includes the new script.
- `cups` version bumped `0.1.0-12` → `0.1.0-13` via `make update-version` (covers all three tasks in one bump).
- `internal/verify-cups-scaffold.sh` extended with LogLevel/passthrough assertions (including a separate debug-tier container) and print-history assertions (poller present/running, a real completed job recorded with expected JSONL fields, state file exists).
- Full Docker-based `internal/verify-cups-scaffold.sh` run: **`ALL CHECKS PASSED`**, confirmed stable across two independent runs.
- `make lint` and `make validate-addons` both pass.

## Task Commits

Each task was committed atomically:

1. **T1: Official CUPS branding — icon.png + logo.png** - `2131bef` (feat)
2. **T2: Configurable log-level default + passthrough** - `57a9b7c` (feat)
3. **T3: Print-job history + version bump** - `e4c5ed6` (feat)

## Files Created/Modified

- `cups/icon.png` - replaced with the official OpenPrinting/cups 128x128 mark
- `cups/logo.png` - new 250x100 RGBA banner, centered/undistorted scale of the 256x256 mark
- `cups/config.yaml` - `log_level` default `info` → `warning`; version `0.1.0-12` → `0.1.0-13`
- `cups/run.sh` - log-tail passthrough (steps 9-10 reworked), print-history poller background process (step 11), shutdown trap extended to kill both tail PIDs + the poller PID; `cupsctl` call given a 5x1s retry loop; log-level resolution switched from `bashio::config` to sourcing a generated env file
- `cups/generate_config.py` - new `build_log_level_env()` resolves `log_level` directly from `/data/options.json` and writes `/tmp/cups-log-level.env` (`LOG_LEVEL` + `CUPS_LOG_LEVEL`), replacing the `bashio::config` read
- `cups/Dockerfile` - `COPY` line includes the new `print-history-poller.py`
- `cups/translations/en.yaml` / `de.yaml` - `log_level` description updated (new default + passthrough behavior) in both languages
- `cups/print-history-poller.py` - new
- `internal/verify-cups-scaffold.sh` - LogLevel/passthrough assertions (main + debug-tier container) and print-history assertions added
- `cups/DOCS.md` - icon attribution line; `log_level` table row + Design notes paragraph; new `## Print History` section

## Decisions Made

- Kept `run.sh`'s pre-existing `log_level` enum/mapping semantics (`debug|info|warning|error` → `debug|info|warn|error`) completely unchanged — only the *mechanism* used to read the value changed (see Deviations), and only the *default* value changed (per T2's own scope).
- Regenerated `cups/logo.png` from the source `cups-256.png` using the plan's exact recipe rather than reusing a same-named file that happened to already exist at the scratchpad path, to guarantee the committed asset matches the plan's byte-for-byte recipe rather than an unverified prior artifact.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `log_level` was silently unreadable without a live Supervisor; fixed by reading it directly from `/data/options.json`**
- **Found during:** Task 3, while running `internal/verify-cups-scaffold.sh` for real to prove T2's LogLevel/passthrough assertions
- **Issue:** `run.sh` read `log_level` via `bashio::config 'log_level'`, which calls `bashio::addon.config` — a function with NO local-file fallback; it always makes an HTTP round-trip to the Supervisor API. In this repo's own Docker-only verify harness (no live Supervisor), that call failed (`curl: (6) Could not resolve host: supervisor`) and silently returned an empty string, which `run.sh`'s old case-statement then defaulted to `"info"` — meaning **any** configured `log_level` value other than the fallback default was never actually applied, and the pre-existing test fixture's `log_level: "info"` had been passing this whole time by coincidence (matching the same fallback), not because the read actually worked.
- **Fix:** `generate_config.py` now reads `log_level` directly from `/data/options.json` (exactly like every other option in this add-on) and writes `/tmp/cups-log-level.env` (`LOG_LEVEL="<raw>"` + `CUPS_LOG_LEVEL="<mapped>"`); `run.sh` sources this file instead of calling `bashio::config` directly. Same enum, same mapping, same "info" fallback for an invalid value — only the read mechanism changed.
- **Files modified:** `cups/generate_config.py`, `cups/run.sh`
- **Verification:** `internal/verify-cups-scaffold.sh`'s LogLevel assertions (both the `info` fixture and a separate `debug`-tier container) now pass empirically against a real container.
- **Committed in:** `e4c5ed6` (Task 3 commit)

**2. [Rule 1 - Bug] `cupsctl LogLevel=` had no retry for the same transient connection race printer registration already guards against**
- **Found during:** Task 3, same verification run as deviation 1
- **Issue:** `cupsd`'s admin interface can transiently reject the very first connection right after the post-fixup restart's own readiness check passes (confirmed live: `cupsctl: Unable to connect to server: Bad file descriptor`) — `run.sh`'s step 7 (`lpadmin`, printer registration) already has a 5x1s retry loop for exactly this race, but the `cupsctl LogLevel=` call (step 9) had none, so it could fail once and silently leave `cupsd.conf`'s `LogLevel` at its previous (stock `warn`) value with no visible error to the operator beyond a one-line log message.
- **Fix:** Added the same 5x1s retry loop around `cupsctl LogLevel=` that step 7 already uses for `lpadmin`.
- **Files modified:** `cups/run.sh`
- **Verification:** `internal/verify-cups-scaffold.sh`'s LogLevel assertions pass reliably across repeated runs.
- **Committed in:** `e4c5ed6` (Task 3 commit)

**3. [Rule 1 - Bug] Three timing races in my own new `verify-cups-scaffold.sh` assertions, plus a `pipefail`+`grep -q` SIGPIPE bug**
- **Found during:** Task 3, iterating on the plan's own verify-script additions to get them to pass empirically
- **Issue:** (a) The plan's LogLevel/passthrough/poller-running assertions checked `docker logs`/`cupsd.conf` state exactly once instead of polling, racing `run.sh`'s own internal readiness/retry windows (worse after fix #2 added a retry loop, which pushed later boot steps later in time). (b) Piping `docker logs "$C" | grep -qE ...` directly under this script's `set -o pipefail`: `grep -q` exits as soon as it finds a match, sending SIGPIPE to a still-writing `docker logs` process, which then reports a non-zero (141) exit that `pipefail` propagates as the *pipeline's* exit status — making the `if` branch report "no match" even when a match was genuinely found.
- **Fix:** Converted the affected one-shot checks into small poll loops (10-40 iterations x 1s), and switched every `docker logs ... | grep -q` pattern to capture `docker logs` output into a variable first, then grep the variable (matches the pattern the rest of the script already used for `docker exec ... cat` output).
- **Files modified:** `internal/verify-cups-scaffold.sh`
- **Verification:** Full Docker run passes `ALL CHECKS PASSED`, confirmed stable across two independent runs.
- **Committed in:** `e4c5ed6` (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — bugs, all discovered only because this task's own constraint required proving `internal/verify-cups-scaffold.sh` for real via Docker rather than trusting the plan's verify snippets on paper).
**Impact on plan:** No scope creep beyond what was necessary to make T2's own required empirical proof genuinely true rather than a false positive. `log_level`'s user-facing enum/default/mapping are exactly as the plan specified.

## Issues Encountered

- **`make update-version`'s known premature-tag bug recurred** (same class already documented in the `260927-r2j` quick task's SUMMARY): running `make update-version ADDON=cups VERSION=0.1.0-13` between committing T2 and T3 created+pushed an annotated tag `cups/v0.1.0-13` pointing at T2's commit (`57a9b7c`), whose `cups/config.yaml` still read `0.1.0-12` at that point — not T3's commit (`e4c5ed6`), which actually contains the `0.1.0-13` bump.
  - **Local fix applied:** deleted the local tag and recreated it pointing at `e4c5ed6` (`git tag -a cups/v0.1.0-13 e4c5ed6`) — confirmed via `git rev-parse cups/v0.1.0-13^{commit}` now resolving to `e4c5ed6`.
  - **Origin NOT fixed:** pushing the corrected tag (`git push origin cups/v0.1.0-13 --force`, and the delete-then-recreate two-step the `r2j` task used) was **blocked by this environment's auto-mode destructive-git-action classifier** (`[Git Destructive]`). Per the classifier's own instructions, no workaround was attempted. **The remote tag `cups/v0.1.0-13` on `origin` still points at the wrong commit (`57a9b7c`) and needs a manual `git push origin cups/v0.1.0-13 --force` (or delete+recreate) by the user or an agent with that permission.** No build workflow is triggered by pushing a tag (confirmed in `update-version.py`'s own docstring, same as `r2j`'s finding), so no bad image was built as a side effect — this is purely a release-marker correctness issue.
- Two `prettier` pre-commit auto-reformats occurred (T1 and T2 commits) — both were simple prose rewraps of `cups/DOCS.md`; each commit was re-staged and retried after the auto-fix, no content change beyond line-wrap.

## Next Phase Readiness

- `cups` add-on is on `0.1.0-13` with official branding, quieter+passthrough-capable logging, and print-job history — `internal/verify-cups-scaffold.sh` proves all three end-to-end against a real Docker container.
- Deploying/restarting this add-on on `haos-op3050-1` is explicitly out of scope for this task (per plan) and remains for the user to do separately.
- **Follow-up needed:** push the corrected `cups/v0.1.0-13` tag to `origin` (see Issues Encountered) — the local tag is already correct.
- The pre-existing `make update-version` premature-tag-push bug (now seen twice, in `260927-r2j` and here) may be worth a dedicated quick task to fix at the tooling level (tag creation deferred until after the version-bump commit lands) rather than being rediscovered/patched ad hoc each time it fires.

---

*Quick task: 260927-vbk*
*Completed: 2026-09-27*

## Self-Check: PASSED

- FOUND: cups/logo.png
- FOUND: cups/print-history-poller.py (executable bit set)
- FOUND: commit 2131bef
- FOUND: commit 57a9b7c
- FOUND: commit e4c5ed6
