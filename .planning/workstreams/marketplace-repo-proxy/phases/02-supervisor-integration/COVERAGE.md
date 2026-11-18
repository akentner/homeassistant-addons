# API Coverage — Home Assistant Supervisor API (store, manager role)

> Full coverage by default. Opt-outs are explicit, reasoned decisions.

Phase 2 integrates one external service: the local Home Assistant Supervisor REST API, reached over TCP at
`http://supervisor` with the add-on's `SUPERVISOR_TOKEN`, from the `sync` process only. `hassio_role: manager` opens
far more than the store; the locked decision D-02 limits the add-on to four `(method, path)` pairs, enforced by the
allow-list in `marketplace-repo-proxy/app/supervisor.py` before any network I/O. GitHub (git smart HTTP) coverage is
unchanged from Phase 1 (see `../01-git-serving-core/COVERAGE.md`).

| capability | decision | reason |
|---|---|---|
| `GET /store/repositories` (list slugs and sources) | INTEGRATE | |
| `POST /store/repositories` (add the `local` store URL) | INTEGRATE | |
| `DELETE /store/repositories/{slug}` (own slugs only) | INTEGRATE | |
| `POST /store/reload` (after an upstream change) | INTEGRATE | |
| `GET /store/repositories/{slug}` (one repository) | OPT-OUT | not needed: the list call already carries slug and source (D-02 allow-list) |
| `POST /store/repositories/{slug}/repair` | OPT-OUT | explicitly out of scope: repair is an operator action in the Supervisor UI, outside the D-02 allow-list |
| `GET /store` (store info incl. installed add-ons) | OPT-OUT | explicitly out of scope: would pre-check refusals, but D-02 allows four calls only (RESEARCH Q-7) |
| `/store/addons/*`, `/store/apps/*` (info, install, update) | OPT-OUT | explicitly out of scope: the proxy never installs or updates add-ons; the E2E installs through the `ha` CLI |
| `/addons/*` control (start, stop, uninstall, options) | OPT-OUT | explicitly out of scope: never uninstall or touch add-ons (D-09); not in the allow-list |
| `GET /addons/self/info` (own hostname, slug) | OPT-OUT | not needed: hostname comes from the kernel UTS name, verified formula (RESEARCH "Hostname and store URL identity") |
| `/backups`, `/core`, `/homeassistant`, `/host`, `/os`, `/supervisor` | OPT-OUT | explicitly out of scope: manager-role surface the add-on must never use (D-01, D-02) |
| `/docker`, `/mounts`, `/network`, `/resolution` | OPT-OUT | explicitly out of scope: manager-role surface the add-on must never use (D-02) |
| `/v2/*` API (feature-flagged sub-app) | OPT-OUT | not needed: the four routes are served on the V1 root; `/v2` paths are refused by the allow-list |
| Per-add-on Unix socket transport (`SUPERVISOR_SOCKET`) | OPT-OUT | not needed yet: absent in Supervisor `2026.11.0`; TCP stays default; transport isolated for a follow-up (assumption Q-6) |
| Core WebSocket `STORE_RELOADED` event | OPT-OUT | not needed: the Supervisor sends it to Core itself after `POST /store/reload` |
