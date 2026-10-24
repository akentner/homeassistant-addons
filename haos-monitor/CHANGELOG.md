# Changelog

All notable changes to the **HAOS Monitor** add-on are documented in this file. The add-on is our own code with no
upstream project, so every entry is add-on specific.

## [0.6.0-1] - 2026-10-25

- Status page: add a "Reload" button that refreshes all hosts immediately.

## [0.6.0] - 2026-10-25

- Add Ingress: sidebar entry and "Open Web UI" button with a status page per host (values, violated thresholds, ports,
  blocked tasks, last kernel error, recent incidents).
- Add `/api/status.json`, `/api/metrics.txt`, `/api/hosts.json` and `/api/incidents.json`. `/cgi-bin/status` and
  `/cgi-bin/metrics` keep working.

## [0.5.0-1] - 2026-10-24

- Fix: `image:` pointed at `amd64-haos-monitor`, but CI publishes `amd64-haos_monitor`, so the Supervisor could not pull
  the image (403 denied).

## [0.5.0] - 2026-10-24

- Kernel error detection: error-level kernel lines and known failure texts (I/O error, UAS abort, USB reset, OOM,
  lockups) are logged as `KERR` and counted over the last 10 minutes of host uptime. New option `problem_kmsg`, sensor
  `kmsg_errors`, problem reason `kmsg`, attributes `kmsg_found`, `kmsg_errors`, `kmsg_last`, metric
  `haos_monitor_kmsg_errors`.
- Kernel stack dump (`DSTACK`) of tasks stuck in D-state, read from `/proc/<pid>/stack` (no sysrq, no host change).
- `INCIDENT start|change|end` marker lines when `problem` changes.
- Samples are mirrored to a small `<slug>.log.state`, so a kernel log flood cannot hide them from the status code.

## [0.4.1] - 2026-10-24

- Optional host port for `8099/tcp` (status JSON and metrics), closed by default.

## [0.4.0] - 2026-10-24

- Prometheus/VictoriaMetrics endpoint `/cgi-bin/metrics` (all hosts, label `host`), built from the same status data as
  the JSON endpoint and MQTT.

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
