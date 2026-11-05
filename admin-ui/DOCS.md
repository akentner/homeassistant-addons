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

One rule is added: the lib and the Python skeleton are copied into consumer add-ons only by `make sync-admin-ui` or
`make release-admin-ui-lib` (both use the same sync script). Consumer copies are never edited by hand, and the sources
change only in this add-on.

## Rules

Each rule names the test or review that enforces it. The status says how far that enforcement goes today: `enforced`
means an automated check fails on a violation, `review` means only part of it is automated and the rest is a review
item, `unverified` means the claim depends on live Home Assistant behaviour that the spike has not recorded yet.

| ID   | Rule                                                                                                                                                                                                                                                                                                                                       | Enforced by                                                                              | Status     |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- | ---------- |
| R-01 | Every request passes the ingress gate: peer 172.30.32.2 plus a non-empty `X-Ingress-Path`, otherwise 403 `ingress_only`, for every method and path. The GUI port is never published. Only a route registered with `public=True` (exact method and literal path) can be reached without ingress, never static files, the index or the icon. | skeleton gate tests in `test_skeleton_server.py`, `internal/verify-admin-ui-scaffold.sh` | enforced   |
| R-02 | URLs are relative (no leading slash, no scheme). Download links use `apiHref`, and requests go only through the lib client.                                                                                                                                                                                                                | scanner rule `urls`, `api.test.mjs`                                                      | enforced   |
| R-03 | State never goes into markup: text nodes only, no raw-markup APIs, no `eval`, no string timers.                                                                                                                                                                                                                                            | scanner rule `markup`, component tests with hostile text                                 | enforced   |
| R-04 | Destructive actions need type-to-confirm: `ConfirmDialog` with `expected`, and the server answers `confirmation_required` when the phrase is missing.                                                                                                                                                                                      | ui tests, `test_demo_api.py`                                                             | enforced   |
| R-05 | The runtime is vendored and pinned by SHA-256: no CDN, no npm, no build step.                                                                                                                                                                                                                                                              | scanner rule `vendor`, `test_static_rules.py`                                            | enforced   |
| R-06 | Every user-visible string goes through `t()` or `tp()`. German and English have identical keys and placeholders, and keys are never built dynamically.                                                                                                                                                                                     | `i18n.test.mjs`                                                                          | enforced   |
| R-07 | Dates, times, numbers, bytes and relative times use `Intl` through `format.mjs`.                                                                                                                                                                                                                                                           | `format.test.mjs` for the lib, review for add-on code                                    | review     |
| R-08 | Colours come only from tokens and work in both themes. Text contrast is at least 4.5:1, and `prefers-color-scheme` is the default.                                                                                                                                                                                                         | `test_css.py` (tokens, contrast, hex hygiene)                                            | enforced   |
| R-09 | Accessibility minimum: dialog role with focus move, trap and return, `aria-live` toasts, `role=alert` errors, labelled controls, `th scope`, visible focus, reduced motion.                                                                                                                                                                | `a11y.test.mjs`, `ui.test.mjs`, `test_css.py`                                            | enforced   |
| R-10 | Storage keys are namespaced (`admin-ui:lang`, `<slug>:<key>`) and every access sits in try/catch.                                                                                                                                                                                                                                          | scanner rule `storage`, `i18n.test.mjs`                                                  | enforced   |
| R-11 | No third-party scripts and no inline script, handler or style attribute, so the page stays CSP compatible. The CSP header is a default and promised only after spike item S9.                                                                                                                                                              | scanner rule `csp`; live behaviour by spike item S9                                      | unverified |
| R-12 | Test duty: every GUI ships node tests for its views plus i18n parity and runs them in CI.                                                                                                                                                                                                                                                  | CI job for admin-ui (plan 26-09); existing add-ons follow in their migration phases      | review     |
| R-13 | HA theme and layout are progressive enhancement: own tokens and the fixed layout always work, theme sync and bridge only enhance, and any failure means the own theme.                                                                                                                                                                     | `theme_sync.test.mjs`, `ha_bridge.test.mjs`; live behaviour by the spike                 | unverified |
| R-14 | The backend returns stable error codes. The UI maps `errors.<code>`, unknown codes show a generic text plus `[code]`, and the backend `message` is never the primary text.                                                                                                                                                                 | `i18n.test.mjs` (`tError`), `test_demo_api.py`                                           | enforced   |
| R-15 | Lib and skeleton sources change only in `admin-ui/`. Consumer copies are never hand-edited, and the drift check fails on a mismatch.                                                                                                                                                                                                       | `make check-admin-ui-sync`, `test_sync.py`                                               | enforced   |

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

| Module       | Public names                                                                                                                             |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `errors.py`  | `ERROR_STATUS` (error code to HTTP status), `ApiError(code, message, status)`, `register_error_code(code, status)`                       |
| `router.py`  | `Request` (`arg`, `body`), `Router` (`add(..., public=False)`, `is_public`, `routes`, `match`), `Download(filename, content_type, data)` |
| `static.py`  | `StaticFiles(root)` with `resolve(path)`, `SEGMENT_RE`, `CONTENT_TYPES`; extension whitelist and containment check                       |
| `ingress.py` | `INGRESS_REMOTE`, `is_ingress(peer, headers, remote)`, `ingress_user(headers)`                                                           |
| `headers.py` | `DEFAULT_CSP`, `security_headers(kind, csp)`                                                                                             |
| `server.py`  | `MAX_BODY`, `make_handler(router, static, ...)`, `make_server(router, static, port, ...)`, `serve(server)`                               |

A route registered with `Router.add(method, pattern, handler, public=True)` is the one exception to the gate: exactly
that method and that literal path (for example a health check on an optionally published port) is served without
ingress. The path is compared as sent, with no normalisation, decoding, prefix match or case folding, so `/api/health/`,
`//api/health`, `/api/./health`, `/api/%68ealth` and `/API/health` stay 403. `add` raises `ValueError` for a public
route with a `{param}`, dot segments, a trailing slash or a path at `/`, `/icon` or below `/static`. Other methods on
the same path, `HEAD` and `OPTIONS` included, stay 403 unless registered themselves. A public handler gets
`Request.public` set to true and a header view without `X-Ingress-*` and `X-Remote-User-*`, so `ingress_user` is `None`:
never decide anything on identity there, and return no secret values. Responses carry the usual API headers; the CSP
setting does not matter. The default is `public=False`, so existing consumers see no change.

Handler results are a dict (200 JSON), a `(status, dict)` pair, `None` (204) or a `Download`. The gate runs first for
every method and path. API responses carry `Cache-Control: no-store`, static files `no-cache`, all responses `nosniff`,
and static files carry no `X-Frame-Options` because Home Assistant frames the page. Unexpected exceptions return
`500 internal_error` with the traceback on stdout only.

Static caching: every static response (and `/`) carries `Cache-Control: no-cache` and a strong `ETag` (sha256 of the
served bytes); a matching `If-None-Match` (list, `W/` prefix and `*` accepted) answers `304` without body. No
`Last-Modified` is sent, because it invites heuristic caching. `/` is served with every `src`/`href="static/..."` value
rewritten to `...?v=<hash of that asset>`, so a changed asset changes the index and its ETag; consumers edit nothing. ES
module imports inside `.mjs` files stay unversioned and rely on revalidation. `StaticFiles.resolve()` still returns
`(content, content type)`; `resolve_asset()` adds the ETag. The skeleton registers no service worker and never sends
`Clear-Site-Data`. A browser that cached a page heuristically before this change (for example the 0.6.x busybox page of
haos-monitor) never asks the server again until that entry expires: a hard reload once clears it.

The demo API (`app/web/demo_api.py`) serves fake data for the gallery and the sample CRUD: `api/health`, `api/items`
with create, update and a type-to-confirm delete, `api/fail/<code>` for error states, `api/slow`, `api/whoami` and
`api/echo`.

### Browser lib

All modules live in `admin-ui/app/web/static/lib/`, one self-contained directory. Imports inside it are `./x.mjs` or
`./vendor/preact-htm.mjs` only.

| Module                             | Exports                                                                                                                                                                              |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `api.mjs`                          | `ApiClientError`, `buildUrl`, `request`, `get`, `post`, `put`, `patch`, `del`                                                                                                        |
| `ingress.mjs`                      | `isEmbedded`, `assertRelative`, `apiHref`, `errorKey`, `detectEmbedContext`, `infoLinkPlan`                                                                                          |
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
when the image fails to load; `iconSrc={null}` turns it off. `infoPath` adds an info link (bar icon, or burger menu
entry when folded). The bar stays one compact row: children passed to `Topbar` are hidden below 600 px, so put nothing
essential there.

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
   GUI port in the manifest. Only if a health check must work on an optionally published port, register that one route
   with `public=True`.
6. Run the rules scanner (`make check-admin-ui-rules`) and your node and pytest tests, and add them to CI.

## Distribution

The lib is distributed by copy because the Docker build context is the add-on directory. A consumer pulls a new lib
version through the shared lib-release command; each add-on keeps its own release version.

- `LIB.stamp` in every consumer copy has two lines: `version <X.Y.Z>` and `sha256 <tree hash>`. The tree hash covers the
  sorted relative paths and the file hashes, and skips the stamp itself, `__pycache__` and `*.pyc`.
- `admin-ui/lib.lock` holds the version and the hashes of `lib/` and `skeleton/`.
- `make sync-admin-ui` refreshes the lock, `make sync-admin-ui ADDON=<name>` creates or updates one consumer.
- `make check-admin-ui-sync` runs the drift check for the pre-commit hook and CI.
- `make check-admin-ui-rules` runs the static rules scanner and `make test-admin-ui` the node and pytest suites. Both
  checks are members of `make check-all` and run as path-scoped pre-commit hooks, so the same commands run locally, in
  pre-commit and in CI.

### Shared library release

Run `make release-admin-ui-lib VERSION=X.Y.Z` after finishing the source changes. This updates the independent browser
lib `VERSION`, synchronises the library and Python skeleton into every registered consumer, refreshes all stamps and the
lock, and checks strict consistency. It then runs the blueprint rules, library tests and the ntfy, Secrets Sync web and
HAOS Monitor consumer tests, each in a separate Python process. New consumers register once with
`make sync-admin-ui ADDON=<name>` and are discovered automatically afterwards.

The release version must be SemVer without an add-on subpatch. Downgrades and reusing a version with changed sources
fail; repeating an unchanged release is safe. Commit the library sources, lock and consumer copies together. CI uses
`make check-admin-ui-sync STRICT=yes` and runs the consumer tests, so a consumer behind the source fails the build.

This prepares the monorepo update locally; it does not publish a release or deploy an app. Before shipping consumer
images, bump each affected add-on with `make update-version` according to its release policy. The library version is
independent of the demo add-on version and of upstream binaries such as ntfy. Renovate is not needed for these local
copies; external repositories would require a published dependency and a versioned download step first.

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

The own bar stays (HA parent header height, falling back to 56 px). To avoid a second bar, the kiosk policy asks HA to
hide its bar only when HA would draw one:

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

| ID  | Check                                | How the demo page observes it                                           | Pass criterion                                                                       | Result                                                                                                                                                                                                                                                                        | Status         |
| --- | ------------------------------------ | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| S1  | Parent access                        | parent document read result and error name, `window.parent` comparison  | readable in the panel, reported as not embedded in a direct tab                      | Panel, parent readable (`readable_same`); direct-tab case belongs to S12                                                                                                                                                                                                      | verified       |
| S2  | Variable read                        | table of all whitelist variables with raw value and parse result        | present and parseable in light, dark, a custom theme and a new primary colour        | HA default dark only: 4 of 5 variables parsed, `bd` null (divider not read), surface and accent skipped by the contrast guard; light, custom and new primary colour not run                                                                                                   | verified       |
| S3  | Change detection                     | counters for observer fires and poll differences while switching themes | token change within 1 second without reload, no loops                                | Not run: no theme switch during the run (observer 0, poll 76, apply 1), change detection unchecked. Follow-up: rerun with live theme switch                                                                                                                                   | not-applicable |
| S4  | Bridge                               | log of every properties message, resize across 870 pixels, rotation     | `narrow` flips at 870 pixels, insets set on notch devices, fallback works on silence | Limited: bridge answered, `narrow` false, insets present; flip at 870 px and rotation not run                                                                                                                                                                                 | verified       |
| S5  | Double top bar                       | frame top measurement in docked, hidden-sidebar, narrow and kiosk modes | no double bar after the policy, menu button opens the drawer, HA restores on leaving | Docked sidebar only: host bar false, kiosk false; hidden sidebar, narrow and kiosk policies not run                                                                                                                                                                           | verified       |
| S6  | `handleSafeArea`                     | toggle re-subscribes with the option, insets displayed                  | confirms the safe-area handling on iOS and Android, default stays off                | Default off (`safe_area_off`); toggle on iOS and Android not run                                                                                                                                                                                                              | verified       |
| S7  | `navigate`                           | button and topbar info link post a navigate message                     | HA navigates                                                                         | Panel: the S7 button navigates (user observation, 2026-11-02). The info link used a retired path and opened the wrong page; fixed to `/config/app/<slug>/info`, re-test open. Dashboard card: message sent, ignored by the host (no answer, no navigation)                    | verified       |
| S8  | Clipboard                            | `CopyField` over HTTP and HTTPS, in panel and card                      | copy works or the fallback message appears                                           | Not run (`not_run`). Follow-up: copy over HTTP and HTTPS, in panel and card                                                                                                                                                                                                   | not-applicable |
| S9  | CSP                                  | CSP header enabled, violation counter                                   | zero violations during gallery, CRUD and theme sync                                  | `violations_0` in run A, but the header was not confirmed live in HA and the counter counts only while `#/spike` is open. The image sends it (smoke script), no live look at HA or proxies. Follow-up: check the header in the network tab (see Testing the CSP), then set S9 | not-applicable |
| S10 | Storage                              | language survives a reload, behaviour with storage blocked              | no exception, the default language works                                             | Not run (`not_run`). Follow-up: reload test and run with storage blocked                                                                                                                                                                                                      | not-applicable |
| S11 | Admin and non-admin                  | `api/whoami` groups, open as non-admin with `panel_admin: false`        | panel visible and functional for non-admins                                          | Admin only: `identity_yes`, group `system-admin`; non-admin user not run                                                                                                                                                                                                      | verified       |
| S12 | Direct access                        | published port and ingress URL in a plain tab                           | port answers 403 `ingress_only`, ingress tab shows the own theme                     | Not run: only the ingress path inside the panel, no direct tab, no published port. Follow-up: plain-tab run                                                                                                                                                                   | not-applicable |
| S13 | Dashboard webpage card               | card pointing at the ingress URL                                        | record whether it is blocked and whether theme sync works                            | Partly: a third-party card (`custom:addon-iframe-card`) loads the page, but the host protocol is not answered and top navigation is blocked by the frame sandbox. Theme sync in the card not checked                                                                          | not-applicable |
| S14 | Language and theme switch while open | live switch                                                             | re-render without reload                                                             | Not run: `de_dark` is only the state, no live switch. Follow-up: switch language and theme with the page open                                                                                                                                                                 | not-applicable |
| S15 | After an HA update                   | HA versions recorded per run                                            | re-run per HA release, dated rows in this table                                      | Limited: HA core 2026.10.4 recorded, frontend version missing; no run after an HA update yet                                                                                                                                                                                  | verified       |

A run is recorded from the copy-as-JSON result block of the demo page. Record the HA core and frontend version, the
browser or companion app and the access path (panel, card, direct tab). Set the status to `verified`, `failed` or
`not-applicable`, fill the result cell and update the `Verified on:` line. A result may contain HA versions, the browser
or app, the access path and pass or fail. It must never contain tokens, real hostnames or user names.

### Testing navigate live with the info link (S7)

The topbar shows an info icon (ⓘ) that opens this add-on's page in Home Assistant (`/config/app/<slug>/info`). Since HA
2026.2 add-ons are called apps and the frontend route is `/config/app/<slug>/...` (tabs info, documentation, config,
logs); the old `/hassio/addon/<slug>/info` is not a route of the current frontend, and older HA versions are not
supported by this link. The slug comes from the Supervisor (`GET http://supervisor/addons/self/info`, allowed for every
add-on) and reaches the page as `addon_slug` in `api/health`. Without a token or answer (direct run) the key is missing
and the link is hidden. How the link works depends on the embedding (see below). In the app panel a click sends a
`home-assistant/navigate` message, with the plain link as fallback. HA never confirms `navigate`, so the page can only
say "sent, not confirmed by the host". Expected result: HA opens the add-on page without a full reload; you observe that
yourself. The result block records the last path as `navigate.last_path` (`bridge`, `fallback` or `new_tab`, else
`none`) and `navigate.count`. On narrow layouts with the burger menu the link is an entry of that menu. The existing S7
button stays.

### Embedding contexts

`detectEmbedContext` and `infoLinkPlan` (lib `ingress.mjs`) read how the page is embedded and the info link follows:

| Context | Detected by                                           | Info link                                                                    |
| ------- | ----------------------------------------------------- | ---------------------------------------------------------------------------- |
| panel   | the HA bridge answers (`properties` message)          | navigate message; plain link to the top window as fallback                   |
| card    | framed, `sandbox` attribute on the frame, host silent | top window if the sandbox allows it, a new tab if only `allow-popups` is set |
| tab     | no parent frame                                       | plain link in the same window                                                |
| unknown | framed, host silent, frame not readable               | link to the top window                                                       |

The frame is only readable when the parent is same-origin, and a sandbox sent as a header cannot be seen. A sandbox
without `allow-top-navigation` or `allow-top-navigation-by-user-activation` blocks a top-window link: the browser then
logs an error and nothing happens. So the link opens a new tab when `allow-popups` is set and is hidden otherwise. The
spike view shows the context (`embed.kind`, the relevant sandbox tokens, `embed.top_navigation`) in the result block.
Observed on 2026-11-02 (HA core 2026.10.4, Chromium): the panel answers the bridge and the S7 button navigates; a
third-party dashboard card (`custom:addon-iframe-card`) loads the page but ignores the navigate protocol (only the app
panel of HA implements it) and its sandbox blocks top navigation.

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

## Consumer integration

The ntfy, secrets-sync and haos-monitor migration implementations are included in this branch. All three consume lib
0.7.0 from `vendor/admin-ui/` and the Python skeleton from `app.web.admin_ui`, maintained with `make sync-admin-ui`.
ntfy keeps its domain components and seven views; Secrets Sync uses Preact views and preserves its public health/status
routes; HAOS Monitor serves its ingress GUI on internal port 8100 while retaining machine endpoints on port 8099.
Deploying the HAOS Monitor migration requires its updated image and add-on manifest together.

The skeleton supports explicitly public routes for machine health/status checks. Routes are ingress-only by default;
consumer APIs and static UI assets retain the ingress gate. Tests cover the public-route exceptions.

## Security notes

- The gate checks the peer address and the header. Spoofing the header requires reaching the unpublished port, which is
  why the port is never published.
- The ingress page shares the origin with Home Assistant: `localStorage` and `window.parent` are readable both ways.
  Therefore storage keys are namespaced and no third-party scripts are loaded.
- `X-Ingress-Path` is set by Home Assistant Core, not by the Supervisor.
- The `X-Remote-User-*` headers are informational only and never an authorisation decision.
- Public routes are an explicit, exact opt-out of the gate (see the library reference). Keep them read-only status
  endpoints without secret values: anyone who can reach the published port can call them.

## Follow-up

- Run the ntfy and secrets-sync frontend tests in CI.
- Add `haos-monitor` to `internal/base-image-config.yaml`.
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

## HA navigation and table layout

The Tokens demo includes a live sync table showing HA variables, their library targets, validated values and whether
they are applied or use a fallback. It includes the derived accent text colour and the header height (56 px fallback).
The table subscribes to theme-sync changes; the Spike variable table also includes `--header-height`.

The topbar must **match the HA parent's `--header-height`, including its bottom border**, with **56 CSS px as the
fallback**. The existing theme sync reads the value from the `home-assistant` host, falling back to the parent document
root. It accepts only pixel lengths from 32 to 128 px; missing, inaccessible or invalid values remove the override.
Height sync is independent of colour validation and follows the same polling/events and cleanup as theme sync.
`status().headerHeight` reports the accepted length or `null` when using the fallback. This applies to desktop and
mobile, with inline or collapsed navigation. Contents must not enlarge the bar. Safe-area padding and an optional
separate tab bar sit outside its height. CSS and theme-sync tests enforce this rule.

`Topbar` and `TabNav` accept an optional `icon` on each view: an SVG path string in a 24 × 24 view box (for example an
MDI path). Icons inherit the text colour, are decorative and keep the translated link label visible. Omit `icon` for
text-only navigation. Active navigation uses the accent underline; overflow still folds into the accessible menu.

Data-table headers are at least 56 px high and body cells at least 52 px. These are minimums: wrapped text and expanded
content can grow. Keep actions in `td.actions` (the lib preserves its table-cell display); use `.actions` containers for
flex layouts outside cells. Put wide tables in `.table-scroll` and expanded details in a following `.card` to get
consistent separation. The gallery includes rows with and without actions plus expandable details for comparison.

Theme-sync contrast checks composite translucent text over the page and card backgrounds, and translucent cards over the
page background. Valid RGBA values are preserved when applied. The page background must remain opaque so its contrast
can be determined; text and accent still need at least 4.5:1 contrast on both surfaces.

### HA card appearance

Cards use `--ha-card-background` (falling back to `--card-background-color`), `--ha-card-border-radius` (falling back to
`--ha-border-radius-lg`) and `--ha-card-box-shadow` from the parent HA host or document root. They map to
`--sync-ha-card-background`, `--sync-card-radius` and `--sync-card-shadow`, respectively. Card-only styles do not change
the toolbar or dialogs. The Tokens view shows each value and its applied/fallback state, updating with theme sync.

Card backgrounds retain the text contrast check. Radius accepts one to four nonnegative pixel or percentage lengths;
shadows accept `none` or up to eight layers of bounded pixel lengths, optional `inset`, and parsed colours. Arbitrary
CSS functions and declarations are rejected. Invalid or removed overrides restore the library defaults (8 px radius, no
shadow and the regular card surface). Isolated light/dark demo panels keep their own appearance.

`transparent` is accepted as a fully transparent card background and evaluated over the page background. The Tokens view
displays the original parent card-background input; a rejected value is labelled as missing, unsupported or insufficient
contrast instead of silently displaying the regular surface colour.
