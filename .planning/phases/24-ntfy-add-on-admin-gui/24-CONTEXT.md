# Phase 24: ntfy add-on + admin GUI - Context

**Gathered:** 2026-11-01
**Status:** Ready for planning

<domain>
## Phase Boundary

New `ntfy/` add-on based on upstream ntfy (binwiederhier/ntfy) that replaces the currently used third-party add-on
(`mrschloemps Repo`, "ntfy Server" 1.2.4: one topic per user, no free ACLs). It passes ntfy's server configuration
through as add-on options and ships an ingress-only admin GUI for users, ACLs and tokens. Live users/ACLs/tokens live
in ntfy's `auth.db` under `/data`; add-on options carry only a baseline. The GUI can export the current state as a
desired-state file (the contract for Phase 25). The IaC API itself is Phase 25 and out of scope here.

</domain>

<decisions>
## Implementation Decisions

### Source of truth and data model (carried forward from the planning discussion)
- **D-01:** Live users, ACLs and tokens live in ntfy's `auth.db` in `/data` (persisted, part of HA backups). Writing
  live ACLs back into the add-on options via `POST supervisor/addons/self/options` is rejected (edit conflicts,
  secrets in options/backups, duplicate of `auth.db`).
- **D-02:** The GUI backend drives ntfy through the CLI (`ntfy user/access/token`) or the DB, never through the
  undocumented `/v1/users` HTTP API. No ntfy admin password is needed on the network.
- **D-03:** The GUI is served via HA Ingress only (ingress check like `secrets-sync`: remote `172.30.32.2` plus
  `X-Ingress-Path`). ntfy itself is not proxied through ingress.

### Bootstrap and options baseline
- **D-04:** First admin comes from the options `admin_user` + `admin_password` (`password` type). The add-on creates
  it at start if missing; it is idempotent and never overwrites a password later changed in the GUI.
- **D-05:** Baseline entries come from add-on options and are applied **additively via the CLI** at start (set or
  add, never delete). ntfy's native declarative `auth-users`/`auth-access` (delete-on-restart semantics) is **not**
  used. Baseline entries show origin `options` in the GUI and stay editable. — **Reversibility:** costly — option
  names and semantics become part of every user's stored add-on configuration.
- **D-06:** Option compatibility with the old add-on: `baseline_users[]` takes the same fields as the old `users[]`
  (`username`, `password`, `topic`, `write_access`). Each entry becomes a user plus an ACL on its topic (`rw` when
  `write_access` is true, else `ro`). Old options can be copied over 1:1. — **Reversibility:** costly — same
  reason as D-05.
- **D-07:** Migration is options-based only: no DB import, the message cache starts empty. Moving `auth.db` by hand
  stays possible but is not a supported path.

### Origin marker and export
- **D-08:** Origin values are `gui | options | iac`. A sidecar file in `/data` stores the origin per user/ACL/token
  because ntfy's DB has no such field. Entries without a sidecar record (for example created with the ntfy CLI) count
  as `gui`. `iac` is only written from Phase 25 on.
- **D-09:** Export is available as YAML and JSON from one versioned schema (`schema: 1`). By default it contains no
  secrets: users with role/tier, ACLs, token metadata (label, expiry). A checkbox "include password hashes" adds
  hashes (for migrating to another instance). Token values are never part of the export. — **Reversibility:**
  one-way — the schema is the contract for Phase 25 (`GET /v1/state`, `PUT /v1/desired-state`) and for IaC repos
  that consume it.

- **D-18:** Option `baseline_overwrite_passwords` (bool, default `false`). When false, passwords of baseline users that
  already exist are never touched at start (rotation happens in the GUI). When true, the baseline password is set
  again at every start (the old add-on's behaviour). Decided 2026-11-02. Related answers the same day:
  `attachments_enabled` defaults to `true` (limits 1G / 15M / 12h, like the old add-on); `enable_web_ui: true` serves
  `/` and `/app`, `false` disables the web UI.

### Reachability and network
- **D-10:** Bridge network (`host_network: false`), changed on 2026-11-02 from the earlier "host_network like the old
  add-on" decision (host_network was never technically required). ntfy listens on the fixed container port 8000
  (`ports: 8000/tcp: null`, not published on the host by default; the user may map a host port in the HA UI). The
  `listen_port` option is dropped. Cloudflared/Traefik reach it by add-on hostname and container port
  (`72a005f5-ntfy:8000`, same pattern as `coding-assistants`); that hostname replaces the old
  `f6c6b703-ntfy-server` as the one routing change during migration. The GUI listens separately on the ingress port
  8099 and is not reachable from the LAN. `base_url` and `enable_web_ui` stay options (current values:
  `https://ntfy.akentner.de`, web UI on). The ingress gate (`172.30.32.2` + `X-Ingress-Path`) is proven for bridge
  add-ons by `secrets-sync`, so no live-HA verification wave is needed for it. Old and new add-on can run side by
  side during migration (different hostnames, no host port clash). — **Reversibility:** costly — hostname and
  routing targets in Cloudflared/Traefik depend on it.

### GUI scope and dangerous actions
- **D-11:** Reset replaces the old `reset_data` option and is split into separate GUI actions: "reset ACLs",
  "clear message cache" and "everything incl. users". Each needs a typed confirmation and writes an `auth.db` backup
  first.
- **D-12:** Guardrails: the last admin and the options-defined `admin_user` cannot be deleted or demoted in the GUI
  (password change is allowed). Every destructive action asks for confirmation.
- **D-13:** Token values can be revealed by click in the GUI at any time (user choice, deviates from the
  "show once" recommendation; ntfy stores tokens in clear text anyway). Mitigation to plan: values are hidden by
  default and revealed per row on demand, never in list payloads unless requested.
- **D-14:** `auth.db` backups go to `/data/backups`, before every destructive action and daily at start, rotated by
  an option `backup_keep` (default 10). Backups can be downloaded in the GUI.
- **D-15:** Message cache and attachments are options: pass through at least `cache_duration` and
  `attachments_enabled` (with size/quota limits when enabled); `cache.db` persists in `/data`. Exact option set is
  Claude's discretion within this.
- **D-16:** GUI technology: vanilla JS plus a vendored Preact/htm single file (~10 KB, no CDN, no npm, no build step),
  served by a Python stdlib `ThreadingHTTPServer` with static files and a JSON API, in the style of `secrets-sync`.
  HA-style look. A later move to a Node SPA stays open. — **Reversibility:** reversible — static frontend behind a
  JSON API.
- **D-17:** GUI feature list is the one from the ROADMAP goal: user list (role, tier, tokens), ACL CRUD per
  topic/user incl. `everyone` and wildcards, topic x user matrix, token create/label/expire/revoke, effective-rights
  lookup, random 16-char topic generator with default ACL (`homeassistant` rw, `akentner` ro), health (status, DB
  size, test publish), export button.

### Claude's Discretion
- Base image choice and how the ntfy binary is installed (HA base image plus upstream release artifact at build time,
  per repo constraints), process supervision between ntfy and the GUI server, API shape of the GUI JSON endpoints,
  sidecar file format, exact option names beyond those listed, HA-style CSS details, test layout.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Repo rules and add-on pattern
- `CLAUDE.md` — add-on structure, 3-file versioning, constraints (HA base image, no bundled source, local
  `docker build` before Dockerfile commits, no Co-Authored-By), worktree rules
- `docs/DEVELOPMENT.md` — add-on development workflow
- `docs/UPDATE_VERSION.md` — version bump via `make update-version`
- `docs/AUTO_UPDATE_GUIDE.md` — `.upstream.yaml` and the auto-update workflow
- `.planning/codebase/CONVENTIONS.md`, `.planning/codebase/STRUCTURE.md`, `.planning/codebase/TESTING.md` — lint,
  layout and test conventions

### GUI reference implementations
- `secrets-sync/app/web/server.py` — stdlib server, ingress-only check (`INGRESS_REMOTE`, `X-Ingress-Path`), static
  shell plus JSON API
- `secrets-sync/app/web/static/` — static frontend layout (`index.html`, `app.js`, `app.css`, `icon.png`)
- `secrets-sync/Dockerfile`, `secrets-sync/config.yaml` — ingress setup (`ingress_port: 8099`, `panel_admin`)
- `haos-monitor/config.yaml`, `haos-monitor/DOCS.md` — second ingress GUI add-on, `image:` key, ports and map usage
- `gatus/config.yaml`, `gatus/run.sh`, `gatus/generate_config.py` — options-to-config bridge for a Go service

### Upstream and prior art
- https://docs.ntfy.sh/config/ — `auth-file`, `auth-default-access`, `auth-users`, `auth-access`, `auth-tokens`, CLI
  `ntfy user/access/token`
- https://github.com/binwiederhier/ntfy/releases/tag/v2.5.0 — admin API `v1/users`, `v1/users/access` (undocumented,
  not used)
- Old add-on source: https://github.com/mrschloemp/ntfy-addon-HomeAssistant — option set to stay compatible with

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `secrets-sync/app/web/server.py`: ingress-only gate and handler structure to copy for the ntfy GUI server
- `secrets-sync/app/web/static/*`: HA-style static frontend skeleton
- `gatus/run.sh` + `gatus/generate_config.py`: pattern for turning `/data/options.json` into the service config
- `internal/update-version.py`, `make update-version`: versioning for the new add-on (3-file sync)

### Established Patterns
- Add-ons use the `image:` key with `ghcr.io/akentner/homeassistant-addons/{arch}-<name>`, `init: false`,
  `startup: application`, ingress on port 8099, `panel_admin: true`
- Python scripts: stdlib only, type hints, `pathlib.Path`, English comments, 120-char lines
- Upstream binaries are downloaded at build time, never bundled; `.upstream.yaml` drives the daily auto-update

### Integration Points
- Old add-on `f6c6b703_ntfy_server` (host_network, listen_port 8000, hostname `f6c6b703-ntfy-server`, options `admin_user`, `admin_password`,
  `auth_default_access`, `base_url`, `enable_web_ui`, `listen_port`, `reset_data`, `users[]`) is the migration source
- Consumers: Home Assistant (`homeassistant` rw), the notebook client (`akentner` ro), Gatus (`gatus` user),
  Cloudflare/Traefik routing to `ntfy.akentner.de` (target must change to the new add-on hostname; current target not
  checked, see Specific Ideas)
- Phase 25 consumes the export schema defined here

</code_context>

<specifics>
## Specific Ideas

- Topics follow the existing convention: random 16-character alphanumeric strings (A-Z, a-z, 0-9), default ACL
  `homeassistant` rw, `akentner` ro; topic `public` with everyone ro is a known pattern.
- Migration note for DOCS: the old `listen_port` option has no counterpart (fixed container port 8000); someone must
  repoint the Cloudflared/Traefik target for `ntfy.akentner.de` from the old to the new add-on hostname, and check
  whether any client still uses `http://<HA-IP>:8000` directly (HA ntfy integration, Gatus) before relying on an
  unpublished port.
- Known gaps for research: ntfy CLI behaviour against a live DB (SQLite concurrency while the server runs), ingress
  path handling for the GUI, whether the ntfy web app and `/app` work with the chosen `base_url`.

</specifics>

<deferred>
## Deferred Ideas

- Import of a desired-state file through the GUI — Phase 25 covers machine import via the API; revisit if needed.
- Node/framework SPA for the GUI — possible later migration (D-16).
- IaC API, bearer token, `dry_run`/`prune` — Phase 25.

None of the reviewed todos matched this phase.

</deferred>

---

*Phase: 24-ntfy-add-on-admin-gui*
*Context gathered: 2026-11-01*
