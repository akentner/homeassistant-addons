---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
plan: 11
type: execute
wave: 2
depends_on: ["21-08"]
files_modified:
  - cups/avahi-guard.sh
  - cups/run.sh
  - internal/verify-cups-avahi-guard.sh
  - internal/verify-cups-hardening.sh
autonomous: true
gap_closure: true
optional: true
decision_required: true
requirements: [D-11, D-08]

estimate:
  tokens: 80000
  raw_tokens: 80000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "After a post-claim rename (forced in docker through the D-Bus SetHostName call that avahi itself makes on a collision) the add-on restores `<avahi_hostname>.local` without a container restart within 90 seconds, logs `[avahi-guard] WARNING: hostname lost` and `[avahi-guard] INFO: hostname recovered`, and cupsd's `_ipp._tcp` service resolves to the expected host again -- proven by an in-container resolved browse line; against the pre-change run.sh and avahi-guard.sh the same scenario FAILS (RED)"
    - "Recovery is bounded and never fatal: per loss episode at most 2 D-Bus reclaims, then at most 2 avahi restarts with 30 s and 90 s backoff, then exactly one `ERROR: giving up` line, after which supervision continues with one slow retry every 300 s; run.sh and the container never exit because of a name problem, under bashio's errexit"
    - "SIGTERM stops the supervisor promptly (docker stop finishes without escalating to SIGKILL), cupsd is stopped, avahi is stopped last so goodbye packets go out, and the container exit status of an unexpected cupsd exit is preserved as before"
    - "The add-on log proves the supervisor is alive: a `supervising host name` line at start and a heartbeat every 30 minutes (and a log-volume budget: at most one heartbeat per 30 min while nothing is wrong)"
    - "A host-name conflict becomes self-diagnosing: avahi runs with --debug through a filter that drops D-Bus method noise and `Received packet from invalid interface`, rate-limits unclassified lines, always passes startup/registration/conflict lines, and dumps the last 200 raw lines as context when a conflict signature appears -- while chroot, privilege dropping, allow-interfaces and the D-Bus claim behave exactly as before"
    - "D-08 is applied as written: no watchdog or monitor for the slot-exhaustion message exists; supervision concerns only the host name (D-11), and the code comments that over-read D-08 are corrected"
  artifacts:
    - cups/avahi-guard.sh
    - cups/run.sh
    - internal/verify-cups-avahi-guard.sh
  key_links:
    - "run.sh final wait -> supervise loop in the main shell: AVAHI_PID and CUPSD_PID are children of that shell, so only it can wait on, stop and restart them (a background subshell cannot)"
    - "avahi_guard_set_hostname (D-Bus SetHostName) -> avahi re-probes the expected name -> cupsd's already registered SRV target `<name>.local` resolves again with no cupsd action (planning-time spike: browse-works/resolve-fails while renamed, resolved again within 6 s of the reclaim)"
    - "avahi restart (escalation) -> cupsd's avahi client reconnects and re-registers by itself (planning-time spike: resolved `=` line within 14 s of a fresh avahi-daemon); verified again by the rename scenario, with a cupsd SIGHUP fallback added only if that assertion fails"
    - "avahi --debug -> avahi_guard_capture_filter -> add-on log: the conflicting record text (`Received conflicting ... [<record>]`) reaches `ha apps logs` next to `Host name conflict`"
---

<objective>
> DEFERRED-PENDING-USER-DECISION. Plans 21-08, 21-09 and 21-10 fix and re-prove the observed failure (our own local test
> container announcing the default name). This plan and 21-12 add runtime RECOVERY and EVIDENCE CAPTURE for the case that
> a foreign announcer on the LAN claims `cups.local` anyway. They are not required to close Phase 21 and do not block
> 21-10. The user chooses: include them in Phase 21, or defer them to a later phase. If 21-10 reports a rename during a
> QUIET window, this plan becomes required. The orchestrator must not execute 21-11/21-12 without that choice.

Make the next occurrence of a lost name self-healing and self-diagnosing. Today cups/avahi-guard.sh returns after five
stable polls, so a conflict minutes later is neither detected nor retried and cupsd keeps announcing a stale SRV target
(21-VERIFICATION truths #13/#14 mechanism). Add (A) supervision with bounded recovery for the lifetime of the container and
(B) an always-on, filtered avahi debug capture that names the conflicting record and context.

Decision interpretation (explicit, reviewable): D-08 says there is no watchdog or log monitoring for the SLOT-EXHAUSTION
error, because enable-reflector=no makes that failure impossible. It does not forbid supervising the avahi host name, and
D-11 (a fixed host name) requires that the name is KEPT. The comments "startup-only, no watchdog -- D-08" in
cups/avahi-guard.sh and cups/run.sh over-read D-08 and are rewritten here. No new add-on option is added (D-05 keeps the
minimal surface; the root cause was test-induced and a schema/translation change for a diagnostic switch is not
justified): the AVAHI_GUARD_* environment variables stay test tunables.

Design decisions (justified):
1. Placement: a loop in run.sh's main shell (replacing the final `wait "$CUPSD_PID"`), with the logic as library functions in
   avahi-guard.sh. Rejected: a background subshell loop (cannot wait on or update AVAHI_PID/CUPSD_PID, so `avahi_guard_stop`
   would break) and an s6 service (the image runs run.sh as the /init CMD; adding s6-rc services would change the add-on's
   architecture). Interruptibility: sleep in the background and `wait` on it, so the TERM/INT trap fires immediately.
2. Detection: poll D-Bus GetState/GetHostNameFqdn every 15 s (cheap, two dbus-send calls) plus `kill -0` on AVAHI_PID; a loss is
   confirmed after two consecutive bad polls so avahi's brief `registering` state is not mistaken for a loss.
3. Recovery ladder (least disruptive first): (1) D-Bus SetHostName to the expected short name, wait for a settled claim
   (no avahi restart, no cupsd action needed: spike-verified); (2) stop and restart avahi with the existing backoffs (cupsd
   re-registers by itself: spike-verified); (3) give up for this episode with one ERROR and retry the reclaim every 300 s.
4. Evidence: the conflicting record is only logged by avahi at debug level (`Received conflicting record [...]`, `Received
   conflicting probe [...]. Local host lost. Withdrawing.`), so avahi runs with --debug behind a filter. A real foreign-packet
   injection was investigated at planning time and is not portable (a spoofed on-link multicast source fails with ENETUNREACH;
   dummy/veth/bridge interfaces cannot be created rootless here), so tests model the conflict with the exact avahi source
   strings and force the rename through SetHostName, which is the same call avahi-daemon makes on a collision.
Decisions D-07, D-10, D-12 are unchanged; D-01..D-06, D-09, D-13 are untouched.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-CONTEXT.md
@.planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-VERIFICATION.md
@.planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-05-SUMMARY.md
@.planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-08-PLAN.md
@cups/avahi-guard.sh
@cups/run.sh
@internal/cups-test-isolation.sh
@internal/verify-cups-avahi-guard.sh
@internal/verify-cups-hardening.sh
</context>

<tasks>

<task type="tracer">
  <name>Task 1: Supervisor loop with SetHostName reclaim, proven by a forced rename in a real container (RED then GREEN)</name>
  <reversibility rating="reversible">Library functions plus a loop in run.sh; reverting restores the startup-only guard. No option, schema or on-disk format changes.</reversibility>
  <read_first>
    cups/avahi-guard.sh (avahi_guard_query, avahi_guard_wait_settled, avahi_guard_stop, the errexit-safety comment learned in
    21-05: under `with-contenv bashio` a bare failing command ends the script), cups/run.sh (steps 4, 6, 8 where CUPSD_PID is
    reassigned after the UUID-fixup restart, and step 12: the cleanup function and the final wait), internal/verify-cups-avahi-guard.sh
    and internal/cups-test-isolation.sh (cups_lan_run: the only helper that leaves a real mDNS interface, needed because the service
    must be browsable), 21-05-SUMMARY.md (deviation 1, errexit)
  </read_first>
  <files>cups/avahi-guard.sh, cups/run.sh, internal/verify-cups-avahi-guard.sh</files>
  <action>
    In cups/avahi-guard.sh add: a classifier that turns one query plus a `kill -0` of AVAHI_PID into ok, renamed, registering
    or down; `avahi_guard_set_hostname`, which calls org.freedesktop.Avahi.Server.SetHostName over dbus-send with the short
    expected name (AVAHI_EXPECTED_HOSTNAME) and never lets a non-zero status escape; `avahi_guard_reclaim`, which does that and
    then waits with the existing `avahi_guard_wait_settled`; and `avahi_guard_supervise_tick`, one iteration that polls, counts
    consecutive bad polls (confirm after AVAHI_GUARD_SUPERVISE_CONFIRM, default 2), and on a confirmed loss logs `[avahi-guard]
    WARNING: hostname lost: expected <fqdn>, avahi runs as <actual> (episode <n>)`, runs one reclaim, and on success logs
    `[avahi-guard] INFO: hostname recovered: <fqdn> after <s>s via reclaim (episode <n>)`. Tunables (environment, test-only,
    documented in the file header): AVAHI_GUARD_SUPERVISE_POLL (default 15), AVAHI_GUARD_SUPERVISE_CONFIRM. Every command that
    can return non-zero sits in an `if` or has an `||` guard. Rewrite the header's "Scope: startup only ... (D-08)" paragraph
    to the new truth: startup guard plus host-name supervision; D-08 concerns only the slot-exhaustion watchdog.
    In cups/run.sh replace the final `wait "$CUPSD_PID"` by a supervise loop in the main shell: log `[avahi-guard] INFO:
    supervising host name <fqdn> (poll <n>s)` once, then loop until a STOPPING flag (set by the TERM/INT trap) or until
    cupsd is gone; each pass runs the tick, then `sleep <poll> & wait $!` so the trap interrupts it at once. When cupsd has
    exited, collect its status with `wait "$CUPSD_PID"` and exit with that status after cleanup, preserving today's
    semantics. The cleanup function additionally sets the flag and kills the pending sleep. Correct the step-4 and step-12
    comments that cite D-08 for "startup-only".
    In internal/verify-cups-avahi-guard.sh add a `CUPS_ADDON_DIR` override for ADDON_DIR (as the scaffold verifier has) and
    scenario `rename` (add it to ALL_SCENARIOS): fixture with a printer entry and `cups_test_hostname ren`, started with
    `cups_lan_run` plus `-e AVAHI_GUARD_SUPERVISE_POLL=3`; wait for `RESULT: claimed`; assert the baseline (in-container
    `avahi-browse -t -r -p -k _ipp._tcp` has a resolved `=` line whose host is `<name>.local` -- skip the scenario with a
    reason if the container has no browsable mDNS interface); force the rename with `docker exec ... dbus-send ...
    SetHostName string:<name>-2`; assert that within 90 s GetHostNameFqdn is `<name>.local` again, that the log contains the
    `hostname lost` and `hostname recovered` lines, and that the resolved browse line is back with the expected host; print the
    measured recovery time. RED proof to record: build from a copy of cups/ whose run.sh and avahi-guard.sh come from
    `git show a1ace38:cups/run.sh` and `git show a1ace38:cups/avahi-guard.sh`, run with `CUPS_ADDON_DIR` pointing at it:
    `--scenario rename` must FAIL (no recovery), then PASS on the new code.
  </action>
  <verify>
    <automated>shellcheck -e SC1091 -e SC2034 cups/run.sh cups/avahi-guard.sh internal/verify-cups-avahi-guard.sh &amp;&amp; bash internal/verify-cups-avahi-guard.sh --scenario rename --scenario claim</automated>
  </verify>
  <acceptance_criteria>
    - `--scenario rename` passes on the new code with the recovery time printed (expected well under 90 s) and fails against the pre-change copy (RED, recorded)
    - the `claim` scenario still passes (supervision does not disturb the startup path)
    - shellcheck is clean for run.sh, avahi-guard.sh and the verifier; a local docker build of cups/ succeeded before any commit (repository rule; the verifier builds it)
    - the container keeps running after the recovery (cupsd alive, no exit)
  </acceptance_criteria>
  <done>A renamed host is detected and the fixed name is claimed back in a real container, cupsd's service resolves again, and the pre-change code demonstrably cannot do it.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Bounded ladder, give-up, heartbeat, clean SIGTERM, errexit safety</name>
  <reversibility rating="reversible">Extends the Task 1 functions; tunables are environment variables only.</reversibility>
  <read_first>
    cups/avahi-guard.sh and cups/run.sh (after Task 1), internal/verify-cups-avahi-guard.sh (run_harness: the harness container
    runs the real library under `set -e` with avahi_guard_query overridable; scenario_lost and scenario_unsettled as patterns),
    21-05-SUMMARY.md (the bashio errexit deviation: a harness without errexit hid a real bug)
  </read_first>
  <files>cups/avahi-guard.sh, cups/run.sh, internal/verify-cups-avahi-guard.sh</files>
  <behavior>
    - Test 1 (persistent conflict): with the query forced to a foreign name after the initial claim and SetHostName a no-op, one episode produces exactly 2 reclaim attempts, then 2 avahi restart attempts, then exactly one `ERROR: giving up` line, then at least one `slow retry` line; the supervise function returns 0 after AVAHI_GUARD_SUPERVISE_MAX_TICKS and avahi is still running
    - Test 2 (recovery after the second restart): the forced name clears after the second restart -> `hostname recovered ... via restart`, no `giving up` line, episode counter increments on the next loss
    - Test 3 (errexit): all of the above under `set -e` in the harness, ending with EXIT=0
    - Test 4 (SIGTERM): a full container is stopped with `docker stop -t 10`; it stops in under 8 s, the container exit code is not 137, the log shows the supervisor stopping and avahi's `Got SIGTERM, quitting` after it
    - Test 5 (heartbeat): with AVAHI_GUARD_HEARTBEAT=5 a quiet run logs `supervisor alive` lines with the episode count
  </behavior>
  <action>
    Implement the recovery ladder inside the supervise tick/state: per loss episode, up to AVAHI_GUARD_RECLAIM_ATTEMPTS (default 2)
    reclaims (each logged `[avahi-guard] INFO: reclaim attempt <a>/<n>`), then up to the existing backoff list (AVAHI_GUARD_BACKOFFS,
    default `30 90`) of avahi restarts using `avahi_guard_stop`, the pid-file cleanup run.sh already does at boot, `avahi_guard_launch`
    and `avahi_guard_wait_settled`, then `[avahi-guard] ERROR: giving up on episode <n> after <k> attempts -- another responder
    probably claims <fqdn>; the avahi lines above name its record. Will retry every <s>s` exactly once per episode, and afterwards a
    reclaim every AVAHI_GUARD_GIVEUP_RETRY seconds (default 300) logged as `slow retry` at INFO. A successful step ends the episode
    with the `hostname recovered ... via reclaim|restart` line; a later loss starts a new episode. After any avahi restart the
    supervisor re-checks cupsd's registration with the same in-container resolved-browse test the rename scenario uses when at
    least one printer is configured; if the service does not resolve to the expected host 20 s after a restart-type recovery,
    log an ERROR naming it and add a `kill -HUP` of cupsd as the re-registration fallback only if the scenario proves it is needed
    (do not add it speculatively). Add the heartbeat (`[avahi-guard] INFO: supervisor alive: <fqdn> held, episodes=<n>`) every
    AVAHI_GUARD_HEARTBEAT seconds (default 1800) and the test-only AVAHI_GUARD_SUPERVISE_MAX_TICKS (0 = unlimited) so a harness can
    bound the loop. Nothing in the loop may exit the script: guard every status, and keep `wait`/`sleep` handling errexit-safe.
    In internal/verify-cups-avahi-guard.sh add harness scenarios `persistent` (tests 1-3, using run_harness-style containers
    through `cups_isolated_bash`, stub query with a counter so the first polls report the expected name, tunables set small) and
    `sigterm` (tests 4-5 on a real isolated container through `cups_isolated_run`, measured with `docker stop`, `docker inspect`
    exit code and log order). Do not add any watchdog for the slot-exhaustion message (D-08 as written).
  </action>
  <verify>
    <automated>shellcheck -e SC1091 -e SC2034 cups/run.sh cups/avahi-guard.sh internal/verify-cups-avahi-guard.sh &amp;&amp; bash internal/verify-cups-avahi-guard.sh</automated>
  </verify>
  <acceptance_criteria>
    - the whole guard verifier prints RESULT: PASS (claim, lost, unsettled, refuse, isolation, rename, persistent, sigterm), including the exact counts of reclaim, restart and giving-up lines from test 1
    - docker stop of the full container finishes in under 8 s with an exit code other than 137, and avahi's goodbye (`Got SIGTERM`) is logged after cupsd was stopped
    - a quiet run shows the start line and at least two heartbeat lines at the shortened interval
    - the harness runs under `set -e` and still ends with EXIT=0 in the persistent-conflict scenario (never-fatal property)
  </acceptance_criteria>
  <done>Recovery is bounded, loud on giving up, quiet when healthy, stops cleanly and can never take the container down.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Always-on filtered avahi debug capture with conflict context</name>
  <reversibility rating="reversible">One launch-line change and a filter function; reverting returns to the plain undaemonized start.</reversibility>
  <read_first>
    cups/avahi-guard.sh (avahi_guard_launch and AVAHI_PID handling), internal/verify-cups-hardening.sh (python3 sections that run bash
    snippets with subprocess), the avahi source strings in avahi-core/server.c and avahi-daemon/main.c as listed in the objective,
    the planning-time observation that `--debug` adds one `dbus-protocol.c:`/`dbus-entry-group.c:` line per D-Bus call (so the guard's own
    polls would flood the log) and ~1000 `Received packet from invalid interface.` lines in 7 minutes on the live host
  </read_first>
  <files>cups/avahi-guard.sh, internal/verify-cups-hardening.sh, internal/verify-cups-avahi-guard.sh</files>
  <behavior>
    - Test 1: fed a mixed stream, the filter drops `dbus-*.c:` and `chroot.c:` method lines, `Received packet from invalid interface.`, `Packet too short or invalid`, `Received invalid packet` and `Invalid response packet`, and passes startup, registration, `Host name conflict`, `Withdrawing address record`, `Joining`/`Leaving mDNS` and `WARNING:` lines unchanged
    - Test 2: a conflict signature (`Host name conflict`, `Received conflicting probe`, `Received conflicting record`, `Local host lost`, `Resetting our record`, `goodbye record for one of our records`) after 5000 noise lines produces one `[avahi-capture]` context dump of at most 200 raw lines ending with the trigger, not 5000 lines, and a second trigger within 10 s does not dump again
    - Test 3: unclassified lines beyond 30 per 60 s window are suppressed and summarised once per window with a count
    - Test 4 (docker, real avahi): the container log still shows `Successfully called chroot()` and `Successfully dropped remaining capabilities`, the guard claims on attempt 1, no `dbus-protocol.c:` line appears while the guard polls, and fewer than 60 capture-related lines appear in a 60 s idle window
  </behavior>
  <action>
    Add `avahi_guard_capture_filter` to cups/avahi-guard.sh: a pure-bash `read` loop (no new packages) over stdin that keeps a ring
    buffer of the last 200 raw lines, applies the drop list, the pass list and a per-minute budget of 30 unclassified lines with a
    `[avahi-capture] INFO: suppressed <n> avahi lines in the last minute` summary, and on a conflict signature prints the ring as
    `[avahi-capture] context:` lines followed by the trigger (dump at most once per 10 s). Change `avahi_guard_launch` to start
    `avahi-daemon --debug` with stdout and stderr redirected into a process substitution running the filter, still as a background
    job so `$!` remains avahi's own pid (assert that `kill -0` and the process command line match avahi-daemon; the chroot and
    privilege-dropping lines must remain, so do not add --no-chroot or --no-rlimits). The filter writes to stderr (the add-on
    log). No option is added; the capture is always on, and its budget keeps the log bounded.
    In internal/verify-cups-hardening.sh add the host-side filter tests 1-3: source the library in a bash subprocess and pipe crafted
    lines (the exact avahi strings listed in the objective, a 5000-line noise burst, a timing bound of a few seconds). In
    internal/verify-cups-avahi-guard.sh add scenario `capture` for test 4 (a `cups_lan_run` container with a unique name, 60 s idle
    window). Tests model the conflict with source strings because a real foreign packet cannot be injected portably here (see the
    objective); the first real conflict on the live host is the final evidence.
  </action>
  <verify>
    <automated>shellcheck -e SC1091 -e SC2034 cups/avahi-guard.sh internal/verify-cups-hardening.sh internal/verify-cups-avahi-guard.sh &amp;&amp; bash internal/verify-cups-hardening.sh &amp;&amp; bash internal/verify-cups-avahi-guard.sh</automated>
  </verify>
  <acceptance_criteria>
    - hardening prints RESULT: PASS including filter tests 1-3; the guard verifier prints RESULT: PASS including `capture`
    - RED proof recorded: the filter tests run against a copy of avahi-guard.sh from commit a1ace38 fail (no filter function)
    - the scaffold and paperless verifiers still pass (`bash internal/verify-cups-scaffold.sh`, `bash internal/verify-cups-paperless-upload.sh`) -- production start path, D-Bus claim and printer registration are unchanged
    - `git diff -- cups/config.yaml cups/Dockerfile` is empty
  </acceptance_criteria>
  <done>The next real conflict puts the conflicting record and its surrounding lines into `ha apps logs`, without flooding the log and without changing how avahi is sandboxed.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| container -> avahi D-Bus API | the supervisor calls SetHostName and restarts avahi inside its own container |
| LAN mDNS -> avahi debug output | untrusted packet contents (record text) are written to the add-on log through the filter |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-21-30 | Denial of Service | supervisor loop restarting avahi repeatedly against a persistent foreign claimant | medium | mitigate | bounded ladder per episode (2 reclaims, 2 restarts), one give-up ERROR, then one reclaim per 300 s; never fatal, never exits |
| T-21-31 | Denial of Service | log flooding through --debug (noise, hostile LAN traffic) | medium | mitigate | drop list for known noise, 30 lines per minute budget for the rest with a summary, ring dump only on a conflict signature and at most once per 10 s |
| T-21-32 | Tampering / Injection | attacker-controlled record text in avahi debug lines reaching the log and `ha apps logs` | low | mitigate | lines are only printed, never evaluated or used as arguments; the filter uses `read -r` and pattern matching only |
| T-21-33 | Elevation of Privilege | enabling debug mode weakening sandboxing | low | mitigate | only `--debug` is added; chroot and privilege dropping stay (asserted by the capture scenario); no --no-chroot, no --no-rlimits |
| T-21-SC | Tampering | npm/pip/cargo installs | low | accept | no package-manager install in this plan; the filter is pure bash |
</threat_model>

<verification>
Order: Task 1 (tracer: reclaim e2e, RED/GREEN) -> Task 2 (ladder, give-up, SIGTERM, heartbeat) -> Task 3 (capture). Final:
shellcheck on run.sh, avahi-guard.sh and the three verifiers; `bash internal/verify-cups-hardening.sh`; the full guard verifier;
scaffold and paperless verifiers; `git diff --stat -- cups/` shows only run.sh and avahi-guard.sh. Local runs use the 21-08 isolation
helper; scenarios that need a browsable service use the unique-name LAN helper. No version bump here (21-12).
</verification>

<success_criteria>
- A forced rename is healed in a real container without a restart, with exact, bounded behaviour under a persistent conflict
- The supervisor is visible in the log, stops cleanly and cannot take the container down
- A conflict leaves the conflicting record and context in the add-on log; D-08 is respected as written
</success_criteria>

<output>
Create `.planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-11-SUMMARY.md` when done
</output>
