// English strings of the HAOS Monitor page. Flat dotted keys; {name} marks a parameter. Same keys as strings.de.mjs.
export default {
  "app.title": "HAOS Monitor",

  "hm.verdict.ok": "OK",
  "hm.verdict.syncing": "Updating…",
  "hm.verdict.problem": "PROBLEM",
  "hm.verdict.unknown": "Unknown",

  "hm.reasons.label": "Reasons",
  "hm.reason.stale": "Stale samples",
  "hm.reason.io_full10": "I/O stall",
  "hm.reason.sda_inflight": "sda requests piling up",
  "hm.reason.dstate": "Blocked tasks",
  "hm.reason.kmsg": "Kernel errors",

  "hm.values.caption": "Measured values of {host}",
  "hm.row.age": "Sample age (s)",
  "hm.row.up": "Host booted",
  "hm.row.up.value": "{time} ({relative})",
  "hm.row.load1": "Load (1 min)",
  "hm.row.io_some10": "I/O some (10 s avg %)",
  "hm.row.io_full10": "I/O full (10 s avg %)",
  "hm.row.mem_full10": "Memory full (10 s avg %)",
  "hm.row.sda_inflight": "sda in-flight requests",
  "hm.row.mmc_inflight": "mmc in-flight requests",
  "hm.row.dstate": "Tasks in D-state",
  "hm.row.kmsg_errors": "Kernel errors (10 min)",
  "hm.value.unknown": "–",
  "hm.violated": "Threshold exceeded",

  "hm.ports.label": "Reachability",
  "hm.port.ping": "Ping",
  "hm.port.ssh": "SSH 22222",
  "hm.port.mqtt": "MQTT 1883",
  "hm.port.ha": "HA 8123",
  "hm.port.observer": "Observer 4357",
  "hm.port.state.up": "reachable",
  "hm.port.state.down": "unreachable",
  "hm.port.state.unknown": "unknown",

  "hm.key.label": "SSH key",
  "hm.key.invalid": "invalid",

  "hm.blocked.title": "Blocked tasks",
  "hm.kmsg.title": "Last kernel error",
  "hm.incidents.title": "Recent incidents",
  "hm.incidents.none": "none logged",

  "hm.updated": "Updated {time}",
  "hm.problems.one": "{n} problem",
  "hm.problems.other": "{n} problems",
  "hm.empty": "No hosts configured.",

  "errors.hosts_unavailable": "The host list is not available",
  "errors.status_failed": "The status of this host could not be determined",
};
