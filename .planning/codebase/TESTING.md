# Testing

_Last updated: 2026-04-03_

## Summary

This repository has no automated unit or integration tests. The `make test` target is an alias for `make lint`, meaning
"testing" in this project refers exclusively to static analysis and structural validation. All quality enforcement
happens via pre-commit hooks and GitHub Actions CI.

## Test Framework

**None.** No test runner, no test files, no test directories exist in this repository.

## What `make test` Actually Does

```makefile
test: lint
```

`make test` runs `make lint`, which executes all pre-commit hooks via `pre-commit run --all-files`.

## Static Analysis Pipeline (acting as "tests")

### Pre-commit Hooks (`.pre-commit-config.yaml`)

- **yamllint** — YAML syntax and style validation (2-space indent, 120-char limit)
- **markdownlint** — Markdown style (ATX headers, 4-space list indent, 120-char limit)
- **shellcheck** — Shell script linting (SC1091, SC2034 ignored)
- **hadolint** — Dockerfile linting (currently **disabled** in config)
- **validate-addons** — Checks required files exist, YAML is valid
- **validate-versions** — Checks 3-file version sync (config.yaml / build.yaml / README.md)
- Generic hooks: trailing whitespace, EOF newline, line endings, large files, merge conflicts

### GitHub Actions CI (`lint.yml`)

- Runs on push and pull requests
- Executes `make check-all` (lint + validate-addons + validate-versions)
- Uses `actionlint` for workflow YAML validation

## Explicitly Untested Code

| Component                                                | Risk                                                       |
| -------------------------------------------------------- | ---------------------------------------------------------- |
| `phone-logger/generate_config.py` `transform()` function | Core config transformation logic — no unit tests           |
| `scripts/update-version.py`                              | Version bumping script — no regression tests               |
| Docker image runtime behavior                            | No container smoke tests                                   |
| MQTT bridge logic in `fritz-callmonitor2mqtt/run.sh`     | No integration tests against real FRITZ!Box or MQTT broker |
| Phone logger adapter logic                               | No functional tests for call event processing              |

## CI/CD

- **Platform:** GitHub Actions
- **Trigger:** push, pull_request
- **Auto-update:** Daily cron workflow documented in `.upstream.yaml` files — but the corresponding workflow file does
  not exist in `.github/workflows/` (only `lint.yml` is present)

## Key Observations

- No test framework is installed or referenced anywhere in the codebase
- Quality is enforced structurally (required files, version sync) rather than behaviorally (correct runtime behavior)
- The most complex logic (`generate_config.py`, `update-version.py`) has zero test coverage
- Adding tests would require selecting a framework (pytest for Python) and creating test fixtures
