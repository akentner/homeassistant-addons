import test from "node:test";
import assert from "node:assert/strict";
import { install, findAll, findByText, prop, settle } from "./fakedom.mjs";

const doc = install();
const STATIC = new URL("../../app/web/static/", import.meta.url);
const ui = await import(new URL("lib/ui.mjs", STATIC));
const shell = await import(new URL("lib/shell.mjs", STATIC));
const { setLang, getLang } = await import(new URL("lib/i18n.mjs", STATIC));
const { auditNames, auditTables } = await import("./a11y_audit.mjs");
const { html, render } = ui;
const { parseHash, useHashRoute, Topbar, LangSwitch, TabNav, ErrorBoundary } = shell;

const IDS = ["users", "acl", "health"];
const tag = (root, name) => findAll(root, (n) => n.localName === name);
const byClass = (root, cls) => findAll(root, (n) => (n.attributes.class || "").split(" ").includes(cls));

async function mount(vnode) {
  const root = doc.createElement("div");
  doc.appendChild(root);
  render(vnode, root);
  await settle();
  return root;
}

// Minimal bridge double with the store shape of ha-bridge.mjs
function fakeBridge(kiosk = false) {
  const listeners = new Set();
  const state = { kiosk };
  return {
    toggles: 0,
    getState: () => state,
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    toggleMenu() {
      this.toggles++;
    },
    set(value) {
      state.kiosk = value;
      listeners.forEach((fn) => fn(state));
    },
    count: () => listeners.size,
  };
}

test.beforeEach(() => {
  setLang("en");
  doc.activeElement = null;
  while (doc.childNodes.length) doc.removeChild(doc.childNodes[0]);
});

// ---- parseHash ----

test("parseHash: known id with query parameters", () => {
  assert.deepEqual(parseHash("#/users?x=1&y=a%20b", IDS, "health"), { id: "users", params: { x: "1", y: "a b" } });
});

test("parseHash: unknown, empty or non-string hashes give the default", () => {
  assert.deepEqual(parseHash("#/nope", IDS, "acl"), { id: "acl", params: {} });
  assert.deepEqual(parseHash("", IDS, "acl"), { id: "acl", params: {} });
  assert.deepEqual(parseHash(undefined, IDS, "acl"), { id: "acl", params: {} });
  assert.deepEqual(parseHash(42, IDS, "acl"), { id: "acl", params: {} });
  assert.deepEqual(parseHash(null, IDS, "acl"), { id: "acl", params: {} });
});

test("parseHash: the default is ids[0] when omitted", () => {
  assert.equal(parseHash("#/x", IDS).id, "users");
});

test("parseHash: plus decodes to space and a value may contain an equals sign", () => {
  assert.deepEqual(parseHash("#/acl?q=a+b&t=x=y", IDS).params, { q: "a b", t: "x=y" });
});

test("parseHash: malformed percent escapes are ignored per parameter", () => {
  assert.deepEqual(parseHash("#/acl?bad=%E0%A4%A&ok=1&%zz=2", IDS).params, { ok: "1" });
});

test("parseHash: a parameter without a value and the hash without slash", () => {
  assert.deepEqual(parseHash("#health?flag", IDS), { id: "health", params: { flag: "" } });
  assert.equal(parseHash("#/users", IDS).id, "users");
});

// ---- useHashRoute ----

test("useHashRoute: follows hashchange and removes the listener on unmount", async () => {
  const listeners = new Set();
  globalThis.location = { hash: "#/acl" };
  globalThis.window = {
    addEventListener: (type, fn) => type === "hashchange" && listeners.add(fn),
    removeEventListener: (type, fn) => type === "hashchange" && listeners.delete(fn),
  };
  let current;
  function Probe() {
    current = useHashRoute(IDS, "users");
    return html`<span>${current.id}</span>`;
  }
  const root = await mount(html`<${Probe} />`);
  assert.equal(current.id, "acl");
  assert.equal(listeners.size, 1);
  globalThis.location.hash = "#/health?a=1";
  listeners.forEach((fn) => fn());
  await settle();
  assert.deepEqual(current, { id: "health", params: { a: "1" } });
  assert.equal(root.textContent, "health");
  render(null, root);
  await settle();
  assert.equal(listeners.size, 0);
  delete globalThis.location;
  globalThis.window = { addEventListener() {}, removeEventListener() {} };
});

test("useHashRoute: works without window and location", async () => {
  const saved = globalThis.window;
  delete globalThis.window;
  let current;
  function Probe() {
    current = useHashRoute(IDS, "acl");
    return html`<span />`;
  }
  await mount(html`<${Probe} />`);
  assert.equal(current.id, "acl");
  globalThis.window = saved;
});

// ---- Topbar ----

test("Topbar: header, heading, status badge and slot children", async () => {
  const root = await mount(
    html`<${Topbar} title="Admin UI" status=${{ kind: "ok", text: "OK" }}><span class="slot">extra</span><//>`,
  );
  const [header] = tag(root, "header");
  assert.equal(header.className, "topbar");
  assert.equal(tag(root, "h1")[0].textContent, "Admin UI");
  assert.equal(byClass(root, "badge")[0].className, "badge ok");
  assert.equal(byClass(root, "slot").length, 1);
  assert.equal(byClass(root, "lang-switch").length, 1);
  assert.equal(byClass(root, "menu-btn").length, 0);
});

test("Topbar: brand image is empty-alt and disappears after an error", async () => {
  const root = await mount(html`<${Topbar} title="T" iconSrc="./icon" />`);
  const [img] = tag(root, "img");
  assert.equal(img.attributes.alt, "");
  assert.equal(img.attributes.src, "./icon");
  img.dispatch("error");
  await settle();
  assert.equal(tag(root, "img").length, 0);
  const noIcon = await mount(html`<${Topbar} title="T" />`);
  assert.equal(tag(noIcon, "img").length, 0);
});

test("Topbar: hostile title and status stay text nodes", async () => {
  const root = await mount(html`<${Topbar} title="<b>x</b>" status=${{ kind: "error", text: "<script>1</script>" }} />`);
  assert.equal(findAll(root, (n) => ["b", "script"].includes(n.localName)).length, 0);
  assert.ok(root.textContent.includes("<b>x</b>"));
});

test("Topbar: the menu button follows the bridge kiosk state and calls toggleMenu", async () => {
  const bridge = fakeBridge(false);
  const root = await mount(html`<${Topbar} title="T" bridge=${bridge} />`);
  assert.equal(byClass(root, "menu-btn").length, 0);
  bridge.set(true);
  await settle();
  const [btn] = byClass(root, "menu-btn");
  assert.equal(btn.attributes["aria-label"], "Menu");
  btn.dispatch("click");
  assert.equal(bridge.toggles, 1);
  bridge.set(false);
  await settle();
  assert.equal(byClass(root, "menu-btn").length, 0);
});

test("Topbar: an initial kiosk state shows the button at once and unmount unsubscribes", async () => {
  const bridge = fakeBridge(true);
  const root = await mount(html`<${Topbar} title="T" bridge=${bridge} />`);
  assert.equal(byClass(root, "menu-btn").length, 1);
  assert.equal(bridge.count(), 1);
  render(null, root);
  await settle();
  assert.equal(bridge.count(), 0);
});

test("Topbar: works without a bridge", async () => {
  const root = await mount(html`<${Topbar} title="T" />`);
  assert.equal(byClass(root, "menu-btn").length, 0);
  assert.equal(tag(root, "h1").length, 1);
});

// ---- LangSwitch ----

test("LangSwitch: named select, one option per language, change re-renders in the new language", async () => {
  const root = await mount(html`<div><${LangSwitch} /><${TabNav} views=${[{ id: "users", titleKey: "btn.save" }]} activeId="users" /></div>`);
  const [select] = tag(root, "select");
  assert.equal(select.className, "lang-switch");
  assert.equal(select.attributes["aria-label"], "Language");
  const options = tag(select, "option");
  assert.deepEqual(options.map((o) => o.textContent), ["Deutsch", "English"]);
  assert.equal(prop(select, "value"), "en");
  select.value = "de";
  select.dispatch("change", { target: select });
  await settle();
  assert.equal(getLang(), "de");
  assert.equal(select.attributes["aria-label"], "Sprache");
  assert.ok(root.textContent.includes("Speichern"));
});

// ---- TabNav ----

test("TabNav: labelled nav, fixed hash links, aria-current on the active tab only", async () => {
  const views = [{ id: "users", title: "Users" }, { id: "acl", titleKey: "btn.save" }];
  const root = await mount(html`<${TabNav} views=${views} activeId="acl" />`);
  const [nav] = tag(root, "nav");
  assert.equal(nav.attributes["aria-label"], "Navigation");
  const links = tag(root, "a");
  assert.deepEqual(links.map((a) => a.attributes.href), ["#/users", "#/acl"]);
  assert.deepEqual(links.map((a) => a.className), ["tab", "tab active"]);
  assert.equal(links[0].attributes["aria-current"], undefined);
  assert.equal(links[1].attributes["aria-current"], "page");
  assert.equal(links[1].textContent.trim(), "Save");
  const custom = await mount(html`<${TabNav} views=${views} activeId="users" label="Sections" />`);
  assert.equal(tag(custom, "nav")[0].attributes["aria-label"], "Sections");
});

// ---- ErrorBoundary ----

test("ErrorBoundary: a throwing child is replaced by the localized note, siblings keep rendering", async () => {
  function Bomb() {
    throw new Error("secret stack");
  }
  const root = await mount(
    html`<div><p class="before">before</p><${ErrorBoundary}><${Bomb} /><//><p class="after">after</p></div>`,
  );
  assert.equal(byClass(root, "before").length, 1);
  assert.equal(byClass(root, "after").length, 1);
  const alerts = findAll(root, (n) => n.attributes.role === "alert");
  assert.equal(alerts.length, 1);
  assert.ok(alerts[0].textContent.includes("This view could not be displayed"));
  assert.ok(!root.textContent.includes("secret stack"));
  setLang("de");
  await settle();
  assert.ok(root.textContent.includes("Diese Ansicht konnte nicht angezeigt werden"));
});

test("ErrorBoundary: healthy children render unchanged", async () => {
  const root = await mount(html`<${ErrorBoundary}><p class="fine">ok</p><//>`);
  assert.equal(byClass(root, "fine").length, 1);
});

// ---- audits and translations ----

function Shell() {
  return html`<div>
    <${Topbar} title="Admin UI" iconSrc="./icon" status=${{ kind: "ok", text: "OK" }} bridge=${fakeBridge(true)} />
    <${TabNav} views=${[{ id: "users", title: "Users" }, { id: "acl", titleKey: "btn.save" }]} activeId="users" />
  </div>`;
}

test("shell pieces pass the accessible-name audit and resolve all texts in de and en", async () => {
  const root = await mount(html`<${Shell} />`);
  const marker = /\[(btn|dlg|state|copy|errors|lang|nav)\./;
  assert.deepEqual(auditNames(root), []);
  assert.deepEqual(auditTables(root), []);
  assert.ok(!marker.test(root.textContent));
  setLang("de");
  await settle();
  assert.deepEqual(auditNames(root), []);
  assert.ok(!marker.test(root.textContent));
  assert.equal(findByText(root, "a", "Speichern").length, 1);
});

// Preact timers can outlive the tests; end the worker once the results are reported.
test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
