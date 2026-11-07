---
status: complete
---

# Quick 261105-ffy summary

- Commit 1 `5ac5d49`: replay limit (cutoff = uptime - 300 s, old lines neither KMSG nor KERR), rotate check every 100
  lines in `log()`.
- Commit 2 `745914b`: `syncing` state, version 0.7.2-0, CHANGELOG, DOCS.
- Part 3 (admin-ui ETag / asset version query) deferred: the change sits in the shared skeleton
  (`admin-ui/app/web/skeleton/static.py`, `resolve()` signature) that is copied to every consumer add-on and needs
  a lib release (`make release-admin-ui-lib`) plus consumer version bumps. Too large for a small follow-up commit.
- Design note: while syncing only the `stale` verdict is held back; real problems still raise `problem`.
- Not verified: behaviour on the real host (`/dev/kmsg` replay timing, real SSH session). `make lint` fails only in
  the unrelated `terraform-bridge` hook (image 84.9 MB > 60 MiB cap), also without these changes.
