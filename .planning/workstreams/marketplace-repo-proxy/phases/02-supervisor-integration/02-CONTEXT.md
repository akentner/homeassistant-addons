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
- **D-28 (user decision 2026-11-18, alignment with Phase 3):** The registration status of the `local` user in
  `/data/supervisor.json` is one field per repository with exactly the fixed values `registered`, `missing`, `leftover`,
  `error`. No other value is ever written there (no `pending`, `interrupted`, `orphaned`, ...); finer detail may live in
  separate fields but never as a status value. Phase 3 renders the four values through fixed i18n keys, so the value set
  is part of the `supervisor.json` contract and is documented in DOCS.md. The mapping of internal situations to the four
  values (and the precedence when several apply, e.g. current URL registered while an old store repository is a
  leftover) is defined once in the contract and tested.
- **D-29 (user decision 2026-11-18, Phase 3 interface):** `/data/supervisor.json` always contains this structure, which
  Phase 3 reads as is: a top-level key `repositories` holding a list of objects
  `{"repository": "owner/repo", "registration": "registered|missing|leftover|error", "message": "..."}`. `message` is
  optional, a plain human-readable string without secrets, URLs or hashes (no token, no store URL, no access hash, no
  Supervisor error text that contains a URL). Further keys are allowed at the top level and inside each object, but this
  structure must always be present and valid. The contract (DOCS.md) and the Phase 2 tests (pytest and the verify
  script) assert exactly this shape, the D-28 value set and the absence of secrets, URLs and 32-hex values in `message`.
- **D-11 (user decision 2026-11-18, Q-2):** Rotating the `local` user revokes the old URL **immediately**, like any user
  rotation (SPIKE "Rotation is expensive"): the old access entry and its symlink are removed in the same rotation, so
  the old URL gets 404 right away. Before rotating, the operator gets a clear warning that add-ons installed from the old
  store repository get no updates until they are reinstalled from the new one. The leftover lifecycle of the old store
  repository (D-09/D-10: removal attempted, refusal reported, never forced) stays unchanged. There is no
  keep-old-URL-serving variant and no `--revoke-old` flag.
- **D-30 (user decision 2026-11-18, was planner assumption A-17 in 02-01-PLAN.md):** D-28 mapping and precedence as
  written in A-17: first match wins, `error` > `leftover` > `registered` > `missing`, with the facts and examples listed
  there.
- **D-31 (user decision 2026-11-18, was planner assumption A-18 in 02-04-PLAN.md):** `mrp local rotate` prints the D-11
  warning on every call and rotates only with `--yes` (flag, no interactive prompt); the sync process needs no
  confirmation key in the request file.
- **D-32 (user decision 2026-11-18, was planner assumption A-22 in 02-01-PLAN.md):** D-29 details as written in A-22:
  `message` only from fixed English templates, never Supervisor text (masked text to the log, `error` code and
  `error_status` in the state), `message` absent for `registered`, unconfigured repositories with a recorded store
  repository listed after the configured ones (`configured: false`, `leftover`), file written at every sync start
  before the first Supervisor call.

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
- **D-24 (user decision 2026-11-18, Q-1):** The E2E runs **after** the squash merge of Plans 02-01 to 02-06, with the CI
  image `0.1.0-2` installed from this repository (install source as decided in SPIKE, hostname
  `{repo-hash}-marketplace-repo-proxy`). Plan 02-07 is executed as a follow-up step after that merge, not together with
  02-01 to 02-06; it has no install-source decision checkpoint and no local-copy variant. A defect found in the E2E is
  fixed as a further subpatch (`0.1.0-3`).
- **D-25 (user decision 2026-11-18, Q-5):** At E2E time the executing worker creates the private test repository with
  `gh` under the user's GitHub account and pushes its content (`repository.yaml`, one trivial test add-on) and later the
  update commit. The user creates the fine-grained PAT (Contents: read-only, selected repositories incl. the test
  repository) and enters it in the proxy options; the worker never creates or handles the PAT. The test repository name
  never appears in repository files, plan files, SUMMARYs or commit messages. After the E2E the test repository stays
  until the user decides about deleting it; that decision is its own checkpoint, and deletion happens only on explicit
  approval.
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
  `local` user and the leftover report, and replaces "No effect yet".
- **D-26 (user decision 2026-11-18, Q-4):** DOCS.md gets a security note on `hassio_role: manager`: what the role allows,
  why the proxy needs it, the allow-list mitigation and the lower security rating (7 → 6 per research). README.md gets a
  one-line pointer to that note.
- **D-27 (user decision 2026-11-18, Q-3):** No automatic removal of a `local` store repository. `register_local: false`
  only stops adding; removing a repository from `repositories` removes nothing in the store. Removal happens only as an
  explicit operator action.

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
## Open Questions

All five questions were decided by the user on 2026-11-18 and are now decisions:

- **Q-1 (E2E install source and order):** decided → D-24 (after the squash merge, CI image `0.1.0-2`).
- **Q-2 (old `local` URL after rotation):** decided → D-11 (revoke immediately, warn before rotating).
- **Q-3 (removal triggers):** decided → D-27 (no automatic removal).
- **Q-4 (manager-role warning):** decided → D-26 (DOCS.md security note, README pointer).
- **Q-5 (E2E test repository):** decided → D-25 (worker creates it with `gh` at E2E time, user creates the PAT, repo
  kept until the user decides).

Research questions Q-6 (token API over TCP, socket transport later) and Q-7 (only the four allow-listed calls, no
pre-check before DELETE) stay planner assumptions as written in the plans.

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
*Context gathered: 2026-11-18 (from SPIKE.md and the manager brief, discuss step skipped); amended 2026-11-18 (user
decisions on Q-1 to Q-5: D-11 revised, D-24 to D-27 added; A-17, A-18, A-22 confirmed as D-30 to D-32)*
