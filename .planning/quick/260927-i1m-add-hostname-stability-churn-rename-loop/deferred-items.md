# Deferred Items — quick-260927-i1m

## Pre-existing test failure (out of scope, not caused by this task)

`tests/test_mdns_scan.py::TestMainIndependence::test_main_does_not_raise_on_monitor_crash` fails in this
dev sandbox with `PermissionError: [Errno 13] Permission denied: '/data'` — it never patches
`mdns_scan.OUTPUT_FILE`, so `main()` tries to `mkdir` the real `/data/results` path, which does not
exist and is not writable by a non-root user on this machine.

**Confirmed pre-existing:** reproduced against the original `mdns_scan.py` (`HEAD~1`, i.e. before this
quick task's T1 commit) and the original `tests/test_mdns_scan.py` — same failure, same
`write_output()` -> `OUTPUT_FILE.parent.mkdir(...)` call site. Not introduced by T1/T2 of this quick
task; out of scope to fix per the executor's scope-boundary rule (only auto-fix issues directly caused
by the current task's changes).

Full suite otherwise green: 53 passed, 1 pre-existing failure, after T1+T2 changes.
