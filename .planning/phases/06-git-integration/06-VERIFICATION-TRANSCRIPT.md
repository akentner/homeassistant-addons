# Phase 6 Plan 2: GIT-01..05 Verification Transcript

**Verifier:** `.planning/phases/06-git-integration/verify-git-integration.sh` **Image:** `local/markdown-renderer:1.1.0`
**Runtime:** podman 5.8.3 **Date:** 2026-06-28

## Verifier Output (verbatim)

```text
Using container runtime: podman
Image found: local/markdown-renderer:1.1.0

━━━ SCENARIO A — startup pull refreshes repo before nginx (GIT-01) ━━━
  PASS container started and nginx is serving (Scenario A fixture)
  PASS GIT-02: 'git config --global --add safe.directory *' ran at startup
  PASS GIT-01: pulled file content present on disk inside container
  PASS GIT-01: GET /test-repo/newfile-A.md returns HTTP 200
  PASS GIT-01: git pull invocations or success indicators in logs

━━━ SCENARIO B — unreachable git remote is non-blocking (GIT-05) ━━━
  PASS container stayed running despite unreachable git_url
  PASS GIT-05: git pull failure logged as WARNING
  PASS GIT-05: /test-repo/ serves locally cached content (Docsify SPA)

━━━ SCENARIO C — no git invocation when git_pull disabled (GIT-03) ━━━
  PASS container started (no git sync configured)
  PASS GIT-03: no 'git pull' or 'git clone' invocations in logs
  PASS GIT-03: no git processes running inside container

━━━ SCENARIO D — periodic background sync updates content (GIT-04) ━━━
  PASS container started with git_pull_interval=5 (no startup pull)
  PASS GIT-04: periodically-pulled file content present on disk inside container
  PASS GIT-04: GET /test-repo/newfile-D.md returns HTTP 200
  PASS GIT-04: 4 git pull invocations in logs (periodic loop ran)

━━━ SCENARIO E — first-time clone via file:// git_url (D-02) ━━━
  PASS container started with empty (non-repo) namespace path
  PASS D-02: .git/ directory exists in not-a-repo after startup (clone succeeded)
  PASS D-02: /not-a-repo/ serves content cloned from file:// git_url

══════════════════════════════════════════════════════
  ALL VERIFICATIONS PASSED  (18 assertions)
══════════════════════════════════════════════════════
```

Exit code: **0**. `make check-all` exits 0.

## Bugs Fixed During Verification

Three correctness bugs surfaced from the empirical verifier (none of which would have been caught by static review
alone). All fixes follow deviation Rule 1 (Bug auto-fix); each is necessary for the add-on to work correctly in
production.

### 1. `run.sh` aborts with `fatal: $HOME not set` on first line

- **Found during:** Scenario A first run.
- **Symptom:** Container exited immediately with `fatal: $HOME not set` from the
  `git config --global --add safe.directory '*'` line. The HA base image
  (`ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20`) does not export `$HOME` by default.
- **Fix:** Added `export HOME=/root` as the first executable line of `run.sh`, before the `git config --global` call.
  The comment explains why HOME is needed (git writes to `$HOME/.gitconfig`).
- **Files modified:** `markdown-renderer/run.sh` (1 added line + comment).
- **Verification:** All 5 scenarios start cleanly;
  `podman exec mr-git-test sh -c 'git config --global --get-all safe.directory'` returns `*`.

### 2. `Dockerfile` does not COPY `_git_sync.py` into the image

- **Found during:** Scenario A first run (after the HOME fix).
- **Symptom:** Container exited with `python3: can't open file '/app/_git_sync.py': [Errno 2] No such file or directory`
  even though `run.sh` invokes it. The Dockerfile's `COPY` line was unchanged from Phase 5 and only included
  `run.sh generate_nginx.py`.
- **Fix:** Added `_git_sync.py` to the `COPY` line and to the `chmod a+x` invocation so the new helper is present and
  executable in the built image.
- **Files modified:** `markdown-renderer/Dockerfile` (1 line extended).
- **Verification:** `podman run --rm local/markdown-renderer:1.1.0 ls /app/_git_sync.py` shows the file present.

### 3. `_git_sync.py` captures git output but never surfaces it

- **Found during:** Scenario A first run (after the Dockerfile fix).
- **Symptom:** Git pull ran successfully (new file was on disk) but container logs contained no "git pull" /
  "Fast-forward" / "Already up to date" line because `subprocess.run(..., capture_output=True, ...)` swallowed git's
  stdout. The plan's verifier explicitly required "log contains success indicator" — without surfacing git's output,
  that assertion is structurally impossible.
- **Fix:** Both `_git_pull` and `_git_clone` now print an `INFO: git ...: <git stdout>` line after a successful
  invocation (failures still print `WARNING:` as before, per D-07/GIT-05). This makes pull invocations visible in HA
  Supervisor logs without changing the GIT-05 non-blocking contract (failures still log only warnings).
- **Files modified:** `markdown-renderer/_git_sync.py` (~10 lines added).
- **Verification:** Scenario A and D log lines include `INFO: git pull for <path>: Already up to date.` / `Fast-forward`
  markers; Scenario C correctly shows zero matches (no INFO/WARNING about git pull/clone).

## Test Reproducibility

Re-run the verifier after rebuilding:

```bash
make build-addon ADDON=markdown-renderer   # uses local/markdown-renderer:1.1.0
bash .planning/phases/06-git-integration/verify-git-integration.sh
```

Both runs in this transcript finished with exit code 0 and `ALL VERIFICATIONS PASSED (18 assertions)`.
