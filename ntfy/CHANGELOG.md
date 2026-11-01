# Changelog

All notable changes to the **ntfy** add-on are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/). The add-on version follows upstream ntfy; a change that only touches
the add-on (GUI, options, docs) bumps the subpatch (`-N`).

## [2.36.0-0] - 2026-11-01

### Added

- ntfy server add-on on the bridge network, listening on container port 8000 (`72a005f5-ntfy:8000`)
- Options pass-through for base URL, web UI, proxy trust, default access, message cache and attachments
- Ingress-only admin GUI for users, ACLs, tokens and effective rights
- Baseline users from the options, applied additively; origin markers `gui` and `options`
- State export (schema 1) as YAML and JSON, without secrets by default
- Daily and pre-action backups of `auth.db`, and guarded reset actions with typed confirmation

[Unreleased]: https://github.com/akentner/homeassistant-addons/compare/ntfy/v2.36.0-0...HEAD
[2.36.0-0]: https://github.com/akentner/homeassistant-addons/tree/ntfy/v2.36.0-0
