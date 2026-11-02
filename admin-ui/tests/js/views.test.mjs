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


// ---- view helpers ----
const { Toasts } = await import(new URL("lib/ui.mjs", STATIC));

async function mountView(id, { params = {}, ha = makeHa(), lang = "en" } = {}) {
  setLang(lang);
  calls = [];
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

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
