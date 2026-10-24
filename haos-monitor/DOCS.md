# HAOS Monitor

Observes one or more HAOS hosts over SSH and records kernel log and I/O stall indicators. Per host it writes
`/share/haos-monitor/<slug>.log`, serves a status JSON and publishes MQTT discovery entities.

## Repository exception

This add-on is our own code, not a wrapper around an upstream project. It therefore has no `.upstream.yaml`, no
auto-update and ships its scripts in the add-on directory (the repo-wide "no bundled source" rule does not apply). Its
image is built and published by CI like the others (`image:` key). The other repo rules still apply: HA base image only,
3-file version sync via `make update-version`, and a local `docker build` before every commit.

## Prerequisites

- The observer must **not** run on the observed host. Nextgen watches the backup host; the backup host runs its own
  instance watching Nextgen.
- Every host needs HAOS host SSH on port 22222 (root) with the public key of the configured private key authorized.

## Options

| Option                        | Default                  | Description                                          |
| ----------------------------- | ------------------------ | ---------------------------------------------------- |
| `hosts[].name`                | `ha-backup`              | Display name; slug = lowercase, non-alphanumeric→`_` |
| `hosts[].host`                | `192.168.178.9`          | Host or IP to observe                                |
| `hosts[].port`                | `22222`                  | SSH port                                             |
| `hosts[].ssh_private_key`     |                          | Private key (full content)                           |
| `interval`                    | `10`                     | Sampling and MQTT publish interval (s)               |
| `problem_age`                 | `60`                     | `problem=1` if `age >=` this (s)                     |
| `problem_io_full10`           | `30`                     | `problem=1` if `io_full10 >=` this (%)               |
| `problem_sda_inflight`        | `8`                      | `problem=1` if `sda_inflight >=` this                |
| `problem_dstate`              | `1`                      | `problem=1` if `dstate >=` this (pipe waits ignored) |
| `problem_kmsg`                | `1`                      | `problem=1` if `kmsg_errors >=` this (last 10 min)   |
| `mqtt_host` / `mqtt_port`     | `a0d7b954-emqx` / `1883` | Broker for discovery (not the observed host)         |
| `mqtt_user` / `mqtt_password` |                          | Empty user = anonymous                               |
| `mqtt_discovery_prefix`       | `homeassistant`          | Discovery prefix                                     |
| `mqtt_clear_discovery`        | `false`                  | Clear retained topics, then idle (see below)         |

`dstate` counts only D-state tasks whose wchan is not a pipe wait (`anon_pipe_read` etc., e.g. short-lived `runc`);
those lines stay in the log but do not raise `problem`.

A host with a missing or malformed key, or a duplicate slug, is skipped; the others keep running.

## Evidence in the log

`/share/haos-monitor/<slug>.log` (UTC) holds, besides the raw lines, markers meant for `grep` after an incident:

| Line       | Meaning                                                                                              |
| ---------- | ---------------------------------------------------------------------------------------------------- |
| `KERR`     | Kernel line of level err or worse, or a known failure text (I/O error, UAS abort, USB reset, OOM, …) |
| `DSTACK`   | Kernel stack of a task stuck in D-state, from `/proc/<pid>/stack`; once, then every minute           |
| `INCIDENT` | `start` (with reasons and values), `change` and `end` (with duration) of the `problem` flag          |
| `BOOT`     | Host uptime at connect; a lower value than before marks a reboot                                     |

`DSTACK` shows where the I/O hangs (for example `blk_mq_get_tag` or `usb_*` frames) without changing any host setting.
Pipe waits such as short-lived `runc` are skipped. `KERR` lines count per kernel message number and host boot, so the
full kernel log replay after a reconnect does not count twice. Kernel errors right after a reboot also count for 10
minutes of uptime, so a reboot can raise `problem` briefly.

Samples, probes and `KERR` lines are mirrored to `<slug>.log.state` (trimmed at 1 MB), which the status code reads, so a
kernel log flood cannot push the samples out of its window.

## Status endpoint

`http://local-haos-monitor:8099/cgi-bin/status[?host=<slug>]` returns flat JSON (for Gatus): numbers plus the strings
`reasons`, `dstate_tasks` and `kmsg_last`. Without `host` the first configured host is returned; an unknown host gives
HTTP 404 `{"error":"unknown host"}`.

## Metrics endpoint

`http://local-haos-monitor:8099/cgi-bin/metrics` returns all hosts in Prometheus text format (also for VictoriaMetrics /
vmagent). Every sample carries `host="<slug>"`; values that are unknown are omitted, so a host without data only shows
the age and problem series.

| Metric                                      | Extra label | Meaning                                        |
| ------------------------------------------- | ----------- | ---------------------------------------------- |
| `haos_monitor_sample_age_seconds`           |             | Age of the newest SSH sample                   |
| `haos_monitor_probe_age_seconds`            |             | Age of the newest port probe                   |
| `haos_monitor_host_uptime_seconds`          |             | Uptime of the observed host                    |
| `haos_monitor_load1`                        |             | 1 minute load average                          |
| `haos_monitor_io_some_pressure_percent`     |             | PSI io some, avg10                             |
| `haos_monitor_io_full_pressure_percent`     |             | PSI io full, avg10                             |
| `haos_monitor_memory_full_pressure_percent` |             | PSI memory full, avg10                         |
| `haos_monitor_disk_inflight_requests`       | `device`    | In-flight I/O (`sda`, `mmcblk1`)               |
| `haos_monitor_dstate_tasks`                 |             | D-state tasks (pipe waits ignored)             |
| `haos_monitor_kmsg_errors`                  |             | Kernel error lines, last 10 min of host uptime |
| `haos_monitor_ping_up`                      |             | Host answers ping                              |
| `haos_monitor_port_open`                    | `port`      | `22222`, `1883`, `8123`, `4357` reachable      |
| `haos_monitor_problem`                      |             | 1 if any threshold is exceeded                 |
| `haos_monitor_problem_reason`               | `reason`    | `stale`, `io_full10`, `sda_inflight`, `dstate` |

Scrape example (Prometheus / vmagent):

```yaml
scrape_configs:
  - job_name: haos-monitor
    metrics_path: /cgi-bin/metrics
    scrape_interval: 15s
    static_configs:
      - targets: ["local-haos-monitor:8099"]
```

The port is closed by default; the scraper must reach the add-on network (`local-haos-monitor`, e.g. via Supervisor
DNS). To scrape from elsewhere in the LAN, set a host port for `8099/tcp` in the add-on's Network tab (optional). The
endpoints have no authentication, so open it only in a trusted network.

## MQTT

- State: `haos-monitor/<slug>/state`; availability (Last Will): `haos-monitor/<slug>/availability`.
- Discovery: `<prefix>/sensor|binary_sensor/haos_monitor_<slug>/<field>/config`, one device `HAOS Monitor <name>`.
- `binary_sensor.…_problem` carries attributes explaining the cause: `reasons` (comma list of `stale`, `io_full10`,
  `sda_inflight`, `dstate`, `kmsg`, or `none`), one boolean per component, the offending `dstate_tasks`
  (`pid (comm):wchan`) `kmsg_last` (the newest kernel error line) and the values behind them. The same fields are in the
  status JSON (`reasons`, `r_age`, `r_io`, `r_sda`, `r_dstate`, `r_kmsg`, `kmsg_errors`, `kmsg_last`).
- Remove entities: set `mqtt_clear_discovery: true` and restart (publishes empty retained payloads), or
  `mosquitto_pub -r -n -t '<topic>'` per topic. Set it back to `false` afterwards.
