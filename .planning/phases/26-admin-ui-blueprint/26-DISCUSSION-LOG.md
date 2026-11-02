# Phase 26: admin-ui blueprint - Discussion Log

> Audit trail only. Not consumed by downstream agents. Decisions are in `26-CONTEXT.md`.

**Date:** 2026-11-02
**Areas discussed:** Lib distribution + source, Migration of the three GUIs, i18n de/en, Demo add-on + tests/CI,
HA theme sync (added by the user during the discussion)

## Pre-discussion (before discuss-phase)

| Question | Chosen |
|---|---|
| What is the meta add-on? | Real HA add-on with demo GUI |
| Lib scope | Tokens + base CSS, API client + ingress helper, Preact/htm components, Python server skeleton |
| Rules | Dark/light + a11y, i18n de/en, test duty, security/ingress rules |

## Lib distribution + source

| Question | Options | Chosen |
|---|---|---|
| Distribution | Copy + sync + drift check / download by git tag / build context to repo root | Copy + sync + drift check |
| Source of truth | `admin-ui/app/web/static/lib/` / separate `admin-ui/lib/` / stays in ntfy | `admin-ui/app/web/static/lib/` |
| Versioning | VERSION file + hash pin / always in sync / you decide | VERSION file + hash pin |

## Migration of the three GUIs

| Question | Chosen |
|---|---|
| ntfy | Own follow-up phase |
| secrets-sync | Full migration to Preact/htm |
| haos-monitor | Rebuild on the blueprint stack |
| Phase 26 scope (clarification: answers conflicted) | 26 = admin-ui + rules; all three migrations = follow-up phases |

## i18n de/en

| Question | Chosen |
|---|---|
| Language source | `navigator.language`, fallback en, manual switcher in localStorage |
| Strings | Lib `t()` + base strings, per-add-on de/en files |
| Backend errors, formats | Stable error codes translated by key, `Intl` for date/number |

## Demo add-on + tests/CI

| Question | Chosen |
|---|---|
| Demo content | Component gallery + fake API + rules page |
| Packaging | Normal add-on, own version scheme, no auto-update |
| CI | New job in lint workflow: node tests, pytest, sync check |
| Enforced rules | i18n parity, ingress gate, static rules, a11y minimum (all four) |

## HA theme sync (user addition: "check how far the external theme can be accessed")

Research by a subagent (source reading only): same-origin likely, official postMessage protocol exists for
`narrow`/`safeAreaInsets` (no theme, no language), topbar height not readable, theme variables via parent
`documentElement`, no change event.

| Question | Chosen |
|---|---|
| Coupling | Progressive enhancement |
| Dark/light source | Derive from parent background luminance |
| Layout | Keep own 56px topbar, react to narrow/safe area |
| Verification | Live spike in the demo add-on |

## Deferred

ntfy switch-over, secrets-sync rewrite, haos-monitor rebuild, frontend tests in CI for existing add-ons.
