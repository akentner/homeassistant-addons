## Resolved

Implemented in commit `aac766b` (`feat(21-03): add CUPS add-on options translations (en/de)`):
added `cups/translations/en.yaml` and `cups/translations/de.yaml` following the official HA
add-on translations schema (top-level `configuration:` key, `{name, description}` per option).
Covers all six top-level options: `avahi_reflector`, `avahi_hostname`, `avahi_use_ipv6`,
`server_aliases`, `printers`, `log_level`. HA's schema only supports top-level option
translation, not per-nested-field translation for the `printers[]` list-of-objects, so that
option's description summarizes the object shape in prose instead.

---

created: 2026-09-26T11:35:30.796Z
title: cups config options friendly names and DE/EN translations
area: general
severity: cosmetic
files:
  - cups/config.yaml
  - cups/translations/en.yaml (to create)
  - cups/translations/de.yaml (to create)
---

## Problem

The `cups/` add-on's `config.yaml` options (e.g. `avahi_reflector`, `avahi_hostname`,
`avahi_use_ipv6`, `printers[]`, `log_level`) currently show up in the HA Options UI as raw
option keys with no friendly display name or description. Raised by the user during phase 21
wave 3 rollout, to be picked up once the mDNS hostname-stability fix is confirmed working.

## Solution

Add a `translations/en.yaml` (and `de.yaml` if HA's add-on translation schema supports it) under
`cups/` giving each option a friendly name and description, matching the schema/convention used by
translations in this repo's other add-ons if any exist (check `phone-logger/` and `meridian/` for
precedent). TBD on exact HA add-on translations file format if not already used elsewhere in this
repo.
