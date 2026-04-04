# Retrospective

## Milestone: v1.0 — MVP

**Shipped:** 2026-04-04 **Phases:** 3 | **Plans:** 6 **Timeline:** 2026-04-03 → 2026-04-04 (2 days)

### What Was Built

1. CI quality gate fixed: `validate-versions` hook covers all add-ons, hadolint v2.14.0 active with HA-specific rules
2. Auto-update GitHub Actions workflow: zero-touch daily upstream version sync via `gh` CLI + `update-version.py`
3. Meridian add-on: Claude Max → Anthropic-compatible proxy, bun build stage + HA runtime, OAuth persistence via
   `/data/.claude`

### What Worked

- **GSD phasing**: Breaking the work into 3 focused phases (quality → automation → new add-on) kept each execution clean
  and independently verifiable
- **Worktree pattern for Meridian**: Isolating the multi-stage Dockerfile in a worktree prevented CI noise during
  development
- **Plan self-checks**: Every plan included a `Self-Check: PASSED` block — made verification trivial
- **3-file versioning**: Existing versioning convention required zero rethinking for the new meridian add-on

### What Was Inefficient

- ROADMAP.md progress table was not updated mid-milestone (Phase 2 still showed "Not started" when Phase 3 began);
  cosmetic but creates confusion when reading mid-flight
- Phase 01-01 and 01-02 SUMMARY metadata used different frontmatter key styles (`key_files` vs `key-files`) — no
  functional impact but inconsistent

### Patterns Established

- **Multi-stage Node.js HA add-on**: oven/bun:1 build stage + HA amd64-base runtime, copy `dist/` + `node_modules`
- **Credential guard run.sh pattern**: symlink `/root/.claude → /data/.claude`, check for `.claude.json`, exit 1 with
  actionable message if absent, then read bashio config + exec proxy
- **Global hadolint ignore for HA patterns**: DL3006 (dynamic FROM), DL3018 (unpinned apk), DL3059 (multiple RUN),
  DL4006 (pipefail), DL3016 (npm install -g)

### Key Lessons

- The `version_strip` sed workaround (inline `# shellcheck disable=SC2001`) is correct: bash parameter expansion cannot
  handle dynamic regex patterns — document this permanently so it doesn't get revisited
- `GITHUB_TOKEN`-pushed commits do not trigger other workflows by design; add a comment to the workflow file so future
  maintainers don't spend time debugging

### Cost Observations

- Sessions: 1 primary session
- Model: balanced profile (sonnet)
- Notable: entire v1.0 milestone completed in a single day; planning artifacts kept execution tight

---

## Cross-Milestone Trends

| Metric           | v1.0 |
| ---------------- | ---- |
| Phases           | 3    |
| Plans            | 6    |
| Days             | 2    |
| Files changed    | 75   |
| Deviations       | 4    |
| Deviations fixed | 4    |
