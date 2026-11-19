# Marketplace Repo Proxy

Read-only git proxy that makes private GitHub add-on repositories installable from the Home Assistant add-on store. The
goal and the open design questions are in [GOAL.md](GOAL.md).

## Overview

The add-on keeps a local mirror of each configured private GitHub repository and serves it to the add-on store as a
plain, read-only git repository:

- A sync service fetches every configured repository with one read-only GitHub token, at start, on an interval and on
  request.
- lighttpd with `git http-backend` serves the mirrors over smart HTTP (clone and fetch only, no push).
- Every user of a repository gets its own store URL with a random access hash. Revoking a user disables exactly that URL
  at the next request.
- A management page in Home Assistant shows the repositories with their sync state, manages the users and shows when
  each user last fetched.

The add-on itself never installs anything. A Home Assistant instance adds a store URL as a repository, and its
Supervisor clones from the add-on like from any public repository.

Users are managed on the [management page](#management-page) or with the `mrp` command inside the container (see
[Managing users](#managing-users)). Not in this version: self-registration in the local add-on store, the provisioning
API and documented public access through a reverse proxy. They follow in later versions.

## Repository exception

This add-on is our own code, not a wrapper around an upstream project. It therefore has no `.upstream.yaml` and no
auto-update. Its image is built and published by CI like the others (`image:` key). The other repo rules still apply: HA
base image only, 3-file version sync via `make update-version`, and a local `docker build` before every commit.

## Options

| Option                      | Type                          | Default  | Description                                                                                                                                             |
| --------------------------- | ----------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `github_token`              | password                      | empty    | Fine-grained personal access token with `Contents: read-only` on the repositories below. Never logged. Empty token: every repository `auth_failed`.     |
| `sync_interval`             | integer, minimum 5            | `15`     | Minutes between two sync cycles.                                                                                                                        |
| `public_url`                | URL, optional                 | not set  | Base URL behind a reverse proxy, e.g. `https://addons.example.com`. Not set: internal access only. Adds a second (public) store URL per user.           |
| `repositories`              | list                          | empty    | Private GitHub repositories to serve.                                                                                                                   |
| `repositories[].repository` | `owner/repo`                  | required | GitHub owner (user or organization) and repository name. Case-insensitive; a `.git` suffix is not allowed.                                              |
| `repositories[].branch`     | branch name, optional         | not set  | Branch to serve. Not set: the repository's default branch. Only this branch is offered as a ref; see [Security notes](#security-notes) for old commits. |
| `register_local`            | boolean                       | `true`   | Register the internal store URL in this Home Assistant's add-on store. **No effect yet**; takes effect in a later version.                              |
| `api_enabled`               | boolean                       | `false`  | Enable the provisioning API. **No effect yet**; takes effect in a later version.                                                                        |
| `log_level`                 | `debug\|info\|warning\|error` | `info`   | Verbosity of the add-on log. Tokens and access hashes are never logged, at any level.                                                                   |

Users and their access hashes never appear in the options. They live in `/data/access.json` (see
[Managing users](#managing-users) and [Contracts](#contracts)). An invalid or duplicate entry in `repositories` is
skipped with a warning in the log; the other entries keep working. A `public_url` that is not a valid `http(s)` URL, or
that has credentials (`user:password@`), a query or a fragment, is ignored the same way, so no credentials reach the
log.

Example:

```yaml
github_token: "<fine-grained token>"
sync_interval: 15
repositories:
  - repository: example-org/private-addons
  - repository: example-org/beta-addons
    branch: stable
register_local: true
api_enabled: false
log_level: info
```

## Store URLs

A store URL has the form:

```text
http://{hostname}:8080/repo/{owner}/{repo}/{hash}
```

- `{hostname}` is the add-on's container hostname. For an install from this repository it is
  `{repo-hash}-marketplace-repo-proxy`, where `{repo-hash}` is the prefix the Supervisor gives this repository's
  add-ons.
- `{owner}/{repo}` is the repository as configured in `repositories`.
- `{hash}` is the user's access hash: 32 lowercase hex characters. Unknown owners, repositories and hashes all answer
  with the same 404.

At every start the add-on log lists each configured repository and, per user, the internal store URL and, when
`public_url` is set, the public one (`{public_url}/repo/{owner}/{repo}/{hash}`). Both are masked to the first 4
characters of the hash, for example `.../repo/example-org/private-addons/3f9c…`. The full URL is shown only in the
Access view of the [management page](#management-page) and printed by `mrp users add` and `mrp users url` (see
[Managing users](#managing-users)).

To use a URL, add it in Home Assistant under **Settings → Add-ons → Add-on store → ⋮ → Repositories**.

- Query parameters on the store URL (for example `?ref=main&tab=readme`) are accepted and ignored.
- A `#branch` suffix works for the served branch: the Supervisor removes it and clones that branch. Only the configured
  branch (or the default branch) is served, so any other branch name fails.
- The URL is the repository's identity in the consuming Supervisor. A different URL (for example a new hash after a
  rotation) is a different repository: it has to be added again, and its add-ons have to be reinstalled.
- Port `8080` is not published by default. The URL works on the internal `hassio` network, i.e. for the Supervisor and
  for other add-ons of the same Home Assistant. There is no TLS inside the add-on. Do not publish the port to reach it
  from outside; public access through a reverse proxy is documented in a later version.

## Management page

The management page runs inside Home Assistant through ingress. Open it from the sidebar panel **Repo Proxy** (shown to
administrators only) or with **Open Web UI** on the add-on's page. The page is in English or German (switch in the top
bar). The top bar shows the full add-on version including the subpatch (for example `0.1.0-2`); the value is written
into the image at build time, and a local build without it shows no version. The page has three views.

### Repositories

- One row per configured repository: `owner/repo` with the served branch and where it comes from (configured or upstream
  default), the status (codes in [Sync and status](#sync-and-status)) with its message, the last sync (relative), the
  HEAD short SHA and the add-ons found. Without a `status.json` yet, the view says so instead of showing an error.
- The sync line shows whether a sync is idle, requested or running, and when the next one is due. The view refreshes
  every 15 seconds, and every 2 seconds while a sync is requested or running.
- **Sync now** requests one sync cycle over all repositories, the same as `mrp sync`. There is one button for all
  repositories because a cycle always covers all of them.
- A **Registration** column shows whether a repository is registered in this Home Assistant's add-on store: registered,
  not registered (missing), leftover (the local store still lists an earlier store URL of the repository) or error. The
  column appears only when registration data exists; self-registration follows in a later version.

### Access

- One card per configured repository with its users: label, source badge, creation time and last fetch. The source badge
  shows who created the user: `gui` (this page), `cli` (`mrp`), `api` (the provisioning API of a later version) or
  `system` (the add-on itself).
- **Add user** creates a user with a new random hash and source `gui` (label rules as for `mrp users add`). The new
  store URLs (internal, and public when `public_url` is set) are shown once, right away.
- **Show URLs** loads a user's store URLs on demand and shows them in copy fields; **Hide URLs** removes them from the
  page. Besides `mrp users add` and `mrp users url`, this is the only place that shows full store URLs. The user list
  itself never contains a hash or a URL.
- **Revoke** and **Rotate** ask for confirmation: type the user label exactly. Revoke removes the user; its URL answers
  404 from the next request on. Rotate gives the user a new random hash in one step: the old URL answers 404 at once and
  the new URL works at once. The user keeps its source, `created` restarts at the rotation time, and unknown fields of
  the entry are dropped.
- A rotation has consequences for the consumers: the consuming Supervisor sees the new URL as a new repository. Back up
  the data of the add-ons installed from the old URL, rotate, remove the old repository in Home Assistant, add the new
  URL and reinstall the add-ons.
- Users with source `system` are read-only: the page offers no revoke and no rotate for them.
- Entries of repositories that are no longer configured are listed under **Inactive entries** with Revoke only; they
  grant no access.
- **Last fetch** is the time of the user's last clone or fetch with the current URL (definition in
  [/data/last-fetch.json](#datalast-fetchjson)), shown relative, or "never". After a rotation or a re-creation it shows
  "never" until the new URL is used.
- When `/data/access.json` cannot be read, every action is refused with an error and nothing is changed.

### Info

Static notes without actions: how to add a store URL in Home Assistant (one host name per Home Assistant instance,
because the host is part of the repository's identity), what a reverse proxy in front of the add-on must do (TLS at the
proxy, no caching of `/repo/*`, no logging of request paths) and the rotation procedure.

### Access to the page

- The page is reachable only through Home Assistant ingress. Every other request gets 403, whatever its method or path.
- Port 8099 (the page's port inside the container) is never published.
- The page's process holds neither the GitHub token nor the Supervisor token; it reads only non-secret options.

## Managing users

Users are managed on the [management page](#management-page) or with the `mrp` command inside the running container. On
the Home Assistant host (for example from the SSH add-on with host access), the container is called
`addon_{repo-hash}_marketplace_repo_proxy`:

```bash
docker exec addon_{repo-hash}_marketplace_repo_proxy mrp --help
```

| Command                                | Effect                                                                                                                                                |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `mrp users add {owner/repo} {user}`    | Creates the user with a new random hash and prints its store URL(s). `--hash {32 hex}` sets a given hash.                                             |
| `mrp users list [{owner/repo}]`        | Lists repository, user, source, creation time and the masked hash, tab-separated; `(inactive)` marks entries of repositories that are not configured. |
| `mrp users url {owner/repo} {user}`    | Prints the user's store URL(s) again.                                                                                                                 |
| `mrp users revoke {owner/repo} {user}` | Removes the user; the URL answers 404 from the next request on. Other users keep access.                                                              |
| `mrp sync`                             | Requests a sync of all repositories now (see [Sync and status](#sync-and-status)).                                                                    |
| `mrp reconcile`                        | Rebuilds the access links from `/data/access.json` (normally not needed).                                                                             |

Examples:

```bash
docker exec addon_{repo-hash}_marketplace_repo_proxy mrp users add example-org/private-addons alice
# internal: http://{repo-hash}-marketplace-repo-proxy:8080/repo/example-org/private-addons/{hash}
# public: https://addons.example.com/repo/example-org/private-addons/{hash}   (only when public_url is set)

docker exec addon_{repo-hash}_marketplace_repo_proxy mrp users list example-org/private-addons
docker exec addon_{repo-hash}_marketplace_repo_proxy mrp users url example-org/private-addons alice
docker exec addon_{repo-hash}_marketplace_repo_proxy mrp users revoke example-org/private-addons alice
docker exec addon_{repo-hash}_marketplace_repo_proxy mrp sync
```

- A user label is 1 to 64 characters: letters, digits, `.`, `_` and `-`, starting with a letter or digit. The label
  `local` is reserved for a system user of a later version.
- Only `mrp users add` and `mrp users url` (to the terminal) and the Access view of the management page (Add user, Show
  URLs) show the full URL. Treat it as a secret.
- Errors print `error: {code}` and exit with 1, for example `repository_unknown` (not in `repositories`), `user_exists`,
  `user_unknown`, `invalid_user`, `user_reserved`, `invalid_hash`, `hash_conflict` (the given hash is already in use)
  and `options_invalid`. Usage errors exit with 2.
- **Rotation** gives a user a new hash. The management page rotates in one step (Rotate in the Access view); the user
  keeps its source and `created` restarts at the rotation time. With `mrp`, rotation is `mrp users revoke` followed by
  `mrp users add` for the same user. The new URL has a new hash, so the consuming Supervisor sees a new repository: back
  up the data of the add-ons installed from the old URL, remove the old repository, add the new URL and reinstall the
  add-ons.
- `/data/access.json` can also be edited directly (rules in [Contracts](#contracts)). The add-on applies a hand edit
  within about a second. A file that is not valid JSON is moved aside to `access.json.corrupt` and every URL stops
  working until it is fixed, so prefer `mrp`.
- `mrp sync` and the management page's **Sync now** button are the manual sync triggers. There is no trigger through the
  add-on's standard input.

## Sync and status

The sync service runs one cycle over all configured repositories at start, then every `sync_interval` minutes. A "Sync
now" request (`mrp sync` or the **Sync now** button of the management page) starts a cycle within about a second;
requests that arrive during a running cycle are combined into one more cycle. The interval restarts after every cycle.

Each repository's result is written to `/data/status.json` (see [Contracts](#contracts)) and logged as one line, for
example `sync example-org/private-addons: ok (main @ 0123456789ab, changed)`. Status codes:

| Status               | Meaning                                                                                                                                             | What to do                                                                                                 |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `pending`            | Configured, no sync attempt yet.                                                                                                                    | Wait for the first cycle.                                                                                  |
| `ok`                 | Synced; the mirror serves the branch's current state.                                                                                               | Nothing.                                                                                                   |
| `auth_failed`        | GitHub refused the token (401/403), or `github_token` is empty.                                                                                     | Check that the token is set, not expired and not revoked, and has `Contents: read-only` on the repository. |
| `not_found`          | Repository or branch not found upstream, or the branch name is invalid. GitHub also answers this way for a private repository the token cannot see. | Check the `owner/repo` spelling, the `branch` option and the token's repository selection.                 |
| `no_repository_yaml` | Synced, but the branch root has no `repository.yaml` (or `.yml`/`.json`); the add-on store rejects such a repository.                               | Add `repository.yaml` to the upstream repository.                                                          |
| `fetch_failed`       | Anything else: network error, timeout, unexpected git error. The `message` field has a one-line reason.                                             | Check the network; the next cycle retries.                                                                 |

A repository that fails keeps serving its last good state: the mirror is only replaced by a successful fetch, and
`head`, `addons` and `last_success` in `status.json` keep their last good values. This also holds after a change of
`branch`: the mirror switches to the new branch only once it has been fetched.

## Contracts

The management page and the `mrp` CLI build on these files, and the provisioning API of a later version will build on
them too. Their names, locations, field names and write rules are stable: later versions may add fields, but never
rename or remove them. All files are UTF-8 JSON with mode 0600, and all timestamps are ISO 8601 UTC with `Z` and second
precision (`2026-11-18T12:00:00Z`).

### /data/access.json

Users and their access hashes. Example:

```json
{
  "schema": 1,
  "entries": [
    {
      "created": "2026-11-18T12:00:00Z",
      "hash": "{32 lowercase hex}",
      "repository": "example-org/private-addons",
      "source": "cli",
      "user": "alice"
    }
  ]
}
```

| Field                  | Type    | Meaning                                                                                                                            |
| ---------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `schema`               | integer | Document version, currently `1`.                                                                                                   |
| `entries`              | list    | One entry per (repository, user).                                                                                                  |
| `entries[].repository` | string  | `owner/repo` as configured in `repositories` (case kept, matched case-insensitively).                                              |
| `entries[].user`       | string  | User label, `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`, unique per repository. `local` is reserved for the system user (source `system`). |
| `entries[].hash`       | string  | Access hash: 32 lowercase hex characters, 128 random bits, unique across the whole file.                                           |
| `entries[].created`    | string  | Creation time (ISO 8601 UTC with `Z`). A rotation on the management page sets it to the rotation time.                             |
| `entries[].source`     | string  | Who created the entry: `gui`, `api`, `system` or `cli`. `cli` marks users created with `mrp`.                                      |

Write rules:

- Write only through the add-on's access store (today `mrp` and the management page, source `gui`; the provisioning API
  of a later version). Every read and every read-modify-write holds an exclusive lock on
  `/run/marketplace-repo-proxy/access.lock`.
- A write goes to a temporary file in `/data` (mode 0600) and atomically replaces `access.json` by rename, so readers
  never see a partial file.
- Unknown top-level keys and unknown entry fields are preserved by every write.
- A missing file means no users. A file that is not valid JSON is moved to `access.json.corrupt` and the add-on
  continues with no users (fail closed).
- A `schema` newer than this version knows is refused: nothing is written, and the add-on does not start until the file
  is fixed or the add-on is updated.
- Entries of repositories that are not configured stay in the file but grant no access.
- Changes, including hand edits, are applied within about a second. A hand edit bypasses the lock; replace the file in
  one step (write a copy, then rename it over `access.json`).

### /data/status.json

Sync state, written only by the sync service, always by atomic replace (readers need no lock). Example:

```json
{
  "schema": 1,
  "updated": "2026-11-18T12:00:06Z",
  "upstream_override": false,
  "sync": {
    "state": "idle",
    "last_started": "2026-11-18T12:00:00Z",
    "last_finished": "2026-11-18T12:00:06Z",
    "next_due": "2026-11-18T12:15:06Z",
    "interval_minutes": 15,
    "reason": "startup"
  },
  "repositories": [
    {
      "repository": "example-org/private-addons",
      "branch": "main",
      "branch_source": "upstream_default",
      "status": "ok",
      "message": "",
      "last_attempt": "2026-11-18T12:00:05Z",
      "last_success": "2026-11-18T12:00:05Z",
      "last_change": "2026-11-18T12:00:05Z",
      "head": "0123456789ab",
      "addons": ["demo"],
      "refs_changed": true
    }
  ]
}
```

| Field                          | Type              | Meaning                                                                                           |
| ------------------------------ | ----------------- | ------------------------------------------------------------------------------------------------- |
| `schema`                       | integer           | Document version, currently `1`.                                                                  |
| `updated`                      | timestamp         | Time of the last write.                                                                           |
| `upstream_override`            | boolean           | `true` only when the test-only upstream override is set (test setups, never through the options). |
| `sync.state`                   | string            | `idle` or `running`.                                                                              |
| `sync.last_started`            | timestamp or null | Start of the last cycle.                                                                          |
| `sync.last_finished`           | timestamp or null | End of the last cycle.                                                                            |
| `sync.next_due`                | timestamp or null | When the next interval cycle is due.                                                              |
| `sync.interval_minutes`        | integer           | Effective `sync_interval`.                                                                        |
| `sync.reason`                  | string or null    | What started the last cycle: `startup`, `interval` or `request`.                                  |
| `repositories`                 | list              | One entry per configured repository, in options order.                                            |
| `repositories[].repository`    | string            | `owner/repo` as configured.                                                                       |
| `repositories[].branch`        | string or null    | Served branch: the configured one, or the upstream default branch once it is known.               |
| `repositories[].branch_source` | string            | `configured` or `upstream_default`.                                                               |
| `repositories[].status`        | string            | Status code, see below.                                                                           |
| `repositories[].message`       | string            | One sanitised line for humans; empty on success. Never contains the token or a hash.              |
| `repositories[].last_attempt`  | timestamp or null | Last sync attempt.                                                                                |
| `repositories[].last_success`  | timestamp or null | Last attempt with status `ok` or `no_repository_yaml`; kept when a later attempt fails.           |
| `repositories[].last_change`   | timestamp or null | Last successful attempt that changed the served refs.                                             |
| `repositories[].head`          | string or null    | Short SHA (12 characters) of the served commit; kept when a later attempt fails.                  |
| `repositories[].addons`        | list of strings   | Directories of the add-ons found in the served commit; kept when a later attempt fails.           |
| `repositories[].refs_changed`  | boolean           | The last attempt changed the served refs (only `true` on success).                                |

Status codes: `pending`, `ok`, `auth_failed`, `not_found`, `no_repository_yaml`, `fetch_failed` (meaning in
[Sync and status](#sync-and-status)). `pending` and `fetch_failed` extend the original four codes; all six keep their
meaning.

### /data/last-fetch.json

Last fetch per (repository, user), shown in the Access view of the management page. Example:

```json
{
  "schema": 1,
  "updated": "2026-11-18T12:04:58Z",
  "entries": [
    {
      "repository": "example-org/private-addons",
      "user": "alice",
      "last_fetch": "2026-11-18T12:04:58Z"
    }
  ]
}
```

| Field                  | Type      | Meaning                                                                                      |
| ---------------------- | --------- | -------------------------------------------------------------------------------------------- |
| `schema`               | integer   | Document version, currently `1`.                                                             |
| `updated`              | timestamp | Time of the last write.                                                                      |
| `entries`              | list      | One entry per (repository, user) with a recorded fetch, sorted by repository and user.       |
| `entries[].repository` | string    | `owner/repo` as stored in `access.json`.                                                     |
| `entries[].user`       | string    | User label as stored in `access.json`.                                                       |
| `entries[].last_fetch` | timestamp | Time of the user's last fetch (ISO 8601 UTC with `Z`), as recorded by the add-on, see below. |

Write rules:

- Single writer: the `fetchlog` service. Every write goes to a temporary file in `/data` (mode 0600) and atomically
  replaces `last-fetch.json` by rename, so readers need no lock. The management page only reads the file.
- The file never contains an access hash; entries are keyed by repository and user.
- A fetch is a `POST …/git-upload-pack` request answered with 200: a clone, a fetch and, with git protocol v2, also
  `git ls-remote`. Bare `info/refs` requests and failed requests do not count.
- The file is written, and a `fetch:` line is logged, at most once per access hash per minute. Later fetches within that
  minute are kept in memory and written at the next minute or when the service stops.
- Entries of users that no longer exist in `access.json` are dropped at the next write (nothing is dropped while
  `access.json` cannot be read).
- A rotated or re-created user keeps its old record until the next fetch. The management page shows `last_fetch` only
  when it is newer than the entry's `created`, so it shows "never" until the new URL is used.
- A missing file means no records. A file that is not valid JSON, has a different layout or a newer `schema` is ignored
  and replaced at the next write; it is never moved aside.
- The file is part of backups, like `access.json`.

### Sync trigger

`/run/marketplace-repo-proxy/sync.request` requests a sync of all repositories. Any process in the container creates the
file (`mrp sync` writes `{}`; the content is ignored). The sync service polls for it every second while idle and removes
it before the cycle starts. Requests that arrive during a running cycle are combined into exactly one more cycle. The
interval restarts after every cycle. `/run` is not part of backups.

## Security notes

- **GitHub token.** Use a fine-grained personal access token with `Contents: read-only` on the served repositories only.
  Only the sync service uses it, at fetch time, and only through its process environment. It never appears in the log,
  in a repository config, in the web server's environment or in the served data. An expired or revoked token shows up as
  `auth_failed`.
- **Access hashes.** No log line contains a full hash; the startup log masks hashes to their first 4 characters. Full
  store URLs are printed only by `mrp users add` and `mrp users url`, to the terminal, and shown on demand in the Access
  view of the management page.
- **Access log only into the fetch sink.** lighttpd's access log (method, path and status only) goes to nothing but a
  forwarder that runs as the web server user (`lighttpd`). The forwarder keeps successful `git-upload-pack` requests and
  passes owner, repository and hash over a private socket that only group `lighttpd` can use to the root service
  `fetchlog`, which maps the hash to its user. The add-on log shows only `fetch: {user} → {owner}/{repo}`. No hash and
  no request line is written anywhere: not to the add-on log, not to a file, not to the forwarder's output. Residual
  risk: a process running as the web server user could send false fetch records; this affects only the displayed last
  fetch, never access.
- **Management page.** Reachable only through Home Assistant ingress (every other request gets 403); port 8099 is never
  published. Its process holds neither the GitHub token nor the Supervisor token. Store URLs appear only on demand (Add
  user, Show URLs) and are never logged, and every response carries `Cache-Control: no-store`.
- **Files.** `/data` has mode 0700, and `access.json`, `status.json` and `last-fetch.json` have mode 0600.
- **Backups.** A backup of this add-on contains `/data`: the token (in the options) and every access hash. Treat these
  backups as secret. Restoring one keeps all store URLs valid.
- **Store URLs are capabilities.** Anyone on the `hassio` network who holds a URL can clone that repository. Hand URLs
  out only to the instances that need them, and revoke a leaked URL (Revoke on the management page or
  `mrp users revoke`); rotate it if the user still needs access.
- **Read-only.** Pushes are refused (403), and only the smart-HTTP read endpoints are served.
- **Old commits.** Only the configured branch is offered as a ref. Commits that are no longer on it (an earlier branch,
  history replaced by a force-push) stay in the mirror until git's garbage collection removes them. Until then a client
  with a valid store URL for that repository can fetch such a commit by its full commit ID. Nothing crosses
  repositories, and nothing is reachable without a valid URL.
- **No public exposure without TLS.** Keep port `8080` unpublished; the add-on serves plain HTTP.

## Limitations

- HACS cannot use these URLs; only the Home Assistant add-on store can.
- Private git submodules in a served repository fail to clone.
- Add-ons that use private container images still need registry credentials on the consuming host.
- No TLS inside the add-on.
- Publication through a reverse proxy (`public_url`) is documented in a later version.

## Development

`bash internal/verify-marketplace-repo-proxy.sh` builds the image and proves the add-on against a local upstream fixture
(it never contacts GitHub). It starts containers and must never run in two worktrees at the same time.

`bash internal/verify-marketplace-repo-proxy-gui.sh` builds the image and proves the management page (ingress gate,
overview, version, Sync now), the access actions (add, URLs, revoke, rotate) and the fetch sink (last fetch, privileges,
no hash in any output) in containers, again without GitHub. It needs a free Docker subnet around the HA ingress address,
refuses to start while any marketplace-repo-proxy verify run is active and must never run in two worktrees at the same
time.
