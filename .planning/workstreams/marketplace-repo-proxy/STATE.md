---
gsd_state_version: "1.0"
current_phase: 02
current_plan: 5
status: executing
stopped_at: Completed 02-04-PLAN.md
last_updated: "2026-11-18T23:40:58.963Z"
last_activity: 2026-11-18
last_activity_desc: Phase 02 execution started
state_head: 68fa4e23ec52c0e5999a707c8b5e96a8a82ff8ca
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 13
  completed_plans: 10
  percent: 0
workstream: marketplace-repo-proxy
created: 2026-11-17
current_phase_name: Supervisor integration
---

# Project State

## Current Position

**Current Plan:** 5
**Total Plans in Phase:** 7
**Status:** Ready to execute
**Current Phase:** 02
**Last Activity:** 2026-11-18 — Phase 02 execution started
**Last Activity Description:** Phase 02 execution started

## Progress

**Phases Complete:** 0
**Progress:** [░░░░░░░░░░] 0%

## Session Continuity

**Last session:** 2026-11-18T23:40:58.933Z
**Stopped At:** Completed 02-04-PLAN.md
**Resume File:** None

## Performance Metrics

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 13 min | 2 tasks | 34 files |
| Phase 01 P02 | 10min | 3 tasks | 7 files |
| Phase 01 P03 | 8min | 3 tasks | 11 files |
| Phase 01 P04 | 4min | 2 tasks | 5 files |
| Phase 01 P05 | 8min | 2 tasks | 1 files |
| Phase 01 P06 | 6min | 4 tasks | 7 files |
| Phase 02 P01 | 13min | 2 tasks | 11 files |
| Phase 02 P02 | 13min | 3 tasks | 8 files |
| Phase 02 P03 | 11min | 2 tasks | 7 files |
| Phase 02 P04 | 5min | 2 tasks | 4 files |

## Decisions

- [Phase 01]: 01-01: AccessStore.locked() is reentrant per thread so users add stores and reconciles under one lock
- [Phase 01]: 01-01: sync sets umask 022; init sets /srv/git and /srv/git/repos 0755 and /etc/gitconfig 0644 so lighttpd can read repos and safe.directory
- [Phase 01]: Sync trigger file is unlinked before every cycle; a pending request is served by any cycle that starts after it
- [Phase 01]: Invalid test upstream override fails closed: all repositories fetch_failed, upstream_override true, no git call
- [Phase 01]: 01-03: a client hash already used by any access entry is hash_conflict; invalid_hash stays for malformed values
- [Phase 01]: 01-03: RESERVED_USERS ({local}) is matched case-insensitively and only source system may use it
- [Phase 01]: 01-03: access.json reads also hold the store lock, so the corrupt-file rename never races a writer
- [Phase 01]: 01-03: access-watch is its own s6 longrun without container env; it keeps only the repository list from options and never uses the PAT
- [Phase 01]: 01-04: safe.directory write failure and symlink-tree OSError are logged and survived; only OptionsError and AccessSchemaError stop init (D-28)
- [Phase 01]: 01-04: startup user count and user lines list only entries reconcile links (valid label, 32-hex hash)
- [Phase 01]: 01-05: /proc scans in the verify script carry positive controls (cmdline scan must see app.watch, environ scan must see SUPERVISOR_TOKEN in sync's env)
- [Phase 01]: 01-05: secrets reach verify containers only on stdin (options rewrite, needles files), never in an argv
- [Phase 01]: 01-06: DOCS.md describes access-watch as its own s6 longrun (as built), not a thread in sync
- [Phase 01]: 01-06: interim user commands documented with container addon_{repo-hash}_marketplace_repo_proxy; Phase 1 released as 0.1.0-1 without tag (manager tags after squash merge)
- [Phase 02]: 02-01: Supervisor calls only in app.supervisor (four-call allow-list, no proxy, no redirects); token read only in app.sync
- [Phase 02]: 02-01: supervisor.json registration/message are recomputed from facts (in_store, error) on every write; message only from fixed templates
- [Phase 02]: 02-01: registration pass skipped while sync is stopping; Registrar construction failure disables registration, never the sync loop
- [Phase 02]: 02-02: Store reload compares the served head against the head carried in status.json (StatusWriter.head_changes); only repositories with in_store true before the pass trigger it, one reload per interval, pending persisted in supervisor.json and sent from the wait loop (reason supervisor, never a sync cycle)
- [Phase 02]: 02-02: supervisor_state masks the reload message with app.gitops.sanitize, not app.supervisor.mask_text, to keep the import boundary (only registration and sync import the client); the Registrar masks with mask_text first
- [Phase 02]: 02-02: fake Supervisor records requests and saves store.json before it answers (fixed a request-log race that flaked test_supervisor)
- [Phase 02]: 02-03: mrp local remove reaches the Supervisor only through request files that the sync process executes once; DELETE only for slugs recorded in supervisor.json (current registration or leftover)
- [Phase 02]: 02-03: a refused DELETE becomes an in_use leftover (revoked kept) that the loop never retries; the pass drops leftovers and unconfigured repositories whose slug is gone, without DELETE
- [Phase 02]: 02-03: local and local.* are reserved; AccessStore.revoke needs system=True for them; retire_and_replace/undo_retire accept reserved labels only
- [Phase 02]: 02-03: supervisor_state masks leftover messages with gitops.sanitize (import boundary); the Registrar applies mask_text first
- [Phase 02]: 02-04: rotation old slug = recorded store_slug when valid, else the current local URL's slug; retired label local.{old slug}; any add exception rolls back via undo_retire
- [Phase 02]: 02-04: leftover detection is report-only: retired local.* entries are revoked by the pass (interrupted while listed); recorded-but-not-current listed slugs become orphaned with user null
- [Phase 02]: 02-04: mrp local rotate always prints the D-11 warning; --yes required (confirmation_required otherwise); confirmation lives only in the CLI
