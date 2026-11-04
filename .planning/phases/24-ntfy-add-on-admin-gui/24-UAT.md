---
status: partial
phase: 24-ntfy-add-on-admin-gui
source: 24-VERIFICATION.md (human_verification), 24-01..24-11-SUMMARY.md
started: 2026-11-03T09:00:00Z
updated: 2026-11-03T10:30:00Z
---

## Current Test

[testing paused - 2 items outstanding: tests 8 and 9 are blocked (production routing, published image)]

## Tests

### 1. Sidebar entry and panel opens
expected: Sidebar entry appears (panel_admin), panel opens in the ingress frame, no blank page. Log: render_config, bootstrap, baseline lines, no password.
result: pass
note: sidebar title is 'ntfy' (panel_title is not changed in the UAT copy); log part checked by Claude (render_config, admin created, 3 baseline users, no password in log)

### 2. Views render (users, acl, matrix, tokens, tools, health, data), light and dark, reload keeps hash route
expected: All seven views render with HA-style look, relative URLs work under /api/hassio_ingress/<token>/, no console errors, reload keeps the route.
result: pass

### 3. Ingress gate from the LAN
expected: http://<HA-IP>:8099/ and /api/users answer 403 ingress_only (or are unreachable).
result: pass
note: checked by Claude from the HA host against the add-on container; 403 ingress_only on /, /api/users, /api/health, also with a forged X-Ingress-Path; port 8099 unreachable from LAN/Tailscale

### 4. Export and backup downloads in the iframe
expected: Data view downloads JSON and YAML (with and without hashes) and a backup; default export has no hashes; schema 1.
result: pass
note: tab is labelled 'Export & backups' in the GUI (Claude called it 'Data' after the route name)

### 5. Token create, copy, reveal
expected: Create shows the value; copy works or falls back to select-all; list rows are hidden until Reveal.
result: pass

### 6. CSP / console under HA ingress
expected: No CSP violations in the console; vendored modules load.
result: pass

### 7. Migration baseline and test publish
expected: Baseline users show origin options; Health test publish returns ok.
result: pass

### 8. Reverse proxy repoint (Cloudflared/Traefik to 72a005f5-ntfy:8000), direct port-8000 clients
expected: Health ok through ntfy.akentner.de; publish/subscribe work for HA, notebook, Gatus.
result: blocked
blocked_by: third-party
reason: needs production routing change; not part of the local UAT add-on

### 9. Install from the Supervisor store (GHCR image)
expected: Image pull succeeds, store shows icon/logo and translations.
result: blocked
blocked_by: release-build
reason: no published image/tag yet (D-14: UAT is local)

## Summary

total: 9
passed: 7
issues: 0
pending: 0
skipped: 0
blocked: 2

## Gaps
