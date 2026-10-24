#!/bin/sh
# Prometheus/VictoriaMetrics text exposition of all hosts: /cgi-bin/metrics
# Built from status.sh, so Gatus, MQTT and metrics always agree. Missing values (-1) are omitted.
HOSTS=${HOSTS_FILE:-/etc/haos-monitor.hosts}
STATUS=${STATUS_SH:-/status.sh}

printf 'Content-Type: text/plain; version=0.0.4; charset=utf-8\r\n\r\n'
cut -f1 "$HOSTS" 2>/dev/null | while IFS= read -r slug; do
  "$STATUS" "$slug" | jq -c --arg h "$slug" '. + {host: $h}'
done | jq -rs '
def hl: "host=\"\(.host)\"";
def fam($n; $help; $rows):
  ($rows | map(select(.v != null and .v >= 0))) as $r
  | if ($r | length) == 0 then empty
    else "# HELP \($n) \($help)", "# TYPE \($n) gauge", ($r[] | "\($n){\(.l)} \(.v)") end;
. as $hosts
| def per(f): [$hosts[] | {l: hl, v: f}];
  def per2($lk; $items): [$hosts[] | . as $s | $items[] | {l: ($s | hl) + ",\($lk)=\"\(.[0])\"", v: ($s[.[1]])}];
  fam("haos_monitor_sample_age_seconds"; "Age of the newest SSH sample"; per(.age)),
  fam("haos_monitor_probe_age_seconds"; "Age of the newest port probe"; per(.probe_age)),
  fam("haos_monitor_host_uptime_seconds"; "Uptime of the observed host"; per(.up)),
  fam("haos_monitor_load1"; "1 minute load average of the observed host"; per(.load1)),
  fam("haos_monitor_io_some_pressure_percent"; "PSI io some avg10"; per(.io_some10)),
  fam("haos_monitor_io_full_pressure_percent"; "PSI io full avg10"; per(.io_full10)),
  fam("haos_monitor_memory_full_pressure_percent"; "PSI memory full avg10"; per(.mem_full10)),
  fam("haos_monitor_disk_inflight_requests"; "In-flight I/O requests per device";
      per2("device"; [["sda", "sda_inflight"], ["mmcblk1", "mmc_inflight"]])),
  fam("haos_monitor_dstate_tasks"; "Tasks in uninterruptible sleep (pipe waits ignored)"; per(.dstate)),
  fam("haos_monitor_kmsg_errors"; "Kernel error lines within the last 10 minutes of host uptime"; per(.kmsg_errors)),
  fam("haos_monitor_ping_up"; "Observed host answers ping"; per(.ping)),
  fam("haos_monitor_port_open"; "TCP port reachable from the add-on";
      per2("port"; [["22222", "p22222"], ["1883", "p1883"], ["8123", "p8123"], ["4357", "p4357"]])),
  fam("haos_monitor_problem"; "1 if any problem threshold is exceeded"; per(.problem)),
  fam("haos_monitor_problem_reason"; "1 per fired problem component";
      per2("reason"; [["stale", "r_age"], ["io_full10", "r_io"], ["sda_inflight", "r_sda"], ["dstate", "r_dstate"], ["kmsg", "r_kmsg"]]))
'
