# 17-02 Summary — iac-runner Phase 17 run contracts + ID/dir primitives

## Final error_code constant list

20 constants shipped in `iac-runner/internal/contract/types.go`. The handlers in 17-06 reference these by name —
do not introduce string literals.

### git_* (8 codes — GIT-04)

| Constant | Wire value |
|----------|------------|
| `ErrCodeGitSSHHandshake` | `git_ssh_handshake` |
| `ErrCodeGitDNSFailure` | `git_dns_failure` |
| `ErrCodeGitRefNotFound` | `git_ref_not_found` |
| `ErrCodeGitUnauthorized` | `git_unauthorized` |
| `ErrCodeGitNonFastForward` | `git_non_fast_forward` |
| `ErrCodeGitCloneFailed` | `git_clone_failed` |
| `ErrCodeGitCloneMissing` | `git_clone_missing` |
| `ErrCodeGitRefPullIncompatible` | `git_ref_pull_incompatible` |

### run_* (6 codes)

| Constant | Wire value |
|----------|------------|
| `ErrCodeRunTofuNotFound` | `run_tofu_not_found` |
| `ErrCodeRunInvalidDir` | `run_invalid_dir` |
| `ErrCodeRunUnknownRepo` | `run_unknown_repo` |
| `ErrCodeRunUnknownID` | `run_unknown_id` |
| `ErrCodeRunNotFound` | `run_not_found` |
| `ErrCodeRunCapacityExhausted` | `run_capacity_exhausted` |

### apply_* + plan_*

| Constant | Wire value |
|----------|------------|
| `ErrCodeApplyAlreadyRunning` | `apply_already_running` |
| `ErrCodeApplyTimeout` | `apply_timeout` |
| `ErrCodeApplyFailed` | `apply_failed` |
| `ErrCodePlanTimeout` | `plan_timeout` |
| `ErrCodeApplyCapacityExhausted` | `apply_capacity_exhausted` |

### auth_*

| Constant | Wire value |
|----------|------------|
| `ErrCodeUnauthorized` | `unauthorized` (pre-existing AUTHR-02 value, NOT renamed) |

## D-06 vs D-19 capacity-code discrepancy resolution

Two locked decisions name the capacity-exhaustion code differently:

- **D-19** lists it under `run_*` as `run_capacity_exhausted`
- **D-06** is the decision that specifies the observable HTTP behavior (503 + `Retry-After: 30` + capacity code)

**Resolution shipped:** handlers MUST emit `apply_capacity_exhausted` (D-06, the behavioral decision wins on the
wire). `run_capacity_exhausted` is kept declared as the reserved taxonomy slot per D-19. 17-07's DOCS.md error_code
table documents both rows so an operator can find either name.

## "envs/.." pre-Clean scan: REQUIRED

`filepath.Clean("envs/..")` reduces to `"."`, which would otherwise be accepted as the repo root per D-23 — a
silent path escape. `ValidateDir` therefore performs an **explicit pre-Clean segment scan**:

```go
for _, seg := range strings.Split(dir, "/") {
    if seg == ".." {
        return "", fmt.Errorf("%w: %s", ErrInvalidDir, InvalidDirMessage)
    }
}
```

The post-Clean checks (`cleaned == ".."`, `strings.HasPrefix(cleaned, "../")`, etc.) remain as defense-in-depth
in case Clean ever changes its behavior, but the pre-Clean scan is the one that catches `"envs/.."`.

## Files changed

| File | Change |
|------|--------|
| `iac-runner/internal/contract/types.go` | +RunKind + RunStatus enums + RunAccepted/RunDetail/RunSummary/RunListResponse + 4 pagination bound constants + 20 error_code constants; package doc comment updated (removed stale Plan 01/02/03 references) |
| `iac-runner/internal/runs/ids.go` | NEW — `RunIDLength = 16`, `NewRunID()`, `IsValidRunID()` |
| `iac-runner/internal/runs/ids_test.go` | NEW — 4 test funcs: length/charset (100 iter), uniqueness (10000 iter), accepts-generated (100 iter), rejects-malformed (12 sub-cases) |
| `iac-runner/internal/runs/dir.go` | NEW — `ErrInvalidDir` sentinel + `InvalidDirMessage` + `ValidateDir()` |
| `iac-runner/internal/runs/dir_test.go` | NEW — 2 test funcs: accepts (7 sub-cases), rejects (8 sub-cases, all `errors.Is(ErrInvalidDir)` asserted) |

## Verification

- `cd iac-runner && go build ./...` — exit 0
- `cd iac-runner && go vet ./...` — exit 0
- `cd iac-runner && go test ./internal/runs/... -count=1` — exit 0 (29 sub-tests pass)
- `cd iac-runner && go test ./... -count=1` — exit 0 (Phase 16 auth/keys/logging/statebackend/handlers suites all green; no regression)
- 20 `ErrCode*` constant declarations (plan acceptance: >= 18)
- `git diff --name-only` lists exactly the 5 files in `files_modified`

## Commit

`feat(17-02): iac-runner Phase 17 run contracts + ID/dir primitives` (5b41d49)
