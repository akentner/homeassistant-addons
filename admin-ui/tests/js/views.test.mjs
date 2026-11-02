import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { install, findAll, findByText, prop, settle } from "./fakedom.mjs";
import { auditNames, auditTables } from "./a11y_audit.mjs";

const doc = install();
const STATIC = new URL("../../app/web/static/", import.meta.url);

// ---- window / location stub with a controllable hashchange ----
const handlers = new Set();
globalThis.window = {
  addEventListener: (type, fn) => type === "hashchange" && handlers.add(fn),
  removeEventListener: (type, fn) => type === "hashchange" && handlers.delete(fn),
};
globalThis.location = { hash: "" };
const navigate = async (hash) => {
  globalThis.location.hash = hash;
  for (const fn of [...handlers]) fn({});
  await settle();
};

// ---- fetch stub ----
let calls = [];
let healthPayload = { status: "ok", addon_version: "0.1.0-0", lib_version: "0.1.0" };
let healthFails = false;
globalThis.fetch = async (url, init = {}) => {
  const method = init.method || "GET";
  calls.push({ method, url });
  if (url === "api/health") {
    if (healthFails) return { ok: false, status: 500, json: async () => ({ error: "internal_error" }) };
    return { ok: true, status: 200, json: async () => healthPayload };
  }
  return { ok: false, status: 404, json: async () => ({ error: "not_found" }) };
};

const { html, render } = await import(new URL("lib/ui.mjs", STATIC));
const { setLang } = await import(new URL("lib/i18n.mjs", STATIC));
const { App, VIEWS, ThemeChip } = await import(new URL("app.mjs", STATIC));
setLang("en");

// ---- HA wiring stubs ----
function makeHa(syncStatus = { active: false, mode: null }) {
  const log = [];
  const listeners = new Set();
  const ha = {
    log,
    bridge: {
      getState: () => ({ kiosk: false }),
      subscribe: () => () => {},
      toggleMenu() {},
      start: () => log.push("bridge.start"),
      dispose: () => log.push("bridge.dispose"),
    },
    sync: {
      status: () => syncStatus,
      subscribe: (fn) => {
        listeners.add(fn);
        return () => listeners.delete(fn);
      },
      start: () => log.push("sync.start"),
      dispose: () => log.push("sync.dispose"),
    },
    setStatus(next) {
      syncStatus = next;
      listeners.forEach((fn) => fn());
    },
  };
  return ha;
}

const fakeLoad = async (id) => ({ default: () => html`<p class="fake-view">view ${id}</p>` });

async function mountApp({ ha = makeHa(), load = fakeLoad, hash = "" } = {}) {
  calls = [];
  globalThis.location.hash = hash;
  const root = doc.createElement("div");
  render(html`<${App} ha=${ha} load=${load} />`, root);
  await settle();
  return { root, ha };
}

test("the health badge shows ok and the request URL is relative", async () => {
  healthPayload = { status: "ok", addon_version: "0.1.0-0", lib_version: "0.1.0" };
  healthFails = false;
  const { root } = await mountApp();
  assert.equal(findByText(root, "span", "OK").length, 1);
  assert.equal(findByText(root, "h1", "Admin UI").length, 1);
  assert.match(root.textContent, /Add-on 0\.1\.0-0/);
  assert.ok(calls.some((c) => c.url === "api/health" && c.method === "GET"));
  assert.ok(!/^(\/|[a-z][a-z0-9+.-]*:)/i.test(calls[0].url));
});

test("hostile health strings stay text nodes", async () => {
  healthPayload = { status: "<b>x</b>", addon_version: "<i>v</i>", lib_version: "0" };
  const { root } = await mountApp();
  assert.equal(findAll(root, (n) => n.localName === "b" || n.localName === "i").length, 0);
  assert.ok(root.textContent.includes("<b>x</b>"));
  healthPayload = { status: "ok", addon_version: "0.1.0-0", lib_version: "0.1.0" };
});

test("a failing health request renders the error badge", async () => {
  healthFails = true;
  const { root } = await mountApp();
  healthFails = false;
  assert.equal(findByText(root, "span", "Error").length, 1);
});

test("topbar, navigation, main region and language switch render", async () => {
  const { root } = await mountApp();
  assert.equal(findAll(root, (n) => n.localName === "header" && n.className === "topbar").length, 1);
  const links = findAll(root, (n) => n.localName === "a" && n.className.includes("tab"));
  assert.deepEqual(
    links.map((a) => a.getAttribute("href")),
    VIEWS.map((v) => `#/${v.id}`),
  );
  assert.equal(findAll(root, (n) => n.localName === "main").length, 1);
  assert.equal(findAll(root, (n) => n.localName === "select" && n.className === "lang-switch").length, 1);
  assert.equal(auditNames(root).length, 0);
});

test("the default route is the gallery, an unknown or hostile hash falls back to it", async () => {
  const seen = [];
  const load = async (id) => {
    seen.push(id);
    return fakeLoad(id);
  };
  const { root } = await mountApp({ load });
  assert.deepEqual(seen, ["gallery"]);
  assert.match(root.textContent, /view gallery/);
  await navigate("#/../../x");
  assert.deepEqual(seen.at(-1), "gallery");
  await navigate("#/nope");
  assert.ok(seen.every((id) => VIEWS.some((v) => v.id === id)), seen.join());
});

test("hashchange loads the routed view and marks its tab active", async () => {
  const { root } = await mountApp();
  await navigate("#/crud");
  assert.match(root.textContent, /view crud/);
  const active = findAll(root, (n) => n.localName === "a" && n.className.includes("active"));
  assert.equal(active.length, 1);
  assert.equal(active[0].getAttribute("href"), "#/crud");
});

test("a failing view import shows the localized error", async () => {
  const { root } = await mountApp({
    load: async () => {
      throw new Error("boom detail");
    },
  });
  assert.match(root.textContent, /This view could not be loaded/);
  assert.ok(!root.textContent.includes("boom detail"));
});

test("a view that throws while rendering is caught by the boundary", async () => {
  const { root } = await mountApp({
    load: async () => ({
      default: () => {
        throw new Error("render boom");
      },
    }),
  });
  assert.match(root.textContent, /could not be displayed/);
});

test("ThemeChip shows the own theme without sync and the mode with an active sync", async () => {
  const ha = makeHa({ active: false, mode: null });
  const root = doc.createElement("div");
  render(html`<${ThemeChip} sync=${ha.sync} />`, root);
  await settle();
  assert.equal(findByText(root, "span", "Own theme").length, 1);
  ha.setStatus({ active: true, mode: "dark" });
  await settle();
  assert.equal(findByText(root, "span", "Theme: dark").length, 1);
});

test("HA bridge and theme sync are started and disposed with the app", async () => {
  const { root, ha } = await mountApp();
  assert.deepEqual(ha.log.filter((e) => e.endsWith("start")).sort(), ["bridge.start", "sync.start"]);
  render(null, root);
  await settle();
  assert.deepEqual(ha.log.filter((e) => e.endsWith("dispose")).sort(), ["bridge.dispose", "sync.dispose"]);
});

test("the app works without any embedding parent (real bridge and sync, nothing injected)", async () => {
  calls = [];
  const saved = globalThis.window;
  const win = { ...saved, document: doc, location: { hash: "" } };
  win.parent = win;
  globalThis.window = win;
  const root = doc.createElement("div");
  render(html`<${App} load=${fakeLoad} />`, root);
  await settle();
  assert.equal(findByText(root, "span", "Own theme").length, 1);
  render(null, root);
  globalThis.window = saved;
});

test("app.mjs imports only public lib modules and never lib/vendor", () => {
  const src = readFileSync(new URL("app.mjs", STATIC), "utf8");
  for (const m of src.matchAll(/from\s+"(\.[^"]+)"/g)) {
    assert.ok(!m[1].includes("vendor"), m[1]);
    assert.ok(existsSync(new URL(m[1], STATIC)), m[1]);
  }
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
