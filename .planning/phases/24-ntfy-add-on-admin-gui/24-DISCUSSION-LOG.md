# Phase 24: ntfy add-on + admin GUI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-01
**Phase:** 24-ntfy add-on + admin GUI
**Areas discussed:** Bootstrap & options baseline, origin & export format, reachability & migration, GUI scope &
dangerous actions, GUI technology/backups/cache

---

## Bootstrap & options baseline

| Option | Description | Selected |
|--------|-------------|----------|
| Options admin_user + admin_password | Add-on creates the admin at start if missing, idempotent | ✓ |
| First GUI call (wizard) | No secret in options, but a setup window | |
| Only via auth-users in options | Password hash directly in options | |

| Option | Description | Selected |
|--------|-------------|----------|
| Add-on applies additively via CLI | Own baseline options, never deletes, origin `options` | ✓ |
| ntfy-native auth-users/auth-access | Provisioned, read-only, deleted on restart | |
| No baseline in v1 | Options only base-url/default access/admin | |

**User's choice:** Recommended options for both.
**Notes:** Context later showed the old add-on already has `admin_user`/`admin_password`, which fits the first choice.

---

## Origin & export format

| Option | Description | Selected |
|--------|-------------|----------|
| No secrets | Users, ACLs, token metadata only | |
| Optional with hashes | Default without secrets, checkbox adds password hashes | ✓ |
| Always with hashes | Full snapshot, export itself is a secret | |

| Option | Description | Selected |
|--------|-------------|----------|
| YAML and JSON, one schema | Versioned `schema: 1` | ✓ |
| YAML only | | |
| JSON only | | |

| Option | Description | Selected |
|--------|-------------|----------|
| gui \| options \| iac | Sidecar in /data, unknown entries count as gui | ✓ |
| gui \| iac only | Baseline counts as iac | |

**User's choice:** Optional hashes; YAML+JSON; three origin values.
**Notes:** Deviation from the recommended "no secrets": hashes are opt-in via checkbox. Token values stay out of the export.

---

## Reachability & migration

| Option | Description | Selected |
|--------|-------------|----------|
| host_network + listen_port 8000 as before | Routing and clients unchanged | ✓ |
| Bridge network with published port | More isolated, routing must change | |

| Option | Description | Selected |
|--------|-------------|----------|
| Options-compatible baseline | `baseline_users[]` with the old fields, additive | ✓ |
| Fresh start + export of old structure | | |
| DB takeover via backup/restore | | |

**User's choice:** Recommended options for both.
**Notes:** Old add-on options were inspected: `admin_user`, `admin_password`, `auth_default_access`, `base_url`, `enable_web_ui`, `listen_port`, `reset_data`, `users[]` (username/password/topic/write_access). One earlier statement ("the old add-on has no options") was wrong and corrected during the discussion. The admin password was displayed in tool output while checking; user was advised to consider rotating it.

---

## GUI scope & dangerous actions

| Option | Description | Selected |
|--------|-------------|----------|
| Separate reset actions | ACLs / cache / everything, typed confirmation, auto backup | ✓ |
| One reset button | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Last admin + options admin protected | | ✓ |
| Only last admin protected | | |
| No guardrails | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Show token once | Masked afterwards | |
| Always revealable by click | More convenient, screenshot risk | ✓ |

**User's choice:** Separate resets; last admin + options admin protected; tokens always revealable.
**Notes:** Deviation from the recommended "show once". Recorded as D-13 with a mitigation (hidden by default, revealed per row on demand).

---

## GUI technology, backups, cache

| Option | Description | Selected |
|--------|-------------|----------|
| Like secrets-sync (stdlib server + static vanilla JS) | | (first choice, then refined) |
| Like haos-monitor (busybox httpd + CGI) | | |
| Node/framework SPA | | (asked about extra effort) |
| Vanilla JS + vendored Preact/htm | No build step, no npm | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| /data/backups, last 10 | | |
| Only before destructive actions, last 5 | | |
| Configurable via option | `backup_keep`, default 10 | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Persistent cache, attachments off | | |
| Cache + attachments persistent | | |
| Both switchable via options | `attachments_enabled`, `cache_duration`, ... | ✓ |

**User's choice:** Tried option 1 and asked how much more effort option 3 would be. After the estimate (+30–50 % on the GUI part, extra npm maintenance), chose vanilla JS + vendored Preact/htm.
**Notes:** Backup retention and cache/attachments become options.

---

## Claude's Discretion

Base image and ntfy install method, process supervision, GUI JSON API shape, sidecar file format, exact option names
beyond those listed, CSS details, test layout.

## Deferred Ideas

GUI import of a desired-state file; Node SPA migration; IaC API (Phase 25).

---

## Follow-up 2026-11-02: network mode (revises D-10)

Triggered by the ntfy-ingress spike: `host_network: true` + ingress has no precedent in the repo, the ingress peer
address is unverified and port 8099 would be reachable from the LAN.

| Option | Description | Selected |
|--------|-------------|----------|
| Keep host_network + listen_port 8000 | Routing unchanged, needs a live-HA verification wave | |
| Bridge network, port 8000 not published | Cloudflared/Traefik reach `72a005f5-ntfy:8000` internally; `listen_port` dropped | ✓ |
| Bridge network, port 8000 published | LAN clients keep working, ntfy directly reachable in the LAN | |

**User's choice:** Bridge network; the user asked why host_network was needed at all and noted that Cloudflared can
target ports. Port stays unpublished by default (recommended option).
**Notes:** The earlier host_network choice was inherited from the old add-on, not a technical requirement. Open item
for DOCS/planning: check which clients still use `http://<HA-IP>:8000` directly and the current Cloudflared/Traefik
target before cut-over.
