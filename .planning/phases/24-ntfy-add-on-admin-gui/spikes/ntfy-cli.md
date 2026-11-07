# Spike: ntfy CLI / auth.db behaviour (ntfy-cli)

**Date:** 2026-11-01 · **Image:** `binwiederhier/ntfy:latest` = **ntfy 2.36.0** (entrypoint `ntfy`, upstream also supports
PostgreSQL via `database-url`; SQLite `auth-file` is the path assumed here) · **Host sqlite3:** 3.54.0
**Status legend:** VERIFIED = observed in this spike; ASSUMPTION = not tested.

Setup (throwaway, removed afterwards): `docker run -d --name ntfy-spike-cli --user 1000:1000 -p 18081:80
-v /tmp/akentner/ntfy-spike-cli/data:/data -e NTFY_AUTH_FILE=/data/user.db -e NTFY_AUTH_DEFAULT_ACCESS=deny-all
-e NTFY_CACHE_FILE=/data/cache.db binwiederhier/ntfy serve`. CLI calls ran as `docker exec -e NTFY_AUTH_FILE=/data/user.db
-e NTFY_AUTH_DEFAULT_ACCESS=deny-all ntfy-spike-cli ntfy <args>` (same container, same `/data`, as in the add-on).
All passwords/tokens below were throwaway values.

## Verdict

CLI against the live `user.db` **works and the server sees changes immediately** (no restart). No locking problems
with parallel CLI writes. There is **no JSON output**: text must be parsed, or `user.db` read read-only via sqlite.
Recommended split: **reads via short-lived read-only sqlite, writes via CLI**. Several quirks matter for the GUI (see
"Gotchas").

## (1) CLI against a running server — VERIFIED

- Server running, `ntfy user add/access/token/...` all succeeded against `/data/user.db`.
- Changes effective on the next request, no restart/signal:
  - `access alice topicA rw` then `curl -u alice:… -d hello /topicA` → 200 (before the grant: 403/401 path, ACL deny-all).
  - `access alice topicA deny` → 403 on next request; `user change-pass alice` → old password 401, new 200.
  - `token add alice` → token usable as `Authorization: Bearer` → 200; `token remove` → next request 401.
  - `access everyone pub ro` → anonymous read 200; `access everyone 'up*' wo` → anonymous publish 200, read 403.
  - Wildcard `access bob 'topic*' ro` → bob reads `/topicZ` 200 (after fresh grant).
- Running as uid 1000 works; CLI needs only `NTFY_AUTH_FILE` (or `-H`); `NTFY_AUTH_DEFAULT_ACCESS` only affects the
  "(server config)" lines in listings. Without auth-file: `option database-url or auth-file not set; auth is
  unconfigured for this server`, exit 1.
- CLI call cost: ~0.1 s per `docker exec` incl. process start; bcrypt (cost 10) for `user add`.

## (2) SQLite concurrency — VERIFIED

- **Not WAL.** `PRAGMA journal_mode` on `user.db` → `delete` (rollback journal). No `-wal`/`-shm` files in `/data`.
  `PRAGMA busy_timeout` of a fresh connection = 0 (per-connection, says nothing about ntfy's own value).
- Test A: 6 parallel workers × 25 × (`user add` + `access … rw` + `token add`) = 450 CLI writes while a publisher
  loop hit the server (200 publishes; 59×200, 141×429 = ntfy publish rate limit, unrelated to DB). **0 failures**, no
  "locked/busy" in server log.
- Test B: 20 parallel workers × 75 CLI writes (1500) without publisher: **0 failures**. Final DB: 153+ users.
- Test C: 3 more writers while a loop ran 300× `sqlite3 "file:…?mode=ro"` selects: 0 errors on either side.
- Test D (important): a read-only connection **holding an open read transaction** (`BEGIN; SELECT …`, no commit)
  made a CLI write fail after **~5.1 s** with `database is locked`, exit 1. So ntfy uses a ~5 s busy timeout and
  rollback-journal mode: **readers must open, query and close quickly; never keep a connection/transaction open.**
- Consequence (assumption, not stress-tested beyond the above): short serialized CLI calls are safe; the GUI backend
  should still serialize its own writes with a lock and treat `database is locked` as retryable.

## (3) CLI syntax / exit codes / output — VERIFIED

Exit code is **0 on success, 1 on every error** (no distinct codes); the reason is only in the message (stdout).
No `--json`/machine-readable flag exists for `user list`, `access`, `token list`.

| Action | Command | Success output (exit 0) | Error cases (exit 1) |
|---|---|---|---|
| list users + ACL | `ntfy user list` (alias `ntfy access`) | see format below | — |
| add user | `NTFY_PASSWORD=… ntfy user add [--role=admin\|user] NAME` | `user alice added with role user` | `user alice already exists`; no NTFY_PASSWORD and no TTY: `password: inappropriate ioctl for device`; bad name (space, `/`): `invalid argument`; bad role: `role must be either 'user' or 'admin'` |
| delete user | `ntfy user del NAME` (aliases `remove`, `rm`) | `user bob removed` | `user bob does not exist` |
| change password | `NTFY_PASSWORD=… ntfy user change-pass NAME` | `changed password for user alice` | no env + no TTY: ioctl error |
| change role | `ntfy user change-role NAME admin\|user` | `changed role for user bob to admin` | `user nosuch does not exist`; bad role: usage message |
| change tier | `ntfy user change-tier NAME TIER` | — | `tier not found` (no tiers exist by default) |
| show access | `ntfy access [USER]` | listing for USER | `user nosuch does not exist` |
| set access | `ntfy access USER TOPIC PERM` | `granted read-write access to topic topicA` + listing of that user | bad perm: `permission must be one of: read-write, read-only, write-only, or deny (or the aliases: read, ro, write, wo, none)`; unknown user: `user nosuch does not exist`; bad topic (space): `invalid argument` |
| deny | `ntfy access USER TOPIC deny` | `revoked all access to topic topicA` — stores an explicit **deny entry** (listing: `no access to topic topicA`) | — |
| reset | `ntfy access --reset [USER [TOPIC]]` | `reset access for all users` / `reset access for user alice` / `reset access for user bob and topic topic*` | — |
| token list | `ntfy token list [USER]` | see format below; none: `no users with tokens` | `user nosuch does not exist` |
| token add | `ntfy token add [--expires=2d\|-e "tuesday, 8pm"] [--label=…\|-l …] USER` | `token tk_… created for user alice, never expires` / `…, expires Tue Nov  3 22:06:54 UTC 2026` | `user nosuch does not exist` |
| token remove | `ntfy token remove USER TOKEN` (aliases `del`, `rm`) | `token tk_… for user alice removed` | `token not found` |
| token generate | `ntfy token generate` | prints a random `tk_` + 29 chars string without storing it | — |

`everyone` and `*` as USERNAME address the anonymous user (stored as user `*`, id `u_everyone`). Wildcards: `*` in
topic, e.g. `up*`, `topic*`, bare `*` (all topics) — accepted and effective (`access alice '*' rw` accepted).

**Listing format** (`user list` / `access`; per user a header line, then `- ` lines):

```text
user admin (role: admin, tier: none)
- read-write access to all topics (admin role)
user alice (role: user, tier: none)
- read-write access to topic topicA
- no access to topic topicB
user provuser (role: user, tier: none, server config)
- read-write access to topic provtopic (server config)
user * (role: anonymous, tier: none)
- write-only access to topic up*
- read-only access to topic pub
- no access to any (other) topics (server config)
- no topic-specific permissions
```

Permission phrases: `read-write|read-only|write-only|no access to topic T`; `no topic-specific permissions` when none.
Parsing is feasible but brittle (human text, i18n-free, trailing markers `(server config)`).

**Token list format:**

```text
user alice
- tk_i9p3o5ex92ssaiheh3si827f0hm2z (ci runner), expires 03 Nov 26 22:06 UTC, accessed from 0.0.0.0 at 01 Nov 26 22:06 UTC
- tk_luozuz6se5qit0gnil4afc9anq0h4, never expires, accessed from 0.0.0.0 at 01 Nov 26 22:06 UTC
```

**Token values are printed in clear text** by `token list` and are stored in clear text in `user_token.token`.
Passwords are bcrypt (`$2a$10$…`, 60 chars) in `user.pass`; the CLI never prints them.

## (4) First admin, non-interactive, idempotent — VERIFIED

- Password **only via `NTFY_PASSWORD`**; stdin is not read (needs a TTY otherwise → `inappropriate ioctl for device`).
  Special characters work: password `p@ss w"ord$1` authenticated fine. An **empty** `NTFY_PASSWORD` is treated as unset.
  (`ntfy user hash` also needs a TTY and ignores `NTFY_PASSWORD`; irrelevant unless using declarative `auth-users`.)
- `user add` on an existing user: exit 1, `user <name> already exists`, and the **password is not changed** — so
  `NTFY_PASSWORD=… ntfy user add --role=admin admin` at every start is naturally non-overwriting (D-04).
  Cleaner idempotency check without parsing error text: read-only sqlite `select 1 from user where user='admin'`,
  or `ntfy user list | grep -q '^user admin '`.
- Role of an existing user can be changed with `change-role` (see gotcha: it wipes ACLs).

Suggested bootstrap (shell, assumption-free parts only):

```bash
if [ -z "$(sqlite3 "file:/data/user.db?mode=ro" "select 1 from user where user='${ADMIN}'")" ]; then
  NTFY_PASSWORD="$ADMIN_PASS" ntfy user add --role=admin "$ADMIN"
fi
```

## (5) Tier / provisioned flags, origin — VERIFIED

- `provisioned INT` exists on **`user`, `user_access`, `user_token`** (0 = created via CLI/API, 1 = from declarative
  `auth-users` / `auth-access` / `auth-tokens`). `tier_id` is on `user` (FK `tier`); tier table is empty by default
  (`ntfy tier add` exists; `tier: none` in all listings).
- CLI shows provisioned entries only as text suffix `(server config)` on the user header, ACL line and token line.
  Everything else (UI/CLI) cannot tell origin `gui` from `options` — **D-08 sidecar is required**; the DB has no
  free-form origin field. `user.prefs` is JSON (`{}`) but is ntfy's user preferences, not for our use.
- Declarative test (server.yml with `auth-users: ["provuser:<bcrypt>:user"]`, `auth-access: ["provuser:provtopic:rw"]`,
  `auth-tokens: ["provuser:tk_<29 chars>:prov label"]`): rows created with `provisioned=1`; auth works (200).
  - `user del / change-pass / change-role` on a provisioned user → exit 1 `cannot change or delete provisioned user`.
  - `token remove` on provisioned token → exit 1 `cannot change or delete provisioned token`.
  - `access provuser provtopic deny` and `access --reset provuser` **succeeded** on the provisioned ACL (no guard);
    it would be re-created on next restart. Not relevant for D-05 (declarative not used) but shows `(server config)`
    entries must never appear in our add-on.
  - `auth-access` may only reference provisioned users: `invalid auth-access: alice:topicA:ro, user alice is not
    provisioned` → server exits at startup.
- Confirms D-05: don't mix declarative provisioning with GUI-managed rows. If baseline were ever provisioned, GUI
  edits would be blocked with the errors above.

## (6) Read-only DB access — VERIFIED

`sqlite3 "file:/data/user.db?mode=ro"` works while the server runs (journal mode `delete`; keep reads short, see (2) D).
Schema version table: `schemaVersion(id=1, version=10, min_version=1)` — **pin/check `version` at GUI start** and
degrade to CLI-only if it changes in a future ntfy.

Relevant tables (verbatim DDL, trimmed to what we need; the DB also has `user_phone`, `user_email`,
`user_magic_link`, `usage` which we ignore):

```sql
CREATE TABLE user (
  id TEXT PRIMARY KEY,                -- 'u_everyone' for anonymous, else 'u_' + 10 random chars
  tier_id TEXT,                       -- FK tier(id)
  user TEXT NOT NULL,                 -- name; anonymous user is '*'
  pass TEXT NOT NULL,                 -- bcrypt hash ('$2a$10$…'); '' for '*'
  role TEXT CHECK (role IN ('anonymous','admin','user')) NOT NULL,
  prefs JSON NOT NULL DEFAULT '{}',
  sync_topic TEXT NOT NULL,           -- 'st_…' (ntfy app sync), not an ACL
  provisioned INT NOT NULL,           -- 1 = from server config
  stats_messages INT NOT NULL DEFAULT 0, stats_emails INT NOT NULL DEFAULT 0, stats_calls INT NOT NULL DEFAULT 0,
  stripe_customer_id TEXT, stripe_subscription_id TEXT, stripe_subscription_status TEXT,
  stripe_subscription_interval TEXT, stripe_subscription_paid_until INT, stripe_subscription_cancel_at INT,
  created INT NOT NULL,               -- unix seconds
  deleted INT,
  FOREIGN KEY (tier_id) REFERENCES tier (id)
);
CREATE UNIQUE INDEX idx_user ON user (user);

CREATE TABLE user_access (
  user_id TEXT NOT NULL,              -- FK user(id) ON DELETE CASCADE
  topic TEXT NOT NULL,                -- pattern; '*' wildcards stored as given (see assumption below)
  read INT NOT NULL, write INT NOT NULL,   -- rw=1/1, ro=1/0, wo=0/1, deny=0/0
  owner_user_id INT,                  -- FK user(id); NULL for CLI-created rows (reservations use it)
  provisioned INT NOT NULL,
  PRIMARY KEY (user_id, topic)
);

CREATE TABLE user_token (
  user_id TEXT NOT NULL,              -- FK user(id) ON DELETE CASCADE
  token TEXT NOT NULL,                -- clear text 'tk_…'
  label TEXT NOT NULL,                -- '' if none
  last_access INT NOT NULL,           -- unix seconds
  last_origin TEXT NOT NULL,          -- IP, '0.0.0.0' when unknown
  expires INT NOT NULL,               -- unix seconds, 0 = never
  provisioned INT NOT NULL,
  PRIMARY KEY (user_id, token)
);
CREATE UNIQUE INDEX idx_user_token ON user_token (token);

CREATE TABLE tier ( id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  messages_limit INT NOT NULL, messages_expiry_duration INT NOT NULL, emails_limit INT NOT NULL,
  calls_limit INT NOT NULL, reservations_limit INT NOT NULL, attachment_file_size_limit INT NOT NULL,
  attachment_total_size_limit INT NOT NULL, attachment_expiry_duration INT NOT NULL,
  attachment_bandwidth_limit INT NOT NULL, stripe_monthly_price_id TEXT, stripe_yearly_price_id TEXT );
```

Observed rows: anonymous `u_everyone|*|role anonymous|provisioned 0`; `admin` role admin; ACL rows `topicA|1|1`;
`user_token` row with `label=''`, `expires=0`, `last_origin=0.0.0.0`.

Useful read-only queries for the GUI/export:

```sql
SELECT u.user, u.role, u.provisioned, t.code AS tier FROM user u LEFT JOIN tier t ON t.id = u.tier_id ORDER BY u.user;
SELECT u.user, a.topic, a.read, a.write FROM user_access a JOIN user u ON u.id = a.user_id ORDER BY u.user, a.topic;
SELECT u.user, k.label, k.expires, k.last_access, k.last_origin, substr(k.token,1,7) AS prefix
  FROM user_token k JOIN user u ON u.id = k.user_id;   -- add k.token only on explicit reveal (D-13)
```

Pros: structured, no text parsing, can omit token values from list payloads by construction (D-13), includes
`pass` hashes for the export option (D-09). Cons: depends on ntfy internal schema (version 10 here); never write to it.

## Gotchas for design (all VERIFIED unless noted)

1. **`change-role` wipes ACLs.** `bob` had `topic*`, `wild*`, `x*` (ro); `change-role bob admin` then
   `change-role bob user` left `no topic-specific permissions`. A GUI "change role" must snapshot ACLs and re-apply
   them after `user → admin → user`, or warn. (Also explains why an earlier bob request went 403 in the run.)
2. `ntfy user list NAME` **ignores NAME** and prints all users (`ntfy access NAME` filters correctly). Use `access NAME`
   or the DB for per-user views. `access nosuch` / `token list nosuch` → `user nosuch does not exist`, exit 1.
3. `access USER TOPIC deny` stores a **deny row** (not a delete); `access --reset USER TOPIC` removes the row. The GUI
   must offer both ("deny" vs "remove rule"). Exit codes don't distinguish "no-op" cases.
4. Any error → exit 1, message on stdout; parse `already exists` / `does not exist` / `invalid argument` strings
   or pre-check state via DB.
5. Password only via env (`NTFY_PASSWORD`), so call the CLI from Python with `subprocess.run(..., env={...,
   "NTFY_PASSWORD": pw}, stdin=DEVNULL)` — never as argv (visible in `ps`). Pass every other argument as a list (no shell).
6. Open read-only sqlite connections must be short-lived; a held read transaction blocks CLI writes for 5 s, then
   `database is locked` (exit 1).
7. User/topic validation by ntfy: names with spaces or `/` → `invalid argument`. Topic regex for the GUI generator
   (`[A-Za-z0-9]{16}`) is safe.
8. Server `auth-default-access` (`deny-all` here) only changes the `(server config)` line, not stored data.

## Open questions / not tested (ASSUMPTIONS)

- Exact busy timeout value in ntfy (observed ≈5 s), and whether the server's own writes (`last_access`, stats) can
  starve a CLI write under heavy publish load. Only 200 publishes tested (rate limited).
- Whether `*` inside stored topic patterns is saved as `*` or translated to SQL `%` in `user_access.topic` (the
  `access` listing prints `*`; the stored column was not inspected for a wildcard row after the final run). Check
  before building the export/ACL matrix against the DB.
- PostgreSQL mode (`database-url`) irrelevant here; behaviour of CLI/DB access would differ (no sqlite file).
- Tiers (`ntfy tier add/list`) were not exercised; the tier is `none` for all users in this spike.
- `ntfy token list` shows `accessed from 0.0.0.0 at <creation time>` for never-used tokens; `last_access` semantics
  for unused tokens (creation time vs 0) not further verified.

## Cleanup

Container `ntfy-spike-cli` removed; data under `/tmp/akentner/ntfy-spike-cli/data` emptied (scripts `n.sh`,
`conc.sh`, `server.yml`, logs remain in that dir). Nothing committed, pushed or created in the repo besides this file.

## Follow-up (2026-11-01, ntfy 2.36.0, fresh `user.db`, all VERIFIED)

Setup: new container `ntfy-spike-cli` (port 18081, data `/tmp/akentner/ntfy-spike-cli/data2`), same env as above;
DB read via `sqlite3 "file:…/data2/user.db?mode=ro"`. Container removed afterwards.

### (a) Wildcard storage: SQL `%`, not `*`

`access everyone 'up*' wo`, `access everyone '*' ro`, `access alice 'a*b*' rw` →

```text
sqlite3 -header … "select u.user,a.topic,hex(a.topic),a.read,a.write from user_access a join user u on u.id=a.user_id"
user|topic|hex|read|write
*|up%|757025|0|1       <- 'up*' stored as 'up%' (hex 75 70 25), wo = read 0 / write 1
*|%|25|1|0             <- '*' stored as '%'
alice|a%b%|61256225|1|1
```

The CLI listing translates back (`- write-only access to topic up*`). A raw-DB reader (export, ACL matrix) must map
`%` → `*` itself. Topic names cannot contain `%` (invalid), so the mapping is lossless.

### (b) `user_token.last_access`

- Never-used token: `last_access` = **creation time** (not 0): created at epoch `1793571150`,
  row `|1793571150|0.0.0.0|0` (label empty, origin `0.0.0.0`, expires 0). `token list` prints that creation time as
  "accessed from 0.0.0.0 at <creation>" — it does **not** mean the token was used.
- After first use (`Authorization: Bearer` → HTTP 200): updated **lazily/batched**, not immediately. Unchanged 2 s
  and 28 s after the first use; after a second use at `…187` the DB showed `…187` within ≤25 s (first poll at +25 s
  still old, next poll at +50 s new). `last_origin` stays `0.0.0.0` for requests from the docker host/bridge in this
  test (real client IP expected behind a proxy; not tested). So "last used" in the GUI is approximate (tens of
  seconds delay) and "never used" cannot be told apart from "used once" by `last_access == created` alone.

### (c) Tiers

- `ntfy tier list` on a fresh DB: empty output, exit 0. `ntfy tier add --name=Pro protier` (CODE positional; flags:
  `--name --message-limit --message-expiry-duration --email-limit --call-limit --reservation-limit
  --attachment-file-size-limit --attachment-total-size-limit --attachment-expiry-duration
  --attachment-bandwidth-limit`, plus Stripe flags) → prints tier block (`tier protier (id: ti_7c93Y)`, Name, limits).
- `ntfy user change-tier alice protier` → `changed tier for user alice to protier`; listing header becomes
  `user alice (role: user, tier: Pro)` (shows tier **name**, not code); DB: `user.tier_id = ti_7c93Y`, join
  `tier.code = protier`.
- Removing a tier from a user: `change-tier alice none` and `--remove` → `tier not found`, exit 1 (CLI help lists no
  clear option; tier stays `Pro`). `tier remove protier` while assigned → `FOREIGN KEY constraint failed`, exit 1.
  So a tier cannot be unassigned via CLI once set (only via `tier remove` after no user references it — which the
  CLI offers no way to achieve; assumption: needs SQL or deleting the user). Tiers are out of scope for Phase 24;
  recommendation: never call `change-tier`, show `tier` read-only.

### (d) `access --reset USER TOPIC` needs the literal CLI pattern

- `access --reset everyone 'up*'` → `reset access for user * and topic up*`, row `up%` removed (remaining: `*`/`%`).
- `access --reset alice 'a%b%'` (stored form) → `invalid argument`, exit 1, nothing removed.
- `access --reset alice 'a*b*'` → removed.
- `access --reset everyone nomatch` → still `reset access … topic nomatch`, exit 0 (**no-op reports success**; the
  DB row count stayed 2). Always use the `*` form on the CLI; convert `%` → `*` when reading from the DB.

### (e) `change-role` and ACLs (clean user `carol`, one CLI call per step)

```text
BEFORE   (access c1 rw; access 'c*' ro; access cd deny)
user carol (role: user, tier: none)
- read-write access to topic c1
- read-only access to topic c*
- no access to topic cd
$ ntfy user change-role carol admin      -> changed role for user carol to admin   (exit 0)
AFTER user->admin
user carol (role: admin, tier: none)
- read-write access to all topics (admin role)          (user_access rows for carol: 0)
$ ntfy user change-role carol user       -> changed role for user carol to user    (exit 0)
AFTER admin->user
user carol (role: user, tier: none)
- no topic-specific permissions
```

Gotcha 1 is **confirmed** and precise: the wipe happens on `user → admin` (rows deleted, count 0); `admin → user`
restores nothing. Same-role `change-role carol user` (after re-adding `c1 rw`) kept the ACL (`read-write … c1`).
Order for the GUI: snapshot ACLs (via DB, `%`→`*`) before any role change to/from admin and re-apply after demotion.
