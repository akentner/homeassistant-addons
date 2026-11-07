---
phase: 26-admin-ui-blueprint
plan: 02
subsystem: infra
tags: [ha-addon, ingress, python-stdlib, csp, demo-api]
requires:
  - phase: 26-01
    provides: skeleton package in final module layout, demo health API, tracer tests
provides:
  - headers.py (DEFAULT_CSP, security_headers) applied to every response inside _send
  - errors.register_error_code, make_handler/make_server csp and error_mappers, serve()
  - ingress.ingress_user (X-Remote-User-* reader)
  - complete demo API (items CRUD, fail/{code}, slow, whoami, echo) and app.main.build_config
affects: [26-06, 26-09, 26-10, 26-11]
requirements-completed: [D-03, D-10, D-15, D-16, PD-01, PD-07, PD-12]
key-files:
  created:
    - admin-ui/app/web/skeleton/headers.py
    - admin-ui/tests/test_skeleton_server.py
    - admin-ui/tests/test_demo_api.py
  modified:
    - admin-ui/app/web/skeleton/__init__.py
    - admin-ui/app/web/skeleton/errors.py
    - admin-ui/app/web/skeleton/ingress.py
    - admin-ui/app/web/skeleton/server.py
    - admin-ui/app/web/demo_api.py
    - admin-ui/app/main.py
status: complete
---

# Phase 26 Plan 02: Skeleton hardening and demo API Summary

**The skeleton now exposes the full C2 surface (headers/CSP switch, error registry, exception mappers, ingress user,
SIGTERM-safe `serve()`) and the demo API the full C3 surface, both covered by tests.**

## Accomplishments

- Security headers on every response including the 403 gate; CSP only on `/` and static, `csp=None` switches it off;
  no `X-Frame-Options` anywhere.
- `register_error_code` validates code pattern and status range, is idempotent, rejects conflicts. Mappers are
  consulted by `isinstance` before the generic 500; unmapped exceptions stay `internal_error` without text.
- Demo API: seeded CRUD with validation, conflict, protected and type-to-confirm delete (order not_found, protected,
  confirmation_required), table-driven `api/fail/{code}` for every code plus `teapot` (418) and `boom`, `api/slow`
  clamped to 2000 ms, `api/whoami` (own identity only), `api/echo`.
- `build_config` reads `ADMIN_UI_PORT|INGRESS_REMOTE|VERSION|CSP`; `main()` runs through `serve()`.
- ntfy's server tests ported (gate for all methods and paths, router, body rules, response kinds, mapping, static
  whitelist incl. symlink escape) plus chunked/bad Content-Length, headers, CSP switch, registry, serve().

## Verification

- `uv run --with pytest python3 -m pytest admin-ui/tests -q`: 129 passed (includes plan 26-01 tests).
- 18 tests in `test_skeleton_server.py` (112 incl. parametrized cases in the run), 13 in `test_demo_api.py`.

## Deviations

- `demo_api.register` has an extra optional keyword `clock` (injectable timestamps for tests); C3 call sites unaffected.
- DELETE reads `confirm` from the JSON body and falls back to the `confirm` query argument.
- Docker verify script not run (instructed).

## Commits

- c6ea088 feat(admin-ui): harden skeleton with security headers, error registry, mappers and serve()
- 72cf3af feat(admin-ui): complete demo API and env-driven config
