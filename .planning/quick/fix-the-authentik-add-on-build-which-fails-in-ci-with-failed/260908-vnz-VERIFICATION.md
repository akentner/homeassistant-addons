---
phase: quick-260908-vnz
verified: 2026-09-09T17:12:00Z
status: passed
score: 7/7 must-haves verified
covered_files:
  - ".planning/quick/fix-the-authentik-add-on-build-which-fails-in-ci-with-failed/260908-vnz-PLAN.md"
  - ".planning/quick/fix-the-authentik-add-on-build-which-fails-in-ci-with-failed/260908-vnz-SUMMARY.md"
  - "authentik/Dockerfile"
  - "authentik/run.sh"
covered_digest: "v1:sha256:f95dc2ea4b03a8b72febc8ce4c3cef791bae61ab73d51322f164b2c7eee0bff4"
behavior_unverified: 0
overrides_applied: 0
deferred:
  - truth: "Live verification: the add-on installs on a HA host and authentik serves on :9000 against a live PostgreSQL/Valkey"
    addressed_in: "Declared follow-up: publish an authentik image to ghcr, then add the `image:` key to authentik/config.yaml"
    evidence: "PLAN.md <verification>: 'Deliberately NOT verified here: live add-on installation on a HA host, and authentik actually serving on :9000. Those need a published image plus a real HA install; the follow-up that adds the pre-built-image key is the natural place for that empirical check.' Not a must-have of this item; the pre-change two-process shape was never live-verified either, so this is not a regression introduced here."
---

# Quick 260908-vnz: Fix the authentik add-on build failing in CI — Verification Report

**Item Goal:** Fix the authentik add-on build failing in CI with
`failed to compute cache key: "/usr/bin/authentik-server": not found` — adapt the add-on to upstream 2026.8.1's
single-binary layout (Dockerfile COPY removal + `run.sh` single-`allinone` startup), proven by a real local container
build, with no version bump and no `image:` key.
**Verified:** 2026-09-09T17:12:00Z
**Status:** passed
**Re-verification:** No — initial verification
**Commit under verification:** `dc544d1` (base `2c94feb`), 2 files, 6 insertions / 11 deletions

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                       | Status     | Evidence                                                                                                                                                                                                                                                                                                                                                                             |
| --- | ----------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Local container build with CI's build-graph args completes successfully, no `failed to compute cache key`    | ✓ VERIFIED | **Independent rebuild from the committed tree: `REBUILD_EXIT=0`** (18:58:36→18:59:21, 45 s, 36/37 layers cached) and it resolved to the **identical image digest `6b26b8cc1ebb`** as the executor's build — proving the kept image *is* the build of the committed Dockerfile, not of some other tree state. Executor's log `BUILD_EXIT=0` at line 437. No cache-key error in either. |
| 2   | The container starts authentik as a single supervised process running both the web/API server and the worker | ✓ VERIFIED | Structural: one `exec`, zero `&`-backgrounded lines. **Behavioral (probe run):** `allinone` accepted (no usage error), Python initialized → config loaded → Prometheus recorder → DB pool init → `starting metrics server addr=[::]:9300`; on SIGTERM the internal **arbiter** logged `shutdown gracefully` → `all webservers have been shutdown`. Residual: see `deferred`.        |
| 3   | The add-on still drops privileges to the unprivileged `authentik` user (uid 1000) — never runs as root       | ✓ VERIFIED | `runuser -u authentik --` retained on the collapsed line (exactly 1 non-comment occurrence). In-image: `uid=1000(authentik) gid=1000(authentik)`; `/ak-root`, `/media`, `/certs` all `authentik:authentik`. **Behaviorally exercised:** shell `root uid=0` → after `runuser`: `authentik uid=1000`.                                                                                    |
| 4   | No reference to the removed upstream server executable remains in either file                               | ✓ VERIFIED | `grep -q 'authentik-server' authentik/Dockerfile authentik/run.sh` → absent (was 3 hits). `'Go binary'` → absent (was 2 hits). In-image `test -e /usr/bin/authentik-server` → absent, confirming the path really is gone upstream.                                                                                                                                                    |
| 5   | The 18 verified-to-exist COPY source paths are all still copied — exactly one COPY line removed              | ✓ VERIFIED | Non-comment `COPY --from=authentik-source` count = **18** (total in file also 18 — no commented-out survivor). The 18 paths match the plan's verified list exactly. `git diff` shows exactly one COPY line deleted. Build log executed **18** stage-2 COPY steps; total steps 37 (a 19-COPY file would be 38).                                                                         |
| 6   | Published version unchanged (no bump) and `authentik/config.yaml` gains no pre-built-image key               | ✓ VERIFIED | `config.yaml: version: "2026.8.1-0"`, `build.yaml: VERSION: "2026.8.1"`, README badge `v2026.8.1` — 3-file sync intact, `git diff --quiet 2c94feb..HEAD` on config/build/DOCS/README passes. **No `image` string exists anywhere in `authentik/config.yaml`**, and `git log -S'image:' -- authentik/config.yaml` returns nothing — the key was never added, in any commit.            |
| 7   | `pre-commit run --files authentik/Dockerfile authentik/run.sh` exits 0; full `make lint` run and reported     | ✓ VERIFIED | Scoped gate: **exit 0**, 0 `Failed`. `shellcheck -e SC1091 -e SC2034 authentik/run.sh` → exit 0. **Full `make lint` independently re-run: exit 0, all 21 hooks `Passed`** — including both terraform-bridge container-building hooks — and `git status` was byte-identical before/after, so no fixer mutated the tree.                                                                 |

**Score:** 7/7 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact              | Expected                                                                           | Status     | Details                                                                                                                                                                                                                                                                            |
| --------------------- | ---------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `authentik/Dockerfile` | Stale COPY removed, preceding comment block corrected to describe the single binary | ✓ VERIFIED | Line 27 banner `# ── Authentik binary ──` (singularized); lines 28-29 now describe "single Rust binary carrying the server, worker and allinone subcommands — dynamically linked to libpython3.14". Box-drawing style preserved. `CMD ["/run.sh"]`, `EXPOSE 9000 9443`, `useradd --uid 1000`, LABEL block, apt list, `ldconfig` all untouched. |
| `authentik/run.sh`     | Two-process startup replaced by one exec'd supervised process, comments corrected   | ✓ VERIFIED | 7-line trailing block → 3 lines ending `exec runuser -u authentik -- /usr/bin/authentik allinone` (line 107, EOF). Shebang `#!/usr/bin/with-contenv bashio`, `# shellcheck shell=bash`, `set -e` intact. Everything above line 114 of the pre-image (venv exports, bashio reads, PostgreSQL/Valkey blocks, `AUTHENTIK_*` exports, email block, media/certs symlinks) unchanged per diff. |

### Key Link Verification

| From                                                     | To                                             | Via                                                        | Status  | Details                                                                                                                                                                                                            |
| -------------------------------------------------------- | ---------------------------------------------- | ---------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `Dockerfile` COPY of `/usr/bin/authentik`                 | `run.sh` exec of that same path                | `allinone` subcommand                                      | ✓ WIRED | Both sides reference the same absolute path. In-image `test -x /usr/bin/authentik` → yes, and `--help` advertises `allinone — Run both the authentik server and worker.` The broken contract is restored end-to-end. |
| `build.yaml args.VERSION` (2026.8.1)                      | `FROM ghcr.io/goauthentik/server:${VERSION}`   | build arg substitution                                     | ✓ WIRED | Build log stage 1: `FROM ghcr.io/goauthentik/server:2026.8.1 AS authentik-source --> 2c9dd0d4db11`, matching the locally stored upstream image. VERSION unchanged, as required.                                     |
| `run.sh` `runuser -u authentik` privilege drop             | Dockerfile uid-1000 user + chown of /ak-root, /media, /certs | `useradd --uid 1000 --gid 1000` + `chown -R authentik:authentik` | ✓ WIRED | The user the script drops to exists with uid 1000 and owns all three paths. Verified live: `runuser -u authentik -- id -u` → `1000`.                                                                                |

### Behavioral Spot-Checks

| Behavior                                          | Command                                                                                                   | Result                                                                     | Status |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ------ |
| Committed Dockerfile builds                       | `podman build --build-arg BUILD_FROM=…amd64-base-debian:trixie --build-arg VERSION=2026.8.1 --build-arg BUILD_ARCH=amd64 -t localhost/authentik-reverify:2026.8.1 authentik/` | `REBUILD_EXIT=0`, 45 s, same digest `6b26b8cc1ebb`                          | ✓ PASS |
| Rust binary present, executable, advertises allinone | `test -x /usr/bin/authentik && /usr/bin/authentik --help \| grep allinone`                                | `allinone  Run both the authentik server and worker.`                       | ✓ PASS |
| Removed upstream path really absent                | `test -e /usr/bin/authentik-server`                                                                       | absent                                                                     | ✓ PASS |
| `runuser` available for the privilege drop          | `test -x /usr/sbin/runuser`; `command -v runuser`                                                          | executable; bare name also resolves (`/usr/sbin` on PATH)                   | ✓ PASS |
| Privilege drop actually drops                      | `runuser -u authentik -- id -un`                                                                          | `root uid=0` → `authentik uid=1000`                                        | ✓ PASS |
| `allinone` boots as one supervised process          | `timeout 20 runuser -u authentik -- /usr/bin/authentik allinone`                                          | boots to DB-pool init, metrics server on `[::]:9300`; graceful arbiter shutdown on SIGTERM | ✓ PASS |
| Image `run.sh` == committed `run.sh`                | `sha256sum /run.sh` vs `git show HEAD:authentik/run.sh`                                                    | both `d4c632a6e69ee858…` — byte-identical                                   | ✓ PASS |
| Scoped lint gate                                   | `pre-commit run --files authentik/Dockerfile authentik/run.sh`                                            | exit 0, 0 Failed                                                           | ✓ PASS |
| Full repo lint                                     | `make lint`                                                                                               | exit 0, 21/21 Passed, working tree unmodified                               | ✓ PASS |

### Requirements Coverage

No `REQUIREMENTS.md` IDs map to this quick item (`requirements-completed: []` in SUMMARY; no authentik build requirement
in `.planning/REQUIREMENTS.md`). No orphaned requirements found.

### Anti-Patterns Found

| File                   | Line | Pattern | Severity | Impact |
| ---------------------- | ---- | ------- | -------- | ------ |
| —                      | —    | none    | —        | —      |

No `TBD`/`FIXME`/`XXX` debt markers, no `TODO`/`HACK`/`PLACEHOLDER`, no placeholder prose, no stub/empty-return patterns
in either modified file. Both files are net-smaller (6+/11-); the change removes code rather than adding scaffolding.

### Deferred Items

| # | Item                                                                                            | Addressed In                                                          | Evidence                                                                                                                                                                                                     |
| - | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1 | Add-on installs on a HA host and authentik serves on :9000 against a live PostgreSQL/Valkey       | Declared follow-up: publish an authentik ghcr image, then add `image:` | PLAN.md `<verification>` explicitly excludes it ("needs a published image plus a real HA install"). Probe reached DB-pool init and stopped only for want of a live DB — the exact stage `run.sh` starts before `exec`. |

### Human Verification Required

N/A — Infrastructure/tooling phase (Dockerfile + container entrypoint, CI build fix) with no user-facing elements.
All acceptance criteria were verifiable programmatically, and the one behavior-dependent truth (truth 2, the supervised
single-process startup) was exercised behaviorally rather than accepted on symbol presence — so no
`PRESENT_BEHAVIOR_UNVERIFIED` carve-out applies.

### Deviation Assessment

**Declared deviation:** the executor deferred Task 1's commit until after Task 2's build passed, landing both files in
ONE commit (`dc544d1`) instead of the plan's two.

**Judgment: correct, and it matches the plan's intent rather than bending it.**

- Repo `CLAUDE.md` is explicit: *"Any Dockerfile change that modifies packages, base images, or build stages must be
  verified with a local `docker build` before committing and pushing. Do not commit untested Dockerfile changes."* A
  Task-1-first commit would have violated a standing project directive.
- The plan's own Task 1 text already required the two edits to land together: *"Both edits are one root cause; land them
  together so no commit leaves the image buildable but broken at runtime."* Two commits would have produced exactly the
  intermediate state the plan warned against.
- Task 2 is `<files>authentik/Dockerfile, authentik/run.sh (verified, not further modified)</files>` — it adds no code,
  so it had no content of its own to commit.
- Verified end state: `git diff --name-only 2c94feb..HEAD` = exactly the two planned files; `git rev-list --count` = 1.

The committed end state is byte-for-byte what the plan specified. Only commit granularity changed, and in the direction
CLAUDE.md mandates.

### Gaps Summary

None. All seven must-have truths hold against the codebase, verified independently of SUMMARY.md claims.

The load-bearing property — that the *committed* Dockerfile builds — was not taken on trust. The executor's kept image
(`localhost/authentik-addon-verify:2026.8.1`, `6b26b8cc1ebb`, 2.47 GB) proves only that *something* built, so the
committed tree was rebuilt independently: it exited 0 in 45 s and resolved to the **same image digest**, with the image's
`/run.sh` byte-identical (`sha256:d4c632a6…`) to `git show HEAD:authentik/run.sh`. That closes the gap between "the
executor built something" and "the committed change builds".

Scope held exactly: two files, no version bump, and — verified against full git history, not just the diff —
`authentik/config.yaml` has never contained an `image:` key. That absence matters operationally: an `image:` key on
authentik would make the HA Supervisor try to pull a reference that does not exist in ghcr yet, breaking installation.

Two secondary claims in the SUMMARY were also independently re-run rather than accepted: full `make lint` (21/21 Passed,
exit 0, tree unmodified) and the in-image binary probe. Both confirmed.

Verification-only side effect, disclosed: the rebuild created tag `localhost/authentik-reverify:2026.8.1` pointing at the
same image; it was untagged afterwards. The executor's `localhost/authentik-addon-verify:2026.8.1` was left in place, as
the SUMMARY's cleanup note intends. No repo file was modified by verification (`git status` identical before/after).

---

_Verified: 2026-09-09T17:12:00Z_
_Verifier: Claude (gsd-verifier)_
