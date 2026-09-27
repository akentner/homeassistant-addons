---
quick_id: "260927-vbk"
slug: "cups-add-logo-png-banner-configurable-lo"
description: "cups: add logo.png banner, configurable log level with log passthrough, and print job history persistence"
date: "2026-09-27"
status: planned
---

# Quick Task: Official Branding Banner, Log-Level Passthrough, and Print-Job History

## Goal

Three independent, small enhancements to the `cups` add-on:

- **T1** — ship the official upstream CUPS brand mark as both `icon.png` (replacing the current placeholder) and a
  new `logo.png` banner.
- **T2** — quieten the default `log_level` and make cupsd's own file-based logs actually reach the add-on's log
  output (`ha apps logs`/`docker logs`), which nothing does today.
- **T3** — persist a simple, independent JSONL print-job history to `/data`, surviving restarts.

Do NOT deploy/restart the live add-on on `haos-op3050-1` — the user reviews and does that separately.

**Facts established this session — do not re-derive, treat as given:**

1. **`log_level` is NOT a new option — it already exists** (added in an earlier quick task this session, before this
   plan was written): `cups/config.yaml` already has `options.log_level: "info"` and
   `schema.log_level: "list(debug|info|warning|error)?"`, and `cups/run.sh` already maps it to a live `cupsctl
   LogLevel=...` call at container boot (case `debug`/`warning`/`error`/`*` -> `debug`/`warn`/`error`/`info`). T2
   does **not** recreate this option or its enum — it only (a) changes the shipped **default** from `info` to
   `warning` (the user's stated preference for quiet/normal operation — CUPS's own `warn` level) and (b) adds the
   genuinely-missing behavior: nothing today tails cupsd's `error_log`/`access_log` into the add-on's own log
   output, so `ha apps logs` never shows anything cupsd itself logs. That passthrough is what T2 actually builds.
2. **Branding source correction (supersedes any earlier icon-compositing idea from the old placeholder icon):**
   the official upstream CUPS brand mark — not a derivative composited from the add-on's current placeholder
   icon — must be used for both `icon.png` and `logo.png`. Two real, pre-verified PNG source files already exist
   on disk at
   `/tmp/akentner/claude-1000/-home-akentner-Projects-homeassistant-addons/fcaf8baf-5311-432a-a52b-2b744aa0f835/scratchpad/cups-assets/`:
   `cups-128.png` (128x128, 8-bit palette — sourced from `github.com/OpenPrinting/cups`, `desktop/cups-128.png` on
   the `2.4.x` branch) and `cups-256.png` (256x256, RGBA, same source, `desktop/cups-256.png`). **This exact
   scratchpad path belongs to the orchestrating session and may not be reachable from an isolated worktree
   executor's own filesystem** — if T1's first step cannot read both files at that path, STOP T1 and report back
   rather than attempting to `curl`/fetch them from GitHub directly (no guaranteed network access, and these were
   already downloaded and verified once — re-fetching risks a different revision).
   This also resolves the still-open todo `.planning/todos/pending/2026-09-26-cups-add-on-brand-icon-nachliefern.md`
   ("CUPS add-on brand icon nachliefern") — the current `cups/icon.png` is a placeholder black "C" mark, not the
   real CUPS branding; T1 replaces it with the genuine upstream mark.
3. Current `cups/config.yaml` version, confirmed by reading the file at plan-writing time: `0.1.0-12`. **Re-verify
   this yourself at execution time** (do not assume it is still `0.1.0-12` — this file has changed many times this
   session) before computing the one-subpatch bump in T3.

## Must-Haves

- [ ] `cups/icon.png` replaced with the official OpenPrinting/cups `cups-128.png` mark, byte-for-byte, still
      exactly 128x128
- [ ] `cups/logo.png` exists: 250x100, RGBA, transparent background, the official mark scaled to 92px height
      preserving aspect ratio (no stretch/distortion — "1:1 beibehalten"), centered both axes
- [ ] `cups/DOCS.md`'s icon-attribution line correctly cites `github.com/OpenPrinting/cups` (not the archived
      `apple/cups`) and mentions the new `logo.png` banner
- [ ] `cups/config.yaml`'s `options.log_level` default changed from `info` to `warning`; the existing
      `debug|info|warning|error` enum and existing `cupsctl LogLevel=` runtime mapping in `run.sh` are otherwise
      untouched
- [ ] `cups/run.sh` backgrounds `tail -F /var/log/cups/error_log` unconditionally after cupsd starts, and
      additionally `tail -F /var/log/cups/access_log` only when the resolved `log_level` is `debug`
- [ ] The add-on's shutdown trap also terminates both log-tail background processes (and, after T3, the
      print-history poller) — container shutdown stays clean, nothing is left blocking `wait "$CUPSD_PID"`
- [ ] `cups/translations/en.yaml` and `de.yaml`'s existing `log_level` descriptions updated to mention the new
      default and the passthrough behavior, in both languages
- [ ] `cups/print-history-poller.py` (new file) polls `lpstat -W completed -o` every ~20s, tracks the last-seen
      CUPS job id in `/data/print-history-state.json`, and appends one JSON line per newly-completed job to
      `/data/print-history.jsonl` — resilient to cupsd not yet being reachable (retry, never crashes the loop)
- [ ] First-ever run (no state file yet) baselines to the current max completed job id **without** backfilling
      history for jobs that already existed before the poller started
- [ ] `cups/run.sh` backgrounds `print-history-poller.py` (own retry/backoff, not gated on this script's own
      readiness poll) and the shutdown trap also terminates it
- [ ] `cups/Dockerfile`'s `COPY` line includes the new `print-history-poller.py`
- [ ] `cups/DOCS.md` documents `/data/print-history.jsonl`'s field list and the three known, deliberate
      limitations: `final_state` is always `"completed"` (CUPS's own `-W completed` classification already merges
      completed/canceled/aborted, and `lpstat -l`'s `Alerts:` field was empirically confirmed unreliable as a
      distinguishing signal during this feature's design — see T3's Action for the live test), `title`/
      `page_count` are always `null` (not exposed by any CLI text tool in this image without added IPP tooling),
      and there is no automatic rotation/pruning
- [ ] `cups` version bumped by exactly one subpatch, covering all three enhancements in a single bump, via
      `make update-version ADDON=cups VERSION=<current-version-plus-one-subpatch>` (explicit full `X.Y.Z-N`
      string, never bare `X.Y.Z`)
- [ ] `internal/verify-cups-scaffold.sh` extended with: (a) an assertion on cupsd.conf's `LogLevel` line for the
      fixture's configured level plus a separate debug-tier container proving `access_log` is additionally
      tailed only at `debug`, and (b) an assertion that a real completed print job gets recorded into
      `/data/print-history.jsonl` with the expected fields
- [ ] `internal/verify-cups-scaffold.sh` run for real (Docker) prints `ALL CHECKS PASSED`
- [ ] `make lint` and `make validate-addons` pass
- [ ] `python3 -c "import ast; ast.parse(...)"` passes for both `cups/generate_config.py` (unchanged, sanity
      check) and the new `cups/print-history-poller.py`
- [ ] No `Co-Authored-By` line in any commit (repo hard rule)

## Security Notes

- **T1** touches only two static, pre-verified binary asset files (no parsing of untrusted input, no new code
  path) — zero new attack surface.
- **T2** reads only fixed, root-owned local log file paths (`/var/log/cups/error_log`, `.../access_log`); no
  option value or other untrusted input is interpolated into the `tail` invocation. Passthrough makes cupsd's own
  log lines more *visible* (via the add-on's own log output) but does not create any new network exposure or new
  trust boundary — the same data already existed on disk. CUPS itself never writes credentials to
  `error_log`/`access_log`, so this does not risk leaking `admin_password`.
- **T3**'s poller calls `subprocess.run(["lpstat", "-W", "completed", "-o"], ...)` as an argv list (never
  `shell=True`, never a formatted/interpolated shell string) — matches this add-on's existing `shlex.quote`/
  argv-array discipline (T-21-01) elsewhere in `generate_config.py`. All paths it touches
  (`/data/print-history.jsonl`, `/data/print-history-state.json`) are hardcoded constants, never derived from any
  add-on option or other untrusted input, so there is no path-traversal surface. The state file is written
  atomically (temp file + rename) so a mid-write container kill cannot corrupt it into a state that replays
  history twice. `lpstat` output is parsed with a narrow, anchored regex (trailing `-<digits>` job-id suffix);
  unparseable lines are skipped, not fatal.

## Tasks

### T1: Official CUPS branding — `icon.png` + `logo.png`

**Files:** `cups/icon.png`, `cups/logo.png`, `cups/DOCS.md`

**Action:**

1. Confirm both source files are readable at
   `/tmp/akentner/claude-1000/-home-akentner-Projects-homeassistant-addons/fcaf8baf-5311-432a-a52b-2b744aa0f835/scratchpad/cups-assets/cups-128.png`
   and `.../cups-256.png`. **If either is missing/unreadable in your environment, STOP this task and report back**
   — do not attempt to `curl`/fetch them from GitHub as a substitute (see Goal's Fact 2).

2. Replace `cups/icon.png` with `cups-128.png`, byte-for-byte — this is already exactly 128x128, matching HA's
   `icon.png` spec exactly, no resizing/conversion needed:
   ```bash
   cp /tmp/akentner/claude-1000/-home-akentner-Projects-homeassistant-addons/fcaf8baf-5311-432a-a52b-2b744aa0f835/scratchpad/cups-assets/cups-128.png cups/icon.png
   ```
   This removes the old placeholder black-and-white "C" mark icon.

3. Generate `cups/logo.png` from `cups-256.png` using this exact recipe (Pillow; preserves aspect ratio —
   undistorted — per "1:1 beibehalten"; confirmed-good, reuse verbatim):
   ```python
   from PIL import Image
   icon = Image.open('/tmp/akentner/claude-1000/-home-akentner-Projects-homeassistant-addons/fcaf8baf-5311-432a-a52b-2b744aa0f835/scratchpad/cups-assets/cups-256.png').convert('RGBA')
   canvas = Image.new('RGBA', (250, 100), (255, 255, 255, 0))
   target_h = 92
   scale = target_h / icon.height
   target_w = int(round(icon.width * scale))
   icon_resized = icon.resize((target_w, target_h), Image.LANCZOS)
   x = (canvas.width - target_w) // 2
   y = (canvas.height - target_h) // 2
   canvas.paste(icon_resized, (x, y), icon_resized)
   canvas.save('cups/logo.png')
   ```
   Run via `uv run --with pillow python3 -c "..."` (confirmed available) or plain `python3` if Pillow is already
   importable in your environment.

4. In `cups/DOCS.md`, replace the very first line (currently: `Add-on icon is the official CUPS project logo
   (github.com/apple/cups), used under its Apache License 2.0.`) with:
   ```
   Add-on icon and logo banner use the official CUPS project mark (github.com/OpenPrinting/cups), used under its
   Apache License 2.0.
   ```
   (`apple/cups` is the archived predecessor; `OpenPrinting/cups` is the actual current upstream and the real
   source of these two asset files.)

5. No `config.yaml`/options-schema changes needed — HA auto-discovers `icon.png`/`logo.png` by filename
   convention alone.

**Verify:**
```bash
python3 -c "
from PIL import Image
im = Image.open('cups/icon.png')
assert im.size == (128, 128), im.size
print('icon.png OK', im.size, im.mode)
"
python3 -c "
from PIL import Image
im = Image.open('cups/logo.png')
assert im.size == (250, 100), im.size
assert im.mode == 'RGBA', im.mode
print('logo.png OK', im.size, im.mode)
"
grep -c 'OpenPrinting/cups' cups/DOCS.md   # expect >= 1
grep -c 'apple/cups' cups/DOCS.md          # expect 0
```

**Done:** `cups/icon.png` is the official 128x128 CUPS mark (not the old placeholder); `cups/logo.png` exists at
exactly 250x100 RGBA with the mark centered and undistorted; `cups/DOCS.md`'s attribution line correctly cites
`OpenPrinting/cups`.

---

### T2: Configurable log-level default + passthrough to the add-on's own log

**Files:** `cups/config.yaml`, `cups/run.sh`, `cups/translations/en.yaml`, `cups/translations/de.yaml`,
`cups/DOCS.md`, `internal/verify-cups-scaffold.sh`

**Action:**

1. In `cups/config.yaml`, under the `options:` block, change:
   ```yaml
     log_level: "info"
   ```
   to:
   ```yaml
     log_level: "warning"
   ```
   The `schema.log_level: "list(debug|info|warning|error)?"` line is unchanged.

2. In `cups/run.sh`, the current step 9 (`# 9. Map HA log_level option to a cupsctl LogLevel value.` through
   `cupsctl LogLevel="$CUPS_LOG_LEVEL" || log "cupsctl LogLevel failed"`) and step 10 (the final trap/wait) are:
   ```sh
   # 9. Map HA log_level option to a cupsctl LogLevel value.
   LOG_LEVEL=$(bashio::config 'log_level')
   case "$LOG_LEVEL" in
       debug) CUPS_LOG_LEVEL="debug" ;;
       warning) CUPS_LOG_LEVEL="warn" ;;
       error) CUPS_LOG_LEVEL="error" ;;
       *) CUPS_LOG_LEVEL="info" ;;
   esac
   cupsctl LogLevel="$CUPS_LOG_LEVEL" || log "cupsctl LogLevel failed"

   # 10. Forward termination signals to cupsd and wait on it -- the container
   #     stays alive exactly as long as cupsd does. Per D-08: no watchdog for
   #     the legacy-unicast reflector slot-exhaustion error is added here --
   #     with enable-reflector=no (the shipped default) that failure class
   #     cannot occur.
   trap 'kill -TERM "$CUPSD_PID" 2>/dev/null' TERM INT
   wait "$CUPSD_PID"
   ```
   Replace both with (step 9 unchanged, new step 10 inserted, old step 10 renumbered to 11):
   ```sh
   # 9. Map HA log_level option to a cupsctl LogLevel value.
   LOG_LEVEL=$(bashio::config 'log_level')
   case "$LOG_LEVEL" in
       debug) CUPS_LOG_LEVEL="debug" ;;
       warning) CUPS_LOG_LEVEL="warn" ;;
       error) CUPS_LOG_LEVEL="error" ;;
       *) CUPS_LOG_LEVEL="info" ;;
   esac
   cupsctl LogLevel="$CUPS_LOG_LEVEL" || log "cupsctl LogLevel failed"

   # 10. Tail cupsd's own file-based logs into this add-on's own stdout so
   #     `ha apps logs`/`docker logs` actually surface cupsd's logging --
   #     today nothing does this: cupsd's error_log/access_log under
   #     /var/log/cups/ are invisible outside the container. error_log is
   #     always tailed; access_log is ADDITIONALLY tailed only at the most
   #     verbose 'debug' tier (the level used for live diagnosis sessions).
   #     `-F` retries across a missing/not-yet-created or rotated file
   #     rather than exiting.
   tail -n +1 -F /var/log/cups/error_log 2>/dev/null &
   ERROR_LOG_TAIL_PID=$!
   ACCESS_LOG_TAIL_PID=""
   if [ "$LOG_LEVEL" = "debug" ]; then
       tail -n +1 -F /var/log/cups/access_log 2>/dev/null &
       ACCESS_LOG_TAIL_PID=$!
   fi

   # 11. Forward termination signals to cupsd and wait on it -- the container
   #     stays alive exactly as long as cupsd does. Per D-08: no watchdog for
   #     the legacy-unicast reflector slot-exhaustion error is added here --
   #     with enable-reflector=no (the shipped default) that failure class
   #     cannot occur. Also stops the log-tail background processes so
   #     container shutdown stays clean.
   trap 'kill -TERM "$CUPSD_PID" 2>/dev/null; kill -TERM "$ERROR_LOG_TAIL_PID" 2>/dev/null; [ -n "$ACCESS_LOG_TAIL_PID" ] && kill -TERM "$ACCESS_LOG_TAIL_PID" 2>/dev/null' TERM INT
   wait "$CUPSD_PID"
   ```
   (T3 below further edits this same region to add a step 12 print-history poller and extend the trap again —
   expected, sequential edits to the same file.)

3. In `cups/translations/en.yaml`, change:
   ```yaml
     log_level:
       name: Log Level
       description: Add-on log verbosity (debug, info, warning, error).
   ```
   to:
   ```yaml
     log_level:
       name: Log Level
       description: >-
         Add-on log verbosity (debug, info, warning, error). Default is warning for quiet
         operation. cupsd's error log is always forwarded to this add-on's own log output;
         the access log is additionally forwarded only at the debug level.
   ```
   In `cups/translations/de.yaml`, change:
   ```yaml
     log_level:
       name: Log-Level
       description: Ausführlichkeit der Add-on-Protokollierung (debug, info, warning, error).
   ```
   to:
   ```yaml
     log_level:
       name: Log-Level
       description: >-
         Ausführlichkeit der Add-on-Protokollierung (debug, info, warning, error). Standard ist
         warning für einen ruhigen Betrieb. Das error_log von cupsd wird immer in die eigene
         Log-Ausgabe dieses Add-ons weitergeleitet; das access_log zusätzlich nur bei debug.
   ```

4. In `cups/DOCS.md`'s `## Add-on Options` table, change the `log_level` row's default column from `` `info` ``
   to `` `warning` `` and expand its description to mention the passthrough behavior:
   ```
   | `log_level`       | `warning`    | Log verbosity: `debug`, `info`, `warning`, `error`. `error_log` is always tailed into the add-on's own log output; `access_log` is additionally tailed only at the `debug` tier. |
   ```
   Then, in `## Design notes`, insert a new paragraph directly after the existing **No slot-exhaustion watchdog
   (D-08).** paragraph and before **Generic driver, not driverless auto-detection.**:
   ```markdown
   **cupsd's own file-based logs are tailed into the add-on's log output (`log_level`).** Previously, cupsd's
   `error_log`/`access_log` under `/var/log/cups/` were invisible to `ha apps logs`/`docker logs` — nothing in
   this add-on ever surfaced them. `run.sh` now backgrounds `tail -F /var/log/cups/error_log` unconditionally,
   and additionally `tail -F /var/log/cups/access_log` only when `log_level: debug` is selected (the tier used
   for live diagnosis) — a quieter default (`log_level: warning`, mapped to CUPS's own `LogLevel warn`) keeps
   routine operation quiet while `debug` gives full request-level visibility on demand.
   ```

5. In `internal/verify-cups-scaffold.sh`, add a new section directly after the existing "Checking cupsd.conf
   ServerAlias (Host-header validation fix)..." block and before "Checking `<Location /admin>` gained the same
   Allow from lines...":
   ```bash
   yellow "Checking cupsd LogLevel reflects the configured log_level option..."
   if docker exec "${CONTAINER_NAME}" grep -qE '^LogLevel info$' /etc/cups/cupsd.conf; then
       green "   PASS: cupsd.conf LogLevel reflects the fixture's configured log_level=info"
   else
       red "   FAIL: cupsd.conf LogLevel does not reflect log_level=info"
       docker exec "${CONTAINER_NAME}" grep -i '^LogLevel' /etc/cups/cupsd.conf || true
       FAIL=1
   fi

   yellow "Checking cupsd error_log passthrough into the add-on's own log output..."
   if docker logs "${CONTAINER_NAME}" 2>&1 | grep -qE '^[EWID] \['; then
       green "   PASS: cupsd error_log lines appear in the add-on's own log output"
   else
       red "   FAIL: no cupsd error_log lines found in the add-on's own log output"
       FAIL=1
   fi
   if docker logs "${CONTAINER_NAME}" 2>&1 | grep -qE '"(GET|POST|PUT|HEAD) '; then
       red "   FAIL: access_log lines appear despite log_level=info (should only tail at the debug tier)"
       FAIL=1
   else
       green "   PASS: access_log not tailed at the non-debug log_level=info fixture"
   fi

   yellow "Checking debug-tier log_level additionally tails access_log (separate lightweight container)..."
   DEBUG_DATA_DIR="$(mktemp -d)"
   python3 -c "
   import json
   with open('${DATA_DIR}/options.json') as f:
       d = json.load(f)
   d['log_level'] = 'debug'
   with open('${DEBUG_DATA_DIR}/options.json', 'w') as f:
       json.dump(d, f)
   "
   DEBUG_CONTAINER_NAME="${CONTAINER_NAME}-debug"
   docker run --rm -d --name "${DEBUG_CONTAINER_NAME}" -v "${DEBUG_DATA_DIR}:/data" "${IMAGE_NAME}" >/dev/null
   DEBUG_READY=0
   for _ in $(seq 1 40); do
       if docker exec "${DEBUG_CONTAINER_NAME}" lpstat -r >/dev/null 2>&1; then
           DEBUG_READY=1
           break
       fi
       sleep 1
   done
   if [[ "${DEBUG_READY}" != "1" ]]; then
       red "   FAIL: debug-tier container did not become ready"
       FAIL=1
   else
       docker exec "${DEBUG_CONTAINER_NAME}" lpstat -v >/dev/null 2>&1 || true
       sleep 2
       DEBUG_LOGS=$(docker logs "${DEBUG_CONTAINER_NAME}" 2>&1)
       if echo "${DEBUG_LOGS}" | grep -qE '^[EWID] \['; then
           green "   PASS: error_log still tailed at the debug tier"
       else
           red "   FAIL: error_log not tailed at the debug tier"
           FAIL=1
       fi
       if echo "${DEBUG_LOGS}" | grep -qE '"(GET|POST|PUT|HEAD) '; then
           green "   PASS: access_log additionally tailed at the debug tier"
       else
           red "   FAIL: access_log not tailed at the debug tier"
           FAIL=1
       fi
       if docker exec "${DEBUG_CONTAINER_NAME}" grep -qE '^LogLevel debug$' /etc/cups/cupsd.conf; then
           green "   PASS: cupsd.conf LogLevel=debug applied for the debug tier"
       else
           red "   FAIL: cupsd.conf LogLevel not set to debug"
           FAIL=1
       fi
   fi
   docker rm -f "${DEBUG_CONTAINER_NAME}" >/dev/null 2>&1 || true
   rm -rf "${DEBUG_DATA_DIR}" >/dev/null 2>&1 || true
   ```

**Verify:**
```bash
python3 -c "
import yaml
d = yaml.safe_load(open('cups/config.yaml'))
assert d['options']['log_level'] == 'warning', d['options']['log_level']
print('config.yaml default OK')
"
bash -n cups/run.sh
grep -c 'ERROR_LOG_TAIL_PID' cups/run.sh    # expect >= 2 (assignment + trap)
grep -c 'ACCESS_LOG_TAIL_PID' cups/run.sh   # expect >= 2
bash -n internal/verify-cups-scaffold.sh
```
Full empirical proof (LogLevel + passthrough at both tiers) requires Docker and is deferred to T3's Verify, which
runs the complete `internal/verify-cups-scaffold.sh` once, after T3's own additions land too.

**Done:** `config.yaml`'s `log_level` default is `warning`; `run.sh` compiles (`bash -n`) and backgrounds both
tail processes with the trap extended to kill them; both translation files updated in both languages;
`DOCS.md`'s options table and Design notes updated; `verify-cups-scaffold.sh` compiles and contains the new
LogLevel/passthrough sections (full Docker run deferred to T3).

---

### T3: Print-job history persisted to `/data` as JSONL + version bump

**Files:** `cups/print-history-poller.py` (new), `cups/run.sh`, `cups/Dockerfile`, `cups/DOCS.md`,
`internal/verify-cups-scaffold.sh`, `cups/config.yaml`, `cups/build.yaml`, `cups/README.md`

**Action:**

1. **Empirical grounding (already established this session, do not re-derive):** a live test against this
   add-on's own base image (`ghcr.io/home-assistant/amd64-base:3.24` + `cups`/`cups-filters`) confirmed:
   - `lpstat -W completed -o`'s first whitespace-separated field is always `<printer>-<job-id>`, where `<job-id>`
     is CUPS's own always-numeric, always-last-hyphen-separated job id — true regardless of how many hyphens the
     printer name itself contains, so a single rightmost `-<digits>` split is always unambiguous.
   - `lpstat -l`'s `Alerts:` field is **not** a reliable final-state signal: a job that completed normally showed
     `Alerts: job-completed-successfully`, but a job explicitly canceled while genuinely queued (printer disabled
     via `cupsdisable`, then `cancel <job>`) showed `Alerts: none` — indistinguishable from an ordinary success by
     text alone. No `ipptool` (or any other IPP query client) is present in this image to query the job's real
     `job-state` IPP attribute instead. Given this, `final_state` is recorded as the fixed value `"completed"` for
     every job `lpstat -W completed -o` reports (CUPS's own `-W completed` filter already groups
     completed/canceled/aborted together) — this is a deliberate, documented simplification, not an oversight.
   - Neither `lpstat` nor `lpq` exposes the job's title/name or page count for a *completed* job in this image.
     `title`/`page_count` are therefore always recorded as `null`.

2. Create `cups/print-history-poller.py`:
   ```python
   #!/usr/bin/env python3
   """Poll cupsd for newly-completed print jobs and append one JSONL record
   per job to /data/print-history.jsonl.

   Deliberately lightweight (a periodic `lpstat -W completed -o` poll, NOT a
   CUPS notifier/subscription/D-Bus listener, which would be disproportionate
   for a single-printer home setup). State (the last-seen CUPS job id) is
   persisted to /data/print-history-state.json so a restart never replays
   already-recorded jobs.

   Empirically confirmed during this feature's design (live test against
   this add-on's own base image): lpstat's text output cannot reliably
   distinguish a canceled job from a normal completion -- a job explicitly
   canceled while queued showed `Alerts: none` in `lpstat -l`'s output,
   identical to what an ordinary success can also show. No IPP query client
   (e.g. ipptool) is present in this image to ask cupsd for the job's real
   `job-state` attribute instead. `final_state` is therefore always recorded
   as "completed" (CUPS's own `-W completed` filter already groups
   completed/canceled/aborted jobs together). `title`/`page_count` are also
   not exposed by any CLI text tool available here for a completed job, so
   both are always recorded as null. See cups/DOCS.md's Print History
   section for these documented limitations.
   """

   import json
   import re
   import subprocess
   import sys
   import time
   from datetime import datetime, timezone
   from pathlib import Path

   HISTORY_PATH = Path("/data/print-history.jsonl")
   STATE_PATH = Path("/data/print-history-state.json")
   POLL_INTERVAL_SECONDS = 20

   # Matches one line of `lpstat -W completed -o`'s short-form listing: the
   # first field is always "<printer>-<job-id>". CUPS's own job ids are
   # always numeric and always the LAST hyphen-separated component, so a
   # single rightmost split is unambiguous even when the printer's own name
   # contains hyphens (confirmed against CUPS's own naming convention, not a
   # guess -- see module docstring).
   JOB_TOKEN_RE = re.compile(r"^(?P<printer>.+)-(?P<jobid>\d+)$")


   def query_completed_jobs() -> list[tuple[str, int, str]] | None:
       """Return (printer, job_id, user) tuples for every job CUPS currently
       reports as completed/canceled/aborted (CUPS's own -W completed filter
       groups all three). Returns None -- not an empty list -- on any
       failure to reach cupsd, so callers can tell "no jobs" apart from
       "could not ask" (e.g. cupsd not up yet at add-on boot)."""
       try:
           result = subprocess.run(
               ["lpstat", "-W", "completed", "-o"],
               capture_output=True,
               text=True,
               timeout=10,
           )
       except (OSError, subprocess.TimeoutExpired) as exc:
           print(f"WARNING: lpstat invocation failed: {exc}", flush=True)
           return None

       if result.returncode != 0:
           print(
               f"WARNING: lpstat -W completed -o exited {result.returncode}: "
               f"{result.stderr.strip()}",
               flush=True,
           )
           return None

       jobs: list[tuple[str, int, str]] = []
       for line in result.stdout.splitlines():
           fields = line.split()
           if len(fields) < 2:
               continue
           match = JOB_TOKEN_RE.match(fields[0])
           if not match:
               continue
           jobs.append((match.group("printer"), int(match.group("jobid")), fields[1]))
       return jobs


   def load_last_seen_job_id() -> int | None:
       """Return the persisted last-seen job id, or None if no state file
       exists yet (first-ever run -- see establish_baseline())."""
       if not STATE_PATH.exists():
           return None
       try:
           data = json.loads(STATE_PATH.read_text())
           return int(data["last_seen_job_id"])
       except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
           print(f"WARNING: could not read {STATE_PATH}: {exc} -- treating as first run", flush=True)
           return None


   def save_last_seen_job_id(job_id: int) -> None:
       """Atomically persist `job_id` -- write to a temp file then rename, so
       a container killed mid-write never leaves a half-written state file
       behind."""
       tmp_path = STATE_PATH.with_suffix(".tmp")
       tmp_path.write_text(json.dumps({"last_seen_job_id": job_id}))
       tmp_path.replace(STATE_PATH)


   def append_history(printer: str, job_id: int, user: str) -> None:
       """Append one JSONL record for a newly-observed completed job.

       `timestamp` is this poller's OWN wall-clock time at the moment it
       first observed the job (not a parse of CUPS's own textual completion
       date, which is locale-dependent and not reliably parseable). At this
       poller's 20s interval the delta from actual completion is negligible
       for a simple home-use history log. See module docstring for why
       `title`/`page_count` are always null and `final_state` is always
       "completed".
       """
       record = {
           "timestamp": datetime.now(timezone.utc).isoformat(),
           "printer": printer,
           "job_id": job_id,
           "user": user or None,
           "title": None,
           "page_count": None,
           "final_state": "completed",
       }
       with HISTORY_PATH.open("a") as f:
           f.write(json.dumps(record) + "\n")
           f.flush()


   def poll_once(last_seen_job_id: int) -> int:
       """Run one poll cycle. Returns the new last-seen job id (unchanged if
       the poll failed or found nothing new)."""
       jobs = query_completed_jobs()
       if jobs is None:
           return last_seen_job_id

       new_jobs = sorted((j for j in jobs if j[1] > last_seen_job_id), key=lambda j: j[1])
       for printer, job_id, user in new_jobs:
           append_history(printer, job_id, user)
           print(f"INFO: recorded completed job {printer}-{job_id} (user={user})", flush=True)

       if new_jobs:
           last_seen_job_id = new_jobs[-1][1]
           save_last_seen_job_id(last_seen_job_id)
       return last_seen_job_id


   def establish_baseline() -> int | None:
       """First-ever run (no state file): baseline to the CURRENT max
       completed job id WITHOUT emitting history lines for jobs that already
       existed before this poller started -- a forward-only history, not a
       retroactive backfill. Returns None (retry next cycle) if cupsd could
       not be reached yet."""
       jobs = query_completed_jobs()
       if jobs is None:
           return None
       baseline = max((job_id for _, job_id, _ in jobs), default=0)
       save_last_seen_job_id(baseline)
       print(f"INFO: first run -- baselining at job id {baseline} (no retroactive backfill)", flush=True)
       return baseline


   def main() -> None:
       last_seen_job_id = load_last_seen_job_id()
       while last_seen_job_id is None:
           last_seen_job_id = establish_baseline()
           if last_seen_job_id is None:
               time.sleep(POLL_INTERVAL_SECONDS)

       while True:
           try:
               last_seen_job_id = poll_once(last_seen_job_id)
           except Exception as exc:  # noqa: BLE001 -- must never crash this loop
               print(f"WARNING: print-history poll cycle failed: {exc}", flush=True)
           time.sleep(POLL_INTERVAL_SECONDS)


   if __name__ == "__main__":
       sys.exit(main())
   ```

3. In `cups/run.sh`, insert a new step 11 between T2's step 10 (log-tail) and the renumbered trap/wait step
   (T2 renumbered it to 11 — it becomes 12 here), and extend the trap again:
   ```sh
   # 11. Background: poll cupsd for newly-completed print jobs and persist a
   #     simple JSONL history to /data/print-history.jsonl (see
   #     print-history-poller.py's own module docstring for the documented
   #     lpstat-text-output limitations). Started here rather than gated on
   #     this script's own readiness poll -- the poller does its own
   #     retry/backoff if cupsd is not yet reachable.
   python3 /print-history-poller.py &
   PRINT_HISTORY_POLLER_PID=$!

   # 12. Forward termination signals to cupsd and wait on it -- the container
   #     stays alive exactly as long as cupsd does. Per D-08: no watchdog for
   #     the legacy-unicast reflector slot-exhaustion error is added here --
   #     with enable-reflector=no (the shipped default) that failure class
   #     cannot occur. Also stops the log-tail and print-history-poller
   #     background processes so container shutdown stays clean.
   trap 'kill -TERM "$CUPSD_PID" 2>/dev/null; kill -TERM "$ERROR_LOG_TAIL_PID" 2>/dev/null; [ -n "$ACCESS_LOG_TAIL_PID" ] && kill -TERM "$ACCESS_LOG_TAIL_PID" 2>/dev/null; kill -TERM "$PRINT_HISTORY_POLLER_PID" 2>/dev/null' TERM INT
   wait "$CUPSD_PID"
   ```

4. In `cups/Dockerfile`, change:
   ```dockerfile
   COPY run.sh generate_config.py /
   ```
   to:
   ```dockerfile
   COPY run.sh generate_config.py print-history-poller.py /
   ```

5. In `cups/DOCS.md`, insert a new `## Print History` section directly after the `### Printer driver` subsection
   ends and before `## Design notes` begins:
   ```markdown
   ## Print History

   Every completed print job is appended as one JSON line to `/data/print-history.jsonl` (survives add-on
   restarts/updates, since `/data` is this add-on's persistent volume). A lightweight background poller
   (`print-history-poller.py`, started by `run.sh`) queries `lpstat -W completed -o` every ~20 seconds and tracks
   the last-seen CUPS job id in `/data/print-history-state.json` so a restart never replays already-recorded
   jobs. On the very first-ever run (no state file yet), the poller baselines to whatever jobs already exist at
   that moment WITHOUT backfilling them — this is a forward-only history, not a retroactive import.

   Each JSONL line has these fields:

   | Field | Type | Notes |
   | --- | --- | --- |
   | `timestamp` | ISO 8601 string (UTC) | When the poller observed the job as completed, not CUPS's own (locale-dependent, unreliable to parse) completion time |
   | `printer` | string | The CUPS destination name |
   | `job_id` | integer | CUPS's own job id |
   | `user` | string or `null` | Submitting user, from `lpstat`'s output |
   | `title` | `null` (always) | See Known limitations below |
   | `page_count` | `null` (always) | See Known limitations below |
   | `final_state` | `"completed"` (always) | See Known limitations below |

   ### Known limitations (print history)

   - **`final_state` does not currently distinguish canceled/aborted jobs from a normal completion.** CUPS's own
     `lpstat -W completed` classification already groups completed, canceled, and aborted jobs together, and this
     add-on confirmed empirically (during this feature's design) that `lpstat -l`'s `Alerts:` field is not a
     reliable text signal either — a job explicitly canceled while queued showed `Alerts: none`, indistinguishable
     from a normal successful completion. Disambiguating these three states reliably would require an IPP client
     (e.g. `ipptool`, not present in this image) querying the job's `job-state` attribute directly — out of
     proportionate scope for this add-on's single-printer home use case.
   - **`title`/`page_count` are always `null`.** Neither is exposed by any CUPS CLI text tool available in this
     image (`lpstat`, `lpq`) for a completed job, without the same additional IPP tooling noted above.
   - **No automatic rotation or pruning of `print-history.jsonl`.** It grows indefinitely; prune it manually if
     it becomes large.
   ```

6. **Version bump** — read the CURRENT version out of `cups/config.yaml` yourself first (verify it, do not
   assume it is still `0.1.0-12` — this file has changed multiple times this session). This single bump covers
   all of T1/T2/T3 together. Run:
   ```bash
   make update-version ADDON=cups VERSION=<current-version-plus-one-subpatch>
   ```
   Always pass the explicit full `X.Y.Z-N` string, never a bare `X.Y.Z` (root `CLAUDE.md` hard rule — a bare
   version has previously corrupted a release tag in this exact repo). This command also attempts to create/push
   a git tag; if the push step fails (no remote credentials in this environment), that is non-fatal — the three
   version files being correctly updated on disk is what matters. Note any skipped/failed tag push in the
   SUMMARY.

7. In `internal/verify-cups-scaffold.sh`, add a new section after the "Checking printer UUID stability across a
   real container restart..." section and before the final `if [[ "${FAIL}" == "1" ]]; then ... fi` block:
   ```bash
   yellow "Checking print-history poller (Task C: print-history.jsonl)..."
   if docker exec "${CONTAINER_NAME}" test -f /print-history-poller.py; then
       green "   PASS: /print-history-poller.py present in the image"
   else
       red "   FAIL: /print-history-poller.py missing"
       FAIL=1
   fi
   if docker exec "${CONTAINER_NAME}" sh -c 'ps aux | grep -v grep | grep -qF print-history-poller.py'; then
       green "   PASS: print-history-poller.py is running as a background process"
   else
       red "   FAIL: print-history-poller.py is not running"
       FAIL=1
   fi

   # A real, instantly-completing print job directly against cupsd (a
   # throwaway "verify-history-printer" using file:///dev/null -- distinct
   # from this add-on's own testprinter/brlasertest fixtures above, whose
   # device URIs are deliberately unreachable TEST-NET addresses and would
   # never actually complete), so the poller has a real completed job to
   # observe.
   docker exec "${CONTAINER_NAME}" lpadmin -p verify-history-printer -v file:///dev/null -E -m drv:///sample.drv/generic.ppd >/dev/null 2>&1 || true
   docker exec "${CONTAINER_NAME}" sh -c 'echo verify-history-payload > /tmp/verify-history.txt'
   docker exec "${CONTAINER_NAME}" lp -d verify-history-printer -t "verify-history-job" /tmp/verify-history.txt >/dev/null 2>&1 || true

   yellow "   waiting up to 40s for the poller to record the job in print-history.jsonl..."
   HISTORY_SEEN=0
   for _ in $(seq 1 40); do
       if [[ -f "${DATA_DIR}/print-history.jsonl" ]] && grep -qF "verify-history-printer" "${DATA_DIR}/print-history.jsonl"; then
           HISTORY_SEEN=1
           break
       fi
       sleep 1
   done
   if [[ "${HISTORY_SEEN}" == "1" ]]; then
       green "   PASS: print-history.jsonl recorded the verify-history-printer job"
       grep -F "verify-history-printer" "${DATA_DIR}/print-history.jsonl" | tail -1 > "${DATA_DIR}/.verify-history-line.json"
       if python3 -c "
   import json
   with open('${DATA_DIR}/.verify-history-line.json') as f:
       d = json.loads(f.read())
   assert d.get('printer') == 'verify-history-printer', d
   assert isinstance(d.get('job_id'), int), d
   assert 'timestamp' in d, d
   assert d.get('final_state') == 'completed', d
   print('OK')
   " | grep -q OK; then
           green "   PASS: print-history.jsonl line has the expected fields"
       else
           red "   FAIL: print-history.jsonl line missing expected fields"
           FAIL=1
       fi
   else
       red "   FAIL: print-history.jsonl did not record the job within 40s"
       FAIL=1
   fi

   if [[ -f "${DATA_DIR}/print-history-state.json" ]]; then
       green "   PASS: print-history-state.json exists under /data"
   else
       red "   FAIL: print-history-state.json missing under /data"
       FAIL=1
   fi
   ```

**Verify:**
```bash
python3 -c "import ast; ast.parse(open('cups/print-history-poller.py').read())"
python3 -c "import ast; ast.parse(open('cups/generate_config.py').read())"
bash -n cups/run.sh
grep -c 'print-history-poller.py' cups/run.sh       # expect >= 1
grep -c 'print-history-poller.py' cups/Dockerfile   # expect 1
grep 'version:' cups/config.yaml
grep 'VERSION:' cups/build.yaml
make lint
make validate-addons
```
Full empirical run requires Docker (~5-6 min, covers T1/T2/T3's combined assertions) and is the actual proof
this whole plan works end-to-end — run it for real, after all of T1/T2/T3 have landed:
```bash
bash internal/verify-cups-scaffold.sh
```

**Done:** `cups/print-history-poller.py` parses as valid Python; `run.sh` backgrounds it and the extended trap
kills it; `cups/Dockerfile`'s `COPY` line includes it; `cups/DOCS.md` documents the JSONL fields and the three
known limitations; `cups/config.yaml`/`cups/build.yaml` report a version exactly one subpatch above whatever was
read at the start of this task; `make lint` and `make validate-addons` pass; a full
`internal/verify-cups-scaffold.sh` run (Docker available) prints `ALL CHECKS PASSED`, including the new
LogLevel/passthrough assertions from T2 and the print-history assertions from T3.

## Files Changed

- `cups/icon.png` (replaced with the official OpenPrinting/cups 128x128 mark)
- `cups/logo.png` (new — 250x100 banner composited from the official 256x256 mark)
- `cups/config.yaml` (`log_level` default `info` -> `warning`; version bump)
- `cups/run.sh` (log-tail passthrough processes; print-history poller background process; shutdown trap
  extended to kill all three new background PIDs; steps renumbered 9-12)
- `cups/translations/en.yaml` / `de.yaml` (`log_level` description updated in both languages)
- `cups/print-history-poller.py` (new)
- `cups/Dockerfile` (`COPY` line includes the new poller script)
- `internal/verify-cups-scaffold.sh` (LogLevel/passthrough assertions; print-history assertions)
- `cups/DOCS.md` (icon attribution line; `log_level` table row + Design notes paragraph; new `## Print History`
  section)
- `cups/build.yaml` / `cups/README.md` (version bump via `make update-version`, subpatch bump only)

## Out of Scope

- Deploying or restarting this add-on on `haos-op3050-1` — deployment happens separately, later, not part of
  this task
- CUPS's own `page_log`/`PageLogFormat`/`PreserveJobHistory` mechanism, and a full CUPS notifier/subscription/
  D-Bus listener — both explicitly rejected approaches for the print-history feature (disproportionate for a
  single-printer home setup)
- Reliable disambiguation of canceled/aborted vs. a normal completion in `final_state` — would require an IPP
  query client not present in this image; documented as a known limitation instead
- `title`/`page_count` extraction for print-history entries — not exposed by any available CLI text tool without
  the same added IPP tooling; documented as a known limitation instead
- Automatic rotation/pruning of `print-history.jsonl` — documented as a known limitation, not implemented
- A new user-facing config option gating the print-history poller — deliberately always-on, per this task's own
  brief
- `network-tools/` or any other add-on — untouched
- Phase 21's still-pending old-add-on removal — untouched
