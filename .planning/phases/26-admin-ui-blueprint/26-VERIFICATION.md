# Phase 26: admin-ui blueprint - Verification

**Verified:** 2026-11-02 (G-1 and G-3 fixed 2026-11-02) on branch `feat/admin-ui-blueprint` @ fa69315 (worker exec-26-verify)
**Method:** goal-backward; every check below was run in this worktree, not taken from the SUMMARYs.
**Status: `human_needed`**

The deliverables of the phase exist, are consistent and all automated gates are green. What is missing cannot be closed
by code: the live spike (D-14) was only partly done, so R-11 and R-13 stay `unverified`, and the first CI run on GitHub
has not happened. The S9 status inconsistency (G-1) and a stale follow-up line (G-3) were fixed afterwards.

## Phase goal

ROADMAP.md (this worktree) still says "Plans: 0 plans / TBD" and has **no Success Criteria** for Phase 26. The
criteria below are therefore derived from the goal text and D-01..D-17. The manager should refresh the ROADMAP entry in
the main checkout.

## Commands run

| Check                                                                   | Result                                                      |
| ----------------------------------------------------------------------- | ----------------------------------------------------------- |
| `make test-admin-ui` (node `--test` + pytest)                           | exit 0: 277 node tests pass, 266 pytest pass                |
| `make check-admin-ui-sync`                                              | exit 0, `OK admin-ui lock: 0.3.0`                           |
| `make check-admin-ui-rules`                                             | exit 0                                                      |
| `python3 internal/sync-admin-ui.py --check --strict`                    | exit 0 (no consumers yet, so nothing can be behind)         |
| `make validate-versions`                                                | exit 0, admin-ui 0.1.0 in config/build/README               |
| `make validate-addons`                                                  | exit 0, `admin-ui/ validation passed`                       |
| `make lint` (all pre-commit hooks)                                      | exit 2: only `terraform-bridge scaffold verify` fails       |
| `bash internal/verify-admin-ui-scaffold.sh`                             | exit 0, all steps passed (gate, demo, CRUD, CSP, SIGTERM)   |
| `git diff e4ec000..HEAD --stat -- ntfy secrets-sync haos-monitor`       | empty: no migration happened, the three add-ons are unchanged |

Docker: no admin-ui run was active (`docker ps` empty). After the verify run `admin-ui-verify:local` was removed and
no container or image of this check remains. Three exited containers of an unrelated image (`0d2622596df2`, 19 h old)
were already there and were not touched.

## terraform-bridge scaffold verify (red in `make lint`)

Not caused by this phase. `git diff e4ec000..HEAD -- terraform-bridge internal/verify-bridge-scaffold.sh` is empty. The
script fails in stage 1: image 84.9 MB against a 60 MiB cap (OPS-05), the Dockerfile last changed with the golang 1.27
tag bump (a039487). It is red on the base of this branch as well. The quick task summary noted the same.
Follow-up for another phase: raise the cap or slim the image.

## Success criteria (derived from the goal)

| #   | Criterion                                                                                          | Verdict      | Evidence                                                                                                         |
| --- | -------------------------------------------------------------------------------------------------- | ------------ | ---------------------------------------------------------------------------------------------------------------- |
| C1  | A real add-on `admin-ui` with a demo GUI exists and builds                                          | met          | config/build/Dockerfile/run.sh/README/DOCS present, validators green, image built and run by the verify script   |
| C2  | The blueprint fixes design and rules (dark/light, a11y, i18n, tests, ingress/security)              | met          | DOCS.md R-01..R-15 with enforcement column, `test_docs.py`, `test_css.py`, `a11y.test.mjs`, `i18n.test.mjs`      |
| C3  | A reusable lib ships (tokens/CSS, API client + ingress helper, components, Python skeleton)         | met          | `lib/*` (14 modules), `skeleton/*`, `lib_contract.test.mjs` pins the exports, documented in DOCS.md              |
| C4  | Lib distribution decided and implemented (copy + drift check)                                       | met          | `internal/sync-admin-ui.py`, `lib.lock`, `LIB.stamp`, tmp-repo tests in `test_sync.py`; no consumer copy yet     |
| C5  | Migration paths for ntfy, secrets-sync and haos-monitor are discussed, not executed                 | met          | DOCS.md "Migration paths"; empty diff for the three paths                                                         |
| C6  | Rules are enforced by tests, not only documented                                                    | met, 2 review | 12 of 15 `enforced`; R-07 and R-12 `review` by design                                                          |
| C7  | CI job for lib tests, pytest and sync check                                                         | met on paper | `admin-ui` job in `lint.yml` (read-only perms, pinned deps) and in `lint-results`; **never ran on GitHub**        |
| C8  | A live spike of HA theme/iframe access decides what the rules guarantee                             | partial      | run A only (see D-14); R-11 and R-13 remain `unverified`                                                          |

## Decisions D-01..D-17

| ID   | Verdict         | Evidence                                                                                                                                                                                   |
| ---- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| D-01 | met             | real add-on, ingress, `boot: manual`, `panel_admin: false`, no ports, no `.upstream.yaml`, HA base image `amd64-base:3.24`, version via `update-version` (0.1.0-4, 3-file sync green)      |
| D-02 | met             | demo views `gallery`, `tokens`, `language`, `crud`, `rules`, `spike` served (verify script step 5b); `views.test.mjs` sweeps; CRUD incl. error generator in `demo_api.py`                 |
| D-03 | met             | Preact/htm vendored in `lib/vendor/`, sha256 `72284e8e...` identical to ntfy's bundle; no CDN, no npm, no build step; scanner rule `vendor`                                                  |
| D-04 | met             | source in `admin-ui/app/web/static/lib/`; `api.mjs` byte-identical to ntfy's (`cmp`); demo imports only top-level lib modules (scanner rule)                                                  |
| D-05 | met             | copy to `<addon>/app/web/static/vendor/admin-ui/` and `.../admin_ui/`, `make sync-admin-ui`, drift check in hook + `check-all`; build context unchanged. No consumer exists yet, so only the fake-consumer test proves the copy path |
| D-06 | met             | `lib/VERSION` 0.3.0, `LIB.stamp` per copy, `lib.lock` (version + lib + skeleton hash), fail on tamper / same version different hash, warn on behind, `--strict` fails                       |
| D-07 | met             | DOCS.md migration section only; `git diff e4ec000..HEAD` touches no ntfy/secrets-sync/haos-monitor file                                                                                    |
| D-08 | met             | `detectLang` (stored, then `navigator.language`, `de*` to de, else en), switcher in topbar, key `admin-ui:lang` in try/catch; storage-blocked live run (S10) not done                         |
| D-09 | met             | `i18n.mjs` with `t/tp/tError`, `strings.{de,en}.mjs` in lib and demo; `i18n.test.mjs` enforces key and placeholder parity and used-key resolution                                          |
| D-10 | met             | `tError` maps `errors.<code>`, unknown code gives generic text plus `[code]`; `format.mjs` uses `Intl`. R-07 `review`: `interpolate()` does not format numeric params (documented follow-up) |
| D-11 | met in code, partly live | `theme-sync.mjs` inert unless `window.parent !== window`, whitelist, contrast guard, own theme on any failure (`theme_sync.test.mjs`). Live: run A only, 4 of 5 variables parsed, change detection (S3) not run |
| D-12 | met in code     | luminance of parent `--primary-background-color` sets `data-theme` (threshold 0.179), not `hass.themes.darkMode`; unit-tested, observed once live (dark)                                     |
| D-13 | met in code, partly live | 56px own topbar, `subscribe-properties`/`toggle-menu`/`navigate`, `event.source` + origin check, narrow-driven kiosk, probe, freeze guard, 1.5 s no-answer fallback (`ha_bridge.test.mjs`). Live: docked desktop only; narrow, hidden sidebar, kiosk, `handleSafeArea`, rotation not run |
| D-14 | **partial**     | Live spike done as run A only (desktop Chromium, panel, default dark theme, HA core 2026.10.4). S3, S7, S8, S10, S12, S13, S14 not run (`not-applicable`). Runs B..H not done. Plan 26-13 truth "S1..S15 run by a human on all contexts" is **not met**. Honestly documented in DOCS.md and the spike log; no rule or code was adjusted because the data did not contradict the design |
| D-15 | met             | rules cover dark/light + a11y, i18n, test duty, ingress/security (R-01..R-15)                                                                                                              |
| D-16 | met             | gate on every method/path (`test_skeleton_server.py`, verify script: 403 `ingress_only` without header and with foreign peer); static rules scanner (relative URLs, markup, vendor sha, storage, CSP); fake-DOM a11y tests for Modal/Confirm/Toast/Alert; contrast token test (`test_css.py`, stricter than the manual item in the decision) |
| D-17 | met on paper    | `admin-ui` job in `lint.yml` runs node tests, pytest, `make check-admin-ui-sync`; added to `lint-results`. The scanner runs inside pytest (`test_static_rules.py`), not as its own step. Never executed on GitHub; zizmor/actionlint results were taken from the 26-09 summary, not rerun here |

## Registration and structure

- Add-on files: `config.yaml`, `build.yaml`, `Dockerfile`, `run.sh`, `README.md`, `DOCS.md`, `CHANGELOG.md`,
  `icon.png`, `logo.png`, `.dockerignore`, `lib.lock`. No `.upstream.yaml` by design.
- Registered in root `README.md` (section "Admin UI Blueprint"), `CLAUDE.md` (own-code exception), `Makefile` (4 targets,
  `check-all` includes sync and rules), `.pre-commit-config.yaml` (Dockerfile ARG validator, sync hook, rules hook),
  `internal/base-image-config.yaml` (`admin-ui:` entry), `docs/DEVELOPMENT.md`, `lint.yml`.
- `internal/verify-admin-ui-scaffold.sh` exists and passes (stdlib gate, demo views, CRUD, error codes, whoami, vendored
  hash, CSP header present on the container, SIGTERM exit 0).

## Quick tasks (261102, parts 1-4)

Verified by the green suites and by reading the code and the summary:
sticky topbar with safe-area insets (`.shell-head`), `nav="topbar" | "tabs"` with burger, default icon (`icon.png`
shipped), mobile overflow fix (`measure-overflow.py`, 32 cases in Brave per the summary; **not re-run here**), CSP guide
and automatic spike versions, add-on info link. Lib is at 0.3.0, add-on at 0.1.0-4.

## Gaps

| ID  | Gap                                                                                                                                                                                                                                                                 | Severity | Fix                                                                                       |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------------- |
| G-1 | **Fixed.** S9 is now `not-applicable` in DOCS.md, the spike log and the 26-13 summary. Spike count: verified S1, S2, S4, S5, S6, S11, S15 (7, all limited); not-applicable S3, S7, S8, S9, S10, S12, S13, S14 (8). R-11 stays `unverified`. | fixed | docs commits after 90e1888 |
| G-2 | Plan 26-13 truth "matrix run on all contexts" and the claim `no item silently stays pending` are only met by relabeling to `not-applicable` with follow-ups. Accepted as documented, but it is not a pass of D-14.                                                    | medium   | Live runs B..H (human).                                                                   |
| G-3 | **Fixed.** The icon and logo follow-up line was removed from DOCS.md. | fixed | docs commits after 90e1888 |
| G-4 | ROADMAP.md Phase 26 entry is stale in this worktree (0 plans, TBD, no success criteria).                                                                                                                                                                            | info     | Manager updates it in the main checkout (outside this task).                              |

## Known honest gaps (not hidden)

- **D-14 live spike partial** (run A only). Not applicable: S3, S7, S8, S10, S12, S13, S14. S9 is `not-applicable` too: `violations_0`, but no
  confirmed CSP header, and the counter counts only while `#/spike` is open.
- **R-11 and R-13 `unverified`**, R-07 and R-12 `review` (R-07 follow-up: numeric interpolation and a scanner rule for
  `toLocale*`/`toFixed`/`Intl.*`).
- **Frontend version not readable** (HA only has it as a build constant; typed in manually). The `ha.frontend` field in
  the run A block holds the add-on version by mistake.
- **`bd` is null**: the divider variable is not read (whitelist `--divider-color` needs a check against the live raw value).
- **Info link / slug** (Supervisor `addons/self/info`) is tested with a fake only; S7 live is open.
- **CI job `admin-ui` never ran on GitHub.** The first push will show whether the pinned deps, Node 22 and the make
  target work there. `check-admin-ui-sync` runs without `--strict` in CI (right while no consumer exists).
- **No real consumer yet:** the copy path is proven by a fake consumer and by the lib being a plain directory, not by
  ntfy/secrets-sync/haos-monitor (follow-up phases).
- **terraform-bridge scaffold verify red**: see above, not caused by this phase.

## Follow-ups

1. Human runs B..H of the spike (narrow/hidden sidebar/kiosk, phone and Companion app, direct tab, dashboard card,
   non-admin, live theme and language switch, storage blocked); fill the S table; then decide R-11 and R-13.
2. See the CSP header in the network tab (DOCS.md guide), then set S9 (currently `not-applicable`).
3. ~~Fix G-1 and G-3~~ done.
4. Push once and read the first `admin-ui` CI run.
5. R-07 follow-up (numeric interpolation, scanner rule).
6. Check `bd` / `--divider-color`; add a frontend-version field fix to the result block.
7. Migration phases: ntfy switch-over, secrets-sync rewrite, haos-monitor rebuild, ntfy/secrets-sync tests in CI.
8. Separate: terraform-bridge image size cap (OPS-05).

## Verdict

**`human_needed`.** The artifacts, wiring, rules, tests, sync tooling, CI job definition and registration are in place
and verified by running them. No blocking code gap was found. Closing the phase fully needs the live spike runs and the
first CI run. Whether to mark the phase complete before that is the manager's call; the open items are stated above and
none of them is hidden.
