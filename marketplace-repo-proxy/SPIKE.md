# Spike: Supervisor and a local git proxy

Date: 2026-11-16. Supervisor `2026.11.0` (source at `home-assistant/supervisor@e610ca8`), git 2.54, GitPython 3.2.1.
Answers open questions 1, 2, 4, 5 and 6 of [GOAL.md](GOAL.md).

## Result

**The biggest risk is gone.** The Supervisor accepts a plain `http://` URL with an add-on hostname as a store repository
and clones it from inside the `hassio` network, as long as the server speaks **smart HTTP**. A static dumb-HTTP server
does **not** work.

| Question                                    | Answer                                                                 | Evidence          |
| ------------------------------------------- | ---------------------------------------------------------------------- | ----------------- |
| `http://` accepted?                         | Yes. Any URL with scheme and host passes, plus optional `#branch`      | Source + live run |
| Add-on hostname resolvable from Supervisor? | Yes, via the `hassio` DNS (`172.30.32.3`)                              | Live run          |
| Unpublished add-on port reachable?          | Yes, the `hassio` bridge allows container-to-container traffic         | Live run          |
| Dumb HTTP (`git update-server-info`)?       | **No.** Supervisor always clones `--depth 1`; dumb HTTP has no shallow | Local run         |
| Smart HTTP (`git-upload-pack`)?             | Yes: clone `--depth 1`, `ls-remote --heads`, `fetch --update-shallow`  | Live run          |
| Wrong hash?                                 | Clean `repository not found` (404), nothing listed                     | Live + local run  |
| Push through the proxy?                     | Refused (403, `receive-pack` disabled)                                 | Local run         |
| HACS?                                       | **Not solvable here.** HACS reads repositories via the GitHub API      | Known HACS design |

## Supervisor source findings

- **URL validation** (`supervisor/store/validate.py:validate_repository`, `supervisor/validate.py:RE_REPOSITORY`):
  `^(?P<url>[^#\s]+)(?:#(?P<branch>[\w\-./]+))?$`, then `voluptuous.Url()`, which only requires a scheme and a netloc
  (`urlparse`). `http://`, `https://`, `git://`, `ssh://` and IP literals all pass. Scp-style `git@host:path` does not.
  There is no scheme allow-list and no GitHub check.
- **Clone** (`supervisor/store/git.py:GitRepo._clone`):
  `git.Repo.clone_from(url, path, recursive=True, depth=1, shallow-submodules=True[, branch=<#branch>])`. Shallow is
  unconditional, which rules out dumb HTTP (`fatal: dumb http transport does not support shallow capabilities`,
  reproduced locally).
- **Update** (`GitRepo.pull`): `git ls-remote --heads <url>`, then `fetch --update-shallow --depth 1`,
  `reset --hard origin/<branch>`, `submodule update --init --recursive --depth 1`, `clean -xdf`.
- **Validity** (`store/repository.py:RepositoryGit.validate`): `repository.yaml|yml|json` at the root with `name`
  (required), `url`, `maintainer`.
- **Repository identity** (`store/utils.py:get_hash_from_repository`): `sha1(url.lower())[:8]`. This hash is the prefix
  of every add-on slug from that repository (`<hash>_<slug>`). **Changing the URL makes it a different repository**:
  installed add-ons lose their store entry and have to be reinstalled. See
  [URL scheme and access tokens](#url-scheme-and-access-tokens).
- **Refresh cadence** (`misc/tasks.py`): `RUN_RELOAD_APPS = 10800`, so the Supervisor pulls all store repositories every
  3 hours, plus on "Check for updates" in the UI and on `ha store reload`.
- **Boot**: existing repositories load from disk without network (`GitRepo.load` only clones when the folder is
  missing), so the proxy starting after the Supervisor is harmless. A first clone (fresh install, restore without the
  store folder) while the proxy is down raises a resolution issue (`FATAL_ERROR`, suggestion "remove").
- **Jobs**: clone and pull require `JobCondition.INTERNET_SYSTEM`. If the Supervisor thinks it is offline it skips the
  refresh, even though the proxy is local. Acceptable.
- **API role** (`api/middleware/security.py`): `/store.*` needs `hassio_role: manager`. With it the proxy could register
  itself (`POST /store/repositories`) and trigger `POST /store/reload` after a sync.

## Live verification on `haos-op3050-1`

Read-only for production state: no store entry added, no add-on installed or restarted.

1. Temporary smart-HTTP server (Python stdlib wrapper around `git upload-pack --stateless-rpc`, protocol v0) started in
   the SSH add-on (host network), bound to `172.30.32.1:18778` only, `timeout 600`. Test repository with
   `repository.yaml` and one add-on under `/r/<32 hex>.git`.
2. Inside `hassio_supervisor`, with the Supervisor's own Python modules:
   `supervisor.store.validate.validate_repository()` for `http://a0d7b954-ssh:18778/r/<hash>.git` and the IP variant,
   with and without `#main` → valid. `git.Repo.clone_from()` with the same kwargs as `_clone` → OK, checkout contains
   `repository.yaml`. `ls-remote --heads` → OK. `fetch --update-shallow --depth 1` → OK. Wrong hash →
   `remote: not found`.
3. DNS from the Supervisor container: bridged add-ons resolve (`72a005f5-ntfy` → `172.30.33.16`, `core-mariadb` →
   `172.30.33.0`), host-network add-ons resolve to `172.30.32.1`. TCP to the **unpublished** ingress port `8099` of
   `72a005f5-ntfy` connects.
4. Cleanup: server stopped, temp repositories in the SSH add-on and `/data/tmp/mrp-spike-*` in the Supervisor removed.

Side note: git inside the Supervisor container gets `Permission denied` when cloning into `/tmp`; the Supervisor itself
uses `/data/tmp` and `/data/addons/git`. No impact on the proxy.

Not yet tested end to end: the real `ha store repositories add <url>` → install → update cycle. It runs the same
validation and clone code tested above, so the remaining risk is low. Do it with the first implementation, preferably on
`lxc-haos-104` (see [Decisions for the user](#decisions-for-the-user)).

## Recommendation

### Server: lighttpd + `git http-backend` (smart HTTP)

Verified locally on `ghcr.io/home-assistant/amd64-base:3.24` with `apk add git lighttpd`: clone `--depth 1`, fetch,
`ls-remote` OK, with the URL scheme from [URL scheme and access tokens](#url-scheme-and-access-tokens). Image grows by
about 18 MB (git is most of it), lighttpd uses about 3 MB RSS.

```lighttpd
server.modules = ("mod_rewrite", "mod_alias", "mod_setenv", "mod_cgi")
# Empty docroot: anything not routed below is a plain 404 (no listing, no static files)
server.document-root = "/var/empty"
server.port = 8080
server.username = "lighttpd"
server.groupname = "lighttpd"
# git appends its endpoint after an existing query string (".../<hash>?ref=x/info/refs&service=..."),
# so normalise that form back to the plain smart-HTTP paths; the client query is dropped here.
url.rewrite-once = (
  "^(/repo/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/[0-9a-f]{32})\?.*/info/refs&service=git-upload-pack$"
    => "$1/info/refs?service=git-upload-pack",
  "^(/repo/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/[0-9a-f]{32})\?.*/git-upload-pack$" => "$1/git-upload-pack"
)
# Allow-list: only the smart-HTTP read endpoints are mapped to git http-backend
$HTTP["url"] =~ "^/repo/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/[0-9a-f]{32}/(info/refs|git-upload-pack)$" {
  alias.url = ("/repo/" => "/usr/libexec/git-core/git-http-backend/")
}
cgi.assign = ("" => "")
setenv.set-environment = ("GIT_PROJECT_ROOT" => "/srv/git/access", "GIT_HTTP_EXPORT_ALL" => "1")
```

Observed responses (local, two access tokens on one repository):

| Request                                                         | Status                                |
| --------------------------------------------------------------- | ------------------------------------- |
| `/repo/<owner>/<repo>/<hash>/info/refs?service=git-upload-pack` | 200                                   |
| Same with `?ref=main&tab=readme` appended to the store URL      | 200 (clone, fetch, `ls-remote` OK)    |
| Second token of the same repository                             | 200                                   |
| Second token after deleting its symlink                         | 404, effective immediately, no reload |
| Unknown hash, or valid hash under another `<repo>`              | 404                                   |
| `/repo/`, `/repo/<owner>/<repo>/`, `<hash>/HEAD`                | 404                                   |
| `<hash>/info/refs` without `service` (dumb HTTP)                | 403 (`http.getanyfile=false`)         |
| `<hash>/info/refs?service=git-receive-pack`, `git push`         | 403                                   |

Pitfall found: a negated `url.access-deny` block does not work, because lighttpd re-evaluates conditions after splitting
`PATH_INFO` (the URL becomes `/repo`) and denies everything. Map the alias only inside the positive condition.

Alternatives considered:

| Option                          | Verdict                                                                                                                                                  |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Static dumb HTTP                | Ruled out, no shallow support                                                                                                                            |
| `git daemon` (`git://`, 9418)   | Works locally with `--depth 1` and passes URL validation. Fallback if lighttpd causes pain; less common, no HTTP status codes, can never get auth or TLS |
| nginx + fcgiwrap + http-backend | Works in general, but two daemons and more config than lighttpd for the same result                                                                      |
| Custom service                  | Needs Python or another runtime on top of the base image. Not worth it                                                                                   |

### URL scheme and access tokens

Store URL, modelled on GitHub paths:

```text
<scheme>://<host>[:<port>]/repo/<owner>/<repo>/<hash>[?<query>][#<branch>]
http://72a005f5-marketplace-repo-proxy:8080/repo/akentner/private-addons/3f9c…e1      # internal
https://addons.example.com/repo/akentner/private-addons/7a02…4b                        # public
```

- `<owner>/<repo>` is the GitHub repository (assumption: `<base>` = owner/organisation). Owner and repo names are not
  secret; the hash is. Unknown owner, repo or hash all give the same 404, so names cannot be enumerated.
- **Several hashes per repository, one per user (access token).** Each token is a random 128-bit value (`/dev/urandom` →
  32 lowercase hex chars), generated once and persisted in `/data/access.json` keyed by `(repository, user label)`.
  Random beats HMAC-derived: HMAC also needs a persisted secret and adds nothing.
- **Disk layout** (tested): one bare repository per source, one symlink per token:

  ```text
  /srv/git/repos/<owner>/<repo>.git                     # bare mirror, written only by the sync service
  /srv/git/access/<owner>/<repo>/<hash> -> /srv/git/repos/<owner>/<repo>.git
  ```

  `GIT_PROJECT_ROOT=/srv/git/access`. Revoking a user removes the symlink; the next request gets a 404 without a server
  reload. The symlink set is rebuilt from the options at every start, so a user removed from the options is revoked.

- **Query parameters**: git appends its endpoint after the query string
  (`GET /repo/o/r/<hash>?ref=main/info/refs&service=git-upload-pack`, `POST …?ref=main/git-upload-pack`), so a server
  without special handling returns 404. The `url.rewrite-once` rules above normalise both forms; the parameters are
  accepted and **ignored**. The branch for the Supervisor stays `#<branch>` (the Supervisor strips the fragment before
  calling git). Note: the query is part of the Supervisor's repository identity, so a store URL with different
  parameters is a different store repository. Which parameters should mean something is an open decision.
- **Rotation is expensive**, because the URL is the repository identity in the Supervisor: new URL = new repository hash
  = that user's installed add-ons must be reinstalled (back up their data first). With one token per user, rotation only
  hits that one user. Mechanism: per-token option (for example `rotate: true`, consumed once and logged) plus a DOCS.md
  procedure; the old URL stops working right away.
- The host is part of the URL too: `local-marketplace-repo-proxy` (local install), `72a005f5-marketplace-repo-proxy`
  (installed from this repository) and the public domain give different store repositories. Pick one per HA instance and
  keep it.
- Backups of the proxy add-on include `/data` (default), so a restore keeps the tokens and therefore the URLs.
- Logging: map the hash back to the user label (`access granted: alice → akentner/private-addons`), never log the hash
  itself after the one-time startup listing; keep lighttpd's access log off (it would log full paths).

Options sketch (flat list of dicts; HA's options schema is safest without nested lists inside list items):

```yaml
github_token: "github_pat_…" # password
sync_interval: 15
public_url: "" # e.g. https://addons.example.com, empty = internal only
repositories:
  - repository: akentner/private-addons
    branch: main
access:
  - repository: akentner/private-addons
    user: home
  - repository: akentner/private-addons
    user: friend-1
```

### Public exposure

Optional publication on a public domain, off by default.

- **TLS is mandatory and must use a publicly trusted certificate.** The cloning party is another HA instance's
  Supervisor; it uses the system CA bundle and has no way to trust a self-signed certificate or skip verification. A
  plain `http://` URL over the internet would also leak the hash.
- **Recommended: terminate TLS at an existing reverse proxy** (Traefik add-on or Cloudflare Tunnel, both running on
  `haos-op3050-1`). They sit on the `hassio` network and reach `<prefix>-marketplace-repo-proxy:8080` without publishing
  the port. The add-on itself stays plain HTTP and only needs `public_url` to print the public store URLs.
- **Alternative: direct TLS in the add-on** (`ssl`, `certfile`, `keyfile` in `/ssl`, the usual HA convention, lighttpd
  `mod_openssl`) behind a published port. Only useful without a reverse proxy; needs a certificate for the domain.
- Proxy-side settings: no caching of `/repo/*` (CDN caching would serve stale refs or other users' responses), request
  body limit high enough for `git-upload-pack` POSTs, no access logs with full paths (they contain the hash), optional
  rate limit on 404s. With 128-bit tokens brute force is not a practical risk; leaked URLs are.
- Bandwidth is small: each consuming Supervisor does a shallow fetch every 3 hours.
- **Not verified yet**: a clone through Traefik/Cloudflare. Smart HTTP over HTTPS reverse proxies is standard (GitHub,
  Gitea), so the risk is low; test it with the first implementation.

### Upstream authentication

- **v1: one fine-grained PAT** with `Contents: read-only` on the selected repositories, stored as a `password` option
  (`github_token`). One secret covers many repositories, no SSH client or `known_hosts` handling needed.
- Pass it only at fetch time and only via the environment: `GIT_CONFIG_COUNT=1`, `GIT_CONFIG_KEY_0=http.extraHeader`,
  `GIT_CONFIG_VALUE_0="Authorization: Basic base64(x-access-token:<token>)"`. Never in the remote URL or in the
  repository config, never in lighttpd's environment.
- Log a clear error on 401/403 (expired or revoked token). Token lifetime depends on the account/organisation policy.
- Later, optional: per-repository deploy key (read-only by GitHub design, no expiry) via `openssh-client` and a pinned
  `github.com` host key.

### Sync

- Bare repository per source, created with `git init --bare` plus an explicit fetch refspec. **Not**
  `git clone --mirror`: that sets `remote.origin.mirror=true`, which would make a stray `git push` mirror everything
  upstream.
- Fetch only what the store needs: `+refs/heads/<branch>:refs/heads/<branch>` (configured branch, default: upstream
  default branch) and set `HEAD` to it. No `refs/pull/*`, no other branches unless configured.
- `git fetch --prune` updates refs only after the objects are in place, so a concurrent `upload-pack` always sees a
  consistent state.
- **Interval: 15 minutes default, minimum 5** (`sync_interval` option). The Supervisor only looks every 3 hours anyway,
  so a shorter interval only helps manual "Check for updates".
- Manual trigger: `stdin: true` plus `hassio.addon_stdin` with `sync` (no extra port, no webhook). Webhooks are out:
  they need an inbound path, which contradicts "internal only".
- Optional fast path (needs `hassio_role: manager`): after a sync that changed refs, call `POST /store/reload` so
  updates show up within minutes instead of up to 3 hours.
- Run the sync loop as a separate s6 service from lighttpd, so the token never reaches the HTTP server's process tree.

### Read-only guarantees (defence in depth)

1. Upstream token has `Contents: read-only`; the proxy cannot write upstream even if compromised.
2. No push configuration in the bare repositories (`git init --bare`, fetch refspec only, `remote.origin.pushurl` set to
   an invalid value).
3. lighttpd routes only `info/refs` and `git-upload-pack` under `/repo/<owner>/<repo>/<hash>/`; everything else is 404
   from an empty docroot.
4. `git http-backend` refuses `receive-pack` without `REMOTE_USER` (verified 403); also set `http.receivepack=false` and
   `http.getanyfile=false` (no dumb file access) in each bare repository.
5. lighttpd runs as `lighttpd`; repositories are owned by root and only readable for it. That needs `safe.directory` for
   `/srv/git/repos/*` in `/etc/gitconfig`, otherwise git refuses with "dubious ownership" (seen in the spike).
6. No published port by default (`8080/tcp: null`). Every add-on on the `hassio` network can reach the proxy, so the
   hash is the only secret: log the store URLs once at startup at `info`, never the GitHub token.
7. Per-user tokens: a leaked URL is revoked by removing one `access` entry, without touching other users.

### Known limitations

- **HACS cannot use this**: HACS talks to the GitHub API, not to git. Scope the add-on to the add-on store.
- **Private submodules** fail: the Supervisor clones submodules recursively from their own URLs.
- **Private images** (`image:` on private GHCR) need registry credentials on the host
  (`ha docker registries add ghcr.io ...`), or public images, or local builds. Stays a non-goal.

## Decisions for the user

1. **Supervisor API role**: give the add-on `hassio_role: manager` for self-registration and `store/reload` after sync
   (faster updates, but a broad API role and a lower security rating), or stay without API access (manual "add
   repository", up to 3 h update lag)? Recommendation: without for v1, add later if the lag hurts.
2. **Server**: lighttpd + `git http-backend` (recommended) or `git daemon` (smaller config, `git://` URL)?
3. **Install source**: install the proxy from this repository (`72a005f5-…` hostname, CI image) or as a local add-on
   (`local-…`)? It fixes the store URL for good.
4. **End-to-end test host**: run the real store add → install → update test on `lxc-haos-104` (preferred) or on
   `haos-op3050-1` (adds and later removes one store repository)?
5. **Credential**: one fine-grained PAT for v1 (recommended), or deploy keys per repository from the start?
6. **Query parameters**: which GitHub-style parameters should have a meaning? Accepted and ignored is implemented in the
   spike; a meaningful `ref`/`branch` would duplicate the Supervisor's `#branch` and needs a separate repository view
   per ref.
7. **Public TLS**: reverse proxy (Traefik/Cloudflare Tunnel, recommended) or TLS inside the add-on?
8. **`<base>`**: GitHub owner/organisation (assumed), or a free namespace per proxy?
