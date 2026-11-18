import test from "node:test";
import assert from "node:assert/strict";
import { install, findAll, prop, settle } from "./fakedom.mjs";
import { auditNames, auditTables } from "./a11y_audit.mjs";

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

globalThis.location = { hash: "#/repositories" };

const { html, render, Toasts } = await import(new URL("vendor/admin-ui/ui.mjs", STATIC));
const { setLang, t } = await import(new URL("vendor/admin-ui/i18n.mjs", STATIC));
const { formatRelative } = await import(new URL("vendor/admin-ui/format.mjs", STATIC));
// Importing app.mjs registers the add-on strings, as on the real page.
const { App } = await import(new URL("app.mjs", STATIC));
const { default: Repositories } = await import(new URL("views/repositories.mjs", STATIC));
const { default: en } = await import(new URL("strings.en.mjs", STATIC));
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

// ---- view: rows, status, sync state and poll cadence ----

const cls = (root, name) => findAll(root, (n) => (n.className || "").split(" ").includes(name));
const headers = (root) => tag(root, "th").map((th) => th.textContent.trim());
const bodyRows = (root) => tag(tag(root, "tbody")[0], "tr");
// Cell of the row whose repository column starts with `name`, in the column titled `title`.
function cell(root, name, title) {
  const index = headers(root).indexOf(title);
  assert.ok(index >= 0, `column ${title} missing`);
  const row = bodyRows(root).find((tr) => tag(tr, "td")[0].textContent.trim().startsWith(name));
  assert.ok(row, `row ${name} missing`);
  return tag(row, "td")[index];
}
const syncLine = (root) => cls(root, "sync-line")[0];
const visibleText = (root) => root.textContent;

test("view: one row per repository with the status text from the table; a hostile message stays text", async () => {
  setRoutes({
    overview: async () =>
      reply(
        200,
        overview({
          repositories: [
            repo(),
            repo({ repository: "example-org/other-addons", status: "fetch_failed", message: "<b>x</b>" }),
          ],
        }),
      ),
  });
  const root = await mountView();
  assert.equal(bodyRows(root).length, 2);
  assert.equal(cls(cell(root, "example-org/private-addons", "Status"), "badge")[0].textContent.trim(), en["mrp.status.ok"]);
  const failed = cell(root, "example-org/other-addons", "Status");
  assert.equal(cls(failed, "badge")[0].textContent.trim(), en["mrp.status.fetch_failed"]);
  assert.ok(failed.textContent.includes("<b>x</b>"));
  assert.equal(tag(root, "b").length, 0, "markup in data never becomes an element");
  render(null, root);
});

test("view: status_available false shows the no-status hint and no error note", async () => {
  const pending = repo({ status: null, message: "", last_success: null, head: null, addons: [], branch_source: null });
  setRoutes({ overview: async () => reply(200, overview({ status_available: false, repositories: [pending] })) });
  const root = await mountView();
  assert.ok(visibleText(root).includes(en["mrp.repo.no_status"]));
  assert.equal(cls(root, "notice").length, 0);
  assert.equal(bodyRows(root).length, 1);
  render(null, root);
});

test("view: idle sync polls every 15 s, shows the idle state and the next due time, button enabled", async () => {
  setRoutes();
  const root = await mountView();
  assert.equal(activePoll().ms, 15000);
  const line = syncLine(root).textContent;
  assert.ok(line.includes(en["mrp.sync.idle"]), line);
  assert.ok(line.includes(formatRelative(Date.UTC(2026, 10, 18, 12, 10), "en", NOW)), line);
  assert.equal(prop(button(root, "Sync now"), "disabled"), false);
  render(null, root);
});

test("view: a running sync polls every 2 s, shows running and disables Sync now", async () => {
  setRoutes({ overview: async () => reply(200, overview({ syncOver: { state: "running" } })) });
  const root = await mountView();
  assert.equal(activePoll().ms, 2000);
  assert.ok(syncLine(root).textContent.includes(en["mrp.sync.running"]));
  assert.equal(prop(button(root, "Sync now"), "disabled"), true);
  render(null, root);
});

test("view: a requested sync polls every 2 s, shows requested and disables Sync now", async () => {
  setRoutes({ overview: async () => reply(200, overview({ syncOver: { requested: true } })) });
  const root = await mountView();
  assert.equal(activePoll().ms, 2000);
  assert.ok(syncLine(root).textContent.includes(en["mrp.sync.requested"]));
  assert.equal(prop(button(root, "Sync now"), "disabled"), true);
  render(null, root);
});

test("view: the poll returns to 15 s once the running sync is over", async () => {
  let state = "running";
  setRoutes({ overview: async () => reply(200, overview({ syncOver: { state } })) });
  const root = await mountView();
  assert.equal(activePoll().ms, 2000);
  state = "idle";
  activePoll().fn();
  await settle();
  assert.equal(activePoll().ms, 15000);
  assert.equal(prop(button(root, "Sync now"), "disabled"), false);
  render(null, root);
});

// ---- registration column (D-19) ----

const REG_TITLE = () => en["mrp.reg.col"];

test("registration: no column and no note when every registration is null", async () => {
  setRoutes({ overview: async () => reply(200, overview({ repositories: [repo(), repo({ repository: "example-org/b" })] })) });
  const root = await mountView();
  assert.ok(REG_TITLE(), "column title key exists");
  assert.ok(!headers(root).includes(REG_TITLE()));
  assert.ok(!visibleText(root).includes(en["mrp.reg.leftover_note"]));
  render(null, root);
});

test("registration: a leftover row shows the column, the badge, the detail as text and the leftover note", async () => {
  const leftover = repo({ registration: { state: "leftover", detail: "<b>x</b>" } });
  setRoutes({ overview: async () => reply(200, overview({ repositories: [leftover] })) });
  const root = await mountView();
  assert.ok(headers(root).includes(REG_TITLE()));
  const td = cell(root, "example-org/private-addons", REG_TITLE());
  assert.equal(cls(td, "badge")[0].textContent.trim(), en["mrp.reg.leftover"]);
  assert.ok(td.textContent.includes("<b>x</b>"));
  assert.equal(tag(root, "b").length, 0);
  assert.ok(en["mrp.reg.leftover_note"] && visibleText(root).includes(en["mrp.reg.leftover_note"]));
  render(null, root);
});

test("registration: a mix of data and null shows the column, an empty cell for null and no leftover note", async () => {
  const rows = [repo({ registration: { state: "registered" } }), repo({ repository: "example-org/b", registration: null })];
  setRoutes({ overview: async () => reply(200, overview({ repositories: rows })) });
  const root = await mountView();
  assert.ok(headers(root).includes(REG_TITLE()));
  assert.equal(cell(root, "example-org/private-addons", REG_TITLE()).textContent.trim(), en["mrp.reg.registered"]);
  assert.equal(cell(root, "example-org/b", REG_TITLE()).textContent.trim(), "");
  assert.ok(!visibleText(root).includes(en["mrp.reg.leftover_note"]));
  render(null, root);
});

test("registration: each of the four states renders its own text", async () => {
  const states = ["registered", "missing", "leftover", "error"];
  const rows = states.map((state) => repo({ repository: `example-org/${state}`, registration: { state } }));
  setRoutes({ overview: async () => reply(200, overview({ repositories: rows })) });
  const root = await mountView();
  const texts = states.map((state) => cls(cell(root, `example-org/${state}`, REG_TITLE()), "badge")[0].textContent.trim());
  assert.deepEqual(texts, states.map((state) => en[`mrp.reg.${state}`]));
  assert.equal(new Set(texts).size, 4);
  render(null, root);
});

// ---- branch source and add-on names ----

test("branch source comes from the literal key map and add-on names render as text next to the count", async () => {
  const rows = [
    repo({ branch_source: "upstream_default", addons: ["demo", "<b>x</b>"] }),
    repo({ repository: "example-org/b", branch: "release", branch_source: "configured" }),
  ];
  setRoutes({ overview: async () => reply(200, overview({ repositories: rows })) });
  const root = await mountView();
  assert.ok(en["mrp.repo.branch.upstream_default"] && en["mrp.repo.branch.configured"]);
  const first = cell(root, "example-org/private-addons", "Repository").textContent;
  assert.ok(first.includes(t("mrp.repo.branch.upstream_default", { branch: "main" })), first);
  const second = cell(root, "example-org/b", "Repository").textContent;
  assert.ok(second.includes(t("mrp.repo.branch.configured", { branch: "release" })), second);
  const addons = cell(root, "example-org/private-addons", "Add-ons").textContent;
  assert.ok(addons.includes("2 add-ons"), addons);
  assert.ok(addons.includes("demo"), addons);
  assert.ok(addons.includes("<b>x</b>"), addons);
  assert.equal(tag(root, "b").length, 0);
  render(null, root);
});

// ---- top bar version from api/meta (D-30) ----

function makeHa() {
  return {
    bridge: { getState: () => ({ kiosk: false }), subscribe: () => () => {}, toggleMenu() {}, start() {}, dispose() {} },
    sync: { start() {}, dispose() {} },
  };
}

async function mountApp() {
  calls = [];
  intervals.length = 0;
  const root = doc.createElement("div");
  render(html`<${App} ha=${makeHa()} />`, root);
  await settle(10);
  return root;
}
const header = (root) => tag(root, "header")[0];

test("top bar: api/meta version 0.1.0-3 is shown and api/meta is loaded once over several poll ticks", async () => {
  setRoutes({ meta: async () => reply(200, { version: "0.1.0-3" }) });
  const root = await mountApp();
  assert.ok(header(root).textContent.includes("0.1.0-3"));
  assert.equal(cls(header(root), "topbar-version").length, 1);
  for (let i = 0; i < 3; i++) {
    activePoll().fn();
    await settle();
  }
  assert.equal(calls.filter((c) => c.url.endsWith("api/meta")).length, 1);
  assert.ok(calls.filter((c) => c.url.endsWith("api/overview")).length >= 4);
  assert.equal(tag(root, "table").length, 1);
  render(null, root);
});

for (const [name, handler] of [
  ["null version", async () => reply(200, { version: null })],
  ["failed api/meta", async () => reply(500, { error: "internal_error" })],
]) {
  test(`top bar: ${name} renders no version element and the view still renders`, async () => {
    setRoutes({ meta: handler });
    const root = await mountApp();
    assert.equal(cls(header(root), "topbar-version").length, 0);
    assert.equal(cls(header(root), "notice").length, 0);
    assert.equal(tag(root, "table").length, 1);
    assert.equal(calls.filter((c) => c.url.endsWith("api/meta")).length, 1);
    render(null, root);
  });
}

// ---- accessibility audits ----

for (const [name, rows] of [
  ["all-null registration", [repo(), repo({ repository: "example-org/b", status: "fetch_failed", message: "x" })]],
  [
    "registration data",
    [repo({ registration: { state: "leftover", detail: "x" } }), repo({ repository: "example-org/b", registration: null })],
  ],
]) {
  test(`a11y: named controls and scoped table headers with ${name}`, async () => {
    setRoutes({ overview: async () => reply(200, overview({ repositories: rows })) });
    const root = await mountView();
    assert.equal(tag(root, "table").length, 1);
    assert.deepEqual(auditNames(root), []);
    assert.deepEqual(auditTables(root), []);
    render(null, root);
  });
}

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
