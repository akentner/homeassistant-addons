# Phase 3: Meridian Add-on - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents. Decisions are captured in
> CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04 **Phase:** 03-meridian-add-on **Areas discussed:** Dockerfile build strategy, run.sh credential
check, config.yaml options schema, Supervisor wrapper vs. direct node, node_modules strategy, README/metadata,
validate-versions coverage, hadolint rules

---

## Dockerfile Build Strategy

### Source Fetch

| Option                    | Description                                                                                             | Selected |
| ------------------------- | ------------------------------------------------------------------------------------------------------- | -------- |
| GitHub archive tarball    | curl versioned tarball from rynfar/meridian/archive/refs/tags/v${VERSION}.tar.gz — same as phone-logger | ✓        |
| git clone at build time   | git clone --branch v${VERSION} --depth 1 — needs git, larger image                                      |          |
| npm install from registry | npm install -g @rynfar/meridian@${VERSION} — different artifact than GitHub release                     |          |

**User's choice:** GitHub archive tarball **Notes:** Consistent with phone-logger pattern; deterministic and
reproducible.

### Runtime Stage Dependencies

| Option       | Description                                                                                | Selected |
| ------------ | ------------------------------------------------------------------------------------------ | -------- |
| nodejs + npm | Install both via apk — nodejs to run dist/cli.js, npm to install @anthropic-ai/claude-code | ✓        |
| nodejs only  | Skip npm, copy claude-code from bun build stage                                            |          |

**User's choice:** nodejs + npm

---

## run.sh Credential Check

### Check Target

| Option                       | Description                              | Selected |
| ---------------------------- | ---------------------------------------- | -------- |
| /data/.claude/.claude.json   | Actual auth file written by claude login | ✓        |
| /data/.claude non-empty dir  | Looser check, catches partial state      |          |
| Probe claude CLI auth status | More accurate but slower startup         |          |

**User's choice:** `/data/.claude/.claude.json`

### Fail Behavior

| Option                             | Description                                            | Selected |
| ---------------------------------- | ------------------------------------------------------ | -------- |
| Fail immediately with instructions | Print instructions and exit 1 — HA marks add-on failed | ✓        |
| Poll until credentials appear      | Loop/sleep, auto-starts once credentials appear        |          |

**User's choice:** Fail immediately with instructions

---

## config.yaml Options Schema

### User Options

| Option                    | Description                                     | Selected |
| ------------------------- | ----------------------------------------------- | -------- |
| Zero-config               | No user options — empty options/schema sections |          |
| log_level only            | Single option for debugging                     |          |
| log_level + port override | Two options: verbosity and port flexibility     | ✓        |

**User's choice:** log_level + port override (default 3456)

### Port Declaration

| Option                       | Description                                              | Selected |
| ---------------------------- | -------------------------------------------------------- | -------- |
| Declare in ports section     | 3456/tcp in config.yaml ports section — visible in HA UI | ✓        |
| host_network: true           | Skip port declaration, bind to host network              |          |
| No explicit port declaration | Rely on MERIDIAN_HOST=0.0.0.0 only                       |          |

**User's choice:** Declare in ports section

---

## Supervisor Wrapper vs. Direct Node

### Process Management Approach

| Option                         | Description                                                       | Selected |
| ------------------------------ | ----------------------------------------------------------------- | -------- |
| Use upstream supervisor script | exec claude-proxy-supervisor.sh — handles SDK crashes, 1s restart |          |
| Direct node, let HA restart    | exec node dist/cli.js — simpler, HA restarts on crash             |          |
| Custom S6 service              | Most idiomatic for HA base images                                 | ✓        |

**User's choice:** Custom S6 service

### S6 Implementation Style

| Option                                      | Description                                                     | Selected |
| ------------------------------------------- | --------------------------------------------------------------- | -------- |
| S6 via run.sh exec + HA restart config      | run.sh execs node directly, S6 wraps it                         | ✓        |
| Full S6 overlay service directory           | rootfs/etc/s6-overlay/s6-rc.d/meridian/ with run+finish scripts |          |
| bashio shebang + exec (standard HA pattern) | Standard HA add-on, S6 wraps automatically                      |          |

**User's choice:** S6 via run.sh exec + HA restart config (consistent with existing add-on pattern)

---

## node_modules Strategy

| Option                       | Description                                                       | Selected |
| ---------------------------- | ----------------------------------------------------------------- | -------- |
| Copy from build stage        | COPY node_modules from bun stage to runtime — zigbee2mqtt pattern | ✓        |
| npm install in runtime stage | Only copy dist/, re-install node_modules in runtime               |          |

**User's choice:** Copy from build stage

---

## README and config.yaml Metadata

| Option                                    | Description                    | Selected |
| ----------------------------------------- | ------------------------------ | -------- |
| rynfar/meridian (upstream)                | url points to upstream project |          |
| akentner/homeassistant-addons (this repo) | Consistent with other add-ons  | ✓        |

**User's choice:** `https://github.com/akentner/homeassistant-addons`

---

## validate-versions Hook Coverage

| Option                           | Description                                                | Selected |
| -------------------------------- | ---------------------------------------------------------- | -------- |
| Auto-covered, no changes needed  | Dynamic find already covers new add-ons                    |          |
| Verify pre-commit files: pattern | Check that .pre-commit-config.yaml includes meridian paths | ✓        |

**Notes:** Investigation revealed that `.pre-commit-config.yaml` has a hardcoded `files:` pattern —
`^(fritz-callmonitor2mqtt|phone-logger)/(config\.yaml|build\.yaml|README\.md)$` — that does NOT auto-include new
add-ons. The pattern must be updated to add `|meridian`. This is now in-scope (D-15).

---

## Hadolint Rules

| Option                                        | Description                                       | Selected |
| --------------------------------------------- | ------------------------------------------------- | -------- |
| Existing rules + DL3016 for npm -g            | Add DL3016 for npm install -g without version pin | ✓        |
| Discover needed ignores during implementation | Add only rules that actually fire                 |          |
| No changes needed                             | Existing 4 rules are sufficient                   |          |

**User's choice:** Existing rules + DL3016 preemptively

---

## Agent's Discretion

- Exact error message text for the credential-missing guard
- Whether to configure HA restart policy in config.yaml
- `build.yaml` base image version tag
- `DOCS.md` content structure

## Deferred Ideas

None.
