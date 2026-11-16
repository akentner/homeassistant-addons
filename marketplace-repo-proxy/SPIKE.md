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
  installed add-ons lose their store entry and have to be reinstalled. See [Hash scheme](#hash-scheme).
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
`ls-remote` OK. Image grows by about 18 MB (git is most of it), lighttpd uses about 3 MB RSS.

```lighttpd
server.modules = ("mod_alias", "mod_setenv", "mod_cgi")
# Empty docroot: anything not routed below is a plain 404 (no listing, no static files)
server.document-root = "/var/empty"
server.port = 8080
server.username = "lighttpd"
server.groupname = "lighttpd"
# Allow-list: only the smart-HTTP read endpoints of /r/<32 hex>.git are mapped to git http-backend
$HTTP["url"] =~ "^/r/[0-9a-f]{32}\.git/(info/refs|git-upload-pack)$" {
  alias.url = ("/r/" => "/usr/libexec/git-core/git-http-backend/")
}
cgi.assign = ("" => "")
setenv.set-environment = ("GIT_PROJECT_ROOT" => "/srv/git/r", "GIT_HTTP_EXPORT_ALL" => "1")
```

Observed responses: `info/refs?service=git-upload-pack` 200, `/r/`, `HEAD`, `config`, `objects/info/packs`, the CGI
binary path and unknown hashes 404, `git-receive-pack` 403.

Pitfall found: a negated `url.access-deny` block does not work, because lighttpd re-evaluates conditions after splitting
`PATH_INFO` (the URL becomes `/r`) and denies everything. Map the alias only inside the positive condition.

Alternatives considered:

| Option                          | Verdict                                                                                                                                                  |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Static dumb HTTP                | Ruled out, no shallow support                                                                                                                            |
| `git daemon` (`git://`, 9418)   | Works locally with `--depth 1` and passes URL validation. Fallback if lighttpd causes pain; less common, no HTTP status codes, can never get auth or TLS |
| nginx + fcgiwrap + http-backend | Works in general, but two daemons and more config than lighttpd for the same result                                                                      |
| Custom service                  | Needs Python or another runtime on top of the base image. Not worth it                                                                                   |

### Hash scheme

- **Random 128-bit token per source repository**, generated once (`/dev/urandom` → 32 lowercase hex chars), persisted in
  `/data/tokens.json` keyed by the source repository URL plus branch. Lowercase hex matters: the Supervisor lower-cases
  the URL for its own hash.
- Prefer random over HMAC-derived: HMAC also needs a persisted secret, so it adds nothing and couples the URL to config
  edits.
- **Rotation is expensive**, because the URL is the repository identity in the Supervisor: new URL = new repository hash
  = installed add-ons must be reinstalled (back up their data first). So rotation is an emergency action, not a
  schedule: an explicit per-repository option (for example `rotate: true`, consumed once and logged) plus a DOCS.md
  procedure. The old URL stops working right away.
- The hostname is part of the URL too: `local-marketplace-repo-proxy` (local install) and
  `72a005f5-marketplace-repo-proxy` (installed from this repository) give different store repositories. Pick one install
  source and keep it.
- Backups of the proxy add-on include `/data` (default), so a restore keeps the tokens and therefore the URLs.

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
3. lighttpd routes only `info/refs` and `git-upload-pack`; everything else is 404 from an empty docroot.
4. `git http-backend` refuses `receive-pack` without `REMOTE_USER` (verified 403); also set `http.receivepack=false` and
   `http.getanyfile=false` (no dumb file access) in each bare repository.
5. lighttpd runs as `lighttpd`; repositories are owned by root and only readable for it. That needs
   `safe.directory = /srv/git/r/*` in `/etc/gitconfig`, otherwise git refuses with "dubious ownership" (seen in the
   spike).
6. No published port by default (`8080/tcp: null`). Every add-on on the `hassio` network can reach the proxy, so the
   hash is the only secret: log the full store URL once at startup at `info`, never the token.

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
