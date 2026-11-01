---
phase: 24-ntfy-add-on-admin-gui
plan: 07
subsystem: backend
tags: [ntfy, rights, tokens, topics, python-stdlib]
requires: ["24-02", "24-03"]
provides:
  - effective-rights evaluator and GET api/effective
  - token services and routes (list, create, reveal, revoke) with D-13 value hygiene
  - random topic suggestion GET api/topics/suggest
affects: [24-10, 24-11]
actuals:
  tasks: 3
  commits: 3
requirements-completed: [D-13, D-08, D-17, ROADMAP-SC4]
completed: 2026-11-02
---

# Phase 24 Plan 07: effective rights, tokens, topic generator Summary

## Commits

- `676fc0c` feat(ntfy): add effective-rights evaluator and GET api/effective
- `57bba20` feat(ntfy): add token services and routes with on-demand reveal
- topic suggestion commit (`feat(ntfy): add random topic suggestion with default ACL`)

## Verification

- `pytest test_rights test_tokens test_topics test_contract`: 50 passed; whole `ntfy/tests`: 154 passed.
- py_compile of the three services ok; no line over 120 chars in the new files; no `import random` in topics.py.
- No Docker used.

## Deviations

1. Source kind: a matching `everyone` rule is always `everyone-rule` (also when the queried user is `everyone`),
   otherwise `user-rule`.
2. Token revoke also writes an audit line (`token revoked user= id=`) next to the reveal line; neither has the value.
3. API handlers reject non-string `label`/`expires`/`user`/`id` with `bad_request`; empty label/expires strings count
   as absent.
4. Test servers use `make_server(..., ingress_remote="127.0.0.1")` so the in-process peer passes the ingress gate.

## Open points for later waves

- 24-11 must run the evaluator against real ntfy HTTP status codes (T-24-26); only the six verified outcomes and the
  documented tie-breaks are unit-tested here.
- `tokens.list_tokens` does not prune origin records; callers that want pruning call `origins.prune` (24-06/09).
- Token create/revoke on provisioned tokens is left to the CLI error (`protected`/`ntfy_error` mapping).
- `suggest()` only proposes; the client applies the ACL with one `PUT api/acl` per entry (24-06 route).
