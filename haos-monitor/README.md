# Home Assistant Add-on: HAOS Monitor

[![Release][release-shield]][release] ![Project Stage][project-stage-shield] ![Project Maintenance][maintenance-shield]

Diagnostic monitor for HAOS hosts that hang without leaving a trace.

## About

Some hosts keep answering ping while SSH, web UI and Observer are dead. After the reboot the evidence is gone. This
add-on keeps an SSH session open to each observed host and records what happens **before** it freezes: the kernel log,
I/O pressure, in-flight requests on the data disk and tasks stuck in uninterruptible sleep. Port probes from outside
show which services are still reachable.

It is our own code, not an upstream wrapper (see the exception in [DOCS.md][docs]).

## Features

- Several hosts per add-on, one log file each in `/share/haos-monitor/<slug>.log` (rotated at 20 MB × 5)
- Status JSON for Gatus at `http://local-haos-monitor:8099/cgi-bin/status[?host=<slug>]`
- Prometheus/VictoriaMetrics metrics at `http://local-haos-monitor:8099/cgi-bin/metrics`
- MQTT discovery: one device per host with sensors and binary sensors, availability via Last Will
- `problem` sensor with the reasons as attributes (stale data, I/O pressure, in-flight I/O, D-state tasks, kernel
  errors)
- Evidence for post-mortems: kernel stacks of blocked tasks (`DSTACK`), kernel error lines (`KERR`) and `INCIDENT`
  markers in the log
- Remote side uses shell builtins only, so it keeps working while the data disk is stalled

## Configuration

Add each host under `hosts` with its name, IP, SSH port (HAOS host SSH is `22222`) and a private key that is authorized
on that host. The thresholds are deliberately sensitive: a few false positives are better than no visibility.

See [DOCS.md][docs] for all options, the status endpoint and the MQTT entities.

[docs]: DOCS.md
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-orange.svg
[release-shield]: https://img.shields.io/badge/version-v0.5.0-blue.svg
[release]: https://github.com/akentner/homeassistant-addons/tree/v0.5.0
