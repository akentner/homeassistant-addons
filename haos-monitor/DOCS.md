# HAOS Monitor

Observes one or more HAOS hosts over SSH and records kernel log and I/O stall indicators. Per host it writes
`/share/haos-monitor/<slug>.log`, serves a status JSON and publishes MQTT discovery entities.

## Repository exception

This add-on is our own code, not a wrapper around an upstream project. It therefore has no `.upstream.yaml`, no
auto-update and ships its scripts in the add-on directory (the repo-wide "no bundled source" rule does not apply). It is
built locally by the Supervisor (no `image:` key). The other repo rules still apply: HA base image only, 3-file version
sync via `make update-version`, and a local `docker build` before every commit.

## Prerequisites

- The observer must **not** run on the observed host. Nextgen watches the backup host; the backup host runs its own
  instance watching Nextgen.
- Every host needs HAOS host SSH on port 22222 (root) with the public key of the configured private key authorized.

## Options

| Option                                         | Default         | Description                                         |
| ---------------------------------------------- | --------------- | --------------------------------------------------- |
| `hosts[].name`                                 | `ha-backup`     | Display name; slug = lowercase, non-alphanumeric→`_` |
| `hosts[].host`                                 | `192.168.178.9` | Host or IP to observe                               |
| `hosts[].port`                                 | `22222`         | SSH port                                            |
| `hosts[].ssh_private_key`                      |                 | Private key (full content)                          |
| `interval`                                     | `10`            | Sampling and MQTT publish interval (s)              |
| `problem_age`                                  | `60`            | `problem=1` if `age >=` this (s)                    |
| `problem_io_full10`                            | `30`            | `problem=1` if `io_full10 >=` this (%)              |
| `problem_sda_inflight`                         | `8`             | `problem=1` if `sda_inflight >=` this               |
| `problem_dstate`                               | `1`             | `problem=1` if `dstate >=` this (pipe waits ignored) |
| `mqtt_host` / `mqtt_port`                      | `a0d7b954-emqx` / `1883` | Broker for discovery (not the observed host) |
| `mqtt_user` / `mqtt_password`                  |                 | Empty user = anonymous                              |
| `mqtt_discovery_prefix`                        | `homeassistant` | Discovery prefix                                    |
| `mqtt_clear_discovery`                         | `false`         | Clear retained topics, then idle (see below)        |

`dstate` counts only D-state tasks whose wchan is not a pipe wait (`anon_pipe_read` etc., e.g. short-lived `runc`);
those lines stay in the log but do not raise `problem`.

A host with a missing or malformed key, or a duplicate slug, is skipped; the others keep running.

## Status endpoint

`http://local-haos-monitor:8099/cgi-bin/status[?host=<slug>]` returns flat JSON (for Gatus): numbers plus the strings `reasons` and `dstate_tasks`. Without `host` the
first configured host is returned; an unknown host gives HTTP 404 `{"error":"unknown host"}`.

## MQTT

- State: `haos-monitor/<slug>/state`; availability (Last Will): `haos-monitor/<slug>/availability`.
- Discovery: `<prefix>/sensor|binary_sensor/haos_monitor_<slug>/<field>/config`, one device "HAOS Monitor <name>".
- `binary_sensor.…_problem` carries attributes explaining the cause: `reasons` (comma list of `stale`, `io_full10`,
  `sda_inflight`, `dstate`, or `none`), one boolean per component, the offending `dstate_tasks` (`pid (comm):wchan`) and
  the values behind them. The same fields are in the status JSON (`reasons`, `r_age`, `r_io`, `r_sda`, `r_dstate`).
- Remove entities: set `mqtt_clear_discovery: true` and restart (publishes empty retained payloads), or
  `mosquitto_pub -r -n -t '<topic>'` per topic. Set it back to `false` afterwards.
