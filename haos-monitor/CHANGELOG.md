# Changelog

All notable changes to the **HAOS Monitor** add-on are documented in this file. The add-on is our own code with no
upstream project, so every entry is add-on specific.

## [0.8.3-0] - 2026-11-05

### Changed

- Use admin-ui lib 0.9.1: info toasts get a blue accent

## [0.8.2-0] - 2026-11-05

### Changed

- Use admin-ui lib 0.9.0: toasts look like the Home Assistant snackbar

## [0.8.1-0] - 2026-11-05

### Fixed

- The info icon and the version did not show up: the Supervisor token is not in the environment of the GUI process, so
  it is now also read from the s6 container environment
- Without the language switch the info icon, badge and version now sit at the right edge of the top bar (lib 0.8.1)

## [0.8.0-0] - 2026-11-05

### Changed

- Topbar: the language switch is gone (the page follows the browser language); right-aligned it now shows an info icon
  that opens the add-on's configuration page in Home Assistant, the status badge and the add-on version
- The info icon and the version come from the Supervisor (`addon_slug` and `addon_version` in `/api/overview`, needs no
  extra permission); without an answer both stay hidden
- Use admin-ui lib 0.8.0

## [0.7.3-0] - 2026-11-05

### Changed

- Use admin-ui lib 0.7.1: static files and the page carry a strong `ETag` and answer `If-None-Match` with `304`;
  `index.html` is served with `?v=<hash>` asset URLs and stays `no-cache`, so a changed front end is never shown from a
  stale browser cache
- A browser that cached the 0.6.x page heuristically may need one hard reload (Ctrl+Shift+R) after updating

## [0.7.2-0] - 2026-11-05

### Fixed

- Limit the kernel log replay on start: lines older than 5 minutes before the host uptime are dropped on the host, so
  old errors are not counted as new and fresh samples no longer queue behind the backlog (host showed red for about 15
  minutes after every start)
- Check the log size only every 100 lines instead of forking `wc` for each line

### Added

- State `syncing`: the monitor marks its start (`SYNC start` / `SYNC done`); `/api/status.json` gets `"syncing":true`
  and holds back the stale verdict for at most 10 minutes, so `problem` and Gatus stay green. Real problems still count.
  New metric `haos_monitor_syncing`; the web UI shows an "Updating…" badge instead of red

## [0.7.1-0] - 2026-11-04

### Changed

- Use admin-ui lib 0.7.0 with HA-style navigation, optional icons and consistent minimum table row heights
- Fix overlapping badge lines and preserve table layout in action cells

## [0.7.0] - 2026-11-02

- Change: the status page is rebuilt on the shared admin-ui blueprint (Preact, German and English, light and dark theme,
  HA theme when embedded). One card per host with the same information as before: verdict and reasons, all values with
  violated thresholds highlighted, port chips, the SSH key line, blocked tasks, the last kernel error and the last 10
  incident lines. It still refreshes every 10 seconds and has a Reload button.
- Change: the page is served by a small Python server behind the ingress gate on the internal port 8100 and is no longer
  reachable on the optional published port 8099, where it was unauthenticated. `python3` is added to the image.
- Change: a port without probe data now shows as unknown instead of down, and the uptime line uses localized relative
  time (for example "5 days ago").
- Unchanged contracts: `/api/status.json`, `/cgi-bin/status`, `/api/metrics.txt`, `/cgi-bin/metrics`, `/api/hosts.json`
  and `/api/incidents.json` stay on port 8099 exactly as before, so Gatus and Prometheus configurations keep working.
  The port settings, options and MQTT entities are unchanged.
- CI: front end and add-on tests run in the lint workflow (job `haos-monitor`).

## [0.6.1-1] - 2026-10-31

- Show the SHA256 fingerprint and type of each host's SSH key on the status page, in `/api/status.json` (`key_fp`,
  `key_type`) and as `problem` sensor attributes (`key_fingerprint`, `key_type`), so you can compare it with the
  authorized key on the host. It is computed from the configured private key at start; an unreadable key shows
  `invalid`. A startup log line prints it too.

## [0.6.1] - 2026-10-26

- `dstate` no longer counts the ext4 journal thread (`jbd2/…`) waiting on `__wait_on_buffer` and idle kernel workers
  (`worker_thread`). They caused about one short `problem` per three hours on a healthy host.

## [0.6.0-2] - 2026-10-25

- Status page: show the host boot time (local time) with the relative uptime, e.g. `2026-10-20 08:12:33 (5d 1h ago)`.

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
