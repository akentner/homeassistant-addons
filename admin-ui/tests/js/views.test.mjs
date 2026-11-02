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
const reply = (status, data) => ({ ok: status < 400, status, json: async () => data });
const failure = (status, code) => reply(status, { error: code, message: `backend text for ${code}` });
const FAIL_STATUS = {
  bad_request: 400, confirmation_required: 400, ingress_only: 403, not_found: 404, method_not_allowed: 405,
  conflict: 409, protected: 409, payload_too_large: 413, internal_error: 500, teapot: 418,
};
const seedItems = () => [
  { id: "1", name: "alpha", note: "First", locked: false, created: 1700000000000 },
  { id: "2", name: "<b>alice</b>", note: "hostile", locked: false, created: 1710000000000 },
  { id: "3", name: "locked", note: "protected", locked: true, created: 1720000000000 },
];
let items = seedItems();
let nextId = 10;
const nameOk = (v) => typeof v === "string" && v.trim().length >= 1 && v.trim().length <= 40;
const taken = (name, except) => items.some((i) => i.name.toLowerCase() === name.toLowerCase() && i.id !== except);

// In-JS mirror of the Python demo API (status codes and error codes of C3).
globalThis.fetch = async (url, init = {}) => {
  const method = init.method || "GET";
  const body = init.body ? JSON.parse(init.body) : undefined;
  calls.push({ method, url, body });
  const path = url.split("?")[0];
  if (path === "api/health") return healthFails ? failure(500, "internal_error") : reply(200, healthPayload);
  if (method === "GET" && path === "api/items") return reply(200, { items: items.map((i) => ({ ...i })) });
  if (method === "POST" && path === "api/items") {
    if (!nameOk(body.name)) return failure(400, "bad_request");
    if (taken(body.name.trim())) return failure(409, "conflict");
    const item = { id: String(nextId++), name: body.name.trim(), note: body.note || "", locked: false, created: 1730000000000 };
    items.push(item);
    return reply(201, item);
  }
  const m = /^api\/items\/(\w+)$/.exec(path);
  if (m) {
    const item = items.find((i) => i.id === m[1]);
    if (!item) return failure(404, "not_found");
    if (item.locked) return failure(409, "protected");
    if (method === "PUT") {
      if (!nameOk(body.name)) return failure(400, "bad_request");
      if (taken(body.name.trim(), item.id)) return failure(409, "conflict");
      item.name = body.name.trim();
      item.note = body.note ?? item.note;
      return reply(200, item);
    }
    if (method === "DELETE") {
      if (!body || body.confirm !== item.name) return failure(400, "confirmation_required");
      items = items.filter((i) => i !== item);
      return { ok: true, status: 204 };
    }
  }
  const f = /^api\/fail\/(\w+)$/.exec(path);
  if (method === "GET" && f) return failure(FAIL_STATUS[f[1]] || 404, FAIL_STATUS[f[1]] ? f[1] : "not_found");
  if (method === "GET" && path === "api/slow") return reply(200, { ok: true, waited_ms: 600 });
  return failure(404, "not_found");
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


// ---- view helpers ----
const { Toasts } = await import(new URL("lib/ui.mjs", STATIC));

async function mountView(id, { params = {}, ha = makeHa(), lang = "en" } = {}) {
  setLang(lang);
  calls = [];
  items = seedItems();
  const mod = await import(new URL(`views/${id}.mjs`, STATIC));
  const root = doc.createElement("div");
  render(html`<div><${mod.default} params=${params} ha=${ha} /><${Toasts} /></div>`, root);
  await settle();
  return root;
}
const click = async (root, tag, text) => {
  const node = findByText(root, tag, text)[0];
  assert.ok(node, `${tag} "${text}" not found`);
  node.dispatch("click");
  await settle();
  return node;
};
const roleOf = (root, role) => findAll(root, (n) => n.getAttribute && n.getAttribute("role") === role);

// ---- gallery ----
test("gallery: every component section and all badge kinds render", async () => {
  const root = await mountView("gallery");
  for (const heading of ["Badge", "Toast", "Modal", "Confirm dialog", "Copy field", "Data table", "Tabs", "Loading", "Error note", "Field"]) {
    assert.equal(findByText(root, "h2", heading).length, 1, heading);
  }
  const kinds = ["ok", "warn", "degraded", "error", "muted", "info"];
  for (const kind of kinds) {
    assert.ok(findAll(root, (n) => n.localName === "span" && n.className === `badge ${kind}`).length >= 1, kind);
  }
  assert.equal(roleOf(root, "status").length >= 1, true);
  assert.equal(findAll(root, (n) => n.localName === "table").length, 1);
  assert.equal(auditNames(root).length, 0);
  assert.equal(auditTables(root).length, 0);
});

test("gallery: the modal opens, closes with its action and with Escape", async () => {
  const root = await mountView("gallery");
  assert.equal(roleOf(root, "dialog").length, 0);
  const opener = await click(root, "button", "Open dialog");
  assert.equal(roleOf(root, "dialog").length, 1);
  assert.notEqual(doc.activeElement, opener);
  const dialog = roleOf(root, "dialog")[0];
  assert.ok(dialog.contains(doc.activeElement));
  await click(dialog, "button", "Close");
  assert.equal(roleOf(root, "dialog").length, 0);
  await click(root, "button", "Open dialog");
  doc.dispatch("keydown", { key: "Escape" });
  await settle();
  assert.equal(roleOf(root, "dialog").length, 0);
});

test("gallery: the dangerous confirm needs the exact phrase, the plain one does not", async () => {
  const root = await mountView("gallery");
  await click(root, "button", "Plain confirm");
  const plain = roleOf(root, "dialog")[0];
  assert.equal(prop(findByText(plain, "button", "Confirm")[0], "disabled"), false);
  await click(plain, "button", "Cancel");
  assert.equal(roleOf(root, "dialog").length, 0);

  await click(root, "button", "Dangerous confirm");
  const dlg = roleOf(root, "dialog")[0];
  const input = findAll(dlg, (n) => n.localName === "input")[0];
  assert.equal(prop(findByText(dlg, "button", "Delete")[0], "disabled"), true);
  for (const wrong of ["Delete", "delet", "delete "]) {
    input.value = wrong;
    input.dispatch("input", { target: input });
    await settle();
    assert.equal(prop(findByText(dlg, "button", "Delete")[0], "disabled"), true, wrong);
  }
  input.value = "delete";
  input.dispatch("input", { target: input });
  await settle();
  assert.equal(prop(findByText(dlg, "button", "Delete")[0], "disabled"), false);
  findByText(dlg, "button", "Delete")[0].dispatch("click");
  await settle();
  assert.equal(roleOf(root, "dialog").length, 0);
  assert.ok(root.textContent.includes("Confirmed"));
});

test("gallery: toasts appear with the right roles", async () => {
  const root = await mountView("gallery");
  await click(root, "button", "Error toast");
  assert.ok(roleOf(root, "alert").some((n) => n.textContent.includes("Something went wrong")));
  await click(root, "button", "Success toast");
  assert.ok(roleOf(root, "status").some((n) => n.textContent.includes("Saved successfully")));
  await click(root, "button", "Info toast");
  assert.ok(root.textContent.includes("For your information"));
});

test("gallery: tabs change with the arrow keys", async () => {
  const root = await mountView("gallery");
  const tabs = () => roleOf(root, "tab");
  const selected = () => tabs().findIndex((n) => n.getAttribute("aria-selected") === "true");
  assert.equal(selected(), 0);
  assert.ok(root.textContent.includes("Panel of tab one"));
  tabs()[0].dispatch("keydown", { key: "ArrowRight" });
  await settle();
  assert.equal(selected(), 1);
  assert.ok(root.textContent.includes("Panel of tab two"));
  tabs()[1].dispatch("keydown", { key: "ArrowLeft" });
  await settle();
  assert.equal(selected(), 0);
});

test("gallery: hostile names stay text, unknown error codes show [code], values are formatted", async () => {
  const root = await mountView("gallery");
  assert.equal(findAll(root, (n) => n.localName === "b").length, 0);
  assert.ok(root.textContent.includes("<b>bold</b> row"));
  assert.ok(root.textContent.includes("[teapot]"));
  assert.match(root.textContent, /2 KiB/);
  await click(root, "button", "Toggle known error");
  assert.ok(root.textContent.includes("conflicts with the current state"));
});

// ---- tokens ----
const TOKEN_VALUES = {
  light: { bg: "#f4f5f7", fg: "#1c1e21", card: "#ffffff", bd: "#dcdfe4", mut: "#586069", ok: "#176f2c", warn: "#8a5700",
    err: "#cf222e", acc: "#0969da", chip: "#eef0f3", hover: "#f0f2f5", shadow: "0 8px 28px rgba(0, 0, 0, 0.25)",
    "on-acc": "#ffffff", "on-err": "#ffffff" },
  dark: { bg: "#111315", fg: "#e6e8eb", card: "#1b1e21", bd: "#32363b", mut: "#9aa1aa", ok: "#3fb950", warn: "#d29922",
    err: "#f85149", acc: "#58a6ff", chip: "#23272b", hover: "#202428", shadow: "0 8px 28px rgba(0, 0, 0, 0.6)",
    "on-acc": "#0b1220", "on-err": "#ffffff" },
};
const withStyles = async (fn) => {
  const saved = globalThis.getComputedStyle;
  globalThis.getComputedStyle = (el) => ({
    getPropertyValue: (name) => (TOKEN_VALUES[el.getAttribute("data-theme")] || {})[name.slice(2)] || "",
  });
  try {
    return await fn();
  } finally {
    globalThis.getComputedStyle = saved;
  }
};

test("tokens: two isolated panels show every token with its resolved value", async () => {
  const root = await withStyles(() => mountView("tokens"));
  const panels = findAll(root, (n) => n.className.includes("theme-isolated"));
  assert.deepEqual(panels.map((n) => n.getAttribute("data-theme")), ["light", "dark"]);
  for (const panel of panels) {
    assert.equal(findAll(panel, (n) => n.className.startsWith("swatch swatch-")).length, 14);
    assert.ok(panel.textContent.includes("--on-err"));
  }
  assert.ok(panels[0].textContent.includes("#f4f5f7"));
  assert.ok(panels[1].textContent.includes("#111315"));
  assert.equal(auditNames(root).length, 0);
  assert.equal(auditTables(root).length, 0);
});

test("tokens: contrast ratios come from the resolved values with a pass/fail verdict", async () => {
  const root = await withStyles(() => mountView("tokens"));
  const [light] = findAll(root, (n) => n.className.includes("theme-isolated"));
  const row = findAll(light, (n) => n.localName === "tr").find((r) => r.textContent.startsWith("--fg / --bg"));
  assert.match(row.textContent, /\d+\.\d+:1/);
  assert.ok(row.textContent.includes("Pass"));
  const low = await withStyles(async () => {
    TOKEN_VALUES.light.mut = "#cccccc";
    try {
      return await mountView("tokens");
    } finally {
      TOKEN_VALUES.light.mut = "#586069";
    }
  });
  const lowRow = findAll(low, (n) => n.localName === "tr").find((r) => r.textContent.startsWith("--mut / --bg"));
  assert.ok(lowRow.textContent.includes("Fail"));
});

test("tokens: without computed styles or with unparsable values there is no ratio and no verdict", async () => {
  const root = await mountView("tokens");
  const rows = findAll(root, (n) => n.localName === "tr").filter((r) => r.textContent.includes(" / --"));
  assert.ok(rows.length > 0);
  assert.ok(rows.every((r) => !/Pass|Fail/.test(r.textContent) && !r.textContent.includes(":1")));
  const garbage = await withStyles(async () => {
    TOKEN_VALUES.light.fg = "not-a-color";
    try {
      return await mountView("tokens");
    } finally {
      TOKEN_VALUES.light.fg = "#1c1e21";
    }
  });
  const [light] = findAll(garbage, (n) => n.className.includes("theme-isolated"));
  const row = findAll(light, (n) => n.localName === "tr").find((r) => r.textContent.startsWith("--fg / --bg"));
  assert.ok(!/Pass|Fail/.test(row.textContent));
});

test("tokens: the note names the sync status and the view renders in German", async () => {
  const root = await mountView("tokens", { ha: makeHa({ active: true, mode: "dark" }) });
  assert.match(root.textContent, /Theme sync: dark/);
  const de = await mountView("tokens", { lang: "de" });
  assert.match(de.textContent, /Theme-Sync: aus/);
  assert.ok(findByText(de, "h2", "Hell").length === 1 && findByText(de, "h2", "Dunkel").length === 1);
  setLang("en");
});


// ---- language ----
const typeInto = async (node, value) => {
  node.value = value;
  node.dispatch("input", { target: node });
  await settle();
};
const inputById = (root, id) => findAll(root, (n) => n.localName === "input" && n.getAttribute("id") === id)[0];

test("language view: parameters, plurals, formatting and localized probe errors", async () => {
  const root = await mountView("language");
  const text = () => root.textContent;
  assert.match(text(), /Hello Alex, you have 3 new messages\./);
  assert.match(text(), /1 item(?!s)/);
  await typeInto(inputById(root, "language-count"), "3");
  assert.match(text(), /3 items/);
  assert.match(text(), /1\.5 KiB|1,5 KiB/);
  assert.match(text(), /1,234,567\.89/);
  assert.match(text(), /Relative time: .*ago/);
  assert.ok(text().includes("[teapot]"));
  assert.ok(text().includes("conflicts with the current state"));
  assert.ok(!text().includes("backend text for"));
  assert.ok(calls.some((c) => c.url === "api/fail/teapot") && calls.some((c) => c.url === "api/fail/conflict"));
});

test("language view: switching the language re-renders every text without reload", async () => {
  const root = await mountView("language");
  assert.match(root.textContent, /Hello Alex/);
  setLang("de");
  await settle();
  const text = root.textContent;
  assert.match(text, /Hallo Alex, Sie haben 3 neue Nachrichten\./);
  assert.match(text, /1 Eintrag/);
  assert.match(text, /1\.234\.567,89/);
  assert.match(text, /Die Seitensprache ist Deutsch\./);
  assert.ok(text.includes("Der Server konnte nicht erreicht werden") || text.includes("Änderung"), "errors localized");
  assert.ok(!text.includes("Hello Alex"));
  setLang("en");
  await settle();
  assert.match(root.textContent, /Hello Alex/);
});

// ---- crud ----
const rowOf = (root, needle) => findAll(root, (n) => n.localName === "tr").find((r) => r.textContent.includes(needle));
const byLabel = (root, label) => findAll(root, (n) => n.localName === "button" && n.getAttribute("aria-label") === label)[0];
const dialogIn = (root) => roleOf(root, "dialog")[0];
const submit = async (root, id) => {
  findAll(root, (n) => n.localName === "form" && findAll(n, (c) => c.getAttribute("id") === id).length)[0].dispatch("submit");
  await settle();
};

test("crud view: loads the list, shows the locked badge and keeps hostile names as text", async () => {
  const root = await mountView("crud");
  assert.ok(calls.some((c) => c.method === "GET" && c.url === "api/items"));
  assert.equal(findAll(root, (n) => n.localName === "tbody")[0].childNodes.length, 3);
  assert.ok(root.textContent.includes("<b>alice</b>"));
  assert.equal(findAll(root, (n) => n.localName === "b").length, 0);
  assert.ok(rowOf(root, "locked").textContent.includes("locked"));
  assert.equal(auditNames(root).length, 0);
});

test("crud view: create posts the form, toasts and reloads; the server validation is localized", async () => {
  const root = await mountView("crud");
  await typeInto(inputById(root, "crud-name"), "gamma");
  await typeInto(inputById(root, "crud-note"), "third");
  await submit(root, "crud-name");
  const post = calls.find((c) => c.method === "POST" && c.url === "api/items");
  assert.deepEqual(post.body, { name: "gamma", note: "third" });
  assert.ok(roleOf(root, "status").some((n) => n.textContent.includes("Item created")));
  assert.ok(rowOf(root, "gamma"));
  assert.equal(inputById(root, "crud-name").value, "");

  await typeInto(inputById(root, "crud-name"), "   ");
  await submit(root, "crud-name");
  assert.ok(root.textContent.includes("The request was invalid"));
  assert.ok(!root.textContent.includes("backend text for"));

  await typeInto(inputById(root, "crud-name"), "ALPHA");
  await submit(root, "crud-name");
  assert.ok(root.textContent.includes("The change conflicts with the current state"));
});

test("crud view: edit through the modal sends PUT; the protected item shows the protected error", async () => {
  const root = await mountView("crud");
  byLabel(root, "Edit alpha").dispatch("click");
  await settle();
  let dlg = dialogIn(root);
  await typeInto(inputById(dlg, "crud-edit-name"), "alpha2");
  await submit(dlg, "crud-edit-name");
  const put = calls.find((c) => c.method === "PUT");
  assert.equal(put.url, "api/items/1");
  assert.equal(put.body.name, "alpha2");
  assert.equal(roleOf(root, "dialog").length, 0);
  assert.ok(rowOf(root, "alpha2"));

  byLabel(root, "Edit locked").dispatch("click");
  await settle();
  dlg = dialogIn(root);
  await submit(dlg, "crud-edit-name");
  assert.ok(dlg.textContent.includes("protected and cannot be changed"));

  await click(dlg, "button", "Cancel");
  byLabel(root, "Edit <b>alice</b>").dispatch("click");
  await settle();
  assert.equal(findAll(root, (n) => n.localName === "b").length, 0);
  assert.ok(dialogIn(root).textContent.includes("Edit <b>alice</b>"));
});

test("crud view: delete needs the exact item name and sends it as the confirmation", async () => {
  const root = await mountView("crud");
  byLabel(root, "Delete alpha").dispatch("click");
  await settle();
  const dlg = dialogIn(root);
  const input = findAll(dlg, (n) => n.localName === "input")[0];
  const confirmBtn = () => findByText(dlg, "button", "Delete")[0];
  assert.equal(prop(confirmBtn(), "disabled"), true);
  await typeInto(input, "alph");
  assert.equal(prop(confirmBtn(), "disabled"), true);
  await typeInto(input, "alpha");
  assert.equal(prop(confirmBtn(), "disabled"), false);
  confirmBtn().dispatch("click");
  await settle();
  const call = calls.find((c) => c.method === "DELETE");
  assert.equal(call.url, "api/items/1");
  assert.deepEqual(call.body, { confirm: "alpha" });
  assert.equal(roleOf(root, "dialog").length, 0);
  assert.equal(rowOf(root, "alpha"), undefined);
  assert.ok(roleOf(root, "status").some((n) => n.textContent.includes("Item deleted")));
});

test("crud view: hostile names stay text in the confirm dialog; the locked item shows protected", async () => {
  const root = await mountView("crud");
  byLabel(root, "Delete <b>alice</b>").dispatch("click");
  await settle();
  assert.ok(dialogIn(root).textContent.includes('Delete "<b>alice</b>" permanently'));
  assert.equal(findAll(root, (n) => n.localName === "b").length, 0);
  await click(dialogIn(root), "button", "Cancel");

  byLabel(root, "Delete locked").dispatch("click");
  await settle();
  const dlg = dialogIn(root);
  await typeInto(findAll(dlg, (n) => n.localName === "input")[0], "locked");
  findByText(dlg, "button", "Delete")[0].dispatch("click");
  await settle();
  assert.ok(dlg.textContent.includes("protected and cannot be changed"));
  assert.ok(rowOf(root, "locked"));
});

test("crud view: slow request shows Loading, the error generator covers every stable code", async () => {
  const root = await mountView("crud");
  const slowBtn = findByText(root, "button", "Slow request")[0];
  slowBtn.dispatch("click");
  await Promise.resolve();
  await settle(1);
  await settle();
  assert.ok(calls.some((c) => c.url.startsWith("api/slow")));
  assert.ok(roleOf(root, "status").some((n) => n.textContent.includes("slow request finished")));

  const select = findAll(root, (n) => n.localName === "select")[0];
  const options = findAll(select, (n) => n.localName === "option").map((n) => n.textContent.trim());
  assert.deepEqual(options, [
    "bad_request", "confirmation_required", "ingress_only", "not_found", "method_not_allowed",
    "conflict", "protected", "payload_too_large", "internal_error", "teapot",
  ]);
  const expected = { bad_request: "request was invalid", conflict: "conflicts with the current state", teapot: "[teapot]" };
  for (const [code, fragment] of Object.entries(expected)) {
    select.value = code;
    select.dispatch("change", { target: select });
    await settle();
    await click(root, "button", "Trigger error");
    assert.ok(calls.some((c) => c.url === `api/fail/${code}`), code);
    assert.ok(roleOf(root, "alert").some((n) => n.textContent.includes(fragment)), code);
  }
});

// ---- whole-demo sweeps ----
test("every VIEWS id has a view file with matching meta, a default component and resolvable imports", async () => {
  assert.deepEqual(VIEWS.map((v) => v.id), ["gallery", "tokens", "language", "crud", "rules", "spike"]);
  for (const v of VIEWS) {
    const file = new URL(`views/${v.id}.mjs`, STATIC);
    assert.ok(existsSync(file), v.id);
    const mod = await import(file);
    assert.equal(mod.meta.id, v.id);
    assert.equal(mod.meta.titleKey, v.titleKey);
    assert.equal(typeof mod.default, "function");
    const src = readFileSync(file, "utf8");
    for (const m of src.matchAll(/from\s+"(\.[^"]+)"/g)) {
      assert.ok(existsSync(new URL(m[1], file)), `${v.id}: ${m[1]}`);
      assert.ok(!m[1].includes("vendor"), `${v.id}: ${m[1]}`);
    }
  }
});

test("whole demo: every view in en and de has no unlabeled control, no unresolved [key] marker and relative URLs only", async () => {
  const all = [];
  for (const lang of ["en", "de"]) {
    for (const v of VIEWS) {
      setLang(lang);
      calls = [];
      items = seedItems();
      const root = doc.createElement("div");
      globalThis.location.hash = `#/${v.id}`;
      render(html`<${App} ha=${makeHa()} />`, root);
      await settle(12);
      const where = `${v.id}/${lang}`;
      assert.deepEqual(auditNames(root).map((x) => x.tag), [], `${where}: unlabeled control`);
      assert.deepEqual(auditTables(root), [], `${where}: th without scope`);
      assert.ok(!/\[(?:app|demo|btn|state|errors|lang|nav|copy|dlg)\.[\w.]+\]/.test(root.textContent), `${where}: missing key`);
      assert.ok(findAll(root, (n) => n.localName === "h2").length > 0, `${where}: view did not load`);
      all.push(...calls);
      render(null, root);
    }
  }
  setLang("en");
  assert.ok(all.length > 0);
  for (const c of all) assert.ok(!/^(\/|[a-z][a-z0-9+.-]*:)/i.test(c.url), c.url);
});

test("whole demo: open dialogs keep accessible names in both languages", async () => {
  for (const lang of ["en", "de"]) {
    const gallery = await mountView("gallery", { lang });
    const buttons = findAll(gallery, (n) => n.localName === "button" && n.className.includes("btn"));
    for (const label of lang === "en" ? ["Open dialog", "Dangerous confirm"] : ["Dialog öffnen", "Gefährliche Bestätigung"]) {
      const opener = buttons.find((b) => b.textContent.trim() === label);
      assert.ok(opener, label);
      opener.dispatch("click");
      await settle();
      assert.deepEqual(auditNames(gallery).map((x) => x.tag), [], `gallery/${lang}/${label}`);
      doc.dispatch("keydown", { key: "Escape" });
      await settle();
    }
    const crud = await mountView("crud", { lang });
    const edit = findAll(crud, (n) => n.localName === "button" && (n.getAttribute("aria-label") || "").includes("alpha"))[0];
    edit.dispatch("click");
    await settle();
    assert.deepEqual(auditNames(crud).map((x) => x.tag), [], `crud/${lang}`);
  }
  setLang("en");
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
