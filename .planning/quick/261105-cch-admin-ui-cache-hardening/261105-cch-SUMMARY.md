---
quick_id: 261105-cch
status: complete
---

# Summary 261105-cch

Executed on `feat/admin-ui-cache-hardening` (local only, no push). Lib 0.7.1: strong ETag + 304, `/` served with
`?v=<hash>` asset URLs, `resolve()` unchanged (`resolve_asset()` added). Consumers synced by script and bumped:
haos-monitor 0.7.3-0, secrets-sync 0.7.2-0, ntfy 2.37.2-2; admin-ui demo add-on not bumped (0.2.0-0).
Decisions: D1 one PR, D2 0.7.1 (no consumer calls `resolve()`), D3 no Clear-Site-Data, D4 no demo bump, D5 entry assets only.
Not verified: H1/H2/H3 on the real browser or proxy; live HA behaviour; terraform-bridge scaffold hook fails
(image size cap) in `make check-all`, unrelated to this change.
