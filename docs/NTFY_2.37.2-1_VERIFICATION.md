# ntfy 2.37.2-1 local verification

Date: 2026-11-04. Branch: `feat/admin-ui-blueprint`.

- Merged `origin/main` in `f87aef7`, preserving branch UI fixes, development versions and both branches' test jobs.
- Ran `make sync-admin-ui`; all consumers match canonical lib 0.7.0 and the server skeleton.
- Updated ntfy using `make update-version ADDON=ntfy VERSION=2.37.2-1 NO_TAG=yes NO_PUSH=yes`. Binary/build version and
  README badge remain 2.37.2. Upstream changelog notes are preserved.
- Passed version validation, strict library synchronization, blueprint rules and `git diff --check`.
- Passed read-only pre-commit YAML, merge-conflict and actionlint checks. Merge commit hooks also passed, including
  Markdown, schema validation, gitleaks and offline zizmor.
- Passed Admin UI Node tests (311), Admin UI pytest (372), ntfy pytest (386), ntfy Node tests (127), Secrets Sync Node
  tests (30), Secrets Sync web pytest (66) and HAOS Monitor pytest (216).
- Built `local/ntfy:2.37.2` using `make build-addon ADDON=ntfy`. The host lacked Buildx; supplied Buildx v0.29.1 through
  temporary `DOCKER_CONFIG=/tmp/ntfy-docker`, without repository build changes.
- Image reports `ntfy version 2.37.2`. All 61 files under `ntfy/app/web` match the image byte for byte.

No remote push, release tag, publication or Home Assistant installation was performed. Existing agent documentation
changes remain outside the task commits.
