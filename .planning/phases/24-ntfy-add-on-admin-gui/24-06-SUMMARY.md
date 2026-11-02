---
phase: 24-ntfy-add-on-admin-gui
plan: 06
subsystem: backend
tags: [ntfy, accounts, acl, guardrails, python-stdlib]
requires: [24-02, 24-03]
provides:
  - accounts service layer (users, ACL rules, guardrails, role-change stash)
  - users and ACL JSON endpoints (C10 rows owned by 24-06)
affects: [24-10, 24-11]
actuals:
  tasks: 2
  commits: 2
key-files:
  created:
    - ntfy/app/accounts.py
    - ntfy/app/web/api/acl.py
    - ntfy/tests/test_accounts.py
    - ntfy/tests/test_api_accounts.py
  modified:
    - ntfy/app/web/api/users.py
requirements-completed: [D-05, D-08, D-12, D-17, ROADMAP-SC4]
completed: 2026-11-02
---

# Phase 24 Plan 06: accounts backend Summary

## Commits

- `78f01b5` feat(ntfy): add user and ACL services with guardrails and role-change stash
- `5f2c1d6` feat(ntfy): add users and ACL JSON endpoints

## Verification

- `pytest test_accounts test_api_accounts test_contract`: 61 passed (23 + 14 tests); full `pytest ntfy/tests`: 165 passed.
- py_compile ok, no line over 120 chars, includes the two-admin race test (exactly one demotion succeeds) and a test
  that the route set equals the C10 rows for `/api/users*` and `/api/acl`.
- No Docker used.

## Deviations

1. Protection order: `anonymous` > `options_admin` > `last_admin`; `last_admin` applies to the only admin-role user
   that is not the options admin (if the options admin is the sole admin it reports `options_admin`).
2. `delete_user` checks protection before the typed confirmation, so a protected user always yields `protected`.
3. `everyone` in create/delete/role/password gives `bad_request`; `set_rule`/`list_rules` accept it.
4. `DELETE /api/users/{name}` without `confirm` in the body gives `confirmation_required`, a non-string gives
   `bad_request`.
5. A failed restore on demotion re-stashes the not yet restored rules and re-raises.
6. Executed inline; STATE.md, ROADMAP.md and state.json untouched.

## Open points for later waves

- Role-change promotion drops the origin records of the stashed rules; they return on demotion with the stashed origins.
- `change_role` returns `dropped_rules = 0` for demotion; the number of restored rules is not reported.
- A user listed in the stash who is deleted loses the stash (`drop_user` cascades).
- `GET /api/users` in `accounts.list_users` reads users, ACL and tokens (3 short DB reads); fine at this scale.
- Provisioned users: the CLI error `provisioned` surfaces as `protected` (409) via the router.
