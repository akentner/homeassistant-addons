---
phase: 21-cups-print-server-addon-airprint-mdns-fixes
plan: 12
type: execute
wave: 3
depends_on: ["21-10", "21-11"]
files_modified:
  - cups/DOCS.md
  - cups/README.md
  - cups/config.yaml
  - cups/build.yaml
  - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-12-SUMMARY.md
autonomous: false
gap_closure: true
optional: true
decision_required: true
requirements: [D-11, D-12, D-08]

estimate:
  tokens: 40000
  raw_tokens: 40000
  tasks: 4
  confidence: low

must_haves:
  truths:
    - "cups/DOCS.md and cups/README.md describe what the guard really does after 21-11 (startup claim plus lifelong host-name supervision with a bounded recovery ladder, the new log lines, the filtered avahi capture) and no longer say that a later conflict is neither healed nor monitored or attribute that to D-08; the slot-exhaustion paragraph states that D-08 concerns that error only"
    - "cups is bumped to 0.1.0-17 only through `make update-version ADDON=cups VERSION=0.1.0-17 NO_TAG=yes` (config.yaml, build.yaml and the README badge in sync, no tag created by the plan); `make validate-versions` and `make validate-addons` pass"
    - "Publication (push of main, tag cups/v0.1.0-17, CI build) happens only after an explicit blocking-human decision; agents never push, tag or dispatch on their own"
    - "On the live host after the update: the add-on log shows `supervising host name` at start and a heartbeat within 30 minutes; a quiet `--watch` ends PASS with milestones age+2m, age+10m and age+30m PASS; a forced rename (human-run D-Bus call) is recovered within 90 seconds with `hostname lost` and `hostname recovered` in the log; if a real conflict occurs during observation, success means recovered within 90 s with the conflicting record named in an `[avahi-capture]` context block -- a rename that is not recovered is a FAIL"
  artifacts:
    - cups/DOCS.md
    - .planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-12-SUMMARY.md
  key_links:
    - "make update-version ADDON=cups VERSION=0.1.0-17 NO_TAG=yes -> config.yaml / build.yaml / README badge; tag and image come only from the publication decision"
    - "published image amd64-cups:0.1.0-17 (internal/verify-image-availability.sh --addon cups) -> human-run ha apps update -> the 21-09 watch plus the forced-rename drill"
---

<objective>
> DEFERRED-PENDING-USER-DECISION, together with 21-11. Execute only if the user chose to include runtime recovery and
> capture in Phase 21 (or if 21-10 reported a rename in a quiet window). Not required to close Phase 21; it must not run
> while plan 21-10's quiet window is open.

Finish what 21-11 started: correct the documentation, bump the version without tagging, decide publication explicitly,
and prove the new behaviour on haos-op3050-1 over time, including a deliberate rename that the supervisor must heal.

Acceptance, stated explicitly: success is (1) a quiet `--watch` of at least 30 minutes on the updated boot with `WATCH RESULT:
PASS` and milestones PASS at +2, +10 and +30 minutes, (2) the supervisor visible in the add-on log (`supervising host name`, a
heartbeat), (3) a human-forced rename recovered within 90 seconds with both log lines, and (4) after one plain restart the same
quiet watch passes again. If a conflict occurs during observation, success is "the guard recovered the name within 90 s and the
log names the conflicting record" -- a rename that is not recovered is a FAIL. Live mutations (publication, update, forced
rename, restart) are human decisions or human-run commands; agents run read-only commands only. Local docker verification of
cups/ precedes any commit (repository rule); the Dockerfile and packages are unchanged by this phase's code.
Decisions D-08 (as written: slot-exhaustion only), D-11 and D-12 are the ones touched.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-CONTEXT.md
@.planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-10-PLAN.md
@.planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-11-PLAN.md
@.planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-07-PLAN.md
@cups/DOCS.md
@cups/README.md
@cups/config.yaml
@docs/UPDATE_VERSION.md
@.github/RELEASE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Correct DOCS and README, bump to 0.1.0-17 without a tag, run every local verifier</name>
  <reversibility rating="costly">The version string and image tag become public once published; the bump itself is a local commit and still revertible before publication.</reversibility>
  <read_first>
    cups/DOCS.md (the paragraphs "Avahi startup guard (D-11)" and "No slot-exhaustion watchdog (D-08)", the Migration section), cups/README.md (the
    feature bullet about the startup guard), docs/UPDATE_VERSION.md (explicit X.Y.Z-N rule, NO_TAG), 21-06-SUMMARY.md (the exact earlier bump command
    and result), 21-11-SUMMARY.md (final log line texts and tunables), the repository CLAUDE.md (120-column markdown, no attribution lines)
  </read_first>
  <files>cups/DOCS.md, cups/README.md, cups/config.yaml, cups/build.yaml</files>
  <action>
    Rewrite the DOCS paragraph on the guard into "Avahi guard and supervision (D-11)": what runs at start (claim, retries, cupsd held back
    until settled), what runs afterwards (a poll every 15 s, loss confirmed after two polls, the ladder: 2 D-Bus reclaims, 2 avahi
    restarts with 30 s and 90 s backoff, one `ERROR: giving up` per episode, then a retry every 300 s, never an exit), the exact log lines to
    look for (`supervising host name`, `hostname lost`, `hostname recovered`, `giving up`, `supervisor alive`, `[avahi-capture]` context
    blocks), and what the capture is (avahi `--debug` behind a filter that names the conflicting record). Add a short "Local testing" note:
    never run a cups container with the default host name `cups` next to a live add-on -- use the helper in internal/cups-test-isolation.sh,
    which refuses it (the 2026-10-04 incident). Keep the slot-exhaustion paragraph, adding that D-08 covers that error only and that the host
    name is supervised. Update the README feature bullet to match. Then run `make update-version ADDON=cups VERSION=0.1.0-17 NO_TAG=yes`
    (explicit X.Y.Z-N; do not edit versions by hand), and run `make validate-versions`, `make validate-addons`, `pre-commit run --files
    cups/DOCS.md cups/README.md cups/config.yaml cups/build.yaml`, shellcheck on every touched script, `bash internal/verify-cups-hardening.sh`,
    `bash internal/verify-cups-avahi-guard.sh`, `bash internal/verify-cups-scaffold.sh` and `bash internal/verify-cups-paperless-upload.sh`
    (these build the image locally). All new prose lines at most 120 columns (table rows exempt); no tag is created and nothing is pushed.
  </action>
  <verify>
    <automated>make validate-versions &amp;&amp; make validate-addons &amp;&amp; grep -q '^version: "0.1.0-17"' cups/config.yaml &amp;&amp; test -z "$(git tag --list 'cups/v0.1.0-17')" &amp;&amp; bash internal/verify-cups-hardening.sh</automated>
  </verify>
  <acceptance_criteria>
    - config.yaml reads 0.1.0-17, build.yaml VERSION 0.1.0, the README badge v0.1.0, `make validate-versions` and `make validate-addons` pass, `git tag --list 'cups/v0.1.0-17'` is empty
    - the four local verifiers listed above all print RESULT: PASS or ALL CHECKS PASSED
    - the DOCS text contains the sentence that D-08 covers slot exhaustion only, and no sentence claims a later conflict is neither healed nor monitored
    - `awk 'length > 120 && !/^\|/' cups/DOCS.md cups/README.md | wc -l` prints 0
  </acceptance_criteria>
  <done>Docs match the behaviour, the version is bumped locally and untagged, and every local verifier is green before publication is even discussed.</done>
</task>

<task type="checkpoint:decision" gate="blocking-human">
  <decision>How to publish cups 0.1.0-17 (push main, create tag cups/v0.1.0-17, CI build)</decision>
  <context>
    Publication is broader than the cups add-on: a push of main fires build.yml for every add-on directory changed in the pushed range, pushes
    images to ghcr.io and sends HA webhooks. Before asking, run and show these read-only facts: `git log --oneline origin/main..HEAD` (commits a
    push would publish), `git diff --name-only origin/main..HEAD` reduced to the distinct top-level add-on directories, and whether the tag
    `cups/v0.1.0-17` exists locally or on origin. The tag is created by `make update-version ADDON=cups VERSION=0.1.0-17` after the bump is
    committed (documented flow in docs/UPDATE_VERSION.md and .github/RELEASE.md). The last publication (0.1.0-16) was done by the orchestrator on
    explicit user instruction, merging origin/main rather than rebasing to keep the SHAs cited in .planning stable.
  </context>
  <options>
    <option id="human">
      <name>The human publishes</name>
      <pros>No agent ever pushes; the human sees the rebuild list first</pros>
      <cons>Manual steps and a wait for the cups build</cons>
    </option>
    <option id="orchestrator">
      <name>The orchestrator publishes on explicit instruction</name>
      <pros>Same proven procedure as 0.1.0-16 (merge origin/main, push, tag via make); less manual work</pros>
      <cons>Requires the human's explicit go after seeing the rebuild list; the push touches every add-on changed in the range</cons>
    </option>
    <option id="hold">
      <name>Hold: do not publish now</name>
      <pros>Keeps 0.1.0-16 running unchanged; code and docs stay committed locally</pros>
      <cons>The recovery and capture code does not run on the live host; Task 3 and 4 cannot start</cons>
    </option>
  </options>
  <resume-signal>Reply `human`, `orchestrator` or `hold`; after publication reply `published` once the cups build run succeeded (`gh run list --workflow build.yml --limit 5`)</resume-signal>
</task>

<task type="checkpoint:human-action" gate="blocking-human">
  <name>Task 3: Update the live add-on, observe 30+ quiet minutes, force one rename</name>
  <precondition>Task 2 was answered `published`; `./internal/verify-image-availability.sh --addon cups --grace-minutes 0` exits 0 for 0.1.0-17</precondition>
  <read_first>
    internal/verify-cups-mdns-live.sh (--watch, --assert, --settle-wait, milestone line), 21-10-SUMMARY.md (the quiet-window rule and the baseline on 0.1.0-16),
    cups/avahi-guard.sh (exact log lines of the supervisor), 21-07-PLAN.md (the earlier update procedure)
  </read_first>
  <action>
    Poll the availability probe until the exact tag is anonymously pullable (at most 30 minutes, then stop and name the state). After the human
    replies `updated`, check read-only that `ha apps info 72a005f5_cups --raw-json` shows version 0.1.0-17 and state started, then run in the
    background `bash internal/verify-cups-mdns-live.sh --watch 32 --interval 120 --settle-wait 120 --quiet-since $TP --mask` (output outside the repository; `TP=$(date +%s)` is recorded before the update instruction is presented, so the quiet window covers the update-to-first-round gap) and wait for
    `WATCH RESULT:`. Take the read-only log excerpt of this boot (after the last `attempt 1/3: starting avahi-daemon`) filtered for `avahi-guard`,
    `avahi-capture`, `Host name conflict`: it must contain `supervising host name` and, after 30 minutes, a `supervisor alive` heartbeat. Then, after
    the human replies `drilled`, poll `bash internal/verify-cups-mdns-live.sh --assert --mask` every 15 s for at most 120 s and record the time until
    `RESULT: PASS`, and take the log excerpt showing `hostname lost` and `hostname recovered`. Stop rules as in 21-10: INVALID repeats the window, a
    FAIL in a quiet window ends the plan with gaps remaining; an unrecovered drill is a FAIL.
  </action>
  <instructions>
    What I already did: confirmed the image is anonymously pullable and the watch tooling is in place.

    What I need from you, in order, from your own shell (the update restarts the add-on; your quiet promise starts NOW, before the update: no podman/docker container on the workstation until I report the watch finished, about 40 minutes counted from the update command):
    ! ssh haos-op3050-1 "ha store reload"
    ! ssh haos-op3050-1 "ha apps update 72a005f5_cups"
    Reply `updated`. After the 32-minute watch I will ask for the drill, which renames the host name on purpose (the supervisor must heal it):
    ! ssh haos-op3050-1 "docker exec app_72a005f5_cups dbus-send --system --print-reply --dest=org.freedesktop.Avahi / org.freedesktop.Avahi.Server.SetHostName string:cups-drill"
    Reply `drilled` right after you ran it.
  </instructions>
  <verification>`WATCH RESULT: PASS` with milestones PASS and quiet rounds, the supervisor start line and a heartbeat in the log, and after the drill `RESULT: PASS` within 90 s with the `hostname lost` and `hostname recovered` lines.</verification>
  <acceptance_criteria>
    - the update and the drill were run by the human; no agent ran a mutating command
    - the watch, log excerpt and drill timing are recorded masked, without dotted-quad addresses
    - a drill not recovered within 90 s, or a FAIL in a quiet window, ends the plan as gaps remaining
  </acceptance_criteria>
  <resume-signal>Reply `updated` after the update, then `drilled` after the drill command, or describe what went wrong</resume-signal>
</task>

<task type="checkpoint:human-action" gate="blocking-human">
  <name>Task 4: One restart on 0.1.0-17, observe again, write the verdict</name>
  <precondition>Task 3 ended with a PASS watch and a recovered drill</precondition>
  <read_first>
    internal/verify-cups-mdns-live.sh, 21-VERIFICATION.md (truths #13 and #14), 21-10-SUMMARY.md (how the earlier verdicts were written)
  </read_first>
  <action>
    After the human replies `restarted`, repeat the quiet watch with `--settle-wait 90 --quiet-since $TP` (fresh `TP` recorded before the instruction is presented), take the boot's log excerpt and confirm the supervisor start
    line. Write 21-12-SUMMARY.md with masked transcripts: the update boot watch, the drill timing and log lines, the restart-boot watch, the quiet
    statement per window and the verdict for truths #13 and #14 and for D-11. State in one line whether a real conflict occurred during any window and,
    if so, whether the log named the conflicting record and the name was recovered within 90 s. Close with the next step: `/gsd-verify-work 21`.
  </action>
  <instructions>
    What I already did: the update boot was observed for 32 quiet minutes and the forced rename was healed.

    What I need from you: your quiet promise starts NOW, before the restart: no podman/docker container on the workstation until I report the watch finished (about 40 minutes counted from the restart command). Then one more restart from your shell, and reply `restarted`:
    ! ssh haos-op3050-1 "ha apps restart 72a005f5_cups"
  </instructions>
  <verification>PASS watch with milestones PASS on the restarted boot; 21-12-SUMMARY.md exists, is masked and states the verdict per truth.</verification>
  <acceptance_criteria>
    - the restart was run by the human; the SUMMARY contains no dotted-quad IPv4 address and no credential value
    - truths #13 and #14 are reported closed only if every observation in this plan and in 21-10 was `WATCH RESULT: PASS` with a verified events history and quiet (INVALID and PASS-UNVERIFIED-QUIET do not count)
  </acceptance_criteria>
  <resume-signal>Reply `restarted` after you ran the restart command, or describe what went wrong</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| repository -> GitHub Actions -> ghcr.io -> Supervisor image pull | the artifact the live host runs is built by CI and pulled anonymously |
| operator workstation -> haos-op3050-1 via SSH | update, a deliberate rename and a restart mutate a production add-on |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-21-34 | Denial of Service / Tampering | live update, forced rename and restart of the production cups add-on | high | mitigate | blocking-human checkpoints, human-run commands, one add-on, stop at the first FAIL; the drill is bounded to a 90 s recovery assertion |
| T-21-35 | Tampering (supply chain) | the image published to ghcr.io and pulled by the Supervisor | medium | mitigate | build pipeline unchanged; the human decides publication after seeing the rebuild list; the availability probe proves the exact tag is anonymously pullable before any update |
| T-21-36 | Information Disclosure | transcripts of live LAN state committed to the planning directory | low | mitigate | `--mask` on every capture, acceptance criteria forbid dotted-quad addresses and credentials |
| T-21-SC | Tampering | npm/pip/cargo installs | low | accept | no package-manager install in this plan; package-legitimacy gate not triggered |
</threat_model>

<verification>
Strictly sequential: Task 1 (docs, version, local verifiers) -> Task 2 (publication decision) -> Task 3 (update, watch, drill) -> Task 4 (restart, verdict).
Nothing in Task 3 may run if the availability probe failed; nothing may run while 21-10's quiet window is open. Afterwards run `/gsd-verify-work 21`.
</verification>

<success_criteria>
- Docs and code agree; cups 0.1.0-17 is bumped locally, untagged, and published only by explicit decision
- The supervisor is visible in the live log, a forced rename heals within 90 s, and the quiet watch passes at +2, +10 and +30 minutes after the update and after a restart
- Any failure is reported as a persisting gap with evidence
</success_criteria>

<output>
Create `.planning/phases/21-cups-print-server-addon-airprint-mdns-fixes/21-12-SUMMARY.md` when done
</output>
