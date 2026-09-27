---
quick_id: "260927-vwt"
slug: "docs-add-on-presentation-metadata-best-p"
description: "docs: add-on presentation & metadata best practices (icon/logo, translations, changelog)"
date: "2026-09-27"
status: planned
---

# Quick Task: Add-on Presentation & Metadata Best Practices

## Goal

Add a new "Add-on Presentation & Metadata" best-practices section to `docs/DEVELOPMENT.md` — the repo-wide
reference doc. This is documentation-only: no code changes, no add-on directory touched, no version bump (this is
a repo-level file, not part of any single add-on's 3-file version sync).

`docs/DEVELOPMENT.md` currently has exactly 6 top-level `##` sections (confirmed via `grep -n "^## "
docs/DEVELOPMENT.md`): Versioning Rules, Version Update Tool, Auto-Update System, Pre-commit Validation, Security
Scanning, GitHub Actions Reusable Build Workflows. The new section is inserted as a 7th, positioned right after
`## Auto-Update System` and right before `## Pre-commit Validation` (thematically: per-add-on required-file
conventions, same tier as Versioning Rules, before the CI/validation-focused sections).

The content below has already been fact-checked against this repository's current state and against HA's own
developer docs (fetched live this session) — use it verbatim rather than re-deriving the facts, several of which
correct easy-to-assume-wrong details:

- HA's **enforced** rule for `icon.png` is the 1:1 (square) aspect ratio — 128x128px is only the *recommended*
  size, not a hard pixel requirement. (`litellm/icon.png` is 512x512 and still valid because it's square.)
- `logo.png` currently exists for **two** add-ons in this repo (`cups`, `gatus`), not one.
- Only `cups/translations/` exists today; no other add-on has adopted the translations convention yet.
- 8 of 11 add-ons have a `CHANGELOG.md`; `cups`, `iac-runner`, and `terraform-bridge` do not yet.

## Must-Haves

- [ ] `docs/DEVELOPMENT.md` gains exactly one new top-level `## Add-on Presentation & Metadata` section, inserted
      immediately after the `## Auto-Update System` section and immediately before `## Pre-commit Validation`
- [ ] The new section contains exactly four `###` subsections, in this order: `### Icon & Logo`,
      `### Translations`, `### CHANGELOG.md`, `### Other Operational Lessons`
- [ ] `### Icon & Logo` states the aspect-ratio-is-the-enforced-rule / 128x128-is-only-recommended distinction,
      and cites `litellm/icon.png` (512x512) as a compliant example
- [ ] `### Icon & Logo` correctly states that `cups` and `gatus` currently ship `logo.png` (not just one add-on)
- [ ] `### Translations` correctly states that only `cups/translations/` exists in the repo today
- [ ] `### CHANGELOG.md` correctly states that `cups`, `iac-runner`, and `terraform-bridge` do not have one yet
      (8 of 11 add-ons do)
- [ ] `### Other Operational Lessons` covers all five items from the content block below (schema nesting cap,
      host_network mDNS sibling conflict, log tail -F + shutdown trap, `/data` persistence, no bare-`X.Y.Z` bump)
      without duplicating the existing `## Versioning Rules` section's content — cross-reference it instead
- [ ] No other section of `docs/DEVELOPMENT.md` is modified — diff is additive-only, one new section
- [ ] No add-on directory, no other docs file, and no `STATE.md`/`ROADMAP.md` edit beyond what the quick-task
      workflow itself normally performs
- [ ] `make lint` passes cleanly (prettier/markdownlint apply to this file — one auto-fix-then-rerun cycle is
      expected and fine, see Verify)
- [ ] No `Co-Authored-By` line in the commit (repo hard rule, root `CLAUDE.md`)

## Tasks

### T1: Insert the "Add-on Presentation & Metadata" section into `docs/DEVELOPMENT.md`

**Files:** `docs/DEVELOPMENT.md`

**Action:**

1. Read `docs/DEVELOPMENT.md`'s current full content first, so you can locate the exact insertion point. Confirm
   via `grep -n "^## " docs/DEVELOPMENT.md` that it shows exactly 6 top-level headings and that `## Auto-Update
   System` is immediately followed by `## Pre-commit Validation` (no other section between them).

2. Using the Edit tool, insert the block below verbatim, as a new section, directly after `## Auto-Update
   System`'s last line (`- Automatic reset of subpatch to \`-0\``) and its trailing blank line, and directly
   before the `## Pre-commit Validation` heading. Do not alter the content of `## Auto-Update System` or
   `## Pre-commit Validation` themselves — only insert the new block between them, separated by blank lines
   matching the existing file's spacing convention (one blank line between a section's last line and the next
   `##` heading).

3. The verbatim content to insert (outer fence uses 4 backticks only to escape the nested 3-backtick examples
   inside it — do not include the outer 4-backtick fence lines themselves in the inserted content, only what is
   between them):

````markdown
## Add-on Presentation & Metadata

Add-ons are also judged by how they present in the Supervisor UI and by how well their metadata communicates
changes and config options to the user. This section covers icon/logo conventions, per-add-on translations, and
CHANGELOG.md practice, plus a handful of hard-won operational lessons from add-ons built in this repo.

### Icon & Logo

| File       | Format | Aspect ratio                 | Recommended size | Shown at                            |
| ---------- | ------ | ----------------------------- | ------------------ | -------------------------------------- |
| `icon.png` | PNG    | 1:1 (square) — **enforced**   | 128x128px           | Add-on store list                       |
| `logo.png` | PNG    | flexible                      | ~250x100px          | Top of the add-on's own detail page     |

(source: developers.home-assistant.io/docs/add-ons/presentation/)

1. **`icon.png`'s hard rule is the aspect ratio, not the pixel count.** HA requires a square (1:1) icon; 128x128px
   is only the *recommended* size. `litellm/icon.png` ships at 512x512 and is still valid because it stays square
   — don't assume every icon in this repo is literally 128x128px, and don't treat a larger square icon as broken.
2. **`logo.png` is optional but recommended** for add-ons with real upstream branding. As of this writing, `cups`
   and `gatus` ship one; the rest have `icon.png` only (or neither). Add a logo when the upstream project has
   distinct brand assets worth showing.
3. **Prefer the upstream project's own official brand assets over inventing new ones.** Precedent: `cups`'s
   `icon.png` originally shipped a placeholder ("UNIX PRINTING SYSTEM" text mark referencing the archived
   `apple/cups` project); it was replaced with the current upstream mark from `github.com/OpenPrinting/cups`
   (`desktop/cups-128.png` used as-is for `icon.png`, `desktop/cups-256.png` composited onto a 250x100 transparent
   canvas for `logo.png`).
4. **When compositing a square source onto a non-square logo canvas, preserve aspect ratio** — scale and center on
   a transparent background. Never stretch or distort the source to fill the target rectangle.
5. **Always cite the actual current upstream repo** in the add-on's DOCS.md/README.md attribution line (not an
   archived predecessor), and name the license the asset is used under (e.g. Apache License 2.0 for CUPS's marks).

### Translations

Convention (established by `cups`): `{addon}/translations/en.yaml` and `{addon}/translations/de.yaml`, each with a
top-level `configuration:` key mapping every `config.yaml` option name to a `name:` (short label) and
`description:` (fuller explanation — use YAML `>-` folded style for longer text):

```yaml
configuration:
  log_level:
    name: Log Level
    description: Add-on log verbosity (debug, info, warning, error).
```

1. **Language parity is required.** Every option key present in `en.yaml` must have a matching key in `de.yaml`,
   and vice versa.
2. **Keep translations in sync with option semantics, not just written once at option-creation time.** Precedent:
   when `cups`'s `log_level` option's default and behavior changed in a same-day quick task, both `en.yaml` and
   `de.yaml` were updated in the same change — a stale translation describing old behavior is a real, recurring
   risk.
3. **A `translations/` directory is not yet universal in this repo.** As of this writing only
   `cups/translations/` exists; other add-ons rely on plain `config.yaml` schema without translated labels. That
   fallback is acceptable for an add-on with no `translations/` directory yet — don't retrofit a full translations
   setup as a side effect of an unrelated change, but add it when meaningfully expanding that add-on's options.

### CHANGELOG.md

Convention (Keep-a-Changelog style, confirmed via `network-tools/CHANGELOG.md`): `## [X.Y.Z-N] - YYYY-MM-DD`
version headers matching `config.yaml`'s own subpatch-inclusive version string (not `build.yaml`'s upstream-only
version), with `### Added` / `### Changed` / `### Fixed` subsections as applicable, and reference-style compare
links at the bottom:

```markdown
[Unreleased]: https://github.com/akentner/homeassistant-addons/compare/<addon>/vX.Y.Z-N...HEAD
[X.Y.Z-N]: https://github.com/akentner/homeassistant-addons/compare/<addon>/vPREV...<addon>/vX.Y.Z-N
```

1. **Every version bump gets a CHANGELOG.md entry in the same commit/task**, describing the actual user-visible
   change — and, for a bug fix, briefly the root cause if it adds useful context for future readers. Not just
   "bump version". Precedent: `network-tools`'s mDNS-conflict fix entry explains both the fix and why an
   initially-tried alternative (`disable-publishing=yes`) was empirically insufficient.
2. **Keep the `[Unreleased]` link's compare-base updated** to point at the new latest version tag when a new
   version section is added, so it doesn't silently point at a stale prior release.
3. **Not every add-on has one yet.** As of this writing, 8 of 11 add-ons carry a `CHANGELOG.md` (`authentik`,
   `coding-assistants`, `gatus`, `litellm`, `markdown-renderer`, `meridian`, `network-tools`, `phone-logger`);
   `cups`, `iac-runner`, and `terraform-bridge` do not — start one on that add-on's next version bump rather than
   backfilling history retroactively.

### Other Operational Lessons

A handful of real bugs fixed in this repo generalize into rules worth following in any add-on:

1. **Options-schema nesting is capped at 2 levels.** HA's add-on options schema micro-language supports nested
   arrays/dicts to a maximum depth of two (developers.home-assistant.io/docs/add-ons/configuration/). A deeper
   structure must be flattened — typically by hoisting the inner structure to its own top-level list of objects
   with an explicit foreign-key field pointing back to its parent. This repo did exactly that for `cups`'s
   `printer_presets` feature (since removed for unrelated reasons — it turned out ineffective for its purpose —
   but the flattening technique remains the correct pattern for any future deeply-nested option).
2. **`host_network: true` add-ons that broadcast on the network must be conscious of siblings.** Two
   `host_network` add-ons on the same host share the exact same host IP addresses. If both run independent
   avahi-daemons that each publish address/reverse-PTR records by default, they perpetually and mutually reject
   each other's records as RFC 6762 conflicts, causing an endless hostname-rename loop on both sides. An add-on
   that only needs to *browse* mDNS (not advertise itself) should ship an `avahi-daemon.conf` with
   `publish-addresses=no` to opt out entirely — `network-tools` shipped exactly this fix in `0.5.0-3`.
3. **Surface an internal daemon's own log files to the add-on's log output.** A service that logs to its own
   files (not stdout) inside the container is invisible to `ha apps logs` / `docker logs` by default. Background
   a `tail -F` on the relevant log file(s) from `run.sh` after starting the service, gated by a configurable
   `log_level`-style option, and add that background process to the container's shutdown trap so it doesn't block
   clean termination.
4. **Persistent state belongs under `/data`, not the container's writable layer.** Anything needing to survive a
   restart or image update — a small state file, a history log, generated config that must stay stable across
   restarts — must be written under `/data`, never under `/etc`, `/tmp`, or `/var` inside the image layer, which
   resets on every recreation.
5. **Never bump a version with a bare `X.Y.Z`** — always pass the explicit full `X.Y.Z-N` string via
   `make update-version ADDON=<name> VERSION=<explicit-string>`. See `## Versioning Rules` above; this is the same
   hard rule, repeated here only as a pointer, not duplicated.
````

4. After inserting, re-read the file to confirm blank-line spacing around the new section matches the rest of the
   document (one blank line before the `##` heading, one blank line after the section's last line, before the
   next `##` heading).

**Verify:**

```bash
grep -n "^## " docs/DEVELOPMENT.md
```

Expect 7 lines, with `## Add-on Presentation & Metadata` appearing between `## Auto-Update System` and
`## Pre-commit Validation`.

```bash
awk '/^## Add-on Presentation & Metadata/,/^## Pre-commit Validation/' docs/DEVELOPMENT.md | grep -c "^### "
```

Expect `4`.

```bash
make lint
```

`make lint` runs `pre-commit run --all-files`, which includes the prettier hook for Markdown. On a hand-authored
insertion, prettier commonly reformats table/list spacing on its first pass — pre-commit reports the run as
failed but the file is now reformatted. **Run `make lint` a second time** to confirm a clean pass with no further
modifications. Fix anything markdownlint flags (e.g. MD040 missing code-fence language) and re-run until both
prettier and markdownlint are green.

```bash
git diff --stat
```

Expect exactly one file changed: `docs/DEVELOPMENT.md`.

**Done:** `docs/DEVELOPMENT.md` has 7 top-level `##` sections in the correct order; the new section has exactly 4
`###` subsections in the specified order and content; `make lint` passes clean on a repeated run; `git diff --stat`
shows only `docs/DEVELOPMENT.md` changed; no other file is touched.

## Files Changed

- `docs/DEVELOPMENT.md` (new `## Add-on Presentation & Metadata` section inserted after `## Auto-Update System`
  and before `## Pre-commit Validation`; no other section modified)

## Out of Scope

- Actually creating/replacing `cups/logo.png` or `cups/icon.png` — that is the separate, already-planned quick
  task `260927-vbk`, currently executing on a worktree branch (`worktree-agent-a2b49470d4133d43c`), not part of
  this docs-only task
- Resizing `litellm/icon.png` to 128x128 — it is already spec-compliant (square) and out of scope for a docs task
- Backfilling `translations/` or `CHANGELOG.md` for any add-on that lacks one — this task documents the
  convention, it does not retrofit it repo-wide
- Any add-on directory, `Makefile`, `internal/` script, or `.github/workflows/` file
- `STATE.md` / `ROADMAP.md` edits beyond what the quick-task workflow itself performs automatically
- A version bump of any kind (this is a repo-level docs file, not part of any add-on's 3-file version sync)
