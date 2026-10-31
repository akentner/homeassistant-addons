---
quick_id: "261031-srb"
slug: "haos-monitor-show-ssh-key-fingerprint-pe"
description: "haos-monitor: show the SSH key fingerprint per host so the user can debug which key is actually deployed"
date: "2026-10-31"
status: planned
phase: quick-261031-srb
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - haos-monitor/run.sh
  - haos-monitor/status.sh
  - haos-monitor/index.html
  - haos-monitor/mqtt.sh
  - haos-monitor/DOCS.md
  - haos-monitor/CHANGELOG.md
  - haos-monitor/config.yaml
  - .planning/quick/261031-srb-haos-monitor-show-ssh-key-fingerprint-pe/261031-srb-verify.sh
autonomous: true
requirements: [QUICK-261031-srb]

estimate:
  tokens: 35000
  raw_tokens: 35000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "Every host card on the Ingress status page shows `SSH key <TYPE> SHA256:<fingerprint>`, identical to the output of `ssh-keygen -l -f <public key>` for the configured key"
    - "`/api/status.json?host=<slug>` carries the string fields `key_fp` and `key_type`; the MQTT `problem` binary sensor carries the same values as attributes `key_fingerprint` and `key_type`"
    - "A key that `write_key` accepts but `ssh-keygen` rejects (damaged body, truncated, passphrase-protected) shows `invalid`; the host stays listed and monitored and `run.sh` does not abort"
    - "A key whose newlines were flattened (spaces, literal backslash-n, CRLF) yields the same fingerprint as the intact key"
    - "Neither the private key nor the key comment appears in the hosts file, any endpoint or the container log; only the public-key fingerprint and key type are exposed"
    - "`haos-monitor/config.yaml` reads `0.6.1-1` while `build.yaml` and `README.md` are unchanged, `make validate-versions` passes and a local `docker build` of `haos-monitor/` succeeds"
  artifacts:
    - path: "haos-monitor/run.sh"
      provides: "key_fingerprint() helper, extended hosts-file line (columns 5 and 6), startup log line"
      contains: "key_fingerprint"
    - path: "haos-monitor/status.sh"
      provides: "key_fp and key_type fields in the status JSON"
      contains: "key_fp"
    - path: "haos-monitor/index.html"
      provides: "keyText() helper and the per-host SSH key line"
      contains: "keyText"
    - path: "haos-monitor/mqtt.sh"
      provides: "key_fingerprint and key_type attributes on the problem sensor"
      contains: "key_fingerprint"
    - path: "haos-monitor/DOCS.md"
      provides: "section `## SSH key fingerprint` plus the new field in the UI, status and MQTT paragraphs"
      contains: "## SSH key fingerprint"
    - path: "haos-monitor/CHANGELOG.md"
      provides: "entry for 0.6.1-1"
      contains: "[0.6.1-1]"
    - path: "haos-monitor/config.yaml"
      provides: "subpatch bump 0.6.1-0 to 0.6.1-1"
      contains: "0.6.1-1"
    - path: ".planning/quick/261031-srb-haos-monitor-show-ssh-key-fingerprint-pe/261031-srb-verify.sh"
      provides: "staged functional verification (fingerprint, status, mqtt, ui, docker)"
      contains: "STAGE"
  key_links:
    - from: "haos-monitor/run.sh"
      to: "haos-monitor/status.sh"
      via: "/etc/haos-monitor.hosts columns 5 (fingerprint) and 6 (key type), read with awk -F tab"
      pattern: "key_fp"
    - from: "haos-monitor/status.sh"
      to: "haos-monitor/index.html"
      via: "/api/status.json fields key_fp, key_type rendered by keyText(s)"
      pattern: "keyText"
    - from: "haos-monitor/status.sh"
      to: "haos-monitor/mqtt.sh"
      via: "state topic payload value_json.key_fp, value_json.key_type in PROBLEM_ATTRS"
      pattern: "value_json.key_fp"
---

<objective>
Show the SSH key fingerprint (full SHA256 plus key type) of every observed host, so a user can see which key the
add-on actually uses and compare it with the authorized key on the host.

Purpose: when SSH auth to a host fails or the monitor goes `stale`, the first question is "which key is deployed in
the add-on options?". Today the answer is invisible (the option is a password field).
Output: fingerprint in `/api/status.json` (`key_fp`, `key_type`), on the Ingress status page, as attributes of the MQTT
`problem` sensor, in a startup log line, documented in DOCS.md and CHANGELOG.md, add-on subpatch bumped to `0.6.1-1`.

Locked decisions (the user's brief, labelled for traceability; there is no CONTEXT.md in quick mode):

- D-01: Scope is ONLY `haos-monitor/` (secrets-sync is not touched). The verify script lives in the quick task
  directory, not in `internal/`, so that no file outside `haos-monitor/` and `.planning/quick/` is added.
- D-02: Show the FULL SHA256 fingerprint (not sensitive) plus key type per host on the status page (`index.html`), in
  `/api/status.json` (`status.sh`) and as an attribute on the MQTT entity (`mqtt.sh`) via the existing attribute
  mechanism.
- D-03: Compute it in `run.sh` from the SAME key file `write_key` writes (`KEY_FILE` under `/dev/shm`) with
  `ssh-keygen -y -f KEY_FILE | ssh-keygen -l -f -`. `ssh-keygen` is present in the image (shipped by the
  `openssh-keygen` package that `openssh-client` pulls in; confirmed in a probe build, `Dockerfile` needs no change).
  Never print, log or expose the private key or anything else derived from it except fingerprint and type. A malformed
  key that `write_key` accepts but `ssh-keygen` rejects shows `invalid` and must not crash the host loop.
- D-04: Hand the value to the web layer through the existing per-host data path. Chosen: extend each
  `/etc/haos-monitor.hosts` line with two columns (fingerprint, key type); all existing consumers read only column 1
  (`cut -f1`) or columns 1-3 (`hosts.cgi`), so nothing breaks, and `status.sh` already is the single producer that
  status JSON, metrics and MQTT share.
- D-05: Repo rules. Add-on-only change, so the version is a subpatch bump as its own step via
  `make update-version`; CHANGELOG.md and DOCS.md updated (DOCS states the value is a public-key fingerprint);
  markdown passes prettier and markdownlint (120 columns); shell passes shellcheck (`-e SC1091 -e SC2034`).
- D-06: Verification: a local `docker build` of `haos-monitor/` (mandatory), a throwaway ed25519 key compared with
  `ssh-keygen -l -f key.pub`, the flattened-newline variants `write_key` repairs, `make validate-versions` and
  `make lint` (pre-commit) on the changed files.
- D-07: Do NOT touch `.planning/STATE.md` or `ROADMAP.md` (add-on worktree rule). No push, and no
  `Co-Authored-By` line in the commit.

Discretion calls (documented): the fingerprint is attached to the existing `problem` sensor attributes rather than a
new text entity (the existing mechanism, no new entity or `entity_category` plumbing); a one-line startup log entry
with fingerprint and type is added (public data, first place a user looks); `ssh-keygen -y` runs with `-P ''` and
stdin from `/dev/null` so a passphrase-protected key can never make it prompt and hang startup; `-E sha256` pins the
hash. The brief's example bump (`0.6.0-2` to `0.6.0-3`) is stale: `config.yaml` is at `0.6.1-0`, so the next subpatch
is `0.6.1-1`. Not planned: a Prometheus metric or `hosts.json` field for the fingerprint (not requested).
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@haos-monitor/DOCS.md
@.claude/skills/update-version/SKILL.md

Commit policy for this plan: ONE commit after Task 3's verification passes (repo convention, see b8daa23: code, docs
and version files together), message `feat(haos-monitor): show the SSH key fingerprint per host (0.6.1-1)`, staged by
path only (`git add haos-monitor/ .planning/quick/261031-srb-haos-monitor-show-ssh-key-fingerprint-pe/`), no
`Co-Authored-By` or AI-attribution line, no push. The quick workflow's own SUMMARY.md may be added to that directory;
`.planning/STATE.md` and `.planning/ROADMAP.md` stay untouched (D-07).
</context>

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: Tracer - key fingerprint from run.sh through the hosts file and status.sh into /api/status.json, proven in the real container</name>
  <files>haos-monitor/run.sh, haos-monitor/status.sh, .planning/quick/261031-srb-haos-monitor-show-ssh-key-fingerprint-pe/261031-srb-verify.sh</files>
  <read_first>
    haos-monitor/run.sh (write_key, the host loop, the printf that appends to HOSTS)
    haos-monitor/status.sh (env overrides ENV_FILE/LOGDIR, the final printf JSON block)
    haos-monitor/hosts.cgi, haos-monitor/metrics.cgi, haos-monitor/status.cgi, haos-monitor/incidents.cgi (consumers of the hosts file)
    haos-monitor/Dockerfile
  </read_first>
  <behavior>
    The verify script `261031-srb-verify.sh` is a bash script (`set -u`, shebang `#!/bin/bash`, executable, repo root
    from `git rev-parse --show-toplevel`). Arguments are stage names out of `fingerprint status mqtt ui docker`; no
    argument runs all five. Every assertion prints `ok <label>` or `FAIL <label>`; a stage prints `STAGE <name> OK` only
    when nothing failed, and the script exits non-zero if any assertion failed. It works in a temp dir created with
    `mktemp -d` and removed by an EXIT trap via `rm -rf -- "${TMP:?}"` (never an unguarded variable). It must never
    contain a literal PEM header or footer line (gitleaks scans the staged diff); bad-key variants are derived from
    freshly generated keys with `head`/`tail`.

    Stage `fingerprint` (host level, no Docker):
    - Extracts the real `write_key()` and `key_fingerprint()` definitions out of `haos-monitor/run.sh` with a
      `sed -n '/^NAME() {/,/^}/p'` range (FAIL if `key_fingerprint()` is absent) and runs them in a child `sh -e`, the
      same strictness as `run.sh`'s `set -e`. The child writes the key with `write_key`, calls `key_fingerprint` on the
      written file and prints `KEY_FP|KEY_TYPE`.
    - Throwaway keys: ed25519 with comment `secret-comment@example`, RSA 2048, and a passphrase-protected ed25519.
      Expected values come from `ssh-keygen -l -E sha256 -f <key>.pub` (field 2 = fingerprint, trailing parenthesized
      token = type).
    - Must equal the expected fingerprint and type: intact ed25519 (ED25519), intact RSA (RSA), ed25519 flattened to
      spaces (`tr '\n' ' '`), ed25519 flattened to literal backslash-n sequences, ed25519 with CRLF line endings, RSA
      flattened to spaces.
    - Must print `invalid|` (empty type) and exit 0 under `sh -e`: the passphrase-protected key, a truncated key
      (header line, first body line, footer line), a key with a replaced body (header, one fixed line of base64 `A`
      characters, footer).
    - Leakage: for the intact ed25519 case the output is exactly one line, KEY_FP matches `^SHA256:[A-Za-z0-9+/]{43}$`,
      KEY_TYPE matches `^[A-Z0-9-]+$`, and neither `secret-comment` nor any 30-character slice of the key body occurs
      in the output.

    Stage `status` (host level, no Docker):
    - Fixture hosts file in the temp dir, tab-separated: `good_host` with a fingerprint and `ED25519`; `bad_host` with
      `invalid` and an empty sixth column (line ends in a tab); `old_host` with only the four old columns; `evil_host`
      with fifth column `SHA256:abc"},"x":"y` and sixth column `ED"25519`.
    - For each slug run `HOSTS_FILE=<fixture> LOGDIR=<empty temp dir> ENV_FILE=/nonexistent sh haos-monitor/status.sh <slug>`.
      Every output passes `jq -e .`. `good_host`: `.key_fp`/`.key_type` equal the fixture. `bad_host`: `invalid` and
      the empty string. `old_host`: both empty strings. `evil_host`: `.x` is absent and `.key_fp`/`.key_type` match
      `^[A-Za-z0-9+/:=_-]*$`. The pre-existing fields `.age`, `.problem`, `.reasons`, `.kmsg_last` are still present.
    - Consumer regression on the same fixture: `HOSTS_FILE=<fixture> sh haos-monitor/hosts.cgi` (drop its two header
      lines) lists 4 slugs; `HOSTS_FILE=<fixture> STATUS_SH=<abs path of haos-monitor/status.sh> LOGDIR=<temp dir> ENV_FILE=/nonexistent sh haos-monitor/metrics.cgi`
      still emits a `haos_monitor_problem{host="good_host"}` sample.

    Stage `docker` (the end-to-end tracer, uses the real image):
    - FAIL unless `docker info` works. `docker build -q -t haos-monitor-keyfp-<pid> haos-monitor/` must succeed, and
      `docker run --rm --entrypoint sh <image> -c 'command -v ssh-keygen'` must succeed (ssh-keygen availability, D-03).
    - Build `options.json` in the temp dir with `jq -n` (all required options: interval 10, the five `problem_*`
      thresholds, `mqtt_host` 127.0.0.1, `mqtt_port` 1883, empty MQTT user/password, `mqtt_discovery_prefix`
      homeassistant, `mqtt_clear_discovery` false) and three hosts at 127.0.0.1 port 1: `Good Host` (intact ed25519 with
      the secret comment), `Flat Host` (RSA flattened to spaces), `Bad Host` (replaced-body key). `chmod 644` it.
    - `docker run -d --name haos-monitor-keyfp-<pid> -v <options>:/data/options.json:ro <image>`; poll up to 30 s with
      `docker exec <c> wget -qO- 'http://127.0.0.1:8099/api/status.json?host=good_host'` until JSON arrives.
    - `.key_fp`/`.key_type` of `good_host` and `flat_host` equal the values from `ssh-keygen -l -E sha256 -f <pub>`;
      `bad_host` gives `invalid` and `""`. `/etc/haos-monitor.hosts` in the container has exactly 3 lines, all with 6
      tab-separated columns (`awk -F'\t' '{print NF}' | sort -u` prints `6`). `/api/hosts.json` lists 3 hosts and
      `/api/metrics.txt` contains a `haos_monitor_problem{host="good_host"}` sample.
    - `docker logs` contains `ssh key ED25519 SHA256:` for Good Host and `ssh key invalid` for Bad Host.
    - Leakage: the concatenation of `docker logs`, the three status JSONs, the hosts file, `hosts.json` and `metrics.txt`
      contains neither the text `PRIVATE KEY`, nor `secret-comment`, nor a 30-character slice of the good or flat key body.
    - The EXIT trap removes the container (`docker rm -f`) and the image tag (`docker rmi`).

    Stages `mqtt` and `ui` are specified in Task 2 and are written now as part of the same script so they start red.
  </behavior>
  <action>
    Honour D-01 to D-04 (and D-06 for the checks). Work test-first:

    1. Create `261031-srb-verify.sh` in the quick task directory exactly per the behavior block, including the `mqtt`
       and `ui` stage functions from Task 2's behavior block (so Task 2 starts red). Make it executable. It must pass
       `shellcheck -e SC1091 -e SC2034`. Run `fingerprint` and `status` once against the unchanged tree and confirm they
       FAIL (key_fingerprint missing, key_fp missing) before editing production files.

    2. `haos-monitor/run.sh`: add a function `key_fingerprint()` next to `write_key()` in the same style (name at column
       0, closing brace at column 0, so the verify script can extract it by sed range; first-line comment says
       `$1 = key file; sets KEY_FP and KEY_TYPE`). It derives the public key with `ssh-keygen -y -P ''` on the key file
       with stdin from `/dev/null` and stderr discarded, pipes it to `ssh-keygen -l -E sha256 -f -` with stderr
       discarded, and assigns the pipeline result to a variable with a trailing fallback to the empty string, because
       `run.sh` runs under `set -e` and a rejected key must not abort the loop. Take the fingerprint as field 2 of that
       line (awk) and the key type as the last parenthesized token (sed). Accept the fingerprint only when it matches
       `^SHA256:[A-Za-z0-9+/]+$` (grep -Eq inside an `if`), otherwise set `KEY_FP=invalid` and `KEY_TYPE=` empty; accept
       the type only when it matches `^[A-Za-z0-9_-]+$`. The raw `ssh-keygen` line also carries the key comment, so it
       must never be echoed, logged or stored: only the validated `KEY_FP`/`KEY_TYPE` leave the function. End with an
       explicit `return 0`.

    3. `haos-monitor/run.sh` host loop: right after `write_key` succeeds, call `key_fingerprint "$KEY_FILE"`. Print one
       stderr line in the existing `[run] host '$NAME': ...` style: `ssh key $KEY_TYPE $KEY_FP` for a valid key, or
       `ssh key invalid (ssh-keygen cannot read it: damaged, truncated or passphrase-protected)` when `KEY_FP` is
       `invalid`. A rejected key does NOT skip the host (the user wants to see `invalid` next to a host that cannot log
       in). Extend the `printf` that appends to `$HOSTS` to six tab-separated columns: slug, name, host, port,
       `$KEY_FP`, `$KEY_TYPE`, and put a one-line comment above it naming the six columns.

    4. `haos-monitor/status.sh`: just before the final JSON printf block, look up the two columns for `$SLUG` in
       `${HOSTS_FILE:-/etc/haos-monitor.hosts}` (same override variable name `hosts.cgi`, `metrics.cgi` and
       `incidents.cgi` already use), with two `awk -F'\t' -v s="$SLUG" '$1 == s {print $5; exit}'` style lookups (column
       5, then column 6), stderr discarded. Pipe the first through `tr -cd` keeping only `A-Za-z0-9+/:=_-` (put the
       hyphen last) into `key_fp`, the second through `tr -cd` keeping only `A-Za-z0-9_-` into `key_type`. The filter is
       what keeps the values safe inside the JSON string, so do not drop it. Append `"key_fp":"%s","key_type":"%s"` to
       the last printf after `kmsg_last`, passing `"$key_fp" "$key_type"`. Missing columns must yield empty strings.
       No `set -e`/`set -u` is added to this file.

    5. Do not change the `Dockerfile`; only if the docker stage's ssh-keygen availability assertion fails, add
       `openssh-keygen` to the existing `apk add` line (then the local-build rule applies, which the docker stage
       already satisfies).

    6. Run the `fingerprint`, `status` and `docker` stages until all pass.
  </action>
  <verify>
    <automated>bash .planning/quick/261031-srb-haos-monitor-show-ssh-key-fingerprint-pe/261031-srb-verify.sh fingerprint status docker && shellcheck -e SC1091 -e SC2034 haos-monitor/run.sh haos-monitor/status.sh .planning/quick/261031-srb-haos-monitor-show-ssh-key-fingerprint-pe/261031-srb-verify.sh</automated>
  </verify>
  <done>
    Baseline at HEAD: `grep -c key_fp` and `grep -c key_fingerprint` are 0 in run.sh and status.sh, and the verify script
    does not exist. After the task: the three stages print `STAGE <name> OK`; the real container serves `key_fp`/`key_type`
    in `/api/status.json` equal to `ssh-keygen -l -f key.pub` for the intact and the space-flattened key, `invalid` for
    the damaged key, the hosts file has 6 columns, other endpoints still work, and no private key material or key
    comment shows up anywhere. The local `docker build` succeeded.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Show the fingerprint on the status page and as MQTT problem-sensor attributes</name>
  <files>haos-monitor/index.html, haos-monitor/mqtt.sh</files>
  <read_first>
    haos-monitor/index.html (CSS block, el()/num()/uptime() helpers, render())
    haos-monitor/mqtt.sh (PROBLEM_ATTRS, config_json)
    .planning/quick/261031-srb-haos-monitor-show-ssh-key-fingerprint-pe/261031-srb-verify.sh (stages mqtt and ui)
  </read_first>
  <behavior>
    Stage `mqtt` of the verify script:
    - `grep '^PROBLEM_ATTRS=' haos-monitor/mqtt.sh` yields exactly one line, which contains
      `'key_fingerprint': value_json.key_fp` and `'key_type': value_json.key_type`, and still contains the old
      `'reasons': value_json.reasons` and `'kmsg_last': value_json.kmsg_last`.
    - Render check: if `uv run --with jinja2 python3 -c 'import jinja2'` itself fails, print `SKIP jinja render` and
      continue; otherwise strip the surrounding double quotes from that line, render it with Jinja2 using a
      `value_json` taken from a real `status.sh` run on the `good_host` fixture, parse the result with `json.loads` and
      assert `key_fingerprint` and `key_type` equal the fixture values and `reasons` is present.

    Stage `ui` of the verify script:
    - `grep -c 'keyText('` on `haos-monitor/index.html` is at least 2 (definition plus use) and `grep -c 'SSH key'`
      is at least 1 (both 0 at HEAD).
    - Syntax: the body of the inline `<script>` (lines between the `<script>` and `</script>` tags) is written to a
      temp `.js` file and passes `node --check`.
    - Behavior of `function keyText(s)` (extracted with `sed -n '/^function keyText/,/^}/p'` and evaluated in `node`):
      `{key_fp: "SHA256:abc", key_type: "ED25519"}` gives `ED25519 SHA256:abc`; `{key_fp: "SHA256:abc", key_type: ""}`
      gives `SHA256:abc`; `{key_fp: "invalid", key_type: ""}` gives `invalid`; `{key_fp: ""}` and `{}` give the en dash
      `–` (the same character `num()` uses).
  </behavior>
  <action>
    Implements D-02 for the UI and MQTT surfaces; the data already arrives in the status JSON from Task 1.

    1. `haos-monitor/index.html`: add a pure helper `function keyText(s)` after the existing `num`/`pad` helpers, written
       as a multi-line top-level function so its closing brace sits at column 0 (the verify script extracts it by sed
       range). Contract: empty or missing `s.key_fp` returns `–`; `s.key_fp === "invalid"` returns `invalid`; otherwise
       the type (when non-empty) followed by one space and the fingerprint. In `render()`, directly after the ports
       chips (`c.appendChild(chips)`) and before the "Blocked tasks" block, append one `div` of class `key` (plus
       class `bad` when `s.key_fp === "invalid"`) built with the existing `el()` helper: a `dim` span with the text
       `SSH key ` followed by a span with `keyText(s)`. Use `textContent` through `el()` only, never `innerHTML` (the
       value is already filtered in `status.sh`, this is defense in depth). Add two CSS rules next to the `.chips`
       rules: `.key` (small monospace-friendly line: `margin: 8px 0 0; font-size: 12px; word-break: break-all;`) and
       `.key.bad` (color `var(--bad)`, font-weight 600). Do not touch `ROWS`, `PORTS`, `FMT`, `tick()` or the polling.

    2. `haos-monitor/mqtt.sh`: extend the single-line `PROBLEM_ATTRS` dict by appending
       `'key_fingerprint': value_json.key_fp, 'key_type': value_json.key_type` immediately before the closing brace and
       the `| tojson` filter. This reuses the existing `json_attributes_template` mechanism of the `problem` binary
       sensor (D-02); do not add an entity to `ENTITIES`, do not touch `config_json`, topics or availability. Reason in
       the comment above `PROBLEM_ATTRS`: the key is the first suspect when `stale` fires because SSH login fails. The
       discovery config is republished at every add-on start, so the new attributes appear after the restart.

    3. Run the `mqtt` and `ui` stages until both pass.
  </action>
  <verify>
    <automated>bash .planning/quick/261031-srb-haos-monitor-show-ssh-key-fingerprint-pe/261031-srb-verify.sh mqtt ui && shellcheck -e SC1091 -e SC2034 haos-monitor/mqtt.sh</automated>
  </verify>
  <done>
    Baseline at HEAD: `grep -c key_fp` is 0 in index.html and mqtt.sh, `grep -c keyText` is 0 in index.html. After the
    task: stages `mqtt` and `ui` print `STAGE <name> OK`, the page script parses, `keyText` returns the specified
    strings for the five cases, and the rendered `PROBLEM_ATTRS` template carries `key_fingerprint` and `key_type` next
    to the old attributes. Visual layout is not machine-checked; `.key` is a plain text line under the port chips.
  </done>
</task>

<task type="auto">
  <name>Task 3: Document the field, add the changelog entry, bump the subpatch to 0.6.1-1 and run the full verification</name>
  <files>haos-monitor/DOCS.md, haos-monitor/CHANGELOG.md, haos-monitor/config.yaml</files>
  <read_first>
    haos-monitor/DOCS.md (Options, Evidence in the log, Web UI, Status endpoint, MQTT sections)
    haos-monitor/CHANGELOG.md (entry style)
    .claude/skills/update-version/SKILL.md (subpatch rule, NO_TAG)
    internal/update-version.py (main(): tag creation and push happen by default)
  </read_first>
  <action>
    Implements D-05 (docs, changelog, version) and finishes D-06 (full verification, commit). Use `Edit` on existing
    files, never `Write`.

    1. `haos-monitor/DOCS.md`:
       - Add a new section `## SSH key fingerprint` between the paragraph that ends "the others keep running." and
         `## Evidence in the log`. Content: at start the add-on derives the public key from each configured private key
         (the same file the monitor logs in with) and shows the SHA256 fingerprint plus key type, e.g. `ED25519
         SHA256:xsND1Padt7j…` (use an abbreviated example ending in an ellipsis, never a full-looking fingerprint, because
         gitleaks scans the staged diff). It is a PUBLIC-key fingerprint, the same format as `ssh-keygen -lf <key>.pub`
         and `ssh-keygen -lf authorized_keys` on the host, so compare the two; it is not sensitive. The private key and
         the key comment are never shown or logged. List where it appears: the status page line "SSH key", the status
         JSON fields `key_fp` and `key_type`, the attributes `key_fingerprint` and `key_type` of the `problem` binary
         sensor, and the startup log line. `invalid` means `ssh-keygen` cannot read the key (damaged or truncated paste,
         or passphrase-protected: the monitor connects non-interactively and cannot use a passphrase); the host stays
         monitored and will go `stale` because SSH login fails. An empty `key_fp` means no value is known. The value is
         computed at add-on start, so restart after changing the key.
       - Web UI paragraph: add the SSH key fingerprint to the list of what each host card shows.
       - Status endpoint paragraph: the strings are now `reasons`, `dstate_tasks`, `kmsg_last`, `key_fp` and `key_type`.
       - MQTT bullet about `binary_sensor.…_problem` attributes: add `key_fingerprint` and `key_type`, and add `key_fp`
         and `key_type` to the sentence listing the status JSON fields.
       - Do not change the Options table or the Metrics table (prettier would require re-aligning them).

    2. `haos-monitor/CHANGELOG.md`: insert above `## [0.6.1]` a new entry headed `## [0.6.1-1] - 2026-10-31` with one
       bullet: the status page, `/api/status.json` (`key_fp`, `key_type`) and the `problem` sensor attributes
       (`key_fingerprint`, `key_type`) now show the SHA256 fingerprint and type of each host's SSH key, the fingerprint
       is computed from the configured private key at start, an unreadable key shows `invalid`, plus a startup log line.

    3. Version bump as its own step, add-on-only change (D-05, D-07). Read the current value first (`grep '^version:'
       haos-monitor/config.yaml` shows `0.6.1-0`). Dry run: `./internal/update-version.py haos-monitor 0.6.1-1
       --dry-run --no-tag`. Apply: `make update-version ADDON=haos-monitor VERSION=0.6.1-1 NO_TAG=yes`. `NO_TAG=yes`
       is required: without it the script creates and pushes the tag `haos-monitor/v0.6.1-1` to origin (D-07: no push).
       Never pass plain `0.6.1` (resets the subpatch to `-0`) and do not hand-edit version strings. Only `config.yaml`
       may change among the version files (`build.yaml` and `README.md` carry no subpatch); the make target runs
       `validate-versions` itself.

    4. Format and lint: run `pre-commit run --files haos-monitor/DOCS.md haos-monitor/CHANGELOG.md haos-monitor/config.yaml
       haos-monitor/run.sh haos-monitor/status.sh haos-monitor/mqtt.sh haos-monitor/index.html
       .planning/quick/261031-srb-haos-monitor-show-ssh-key-fingerprint-pe/261031-srb-verify.sh`. Prettier reflows prose
       to 120 columns and may rewrite the markdown on the first run (the run then reports failure); re-run until it
       passes. If gitleaks flags a docs example, shorten the example, do not add allowlist entries.

    5. Final gate, then commit once per the commit policy in `<context>` (stage by path, no Co-Authored-By, no push, no
       STATE.md/ROADMAP.md edits). The final gate re-runs every verify stage including the Docker build, because
       Task 2 changed files after Task 1's build.
  </action>
  <verify>
    <automated>bash .planning/quick/261031-srb-haos-monitor-show-ssh-key-fingerprint-pe/261031-srb-verify.sh fingerprint status mqtt ui docker && make validate-versions && test "$(grep -c '^version: "0\.6\.1-1"$' haos-monitor/config.yaml)" = 1 && git diff --quiet -- haos-monitor/build.yaml haos-monitor/README.md && test "$(grep -c '^## \[0\.6\.1-1\] - 2026-10-31$' haos-monitor/CHANGELOG.md)" = 1 && test "$(grep -c '^## SSH key fingerprint$' haos-monitor/DOCS.md)" = 1 && grep -q 'key_fp' haos-monitor/DOCS.md && grep -q 'key_fingerprint' haos-monitor/DOCS.md && (pre-commit run --files haos-monitor/DOCS.md haos-monitor/CHANGELOG.md haos-monitor/config.yaml haos-monitor/run.sh haos-monitor/status.sh haos-monitor/mqtt.sh haos-monitor/index.html .planning/quick/261031-srb-haos-monitor-show-ssh-key-fingerprint-pe/261031-srb-verify.sh || pre-commit run --files haos-monitor/DOCS.md haos-monitor/CHANGELOG.md haos-monitor/config.yaml haos-monitor/run.sh haos-monitor/status.sh haos-monitor/mqtt.sh haos-monitor/index.html .planning/quick/261031-srb-haos-monitor-show-ssh-key-fingerprint-pe/261031-srb-verify.sh)</automated>
  </verify>
  <done>
    Baselines at HEAD (all expected to change): `config.yaml` version `0.6.1-0` (gate count 0), `## [0.6.1-1]` heading
    count 0, `## SSH key fingerprint` heading count 0, `key_fp` count 0 in DOCS.md. After the task: all five verify
    stages pass, `config.yaml` is `0.6.1-1` with `build.yaml` and `README.md` untouched, `make validate-versions` and
    pre-commit (prettier, markdownlint, shellcheck, gitleaks, validate-versions) pass on the changed files, DOCS.md
    documents the field and states it is a public-key fingerprint, CHANGELOG.md has the `0.6.1-1` entry, and one local
    commit exists (not pushed, no tag).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| add-on options to run.sh | `ssh_private_key` is secret input; only its public fingerprint may leave `run.sh` |
| run.sh to hosts file to status.sh | tab-separated file in the container; values are re-read by CGI scripts |
| status endpoint to browser and MQTT | `/api/status.json` is unauthenticated inside the add-on network (Ingress is admin-only); values end up in HTML and Jinja |
| ssh-keygen to run.sh | child process output includes the key comment, which can contain user or host names |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-261031-01 | Information disclosure | `key_fingerprint()` in run.sh, log line, hosts file, JSON | high | mitigate | Only the validated `KEY_FP` (regex `^SHA256:[A-Za-z0-9+/]+$`) and `KEY_TYPE` leave the function; the raw `ssh-keygen -l` line (contains the key comment) is never echoed or stored; stderr of both `ssh-keygen` calls is discarded; the key is never passed as an argument. The verify script's `fingerprint` and `docker` stages assert that neither a key-body slice, the text `PRIVATE KEY` nor the secret comment appears in output, logs, hosts file or endpoints. |
| T-261031-02 | Tampering | `key_fp`/`key_type` in the JSON string, the HTML and the MQTT template | medium | mitigate | `status.sh` filters both values with `tr -cd` to the characters a fingerprint or type can contain (no quote, backslash, angle bracket or whitespace), so the JSON stays valid and no markup or template syntax can pass; `index.html` renders through `el()`/`textContent`. The `status` stage feeds a hostile fixture value and asserts valid JSON and no injected field. |
| T-261031-03 | Denial of service | `ssh-keygen -y` prompting for a passphrase during start | medium | mitigate | `-P ''` supplies an empty passphrase and stdin is `/dev/null`, so a passphrase-protected key fails fast to `invalid` instead of blocking `run.sh` (which would stop all hosts and the web server from starting). Covered by the passphrase-protected key case. |
| T-261031-04 | Denial of service | `run.sh` under `set -e` with a key `ssh-keygen` rejects | medium | mitigate | The pipeline assignment has an explicit `|| ` fallback and the function ends with `return 0`; a rejected key yields `invalid` and the host loop continues. Covered by the truncated, replaced-body and passphrase cases run under `sh -e`, and by the Bad Host in the container run. |
| T-261031-05 | Information disclosure | unauthenticated `/api/status.json` exposes the fingerprint | low | accept | A public-key fingerprint is not secret; the endpoint is already unauthenticated by documented design (port closed by default, Ingress admin-only). DOCS.md states that the value is a public-key fingerprint. |
| T-261031-06 | Repudiation | stale fingerprint after the key option changed | low | accept | The value is computed at add-on start from the same file the monitor uses; a restart is needed after changing options anyway, and DOCS.md says so. |
| T-261031-SC | Tampering | npm/pip/cargo installs | high | accept | No package-manager installs in this plan: `ssh-keygen` already ships in the image via `openssh-client`, the verify script uses only tools already on the dev machine (`uv run --with jinja2` is a read-only test dependency fetched at verify time, not shipped). Package legitimacy gate not applicable. |
</threat_model>

<verification>
Source audit (every item covered, nothing unplanned):

| Source | Item | Covered by |
|--------|------|------------|
| GOAL | Show the SSH key fingerprint per host to debug the deployed key | Tasks 1-3 |
| REQ | none (quick task, no phase requirement IDs) | n/a |
| RESEARCH | none (no RESEARCH.md; ssh-keygen presence verified by a probe build of the current image) | Task 1 docker stage re-checks it |
| CONTEXT | D-01 scope only haos-monitor/ | all tasks; verify script kept in the quick dir |
| CONTEXT | D-02 full fingerprint plus type on UI, status.json, MQTT attribute | Task 1 (status.json), Task 2 (UI, MQTT) |
| CONTEXT | D-03 compute in run.sh from KEY_FILE, `invalid` on rejection, no leakage | Task 1 |
| CONTEXT | D-04 hand-off through the existing per-host data path | Task 1 (hosts file columns 5-6) |
| CONTEXT | D-05 subpatch bump, CHANGELOG, DOCS, markdown and shell lint | Task 3 |
| CONTEXT | D-06 local docker build, throwaway key compare, flattened variants, validate-versions, lint | Task 1 (stages), Task 3 (final gate) |
| CONTEXT | D-07 no STATE.md/ROADMAP.md, no push | Task 3 (NO_TAG=yes, commit policy) |
| Deferred | none given | nothing deferred is planned |

Overall checks (run by Task 3): `bash .planning/quick/261031-srb-haos-monitor-show-ssh-key-fingerprint-pe/261031-srb-verify.sh`
with no argument runs all five stages; `make validate-versions`; pre-commit on the eight touched files.
</verification>

<success_criteria>
- The status page, `/api/status.json` and the MQTT `problem` sensor attributes show the SHA256 fingerprint and key type
  of each host's configured key, and the values equal `ssh-keygen -l -f <public key>`, also for newline-flattened keys.
- An unreadable key shows `invalid` without stopping the other hosts or the web server.
- No private key material or key comment is exposed anywhere.
- `config.yaml` is `0.6.1-1`, CHANGELOG.md and DOCS.md are updated and lint-clean, the local `docker build` passed.
- One local commit, nothing pushed, no tag created, STATE.md and ROADMAP.md untouched.
</success_criteria>

<output>
Create `.planning/quick/261031-srb-haos-monitor-show-ssh-key-fingerprint-pe/261031-srb-SUMMARY.md` when done
</output>
