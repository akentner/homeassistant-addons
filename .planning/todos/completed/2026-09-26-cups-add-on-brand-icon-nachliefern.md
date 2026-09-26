## Resolved

Implemented in commit `d0a8378` (`feat(21-03): add CUPS add-on store icon`): added
`cups/icon.png`, a 128x128 8-bit RGBA PNG matching the `meridian/icon.png` precedent.
Generated programmatically with Pillow (`uv run --with pillow`) rather than downloading any
third-party image, to avoid licensing risk -- a solid deep-teal rounded-square background with
a bold white printer silhouette and a small wifi/mDNS-style arc.

---

created: 2026-09-26T11:35:30.796Z
title: CUPS add-on brand icon nachliefern
area: general
severity: cosmetic
files:
  - cups/icon.png (missing)
---

## Problem

The `cups/` add-on (forked from `f1c878cb_cups` in phase 21) does not yet have its own brand icon.
Home Assistant's add-on store shows a generic/placeholder icon until one is supplied. Raised by the
user during phase 21 wave 3 rollout, to be picked up once the mDNS hostname-stability fix is
confirmed working.

## Solution

Add `cups/icon.png` (and `logo.png` if this repo's other add-ons follow that convention — check
`phone-logger/` and `meridian/` for the established icon file naming/size). TBD on source image
(CUPS project branding vs. a custom icon).
