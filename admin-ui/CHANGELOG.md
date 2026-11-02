# Changelog

All notable changes to the **Admin UI Blueprint** add-on are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/). This is our own code without an upstream project: the version is bumped
manually with `make update-version`.

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
