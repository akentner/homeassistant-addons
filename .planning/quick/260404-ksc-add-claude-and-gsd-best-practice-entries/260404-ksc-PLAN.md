---
phase: quick
plan: 260404-ksc
type: execute
wave: 1
depends_on: []
files_modified:
  - .gitignore
autonomous: true
requirements: []

must_haves:
  truths:
    - ".claude/ directory contents are not tracked by git (except hooks/ and commands/ subdirectories)"
    - ".planning/research/ artifacts are not tracked by git"
    - "Existing .env, .idea/, .vscode/ entries remain intact"
    - ".claude/hooks/ and .claude/commands/ are explicitly re-included via negation rules"
  artifacts:
    - path: ".gitignore"
      provides: "Updated ignore rules for Claude and GSD artifacts"
      contains: ".claude/"
  key_links:
    - from: ".gitignore"
      to: ".claude/hooks/"
      via: "negation pattern !.claude/hooks/"
      pattern: "!.claude/hooks/"
---

<objective>
Update .gitignore to ignore Claude Code local state and GSD research artifacts while preserving
tracked subdirectories that contain project-relevant configuration.

Purpose: Keep the repository clean of developer-local Claude and GSD artifacts without losing hooks and commands that
are part of the project workflow.

Output: Updated .gitignore with three new sections appended after existing entries. </objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Update .gitignore with Claude and GSD ignore rules</name>
  <files>.gitignore</files>
  <action>
    Append the following three sections to .gitignore, after the existing entries. Preserve all
    existing content exactly. Use LF line endings (no CRLF).

    Section 1 — Claude Code local state (ignore the directory, but re-include two tracked subdirs):

    ```
    # Claude Code local state
    .claude/
    !.claude/hooks/
    !.claude/commands/
    ```

    Section 2 — GSD research artifacts:

    ```
    # GSD research artifacts
    .planning/research/
    ```

    Important: Git negation patterns require the parent directory to not itself be ignored. Since
    .claude/ is ignored as a whole, the negation !.claude/hooks/ only works when git processes the
    directory contents. Verify with `git status` that .claude/hooks/ and .claude/commands/ (if
    present) show as tracked/untracked files rather than being fully hidden. If the negation does
    not take effect (git still hides hooks/ and commands/), replace the pattern with the more
    explicit form:

    ```
    .claude/*
    !.claude/hooks/
    !.claude/commands/
    ```

    This form ignores all direct children of .claude/ individually, which allows the negations to
    apply correctly.

  </action>
  <verify>
    <automated>git check-ignore -v .claude/ .planning/research/ .env .idea/ 2>&1; git status --short | head -20</automated>
  </verify>
  <done>
    - `git check-ignore -v .claude/` reports .gitignore as the source rule
    - `git check-ignore -v .planning/research/` reports .gitignore as the source rule
    - `git check-ignore -v .env` still reports .gitignore (existing rule intact)
    - `git status` no longer shows `?? .claude/` or `?? .planning/research/` as untracked
    - .claude/hooks/ contents (if any files exist) appear as untracked or tracked, not hidden
  </done>
</task>

</tasks>

<verification>
Run the automated verify command from Task 1. Confirm:
1. .claude/ is ignored
2. .planning/research/ is ignored
3. .env, .idea/, .vscode/ entries are still present in .gitignore
4. Negation rules for .claude/hooks/ and .claude/commands/ are present
</verification>

<success_criteria> `git status` no longer lists `?? .claude/` or `?? .planning/research/`. The .gitignore file contains
all original entries plus the two new sections. The negation patterns for hooks/ and commands/ are present in the file.
</success_criteria>

<output>
After completion, create `.planning/quick/260404-ksc-add-claude-and-gsd-best-practice-entries/260404-ksc-SUMMARY.md`
</output>
