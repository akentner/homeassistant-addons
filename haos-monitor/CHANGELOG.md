# Changelog

All notable changes to the **HAOS Monitor** add-on are documented in this file. The add-on is our own code with no
upstream project, so every entry is add-on specific.

## [0.3.0] - 2026-10-24

- First published release: image `ghcr.io/akentner/homeassistant-addons/{arch}-haos-monitor` built by CI, icon, logo,
  translations (en, de) and full options schema (MQTT options added).
- D-state tasks waiting on a pipe (`anon_pipe_read`, e.g. short-lived `runc`) no longer count as problem.
- The `problem` binary sensor exposes `reasons` and one attribute per component. The status JSON gains `reasons`,
  `r_age`, `r_io`, `r_sda`, `r_dstate` and `dstate_tasks`.

## [0.2.0] - 2026-10-24

- Multiple hosts (`hosts[]`), one log file per host in `/share/haos-monitor/<slug>.log`.
- HTTP status endpoint on port 8099 (`/cgi-bin/status[?host=<slug>]`) for Gatus.
- MQTT discovery with availability (Last Will): one device per host with sensors and binary sensors.

## [0.1.0] - 2026-10-24

- Initial version: SSH monitor for one host, kernel log plus I/O stall indicators in `/share/haos-monitor/`.
