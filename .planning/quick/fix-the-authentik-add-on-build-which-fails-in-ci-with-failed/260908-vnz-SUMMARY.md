---
phase: quick-260908-vnz
plan: "01"
subsystem: infra
tags: [authentik, docker, podman, home-assistant-addon, ci, rust, allinone]
status: complete

requires:
  - phase: "authentik add-on (pre-existing)"
    provides: "Two-binary Dockerfile + run.sh startup shape written against upstream authentik <= 2026.7"
provides:
  - "authentik/Dockerfile adapted to upstream 2026.8.1's single-binary layout — the stale /usr/bin/authentik-server COPY removed, banner + comment rewritten for the one Rust binary"
  - "authentik/run.sh collapsed from a backgrounded-server + exec'd-worker pair to one supervised `exec runuser -u authentik -- /usr/bin/authentik allinone`"
  - "Empirical proof that the add-on image builds green locally with CI's build-graph args (podman, exit 0)"
affects: [authentik add-on release, CI Build Authentik workflow, follow-up that publishes an authentik ghcr image]

actuals:
  tokens: 2553
  tasks: 2
  commits: 1
  plan_head_before: 2c94feb45a854c62f57d57ab344cfef2d38172b3

tech-stack:
  added: []
  patterns:
    - "Single exec'd supervised process as the HA add-on entrypoint (container PID 1 lifecycle tracks the whole application)"

key-files:
  created: []
  modified:
    - authentik/Dockerfile
    - authentik/run.sh

key-decisions:
  - "Use upstream's `allinone` subcommand rather than two separate `server` + `worker` invocations — it is what upstream documents for combined operation and it is the only shape that gives the HA Supervisor a single process to supervise"
  - "Keep `runuser -u authentik --` on the collapsed invocation — collapsing two processes into one must not collapse the privilege drop; authentik never runs as root"
  - "Run the load-bearing local container build BEFORE committing, deviating from the plan's task ordering, because repo CLAUDE.md forbids committing an unbuilt Dockerfile change"
  - "No version bump and no pre-built-image key — the fix adapts the add-on to what 2026.8.1 ships; publishing an image is a separate follow-up"

patterns-established:
  - "Comment-stripped count gates (`grep -vE '^(#|[[:blank:]]+#)' | grep -c`) so a reworded comment banner can neither satisfy nor break a structural assertion"

requirements-completed: []
---

# Quick 260908-vnz: Fix the authentik add-on build failing in CI Summary

Removed the `COPY` of `/usr/bin/authentik-server` — a path upstream authentik 2026.8.1 no longer ships, which was the
literal cause of CI run 33640040380's `failed to compute cache key … not found` — and collapsed `run.sh`'s two-process
startup into one privilege-dropped, supervised `authentik allinone` exec; proven by a local `podman build` that exits 0.

## What Was Built

**Root cause.** Upstream authentik 2026.8.1 replaced the separate Go server executable with a single Rust binary at
`/usr/bin/authentik` carrying `allinone` / `server` / `worker` / `proxy` / `healthcheck` subcommands. Two add-on files
still assumed the old two-binary layout: the Dockerfile copied the removed path (the build-time failure CI hit) and
`run.sh` executed it (a latent runtime failure the build error was hiding).

**`authentik/Dockerfile`** — the `# ── Authentik binaries ──` block (lines 27-31) became a singular
`# ── Authentik binary ──` block describing the one Rust binary and its `libpython3.14` linkage. The stale
`COPY --from=authentik-source /usr/bin/authentik-server …` line is gone. `COPY --from=authentik-source` instruction
count on non-comment lines: **19 → 18**. Nothing else in the file changed — not the apt list, not the Python 3.14
runtime COPYs, not `ldconfig`, not the `/ak-root` venv COPY, not the app-file COPYs, not the user creation, not
`EXPOSE 9000 9443`, not `CMD ["/run.sh"]`, not the `LABEL` block.

**`authentik/run.sh`** — the trailing 7-line block (backgrounded server + `exec`'d worker, plus both banners and both
`bashio::log.info` lines) became three lines:

```sh
# ── Start authentik (single Rust binary: server + worker) ────────────────────
bashio::log.info "Starting authentik (server + worker) on :9000/:9443..."
exec runuser -u authentik -- /usr/bin/authentik allinone
```

This also removes a real supervision defect: previously, if the `exec`'d worker died the backgrounded server was left
unsupervised, and if the server died nothing noticed. Now container exit tracks application exit, so the HA Supervisor's
restart policy applies (T-vnz-03 mitigated). Everything above the edited block is untouched — Python venv exports,
bashio option reads, persistent secret generation, the PostgreSQL init/start/wait/provision block, the Valkey start,
every `AUTHENTIK_*` export, the email block, and the `/data/media` + `/data/certs` symlink setup.

## Verification Results

### 1. Local container build — the load-bearing gate

Built with the three of CI's nine build args that reach the build graph or the arch label
(`.github/workflows/_build-template.yml` lines 157-166):

```bash
podman build \
  --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:trixie \
  --build-arg VERSION=2026.8.1 \
  --build-arg BUILD_ARCH=amd64 \
  -t localhost/authentik-addon-verify:2026.8.1 \
  authentik/
```

| Item            | Result                                                   |
| --------------- | -------------------------------------------------------- |
| Exit status     | **0** (`BUILD_EXIT=0` sentinel in log)                   |
| Wall time       | ~6 min 3 s (18:45:10 → 18:51:13 local, 2026-09-09)       |
| Steps completed | 37/37 in stage 2                                         |
| Image           | `localhost/authentik-addon-verify:2026.8.1`, **2.47 GB** |
| Log             | `${TMPDIR:-/tmp}/authentik-build-260908-vnz.log`         |

Log tail proving success:

```text
[2/2] STEP 37/37: LABEL     io.hass.name="${BUILD_NAME}" …
[2/2] COMMIT localhost/authentik-addon-verify:2026.8.1
--> 6b26b8cc1ebb
Successfully tagged localhost/authentik-addon-verify:2026.8.1
6b26b8cc1ebb24a4eebf064f05bde6f9e744dfbbde6bc167b1734cf93bce5388
BUILD_EXIT=0
```

No `failed to compute cache key` error for any COPY source path — the exact failure mode CI hit, reproduced green
locally.

### 2. In-image runtime probe

```bash
podman run --rm --entrypoint /bin/sh localhost/authentik-addon-verify:2026.8.1 -c \
  'test -x /usr/bin/authentik && test -x /usr/sbin/runuser && /usr/bin/authentik --help' | grep -q allinone
# exit 0
```

Raw output (annotated probe run):

```text
authentik_exec=yes
runuser_exec=yes
{"…","target":"authentik","event":"authentik is starting","version":"2026.8.1"}
Usage: authentik <command> [<args>]

Commands:
  allinone          Run both the authentik server and worker.
  server            Run the authentik server.
  worker            Run the authentik worker.
  proxy             Run the authentik proxy outpost.
  healthcheck       Run healthcheck
```

Three things proven inside the artifact CI will build: `/usr/bin/authentik` is present and executable, it advertises
`allinone`, and `/usr/sbin/runuser` is present and executable so `run.sh`'s privilege drop has something to call. The
`runuser` half was a regression tripwire on an already-confirmed fact (from `util-linux` in the HA base image) — it
passed, so nothing was reported or halted on it.

### 3. Textual gates (Task 1)

| # | Gate                                                             | Result           |
| - | ---------------------------------------------------------------- | ---------------- |
| 1 | `! grep -q 'authentik-server' Dockerfile run.sh`                 | exit 0 (3 → 0)   |
| 2 | `! grep -q 'Go binary' Dockerfile run.sh`                        | exit 0 (2 → 0)   |
| 3 | non-comment `COPY --from=authentik-source` count `= 18`          | exit 0, count 18 |
| 4 | non-comment `runuser -u authentik` count `= 1`                   | exit 0, count 1  |
| 5 | non-comment line contains `exec runuser … authentik allinone`    | exit 0           |
| 6 | `shellcheck -e SC1091 -e SC2034 authentik/run.sh`                | exit 0           |
| 7 | `git diff --quiet HEAD -- config.yaml build.yaml DOCS.md README.md` | exit 0        |

### 4. Lint

**GATE — scoped run: `pre-commit run --files authentik/Dockerfile authentik/run.sh` → exit 0.** Hooks that actually
fired and passed: `trim trailing whitespace`, `fix end of files`, `check for added large files`, `check for case
conflicts`, `check for merge conflicts`, `check that executables have shebangs`, `check that scripts with shebangs are
executable`, `mixed line ending`, `shellcheck`, `Lint Dockerfiles` (hadolint), plus both `always_run: true` repo gates
`Validate Add-on Versioning` and `Validate Add-on config.yaml Schema` — so the 3-file version-sync check was enforced.
Both `terraform-bridge` hooks reported `Skipped (no files to check)`, as intended.

**REPORTED, NOT GATED — full `make lint` (`pre-commit run --all-files`) → exit 0.** All 21 hooks `Passed`, including
`verify-bridge-scaffold` and `verify-bridge-no-token-leak` (which container-build and `docker run` the unrelated
`terraform-bridge` add-on). Nothing went red, so there is no failing hook or file to name. This is reported as a
courtesy datapoint only — it is not attributable to this fix either way.

### 5. Scope

```text
$ git diff --stat <plan-base>..HEAD -- authentik/
 authentik/Dockerfile |  7 +++----
 authentik/run.sh     | 10 +++-------
 2 files changed, 6 insertions(+), 11 deletions(-)
```

Pre-commit `git diff --name-only HEAD -- authentik/` listed exactly `authentik/Dockerfile,authentik/run.sh` — gate 4 of
Task 2, exit 0. `config.yaml`, `build.yaml`, `DOCS.md` and `README.md` are byte-identical to HEAD. No file outside
`authentik/` was touched. The pre-existing unrelated working-tree entries (`.planning/WINDOWS.md` modified; untracked
`.gsd/`, `.planning/quick-batches/260908-vnx/`, the sibling item's quick dir, `network-tools/.planning/quick/`) were
left alone and are not staged.

## Explicitly NOT Done (deliberate, per plan)

- **No version bump.** `authentik/config.yaml` stays `2026.8.1-0`, `authentik/build.yaml` stays `2026.8.1`. The fix
  adapts the add-on to what 2026.8.1 already ships; it does not move to a different upstream release.
- **No pre-built-image key added to `authentik/config.yaml`.** No authentik image exists in ghcr yet, so declaring one
  would leave the add-on referencing an unpullable image and therefore uninstallable. **The follow-up that publishes an
  authentik image and then adds the `image:` key remains open.** Sibling batch item `260908-vny` added that key for five
  *other* add-ons and deliberately excluded authentik.
- **No aarch64 change** — still commented out in both `config.yaml` and `build.yaml`.
- **No docs edits.** `authentik/DOCS.md` line 26 ("Authentik worker | Background tasks…") stays accurate — the worker
  still runs, inside the supervised process — and line 18 ("three processes") becomes *more* accurate after this change.

## Still-Open Follow-Ups

| Follow-up | Why deferred |
| --------- | ------------ |
| **Publish an authentik image to ghcr, then add the `image:` key to `authentik/config.yaml`** | The image does not exist yet. This fix makes the build green so CI *can* publish one; adding the key first would break the add-on. |
| **`run.sh`'s bare-name `runuser` invocation** (vs. absolute `/usr/sbin/runuser`) | Pre-existing and working — `run.sh` runs under `#!/usr/bin/with-contenv bashio`, not a bare root `sh`. Switching to the absolute path is a separate decision, explicitly out of this item's scope. |
| **Digest-pinning the upstream `FROM ghcr.io/goauthentik/server:${VERSION}` tag** (threat T-vnz-02, medium, `accept`) | The mutable tag is load-bearing for the `.upstream.yaml` auto-update system, which rewrites `args.VERSION` on every upstream release; digest pinning would break that automation. Below the `high` blocking threshold and unchanged by this plan. |
| **Live verification: add-on installs on a HA host and authentik serves on :9000** | Needs a published image plus a real HA install. The natural place for this empirical check is the follow-up above. |

## Deviations from Plan

### Auto-fixed / process deviations

**1. [CLAUDE.md precedence] Task 1's commit was deferred until after Task 2's build**

- **Found during:** Task 1, at the commit step
- **Issue:** The plan sequences a Task 1 commit before Task 2's local container build. Repo `CLAUDE.md` states: *"Any
  Dockerfile change that modifies packages, base images, or build stages must be verified with a local `docker build`
  before committing and pushing. Do not commit untested Dockerfile changes."* Committing Task 1 first would have
  violated that directive, and the coordinator's dispatch notes independently reinforced it ("do not commit a Dockerfile
  change you have not built").
- **Fix:** Ran all seven Task 1 textual gates (green), then ran Task 2's build + probe + lint gates (green), then made a
  single commit covering both files. CLAUDE.md takes precedence over plan task ordering.
- **Files modified:** none beyond the plan's two — this changed sequencing only, not content.
- **Commit:** `dc544d1`
- **Effect on plan intent:** none. Task 1 is a `tracer` whose two edits are one root cause and the plan already required
  them to land together; Task 2 adds no code, so the merged commit is exactly the plan's intended end state.

No Rule 1 (bug), Rule 2 (missing critical functionality), Rule 3 (blocking issue) or Rule 4 (architectural) deviations
occurred. No auth gates. No fix attempts consumed. No stubs, skipped tests or unrun `<verify>` gates — every gate in the
plan was executed and every one passed, so nothing was appended to `.planning/WINDOWS.md` (and the pre-existing unstaged
modification there was left untouched per dispatch instructions).

### Tracer feedback gate

Task 1 is `type="tracer"` with no `gate="blocking-human"` attribute. Auto mode is **not** active
(`workflow._auto_chain_active=false`, `workflow.auto_advance=false`), and `workflow.human_verify_mode=end-of-phase` with
a fully `<automated>` Task 1 `<verify>` block — so per the interactive branch the gate re-ran the verify set end-to-end
rather than raising a checkpoint. All seven gates passed, so execution continued to Task 2 with no checkpoint.

## Threat Model Outcome

| Threat ID | Disposition | Outcome |
| --------- | ----------- | ------- |
| T-vnz-01 (EoP — privilege drop) | mitigate | **Mitigated.** Exactly one non-comment `runuser -u authentik` line remains and it is the `exec`'d `allinone` line (gates 4 + 5). `/usr/sbin/runuser` confirmed executable in the built image. |
| T-vnz-02 (supply chain — mutable tag) | accept | Unchanged. See follow-ups table. |
| T-vnz-03 (DoS — supervision) | mitigate | **Mitigated by the fix itself.** Single `exec`'d process; no `&` backgrounding remains. |
| T-vnz-04 (build log disclosure) | accept | Log written to `${TMPDIR:-/tmp}/`, outside the repo, never committed. All three build args non-secret. |
| T-vnz-SC (package-manager installs) | accept | No package install added or changed; the `apt-get install` list is untouched. |

**Non-goal guard held:** `git diff --quiet HEAD -- authentik/config.yaml` passed — no pre-built-image key was added.

No new threat surface introduced: the change removes one filesystem copy from a third-party image and reduces two
processes to one. No new network endpoint, auth path, file-access pattern or schema change at a trust boundary.

## Commits

| Commit    | Type  | Message                                                                          | Files |
| --------- | ----- | -------------------------------------------------------------------------------- | ----- |
| `dc544d1` | `fix` | `fix(260908-vnz): adapt authentik add-on to upstream 2026.8.1 single-binary layout` | 2     |

Measured: `git rev-list --count 2c94feb..HEAD` = **1**. Base recorded as `plan_head_before: 2c94feb45a854c…`. Committed
inline on `main` (dispatch resolved `dispatch.isolation = none` — no worktree, no feature branch);
`git.allow_default_branch_commits=true` is set in `.planning/config.json`, so the executor's protected-branch assertion
resolved `is-protected=false` and the commit was permitted.

Docs artifacts (this SUMMARY, `STATE.md`, `ROADMAP.md`) are deliberately **not** committed here — the batch orchestrator
owns those writes.

## Cleanup Note

The verification image `localhost/authentik-addon-verify:2026.8.1` (2.47 GB) was **kept** — it makes a re-check cheap.
Remove with `podman rmi localhost/authentik-addon-verify:2026.8.1` if the space is wanted.

## Self-Check: PASSED

- `authentik/Dockerfile` — FOUND
- `authentik/run.sh` — FOUND
- `.planning/quick/fix-the-authentik-add-on-build-which-fails-in-ci-with-failed/260908-vnz-SUMMARY.md` — FOUND
- Commit `dc544d1` — FOUND in `git log --all`, 2 files changed, 6 insertions(+), 11 deletions(-)
- Post-commit gate re-assertion against HEAD content: stale path gone, `COPY --from=authentik-source` count 18,
  non-comment `runuser -u authentik` count 1, working tree clean vs HEAD under `authentik/`

No missing items.
