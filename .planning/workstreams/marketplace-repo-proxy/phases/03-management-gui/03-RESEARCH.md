# Phase 3: Management GUI - Research

**Researched:** 2026-11-18
**Domain:** Ingress admin GUI on the admin-ui blueprint (Python stdlib skeleton + Preact lib), lighttpd piped access
log, shared access store, s6-overlay services
**Confidence:** HIGH (sink mechanism, skeleton wiring, access-store composition: empirical and code-verified) /
MEDIUM (verify-script network trick, UX details)

## Summary

The deciding question of this phase (Q-2) is settled by experiment, not docs: on the add-on's own base image
(`amd64-base:3.24`, Alpine 3.24.3, **lighttpd 1.4.85**, Python 3.14.10) a piped access logger
(`accesslog.filename = "|<cmd>"`) runs as **uid 100 / gid 101 (`lighttpd`)**, both at startup and after lighttpd
respawns it (about a minute after it dies, observed 54 s). It can therefore never read `/data/access.json` (0600 root in
a 0700 root dir), and D-22 forbids widening those modes. lighttpd writes to the logger through a **non-blocking** pipe
whose read end it keeps open itself: a dead or stalled logger never stalls git serving. Records queue in the 64 KiB pipe
buffer and are then dropped with a content-free `error flushing log <cmd>` line on lighttpd's stderr. The s6-rc pipeline
alternative (lighttpd stdout → root consumer) fails: lighttpd 1.4.85 points fd 1 at `/dev/null` at startup.

**Recommended sink mechanism (conforms to D-20 and D-22):**

- lighttpd → piped forwarder `app/fetchsink.py` (stdlib only, runs as `lighttpd`, started with
  `python3 -I <path>`). The forwarder forwards only `POST /repo/<owner>/<repo>/<32hex>/git-upload-pack 200` as one
  datagram `owner repo hash`.
- The datagram goes to an AF_UNIX SOCK_DGRAM socket `/run/mrp-fetch/fetch.sock` (dir root:lighttpd 0710, socket
  root:lighttpd 0620).
- A new root s6 longrun `fetchlog` receives it. `fetchlog` maps hash → (repository, user) from a signature-cached,
  **non-destructive** locked read of `access.json`. It is the single writer of `/data/last-fetch.json` and logs only
  `fetch: <user> → <owner>/<repo>`.
- The whole chain was prototyped end to end in a throwaway container. Other uids are refused (`EACCES`), the receiver
  restarts without a lighttpd or forwarder restart, and nothing is printed.

The GUI itself is a straightforward admin-ui consumer like `haos-monitor`:

- `make sync-admin-ui ADDON=marketplace-repo-proxy` adds the copies.
- The skeleton router is wrapped by a thin `app/web/server.py`, and a GUI service module composes `AccessStore`.
- The GUI runs as its own s6 longrun `gui` with plain `#!/bin/sh`. It keeps an `Options` copy with
  `github_token=""`.

Rotation as `revoke` + `add` inside one reentrant `AccessStore.locked()` is atomic for every lock-holding reader and for
git clients. Over 200 rotations a concurrent reader process never saw the user missing. It is not crash-atomic, and it
resets `created`, which this research turns into a feature: "last fetch" is shown only when it is newer than `created`.
GUI reads raise the WR-04 exposure (rename to `.corrupt` on a transient read error) unless they avoid
`AccessStore.load()`. Use a non-destructive read under the same lock.

**Primary recommendation:**

- Build the GUI as a `haos-monitor`-style consumer plus three new services or programs: `gui`, `fetchlog` and the
  piped `fetchsink`.
- Change no existing Python module and no existing line of the lighttpd config (three appended lines).
- Prove the result with a new verify script. The script gives one client container the Supervisor's ingress address
  `172.30.32.2` on a dedicated Docker network.

<user_constraints>

## User Constraints (from CONTEXT.md)

> **Amended 2026-11-18:** user decisions D-19 (registration from `/data/supervisor.json`), D-21
> (`/data/last-fetch.json`, option-a) and D-30 (version in the top bar) in 03-CONTEXT.md supersede the copies below and
> every recommendation in this file that conflicts with them.

### Locked Decisions

#### GUI server and blueprint (MRP-12)
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

#### Processes and secrets
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

#### Access store (MRP-14, shared with CLI and access-watch)
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

#### Repositories view and "Sync now" (MRP-13)
- **D-17:** The Repositories view reads `/data/status.json` (single writer `sync`, atomic replace, readers need no lock):
  `owner/repo`, branch and its source, status code (`pending`, `ok`, `auth_failed`, `not_found`, `no_repository_yaml`,
  `fetch_failed`) with its sanitised `message`, last sync (relative), HEAD short SHA, add-ons found, and the sync state
  (`idle`/`running`, next due). A missing or unreadable `status.json` is shown as "no status yet", not as an error page.
- **D-18:** "Sync now" creates the Phase 1 trigger file `/run/marketplace-repo-proxy/sync.request` (content `{}`), the
  same mechanism as `mrp sync`. The trigger is global (one cycle over all repositories), so there is one action, not one
  per repository. The view polls (`usePoll`) to show `running` and then the new result.

#### Registration status slot (MRP-13, data from Phase 2)
- **D-19:** The registration status is optional. One isolated reader (a single function in its own module) returns "no
  data" in Phase 3; the GUI API carries an optional `registration` field per repository that is null/absent, and the
  view shows the registration column or badge (and a leftover note) only when at least one value is present. No import
  of Phase 2 code and no hard reference to its files. Phase 2 has not fixed where it writes the state
  (`status.json` extension or a new file, Phase 2 CONTEXT "Claude's Discretion"); only this reader changes once both
  phases are on `main`.

#### Access-log sink and last fetch (MRP-15)
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

#### Info view (MRP-16)
- **D-23:** Info view with static, translated text and no actions: how to add a store URL in Home Assistant (copy it from
  the Access view; one host name per HA instance, because the host is part of the repository identity), reverse proxy
  notes (TLS at the proxy, no caching of `/repo/*`, no path logging; details follow in Phase 5) and the rotation
  procedure (back up the add-ons' data, remove the old repository, add the new URL, reinstall).

#### Coexistence with Phase 2 (parallel branch)
- **D-24:** Changes to files Phase 2 also touches (`config.yaml`, `Dockerfile`, `rootfs/` s6 services, lighttpd config,
  `DOCS.md`, `CHANGELOG.md`, `.github/workflows/lint.yml`) stay small and additive: new s6 services and new modules
  instead of edits to existing ones, no reordering or reformatting of existing lines.
- **D-25:** Container proof goes into a new script `internal/verify-marketplace-repo-proxy-gui.sh` instead of extending
  Phase 1's `internal/verify-marketplace-repo-proxy.sh` (which Phase 2 extends). It proves: GUI requests from outside
  ingress get 403, the GUI process environment holds neither the PAT nor `SUPERVISOR_TOKEN`, a GUI add/revoke/rotate
  changes git access (200/404), "Sync now" starts a cycle, a clone records last fetch and logs
  `fetch: <user> → <owner>/<repo>`, and no full hash appears in the add-on log or the sink's output. Like every
  `internal/verify-*.sh`, it never runs in two worktrees at the same time.

#### Repository rules (CLAUDE.md)
- **D-26:** HA base image only; no new base image. `python3` is already installed. Any Dockerfile change is verified
  with a local `docker build` before commit.
- **D-27:** Public repository: no hostnames, IPs, e-mail addresses, person names or tokens in files or commit messages;
  the production HA host is named only "production host"; examples use `example-org/private-addons` and placeholders.

#### Release
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

### Deferred Ideas (OUT OF SCOPE)
- Bearer API listener, API token display and rotation, "managed by IaC" marking (Phase 4).
- Reverse-proxy documentation, public HTTPS clone test, `stage` decision (Phase 5).
- Supervisor-aware rotation/removal of the `local` user from the GUI (Q-3).
- Per-repository "Sync now" (the Phase 1 trigger is global).

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MRP-12 | Ingress GUI on the admin-ui lib and skeleton (`ingress_port` 8099, never published), rules R-01 to R-15, de/en strings, node and pytest tests in CI | "Consumer wiring" (sync, router, `make_server`, `app/web/__init__.py`), "CI and Makefile registration" (hard-coded consumer list in `test-admin-ui-consumers`), Pitfalls 5-7, Validation map |
| MRP-13 | Repositories view with sync status, last sync, HEAD short SHA, found add-ons, registration status and "Sync now" | Pattern 4 (status merge, "no status yet"), Pattern 5 (trigger file, `requested` flag, poll cadence), Pattern 6 (registration slot with a fixed normalised shape) |
| MRP-14 | Access view: add user, revoke and rotate (type-to-confirm with the user label), internal and public store URLs as `CopyField`, source badge | Pattern 2 (non-destructive read), Pattern 3 (rotate = revoke + add in one lock, with pre-validation and compensation), error-code table, on-demand URL route, Pitfalls 1-4 |
| MRP-15 | lighttpd access-log sink (`accesslog.filename = "\|…"`): maps hash to user label, records last fetch, logs `fetch: <user> → <owner>/<repo>` only | Section "Access-log sink: evidence and mechanism", "What counts as a fetch", last-fetch contract, Pitfalls 8-10 |
| MRP-16 | Info view with setup steps (store URL, reverse proxy notes, rotation procedure) | Pattern 7 (static view, strings only), D-23 content list |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

Repo `CLAUDE.md`, enforced like locked decisions:

- **Own-code exception:** `marketplace-repo-proxy` is our own code: no `.upstream.yaml`. HA base image only, 3-file
  version sync via `make update-version` (never by hand). Run a local `docker build` before committing Dockerfile changes.
- **admin-ui lib distribution:** the lib is distributed by `make sync-admin-ui`. Consumer copies are never edited by
  hand.
- **One add-on per branch:** stage by path (`git add marketplace-repo-proxy/ ...`), never `git add -A`. Rebase before
  merging (`git pull --rebase --autostash origin main`).
- **Planning files in this worktree:** write only `.planning/quick/` and workstream files here. `STATE.md`,
  `state.json` and `ROADMAP.md` are updated in the main worktree.
- **Verify scripts:** `internal/verify-*.sh` build images and start containers. Never run the same script in two
  worktrees at once.
- **No AI attribution:** no `Co-Authored-By` or AI attribution lines in commits or PRs.
- **Behaviour:** ask before risky actions (version bumps, CI changes) and challenge risky plans.
- **Style:**
    - YAML: 2-space indent, max 120 characters.
    - Markdown: ATX headings, 120-character limit (MD013 is an error), 4-space list indent.
    - Shell: shellcheck, ignoring SC1091 and SC2034.
    - Python: module docstring, type hints, `pathlib`, `argparse` with `RawDescriptionHelpFormatter`,
      `if __name__ == '__main__': sys.exit(main())`, `flush=True` in containerised scripts.
    - Internal scripts: `#!/bin/bash` with `set -e` (the Phase 1 verify script uses `#!/usr/bin/env bash` with
      `set -euo pipefail`; follow that precedent).
- **Workflow:** GSD workflow before edits. English code, comments and commits.
- **Public repository** (D-27): no hostnames, IPs (except well-known placeholders and the fixed HA network constants
  already in the repo), e-mails, names or tokens.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Ingress gate (R-01) | API / Backend (skeleton `make_server`) | — | Peer address + header check must be server-side; the browser cannot be trusted |
| Views, i18n, relative times, type-to-confirm UX | Browser / Client (Preact lib) | — | R-03/R-06/R-07 live in the lib; no server-side templating |
| Confirmation check (`confirmation_required`) | API / Backend (GUI service) | Browser (`ConfirmDialog`) | R-04 requires the server to refuse; the dialog is only UX |
| Access add/revoke/rotate | API / Backend (GUI service → `AccessStore`) | Database/Storage (`/data/access.json`, symlink tree) | Single writer API, flock, atomic replace (D-09) |
| Store URL building | API / Backend (`app/urls.py`) | — | Hostname and `public_url` are server facts (D-08) |
| Sync status | Database/Storage (`/data/status.json`, writer `sync`) | API (read + merge) | Single writer, readers need no lock (D-17) |
| "Sync now" | API (trigger file) | `sync` service (consumer) | Phase 1 mechanism (D-18) |
| Access-log capture | lighttpd (uid `lighttpd`) → forwarder (uid `lighttpd`) | — | Only lighttpd sees the request; the logger inherits its uid (verified) |
| Hash → user mapping, last-fetch persistence | `fetchlog` root service | Storage (`/data/last-fetch.json`) | Needs read access to 0600 root `access.json` (D-22) |
| Registration status | API (isolated reader) | Phase 2 data source (later) | D-19: one function, no import of Phase 2 code |

## Standard Stack

No new package is installed. Everything is already in the image or in CI.

### Core

| Component | Version | Purpose | Evidence |
|-----------|---------|---------|----------|
| lighttpd + `mod_accesslog` | 1.4.85 (Alpine 3.24.3) | Piped access log | `[VERIFIED: local docker run of amd64-base:3.24 + apk add lighttpd]`: `lighttpd/1.4.85 (ssl)`, `/usr/lib/lighttpd/mod_accesslog.so` ships in the base `lighttpd` package (no extra `lighttpd-mod_*` package) |
| python3 (image) | 3.14.10 | GUI, fetchlog, forwarder (stdlib only) | `[VERIFIED: same container]` `Python 3.14.10` |
| admin-ui lib + skeleton | 0.10.0 | Browser lib, Python server skeleton | `[VERIFIED: admin-ui/lib.lock:1]` `version 0.10.0`; `make check-admin-ui-sync` reports `OK ... 0.10.0` for all four existing consumers |
| git | 2.54.1 | Served by `git http-backend` (unchanged) | `[VERIFIED: same container]` |

### Supporting (CI and tests only)

| Tool | Version | Purpose | Evidence |
|------|---------|---------|----------|
| Python in CI | 3.12 | pytest runner (the image runs 3.14: keep code 3.12-compatible) | `[VERIFIED: .github/workflows/lint.yml:308-311]` `python-version: '3.12'` |
| pytest / pyyaml | 9.1.1 / 6.0.3 | Tests | `[VERIFIED: .github/workflows/lint.yml:314]` `python -m pip install 'pytest==9.1.1' 'pyyaml==6.0.3'` |
| Node.js | 22 (CI), v22.23.5 local | `node --test` view and i18n tests | `[VERIFIED: lint.yml:276-279]` ntfy job `node-version: '22'` |
| `fakedom.mjs`, `a11y_audit.mjs` | copies | DOM double and a11y audit for node tests | `[VERIFIED: sha256]` `haos-monitor/tests/js/fakedom.mjs` is identical to `admin-ui/tests/js/fakedom.mjs` (`9053aafa…`); `a11y_audit.mjs` is identical in all three (`c1a67a8b…`). Copy the `haos-monitor` versions |

### Alternatives Considered

| Instead of | Could Use | Tradeoff (verdict) |
|------------|-----------|--------------------|
| Piped forwarder + datagram socket | s6-rc pipeline (lighttpd stdout → root consumer) | **Rejected by experiment:** lighttpd 1.4.85 redirects fd 1 to `/dev/null` at startup, so `accesslog.filename = "/dev/stdout"` writes into `/dev/null` (fd listing below). Using stderr instead would couple git serving to the consumer and mix in lighttpd's error log |
| Datagram socket | FIFO in `/run` | A FIFO open blocks until a reader exists, and the writer gets EPIPE when the reader restarts, so it needs reopen logic. A datagram `sendto` is non-blocking, atomic per record and simply fails while the receiver is down (verified) |
| Forwarder in Python | `cat > fifo` as the piped command | Forwards raw lines including 404 probes with hashes; no filtering at the edge; same FIFO problems |
| Accesslog to a root-only file | — | lighttpd cannot reopen it after the privilege drop; the file would persist hashes outside `/data` (violates D-22) and grow without rotation |
| Forwarder sends `owner repo hash` | Forwarder sends `owner repo sha256(hash)` | Optional hardening: the channel then never carries a capability. D-22 explicitly accepts the plain hash; keep plain unless the reviewer asks |

**Installation:** none. `Dockerfile` needs **no change**: `app/` (including the new modules, static files and vendored
lib) and `rootfs/` are already copied.

`[VERIFIED: marketplace-repo-proxy/Dockerfile:10-12]`:

```text
WORKDIR /opt/marketplace-repo-proxy
COPY app/ ./app/
COPY rootfs/ /
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none) | — | — | — | — | — | No new package in the image, CI or tests |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

## Access-log sink: evidence and mechanism (Q-2, D-20 to D-22)

All experiments ran on `ghcr.io/home-assistant/amd64-base:3.24` with `apk add lighttpd git git-daemon python3`, in
throwaway `docker run --rm` containers (no verify script was run, nothing was left behind).

### Finding 1: the piped logger runs as `lighttpd`, also after a respawn

`[VERIFIED: local docker experiment]`. lighttpd was started as root with `server.username = "lighttpd"`; the logger
records its own `id`:

```text
   45     1 lighttpd lighttpd -D -f /etc/lighttpd/exp.conf
   47    45 lighttpd {sink.sh} /bin/sh /usr/local/bin/sink.sh
=== sink meta
start pid=47 uid=100 gid=101 ppid=45
```

After `kill` of the logger (second experiment, 75 s window):

```text
start pid=26 uid=100 t=1795027803
start pid=51 uid=100 t=1795027859        # respawned 54 s after the kill, still uid 100
```

Consequence: the logger can never open `/data/access.json` (`/data` 0700 root, file 0600 root). **Q-2 answer: no**, not
without widening permissions, which D-22 forbids. A root-side component is required.

### Finding 2: lighttpd never blocks on the logger

`[VERIFIED: local docker experiment]`. Two failure modes were tested:

- **Dead logger:** serving continues (`ls-remote-after-kill ok`). Records written while it was dead were delivered
  after the respawn, because lighttpd keeps the pipe's read end open: they queue in the kernel pipe buffer.
- **Logger that never reads:** 3000 requests were answered in 15 s, all with the correct status. lighttpd reports
  each lost record on its stderr, naming the command and never the content:

  ```text
  3000 requests in 15 s
     3000 404
  (../src/mod_accesslog.c.1058) error flushing log /usr/local/bin/blocksink.sh: Resource temporarily unavailable
  ```

The source confirms it `[CITED: github.com/lighttpd/lighttpd1.4 src/mod_accesslog.c, cross-checked by the experiment]`:

- Piped loggers are written per record, without buffering (`fdlog->mode == FDLOG_PIPE`).
- The buffer is cleared even when the write fails (`buffer_clear(b); /*(clear buffer, even on error)*/`).

Memory therefore stays bounded. The loss bound is the 64 KiB pipe buffer, about 1000 records at roughly 60 bytes each
`[ASSUMED: default Linux pipe size]`.

### Finding 3: the s6-rc pipeline alternative does not work

`[VERIFIED: local docker experiment, /proc/<lighttpd>/fd under docker exec --privileged]`, with lighttpd as a
`producer-for` a root consumer and `accesslog.filename = "/dev/stdout"`:

```text
0 -> /dev/null
1 -> /dev/null              # lighttpd replaced stdout
2 -> pipe:[91817491]
4 -> /dev/null              # the "/dev/stdout" access log
```

The consumer ran as uid 0, but no access record ever arrived, not even after 67 s.

### Finding 4: format and query handling

`[VERIFIED: local docker experiment]`. `accesslog.format = "%m %U %>s"` gives method, the **rewritten** path without
the query, and the final status. The query-form store URL is normalised by the existing `url.rewrite-once` rules before
`%U`:

```text
GET /repo/o/r/0123456789abcdef0123456789abcdef/info/refs 200|GET /repo/o/r/0123…?ref=main&tab=readme/info/refs&service=git-upload-pack HTTP/1.1
POST /repo/o/r/0123456789abcdef0123456789abcdef/git-upload-pack 200|POST /repo/o/r/0123…?ref=main&tab=readme/git-upload-pack HTTP/1.1
GET /__not_found 404            # "/" and other paths outside /repo/ after the Phase 1 rewrite
GET /repo/o/r/0123456789abcdef0123456789abcdef%0A/git-upload-pack 400   # control characters stay escaped
```

(The first two lines come from a run with `%m %U %>s|%r|%q`; the part after `|` shows the raw request line that
`%r`/`%q` would leak. Do not use `%r`, `%q` or `%h`.)

Every record contains the hash, including 404 probes, so the record must never reach a file or a log.

### Finding 5: the additive config form is valid

`[VERIFIED: local docker experiment]`: three lines appended to the unchanged Phase 1
`rootfs/etc/lighttpd/marketplace-repo-proxy.conf` pass `lighttpd -tt` (`config ok`) and log as expected. Use
`server.modules +=` on a new line so the existing `server.modules = (...)` line stays untouched (D-24).

### Recommended mechanism (prototype verified end to end)

```text
lighttpd (uid lighttpd)
   │  accesslog record "%m %U %>s" (non-blocking pipe; lighttpd holds the read end)
   ▼
fetchsink.py  (piped logger, uid lighttpd, python3 -I, stdlib only, prints nothing)
   │  keeps only ^POST /repo/<owner>/<repo>/<32hex>/git-upload-pack 200$
   │  sendto() datagram "owner repo hash" (non-blocking; dropped if the receiver is down)
   ▼
/run/mrp-fetch/fetch.sock   AF_UNIX SOCK_DGRAM, dir root:lighttpd 0710, socket root:lighttpd 0620
   ▼
fetchlog (s6 longrun, root, plain #!/bin/sh)
   │  validates the datagram, maps hash → (repository, user) via a non-destructive locked read
   │  of /data/access.json (cached on the file signature)
   ├─► /data/last-fetch.json   (single writer, atomic replace, 0600, schema 1, no hash)
   └─► add-on log: "fetch: <user> → <owner>/<repo>"  (throttled, never the hash)
```

Prototype result `[VERIFIED: local docker experiment exp4]`:

```text
srw--w----    1 root     lighttpd         0 Nov 18 18:56 fetch.sock
   46     1 root     python3 -u /opt/receiver.py
   51    49 lighttpd /usr/bin/python3 -I /opt/fetchsink.py
=== sample datagram
1795028214 o r 0123456789abcdef0123456789abcdef
=== receiver down
ok                     (git still served)
  datagrams: 0
=== receiver up again (no lighttpd/forwarder restart)
ok
  datagrams: 1
=== can a non-lighttpd unprivileged user send? (nobody)
PermissionError: [Errno 13] Permission denied
=== can lighttpd read the dir listing?
ls: can't open '/run/mrp-fetch': Permission denied
```

Design rules for the plan:

- **Forwarder** (`app/fetchsink.py`):
    - stdlib only (`os`, `re`, `socket`, `sys`), run as
      `accesslog.filename = "|exec /usr/bin/python3 -I /opt/marketplace-repo-proxy/app/fetchsink.py"`.
    - With `-I` it gets no extra entries on `sys.path`, so it must not import `app.*`.
    - It prints nothing (not even errors that could carry a line) and catches every exception per line.
    - Unknown or revoked hashes never get here: lighttpd answers them with 404, and the forwarder keeps only 200s.
      That settles the discretion item "no line for an unknown hash".
- **Channel:**
    - `fetchlog` creates `/run/mrp-fetch` (mkdir, `chown root:lighttpd`, `chmod 0710`) at start.
    - It unlinks a stale socket and binds under `umask 0o177`, then sets `chown 0:<gid of lighttpd>` and `chmod 0o620`.
    - Use a new directory, never `/run/marketplace-repo-proxy` (0700, holds `access.lock` and `sync.request`).
- **Receiver input is untrusted.** The CGI `git http-backend` also runs as `lighttpd` and could send datagrams. Accept
  only `^([A-Za-z0-9._-]+) ([A-Za-z0-9._-]+) ([0-9a-f]{32})$` (`recv(256)`) and drop everything else silently. Impact
  of forged records: wrong "last fetch" display only (integrity of a display field, accept and document).
- **Mapping:**
    - Rebuild the hash → (stored repository, user) map when `os.stat(access.json)` (inode, mtime_ns, size) differs
      from the last build. Stat once per datagram.
    - Read with the non-destructive helper (Pattern 2), never `AccessStore.load()`.
    - Accept only entries whose repository matches `owner/repo` case-insensitively.
- **Persistence and log (discretion recommendation):**
    - Keep the last fetch per `(repository.lower(), user)` in memory.
    - Write `/data/last-fetch.json` and log the `fetch:` line only when a pair's value advanced by at least 60 s since
      its last persisted value, so one clone (2-3 POSTs) or one Supervisor pull (`ls-remote` + `fetch`, 3 POSTs) gives
      one line.
    - Flush on SIGTERM.
    - On startup, read the existing file without renaming it if it is invalid: start empty and overwrite at the next
      write.
    - Prune entries whose (repository, user) no longer exists in `access.json` at each write.
    - Log at `info`.
- **Startup order:** no change to the `lighttpd` service. Datagrams sent before `fetchlog` binds are dropped
  (best-effort field).

### `/data/last-fetch.json` contract (proposal for DOCS.md "Contracts")

> Adopted as D-21 (user decision 2026-11-18, option-a): name and layout below are fixed.

```json
{
  "schema": 1,
  "updated": "2026-11-18T12:00:00Z",
  "entries": [
    { "repository": "example-org/private-addons", "user": "alice", "last_fetch": "2026-11-18T11:59:30Z" }
  ]
}
```

- **Single writer:** `fetchlog`, through `app.jsonio.atomic_write_json` (mode 0600, fsync, rename, directory fsync).
  Readers (GUI) need no lock.
- **No hash, ever.** Keyed by (repository, user) as stored in `access.json`.
- **Display rule** (server-side, in the GUI service): a user's `last_fetch` is reported only when it is strictly
  greater than the entry's `created`. Rotation (which resets `created`, see Pattern 3) and re-creation of a label
  therefore show "never" until the new hash is used. This answers the discretion item "does last fetch survive a
  rotation": the record survives, the display does not.
- **Path:** define it in the new module as `paths.data_dir / "last-fetch.json"`. Do not add a field to the frozen
  `Paths` dataclass in `app/paths.py`; Phase 2 may edit that file (D-24).

## What counts as a fetch (discretion item, MRP-15)

`[VERIFIED: local docker experiment exp4]`, git 2.54.1 client against the Phase 1 lighttpd config. The table counts
datagrams, i.e. `POST git-upload-pack` answered 200:

| Operation | Protocol v2 (git default since 2.26) | Protocol v0 |
|-----------|--------------------------------------|-------------|
| `clone --depth 1` | 2 | 2 |
| `ls-remote --heads` | **1** | 0 (GET `info/refs` only) |
| `fetch --update-shallow --depth 1` (no change) | 2 | 2 |
| `curl .../info/refs?service=git-upload-pack` | 0 | 0 |
| clone with an unknown hash | 0 | 0 |

With protocol v2, `ls-remote` also POSTs (`command=ls-refs`), so "POST = fetch" cannot separate `ls-remote` from a real
fetch. The access log has neither the request body nor a reliable size signal.

The Supervisor's update runs `ls-remote --heads` and then `fetch --update-shallow --depth 1` (SPIKE, Supervisor source
findings), so every Supervisor pull produces POSTs anyway. That the Supervisor uses protocol v2 is `[ASSUMED]`: its git
is a current Alpine git (SPIKE: git 2.54), and v2 is the default.

**Recommendation:** "last fetch" = time of the last `POST …/git-upload-pack` answered **200** with that user's hash.
Document it as "last successful git access (clone, fetch or, with protocol v2, ref listing)". Excluded:

- bare `info/refs` probes (curl, dumb clients, the v0 `ls-remote` handshake);
- every non-200 answer.

## Architecture Patterns

### System Architecture Diagram

```text
                 HA frontend (browser, behind HA login)
                              │ ingress session
                              ▼
     Supervisor ingress proxy (peer 172.30.32.2, sets X-Ingress-Path)
                              │ :8099 (never published)
                              ▼
┌───────────────────────── gui (s6 longrun, root, #!/bin/sh, no PAT, no SUPERVISOR_TOKEN) ─────────────────────────┐
│ skeleton gate (R-01) ─► static (index, views, vendor lib)                                                          │
│                     └─► Router api/*                                                                               │
│                           ├─ GET  overview ──► options (no token) + read_status(/data/status.json)                 │
│                           │                    + registration.read_registration() → None (D-19)                    │
│                           ├─ POST sync ──────► atomic_write_json(/run/marketplace-repo-proxy/sync.request, {})     │
│                           ├─ GET  access ────► non-destructive locked read of access.json + /data/last-fetch.json  │
│                           ├─ POST access/{o}/{r} (add) ─────────┐                                                  │
│                           ├─ GET  access/{o}/{r}/{u}/urls ──────┤  AccessStore (flock /run/.../access.lock)        │
│                           ├─ DELETE access/{o}/{r}/{u} (revoke) ┤  ─► /data/access.json + /srv/git/access symlinks │
│                           └─ POST access/{o}/{r}/{u}/rotate ────┘                                                  │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
        ▲ status.json (writer: sync)       ▲ sync.request (consumer: sync)      ▲ access.json (also CLI, access-watch)
        │                                  │                                    │
   sync (with-contenv, PAT)          access-watch (1 s reconcile)          fetchlog (root) ─► /data/last-fetch.json
                                                                              ▲ datagram "owner repo hash"
   Supervisor / git client ──:8080──► lighttpd (uid lighttpd) ──pipe──► fetchsink (uid lighttpd)
                                         └─ git http-backend (CGI, uid lighttpd) ─► /srv/git/access/<o>/<r>/<hash>
```

### Recommended Project Structure

```text
marketplace-repo-proxy/
├── app/
│   ├── gui.py                    # entry: python3 -m app.gui (s6 longrun gui)
│   ├── fetchlog.py               # entry: python3 -m app.fetchlog (s6 longrun fetchlog, root)
│   ├── fetchsink.py              # piped access logger, runs as lighttpd, stdlib only, no app.* imports
│   └── web/
│       ├── __init__.py           # NEW (make sync-admin-ui does not create it)
│       ├── admin_ui/             # skeleton copy + LIB.stamp (make sync-admin-ui only)
│       ├── server.py             # build_router(...) + make_server(...) wrapper, error mapping
│       ├── service.py            # GUI service layer: token-free options, access read/add/revoke/rotate, overview, trigger
│       ├── registration.py       # D-19: read_registration(paths) -> None
│       └── static/
│           ├── index.html  app.css  app.mjs  model.mjs  strings.de.mjs  strings.en.mjs
│           ├── views/repositories.mjs  views/access.mjs  views/info.mjs
│           └── vendor/admin-ui/  # lib copy + LIB.stamp (make sync-admin-ui only)
├── rootfs/etc/s6-overlay/s6-rc.d/{gui,fetchlog}/{type,run,finish,dependencies.d/init}
├── rootfs/etc/s6-overlay/user-bundles.d/user/contents.d/{gui,fetchlog}
├── rootfs/etc/lighttpd/marketplace-repo-proxy.conf     # + 3 appended lines only
└── tests/ test_gui_server.py test_gui_service.py test_gui_manifest.py test_fetchsink.py test_fetchlog.py
           test_js.py  js/{fakedom,a11y_audit}.mjs  js/{i18n,model,views}.test.mjs
```

Module and service names other than `gui` are at Claude's discretion; the names above are a recommendation.

### Pattern 1: GUI process with a token-free options copy (D-07, D-08)

**What:** the GUI loads options once at start and keeps an `Options` copy whose `github_token` is `""`. `store_urls`
takes an `Options` and reads only `public_url`, so D-08 is met with the same function the CLI uses.

`[VERIFIED: marketplace-repo-proxy/app/options.py:41-48]`:

```python
class Options:
    github_token: str = field(default="", repr=False)
    ...
    public_url: str = ""
    repositories: tuple[RepoSpec, ...] = ()
    ...
    log_level: str = "info"
```

`[VERIFIED: app/urls.py:26]` `def store_urls(options: Options, hostname: str, owner: str, name: str, hash_: str) -> dict[str, str]:`

`[VERIFIED: app/cli.py:181]` `hostname = hostname or socket.gethostname()`

`[VERIFIED: app/watch.py:89-91]` (precedent):

```python
    # keep only what this service needs; the credential is not used here
    specs, log_level = options.repositories, options.log_level
    del options
```

```python
# app/web/service.py (sketch)
import dataclasses, socket
from app.options import Options, load_options
from app.paths import Paths

@dataclasses.dataclass(frozen=True)
class GuiConfig:
    options: Options      # github_token is always "" here
    hostname: str

def load_gui_config(paths: Paths, hostname: str | None = None) -> GuiConfig:
    options = load_options(paths.options_file)          # OptionsError -> log + exit 1 (s6 restarts after finish)
    safe = dataclasses.replace(options, github_token="")
    del options
    return GuiConfig(safe, hostname or socket.gethostname())
```

`gui/run`, modelled on `access-watch/run` `[VERIFIED: rootfs/etc/s6-overlay/s6-rc.d/access-watch/run]`:

```sh
#!/bin/sh
# Deliberately NOT with-contenv: the GUI holds no PAT and no SUPERVISOR_TOKEN (D-07)
cd /opt/marketplace-repo-proxy || exit 1
exec env PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 python3 -m app.gui
```

`finish` = `sleep 3`, like `access-watch` (a GUI crash must not halt the container; git serving continues).

There is no ingress-remote environment override in production: a plain `#!/bin/sh` service does not see `docker -e`
variables. The verify script uses a real `172.30.32.2` peer instead (see "Verify script design").

### Pattern 2: non-destructive locked read for the GUI and fetchlog (WR-04)

**Question:** do frequent GUI reads raise the WR-04 risk?

**Answer: yes, if they use `AccessStore.list_entries()`/`get()`.** Both go through `load()`, which treats any
`OSError` or `ValueError` as corruption and renames the file.

`[VERIFIED: app/access.py:106-125]`:

```python
    def load(self) -> dict[str, Any]:
        ...
        try:
            doc = read_json(path)
        except (OSError, ValueError):
            doc = False  # marker: present but unreadable or invalid
        ...
        self.log.error("access.json is corrupt; moved to access.json.corrupt, starting with no users")
        try:
            os.replace(path, path.with_name(path.name + ".corrupt"))
```

- **Normal operation is safe.** Every writer holds the flock and replaces atomically, so a lock-holding reader never
  sees a partial file.
- **Two cases add exposure, both proportional to the read rate:**
    - a hand edit written in place (non-atomic, against the DOCS advice);
    - a transient `OSError` such as EMFILE in a busy threaded server, or EIO.
- **Consequence:** every URL stops working (fail closed) and an earlier `.corrupt` is overwritten.
- **Comparison:** `access-watch` reads only on a signature change. A GUI polling every few seconds and `fetchlog` mapping
  every fetch would multiply the reads.

**Mitigation (no change to `app/access.py`):** read paths use their own helper that holds the same lock but never renames:

```python
# app/web/service.py (sketch) — composition of AccessStore.locked() and jsonio.read_json
from app.access import AccessStore
from app.jsonio import read_json

class AccessUnavailable(Exception):
    """access.json is unreadable, invalid or has a newer schema; never renamed from a read path."""

def read_entries_safe(store: AccessStore) -> list[dict]:
    with store.locked():
        try:
            doc = read_json(store.paths.access_file)
        except (OSError, ValueError):
            raise AccessUnavailable() from None
    if doc is None:
        return []
    if not (isinstance(doc, dict) and isinstance(doc.get("schema"), int) and not isinstance(doc.get("schema"), bool)
            and isinstance(doc.get("entries"), list) and all(isinstance(e, dict) for e in doc["entries"])):
        raise AccessUnavailable()
    if doc["schema"] > 1:
        raise AccessUnavailable()
    return doc["entries"]
```

- Map `AccessUnavailable` to the API error `access_unavailable` (503) and show a clear state in the view. Let
  `access-watch` do the fail-closed handling, as today.
- **Before every write, check inside the same `store.locked()`:** call `read_entries_safe` first (the lock is
  reentrant per thread), then `store.add`/`store.revoke`.
- Without that check, a GUI add on an unreadable file would rename it and write a file holding only the new user.

`[VERIFIED: app/access.py:84-104]` the lock is reentrant per thread (`_HELD.depth`), and nested `locked()` calls do
not flock a second fd.

### Pattern 3: rotate = revoke + add in one lock (D-10, D-11)

```python
# app/web/service.py (sketch)
from app.access import HASH_RE, RESERVED_USERS, SOURCES, USER_RE, AccessError, AccessStore

def rotate(store, cfg, repository_slug, user, confirm):
    spec = cfg.options.find(repository_slug)
    if spec is None:
        raise AccessError("repository_unknown")
    if confirm != user:                                   # exact, like confirmMatches in the lib
        raise ApiError("confirmation_required", "type the user label to confirm")
    with store.locked():
        entries = read_entries_safe(store)                # Pattern 2: no rename, refuse on unreadable file
        entry = store.get(spec.slug, user)                # reentrant
        if entry is None:
            raise AccessError("user_unknown")
        source = entry.get("source")
        if source == "system" or user.lower() in RESERVED_USERS:
            raise ApiError("protected", "system users are managed by the add-on")   # D-13
        if source not in SOURCES or not USER_RE.fullmatch(user):
            raise AccessError("invalid_user")             # validate BEFORE revoke: add() must not fail afterwards
        old_hash = entry.get("hash")
        store.revoke(spec.slug, user, specs=cfg.options.repositories)
        try:
            new = store.add(spec.slug, user, source=source, specs=cfg.options.repositories)
        except Exception:
            if isinstance(old_hash, str) and HASH_RE.fullmatch(old_hash):   # compensate: restore the old access
                store.add(spec.slug, user, source=source, hash_=old_hash, specs=cfg.options.repositories)
            raise
    return new
```

Quoted values `[VERIFIED: app/access.py:29-32]`:

```python
HASH_RE = re.compile(r"^[0-9a-f]{32}$")
USER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SOURCES = ("gui", "api", "system", "cli")
RESERVED_USERS = frozenset({"local"})  # Phase 2's system user; only source "system" may use these labels
```

**Atomicity, answered with evidence** `[VERIFIED: local probe against the real app/access.py]`:

- One process rotated `alice` 200 times inside `store.locked()`.
- A second process read `list_entries()` in a tight loop. It saw exactly one user set, `[('alice', 'bob')]`, i.e.
  `alice` was never missing.
- Afterwards only the new link existed (`old link present: False | new link present: True | links: 2`), the source was
  kept (`gui`) and `created` was reset.

| Property | Result |
|----------|--------|
| Lock-holding readers (CLI, GUI, access-watch's reconcile, fetchlog) | Never see the intermediate file (flock) |
| access-watch | Its unlocked stat poll may fire between the two writes; its `reconcile()` then blocks on the lock and sees the final state |
| git clients (lighttpd, no lock) | Old link removed by `revoke`, new one created by `add`'s reconcile; never both valid. The new URL is unknown to anyone until the response is sent, so "works at once" holds |
| Crash between the two writes | User missing (fail closed); recoverable by re-adding. **Not crash-atomic**: document |
| `created` | Reset to the rotation time. Matches the documented CLI rotation (revoke + add); use it for the last-fetch display rule |
| Unknown fields of that one entry | Lost (revoke removes the entry, add writes known fields only). Unknown top-level keys survive. Document |
| `rotated` field | Not written (`add` cannot). Not needed, because `created` carries the meaning |

**Alternative** (not recommended, but named for the plan-checker): an in-place hash swap with `store.load()`,
`atomic_write_json` and `reconcile_tree` under `locked()` is crash-atomic and keeps the fields. It is a second writer
code path outside `access.py`, which D-09 forbids in spirit. As an additive `rotate()` at the end of `access.py`, it
would collide textually with Phase 2's likely rotate addition (Q-4: both append at the end of the file). Keep it out.

### Pattern 4: Repositories overview (MRP-13, D-17)

- The source of truth for *which* repositories exist is the options (`cfg.options.repositories`, in options order).
  `status.json` only adds state.
- `read_status(paths)` returns `None` when the file is missing, unreadable or not an object. Map that to `status: null`
  per repository and `status_available: false`, so the view says "no status yet" (D-17).
- Status codes `[VERIFIED: app/status.py:18]`:
  `STATUS_CODES = ("pending", "ok", "auth_failed", "not_found", "no_repository_yaml", "fetch_failed")`.
  The view maps them through a literal table to string keys (R-06: no dynamic keys).
- Include `now_ms` from the server clock (haos-monitor pattern) and convert ISO timestamps with `Date.parse`. Show them
  with `formatRelative(ms, lang, nowMs)` (R-07) so client clock skew does not matter.

### Pattern 5: "Sync now" (D-18)

`[VERIFIED: app/cli.py:138-145]` the Phase 1 trigger:

```python
def _sync(paths: Paths) -> int:
    """Create the D-12 trigger file; the sync service starts a full cycle within about a second."""
    if not paths.run_dir.is_dir():
        paths.run_dir.mkdir(parents=True, exist_ok=True)
        paths.run_dir.chmod(0o700)
    atomic_write_json(paths.trigger_file, {})
```

`[VERIFIED: app/paths.py:37]` `trigger_file=run_dir / "sync.request"`; `[VERIFIED: app/paths.py:45]`
`Path("/data"), Path("/srv/git"), Path("/run/marketplace-repo-proxy"), Path("/etc/gitconfig")`.

- Re-implement those three lines in the service. Do not call `cli._sync`, which prints to stdout.
- `POST api/sync` returns 202 `{"requested": true}`.
- The overview adds `sync.requested = paths.trigger_file.exists()`. The sync service polls once per second and unlinks
  the file when the cycle starts (`app/sync.py` `run_cycle_once`). The view can therefore show "requested" → "running"
  (`sync.state`) → result.
- Poll every 2 s while `requested` or `running`, every 15 s otherwise. `usePoll(fn, ms)` re-arms on an `ms` change:
  `[VERIFIED: admin-ui/app/web/static/lib/hooks.mjs:26-36]`, deps `[ms]`.
- **CSRF hardening:** require a JSON object body (`{}`) on `POST api/sync`. The skeleton only parses a body with
  `Content-Type: application/json` (`server.py` `_read_body`), which forces a CORS preflight for cross-origin callers.
  A body-less POST would bypass that `[ASSUMED: HA's ingress cookie policy is not verified here]`.

### Pattern 6: registration slot (D-19)

> **Superseded in part by amended D-19 (user decision 2026-11-18):** `read_registration` reads `/data/supervisor.json`
> (states `registered`, `missing`, `leftover`, `error`) instead of returning None; the assumed field layout is stated in
> Plan 03-01. The normalised shape and the view rule below still apply.

```python
# app/web/registration.py — the ONLY place that will change when Phase 2 lands
"""Registration status of each repository in the local add-on store (Phase 2 data); no data in Phase 3."""
from __future__ import annotations
from app.paths import Paths

def read_registration(paths: Paths) -> dict[str, dict] | None:
    """Map of repository.lower() -> {"state": ..., ...}, or None when no registration data exists."""
    return None
```

- The overview sets `registration: None` per repository when the reader returns `None` or lacks the key.
- The view renders the column or badge only when at least one repository has a non-null value.
- **Fix the shape now** (the view needs literal string keys, R-06): `{"state": "registered" | "missing" | "leftover" |
  "error"}` plus an optional `detail` text. The Phase 2 follow-up then maps its data into this shape inside
  `read_registration` only. This is an `[ASSUMED]` vocabulary: confirm with the Phase 2 owner (see Open Questions).
- Tests monkeypatch `read_registration` to prove both render paths.

### Pattern 7: views, navigation, strings

- **Shell:**
    - `Topbar` with `views`, `activeId` and `nav="topbar"`, plus `useHashRoute`. Three views: `repositories`
      (default), `access`, `info`.
    - No `icon.png` exists in the add-on, so pass `iconSrc={null}` and avoid a Dockerfile change.
    - ~~No `version`~~ superseded by D-30: the version comes from the build argument `BUILD_VERSION` written into the
      image (Plan 03-01), not from the Supervisor, so the GUI still holds no token (D-07).
    - No `infoPath`: it needs the Supervisor slug.
- **Access view:**
    - One card per configured repository, a `DataTable` of users (label, source `Badge`, created, last fetch), and an
      add form (`Field` + label input).
    - Per-row actions:
        - "Show URLs" fetches `api/access/{o}/{r}/{u}/urls` on demand and renders one `CopyField` per URL (internal,
          public if set).
        - "Rotate" and "Revoke" open a `ConfirmDialog` with `expected={user}` and `danger`.
    - `system` rows show no actions (D-13).
    - Entries of unconfigured repositories go in an "inactive" group with revoke only. The CLI also revokes unconfigured
      ones.
    - The add response returns the URLs once; show them right away.
- **Rotate dialog text** (D-12) must state:
    - the consuming Supervisor sees a new repository;
    - add-ons installed from the old URL must be reinstalled, after backing up their data;
    - the old URL stops working immediately.
- **Strings:**
    - Namespace `mrp.*` for the add-on, `errors.<code>` for the add-on error codes.
    - Do not redefine lib keys (`errors.confirmation_required`, `errors.protected` and `errors.not_found` exist in
      the lib). Pattern: haos-monitor's `i18n.test.mjs` "no key collision" test.
- **Info view:** static `t()` paragraphs and lists only (D-23), no API call.

### API routes (discretion recommendation)

Patterns are registered with a leading slash, as in haos-monitor (`router.add("GET", "/api/overview", ...)`). The client
uses `get("overview")` because `buildUrl` prefixes `api/` and encodes each segment
(`[VERIFIED: admin-ui/app/web/static/lib/api.mjs:15-19]`).

| Method | Path | Body | Result |
|--------|------|------|--------|
| GET | `/api/overview` | — | `{now_ms, status_available, sync:{state,last_started,last_finished,next_due,interval_minutes,reason,requested}, repositories:[{repository,branch,branch_source,status,message,last_attempt,last_success,last_change,head,addons,registration}]}` |
| POST | `/api/sync` | `{}` | 202 `{requested: true}` |
| GET | `/api/access` | — | `{now_ms, repositories:[{repository, active, users:[{user, source, created, last_fetch, protected}]}]}`. **No hash, no URL** |
| POST | `/api/access/{owner}/{repo}` | `{user}` | 201 `{user, source, created, urls:{internal, public?}}` |
| GET | `/api/access/{owner}/{repo}/{user}/urls` | — | `{internal, public?}` |
| DELETE | `/api/access/{owner}/{repo}/{user}` | `{confirm}` | 204 |
| POST | `/api/access/{owner}/{repo}/{user}/rotate` | `{confirm}` | 200 `{urls:{internal, public?}}` |

Router params are unquoted per segment. A `%2F` in `owner` becomes `a/b`, which can never equal a configured key in
`options.find`: safe. Revoke accepts unconfigured repositories, like the CLI (`cli.py:131`); add and rotate require
`options.find(...)`.

### Error codes (D-15; register with `register_error_code` at import, haos-monitor pattern)

| Code | HTTP | Source |
|------|------|--------|
| `repository_unknown` | 404 | Phase 1 AccessError / not configured |
| `user_unknown` | 404 | Phase 1 / revoke returned False |
| `user_exists` | 409 | Phase 1 AccessError |
| `hash_conflict` | 409 | Phase 1 AccessError (not reachable from the GUI, which never sends a hash; map it anyway) |
| `invalid_user` | 400 | Phase 1 AccessError |
| `user_reserved` | 400 | Phase 1 AccessError (`local` with a non-system source) |
| `confirmation_required` | 400 | skeleton, already in `ERROR_STATUS` `[VERIFIED: admin-ui/app/web/skeleton/errors.py:9]` |
| `protected` | 409 | skeleton code `[VERIFIED: errors.py:14]`, reused for system users (D-13) |
| `access_unavailable` | 503 | new: Pattern 2 |

Map `AccessError` through `make_server(..., error_mappers={AccessError: ...})` (ntfy pattern, `ntfy/app/web/server.py`).
Never put an exception message into the response.

### Anti-Patterns to Avoid

- **Calling `AccessStore.list_entries()` on every poll.** It raises the WR-04 exposure (Pattern 2).
- **Returning store URLs in the list endpoint.** The poll response would carry every capability; serve them on demand.
- **Logging the request, the URL or `X-Remote-User-*`.** The skeleton already silences `log_message`; GUI action logs
  name repository and user only.
- **A test hook for the ingress remote in `gui/run`.** It would need `with-contenv` or reading
  `/run/s6/container_environment`, against D-07. Use the network trick instead.
- **Editing `server.modules = (...)`, `lighttpd/run`, `app/access.py`, `app/paths.py` or `app/init.py`.** D-24; none
  of them needs a change.
- **Using `%r`, `%q`, `%h` or `%{...}i` in `accesslog.format`.** They leak the query or client data; `%U` is already
  normalised (Finding 4).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ingress gate, static whitelist, headers, JSON errors | Own HTTP handler | `app.web.admin_ui.make_server` + `Router` | R-01 edge cases (raw path, HEAD/OPTIONS, header views) are already tested in the skeleton |
| Type-to-confirm | Own dialog | `ConfirmDialog expected=` (exact match: `confirmMatches = (typed, expected) => typeof typed === "string" && typed === expected` `[VERIFIED: lib/ui.mjs:152]`) | R-04, focus trap, a11y |
| Copy URL | Clipboard code | `CopyField` | iframe clipboard fallback |
| Relative times | `toLocale*` | `formatRelative(ms, lang, nowMs)` | R-07 |
| access.json writes | Own JSON writer | `AccessStore.add/revoke` | D-09 |
| Atomic JSON file | `open(...).write` | `app.jsonio.atomic_write_json` (mode 0600, fsync, rename, directory fsync: `os.fchmod(handle.fileno(), 0o600)` `[VERIFIED: app/jsonio.py:18]`) | Contract rule for every `/data` file |
| Hash masking in logs | Own regex | `app.logsetup.setup_logging` (`HASH_TOKEN_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])")` `[VERIFIED: app/logsetup.py:13]`) | Defence in depth |
| Store URLs | String formatting | `app.urls.store_urls` | D-08 |

**Key insight:** every hard part of this phase (gate, confirm, atomic writes, locking, masking) already exists and is
tested. The new code is composition plus two small programs (forwarder, receiver).

## Common Pitfalls

### Pitfall 1: hash leak through skeleton tracebacks

- **What goes wrong:** the skeleton prints the full traceback of an unexpected exception with `print`, bypassing the
  logging redactor (`print(traceback.format_exc(), flush=True)` `[VERIFIED: admin-ui/app/web/skeleton/server.py:129]`).
- **Why:** an `OSError` from the symlink tree carries the path, and the path contains the hash, e.g.
  `PermissionError: ... '/srv/git/access/o/r/<hash>'`.
- **How to avoid:**
    - Map `OSError` (and `AccessError`) through `error_mappers`, which suppresses the traceback, and log only
      `type(exc).__name__` (watch.py precedent).
    - In `app/gui.py`, also wrap `sys.stdout` with a writer that applies `app.logsetup.mask_hashes` before
      `setup_logging`.
- **Warning sign:** a pytest that forces an `OSError` in the service and greps captured stdout for 32 hex characters.

### Pitfall 2: GUI add on an unreadable file wipes the other users

- **What goes wrong:** `AccessStore.add` calls `load()`, which renames the corrupt file and starts empty. The new file
  then holds only the new user.
- **How to avoid:** use the Pattern 2 check inside the same lock before every write.

### Pitfall 3: rotate fails half way

- **What goes wrong:** `add()` raises after `revoke()` has written, for example on an invalid stored `source` or a full
  disk. The user is lost.
- **How to avoid:** pre-validate before `revoke`, and re-add with the old hash on failure (Pattern 3).

### Pitfall 4: confirm phrase compared loosely

- **What goes wrong:** the server compares case-insensitively or trims, while the lib compares exactly.
- **How to avoid:** compare with exact `==` on the server.
- **Edge case:** user labels are case-sensitive per contract (`_matches` compares the user exactly).

### Pitfall 5: `test-admin-ui-consumers` does not discover consumers

- **What goes wrong:** `admin-ui/DOCS.md` says new consumers "are discovered automatically", but that holds for sync
  and check only. The test target is a hard-coded list.
- **Evidence** `[VERIFIED: Makefile:128-133]`:

  ```text
  test-admin-ui-consumers: ## Test each consumer separately (their Python app packages share a name)
  	node --test coding-assistants/tests/*.test.mjs
  	python3 -m unittest discover -s coding-assistants/tests -p 'test_*.py'
  	uv run --with pytest --with pyyaml python3 -m pytest ntfy/tests -q
  	uv run --with pytest --with pyyaml --with jinja2 python3 -m pytest secrets-sync/tests/web -q
  	uv run --with pytest --with pyyaml python3 -m pytest haos-monitor/tests -q
  ```

- **How to avoid** (needed for D-05 "`make release-admin-ui-lib` tests it with the other consumers"):
    - Append `uv run --with pytest --with pyyaml python3 -m pytest marketplace-repo-proxy/tests -q`.
    - Add `tests/test_js.py`, which runs the node tests from pytest and skips without node (haos-monitor pattern), so
      the pytest line covers the node tests too.
    - Run each consumer in its own Python process: the package name `app` is shared.

### Pitfall 6: `app/web/__init__.py` missing

- **What goes wrong:** `make sync-admin-ui` creates only `app/web/admin_ui/` and `app/web/static/vendor/admin-ui/`
  (`[VERIFIED: internal/sync-admin-ui.py:35-36]` `LIB_DST = Path("app/web/static/vendor/admin-ui")`,
  `SKELETON_DST = Path("app/web/admin_ui")`).
- **How to avoid:** the plan creates `app/web/__init__.py` itself.

### Pitfall 7: zizmor line anchors in `lint.yml`

- **What goes wrong:** zizmor deferrals are line-anchored (`lint.yml:1:1`, `16:3`, `22:9`, `58:11`, `160:3`); moving a
  line above them breaks them.
- **Evidence:** the `marketplace-repo-proxy` job starts at line 297
  (`[VERIFIED: zizmor.yml, .github/workflows/lint.yml:296-317]`).
- **How to avoid:** add the new steps inside that job, after line 297. Nothing above line 160 moves.

### Pitfall 8: forwarder imports `app.*` or prints

- **What goes wrong:** under `python3 -I <file>` the package is not importable, and any print reaches lighttpd's
  stderr or the container log.
- **How to avoid:** stdlib only and no output. Test it with a subprocess run of the real file under `-I`, feeding lines
  and asserting empty stdout and stderr.
- **Observed:** in the prototype, the forwarder's own stderr writes did not show up in lighttpd's stderr capture. The
  target is unconfirmed, so do not rely on it.

### Pitfall 9: auto-assigned container IP equals the ingress address

- **What goes wrong:** on a Docker network with subnet `172.30.32.0/23`, a container started **without** `--ip` got
  `172.30.32.2` (`[VERIFIED: local docker experiment]` `inet 172.30.32.2/23`). An "outside" client or the proxy itself
  would then pass the gate.
- **How to avoid:** create the network with `--ip-range 172.30.33.0/24`. Auto-assigned addresses then stay outside
  `172.30.32.x` (verified: `inet 172.30.33.0/23`), and only an explicit `--ip 172.30.32.2` gets the ingress address.

### Pitfall 10: `fetch:` log line spam and SD-card writes

- **What goes wrong:** each Supervisor pull makes 3 POSTs and each clone 2.
- **How to avoid:** use the 60 s per-pair rule for both the log line and the file write (see the sink section). Polls
  every 3 hours per consumer keep the write volume negligible.

## Code Examples

### Appended lighttpd lines (D-20, D-24)

```text
# Access log only into the fetch sink (never a file or the add-on log): method, rewritten path without query, status
server.modules += ("mod_accesslog")
accesslog.filename = "|exec /usr/bin/python3 -I /opt/marketplace-repo-proxy/app/fetchsink.py"
accesslog.format = "%m %U %>s"
```

`[VERIFIED: local docker experiment]`: `lighttpd -tt` passes with these lines appended to the unchanged Phase 1 config.
`/usr/bin/python3 -I <file>` ran as the piped logger (exp4 process list). The path
`/opt/marketplace-repo-proxy/app/` follows from `Dockerfile:10-11` (quoted above).

### Forwarder (shape verified in the prototype)

```python
"""Piped lighttpd access logger (runs as user lighttpd): forwards successful upload-pack POSTs to fetchlog.

Stdlib only and started with `python3 -I`, so it imports nothing from app.*. It never prints a line or a hash.
"""
import re, socket, sys

LINE = re.compile(r"^POST /repo/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)/([0-9a-f]{32})/git-upload-pack 200$")
SOCK = "/run/mrp-fetch/fetch.sock"

def main(stream=None, sock_path: str = SOCK) -> int:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.setblocking(False)
    for raw in (stream or sys.stdin.buffer):
        try:
            match = LINE.match(raw.decode("ascii", "replace").rstrip("\n"))
            if match:
                sock.sendto(" ".join(match.groups()).encode("ascii"), sock_path)
        except Exception:      # receiver down, buffer full, bad bytes: drop the record, say nothing
            continue
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### Receiver socket setup (verified prototype)

```python
import grp, os, socket
def bind_socket(path: str) -> socket.socket:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    gid = grp.getgrnam("lighttpd").gr_gid
    os.chown(os.path.dirname(path), 0, gid); os.chmod(os.path.dirname(path), 0o710)
    try: os.unlink(path)
    except FileNotFoundError: pass
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    old = os.umask(0o177)
    try: sock.bind(path)
    finally: os.umask(old)
    os.chown(path, 0, gid); os.chmod(path, 0o620)
    sock.settimeout(1.0)      # wake up for SIGTERM and periodic flushes
    return sock
```

`[VERIFIED: local docker run]` `id lighttpd` → `uid=100(lighttpd) gid=101(lighttpd)`. Resolve the gid by name and do
not hard-code it. In tests, inject the group lookup and skip the chown when not root.

### s6 service files (both new; pattern of access-watch)

```text
rootfs/etc/s6-overlay/s6-rc.d/fetchlog/type              longrun
rootfs/etc/s6-overlay/s6-rc.d/fetchlog/run               #!/bin/sh … exec env PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 python3 -m app.fetchlog
rootfs/etc/s6-overlay/s6-rc.d/fetchlog/finish            #!/bin/sh  sleep 3
rootfs/etc/s6-overlay/s6-rc.d/fetchlog/dependencies.d/init   (empty)
rootfs/etc/s6-overlay/user-bundles.d/user/contents.d/fetchlog (empty)
(same five files for gui)
```

The `run` and `finish` files need mode 0755 in git (the Phase 1 files are executable).

## Verify script design (`internal/verify-marketplace-repo-proxy-gui.sh`, D-25)

Reuse the structure of `internal/verify-marketplace-repo-proxy.sh` (helpers `yget`, `wait_for`, `field_of`, the
fixture image `FROM <proxy image>` + `lighttpd-mod_auth`, the upstream override env `MRP_TEST_UPSTREAM_BASE`, the
`SUPERVISOR_TOKEN` sentinel, needles in files, `/proc` scans with positive controls). Copy the needed parts; do not
source the Phase 1 script (Phase 2 edits it). Use one fixture repository.

**Distinct names**, so it can never clobber Phase 1 artefacts:

- prefix `MRP_GUI_VERIFY_PREFIX` (default `mrp-gui-verify`);
- images `marketplace-repo-proxy-gui-verify:local` and `marketplace-repo-proxy-gui-fixture:local`;
- the header comment: "never run in two worktrees at the same time".

**Ingress from a real peer, no production hook** (Pitfall 9):

```bash
docker network create --subnet 172.30.32.0/23 --ip-range 172.30.33.0/24 --gateway 172.30.32.1 "${NET}"
docker run -d --name "${INGRESS_CLIENT}" --network "${NET}" --ip 172.30.32.2 --entrypoint sh "${IMAGE_TAG}" -c 'exec sleep infinity'
docker run -d --name "${OUTSIDE_CLIENT}" --network "${NET}" --entrypoint sh "${IMAGE_TAG}" -c 'exec sleep infinity'
# GUI call: docker exec "${INGRESS_CLIENT}" curl -s -H 'X-Ingress-Path: /api/hassio_ingress/test' http://${PROXY}:8099/...
```

`172.30.32.2` is the skeleton's ingress peer (`INGRESS_REMOTE = "172.30.32.2"` `[VERIFIED:
admin-ui/app/web/skeleton/ingress.py:7]`), a fixed HA constant already in the repo, so D-27 is not affected. Before
creating the network, fail with a clear message if any existing Docker network overlaps `172.30.32.0/23`, for example on
a machine that runs a Supervisor `[ASSUMED: such a dev host would have the hassio network in that range]`.

**Checks** (one `✓`/`✗` line each):

1. **Static:**
    - `config.yaml` has `ingress: true`, `ingress_port: 8099`, and no `8099` under `ports`.
    - `gui/run` and `fetchlog/run` start with `#!/bin/sh` (no `with-contenv`).
    - The lighttpd config keeps `server.breakagelog = "/dev/null"`, has `accesslog.filename = "|…fetchsink.py"` and
      `accesslog.format = "%m %U %>s"`, and no `%r`/`%q`/`%h`.
2. **Gate:**
    - `OUTSIDE_CLIENT` with the header → 403 `ingress_only`.
    - `INGRESS_CLIENT` without the header → 403.
    - `docker exec PROXY curl 127.0.0.1:8099` with the header → 403.
    - `INGRESS_CLIENT` with the header → 200 for `/`, `/api/overview` and a static file.
    - `Cache-Control: no-store` on `api/`.
3. **Environments:**
    - `/proc/<gui>/environ` and `/proc/<fetchsink>/environ` hold neither the PAT nor the `SUPERVISOR_TOKEN` sentinel.
    - Positive control: the sentinel is found in `sync`'s environment (Phase 1 pattern, `docker exec --privileged`).
    - `ps` shows `fetchsink` as `lighttpd` and `fetchlog` as `root`.
    - `/run/mrp-fetch` is `710 root:lighttpd`, `fetch.sock` is `620 root:lighttpd`.
4. **Sync now:**
    - `POST api/sync` with `{}` → 202.
    - `status.json` `sync.reason` becomes `request` and `last_started` advances.
5. **Add:** `POST api/access/example-org/private-addons` with `{"user":"carol"}` → 201. The URL from the response
   clones from `OUTSIDE_CLIENT` (git port 8080 is not gated by ingress).
6. **Last fetch:**
    - Within about 5 s `/data/last-fetch.json` has `carol`, and `GET api/access` shows a non-null `last_fetch`.
    - `docker logs` contains `fetch: carol → example-org/private-addons`.
7. **Revoke:**
    - `DELETE` without or with a wrong `confirm` → 400 `confirmation_required`.
    - With `confirm: "carol"` → 204, then `info/refs` → 404.
8. **Rotate:**
    - The old URL → 404 and the new one → 200 at the next request.
    - `last_fetch` reads null right after the rotation (display rule) and is set after a clone with the new URL.
9. **System user:** a seeded `source: "system"` entry `local` answers `protected` for revoke and rotate.
10. **Hygiene:**
    - Needle files hold every full hash used. `docker logs` shows no needle and no 32-hex value after `/repo/` or
      `/access/`.
    - `/data/last-fetch.json` and every GUI list response hold no needle.
    - `access.json` mode is still 600 and `/data` still 700.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | verify script, local build | ✓ | 29.9.3 | — |
| `ghcr.io/home-assistant/amd64-base:3.24` | image | ✓ (local cache) | Alpine 3.24.3 | — |
| Node.js | node tests | ✓ | v22.23.5 | `test_js.py` skips without node; CI installs node 22 |
| uv / pytest | pytest | ✓ | pytest 9.1.1 via `uv run --with` | — |
| Python (host) | sync script, scanner | ✓ | 3.x (`python3 internal/sync-admin-ui.py --check` ran) | — |
| Network subnet `172.30.32.0/23` free on the Docker host | verify script | ✓ (no overlapping network found) | — | Script fails with a clear message |

**Missing dependencies with no fallback:** none.

## Validation Architecture

(`workflow.nyquist_validation` is `false` in `.planning/config.json`; this section is included because the phase brief
asks for it.)

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (CI pin) + `node --test` (Node 22) |
| Config file | none; `marketplace-repo-proxy/tests/conftest.py` puts the add-on dir on `sys.path` |
| Quick run command | `uv run --with pytest --with pyyaml python3 -m pytest marketplace-repo-proxy/tests -q -x` (Phase 1 suite: 222 tests in 4.49 s, measured) |
| Node run | `node --test marketplace-repo-proxy/tests/js/*.test.mjs` |
| Full suite command | the two above + `make check-admin-ui-sync check-admin-ui-rules` |
| Container proof | `bash internal/verify-marketplace-repo-proxy-gui.sh` (manual, never concurrent, not in CI) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MRP-12 | Every method/path without ingress → 403; no `public=True` route; gate with header from `127.0.0.1` override in tests | pytest | `pytest marketplace-repo-proxy/tests/test_gui_server.py -q` | ❌ Wave 0 |
| MRP-12 | `config.yaml`: `ingress: true`, `ingress_port: 8099`, 8099 not in `ports`; `gui/run` is `#!/bin/sh`; GUI config has `github_token == ""` | pytest | `pytest .../test_gui_manifest.py -q` | ❌ Wave 0 |
| MRP-12 | de/en key and placeholder parity, no lib-key collision, literal keys | node | `node --test .../js/i18n.test.mjs` | ❌ Wave 0 |
| MRP-12 | Rules scanner and copy drift | script | `make check-admin-ui-rules check-admin-ui-sync` | ✅ (scanner auto-discovers via `LIB.stamp`) |
| MRP-13 | Overview merges options + `status.json`; missing or invalid file → `status_available: false`; `now_ms` | pytest | `pytest .../test_gui_service.py -k overview` | ❌ Wave 0 |
| MRP-13 | `POST api/sync` writes `sync.request` with `{}` (0600, run dir 0700); body required | pytest | `pytest .../test_gui_server.py -k sync` | ❌ Wave 0 |
| MRP-13 | `registration` null by default; column hidden; shown when the reader is patched | pytest + node | `-k registration`; `views.test.mjs` | ❌ Wave 0 |
| MRP-14 | add (source `gui`), revoke/rotate confirm rules, system user `protected`, error codes and statuses, unreadable file → `access_unavailable` and **no rename** | pytest | `pytest .../test_gui_service.py -k access` | ❌ Wave 0 |
| MRP-14 | Rotate: concurrent reader process never sees the user missing; old link gone, new link present; compensation restores the old hash on a forced `add` failure | pytest | `-k rotate` (multiprocessing, like the research probe) | ❌ Wave 0 |
| MRP-14 | List response has no hash and no URL; the urls route returns internal (+ public when set) via `store_urls` | pytest | `-k urls` | ❌ Wave 0 |
| MRP-14 | Views: ConfirmDialog `expected` = label, rotate warning text, CopyField per URL, source badges, no actions for `system` | node | `node --test .../js/views.test.mjs` | ❌ Wave 0 |
| MRP-15 | Forwarder: only `POST … 200` forwarded; silent on every input; runs under `python3 -I` from its file | pytest | `pytest .../test_fetchsink.py -q` (real AF_UNIX socket in `tmp_path`) | ❌ Wave 0 |
| MRP-15 | fetchlog: datagram validation, signature-cached mapping, unknown hash → nothing, 60 s rule, `last-fetch.json` contract (0600, schema, no hash), log line format without hash, display rule `last_fetch > created` | pytest | `pytest .../test_fetchlog.py -q` | ❌ Wave 0 |
| MRP-15 | End to end: clone → last fetch + log line; no hash in logs | container | verify script steps 5-6 and 10 | ❌ Wave 0 |
| MRP-16 | Info view renders only `t()` strings, no API call | node | `views.test.mjs` | ❌ Wave 0 |
| D-07 | GUI env without PAT or `SUPERVISOR_TOKEN` | container | verify script step 3 | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** the pytest quick run plus `node --test` for touched front-end files.
- **Per wave merge:** full suite + `make check-admin-ui-sync check-admin-ui-rules`.
- **Phase gate:** full suite green, then the verify script once, plus a local `docker build` (CLAUDE.md), before
  `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `make sync-admin-ui ADDON=marketplace-repo-proxy`, plus a new `app/web/__init__.py`
- [ ] `tests/js/fakedom.mjs`, `tests/js/a11y_audit.mjs` (copies of the haos-monitor files)
- [ ] `tests/test_js.py` (node runner, skip without node, file list pinned like haos-monitor)
- [ ] `tests/conftest.py`: add the `serve` fixture, `Client` and `INGRESS` header (haos-monitor conftest pattern)
      without breaking the Phase 1 fixtures
- [ ] Makefile `test-admin-ui-consumers` line; CI job steps (setup-node, node tests, sync and rules checks)

## Security Domain

`security_enforcement` is absent from config, so it is treated as enabled. ASVS level 1, as in Phase 1.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (delegated) | HA login + ingress; skeleton gate on peer + `X-Ingress-Path` (R-01). No own auth |
| V3 Session Management | no | HA ingress session; no own session or cookie |
| V4 Access Control | yes | Gate on every method and path; no public route (D-03); system users read-only (D-13); `panel_admin` default `true` (`[CITED: contributors.home-assistant.io/apps/reference/configuration]` "`panel_admin` … `true` … only to administrators") |
| V5 Input Validation | yes | `parse_repository`/`options.find`, `USER_RE`, exact confirm compare, JSON-object bodies, strict datagram regex in fetchlog, forwarder regex |
| V6 Cryptography | yes (reuse) | `secrets.token_hex(16)` inside `AccessStore.add` (`new_hash`); nothing new |
| V7 Error handling and logging | yes | Stable codes; no exception text to clients; no hash in logs (Pitfall 1); `fetch:` line without hash |
| V8 Data protection | yes | Store URLs only on demand, `Cache-Control: no-store`; `/data` files 0600; no hash in `last-fetch.json` |

### Known Threat Patterns (proposed register entries for 03-SECURITY)

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| GUI reachable without ingress (published port, other add-on on the hassio network) | Spoofing / EoP | Gate R-01; `8099` never in `ports`; verify script with a real non-ingress peer |
| Hash in access log / sink output / tracebacks | Information disclosure | `%m %U %>s` only into the pipe; forwarder silent; fetchlog logs labels; `error_mappers` + masking stdout wrapper |
| Forged datagrams from the CGI user | Tampering (display integrity) | Socket 0620 root:lighttpd (other uids refused, verified); strict regex; accept residual risk: only `last_fetch` affected |
| Logger stall or death affects git serving | DoS | Non-blocking pipe; lighttpd never blocks (verified); content-free error lines |
| GUI read renames `access.json` (WR-04 amplification) | DoS (fail closed) | Non-destructive locked read; pre-write check in the same lock |
| CSRF on state-changing routes | Tampering | JSON object body required (forces preflight); exact confirm phrase for revoke and rotate; HA ingress cookie `[ASSUMED]` |
| PAT or `SUPERVISOR_TOKEN` in the GUI | Information disclosure | Plain `#!/bin/sh`; token-free `Options`; `/proc/<gui>/environ` scan with a positive control |
| Rotation leaves the user half-revoked | DoS | Pre-validation + compensation; documented non-crash-atomicity |
| T-01-02 changes from "no access log" to "access log only into the sink" | — | Update the threat model and DOCS "Security notes" (D-20) |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The HA Supervisor's git uses protocol v2, so its `ls-remote` also produces a counted POST | What counts as a fetch | Low: last fetch would update only on the fetch part of a pull, which also POSTs |
| A2 | Default Linux pipe buffer 64 KiB bounds the records kept while the forwarder is down | Sink Finding 2 | Low: more or fewer lost `last_fetch` updates during a ≤1 min window |
| A3 | HA's ingress session cookie blocks cross-site requests; the JSON-body rule is extra hardening | Pattern 5, Security | Low: confirm phrase still guards destructive actions; sync trigger is harmless |
| A4 | Registration vocabulary `registered/missing/leftover/error` fits Phase 2's data | Pattern 6 | Medium: the Phase 2 follow-up must map into it or extend the strings |
| A5 | A dev host running a Supervisor has a Docker network overlapping `172.30.32.0/23` | Verify script | Low: the script's overlap pre-check fails with a clear message |
| A6 | Forwarder RSS is about 10 MB (one more Python process) | Sink mechanism | Low: memory only |
| A7 | Placing the ingress keys in `config.yaml` right after `ports_description` avoids Phase 2's insertion point | Coexistence | Low: a trivial rebase conflict at worst |

## Open Questions (RESOLVED)

1. **Registration shape (Q-1 refinement).** RESOLVED
    - What we know: D-19 wants an isolated reader returning no data; R-06 forbids dynamic string keys.
    - What's unclear: the states Phase 2 will produce.
    - Recommendation: Phase 3 fixes the normalised shape (Pattern 6). Tell the manager so Phase 2's follow-up maps into
      it.
    - **Resolution:** adopted. The normalised shape is `{state: registered|missing|leftover|error, detail?}`, keyed by
      the lower-cased repository. Plan 03-01 Task 1 fixes it in `app/web/registration.py` (`REGISTRATION_STATES`,
      `read_registration` returning None) and in the overview rows (`registration: null`), with a `costly`
      reversibility note. Plan 03-01 Task 2 pins it in pytest. Plan 03-06 Task 2 adds the view side
      (`REGISTRATION_KEYS`, `hasRegistration`, a column shown only with data). The manager passes the shape to the
      Phase 2 owner (03-01 "Edge coverage", assumption A4).
    - **Amended by D-19 (user decision 2026-11-18):** the four states are fixed and the source is
      `/data/supervisor.json`; `read_registration` reads it (Plan 03-01) instead of returning None. Only the field layout
      inside that file stays an assumption (Phase 2's contract).
2. **Should `fetchlog` also count `info/refs` 200 as "seen"?** RESOLVED
    - What we know: protocol v2 already counts `ls-remote`.
    - Recommendation: no. Keep the single POST-200 definition and document it.
    - **Resolution:** adopted, `info/refs` does not count. Plan 03-02 Task 1 limits `fetchsink.LINE_RE` to
      `POST …/git-upload-pack 200`, and Plan 03-02 Task 2 tests that `GET …/info/refs 200` is dropped. Plan 03-05
      Task 2 documents the definition in DOCS.md "Contracts".
3. **Topbar version text.** SUPERSEDED by D-30 (user decision 2026-11-18)
    - **D-30:** the top bar shows the full add-on version with subpatch. The Dockerfile declares `ARG BUILD_VERSION`
      (passed as the `config.yaml` version by CI `_build-template.yml` and `make build-addon`) and writes it into a file
      in the image that the GUI reads; no Supervisor call, no token, `build.yaml` unchanged. Plan 03-01 implements it,
      Plan 03-06 tests the rendering. The original resolution below is kept for the record only.
    - Not available without the Supervisor token. The build arg `VERSION` lacks the subpatch.
    - Recommendation: omit. Revisit when Phase 2 provides a Supervisor-aware process that could write the version into
      a file.
    - **Resolution:** adopted, the version is omitted. Plan 03-01 Task 1 renders `Topbar` without `version` and
      `infoPath` (both need the Supervisor, D-07). Revisiting it is not part of Phase 3, so no Phase 3 task covers it.

## Sources

### Primary (HIGH confidence)

- **Local Docker experiments** on `amd64-base:3.24` (throwaway containers, scratch dir outside the repo):
    - piped logger uid and respawn, blocking logger, s6 pipeline fd listing, `%U` format;
    - additive config `-tt`, forwarder + datagram prototype, protocol v0/v2 request counts;
    - ingress-address network allocation.
- **Local probe** against the real `marketplace-repo-proxy/app/access.py`: rotate atomicity across processes.
- **Codebase:**
    - `marketplace-repo-proxy/app/{access,paths,urls,jsonio,status,cli,watch,options,init,logsetup,sync}.py`,
      `rootfs/`, `Dockerfile`, `config.yaml`;
    - `admin-ui/app/web/skeleton/*`, `admin-ui/app/web/static/lib/{api,ui,hooks}.mjs`, `admin-ui/DOCS.md`;
    - `internal/sync-admin-ui.py`, `internal/check-admin-ui-rules.py`, `Makefile`, `.github/workflows/lint.yml`,
      `zizmor.yml`, `.pre-commit-config.yaml`;
    - `haos-monitor/app/web/server.py`, `haos-monitor/tests/{conftest,test_js}.py`, `ntfy/app/web/server.py`;
    - `internal/verify-admin-ui-scaffold.sh`, `internal/verify-marketplace-repo-proxy.sh`.

### Secondary (MEDIUM confidence)

- `github.com/lighttpd/lighttpd1.4` `src/mod_accesslog.c` (raw source via WebFetch), cross-checked by the blocking-logger
  experiment.
- `contributors.home-assistant.io/apps/reference/configuration/`: `ingress_port` default 8099, `panel_admin`
  default `true`, `panel_icon`, `panel_title`.

### Tertiary (LOW confidence)

- None used for decisions.

## Metadata

**Confidence breakdown:**

- **Sink mechanism: HIGH.** Every claim that decides the design was reproduced in the target image.
- **Fetch definition: HIGH** for the client behaviour measured. A1 for the Supervisor's protocol version.
- **Access composition: HIGH.** Code read plus a cross-process probe.
- **GUI wiring, CI, Makefile: HIGH.** Code read.
- **Verify-script network trick: HIGH** for Docker behaviour (verified); MEDIUM for portability to other dev hosts.
- **UX details** (poll cadence, layout): MEDIUM. Discretion items.

**Research date:** 2026-11-18
**Valid until:** 2026-12-18 (stable). Re-check the lighttpd behaviour if the base image moves past lighttpd 1.4.85.
