---
slug: arping-device-name
status: complete
completed: 2026-06-27
---

Added optional `device_name` field to `arping_hosts` config entries.
Multiple hosts with the same `device_name` now share one HA device (sensors grouped per device).
Bumped version to 0.2.2-0. All pre-commit hooks passed.
