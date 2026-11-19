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
- Self-registration: with `register_local` (on by default) the add-on adds its own internal store URL of every
  repository to this Home Assistant's add-on store, and asks the Supervisor to reload the store after an upstream change
  (see [Store registration](#store-registration)).

The add-on itself never installs, updates or uninstalls an add-on. A Home Assistant instance adds a store URL as a
repository, and its Supervisor clones from the add-on like from any public repository.

Not in this version: a management page, the provisioning API and documented public access through a reverse proxy. They
follow in later versions. Until then users and the store registration are managed with the `mrp` command inside the
container (see [Managing users](#managing-users) and [Store registration](#store-registration)).

## Repository exception

This add-on is our own code, not a wrapper around an upstream project. It therefore has no `.upstream.yaml` and no
auto-update. Its image is built and published by CI like the others (`image:` key). The other repo rules still apply: HA
base image only, 3-file version sync via `make update-version`, and a local `docker build` before every commit.

## Options

| Option                      | Type                          | Default  | Description                                                                                                                                                                                                          |
| --------------------------- | ----------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `github_token`              | password                      | empty    | Fine-grained personal access token with `Contents: read-only` on the repositories below. Never logged. Empty token: every repository `auth_failed`.                                                                  |
| `sync_interval`             | integer, minimum 5            | `15`     | Minutes between two sync cycles.                                                                                                                                                                                     |
| `public_url`                | URL, optional                 | not set  | Base URL behind a reverse proxy, e.g. `https://addons.example.com`. Not set: internal access only. Adds a second (public) store URL per user.                                                                        |
| `repositories`              | list                          | empty    | Private GitHub repositories to serve.                                                                                                                                                                                |
| `repositories[].repository` | `owner/repo`                  | required | GitHub owner (user or organization) and repository name. Case-insensitive; a `.git` suffix is not allowed.                                                                                                           |
| `repositories[].branch`     | branch name, optional         | not set  | Branch to serve. Not set: the repository's default branch. Only this branch is offered as a ref; see [Security notes](#security-notes) for old commits.                                                              |
| `register_local`            | boolean                       | `true`   | Register the internal store URL of every repository in this Home Assistant's add-on store after its first successful sync (see [Store registration](#store-registration)). `false` stops adding; it removes nothing. |
| `api_enabled`               | boolean                       | `false`  | Enable the provisioning API. **No effect yet**; takes effect in a later version.                                                                                                                                     |
| `log_level`                 | `debug\|info\|warning\|error` | `info`   | Verbosity of the add-on log. Tokens and access hashes are never logged, at any level.                                                                                                                                |

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
characters of the hash, for example `.../repo/example-org/private-addons/3f9c…`. The full URL is printed only by
`mrp users add` and `mrp users url` (see [Managing users](#managing-users)).

To use a URL, add it in Home Assistant under **Settings → Add-ons → Add-on store → ⋮ → Repositories**.

- Query parameters on the store URL (for example `?ref=main&tab=readme`) are accepted and ignored.
- A `#branch` suffix works for the served branch: the Supervisor removes it and clones that branch. Only the configured
  branch (or the default branch) is served, so any other branch name fails.
- The URL is the repository's identity in the consuming Supervisor. A different URL (for example a new hash after a
  rotation) is a different repository: it has to be added again, and its add-ons have to be reinstalled.
- Port `8080` is not published by default. The URL works on the internal `hassio` network, i.e. for the Supervisor and
  for other add-ons of the same Home Assistant. There is no TLS inside the add-on. Do not publish the port to reach it
  from outside; public access through a reverse proxy is documented in a later version.

## Store registration

The add-on registers its repositories in the add-on store of the Home Assistant it runs on, and keeps them up to date.
It talks to the Supervisor only from the sync process: `mrp local rotate` and `mrp local remove` hand their work to that
process and wait up to 30 seconds for the result, and `mrp local status` only reads the state file.

| Command                               | Effect                                                                                                                                    |
| ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `mrp local status [{owner/repo}]`     | Shows the registration of each repository, the last store reload and every leftover (read from `/data/supervisor.json`).                  |
| `mrp local rotate {owner/repo} --yes` | Rotates the repository's `local` URL; see [Rotating the local URL](#rotating-the-local-url).                                              |
| `mrp local remove {owner/repo}`       | Removes the repository's store repository and retries its leftovers; see [Removing the store repository](#removing-the-store-repository). |

`mrp local status` prints one tab-separated line per repository (repository, registration, store slug, masked URL, and
`(unconfigured)` for a repository that is no longer configured), one line `reload: last {time} {result}, pending yes|no`
and one line per leftover (`leftover`, repository, store slug, reason, user, since). Before the first start of the sync
process it prints `no registration state yet`.

When the sync process is busy with a cycle for longer than 30 seconds, `mrp local rotate` and `mrp local remove` print
`queued: {id}` and exit 0; the request still runs, and `mrp local status` shows its effect later. Errors print
`error: {code}` and exit with 1.

### Self-registration

The add-on keeps one system user `local` (source `system`) per configured repository. Its store URL is the add-on's
internal URL:

```text
http://{repo-hash}-marketplace-repo-proxy:8080/repo/{owner}/{repo}/{hash}
```

After every sync cycle the sync process lists the store repositories (`GET /store/repositories`). For every repository
whose last sync is `ok`, it creates the `local` user when there is none yet and adds its URL
(`POST /store/repositories`) when the store does not list it. The Supervisor clones the repository from the add-on
before it answers, which is why only a repository that synced `ok` (with a valid `repository.yaml`) is added. The add-on
log then shows:

```text
store: example-org/private-addons registered as {store slug} ({masked URL})
```

`{masked URL}` is the URL with the hash masked to its first 4 characters (`.../repo/example-org/private-addons/3f9c…`),
and `{store slug}` is the Supervisor's identity of the store repository: 8 hex characters derived from the URL. The
repository then appears in **Settings → Add-ons → Add-on store** like any added repository.

- **After updating to this version** the add-on registers its configured repositories automatically at the next sync, as
  long as `register_local` is `true` (the default). Set it to `false` before the update to prevent that.
- `register_local: false` stops adding. It removes nothing: a URL that is already in the store stays there and its
  registration stays `registered`. Removal is always an explicit action (see
  [Removing the store repository](#removing-the-store-repository)).
- The `local` user is listed by `mrp users list` like any user (source `system`), and `mrp users url {owner/repo} local`
  prints its full URL. Treat that URL as a secret like every store URL.
- When the Supervisor cannot be reached, does not answer in time, cannot list the store or rejects the add, the
  registration of the affected repositories is `error`, and the add-on log has one warning when the failure starts
  (`store list unavailable: {cause}` or `store: registration of {owner/repo} failed: {reason}`). Serving and syncing go
  on; the next cycle tries again.
- The URL contains the add-on's hostname. It stays the same across restarts, updates and backups, because `/data` keeps
  the hash. When the hostname changes while `/data` stays (for example a backup restored into an install of this add-on
  from another repository, or into a local copy), the add-on logs
  `store: hostname changed since the last run; earlier store URLs are reported as leftovers`, registers the new URL and
  reports the old store repository as an `orphaned` leftover. A fresh install with a new `/data` (for example switching
  between a local copy and the install from this repository) creates a new `local` hash and knows nothing about the old
  store repository: remove that one in the store yourself.

### Store reload

The Supervisor pulls its store repositories on its own only every few hours. To make an upstream change visible within
minutes, the add-on calls `POST /store/reload` after a sync cycle in which the served commit of a repository changed
whose `local` URL was in the store. The log shows `store reload: ok` or `store reload: failed: {reason}`.

- At most one reload per `sync_interval`, also when `mrp sync` starts cycles more often. A change inside that window is
  deferred: the log shows `store reload: deferred until {UTC time}`, and the reload is sent when the window opens.
- A deferred reload survives a restart (`reload.pending` in `/data/supervisor.json`). The first window after a start is
  open, so it is sent after the first cycle.
- A failed reload stays owed and is retried when the next window opens.
- The reload pulls every store repository of this Home Assistant, not only the add-on's own.
- A repository that was just added needs no reload: the Supervisor cloned its current state during the add.

### Rotating the local URL

> **Warning:** rotation revokes the current `local` URL at once. Add-ons installed from the old store repository then
> get no updates until they are reinstalled from the new one.

Rotate the `local` URL when it has leaked, for example through a shared Supervisor log (see
[Security notes](#security-notes)). There is no option that keeps the old URL serving.

```bash
docker exec addon_{repo-hash}_marketplace_repo_proxy mrp local rotate example-org/private-addons --yes
```

- `mrp local rotate {owner/repo}` without `--yes` prints only the warning and `error: confirmation_required` and exits
  with 1. The warning goes to standard error on every call, also with `--yes`.
- With `--yes` the sync process creates a new `local` hash and adds the new URL to the store first. Right after that add
  it revokes the old URL, which answers 404 from the next request on. Then it tries to remove the old store repository
  (`DELETE /store/repositories/{slug}`).
- Success prints `rotated: new store repository {slug} registered; old URL revoked`.
- While add-ons installed from the old store repository exist, the Supervisor refuses the removal. The command prints
  `refused: in_use old store repository {slug} is still used by installed add-ons; ...` and exits with 1. The old store
  repository is reported as a leftover (reason `in_use`, registration `leftover`); its URL is revoked anyway.
- A failed add changes nothing: the old URL stays registered and keeps serving (`error: add_failed`).
- Other errors: `repository_unknown`, `register_local_disabled` (rotation needs `register_local: true`),
  `not_registered` (no `local` user yet), `store_list_unavailable`, and `remove_failed` (the removal failed for another
  reason; leftover `error`).

Procedure when add-ons are installed from the store repository:

1. Back up the data of the add-ons installed from the old store repository.
2. Rotate: `mrp local rotate {owner/repo} --yes`.
3. Install the add-ons from the new store repository and restore their data.
4. Uninstall the add-ons from the old store repository.
5. Remove the leftover: `mrp local remove {owner/repo}`.

Until step 5, the Supervisor log shows failed pulls of the revoked URL at every store reload.

### Removing the store repository

```bash
docker exec addon_{repo-hash}_marketplace_repo_proxy mrp local remove example-org/private-addons
```

- `mrp local remove {owner/repo}` retries every leftover of the repository.
- It removes the current registration only when `register_local` is `false` or the repository is no longer in
  `repositories`. Otherwise, with no leftover to retry, it answers `error: register_local_enabled`.
- Removing a store repository also revokes the `local` URL that served it. When `register_local` is turned on again
  later, the add-on registers a new `local` URL.
- Success prints `removed: {owner/repo}: store repository removed (see mrp local status)`; the registration is then
  `missing` (an unconfigured repository disappears from the list).
- The Supervisor refuses to remove a store repository that installed add-ons still use. The command prints
  `refused: in_use {owner/repo}: ...` and exits with 1. Nothing changes in the store, and the store repository is
  reported as a leftover (`in_use`). Uninstall those add-ons, then run the command again. The add-on never forces a
  removal and never uninstalls an add-on.
- Other errors: `repository_unknown`, `not_registered` (nothing recorded to remove), `store_list_unavailable` and
  `remove_failed`.

`register_local: false` and removing a repository from `repositories` remove nothing in the store by themselves. Removal
is always an explicit operator action. A repository that is removed from `repositories` stops serving, but its store
repository stays listed: the Supervisor log shows failed pulls at every store reload, and the repository is shown as
`leftover` with `configured: false` until its store repository is removed.

Removing the store repository in Home Assistant (**Settings → Add-ons → Add-on store → ⋮ → Repositories**, or
`ha store delete {slug}`) also works. The add-on notices it at the next sync: leftovers and unconfigured repositories
whose store repository is gone are dropped from `/data/supervisor.json`, and their `local` URLs are revoked. A
configured repository with `register_local: true` is added again at the next sync, so set `register_local: false` first.

### Leftovers

A leftover is a store repository that the add-on registered and could not remove, or no longer uses. Leftovers are never
removed automatically. Each one is logged at warning level as `store: {owner/repo} leftover {slug} ({reason})`, and
`mrp local status` and `leftovers[]` in `/data/supervisor.json` show it. While a repository has a leftover, its
registration is `leftover` (or `error`, which takes precedence).

| Reason        | Meaning                                                                                                                                                                                           | What to do                                                                                        |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `in_use`      | The Supervisor refused the removal (during a rotation or `mrp local remove`) because add-ons installed from the store repository still exist.                                                     | Reinstall those add-ons from the new store repository or uninstall them, then `mrp local remove`. |
| `error`       | The removal failed for another reason (Supervisor error or timeout).                                                                                                                              | Check the add-on log, then run `mrp local remove` again.                                          |
| `interrupted` | A rotation stopped between the switch to the new URL and the revoke of the old one, for example by a restart. The next sync revokes the old URL and reports its store repository if still listed. | As for `in_use`: move the installed add-ons, then `mrp local remove`.                             |
| `orphaned`    | A store repository the add-on recorded earlier is still listed but is no longer the current one: the hostname changed, or `access.json` was edited by hand.                                       | Move the add-ons installed from it, then `mrp local remove`.                                      |

A repository that was removed from `repositories` while its store repository is still listed has no entry in
`leftovers[]`, but its registration is `leftover` too (`configured: false`). Remove it with `mrp local remove` or in the
store.

A leftover disappears once its store repository is gone: at once when `mrp local remove` removed it, at the next sync
when it was removed in Home Assistant.

## Managing users

There is no management page yet. Until it exists, users are managed with the `mrp` command inside the running container.
On the Home Assistant host (for example from the SSH add-on with host access), the container is called
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

- A user label is 1 to 64 characters: letters, digits, `.`, `_` and `-`, starting with a letter or digit. The labels
  `local` and `local.*` are reserved for the add-on's own store registration: `mrp users add` and `mrp users revoke`
  answer `error: user_reserved` for them. Manage that registration with `mrp local` (see
  [Store registration](#store-registration)).
- Only `mrp users add` and `mrp users url` print the full URL, and only to the terminal. Treat it as a secret.
- Errors print `error: {code}` and exit with 1, for example `repository_unknown` (not in `repositories`), `user_exists`,
  `user_unknown`, `invalid_user`, `user_reserved`, `invalid_hash`, `hash_conflict` (the given hash is already in use)
  and `options_invalid`. Usage errors exit with 2.
- **Rotation** is `mrp users revoke` followed by `mrp users add` for the same user. The new URL has a new hash, so the
  consuming Supervisor sees a new repository: back up the data of the add-ons installed from the old URL, remove the old
  repository, add the new URL and reinstall the add-ons. The add-on's own `local` URL rotates with `mrp local rotate`
  instead (see [Rotating the local URL](#rotating-the-local-url)).
- `/data/access.json` can also be edited directly (rules in [Contracts](#contracts)). The add-on applies a hand edit
  within about a second. A file that is not valid JSON is moved aside to `access.json.corrupt` and every URL stops
  working until it is fixed, so prefer `mrp`.
- `mrp sync` is the only manual sync trigger. There is no trigger through the add-on's standard input.

## Sync and status

The sync service runs one cycle over all configured repositories at start, then every `sync_interval` minutes. A "Sync
now" request (`mrp sync`, later the management page) starts a cycle within about a second; requests that arrive during a
running cycle are combined into one more cycle. The interval restarts after every cycle.

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

The management page and the provisioning API of later versions build on these files. Their names, locations, field names
and write rules are stable: later versions may add fields, but never rename or remove them. All files are UTF-8 JSON
with mode 0600, and all timestamps are ISO 8601 UTC with `Z` and second precision (`2026-11-18T12:00:00Z`).

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
| `entries[].created`    | string  | Creation time (ISO 8601 UTC with `Z`).                                                                                             |
| `entries[].source`     | string  | Who created the entry: `gui`, `api`, `system` or `cli`. `cli` marks users created with `mrp`.                                      |

Write rules:

- Write only through the add-on's access store (`mrp` now, the management page and the API later). Every read and every
  read-modify-write holds an exclusive lock on `/run/marketplace-repo-proxy/access.lock`.
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

### /data/supervisor.json

Store registration state (see [Store registration](#store-registration)). Rules:

- Single writer: the sync process. Every write is an atomic replace with mode 0600, so readers need no lock.
- The file is written at every start of the sync process, before its first Supervisor call, and after every change.
- It holds store slugs and masked URLs only, never a full access hash, a full store URL or a token.
- The keys of each object are written in alphabetical order. Do not rely on any key order.
- Later versions may add fields, but never rename or remove them.

#### Phase 3 interface

The management page of a later version reads this part of the file as is:

- The top-level key `repositories` is always present: a list of objects.
- There is one object per configured repository, in options order, followed by one object per repository that is no
  longer configured but whose store repository is still recorded (`configured: false`). On the first start every
  repository is `missing`; later starts keep the last recorded facts until the next check.
- Each object has `repository` (`owner/repo` as configured), `registration` (one of the four values in
  [Registration status](#registration-status)) and an optional `message`. All other keys are additions.
- `message` is plain human-readable text from the fixed English templates below. It never contains a token, a URL, a
  `/repo/` path, a hash or Supervisor error text. Supervisor text stays in the add-on log; the state keeps the code in
  `error` and the HTTP status in `error_status`. `message` is absent for `registered`.

| `registration` | Situation                        | `message`                                                                                                            |
| -------------- | -------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `registered`   | any                              | none                                                                                                                 |
| `missing`      | `register_local: false`          | `Registration is turned off (register_local: false)`                                                                 |
| `missing`      | otherwise                        | `Not in the store yet; added after the next successful sync`                                                         |
| `leftover`     | configured, with leftovers       | `{N} old store repository left ({reasons}); see mrp local status` (`repositories` for more than one, reasons sorted) |
| `leftover`     | no longer configured             | `No longer configured; its store repository is still listed`                                                         |
| `error`        | `add_rejected`                   | `The Supervisor rejected the store URL (HTTP {status})`                                                              |
| `error`        | `store_list_unavailable`         | `Store list unavailable (HTTP {status})`                                                                             |
| `error`        | `timeout`                        | `The Supervisor did not answer in time`                                                                              |
| `error`        | `unreachable`                    | `The Supervisor is unreachable`                                                                                      |
| `error`        | `token_missing`                  | `No Supervisor token in the add-on environment`                                                                      |
| `error`        | `internal_error` or unknown code | `Internal error; see the add-on log`                                                                                 |

`{status}` is `?` when no HTTP status is known. A message is one line of at most 200 characters; text that looks like a
URL, a hash or a token is replaced by `Details are in the add-on log`.

Example with two repositories (other keys omitted):

```json
{
  "repositories": [
    {
      "repository": "example-org/private-addons",
      "registration": "registered"
    },
    {
      "repository": "example-org/beta-addons",
      "registration": "missing",
      "message": "Not in the store yet; added after the next successful sync"
    }
  ]
}
```

#### Registration status

The field `registration` has exactly these four values. No other value is ever written, and later versions keep this
set. Finer detail lives in `in_store`, `error` and `leftovers[]`.

| Value        | Meaning                                                                                                                                        |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `registered` | The repository's current `local` URL is in the store.                                                                                          |
| `missing`    | The current `local` URL is not in the store: not added yet, registration turned off, or removed.                                               |
| `leftover`   | An old store repository of this repository is left over (see `leftovers[]`), or the repository is no longer configured but still in the store. |
| `error`      | The last check or add failed; `error` and `error_status` give the cause.                                                                       |

Mapping from situations to values:

| Situation                                                                                                    | `registration` |
| ------------------------------------------------------------------------------------------------------------ | -------------- |
| Synced `ok` and the current `local` URL is listed or was just added                                          | `registered`   |
| `register_local: false` and the current URL is still listed                                                  | `registered`   |
| First start, before any registration                                                                         | `missing`      |
| Not yet synced `ok`, URL not listed                                                                          | `missing`      |
| `register_local: false` and the URL is not listed                                                            | `missing`      |
| Removed with `mrp local remove`                                                                              | `missing`      |
| Current URL listed while an old store repository is a leftover (rotation refused, `interrupted`, `orphaned`) | `leftover`     |
| Removal refused (`in_use`)                                                                                   | `leftover`     |
| Repository removed from `repositories` while its store repository is still listed                            | `leftover`     |
| Add failed, Supervisor unreachable or too slow, store list unavailable, token missing                        | `error`        |
| Add failed while a leftover exists                                                                           | `error`        |

When several situations apply, the first match wins in this order: `error`, then `leftover`, then `registered`, then
`missing` (`registration_value` in `app/supervisor_state.py`). A failed store list sets `error` only for the
repositories that want a registration in that cycle (synced `ok` and `register_local: true`); the others keep their last
value.

#### All fields

Example:

```json
{
  "schema": 1,
  "updated": "2026-11-18T12:30:07Z",
  "register_local": true,
  "hostname": "{repo-hash}-marketplace-repo-proxy",
  "supervisor": {
    "last_contact": "2026-11-18T12:30:05Z",
    "last_status": 200,
    "last_error": null
  },
  "reload": {
    "last_requested": "2026-11-18T12:15:06Z",
    "last_result": "ok",
    "pending": false,
    "message": ""
  },
  "repositories": [
    {
      "repository": "example-org/private-addons",
      "registration": "leftover",
      "message": "1 old store repository left (in_use); see mrp local status",
      "configured": true,
      "in_store": true,
      "error": null,
      "error_status": null,
      "store_slug": "{8 hex}",
      "masked_url": "http://{repo-hash}-marketplace-repo-proxy:8080/repo/example-org/private-addons/3f9c…",
      "registered_at": "2026-11-18T12:20:00Z",
      "last_checked": "2026-11-18T12:30:05Z"
    }
  ],
  "leftovers": [
    {
      "repository": "example-org/private-addons",
      "store_slug": "{8 hex}",
      "user": "local.{8 hex}",
      "masked_url": "http://{repo-hash}-marketplace-repo-proxy:8080/repo/example-org/private-addons/abcd…",
      "since": "2026-11-18T12:20:00Z",
      "reason": "in_use",
      "message": "Can't remove '{masked URL}'. It's used by installed apps",
      "revoked": true
    }
  ],
  "requests": [
    {
      "id": "{16 hex}",
      "action": "rotate",
      "repository": "example-org/private-addons",
      "result": "refused",
      "code": "in_use",
      "finished": "2026-11-18T12:20:01Z"
    }
  ]
}
```

| Field                          | Type              | Meaning                                                                                                                                                               |
| ------------------------------ | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `schema`                       | integer           | Document version, currently `1`.                                                                                                                                      |
| `updated`                      | timestamp         | Time of the last write.                                                                                                                                               |
| `register_local`               | boolean           | The `register_local` option the sync process started with.                                                                                                            |
| `hostname`                     | string            | Container hostname used in the `local` URLs. A different value at the next start logs the hostname warning (see [Self-registration](#self-registration)).             |
| `supervisor.last_contact`      | timestamp or null | Last attempt to list the store.                                                                                                                                       |
| `supervisor.last_status`       | integer or null   | HTTP status of that attempt; `0` when there was no HTTP answer.                                                                                                       |
| `supervisor.last_error`        | string or null    | Supervisor message (or `timeout`/`unreachable`) of a failed attempt, with hashes masked; null after a successful one.                                                 |
| `reload.last_requested`        | timestamp or null | Last `POST /store/reload`.                                                                                                                                            |
| `reload.last_result`           | string or null    | `ok` or `failed`; null before the first reload.                                                                                                                       |
| `reload.pending`               | boolean           | A reload is owed (deferred or failed). It is sent when the next window opens, also after a restart.                                                                   |
| `reload.message`               | string            | Reason of the last failed reload, with hashes masked; empty after a successful one.                                                                                   |
| `repositories`                 | list              | One object per repository, see [Phase 3 interface](#phase-3-interface).                                                                                               |
| `repositories[].repository`    | string            | `owner/repo` as configured.                                                                                                                                           |
| `repositories[].registration`  | string            | `registered`, `missing`, `leftover` or `error`, see [Registration status](#registration-status).                                                                      |
| `repositories[].message`       | string, optional  | Fixed text for humans, see the template table above; absent for `registered`.                                                                                         |
| `repositories[].configured`    | boolean           | `false` for a repository that is no longer configured but whose store repository is still recorded.                                                                   |
| `repositories[].in_store`      | boolean           | The store listed the current `local` URL at the last check (or it was just added). Kept while the store list is unavailable.                                          |
| `repositories[].error`         | string or null    | Error code of the last check or add: `add_rejected`, `store_list_unavailable`, `timeout`, `unreachable`, `token_missing` or `internal_error`; null when it succeeded. |
| `repositories[].error_status`  | integer or null   | HTTP status for `add_rejected` and `store_list_unavailable`; null otherwise.                                                                                          |
| `repositories[].store_slug`    | string or null    | Supervisor identity (8 hex characters) of the current `local` URL; null before there is a `local` user.                                                               |
| `repositories[].masked_url`    | string            | Current `local` URL with the hash masked; empty before there is a `local` user.                                                                                       |
| `repositories[].registered_at` | timestamp or null | When the current URL was first seen in the store or added.                                                                                                            |
| `repositories[].last_checked`  | timestamp or null | Last check of this repository.                                                                                                                                        |
| `leftovers`                    | list              | Store repositories the add-on registered and could not remove, see [Leftovers](#leftovers).                                                                           |
| `leftovers[].repository`       | string            | `owner/repo` the store repository belongs to.                                                                                                                         |
| `leftovers[].store_slug`       | string            | Supervisor identity (8 hex characters) of the left-over store repository.                                                                                             |
| `leftovers[].user`             | string or null    | Access label that served it: `local` (the current URL, removal refused or failed), `local.{slug}` (retired by a rotation) or null (`orphaned`).                       |
| `leftovers[].masked_url`       | string            | Its URL with the hash masked; empty when unknown.                                                                                                                     |
| `leftovers[].since`            | timestamp         | When the leftover was first recorded.                                                                                                                                 |
| `leftovers[].reason`           | string            | `in_use`, `error`, `interrupted` or `orphaned`.                                                                                                                       |
| `leftovers[].message`          | string            | Supervisor message of the refused removal with hashes masked; may be empty.                                                                                           |
| `leftovers[].revoked`          | boolean           | `true` when its URL no longer serves (always after a rotation).                                                                                                       |
| `requests`                     | list              | Results of the last 20 `mrp local` requests, oldest first.                                                                                                            |
| `requests[].id`                | string            | Request ID, 16 hex characters (`queued: {id}` names it).                                                                                                              |
| `requests[].action`            | string            | `remove` or `rotate`; any other action is `rejected` with the code `invalid_request`.                                                                                 |
| `requests[].repository`        | string            | Repository as given to `mrp local`.                                                                                                                                   |
| `requests[].result`            | string            | `done`, `refused` (the Supervisor refused a removal), `failed` or `rejected` (the request was not valid).                                                             |
| `requests[].code`              | string            | Empty for `done`, else the error code `mrp local` prints, for example `in_use` or `register_local_enabled`.                                                           |
| `requests[].finished`          | timestamp         | When the sync process finished the request.                                                                                                                           |

### Sync trigger

`/run/marketplace-repo-proxy/sync.request` requests a sync of all repositories. Any process in the container creates the
file (`mrp sync` writes `{}`; the content is ignored). The sync service polls for it every second while idle and removes
it before the cycle starts. Requests that arrive during a running cycle are combined into exactly one more cycle. The
interval restarts after every cycle. `/run` is not part of backups.

### Supervisor requests

`/run/marketplace-repo-proxy/supervisor.requests/` is the internal queue between `mrp local` and the sync process. It is
not an API for other tools, and its format may change.

- Only `mrp local remove` and `mrp local rotate` write to it: one file `{id}.json` per request (`id` is 16 hex
  characters) with exactly the keys `id`, `action`, `repository` and `created`.
- The sync process picks the files up between cycles, oldest first, and executes them one at a time. It deletes each
  file before it runs it, validates it as untrusted input and runs it once. Invalid files are deleted with the warning
  `ignored an invalid supervisor request file`.
- The result goes to `requests[]` in `/data/supervisor.json`, where `mrp local` waits for its `id`.
- The directory has mode 0700. `/run` is not part of backups, so a request that has not run yet is lost on a restart.

## Security notes

- **GitHub token.** Use a fine-grained personal access token with `Contents: read-only` on the served repositories only.
  Only the sync service uses it, at fetch time, and only through its process environment. It never appears in the log,
  in a repository config, in the web server's environment or in the served data. An expired or revoked token shows up as
  `auth_failed`.
- **Access hashes.** No log line contains a full hash; the startup log masks hashes to their first 4 characters. Full
  store URLs are printed only by `mrp users add` and `mrp users url`, to the terminal.
- **Files.** `/data` has mode 0700, and `access.json`, `status.json` and `supervisor.json` have mode 0600.
- **Backups.** A backup of this add-on contains `/data`: the token (in the options) and every access hash. Treat these
  backups as secret. Restoring one keeps all store URLs valid.
- **Store URLs are capabilities.** Anyone on the `hassio` network who holds a URL can clone that repository. Hand URLs
  out only to the instances that need them, and revoke a leaked URL (`mrp users revoke`); rotate it if the user still
  needs access.
- **Read-only.** Pushes are refused (403), and only the smart-HTTP read endpoints are served.
- **Old commits.** Only the configured branch is offered as a ref. Commits that are no longer on it (an earlier branch,
  history replaced by a force-push) stay in the mirror until git's garbage collection removes them. Until then a client
  with a valid store URL for that repository can fetch such a commit by its full commit ID. Nothing crosses
  repositories, and nothing is reachable without a valid URL.
- **No public exposure without TLS.** Keep port `8080` unpublished; the add-on serves plain HTTP.
- **Supervisor manager role.** For the store registration the add-on has `hassio_api: true` and `hassio_role: manager`,
  because the Supervisor's store endpoints are reserved for the `manager` role; with the default role every store call
  is refused.
  - The role would allow much more: controlling other add-ons (except their security settings), backups, and the Core,
    host, OS and Supervisor endpoints (plus Docker, mount and network settings).
  - The add-on uses only four calls: `GET /store/repositories`, `POST /store/repositories`,
    `DELETE /store/repositories/{slug}` and `POST /store/reload`. A single client module checks every request against
    this list before any network I/O, and a `DELETE` only ever names a store slug the add-on recorded from its own URLs.
  - The Supervisor token is used only by the sync process. lighttpd and access-watch run without it, and `mrp` never
    uses it: `mrp local` hands its work to the sync process (see [Supervisor requests](#supervisor-requests)).
  - Every call writes one log line `supervisor {METHOD} {path}: {status}` with the path template, without the token, a
    request or response body or a full hash.
  - The manager role lowers the add-on's security rating in the Supervisor from 7 to 6.
  - The Supervisor's own log shows registered store URLs in full when it clones or pulls them. Access to that log equals
    access to the `local` URLs; rotate a `local` URL that has leaked (see
    [Rotating the local URL](#rotating-the-local-url)).
  - A refused removal (add-ons are still installed from the store repository) makes the Supervisor log an error with a
    traceback and, with diagnostics enabled, send an error report. The add-on only causes this on an explicit
    `mrp local rotate` or `mrp local remove`, never in a loop.

## Limitations

- HACS cannot use these URLs; only the Home Assistant add-on store can.
- Private git submodules in a served repository fail to clone.
- Add-ons that use private container images still need registry credentials on the consuming host.
- No TLS inside the add-on.
- Publication through a reverse proxy (`public_url`) is documented in a later version.
- The add-on talks to the Supervisor's TCP API (`http://supervisor`) with its token. Newer Supervisor versions add a
  per-add-on socket, which a later version may use.
- Self-registration covers only the Home Assistant the add-on runs on. Other instances add a store URL by hand.

## Development

`bash internal/verify-marketplace-repo-proxy.sh` builds the image and proves the add-on against a local upstream fixture
(it never contacts GitHub). Next to it, it runs a fake Supervisor container and proves the store registration, the store
reload, rotation, removal, the leftover report and token hygiene (it never contacts a real Supervisor). It starts
containers and must never run in two worktrees at the same time.
