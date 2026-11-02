# Phase 27: ntfy admin-ui lib migration - Context

**Gathered:** 2026-11-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Move the ntfy admin GUI (Phase 24) onto the shared `admin-ui` lib (Phase 26, lib 0.4.0, add-on 0.1.0-6, experimental).
The lib is copied into `ntfy/` by `make sync-admin-ui ADDON=ntfy` and never edited by hand. ntfy keeps only its own
model logic, views and styles. Phase 25 (IaC API) is not part of this phase and starts afterwards.

</domain>

<decisions>
## Implementation Decisions

- **D-01:** Order (user decision 2026-11-02): verify Phase 24 first (including a manual UAT on real HA ingress, which
  also gives the visual reference), then this phase, then Phase 25. This phase does not start executing before the
  Phase 24 verification is done.
- **D-02:** Lib is consumed by copy only: `make sync-admin-ui ADDON=ntfy` creates `ntfy/app/web/static/vendor/admin-ui/`
  and `ntfy/app/web/admin_ui/` with `LIB.stamp` and maintains `admin-ui/lib.lock`. Copies are never edited by hand.
  `make check-admin-ui-sync` and `make check-admin-ui-rules` must be green (pre-commit hook and CI).
- **D-03:** Lib changes happen only in `admin-ui/` through the admin-ui manager (herdr pane `wH:p1`, agent
  `admin-ui`): describe the need (additive, with reason), wait for a new lib version, sync it. ntfy is the first real
  consumer and reports friction there instead of forking.
- **D-04:** Remove the duplicates: `lib/api.mjs` (byte-identical with the lib), `lib/ui.mjs`, the lib parts of
  `app.css`, `vendor/preact-htm.mjs` (vendor check now belongs to the lib). Keep ntfy-specific: `model.mjs` ntfy logic,
  `OriginBadge`, `PermSelect`, `ERROR_HINTS`, `.matrix` and origin-badge styles, the seven views.
- **D-05:** English literals become `static/strings.{de,en}.mjs` registered through the lib (`t()`/`registerStrings`),
  with key parity between both files (tested).
- **D-06:** Server: `ntfy/app/web/server.py` (gate, router, static whitelist) moves onto the skeleton
  `app/web/admin_ui/` as far as it fits. JSON API error codes stay stable; the Phase 24 contract (C8, `ROUTES`,
  registry tests) stays green. Ingress gate on every request, relative URLs only.
- **D-07:** Blueprint rules R-01..R-15 hold for the result: never `innerHTML` with state, type-to-confirm for
  destructive actions, dark/light via lib tokens, a11y minimum, Node tests for views.
- **D-08:** Frontend tests (`ntfy/tests/js/*`, `test_frontend_static.py`) move onto the lib structure; the vendor SHA256
  check is dropped from ntfy (lib owns it). A CI job for ntfy frontend tests is added after the `admin-ui` job
  template in `.github/workflows/lint.yml`.
- **D-09:** Visible look changes slightly (lib tokens fix contrast: `--on-acc`, `--mut`, badge pairs, PD-03). Accepted.
- **D-10:** Theme sync and HA bridge are progressive enhancement only (R-11, R-13 unverified). In dashboard cards
  (`custom:addon-iframe-card`) top navigation is blocked and the navigate protocol is not answered: nothing may depend
  on it.
- **D-11:** Versioning only via `make update-version` (ntfy subpatch +1 for add-on-only change). Local `docker build`
  before Dockerfile commits (hadolint via `docker run hadolint/hadolint`). No Co-Authored-By. Stage by path.
- **D-12:** Branch `feat/ntfy-admin-ui-lib` from current `origin/main`, worktree under
  `~/Projekte/_worktrees/homeassistant-addons/feat/ntfy-admin-ui-lib`. STATE.md/ROADMAP.md/state.json only in the main
  checkout.

- **D-13:** Planning proposals accepted by the user on 2026-11-02 (plans already reflect them): `strings.{de,en}.mjs`
  stay aggregators over per-plan part files (no flat layout); HA bridge and theme sync wired in `app.mjs` as
  progressive enhancement; tab bar navigation (old look); rule delete and token revoke use plain danger confirmations
  (user delete and resets stay type-to-confirm); backend messages are not shown (R-14), a 409 reads generically;
  `NTFY_GUI_CSP=off` is a diagnostic env switch only, never an add-on option; the `Server` header changes to `AdminUi`;
  no `addon_slug` in `api/health`. Open: how the branch build is run in HA for the 27-07 UAT.

### Claude's Discretion
Plan split and waves, which skeleton parts fit ntfy's server, test layout, string key naming.

</decisions>

<canonical_refs>
## Canonical References

- `admin-ui/DOCS.md` (Rules R-01..R-15, Library reference, Consumer recipe, Distribution, Migration paths > ntfy,
  Embedding contexts, Security notes, Follow-up)
- `admin-ui/app/web/static/lib/*`, `admin-ui/app/web/skeleton/*`, `internal/sync-admin-ui.py`, `admin-ui/lib.lock`
- `.planning/phases/26-admin-ui-blueprint/26-CONTEXT.md` (D-01..D-17), `26-VERIFICATION.md`
- `.planning/phases/24-ntfy-add-on-admin-gui/` (24-CONTEXT.md, plans and summaries, contract C1-C13 in 24-01)
- `.github/workflows/lint.yml` (job `admin-ui` as template), `Makefile` (`sync-admin-ui`, `check-admin-ui-*`)

</canonical_refs>

<deferred>
## Deferred Ideas

- Lib changes needed by ntfy go to the admin-ui manager, not this phase.
- IaC API (Phase 25).

</deferred>

---

*Phase: 27-ntfy-admin-ui-lib-migration*
