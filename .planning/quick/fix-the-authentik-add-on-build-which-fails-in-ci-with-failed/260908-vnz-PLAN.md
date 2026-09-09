---
phase: quick-260908-vnz
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - authentik/Dockerfile
  - authentik/run.sh
autonomous: true

must_haves:
  truths:
    - "A local container build of authentik/Dockerfile against upstream 2026.8.1 with `BUILD_FROM`, `VERSION` and
      `BUILD_ARCH` set exactly as CI resolves them completes successfully — no `failed to compute cache key` error for
      any COPY source path. (CI passes nine build args at `.github/workflows/_build-template.yml` lines 157-166. These
      three are the only ones that reach the build graph or the arch label; the other six are git/workflow metadata
      consumed solely by the Dockerfile `LABEL` block, so omitting them cannot change whether the build succeeds.)"
    - "The add-on container starts authentik as a single supervised process that runs both the web/API server and the
      background worker."
    - "The add-on still drops privileges to the unprivileged `authentik` user (uid 1000) before executing the authentik
      binary — it never runs authentik as root."
    - "No reference to the upstream server executable that 2026.8.1 removed remains in either the add-on build
      definition or its startup script."
    - "The 18 upstream COPY source paths that were individually verified to still exist are all still copied — the fix
      removes exactly one COPY line, not more."
    - "The published add-on version is unchanged (no version bump) and authentik/config.yaml gains no pre-built-image
      key."
    - "`pre-commit run --files authentik/Dockerfile authentik/run.sh` exits 0 — shellcheck on the edited run.sh, the
      whitespace/EOF/line-ending fixers, and the two `always_run: true` repo gates (`validate-versions`,
      `validate-addon-config`) which fire regardless of file scoping, so the 3-file version-sync check is still
      enforced. Full `make lint` is run and its result reported, but it does NOT gate this fix."
  artifacts:
    - "authentik/Dockerfile — stale COPY line removed, preceding comment block corrected to describe the single upstream
      binary"
    - "authentik/run.sh — two-process startup replaced by one exec'd supervised process, comments corrected"
  key_links:
    - "authentik/Dockerfile COPY of /usr/bin/authentik (the Rust binary) → authentik/run.sh exec of that same path with
      the `allinone` subcommand. This is the binary contract that broke: the build copied a path upstream no longer
      ships, and the startup script invoked it."
    - "authentik/build.yaml `args.VERSION` (2026.8.1) → Dockerfile `FROM ghcr.io/goauthentik/server:${VERSION}` (stage
      1, the COPY source). VERSION must NOT change — the fix adapts the add-on to what 2026.8.1 ships, it does not move
      to a different upstream release."
    - "authentik/run.sh `runuser -u authentik` privilege drop → Dockerfile's uid-1000 `authentik` user + `chown` of
      /ak-root, /media, /certs. Collapsing two processes into one must not collapse the privilege drop."
---

<objective>
The authentik add-on image cannot be built. CI run 33640040380 (`Build Authentik`, 2026-09-02) failed with:

```
ERROR: failed to build: failed to solve: failed to compute cache key:
failed to calculate checksum of ref ...: "/usr/bin/authentik-server": not found
```

Upstream authentik 2026.8.1 (`ghcr.io/goauthentik/server:2026.8.1`) no longer ships a separate Go server executable. It
ships one Rust binary at `/usr/bin/authentik` carrying the subcommands `server`, `worker`, `allinone`, `proxy` and
`healthcheck` (verified by running the upstream image; `allinone` is documented upstream as "Run both the authentik
server and worker.").

Two files still assume the old two-binary layout: the Dockerfile copies the removed path (build-time failure) and run.sh
executes it (a latent runtime failure that the build error is currently hiding).

Purpose: make the add-on buildable again by adapting it to the layout upstream 2026.8.1 actually ships, and collapse the
startup to the one supervised process that is the correct shape for an HA add-on entrypoint.

Output: two edited files, proven by a real local container build that exits 0. </objective>

<execution_context> @~/.claude/gsd-core/workflows/execute-plan.md @~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@authentik/Dockerfile
@authentik/run.sh
@authentik/build.yaml
@authentik/config.yaml

Verified facts you do NOT need to re-derive (all probed inside the upstream image before this plan was written —
re-probing costs a 1.34 GB image pull for no new information):

- `/usr/bin/authentik-server` is MISSING from `ghcr.io/goauthentik/server:2026.8.1`.
  <!-- planner-discipline-allow: authentik-server -->
- `/usr/bin/authentik` is PRESENT (22 MB Rust binary). `authentik --help` lists `allinone`, `server`, `worker`, `proxy`,
  `healthcheck`.
- `runuser` is PRESENT in the HA base image `ghcr.io/home-assistant/amd64-base-debian:trixie`, at the absolute path
  `/usr/sbin/runuser`, provided by `util-linux`. Probed directly before this plan was written — this is a settled fact,
  not an open question, so nothing in this plan may halt on it. Note that `run.sh` invokes `runuser` by bare name today.
  That is pre-existing behaviour and it works, because run.sh runs under `#!/usr/bin/with-contenv bashio`, not a bare
  root `sh`. **Switching that invocation to the absolute path is a separate decision, NOT part of this fix — do not
  widen scope to change it.**
- All 18 other COPY source paths in authentik/Dockerfile were probed individually and all exist: `/usr/bin/authentik`,
  `/usr/local/bin/python3.14`, `/usr/local/bin/python3`, `/usr/local/bin/python`, `/usr/local/lib/libpython3.14.so.1.0`,
  `/usr/local/lib/libpython3.14.so`, `/usr/local/lib/libpython3.so`, `/usr/local/lib/python3.14`, `/ak-root`,
  `/authentik`, `/blueprints`, `/schemas`, `/web`, `/lifecycle`, `/locale`, `/geoip`, `/manage.py`, `/pyproject.toml`.
  **Do not change any of them.**
- Current file state: the stale COPY is authentik/Dockerfile line 29, its comment line 28; the two-process startup is
  authentik/run.sh lines 117-123 (last lines of the file).
- Baseline recorded 2026-09-08 before any edit: `make lint` (`pre-commit run --all-files`) exits 0 — all 21 hooks pass.
  `shellcheck -e SC1091 -e SC2034 authentik/run.sh` exits 0. Attribution caveat, which is why the _scoped_ form is the
  gate in Task 2 and full `make lint` is only reported: two of those 21 hooks (`verify-bridge-scaffold`,
  `verify-bridge-no-token-leak`) are `files: ^terraform-bridge/.*$` hooks that perform a real container build plus
  `docker run` of the unrelated `terraform-bridge` add-on. `--all-files` makes them fire even though this fix touches no
  terraform-bridge file, and they can go red from container-runtime or network state, or from the concurrent sibling
  batch item 260908-vny — none of which is attributable to these two edits. Only
  `pre-commit run --files authentik/Dockerfile authentik/run.sh` has clean attribution to this fix.
- That scoped form was pre-flighted on the unmodified files at plan-revision time and exits 0, with both
  terraform-bridge hooks reporting `Skipped (no files to check)`. So it is a known-green, known-cheap baseline: a
  non-zero exit after the edits is attributable to the edits.
- Why the gates use the asterisk-free `grep -vE '^(#|[[:blank:]]+#)'` form — history, not an active constraint. The
  repo's `prettier` pre-commit hook used to format every markdown file under `.planning/`, and its emphasis pass
  rewrote a matched pair of asterisk characters into underscores. On the first commit attempt that silently corrupted
  the comment-stripping regex in two of this plan's gates, turning the zero-or-more-blanks quantifier into a literal
  underscore and disabling the comment filter. **That hazard is now fixed at the source:** commit `120c55a` added
  `.planning/` to `.prettierignore`, so the hook no longer touches any file in this directory. The asterisk-free form
  stays because it was verified byte-identical in output to the quantifier form on both edited files — there is no
  reason to churn it back, and equally no reason to add further formatter workarounds. Do not treat prettier as an
  adversary when writing gates: asterisks are fine, and gate blocks need no defensive blank-line separation.
- `authentik/DOCS.md` line 26 ("Authentik worker | Background tasks, email delivery, scheduling") stays accurate — the
  worker still runs, inside the supervised process — and line 18 ("three processes": PostgreSQL, Valkey, authentik)
  becomes _more_ accurate after this change. **DOCS.md is deliberately NOT in scope. Do not edit it.**

Out of scope, explicitly (deliberate follow-ups, not oversights):

- Do NOT bump the authentik version. `config.yaml` stays `2026.8.1-0`, `build.yaml` stays `2026.8.1`.
- Do NOT add a pre-built-image key to authentik/config.yaml. No authentik image exists in ghcr yet; adding one is the
  follow-up once CI has published one. Sibling batch item 260908-vny handles that key for five _other_ add-ons and
  explicitly excludes authentik.
- Do NOT touch aarch64 (still commented out in both config.yaml and build.yaml).
</context>

<tasks>

<task type="tracer">
  <name>Task 1: Restore the upstream binary contract in both add-on files</name>
  <files>authentik/Dockerfile, authentik/run.sh</files>
  <precondition>Working directory is the repo root `/home/akentner/Projects/homeassistant-addons`, and `git diff --name-only HEAD -- authentik/` is empty before you start (no pre-existing uncommitted authentik edits to entangle with).</precondition>
  <action>
Thinnest complete path through both layers the failure spans — build-time binary layout and
run-time entrypoint. Both edits are one root cause; land them together so no commit leaves the
image buildable but broken at runtime.

**(a) authentik/Dockerfile — remove the stale COPY and fix its comment.**

Delete line 29, the `COPY --from=authentik-source` of the removed upstream server executable path
(`/usr/bin/authentik-server`), and rewrite the comment on line 28 that describes it.
<!-- planner-discipline-allow: authentik-server -->

The current comment block (lines 27-31) describes a two-binary layout: a nearly-static Go executable plus a separate
Rust one. After the edit the block must describe the single Rust binary that 2026.8.1 actually ships — one that carries
the `server`, `worker` and `allinone` subcommands and is dynamically linked against libpython3.14. Update the section
heading from plural to singular.

Both files contain exactly one occurrence of the `Go binary` phrasing, and both sit inside the regions this task
rewrites — Dockerfile line 28 here, run.sh line 117 in (b). Neither may survive the edit; the file-wide gate below
asserts exactly that, and is satisfiable precisely because there is no occurrence outside these two regions. Same shape
for the removed-executable path literal: all three of its occurrences (Dockerfile lines 28 and 29, run.sh line 119) are
inside the rewritten regions.
<!-- planner-discipline-allow: Go binary -->

Keep the surviving `COPY --from=authentik-source /usr/bin/authentik /usr/bin/authentik` line exactly as-is. Keep the
box-drawing (`──`) comment-banner style used throughout the file. Touch nothing else in the Dockerfile: not the apt
list, not the Python 3.14 runtime COPYs, not `ldconfig`, not the `/ak-root` venv COPY, not the app-file COPYs, not the
user creation, not `EXPOSE 9000 9443`, not `CMD ["/run.sh"]`, not the LABEL block.

**(b) authentik/run.sh — collapse the two-process startup to one supervised exec.**

Replace lines 117-123 (the whole trailing block: the backgrounded server invocation and the exec'd worker invocation,
plus both of their comment banners and both `bashio::log.info` lines) with a single supervised invocation:

```
exec runuser -u authentik -- /usr/bin/authentik allinone
```

preceded by one corrected comment banner and one `bashio::log.info` line describing what actually starts. `allinone`
runs both the server and the worker inside one supervised process, which is the correct shape for an HA add-on
entrypoint: the container's PID 1 lifecycle now tracks the whole application, and the orphaned-background-process
problem disappears (previously, if the exec'd worker died the backgrounded server was left unsupervised, and if the
server died nothing noticed).

Three invariants for this edit:

- The privilege drop stays. `runuser -u authentik --` must remain — authentik must not run as root. The Dockerfile
  creates that uid-1000 user and chowns /ak-root, /media and /certs to it.
- Exactly ONE process invocation remains in the file. No `&` backgrounding.
- Everything above line 117 is untouched: the Python venv exports, the bashio option reads, the persistent secret
  generation, the PostgreSQL init/start/wait/provision block, the Valkey start, every `AUTHENTIK_*` export, the email
  block, and the /data/media + /data/certs symlink setup. Those already-running PostgreSQL and Valkey daemons are
  unaffected by `exec` — the previous code also exec'd, so that lifecycle is unchanged by this plan.

Do not modify the shebang (`#!/usr/bin/with-contenv bashio`), the `# shellcheck shell=bash` directive, or `set -e`.

**Do not touch any file other than these two.** Specifically not config.yaml, not build.yaml, not DOCS.md, not
README.md, not CHANGELOG.md.

</action>

<verify>
<automated>! grep -q 'authentik-server' authentik/Dockerfile authentik/run.sh</automated>
<automated>! grep -q 'Go binary' authentik/Dockerfile authentik/run.sh</automated>
<automated>test "$(grep -vE '^(#|[[:blank:]]+#)' authentik/Dockerfile | grep -c 'COPY --from=authentik-source')" = "18"</automated>
    <automated>test "$(grep -vE '^(#|[[:blank:]]+#)' authentik/run.sh | grep -c 'runuser -u authentik')" = "1"</automated>
<automated>grep -vE '^(#|[[:blank:]]+#)' authentik/run.sh | grep -q 'exec runuser -u authentik -- /usr/bin/authentik allinone'</automated>
<automated>shellcheck -e SC1091 -e SC2034 authentik/run.sh</automated>
<automated>git diff --quiet HEAD -- authentik/config.yaml authentik/build.yaml authentik/DOCS.md authentik/README.md</automated>
</verify>

<done>
The stale
COPY line is gone and its comment block describes the single upstream binary. Exactly 18 `COPY --from=authentik-source`
lines remain. run.sh ends with one exec'd, privilege-dropped `allinone` invocation and no backgrounded process.
shellcheck passes with the repo's ignore set. config.yaml, build.yaml, DOCS.md and README.md are byte-identical to HEAD.

Note on the gates above: the two `!  grep` gates are file-wide on purpose — after this edit there is no legitimate
remaining occurrence of either literal in either file, and both currently match (3 and 2 hits respectively), so they are
load-bearing, not decorative. The two count gates filter comment lines so a reworded banner cannot satisfy or break them
by prose alone. </done> </task>

<task type="auto">
  <name>Task 2: Prove it with a real local container build, an in-image binary probe, and repo lint</name>
  <files>authentik/Dockerfile, authentik/run.sh (verified, not further modified)</files>
  <precondition>`podman` is on PATH (podman 6.1.0 confirmed on this host; `docker` here is a podman shim, so either name works), network egress to ghcr.io and deb.debian.org is available (the build pulls `ghcr.io/home-assistant/amd64-base-debian:trixie`, which is NOT yet in the local store, and runs `apt-get install`), and ~3 GB of free space exists in the container store (59 GB free at plan time).</precondition>
  <action>
This task adds no code. It is the load-bearing proof, mandated by repo CLAUDE.md: *"Any Dockerfile
change that modifies packages, base images, or build stages must be verified with a local
`docker build` before committing and pushing. Do not commit untested Dockerfile changes."*

**Build with the three CI build args that reach the build graph or the arch label.**
`.github/workflows/_build-template.yml` lines 157-166 pass nine args in total. It resolves `BUILD_FROM` from
`build.yaml`'s `build_from.amd64`, `VERSION` from `args.VERSION`, and `BUILD_ARCH` from the matrix arch — those three
are the ones reproduced here. The remaining six (`BUILD_DATE`, `BUILD_NAME`, `BUILD_DESCRIPTION`, `BUILD_REF`,
`BUILD_REPOSITORY`, `BUILD_VERSION`) are git and workflow metadata consumed only by the Dockerfile's `LABEL` block, so
omitting them cannot change whether the build succeeds — the build proof below is still a faithful reproduction of CI's
build:

```
BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:trixie
VERSION=2026.8.1
BUILD_ARCH=amd64
```

Run it detached with the output captured to a log outside the repo, and append the exit status as a greppable sentinel.
This build pulls a base image and installs PostgreSQL + Valkey, so it takes several minutes and emits thousands of apt
lines — it can exceed a single foreground command timeout, and dumping the log into context is pure waste. Use a
background invocation, then poll the log for the sentinel.

```bash
LOG="${TMPDIR:-/tmp}/authentik-build-260908-vnz.log"   # exactly this path — gate 1 reads it
podman build \
  --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:trixie \
  --build-arg VERSION=2026.8.1 \
  --build-arg BUILD_ARCH=amd64 \
  -t localhost/authentik-addon-verify:2026.8.1 \
  authentik/ > "$LOG" 2>&1
echo "BUILD_EXIT=$?" >> "$LOG"
```

Do not substitute a different log path — gate 1 below reads exactly `${TMPDIR:-/tmp}/authentik-build-260908-vnz.log`, so
writing anywhere else (a session scratchpad, the repo) makes the gate read a file that does not exist and report a false
failure.

When the sentinel appears, read only `tail -40 "$LOG"`. On failure,
`grep -nE 'ERROR|not found|error:' "$LOG" | tail -20` to locate the failing step — do not cat the whole log.

**Then probe the built image** for the runtime contract, overriding the entrypoint so the HA base image's init does not
start:

```bash
podman run --rm --entrypoint /bin/sh localhost/authentik-addon-verify:2026.8.1 -c \
  'test -x /usr/bin/authentik && test -x /usr/sbin/runuser && /usr/bin/authentik --help' 2>&1 | grep -q allinone
```

This proves three things at once inside the artifact CI will build: the Rust binary is present and executable,
`/usr/sbin/runuser` is present and executable so the privilege drop in run.sh has something to call, and the binary
really exposes the `allinone` subcommand this plan's entrypoint depends on.

Two deliberate properties of the `runuser` half of that probe:

- **It is path-based (`test -x /usr/sbin/runuser`), not PATH-based.** A `command -v runuser` here would resolve against
  the PATH of this ad-hoc plain-root `sh`, which is not the environment `run.sh` actually starts in
  (`#!/usr/bin/with-contenv bashio`). It would therefore be measuring the wrong environment and could report a false
  negative about a binary that is in fact present.
- **It is a regression tripwire, not an open question, so it does NOT halt.** `/usr/sbin/runuser` was already probed
  directly in `ghcr.io/home-assistant/amd64-base-debian:trixie` and confirmed present (from `util-linux`) before this
  plan was written. If it ever fails, record that in the SUMMARY and continue — do not stop the task on it, and do NOT
  improvise a substitute privilege-drop mechanism (`su`, `gosu`, `setpriv`, `USER authentik`); swapping that mechanism
  is a design decision for the user, not a silent repair inside a build-fix task. Equally, do not "fix" run.sh's
  bare-name `runuser` call into an absolute path — that is pre-existing, working, and out of scope.

**Then lint — the scoped run is the gate, the full run is reported.**

The GATE is `pre-commit run --files authentik/Dockerfile authentik/run.sh`. It must exit 0.

Despite the narrow `--files` scope it still covers everything that can see this fix. This was pre-flighted on the
unmodified files at plan-revision time (exit 0), and these hooks reported `Passed` — i.e. they really do run under the
scoped form, they are not silently skipped: `shellcheck`, `Lint Dockerfiles` (hadolint, on authentik/Dockerfile),
`trim trailing whitespace`, `fix end of files`, `mixed line ending`, `check that scripts with shebangs are executable`,
plus both `always_run: true` local hooks `Validate Add-on Versioning` and `Validate Add-on config.yaml Schema`, which
pre-commit runs regardless of file scoping — so the repo's 3-file version-sync check is still enforced here and a stray
version edit would still be caught.

The scoped form loses no authentik-relevant coverage. In the same pre-flight, `terraform-bridge scaffold verify` and
`terraform-bridge no-token-leak` both reported `Skipped (no files to check)` — which is the entire point. And
`Validate Dockerfile ARG-before-FROM scope` is scoped `files: ^(phone-logger|meridian|iac-runner)/Dockerfile$`, so it
never applies to `authentik/Dockerfile` under _either_ form; scoping does not hide it.

ALSO run full `make lint` (= `pre-commit run --all-files`) and report its outcome in the SUMMARY, but do NOT gate this
item on it. **This is not a cheap check, and nobody reading this later should mistake it for one:** it executes all 21
hooks, two of which — `verify-bridge-scaffold` and `verify-bridge-no-token-leak` — are `files: ^terraform-bridge/.*$`
hooks whose entry scripts perform a real container build plus `docker run`/`docker exec` of the unrelated
`terraform-bridge` add-on (image-size assertion, SIGTERM drain, SIGHUP reopen, token-leak assertions). Under
`--all-files` they fire even though this fix touches no terraform-bridge file. They need a working container runtime and
network and take minutes, and they can go red from terraform-bridge state, from runtime state, or from the concurrent
sibling batch item 260908-vny (which touches YAML and Markdown elsewhere) — none of which says anything about whether
this build fix is correct.

So: if full `make lint` fails, record the failing hook and file in the SUMMARY and move on. Fix it only if the failure
is in `authentik/Dockerfile` or `authentik/run.sh` — in which case the scoped gate above would have caught it too.

Note what this scoping does NOT relax: the local container build above stays the load-bearing gate of this plan, exactly
as repo CLAUDE.md requires. Narrowing the lint gate must not turn the build into an optional step.

**Finally, confirm scope.** `git diff --name-only HEAD -- authentik/` must list exactly the two edited files and nothing
else.

The verification image can be removed afterwards with `podman rmi localhost/authentik-addon-verify:2026.8.1` — optional;
keeping it costs ~2 GB and speeds up a re-check.

</action>

<verify>
<automated>grep -q 'BUILD_EXIT=0' "${TMPDIR:-/tmp}/authentik-build-260908-vnz.log"</automated>
<automated>podman run --rm --entrypoint /bin/sh localhost/authentik-addon-verify:2026.8.1 -c 'test -x /usr/bin/authentik && test -x /usr/sbin/runuser && /usr/bin/authentik --help' 2>&1 | grep -q allinone</automated>
<automated>pre-commit run --files authentik/Dockerfile authentik/run.sh</automated>
<automated>CHANGED="$(git diff --name-only HEAD -- authentik/)" && test "$(printf '%s\n' "$CHANGED" | sort | paste -sd, -)" = "authentik/Dockerfile,authentik/run.sh"</automated>
</verify>

<done>
The local build exits 0 — this is the single
load-bearing criterion of the whole plan; it is the same failure mode CI hit, reproduced green locally with CI's own
build-graph args. The built image contains an executable `/usr/bin/authentik` that advertises `allinone`, and
`/usr/sbin/runuser` is present and executable for the privilege drop. The scoped lint gate
`pre-commit run --files authentik/Dockerfile authentik/run.sh` exits 0. Exactly two files differ from HEAD under
`authentik/`.

Full `make lint` was also run and its outcome recorded in the SUMMARY, but it is reported, not gated: under
`--all-files` two of the 21 hooks container-build the unrelated `terraform-bridge` add-on, so a red there is not
attributable to this fix. </done> </task>

</tasks>

<threat_model>

## Trust Boundaries

| Boundary                               | Description                                                                                                                                                                                      |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| upstream registry → add-on image build | `ghcr.io/goauthentik/server:${VERSION}` is a third-party image whose filesystem is copied wholesale into the shipped add-on (19 → 18 COPY instructions, including `/ak-root` and all app files). |
| container PID 1 → authentik process    | run.sh runs as root (bashio, PostgreSQL init, chown) and must hand the application off to an unprivileged uid. This plan rewrites exactly that hand-off.                                         |

## STRIDE Threat Register

ASVS level 1, blocking threshold `high`.

| Threat ID | Category                 | Component                                    | Severity | Disposition | Mitigation Plan                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| --------- | ------------------------ | -------------------------------------------- | -------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T-vnz-01  | Elevation of Privilege   | `authentik/run.sh` startup hand-off          | high     | mitigate    | The rewrite collapses two invocations into one; dropping `runuser -u authentik --` in the process would run the IdP as root. Task 1 gate asserts exactly one non-comment `runuser -u authentik` line remains AND that it is the exec'd `allinone` line; Task 2 probes `test -x /usr/sbin/runuser` in the built image as a regression tripwire (that path was already confirmed present, from `util-linux`, before planning — so the probe reports rather than halts, and an improvised substitute mechanism is forbidden either way). |
| T-vnz-02  | Tampering (supply chain) | `FROM ghcr.io/goauthentik/server:${VERSION}` | medium   | accept      | The upstream image is referenced by mutable tag, not digest. This is the pre-existing repo-wide pattern and is load-bearing for the `.upstream.yaml` auto-update system, which rewrites `args.VERSION` on every upstream release; digest pinning would break that automation. Unchanged by this plan (no version bump), below the `high` blocking threshold, and a deliberate follow-up rather than an oversight.                                                                                                                     |
| T-vnz-03  | Denial of Service        | container supervision                        | medium   | mitigate    | The removed two-process shape left an unsupervised orphan on either process's death (backgrounded server survived a dead worker; a dead server went unnoticed). The single `exec`'d `allinone` process makes container exit track application exit, so the HA Supervisor's restart policy applies. This is the fix itself, not extra work.                                                                                                                                                                                            |
| T-vnz-04  | Information Disclosure   | local build log                              | low      | accept      | The build log is written outside the repo (`${TMPDIR:-/tmp}/…`) and never committed. All three build args are non-secret (a public base image ref, a version string, an arch string); no credentials are passed to the build.                                                                                                                                                                                                                                                                                                         |
| T-vnz-SC  | Tampering                | npm/pip/cargo installs                       | n/a      | accept      | No package-manager install is added or changed by this plan. The Dockerfile's `apt-get install` list is untouched and no npm/pip/cargo install exists in either edited file, so the package-legitimacy gate does not fire and no RESEARCH.md audit table is required.                                                                                                                                                                                                                                                                 |

## Non-goal guard (security-relevant)

Adding a pre-built-image key to `authentik/config.yaml` would make the HA Supervisor pull an image that does not exist
in ghcr yet, leaving the add-on uninstallable. Explicitly excluded from this plan and gated:
`git diff --quiet HEAD -- authentik/config.yaml` in Task 1. </threat_model>

<verification>
Run from the repo root, in order:

1. `! grep -q 'authentik-server' authentik/Dockerfile authentik/run.sh` — stale path fully gone.
   <!-- planner-discipline-allow: authentik-server -->
2. `test "$(grep -vE '^(#|[[:blank:]]+#)' authentik/Dockerfile | grep -c 'COPY --from=authentik-source')" = "18"` —
   exactly one COPY removed.
3. `test "$(grep -vE '^(#|[[:blank:]]+#)' authentik/run.sh | grep -c 'runuser -u authentik')" = "1"` — one
   privilege-dropped invocation.
4. `shellcheck -e SC1091 -e SC2034 authentik/run.sh` — repo's shell gate.
5. **The local container build exits 0** with `BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:trixie`,
   `VERSION=2026.8.1`, `BUILD_ARCH=amd64` — the three of CI's nine build args that reach the build graph or the arch
   label. This is the criterion that actually decides whether the plan succeeded, and repo CLAUDE.md mandates it for any
   Dockerfile change; every textual gate above is a cheap guard against a wrong-shaped edit that would still build.
6. In-image probe: `/usr/bin/authentik` executable, `/usr/sbin/runuser` executable, `--help` mentions `allinone`. The
   `runuser` half is a tripwire on a already-confirmed fact — report, never halt.
7. `pre-commit run --files authentik/Dockerfile authentik/run.sh` exits 0. **This is the lint gate.** Full `make lint`
   is run and reported but NOT gated — under `--all-files` two of its 21 hooks container-build the unrelated
   `terraform-bridge` add-on, so its result is not attributable here.
8. `git diff --name-only HEAD -- authentik/` lists exactly `authentik/Dockerfile` and `authentik/run.sh`.

Deliberately NOT verified here: live add-on installation on a HA host, and authentik actually serving on :9000. Those
need a published image plus a real HA install; the follow-up that adds the pre-built-image key is the natural place for
that empirical check. </verification>

<success_criteria>

- The authentik image builds locally from an unmodified `authentik/build.yaml` version (2026.8.1) with CI's three
  build-graph/arch-label args (`BUILD_FROM`, `VERSION`, `BUILD_ARCH`), exit 0.
- `authentik/Dockerfile` copies the 18 upstream paths that exist and none that do not.
- `authentik/run.sh` starts authentik as one exec'd, unprivileged, supervised `allinone` process.
- No version bump; no pre-built-image key; no aarch64 change; no docs edits.
- `pre-commit run --files authentik/Dockerfile authentik/run.sh` exits 0 (the lint gate); full `make lint` run and its
  result reported, not gated.
- Exactly two files changed. </success_criteria>

<output>
Create `.planning/quick/fix-the-authentik-add-on-build-which-fails-in-ci-with-failed/260908-vnz-SUMMARY.md` when done.

Record in the summary: the build's total wall time and exit status, the `tail` of the build log proving success, the
in-image probe output (confirming `allinone` is advertised and `/usr/sbin/runuser` is executable), the scoped lint
gate's result, the full `make lint` result reported separately as non-gating (naming the failing hook and file if it
went red), and the exact `git diff --stat` for `authentik/`. Note explicitly that the version was NOT bumped and no
pre-built-image key was added, so the follow-up that publishes an authentik image remains open. Note as still-open
follow-ups, deliberately untouched here: run.sh's bare-name `runuser` invocation, and digest-pinning of the upstream
`FROM` tag (T-vnz-02). </output>
