# Phase 13 — Deferred Items

Out-of-scope discoveries logged during Phase 13 execution. Per the executor scope boundary, these are **not** fixed as
part of Phase 13 — they are pre-existing conditions in files unrelated to this phase's changes.

## 1. `info_hub/README.md:7` — MD040 fenced-code-language

- **Found during:** Plan 03, Task 2 (DOCS.md author run), when the `markdownlint-cli2` pre-commit hook first ran against
  a non-`.planning/` Markdown file in this phase.
- **Finding:** `markdownlint-cli2` reports
  `info_hub/README.md:7 error MD040/fenced-code-language Fenced code blocks should have a language specified`.
- **Why it surfaced now:** The hook lints `**/*.md` globally, but `.planning/**` is excluded. Plans 01 and 02 changed
  only Go sources and `.planning/` documents, so the hook never ran during Phase 13 until `DOCS.md` was added.
- **Scope:** Unrelated to Phase 13. `info_hub/` is a different add-on; the file is untouched by this phase.
- **Impact:** The `markdownlint-cli2` pre-commit hook fails for **any** commit touching a linted Markdown file until
  this is fixed. `terraform-provider-homeassistant/DOCS.md` itself is markdownlint-clean (verified: the summary reports
  exactly 1 issue across 38 files, and it is this one).
- **Suggested fix:** Add a language tag to the fenced block at `info_hub/README.md:7` (e.g. ` ```text `). One-line
  change; belongs in an `info_hub` maintenance commit, not a Phase 13 commit.

## 2. Docker-dependent Bridge verification hooks cannot run in this environment

- **Found during:** Plan 03, Task 1 (contract extension commit).
- **Finding:** `verify-bridge-scaffold` (exit 2, `docker not found in PATH`) and `verify-bridge-no-token-leak`
  (exit 127) both fail because `docker` is not installed on this host.
- **Scope:** Environment limitation, not a code defect. Both scripts are container-runtime integration checks — they
  build and run the Bridge image. Neither compiles or lints Go source (`grep -c 'go build|go test'` returns 0 for both).
- **Compensating verification performed:** `go build ./...`, `go vet ./...`, and `go test -count=1 -race ./...` all exit
  0 on both the Bridge and Provider trees; the token-leak negative grep
  (`grep -RE 'slog\..*(nonce|bearer|Bearer)' internal/ | grep -v _test.go`) returns 0 matches.
- **Follow-up:** Phase 14 runs the real-HA end-to-end verification on a host with Docker available; these two hooks
  should be re-run there to close the gap.
