# Changelog

All notable changes to the **Marketplace Repo Proxy** add-on are documented in this file. The add-on is our own code
with no upstream project, so every entry is add-on specific.

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
