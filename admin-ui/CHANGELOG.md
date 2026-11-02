# Changelog

All notable changes to the **Admin UI Blueprint** add-on are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/). This is our own code without an upstream project: the version is bumped
manually with `make update-version`.

## [0.1.0-0] - 2026-11-02

### Added

- Tracer slice: ingress gate, router and health API in the Python skeleton, JSON client and vendored Preact in the
  browser lib, demo page with a health badge
- Add-on shell: manifest without published ports, `boot: manual`, Dockerfile on the Home Assistant base image and
  `run.sh`
- Blueprint documentation: rules R-01 to R-15 with their enforcing tests, library reference, consumer recipe, HA
  integration facts and the spike result table, guarded by a structure test
- Sync tooling with drift check and the rules scanner for consumer add-ons, wired into the Makefile and the CI job
- Registration in the root README, the repository rules and the base-image tracking file

Release links are added after the first tag exists.
