# Admin UI Blueprint documentation

This add-on is the blueprint for every admin GUI in this repository: a runnable demo behind Home Assistant ingress, a
shared browser lib (tokens, API client, Preact/htm components, i18n, optional HA theme sync), a Python server skeleton
and the rules that keep all GUIs alike. The demo only shows fake data and is not meant for production use.

## Repository exception

This add-on is our own code, not a wrapper around an upstream project. It therefore has no `.upstream.yaml`, no
auto-update and ships its scripts and the lib in the add-on directory (the repo-wide "no bundled source" rule does not
apply). Its image is built and published by CI like the others (`image:` key). The other repo rules still apply: HA base
image only, 3-file version sync via `make update-version`, and a local `docker build` before every commit that touches
the Dockerfile. Version bumps are manual.

One rule is added: the lib and the Python skeleton are copied into consumer add-ons only by `make sync-admin-ui`.
Consumer copies are never edited by hand, and the sources change only in this add-on.

## Rules

Each rule names the test or review that enforces it. The status says how far that enforcement goes today: `enforced`
means an automated check fails on a violation, `review` means only part of it is automated and the rest is a review
item, `unverified` means the claim depends on live Home Assistant behaviour that the spike has not recorded yet.

| ID   | Rule                                                                                                                                                                                 | Enforced by                                                                              | Status     |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- | ---------- |
| R-01 | Every request passes the ingress gate: peer 172.30.32.2 plus a non-empty `X-Ingress-Path`, otherwise 403 `ingress_only`, for every method and path. The GUI port is never published. | skeleton gate tests in `test_skeleton_server.py`, `internal/verify-admin-ui-scaffold.sh` | enforced   |
| R-02 | URLs are relative (no leading slash, no scheme). Download links use `apiHref`, and requests go only through the lib client.                                                          | scanner rule `urls`, `api.test.mjs`                                                      | enforced   |
| R-03 | State never goes into markup: text nodes only, no raw-markup APIs, no `eval`, no string timers.                                                                                      | scanner rule `markup`, component tests with hostile text                                 | enforced   |
| R-04 | Destructive actions need type-to-confirm: `ConfirmDialog` with `expected`, and the server answers `confirmation_required` when the phrase is missing.                                | ui tests, `test_demo_api.py`                                                             | enforced   |
| R-05 | The runtime is vendored and pinned by SHA-256: no CDN, no npm, no build step.                                                                                                        | scanner rule `vendor`, `test_static_rules.py`                                            | enforced   |
| R-06 | Every user-visible string goes through `t()` or `tp()`. German and English have identical keys and placeholders, and keys are never built dynamically.                               | `i18n.test.mjs`                                                                          | enforced   |
| R-07 | Dates, times, numbers, bytes and relative times use `Intl` through `format.mjs`.                                                                                                     | `format.test.mjs` for the lib, review for add-on code                                    | review     |
| R-08 | Colours come only from tokens and work in both themes. Text contrast is at least 4.5:1, and `prefers-color-scheme` is the default.                                                   | `test_css.py` (tokens, contrast, hex hygiene)                                            | enforced   |
| R-09 | Accessibility minimum: dialog role with focus move, trap and return, `aria-live` toasts, `role=alert` errors, labelled controls, `th scope`, visible focus, reduced motion.          | `a11y.test.mjs`, `ui.test.mjs`, `test_css.py`                                            | enforced   |
| R-10 | Storage keys are namespaced (`admin-ui:lang`, `<slug>:<key>`) and every access sits in try/catch.                                                                                    | scanner rule `storage`, `i18n.test.mjs`                                                  | enforced   |
| R-11 | No third-party scripts and no inline script, handler or style attribute, so the page stays CSP compatible. The CSP header is a default and promised only after spike item S9.        | scanner rule `csp`; live behaviour by spike item S9                                      | unverified |
| R-12 | Test duty: every GUI ships node tests for its views plus i18n parity and runs them in CI.                                                                                            | CI job for admin-ui (plan 26-09); existing add-ons follow in their migration phases      | review     |
| R-13 | HA theme and layout are progressive enhancement: own tokens and the fixed layout always work, theme sync and bridge only enhance, and any failure means the own theme.               | `theme_sync.test.mjs`, `ha_bridge.test.mjs`; live behaviour by the spike                 | unverified |
| R-14 | The backend returns stable error codes. The UI maps `errors.<code>`, unknown codes show a generic text plus `[code]`, and the backend `message` is never the primary text.           | `i18n.test.mjs` (`tError`), `test_demo_api.py`                                           | enforced   |
| R-15 | Lib and skeleton sources change only in `admin-ui/`. Consumer copies are never hand-edited, and the drift check fails on a mismatch.                                                 | `make check-admin-ui-sync`, `test_sync.py`                                               | enforced   |

Contrast became test-enforced in this phase: the original decision D-16 kept contrast a manual review item, and the
blueprint deliberately extends it (PD-03). The lib fixes the token pairs while extracting them from the ntfy GUI, and
`test_css.py` locks every text/background pair in both themes at 4.5:1.

## Library reference

The tables below list exactly what the modules export. `admin-ui/tests/js/lib_contract.test.mjs` compares the real
exports of every lib module with this list and `tests/test_docs.py` checks that every name appears on this page, so a
mismatch between this page and the code is a bug and turns a test red.

### Python skeleton

Package `app.web.skeleton` in this add-on, delivered to consumers as `app.web.admin_ui`. Standard library only, relative
imports only.

| Module       | Public names                                                                                                       |
| ------------ | ------------------------------------------------------------------------------------------------------------------ |
| `errors.py`  | `ERROR_STATUS` (error code to HTTP status), `ApiError(code, message, status)`, `register_error_code(code, status)` |
| `router.py`  | `Request` (`arg`, `body`), `Router` (`add`, `routes`, `match`), `Download(filename, content_type, data)`           |
| `static.py`  | `StaticFiles(root)` with `resolve(path)`, `SEGMENT_RE`, `CONTENT_TYPES`; extension whitelist and containment check |
| `ingress.py` | `INGRESS_REMOTE`, `is_ingress(peer, headers, remote)`, `ingress_user(headers)`                                     |
| `headers.py` | `DEFAULT_CSP`, `security_headers(kind, csp)`                                                                       |
| `server.py`  | `MAX_BODY`, `make_handler(router, static, ...)`, `make_server(router, static, port, ...)`, `serve(server)`         |

Handler results are a dict (200 JSON), a `(status, dict)` pair, `None` (204) or a `Download`. The gate runs first for
every method and path. API responses carry `Cache-Control: no-store`, static files `no-cache`, all responses `nosniff`,
and static files carry no `X-Frame-Options` because Home Assistant frames the page. Unexpected exceptions return
`500 internal_error` with the traceback on stdout only.

The demo API (`app/web/demo_api.py`) serves fake data for the gallery and the sample CRUD: `api/health`, `api/items`
with create, update and a type-to-confirm delete, `api/fail/<code>` for error states, `api/slow`, `api/whoami` and
`api/echo`.

### Browser lib

All modules live in `admin-ui/app/web/static/lib/`, one self-contained directory. Imports inside it are `./x.mjs` or
`./vendor/preact-htm.mjs` only.

| Module                             | Exports                                                                                                                                                                              |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `api.mjs`                          | `ApiClientError`, `buildUrl`, `request`, `get`, `post`, `put`, `patch`, `del`                                                                                                        |
| `ingress.mjs`                      | `isEmbedded`, `assertRelative`, `apiHref`, `errorKey`                                                                                                                                |
| `hooks.mjs`                        | `useAsync`, `usePoll`                                                                                                                                                                |
| `format.mjs`                       | `formatDateTime`, `formatRelative`, `formatBytes`, `formatNumber` (Intl based, epoch milliseconds)                                                                                   |
| `i18n.mjs`                         | `LANGS`, `LANG_STORAGE_KEY`, `detectLang`, `getLang`, `setLang`, `useLang`, `useT`, `t`, `tp`, `tError`, `registerStrings`                                                           |
| `strings.de.mjs`, `strings.en.mjs` | default export: flat object with dotted keys                                                                                                                                         |
| `color.mjs`                        | `parseColor`, `serializeColor`, `relativeLuminance`, `contrastRatio`, `isDarkColor`, `pickOnColor`                                                                                   |
| `theme-sync.mjs`                   | `createThemeSync`, `THEME_WHITELIST`                                                                                                                                                 |
| `ha-bridge.mjs`                    | `createHaBridge`                                                                                                                                                                     |
| `a11y.mjs`                         | `tabbables`, `nextTabTarget`, `useUid`                                                                                                                                               |
| `ui.mjs`                           | the Preact exports, `toast`, `Toasts`, `Modal`, `ConfirmDialog`, `confirmMatches`, `Badge`, `ErrorNote`, `Loading`, `CopyField`, `Tabs`, `DataTable`, `Field`, `useAsync`, `usePoll` |
| `shell.mjs`                        | `Topbar`, `LangSwitch`, `TabNav`, `ErrorBoundary`, `parseHash`, `useHashRoute`, `needsBurger`                                                                                        |

`Topbar` is sticky (together with the tab bar) and respects the bridge safe-area insets. With `views`, `activeId` and
`nav="topbar"` the navigation sits in the bar and folds into a burger menu when it does not fit; `nav="tabs"` (default)
keeps the tab bar. It shows the add-on icon (`./icon`, served from the add-on's `icon.png`) before the name and hides it
when the image fails to load; `iconSrc={null}` turns it off. The bar stays one compact row: children passed to `Topbar`
are hidden below 600 px, so put nothing essential there.

The formatters take the language as second argument. `formatDateTime(ms, lang, opts)` merges an optional `opts` object
(for example `timeZone`) into the `Intl.DateTimeFormat` options and `formatRelative(ms, lang, nowMs)` takes an optional
reference time. The bridge state exposes `kioskFrozen` (see the freeze guard below) and the status values `idle`,
`waiting`, `ok` and `no_answer`; the theme sync reports the reasons `ok`, `not_embedded` and `parent_inaccessible`.

`base.css` provides the tokens
`--bg --fg --card --bd --mut --ok --warn --err --acc --chip --hover --shadow --on-acc --on-err`. Light is the default on
`:root`, dark follows `prefers-color-scheme` unless `data-theme="light"` is set, and `data-theme="dark"` or `"light"`
forces a theme on any element. The tokens `bg card fg bd acc on-acc` read `var(--sync-x, <default>)`, which is the hook
for the optional theme sync. The class `.theme-isolated` neutralises inherited `--sync-*` values so a panel can show the
true tokens. Further classes: `.sr-only`, `.menu-btn`, `.lang-switch`, `.tablist`, `.tabpanel`, `.hint` and
`.badge.info`, next to everything extracted from the ntfy GUI.

String keys are flat and dotted with `{name}` placeholders and `.one` / `.other` plurals. The lib owns the namespaces
`btn`, `copy`, `dlg`, `state`, `errors`, `lang` and `nav`. An add-on registers its own strings from
`static/strings.{de,en}.mjs` with `registerStrings`. `t(key, params)` translates, `tp(key, n, params)` picks a plural,
`tError(err)` maps an `ApiClientError` to `errors.<code>` and falls back to the generic text plus `[code]`. The language
comes from the stored choice (key `admin-ui:lang`), then `navigator.language` (`de*` gives German), else English.

## Consumer recipe

For a new or migrating add-on:

1. Run `make sync-admin-ui ADDON=<name>`. It copies the lib to `<name>/app/web/static/vendor/admin-ui/` and the skeleton
   to `<name>/app/web/admin_ui/`, and writes a `LIB.stamp` into both.
2. Link the stylesheet `static/vendor/admin-ui/base.css` from the page, relative and without a leading slash.
3. Import components and helpers from `./vendor/admin-ui/ui.mjs` and the other lib modules, never from `vendor/` inside
   the lib.
4. Add `static/strings.de.mjs` and `static/strings.en.mjs` and register them with `registerStrings`. Keep the key sets
   identical.
5. Wire the server with `app.web.admin_ui`: build a `Router`, `StaticFiles` and call `make_server`. Never publish the
   GUI port in the manifest.
6. Run the rules scanner (`make check-admin-ui-rules`) and your node and pytest tests, and add them to CI.

## Distribution

The lib is distributed by copy because the Docker build context is the add-on directory. A consumer pulls a new lib
version deliberately: sync, then bump its own version.

- `LIB.stamp` in every consumer copy has two lines: `version <X.Y.Z>` and `sha256 <tree hash>`. The tree hash covers the
  sorted relative paths and the file hashes, and skips the stamp itself, `__pycache__` and `*.pyc`.
- `admin-ui/lib.lock` holds the version and the hashes of `lib/` and `skeleton/`.
- `make sync-admin-ui` refreshes the lock, `make sync-admin-ui ADDON=<name>` creates or updates one consumer.
- `make check-admin-ui-sync` runs the drift check for the pre-commit hook and CI.
- `make check-admin-ui-rules` runs the static rules scanner and `make test-admin-ui` the node and pytest suites. Both
  checks are members of `make check-all` and run as path-scoped pre-commit hooks, so the same commands run locally, in
  pre-commit and in CI.

| Situation of a consumer copy                    | Check result             |
| ----------------------------------------------- | ------------------------ |
| In sync with the lock                           | ok                       |
| Tampered copy (hash differs from its own stamp) | fails                    |
| Same version number but a different hash        | fails                    |
| Behind the current lib version                  | warns, exit code stays 0 |
| Behind, checked with `--strict`                 | fails                    |
| Ahead of the current lib version                | fails                    |

## HA integration

Everything here is progressive enhancement (R-13). Without Home Assistant around the page, in a direct tab, in a
dashboard card or after an HA update that changes the internals, the page keeps its own tokens and its fixed layout.

The protocol is undocumented and has no stability promise. It is read from the frontend source (`ha-panel-app.ts` and
the theme code) and is verified live only by the spike below. Minimum frontend versions: the bridge
(`subscribe-properties`, `kioskMode`) needs `20260128.0`, and `handleSafeArea` needs `20260729.0` (only that option).
Older hosts do not answer.

### Theme sync

`createThemeSync` is active only when `window.parent` differs from `window`. It reads five CSS variables of the parent
`documentElement` inside try/catch and writes `--sync-*` properties that `base.css` consumes:

| Own property  | Read from                    | Group   |
| ------------- | ---------------------------- | ------- |
| `--sync-bg`   | `--primary-background-color` | surface |
| `--sync-card` | `--card-background-color`    | surface |
| `--sync-fg`   | `--primary-text-color`       | surface |
| `--sync-bd`   | `--divider-color`            | surface |
| `--sync-acc`  | `--primary-color`            | accent  |

`--sync-on-acc` is derived from the accent with `pickOnColor`. The chip, hover, muted and status colours are never
synced: they form text-on-fill pairs whose counterpart HA does not expose, so the own validated defaults stay.

Values are parsed to numbers and written back as `#rrggbb` or `rgba()`, so a hostile theme value cannot inject CSS. A
group is applied only when its text/background pairs reach 4.5:1. HA's default accent `#009ac7` has about 3.26:1 on
white, so in the default light theme the accent group is skipped and the own accent stays; a dark theme with a lighter
accent passes. `data-theme` follows the relative luminance of `--primary-background-color` (dark below 0.179), never the
internal `hass.themes.darkMode` (D-12). An unparseable or non-opaque background removes everything the module wrote.
Changes are found through a `MutationObserver` on the parent `style` attribute, a poll every 3 seconds and refreshes on
focus and visibility changes.

### Bridge

`createHaBridge` subscribes with `home-assistant/subscribe-properties` and receives `home-assistant/properties` with
`narrow`, `safeAreaInsets` and `route`. Inbound messages count only from `window.parent` with an origin equal to the
page origin, and every field is validated. It also posts `toggle-menu` for the menu button of the own bar and `navigate`
for a validated single-slash path.

The own 56px bar stays. To avoid a second bar, the kiosk policy asks HA to hide its bar only when HA would draw one:

- Policy `narrow` (default): kiosk is requested from `narrow` transitions only. On a docked desktop sidebar it is never
  requested, because kiosk turns that sidebar into a modal drawer for as long as the page is open.
- Policy `never` never requests kiosk, policy `always` requests it from the start.
- A host-bar probe measures the top of the frame element. A value of at least 40 pixels plus the safe-area top means HA
  draws its own bar although `narrow` is false (hidden sidebar), and kiosk is requested. The probe result is sticky: it
  is not undone when kiosk hides HA's bar, only when `narrow` changes or `configure` is called.
- A freeze guard stops a loop: more than 4 kiosk transitions within 10 seconds freeze the state (`kioskFrozen`).

Without a valid answer within 1.5 seconds the status becomes `no_answer` and the fixed layout applies.

### Not guaranteed

- That the parent document is readable in every context (companion app web views, other front-end URLs, proxies).
- That the bridge exists on an HA version older than the minimum versions above, or stays unchanged after an update.
- That dashboard webpage cards work: their frame is sandboxed and does not run the message handler, and the ingress
  session may be refused. This stays unverified until spike item S13.
- That the kiosk drawer, `handleSafeArea` and the host-bar probe behave the same on all platforms (S5 and S6).
- That a CSP header is accepted by every setup (R-11, S9). The single panel run showed zero violations, but the header
  presence was not confirmed, so R-11 stays `unverified`.
- That theme changes are detected live (S3 not run) and that sync works outside the admin panel: the direct tab (S12),
  the dashboard card (S13) and the Companion app were not run.
- Observed so far (run A, desktop Chromium, panel, HA default dark theme, HA core 2026.10.4): the parent is readable,
  four of five variables parse, the divider variable is not read (`bd` null), the surface and accent groups are skipped
  by the contrast guard (own theme stays), the bridge answers, no host bar and no kiosk on a docked sidebar, and the
  identity headers arrive for an admin.

## Live spike results

The demo page is the instrument: a `#/spike` view that shows the parent access, the variables, the change counters, the
bridge messages and a copy-as-JSON result block. Results decide what the rules guarantee.

Verified on: HA core 2026.10.4 / frontend not recorded (2026-11-02)

Run A only (desktop Chromium, panel via ingress, add-on 0.1.0-2, HA default dark theme). Runs B to H were not done;
every item without evidence is `not-applicable` with a follow-up. Details: the dated log `spikes/ha-iframe-theme.md` in
the phase 26 planning directory.

| ID  | Check                                | How the demo page observes it                                           | Pass criterion                                                                       | Result                                                                                                                                                                      | Status         |
| --- | ------------------------------------ | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| S1  | Parent access                        | parent document read result and error name, `window.parent` comparison  | readable in the panel, reported as not embedded in a direct tab                      | Panel, parent readable (`readable_same`); direct-tab case belongs to S12                                                                                                    | verified       |
| S2  | Variable read                        | table of all whitelist variables with raw value and parse result        | present and parseable in light, dark, a custom theme and a new primary colour        | HA default dark only: 4 of 5 variables parsed, `bd` null (divider not read), surface and accent skipped by the contrast guard; light, custom and new primary colour not run | verified       |
| S3  | Change detection                     | counters for observer fires and poll differences while switching themes | token change within 1 second without reload, no loops                                | Not run: no theme switch during the run (observer 0, poll 76, apply 1), change detection unchecked. Follow-up: rerun with live theme switch                                 | not-applicable |
| S4  | Bridge                               | log of every properties message, resize across 870 pixels, rotation     | `narrow` flips at 870 pixels, insets set on notch devices, fallback works on silence | Limited: bridge answered, `narrow` false, insets present; flip at 870 px and rotation not run                                                                               | verified       |
| S5  | Double top bar                       | frame top measurement in docked, hidden-sidebar, narrow and kiosk modes | no double bar after the policy, menu button opens the drawer, HA restores on leaving | Docked sidebar only: host bar false, kiosk false; hidden sidebar, narrow and kiosk policies not run                                                                         | verified       |
| S6  | `handleSafeArea`                     | toggle re-subscribes with the option, insets displayed                  | confirms the safe-area handling on iOS and Android, default stays off                | Default off (`safe_area_off`); toggle on iOS and Android not run                                                                                                            | verified       |
| S7  | `navigate`                           | button posts a navigate message to the config page                      | HA navigates                                                                         | Not run (`not_run`). Follow-up: press the navigate button in a panel run                                                                                                    | not-applicable |
| S8  | Clipboard                            | `CopyField` over HTTP and HTTPS, in panel and card                      | copy works or the fallback message appears                                           | Not run (`not_run`). Follow-up: copy over HTTP and HTTPS, in panel and card                                                                                                 | not-applicable |
| S9  | CSP                                  | CSP header enabled, violation counter                                   | zero violations during gallery, CRUD and theme sync                                  | `violations_0` in the panel run, but presence of the CSP header was not confirmed, so this is weak evidence. Follow-up: check the response header in the network tab        | verified       |
| S10 | Storage                              | language survives a reload, behaviour with storage blocked              | no exception, the default language works                                             | Not run (`not_run`). Follow-up: reload test and run with storage blocked                                                                                                    | not-applicable |
| S11 | Admin and non-admin                  | `api/whoami` groups, open as non-admin with `panel_admin: false`        | panel visible and functional for non-admins                                          | Admin only: `identity_yes`, group `system-admin`; non-admin user not run                                                                                                    | verified       |
| S12 | Direct access                        | published port and ingress URL in a plain tab                           | port answers 403 `ingress_only`, ingress tab shows the own theme                     | Not run: only the ingress path inside the panel, no direct tab, no published port. Follow-up: plain-tab run                                                                 | not-applicable |
| S13 | Dashboard webpage card               | card pointing at the ingress URL                                        | record whether it is blocked and whether theme sync works                            | Not run: result block came from the panel, not from a dashboard card. Follow-up: webpage card run                                                                           | not-applicable |
| S14 | Language and theme switch while open | live switch                                                             | re-render without reload                                                             | Not run: `de_dark` is only the state, no live switch. Follow-up: switch language and theme with the page open                                                               | not-applicable |
| S15 | After an HA update                   | HA versions recorded per run                                            | re-run per HA release, dated rows in this table                                      | Limited: HA core 2026.10.4 recorded, frontend version missing; no run after an HA update yet                                                                                | verified       |

A run is recorded from the copy-as-JSON result block of the demo page. Record the HA core and frontend version, the
browser or companion app and the access path (panel, card, direct tab). Set the status to `verified`, `failed` or
`not-applicable`, fill the result cell and update the `Verified on:` line. A result may contain HA versions, the browser
or app, the access path and pass or fail. It must never contain tokens, real hostnames or user names.

### Testing the CSP in a live Home Assistant (S9)

1. **Find the header.** Open the add-on in Home Assistant (sidebar panel). In the browser developer tools open the
   Network tab, tick "Disable cache", filter by `hassio_ingress` and reload the page. Select the document request
   (`.../api/hassio_ingress/<token>/`, type `document`) and read the response header `Content-Security-Policy`. It must
   equal `DEFAULT_CSP` from `admin-ui/app/web/skeleton/headers.py`. The header is sent on the HTML page and on static
   files, not on `api/` responses. `curl` or a headless browser cannot test this: the ingress path needs a Home
   Assistant session, and the point is what HA and its proxies actually deliver.
2. **Header missing or different?** Then the result proves nothing. The container sends it unless the environment
   variable `ADMIN_UI_CSP` is `off` (`strict` is the default, read in `app/main.py`). The add-on has no options and
   `run.sh` does not set the variable, so a missing header means a proxy or HA changed it. Record that as the finding.
3. **Recognise violations.** Open the Console during the whole test. A violation shows as `Refused to load ...` or
   `Refused to execute inline ...` plus the violated directive, and the browser fires a `securitypolicyviolation` event.
   The counter of S9 counts only those events, only for this page's document, and only while the `#/spike` view is open
   (the listener lives in that view). Violations on other views, in the HA frame around it and anything that is only
   logged by HA are not counted: watch the Console there yourself.
4. **When a zero counter counts.** Only if step 1 confirmed the header, the page was loaded with the cache disabled, and
   the actions below were done. The smoke script (`internal/verify-admin-ui-scaffold.sh`) shows the header on the
   container itself (26-13 summary). That is not an observation of what HA or a proxy delivers, so it does not replace
   step 1.
5. **Actions during the test.** Open the gallery and use toast, modal and confirm dialog. Do the sample CRUD (create,
   edit, delete with type-to-confirm). Switch language and dark mode so theme sync applies. On `#/spike` press the
   bridge buttons (policy, `handleSafeArea`, navigate), copy a sample and run the storage and identity checks. Return to
   `#/spike` at the end and read the counter.
6. **Record it.** Update the S9 row with the date, the HA core version and the access path (panel, card, direct tab),
   and say whether the header was seen in the network tab. Set `verified` only with a confirmed header and no violation.
   The `Verified on:` line gets the same date.
7. **On a violation** the fix is a code change, not a setting: `DEFAULT_CSP` is a constant in
   `admin-ui/app/web/skeleton/headers.py` and cannot be changed through add-on options. Note the directive and the
   blocked kind (`inline`, `eval`, `self`, other), fix the page or loosen the constant deliberately, rerun
   `make test-admin-ui`, and run the test again. Do not switch the header off to get a green result.

The versions of S15 are filled in automatically where Home Assistant allows it: the HA core version is read from the
same-origin parent (`hass.config.version`), the add-on version from `api/health`, the browser from client hints or the
user agent. The result block marks each source as `auto`, `manual` or `not_recorded`. The HA frontend version is not
detected: Home Assistant only knows it as a build-time constant, so type it in from Settings, About. A typed value
overrides a detected one, and nothing is guessed.

## Migration paths

None of these is executed in this phase (D-07); they are the planned follow-up phases.

### ntfy

ntfy has its own `lib/api.mjs`, `lib/ui.mjs`, `lib/model.mjs`, `app.css`, `vendor/` and tests that duplicate the lib.
Steps: drop the duplicates, run `make sync-admin-ui ADDON=ntfy`, replace the English literals by strings with a German
and an English file, and keep only the ntfy-specific model and views. The look changes slightly because the lib tokens
fix the contrast of the old colours. Its frontend tests move into CI as part of that phase.

### secrets-sync

`secrets-sync` is a stdlib server with a vanilla-JS GUI of about 540 lines that uses `window.confirm()`. The end state
is a full rewrite on Preact/htm with the lib `ConfirmDialog` (type-to-confirm) instead of `confirm`, the skeleton for
the server, strings in two languages and its tests in CI. Risk: the rewrite is larger than a copy and needs its tests
ported first.

### haos-monitor

`haos-monitor` is a busybox/CGI GUI. The end state is a rebuild on the blueprint stack, a Python server plus Preact.
That phase also decides whether it gets the ingress gate. It is also missing from `internal/base-image-config.yaml`,
which is noted as follow-up only.

## Security notes

- The gate checks the peer address and the header. Spoofing the header requires reaching the unpublished port, which is
  why the port is never published.
- The ingress page shares the origin with Home Assistant: `localStorage` and `window.parent` are readable both ways.
  Therefore storage keys are namespaced and no third-party scripts are loaded.
- `X-Ingress-Path` is set by Home Assistant Core, not by the Supervisor.
- The `X-Remote-User-*` headers are informational only and never an authorisation decision.

## Follow-up

- ntfy switch-over to the lib.
- secrets-sync rewrite on Preact/htm.
- haos-monitor rebuild on the blueprint stack.
- Run the ntfy and secrets-sync frontend tests in CI.
- Add `haos-monitor` to `internal/base-image-config.yaml`.
- Icon and logo images for the add-on.
- Re-run the live spike for every HA release.
- Live spike follow-ups (only run A was done): S3 theme-change detection with a live theme switch; S4 and S5 narrow flip
  at 870 px, rotation, hidden sidebar and the three kiosk policies; S6 toggle on iOS and Android; S7 navigate; S8
  clipboard; S10 storage; S12 direct tab; S13 dashboard card; S14 live language and theme switch; non-admin run for S11;
  record the frontend version (the result block field `ha.frontend` showed the add-on version, do not use it).
- `bd` is null: find which parent variable and raw value the divider read returns and whether the whitelist
  (`--divider-color`) needs a correction.
- Check the CSP response header in the browser network tab before S9 counts as reliable evidence (R-11).
- R-07 stays `review`, no fix in phase 26. (1) `interpolate()` in `lib/i18n.mjs` inserts parameters with
  `String(params[name])`, so numeric parameters (`count`, `n`, `done`, `total`) are unformatted; fix: format
  `typeof number` through `formatNumber`, leave strings unchanged, with a test. (2) Add a scanner rule in
  `internal/check-admin-ui-rules.py` for `toLocale*`, `toFixed` and `Intl.*` outside `lib/format.mjs`; allow list:
  `lib/color.mjs` (CSS alpha), the result block in `spike.mjs` (`generatedAt` and counters are machine readable) and
  `Intl.PluralRules` in `lib/i18n.mjs`. After that R-07 could become `enforced`.
