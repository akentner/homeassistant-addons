# Phase 3: Management GUI - Context

**Gathered:** 2026-11-18
**Status:** Ready for planning
**Source:** Discuss step skipped by instruction. Decisions come from `marketplace-repo-proxy/SPIKE.md` (section
"Decisions" is binding, the design sections "Management page (Ingress)", "URL scheme and access tokens" and
"Read-only guarantees" are the agreed design), the Phase 1 contracts in `marketplace-repo-proxy/DOCS.md` and the
manager brief for this phase (2026-11-18). Items those sources do not answer are listed under "Claude's Discretion" or
"Open questions"; they are not decided here.

<domain>
## Phase Boundary

An ingress page on the admin-ui blueprint shows the published repositories with their sync state, manages users and
their hashes (add, revoke, rotate), shows each user's store URLs and last fetch, and explains the setup. A lighttpd
access-log sink feeds "last fetch" without ever logging a hash.

In scope: MRP-12 (ingress GUI on the admin-ui lib and skeleton, rules, de/en, tests in CI), MRP-13 (Repositories view,
"Sync now", registration status slot), MRP-14 (Access view), MRP-15 (access-log sink, last fetch), MRP-16 (Info view).

Out of scope: Supervisor calls, the `local` system user's lifecycle and the registration data itself (Phase 2, built in
parallel on another branch); the bearer API listener, API token display and the "managed by IaC" marking beyond the
plain `api` source badge (Phase 4); reverse-proxy documentation and the HTTPS clone test (Phase 5).

</domain>

<decisions>
## Implementation Decisions

### GUI server and blueprint (MRP-12)
- **D-01:** The GUI uses the admin-ui browser lib and Python skeleton, copied in only by
  `make sync-admin-ui ADDON=marketplace-repo-proxy` (consumer copies under `app/web/static/vendor/admin-ui/` and
  `app/web/admin_ui/`, each with `LIB.stamp`). Consumer copies are never edited by hand (R-15). The consumer recipe in
  `admin-ui/DOCS.md` is the reference; `haos-monitor` and `ntfy` are the closest existing consumers.
- **D-02:** `config.yaml` gets `ingress: true` and `ingress_port: 8099`. Port 8099 never appears under `ports`. The
  change to `config.yaml` is additive only (Phase 2 adds `hassio_api`/`hassio_role` to the same file).
- **D-03:** Every request passes the skeleton's ingress gate (R-01): the Supervisor's ingress peer (`INGRESS_REMOTE`)
  plus a non-empty `X-Ingress-Path`, otherwise 403 `ingress_only` for every method and path. Phase 3 registers no `public=True` route. Git
  traffic never runs through the GUI server.
- **D-04:** Rules R-01 to R-15 apply to the GUI and `make check-admin-ui-rules` passes. R-16 (bearer listener) is not
  used in this phase: no API listener, no port 8098 (Phase 4). All user-visible strings go through `t()`/`tp()` with
  identical German and English key sets (R-06); errors map through `tError` (R-14); dates and relative times through
  `format.mjs` (R-07).
- **D-05:** Tests: node tests for the views and i18n parity (R-12) and pytest for the server routes and the GUI service
  layer. The existing CI job `marketplace-repo-proxy` in `.github/workflows/lint.yml` gains Node setup, the node tests,
  `make check-admin-ui-sync` and `make check-admin-ui-rules` (pattern: the `ntfy` job). The add-on becomes a registered
  admin-ui consumer, so `make release-admin-ui-lib` tests it with the other consumers.

### Processes and secrets
- **D-06:** The GUI runs as its own s6 longrun `gui` (new service directory, entry in the user bundle, depends on
  `init`), next to `init`, `lighttpd`, `sync` and `access-watch`. No existing service is merged into it.
- **D-07:** The GUI holds no GitHub PAT and no `SUPERVISOR_TOKEN` (manager brief). Its run script uses plain
  `#!/bin/sh` without `with-contenv`, like `access-watch` and `lighttpd`. From the add-on options it keeps only
  non-secret fields (repository list, `public_url`, log level), following the `access-watch` precedent (Phase 1 01-03:
  "keeps only the repository list from options and never uses the PAT"). No response, log line or long-lived object of
  the GUI contains the token. Note: SPIKE "Supervisor integration" says the Supervisor token "stays in the `gui`/`sync`
  processes"; the manager brief is later and stricter and wins (Phase 2 D-03 is consistent with it).
- **D-08:** Internal store URLs are built exactly like the Phase 1 startup log and CLI (`app/urls.py`
  `store_urls`/`internal_base`, same hostname source); public store URLs appear only when `public_url` is set.

### Access store (MRP-14, shared with CLI and access-watch)
- **D-09:** The GUI writes `/data/access.json` only through Phase 1's `app.access.AccessStore`: the exclusive lock on
  `/run/marketplace-repo-proxy/access.lock` (plus the per-thread reentrant lock), re-read under the lock, temp file +
  `fsync` + atomic rename + directory `fsync`, unknown fields preserved, symlink created/removed in the same lock. No
  second writer implementation. CLI, `access-watch` and GUI follow identical rules. GUI-created entries carry
  `source: "gui"`.
- **D-10:** Phase 3 composes existing `AccessStore` methods (`locked()`, `get`, `list_entries`, `add`, `revoke`,
  `reconcile`) in its own GUI service module and avoids changes to `app/access.py`. Phase 2 may change that file for the
  `local` user's rotation; keeping Phase 3 out of it keeps the merge simple. If a change to `app/access.py` turns out to
  be unavoidable, it is additive (new function at the end, no edits to existing ones) and named in the plan.
- **D-11:** Rotate gives an existing (repository, user) a new random hash in one locked operation (no window in which
  the user is missing or both hashes work); the old URL answers 404 from the next request on, the new URL works at once.
- **D-12:** Revoke and rotate are destructive: `ConfirmDialog` with `expected` = the user label, and the server answers
  `confirmation_required` when the phrase is missing or wrong (R-04). The rotate dialog states the consequence before
  confirming: the consuming Supervisor sees a new repository, the add-ons installed from the old URL must be reinstalled
  (back up their data first), and the old URL stops working immediately.
- **D-13:** Users with `source: "system"` (Phase 2's `local` user) are shown read-only: no revoke or rotate in the GUI.
  `AccessStore` already refuses the reserved label for non-system sources (`user_reserved`). Their lifecycle belongs to
  Phase 2's Supervisor-aware path. Users with source `gui`, `cli` or `api` can be revoked and rotated.
- **D-14:** Each user row shows a source badge: `gui`, `cli`, `api` or `system` (MRP-14; `cli` per Phase 1 D-25).
- **D-15:** Stable error codes (R-14), reusing Phase 1's codes where they exist: `repository_unknown`, `user_exists`,
  `user_unknown`, `invalid_user`, `user_reserved`, `hash_conflict`, plus `confirmation_required`; every code has an
  `errors.<code>` string in both languages.
- **D-16:** Full store URLs appear only in the Access view, as text in `CopyField` (R-03), behind HA login and ingress.
  They are never logged. API responses keep the skeleton's `Cache-Control: no-store`.

### Repositories view and "Sync now" (MRP-13)
- **D-17:** The Repositories view reads `/data/status.json` (single writer `sync`, atomic replace, readers need no lock):
  `owner/repo`, branch and its source, status code (`pending`, `ok`, `auth_failed`, `not_found`, `no_repository_yaml`,
  `fetch_failed`) with its sanitised `message`, last sync (relative), HEAD short SHA, add-ons found, and the sync state
  (`idle`/`running`, next due). A missing or unreadable `status.json` is shown as "no status yet", not as an error page.
- **D-18:** "Sync now" creates the Phase 1 trigger file `/run/marketplace-repo-proxy/sync.request` (content `{}`), the
  same mechanism as `mrp sync`. The trigger is global (one cycle over all repositories), so there is one action, not one
  per repository. The view polls (`usePoll`) to show `running` and then the new result.

### Registration status slot (MRP-13, data from Phase 2)
- **D-19:** The registration status is optional. One isolated reader (a single function in its own module) returns "no
  data" in Phase 3; the GUI API carries an optional `registration` field per repository that is null/absent, and the
  view shows the registration column or badge (and a leftover note) only when at least one value is present. No import
  of Phase 2 code and no hard reference to its files. Phase 2 has not fixed where it writes the state
  (`status.json` extension or a new file, Phase 2 CONTEXT "Claude's Discretion"); only this reader changes once both
  phases are on `main`.

### Access-log sink and last fetch (MRP-15)
- **D-20:** lighttpd writes its access log to a pipe (`accesslog.filename = "|<sink>"`). The sink maps the hash in the
  request path to the user label, records "last fetch" per (repository, user) and logs only
  `fetch: <user> → <owner>/<repo>`. It never writes the hash or the raw request line anywhere: not to stdout or stderr,
  not to the add-on log, not to a file. `server.breakagelog = "/dev/null"` stays. Phase 1 T-01-02 ("no access log")
  changes to "access log only into the sink"; the security model is updated accordingly.
- **D-21:** "Last fetch" is persisted in a new contract file under `/data` (survives restarts and is part of backups like
  `access.json`): JSON with a `schema` field, mode 0600, atomic replace, exactly one writer. It is documented in
  DOCS.md "Contracts" like the Phase 1 files (names, fields, write rules, timestamps in ISO 8601 UTC with `Z`). The GUI
  reads it.
- **D-22:** The sink must not widen any permission: `/data` stays 0700, `access.json` 0600, access directories 0711
  (Phase 1 T-01-09, T-01-21). How the sink gets the hash-to-user mapping given that lighttpd runs as `lighttpd` is a
  research item (see Open questions); a design where the piped process forwards only (owner, repo, hash) over a private
  channel to a root-side component is acceptable when the hash is never logged and never persisted outside 0600 files in
  `/data`.

### Info view (MRP-16)
- **D-23:** Info view with static, translated text and no actions: how to add a store URL in Home Assistant (copy it from
  the Access view; one host name per HA instance, because the host is part of the repository identity), reverse proxy
  notes (TLS at the proxy, no caching of `/repo/*`, no path logging; details follow in Phase 5) and the rotation
  procedure (back up the add-ons' data, remove the old repository, add the new URL, reinstall).

### Coexistence with Phase 2 (parallel branch)
- **D-24:** Changes to files Phase 2 also touches (`config.yaml`, `Dockerfile`, `rootfs/` s6 services, lighttpd config,
  `DOCS.md`, `CHANGELOG.md`, `.github/workflows/lint.yml`) stay small and additive: new s6 services and new modules
  instead of edits to existing ones, no reordering or reformatting of existing lines.
- **D-25:** Container proof goes into a new script `internal/verify-marketplace-repo-proxy-gui.sh` instead of extending
  Phase 1's `internal/verify-marketplace-repo-proxy.sh` (which Phase 2 extends). It proves: GUI requests from outside
  ingress get 403, the GUI process environment holds neither the PAT nor `SUPERVISOR_TOKEN`, a GUI add/revoke/rotate
  changes git access (200/404), "Sync now" starts a cycle, a clone records last fetch and logs
  `fetch: <user> → <owner>/<repo>`, and no full hash appears in the add-on log or the sink's output. Like every
  `internal/verify-*.sh`, it never runs in two worktrees at the same time.

### Repository rules (CLAUDE.md)
- **D-26:** HA base image only; no new base image. `python3` is already installed. Any Dockerfile change is verified
  with a local `docker build` before commit.
- **D-27:** Public repository: no hostnames, IPs, e-mail addresses, person names or tokens in files or commit messages;
  the production HA host is named only "production host"; examples use `example-org/private-addons` and placeholders.

### Release
- **D-28:** The last step of the phase is the subpatch bump through
  `make update-version ADDON=marketplace-repo-proxy VERSION=<next> NO_TAG=yes` (never by hand). `<next>` is the next
  free subpatch at that moment, read fresh from `origin/main` (`git fetch origin main`, then the version in
  `origin/main:marketplace-repo-proxy/config.yaml`): expected `0.1.0-3` if Phase 2 is merged first, else `0.1.0-2`. If
  `origin/main` carries `marketplace-repo-proxy/` changes this branch lacks, the branch is rebased onto `origin/main`
  first (`git pull --rebase --autostash origin main`); a conflict stops the plan and goes to the manager. `CHANGELOG.md`
  gets `## [<next>] - <date>`. No tag; the manager tags after the squash merge (Phase 1 D-32).
- **D-29:** `DOCS.md` replaces "There is no management page yet" with the GUI's usage (the `mrp` CLI stays documented),
  adds the last-fetch contract and the sink to "Contracts" and "Security notes"; `README.md` mentions the management
  page. `translations/*.yaml` change only if new options are added (none are planned).

### Claude's Discretion
- GUI API routes and JSON field names (relative URLs under `api/`, R-02), for example `api/repositories`, `api/sync`,
  `api/access`, `api/access/{owner}/{repo}/{user}` and `.../rotate`.
- Whether the Access list returns full URLs for every user or the URLs are fetched per user on demand (both meet D-16;
  on demand reduces exposure in a single response).
- Whether rotate keeps `created` and `source` or resets them, and whether an additive field (for example `rotated`) is
  written. The DOCS.md contract allows new fields; the choice is documented.
- What counts as a fetch for "last fetch" (likely a successful `git-upload-pack` POST; `info/refs` alone is only the
  handshake of `ls-remote`), and whether last fetch survives a rotation; documented either way.
- Behaviour of the sink for an unknown or revoked hash (no line, or a line without the hash), log level and throttling of
  the `fetch:` lines.
- Navigation (`Topbar` with `nav="topbar"` or tabs), poll intervals, panel icon and title in `config.yaml`, version text
  in the top bar.
- Module layout under `app/web/` and of the sink, s6 service names other than `gui`.

</decisions>

<specifics>
## Specific Ideas

- SPIKE "Management page (Ingress)" table is the view specification: Repositories (`owner/repo`, branch, last sync
  relative, HEAD short SHA, add-ons found, status; action Sync now), Access (per repository: user label, created, last
  fetch, store URLs internal and public as `CopyField`; actions add, revoke, rotate), Info (setup steps; no actions).
- Phase 1 `status.json` already carries everything the Repositories view needs (`head`, `addons`, `last_success`,
  `last_attempt`, `sync.state`, `sync.next_due`).
- `access.json` entries of repositories that are not configured stay in the file but grant no access; the GUI should show
  them as inactive (like `mrp users list` marks `(inactive)`) or leave them out, not crash.
- Known Phase 1 deferrals that touch the GUI: WR-04 (a transient read error moves `access.json` aside to `.corrupt`) and
  AR-02 (old commits reachable by SHA with a valid URL). The GUI reads `access.json` far more often than the CLI, so the
  research should say whether GUI reads raise the WR-04 risk.
- The admin-ui consumer test runner runs each consumer in its own Python process because the consumers' app packages
  share the name `app`; this add-on's package is also `app`.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design and decisions
- `marketplace-repo-proxy/SPIKE.md` — binding "Decisions"; "Management page (Ingress)", "URL scheme and access tokens"
  (rotation cost, logging rule for the sink), "Read-only guarantees"
- `marketplace-repo-proxy/DOCS.md` — contracts `/data/access.json`, `/data/status.json`, sync trigger; `mrp` CLI; error
  codes
- `.planning/workstreams/marketplace-repo-proxy/REQUIREMENTS.md` — MRP-12 to MRP-16
- `.planning/workstreams/marketplace-repo-proxy/ROADMAP.md` — Phase 3 success criteria 1-5
- `.planning/workstreams/marketplace-repo-proxy/phases/01-git-serving-core/01-CONTEXT.md`, `01-SECURITY.md`,
  `01-REVIEW-DISPOSITION.md`, `01-0*-SUMMARY.md` — Phase 1 decisions, threat register, deferred findings, built modules

### Blueprint
- `admin-ui/DOCS.md` — rules R-01 to R-16, library reference, consumer recipe, distribution
- `haos-monitor/app/web/`, `ntfy/app/` and their `tests/` — existing consumers (server wiring, strings, node tests)
- `internal/sync-admin-ui.py`, `internal/check-admin-ui-rules.py`, `Makefile` targets `sync-admin-ui`,
  `check-admin-ui-sync`, `check-admin-ui-rules`, `test-admin-ui-consumers`

### Repository rules
- `CLAUDE.md` — own-code exception, 3-file versioning, local docker build, verify-script concurrency, one add-on per
  branch

### Existing code
- `marketplace-repo-proxy/app/access.py`, `urls.py`, `options.py`, `paths.py`, `status.py`, `jsonio.py`, `watch.py`,
  `cli.py`, `logsetup.py`
- `marketplace-repo-proxy/rootfs/etc/lighttpd/marketplace-repo-proxy.conf`, `rootfs/etc/s6-overlay/`
- `marketplace-repo-proxy/config.yaml`, `Dockerfile`, `tests/`, `internal/verify-marketplace-repo-proxy.sh`
- `.github/workflows/lint.yml` jobs `marketplace-repo-proxy` and `ntfy`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AccessStore` (`app/access.py`): reentrant `locked()`, `get`, `list_entries`, `add(..., source=..., specs=...)`,
  `revoke`, `reconcile`; `RESERVED_USERS`; `AccessError` codes.
- `app/urls.py`: `store_urls`, `internal_base`, `masked_store_url`, `mask_hash`.
- `app/status.py`: `read_status` and the status schema.
- `app/logsetup.py`: `SafeFormatter` and the redactor that masks 32-hex values.
- `access-watch` s6 service: template for a Python longrun without container environment.

### Established Patterns
- Python stdlib only inside the image (`apk` `python3`, no PyPI).
- Each s6 longrun has `type`, `run`, `finish`, `dependencies.d/init` and an entry in
  `user-bundles.d/user/contents.d/`.
- Tests: pytest with file fixtures and injected paths (`tests/conftest.py`), RED stubs before implementation.
- CI: per-add-on job appended at the end of `lint.yml`.

### Integration Points
- New: `marketplace-repo-proxy/app/web/` (server, GUI service layer, static views, strings), the sink, s6 services `gui`
  (and the sink's, if it needs one), lighttpd `accesslog` settings, `internal/verify-marketplace-repo-proxy-gui.sh`.
- Changed: `config.yaml` (ingress keys), `Dockerfile` (only if needed), `DOCS.md`, `README.md`, `CHANGELOG.md`,
  `.github/workflows/lint.yml`.

</code_context>

<open_questions>
## Open Questions (not decided; collected for the manager, not blocking planning)

- **Q-1 (registration source):** Phase 2 writes the registration state to a place it has not fixed yet. Assumption:
  Phase 3 ships the isolated reader returning "no data" (D-19); whichever phase merges second wires the reader to the
  real source in a small follow-up.
- **Q-2 (sink privileges):** Can a lighttpd piped logger read `/data/access.json` without widening permissions? Depends
  on whether lighttpd spawns piped loggers before dropping to user `lighttpd` and on respawn behaviour. Research
  decides the mechanism within D-22.
- **Q-3 (rotation of `local`):** Assumption: the GUI never revokes or rotates the `local` system user (D-13). If the
  user wants that from the GUI, it needs a request path to the Supervisor-aware process from Phase 2, which this phase
  does not build.
- **Q-4 (rotate in both phases):** Phase 2 may add a rotate operation to `app/access.py` for the `local` user, while
  Phase 3 rotates in its own service module (D-10). If both exist after the merge, consolidating them is a follow-up.

</open_questions>

<deferred>
## Deferred Ideas

- Bearer API listener, API token display and rotation, "managed by IaC" marking (Phase 4).
- Reverse-proxy documentation, public HTTPS clone test, `stage` decision (Phase 5).
- Supervisor-aware rotation/removal of the `local` user from the GUI (Q-3).
- Per-repository "Sync now" (the Phase 1 trigger is global).

</deferred>

---

*Phase: 03-management-gui*
*Context gathered: 2026-11-18 (from SPIKE.md, Phase 1 contracts and the manager brief; discuss step skipped)*
