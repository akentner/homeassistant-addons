---
status: complete
---

# Quick Task 261025-lpy: litellm builder back to Python 3.13

## Problem

Renovate PR #53 (`639b050`) bumped the litellm builder to `python:3.15-slim-bookworm`. litellm requires Python
`<3.15`, so the build of `1.106.4-0` failed (run 40187491657) and the image was never pushed. `config.yaml` already
advertised that version, so `Verify Image Availability` (run 40196795005) failed with HTTP 404. The runtime stage is
Debian trixie with python3.13 and the builder output is copied to `dist-packages` of python3.13, so 3.13 is also the
only ABI-correct choice.

## Changes

- `e53adb5` — `litellm/Dockerfile`: builder reverted to `python:3.13-slim-bookworm` (local `docker build` verified)
- `e994606` — `.github/renovate.json`: `allowedVersions: "3.13"` for the python Docker tag in `litellm/Dockerfile`

## Verification

- Build Add-on run 40212543523: success, `amd64-litellm:1.106.4-0` published
- Verify Image Availability run 40212723137: success
- Renovate rule not exercised yet; confirm at the next Renovate run
