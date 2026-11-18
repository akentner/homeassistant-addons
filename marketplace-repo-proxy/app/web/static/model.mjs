// Pure model of the management page: status code to string key and badge kind, short SHA, ISO time to epoch ms.
// No imports and no DOM; every label is a literal key that the page resolves through i18n (R-06).

// Literal table: call sites index it so the i18n scanner can follow every key.
export const STATUS_KEYS = {
  pending: "mrp.status.pending",
  ok: "mrp.status.ok",
  auth_failed: "mrp.status.auth_failed",
  not_found: "mrp.status.not_found",
  no_repository_yaml: "mrp.status.no_repository_yaml",
  fetch_failed: "mrp.status.fetch_failed",
};

const has = (table, key) => typeof key === "string" && Object.prototype.hasOwnProperty.call(table, key);

// Unknown or missing status -> "no status".
export function statusKey(code) {
  return has(STATUS_KEYS, code) ? STATUS_KEYS[code] : "mrp.status.none";
}

// Badge kind of a status code.
export function statusKind(code) {
  if (code === "ok") return "ok";
  if (code === "pending" || code === "no_repository_yaml") return "warn";
  if (code === "auth_failed" || code === "not_found" || code === "fetch_failed") return "err";
  return "muted";
}

// First 12 characters of a commit SHA, "" for anything else. status.json already stores the 12-character short SHA;
// a full 40-hex SHA is accepted too.
export function shortSha(head) {
  return typeof head === "string" && /^[0-9a-f]{7,40}$/.test(head) ? head.slice(0, 12) : "";
}

// ISO 8601 timestamp -> epoch ms, null when missing or not parseable.
export function toMs(iso) {
  if (typeof iso !== "string") return null;
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? ms : null;
}
