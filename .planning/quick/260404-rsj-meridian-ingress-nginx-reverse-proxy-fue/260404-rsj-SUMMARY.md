---
phase: quick
plan: 260404-rsj
subsystem: meridian
tags: [nginx, ingress, reverse-proxy, sub_filter, homeassistant]
tech-stack:
  added:
    - nginx (Alpine apk package, installed in meridian container)
  patterns:
    - nginx sub_filter for dynamic path rewriting via HTTP header variable
    - nginx background daemon started before exec in run.sh
key-files:
  created:
    - meridian/nginx.conf
  modified:
    - meridian/Dockerfile
    - meridian/run.sh
    - meridian/config.yaml
decisions:
  - nginx daemon mode (no daemon off) so it forks to background before exec meridian
  - ingress_port changed to 8099; LAN port 3456 kept unchanged via ports mapping
  - sub_filter_once off to replace all occurrences per response body
---

# Quick Task 260404-rsj: Meridian Ingress nginx Reverse Proxy

**One-liner:** nginx reverse proxy on port 8099 rewrites absolute path references in Meridian HTML/JS responses using
the X-Ingress-Path header so HA Ingress panel works without 404s.

## What Was Built

Added nginx as an Ingress-facing reverse proxy inside the meridian add-on container. HA Ingress now connects to nginx on
port 8099; nginx forwards requests to meridian on 127.0.0.1:3456 and rewrites absolute path prefixes in HTML/JS response
bodies using the `$http_x_ingress_path` variable from the `X-Ingress-Path` header that HA Ingress injects.

## Tasks Completed

| Task | Name                                             | Commit  | Files                                    |
| ---- | ------------------------------------------------ | ------- | ---------------------------------------- |
| 1    | Create nginx.conf with X-Ingress-Path sub_filter | 18d140d | meridian/nginx.conf (created)            |
| 2    | Update Dockerfile, run.sh, config.yaml for nginx | 8a3c2f5 | meridian/Dockerfile, run.sh, config.yaml |

## Files Changed

- **meridian/nginx.conf** (new): nginx config listening on 8099, proxy_pass to 127.0.0.1:3456, 10 sub_filter rules
  covering href, src, fetch, action, /api/, /telemetry/, /health paths.
- **meridian/Dockerfile**: added `nginx` to apk install line; added `COPY nginx.conf /etc/nginx/nginx.conf`.
- **meridian/run.sh**: added `nginx` call (background daemon) + log line before `exec meridian`.
- **meridian/config.yaml**: changed `ingress_port` from `3456` to `8099`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed invalid garbage line from Dockerfile**

- **Found during:** Task 2 (make lint run)
- **Issue:** Line 3 of meridian/Dockerfile contained a random alphanumeric string
  (`LbHztEGZ98JkUJYq5nNaVmFNQLGVdlx8laTuzqCvHzcMcXLV#9R_...`) that was already in the working tree as an unstaged
  modification (visible in the initial `git status M meridian/Dockerfile`). hadolint reported exit code 1 on this line.
- **Fix:** Removed the garbage line, restoring a clean `FROM $BUILD_FROM` followed by a blank line.
- **Files modified:** meridian/Dockerfile
- **Commit:** 8a3c2f5 (included in Task 2 commit)

## Decisions Made

1. **nginx daemon mode** — nginx is started without `daemon off` so it forks to the background. This allows
   `exec meridian` to remain the process that HA's S6 restart policy monitors.
2. **ingress_port: 8099** — HA Ingress connects to nginx; direct LAN access on 3456 is preserved via the unchanged
   `ports: 3456/tcp: 3456` mapping.
3. **sub_filter_once off** — All occurrences per response are replaced, not just the first, since Meridian's HTML/JS may
   reference the same paths multiple times.

## Self-Check

- [x] meridian/nginx.conf exists
- [x] meridian/Dockerfile contains nginx in apk line and COPY nginx.conf
- [x] meridian/run.sh starts nginx before exec meridian
- [x] meridian/config.yaml has ingress_port: 8099
- [x] Commit 18d140d exists (nginx.conf)
- [x] Commit 8a3c2f5 exists (Dockerfile, run.sh, config.yaml)
- [x] make lint passes (all hooks green)

## Self-Check: PASSED
