---
status: complete
---

# Summary

- `ntfy/app/web/static/app.mjs`: `nav="topbar"`, `infoPath()` from `health.addon_slug`.
- `strings/core.{de,en}.mjs`: `app.version` = `v{version}`.
- `ntfy/run.sh` exports `NTFY_ADDON_SLUG`; `api/health.py` returns validated `addon_slug`; `contract.py` Health type.
- Tests: JS app tests adapted + info button test, pytest slug test. Version 2.37.2-3.
- No lib/skeleton change, no `make sync-admin-ui` needed.
