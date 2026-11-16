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
`lxc-haos-104` (see [Decisions](#decisions)).

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

- `<owner>/<repo>` is the GitHub repository (decided: `<base>` = owner/organisation). Owner and repo names are not
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
  reload. The symlink set is rebuilt from `/data/access.json` at every start, so a stray symlink cannot survive.

- **Query parameters**: git appends its endpoint after the query string
  (`GET /repo/o/r/<hash>?ref=main/info/refs&service=git-upload-pack`, `POST …?ref=main/git-upload-pack`), so a server
  without special handling returns 404. The `url.rewrite-once` rules above normalise both forms; the parameters are
  accepted and **ignored** (decided: no parameter carries meaning). The branch for the Supervisor stays `#<branch>` (the
  Supervisor strips the fragment before calling git). Note: the query is part of the Supervisor's repository identity,
  so a store URL with different parameters is a different store repository.
- **Rotation is expensive**, because the URL is the repository identity in the Supervisor: new URL = new repository hash
  = that user's installed add-ons must be reinstalled (back up their data first). With one token per user, rotation only
  hits that one user. Mechanism: "Rotate" on the management page (type-to-confirm, with a reinstall warning) plus a
  DOCS.md procedure; the old URL stops working right away.
- The host is part of the URL too: `local-marketplace-repo-proxy` (local install), `72a005f5-marketplace-repo-proxy`
  (installed from this repository) and the public domain give different store repositories. Pick one per HA instance and
  keep it.
- Backups of the proxy add-on include `/data` (default), so a restore keeps the tokens and therefore the URLs.
- Logging: never log the hash. lighttpd's access log goes to a pipe (`accesslog.filename = "|<sink>"`); the sink maps
  the hash to the user label, records "last fetch" per user for the management page and logs only
  `fetch: <user> → <owner>/<repo>`. Not tested in the spike.

Options sketch: the options hold only what the sync needs. Users and their hashes live on the
[management page](#management-page-ingress) and in `/data/access.json`, so adding or revoking a user needs no restart
and no hash ever appears in the add-on options.

```yaml
github_token: "github_pat_…" # password
sync_interval: 15
public_url: "" # e.g. https://addons.example.com, empty = internal only
repositories:
  - repository: akentner/private-addons
    branch: main
```

### Public exposure

Optional publication on a public domain, off by default. **Decided: TLS terminates at a reverse proxy.**

- **TLS is mandatory and must use a publicly trusted certificate.** The cloning party is another HA instance's
  Supervisor; it uses the system CA bundle and has no way to trust a self-signed certificate or skip verification. A
  plain `http://` URL over the internet would also leak the hash.
- **The reverse proxy terminates TLS** (Traefik add-on or Cloudflare Tunnel, both running on `haos-op3050-1`). They sit
  on the `hassio` network and reach `<prefix>-marketplace-repo-proxy:8080` without publishing the port. The add-on
  itself stays plain HTTP and only needs `public_url` to print the public store URLs.
- No TLS inside the add-on (`ssl`/`certfile`/`keyfile`). The git port stays unpublished by default; publishing it
  remains possible for LAN or Tailscale use over plain HTTP.
- Proxy-side settings: no caching of `/repo/*` (CDN caching would serve stale refs or other users' responses), request
  body limit high enough for `git-upload-pack` POSTs, no access logs with full paths (they contain the hash), optional
  rate limit on 404s. With 128-bit tokens brute force is not a practical risk; leaked URLs are.
- Bandwidth is small: each consuming Supervisor does a shallow fetch every 3 hours.
- **Not verified yet**: a clone through Traefik/Cloudflare. Smart HTTP over HTTPS reverse proxies is standard (GitHub,
  Gitea), so the risk is low; test it with the first implementation.

### Management page (Ingress)

A GUI behind HA ingress lists the published repositories and manages users and hashes. It follows the admin-ui blueprint
(`admin-ui/DOCS.md`, rules R-01 to R-15): Python stdlib server skeleton and Preact lib, copied in by
`make sync-admin-ui ADDON=marketplace-repo-proxy` and never edited by hand.

- **Two servers, two ports.** lighttpd serves git on `8080` (unpublished by default, reached by Supervisors and the
  reverse proxy). The GUI runs on the ingress port (`ingress: true`, `ingress_port: 8099`), never published. The
  blueprint's ingress gate (R-01: peer `172.30.32.2` plus `X-Ingress-Path`) rejects everything else, so git traffic
  cannot run through the GUI server, and does not need to.
- **Image**: `apk add python3` on top of git and lighttpd; the blueprint uses the same `amd64-base:3.24`.
- **Process separation** (s6 services): `sync` is the only process with the GitHub token; `lighttpd` and `gui` never see
  it. The GUI reads sync state from `/data/status.json`, requests a sync through a trigger file the sync loop watches,
  and creates or removes the access symlinks itself.
- **Source of truth**: repositories and the token in the add-on options (they need a restart anyway), users and hashes
  in `/data/access.json`, written only by the GUI.

| View         | Content                                                                                                                                                  | Actions                                                                                         |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Repositories | `owner/repo`, branch, last sync (relative), HEAD short SHA, add-ons found in the mirror, status (`ok`, `auth_failed`, `not_found`, `no_repository_yaml`) | Sync now                                                                                        |
| Access       | Per repository: user label, created, last fetch, store URLs internal and public (`CopyField`)                                                            | Add user (generates a hash); revoke and rotate, both type-to-confirm with the user label (R-04) |
| Info         | Setup steps: add the URL in the store, reverse proxy notes, rotation procedure                                                                           | none                                                                                            |

- The page sits behind HA login and ingress, so it may show full store URLs. They are rendered as text only (R-03) and
  never logged.
- API errors use stable codes (R-14), for example `repository_unknown`, `user_exists`, `confirmation_required`.
- Rotate shows the consequence before confirming: the user's Supervisor sees a new repository and must reinstall the
  add-ons from it.

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
7. Per-user tokens: a leaked URL is revoked on the management page, without touching other users.
8. The management page is reachable only through ingress (blueprint gate R-01); its port is never published.

### Known limitations

- **HACS cannot use this**: HACS talks to the GitHub API, not to git. Scope the add-on to the add-on store.
- **Private submodules** fail: the Supervisor clones submodules recursively from their own URLs.
- **Private images** (`image:` on private GHCR) need registry credentials on the host
  (`ha docker registries add ghcr.io ...`), or public images, or local builds. Stays a non-goal.

## Decisions

Decided by the user (2026-11-17):

- Public exposure through a reverse proxy that terminates TLS; no TLS in the add-on.
- `<base>` in `/repo/<base>/<repo>/<hash>` is the GitHub owner/organisation.
- Query parameters on the store URL are accepted and ignored.
- A management page behind ingress shows the published repositories and their users/hashes.

Still open:

1. **Supervisor API role**: give the add-on `hassio_role: manager` for self-registration and `store/reload` after sync
   (faster updates, but a broad API role and a lower security rating), or stay without API access (manual "add
   repository", up to 3 h update lag)? Recommendation: without for v1, add later if the lag hurts.
2. **Server**: lighttpd + `git http-backend` (recommended, all tests above) or `git daemon` (`git://` URL, does not fit
   the `https://` reverse proxy)?
3. **Install source**: install the proxy from this repository (`72a005f5-…` hostname, CI image) or as a local add-on
   (`local-…`)? It fixes the internal store URLs for good.
4. **End-to-end test host**: run the real store add → install → update test on `lxc-haos-104` (preferred) or on
   `haos-op3050-1` (adds and later removes one store repository)?
5. **Credential**: one fine-grained PAT for v1 (recommended), or deploy keys per repository from the start?
6. **Where users live**: managed on the page and stored in `/data/access.json` (recommended: no restart, no hashes in
   the options), or declared in the add-on options with a read-only page (config as code, restart per change)?
