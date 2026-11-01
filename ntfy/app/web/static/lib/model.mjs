// Pure helpers (no DOM, no preact, no fetch). Mirrors ntfy/app/contract.py; keep both in sync.

export const PERMISSIONS = ["rw", "ro", "wo", "deny"];
export const PERMISSION_LABELS = {
  rw: "read + write",
  ro: "read only",
  wo: "write only",
  deny: "deny",
};
export const ORIGINS = ["gui", "options", "iac"];
export const RESET_PHRASES = { acls: "reset acls", cache: "clear cache", everything: "reset everything" };

const USERNAME_RE = /^[a-zA-Z0-9_][-_.+@a-zA-Z0-9]{0,63}$/;
const TOPIC_PATTERN_RE = /^[a-zA-Z0-9_*][-_a-zA-Z0-9*]{0,63}$/;
const TOPIC_RE = /^[a-zA-Z0-9_][-_a-zA-Z0-9]{0,63}$/;
const DURATION_RE = /^[0-9]+[smhd]$/;
const LABEL_RE = /^[^\x00-\x1f]{0,64}$/;

export const validUsername = (s) => typeof s === "string" && USERNAME_RE.test(s);
export const validTopicPattern = (s) => typeof s === "string" && TOPIC_PATTERN_RE.test(s);
export const validTopic = (s) => typeof s === "string" && TOPIC_RE.test(s);
export const validDuration = (s) => typeof s === "string" && DURATION_RE.test(s);
export const validLabel = (s) => typeof s === "string" && LABEL_RE.test(s);

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\\/-]/g, "\\$&");

// ntfy semantics: '*' matches any sequence, case-sensitive, everything else literal ('_' included).
export function matchTopic(pattern, topic) {
  const source = pattern.split("*").map(escapeRe).join(".*");
  return new RegExp(`^(?:${source})$`, "s").test(topic);
}

const byName = (a, b) => {
  if (a === b) return 0;
  if (a === "everyone") return -1;
  if (b === "everyone") return 1;
  return a < b ? -1 : 1;
};

export function sortRules(rules) {
  return [...rules].sort((a, b) => byName(a.user, b.user) || (a.topic < b.topic ? -1 : a.topic > b.topic ? 1 : 0));
}

export function groupRulesByUser(rules) {
  const groups = {};
  for (const rule of sortRules(rules)) (groups[rule.user] ||= []).push(rule);
  return groups;
}

// users: [{username}] or [name]; rules: [{user, topic, permission}]
export function buildMatrix(users, rules) {
  const names = new Set(users.map((u) => (typeof u === "string" ? u : u.username)));
  for (const r of rules) names.add(r.user);
  const topics = [...new Set(rules.map((r) => r.topic))].sort();
  const cells = {};
  for (const name of names) cells[name] = {};
  for (const r of rules) cells[r.user][r.topic] = r.permission;
  return { users: [...names].sort(byName), topics, cells };
}

export function fmtBytes(n) {
  if (!Number.isFinite(n) || n < 0) return "-";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return i === 0 ? `${v} B` : `${v.toFixed(1)} ${units[i]}`;
}

const pad = (n) => String(n).padStart(2, "0");

export function fmtUnix(ts) {
  if (!ts) return "-";
  const d = new Date(ts * 1000);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function fmtExpiry(ts, nowMs = Date.now()) {
  if (!ts) return "never";
  return ts * 1000 <= nowMs ? `expired ${fmtUnix(ts)}` : fmtUnix(ts);
}

export function relTime(ts, nowMs = Date.now()) {
  if (!ts) return "-";
  const sec = Math.round((nowMs - ts * 1000) / 1000);
  if (sec < 45) return "just now";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min} min ago`;
  const hours = Math.round(min / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

const PROTECTION = {
  last_admin: "last admin",
  options_admin: "admin from options",
  anonymous: "anonymous user",
};

export function protectionLabel(reason) {
  return PROTECTION[reason] || (reason ? String(reason) : "");
}

export const confirmMatches = (typed, expected) => typeof typed === "string" && typed === expected;
