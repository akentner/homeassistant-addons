import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { install, findAll, findByText, prop, settle } from "./fakedom.mjs";

const doc = install();
const STATIC = new URL("../../app/web/static/", import.meta.url);
const { html, render } = await import(new URL("vendor/preact-htm.mjs", STATIC));
const { VIEWS } = await import(new URL("app.mjs", STATIC));
const { RESET_PHRASES } = await import(new URL("lib/model.mjs", STATIC));

const TOKEN_VALUE = "tk_" + "a1b2c3d4e5".repeat(3).slice(0, 29);
const fixtures = {
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

let calls = [];
globalThis.fetch = async (url, init = {}) => {
  const method = init.method || "GET";
  calls.push({ method, url, body: init.body ? JSON.parse(init.body) : undefined });
  const path = url.split("?")[0];
  const data = fixtures[`${method} ${path}`];
  const ok = data !== undefined;
  return { ok, status: ok ? 200 : 404, json: async () => (ok ? data : { error: "not_found", message: "no fixture" }) };
};

async function mount(id, params = {}) {
  calls = [];
  const mod = await import(new URL(`views/${id}.mjs`, STATIC));
  const root = doc.createElement("div");
  render(html`<${mod.default} params=${params} />`, root);
  await settle();
  return root;
}

const all = (root) => root.textContent;

test("every view file exists, exports meta and a default function", async () => {
  assert.equal(VIEWS.length, 7);
  for (const v of VIEWS) {
    const file = new URL(`views/${v.id}.mjs`, STATIC);
    assert.ok(existsSync(file), v.id);
    const mod = await import(file);
    assert.equal(mod.meta.id, v.id);
    assert.equal(typeof mod.default, "function");
    const src = readFileSync(file, "utf8");
    for (const m of src.matchAll(/from\s+"(\.[^"]+)"/g)) assert.ok(existsSync(new URL(m[1], file)), `${v.id}: ${m[1]}`);
  }
});

test("users view: protected row has disabled Delete, hostile name stays text", async () => {
  const root = await mount("users");
  const text = all(root);
  assert.match(text, /admin from options/);
  assert.match(text, /<b>alice<\/b>/);
  assert.equal(findAll(root, (n) => n.localName === "b").length, 0);
  const rows = findAll(root, (n) => n.localName === "tr");
  const adminRow = rows.find((r) => r.textContent.includes("options_admin") || r.textContent.includes("admin from"));
  const del = findByText(adminRow, "button", "Delete")[0];
  assert.ok(del && prop(del, "disabled"));
  const aliceRow = rows.find((r) => r.textContent.includes("alice"));
  assert.ok(!prop(findByText(aliceRow, "button", "Delete")[0], "disabled"));
});

test("acl view renders rules", async () => {
  const text = all(await mount("acl"));
  assert.match(text, /alerts/);
  assert.match(text, /news-\*/);
  assert.match(text, /everyone/);
});

test("matrix view has everyone column and a row per topic", async () => {
  const root = await mount("matrix");
  const heads = findAll(root, (n) => n.localName === "th").map((n) => n.textContent.trim());
  assert.ok(heads.includes("everyone"));
  const body = findAll(root, (n) => n.localName === "tbody")[0];
  assert.equal(findAll(body, (n) => n.localName === "tr").length, 2);
});

test("tokens view: no token value before reveal, once after, gone after hide", async () => {
  const root = await mount("tokens");
  assert.match(all(root), /tk_abcde/);
  assert.match(all(root), /phone/);
  assert.ok(!/tk_[a-z0-9]{29}/.test(all(root)));
  const inputValues = () => findAll(root, (n) => n.localName === "input").map((n) => prop(n, "value"));
  findByText(root, "button", "Reveal")[0].dispatch("click");
  await settle();
  assert.equal(inputValues().filter((v) => v === TOKEN_VALUE).length, 1);
  assert.ok(calls.some((c) => c.url === "api/tokens/reveal" && c.body.id === "tk_abcde"));
  findByText(root, "button", "Hide")[0].dispatch("click");
  await settle();
  assert.equal(inputValues().filter((v) => v === TOKEN_VALUE).length, 0);
  assert.ok(!all(root).includes(TOKEN_VALUE));
});

test("tools view renders lookup form and generator", async () => {
  const root = await mount("tools");
  assert.match(all(root), /Effective rights/);
  assert.equal(findByText(root, "button", "Generate").length, 1);
  findByText(root, "button", "Generate")[0].dispatch("click");
  await settle();
  assert.ok(findAll(root, (n) => n.localName === "input").some((n) => prop(n, "value") === "abcdefghijklmnop"));
});

test("health view shows status and formatted sizes", async () => {
  const text = all(await mount("health"));
  assert.match(text, /ok/);
  assert.match(text, /2\.0 KiB/);
  assert.match(text, /1\.0 MiB/);
  assert.match(text, /Test publish/);
});

test("data view: reset needs the exact phrase, then posts it", async () => {
  const root = await mount("data");
  assert.match(all(root), /Download export/);
  assert.match(all(root), /auth-20261102T100000Z\.db/);
  assert.equal(findAll(root, (n) => n.localName === "button" && /Reset|Clear/.test(n.textContent)).length, 3);
  findByText(root, "button", "Reset ACLs")[0].dispatch("click");
  await settle();
  const confirm = findByText(root, "button", "Execute")[0];
  assert.ok(prop(confirm, "disabled"));
  const input = findAll(root, (n) => n.localName === "input" && prop(n, "type") === "text").pop();
  input.value = "reset acl";
  input.dispatch("input");
  await settle();
  assert.ok(prop(findByText(root, "button", "Execute")[0], "disabled"));
  input.value = RESET_PHRASES.acls;
  input.dispatch("input");
  await settle();
  const ready = findByText(root, "button", "Execute")[0];
  assert.ok(!prop(ready, "disabled"));
  ready.dispatch("click");
  await settle();
  const call = calls.find((c) => c.method === "POST" && c.url === "api/reset/acls");
  assert.deepEqual(call.body, { confirm: "reset acls" });
});

test("all requested URLs are relative", async () => {
  for (const v of VIEWS) await mount(v.id);
  assert.ok(calls.length > 0);
  for (const c of calls) assert.ok(!/^(\/|[a-z][a-z0-9+.-]*:)/i.test(c.url), c.url);
});

// Preact/toast timers can outlive the tests; end the worker once the results are reported.
test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
