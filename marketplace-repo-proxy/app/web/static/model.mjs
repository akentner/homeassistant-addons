// Pure model of the management page: status, registration and branch-source string keys and badge kinds, short SHA,
// ISO time to epoch ms and the poll cadence. No imports and no DOM; every label is a literal key that the page resolves
// through i18n (R-06).

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

// Registration state of a repository in the local add-on store (/data/supervisor.json, D-19). Literal table: the view
// indexes it only with a state that is an own key.
export const REGISTRATION_KEYS = {
  registered: "mrp.reg.registered",
  missing: "mrp.reg.missing",
  leftover: "mrp.reg.leftover",
  error: "mrp.reg.error",
};

// Badge kind of a registration state.
export function registrationKind(state) {
  if (state === "registered") return "ok";
  if (state === "missing" || state === "leftover") return "warn";
  if (state === "error") return "err";
  return "muted";
}

// Text key of a known registration state, null for anything else.
export function registrationKey(state) {
  return has(REGISTRATION_KEYS, state) ? REGISTRATION_KEYS[state] : null;
}

// True when at least one repository row carries registration data; otherwise the view shows no registration column.
export function hasRegistration(rows) {
  return Array.isArray(rows) && rows.some((row) => Boolean(row) && row.registration !== null && row.registration !== undefined);
}

// Where the served branch comes from (status.json branch_source).
export const BRANCH_KEYS = {
  configured: "mrp.repo.branch.configured",
  upstream_default: "mrp.repo.branch.upstream_default",
};

// Text key of a known branch source, null for anything else.
export function branchKey(source) {
  return has(BRANCH_KEYS, source) ? BRANCH_KEYS[source] : null;
}

export const POLL_BUSY_MS = 2000;
export const POLL_IDLE_MS = 15000;

// Poll api/overview every 2 s while a sync is requested or running, every 15 s otherwise (D-18).
export function pollMs(overview) {
  const sync = overview && overview.sync;
  if (sync && (sync.requested === true || sync.state === "running")) return POLL_BUSY_MS;
  return POLL_IDLE_MS;
}
