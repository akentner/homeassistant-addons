---
quick_id: "260927-wzn"
slug: "fix-internal-update-version-py-tag-timin"
description: "fix: internal/update-version.py tag-timing bug (tag points at pre-bump commit)"
date: "2026-09-27"
status: planned
---

# Quick Task: Fix `internal/update-version.py` Tag-Timing Bug

## Goal

`internal/update-version.py` (invoked via `make update-version ADDON=<name> VERSION=<X.Y.Z-N>`, and transitively by
`make release`) must **never** create or push a git tag that points at a commit which does not actually contain the
version bump the tag names.

**Root cause (confirmed by reading the current file):** `create_and_push_tag()` is called from the tail of `main()`
in the SAME invocation as the file edits (`update_config_yaml`/`update_build_yaml`/`update_readme_md`), but BEFORE
any commit exists for those edits. `git tag` always points at whatever `HEAD` is *right now*; since the version-bump
changes are still uncommitted working-tree changes at that point, the tag necessarily points at the PRE-bump commit.
The script's own "Next steps" output tells the caller to `git add && git commit` the version files as a separate,
later, manual step — by which time the tag has already been created and pushed against the wrong (older) HEAD.

**This bit this exact repo twice in one day** (both documented in this session's own `.planning/quick/` SUMMARYs):

- `260927-r2j` (`.planning/quick/260927-r2j-cups-remove-airprint-print-presets-featu/260927-r2j-SUMMARY.md`):
  `make update-version ADDON=cups VERSION=0.1.0-12` created+pushed `cups/v0.1.0-12` pointing at a commit whose
  `config.yaml` still read `0.1.0-11`. Manually deleted and recreated after discovery.
- `260927-vbk` (`.planning/quick/260927-vbk-cups-add-logo-png-banner-configurable-lo/260927-vbk-SUMMARY.md`):
  the same class of bug recurred for `cups/v0.1.0-13` — the corrected tag could not even be re-pushed to origin in
  that session (blocked by the destructive-git-action guard) and is flagged there as still needing a manual fix.

**Fix mechanism (goal-backward from the two incidents, not a rigid spec — implemented exactly, see T1):** before
tagging, check whether the exact files this script just wrote (`config.yaml`/`build.yaml`/`README.md`, plus the
co-located Provider's `build.yaml` for `terraform-bridge`) are dirty per `git status --porcelain`. If dirty, the
version bump has not been committed yet, so tagging is deferred (not an error — file edits still succeeded) with a
clear message telling the caller to commit first, then re-run (idempotent: a second run with matching files is a
no-op file-edit-wise and, with a now-clean tree, proceeds straight to a correct tag). If clean (already committed, or
this run made no changes because the target version was already in place), HEAD provably holds the named version, so
tagging proceeds exactly as today. The existing "tag already exists locally/on origin" skip-logic and the
never-force-push design are untouched.

**Also correct** `docs/UPDATE_VERSION.md` (documents the current buggy "edit → tag immediately → commit later" flow
in its worked example) and `docs/DEVELOPMENT.md`'s short "Version Update Tool" pointer section, so both describe the
corrected commit-before-tag ordering.

**Testing:** no automated test exists for `internal/update-version.py` today. Add one that reproduces the bug and
proves the fix against a real throwaway git repo (pure git operations, no Docker) — and prove it actually fails
against the pre-fix behavior before landing the fix, not just assumed to work.

## Must-Haves

- [ ] Running `internal/update-version.py <addon> <version>` with uncommitted version-file changes does **not**
      create or push a tag; it exits 0 (file edits still succeeded) and tells the caller to commit first, then
      re-run
- [ ] Running it again after committing (or when the target version was already in place) **does** create the tag,
      and that tag's commit's `config.yaml` genuinely contains the target version
- [ ] A regression test proves both of the above automatically, without Docker or network, and was proven to
      actually FAIL against the pre-fix behavior before the fix landed (not merely assumed to catch the bug)
- [ ] The regression test is wired into `make check-all` so this class of bug cannot silently regress again
- [ ] `docs/UPDATE_VERSION.md` and `docs/DEVELOPMENT.md` accurately describe the corrected commit-before-tag flow —
      no worked example still implies "edit → tag → commit later" as safe
- [ ] Existing behavior is unchanged: three-file sync, `--no-tag`/`--no-push`/`--check-release` flags, the
      `terraform-bridge` → Provider cross-artifact bump, and the existing-tag skip/never-force-push logic
- [ ] No `Co-Authored-By` line in any commit (repo hard rule)

## Security Notes

- The fix only adds a read-only `git status --porcelain` check scoped to three-to-four known, constant file paths
  (derived from the already-validated `addon_name` argument) before an existing git-tag code path — no new
  untrusted input, no new network call, no `shell=True` (matches the file's existing argv-list `subprocess.run`
  discipline).
- The new regression test operates entirely inside a `mktemp -d` throwaway git repository, cleaned up via `trap ...
  EXIT`, and never touches this repo's own git state or any real remote (`--no-push` is used for both invocations,
  so no `origin` remote is required or contacted).
- No secrets, credentials, or CI workflow files are touched. `.github/workflows/auto-update.yml` already passes
  `--no-tag` (fixed previously in quick task `260909-rll`) and is unaffected by this change; this fix only changes
  the *default* (no-flag) path used by local/manual `make update-version` and `make release` invocations.

## Tasks

### T1: Fix the tag-timing bug in `internal/update-version.py`

**Files:** `internal/update-version.py`

**Action:**

1. Before making any edit, save an unmodified copy of the current (pre-fix) script somewhere OUTSIDE this repo's
   working tree, for later use in T2's RED proof — e.g. your session's scratchpad directory (if your environment
   provides one) or a plain `mktemp` path, such as `cp internal/update-version.py /tmp/update-version-pre-fix.py`.
   Record the exact path you used. Do not commit this copy; it is a throwaway reference file only.

2. Insert this new helper function immediately above `def create_and_push_tag(version: str, addon_name: str, push:
   bool = True, dry_run: bool = False) -> bool:` (currently the function starting at line 199):

   ```python
   def files_have_uncommitted_changes(paths: list) -> bool:
       """Return True if any of the given paths carry uncommitted changes in git.

       Scoped to exactly these paths via `git status --porcelain -- <paths>` so the
       check is blind to any OTHER unrelated dirty file elsewhere in the working
       tree (e.g. an in-progress edit to a different add-on). Nonexistent paths are
       skipped rather than passed to git, which would otherwise report them as
       untracked-and-therefore-dirty for the wrong reason.
       """
       import subprocess

       existing = [str(p) for p in paths if p.exists()]
       if not existing:
           return False
       result = subprocess.run(
           ["git", "status", "--porcelain", "--"] + existing,
           capture_output=True, text=True
       )
       return bool(result.stdout.strip())
   ```

3. Replace the entire tail of `main()` — from the `print()` immediately after the `readme_success, readme_changes =
   update_readme_md(...)` call through the final `return 0` (currently these exact lines):

   ```python
       print()
       print(f"📊 {'Would update' if args.dry_run else 'Updated'} {success_count}/{total_files} files")

       # Tag creation is independent of how many files needed updating. Subpatch-only
       # bumps only touch config.yaml (build.yaml/README stay on the same SemVer), and
       # no-op confirmations shouldn't silently drop the tag request.
       if args.dry_run:
           if not args.no_tag:
               # Use config_new (with subpatch) so the tag matches the OCI image tag
               # the build workflow publishes. See comment at the update_*() calls
               # above for why this is the canonical source.
               print(f"\n🏷️  Would also create and push tag {args.addon_name}/v{config_new}")
           return 0

       if success_count == total_files:
           print("🎉 All files updated successfully!")
       elif success_count == 0:
           print("✅ Already at target version — confirming tag")
       else:
           print(f"ℹ️  {success_count}/{total_files} files needed updating (others already matched target)")

       if not args.no_tag:
           print()
           print("🏷️  Creating and pushing git tag...")
           tag_ok = create_and_push_tag(
               config_new,
               args.addon_name,
               push=not args.no_push,
               dry_run=False,
           )
           if not tag_ok:
               print()
               print("⚠️  Tag push failed — push manually:")
               print(f"   git push origin {args.addon_name}/v{config_new}")
               return 1

       print("\n💡 Next steps:")
       print("   • Run 'make validate-versions' to verify")
       print("   • Run 'make check-all' for full validation")
       print(f"   • Commit: git add {args.addon_name} && git commit -m 'chore: update {args.addon_name} to v{args.new_version}'")
       if args.no_tag:
           # The tag was deliberately not created, so do not suggest pushing one
           # that does not exist — the release step creates it.
           print(f"   • Push:  git push origin main   (tag skipped; release with: "
                 f"make update-version ADDON={args.addon_name} VERSION={args.new_version})")
       else:
           print(f"   • Push:  git push origin main {args.addon_name}/v{config_new}")
       return 0
   ```

   with:

   ```python
       print()
       print(f"📊 {'Would update' if args.dry_run else 'Updated'} {success_count}/{total_files} files")

       # Tag creation is independent of how many files needed updating. Subpatch-only
       # bumps only touch config.yaml (build.yaml/README stay on the same SemVer), and
       # no-op confirmations shouldn't silently drop the tag request.
       if args.dry_run:
           if not args.no_tag:
               # Use config_new (with subpatch) so the tag matches the OCI image tag
               # the build workflow publishes. See comment at the update_*() calls
               # above for why this is the canonical source.
               print(f"\n🏷️  Would also create and push tag {args.addon_name}/v{config_new}")
           return 0

       if success_count == total_files:
           print("🎉 All files updated successfully!")
       elif success_count == 0:
           print("✅ Already at target version — confirming tag")
       else:
           print(f"ℹ️  {success_count}/{total_files} files needed updating (others already matched target)")

       # `git tag` always points at HEAD. The edits above are still UNCOMMITTED
       # working-tree changes at this point in the same invocation, so tagging
       # unconditionally here would tag the PRE-bump commit — a tag that lies
       # about which commit actually holds the version it names. This happened
       # for real, twice, in one day (260927-r2j, 260927-vbk quick tasks): an
       # annotated tag was created+pushed against a commit whose config.yaml
       # still read the OLD version, and had to be manually deleted and
       # recreated. Refuse instead of guessing: if the exact files this script
       # writes are still dirty, defer tagging. A caller who commits and
       # re-runs lands in the success_count == 0 branch above with a clean
       # tree, so the tag path below then correctly tags HEAD.
       tag_action = "skipped_no_tag"
       if not args.no_tag:
           version_file_paths = [addon_dir / "config.yaml", addon_dir / "build.yaml", addon_dir / "README.md"]
           if args.addon_name == "terraform-bridge":
               version_file_paths.append(Path("terraform-provider-homeassistant") / "build.yaml")

           if files_have_uncommitted_changes(version_file_paths):
               tag_action = "skipped_dirty"
               print()
               print("⚠️  Version files changed but not yet committed — refusing to tag the wrong commit.")
               print(f"   Commit them first: git add {args.addon_name} && git commit -m 'chore: update {args.addon_name} to v{args.new_version}'")
               print(f"   Then re-run to create the tag against the correct commit:")
               print(f"   make update-version ADDON={args.addon_name} VERSION={args.new_version}")
               print("   (the re-run is a no-op for the file edits themselves — they already match the")
               print("    target — and will correctly tag HEAD once the working tree is clean)")
           else:
               print()
               print("🏷️  Creating and pushing git tag...")
               tag_ok = create_and_push_tag(
                   config_new,
                   args.addon_name,
                   push=not args.no_push,
                   dry_run=False,
               )
               if not tag_ok:
                   print()
                   print("⚠️  Tag push failed — push manually:")
                   print(f"   git push origin {args.addon_name}/v{config_new}")
                   return 1
               tag_action = "created"

       print("\n💡 Next steps:")
       print("   • Run 'make validate-versions' to verify")
       print("   • Run 'make check-all' for full validation")
       print(f"   • Commit: git add {args.addon_name} && git commit -m 'chore: update {args.addon_name} to v{args.new_version}'")
       if tag_action == "created":
           print(f"   • Push:  git push origin main {args.addon_name}/v{config_new}")
       elif tag_action == "skipped_dirty":
           print(f"   • Push:  git push origin main   (tag deferred until the working tree is clean — see above; "
                 f"re-run make update-version ADDON={args.addon_name} VERSION={args.new_version} after committing to create it)")
       else:
           # args.no_tag was passed deliberately, so do not suggest pushing a tag that does not exist.
           print(f"   • Push:  git push origin main   (tag skipped; release with: "
                 f"make update-version ADDON={args.addon_name} VERSION={args.new_version})")
       return 0
   ```

4. Do not touch `create_and_push_tag()`'s own body, the existing-tag skip/never-force-push logic inside it, the
   argparse surface, `update_config_yaml`/`update_build_yaml`/`update_readme_md`, or the `terraform-bridge` →
   Provider cross-artifact bump block above this tail — this task changes only the tag-decision tail of `main()`
   plus the one new helper function.

**Verify:**

```bash
python3 -m py_compile internal/update-version.py
python3 internal/update-version.py --help >/dev/null
grep -c "files_have_uncommitted_changes" internal/update-version.py   # expect >= 2 (def + call site)
grep -c "refusing to tag" internal/update-version.py                   # expect >= 1
```

**Done:** `internal/update-version.py` compiles, `--help` still works unchanged, the new helper exists and is called
from `main()`'s tag-decision tail, and the tail now branches on `files_have_uncommitted_changes()` before ever
calling `create_and_push_tag()`.

---

### T2: Regression test proving the fix (RED before the fix existed, GREEN after) + wire into `make check-all`

**Files:** `internal/verify-update-version-tag-timing.sh` (new), `Makefile`

**Action:**

1. Create `internal/verify-update-version-tag-timing.sh`:

   ```bash
   #!/usr/bin/env bash
   # Regression test for the update-version.py tag-timing bug (260927-r2j /
   # 260927-vbk incidents, documented in .planning/quick/): create_and_push_tag()
   # used to run in the same invocation as the version-file edits, before any
   # commit existed for them, so the annotated tag always pointed at the PRE-bump
   # commit. This proves, against a real throwaway git repo (no Docker, no
   # network, no origin remote required), that:
   #
   #   1. Tagging is DEFERRED while the version files it just wrote are still
   #      uncommitted (the exact precondition that caused both incidents).
   #   2. Once committed, a re-run creates the tag pointing at the commit that
   #      ACTUALLY contains the bumped version.
   #
   # UPDATE_VERSION_PY may be overridden to point at an alternate copy of the
   # script (e.g. a pre-fix scratch copy) to prove this test fails against the
   # old buggy behavior. Defaults to this repo's own internal/update-version.py.

   set -euo pipefail

   RED='\033[0;31m'
   GREEN='\033[0;32m'
   YELLOW='\033[1;33m'
   NC='\033[0m'

   red()    { echo -e "${RED}$*${NC}"; }
   green()  { echo -e "${GREEN}$*${NC}"; }
   yellow() { echo -e "${YELLOW}$*${NC}"; }

   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
   UPDATE_VERSION_PY="${UPDATE_VERSION_PY:-${SCRIPT_DIR}/update-version.py}"
   FAIL=0

   if [[ ! -f "${UPDATE_VERSION_PY}" ]]; then
       red "FAIL: UPDATE_VERSION_PY not found at ${UPDATE_VERSION_PY}"
       exit 1
   fi

   WORK_DIR="$(mktemp -d)"
   cleanup() { rm -rf "${WORK_DIR}"; }
   trap cleanup EXIT

   yellow "Testing ${UPDATE_VERSION_PY}"
   yellow "Setting up throwaway git repo at ${WORK_DIR}..."
   cd "${WORK_DIR}"
   git init -q
   git config user.email "test@example.invalid"
   git config user.name "verify-update-version-tag-timing"
   git config commit.gpgsign false

   mkdir fakeaddon
   cat > fakeaddon/config.yaml <<'EOF'
   name: "Fake Addon"
   version: "1.0.0-0"
   slug: fakeaddon
   EOF
   cat > fakeaddon/build.yaml <<'EOF'
   build_from:
     amd64: "ghcr.io/home-assistant/amd64-base:3.20"
   args:
     VERSION: "1.0.0"
   EOF
   cat > fakeaddon/README.md <<'EOF'
   # Fake Addon

   [release-shield]: https://img.shields.io/badge/version-v1.0.0-blue.svg
   [release]: https://github.com/akentner/homeassistant-addons/tree/v1.0.0
   EOF

   git add -A
   git commit -q -m "initial state: fakeaddon at 1.0.0-0"
   INITIAL_SHA="$(git rev-parse HEAD)"
   yellow "Initial commit: ${INITIAL_SHA}"

   echo ""
   yellow "Step 1: run update-version.py WITHOUT committing the result..."
   set +e
   STEP1_OUTPUT="$(python3 "${UPDATE_VERSION_PY}" fakeaddon 1.0.0-1 --no-push 2>&1)"
   STEP1_EXIT=$?
   set -e
   echo "${STEP1_OUTPUT}"

   if [[ "${STEP1_EXIT}" -ne 0 ]]; then
       red "FAIL: update-version.py exited ${STEP1_EXIT} on the first (uncommitted) run -- expected 0"
       FAIL=1
   fi

   if echo "${STEP1_OUTPUT}" | grep -qi "refusing to tag"; then
       green "PASS: script refused to tag while version files are uncommitted"
   else
       red "FAIL: script did not report refusing to tag on a dirty working tree"
       FAIL=1
   fi

   if git rev-parse --verify "refs/tags/fakeaddon/v1.0.0-1" >/dev/null 2>&1; then
       red "FAIL: tag fakeaddon/v1.0.0-1 exists after the uncommitted run -- this is the exact bug"
       FAIL=1
   else
       green "PASS: no tag was created while the bump was uncommitted"
   fi

   CURRENT_SHA="$(git rev-parse HEAD)"
   if [[ "${CURRENT_SHA}" != "${INITIAL_SHA}" ]]; then
       red "FAIL: HEAD moved without an explicit commit -- test setup assumption violated"
       FAIL=1
   fi

   echo ""
   yellow "Step 2: commit the version-bump files, then re-run (idempotent)..."
   git add fakeaddon
   git commit -q -m "chore: update fakeaddon to v1.0.0-1"
   BUMP_SHA="$(git rev-parse HEAD)"
   yellow "Bump commit: ${BUMP_SHA}"

   set +e
   STEP2_OUTPUT="$(python3 "${UPDATE_VERSION_PY}" fakeaddon 1.0.0-1 --no-push 2>&1)"
   STEP2_EXIT=$?
   set -e
   echo "${STEP2_OUTPUT}"

   if [[ "${STEP2_EXIT}" -ne 0 ]]; then
       red "FAIL: update-version.py exited ${STEP2_EXIT} on the second (clean) run -- expected 0"
       FAIL=1
   fi

   if git rev-parse --verify "refs/tags/fakeaddon/v1.0.0-1" >/dev/null 2>&1; then
       green "PASS: tag fakeaddon/v1.0.0-1 now exists"
   else
       red "FAIL: tag fakeaddon/v1.0.0-1 was not created on the clean re-run"
       FAIL=1
   fi

   TAG_SHA="$(git rev-parse "fakeaddon/v1.0.0-1^{commit}" 2>/dev/null || echo "MISSING")"
   if [[ "${TAG_SHA}" == "${BUMP_SHA}" ]]; then
       green "PASS: tag points at the bump commit (${BUMP_SHA}), not the stale initial commit"
   else
       red "FAIL: tag points at ${TAG_SHA}, expected the bump commit ${BUMP_SHA}"
       FAIL=1
   fi

   # The exact assertion that would have caught both real incidents: the tagged
   # commit's config.yaml must actually contain the target version.
   TAGGED_CONFIG_VERSION="$(git show "${TAG_SHA}:fakeaddon/config.yaml" 2>/dev/null | grep '^version:' | head -1 || true)"
   if echo "${TAGGED_CONFIG_VERSION}" | grep -q '1.0.0-1'; then
       green "PASS: the tagged commit's config.yaml actually contains 1.0.0-1"
   else
       red "FAIL: the tagged commit's config.yaml reads '${TAGGED_CONFIG_VERSION}', not 1.0.0-1"
       FAIL=1
   fi

   echo ""
   if [[ "${FAIL}" == "1" ]]; then
       red "SOME CHECKS FAILED"
       exit 1
   fi

   green "ALL CHECKS PASSED"
   exit 0
   ```

   Make it executable: `chmod +x internal/verify-update-version-tag-timing.sh`.

2. **Prove RED before trusting the test**: run it against the pre-fix copy you saved in T1 step 1 (substitute the
   exact path you used there for `/tmp/update-version-pre-fix.py` below) —

   ```bash
   UPDATE_VERSION_PY=/tmp/update-version-pre-fix.py bash internal/verify-update-version-tag-timing.sh; echo "exit=$?"
   ```

   This MUST print at least the "tag ... exists after the uncommitted run — this is the exact bug" FAIL line and
   exit with `exit=1` — that is the proof this test actually catches the real bug, not a test that would have
   passed regardless. If it does NOT fail here, the test is not exercising the bug correctly — stop and fix the
   test before proceeding.

3. **Prove GREEN against the fixed script** (the one T1 already edited in the real `internal/`):

   ```bash
   bash internal/verify-update-version-tag-timing.sh; echo "exit=$?"
   ```

   This MUST print `ALL CHECKS PASSED` and `exit=0`.

4. Wire the new script into the Makefile. In `validate-versions:`'s block, insert a new target directly after it and
   before the `# verify-images and verify-images-self-test are deliberately NOT members of check-all...` comment:

   ```makefile
   validate-versions: ## Validate add-on versioning consistency
   	@echo "🔍 Validating add-on versions..."
   	./internal/validate-versions.sh

   # Unlike verify-images below, this is offline, deterministic, and fails only for
   # something in this repo's own internal/update-version.py -- it builds a
   # throwaway git repo in a temp dir and never touches network or Docker. That is
   # exactly the bar check-all's other members meet, so this one joins check-all
   # too (verify-images does not, for the reasons in the comment below).
   verify-update-version-tag-timing: ## Regression-test that update-version.py never tags before the bump commit exists
   	@echo "🔍 Verifying update-version.py's tag-timing fix (pure git, temp repo, no Docker/network)..."
   	./internal/verify-update-version-tag-timing.sh

   ```

   Add `verify-update-version-tag-timing` to the `.PHONY:` line (after `validate-versions`), and add it as a
   prerequisite of `check-all` (after `validate-dockerfiles`):

   ```makefile
   check-all: lint validate-addons validate-versions validate-dockerfiles verify-update-version-tag-timing ## Run all checks (lint + validate + versions + dockerfile args + tag-timing)
   ```

5. Re-run the full gate to confirm nothing else regressed: `make check-all`.

**Verify:**

```bash
bash internal/verify-update-version-tag-timing.sh   # expect: ALL CHECKS PASSED, exit 0
grep -c "verify-update-version-tag-timing" Makefile  # expect >= 3 (.PHONY, target, check-all)
make check-all
```

**Done:** the new test script exists, is executable, was proven to FAIL against the pre-fix script (documented in
the SUMMARY with the exact output/exit code observed) and to PASS against the fixed script; it is wired into
`check-all` via the Makefile; `make check-all` passes end to end.

---

### T3: Correct `docs/UPDATE_VERSION.md` and `docs/DEVELOPMENT.md` to describe the fixed commit-before-tag flow

**Files:** `docs/UPDATE_VERSION.md`, `docs/DEVELOPMENT.md`

**Action:**

1. In `docs/UPDATE_VERSION.md`, replace this sentence (directly under the "What the tool does" table):

   ```markdown
   After updating files, it **creates and pushes the git tag `<addon>/v<config_version>`** (subpatch-suffixed) by default.
   See [Git tag format](#git-tag-format) below for why.
   ```

   with:

   ```markdown
   After updating files, it **creates and pushes the git tag `<addon>/v<config_version>`** (subpatch-suffixed) by
   default — but only once the working tree for these three files is clean (i.e. the version bump is already
   committed, or this run made no changes because the files already matched the target). If the files it just wrote
   are still uncommitted, it defers tagging and tells you to commit first, then re-run. See
   [Commit-before-tag ordering](#commit-before-tag-ordering) for why, and [Git tag format](#git-tag-format) below
   for the tag format itself.
   ```

2. Insert a new section immediately after that table/paragraph and before `## Choosing the right VERSION= value`.
   Note the outer wrapper below uses FOUR backticks specifically because the content it wraps contains its own
   nested three-backtick `bash` block — copy the inner content only (without the outer four-backtick fence) into
   the doc:

   ````markdown
   ## Commit-before-tag ordering

   `git tag` always points at whatever commit is currently `HEAD`. The three file edits above happen in the same
   invocation as the tag step but only produce **uncommitted working-tree changes** — not a commit. If the tool
   tagged unconditionally right after writing the files, the tag would point at HEAD as it was *before* this run,
   i.e. a commit that does **not** yet contain the version bump.

   This bit this repo twice for real in one day (2026-09-27, `260927-r2j` and `260927-vbk` quick tasks): an
   annotated tag was created and pushed against a commit whose `config.yaml` still read the OLD version, and had to
   be manually deleted and recreated after the fact.

   The tool checks `git status --porcelain` scoped to exactly `config.yaml`/`build.yaml`/`README.md` (and, for
   `terraform-bridge`, the co-located Provider's `build.yaml`) before tagging:

   - **Dirty** (these files have uncommitted changes): tagging is deferred. The tool prints a message telling you
     to commit the version bump first, then re-run `make update-version` — the re-run is a no-op for the file edits
     (they already match the target) and, with a clean tree, proceeds straight to a correct tag.
   - **Clean** (either you already committed, or this run made no file changes because the target version was
     already in place): tagging proceeds immediately, since HEAD now provably holds the version the tag names.

   Practical effect: a bump-then-tag flow now needs two steps, not one:

   ```bash
   make update-version ADDON=<addon-name> VERSION=<X.Y.Z-N>
   git add <addon-name> && git commit -m "chore: update <addon-name> to v<X.Y.Z-N>"
   make update-version ADDON=<addon-name> VERSION=<X.Y.Z-N>   # no-op file-wise, now tags HEAD correctly
   ```
   ````

3. In the `## No-op behaviour` section, append this sentence to the existing paragraph:

   ```markdown
   A no-op run against an already-clean working tree is also exactly how the tool creates the tag on a second
   invocation — see [Commit-before-tag ordering](#commit-before-tag-ordering).
   ```

4. In the `## Worked example — subpatch bump` section, insert a commit step between the two invocations — replace
   (both blocks below use a FOUR-backtick outer wrapper only because they contain a nested three-backtick `bash`
   block; copy the inner `bash`-fenced content only into the doc):

   ````markdown
   ```bash
   # Edit code in coding-assistants/ (Dockerfile, run.sh, DOCS.md, …)

   # Confirm the bump without touching the tag yet
   make update-version ADDON=coding-assistants VERSION=1.0.0-2 NO_TAG=yes NO_PUSH=yes

   # When ready to ship:
   ./internal/update-version.py coding-assistants 1.0.0-2
   # → updates files (no-op since already at target)
   # → creates local tag coding-assistants/v1.0.0-2
   # → pushes tag to origin

   # The tag push builds NOTHING. build.yml fires on a push to main touching
   # anything inside an add-on directory, so it is the commit of the version
   # files that publishes the image at ghcr.io/.../1.0.0-2. (A source-only
   # change -- run.sh, a *.py helper, Go sources -- rebuilds it too.)
   ```
   ````

   with:

   ````markdown
   ```bash
   # Edit code in coding-assistants/ (Dockerfile, run.sh, DOCS.md, …)

   # Confirm the bump without touching the tag yet
   make update-version ADDON=coding-assistants VERSION=1.0.0-2 NO_TAG=yes NO_PUSH=yes

   # Commit the version-bump files BEFORE tagging -- git tag always points at
   # HEAD, and HEAD is still the pre-bump commit until this commit lands.
   git add coding-assistants && git commit -m "chore: update coding-assistants to v1.0.0-2"

   # When ready to ship:
   ./internal/update-version.py coding-assistants 1.0.0-2
   # → files already match target (no-op)
   # → working tree for these files is now clean, so it's safe to tag
   # → creates local tag coding-assistants/v1.0.0-2
   # → pushes tag to origin

   # The tag push builds NOTHING. build.yml fires on a push to main touching
   # anything inside an add-on directory, so it is the commit of the version
   # files that publishes the image at ghcr.io/.../1.0.0-2. (A source-only
   # change -- run.sh, a *.py helper, Go sources -- rebuilds it too.)
   ```
   ````

5. In `docs/DEVELOPMENT.md`'s "Version Update Tool" section, replace:

   ```markdown
   The tool updates `config.yaml`, `build.yaml`, and `README.md` badges, then creates and pushes the git tag.
   ```

   with:

   ```markdown
   The tool updates `config.yaml`, `build.yaml`, and `README.md` badges, then creates and pushes the git tag — but
   only once those files are committed (it defers tagging and tells you to commit first if they're still dirty; see
   [Commit-before-tag ordering](UPDATE_VERSION.md#commit-before-tag-ordering)).
   ```

**Verify:**

```bash
grep -c "Commit-before-tag ordering" docs/UPDATE_VERSION.md   # expect >= 1
grep -c "260927-r2j" docs/UPDATE_VERSION.md                    # expect >= 1
grep -c "Commit-before-tag ordering" docs/DEVELOPMENT.md        # expect >= 1
make lint
```

**Done:** both docs describe the corrected two-step commit-then-tag flow; the worked example includes the commit
step between the two invocations; `make lint` passes (prettier/markdownlint on both files).

## Files Changed

- `internal/update-version.py` — new `files_have_uncommitted_changes()` helper; `main()`'s tag-decision tail now
  defers tagging while the version files it wrote are still uncommitted, and tags correctly once they're clean
- `internal/verify-update-version-tag-timing.sh` — new regression test (pure git, temp repo, no Docker/network)
- `Makefile` — new `verify-update-version-tag-timing` target, wired into `check-all` and `.PHONY`
- `docs/UPDATE_VERSION.md` — new "Commit-before-tag ordering" section; corrected worked example; updated "What the
  tool does" bullet and "No-op behaviour" note
- `docs/DEVELOPMENT.md` — "Version Update Tool" pointer section updated to mention the commit-before-tag precondition

## Out of Scope

- Any add-on directory (`cups/`, `terraform-bridge/`, etc.) — untouched, per the task brief's explicit constraint
- `.github/workflows/auto-update.yml` / `base-image-update.yml` — already pass `--no-tag` (fixed in `260909-rll`);
  unaffected by this change, which only touches the default (no-flag) path
- Retroactively fixing already-wrong historical tags on origin (e.g. the still-outstanding `cups/v0.1.0-13`
  mis-pointing issue flagged in `260927-vbk`'s SUMMARY) — that is a one-off manual cleanup, not this tool fix
- Adding a new CLI flag to `update-version.py` or a new argument to the `update-version` Makefile target — the fix
  is fully automatic (git-state detection), no new flag needed; the only Makefile change is the new test target
