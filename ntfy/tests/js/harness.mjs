// Shared view-test harness: fake DOM, English language, lib + ntfy strings, mutable fixtures, failure injection and a
// recording fetch stub. Importing this module has side effects (it installs the fake DOM and globalThis.fetch).
import { install } from "./fakedom.mjs";

export { findAll, findByText, prop, settle } from "./fakedom.mjs";

export const doc = install();
export const STATIC = new URL("../../app/web/static/", import.meta.url);

const { html, render } = await import(new URL("lib/ui.mjs", STATIC));
const i18n = await import(new URL("vendor/admin-ui/i18n.mjs", STATIC));
const { default: de } = await import(new URL("strings.de.mjs", STATIC));
const { default: en } = await import(new URL("strings.en.mjs", STATIC));
const { settle } = await import("./fakedom.mjs");

i18n.registerStrings({ de, en });
i18n.setLang("en");

export { html, render };
export const { setLang } = i18n;

export const TOKEN_VALUE = "tk_" + "a1b2c3d4e5".repeat(3).slice(0, 29);

// Keyed "METHOD path" (percent-decoded paths work too). Tests may mutate this object.
export const fixtures = {
  "GET api/users": {
    users: [
      { name: "everyone", role: "anonymous", tier: null, origin: "gui", provisioned: false, protected: true,
        protected_reason: "anonymous", acl_count: 1, token_count: 0 },
      { name: "admin", role: "admin", tier: null, origin: "options", provisioned: true, protected: true,
        protected_reason: "options_admin", acl_count: 0, token_count: 0 },
      { name: "<b>alice</b>", role: "user", tier: null, origin: "gui", provisioned: false, protected: false,
        protected_reason: null, acl_count: 2, token_count: 1 },
    ],
  },
  "GET api/acl": {
    rules: [
      { user: "<b>alice</b>", topic: "alerts", permission: "rw", origin: "gui" },
      { user: "everyone", topic: "news-*", permission: "ro", origin: "gui" },
    ],
  },
  "GET api/tokens": {
    tokens: [
      { id: "tk_abcde", user: "<b>alice</b>", prefix: "tk_abcde", label: "phone", expires: 0, expires_at: null,
        last_access: 0, last_origin: "", origin: "gui" },
    ],
  },
  "POST api/tokens/reveal": { value: TOKEN_VALUE },
  "GET api/health": {
    status: "ok", addon_version: "2.36.0-0", ntfy: { healthy: true, role: "server" },
    db: { schema_version: 10, supported: true, size_bytes: 2048, cache_size_bytes: 1048576, error: null },
    counts: { users: 3, acl_rules: 2, tokens: 1 },
  },
  "GET api/backups": {
    backups: [{ name: "auth-20261102T100000Z.db", size_bytes: 4096, created: "2026-11-02T10:00:00Z", reason: "manual" }],
  },
  "POST api/reset/acls": { done: true, backup: "auth-x.db" },
  "GET api/topics/suggest": { topic: "abcdefghijklmnop", acl: [{ user: "everyone", permission: "wo" }] },
};

// Same keys as fixtures: {status, error, message} makes that request fail with an {error, message} body.
export const failures = {};

let recorded = [];
export const calls = () => recorded;

globalThis.fetch = async (url, init = {}) => {
  const method = init.method || "GET";
  recorded.push({ method, url, body: init.body ? JSON.parse(init.body) : undefined });
  const path = url.split("?")[0];
  let decoded = path;
  try {
    decoded = decodeURIComponent(path);
  } catch {
    // keep the raw path
  }
  const keys = [`${method} ${path}`, `${method} ${decoded}`];
  const fail = keys.map((k) => failures[k]).find(Boolean);
  if (fail) {
    return { ok: false, status: fail.status, json: async () => ({ error: fail.error, message: fail.message ?? fail.error }) };
  }
  const key = keys.find((k) => fixtures[k] !== undefined);
  if (key === undefined) {
    return { ok: false, status: 404, json: async () => ({ error: "not_found", message: "no fixture" }) };
  }
  return { ok: true, status: 200, json: async () => fixtures[key] };
};

export async function mount(id, params = {}, { lang = "en" } = {}) {
  setLang(lang);
  recorded = [];
  const mod = await import(new URL(`views/${id}.mjs`, STATIC));
  const root = doc.createElement("div");
  render(html`<${mod.default} params=${params} />`, root);
  await settle();
  return root;
}

export const all = (root) => root.textContent;
