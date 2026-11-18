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

The add-on itself never installs anything. A Home Assistant instance adds a store URL as a repository, and its
Supervisor clones from the add-on like from any public repository.

Not in this version: a management page, self-registration in the local add-on store, the provisioning API and documented
public access through a reverse proxy. They follow in later versions. Until then users are managed with the `mrp`
command inside the container (see [Managing users](#managing-users)).

## Repository exception

This add-on is our own code, not a wrapper around an upstream project. It therefore has no `.upstream.yaml` and no
auto-update. Its image is built and published by CI like the others (`image:` key). The other repo rules still apply: HA
base image only, 3-file version sync via `make update-version`, and a local `docker build` before every commit.

## Options

| Option                      | Type                          | Default  | Description                                                                                                                                         |
| --------------------------- | ----------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `github_token`              | password                      | empty    | Fine-grained personal access token with `Contents: read-only` on the repositories below. Never logged. Empty token: every repository `auth_failed`. |
| `sync_interval`             | integer, minimum 5            | `15`     | Minutes between two sync cycles.                                                                                                                    |
| `public_url`                | URL, optional                 | not set  | Base URL behind a reverse proxy, e.g. `https://addons.example.com`. Not set: internal access only. Adds a second (public) store URL per user.       |
| `repositories`              | list                          | empty    | Private GitHub repositories to serve.                                                                                                               |
| `repositories[].repository` | `owner/repo`                  | required | GitHub owner (user or organization) and repository name. Case-insensitive; a `.git` suffix is not allowed.                                          |
| `repositories[].branch`     | branch name, optional         | not set  | Branch to serve. Not set: the repository's default branch. Only this one branch is served.                                                          |
| `register_local`            | boolean                       | `true`   | Register the internal store URL in this Home Assistant's add-on store. **No effect yet**; takes effect in a later version.                          |
| `api_enabled`               | boolean                       | `false`  | Enable the provisioning API. **No effect yet**; takes effect in a later version.                                                                    |
| `log_level`                 | `debug\|info\|warning\|error` | `info`   | Verbosity of the add-on log. Tokens and access hashes are never logged, at any level.                                                               |

Users and their access hashes never appear in the options. They live in `/data/access.json` (see
[Managing users](#managing-users) and Contracts). An invalid or duplicate entry in `repositories` is skipped with a
warning in the log; the other entries keep working.

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

- A user label is 1 to 64 characters: letters, digits, `.`, `_` and `-`, starting with a letter or digit. The label
  `local` is reserved for a system user of a later version.
- Only `mrp users add` and `mrp users url` print the full URL, and only to the terminal. Treat it as a secret.
- Errors print `error: {code}` and exit with 1, for example `repository_unknown` (not in `repositories`), `user_exists`,
  `user_unknown`, `invalid_user`, `user_reserved`, `invalid_hash`, `hash_conflict` (the given hash is already in use)
  and `options_invalid`. Usage errors exit with 2.
- **Rotation** is `mrp users revoke` followed by `mrp users add` for the same user. The new URL has a new hash, so the
  consuming Supervisor sees a new repository: back up the data of the add-ons installed from the old URL, remove the old
  repository, add the new URL and reinstall the add-ons.
- `/data/access.json` can also be edited directly (rules in Contracts). The add-on applies a hand edit within about a
  second. A file that is not valid JSON is moved aside to `access.json.corrupt` and every URL stops working until it is
  fixed, so prefer `mrp`.
- `mrp sync` is the only manual sync trigger. There is no trigger through the add-on's standard input.

## Sync and status

The sync service runs one cycle over all configured repositories at start, then every `sync_interval` minutes. A "Sync
now" request (`mrp sync`, later the management page) starts a cycle within about a second; requests that arrive during a
running cycle are combined into one more cycle. The interval restarts after every cycle.

Each repository's result is written to `/data/status.json` (see Contracts) and logged as one line, for example
`sync example-org/private-addons: ok (main @ 0123456789ab, changed)`. Status codes:

| Status               | Meaning                                                                                                                                             | What to do                                                                                                 |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `pending`            | Configured, no sync attempt yet.                                                                                                                    | Wait for the first cycle.                                                                                  |
| `ok`                 | Synced; the mirror serves the branch's current state.                                                                                               | Nothing.                                                                                                   |
| `auth_failed`        | GitHub refused the token (401/403), or `github_token` is empty.                                                                                     | Check that the token is set, not expired and not revoked, and has `Contents: read-only` on the repository. |
| `not_found`          | Repository or branch not found upstream, or the branch name is invalid. GitHub also answers this way for a private repository the token cannot see. | Check the `owner/repo` spelling, the `branch` option and the token's repository selection.                 |
| `no_repository_yaml` | Synced, but the branch root has no `repository.yaml` (or `.yml`/`.json`); the add-on store rejects such a repository.                               | Add `repository.yaml` to the upstream repository.                                                          |
| `fetch_failed`       | Anything else: network error, timeout, unexpected git error. The `message` field has a one-line reason.                                             | Check the network; the next cycle retries.                                                                 |

A repository that fails keeps serving its last good state: the mirror is only replaced by a successful fetch, and
`head`, `addons` and `last_success` in `status.json` keep their last good values.
