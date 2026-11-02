// Pure helpers for the Secrets Sync views: tolerant readers for state.json blocks (older state files miss blocks), key
// filtering, status mapping and the clipboard helper. No DOM access at import time. State holds key NAMES only.
export const TAB_IDS = ["keys", "synthetic", "usage", "events"];
export const MAX_KEYS = 500;
export const MAX_USAGE = 300;
export const MAX_EVENTS = 100;
export const MAX_REFS = 20;

export const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
export const asObj = (v) => (isObj(v) ? v : {});
export const asArr = (v) => (Array.isArray(v) ? v : []);
export const str = (v) => (v === null || v === undefined ? "" : String(v));
export const dash = (v) => (str(v) === "" ? "-" : str(v));

// ISO string -> epoch milliseconds, null when missing or unparsable.
export function parseTime(v) {
  if (typeof v !== "string") return null;
  const ms = Date.parse(v);
  return Number.isFinite(ms) ? ms : null;
}

export function isStale(state) {
  if (state.stale === true) return true;
  const age = state.age_seconds;
  const interval = state.interval;
  return typeof age === "number" && typeof interval === "number" && age > 2 * interval;
}

// {id, kind}: id is one of ok, degraded, error, stale, starting; kind is the Badge kind.
export function statusInfo(state) {
  let id = typeof state.status === "string" && state.status ? state.status : "starting";
  if (id === "ok" && isStale(state)) id = "stale";
  if (!["ok", "degraded", "error", "stale", "starting"].includes(id)) id = "starting";
  return { id, kind: { ok: "ok", degraded: "degraded", error: "error", stale: "warn", starting: "muted" }[id] };
}

// Case-insensitive substring filter over names; non-string entries are stringified.
export function filterKeys(names, query) {
  const q = str(query).trim().toLowerCase();
  const all = asArr(names).map(str);
  return q ? all.filter((n) => n.toLowerCase().includes(q)) : all;
}

export const syntheticSet = (state) => new Set(asArr(asObj(state.keys).synthetic).map(str));

// Hash id wins, then the stored tab, then the first tab.
export function pickTab(hashId, stored) {
  if (TAB_IDS.includes(hashId)) return hashId;
  return TAB_IDS.includes(stored) ? stored : TAB_IDS[0];
}

// Copies text; resolves "copied", "selected" (text selected, user presses Ctrl+C) or "failed".
// The clipboard API can be blocked inside the ingress iframe, then a hidden textarea and execCommand is tried.
export async function copyText(text, { nav = globalThis.navigator, doc = globalThis.document } = {}) {
  try {
    await nav.clipboard.writeText(text);
    return "copied";
  } catch {
    // fall through to the textarea fallback
  }
  let area = null;
  try {
    area = doc.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.className = "sr-only";
    doc.body.appendChild(area);
    area.select();
    return doc.execCommand("copy") ? "copied" : "selected";
  } catch {
    return "failed";
  } finally {
    try {
      if (area && area.parentNode) area.parentNode.removeChild(area);
    } catch {
      // detached already
    }
  }
}
