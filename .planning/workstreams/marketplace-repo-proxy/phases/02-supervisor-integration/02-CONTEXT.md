# Phase 2: Supervisor integration - Context

**Gathered:** 2026-11-18
**Status:** Ready for planning
**Source:** Discuss step skipped by instruction. Decisions come from `marketplace-repo-proxy/SPIKE.md` (section
"Decisions" is binding; section "Supervisor integration" is the agreed design), REQUIREMENTS.md MRP-07 to MRP-11 and the
manager's phase brief (2026-11-18). Items these sources do not answer are listed under "Claude's Discretion" (planner
decides) or "Open questions" (not decided here; planned as checkpoints or reported as assumptions).

<domain>
## Phase Boundary

The local Supervisor gets the proxy's repositories automatically and sees upstream changes within minutes: the add-on
gets `hassio_api: true` / `hassio_role: manager`, keeps one `local` system user per repository, registers that user's
internal store URL in the local store, reloads the store after a sync that changed refs, rotates or removes the `local`
user without ever forcing the removal of a store repository, and is proven once end to end on the production host.

In scope: MRP-07 (manifest keys, allow-listed Supervisor client), MRP-08 (self-registration), MRP-09 (store reload after
changed refs, rate-limited), MRP-10 (rotation/removal of the `local` user, add-first, never forced, leftover reported),
MRP-11 (live E2E on the production host with full cleanup), the docs for all of it, and the subpatch bump `0.1.0-2`.

Out of scope (later phases): ingress GUI and the registration status view (Phase 3; this phase only writes the data
the view will read), access-log sink, provisioning API, public URLs, `stage` decision. Review findings deferred in
Phase 1 (WR-01, WR-04, IN-01 to IN-07) stay deferred unless a Phase 2 change touches the same code anyway.

</domain>

<decisions>
## Implementation Decisions

### Manifest and Supervisor client (MRP-07)
- **D-01:** `config.yaml` gets `hassio_api: true` and `hassio_role: manager` (SPIKE "Decisions": manager role in v1).
  No other API permission keys (`homeassistant_api`, `auth_api`, `docker_api`, `host_network`, ...) are added.
- **D-02:** Exactly one Supervisor client module. It holds an allow-list of `(method, path)` and refuses everything
  else before any network I/O: `GET /store/repositories`, `POST /store/repositories`,
  `DELETE /store/repositories/{slug}` (slug restricted to the Supervisor's repository-slug shape), `POST /store/reload`.
  No other module talks to the Supervisor.
- **D-03:** `SUPERVISOR_TOKEN` is read only by the process that makes Supervisor calls and never reaches lighttpd or
  access-watch (both already run under plain `#!/bin/sh` without the container environment). It never appears in logs,
  `status.json`, `access.json`, exceptions or test output.
- **D-04:** Every Supervisor call is logged (method, allow-listed path template, result/status code) without the token
  and without a full access hash. Store URLs in these log lines are masked like the startup log (Phase 1 D-17/D-27).

### Self-registration (MRP-08)
- **D-05:** One system user per configured repository: user label `local`, `source: "system"` (Phase 1 already reserves
  the label and the source: `access.py` `RESERVED_USERS`, D-25). The hash is a normal random 128-bit access hash.
- **D-06:** When `register_local` is true and `GET /store/repositories` does not list the `local` user's internal store
  URL, the proxy adds it with `POST /store/repositories`. The internal URL uses the add-on's own hostname, as the
  Phase 1 startup log does.
- **D-07:** Registration only for repositories whose last sync is `ok` (a valid bare repository with `repository.yaml`),
  because the Supervisor clones the URL during the add and a failed first clone raises a resolution issue (SPIKE
  "Supervisor source findings", Boot).

### Store reload (MRP-09)
- **D-08:** After a sync cycle in which at least one repository's refs changed, the proxy calls `POST /store/reload`.
  At most one reload per sync interval, also when manual "sync now" triggers run cycles more often. A failed reload is
  logged and retried no earlier than the next cycle that is allowed to reload.

### Rotation and removal of the `local` user (MRP-10)
- **D-09:** Rotation: create the new hash, add the new internal URL to the store first, then try to remove the old store
  repository. Removal: try to remove the store repository. In both cases a refusal by the Supervisor (installed add-ons
  still use the repository, `StoreError ... used by installed apps`) is reported, never forced, and never retried in a
  loop. The proxy never calls anything that uninstalls add-ons.
- **D-10:** A leftover (old URL still registered because the Supervisor refused) is recorded in a machine-readable place
  that the Phase 3 GUI can show (registration status, MRP-13), and logged at warning level.
- **D-11:** The old access entry (and its symlink) of a rotated `local` user: SPIKE says "the old URL stops working right
  away" for rotations. For the `local` user this would break the leftover store repository's updates for still-installed
  add-ons. **Not decided here — see Open questions Q-2.**

### Tests (manager brief)
- **D-12:** No test talks to a real Supervisor. pytest uses a fake Supervisor (stdlib HTTP server or injected
  transport); `internal/verify-marketplace-repo-proxy.sh` runs a fake Supervisor container on the verify network. The
  fake records every request so tests can prove the allow-list (only the four calls, nothing else) and the token's
  absence from lighttpd's process tree and from logs.
- **D-13:** The fake Supervisor should behave like the real one where it matters: the add call clones the URL
  (`git clone --depth 1`, as SPIKE "Clone") and rejects an invalid repository; removal can be configured to refuse with
  the "used by installed apps" error.

### Live E2E (MRP-11, manager brief)
- **D-14:** The live E2E is its own plan, `autonomous: false`, last in the phase. It runs on the production host
  (named only "production host" in every file and commit message) through the `ha` wrapper (SSH); tests never touch it.
- **D-15:** There is a checkpoint before **every** action on the host; the user approves each one through the manager.
  Sequence: add the store repository (via the proxy's self-registration) → install a test add-on from it → change
  upstream → update visible in the store (proves MRP-09 without waiting for the 3-hour Supervisor reload) → full
  cleanup (test add-on uninstalled, store repository removed, proxy configuration back to its prior state).
- **D-16:** No restart of Home Assistant Core or the Supervisor without explicit approval. A refused removal during
  cleanup is the expected MRP-10 behaviour while the test add-on is installed; cleanup order is uninstall first, then
  remove the store repository.
- **D-17:** Evidence written to the plan SUMMARY contains no hostnames, IPs, access hashes, tokens, e-mail addresses or
  person names; store URLs are masked.

### Release and docs
- **D-18:** Subpatch bump to `0.1.0-2` at the end of the phase through
  `make update-version ADDON=marketplace-repo-proxy VERSION=0.1.0-2 NO_TAG=yes` (never by hand). CHANGELOG.md gets
  `## [0.1.0-2] - <date>`. No tag in the plan; the manager tags after the squash merge onto `main` (Phase 1 D-32).
- **D-19:** DOCS.md documents `register_local` (now effective), self-registration, store reload, rotation/removal of the
  `local` user and the leftover report, and replaces "No effect yet". Whether DOCS.md/README.md need an explicit warning
  about `hassio_role: manager` and the security rating is a research item (manager brief); the recommendation is in
  Open questions Q-4.

### Repository rules (CLAUDE.md)
- **D-20:** HA base image only. Any Dockerfile change is verified with a local `docker build` before commit.
- **D-21:** Versions only via `make update-version`.
- **D-22:** Docker verify scripts must not run in two worktrees at the same time.
- **D-23:** Public repository: no hostnames, IPs, e-mail addresses, person names or tokens in files or commit messages.

### Claude's Discretion
- Which process makes the Supervisor calls. SPIKE: the token "stays in the `gui`/`sync` processes". A natural choice is
  the sync service (it already runs `with-contenv` and knows when refs changed); requests from the CLI (and later the
  GUI) could reach it through a request file like the Phase 1 sync trigger. The planner decides, within D-02/D-03.
- HTTP client (stdlib `urllib.request` is enough; no new Python package), timeouts, response parsing.
- How to detect "refs changed" (compare the fetched branch tip before/after per repository).
- Where the registration state lives (`status.json` extension or a new `/data/supervisor.json`), within D-10, and its
  field names. It is a contract the Phase 3 GUI consumes, so it is documented like the Phase 1 contracts.
- How the operator triggers rotation/removal of the `local` user in Phase 2 (no GUI yet), for example a new `mrp`
  subcommand that is allowed to act on `local` only through the Supervisor-aware path.
- How the verify script provides the fake Supervisor (container with network alias `supervisor`, or a test-only base-URL
  override via environment like the Phase 1 upstream override; an override must not be reachable through add-on
  options).
- Wave layout, as long as the E2E plan is last and the bump happens once at the end of the code work.

</decisions>

<open_questions>
## Open Questions (not decided; do not guess)

- **Q-1 (E2E install source and order):** CI builds and publishes images only from `main`. The production host can run
  the Phase 2 code either (a) after the squash merge and CI image of `0.1.0-2` (install source as decided in SPIKE,
  hostname `{repo-hash}-marketplace-repo-proxy`), or (b) before the merge as a local add-on copy built on the host
  (different hostname and therefore a different store URL; local build). The E2E plan must start with a
  `checkpoint:decision` for this, recommending (a), and must work for both.
- **Q-2 (old `local` URL after rotation):** Keep serving the old `local` access entry while its store repository is a
  leftover (installed add-ons keep getting updates until the operator reinstalls), or revoke it right away like any user
  rotation (SPIKE "Rotation is expensive")? Planner: pick the variant that keeps installed add-ons working (keep until the
  store repository is gone), mark it as an assumption in the plan, and expose it for confirmation.
- **Q-3 (removal triggers):** Does `register_local: false`, or removing a repository from `repositories`, remove the
  `local` store repository automatically? Planner assumption: no automatic removal; `register_local: false` only stops
  adding; removal is an explicit operator action. Mark as assumption.
- **Q-4 (manager-role warning):** Recommendation: yes — DOCS.md gets a security note on what `hassio_role: manager`
  allows, why the proxy needs it, the allow-list mitigation and the lower security rating; README.md gets a one-line
  pointer. Research confirms the rating effect from the Supervisor source.
- **Q-5 (E2E test repository):** The E2E needs a private upstream repository with `repository.yaml` and one trivial test
  add-on that the configured PAT can read, and a way to change it upstream (version bump commit). Which repository is
  used, and who pushes the change, is a `checkpoint:human-action` in the E2E plan; no repository name is written into
  files.

</open_questions>

<specifics>
## Specific Ideas

- Supervisor repository identity is `sha1(url.lower())[:8]` (SPIKE); the slug in `DELETE /store/repositories/{slug}`
  is that hash. Find the proxy's own entries by URL, not by name.
- The `local` user's hash must be stable across restarts (it is the store identity); a restore keeps it (`/data` is in
  the backup).
- Phase 1 verify script already has a positive control that `SUPERVISOR_TOKEN` is in sync's environment and a `/proc`
  scan proving it is not in lighttpd's; Phase 2 extends that with a real token value and the fake Supervisor.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design and decisions
- `marketplace-repo-proxy/SPIKE.md` — "Decisions" (binding), "Supervisor integration", "Supervisor source findings",
  "URL scheme and access tokens" (rotation cost, repository identity)
- `.planning/workstreams/marketplace-repo-proxy/REQUIREMENTS.md` — MRP-07 to MRP-11
- `.planning/workstreams/marketplace-repo-proxy/ROADMAP.md` — Phase 2 success criteria 1-5
- `.planning/workstreams/marketplace-repo-proxy/phases/01-git-serving-core/01-CONTEXT.md` — Phase 1 decisions and
  contracts (D-17, D-20, D-24 to D-32)
- `.planning/workstreams/marketplace-repo-proxy/phases/01-git-serving-core/01-SECURITY.md` — threat register to extend
- `.planning/workstreams/marketplace-repo-proxy/phases/01-git-serving-core/01-REVIEW-DISPOSITION.md` — deferred findings

### Repository rules
- `CLAUDE.md` — own-code exception, 3-file versioning, local docker build, verify-script concurrency, public repository

### Existing code
- `marketplace-repo-proxy/app/` (`sync.py`, `access.py`, `status.py`, `urls.py`, `cli.py`, `init.py`, `jsonio.py`,
  `logsetup.py`), `marketplace-repo-proxy/tests/`, `marketplace-repo-proxy/rootfs/etc/s6-overlay/`,
  `internal/verify-marketplace-repo-proxy.sh`, `marketplace-repo-proxy/DOCS.md`, `README.md`, `CHANGELOG.md`,
  `config.yaml`, `translations/`

</canonical_refs>

<deferred>
## Deferred Ideas

- Registration status view and leftover display in the GUI (Phase 3, MRP-13).
- Phase 1 review findings WR-01, WR-04, IN-01 to IN-07 (user decision 2026-11-18).
- Manual sync trigger via `stdin` (Phase 1 D-29).

</deferred>

---

*Phase: 02-supervisor-integration*
*Context gathered: 2026-11-18 (from SPIKE.md and the manager brief, discuss step skipped)*
