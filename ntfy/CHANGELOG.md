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
