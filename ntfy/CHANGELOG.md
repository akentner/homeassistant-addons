# Changelog

All notable changes to the **ntfy** add-on are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/). The add-on version follows upstream ntfy; a change that only touches
the add-on (GUI, options, docs) bumps the subpatch (`-N`).

## [2.36.0-0] - 2026-11-01

### Added

- ntfy server add-on on the bridge network, listening on container port 8000 (`72a005f5-ntfy:8000`)
- Options pass-through for base URL, web UI, proxy trust, default access, message cache and attachments
- Ingress-only admin GUI: users, ACL rules with a topic x user matrix, tokens, effective-rights lookup, random topic
  generator, health with test publish, state export and backups
- Baseline users from the options, applied additively at each start; origin markers `gui` and `options`; optional
  `baseline_overwrite_passwords`
- State export (schema 1) as YAML and JSON, without secrets by default
- Daily and pre-action backups of `auth.db` with rotation, and guarded reset actions with typed confirmation
- Guardrails for the last admin and the options admin, and a role-change stash that restores rules on demotion
- Migration guide from the mrschloemps ntfy Server add-on (see DOCS.md)

Release links are added after the first tag exists.
