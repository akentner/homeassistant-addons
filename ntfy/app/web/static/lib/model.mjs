// Pure helpers (no DOM, no preact, no fetch). Mirrors ntfy/app/contract.py; keep both in sync.

export const PERMISSIONS = ["rw", "ro", "wo", "deny"];
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

export function expiryState(ts, nowMs = Date.now()) {
  if (!ts) return "never";
  return ts * 1000 <= nowMs ? "expired" : "active";
}

// ---- key-free logic for the views (additive; the views map kinds to i18n keys) ----

const PROTECTION_KINDS = ["last_admin", "options_admin", "anonymous"];

export function protectionKind(reason) {
  return PROTECTION_KINDS.includes(reason) ? reason : "other";
}

const EFFECTIVE_KINDS = { admin: "admin", "user-rule": "user_rule", "everyone-rule": "everyone_rule" };

export function effectiveExplain(eff) {
  const src = eff && eff.source ? eff.source : {};
  const kind = EFFECTIVE_KINDS[src.kind] || "default";
  if (kind === "user_rule" || kind === "everyone_rule") {
    const rule = src.rule || {};
    return { kind, params: { user: rule.user, topic: rule.topic, permission: rule.permission } };
  }
  return { kind, params: {} };
}
