# Phase 26: admin-ui blueprint - Research

**Researched:** 2026-11-02
**Domain:** HA add-on admin GUI blueprint (vendored Preact/htm lib, stdlib Python server skeleton, copy+hash distribution,
iframe/theme integration with the HA frontend)
**Confidence:** HIGH for extraction/scaffold/CI facts (read in this worktree), HIGH for HA frontend protocol facts (read
from source), MEDIUM for everything that depends on live HA behaviour (marked `[ASSUMED]`, to be settled by the spike)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Form and packaging**
- **D-01:** `admin-ui` is a real add-on with a demo GUI (ingress, image). Own version scheme, manual bumps via
  `make update-version`, no `.upstream.yaml`, no auto-update (like `haos-monitor`). HA base image only.
- **D-02:** Demo GUI shows: component gallery (Badge, Toast, Modal, ConfirmDialog, CopyField, tables, tabs), token view
  (light/dark), i18n switcher, a sample CRUD against a fake API of the Python skeleton including error states, and the
  rules as a checklist page.

**Lib scope and technology**
- **D-03:** Lib scope: tokens + base CSS, API client + ingress helper, Preact/htm components, Python server skeleton
  (router, static whitelist, JSON helpers, security headers, ingress gate). Preact/htm vendored, no CDN, no npm, no build
  step (carries D-16 of Phase 24). — **Reversibility:** costly — every consuming GUI is built on the component model; a
  framework switch touches all of them.
- **D-04:** Source of truth for the lib is `admin-ui/app/web/static/lib/` in the meta add-on. The lib is extracted from
  the ntfy GUI (`lib/api.mjs`, `lib/ui.mjs`, `lib/model.mjs`, `app.css`). The demo is always a consumer of the lib.

**Distribution**
- **D-05:** Docker build context is `./<addon>`, so the lib is distributed by copy: `make sync-admin-ui` copies it to
  `<addon>/app/web/static/vendor/admin-ui/` (committed). A pre-commit/CI drift check compares hashes. No download at
  build, no change of the build context. — **Reversibility:** reversible — tooling only, copies stay plain files.
- **D-06:** Lib version lives in a `VERSION` file. The sync script writes version + hash into each consumer copy.
  Consumers pin by hash; the drift check fails on mismatch. A consumer pulls updates deliberately (sync + its own
  version bump).

**Migration (documented here, executed later)**
- **D-07:** Phase 26 = admin-ui + rules only. ntfy switch-over, `secrets-sync` and `haos-monitor` are separate follow-up
  phases (see Deferred). Chosen end state: `secrets-sync` full rewrite on Preact/htm (replace `window.confirm()` with the
  lib ConfirmDialog), `haos-monitor` rebuilt on the blueprint stack (Python server + Preact instead of busybox/CGI), ntfy
  switched to the lib copy.

**i18n (de/en)**
- **D-08:** Language from `navigator.language` (`de*` -> `de`, else `en`) with a manual switcher in the topbar stored in
  `localStorage` (wrapped in try/catch). No add-on option for language.
- **D-09:** The lib provides the `t()` mechanics (`lib/i18n.mjs`) and base strings (`strings.{de,en}.mjs`: buttons,
  dialogs, errors). Each add-on adds its own `app/strings.{de,en}.mjs`. A test enforces identical key sets for de and en.
- **D-10:** The backend returns stable error codes (as today, `error` in JSON); the UI translates by key. Unknown code ->
  generic localized text plus the code in brackets. Dates, times and numbers via `Intl` (`DateTimeFormat`,
  `RelativeTimeFormat`).

**HA theme and layout (progressive enhancement)**
- **D-11:** Own tokens plus `prefers-color-scheme` stay the default and always work (direct tab, cards, after HA
  updates). An optional `theme-sync` module, active only when `window.parent !== window`, reads a whitelist of HA CSS
  variables from the parent `documentElement` in a try/catch and maps them to the tokens via `var(--ha-…, <default>)`.
  Failure = own theme. — **Reversibility:** reversible — optional module behind a fallback.
- **D-12:** Dark/Light with sync active is derived from the luminance of the parent `--primary-background-color` (sets
  `data-theme`), not from the internal `hass.themes.darkMode`.
- **D-13:** The own 56px topbar stays. The lib subscribes to the official `home-assistant/subscribe-properties`
  postMessage protocol (`narrow`, `safeAreaInsets`), uses `home-assistant/toggle-menu` for the menu button in narrow mode
  and avoids a double topbar (HA shows its own 40px bar only when narrow or sidebar hidden; `kioskMode: true` when our bar
  takes over). Without an answer the fixed layout applies.
- **D-14:** Verification is a **live spike in the demo add-on against a real HA instance**. Results are recorded in the
  rules and decide what the rules guarantee. Test matrix: panel on desktop/mobile/Companion app, direct access (port and
  ingress URL in a tab), dashboard webpage card, theme switch and language switch with the page open, admin vs
  non-admin, kiosk mode/`handleSafeArea`, behavior after an HA update.

**Rules and enforcement**
- **D-15:** The blueprint rules cover dark/light + a11y minimum, i18n de/en, test duty, security/ingress rules (gate on
  every request, relative URLs only, never `innerHTML` with state, type-to-confirm for destructive actions).
- **D-16:** Enforced by tests (not only documented): i18n key parity de/en; ingress gate on every request (only
  `172.30.32.2` + `X-Ingress-Path`, else 403, like ntfy); static rules (relative URLs, no `innerHTML` with state, vendor
  SHA256); a11y minimum via fake-DOM tests (`role=dialog`, `aria-label`/`aria-live`, focus handling in Modal). Contrast
  stays a manual review item.
- **D-17:** New CI job in the lint workflow: `node --test` for the lib, pytest for `admin-ui`, and
  `make check-admin-ui-sync`. (Today the ntfy Node tests run only locally via `ntfy/tests/test_js.py`, skipped without
  node; making ntfy/secrets-sync tests part of CI is left to the follow-up phases.)

### Claude's Discretion
- Exact file layout inside `admin-ui/`, naming of the sync script and Makefile targets.
- Concrete token names for the HA theme whitelist after verifying against the HA frontend source
  (`src/resources/theme/*.globals.ts`) and the spike.
- Polling interval/MutationObserver details of `theme-sync`, as long as D-11 fallback holds.

### Deferred Ideas (OUT OF SCOPE)
- **ntfy switch-over to the lib** — own follow-up phase (ntfy copy, drop its local duplicates).
- **secrets-sync full rewrite on Preact/htm** — own follow-up phase (replaces `window.confirm()`, rewrites ~540 lines of
  Vanilla-JS and its tests).
- **haos-monitor rebuild on the blueprint stack** — own follow-up phase (Python server + Preact instead of busybox/CGI);
  also decide whether it gets the ingress gate.
- **Run ntfy/secrets-sync frontend tests in CI** — part of the follow-up migrations.
- **Python server skeleton API details, component list depth, detailed a11y checklist** — left to research/planning (not
  discussed).
</user_constraints>

<phase_requirements>
## Phase Requirements

No requirement IDs were supplied (ROADMAP "Requirements: TBD"). The planner should derive acceptance criteria from
D-01..D-17; the "Validation Architecture" section maps each decision to a concrete automated check.
</phase_requirements>

## Project Constraints (from CLAUDE.md)

Repo `CLAUDE.md` (worktree root) plus `/home/akentner/CLAUDE.md`:

- HA base images only (`ghcr.io/home-assistant/...`), no generic Alpine/Python/Node base. `[VERIFIED: CLAUDE.md]`
- 3-file versioning (`config.yaml` `X.Y.Z-N`, `build.yaml` `args.VERSION` `X.Y.Z`, `README.md` badge `vX.Y.Z`); never edit
  versions by hand after scaffold, use `make update-version`.
- Local `docker build` before committing any Dockerfile change (docker 29.9.2 is available here).
- Stage by path, never `git add -A`; **no `Co-Authored-By` / AI attribution lines** in commits or PR bodies.
- One add-on per branch; in a worktree write only `.planning/phases/26-*/` and quick/workstream files, never
  `STATE.md`, `state.json`, `ROADMAP.md`.
- `haos-monitor` exception model (own code, no `.upstream.yaml`, no auto-update, scripts in the add-on dir) is the model
  for `admin-ui`; CLAUDE.md "Exception" paragraph should be extended to name `admin-ui`.
- Lint rules: YAML 2-space, 120 cols (warning level); Markdown 120 cols enforced + prettier `proseWrap: always`; shell
  `shellcheck` (SC1091/SC2034 ignored); Python scripts in `internal/` stdlib only.
- Docker verify scripts (`internal/verify-*.sh`) start containers: never run the same script in two worktrees at once.
- Chat in German, code/commits/comments in English (global CLAUDE.md). Plans must be goal-backward verifiable.

## Summary

The ntfy GUI is already structured the way the lib needs to be: `lib/api.mjs` (61 lines) is fully generic, `lib/ui.mjs`
(175 lines) is generic except `OriginBadge`/`PermSelect` and a hard-coded `ERROR_HINTS` table, `lib/model.mjs` is
ntfy-specific except the formatting helpers and `confirmMatches`, `app.css` (131 lines) splits cleanly into tokens/base/
components versus ntfy-only `.matrix`/`.badge.gui|options|iac`, and `server.py` (244 lines) is generic except three
imports from `app.contract`/`app.ntfycli`. Extraction is therefore mostly **moving + parameterizing**, with four real
gaps that the lib must close because ntfy does not have them: (1) i18n (all strings are English literals, including
`aria-label="Close"` and `"Copied"`), (2) focus management in `Modal` (no focus move, trap or return), (3) a
`[data-theme]` token path for theme-sync and the light/dark demo panels, (4) the postMessage bridge and theme-sync
modules.

The HA-frontend facts the CONTEXT report assumed were checked against current `dev` source (commit `78f6a55e`,
2026-11-02) and the latest stable frontend tag `20260930.5`. The protocol is real and matches D-13, with three
corrections that change the design: **(a)** `kioskMode:true` does not merely hide HA's 40px bar, it turns the *whole*
HA sidebar into a modal drawer (`sidebarNarrow = ... || this.hass.kioskMode`), so on desktop it must stay off; **(b)**
`properties` carries only `narrow`, not `dockedSidebar`, so the "docked sidebar hidden -> HA shows its 40px bar on
desktop" case cannot be detected from the message (use a same-origin `frameElement` offset heuristic or accept a double
bar); **(c)** `X-Ingress-Path` is set by **HA Core** (`homeassistant/components/hassio/ingress.py:275`), not by the
Supervisor, which only passes it through. Theme variables are applied with `style.setProperty` on the parent
`document.documentElement` (verified), defaults live in `html {}` stylesheet rules, there is no change event, so
theme-sync needs a MutationObserver on the parent's `style` attribute plus a slow poll.

Distribution (D-05/D-06) works with a deterministic tree hash written to a plain-text stamp file (not JSON, because the
repo's `pretty-format-json --autofix` hook would rewrite it). Today there is **no consumer**, so a committed
`admin-ui/lib.lock` is needed to make the drift check non-vacuous, and the sync script must be unit-tested against a
temp-dir fake consumer. The CI job is appended at the **end** of `lint.yml` with single-line edits to `lint-results`;
that keeps the line-anchored zizmor deferrals in `zizmor.yml` valid (verified with `zizmor 1.30.1`: no findings).

**Primary recommendation:** Build `admin-ui` as a haos-monitor-style own-code add-on whose demo imports the lib source
directly; make `lib/` one self-contained directory (including `vendor/preact-htm.mjs` and `VERSION`) so a plain
directory copy preserves all relative imports; ship a tree-hash sync/check script (stdlib) wired into Makefile,
pre-commit and an appended `lint.yml` job; and treat every HA-integration behaviour not read from source as
`[ASSUMED]` until the `#/spike` page has been run on the real instance.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Ingress gate (peer 172.30.32.2 + `X-Ingress-Path`) | API / Backend (Python skeleton) | — | Only the add-on process sees peer IP and headers; must run before routing and static serving |
| Static file whitelist, security headers | API / Backend | — | Same process serves `static/`; CSP/nosniff are response headers |
| Stable error codes (`{error, message}`) | API / Backend | Browser (translates by code) | D-10: backend never localizes, UI maps `errors.<code>` |
| Relative-URL API client, `ApiClientError` | Browser / Client | — | Page lives below `/api/hassio_ingress/<token>/`, only the browser knows its base |
| Components, hooks, focus/a11y | Browser / Client | — | Preact/htm in the iframe |
| i18n `t()`, `Intl` formatting, language persistence | Browser / Client | — | D-08: `navigator.language` + `localStorage`, no add-on option |
| Tokens/base CSS, `[data-theme]` | Browser / Client (CSS) | — | Pure CSS custom properties, no server involvement |
| Theme sync, postMessage bridge | Browser / Client | HA frontend (parent window) | Reads parent `documentElement`; HA answers `subscribe-properties` |
| Lib distribution (copy + hash) | Repo tooling (Makefile/pre-commit/CI) | — | Build context is `./<addon>`; nothing outside the add-on dir is reachable at build |
| Add-on build/publish | CI (`build.yml`) | Supervisor | Auto-detected from config.yaml+build.yaml+Dockerfile triple |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| htm standalone bundle (Preact 10.x inside) | htm 3.1.1, file `preact-htm.mjs`, 13194 bytes, sha256 `72284e8e9079c87817145df1110f74e8a2aa040b2fc384922e18dfcb46fc1fd7` | Component runtime, no build step | Already vendored and pinned in ntfy; D-03 locks vendoring `[VERIFIED: sha256sum of ntfy/app/web/static/vendor/preact-htm.mjs this session; ntfy/app/web/static/vendor/README.txt]` |
| Python stdlib (`http.server`, `ThreadingHTTPServer`, `json`, `re`, `pathlib`) | system `python3` from Alpine | Server skeleton | No dependencies, same as ntfy/secrets-sync `[VERIFIED: ntfy/app/web/server.py:1-18]` |
| Node built-in test runner (`node --test`) | Node 22 (local v22.23.4, CI `node-version: '22'`) | Lib JS tests | Already used by ntfy; no devDependencies `[VERIFIED: ran 25 ntfy tests green]` |
| pytest | 9.2.0 on PyPI (`pip` latest) | Server + static-rule + sync tests | ntfy convention (`uv run --with pytest python3 -m pytest`) `[VERIFIED: pypi.org/pypi/pytest/json]` |

Exports of the vendored bundle (verified by `import()` in Node this session): `Component createContext h html render
useCallback useContext useDebugValue useEffect useErrorBoundary useImperativeHandle useLayoutEffect useMemo useReducer
useRef useState`. `ntfy/app/web/static/vendor/README.txt` lists only seven as "used by the app"; `app.mjs` also imports
`useErrorBoundary`, so the lib's re-export list and its `REQUIRED_EXPORTS` test must include it (plus `useLayoutEffect`,
`useContext`, `useReducer` if the lib uses them).

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `hashlib`/`argparse`/`pathlib` (stdlib) | — | `internal/sync-admin-ui.py` | Sync + drift check; keep stdlib-only like `internal/update-version.py` |
| `zizmor` | 1.30.1 (pinned in `.pre-commit-config.yaml`) | Audits the edited `lint.yml` | Run `uvx zizmor@1.30.1 --offline --config zizmor.yml .github/workflows/lint.yml` after editing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Preact 10 bundle in htm 3.1.1 | Preact 11 (npm `preact` latest is 11.1.1) | Different bundle, new hash, re-test; out of scope for a blueprint phase. Record as follow-up in vendor README |
| Copy + hash (D-05) | git submodule / download at build | Locked by D-05; build context is `./<addon>` so neither works without changing CI |
| `light-dark()` CSS for one-block tokens | Duplicate token blocks + a parity test | `light-dark()` needs Chromium 123+; HA itself still supports Android WebView Chromium 109-124 `[VERIFIED: src/layouts/home-assistant-main.ts:183-188 comment "Android WebView (Chromium 109-124)"]`. Use duplicated blocks + test |

**Installation:** no package installs. Preact/htm is already vendored. CI needs `pip install pytest` only (pin it:
`pytest==9.2.0`).

**Version verification:** `npm view htm version` -> `3.1.1` (dist-tag latest, modified 2022-10-11); `npm view preact
version` -> `11.1.1` (not adopted); `pytest` 9.2.0 on PyPI `[VERIFIED: registry queries this session]`.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| htm | npm | ~6 yrs (3.1.1 from 2022-04-26) | ~2.7M/wk | github.com/developit/htm | OK | Approved; **not installed**, only the already vendored standalone bundle is used |
| preact | npm | ~10 yrs | ~53.6M/wk | github.com/preactjs/preact | SUS (reason `too-new`: latest release 2026-10-31) | Not installed; Preact only ships inside the vendored bundle. Version-recency false positive, no action unless the bundle is upgraded (then add `checkpoint:human-verify`) |
| pytest | PyPI | ~15 yrs (latest 9.2.0, 2026-10-27) | n/a (registry lacks counts) | github.com/pytest-dev/pytest | SUS (`too-new`, `unknown-downloads`) | Flagged: dev/CI-only, already the repo's test runner (ntfy). Planner: add `checkpoint:human-verify` before pinning it in `lint.yml` |

**Packages removed due to SLOP verdict:** none
**Packages flagged as suspicious [SUS]:** `preact` (not installed), `pytest` (CI pin) — `pytest`
`[WARNING: flagged as suspicious — verify before using.]` (verdict is a recency artifact; the name is established repo
practice, so the human check is a 10-second confirmation of the pinned version).

*`gsd-tools query package-legitimacy check` was run for `htm preact` (npm) and `pytest` (pypi). No `postinstall` script on
`htm@3.1.1`.*

## Architecture Patterns

### System Architecture Diagram

```
 HA browser tab / Companion app
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │ HA frontend (origin = HA)                                                    │
 │  ha-panel-app ──creates session cookie──> iframe src=/api/hassio_ingress/<t>/│
 │      ▲  postMessage "home-assistant/properties" {narrow,route,safeAreaInsets}│
 │      │  ◄── "subscribe-properties"{kioskMode?,handleSafeArea?} / "toggle-menu"│
 │  <html style="--primary-background-color:...">  <── theme vars (setProperty)  │
 │      │ same-origin read (try/catch)                                          │
 │  ┌───▼────────────────────── iframe (admin-ui GUI, same origin) ───────────┐ │
 │  │ index.html ─> app.mjs ─> lib/{ui,api,i18n,theme-sync,ha-bridge,...}.mjs │ │
 │  │    tokens (base.css) ◄─ theme-sync sets --sync-* + data-theme            │ │
 │  │    t(key) ◄─ strings.{de,en}.mjs   fetch("api/...") relative URLs only   │ │
 │  └───────────────────────────────┬──────────────────────────────────────────┘ │
 └──────────────────────────────────┼────────────────────────────────────────────┘
                                    │ HTTP via Core ingress proxy -> Supervisor (172.30.32.2)
 ┌──────────────────────────────────▼────────────────────────────────────────────┐
 │ add-on container: python3 -m app.main                                          │
 │  ThreadingHTTPServer ─> GATE (peer==172.30.32.2 && X-Ingress-Path) else 403    │
 │     ├─ GET / , /static/<whitelist>  (nosniff, CSP, no-cache)                   │
 │     └─ Router: /api/... -> handler(Request) -> dict | (status,dict) | None |   │
 │                 Download ; ApiError -> {"error": code, "message"} ; other ->   │
 │                 500 internal_error (traceback to stdout only)                  │
 └────────────────────────────────────────────────────────────────────────────────┘

 Repo tooling:  admin-ui/app/web/static/lib/ ──sync-admin-ui.py──> <addon>/app/web/static/vendor/admin-ui/
                admin-ui/app/web/skeleton/   ──────────────────> <addon>/app/web/admin_ui/
                tree hash + VERSION  ──> LIB.sha256 stamp ; check = pre-commit hook + make target + lint.yml job
```

### Recommended Project Structure
```
admin-ui/
├── config.yaml build.yaml Dockerfile run.sh .dockerignore
├── README.md DOCS.md CHANGELOG.md icon.png logo.png          # DOCS.md carries the blueprint rules + spike results
├── lib.lock                       # `version` + `sha256` of the current lib tree (makes drift check non-vacuous)
├── app/
│   ├── __init__.py  main.py       # `python3 -m app.main`: builds router, serves, SIGTERM handling (from ntfy gui.py)
│   └── web/
│       ├── __init__.py
│       ├── skeleton/              # SOURCE of Python lib (relative imports only): errors.py router.py static.py
│       │                          #   headers.py server.py ingress.py  -> synced to <addon>/app/web/admin_ui/
│       ├── demo_api.py            # fake in-memory API: CRUD, forced error codes, whoami, slow
│       └── static/
│           ├── index.html app.mjs app.css          # demo-only
│           ├── strings.de.mjs strings.en.mjs       # demo app strings (location is discretion, see Open Questions)
│           ├── views/*.mjs                         # gallery, tokens, i18n, crud, rules, spike
│           └── lib/                                # SOURCE OF TRUTH (D-04), self-contained directory
│               ├── VERSION
│               ├── base.css                        # tokens + base + components
│               ├── api.mjs ingress.mjs ui.mjs hooks.mjs a11y.mjs format.mjs
│               ├── i18n.mjs strings.de.mjs strings.en.mjs
│               ├── ha-bridge.mjs theme-sync.mjs shell.mjs
│               └── vendor/ preact-htm.mjs LICENSE-htm.txt LICENSE-preact.txt README.txt
└── tests/
    ├── conftest.py test_server.py test_static_rules.py test_sync.py test_js.py test_addon_scaffold.py
    └── js/ fakedom.mjs *.test.mjs
```
Rationale for `lib/vendor/` inside `lib/`: the lib's own import is `./vendor/preact-htm.mjs`, so copying the single
directory to `<addon>/app/web/static/vendor/admin-ui/` keeps every relative import valid. ntfy today imports
`../vendor/preact-htm.mjs` from `lib/ui.mjs` (ui.mjs:2), which would break after a flat copy.

### Pattern 1: Self-contained lib directory + tree hash
**What:** one directory is the unit of distribution; a deterministic hash over `(relative path, sha256 of bytes)`.
**Example (design, `[ASSUMED]` code shape; algorithm choices are mine):**
```python
def tree_hash(root: Path, skip: frozenset[str] = frozenset({"LIB.sha256"})) -> str:
    digest = hashlib.sha256()
    files = [p for p in root.rglob("*") if p.is_file() and p.name not in skip and "__pycache__" not in p.parts]
    for path in sorted(files, key=lambda p: p.relative_to(root).as_posix()):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()
```

### Pattern 2: Ingress gate first, extension points for add-on errors
Skeleton keeps ntfy's exact behaviour (gate before routing for *every* method and path, `close_connection` on errors,
`500 internal_error` with traceback only on stdout) but removes the three ntfy imports:
```python
# skeleton/errors.py  (generic ERROR_STATUS; add-ons extend it)
ERROR_STATUS = {"bad_request": 400, "ingress_only": 403, "not_found": 404, "method_not_allowed": 405,
                "conflict": 409, "protected": 409, "payload_too_large": 413, "internal_error": 500}
def register_error_code(code: str, status: int) -> None: ...
# skeleton/server.py
def make_handler(router, static: StaticFiles, *, ingress_remote=INGRESS_REMOTE, server_version="AdminUi",
                 error_mappers: dict[type[Exception], Callable[[Exception], ApiError]] | None = None): ...
```
`NtfyCliError -> api_error_from_cli` becomes an entry in `error_mappers` (ntfy-side, follow-up phase). `STATIC_DIR` stops
being a module global (ntfy's `test_static_whitelist` monkeypatches `srv.STATIC_DIR`): pass a `StaticFiles(root)` object.

### Pattern 3: Pure functions with injectable environment (testability)
`detectLang(navLike, storageLike)`, `createThemeSync({win, ...})`, `createHaBridge({win, ...})`. Reason verified here:
Node 22 already has a global `navigator` (`language` is `de-DE` on this machine) and `fakedom.mjs` does
`globalThis.navigator ??= {}` (fakedom.mjs:168), so a global stub would be non-hermetic (differs between local and CI).
`localStorage` is `undefined` in Node 22 (checked), so the `try { localStorage... } catch {}` rule must also guard
`typeof localStorage === "undefined"`.

### Pattern 4: Focus helpers that do not need a selector engine
Walk `childNodes` recursively and test `localName`/`disabled`/`tabindex` instead of `querySelectorAll`, so the same
helper runs in the real DOM and in `fakedom.mjs` (which has no `querySelector*`, `focus()`, or `activeElement`).

### Anti-Patterns to Avoid
- **Absolute URLs or leading-slash paths** anywhere (page sits below an ingress token path). `buildUrl` already throws on
  these (api.mjs:17).
- **`innerHTML`/`outerHTML`/`insertAdjacentHTML`/`dangerouslySetInnerHTML`/`document.write`/`eval`/`new Function`/string
  timers** — covered by the existing regex set in `ntfy/tests/test_frontend_static.py:30-39`; reuse verbatim.
- **Dynamic `t()` keys** (`t(\`x.${y}\`)`): defeats the "every used key exists" scan. Use a helper (`tError(code)`).
- **Dark token block written twice by hand without a test**: guarantee the two blocks stay identical by test.
- **`kioskMode:true` unconditionally**: collapses HA's docked sidebar on desktop (see HA section).
- **Importing the demo app's code from the lib or the lib from `internal/`**: the lib directory must be copyable alone.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Date/time/number/relative formatting | Hand-written `fmtUnix`/`relTime`/`fmtBytes` strings (ntfy `model.mjs:61,75,86`, English-only) | `Intl.DateTimeFormat`, `Intl.RelativeTimeFormat({numeric:"auto"})`, `Intl.NumberFormat`, `Intl.PluralRules` | Verified in Node 22: `de` -> "gestern", "01.01.1970, 00:00", "1,5"; zero code, correct de/en |
| JSON body parsing/limits, static path safety | New parser | Port ntfy's `_read_body` + `SEGMENT_RE` + `resolve().relative_to(root)` | Covered by ntfy's tests incl. symlink escape and `.py` not served |
| Component runtime | Own virtual DOM | Vendored Preact/htm | D-03 |
| Tree hashing / drift | `git diff`-based checks | `hashlib` tree hash in one stdlib script | Works on a bare checkout, in pre-commit and in CI without git history |
| Contrast math | External lib | 15-line WCAG function in a test (computed values below) | No dependency; also reused by theme-sync's guard |
| Clipboard | `execCommand` only | `navigator.clipboard.writeText` with the existing select+`execCommand` fallback (`ui.mjs:123-145`) | Keep ntfy's fallback; verified in the spike |

**Key insight:** every mechanism the lib needs is either already written and tested in ntfy or is a platform primitive
(`Intl`, `MutationObserver`, `postMessage`). The risk is not missing code, it is *unenforced* conventions, hence
the test-first rule set (D-16).

## Extraction Inventory: ntfy GUI -> lib

Sizes from `wc -l`; per-file line references below are exact (`[VERIFIED: files read this session]`).

| ntfy file | Verdict | Goes to lib | Stays ntfy-specific / needs change |
|-----------|---------|-------------|-------------------------------------|
| `lib/api.mjs` (61) | **generic, move as is** | `ApiClientError`, `buildUrl` (rejects absolute: `api.mjs:17` "absolute or empty API path rejected"), `request` (credentials `same-origin`, `cache: "no-store"`, 204 -> null, `network_error` code at `:41`), `get/post/put/patch/del` | Add `ingress.mjs`: `isIngress()`, `assertRelative(url)`, `apiHref(path)` for download links (`<a href="api/backups/x.db" download>`), `errorKey(err)` -> `errors.<code>` |
| `lib/ui.mjs` (175) | **mostly generic** | `html/render/hooks` re-exports (`:5`), `toast/Toasts` (`:8-40`, `TOAST_MS=5000`), `Modal` (`:42`), `ConfirmDialog` (`:59`), `Badge` (`:89`), `ErrorNote` (`:103`), `Loading` (`:112`), `CopyField` (`:123`), `useAsync` (`:147`), `usePoll` (`:167`) | `OriginBadge` (`:93`), `PermSelect` (`:116`) and the import of `PERMISSIONS…` from `./model.mjs` (`:3`) stay in ntfy. `ERROR_HINTS` (`:98`, ntfy db_* codes) becomes strings keys. `confirmMatches` (from `model.mjs:107`) moves to the lib. **Gaps to fix on extraction:** `aria-label="Close"` hard-coded (`:52`), `Copied`/`Copy` literals (`:128`+), `Type <code>… to confirm</code>` label not associated with the input (`:76`), no focus management in `Modal`, toast `kind` whitelist `["ok","error","info"]` fine, toasts hold final strings (not re-translated on language switch: document) |
| `lib/model.mjs` (127) | **ntfy-specific** except helpers | `fmtBytes` (`:61`), `fmtUnix` (`:75`), `relTime` (`:86`) -> rewrite as Intl-based `format.mjs`; `confirmMatches` (`:107`) -> `util` | Everything else (`PERMISSIONS`, validators mirroring `contract.py`, `matchTopic`, `buildMatrix`, `describeEffective`, `protectionLabel`) stays |
| `app.css` (131) | **split** | Lines 1-12 tokens (`--bg --fg --card --bd --mut --ok --warn --err --acc --chip --hover --shadow`), base/typography, `.topbar/.tabs/.tab`, `.card/.grid/.toolbar`, `table.data`, `.badge` + `ok/warn/error/muted`, `.btn*`, form controls + focus outline, `.form-row`, `.actions`, `.copy-field`, `.notice*`, modal, toasts, `.danger-zone/.danger-row`, `@media (max-width: 600px)` | `.badge.gui/.options/.iac` (`:55-57`), `.matrix*` (`:107-118,129-130`), `.toolbar label`. secrets-sync uses `--bar` instead of `--hover/--shadow`; blueprint token set = ntfy's plus `--on-acc` (see Pitfall 6); drop `--bar` (topbar uses `--card`) |
| `app.mjs` (125) | **mixed** | `parseHash` generalized to `parseHash(hash, ids)` (`:16`), `Boundary` (`:68`, `useErrorBoundary`), `Guarded` error handling, health-poll pattern (`usePoll(load, 15000)` `:93`) -> `shell.mjs` (`Topbar`, `TabNav`, `ErrorBoundary`, `useHashRoute`) | `VIEWS` (`:6`), `loadView` (`:34`: `import(\`./views/${id}.mjs\`)` must stay in app code so the literal relative prefix is analyzable), health text, brand icon |
| `index.html` (22) | template | meta `color-scheme`, `<link href="static/vendor/admin-ui/base.css">` + app css, module script, noscript | Title/icon; keep JS in files (CSP `script-src 'self'`) |
| `vendor/*` | **move into `lib/vendor/`** | `preact-htm.mjs`, `LICENSE-htm.txt` (Apache-2.0), `LICENSE-preact.txt` (MIT), `README.txt` (update procedure) | — |
| `server.py` (244) | **generic after 3 changes** | `Download`, `Request` (`arg/body`), `Router` (`add/routes/match`, 404/405), `resolve_static`, `make_handler`, `make_server`; limits `MAX_BODY = 65536` (`:22`), `SEGMENT_RE` (`:24`), `CONTENT_TYPES` (`:25`) | `from app.contract import INGRESS_REMOTE, ApiError, api_error_from_cli` and `from app.ntfycli import NtfyCliError` (`:18-19`), `server_version = "NtfyGui"`, module-global `STATIC_DIR` (`:21`), `ERROR_STATUS` ntfy codes (`contract.py:203`: includes `ntfy_error`, `db_*`, `locked`) |
| `app/gui.py` (45) | pattern for `app/main.py` | SIGTERM/SIGINT -> `server.shutdown()` in a thread (`gui.py:30-35`), `serve_forever`/`server_close` | env names (`NTFY_GUI_PORT`) |
| `tests/js/fakedom.mjs` (174) | **move to lib tests** | whole file | add `focus/activeElement/contains`, more `EVENT_PROPS` (see a11y) |
| `tests/js/api.test.mjs`, `ui.test.mjs`, `model.test.mjs` | port | api tests as is; `ui` export-contract test with new `EXPECTED` list; format tests rewritten for Intl | `views.test.mjs`/`topic_cases.json` stay ntfy |
| `tests/test_server.py` (157) | port | gate/router/body/response/exception/static-whitelist tests; `test_response_kinds` currently asserts `X-Frame-Options is None` for static (page must be frameable) — keep, add CSP assertions | monkeypatch of `srv.STATIC_DIR` -> pass `StaticFiles(tmp)` |
| `tests/test_frontend_static.py` (92) | port + generalize | `SHA256` (`:16`), `REQUIRED_EXPORTS`, `URL_PATTERNS`, `DANGEROUS_PATTERNS` (`:30-39`), per-file parametrization excluding `vendor/`, `test_scan_patterns_detect` self-test | hash constant duplicated in ntfy until its migration phase |
| `tests/test_js.py` (20) | port | `node --test <explicit files>` (Node 22 rejects a directory arg; ntfy passes explicit files `test_js.py:16-17`), skip without node | — |

Existing fake-DOM tests drive Preact through `render(html\`...\`, root)` then `await settle()` (6 x 5 ms) and read
`findAll/findByText/prop` (`views.test.mjs:59-68`). `views.test.mjs` ends with
`setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref()` (line 178) because toast/poll timers keep the worker
alive; every lib test file that triggers `toast()` or `usePoll` needs the same hook (or the lib uses `unref` where
available).

## Add-on Scaffold (copy from haos-monitor + ntfy) and Registration Checklist

Model files (all read this session): `haos-monitor/{config,build}.yaml`, `haos-monitor/Dockerfile`,
`ntfy/{config,build}.yaml`, `ntfy/Dockerfile`, `ntfy/run.sh`, `ntfy/.dockerignore`, `ntfy/README.md`, `ntfy/DOCS.md`,
`ntfy/CHANGELOG.md`.

**Files to create in `admin-ui/`:**

| File | Content / rule |
|------|----------------|
| `config.yaml` | Required by `internal/validate-addon-config.py`: `name version slug description arch startup boot` `[VERIFIED: validate-addon-config.py REQUIRED_FIELDS]`. Recommended: `name: "Admin UI Blueprint"`, `version: "0.1.0-0"`, `slug: "admin_ui"` (image name derives from the directory: `tr '-' '_'`, see `_build-template.yml` "Compute image slug"), `init: false`, `arch: [amd64]`, `image: "ghcr.io/akentner/homeassistant-addons/{arch}-admin_ui"`, `startup: "application"`, `boot: "manual"`, `ingress: true`, `ingress_port: 8099`, `panel_icon: "mdi:palette-swatch"`, `panel_title: "Admin UI"`, `panel_admin: false` (needed for the spike's non-admin check, safe: fake data only), **no `ports:`** (gate is the only protection, do not publish), `options: {}`, `schema: {}`. `build_from`/`args` belong in `build.yaml`, not here (ntfy `config.yaml` has none) |
| `build.yaml` | Mirror haos-monitor/ntfy (`build.yaml:1-4`): `build_from:\n  amd64: "ghcr.io/home-assistant/amd64-base:3.24"` + `args:\n  VERSION: "0.1.0"`. `make build-addon` greps `amd64:` and `VERSION:` from this file `[VERIFIED: Makefile build-addon]`; `validate-versions.sh` regex needs `VERSION: "X.Y.Z"` quoted |
| `Dockerfile` | `ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24` **before** `FROM ${BUILD_FROM}` (validator rule), `RUN apk add --no-cache python3`, `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1`, `WORKDIR /opt/admin-ui`, `COPY app/ ./app/`, `COPY run.sh /run.sh`, `RUN chmod +x /run.sh`, `CMD ["/run.sh"]` (ntfy `Dockerfile:21-27`). hadolint runs with DL3008/DL3018/DL3059/DL4006/DL3016 ignored |
| `run.sh` | `#!/usr/bin/with-contenv bashio` + `# shellcheck shell=bash`, `cd /opt/admin-ui`, export add-on version from `bashio::app.version \|\| bashio::addon.version` (ntfy `run.sh:11`), `exec python3 -m app.main`. Must be git-mode 100755 (`check-shebang-scripts-are-executable`) |
| `.dockerignore` | `tests/`, `docs/`, `.pytest_cache/`, `**/__pycache__/` (ntfy's) |
| `README.md` | Needs a line with `version-v0.1.0-` for `validate-versions.sh`: ntfy/haos-monitor use `[release-shield]: https://img.shields.io/badge/version-v0.6.1-blue.svg` + `[release]: .../tree/v0.6.1` link-reference definitions (haos-monitor README tail). Write by hand once, then only via `make update-version` |
| `DOCS.md` | The blueprint rules, lib API, sync workflow, migration paths (D-07), spike results (D-14). Own-code exception paragraph (copy haos-monitor `DOCS.md:5-9`) |
| `CHANGELOG.md` | Hand-written (haos-monitor style; `**/CHANGELOG.md` is excluded from markdownlint) |
| `translations/en.yaml`, `de.yaml` | Only needed when `options` exist. With `options: {}` skip them (HA reads none); keep the door open for later options |
| `icon.png` / `logo.png` | Optional; ntfy and haos-monitor ship both |
| **no** `.upstream.yaml` | Absence is what keeps auto-update away: lint.yml only validates `.upstream.yaml` if present `[VERIFIED: lint.yml "Validate Add-on configurations"]` |

**Registration places outside `admin-ui/` (complete list):**

| # | File | Change | Evidence |
|---|------|--------|----------|
| 1 | `.github/workflows/build.yml` | **None.** Add-on is auto-detected from the `config.yaml`+`build.yaml`+`Dockerfile` triple; path filter is `*/**` minus dot-dirs/docs/internal/tools/provider; name must match `^[a-z0-9][a-z0-9._-]*$` (`admin-ui` does) | build.yml `paths:` + detect step |
| 2 | `.github/workflows/_build-template.yml` | **None.** `context: ./<addon>` (line 163), tags `…/{arch}-admin_ui:<config version>` | read lines 60-215 |
| 3 | `internal/base-image-config.yaml` | **Add** `admin-ui:` entry identical to `ntfy`/`secrets-sync` (`image: ghcr.io/home-assistant/amd64-base`, `source_repo: home-assistant/docker-base`, `source_file: alpine/Dockerfile`, `version_pattern: 'ARG ALPINE_VERSION=(?P<version>\d+\.\d+)'`). The base-image workflow iterates exactly this file; it bumps `build.yaml`, `config.yaml` subpatch and README. NOTE: `haos-monitor` is **not** in this file (gap, out of scope) | `base-image-config.yaml`, `base-image-update.yml:101-103`, `update-base-image.py:10-12` |
| 4 | root `README.md` | **Add** an `### [Admin UI Blueprint](./admin-ui)` section in the add-on list (pattern at README `### [ntfy](./ntfy)`: amd64 shield, italic one-liner, paragraph, **Features:** list). Link-reference definitions are only needed for new external URLs | README.md:158-205 |
| 5 | `CLAUDE.md` (repo) | Extend "Exception: `haos-monitor` (own code)" to also name `admin-ui`; add one line about `make sync-admin-ui` | CLAUDE.md:125-131 |
| 6 | `Makefile` | Add targets `sync-admin-ui`, `check-admin-ui-sync` (+ `.PHONY`, `## ` help comments) and add `check-admin-ui-sync` to `check-all` (offline + deterministic, like `validate-versions`) | Makefile policy comment above `verify-images` |
| 7 | `.pre-commit-config.yaml` | Add a `repo: local` hook (pattern: `verify-opencode-gate`: scoped `files:` regex, `pass_filenames: false`, `language: system`) | pre-commit config |
| 8 | `.github/workflows/lint.yml` | Add job `admin-ui` **at the end of the file**; change `lint-results` line `needs: lint` -> `needs: [lint, admin-ui]` and the one `if [[ ... ]]` line, both single-line edits | zizmor.yml line anchors, see CI section |
| 9 | `docs/DEVELOPMENT.md` | Add a short "Admin UI blueprint / sync" section | docs |
| 10 | `internal/verify-admin-ui-scaffold.sh` (optional) | Docker smoke test modeled on `internal/verify-ntfy-scaffold.sh` (build, start, gate 403 without header, 200 with header + `X-Ingress-Path`). Satisfies CLAUDE.md "local docker build before commit" reproducibly | verify-ntfy-scaffold.sh:1-60 |
| 11 | `.github/renovate.json` | **None** (vendor bundle is updated by hand per README procedure) | read |
| 12 | `.gitleaks.toml`, `zizmor.yml` | **None** (verified for zizmor with an appended job) | below |

Auto-discovered, no edit needed: `validate-versions.sh` (any dir with config.yaml+build.yaml, depth 2),
`validate-addon-config.py`, `Makefile validate-addons`, `make validate-dockerfiles` (`find . -maxdepth 2 -name
Dockerfile`), `docker-build-check`, `internal/verify-image-availability.sh` (reads the `image:` key; will be red until the
first image build lands after merge — expected), `dispatch-builds.sh`, `check-version-tags.sh`.
Note: `.pre-commit-config.yaml` `validate-dockerfile-args` hook has a `files:` regex naming only
`phone-logger|meridian|iac-runner`; `admin-ui` is covered by `make validate-dockerfiles` instead (optionally add it to the
regex).

Initial version: write `0.1.0-0` / `0.1.0` / `v0.1.0` directly in the scaffold commit. Later bumps:
`make update-version ADDON=admin-ui VERSION=0.1.1-1 NO_TAG=yes NO_PUSH=yes` while on the feature branch (the script
otherwise tags and pushes; CLAUDE.md says ask before version bumps/tags).

## Sync and drift tooling

**Mapping (single table at the top of `internal/sync-admin-ui.py`, `[ASSUMED]` names):**

| Source | Consumer target |
|--------|-----------------|
| `admin-ui/app/web/static/lib/` | `<addon>/app/web/static/vendor/admin-ui/` (D-05) |
| `admin-ui/app/web/skeleton/` | `<addon>/app/web/admin_ui/` (Python package, relative imports only; **not named in D-05**, see Open Questions) |

**Stamp files in each consumer copy** (plain text, not JSON: `.pre-commit-config.yaml` runs
`pretty-format-json --autofix --indent=2`, which would reformat a JSON stamp and fight the script):
`VERSION` (copied from source) and `LIB.sha256` (one line, the tree hash; excluded from the hash itself). Both need a
trailing newline (`end-of-file-fixer`).

**Source side:** `admin-ui/lib.lock` = two lines `version <VERSION>` / `sha256 <tree hash of both source trees>`,
rewritten by `make sync-admin-ui`. Check 0: source tree hash equals `lib.lock` (so a lib edit without
re-running sync/bumping `VERSION` is red even with zero consumers).

**Consumer discovery:** any `*/app/web/static/vendor/admin-ui/LIB.sha256` (or `*/app/web/admin_ui/LIB.sha256`). A new
consumer opts in once with `make sync-admin-ui ADDON=<name>` (creates the copy + stamp).

**Checks (`--check`):**
1. source tree hash == `lib.lock`;
2. per consumer: recomputed hash of the copy == its `LIB.sha256` (catches hand-edited copies; this is the "pin by hash"
   of D-06);
3. per consumer: if its `VERSION` == source `VERSION` then its hash must equal the source hash; if it differs, report
   "behind (consumer X, source Y)" — **exit 0 by default, non-zero with `--strict`**. Rationale: D-06 says consumers
   "pull updates deliberately"; failing every consumer on every lib change would contradict that. Flagged as Open
   Question 1 because "drift check fails on mismatch" can also be read as strict equality.

**Wiring (patterns copied from the repo):**
```make
sync-admin-ui: ## Copy the admin-ui lib into all consumers and refresh stamps (ADDON=<name> adds a new consumer)
	python3 internal/sync-admin-ui.py $(if $(ADDON),--add $(ADDON),)
check-admin-ui-sync: ## Fail if lib.lock or a consumer copy drifted (offline)
	python3 internal/sync-admin-ui.py --check
```
```yaml
      - id: check-admin-ui-sync
        name: Check admin-ui lib copies are in sync
        entry: python3 internal/sync-admin-ui.py --check
        language: system
        pass_filenames: false
        files: ^(admin-ui/(lib\.lock|app/web/(static/lib|skeleton)/)|[^/]+/app/web/(static/vendor/admin-ui|admin_ui)/|internal/sync-admin-ui\.py)
```
Pre-commit scoping argument (same as the `verify-opencode-gate` hook comment): the check reads a known set of paths, so a
path-scoped trigger is a complete trigger set; `lint.yml` runs `pre-commit run --all-files`, so it also runs in CI.

Sync hygiene: the copied files must already be hook-clean (LF, no trailing whitespace, final newline) or pre-commit will
rewrite them and the *committed* bytes will differ from the hash recorded by the script; the script should copy bytes
verbatim and the source tree must be hook-clean first. Avoid `.md` files inside the lib (would be linted/prettier'd in
every consumer): use `README.txt` like ntfy's vendor dir. Mixed content such as `LICENSE-*.txt` is fine.

Unit tests for the script (`tests/test_sync.py`, tmp-dir fake repo): fresh sync creates copy+stamp; second run is a no-op;
hand-edit of a copied file -> check fails (rule 2); source edit without sync -> fails (rule 0); consumer behind -> exit 0
unless `--strict`; `__pycache__` ignored; hash independent of file order.

## CI: node --test + pytest + sync check in `lint.yml`

State today `[VERIFIED: .github/workflows/lint.yml read in full]`: single job `lint` (Python 3.12, Node 22, pre-commit,
markdownlint-cli2) and a `lint-results` job (`needs: lint`, line 160). **No pytest and no `node --test` run in CI**; ntfy's
Node tests run only through `ntfy/tests/test_js.py` locally (skipped without node).

Recommended job (append after `lint-results`; verified clean with `zizmor 1.30.1 --offline --config zizmor.yml`: "No
findings to report"):
```yaml
  admin-ui:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
    steps:
      - name: Checkout repository
        uses: actions/checkout@v7
        with:
          persist-credentials: false
      - name: Set up Python
        uses: actions/setup-python@v7
        with:
          python-version: '3.12'
      - name: Set up Node.js
        uses: actions/setup-node@v7
        with:
          node-version: '22'
      - name: Install test dependencies
        run: python -m pip install pytest==9.2.0
      - name: Lib unit tests (node)
        run: node --test admin-ui/tests/js/*.test.mjs
      - name: Server and rule tests (pytest)
        run: python -m pytest admin-ui/tests -q
      - name: Lib copies in sync
        run: make check-admin-ui-sync
```
Why appended and single-line edits: `zizmor.yml` carries **line/column-anchored** deferrals for `lint.yml`
(`lint.yml:22:9`, `:16:3`, `:58:11`, `:160:3`, `:1:1`; zizmor.yml header says entries go stale when lines shift and the hook
goes red). Inserting the job before line 160 or adding lines above it would break them. Editing `needs: lint` and the single
`if [[ "${{ needs.lint.result }}" == "success" ]]` line in place does not shift lines. `node --test` with a shell glob
works (ran the 25 ntfy tests that way); pass explicit files, Node 22 rejects a directory argument (ntfy `test_js.py:16-17`).
`test_js.py`-style wrapper inside `admin-ui/tests` is still worthwhile for local `pytest` runs, but then CI would run the
node tests twice; either keep the wrapper (skip in CI via env) or run only pytest in CI. Recommended: keep both locally
and in CI (cost: ~1 s), simpler than conditional skipping.

Also: the existing `lint` job's "Lint shell scripts" step runs `shellcheck` on every `*.sh` (so `admin-ui/run.sh` and any
`internal/verify-admin-ui-*.sh` are checked) and `markdownlint-cli2 "**/*.md"`. `.planning/` is excluded from both
markdownlint and prettier.

## Theme and iframe facts (verified against HA frontend source)

Sources read in full this session: `src/panels/app/ha-panel-app.ts` (589 lines), `src/layouts/home-assistant-main.ts` (228),
`src/state/themes-mixin.ts` (195), `src/common/dom/apply_themes_on_element.ts` (202), `src/data/hassio/ingress.ts` (62),
`src/resources/theme/color/color.globals.ts` (405), `core.globals.ts`, `main.globals.ts`; Core
`homeassistant/components/hassio/ingress.py`; Supervisor `supervisor/api/ingress.py`. Frontend `dev` HEAD
`78f6a55e3c507a0ee67ab69a97069c6e25398989` (2026-11-02); latest stable tag `20260930.5` (2026-10-23).

### Verified

| # | Fact | Evidence (quote verbatim) |
|---|------|--------------------------|
| H1 | The app panel is an iframe **without** `sandbox` and without `allow` | `ha-panel-app.ts:139-150`: `<iframe class=${classMap({ loaded: ..., "kiosk-mode": ..., "handle-safe-area": ... })} title=${this._addon.name} src=${this._addon.ingress_url!} @load=${this._checkLoaded} ${ref(this._iframeRef)}>` |
| H2 | HA reads `iframe.contentDocument` of the app, i.e. ingress is same-origin with HA | `ha-panel-app.ts:353-355`: `iframe.contentDocument?.body.textContent === "502: Bad Gateway"` |
| H3 | HA listens to `window` messages, accepts only `event.source === iframe.contentWindow`; handled types: `home-assistant/navigate` (`navigate(data.path, data.options)`), `home-assistant/toggle-menu`, `home-assistant/subscribe-properties`, `home-assistant/unsubscribe-properties` | `ha-panel-app.ts:416-452` |
| H4 | `subscribe-properties` data: `handleSafeArea` (`this._handleSafeArea = !!data.handleSafeArea`), `kioskMode` (`if (data.kioskMode && !this.hass.kioskMode) { this._enabledKioskMode = true; fireEvent(window, "hass-kiosk-mode", { enable: true }); }`); then `_sendPropertiesToIframe()` | `ha-panel-app.ts:431-441` |
| H5 | HA -> iframe message: `{ type: "home-assistant/properties", narrow, route, safeAreaInsets: {top,right,bottom,left} }`, posted with targetOrigin `"*"`, sent again on `narrow`/`route` change and on window `resize`; insets are trimmed CSS strings (`styles.getPropertyValue("--safe-area-inset-top").trim()`) | `ha-panel-app.ts:78-83,456-489` |
| H6 | HA's own bar: rendered only when `!this._kioskMode && (this.narrow \|\| this.hass.dockedSidebar === "always_hidden")`; height `calc(40px + var(--safe-area-inset-top, 0px))`; iframe below it `height: calc(100% - 40px - var(--safe-area-inset-top, 0px))`; menu button fires `hass-toggle-menu` | `ha-panel-app.ts:125-137,540-568` |
| H7 | Safe-area padding is applied **on the iframe element** ("CSS variables don't cross the iframe boundary"); `handleSafeArea` removes it (`iframe.handle-safe-area { padding: 0; }`) | `ha-panel-app.ts:510-537` |
| H8 | `kioskMode` also changes the sidebar: `const sidebarNarrow = this._sidebarNarrow \|\| this._externalSidebar \|\| this.hass.kioskMode;` (modal drawer), and `hass-toggle-menu` then toggles the drawer (`if (this._sidebarNarrow \|\| this.hass.kioskMode) { this._drawerOpen = ev.detail?.open ?? !this._drawerOpen; }`) | `home-assistant-main.ts:62-63,122-124` |
| H9 | `narrow` = media query `(max-width: 870px)` | `home-assistant-main.ts:56` |
| H10 | `_enabledKioskMode` is reset to disabled when the panel is disconnected, when switching app, and on `unsubscribe-properties` | `ha-panel-app.ts:110-112,183-188,443-450` |
| H11 | Theme variables are written by `style.setProperty` on the **parent `document.documentElement`** (also `document.documentElement.style.backgroundColor = computedStyles.getPropertyValue("--primary-background-color")`); there is no event, no `hass` push to the iframe | `themes-mixin.ts:141-147,177-178`; `apply_themes_on_element.ts:148-153` |
| H12 | Default (light) values come from `html { ... }` stylesheet rules, dark values are applied inline as `darkColorVariables`; so `getComputedStyle(parent.documentElement).getPropertyValue("--primary-background-color")` works for both. Early dark apply on first load when `prefers-color-scheme: dark` | `color.globals.ts:46-48` (`--card-background-color: #ffffff; --primary-background-color: #fafafa; --secondary-background-color: #e5e5e5;`), `:342-345` (dark `#111111/#1c1c1c/#282828`); `apply_themes_on_element.ts:54-57`; `themes-mixin.ts:53-66` |
| H13 | Variable names that exist (all in `color.globals.ts`): `--primary-text-color`, `--secondary-text-color`, `--text-primary-color`, `--disabled-text-color`, `--primary-color`, `--accent-color`, `--divider-color`, `--outline-color`, `--shadow-color`, `--error-color`, `--warning-color`, `--success-color`, `--info-color`, `--card-background-color`, `--primary-background-color`, `--secondary-background-color` (`:8-48`). `--primary-text-color: var(--ha-color-text-primary)` and `--primary-color: var(--ha-color-primary-40)` are var() references, `computed` values resolve them; `--ha-color-primary-40: #009ac7` (`color/core.globals.ts:22`) |
| H14 | A custom theme (user YAML) can override any of them and `modes.dark/modes.light` pick the variant; a theme without `modes` forces `darkMode = false` for light-only etc. | `themes-mixin.ts:128-134`; `apply_themes_on_element.ts:119-131` |
| H15 | Ingress session cookie: `ingress_session=<id>;path=/api/hassio_ingress/;SameSite=Strict` (+`;Secure` on https), created per panel open and kept alive every 60 s | `data/hassio/ingress.ts:6-10`; `ha-panel-app.ts:336-345` |
| H16 | `X-Ingress-Path` is set by **Core**: `headers[X_INGRESS_PATH] = f"/api/hassio_ingress/{token}"` with `X_INGRESS_PATH = "X-Ingress-Path"` | `homeassistant/components/hassio/ingress.py:275` (`_init_header` at `:266`), `const.py:76` |
| H17 | Response headers from the add-on pass through Core and Supervisor except `Transfer-Encoding`, `Content-Length`, `Content-Type`, `Content-Encoding` -> add-on CSP/nosniff reach the browser; neither proxy adds XFO/CSP | `core .../ingress.py` `RESPONSE_HEADERS_FILTER`; `supervisor/api/ingress.py:65-73` |
| H18 | Supervisor adds user identity request headers `X-Remote-User-Id`, `-Name`, `-Display-Name`, `-Groups` (`","`-joined `effective_group_ids`) and strips client-supplied ones; useful to display admin/non-admin in the spike | `supervisor/api/ingress.py:410-419` (`_init_header`), `supervisor/const.py:112-115` |
| H19 | Dashboard "webpage" card iframes are sandboxed `allow-forms allow-popups allow-pointer-lock allow-same-origin allow-scripts allow-modals allow-downloads` with `allow="fullscreen"` and **do not** run the postMessage handler | `src/util/iframe.ts` (`IFRAME_SANDBOX`), `hui-iframe-card.ts:102-125` |
| H20 | Protocol age: `subscribe-properties` + `kioskMode` present in frontend tag `20260128.0`; `handleSafeArea` first in `20260729.0` (absent in `20260624.6`); present in stable `20260930.5` | `curl` + `grep -c` over tagged `ha-panel-app.ts` this session; PR "Add safe area handling and opt-out to custom panels and apps (#53127)" |
| H21 | Latest `ha-panel-app.ts` commits: ingress websocket commands (#54695, 2026-10-26, dev/prerelease only), timers cleanup (#55056), route for sidebar entries (#54404) | `gh api commits?path=...` |

### Uncertain / not verifiable from source (all `[ASSUMED]`, settled by the spike)
- A1: whether `window.parent.document`/`getComputedStyle` on the parent works in every context (Companion app WebViews,
  non-default `frontend_url`/proxies, `X-Frame-Options`), and that a `MutationObserver` created in the iframe can observe the
  parent's `documentElement` `style` attribute across all browsers.
- A2: that Companion apps reuse the same `ha-panel-app` path (the external-app sidebar flag `hass.auth.external.config
  .hasSidebar` redirects `toggle-menu` to a native `sidebar/show` message, `home-assistant-main.ts:104-118`).
- A3: no documentation: GitHub code search of `home-assistant/developers.home-assistant.io` for `subscribe-properties`
  returned nothing, and the only hit in the frontend is `ha-panel-app.ts`. This is an absence in a search index, not proof;
  treat the protocol as **undocumented and without stability promise** (CONTEXT cites the same).
- A4: CONTEXT cites `frontend/discussions/52204` ("ingress in dashboard cards fails with 401"); the discussion could not
  be found by number via the API (404). Treat the 401 behaviour as unverified; the spike must test it (cookie
  `SameSite=Strict`, `path=/api/hassio_ingress/`, session created only by opening the panel).
- A5: that `getComputedStyle` of custom properties returns var()-substituted values consistently across browsers
  (specified by CSS, but untested here).
- A6: dynamic `kioskMode` toggling by narrow state (see below) re-subscribes cleanly without flicker/loops.

### Design consequences (prescriptive)

**`ha-bridge.mjs`** (injectable `win`): active only when `win.parent !== win`; `subscribe({kioskMode, handleSafeArea})`
posts `{type: "home-assistant/subscribe-properties", ...}` to `win.parent` (targetOrigin `win.location.origin`, which
equals HA's origin under ingress; `[ASSUMED]`); listens on `message` and accepts only
`event.source === win.parent && event.data?.type === "home-assistant/properties"` (HA posts with `"*"`, so source+origin
checks are the only authentication); exposes state `{narrow, route, safeAreaInsets, lastMessageAt}` via a tiny store;
`toggleMenu()` posts `home-assistant/toggle-menu`; `navigate(path)` posts `home-assistant/navigate`; `dispose()` posts
`unsubscribe-properties`. No answer within e.g. 1500 ms -> `state.available = false`, fixed layout (D-13 fallback).
`handleSafeArea` stays **false**: HA already pads the iframe (H7), a topbar below the padded area is correct, and opting
in costs inset plumbing for no gain; document as an option, record spike result.

**Topbar policy** (replaces the naive reading of D-13):
- `narrow === false`, docked sidebar: HA shows nothing above the iframe -> our 56px bar is the only bar. No menu button.
- `narrow === true` (HA would show its 40px bar): call `subscribe({kioskMode: true})` -> HA hides its bar, sidebar becomes a
  drawer, our bar shows a menu button that posts `toggle-menu` (H8 shows this opens the drawer under kiosk).
  Because `kioskMode` is only evaluated when subscribing (`data.kioskMode && !this.hass.kioskMode`) and only cleared by
  `unsubscribe`/disconnect (H10), the bridge must drive kiosk **only from `narrow` transitions**: `narrow false -> true`:
  subscribe with kiosk; `true -> false`: `unsubscribe-properties` then `subscribe-properties` without kiosk (updates must
  resume; unsubscribe also stops `properties`). Never react to the echo of our own transition.
- Desktop with `dockedSidebar === "always_hidden"`: HA draws its 40px bar although `narrow === false`; `properties` does
  not carry `dockedSidebar` (H5). Detect by `win.frameElement?.getBoundingClientRect().top` (same-origin) being >= 40
  after subtracting the safe-area top; if so request kiosk as above. `[ASSUMED]` heuristic, spike item S5. Fallback: accept a
  double bar and document it.
- Enabling kiosk on desktop is **not** done: it would turn the user's docked sidebar into a modal drawer for as long as the
  page is open (H8).

**`theme-sync.mjs`**: active only if `win.parent !== win`; everything in `try/catch`:
```js
// read (parent = win.parent) — [ASSUMED] shape, names verified above
const cs = parent.getComputedStyle(parent.document.documentElement);
const read = (name) => cs.getPropertyValue(`--${name}`).trim();
```
Whitelist -> own `--sync-*` props set on `document.documentElement` and consumed in `base.css` as
`--bg: var(--sync-bg, #f4f5f7);` (this is D-11's `var(--…, default)` mapping; failure = property absent = own default):

| Own token | HA variable (verified name) | Note |
|-----------|-----------------------------|------|
| `--bg` | `--primary-background-color` | luminance source for `data-theme` (D-12) |
| `--card` | `--card-background-color` | |
| `--chip` | `--secondary-background-color` | |
| `--fg` | `--primary-text-color` | |
| `--mut` | `--secondary-text-color` | contrast guard |
| `--bd` | `--divider-color` | usually `rgba(...)` |
| `--acc` | `--primary-color` | HA default `#009ac7` is only 3.26:1 on white (computed): use for fills/borders/focus, guard before using as text |
| `--ok/--warn/--err` | `--success-color/--warning-color/--error-color` | HA defaults fail AA as text on white (`#ffa600` 1.96:1, `#43a047` 3.30:1, `#db4437` 4.29:1, computed): **do not sync by default**, or sync only after the guard |

Contrast guard (recommended): before applying a synced text/background pair, compute the WCAG ratio; if < 4.5, skip that
token (own default stays). `data-theme` = `dark` when relative luminance of the parsed `--primary-background-color` is
< 0.179 (the point where white and black have equal contrast), else `light`; unparseable value -> abort sync entirely.
Parse `#rgb`, `#rrggbb`, `rgb()/rgba()` only.
Change detection: `new parent.MutationObserver(apply).observe(parent.document.documentElement, {attributes: true,
attributeFilter: ["style"]})` (H11: every theme change goes through `style.setProperty`), plus
`visibilitychange`/`focus` re-read and a 2-5 s poll as safety net (Claude's discretion), plus the parent's
`meta[name=color-scheme]` content (changed by `_applyTheme`). Expose `status()` -> `{active, reason, lastSync, mode}` for the
demo's live status chip. Scoped demo panels (`[data-theme="dark"]` token view) must neutralise inherited `--sync-*`
(`--sync-bg: initial` etc.) to show true tokens.

## i18n design (`lib/i18n.mjs`)

- Language resolution (D-08): stored choice (`localStorage` key `admin-ui:lang`) -> `navigator.language` startsWith `de` ->
  `de` else `en`. Pure `detectLang(navLike, storage)` for tests. **All ingress GUIs share HA's origin, hence the same
  `localStorage`** (also HA's own keys): namespacing `admin-ui:` is mandatory, and the shared choice across add-ons is a
  feature. Wrap every access in `try/catch` and guard `typeof localStorage`.
- API: `t(key, params)` (fallback chain active -> `en` -> `[key]` visible marker), `tp(key, n, params)` using
  `Intl.PluralRules` with `key.one`/`key.other` (de and en both have one/other, parity test covers it), `setLang(lang)`
  (persist, set `document.documentElement.lang`, notify subscribers), `useLang()`/`useT()` hook returning `t` bound to the
  current language and re-rendering on change (module-level listener set exactly like toasts in `ui.mjs:8-40`),
  `registerStrings({de, en})` for add-on strings, `tError(err)` -> `errors.<code>` else
  `t("errors.unknown", {code})` => e.g. "Unbekannter Fehler [teapot]" (D-10).
- Strings: flat dotted keys in `export default {...}` modules, lib base namespaces `btn.* dlg.* errors.* state.* format.*
  lang.*`. Add-on strings in their own pair, loaded with static `import` (both languages, a few KB; no async flash).
- Formatting (`format.mjs`): `formatDateTime(ts, lang)` = `Intl.DateTimeFormat(lang, {dateStyle:"medium", timeStyle:"short"})`,
  `formatRelative(ts, lang, now)` = `Intl.RelativeTimeFormat(lang, {numeric:"auto"})` choosing the unit by magnitude,
  `formatBytes(n, lang)` = `Intl.NumberFormat(lang, {maximumFractionDigits: 1})` + `B/KiB/MiB/GiB` (unit symbols are not
  translated). Browser local time zone, which can differ from the HA server zone: document.
- Tests (`i18n.test.mjs`): (1) key-set equality of `strings.de.mjs` vs `strings.en.mjs` for lib **and** every
  `strings.{de,en}.mjs` pair found under `static/` outside `vendor/`; (2) placeholder parity (`{name}` sets per key);
  (3) every literal `t("…")`/`tp("…")`/`tError` usage in lib + demo sources resolves to an `en` key (regex scan,
  dynamic keys are forbidden by rule); (4) `detectLang` table (`de-DE`, `de`, `en-US`, `fr`, stored override, throwing
  storage); (5) switching language re-renders a component in the fake DOM; (6) no `[key]` marker appears when the whole
  demo gallery is rendered in each language.
- Known limitation to document: `toast(kind, text)` stores a final string, so open toasts are not re-translated on a
  language switch (acceptable, they expire in 5 s).

## a11y minimum (what the fake-DOM harness can prove)

Current `fakedom.mjs` (174 lines) supports: `appendChild/insertBefore/removeChild`, `setAttribute/getAttribute`,
`addEventListener/removeEventListener/dispatch(type, extra)` (the `extra` object overrides `preventDefault` so tests can
spy), `textContent`, `className`, `FakeText`, `findAll/findByText/prop/settle`. **Missing, to add:** `focus()` that sets
`document.activeElement` (and `blur()`), `contains(node)`, `document.activeElement`, `tabIndex`, extra `EVENT_PROPS`
(`onkeyup`, `onkeypress`, `onpointerdown`, `onfocusin`: Preact picks `name.toLowerCase() in dom` to decide the event name,
so an unlisted handler is registered under the wrong case; ntfy lists only 8 handlers, `fakedom.mjs:3`), a stub
`querySelector/querySelectorAll` is **not** needed if the lib uses childNode-walk helpers.

Checks to implement (all automated; D-16 asks for the first four):
1. `Modal`: renders `role="dialog"`, `aria-modal="true"`, non-empty `aria-label` or `aria-labelledby` pointing at an existing
   id; close button has a localized `aria-label` (today hard-coded `"Close"`, `ui.mjs:52`).
2. `Modal` focus: on mount focus moves into the dialog (first focusable, or the container with `tabindex="-1"`); `Tab` on the
   last focusable wraps to the first and `Shift+Tab` on the first wraps to the last (both `preventDefault` called); `Escape`
   calls `onClose`; on unmount focus returns to the previously active element.
3. `Toasts`: container `aria-live="polite"` (exists, `ui.mjs:34`); error toasts and `ErrorNote` use `role="alert"`
   (ErrorNote has it, `ui.mjs:106`).
4. `ConfirmDialog`: confirm disabled until the exact phrase is typed; the phrase input has an accessible name (give the
   `<label for>`/`id` pair — today the label is not associated, `ui.mjs:76`); initial focus on **Cancel** for `danger`.
5. Accessible-name sweep: render the whole demo gallery and assert every `button`, `a[href]`, `input`, `select`, `textarea`
   has text, `aria-label`, or an associated `label`; every `th` in a data table has `scope`.
6. Navigation: route tabs are links in a `<nav aria-label>` with `aria-current="page"` on the active one; the in-page
   `Tabs` component (demo requires "tabs") uses `role=tablist/tab/tabpanel`, `aria-selected`, roving `tabindex`, Arrow-key
   handling.
7. Static CSS checks (pytest on `base.css`): contains `:focus-visible` rule, `@media (prefers-reduced-motion: reduce)`,
   `[data-theme="dark"]` block identical to the `@media (prefers-color-scheme: dark)` block, only declared tokens used by
   `var(--…)`.
8. Optional, cheap and valuable despite D-16: token contrast test (below).

**Computed contrast of the current ntfy tokens** (`app.css:3-4` light, `:9-10` dark; WCAG relative-luminance formula,
computed this session):

| Pair | Light | Dark |
|------|-------|------|
| `--fg` on `--bg` | 15.31 | 15.17 |
| `--mut` on `--bg` / `--card` / `--chip` | **4.43** / 4.83 / **4.23** | 7.14 / 6.42 / 5.46 |
| `--ok` on `--card` / `--chip` | 5.08 / **4.45** | 6.59 / 5.61 |
| `--warn` on `--card` / `--chip` | 4.87 / **4.26** | 6.63 / 5.64 |
| `--err` on `--card` / `--chip` | 5.36 / 4.69 | 4.99 / **4.25** |
| `--acc` on `--card` / `--chip` | 5.19 / 4.55 | 6.63 / 5.64 |
| white text on `--acc` (`.btn`) | 5.19 | **2.53** |
| white text on `--err` (`.btn.danger`) | 5.36 | **3.35** |

Bold = below 4.5:1 (WCAG AA body text). So the extracted tokens as they stand fail AA in several places, notably the dark
primary button. Fix while extracting: introduce `--on-acc`/`--on-err` (dark text on the light dark-mode accents), darken
light `--mut`, and put badge text on `--card` not `--chip` or darken accordingly; then lock it with the contrast test.

## Common Pitfalls

### Pitfall 1: Relative imports break after a flat copy
**What goes wrong:** ntfy `lib/ui.mjs:2` imports `../vendor/preact-htm.mjs`; copying `lib/` alone to
`vendor/admin-ui/` makes that resolve to `static/vendor/preact-htm.mjs` (nonexistent in consumers).
**Why:** vendor dir was a sibling of `lib/`. **Avoid:** `lib/vendor/` inside the lib, import `./vendor/preact-htm.mjs`;
test that every relative import in the lib resolves inside the lib directory (`views.test.mjs:79` does this for views).
**Warning signs:** Node tests pass in the source, browser 404s in a consumer.

### Pitfall 2: Static whitelist hides new file types
`CONTENT_TYPES` (`server.py:25-32`) has only `mjs js css png svg txt`; `SEGMENT_RE` (`:24`) rejects names starting with
`.` or containing anything but `[A-Za-z0-9_.-]`; extension-less files (`VERSION`, `LIB.sha256`) are served as 404 (fine, they
need not be served). A `.woff2`/`.json`/`.ico` file in the lib would 404 silently: either add the type or forbid it by rule.

### Pitfall 3: Ingress gate only protects if the add-on is not published
The gate is `peer == 172.30.32.2 and bool(X-Ingress-Path)` (`server.py:166-167`). The header alone is spoofable by any
client that can reach the port; the peer address is what holds. Never add `ports:` for the GUI port. The Supervisor
docker network address is a fact repo docs rely on (ntfy spike marks it `[V by secrets-sync production usage]`, not
re-tested here). **`X-Ingress-Path` is set by Core (H16), not the Supervisor** — correct the ntfy spike text when writing
DOCS.

### Pitfall 4: Ingress GUIs share HA's origin
Same origin as the HA frontend means same `localStorage` (HA stores `hassTokens` there) and readable `window.parent`.
Hence: no third-party scripts ever (vendored only, CSP `script-src 'self'`), namespaced storage keys, never log or echo
storage. This is also why theme-sync and the bridge can work at all (H2) and why the rule set matters.

### Pitfall 5: zizmor deferrals are line-anchored
Covered in the CI section. Append the new job; edit `lint-results` in place; re-run `uvx zizmor@1.30.1 --offline --config
zizmor.yml .github/workflows/lint.yml`.

### Pitfall 6: Tokens fail contrast (see table) and `.btn` color is hard-coded `#fff` (`app.css:62` `color: #fff`)
Extract with `--on-acc`. Do not carry the issue into the blueprint.

### Pitfall 7: Hooks rewrite committed files
`trailing-whitespace`, `end-of-file-fixer`, `mixed-line-ending`, `pretty-format-json`, prettier-on-markdown run on every
file (`vendor` included). The vendored `preact-htm.mjs` already ends with `\n` (`;\n`), license files pass today. A
sync script that emits JSON or a file without newline will be rewritten by hooks after the hash was computed. Plain
text stamps + `.mjs`/`.css`/`.txt` only inside the lib.

### Pitfall 8: Fake-DOM tests are not hermetic about globals
`navigator` already exists in Node 22 (`navigator.language === "de-DE"` here, `en-US` on CI) and `localStorage` does not.
Inject, do not stub globals. Timers (`toast` 5000 ms, `usePoll`) keep the test worker alive: reuse the `test.after(...
process.exit ...unref())` hook.

### Pitfall 9: i18n completeness drifts silently
Parity of *keys between languages* is not enough: also scan used keys, placeholder sets, and forbid dynamic keys. The
backend never localizes (D-10): `message` from the API is English and must not be shown as the primary text.

### Pitfall 10: Theme-sync against HA internals
No stability promise (`hass` object doc, CONTEXT). Everything must degrade silently; never throw from the observer
callback; surface status in the UI instead of console noise. Re-run the spike per HA release.

### Pitfall 11: `kioskMode` side effect (see H8) and `properties` lacking `dockedSidebar`
Covered in the topbar policy.

### Pitfall 12: Line-length/lint rules
Markdown (`DOCS.md`, `README.md`, root README section) <= 120 columns and prettier-wrapped (`proseWrap: always`,
`.prettierrc.yaml`); tables are exempt from MD013 (`.markdownlint.json` `"tables": false`); `CHANGELOG.md` is excluded
from markdownlint. YAML 2-space, 120 col warning (`config.yaml` description must stay short). `run.sh`: shellcheck clean with
`# shellcheck shell=bash`. Python/JS have no linter configured; follow ntfy style (~120 cols). New `.py` scripts with a
shebang must be executable.

### Pitfall 13: Dockerfile ARG-before-FROM validator is lenient but the build is not
`validate-dockerfile-args.sh` only inspects `FROM` lines after the first one, so a single-stage file passes even with a
missing `ARG BUILD_FROM`; keep the ntfy form (`ARG BUILD_FROM=<default>` then `FROM ${BUILD_FROM}`) and rely on a real
`docker build` (CLAUDE.md rule) rather than the validator.

### Pitfall 14: CSP vs Preact styles
`style-src 'self'` blocks inline `style=""` *attributes* set via markup but not CSSOM writes; Preact applies style objects
and strings through `dom.style`, theme-sync uses `style.setProperty`. Expected to work, `[ASSUMED]`: verify in the spike
(console CSP violations) before the rules promise CSP.

### Pitfall 15: Image does not exist until the first build
`verify-image-availability.yml` reads `image:` from `config.yaml` and will be red between merge and the first
`build.yml` run; expected for every new add-on.

## Code Examples

### Server skeleton surface (keeps ntfy behaviour; `[ASSUMED]` names)
```python
# admin-ui/app/web/skeleton/__init__.py
from .errors import ApiError, register_error_code
from .router import Request, Router, Download
from .static import StaticFiles
from .server import make_server, serve, INGRESS_REMOTE   # INGRESS_REMOTE = "172.30.32.2"
from .ingress import ingress_user                         # reads X-Remote-User-* (see H18)
```
Security headers added on every response by `_send`: `X-Content-Type-Options: nosniff` (exists,
`server.py:149`), `Referrer-Policy: same-origin`, and on HTML/static a CSP such as
`default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none';
form-action 'self'; frame-ancestors 'self'` (`[ASSUMED]`, spike S9). **No `X-Frame-Options`** (the page is framed; ntfy's
test asserts it is absent for static, `test_server.py` `test_response_kinds`).

### Fake API for the demo (`demo_api.py`)
Routes: `GET api/health`, `GET|POST api/items`, `PUT|DELETE api/items/{id}` (in-memory, `threading.Lock`),
`GET api/fail/{code}` (returns each `ERROR_STATUS` code for the error-state gallery, incl. 413/500), `GET api/slow`
(loading state), `GET api/whoami` (echoes `X-Remote-User-*` for the admin/non-admin spike), `POST api/echo`. Demo CRUD
errors use stable codes (`bad_request`, `conflict`, `protected`).

### Modal focus helper (works in real and fake DOM)
```js
const TABBABLE = new Set(["a", "button", "input", "select", "textarea"]);
export function tabbables(root, out = []) {
  for (const n of root.childNodes) {
    if (n.nodeType !== 1) continue;
    const ti = n.getAttribute("tabindex");
    if ((TABBABLE.has(n.localName) && !n.disabled && ti !== "-1" && !(n.localName === "a" && !n.getAttribute("href")))
        || (ti !== null && ti !== "-1")) out.push(n);
    tabbables(n, out);
  }
  return out;
}
```

### Static rule scan reuse
Copy `URL_PATTERNS`/`DANGEROUS_PATTERNS` from `ntfy/tests/test_frontend_static.py:20-39` unchanged and keep
`test_scan_patterns_detect` so the patterns themselves are tested. Recommended: put the scanner in
`internal/check-admin-ui-rules.py` (stdlib), run it from the admin-ui pytest for the demo and from `check-all` for every
consumer found by stamp, so follow-up migrations inherit enforcement without copying tests.

## State of the Art

| Old approach | Current approach | When changed | Impact |
|--------------|------------------|--------------|--------|
| Add-on panel via bare iframe | `ha-panel-app` with `subscribe-properties`/`properties`, `toggle-menu`, `navigate`, `kioskMode`, `handleSafeArea` | frontend `20260128.0` (protocol), `20260729.0` (safe area opt-out) | Layout can adapt; minimum frontend for D-13 = `20260128.0` `[VERIFIED: tag grep]`; older HA ignores the messages -> fallback layout |
| Generic `supervisor/api` ws for ingress | Dedicated `supervisor/ingress/{info,session,validate_session}` | frontend commit #54695, 2026-10-26 (dev, prerelease `20261028.x`) | Per-app authorization incl. non-admin apps; relevant for the `panel_admin: false` spike `[CITED: commit message, gh api]` |
| `X-Frame-Options`-style framing control | CSP `frame-ancestors` | — | Use CSP, no XFO (page must be framed) |
| Preact 10 | Preact 11.1.1 on npm | 2026 | Not adopted; vendored htm standalone is Preact 10.x |

**Deprecated/outdated:** the CONTEXT assumption "D-13 kioskMode only removes HA's bar" (see H8); the ntfy spike statement
that `X-Ingress-Path` comes from the Supervisor `[A]` (it comes from Core, H16).

## Spike design (D-14): `#/spike` view in the demo

The page is the instrument; results go to `admin-ui/DOCS.md` ("Verified on HA <core>/<frontend>") and to
`.planning/phases/26-admin-ui-blueprint/` as a dated log. Show a **copy-as-JSON result block** so each run is recorded the
same way (HA core + frontend version from Settings > About, browser/app, access path).

| ID | Check | How the page observes it | Pass criterion |
|----|-------|--------------------------|----------------|
| S1 | Parent access | `try { parent.document.documentElement }` result + error name; `window.parent !== window`; `location.origin === parent.location.origin` | readable in panel, card; "not an iframe" in direct tab |
| S2 | Variable read | table of all whitelist vars with raw values + parse result | values present and parseable in light, dark, a custom theme, changed primary color |
| S3 | Change detection | counters for MutationObserver fires, poll diffs; instruct: switch theme / dark mode / OS dark with page open | token change within <= 1 s without reload; no loops |
| S4 | Bridge | log of every `properties` message with timestamp; resize across 870 px; rotate on mobile | `narrow` flips at 870 px; insets non-empty on notch devices; no message on old HA -> fallback layout works |
| S5 | Double topbar | measure `frameElement.getBoundingClientRect().top`; modes: desktop docked, desktop `always_hidden` (Profile > Browser settings), narrow, narrow + kiosk requested | no double bar after policy; menu button opens the drawer; leaving the page restores HA UI (H10) |
| S6 | `handleSafeArea` | toggle button re-subscribes with `handleSafeArea: true`, display insets | confirms H7 on iOS/Android Companion; decide to keep default `false` |
| S7 | `navigate` | button -> `home-assistant/navigate` to `/config` | HA navigates |
| S8 | Clipboard | `CopyField` on HTTP vs HTTPS, panel vs card | writeText works or fallback message appears |
| S9 | CSP | enable the CSP header; watch `securitypolicyviolation` events counter | zero violations during gallery + CRUD + theme-sync; if not, relax and record |
| S10 | Storage | language switch persists across reload; behaviour with storage blocked (private mode/Companion) | no exception, default language works |
| S11 | Admin vs non-admin | `api/whoami` shows `X-Remote-User-Groups`; open as non-admin with `panel_admin: false` | panel visible and functional for non-admin; record Core ingress authorization behaviour |
| S12 | Direct access | `http://<host>:8099/` and ingress URL in a plain tab | port: 403 `ingress_only`; ingress tab: works, theme = own, status chip says "own theme" |
| S13 | Webpage card | card pointing at the ingress URL | record whether 401/blocked (A4), whether theme-sync works (sandbox has `allow-same-origin`, H19) |
| S14 | Language/theme switch with page open | live | re-render without reload |
| S15 | After HA update | record HA versions per run; re-run monthly | table in DOCS with dates |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Parent `document` + `getComputedStyle` + `MutationObserver` work in all target contexts | HA facts | Theme-sync inert in some contexts; fallback holds (own theme) |
| A2 | Companion app uses the same ha-panel-app iframe path | HA facts | Menu button/kiosk behave differently in the app |
| A3 | Protocol undocumented and unstable | HA facts | Documentation exists; lower risk |
| A4 | Dashboard card with ingress URL gets 401 | HA facts / spike | Card use case would work better than assumed |
| A5 | `getComputedStyle` returns var()-resolved custom property values consistently | theme-sync | Wrong colors; guard by parse+abort |
| A6 | Narrow-driven kiosk re-subscribe does not flicker/loop | Topbar policy | Need a simpler policy (accept double bar on narrow) |
| A7 | targetOrigin `win.location.origin` is correct for `postMessage` to HA | ha-bridge | Messages not delivered; use `"*"` for outbound (HA authenticates by source only anyway) |
| A8 | `frameElement` top-offset heuristic detects HA's 40px bar | Topbar policy | Double bar on `always_hidden` desktop |
| A9 | CSP `style-src 'self'` + CSSOM style writes cause no violations | Pitfall 14 | Rules must not promise CSP; relax `style-src` |
| A10 | Supervisor gateway 172.30.32.2 remains the ingress peer | Gate | Gate blocks everything; make `INGRESS_REMOTE` configurable via env as ntfy does |
| A11 | WCAG luminance threshold 0.179 yields the user's perceived dark/light | theme-sync | Wrong `data-theme`; tune with spike data |
| A12 | `panel_admin: false` + `boot: manual` are acceptable for a demo add-on | Scaffold | User prefers admin-only / auto-start |
| A13 | Python 3.12+ stdlib is present via Alpine 3.24 `python3` (exact minor not checked) | Standard stack | Use only syntax ntfy already uses (`from __future__ import annotations`, `X | None` in annotations) |
| A14 | Lag of a consumer behind the source should be a warning, not a failure | Sync | Strict mode needed; flip default |

## Open Questions (RESOLVED)

All questions below are decided in the Shared Contract of `26-01-PLAN.md` (PD-01..PD-09).

1. **Drift semantics (D-06 wording).** Fail on any difference between consumer and source, or only on tamper / RESOLVED: PD-01.
   same-version-different-hash, warn on "behind"?
   - Known: D-06 "consumers pull updates deliberately", "the drift check fails on mismatch".
   - Recommendation: fail on tamper and same-version mismatch, warn on behind, `--strict` flag for the strict reading.
     Ask the user once during planning.
2. **Does the demo import `lib/` directly or via its own vendored copy?** D-04 says "the demo is always a consumer". RESOLVED: PD-02.
   Recommendation: import the source directly (docker context contains it, one fewer copy), and treat "consumer" as "uses
   only public exports"; the sync test with a fake consumer covers the copy path.
3. **Python skeleton sync target.** D-05 names only the static path. Recommendation: `admin-ui/app/web/skeleton/` -> RESOLVED: PD-04.
   `<addon>/app/web/admin_ui/` with the same stamp scheme; confirm.
4. **Location of per-add-on strings.** D-09 says `app/strings.{de,en}.mjs`. Recommendation: `static/strings.{de,en}.mjs` RESOLVED: PD-05.
   next to `app.mjs` (so `app/` is read as "the web app", not a literal directory).
5. **`panel_admin` and `boot` of the demo** (A12). RESOLVED: PD-06.
6. **CSP strictness in the rules** (A9): promise it only after S9. RESOLVED: PD-07.
7. **Contrast token changes** (`--on-acc`, `--mut`): they alter ntfy's look at migration time; acceptable? RESOLVED: PD-03.
8. **Minimum HA version** to state in DOCS: frontend `20260128.0` for the bridge; `20260729.0` only for `handleSafeArea`. RESOLVED: PD-08.
   Which HA core release the user runs is unknown here; the spike records it.
9. **`haos-monitor` missing from `base-image-config.yaml`** — out of scope, mention in the follow-up phase note. RESOLVED: PD-09.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| node | lib tests, CI parity | ✓ | v22.23.4 | — |
| python3 | server, sync script, pytest | ✓ | 3.14.8 (CI uses 3.12) | — |
| uv | `uv run --with pytest ...` | ✓ | 0.13.4 | `pip install pytest` |
| docker | CLAUDE.md local build, verify script | ✓ | 29.9.2 | none (rule requires it) |
| pre-commit | hook runs | ✓ | 4.7.0 | CI runs it |
| hadolint, shellcheck, yq, gh | Dockerfile/shell lint, helpers | ✓ | hadolint 2.14.0, shellcheck present, yq 4.4.5, gh 2.102.1 | — |
| yamllint, markdownlint-cli2, prettier, actionlint | lint rules | ✗ locally | — | via `pre-commit run --files <paths>` (installs hook envs, needs network) and CI; `uvx zizmor@1.30.1` works |
| A real HA instance | spike D-14 | not checked | — | Spike is a manual checkpoint (`checkpoint:human-verify`) executed by the user; plan must not block other tasks on it |

**Missing dependencies with no fallback:** none for development. The live spike requires the user's HA instance and a
mobile/Companion device (human checkpoint).

## Validation Architecture

> `.planning/config.json` has `workflow.nyquist_validation: false`; the orchestrator explicitly requested this section, so
> it is included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Node built-in `node --test` (Node 22) for the lib; pytest 9.2.0 for server, static rules, sync script, scaffold |
| Config file | none; `admin-ui/tests/conftest.py` sets `sys.path` like `ntfy/tests/conftest.py` |
| Quick run command | `node --test admin-ui/tests/js/*.test.mjs` |
| Full suite command | `uv run --with pytest python3 -m pytest admin-ui/tests -q && make check-admin-ui-sync` |

### Phase Decisions -> Test Map
| ID | Behavior | Test Type | Automated Command | File Exists? |
|----|----------|-----------|-------------------|-------------|
| D-01 | add-on scaffold valid: required files, config schema, 3-file version sync, no `.upstream.yaml`, `ports` absent, Dockerfile ARG-before-FROM | pytest + existing validators | `python3 internal/validate-addon-config.py admin-ui && ./internal/validate-versions.sh && make validate-dockerfiles` | ❌ Wave 0 (`tests/test_addon_scaffold.py`) |
| D-01 | image builds and serves behind the gate | docker smoke | `bash internal/verify-admin-ui-scaffold.sh` | ❌ Wave 0 |
| D-02 | demo views import, export `meta`+default, render gallery items, CRUD against fixtures incl. error states, relative URLs only | node fake-DOM | `node --test admin-ui/tests/js/views.test.mjs` | ❌ Wave 0 |
| D-03/D-04 | lib export contract (components/hooks/api/i18n/bridge), no ntfy-specific imports, all relative imports resolve inside `lib/` | node | `node --test admin-ui/tests/js/lib_contract.test.mjs` | ❌ Wave 0 |
| D-03 | vendored bundle SHA256, licences present, required exports | pytest | `pytest admin-ui/tests/test_static_rules.py -k "vendor or licence or exports"` | ❌ Wave 0 (port) |
| D-03 | Python skeleton: router 404/405, body rules, 413, static whitelist, security headers, exception mapping, 204/Download | pytest | `pytest admin-ui/tests/test_server.py` | ❌ Wave 0 (port) |
| D-05/D-06 | sync creates copy+stamp, idempotent, tamper detected, source-without-lock detected, behind = warn/strict fail | pytest (tmp fake repo) | `pytest admin-ui/tests/test_sync.py` | ❌ Wave 0 |
| D-05/D-06 | repo is currently in sync | script | `make check-admin-ui-sync` | ❌ Wave 0 |
| D-08/D-09/D-10 | de/en key + placeholder parity, used-key scan, `detectLang` table, `Intl` formatters in both languages, error-code mapping + unknown-code fallback | node | `node --test admin-ui/tests/js/i18n.test.mjs admin-ui/tests/js/format.test.mjs` | ❌ Wave 0 |
| D-11/D-12 | theme-sync with fake parent: mapping, luminance -> `data-theme`, parse failure -> no-op, throwing parent -> no-op, observer disposal, contrast guard | node | `node --test admin-ui/tests/js/theme_sync.test.mjs` | ❌ Wave 0 |
| D-13 | ha-bridge with fake window: subscribe message shape, source check, narrow-driven kiosk transitions, no-answer fallback, unsubscribe on dispose | node | `node --test admin-ui/tests/js/ha_bridge.test.mjs` | ❌ Wave 0 |
| D-14 | live spike results recorded | manual (human checkpoint) | spike page `#/spike` result JSON stored in DOCS/planning log | n/a (manual-only: needs a real HA) |
| D-15/D-16 | static rules: no absolute URLs/CSS `@import`/`innerHTML`-class APIs/eval in `static/` excluding `vendor/`; pattern self-test | pytest | `pytest admin-ui/tests/test_static_rules.py` | ❌ Wave 0 (port) |
| D-16 | ingress gate on every method/path (header missing, wrong peer), `ingress_only` body | pytest | `pytest admin-ui/tests/test_server.py -k gate` | ❌ Wave 0 (port) |
| D-16 | a11y: dialog roles, focus move/trap/return, aria-live, labels, accessible-name sweep over gallery, tab roles | node fake-DOM | `node --test admin-ui/tests/js/a11y.test.mjs` | ❌ Wave 0 |
| D-16 | CSS: dark block parity, `:focus-visible`, reduced motion, all `var(--x)` declared | pytest | `pytest admin-ui/tests/test_css.py` | ❌ Wave 0 |
| (adv.) | token contrast pairs >= 4.5 (recommended, D-16 says manual) | node | `node --test admin-ui/tests/js/contrast.test.mjs` | ❌ Wave 0 |
| D-17 | CI job runs the three commands; zizmor/actionlint clean | CI + local | `uvx zizmor@1.30.1 --offline --config zizmor.yml .github/workflows/lint.yml` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the single test file touched (`node --test <file>` or `pytest <file>`), < 5 s each (the 25 ntfy node
  tests run in 1.1 s, 40 ntfy pytest tests in 5.3 s here).
- **Per wave merge:** full suite command above + `make validate-versions validate-dockerfiles`.
- **Phase gate:** full suite green, `pre-commit run --files <changed paths>` clean, local `docker build` / verify script
  green, spike checklist recorded, before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `admin-ui/tests/conftest.py` (path setup), `tests/js/fakedom.mjs` (ported + `focus/activeElement/contains` +
      extra `EVENT_PROPS`)
- [ ] ported `test_server.py`, `test_static_rules.py`, `test_js.py`
- [ ] new: `test_sync.py`, `test_css.py`, `test_addon_scaffold.py`, `js/{i18n,format,theme_sync,ha_bridge,a11y,
      lib_contract,views}.test.mjs`
- [ ] `internal/sync-admin-ui.py`, `admin-ui/lib.lock`, Makefile targets, pre-commit hook
- [ ] Framework install in CI: `python -m pip install pytest==9.2.0` (node needs none)

## Security Domain

`security_enforcement` is absent in `.planning/config.json` (treated as enabled).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Delegated to HA/Core ingress (cookie `ingress_session`, H15); the add-on adds none |
| V3 Session Management | no (inherited) | Core/Supervisor sessions; add-on stores no session state |
| V4 Access Control | **yes** | Ingress gate on every request (peer `172.30.32.2` + `X-Ingress-Path`), no published port, admin/non-admin via `X-Remote-User-*` only informational in the demo |
| V5 Input Validation | **yes** | JSON body type check, `MAX_BODY = 65536`, content-type check, segment regex for static paths, server-side validation in demo CRUD; client never trusts markup (text nodes only) |
| V6 Cryptography | no | None used; SHA-256 only for integrity of vendored files and copies |
| V7 Error handling/logging | **yes** | Stable error codes, `500 internal_error` without exception text (traceback to stdout only), `log_message` silenced (query strings may carry names) |
| V8/V9 Data/Communications | yes | `Cache-Control: no-store` for API, `nosniff`, `Referrer-Policy`, CSP; all URLs relative |
| V12 Files/Resources | **yes** | Static whitelist, `resolve().relative_to(root)`, symlink escape and `.py` not served (tested in ntfy) |
| V14 Configuration | yes | HA base image only, no secrets in the demo, vendored bundle pinned by SHA256 |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Direct access to the add-on port spoofing `X-Ingress-Path` | Spoofing/Elevation | Peer-IP check + never publish the port |
| XSS via state interpolated into markup | Tampering | Preact text nodes only; static ban on `innerHTML`-class APIs and `eval` |
| Third-party script on HA's origin reading HA storage | Information disclosure | No CDN, vendored + SHA256, CSP `script-src 'self'` |
| Path traversal / symlink escape in static serving | Information disclosure | Whitelist + resolved-path containment |
| Destructive action by misclick | Tampering | Type-to-confirm `ConfirmDialog` (replaces `window.confirm()` in secrets-sync later) |
| postMessage spoofing from another window | Spoofing | Accept only `event.source === window.parent` (+ origin), never act on payloads other than documented fields |
| Request smuggling/oversized bodies | DoS | `MAX_BODY`, no chunked bodies (`bad_request`), `Content-Length` validation |
| Stored user identity headers shown in demo | Information disclosure | Only echo to the same viewer, never log |

## Sources

### Primary (HIGH confidence)
- This repo, read in full: `ntfy/app/web/{server.py,static/**}`, `ntfy/app/{gui.py,contract.py}`, `ntfy/tests/{test_server,
  test_frontend_static,test_js,conftest}.py`, `ntfy/tests/js/*`, `ntfy/{config,build}.yaml`, `ntfy/{Dockerfile,run.sh}`,
  `haos-monitor/**`, `secrets-sync/Dockerfile`, `Makefile`, `.pre-commit-config.yaml`, `.github/workflows/{lint,build,
  _build-template,base-image-update}.yml`, `internal/{validate-versions.sh,validate-dockerfile-args.sh,
  validate-addon-config.py,base-image-config.yaml}`, `zizmor.yml`, `.markdownlint*.json`, `.prettierrc.yaml`, `CLAUDE.md`
- `https://raw.githubusercontent.com/home-assistant/frontend/dev/src/panels/app/ha-panel-app.ts` (+ tags `20260128.0`,
  `20260624.6`, `20260729.0`, `20260826.0`, `20260930.5`)
- `.../frontend/dev/src/layouts/home-assistant-main.ts`, `src/state/{themes-mixin,sidebar-mixin}.ts`,
  `src/common/dom/apply_themes_on_element.ts`, `src/data/hassio/ingress.ts`, `src/resources/theme/{theme,main.globals,
  core.globals,semantic.globals}.ts`, `src/resources/theme/color/{index,color.globals,core.globals,semantic.globals}.ts`,
  `src/panels/lovelace/cards/hui-iframe-card.ts`, `src/util/iframe.ts`
- `https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/hassio/ingress.py`
- `https://raw.githubusercontent.com/home-assistant/supervisor/main/supervisor/api/ingress.py` (+ `supervisor/const.py`)
- Registry queries (`npm view htm|preact`, PyPI JSON for pytest), `gsd-tools query package-legitimacy check`
- Local runs: `node --test` (25 pass), `pytest` ntfy frontend/js/server (40 pass), Node 22 `Intl`/`navigator` probes,
  `uvx zizmor@1.30.1` on a draft job

### Secondary (MEDIUM confidence)
- `.planning/phases/24-ntfy-add-on-admin-gui/spikes/ntfy-ingress.md` (ntfy-era assumptions, partly corrected here)
- GitHub PR #53127 and commit metadata via `gh api`

### Tertiary (LOW confidence)
- Discussion `frontend/discussions/52204` (cited by CONTEXT, not retrievable by number this session)

## Metadata

**Confidence breakdown:**
- Standard stack / extraction inventory: HIGH — every file read and the test suites executed.
- Add-on scaffold and registration list: HIGH — validators, workflows and Makefile read; build/auto-detect logic traced.
- Sync/drift design: MEDIUM — design is mine (no prior art in repo); constraints from hooks verified, semantics need the
  user's answer to Open Question 1.
- HA protocol and theme facts: HIGH (read from `dev` and tagged source) / MEDIUM-LOW for runtime behaviour (spike).
- i18n and a11y design: MEDIUM — standard techniques, harness gaps verified by reading `fakedom.mjs`.
- Pitfalls: HIGH for repo-derived ones, MEDIUM for CSP/theme runtime.

**Research date:** 2026-11-02
**Valid until:** 2026-11-09 for HA-frontend facts (fast-moving; `ha-panel-app.ts` changed 3 times in the last 5 weeks);
2026-12-02 for repo-derived facts unless the build/lint workflows change.
