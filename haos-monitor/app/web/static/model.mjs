// Pure model of the HAOS Monitor page: what is shown per host, which value violates its threshold, how the boot time and
// the overall status are derived. No imports and no DOM; every label is a literal key that the page resolves through i18n.

// Rows of the values table. `flag` names the status.sh field (r_*) that is 1 when the threshold is violated.
export const ROWS = [
  { field: "age", labelKey: "hm.row.age", flag: "r_age" },
  { field: "up", labelKey: "hm.row.up", flag: null, kind: "boot" },
  { field: "load1", labelKey: "hm.row.load1", flag: null },
  { field: "io_some10", labelKey: "hm.row.io_some10", flag: null },
  { field: "io_full10", labelKey: "hm.row.io_full10", flag: "r_io" },
  { field: "mem_full10", labelKey: "hm.row.mem_full10", flag: null },
  { field: "sda_inflight", labelKey: "hm.row.sda_inflight", flag: "r_sda" },
  { field: "mmc_inflight", labelKey: "hm.row.mmc_inflight", flag: null },
  { field: "dstate", labelKey: "hm.row.dstate", flag: "r_dstate" },
  { field: "kmsg_errors", labelKey: "hm.row.kmsg_errors", flag: "r_kmsg" },
];

export const PORTS = [
  { field: "ping", labelKey: "hm.port.ping" },
  { field: "p22222", labelKey: "hm.port.ssh" },
  { field: "p1883", labelKey: "hm.port.mqtt" },
  { field: "p8123", labelKey: "hm.port.ha" },
  { field: "p4357", labelKey: "hm.port.observer" },
];

export const REASONS = [
  { id: "stale", labelKey: "hm.reason.stale" },
  { id: "io_full10", labelKey: "hm.reason.io_full10" },
  { id: "sda_inflight", labelKey: "hm.reason.sda_inflight" },
  { id: "dstate", labelKey: "hm.reason.dstate" },
  { id: "kmsg", labelKey: "hm.reason.kmsg" },
];

// status.sh reports -1 for "no data yet".
export const isUnknown = (v) => typeof v !== "number" || !Number.isFinite(v) || v < 0;

export const isViolated = (status, row) => Boolean(row && row.flag && status && status[row.flag] === 1);

// Boot time from the server clock (never the browser clock): now - (uptime at the sample + age of the sample).
export function bootMs(status, nowMs) {
  if (!status || isUnknown(status.up) || typeof nowMs !== "number" || !Number.isFinite(nowMs)) return null;
  const age = isUnknown(status.age) ? 0 : status.age;
  return nowMs - (status.up + age) * 1000;
}

export function reasonIds(status) {
  const raw = status && typeof status.reasons === "string" ? status.reasons : "";
  return raw
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part !== "" && part !== "none");
}

export function portState(status, field) {
  const value = status ? status[field] : undefined;
  if (value === 1) return "up";
  if (value === 0) return "down";
  return "unknown";
}

// "unknown" (no fingerprint), "invalid" (run.sh could not read the key) or the validated type and fingerprint.
export function keyInfo(status) {
  const fp = status && typeof status.key_fp === "string" ? status.key_fp : "";
  if (fp === "") return { kind: "unknown" };
  if (fp === "invalid") return { kind: "invalid" };
  const type = typeof status.key_type === "string" ? status.key_type : "";
  return { kind: "ok", type, fp };
}

// Data only (kind, labelKey, count); the page turns it into text. A problem beats a degraded host.
export function overallStatus(data, error, loading) {
  if (!data) {
    if (loading) return { kind: "muted", labelKey: "state.loading", count: 0 };
    if (error) return { kind: "error", labelKey: "state.error", count: 0 };
    return { kind: "muted", labelKey: "state.loading", count: 0 };
  }
  const hosts = Array.isArray(data.hosts) ? data.hosts : [];
  const problems = hosts.filter((h) => h && h.status && h.status.problem === 1).length;
  if (problems > 0) return { kind: "error", labelKey: "hm.problems.other", count: problems };
  if (hosts.some((h) => !h || !h.status || h.error)) return { kind: "degraded", labelKey: "state.degraded", count: 0 };
  return { kind: "ok", labelKey: "state.ok", count: 0 };
}
