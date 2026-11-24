This is a security release. It upgrades the SMTP server library used for e-mail publishing, which fixes a memory
exhaustion attack, and closes two holes in topic reservations, where a user could reserve topics covered by an admin's
wildcard access entry, or reserve topics at all on a tier without reservations. It also stops clients behind proxies
like HAProxy from spoofing their IP address to get around rate limits. Upgrading is recommended if you enable e-mail
publishing, reservations, or run ntfy behind a proxy.

**Security:**

- E-mail publishing: upgrade the SMTP server library ([go-smtp](https://github.com/emersion/go-smtp)) from v0.17.0 to
  v0.26.0, which fixes unbounded memory allocation when a client sends a command between two `BDAT` chunks
  ([GO-2026-7029](https://pkg.go.dev/vuln/GO-2026-7029)); incoming mail now has to use CRLF line endings, as required by
  the SMTP standard
- Reservations: wildcard access entries with an underscore (e.g. `mytopic_*`) now block reservations of topics they
  cover, so users can no longer reserve a topic inside such a namespace and become its owner (thanks to @DogukanK for
  reporting)
- Reservations: users on a tier with a reservation limit of 0 can no longer reserve topics (the limit was treated as
  unlimited) (thanks to @DogukanK for reporting)
- Rate limiting: read all `X-Forwarded-For` (or configured proxy header) lines, not just the first, so clients behind
  proxies like HAProxy can no longer spoof their IP address to bypass the per-IP rate and login limits (thanks to
  @immanuel-lam for reporting)

**Bug fixes + maintenance:**

- Web app: the config hash is now the same on all nodes of a cluster, so the web app no longer asks for a refresh when a
  version check lands on another node, and it no longer covers the database and S3 URLs (which can contain credentials)
- Firebase: log the HTTP status, `Retry-After` header and response body of failed sends, to help diagnose quota errors
  ([#2222](https://github.com/binwiederhier/ntfy/pull/2222))
- E-mail publishing: line breaks in messages published by e-mail no longer contain a carriage return (`\r`) from the
  mail's CRLF line endings
- Update Go and web app dependencies

This is a security release. It hardens message templating against a set of denial-of-service attacks, where a crafted
template could crash the server, exhaust its memory or outrun the execution deadline in a single request. It also stops
slow S3 attachment uploads and unresponsive web push endpoints from tying up memory, connections and goroutines, and
applies the web push subscription limit per IP prefix. **Upgrading is strongly recommended**.

**Security:**

- Message templating: values are now checked before they are printed or JSON-encoded, so a template can no longer crash
  the server by printing a value that references itself, or build a huge string by printing a list of many references to
  one value
- Message templating: `printf` only accepts plain directives (no explicit argument indexes or `%p`) and no lists or
  dicts as arguments, and the `html`, `js` and `urlquery` functions are no longer allowed
- Message templating: the execution deadline is now also enforced inside a single template action, so a long pipeline or
  deeply nested function calls can no longer outrun it
- Message templating: the `regexMatch`, `regexFind`, `regexFindAll`, `regexReplaceAll`, `regexReplaceAllLiteral` and
  `regexSplit` functions (and their `must` variants) now reject patterns longer than 1024 bytes or that compile to more
  than 5000 instructions, so a template can no longer make the server compile and run a huge regular expression
- Message templating: limit the result size of the `cat`, `toPrettyJSON`, `concat` and `keys` functions, and the list
  size of `uniq`, `without` and `has`, so a small template can no longer build a huge string or list in a single call
- Message templating: apply the iteration limit of `until`, `untilStep` and `seq` to decreasing sequences too, so a
  negative step can no longer build an unbounded list
- Attachments: buffer S3 uploads of unknown size in small chunks as data arrives, instead of allocating a full 5 MB part
  up front (and a second one for multipart uploads), so that slow or stalled uploads no longer pin 5-10 MB of memory
  each
- Web push: use a timeout for deliveries and always close the push service response, so slow or unresponsive push
  endpoints can no longer leak connections and goroutines; a timeout or network error no longer removes the subscription
- Web push: count the subscription limit per IP prefix (the same IPv6 /64 or configured prefix as all other limits)
  instead of per full IP address, so rotating addresses within one prefix no longer bypasses it

**Bug fixes + maintenance:**

- Stripe billing: when an abandoned checkout expires (`incomplete_expired`) after the user paid for another
  subscription, the webhook no longer replaces the paying subscription with the expired one
  ([#2199](https://github.com/binwiederhier/ntfy/pull/2199))
- Message templating: errors in an inline message template (`X-Message` with `X-Template: yes`) now name the message
  parameter instead of the priority parameter

This release shares every visitor's rate limits across the nodes of a cluster: a client spread over several nodes is now
limited once instead of once per node, and a node that restarts or crashes takes the limits over from its peers instead
of forgetting them. It also fixes a denial-of-service bug in message templating, where a crafted template could build an
oversized string and crash the server, and builds ntfy with Go 1.27.4 (security fixes).

**Features:**

- Cluster: the nodes share every visitor's rate limits (requests, failed logins, signups and password resets, topic
  creation, e-mails, attachment bandwidth, Firebase pauses) over the mesh every second, so a client spread over several
  nodes gets its limits once, not once per node; a node that restarts or crashes takes the limits over from its peers
  before it serves ([#2182](https://github.com/binwiederhier/ntfy/pull/2182))

**Bug fixes + maintenance:**

- Message templating: the `replace`, `regexReplaceAll` and `join` functions now cap the size of the string they build,
  so a template can no longer amplify small inputs into a multi-gigabyte string and crash the server with an
  out-of-memory error (thanks to Robert Flosbach of Neodyme for the responsible disclosure)
- WebSocket subscribers that a node closes while draining are no longer counted and logged as internal server errors
  (HTTP 500, ntfy error 50001); on ntfy.sh, each node's drain counted ~18k of them and tripped the 5xx alert, although
  clients never saw an error ([#2171](https://github.com/binwiederhier/ntfy/pull/2171))

**Security:**

- Build with Go 1.27.4, which includes security fixes to cgo, the go command, the compiler, the linker and `net/http`

## Changelog

- 05109571fd0931affb6f92b17bbfd62c4d2ea68a Merge pull request #2169 from binwiederhier/release-2380

This release fixes a database slowdown in v2.37.0 when using `visitor-subscriber-rate-limiting` with a user database:
the subscriber activity of UnifiedPush topics was written far too often.

**Bug fixes + maintenance:**

- With `visitor-subscriber-rate-limiting` and a user database, write a UnifiedPush topic's subscriber activity every one
  to two hours instead of every 5 minutes, spread over time, and not at all when a poll or reconnect only repeats the
  same subscriber; on ntfy.sh, v2.37.0's writes of ~45k topics every 5 minutes, all due in the same minute, slowed down
  the database ([#2151](https://github.com/binwiederhier/ntfy/pull/2151))

This release makes UnifiedPush work across several servers: the subscriber who pays for a topic's pushes is shared
through the database, and app servers are told with `410 Gone` when a subscription has been abandoned for 4 days. It
also adds `Retry-After` and the draft `RateLimit` headers to rate limit responses, and frees the memory of one-off
visitors sooner.

**Features:**

- With `visitor-subscriber-rate-limiting`, the subscriber of a UnifiedPush topic (who pays for its pushes) is kept in
  the user database and shared by all servers, so a push to any server is billed to the subscriber instead of answered
  with 507 ([#2136](https://github.com/binwiederhier/ntfy/pull/2136); see
  [subscriber-based rate limiting](https://docs.ntfy.sh/config/#subscriber-based-rate-limiting))
- Send a `Retry-After` header with HTTP 429 responses that are caused by a rate limit with a known wait, e.g. the
  request, e-mail or daily message limits ([#2142](https://github.com/binwiederhier/ntfy/pull/2142); see
  [rate limiting](https://docs.ntfy.sh/config/#rate-limiting))
- Send the IETF draft `RateLimit-Policy` and `RateLimit` headers with publish responses (and with every 429 caused by a
  limit with a quota), for the request and daily message limits
  ([#2143](https://github.com/binwiederhier/ntfy/pull/2143); see
  [rate limiting](https://docs.ntfy.sh/config/#rate-limiting))
- New metric `ntfy_topics_unifiedpush_total`: the UnifiedPush topics whose subscriber state a server keeps in memory
  ([#2136](https://github.com/binwiederhier/ntfy/pull/2136))

**Behavior changes:**

- With `visitor-subscriber-rate-limiting`, a UnifiedPush push to a topic that has had no subscriber (subscribe, poll or
  open stream) for 4 days is answered with `410` (error code 41002) instead of `507`, so app servers like Mastodon
  remove the expired subscription ([#664](https://github.com/binwiederhier/ntfy/issues/664),
  [#2136](https://github.com/binwiederhier/ntfy/pull/2136)); a Matrix push to such a topic gets its pushkey rejected
  (before: after 12 hours without a subscriber on the server that got the push)
- With `visitor-subscriber-rate-limiting`, UnifiedPush messages are counted against the subscriber's account only while
  it has a tier, and against the subscriber's IP address otherwise (also after the account lost its tier or was
  deleted); a tier change applies to the next message ([#2136](https://github.com/binwiederhier/ntfy/pull/2136))
- Ban feed: weights may be fractional (down to `0.001`), auth failures (`42909`) now weigh 2 instead of 10, and a
  UnifiedPush push without a subscriber (`50701`) or to an abandoned topic (`41002`) weighs 0.05, so app servers pushing
  to many offline phones are not banned for it ([#2147](https://github.com/binwiederhier/ntfy/pull/2147))
- The rate limit state of a visitor is forgotten about a minute after it has fully recovered (all buckets refilled)
  instead of after a day without use, which frees the memory of one-off visitors such as floods of new IPs. The
  `visitors` stat and the `ntfy_visitors_total` metric therefore count the visitors of roughly the last minute, not of
  the last day ([#2126](https://github.com/binwiederhier/ntfy/pull/2126))
- Topics without subscribers are dropped from memory after 6 hours without use instead of 16; a publish to such a topic
  recreates it (and counts against `visitor-topic-creation-limit-burst`)
  ([#2136](https://github.com/binwiederhier/ntfy/pull/2136))

**Bug fixes + maintenance:**

- With PostgreSQL and several servers, daily usage a server counted in the last seconds of a visitor's 24-hour period is
  no longer added to the next period (a double count); it is dropped instead
  ([#2136](https://github.com/binwiederhier/ntfy/pull/2136))
- Cluster: a forwarded message for a topic without subscribers on the receiving node now counts as wasted
  (`ntfy_cluster_messages_wasted_total`) and no longer keeps that idle topic in memory
  ([#2140](https://github.com/binwiederhier/ntfy/pull/2140))

# Changelog

All notable changes to the **ntfy** add-on are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/). The add-on version follows upstream ntfy; a change that only touches
the add-on (GUI, options, docs) bumps the subpatch (`-N`).

## [2.38.1-1] - 2026-11-18

### Changed

- Use admin-ui lib 0.10.0: the shared skeleton gains the bearer API listener; this add-on does not use it yet, so its
  behaviour is unchanged

## [2.37.2-8] - 2026-11-07

### Fixed

- The add-on no longer creates the admin or a baseline user with a placeholder password. An empty value, an unresolved
  `!secret` reference, a password equal to the username (for example when an option points to the `*_username` secret
  instead of the `*_password` secret) or a password shorter than 8 characters is refused: the account is not created, a
  clear warning names the user and the reason (never the value), and the other entries are applied as usual
- With `baseline_overwrite_passwords: true` the same check applies: an invalid baseline password is never set on an
  existing user

## [2.37.2-1] - 2026-11-04

### Changed

- Use shared admin-ui lib 0.7.0: HA-style navigation and consistent minimum table row heights
- Fix overlapping badges in expanded user details and preserve table layout for action cells
- Use upstream ntfy 2.37.2

## [2.37.0-2] - 2026-11-03

### Changed

- The admin GUI runs on the shared `admin-ui` library; the look changes slightly, with higher text contrast and
  different colours
- Error messages are translated per error code; unknown codes show the code in brackets
- The page and static files carry a Content-Security-Policy and Referrer-Policy header (`NTFY_GUI_CSP=off` is a
  diagnostic switch only)

### Added

- German and English interface with a language switch, light and dark theme
- Keyboard-operable matrix cells, accessible names and table headers
- Optional Home Assistant theme sync and bridge as progressive enhancement
- Tests for the GUI and the add-on run in CI

### Fixed

- The role-change message names the number of dropped rules
- A test publish that ntfy rate-limits or cannot reach is reported as a failure

## [2.36.0-0] - 2026-11-01

### Added

- ntfy server add-on on the bridge network, listening on container port 8000 (`72a005f5-ntfy:8000`)
- Options pass-through for base URL, web UI, proxy trust, default access, message cache and attachments
- Ingress-only admin GUI: users, ACL rules with a topic x user matrix, tokens, effective-rights lookup, random topic
  generator, health with test publish, state export and backups
- Baseline users from the options, applied additively at each start; origin markers `gui` and `options`; optional
  `baseline_overwrite_passwords`
- State export (schema 1) as YAML and JSON, without secrets by default
- Daily and pre-action backups of `auth.db` with rotation, and guarded reset actions with typed confirmation
- Guardrails for the last admin and the options admin, and a role-change stash that restores rules on demotion
- Migration guide from the mrschloemps ntfy Server add-on (see DOCS.md)

Release links are added after the first tag exists.
