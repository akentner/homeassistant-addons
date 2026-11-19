# Changelog

All notable changes to the **Marketplace Repo Proxy** add-on are documented in this file. The add-on is our own code
with no upstream project, so every entry is add-on specific.

## [0.1.0-2] - 2026-11-19

### Added

- Supervisor integration: the manifest has `hassio_api: true` and `hassio_role: manager`, and a single client is limited
  to four store calls (`GET`/`POST /store/repositories`, `DELETE /store/repositories/{slug}`, `POST /store/reload`),
  checked before any network I/O; the Supervisor token is used only by the sync process
- Self-registration: one system user `local` per repository whose internal store URL is added to the local add-on store
  after the first successful sync. `register_local` now takes effect: after the update the add-on registers its
  configured repositories automatically (set it to `false` before the update to prevent that)
- Store reload after upstream changes of a registered repository, at most once per sync interval; a deferred reload
  survives a restart
- `mrp local status`, `mrp local rotate {owner/repo} --yes` (revokes the old `local` URL at once, after a warning that
  add-ons installed from the old store repository get no updates until they are reinstalled) and
  `mrp local remove {owner/repo}`; a store repository is never removed automatically and never by force
- Leftover reporting (`in_use`, `error`, `interrupted`, `orphaned`) in the log, in `mrp local status` and in
  `/data/supervisor.json`
- `/data/supervisor.json` contract for the management page of a later version, with the registration status values
  `registered`, `missing`, `leftover` and `error`
- Fake Supervisor container in `internal/verify-marketplace-repo-proxy.sh`, which proves registration, store reload,
  rotation, removal, leftovers and token hygiene in the built image
- Documentation of the store registration, the `supervisor.json` contract and the manager role in [DOCS.md](DOCS.md)

### Changed

- The user labels `local` and `local.*` are reserved for the store registration (`mrp users add|revoke` answer
  `user_reserved`)
- The Supervisor security rating of the add-on drops from 7 to 6 (manager role)

## [0.1.0-1] - 2026-11-18

### Added

- Sync service: fetches every configured private GitHub repository with a read-only token (passed only through the
  environment) at start, every `sync_interval` minutes and on request, and writes `/data/status.json` with the status
  codes `pending`, `ok`, `auth_failed`, `not_found`, `no_repository_yaml` and `fetch_failed`
- Read-only smart-HTTP serving (lighttpd + `git http-backend`) under per-user store URLs
  `http://{hostname}:8080/repo/{owner}/{repo}/{hash}` with random 128-bit access hashes; pushes are refused
- Options `github_token`, `sync_interval`, `public_url`, `repositories`, `register_local` and `api_enabled` (the last
  two without effect yet), with English and German translations
- `mrp` CLI inside the container: `users add|list|url|revoke`, `sync` and `reconcile`
- `access-watch` service: applies every change to `/data/access.json`, including hand edits, within about a second
- Startup log with every configured repository and its users' masked store URLs (internal and, with `public_url`,
  public)
- `internal/verify-marketplace-repo-proxy.sh`: proves cloning, sync, the 404/403 matrix, revocation and secret hygiene
  in the built image against a local upstream fixture
- Documentation of options, store URLs, user management and the `access.json`, `status.json` and sync trigger contracts
  in [DOCS.md](DOCS.md)

### Changed

- The placeholder start script is replaced by s6 services: `run.sh` is now the oneshot `init`, and s6-overlay supervises
  the longruns `sync`, `lighttpd` and `access-watch`

## [0.1.0-0] - 2026-11-16

### Added

- Add-on scaffold (manifest, build, Dockerfile, placeholder `run.sh`); the goal is described in [GOAL.md](GOAL.md)
