# Phase 26: admin-ui blueprint - Context

**Gathered:** 2026-11-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Meta add-on `admin-ui`: a real HA add-on (image, ingress, demo GUI) that is the blueprint for all admin GUIs in this
repo, now and later. It fixes design and rules and ships a reusable lib:

- tokens + base CSS
- API client + ingress helper (JS) and a Python server skeleton
- Preact/htm components
- i18n mechanics (de/en) and an optional HA theme-sync module

Delivered in this phase: the add-on and demo GUI, the lib, the rules (DOCS + enforcing tests), the sync script with
drift check, a CI job, and a live spike of the HA theme/iframe access.

**Not in this phase:** migrating `ntfy`, `secrets-sync` and `haos-monitor` onto the lib (follow-up phases, see
Deferred). Phase 26 documents the migration paths only.

</domain>

<decisions>
## Implementation Decisions

### Form and packaging
- **D-01:** `admin-ui` is a real add-on with a demo GUI (ingress, image). Own version scheme, manual bumps via
  `make update-version`, no `.upstream.yaml`, no auto-update (like `haos-monitor`). HA base image only.
- **D-02:** Demo GUI shows: component gallery (Badge, Toast, Modal, ConfirmDialog, CopyField, tables, tabs), token view
  (light/dark), i18n switcher, a sample CRUD against a fake API of the Python skeleton including error states, and
  the rules as a checklist page.

### Lib scope and technology
- **D-03:** Lib scope: tokens + base CSS, API client + ingress helper, Preact/htm components, Python server skeleton
  (router, static whitelist, JSON helpers, security headers, ingress gate). Preact/htm vendored, no CDN, no npm, no
  build step (carries D-16 of Phase 24). — **Reversibility:** costly — every consuming GUI is built on the component
  model; a framework switch touches all of them.
- **D-04:** Source of truth for the lib is `admin-ui/app/web/static/lib/` in the meta add-on. The lib is extracted
  from the ntfy GUI (`lib/api.mjs`, `lib/ui.mjs`, `lib/model.mjs`, `app.css`). The demo is always a consumer of the lib.

### Distribution
- **D-05:** Docker build context is `./<addon>`, so the lib is distributed by copy: `make sync-admin-ui` copies it to
  `<addon>/app/web/static/vendor/admin-ui/` (committed). A pre-commit/CI drift check compares hashes. No download at
  build, no change of the build context. — **Reversibility:** reversible — tooling only, copies stay plain files.
- **D-06:** Lib version lives in a `VERSION` file. The sync script writes version + hash into each consumer copy.
  Consumers pin by hash; the drift check fails on mismatch. A consumer pulls updates deliberately (sync + its own
  version bump).

### Migration (documented here, executed later)
- **D-07:** Phase 26 = admin-ui + rules only. ntfy switch-over, `secrets-sync` and `haos-monitor` are separate
  follow-up phases (see Deferred). Chosen end state: `secrets-sync` full rewrite on Preact/htm (replace
  `window.confirm()` with the lib ConfirmDialog), `haos-monitor` rebuilt on the blueprint stack (Python server +
  Preact instead of busybox/CGI), ntfy switched to the lib copy.

### i18n (de/en)
- **D-08:** Language from `navigator.language` (`de*` -> `de`, else `en`) with a manual switcher in the topbar stored in
  `localStorage` (wrapped in try/catch). No add-on option for language.
- **D-09:** The lib provides the `t()` mechanics (`lib/i18n.mjs`) and base strings (`strings.{de,en}.mjs`: buttons,
  dialogs, errors). Each add-on adds its own `app/strings.{de,en}.mjs`. A test enforces identical key sets for de and en.
- **D-10:** The backend returns stable error codes (as today, `error` in JSON); the UI translates by key. Unknown code
  -> generic localized text plus the code in brackets. Dates, times and numbers via `Intl` (`DateTimeFormat`,
  `RelativeTimeFormat`).

### HA theme and layout (progressive enhancement)
- **D-11:** Own tokens plus `prefers-color-scheme` stay the default and always work (direct tab, cards, after HA
  updates). An optional `theme-sync` module, active only when `window.parent !== window`, reads a whitelist of HA CSS
  variables from the parent `documentElement` in a try/catch and maps them to the tokens via
  `var(--ha-…, <default>)`. Failure = own theme. — **Reversibility:** reversible — optional module behind a fallback.
- **D-12:** Dark/Light with sync active is derived from the luminance of the parent `--primary-background-color`
  (sets `data-theme`), not from the internal `hass.themes.darkMode`.
- **D-13:** The own 56px topbar stays. The lib subscribes to the official `home-assistant/subscribe-properties`
  postMessage protocol (`narrow`, `safeAreaInsets`), uses `home-assistant/toggle-menu` for the menu button in narrow
  mode and avoids a double topbar (HA shows its own 40px bar only when narrow or sidebar hidden; `kioskMode: true`
  when our bar takes over). Without an answer the fixed layout applies.
- **D-14:** Verification is a **live spike in the demo add-on against a real HA instance**. Results are recorded in
  the rules and decide what the rules guarantee. Test matrix: panel on desktop/mobile/Companion app, direct access
  (port and ingress URL in a tab), dashboard webpage card, theme switch and language switch with the page open,
  admin vs non-admin, kiosk mode/`handleSafeArea`, behavior after an HA update.

### Rules and enforcement
- **D-15:** The blueprint rules cover dark/light + a11y minimum, i18n de/en, test duty, security/ingress rules
  (gate on every request, relative URLs only, never `innerHTML` with state, type-to-confirm for destructive actions).
- **D-16:** Enforced by tests (not only documented): i18n key parity de/en; ingress gate on every request (only
  `172.30.32.2` + `X-Ingress-Path`, else 403, like ntfy); static rules (relative URLs, no `innerHTML` with state,
  vendor SHA256); a11y minimum via fake-DOM tests (`role=dialog`, `aria-label`/`aria-live`, focus handling in Modal).
  Contrast stays a manual review item.
- **D-17:** New CI job in the lint workflow: `node --test` for the lib, pytest for `admin-ui`, and
  `make check-admin-ui-sync`. (Today the ntfy Node tests run only locally via `ntfy/tests/test_js.py`, skipped
  without node; making ntfy/secrets-sync tests part of CI is left to the follow-up phases.)

### Claude's Discretion
- Exact file layout inside `admin-ui/`, naming of the sync script and Makefile targets.
- Concrete token names for the HA theme whitelist after verifying against the HA frontend source
  (`src/resources/theme/*.globals.ts`) and the spike.
- Polling interval/MutationObserver details of `theme-sync`, as long as D-11 fallback holds.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing GUIs (inventory sources)
- `.planning/phases/24-ntfy-add-on-admin-gui/24-CONTEXT.md` — D-03 (ingress gate), D-16 (vendored Preact/htm, no build),
  D-17 (GUI feature list)
- `ntfy/app/web/static/` — `app.css`, `app.mjs`, `lib/api.mjs`, `lib/ui.mjs`, `lib/model.mjs`, `vendor/README.txt`
  (vendor update procedure, SHA256 gate)
- `ntfy/app/web/server.py` — ingress gate on every request, static whitelist, router
- `ntfy/tests/test_js.py`, `ntfy/tests/js/*.mjs`, `ntfy/tests/test_frontend_static.py` — Node tests, fake DOM, static rules
- `secrets-sync/app/web/` — Stdlib server, ingress gate, vanilla-JS GUI (migration source)
- `haos-monitor/index.html`, `haos-monitor/httpd.conf`, `haos-monitor/*.cgi` — busybox GUI (migration source)

### Repo rules and build
- `CLAUDE.md` — 3-file versioning, HA base images only, local `docker build` before committing Dockerfile changes
- `docs/DEVELOPMENT.md` — development workflow
- `.github/workflows/_build-template.yml` (line ~163: `context: ./<addon>`), `.github/workflows/lint.yml` — build
  context and CI job location

### HA frontend/iframe behavior (research report 2026-11-02, source reading only, needs the live spike)
- https://github.com/home-assistant/frontend/blob/dev/src/panels/app/ha-panel-app.ts — iframe without sandbox,
  postMessage protocol (`subscribe-properties`, `properties`, `navigate`, `toggle-menu`), 40px topbar rule
- https://github.com/home-assistant/frontend/blob/dev/src/common/dom/apply_themes_on_element.ts — theme variables are
  set via `style.setProperty`, no change event
- https://github.com/home-assistant/frontend/blob/dev/src/data/hassio/ingress.ts — `ingress_session` cookie SameSite=Strict
- https://github.com/home-assistant/supervisor/blob/main/supervisor/api/ingress.py — proxy sets/filters no XFO/CSP
- https://contributors.home-assistant.io/frontend/reference/hass-object/ — `hass` fields, no stability promise
- https://github.com/home-assistant/frontend/discussions/52204 — ingress in dashboard cards fails with 401

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- ntfy `lib/api.mjs`: `ApiClientError`, `buildUrl` (rejects absolute paths), verb helpers -> lib API client.
- ntfy `lib/ui.mjs`: Toast, Modal, ConfirmDialog (type-to-confirm), Badge, CopyField, ErrorNote, `useAsync`,
  `usePoll` -> lib components.
- ntfy `app.css` and secrets-sync `app.css`: identical token names (`--bg --fg --card --bd --mut --ok --warn --err
  --acc --chip`), ntfy adds `--hover --shadow` -> base tokens.
- ntfy `server.py`: ingress gate + static whitelist + JSON router -> Python skeleton.
- ntfy `tests/js/fakedom.mjs`: fake DOM for Node tests -> lib tests and a11y tests.

### Established Patterns
- Ingress gate: peer `172.30.32.2` plus `X-Ingress-Path`, else 403 `ingress_only`.
- All URLs relative (no leading slash) because the page sits below an ingress path.
- No state interpolated into markup (secrets-sync builders, Preact in ntfy).
- Vendored file pinned by SHA256 with a test and an update procedure.
- Add-ons build from `./<addon>`; nothing outside the add-on dir is reachable at build.

### Integration Points
- Makefile: new targets `sync-admin-ui` and `check-admin-ui-sync`; pre-commit hook for the drift check.
- `.github/workflows/lint.yml`: new job for `admin-ui` tests (Node 22 is already set up there).
- `.github/workflows/build.yml`: `admin-ui/` joins the add-on path filter via the standard mechanism.
- README add-on list and `internal/validate-*` scripts (3-file version sync, add-on structure).

</code_context>

<specifics>
## Specific Ideas

- User wants the HA theme usable to simplify design unification (e.g. adopt the HA header height and color schemes
  automatically). Research result: height cannot be read, but `narrow`/`safeAreaInsets` come via the official
  postMessage protocol; colors via parent CSS variables (same-origin, unverified). The spike decides.
- Blueprint demo doubles as the live test bed for the theme-sync spike (shows sync status live).
- Work is distributed by a manager pane to other agents in panes/tabs; one add-on per branch, stage by path.

</specifics>

<deferred>
## Deferred Ideas

- **ntfy switch-over to the lib** — own follow-up phase (ntfy copy, drop its local duplicates).
- **secrets-sync full rewrite on Preact/htm** — own follow-up phase (replaces `window.confirm()`, rewrites
  ~540 lines of Vanilla-JS and its tests).
- **haos-monitor rebuild on the blueprint stack** — own follow-up phase (Python server + Preact instead of
  busybox/CGI); also decide whether it gets the ingress gate.
- **Run ntfy/secrets-sync frontend tests in CI** — part of the follow-up migrations.
- **Python server skeleton API details, component list depth, detailed a11y checklist** — left to research/planning
  (not discussed).

</deferred>

---

*Phase: 26-admin-ui blueprint*
*Context gathered: 2026-11-02*
