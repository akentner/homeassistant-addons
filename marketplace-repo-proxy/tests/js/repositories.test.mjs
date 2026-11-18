import test from "node:test";
import assert from "node:assert/strict";
import { install, findAll, prop, settle } from "./fakedom.mjs";

const doc = install();
const STATIC = new URL("../../app/web/static/", import.meta.url);

// ---- timers: capture the polling interval instead of scheduling it ----
const intervals = [];
globalThis.setInterval = (fn, ms) => {
  const entry = { fn, ms, cleared: false };
  intervals.push(entry);
  return entry;
};
globalThis.clearInterval = (entry) => {
  if (entry) entry.cleared = true;
};
const activePoll = () => intervals.filter((i) => !i.cleared).at(-1);

// ---- fixtures (public repo: placeholders only) ----
const NOW = Date.UTC(2026, 10, 18, 12, 0, 0);
const repo = (over = {}) => ({
  repository: "example-org/private-addons",
  branch: "main",
  branch_source: "configured",
  status: "ok",
  message: "",
  last_attempt: "2026-11-18T11:55:00Z",
  last_success: "2026-11-18T11:55:00Z",
  last_change: "2026-11-18T10:00:00Z",
  head: "0123456789ab",
  addons: ["demo"],
  registration: null,
  ...over,
});
const sync = (over = {}) => ({
  state: "idle",
  last_started: "2026-11-18T11:54:00Z",
  last_finished: "2026-11-18T11:55:00Z",
  next_due: "2026-11-18T12:10:00Z",
  interval_minutes: 15,
  reason: "interval",
  requested: false,
  ...over,
});
const overview = ({ repositories = [repo()], syncOver = {}, status_available = true } = {}) => ({
  now_ms: NOW,
  status_available,
  sync: sync(syncOver),
  repositories,
});

// ---- recording fetch stub ----
const reply = (status, data) => ({ ok: status < 400, status, json: async () => data });
let calls = [];
let routes = {};
const setRoutes = (over = {}) => {
  routes = {
    overview: async () => reply(200, overview()),
    sync: async () => reply(202, { requested: true }),
    meta: async () => reply(200, { version: null }),
    ...over,
  };
};
setRoutes();
globalThis.fetch = async (url, init = {}) => {
  calls.push({ method: init.method || "GET", url, body: init.body });
  const name = String(url).replace(/^api\//, "").split("?")[0];
  const handler = routes[name];
  return handler ? handler(init) : reply(404, { error: "not_found" });
};

const { html, render, Toasts } = await import(new URL("vendor/admin-ui/ui.mjs", STATIC));
const { setLang } = await import(new URL("vendor/admin-ui/i18n.mjs", STATIC));
// Registers the add-on strings, as on the real page.
await import(new URL("app.mjs", STATIC));
const { default: Repositories } = await import(new URL("views/repositories.mjs", STATIC));
setLang("en");

async function mountView() {
  calls = [];
  intervals.length = 0;
  const root = doc.createElement("div");
  render(html`<div><${Repositories} /><${Toasts} /></div>`, root);
  await settle();
  return root;
}

const tag = (root, name) => findAll(root, (n) => n.localName === name);
const button = (root, text) => tag(root, "button").find((b) => b.textContent.trim() === text);
const toastTexts = (root) =>
  findAll(root, (n) => (n.className || "").split(" ").includes("toast")).map((n) => n.textContent.replace("×", "").trim());

test("tracer: Sync now sends one POST to a relative api/sync URL with the body {} and shows the toast", async () => {
  setRoutes();
  const root = await mountView();
  assert.ok(tag(root, "table").length === 1, "the table renders");
  const btn = button(root, "Sync now");
  assert.ok(btn, "Sync now button present");
  calls = [];
  btn.dispatch("click", { bubbles: true });
  await settle();
  const posts = calls.filter((c) => c.method === "POST");
  assert.equal(posts.length, 1);
  assert.ok(posts[0].url.endsWith("api/sync"), posts[0].url);
  assert.ok(!posts[0].url.startsWith("/"), "relative URL");
  assert.equal(posts[0].body, "{}");
  assert.ok(toastTexts(root).includes("Sync requested"), toastTexts(root).join("|"));
  assert.ok(calls.some((c) => c.method === "GET" && c.url.endsWith("api/overview")), "overview refreshed after the request");
  assert.equal(prop(button(root, "Sync now"), "disabled"), false);
  render(null, root);
});

test("Sync now failure shows the localised error text, never the server message", async () => {
  setRoutes({ sync: async () => reply(400, { error: "bad_request", message: "<b>x</b> server text" }) });
  const root = await mountView();
  const before = toastTexts(root).length; // toasts of earlier tests are still on the module-level stack
  button(root, "Sync now").dispatch("click", { bubbles: true });
  await settle();
  const texts = toastTexts(root).slice(before);
  assert.equal(texts.length, 1);
  assert.equal(texts[0], "The request was invalid");
  assert.ok(!texts.some((s) => s.includes("server text")), texts.join("|"));
  assert.ok(!texts.includes("Sync requested"));
  assert.equal(findAll(root, (n) => n.localName === "b").length, 0);
  render(null, root);
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
