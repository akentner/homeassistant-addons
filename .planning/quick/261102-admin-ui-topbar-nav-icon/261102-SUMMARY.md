# Quick 261102 summary

Done: sticky head with safe-area insets, `nav="topbar" | "tabs"` with burger fallback, default `./icon` in the topbar,
generated icon.png/logo.png shipped via Dockerfile, demo switch (`admin-ui:demo-nav`), de+en strings, lib 0.2.0,
add-on 0.1.0-1.

Verification: `make test-admin-ui` (254 node, 248 pytest) green, `check-admin-ui-sync`/`-rules` green, local
`docker build` ok and icon present in the image. `make lint`: only `terraform-bridge scaffold verify` fails (image
60 MiB cap, unrelated to this change).

Deviations: see PLAN notes (tab variant has no tablist role today). Touched DOCS.md (library table row plus one
paragraph) and CHANGELOG.md (new 0.1.0-1 section), which exec-26-w7 also edits: expect a trivial merge.

## Part 2: mobile horizontal scroll (lib 0.2.1, add-on 0.1.0-2)

Cause: `.topbar` is a nowrap flex row of fixed height whose items (menu button, title, badge, version, theme chip,
language switch) were wider than the viewport, and the hidden inline nav (`position: absolute`) escaped the
overflow-hidden slot, which was not its containing block.

Fix (decision: keep the sticky head compact, so no `flex-wrap`/`height: auto`):

- `.topbar > * { min-width: 0 }`, title shrinks with an ellipsis, icon/menu button/badge stay fixed
- `Topbar` children go in `.topbar-extra` (`display: contents`, `display: none` under 600 px)
- `.topnav-slot { position: relative }` so the hidden nav is clipped; `.topnav { min-width: 40px }` keeps room for the
  burger; `needsBurger` now also folds a zero-width slot
- under 600 px: smaller title, language switch capped at 72 px
- `html, body { overflow-x: clip }` as a safety net only

Verification in a real browser: Brave (`/usr/bin/brave`) via Playwright, script `measure-overflow.py`. 320/375/414/600
px x nav topbar/tabs x en/de x without and with a simulated HA host (iframe answering `narrow: true`, so the host
menu button shows): `documentElement.scrollWidth <= innerWidth` and no overflow inside `.topbar` in all 32 cases,
topbar height stays 56 px, exactly one nav burger plus the host button in kiosk (2 `.menu-btn`). Also 700 and 1280 px:
no overflow, inline links at 1280 px, burger at 700 px. The Fake-DOM and CSS tests cover the rules; real HA/phone not
tested.
