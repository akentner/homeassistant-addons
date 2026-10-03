# Phase 21 Review Disposition

| ID | Severity | Title | Disposition |
|----|----------|-------|-------------|
| CR-01 | critical | Print history silently stops recording after a container recreation (job-id counter reset) | open |
| CR-02 | critical | run.sh ignores a failed `generate_config.py`, so "Refusing to start" is not honoured | open |
| CR-03 | critical | Upload worker can upload a truncated PDF (and never the sidecar title) | open |
| WR-01 | warning | Plaintext admin password written to a world-readable script and never removed | open |
| WR-02 | warning | A redirecting paperless-ngx URL turns a failed upload into a "success" | open |
| WR-03 | warning | Numeric options are unbounded and unvalidated; `url`/`token` are never checked at startup | open |
| WR-04 | warning | `$`-anchored validation regexes accept a trailing newline | open |
| WR-05 | warning | `NAME_RE` is used as the CUPS queue-name charset but rejects underscores (and the migration script feeds it such names) | open |
| WR-06 | warning | Print history misses jobs that complete out of id order (multi-printer setups) | open |
| WR-07 | warning | UUID-stability test in verify-cups-scaffold.sh cannot fail | open |
| WR-08 | warning | paperless verify script's title/sidecar assertions are satisfied by the failure path | open |
| WR-09 | warning | One failing `lpadmin` aborts registration of every later printer and the cups-pdf queue | open |
| WR-10 | warning | Root upload worker follows symlinks inside a world-writable (0777) outbox | open |
| IN-01 | info | Docs disagree with code | open |
| IN-02 | info | Duplicated registration snippet builders and doubled warnings | open |
| IN-03 | info | `usb://` URIs are accepted/documented but the add-on cannot reach USB devices | open |
| IN-04 | info | Line-length / lint | open |
| IN-05 | info | Nested option translations may not be applied | open |
| IN-06 | info | Migration helper silently downgrades printers and has a pipefail/SIGPIPE edge | open |
| IN-07 | info | Operational edge cases in run.sh / cupsd scoping | open |
