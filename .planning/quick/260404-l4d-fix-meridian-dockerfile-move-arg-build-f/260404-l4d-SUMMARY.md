---
phase: quick-260404-l4d
plan: 01
status: completed
---

# Summary: Fix Meridian Dockerfile — Move ARG BUILD_FROM Before First FROM

## What was changed

**File:** `meridian/Dockerfile`

### Lines moved

| Before        | After        | Content                                                 |
| ------------- | ------------ | ------------------------------------------------------- |
| Line 17 (old) | Line 1 (new) | `ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.23` |

- `ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.23` was moved from between the `# Stage 2: Runtime` comment and
  `FROM $BUILD_FROM` (line 17) to the very top of the file (line 1), before `FROM oven/bun:1 AS build`.
- The `# Stage 2: Runtime — HA base image with Node.js` comment remained directly above `FROM $BUILD_FROM`.
- All other lines are unchanged.

## Why this fixes the build

Docker ARGs used in `FROM` instructions must be declared in the **global scope** — before any `FROM` instruction. An ARG
declared inside a build stage (after a FROM) is scoped to that stage and is empty everywhere else. Moving
`ARG BUILD_FROM` before the first `FROM` makes the value available to all subsequent `FROM $BUILD_FROM` instructions.

## Verification results

```
$ grep -n "ARG BUILD_FROM" meridian/Dockerfile
1: ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.23
```

Single match on line 1 only. Old position (line 17) is gone.

```
$ pre-commit run --files meridian/Dockerfile
trim trailing whitespace ... Passed
fix end of files ........... Passed
Lint Dockerfiles ........... Passed
(all other hooks: Skipped or Passed)
```

All pre-commit hooks pass with exit code 0.
