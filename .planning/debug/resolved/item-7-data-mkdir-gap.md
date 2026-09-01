---
status: resolved
trigger: "item 7 from CI-red-on-main diagnosis: /data mkdir / no-token-leak gap in terraform-bridge"
created: 2026-09-01
updated: 2026-09-01
---

# Debug Session: item-7-data-mkdir-gap

## Symptoms

**Expected behavior:**
`terraform-bridge/cmd/bridge/main.go` calls `NewFileTokenStore("/data")`. Under real HA Supervisor
deployment, Supervisor auto-provisions `/data` for every add-on, so the token store should be able
to write its token file there without any explicit `mkdir`.

**Actual behavior:**
Unclear whether the bridge itself guarantees `/data` exists (defense-in-depth), or whether it
silently relies entirely on Supervisor's provisioning. Separately,
`internal/verify-bridge-no-token-leak.sh` runs the bridge container via a plain `docker run` with
no `-v` volume mount, so `/data` does not exist in that test context — unknown whether the verify
script currently passes only by coincidence (e.g. token store falls back / creates the dir itself)
or whether it's silently failing to exercise the real write path.

**Error messages:**
None captured yet — not yet reproduced/inspected this session.

**Timeline:**
Surfaced 2026-09-01 during a CI-red-on-main investigation. Split into two tracks: items 1-6
(mechanical lint/shellcheck/actionlint fixes + 2 real bugs) were completed and committed via
`/gsd:quick` this session (commits `5f85217`, `6366bb8`, `87dc714`). Item 7 was deliberately
deferred to `/gsd:debug` per the user's original explicit split (mechanical fixes vs. this
production-risk question).

**Reproduction:**
1. Read `terraform-bridge/cmd/bridge/main.go` — confirm exact call site and any existing
   `/data` provisioning (or lack thereof).
2. Read `terraform-bridge/internal/auth/token.go`'s `NewFileTokenStore` constructor — does it
   `mkdir -p` its own directory, or does it assume the directory already exists and error/fail
   silently if not?
3. Read `internal/verify-bridge-no-token-leak.sh` — confirm it runs `docker run` without a `-v`
   mount for `/data`, and check what the script currently asserts/how it currently passes.
4. Determine: (a) is this a real HA Supervisor production risk, (b) is this purely a
   test-harness gap in the verify script, or (c) both — and what the minimal correct fix is.

## Current Focus

reasoning_checkpoint_2:
  hypothesis: "The verify-bridge-no-token-leak.sh docker run never provides an environment where ResolveBindAddress(\"auto\", ...) can succeed (no --network host, no Tailscale interface anywhere in a GitHub Actions runner) or an explicit-IP fallback (/data/options.json is never populated), so the bridge always calls os.Exit(1) at bind_resolution_failed before it can ever reach the token store — the true, current root cause of the verify-bridge-no-token-leak CI failure."
  confirming_evidence:
    - "Local reproduction (no docker) via unshare -m + bind-mounting an empty dir over /sys/class/net, then running the actual compiled bridge binary with SUPERVISOR_TOKEN set: process logs bind_resolution_failed (no tailscale* interface found) and os.Exit(1)s, identical shape to what an isolated docker-run container would see."
    - "main.go code order (lines 60-79): ResolveBindAddress runs and can fatal-exit strictly before NewFileTokenStore is ever called — confirms token-store code, including the just-applied MkdirAll fix, is unreachable in this failure mode."
    - "git log: commit 680a1bf deliberately flipped config.yaml host_network:true for production Tailscale detection but never updated the verify script's docker run to add --network host or otherwise supply a working bind_address for the test context."
    - "GitHub Actions ubuntu-latest runners do not have Tailscale installed/connected, so even adding --network host to the docker run would not provide a tailscale* interface — the auto-detection path can never succeed in this CI environment regardless of network mode."
  falsification_test: "If this hypothesis is right, giving the bridge an explicit non-auto bind_address (via a real /data/options.json mounted into the container) that satisfies ResolveBindAddress's explicit-IP + bind_allowed_subnets path (e.g. 127.0.0.1 + 127.0.0.0/8) will let the process get past bind resolution and reach NewFileTokenStore/token generation — INITIAL_TOKEN will be readable and the hook should pass."
  fix_rationale: "Root cause is a test-harness/production-parity mismatch: the verify script simulates neither Supervisor's host networking nor a Tailscale-equipped host, so bind_address=auto can never resolve inside it. The minimal, correct fix is to give the test container a real /data (bind-mounted host tmp dir, also resolves the original item-7 question in passing) containing an options.json with an explicit bind_address + bind_allowed_subnets that ResolveBindAddress's already-tested explicit-IP code path accepts — no production code change, no config.yaml change, and the GET / check must then run via `docker exec ... curl` (in-namespace) since the process now binds to loopback-only, not to an externally-reachable interface reachable through -p port mapping. This does not touch bind.go/main.go and does not weaken the invariants under test (SUPERVISOR_TOKEN/Bearer/bridge_token absence, plaintext absence, OPS-01 record) — it only fixes how the test container is started so the bridge can start up at all."
  blind_spots: "Still no local docker to fully verify end-to-end before pushing; relying on a second CI round-trip via the same throwaway branch (not main) to confirm. Have not verified whether the HA base image's curl binary is present in the exact same base image tag used here beyond the upstream Dockerfile reference already inspected (reasonable confidence, not 100% certain until CI confirms exec curl works inside the container)."
next_action: "Update internal/verify-bridge-no-token-leak.sh to mount a real /data host tmpdir with an options.json bind override, drop the now-misleading -p mapping, and exec curl inside the container's namespace for the GET / check; then re-run CI on the same throwaway branch to confirm both the original mkdir fix and this test-harness fix together produce a PASS."

reasoning_checkpoint:
  hypothesis: "NewFileTokenStore(dataDir) never creates dataDir (no os.MkdirAll). Persist/Rotate/WriteInitialTokenFile all call os.CreateTemp(s.dataDir, ...), which fails with ENOENT if dataDir does not already exist. The HA base image (ghcr.io/home-assistant/amd64-base:3.24, from home-assistant/docker-base) does not create /data, and the verify script's plain `docker run` has no -v mount for /data either — so on first start inside that test container, the very first Persist()/WriteInitialTokenFile() call fails, main.go logs token_persist_failed/token_file_write_failed and os.Exit(1)s, and `docker run --rm` immediately removes the crashed container. This is the direct, current cause of the `verify-bridge-no-token-leak` pre-commit hook failing in CI on main."
  confirming_evidence:
    - "token.go: NewFileTokenStore (lines 86-108) never calls os.MkdirAll; only os.ReadFile against tokenPath/gracePath. Persist (128-162), WriteInitialTokenFile (174-202), and Rotate (331-412) all call os.CreateTemp(s.dataDir, ...) which requires dataDir to pre-exist."
    - "main.go line 75: auth.NewFileTokenStore(\"/data\") — no os.MkdirAll(\"/data\", ...) anywhere in cmd/bridge before or after this call."
    - "config.yaml `map:` section only lists `app_config -> /app_config`; no explicit /data entry — consistent with HA convention that /data is Supervisor's implicit per-addon storage, not something add-ons declare via `map`."
    - "Dockerfile FROM ghcr.io/home-assistant/amd64-base:3.24; fetched upstream home-assistant/docker-base alpine/Dockerfile via curl — greps for data/mkdir/VOLUME/WORKDIR show only /etc/fix-attrs.d and /etc/services.d created; no /data directory and no VOLUME /data declared in the base image."
    - "verify-bridge-no-token-leak.sh line 58-60: `docker run --rm -d ... -p 8124:8124 \"${IMAGE_NAME}\"` — no `-v` flag, so /data does not exist inside that container either."
    - "LIVE CI REPRODUCTION: `gh run view 33524244697` (Lint job, main branch, latest push) — `verify-bridge-no-token-leak` hook FAILED with `FAIL: could not read /data/initial-token from running container` immediately followed by `Error response from daemon: No such container: terraform-bridge-leak-test` — i.e. the container had already exited/been auto-removed (`docker run --rm`) before the script's own `docker logs` fallback could even run. This is exactly the crash-on-missing-/data signature, observed directly in production CI, not inferred."
  falsification_test: "If NewFileTokenStore already handled a missing dataDir gracefully, the container would stay alive long enough for `docker exec ... cat /data/initial-token` to succeed, or at minimum `docker logs` would still return output (container still present) instead of 'No such container'. The CI log shows the container is already gone — consistent only with a fast crash-and-remove, not a slow/other failure mode."
  fix_rationale: "The root cause is the token store's implicit assumption that its own dataDir already exists. The correct, minimal fix is defense-in-depth at the source: NewFileTokenStore should os.MkdirAll(dataDir, 0o700) before doing anything else. This removes the implicit contract on ALL callers (main.go today, any future caller/test), works correctly whether /data is Supervisor-bind-mounted (real prod — dockerd auto-creates bind-mount target dirs, so this is normally a no-op) or absent (verify script, local/dev/test contexts) — MkdirAll is idempotent and safe either way. This is NOT a symptom patch (e.g. changing the verify script to skip the check) — it fixes the actual code path that crashes."
  blind_spots: "Have not yet run a live docker build/run locally to observe the fix taking effect (no local docker binary in this WSL2 environment per session notes) — verification will rely on re-running the actual CI job (gh workflow re-run) or pushing a throwaway branch, per the debug session's existing constraint. Have not exhaustively confirmed Supervisor's bind-mount always precedes container start for /data specifically (vs. other Supervisor-managed mounts) — relying on well-established HA developer docs + community consensus that /data is unconditionally provisioned for every add-on, not on reading Supervisor's Python source directly."
next_action: "Apply fix: add os.MkdirAll(dataDir, 0o700) as the first statement in NewFileTokenStore (token.go); then verify via CI re-run (push to a throwaway branch or re-trigger workflow_dispatch) since no local docker is available."

## Evidence

- timestamp: 2026-09-01T investigating
  checked: terraform-bridge/internal/auth/token.go (NewFileTokenStore, Persist, WriteInitialTokenFile, Rotate)
  found: NewFileTokenStore never creates dataDir; only reads tokenPath/gracePath via os.ReadFile (ENOENT for a missing file OR a missing parent dir both surface identically as ErrNoToken, so construction "succeeds" even when dataDir is absent). Persist/WriteInitialTokenFile/Rotate all call os.CreateTemp(s.dataDir, ...), which requires dataDir to already exist and returns an ENOENT-class error otherwise.
  implication: First real write (first-start Persist/WriteInitialTokenFile in main.go) is where a missing /data actually surfaces as a hard failure — not at construction time.

- timestamp: 2026-09-01T investigating
  checked: terraform-bridge/cmd/bridge/main.go (call site, lines 74-107)
  found: Calls auth.NewFileTokenStore("/data") directly; no os.MkdirAll("/data", ...) anywhere before or after. On first-start (store.Hash() == nil), calls store.Generate() -> store.Persist(token) -> store.WriteInitialTokenFile(token) in sequence; any error from Persist or WriteInitialTokenFile logs and os.Exit(1)s.
  implication: main.go has zero defense against a missing /data — it relies entirely on the environment (Supervisor or test harness) to have already created the directory.

- timestamp: 2026-09-01T investigating
  checked: terraform-bridge/config.yaml (map section) + upstream home-assistant/docker-base alpine/Dockerfile (fetched via curl)
  found: config.yaml's `map:` only declares `app_config -> /app_config`, no /data entry (consistent with HA's documented convention that /data is Supervisor's implicit, always-provisioned per-addon storage, not something add-ons opt into via `map`). The HA base image itself (ghcr.io/home-assistant/amd64-base:3.24) does NOT create /data or declare VOLUME /data — confirmed by grepping the fetched upstream Dockerfile for data/mkdir/VOLUME/WORKDIR (only /etc/fix-attrs.d and /etc/services.d are created).
  implication: In real Supervisor deployment, /data is expected to be bind-mounted by Supervisor before the container starts (dockerd auto-creates bind-mount target paths), so production should be fine. But nothing in the image or in config.yaml itself guarantees /data — the guarantee is entirely external (Supervisor's runtime behavior), which is not something this repo can directly verify/enforce, making in-code defense-in-depth worthwhile.

- timestamp: 2026-09-01T investigating
  checked: internal/verify-bridge-no-token-leak.sh (docker run invocation, lines 58-60)
  found: `docker run --rm -d --name ... -e SUPERVISOR_TOKEN=... -p 8124:8124 "${IMAGE_NAME}"` — no `-v` flag at all, so /data does not exist inside the test container (neither bind-mounted nor present in the image).
  implication: The verify script does not simulate Supervisor's /data provisioning — it is a real test-harness gap, but it also happens to be what exposed the underlying application-code gap (missing mkdir) that would otherwise stay latent/untested.

- timestamp: 2026-09-01T investigating
  checked: Live CI — `gh run list --branch main` then `gh run view 33524244697 --log` (Lint job, latest push to main, commit ef3ad49)
  found: "terraform-bridge no-token-leak" pre-commit hook FAILS with exit code 1. Output: `FAIL: could not read /data/initial-token from running container` immediately followed by `Error response from daemon: No such container: terraform-bridge-leak-test` — meaning by the time the script tried its `docker logs` fallback, the container (started with `--rm`) had already exited and been auto-removed by Docker.
  implication: Direct, current, reproducible confirmation of the crash-on-missing-/data hypothesis. This is not a hypothetical latent risk — it is the actual, present cause of CI being red on main today (item 7 of the original CI-red-on-main diagnosis is confirmed, not just theorized).

## Eliminated

- hypothesis: "The missing os.MkdirAll(dataDir) in NewFileTokenStore is the cause of the verify-bridge-no-token-leak CI failure (\"could not read /data/initial-token\")"
  evidence: |
    Applied the MkdirAll fix, pushed it to a throwaway branch (debug/item-7-data-mkdir-gap-verify,
    never touching main), and re-ran the Lint workflow via `gh workflow run lint.yml --ref
    debug/item-7-data-mkdir-gap-verify` (run 33525220428). The verify-bridge-no-token-leak hook
    FAILED IDENTICALLY: "FAIL: could not read /data/initial-token from running container" /
    "Error response from daemon: No such container". The fix had zero effect on the observed
    failure, which falsifies the mkdir-only hypothesis as the cause of THIS CI failure.

    Root-caused further: main.go calls auth.ResolveBindAddress(opts.BindAddress, ...) BEFORE
    auth.NewFileTokenStore("/data") is ever reached. bind_address defaults to "auto", which
    requires a literal `tailscale*` interface under /sys/class/net (bind.go's firstTailscaleIP).
    Reproduced locally (no docker needed) via `unshare -m` + bind-mounting an empty directory
    over /sys/class/net, then running the actual compiled bridge binary with SUPERVISOR_TOKEN
    set: it immediately logged `{"level":"ERROR","msg":"bind_resolution_failed",...,"err":"auth:
    auto-detect Tailscale interface: no tailscale* interface found in /sys/class/net"}` and
    exited 1 — BEFORE ever calling NewFileTokenStore. The verify script's plain `docker run`
    (no --network host, no Tailscale daemon/interface anywhere in a GitHub Actions runner) hits
    this exact path. "/data/initial-token" is never written not because /data is missing, but
    because the process crashes on the bind-address check several lines earlier — the error
    message in the verify script is a misleading downstream symptom of a completely different,
    earlier failure.

    Also found (via git log) that commit 680a1bf ("fix(terraform-bridge): host network + redact
    token log") flipped config.yaml's `host_network: true` specifically so bind_address=auto
    could detect Tailscale on the HOST interface under real Supervisor deployment — but never
    updated verify-bridge-no-token-leak.sh's `docker run` invocation to match (still plain bridge
    network, no --network host, and no Tailscale interface exists on a CI runner regardless of
    network mode).
  timestamp: 2026-09-01T (post-fix CI verification round)

## Resolution

root_cause: |
  TWO layered issues, discovered in sequence:

  1. (Real, but NOT the cause of the observed CI failure) terraform-bridge/internal/auth/token.go's
     NewFileTokenStore(dataDir) never ensured dataDir existed on disk (no os.MkdirAll). All
     subsequent writes (Persist, WriteInitialTokenFile, Rotate) use os.CreateTemp(s.dataDir, ...),
     which requires the directory to already exist. This is a genuine defense-in-depth gap, fixed,
     but proven (via a throwaway-branch CI round-trip) to have ZERO effect on the actual observed
     failure — the token-store code was never even reached.

  2. (The ACTUAL, confirmed root cause of the CI failure) main.go calls
     auth.ResolveBindAddress(opts.BindAddress, ...) BEFORE auth.NewFileTokenStore("/data") is ever
     reached. bind_address defaults to "auto", which requires a literal `tailscale*` interface
     under /sys/class/net (bind.go's firstTailscaleIP). internal/verify-bridge-no-token-leak.sh's
     `docker run` never used --network host (production's config.yaml host_network:true, added in
     commit 680a1bf specifically so bind_address=auto could detect Tailscale on the HOST interface,
     was never mirrored into the test harness) and no GitHub Actions runner has Tailscale
     installed/connected regardless of network mode. So the bridge always hit
     bind_resolution_failed and os.Exit(1)'d before ever calling NewFileTokenStore. The verify
     script's "could not read /data/initial-token" failure was a misleading DOWNSTREAM symptom of
     this earlier, unrelated crash — confirmed by reproducing the exact failure locally without
     docker (unshare -m + bind-mounting an empty dir over /sys/class/net, then running the actual
     compiled bridge binary) and by a live CI round-trip that proved the mkdir fix alone did not
     change the outcome.

  Answer to the original (a)/(b)/(c) framing: the /data question itself resolves to (c) both (real
  defense-in-depth gap + test-harness gap), but it turned out NOT to be what was causing CI to be
  red — that was the unrelated bind-address auto-detection / Tailscale-dependency gap in the same
  test harness, uncovered only after the first fix was verified not to work.
fix: |
  1. terraform-bridge/internal/auth/token.go: added
     `if err := os.MkdirAll(dataDir, 0o700); err != nil { return nil, fmt.Errorf(...) }` as the
     first statement in NewFileTokenStore. Idempotent; a no-op under real Supervisor. Covered by a
     new regression test (TestNewFileTokenStoreCreatesMissingDataDir) proven red-then-green against
     the fix (git stash of token.go reproduced the original ENOENT failure; restoring the fix made
     it pass).
  2. internal/verify-bridge-no-token-leak.sh: mount a real host-backed /data (mktemp -d) into the
     container containing an options.json with an explicit bind_address=127.0.0.1 +
     bind_allowed_subnets=["127.0.0.0/8"] override, so the bridge exercises ResolveBindAddress's
     already-unit-tested explicit-IP path instead of "auto" (no production code or config.yaml
     change). Because the bridge now binds loopback-only, the GET / smoke check runs via
     `docker exec ... curl` inside the container's own namespace instead of a host-mapped port
     (dropped the now-unusable -p 8124:8124 mapping). Cleanup trap extended to rm -rf the temp
     /data dir.
verification: |
  CONFIRMED via live CI (no local docker available in this WSL2 environment, per session
  constraint) — never touched origin/main:
  - Committed both fixes together on a throwaway branch (debug/item-7-data-mkdir-gap-verify),
    pushed, ran `gh workflow run lint.yml --ref debug/item-7-data-mkdir-gap-verify`
    (run 33525951320), then `git reset --soft HEAD~1` on local main to un-advance it back to
    exactly matching origin/main (0 commits ahead) so the fix stayed uncommitted/staged locally.
  - Result: "terraform-bridge no-token-leak...........................................Passed"
    (pre-commit's hook exit code 0 — the script's internal FAIL=1/exit-1 gate means a "Passed"
    status proves every internal assertion succeeded: no SUPERVISOR_TOKEN/Bearer/bridge_token
    substrings, fake token absent, plaintext absent from stdout, actor_token_fp ==
    SHA-256[8](initial-token), preview format correct, path field correct, OPS-01 GET / record
    present).
  - Remaining Lint job failures on that same run (end-of-file-fixer, pretty-format-json,
    verify-bridge-scaffold's 30 MiB image-size cap) are PRE-EXISTING and unrelated — confirmed
    present in the original failing run (33524244697, on main HEAD ef3ad49) before any of this
    session's changes; explicitly out of scope (item 7 only).
  - Cleaned up: deleted the throwaway remote branch after confirming.
  - User confirmed the fix via checkpoint response ("commit"). Committed locally on main as
    commit e2bcf90. NOT pushed to origin/main — per session scope, pushing remains a separate
    pending decision out of scope for this session (see Notes).
files_changed:
  - terraform-bridge/internal/auth/token.go
  - terraform-bridge/internal/auth/token_test.go
  - internal/verify-bridge-no-token-leak.sh

## Notes

- No local `docker build`/`docker run` available in this WSL2 environment — verify any fix via
  CI re-run or a shell with docker available, not locally.
- Do not touch items 1-6 (already done, committed, independently re-verified) — this session is
  scoped to item 7 only.
- Item 7's fix is now committed locally on main as `e2bcf90` (on top of the pre-existing
  `5f85217`..`ef3ad49` items 1-6 commits). Local main is 1 commit ahead of `origin/main`, not
  pushed — pushing remains a separate decision pending user confirmation, not part of this debug
  session's scope.
