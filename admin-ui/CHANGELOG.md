# Changelog

All notable changes to the **Admin UI Blueprint** add-on are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/). This is our own code without an upstream project: the version is bumped
manually with `make update-version`.

## [0.2.2-0] - 2026-11-05

### Fixed

- Lib 0.8.1: with `showLang={false}` the title takes the free width, so the right-hand group sits at the right edge

## [0.2.1-0] - 2026-11-05

### Added

- Lib 0.8.0: `Topbar` options `showLang={false}` (omit the language switch, default `true`) and `version` (plain version
  text after the status badge). Both are opt-in; without them the bar is unchanged

## [0.2.0-0] - 2026-11-04

### Changed

- Shared lib 0.7.0: HA-style parent-synced topbar (56 px fallback), 48 px navigation targets, active underlines and
  optional decorative SVG icons
- Data tables use 52 px body rows and 56 px headers, growing for multiline content
- Keep action cells in the table layout and space expanded detail cards; badges now contribute to line height
- Gallery includes rows with/without actions and expandable details
- Include the public health/status route support required by migrated consumers

## [0.1.0-7] - 2026-11-02

### Added

- Skeleton: `Router.add(..., public=True)` and `Router.is_public` let exactly one registered method and literal path
  through the ingress gate (for a health check on an optionally published port). Static files, the index and the icon
  are never public, and the default stays private (lib 0.5.0)

## [0.1.0-6] - 2026-11-02

### Changed

- The add-on is marked as experimental (`stage: experimental`)

## [0.1.0-5] - 2026-11-02

### Fixed

- The info link opens the add-on page at `/config/app/<slug>/info` (the old `/hassio/addon/...` route is gone since
  add-ons became apps)
- No more blocked top navigation inside sandboxed frames such as a dashboard card: the link opens a new tab when the
  sandbox allows popups and is hidden otherwise (lib 0.4.0: `detectEmbedContext`, `infoLinkPlan`)

### Changed

- Spike view: S7 says "sent, not confirmed by the host" and shows the embedding context; the result block has `embed`
  and the info link path `new_tab`

## [0.1.0-4] - 2026-11-02

### Added

- Info link in the topbar to the add-on's page in Home Assistant (lib 0.3.0, option `infoPath`): navigates through the
  HA bridge when it answers, otherwise a plain `target="_top"` link; folds into the burger menu on narrow layouts
- `api/health` reports `addon_slug` (from the Supervisor, left out when unknown); the spike result block records the
  info link path in `navigate.last_path` and `navigate.count`, so S7 can be checked live

## [0.1.0-3] - 2026-11-02

### Changed

- Spike view detects the HA core version (same-origin parent), the add-on version (`api/health`) and the browser itself;
  the result block gets `*_source` fields (`auto`, `manual`, `not_recorded`) and separate, labelled override fields. The
  frontend version stays a typed field because HA offers no runtime read for it
- DOCS: step-by-step guide to test the CSP in a live Home Assistant

## [0.1.0-2] - 2026-11-02

### Verified

- Live spike run A on a real Home Assistant (desktop panel, HA default dark theme): recorded in `DOCS.md`. Items without
  evidence are `not-applicable` with follow-ups; R-11 and R-13 stay `unverified`

### Fixed

- Mobile: the page no longer scrolls sideways. The topbar stays one compact row, the title shrinks with an ellipsis, and
  the `Topbar` children (the demo's version text and theme chip) fold away under 600 px (lib 0.2.1)

## [0.1.0-1] - 2026-11-02

### Added

- Sticky topbar (with the tab bar) that respects the HA safe-area insets
- Lib option `nav="topbar" | "tabs"` for `Topbar`: navigation in the bar with a burger-menu fallback, or the tab bar
- Add-on icon before the name in the topbar (`./icon`, hidden on load error), plus `icon.png` and `logo.png` for the
  admin-ui add-on; the demo has a navigation style switch (lib 0.2.0)

## [0.1.0-0] - 2026-11-02

### Added

- Tracer slice: ingress gate, router and health API in the Python skeleton, JSON client and vendored Preact in the
  browser lib, demo page with a health badge
- Add-on shell: manifest without published ports, `boot: manual`, Dockerfile on the Home Assistant base image and
  `run.sh`
- Blueprint documentation: rules R-01 to R-15 with their enforcing tests, library reference, consumer recipe, HA
  integration facts and the spike result table, guarded by a structure test
- Sync tooling with drift check and the rules scanner for consumer add-ons, wired into the Makefile and the CI job
- `admin-ui/lib.lock`, the pre-commit hooks `check-admin-ui-sync` and `check-admin-ui-rules`, and their membership in
  `make check-all`, so lib drift and rule violations turn red locally, in pre-commit and in the CI job
- Export contract test of every lib module and a docs test that every export, lib file and make target is documented
- Extended Docker smoke script covering the whole demo, the API error codes and the response headers
- Registration in the root README, the repository rules and the base-image tracking file

Release links are added after the first tag exists.
