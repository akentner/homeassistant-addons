# Spike: ntfy image, add-on conventions, Dockerfile, options schema

Worker spike for Phase 24 (decisions D-01..D-17 locked). Date: 2026-11-01. Container `ntfy-spike-image`, port 18083,
scratch dir `/tmp/akentner/ntfy-spike-image` (nothing created inside the repo except this file).
Legend: **[V]** verified by a command run here, **[A]** assumption / not run.

## 1. What a new add-on `ntfy/` must satisfy

### Files (derived from `secrets-sync/`, `haos-monitor/` (own-code, ingress GUI), `gatus/`, `litellm/`)

| File                      | Required by                                                           | Notes                                                                                                                                   |
| ------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `config.yaml`             | `make validate-addons`, CI detect, `validate-addon-config.py`         | see keys below                                                                                                                          |
| `build.yaml`              | CI detect (triple `config.yaml`+`build.yaml`+`Dockerfile`), versions  | `build_from.amd64` + `args.VERSION` (X.Y.Z, no subpatch)                                                                                |
| `Dockerfile`              | CI detect, hadolint, ARG-before-FROM check                            | CI passes `BUILD_FROM`, `VERSION`, `BUILD_VERSION` etc. as build args                                                                   |
| `run.sh`                  | `make validate-addons` (required file)                                | executable, shebang (pre-commit `check-shebang-scripts-are-executable`)                                                                 |
| `README.md`               | `validate-versions.sh`, `update-version.py`                           | must carry `[release-shield]: https://img.shields.io/badge/version-vX.Y.Z-blue.svg` and `[release]: .../tree/vX.Y.Z` (copy gatus style) |
| `DOCS.md`                 | convention (CLAUDE.md structure list)                                 | option reference                                                                                                                        |
| `CHANGELOG.md`            | convention; shown in HA UI                                            | for own-code add-ons hand-written (haos-monitor/secrets-sync); `auto-update.yml` prepends upstream release notes only if file exists    |
| `icon.png`, `logo.png`    | convention (all add-ons have them)                                    | HA store icon 1:1 / logo; not CI-enforced **[A]**. litellm uses `icon: true` in config                                                  |
| `translations/en.yaml`    | convention (secrets-sync, haos-monitor)                               | `configuration.<opt>.name/description`; also `de.yaml` (user is German)                                                                 |
| `.upstream.yaml`          | `auto-update.yml` (find `.upstream.yaml` maxdepth 2)                  | see below                                                                                                                               |
| `app/` (GUI), `tests/`    | D-16                                                                  | `.dockerignore` excludes `tests/`, `docs/` like secrets-sync                                                                            |

### `config.yaml` keys (**[V]** against `internal/validate-addon-config.py`)

- Required by validator: `name, version, slug, description, arch, startup, boot`. `arch` subset of
  `aarch64|amd64|armhf|armv7|i386`; `startup` in `application|initialize|system|once|services`; `boot` in
  `auto|manual|manual_only`; `ports` values int or null; `map` entries need valid `type` (`addon_config`, `data`, ...).
- Repo pattern: `version: "X.Y.Z-N"`, `init: false`, `image: "ghcr.io/akentner/homeassistant-addons/{arch}-ntfy"`
  (CI slug = dir name with `-` to `_`, `_build-template.yml:114-117`; `ntfy` has no dash so image = `{arch}-ntfy`),
  `url`, `startup: "application"`, `boot: "auto"`, `ingress: true`, `ingress_port: 8099`, `panel_icon`,
  `panel_title`, `panel_admin: true`.
- Per D-10: `host_network: true` (listen_port default 8000 is bound on the host). With `host_network: true` the
  Supervisor ignores `ports:`; do not declare ingress port 8099 in `ports` then (haos-monitor/secrets-sync expose
  8099 via `ports: 8099/tcp: null`, not useful under host network). **[A]** (Supervisor behaviour, not tested).
- **Port collision risk**: with `host_network: true` the ingress port 8099 is also bound on the host network
  namespace; fine as long as nothing else on the HAOS host uses 8099 (no other add-on uses host_network + 8099 in
  this repo **[A]**). Bind the GUI to `0.0.0.0:8099` (Supervisor reaches ingress via host IP `172.30.32.2` -> add-on
  with host_network connects to host address; the secrets-sync gate checks the peer `172.30.32.2`) **[A]**; verify
  on a real HAOS in Phase 24 UAT.
- `map`: `addon_config:rw` is optional (only if users want to drop a raw `server.yml` snippet); `/data` is always
  there and holds `auth.db`, `cache.db`, `backups/`, sidecar file.
- Health check: optional `watchdog`/`health_check` like litellm; ntfy has `GET /v1/health` -> `{"healthy":true}` **[V]**.

### Versioning (3-file scheme) **[V]** read from `update-version.py`, `validate-versions.sh`

- `config.yaml` `X.Y.Z-N`, `build.yaml` `args.VERSION` `X.Y.Z`, README `[release-shield]` + `[release]` with `vX.Y.Z`.
  Create the add-on with all three consistent (`2.36.0-0` / `2.36.0` / `v2.36.0`); afterwards only
  `make update-version ADDON=ntfy VERSION=...`. Note `validate-versions.sh` greps `^[[:space:]]*VERSION:`, so any
  second build arg must not be called `VERSION` (e.g. `NTFY_SHA256`, not `..._VERSION` collisions are fine).
- Upstream tag is `v2.36.0` (latest release **[V]** `gh release view`) so `version_strip: "^v"` works.
- Caveat: the GUI is our own code, so a GUI-only change needs a subpatch bump (`2.36.0-1`) via `make update-version`;
  an upstream bump resets to `-0` (same as litellm/gatus). Document in CHANGELOG.

### `.upstream.yaml` (copy of gatus/litellm) **[V]** format

```yaml
upstream:
  repository: "binwiederhier/ntfy"
  version_pattern: "v*"
  version_strip: "^v"
addon:
  version_pattern: "sync"
```

`auto-update.yml` (daily 06:00 UTC) reads these three keys via `yq`, bumps the 3 files, prepends the release body to
`CHANGELOG.md` and runs `prettier` on it (so ntfy release-note formatting must survive prettier/markdownlint; same as
gatus, which shows long `@user` lines wrapped by prettier).

### Other registration points (grep for `secrets-sync` outside its dir **[V]**)

- Root `README.md`: add a `### [ntfy](./ntfy)` section (list at lines 19..209, header + shield + features).
- `internal/base-image-config.yaml`: add `ntfy:` block identical to `gatus:` (image `ghcr.io/home-assistant/amd64-base`,
  `source_repo: home-assistant/docker-base`, `source_file: alpine/Dockerfile`, `ARG ALPINE_VERSION=...`). Without it the
  base-image bump workflow ignores ntfy and `build.yaml` pins drift. (`base-image-update.yml` iterates this file.)
- `.github/renovate.json`: only needed for extra pinned deps (secrets-sync has `BW_CLI_VERSION`); not needed for ntfy
  because upstream tracking is `.upstream.yaml`.
- Optional: `internal/verify-ntfy-scaffold.sh` in the style of `verify-secrets-sync-scaffold.sh` (structure check) and
  a secret-leak test like `verify-secrets-sync-no-secret-leak.sh`. Per repo notes, do not run docker verify scripts
  in two worktrees at once.
- CI: `build.yml` needs no edit. `detect` auto-discovers any dir with the manifest triple and builds legs for
  `amd64`/`aarch64` found in `build.yaml` `build_from` keys (SUPPORTED_ARCHS in build.yml). It fails if `name:` or
  `description:` is missing. `verify-image-availability.yml` then expects the pullable image tag
  `ghcr.io/akentner/homeassistant-addons/amd64-ntfy:<config version>` for every add-on with `image:`; merging a
  config without a built image breaks install, so the first merge must be followed by a green build.

### CI / lint checks that apply **[V]** from `.pre-commit-config.yaml`, `.yamllint.yml`, `Makefile`, validators

- yamllint (relaxed; 120 cols = warning; 2-space indent; no `---`; max 1 blank line at EOF).
- trailing-whitespace, end-of-file-fixer, check-yaml `--unsafe`, shebang/executable checks, mixed-line-ending LF.
- shellcheck `-e SC1091 -e SC2034` for `run.sh` (use `# shellcheck shell=bash` after the `with-contenv bashio`
  shebang as secrets-sync does).
- prettier + markdownlint-cli2 (120 col, ATX headings) on README/DOCS/CHANGELOG; actionlint n/a.
- gitleaks on staged diff (no real tokens in docs/tests; use obvious dummy values).
- check-added-large-files 1000 KB: the vendored Preact/htm file is ~10 KB; fine. Do **not** commit the ntfy binary.
- hadolint pre-commit ignores `DL3008, DL3018, DL3059, DL4006, DL3016`; `make docker-build-check` ignores
  `DL3018, DL3059, DL4006, DL3016` (stricter: DL3008 and DL3006 active). My Dockerfile passes the stricter set
  **[V]** (exit 0) after replacing `cd /tmp` by absolute paths (DL3003 was triggered by `cd` in RUN).
- `internal/validate-dockerfile-args.sh` (ARG-before-FROM): **[V]** passes for the skeleton below; it only inspects
  `FROM` lines after the first one, so with a single `FROM ${BUILD_FROM}` plus the global `ARG BUILD_FROM=` it is
  trivially satisfied. If a multi-stage build is used, every ARG referenced in a later FROM (e.g.
  `FROM binwiederhier/ntfy:v${VERSION}`) must be declared before the first FROM (gatus does exactly this).
- `make validate-versions`, `validate-addons` (needs `config.yaml`, `Dockerfile`, `run.sh`, `name:`), and
  `validate-addon-config.py` **[V]** pass for the draft config in section 4.
- CLAUDE.md rules: local `docker build` before committing the Dockerfile **[V done here]**; stage by path
  (`git add ntfy/ ...`); no `Co-Authored-By`; GSD docs only in main worktree (STATE/ROADMAP).

### Base image tag used by the other add-ons **[V]**

- All Alpine add-ons: `ghcr.io/home-assistant/amd64-base:3.24` (secrets-sync, haos-monitor); gatus build.yaml 3.24 too
  (its Dockerfile default says 3.23, only a fallback). phone-logger: `amd64-base-python:3.12-alpine3.20`; litellm:
  `amd64-base-debian:trixie`; coding-assistants: Debian bookworm tag. Use `amd64-base:3.24`.

## 2. Getting the ntfy binary into an HA base image

### Upstream release artifacts for v2.36.0 **[V]** (`gh release view`, downloaded `checksums.txt`)

`https://github.com/binwiederhier/ntfy/releases/download/v${VERSION}/` plus:

- `ntfy_${VERSION}_linux_amd64.tar.gz`  sha256 `d2c76d17c4bde762913b1cbbf5ca2ac74c3eade36befb0989b44e7877c8596c2`
- `ntfy_${VERSION}_linux_arm64.tar.gz`  sha256 `f3f8dd78cdb4f25294fd399659f5e67ec0482c17056bc6f74853760284a2b17c`
- `ntfy_${VERSION}_linux_armv7.tar.gz`  sha256 `5c653c6da5f2fb0f72aab71218ce71ba84ab8d0230554785fd63637c045f2f37`
- also `_armv6`, `_darwin_all`, `.deb/.rpm`, `checksums.txt` (sha256 for every asset, one `hash  filename` per line).
- Tarball contains `ntfy_${VERSION}_linux_amd64/ntfy` (+ `server/server.yml`, LICENSE). The binary is a **statically
  linked** x86-64 ELF **[V]** (`file`), so it runs on musl/Alpine without glibc. Web UI (`/app`) is embedded in the
  binary (served with `web-root: app`) **[V]**: HTTP 200 on `/` with `web-root: app`.
- Docker Hub image `binwiederhier/ntfy:v2.36.0` exists with amd64, arm64, arm/v6, arm/v7 **[V]**
  (`docker manifest inspect`).

### Options compared

| Option                                              | Pros                                                                                          | Cons                                                                                                           |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **A. `curl` release tarball + `sha256sum -c`** (rec.) | Matches the repo rule ("HA base image only, download upstream artifact at build time"); `curl` present in the base image; arch via one ARG | checksum from the same origin unless `NTFY_SHA256` is pinned; needs network in build (already true elsewhere) |
| B. `COPY --from=binwiederhier/ntfy:v${VERSION}`     | gatus precedent; no checksum code; multi-arch handled by Docker                               | second registry (Docker Hub rate limits in CI), upstream image is Alpine-based but we only copy the binary; ARG must be global (validated by `validate-dockerfile-args.sh`); path of the binary in the image is `/usr/bin/ntfy` **[A]** (not inspected) |
| C. `apk add ntfy` (Alpine community)                | simplest                                                                                      | version lags upstream; breaks the "auto-update within 24 h" core value; **rejected**                           |
| D. Build from source (go)                           | no trust in artifacts                                                                         | heavy, needs Go + node build for the web UI; rejected                                                          |

Both A and B satisfy "HA base image only": the final stage is `ghcr.io/home-assistant/*-base` and only an upstream
artifact is copied in. Recommendation: **A**, because the checksum step gives integrity verification, it keeps one
registry (GitHub) and mirrors the Gatus-CLI/bw-CLI style. Keep `NTFY_ARCH` as build arg for later arm64/armv7:
mapping from HA `BUILD_ARCH`: `amd64->amd64`, `aarch64->arm64`, `armv7->armv7` (**[A]**, mapping not wired; the repo
builds only amd64 today and build.yml supports only amd64/aarch64).

### Checksum verification options

- **Default (implemented, [V])**: download `checksums.txt` from the same release and `sha256sum -c`. Detects
  truncated/corrupt downloads, not a compromised release. Negative test **[V]**: build with
  `--build-arg NTFY_SHA256=deadbeef` fails with `/tmp/ntfy.tar.gz: FAILED`, exit non-zero.
- **Stronger, optional**: pin `NTFY_SHA256` in `build.yaml args` and let `update-version.py`/auto-update refresh it.
  Not supported by the current update scripts **[A]** (only `VERSION` is touched), so it would need a script change;
  not worth it for Phase 24. Does upstream sign releases (cosign/gpg)? I did not check **[A]**; the asset list shows no
  `.sig`/`.pem` files, so there is no signature to verify **[V]** (asset list above).

## 3. Dockerfile skeleton, run.sh layout

### Dockerfile (built and tested here)

```dockerfile
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.24
FROM ${BUILD_FROM}

ARG VERSION=2.36.0
ARG NTFY_ARCH=amd64
# Optional pin; when empty the checksum is taken from the release's checksums.txt (same origin as the tarball)
ARG NTFY_SHA256=

# python3 only for the admin GUI server; sqlite for debugging auth.db
RUN apk add --no-cache python3 sqlite \
 && curl -fsSL -o /tmp/ntfy.tar.gz "https://github.com/binwiederhier/ntfy/releases/download/v${VERSION}/ntfy_${VERSION}_linux_${NTFY_ARCH}.tar.gz" \
 && curl -fsSL -o /tmp/checksums.txt "https://github.com/binwiederhier/ntfy/releases/download/v${VERSION}/checksums.txt" \
 && if [ -n "${NTFY_SHA256}" ]; then echo "${NTFY_SHA256}  /tmp/ntfy.tar.gz" > /tmp/want.txt; else grep " ntfy_${VERSION}_linux_${NTFY_ARCH}.tar.gz\$" /tmp/checksums.txt | sed "s| .*|  /tmp/ntfy.tar.gz|" > /tmp/want.txt; fi \
 && sha256sum -c /tmp/want.txt \
 && tar -xzf /tmp/ntfy.tar.gz --strip-components=1 -C /tmp "ntfy_${VERSION}_linux_${NTFY_ARCH}/ntfy" \
 && install -m 0755 /tmp/ntfy /usr/local/bin/ntfy \
 && rm -rf /tmp/*

COPY app/ /opt/ntfy-gui/app/
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
```

Results **[V]**:

- `docker build` OK (legacy builder here, BuildKit is used in CI; nothing BuildKit-specific in the file).
  `docker run --entrypoint ntfy ... --version` prints `ntfy version 2.36.0`.
- Image size 241 MB total, almost all of it the base image plus `python3` (64 MB with python3+sqlite on top of base).
  `sqlite` CLI is optional; drop it to save a few MB if not used for debugging.
- Base image already has `curl`, `bashio` (`/usr/bin/bashio`, `with-contenv` shebang), `ca-certificates`; python3 from
  Alpine 3.24 is **3.14.10** (relevant for stdlib: `http.server.ThreadingHTTPServer` and `sqlite3` available) **[V]**.
  Python stdlib is also enough for `sqlite3` read access to `auth.db` (sidecar/export), if D-02 later allows DB reads.
- hadolint (strict `make docker-build-check` rule set) exit 0 **[V]**; ARG-before-FROM validator OK **[V]**.
- The build uses the HA base image's `ash -o pipefail` default shell, so the `if ... ; then ... else ... fi` inside RUN works.
- Add `LABEL`/`BUILD_*` ARG block like gatus only if wanted; secrets-sync/haos-monitor omit it, CI sets labels itself.
- Not tested: arm64/armv7 builds **[A]**.

### ntfy runtime behaviour verified against a live server (container `ntfy-spike-image`, `/data` bind mount)

Server config used (`/etc/ntfy/server.yml`, which is also what the CLI reads automatically **[V]**):

```yaml
base-url: "http://localhost:18083"
listen-http: ":8000"
cache-file: "/data/cache.db"
cache-duration: "12h"
auth-file: "/data/auth.db"
auth-default-access: "deny-all"
behind-proxy: true
web-root: "app"
log-level: "info"
```

- `ntfy serve` starts with that file, `/v1/health` -> `{"healthy":true,"role":"active"}` **[V]**.
- CLI against the same DB while the server runs **[V]**: `ntfy user add [--role=admin] NAME` (password from
  `NTFY_PASSWORD` env, never argv), `ntfy user change-pass NAME`, `ntfy user list`, `ntfy user del NAME`,
  `ntfy access USER TOPIC rw|ro|wo|deny`, `ntfy access --reset USER [TOPIC]`, `ntfy access everyone public ro`,
  `ntfy token add --label=... USER`, `ntfy token list`. CLI is run via `docker exec` here; in the add-on it runs in the
  same container, same `/data`.
- **Idempotency [V]**: `ntfy user add` for an existing user prints `user NAME already exists` and exits **1**; so
  bootstrap must check `ntfy user list` first or tolerate that exit code. `ntfy user change-pass` exits 0.
  `ntfy access USER TOPIC rw` is naturally idempotent (grant overwrites), and re-grants exit 0.
- **SQLite concurrency [V, small]**: 15 sequential `ntfy access` CLI writes during 60 concurrent publishes by an
  authenticated user: 0 CLI failures, 0 occurrences of "locked" in the server log, all 15 ACL rows present. This is a
  light test, not a stress test; D-02's "known gap" is therefore **not** reproduced at this scale.
- **Live effect without restart [V]**: after `ntfy access u2 live2 ro` the user's next request got 200 (was 403);
  after `ntfy access --reset u2 live1` the topic returned 403. So ACL CLI changes are seen by the running server
  immediately, the GUI does not need to restart ntfy. (A first attempt showed 429 for rapid repeated requests because
  of ntfy's rate limiter; use the `ntfy` visitor limits in mind when the GUI does a "test publish".)
- **Input validation [V]**: usernames with a space and topics with `!` are rejected (`invalid argument`); wildcard
  `pre*` is accepted. The option regexes below mirror that (usernames `[-_.+@a-zA-Z0-9]`, topics `[-_a-zA-Z0-9]` with
  optional trailing `*`); I did not read the Go source, so the exact accepted sets are **[A]** beyond these probes.
- `ntfy user list` / `ntfy access` output is human text, no JSON flag **[V]** (`--help` list shows none). The GUI
  backend must parse text (`user NAME (role: X, tier: Y)`, lines `- read-write access to topic T`,
  `- read-only access to topic T`, `- tk_... (label), never expires, accessed from IP at TIME`) or read `auth.db` via
  python `sqlite3` read-only. Parsing output across ntfy upgrades is brittle; recommend a small parser plus a verify
  script, or a read-only SQLite read for lists and CLI for writes (D-02 allows "CLI or the DB").
- **Token output [V]**: `token list` prints the full `tk_...` token values (confirms D-13: they are clear text).
- **Bootstrap without server [A→V partly]**: first CLI call (`user add`) created `auth.db` while the server was already
  running; I did not test CLI before `serve` starts. Since `auth.db` is a plain SQLite file with ntfy applying its
  schema on open, bootstrapping before `ntfy serve` is expected to work **[A]**. Order in `run.sh` should be: write
  `server.yml`, run bootstrap CLI, then start `ntfy serve`, then GUI.

### Proposed `run.sh` layout (prototype tested for signal/exit behaviour only)

```bash
#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -e
OPTIONS=/data/options.json
# 1. options -> /data/server.yml (small python3 -I script or bashio::config; secrets only via env, never logged)
python3 -I /opt/ntfy-gui/app/render_config.py "$OPTIONS" /data/server.yml   # listen-http, base-url, auth-*, cache-*, attachment-*
export NTFY_CONFIG_FILE=/data/server.yml    # ntfy reads this env/flag; /etc/ntfy/server.yml is the default path
# 2. bootstrap (before serve): daily auth.db backup, admin_user if missing, baseline users/ACLs additively (D-04/05/06)
python3 -I /opt/ntfy-gui/app/bootstrap.py
# 3. start both, supervise
ntfy serve & NTFY=$!
python3 -I -m app.main & GUI=$!      # ThreadingHTTPServer on 0.0.0.0:8099, ingress gate as secrets-sync
term() { kill -TERM "$NTFY" "$GUI" 2>/dev/null; wait; exit "${1:-0}"; }
trap 'term 0' TERM INT
# whichever child dies first brings the add-on down so the Supervisor restarts it
wait -n "$NTFY" "$GUI" ; term 1
```

Findings **[V]** with a `/bin/sh` prototype (`ntfy serve &` + python http.server + `trap` + `kill -0` loop):

- `docker stop` terminated cleanly with **exit 0** (a SIGKILL after the 10 s grace period would give 137), so SIGTERM
  reaches ntfy and the helper and both end. I did not capture the duration (`time`/`bc` not available) **[A: seconds]**.
- When `ntfy` is killed (`pkill -x ntfy`) the wrapper terminated and the container stopped; my prototype exited **0**
  in that case, which would make the Supervisor treat a crash as a clean stop. The real script must exit non-zero
  (`term 1`) so `watchdog`/restart policy sees a failure. Not re-run after the fix **[A]**.
- With bashio images the HA init (s6-overlay `with-contenv`) is in use unless `init: false`; the repo uses
  `init: false` everywhere (secrets-sync run.sh `exec`s python directly), so there is no s6 process supervision and
  `run.sh` is PID 1 itself. Consequence: PID 1 must reap/forward signals, hence the trap + `wait -n` above (bash 5 in
  the base image **[A]**, `wait -n` with PID args needs bash >= 5.1 **[A]**; fall back to the `kill -0` loop tested above).
  Alternative: ship a two-service layout with `s6-rc` under `init: true` (base image default); more files, not used elsewhere
  in this repo; not recommended.
- Which process is "supervised": ntfy is the primary service (notification delivery); the GUI is secondary but they
  share the container, so a GUI crash restarting the whole add-on interrupts delivery. Option: restart only the GUI in
  a loop inside `run.sh` (ntfy keeps running) and exit only when ntfy dies. Recommended: GUI restart loop with backoff,
  ntfy death = container exit. Decision for the planner.
- `bashio::config` needs the Supervisor API (token); secrets-sync deliberately reads `/data/options.json` with python
  instead (works in a plain `docker run` for tests). Recommend the same: all option -> config rendering in python
  `-I` (stdlib), secrets via env only, which also allows testing the config renderer without Supervisor.
- Env instead of config file: ntfy also accepts every server option as `NTFY_*` env var; a rendered `server.yml` is easier
  to inspect and to diff, and avoids passwords in `docker inspect`. Recommend `server.yml` with mode 0600 in `/data`.

### Points the planner must decide / watch

1. `base-url` for the add-on is `https://ntfy.akentner.de` (public), while the container listens on plain HTTP; set
   `behind-proxy: true` (default in my draft) so ntfy trusts `X-Forwarded-For` from the Cloudflare/Traefik chain; this
   matters for the rate limiter (visitor IP). Whether `/app` works with the public `base-url` I did not test through the
   proxy **[A]**; only local `http://localhost:18083` was tested (HTTP 200 on `/`).
2. `auth-default-access` default: old add-on had its own default; D-10 says options stay. My draft default is `deny-all`
   (matches the behavior seen in the test: anonymous 403 on topics without ACL **[V]**).
3. `enable_web_ui: false` maps to omitting `web-root` or setting `web-root: disable` **[A]** (ntfy docs: `web-root` can be
   `disable`; not run here).
4. `attachments_enabled: true` requires `attachment-cache-dir: /data/attachments` in `server.yml` and a writable dir
   **[A]** (not run); keep the size limits optional strings with ntfy's unit syntax (`5G`, `15M`, `3h`).
5. Log level in ntfy is `trace|debug|info|warn|error` **[A]** (from `--log-level` help text: default INFO; the full list
   not printed by `--help` here); the draft therefore differs from the other add-ons' `list(debug|info|warning|error)`.
6. First start with empty `admin_password`: the draft makes `admin_password` `password` (required, empty string is
   accepted by the HA validator as a string, so bootstrap must refuse/skip with a clear log line, never generate and
   print a password). Alternatively `password?` and generate+write to `/data` is out of scope (D-04 says the
   option provides it).

## 4. Options schema draft

Names/semantics: `baseline_users[]` copies the old add-on `users[]` fields (D-06): `username`, `password`, `topic`,
`write_access`. `write_access` is optional with default `true`? The old add-on's default for a missing value is
unknown to me **[A]** (CONTEXT says "`rw` when `write_access` is true, else `ro`"); I used `bool?` so the planner must
pick the default (recommend `false` = `ro`, the safer reading of "missing").

Draft `config.yaml` (full file, validated):

```yaml
name: "ntfy"
description: "Self-hosted push notification server (ntfy) with an ingress admin GUI for users, ACLs and tokens"
version: "2.36.0-0"
slug: "ntfy"
init: false
arch:
  - amd64
image: "ghcr.io/akentner/homeassistant-addons/{arch}-ntfy"
url: "https://github.com/akentner/homeassistant-addons"
startup: "application"
boot: "auto"
host_network: true
ingress: true
ingress_port: 8099
panel_icon: "mdi:bell-ring"
panel_title: "ntfy"
panel_admin: true
map:
  - addon_config:rw
options:
  base_url: "https://ntfy.example.com"
  listen_port: 8000
  enable_web_ui: true
  behind_proxy: true
  auth_default_access: "deny-all"
  admin_user: "admin"
  admin_password: ""
  baseline_users: []
  backup_keep: 10
  cache_duration: "12h"
  attachments_enabled: false
  attachment_total_size_limit: "5G"
  attachment_file_size_limit: "15M"
  attachment_expiry_duration: "3h"
  log_level: "info"
schema:
  base_url: "url"
  listen_port: "port"
  enable_web_ui: "bool"
  behind_proxy: "bool"
  auth_default_access: "list(deny-all|read-only|write-only|read-write)"
  admin_user: "match(^[-_.+@a-zA-Z0-9]{1,64}$)"
  admin_password: "password"
  baseline_users:
    - username: "match(^[-_.+@a-zA-Z0-9]{1,64}$)"
      password: "password"
      topic: "match(^[-_a-zA-Z0-9]{1,64}\\*?$)"
      write_access: "bool?"
  backup_keep: "int(1,100)"
  cache_duration: "match(^[0-9]+(s|m|h|d)$)"
  attachments_enabled: "bool"
  attachment_total_size_limit: "match(^[0-9]+[KMGkmg]?$)?"
  attachment_file_size_limit: "match(^[0-9]+[KMGkmg]?$)?"
  attachment_expiry_duration: "match(^[0-9]+(s|m|h|d)$)?"
  log_level: "list(trace|debug|info|warn|error)"
```

Checks **[V]**:

- `uv run --with yamllint yamllint -c .yamllint.yml draft-config.yaml` -> OK (0 findings); 0 lines longer than 120.
- `internal/validate-addon-config.py ntfy` on a scratch dir with this config + a build.yaml -> "Add-on config validation
  passed." (This validator checks only the structural keys listed in section 1, not the `schema:` strings.)
- The four `match()` regexes were exercised with Python `re` against accepted/rejected samples **[V]**
  (`homeassistant`, `a.b@c`, `pre*`, `12h`, `5G` accepted; `bad name`, `a!`, `*`, `1w`, `5GB`, `G` rejected).
- Schema syntax used (types `url`, `port`, `bool`, `password`, `int(min,max)`, `list(a|b)`, `match(regex)`, trailing `?`
  for optional, list of dicts) is the HA add-on schema syntax and mirrors existing add-ons (secrets-sync:
  `url`, `password`, `int(60,86400)`, `list(...)`, list of dicts; litellm: `match(...)`; haos-monitor: `port`). I did
  not run the Supervisor's validator itself, so `match()` with `\\*` and `{1,64}` inside the string is **[A]** until
  installed on a test HA: the doubled backslash is what YAML double-quoted strings need to give the regex `\*`.
- `admin_password` `password` type and every baseline password are masked in the HA UI but stored in clear text in
  options/backups (matches D-01 note and the KB note on add-on options with secrets). `baseline_users[].password`
  inside a list of dicts: the Supervisor handles `password` there as in haos-monitor (`ssh_private_key: "password"`
  in a list) **[V from repo precedent]**.
- Not included on purpose: `reset_data` (replaced by GUI actions, D-11), `users[]` (renamed `baseline_users`).
- Extra options worth deciding: `behind_proxy` (drafted), `timezone` (not drafted), `web_push`/`smtp` (not in scope),
  `enable_login`/`enable_signup` (ntfy options; default would be fine, not exposed), `visitor_*` rate limits (out of scope).
- Migration copy 1:1: old `users[]` keys `username, password, topic, write_access` map straight to `baseline_users[]`;
  old `reset_data` has no counterpart; old add-on version 1.2.4 options `listen_port`, `base_url`,
  `enable_web_ui`, `auth_default_access`, `admin_*` keep their names. I could not inspect the old add-on's exact
  `auth_default_access` value set **[A]** (CONTEXT lists only the names); the draft uses ntfy's native values
  `deny-all|read-only|write-only|read-write`; verify against the old add-on's schema before release or the 1:1 copy may
  fail validation.

## 5. Cleanup

- Container `ntfy-spike-image` removed, image `ntfy-spike-image:test` removed, downloaded tarball dir removed.
  Left in scratch: `/tmp/akentner/ntfy-spike-image/{build,data,server.yml,proto.sh,chk.sh,draft-config.yaml,v}`
  (throwaway, contains dummy passwords `pw-spike-*` only, not real secrets).
- Containers `ntfy-spike-cli` and `ntfy-spike-ingress` (other workers) existed; not touched.
- No repo file changed except this findings file (not committed, nothing pushed).
