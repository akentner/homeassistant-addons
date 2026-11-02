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
const { parseHash, useHashRoute, Topbar, LangSwitch, TabNav, ErrorBoundary, needsBurger } = shell;

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
  const noIcon = await mount(html`<${Topbar} title="T" iconSrc=${null} />`);
  assert.equal(tag(noIcon, "img").length, 0);
});

test("Topbar: shows ./icon by default, decorative, and hides it on error; null turns it off", async () => {
  const root = await mount(html`<${Topbar} title="T" />`);
  const [img] = tag(root, "img");
  assert.equal(img.attributes.src, "./icon");
  assert.equal(img.attributes.alt, "");
  img.dispatch("error");
  await settle();
  assert.equal(tag(root, "img").length, 0);
  assert.equal(tag(await mount(html`<${Topbar} title="T" iconSrc="" />`), "img").length, 0);
});

test("Topbar: slot children sit in a .topbar-extra wrapper that small screens can hide; none without children", async () => {
  const root = await mount(html`<${Topbar} title="T"><span class="slot">extra</span><//>`);
  const [extra] = byClass(root, "topbar-extra");
  assert.equal(byClass(extra, "slot").length, 1);
  assert.equal(byClass(await mount(html`<${Topbar} title="T" />`), "topbar-extra").length, 0);
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

// ---- sticky head, safe-area insets, navigation variants ----

const NAV_VIEWS = [
  { id: "users", title: "Users" },
  { id: "acl", titleKey: "btn.save" },
];

test("Topbar: header and tabs sit in one sticky head wrapper", async () => {
  const root = await mount(html`<${Topbar} title="T" views=${NAV_VIEWS} activeId="users" />`);
  const [head] = byClass(root, "shell-head");
  assert.equal(tag(head, "header").length, 1);
  assert.equal(tag(head, "nav").length, 1);
  assert.equal(byClass(head, "tabs").length, 1);
});

test("Topbar: nav=tabs (and the default) keep the tab bar and no topbar navigation", async () => {
  for (const props of [{}, { nav: "tabs" }, { nav: "bogus" }]) {
    const root = await mount(html`<${Topbar} title="T" views=${NAV_VIEWS} activeId="acl" ...${props} />`);
    assert.equal(byClass(root, "topnav").length, 0);
    const tabs = byClass(root, "tab");
    assert.equal(tabs.length, 2);
    assert.equal(tabs[1].attributes["aria-current"], "page");
  }
});

test("Topbar: without views no navigation renders in either mode", async () => {
  for (const nav of ["tabs", "topbar"]) {
    const root = await mount(html`<${Topbar} title="T" nav=${nav} />`);
    assert.equal(tag(root, "nav").length, 0);
  }
});

test("Topbar: nav=topbar puts the links between the name and the status, no tab bar", async () => {
  const root = await mount(
    html`<${Topbar} title="T" nav="topbar" views=${NAV_VIEWS} activeId="acl" status=${{ kind: "ok", text: "OK" }} />`,
  );
  assert.equal(byClass(root, "tabs").length, 0);
  const header = tag(root, "header")[0];
  const order = header.childNodes.map((n) => (n.localName === "h1" ? "h1" : n.attributes && n.attributes.class) || "");
  const idx = (needle) => order.findIndex((c) => c === needle || c.split(" ").includes(needle));
  assert.ok(idx("h1") >= 0 && idx("h1") < idx("topnav"));
  assert.ok(idx("topnav") < idx("badge"));
  const links = byClass(root, "topnav-link");
  assert.deepEqual(links.map((a) => a.attributes.href), ["#/users", "#/acl"]);
  assert.deepEqual(links.map((a) => a.textContent.trim()), ["Users", "Save"]);
  assert.equal(links[0].attributes["aria-current"], undefined);
  assert.equal(links[1].attributes["aria-current"], "page");
  assert.equal(byClass(root, "nav-burger").length, 0);
});

test("needsBurger: only collapses on known, positive and insufficient sizes", () => {
  assert.equal(needsBurger(500, 300), true);
  assert.equal(needsBurger(300, 300), false);
  assert.equal(needsBurger(200, 300), false);
  assert.equal(needsBurger(500, 0), true); // a squeezed-out slot must fold, not hide the links
  for (const bad of [undefined, null, NaN, 0]) assert.equal(needsBurger(bad, 300), false);
  for (const bad of [undefined, null, NaN]) assert.equal(needsBurger(500, bad), false);
});

// ResizeObserver double: the test sets the measured sizes and triggers the callback by hand.
function stubObserver() {
  const seen = [];
  globalThis.ResizeObserver = class {
    constructor(cb) {
      this.cb = cb;
      seen.push(this);
    }
    observe(node) {
      this.node = node;
    }
    disconnect() {
      this.gone = true;
    }
  };
  return {
    seen,
    restore: () => delete globalThis.ResizeObserver,
  };
}

async function squeeze(root, needed, available) {
  const [wrap] = byClass(root, "topnav");
  const [inline] = byClass(root, "topnav-inline");
  inline.scrollWidth = needed;
  wrap.clientWidth = available;
  for (const ro of globalThis.__ro.seen) if (!ro.gone) ro.cb();
  await settle();
}

async function mountNarrow(props = {}) {
  globalThis.__ro = stubObserver();
  const root = await mount(html`<${Topbar} title="T" nav="topbar" views=${NAV_VIEWS} activeId="users" ...${props} />`);
  await squeeze(root, 600, 300);
  return root;
}

test("topbar nav: too little room collapses into a burger button with aria wiring", async () => {
  const root = await mountNarrow();
  try {
    assert.ok(byClass(root, "topnav-inline")[0].className.includes("is-collapsed"));
    const [btn] = byClass(root, "nav-burger");
    assert.equal(btn.localName, "button");
    assert.equal(btn.attributes.type, "button");
    assert.equal(btn.attributes["aria-label"], "Navigation menu");
    assert.equal(btn.attributes["aria-expanded"], "false");
    assert.equal(byClass(root, "topnav-menu").length, 0);
    btn.dispatch("click");
    await settle();
    const [menu] = byClass(root, "topnav-menu");
    assert.equal(btn.attributes["aria-expanded"], "true");
    assert.equal(btn.attributes["aria-controls"], menu.attributes.id);
    const items = byClass(menu, "topnav-menu-link");
    assert.deepEqual(items.map((a) => a.attributes.href), ["#/users", "#/acl"]);
    assert.equal(items[0].attributes["aria-current"], "page");
    assert.equal(items[1].attributes["aria-current"], undefined);
  } finally {
    globalThis.__ro.restore();
  }
});

test("topbar nav: Escape closes the menu and returns focus to the burger; picking a link closes it", async () => {
  const root = await mountNarrow();
  try {
    const [btn] = byClass(root, "nav-burger");
    btn.dispatch("click");
    await settle();
    const [first] = byClass(root, "topnav-menu-link");
    first.focus();
    first.dispatch("keydown", { key: "Escape", bubbles: true });
    await settle();
    assert.equal(byClass(root, "topnav-menu").length, 0);
    assert.equal(btn.attributes["aria-expanded"], "false");
    assert.equal(doc.activeElement, btn);
    btn.dispatch("click");
    await settle();
    byClass(root, "topnav-menu-link")[1].dispatch("click");
    await settle();
    assert.equal(byClass(root, "topnav-menu").length, 0);
  } finally {
    globalThis.__ro.restore();
  }
});

test("topbar nav: focus leaving the menu closes it, an outside pointer press closes it, tab order is button then links", async () => {
  const root = await mountNarrow();
  try {
    const [btn] = byClass(root, "nav-burger");
    btn.dispatch("click");
    await settle();
    const [wrap] = byClass(root, "topnav");
    const focusable = findAll(wrap, (n) => n.tabIndex === 0 && !byClass(n, "topnav-inline").length);
    const hidden = byClass(root, "topnav-inline")[0];
    const visible = focusable.filter((n) => !hidden.contains(n));
    assert.deepEqual(visible.map((n) => n.localName), ["button", "a", "a"]);
    byClass(root, "topnav-menu-link")[1].dispatch("focusout", { bubbles: true, relatedTarget: doc.createElement("input") });
    await settle();
    assert.equal(byClass(root, "topnav-menu").length, 0);
    btn.dispatch("click");
    await settle();
    doc.dispatch("pointerdown", { target: doc.createElement("div") });
    await settle();
    assert.equal(byClass(root, "topnav-menu").length, 0);
  } finally {
    globalThis.__ro.restore();
  }
});

test("topbar nav: more room expands the links again and drops the burger", async () => {
  const root = await mountNarrow();
  try {
    await squeeze(root, 600, 900);
    assert.equal(byClass(root, "nav-burger").length, 0);
    assert.ok(!byClass(root, "topnav-inline")[0].className.includes("is-collapsed"));
  } finally {
    globalThis.__ro.restore();
  }
});

test("topbar nav: in kiosk mode the nav trigger shows the current view and differs from the host menu button", async () => {
  const bridge = fakeBridge(true);
  const root = await mountNarrow({ bridge });
  try {
    const hostBtn = byClass(root, "menu-btn").filter((b) => !b.className.includes("nav-burger"));
    assert.equal(hostBtn.length, 1);
    assert.equal(hostBtn[0].attributes["aria-label"], "Menu");
    const [burger] = byClass(root, "nav-burger");
    assert.ok(burger.textContent.includes("Users"));
    assert.equal(burger.attributes["aria-label"], "Navigation menu: Users");
    assert.notEqual(burger.textContent.trim(), hostBtn[0].textContent.trim());
  } finally {
    globalThis.__ro.restore();
  }
});

test("topbar nav: the burger label follows the language", async () => {
  const root = await mountNarrow();
  try {
    setLang("de");
    await settle();
    assert.equal(byClass(root, "nav-burger")[0].attributes["aria-label"], "Navigationsmenü");
  } finally {
    globalThis.__ro.restore();
  }
});

test("topbar nav: unmount disconnects the observer", async () => {
  const root = await mountNarrow();
  const ros = globalThis.__ro.seen;
  render(null, root);
  await settle();
  globalThis.__ro.restore();
  assert.ok(ros.length > 0 && ros.every((ro) => ro.gone));
});

test("Topbar: safe-area insets from the bridge reach the sticky head as CSS variables", async () => {
  const bridge = fakeBridge(false);
  bridge.getState().safeAreaInsets = { top: "12px", right: "0", bottom: "-4px", left: "8.5px" };
  const props = [];
  const root = await mount(html`<${Topbar} title="T" bridge=${bridge} />`);
  const [head] = byClass(root, "shell-head");
  head.style.setProperty = (k, v) => props.push([k, v]);
  bridge.getState().safeAreaInsets = { top: "20px", right: "0px", bottom: "0px", left: "0px" };
  bridge.set(false);
  await settle();
  // Preact only writes the changed properties: top 12 -> 20 and left 8.5 -> 0
  assert.deepEqual(Object.fromEntries(props), { "--safe-top": "20px", "--safe-left": "0px" });
});
