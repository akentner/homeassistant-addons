---
phase: 24-ntfy-add-on-admin-gui
verified: 2026-11-02T18:30:00Z
status: gaps_found
score: 5/6 roadmap success criteria verified at HEAD (SC1 and SC3 hold at the delivered ntfy 2.36.0, break at HEAD ntfy 2.37.0)
covered_files:
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-01-PLAN.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-01-SUMMARY.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-02-PLAN.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-02-SUMMARY.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-03-PLAN.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-03-SUMMARY.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-04-PLAN.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-04-SUMMARY.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-05-PLAN.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-05-SUMMARY.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-06-PLAN.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-06-SUMMARY.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-07-PLAN.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-07-SUMMARY.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-08-PLAN.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-08-SUMMARY.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-09-PLAN.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-09-SUMMARY.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-10-PLAN.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-10-SUMMARY.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-11-PLAN.md"
  - ".planning/phases/24-ntfy-add-on-admin-gui/24-11-SUMMARY.md"
  - "internal/verify-ntfy-e2e.sh"
  - "internal/verify-ntfy-registration.sh"
  - "internal/verify-ntfy-scaffold.sh"
  - "ntfy/Dockerfile"
  - "ntfy/app/accounts.py"
  - "ntfy/app/authdb.py"
  - "ntfy/app/bootstrap.py"
  - "ntfy/app/contract.py"
  - "ntfy/config.yaml"
  - "ntfy/run.sh"
covered_digest: "v4:sha256:7ee5d26e73e7449d573fbd048d588e08cd2b140a915e0eb1c52b0e6c94870eea"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "The add-on at HEAD of main (ntfy 2.37.0-0) bootstraps the admin and baseline, serves a working admin GUI and passes its own Docker verifies (SC1 'local docker build verified', SC3 GUI reads auth.db, SC2 admin_user/admin_password bootstrap)"
    status: failed
    reason: >
      Upstream auto-bump 539d014 (chore(ntfy): update to 2.37.0, github-actions[bot], 2026-11-02, after the phase merge)
      moved ntfy's auth.db schema from 10 to 11 (upstream v2.37.0 user/manager_sqlite_schema.go: migration 10->11 only
      creates a new `topic` table). contract.SUPPORTED_AUTH_SCHEMA is pinned to 10, so AuthDb fails closed with
      db_unsupported: GET api/health answers status "degraded" / db.error db_unsupported / schema_version 11, every
      other read returns 503 db_unsupported, and bootstrap.wait_for_auth_db() times out after 60 s and skips
      everything ("auth.db not ready after 60 s, skipping bootstrap"). Result: no admin user, no baseline users/rules,
      no daily backup, GUI unusable. ntfy itself runs (healthy: true). With the same image built at 2.36.0 everything
      passes (scaffold exit 0, e2e 120/120). The pin worked as designed; nothing in the auto-update path checks it.
    artifacts:
      - path: "ntfy/app/contract.py"
        issue: "SUPPORTED_AUTH_SCHEMA = 10 (line 23); 2.37.0 writes schema 11"
      - path: "ntfy/app/bootstrap.py"
        issue: "wait_for_auth_db() uses check_schema()['supported'] -> bootstrap silently skipped on an unsupported schema (log line only)"
      - path: "ntfy/config.yaml, ntfy/build.yaml, ntfy/README.md"
        issue: "already at 2.37.0 / 2.37.0-0 / v2.37.0 on main"
    missing:
      - "Decide and implement schema 11 support: audit the 10->11 diff (additive `topic` table), accept {10, 11} in SUPPORTED_AUTH_SCHEMA (or a SUPPORTED set), extend the fake-ntfy fixture/schema tests, re-run both Docker verifies at 2.37.0"
      - "Guard the auto-update path against this class of break (e.g. a CI/verify step that builds the bumped image and runs verify-ntfy-scaffold.sh before the bump is published; today the bumped add-on is shipped untested)"
      - "Note for the migration: ntfy 2.37.0 migrates an existing auth.db 10->11 irreversibly at start, before the add-on's daily backup (the backup is skipped while the schema is unsupported). Consider a backup before the first start on a new schema."
  - truth: "The offline registration gate (internal/verify-ntfy-registration.sh) passes at HEAD"
    status: failed
    reason: >
      '✗ CHANGELOG.md has no header for 2.37.0-0'. The auto-update (internal/update-version.py) prepends the upstream
      release notes without a `## [X.Y.Z-N]` header (ntfy/CHANGELOG.md line 1 is body text; the only header is the
      hand-written `## [2.36.0-0]` at line 58), so the gate fails after every upstream bump. The gate is over-coupled
      to a hand-maintained header the bot never writes. Not wired into CI (no reference in .github/workflows,
      Makefile or pre-commit), so it breaks nothing automatically. The checks after it in the script (README
      release-shield, icon) were not reached; I ran them by hand: shield v2.37.0 matches build.yaml, icon 128x128 and
      identical to the GUI copy.
    artifacts:
      - path: "internal/verify-ntfy-registration.sh"
        issue: "line 'grep -q ^## [${version}] CHANGELOG.md' cannot hold for bot-generated entries"
      - path: "ntfy/CHANGELOG.md"
        issue: "no header for 2.37.0-0"
    missing:
      - "Drop or relax the CHANGELOG header check (or have the bump tooling write the header)"
deferred: []
human_verification:
  - test: "Install as local add-on on HA (UAT, D-14), version with a schema the GUI supports"
    expected: "Add-on starts from the local build; sidebar entry 'ntfy' appears (panel_admin); Supervisor log shows render_config, bootstrap 'admin user ... created' and baseline lines; no password in the add-on log"
    why_human: "Needs a real Supervisor; the Docker verifies simulate the ingress peer with NTFY_INGRESS_REMOTE=127.0.0.1"
  - test: "Open the GUI from the HA sidebar (desktop and mobile app), click through #/users, #/acl, #/matrix, #/tokens, #/tools, #/health, #/data"
    expected: "Views render in the ingress iframe with the HA-style look (light and dark), relative URLs work under /api/hassio_ingress/<token>/, no blank page or console errors, hash routing keeps working on reload"
    why_human: "Nothing was rendered in a browser by the phase (24-11 open point); the node tests use a fake DOM. Visual look, layout, dialogs are not machine-verifiable here"
  - test: "Direct access to the GUI port from the LAN: http://<HA-IP>:8099/ and http://<HA-IP>:8099/api/users; also via the ingress URL pasted into a plain browser tab without HA session"
    expected: "403 {error: ingress_only} for LAN access (port 8099 is not published anyway); the add-on answers only via HA ingress"
    why_human: "The real peer address 172.30.32.2 plus X-Ingress-Path set by the Supervisor was never exercised (gate is proven by pytest + Docker with a simulated peer, and by secrets-sync precedent)"
  - test: "Export download and backup download inside the ingress iframe (Data view: 'Download export' JSON and YAML, with and without password hashes; backup download link)"
    expected: "Browser downloads the file (anchors with the `download` attribute and relative hrefs work in the iframe); default export has no hashes; schema: 1"
    why_human: "download-anchor behaviour in the ingress iframe and in the Companion app is unchecked"
  - test: "Clipboard / CopyField for token values and the token reveal flow in the browser"
    expected: "Create token shows the value once and it can be copied (or falls back to select-all); list rows are hidden until 'Reveal'"
    why_human: "Clipboard API availability in the HA iframe context cannot be tested offline"
  - test: "Reverse proxy routing: repoint Cloudflared/Traefik for ntfy.akentner.de from f6c6b703-ntfy-server:8000 to 72a005f5-ntfy:8000; then curl https://ntfy.akentner.de/v1/health and publish/subscribe from the HA ntfy integration, the notebook client and Gatus"
    expected: "Health ok, publish and subscribe work with the migrated baseline users (homeassistant rw, akentner ro, gatus); web app / works with base_url https://ntfy.akentner.de (behind_proxy true)"
    why_human: "Needs the real network (Cloudflared/Traefik), DNS and the HA container network. Hostname 72a005f5-ntfy was only verified by computing sha1('https://github.com/akentner/homeassistant-addons')[:8] = 72a005f5, not against a running Supervisor"
  - test: "Check whether any client still uses http://<HA-IP>:8000 directly (HA ntfy integration, Gatus) - port 8000/tcp is not published by default (D-10)"
    expected: "Either no such client, or a host port is mapped in the HA add-on network settings"
    why_human: "Client inventory lives outside the repo"
  - test: "Install from the Supervisor store (GHCR image ghcr.io/akentner/homeassistant-addons/amd64-ntfy:<version>) once a tag/image exists"
    expected: "Image pull succeeds; ntfy/ add-on listed in the store with icon/logo, translations de/en show option labels"
    why_human: "Image publishing and store rendering need GitHub Actions + a real Supervisor; the first ntfy tag does not exist yet (CHANGELOG notes links follow the first tag)"
  - test: "CSP: confirm the GUI works under HA's ingress frame policy (the GUI sends no Content-Security-Policy header itself; only X-Content-Type-Options: nosniff and Cache-Control)"
    expected: "No console CSP violations; vendored module imports (static/vendor/preact-htm.mjs, dynamic import of views/*.mjs) load from the same origin"
    why_human: "Header behaviour of the HA ingress proxy is not reproducible offline"
  - test: "Migration from the old add-on: copy options 1:1 (remove listen_port and reset_data), start new add-on beside the old one; Test publish in the Health view"
    expected: "baseline_users become users with origin 'options'; test publish returns ok true (token for admin_user is created and removed); old and new add-on run side by side without port clash"
    why_human: "Real HA host, real old-add-on options and the user's decision on baseline_overwrite_passwords (default false)"
---

# Phase 24: ntfy add-on + admin GUI - Verification Report

**Phase Goal:** New `ntfy/` add-on based on upstream ntfy that exposes ntfy's server and auth configuration as add-on
options and ships an ingress-only admin GUI. Live ACLs, users and tokens live in ntfy's `auth.db` under `/data`; add-on
options carry only a baseline that is applied additively.
**Verified:** 2026-11-02T18:30:00Z (against `main` at HEAD, ntfy 2.37.0-0)
**Status:** gaps_found
**Re-verification:** No - initial verification

## Summary

Phase 24 as delivered (ntfy 2.36.0) achieves its goal: every decision D-01..D-18 is implemented, all hermetic suites are
green, and the Docker scaffold and E2E (120 checks against real ntfy) pass when the image is built at 2.36.0. However,
`main` now carries ntfy 2.37.0 (auto-bump `539d014`, after the phase merge), whose auth.db schema 11 is rejected by the
phase's own fail-closed schema pin: at HEAD the add-on starts ntfy but creates no admin and no baseline, and the GUI shows
"degraded / db_unsupported". Both Docker verifies fail at HEAD. This is a post-phase regression found while verifying
against HEAD, but it makes the shipped add-on non-functional, so it is recorded as a gap (BLOCKER for deploying / the UAT).
Everything that needs real Home Assistant is listed under `human_verification`.

## Commands actually run (evidence legend: CMD = verified by command, CODE = inferred from reading code, N/A = not verifiable here)

| # | Command | Result |
|---|---------|--------|
| 1 | `uv run --with pytest --with pyyaml python -m pytest ntfy/tests -q` | **327 passed** in 49 s, exit 0 (includes `test_js.py`, which runs the node tests) |
| 2 | `node --test ntfy/tests/js/*.test.mjs` (node v22.23.4) | **25 pass, 0 fail** |
| 3 | `make validate-versions validate-addons` | exit 0; "ntfy/ validation passed" |
| 4 | `python3 internal/validate-addon-config.py ntfy` | "Add-on config validation passed." exit 0 |
| 5 | `bash internal/validate-dockerfile-args.sh` | OK |
| 6 | `bash internal/verify-ntfy-registration.sh` | passes "root README and base-image config" and "translations en/de and DOCS.md cover every option", then **FAILS** `✗ CHANGELOG.md has no header for 2.37.0-0` (see gap 2) |
| 7 | `bash internal/verify-ntfy-scaffold.sh` at HEAD (build.yaml VERSION 2.37.0) | image built, "ntfy and GUI answer" OK, then **FAIL** `✗ api/health content` with `{'db': {'error': 'db_unsupported', 'schema_version': 11, 'supported': False}, 'ntfy': {'healthy': True}, 'status': 'degraded', 'counts': None}`, exit 1 |
| 8 | `bash internal/verify-ntfy-e2e.sh` at HEAD | image built, container started, then **FAIL** `✗ timeout waiting for bootstrap`, exit 1 (bootstrap skipped because schema 11 unsupported) |
| 9 | Same two scripts run from a scratch copy of `ntfy/` + `internal/` with only `build.yaml` args.VERSION set to 2.36.0 (no repo file modified) | scaffold: **all ✓, exit 0** ("health (schema 10) and admin user", gate, no password in server.yml/logs/PID 1 cmdline, GUI restart keeps container, ntfy death exits 1). e2e: **120 checks, 0 failed, "All ntfy e2e checks passed"**, exit 0 |
| 10 | `sha256sum ntfy/app/web/static/vendor/preact-htm.mjs` and `curl https://cdn.jsdelivr.net/npm/htm@3.1.1/preact/standalone.module.js \| sha256sum` | both `72284e8e9079c87817145df1110f74e8a2aa040b2fc384922e18dfcb46fc1fd7` (byte-identical to upstream) |
| 11 | `git log -i --grep=co-authored 6ace08a^..fd3cdfc` and on `ntfy/`, `.planning/phases/24-ntfy-add-on-admin-gui`, `internal/verify-ntfy-*` | no match in 55 commits of the PR #83 range / 65 commits touching the phase paths |
| 12 | `sha1('https://github.com/akentner/homeassistant-addons')[:8]` | `72a005f5` (HA add-on hostname prefix; consistent with `72a005f5-ntfy`) |

Cleanup: containers created by the scripts were removed by their own traps; I removed the `ntfy-verify:local` image I
(re)built and my scratch copy. Pre-existing containers `beautiful_leakey`, `cranky_kapitsa`, `epic_kare` and two
`secrets-sync-no-leak-verify*` containers (not mine, appeared during the run) were not touched.

## Roadmap success criteria

| SC | Verdict | Evidence |
|----|---------|----------|
| 1 Repo pattern, HA base image, bridge network, 3-file sync, local docker build, auto-update, registered | **VERIFIED for 2.36.0; HEAD degraded** | CMD 3/4/5: versions in sync (config `2.37.0-0`, build `2.37.0`, README shield `v2.37.0`), config valid. CODE: `ntfy/` has config.yaml, build.yaml, Dockerfile (HA base `ghcr.io/home-assistant/amd64-base:3.24`, upstream tarball with `sha256sum -c`, no bundled source), run.sh, README, DOCS.md, `.upstream.yaml`, `image:` key, `host_network: false`, `ports: 8000/tcp: null`, no `listen_port`. CMD 6: registered in root README (`### [ntfy](./ntfy)`) and `internal/base-image-config.yaml` (identical to gatus). Docker build succeeded 3 times (CMD 7/8/9). Auto-update works mechanically (bot commit `539d014` bumped 3 files) but shipped a version the add-on cannot use: gap 1. Hostname `72a005f5-ntfy`: computed, not run against a Supervisor |
| 2 Options pass-through and bootstrap | **VERIFIED at 2.36.0; FAILED at HEAD (gap 1)** | CODE: `render_config.py` maps base_url, enable_web_ui (`web-root` `/` or `disable`), behind_proxy, auth_default_access, cache_duration, attachment options; secrets never rendered; server.yml 0600. `bootstrap.py`: `ensure_admin` creates only when missing, never touches an existing password, empty `admin_password` logs and skips; `baseline.py`: additive via CLI, `baseline_overwrite_passwords` (default false) gates `user_change_pass`, origin-owned re-sync only while origin is `options`, removed entries become `gui`, never deletes. config.yaml: `password` type for `admin_password` and `baseline_users[].password`. CMD 1 (test_bootstrap, test_baseline, 120 e2e checks at 2.36.0, CMD 9). At HEAD bootstrap is skipped (CMD 8) |
| 3 Ingress-only GUI, CLI for writes, read-only SQLite for reads, no `/v1/users` | **VERIFIED at 2.36.0; GUI reads fail at HEAD (gap 1)** | CODE: `server.py` `_is_ingress()` = peer `172.30.32.2` AND `X-Ingress-Path`, applied in `_dispatch` before static, routing, body parsing, for every method (GET/HEAD/OPTIONS/POST/PUT/PATCH/DELETE); static whitelist + segment regex + `resolve().relative_to`; `index.html` uses `static/app.css`, `./icon`, `static/app.mjs` (relative), `lib/api.mjs` builds relative `api/` URLs; `grep -rn "v1/users" ntfy/app` empty; `AuthDb` connects `file:...?mode=ro` with 5 s timeout; schema pin `SUPPORTED_AUTH_SCHEMA = 10` checked by `ensure_supported()` before every read; writes via `NtfyCli` (list-form subprocess, no shell, `NTFY_PASSWORD` only in env, `env.pop` otherwise; `--password` appears nowhere in `ntfy/app`); `%`->`*` / `\_`->`_` mapping in `db_topic_to_cli`/`cli_topic_to_db`. Vendored htm/preact: sha256 matches upstream (CMD 10), both licence files present, README.txt records URL/version/hash; scan test rejects absolute URLs and raw HTML. CMD 9: gate test (403 without header and from foreign peer, path traversal blocked), no sentinel password in server.yml, docker logs or PID 1 cmdline. |
| 4 GUI features, guardrails, resets, backups, health | **VERIFIED at 2.36.0** (not usable at HEAD) | CODE: views `users, acl, matrix, tokens, tools, health, data` exist and call the routes in `contract.ROUTES` (23 routes; `test_registry` asserts registered == ROUTES and every frontend call has a route). `accounts.py` guardrails (`options_admin`, `last_admin`, `anonymous`; delete needs typed name + backup; demote protected refused; password change allowed); promote stashes rules in the sidecar after a backup and demote restores them with origins. `tokens.py`: list never carries values, reveal is `POST api/tokens/reveal` (audit-logged without value), create returns value once. `rights.py` evaluator, `topics.suggest` (16 chars `[A-Za-z0-9]`, default ACL homeassistant rw / akentner ro). `maintenance.py`: three resets with phrases `reset acls` / `clear cache` / `reset everything`, backup first, under `ctx.lock`; cache clear deletes `messages` rows and attachment files named like ids only; `reset_everything` refused while `admin_password` empty; test publish makes a 2-minute token and always removes it. `backups.py`: UTC-stamped names, `chmod 600/700`, rotation to `backup_keep` (default 10, schema `int(1,100)`), one `daily` per UTC day, validated download names. CMD 9: e2e 120 checks incl. 48 user/topic pairs agreeing with real ntfy status codes, guardrails, token lifecycle, backups/rotation, resets, cache clearing while ntfy runs |
| 5 Origin marker `gui\|options\|iac` in a sidecar | **VERIFIED** | CODE: `origins.py` (sidecar `origins.json` under `/data`, flock + reload on change, corrupt file renamed and treated as empty, unknown origin value = corrupt; default `gui`); baseline writes `options`; `iac` reserved, never written in this phase. CMD 1 (`test_origins`: corrupt file, unknown origin, stash pop, two-store regression); CMD 9 (e2e scenario 1: baseline origins `options` after first start, GUI-owned rules kept across restarts) |
| 6 Export schema 1, no secrets by default, optional hashes, never token values | **VERIFIED** | CODE: `exporter.py` `SCHEMA_VERSION = 1`, doc keys `schema, generated_at, source, server, users, acl, tokens`; token entries carry user/label/expires/origin only (no value, no id); hashes only with `include_hashes` (and that path is audit-logged); JSON and a deterministic stdlib YAML emitter; `docs/EXPORT_SCHEMA.md` documents the contract. CMD 1 (`test_exporter`: `test_no_secrets_without_hashes_in_any_format`, `test_hashes_only_on_request`); e2e at 2.36.0: no sentinel password in default export |

## Decision coverage D-01..D-18

| D | Status | Evidence |
|---|--------|----------|
| D-01 live data in `auth.db` | CODE+CMD | no write-back to options anywhere; Supervisor options API not referenced in `ntfy/app` |
| D-02 CLI/DB only, no `/v1/users`, no network admin password | CODE | `grep v1/users` empty; writes only through `NtfyCli`; test publish uses a short-lived token created via CLI |
| D-03 ingress only | CODE+CMD | see SC3; real Supervisor peer is human_verification |
| D-04 first admin from options, idempotent | CODE+CMD | `ensure_admin`; `test_existing_admin_password_not_touched`, `test_empty_password_skips_with_log` |
| D-05 baseline additive via CLI | CODE+CMD | no `auth-users`/`auth-access` in `render_config.py`; `baseline.py` never deletes |
| D-06 `baseline_users[]` same fields | CODE | config.yaml schema `username, password, topic, write_access`; `rw` when write_access else `ro` |
| D-07 options-only migration | CODE | DOCS.md migration guide (checked by registration gate: contains `72a005f5-ntfy`, `f6c6b703-ntfy-server`, `baseline_users`) |
| D-08 origin sidecar | CODE+CMD | SC5 |
| D-09 export schema 1 | CODE+CMD | SC6 |
| D-10 bridge network, no host port, no `listen_port` | CODE+CMD | config.yaml; scaffold manifest check "bridge network, port 8000 unpublished, no listen_port" at 2.36.0 |
| D-11 separate resets with typed phrase and backup | CODE+CMD | `maintenance.py`, `data.mjs` (`RESET_PHRASES`), `test_api_maintenance`, e2e |
| D-12 guardrails | CODE+CMD | `accounts.py`, `test_accounts`, `test_api_accounts` |
| D-13 token reveal on click, hidden by default | CODE+CMD | `tokens.py`, `tokens.mjs` (`post("tokens/reveal")`), tests |
| D-14 backups before destructive actions, daily at start, `backup_keep` | CODE+CMD | `backups.py`, `bootstrap.main` `create_daily()`; note daily backup is skipped while the schema is unsupported (gap 1) |
| D-15 cache/attachments options | CODE | `cache_duration`, `attachments_enabled` (default true), size/quota/expiry limits |
| D-16 vanilla JS + vendored Preact/htm, stdlib `ThreadingHTTPServer` | CODE+CMD | SC3 |
| D-17 GUI feature list | CODE+CMD | SC4 (visual rendering not verified here) |
| D-18 `baseline_overwrite_passwords` | CODE+CMD | `baseline.options_overwrite`, `test_flag_true_resets_password_each_run`, e2e at 2.36.0 |

## Run.sh / process model (D-10, plan 24-01 truth)

CODE: `run.sh` is the `with-contenv bashio` entrypoint and PID 1; starts `ntfy serve &`, `python3 -m app.bootstrap &`
(waits for auth.db), GUI under `gui_loop` (restart after 2 s); `wait "${NTFY_PID}"` then `exit 1` when ntfy dies; TERM/INT
trap stops children and exits 0. CMD 9: "GUI restarted, container kept running" and "ntfy death stops the container (exit 1)".

## Anti-pattern / debt scan

- `grep` for `TBD|FIXME|XXX` in `ntfy/` source: none reported by the checks I ran against the files read; not a systematic
  scan of every file (INFO).
- Passwords: `grep -rniE "(print|log\.|logging|audit)\b.*password" ntfy/app` -> only the "admin_password is empty" message and an
  audit line for hash export (no values). INFO: `token remove <user> <token>` passes the token value in the ntfy CLI
  argv inside the container (tokens, not passwords; documented behaviour of the CLI).
- No CSP header is set by the GUI server (INFO; see human_verification).
- Bookkeeping lag (INFO): ROADMAP.md plan checkboxes for 24-01..24-11 are still `[ ]` and STATE.md still says "Phase 24
  context gathered". Not a goal gap; to be updated by the orchestrator.

## Requirements coverage

ROADMAP lists `Requirements: TBD` for Phase 24; plan frontmatter uses D-01..D-18 and ROADMAP-SC1/3/6 as requirement IDs.
All are covered per the tables above. No orphaned requirement IDs.

## Gaps Summary

1. **BLOCKER (deployability at HEAD): schema pin vs ntfy 2.37.0.** Single root cause, post-phase: upstream 2.37.0 uses
   auth schema 11 (additive `topic` table). The add-on's fail-closed design correctly refuses to read an unknown schema,
   but at HEAD that means no bootstrap and an unusable GUI, and both Docker verifies are red. Fix is small in principle
   (audit 10->11, widen the supported set, extend tests and fixture, re-run both verifies) but is a decision for the
   maintainer; the auto-update pipeline has no guard that would have caught it. Phase-24 deliverables themselves are
   correct at the version they were verified against.
2. **WARNING: registration gate vs bot-written CHANGELOG.** `verify-ntfy-registration.sh` fails after every upstream bump
   because it demands a hand-written `## [version]` header. Not in CI; relax or generate the header.

No deferred items: Phases 25 (IaC API), 26 (admin-ui blueprint) and 27 (ntfy admin-ui lib migration) do not cover the
schema pin or the registration gate.

---

_Verified: 2026-11-02T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
