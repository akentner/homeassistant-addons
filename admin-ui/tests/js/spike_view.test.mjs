import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { install, findAll, findByText, prop, settle } from "./fakedom.mjs";
import { auditNames, auditTables } from "./a11y_audit.mjs";

const doc = install();
const STATIC = new URL("../../app/web/static/", import.meta.url);

const { html, render } = await import(new URL("lib/ui.mjs", STATIC));
const { setLang, registerStrings } = await import(new URL("lib/i18n.mjs", STATIC));
registerStrings({
  de: (await import(new URL("strings.de.mjs", STATIC))).default,
  en: (await import(new URL("strings.en.mjs", STATIC))).default,
});
const mod = await import(new URL("views/spike.mjs", STATIC));
const { CHECKS, buildResult, redact, cspKey, accessPathOf, probeStorage, probeParent } = mod;

// ---- stubs ----
let fetchCalls = [];
let healthReply = null;
let whoamiReply = { user: { user_id: "u-123", name: "Alice Admin", display_name: "Alice", groups: ["system-admin", "system-users"] } };
globalThis.fetch = async (url) => {
  fetchCalls.push(url);
  if (url === "api/health") return healthReply ? { ok: true, status: 200, json: async () => healthReply } : { ok: false, status: 503, json: async () => ({ error: "internal_error" }) };
  if (url === "api/whoami") return { ok: true, status: 200, json: async () => whoamiReply };
  return { ok: false, status: 404, json: async () => ({ error: "not_found" }) };
};

function makeHa({ sync = {}, bridge = {} } = {}) {
  const syncListeners = new Set();
  const bridgeListeners = new Set();
  const calls = { configure: [], navigate: [], refresh: 0 };
  let syncStatus = { active: true, mode: "dark", surface: true, accent: true, skipped: [], raw: { bg: "#101010", card: "#202020", fg: "#f0f0f0", bd: "#303030", acc: "#03a9f4" }, counters: { refresh: 2, observer: 1, poll: 3, event: 0, apply: 5 }, lastSync: 1700000000000, ...sync };
  let bridgeState = { embedded: true, status: "ok", narrow: false, safeAreaInsets: null, route: null, kiosk: false, hostBar: false, kioskFrozen: false, messages: 2, lastMessageAt: 1700000000000, ...bridge };
  return {
    calls,
    bridge: {
      getState: () => bridgeState,
      subscribe: (fn) => (bridgeListeners.add(fn), () => bridgeListeners.delete(fn)),
      configure: (o) => (calls.configure.push(o), true),
      navigate: (p) => (calls.navigate.push(p), true),
      toggleMenu() {},
    },
    sync: {
      status: () => syncStatus,
      subscribe: (fn) => (syncListeners.add(fn), () => syncListeners.delete(fn)),
      refresh: () => (calls.refresh += 1),
    },
    pushSync(next) {
      syncStatus = { ...syncStatus, ...next };
      syncListeners.forEach((fn) => fn(syncStatus));
    },
    pushBridge(next) {
      bridgeState = { ...bridgeState, ...next };
      bridgeListeners.forEach((fn) => fn(bridgeState));
    },
  };
}

const embeddedWindow = (parent) => {
  const win = { addEventListener() {}, removeEventListener() {}, location: { origin: "https://ha.example", pathname: "/api/hassio_ingress/tok/" } };
  win.parent = parent || { document: { documentElement: {} }, location: { origin: "https://ha.example" } };
  win.frameElement = { getBoundingClientRect: () => ({ top: 40 }) };
  return win;
};
const plainWindow = () => {
  const win = { addEventListener() {}, removeEventListener() {}, location: { origin: "http://h", pathname: "/" } };
  win.parent = win;
  return win;
};

async function mount({ ha = makeHa(), win = embeddedWindow(), lang = "en" } = {}) {
  setLang(lang);
  fetchCalls = [];
  globalThis.window = win;
  const root = doc.createElement("div");
  render(html`<${mod.default} params=${{}} ha=${ha} />`, root);
  await settle();
  return { root, ha };
}
const click = async (root, text) => {
  const node = findByText(root, "button", text)[0];
  assert.ok(node, `button "${text}" not found`);
  node.dispatch("click");
  await settle();
};
const panel = (root, id) => findAll(root, (n) => n.localName === "section" && n.getAttribute("id") === `spike-${id}`)[0];
const resultJson = (root) => JSON.parse(findAll(root, (n) => n.localName === "pre")[0].textContent);

test("meta and CHECKS cover S1..S15 and equal the ids of DOCS.md", () => {
  assert.equal(mod.meta.id, "spike");
  assert.equal(mod.meta.titleKey, "demo.nav.spike");
  assert.deepEqual(CHECKS.map((c) => c.id), Array.from({ length: 15 }, (_, i) => `S${i + 1}`));
  const docs = readFileSync(new URL("../../DOCS.md", import.meta.url), "utf8");
  const docIds = [...docs.matchAll(/^\| (S\d+)\s+\|/gm)].map((m) => m[1]);
  assert.deepEqual(CHECKS.map((c) => c.id), docIds);
});

test("every probe panel renders with a labelled heading and the result block", async () => {
  const { root } = await mount();
  for (const c of CHECKS) assert.ok(panel(root, c.id), c.id);
  assert.equal(findAll(root, (n) => n.localName === "pre").length, 1);
  assert.equal(auditNames(root).length, 0);
  assert.equal(auditTables(root).length, 0);
});

test("S1 reports an embedded readable parent, a throwing parent and a direct tab", async () => {
  let { root } = await mount();
  assert.match(panel(root, "S1").textContent, /Parent document readable: yes/);
  assert.equal(resultJson(root).probes.S1.ok, true);

  const parent = { location: { origin: "https://ha.example" } };
  Object.defineProperty(parent, "document", {
    get() {
      const e = new Error("secret detail https://ha.example");
      e.name = "SecurityError";
      throw e;
    },
  });
  ({ root } = await mount({ win: embeddedWindow(parent) }));
  assert.match(panel(root, "S1").textContent, /SecurityError/);
  assert.ok(!panel(root, "S1").textContent.includes("secret detail"));
  assert.equal(resultJson(root).probes.S1.ok, false);

  ({ root } = await mount({ win: plainWindow() }));
  assert.equal(resultJson(root).probes.S1.detail, "not_embedded");
  assert.equal(resultJson(root).embedded, false);
});

test("S2 shows parsed colours and a dash for anything that is not a parsed colour", async () => {
  const ha = makeHa({ sync: { raw: { bg: "#101010", card: "url(https://evil)", fg: "<b>x</b>", bd: null, acc: "rgba(1, 2, 3, 0.5)" }, skipped: ["<i>surface</i>"], mode: "dark" } });
  const { root } = await mount({ ha });
  const text = panel(root, "S2").textContent;
  assert.match(text, /#101010/);
  assert.match(text, /rgba\(1, 2, 3, 0\.5\)/);
  assert.ok(!text.includes("evil"));
  assert.equal(findAll(root, (n) => n.localName === "b" || n.localName === "i").length, 0);
  assert.ok(text.includes("<i>surface</i>"));
  await click(root, "Refresh now");
  assert.equal(ha.calls.refresh, 1);
  assert.deepEqual(resultJson(root).sync.skipped, ["other"]);
});

test("S3 counters follow the sync subscription live", async () => {
  const { root, ha } = await mount();
  assert.match(panel(root, "S3").textContent, /apply: 5/);
  ha.pushSync({ counters: { refresh: 9, observer: 4, poll: 6, event: 0, apply: 8 } });
  await settle();
  assert.match(panel(root, "S3").textContent, /observer: 4/);
  assert.match(panel(root, "S3").textContent, /apply: 8/);
});

test("S4 logs bridge changes newest first and keeps at most 20", async () => {
  const { root, ha } = await mount();
  for (let i = 1; i <= 25; i++) {
    ha.pushBridge({ messages: i, narrow: i % 2 === 0 });
    await new Promise((r) => setTimeout(r, 1));
  }
  await settle();
  const rows = findAll(panel(root, "S4"), (n) => n.localName === "tr");
  assert.equal(rows.length, 21);
  assert.match(rows[1].textContent, /25/);
  assert.match(panel(root, "S4").textContent, /Messages received: 25/);
});

test("S5 policy buttons call configure with the fixed policies and show the active one", async () => {
  const { root, ha } = await mount();
  await click(root, "Never");
  await click(root, "Always");
  await click(root, "Narrow only");
  assert.deepEqual(ha.calls.configure, [{ kiosk: "never" }, { kiosk: "always" }, { kiosk: "narrow" }]);
  assert.match(panel(root, "S5").textContent, /Active kiosk policy: Narrow only/);
  assert.match(panel(root, "S5").textContent, /Frame top offset \(px\): 40/);
});

test("S6 toggles handleSafeArea through configure", async () => {
  const { root, ha } = await mount();
  await click(root, "Toggle handleSafeArea");
  await click(root, "Toggle handleSafeArea");
  assert.deepEqual(ha.calls.configure, [{ handleSafeArea: true }, { handleSafeArea: false }]);
});

test("S7 calls navigate('/config') exactly once per click and shows the returned boolean", async () => {
  const { root, ha } = await mount();
  assert.match(panel(root, "S7").textContent, /Message sent: -/);
  await click(root, "Open HA settings");
  assert.deepEqual(ha.calls.navigate, ["/config"]);
  assert.match(panel(root, "S7").textContent, /Message sent: yes/);
  assert.equal(resultJson(root).probes.S7.ok, true);
});

test("S9 counts securitypolicyviolation events by directive and a URI category only", async () => {
  const { root } = await mount();
  doc.dispatch("securitypolicyviolation", { effectiveDirective: "script-src", blockedURI: "inline" });
  doc.dispatch("securitypolicyviolation", { effectiveDirective: "script-src", blockedURI: "inline" });
  doc.dispatch("securitypolicyviolation", { effectiveDirective: "img-src", blockedURI: "https://secret.example/x.png" });
  doc.dispatch("securitypolicyviolation", { effectiveDirective: "<b>x</b>", blockedURI: "eval" });
  await settle();
  const text = panel(root, "S9").textContent;
  assert.match(text, /CSP violations: 4/);
  assert.match(text, /script-src\/inline/);
  assert.ok(!text.includes("secret.example"));
  assert.deepEqual(resultJson(root).csp.violations, { "script-src/inline": 2, "img-src/other": 1, "other/eval": 1 });
  assert.equal(cspKey({ effectiveDirective: "style-src", blockedURI: "self" }), "style-src/self");
  const before = (doc.listeners.securitypolicyviolation || []).length;
  render(null, root);
  await settle();
  assert.equal((doc.listeners.securitypolicyviolation || []).length, before - 1);
});

test("S10 reports ok and blocked storage and removes its own key", async () => {
  const data = {};
  const good = { setItem: (k, v) => (data[k] = v), getItem: (k) => data[k] ?? null, removeItem: (k) => delete data[k] };
  assert.equal(probeStorage(good), "ok");
  assert.deepEqual(data, {});
  const bad = { setItem() { throw new Error("blocked"); }, getItem() { return null; }, removeItem() {} };
  assert.equal(probeStorage(bad), "blocked");
  assert.equal(probeStorage({ setItem() {}, getItem: () => null, removeItem() {} }), "blocked");

  Object.defineProperty(globalThis, "localStorage", { value: bad, configurable: true, writable: true });
  const { root } = await mount();
  await click(root, "Test storage");
  assert.match(panel(root, "S10").textContent, /Storage:\s*blocked/);
  assert.equal(resultJson(root).probes.S10.ok, false);
  delete globalThis.localStorage;
});

test("S11 requests api/whoami with a relative URL and shows groups, never the identity", async () => {
  const { root } = await mount();
  assert.deepEqual(fetchCalls, ["api/whoami", "api/health"]);
  const text = panel(root, "S11").textContent;
  assert.match(text, /Identity header present: yes/);
  assert.match(text, /system-admin, system-users/);
  assert.ok(!/Alice|u-123/.test(root.textContent));
  assert.deepEqual(resultJson(root).whoami, { identity_present: true, groups: ["system-admin", "system-users"] });
});

test("S11 failing request shows an alert and keeps the page alive", async () => {
  const saved = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, status: 500, json: async () => ({ error: "internal_error" }) });
  const { root } = await mount();
  assert.match(panel(root, "S11").textContent, /The request failed/);
  globalThis.fetch = saved;
});

test("S12 derives the access path category from the pathname", async () => {
  assert.equal(accessPathOf("/api/hassio_ingress/abc/"), "ingress");
  assert.equal(accessPathOf("/"), "direct");
  assert.equal(accessPathOf(undefined), "direct");
  const { root } = await mount();
  assert.equal(resultJson(root).access_path, "ingress");
  const direct = await mount({ win: plainWindow() });
  assert.equal(resultJson(direct.root).access_path, "direct");
});

test("hostile status and bridge values render as text nodes and never reach the result", async () => {
  const ha = makeHa({ sync: { mode: "<b>dark</b>", skipped: ["<script>"] }, bridge: { status: "<img src=x>", route: { path: "/secret/path", prefix: "/p" }, safeAreaInsets: { top: "1px", right: "1px", bottom: "1px", left: "1px" } } });
  const { root } = await mount({ ha });
  assert.equal(findAll(root, (n) => ["b", "img", "script", "i"].includes(n.localName)).length, 0);
  const text = JSON.stringify(resultJson(root));
  assert.ok(!text.includes("secret/path") && !text.includes("<"));
  assert.equal(resultJson(root).bridge.route_present, true);
  assert.equal(resultJson(root).bridge.status, "unknown");
});

test("probes never throw: hostile stubs yield defaults", async () => {
  const boom = () => { throw new Error("boom"); };
  const ha = { bridge: { getState: boom, subscribe: boom, configure: boom, navigate: boom }, sync: { status: boom, subscribe: boom, refresh: boom } };
  const { root } = await mount({ ha });
  await click(root, "Open HA settings");
  await click(root, "Never");
  await click(root, "Refresh now");
  assert.equal(resultJson(root).probes.S7.ok, false);
  assert.equal(probeParent({}).embedded, false);
  const noHa = await mount({ ha: undefined });
  assert.ok(noHa.root.textContent.includes("Result block"));
});

test("redact removes identity keys, URLs, hosts and token-like strings at any depth", () => {
  const cleaned = redact({
    user_id: "u1", name: "A", display_name: "B", href: "x", origin: "o", url: "u", host: "h", token: "t",
    keep: "narrow",
    nested: { name: "n", ok: true, list: ["https://a.example/x", "fine", "Bearer abc", "0123456789abcdef0123456789", "ha.example.com", "192.168.1.20", 7] },
  });
  assert.deepEqual(cleaned, { keep: "narrow", nested: { ok: true, list: ["fine", 7] } });
  assert.equal(redact("http://x"), undefined);
  assert.equal(redact(null), null);
});

const FIXTURE = {
  generatedAt: "2026-11-02",
  versions: { core: "2026.10.3", frontend: "20261001.0", app: "Firefox 140 on Linux" },
  accessPath: "ingress",
  embedded: true,
  parent: { embedded: true, readable: true, sameOrigin: true, error: null },
  sync: { active: true, mode: "dark", surface: true, accent: false, skipped: ["accent", "<b>x</b>"], counters: { refresh: 3, observer: 1, poll: 2, apply: 4 }, raw: { bg: "#101010", card: "#202020", fg: "#f0f0f0", bd: "#303030", acc: "javascript:alert(1)" } },
  bridge: { status: "ok", narrow: false, kiosk: false, hostBar: false, kioskFrozen: false, messages: 3, safeAreaInsets: { top: "0px" }, route: { path: "/x" } },
  csp: { counts: { "script-src/inline": 1 } },
  handleSafeArea: false,
  navigateResult: true,
  clipboard: "copied",
  storage: "ok",
  whoami: { identity_present: true, groups: ["system-admin"] },
  lang: "en",
};

test("buildResult snapshot: stable shape and allow-listed content", () => {
  const result = buildResult(FIXTURE);
  assert.equal(result.schema, 1);
  assert.deepEqual(Object.keys(result), ["schema", "generated_at", "ha", "client", "access_path", "embedded", "probes", "sync", "bridge", "csp", "navigate", "whoami"]);
  assert.deepEqual(Object.keys(result.probes), CHECKS.map((c) => c.id));
  assert.deepEqual(result.ha, {
    core: "2026.10.3", core_source: "manual", frontend: "20261001.0", frontend_source: "manual", addon: "", addon_source: "not_recorded",
  });
  assert.deepEqual(result.client, { app: "Firefox 140 on Linux", app_source: "manual" });
  assert.deepEqual(result.sync.colors, { bg: "#101010", card: "#202020", fg: "#f0f0f0", bd: "#303030", acc: null });
  assert.deepEqual(result.sync.skipped, ["accent", "other"]);
  assert.deepEqual(result.bridge, { status: "ok", narrow: false, kiosk: false, hostBar: false, kioskFrozen: false, messages: 3, insets_present: true, route_present: true });
  for (const p of Object.values(result.probes)) assert.ok("ok" in p && typeof p.detail === "string");
});

test("buildResult on a hostile fixture contains no identity, URL, hostname or token", () => {
  const hostile = {
    ...FIXTURE,
    versions: { core: "https://ha.example.com/x", frontend: "ghp_abcdefghijklmnopqrstuvwxyz0123", app: "Firefox on host nas.home.lan" },
    parent: { embedded: true, readable: false, sameOrigin: false, error: "https://evil/<b>x</b>" },
    whoami: { identity_present: true, groups: ["<b>x</b>", "alice@example.com", "system-users"], name: "Alice Admin", user_id: "u-999" },
    sync: { ...FIXTURE.sync, mode: "https://evil" },
  };
  const text = JSON.stringify(buildResult(hostile));
  for (const bad of ["https", "://", "evil", "ha.example", "ghp_", "nas.home", "Alice", "u-999", "alice@", "<b>", "Bearer"]) {
    assert.ok(!text.includes(bad), bad);
  }
  assert.deepEqual(buildResult(hostile).whoami.groups, ["system-users"]);
});

test("the rendered result block contains no page URL, identity, hostname or token", async () => {
  const win = embeddedWindow();
  const ha = makeHa();
  const { root } = await mount({ ha, win });
  const input = (id) => findAll(root, (n) => n.localName === "input" && n.getAttribute("id") === id)[0];
  for (const [id, value] of [["spike-core", "2026.10.3"], ["spike-frontend", "20261001.0"], ["spike-app", "Firefox 140 on Linux"]]) {
    const el = input(id);
    el.value = value;
    el.dispatch("input", { target: el });
  }
  await settle();
  const compact = findAll(root, (n) => n.localName === "input" && n.getAttribute("class") === "mono").at(-1).value;
  const pretty = findAll(root, (n) => n.localName === "pre")[0].textContent;
  assert.equal(JSON.stringify(JSON.parse(pretty)), compact);
  for (const bad of ["ha.example", "hassio_ingress", "Alice", "u-123", "://"]) {
    assert.ok(!pretty.includes(bad), bad);
  }
  assert.equal(JSON.parse(pretty).ha.core, "2026.10.3");
  assert.equal(JSON.parse(pretty).probes.S15.ok, true);
});

test("de and en render all panels without unresolved key markers and with named controls", async () => {
  for (const lang of ["en", "de"]) {
    const { root } = await mount({ lang });
    assert.ok(!/\[demo\.[\w.]+\]/.test(root.textContent), lang);
    assert.equal(auditNames(root).length, 0, lang);
    assert.equal(auditTables(root).length, 0, lang);
    for (const c of CHECKS) assert.ok(panel(root, c.id), `${lang} ${c.id}`);
  }
  setLang("en");
});

test("the view source never touches parent storage, cookies or hass objects", () => {
  const src = readFileSync(new URL("views/spike.mjs", STATIC), "utf8");
  for (const bad of ["parent.localStorage", "parent.sessionStorage", "document.cookie", "parent.hass", "parent.document.querySelector", "getComputedStyle"]) {
    assert.ok(!src.includes(bad), bad);
  }
  assert.equal((src.match(/navigate\("\/config"\)/g) || []).length, 1);
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});

// ---- automatic version detection (S15) ----

function haWindow(version) {
  const win = embeddedWindow({
    document: { documentElement: {}, querySelector: (sel) => (sel === "home-assistant" && version !== undefined ? { hass: { config: { version } } } : null) },
    location: { origin: "https://ha.example" },
  });
  return win;
}
const setNavigator = (value) => Object.defineProperty(globalThis, "navigator", { value, configurable: true, writable: true });
const NAVIGATOR_BACKUP = Object.getOwnPropertyDescriptor(globalThis, "navigator");
const restoreNavigator = () => (NAVIGATOR_BACKUP ? Object.defineProperty(globalThis, "navigator", NAVIGATOR_BACKUP) : delete globalThis.navigator);
const field = (root, id) => findAll(root, (n) => n.localName === "input" && n.getAttribute("id") === id)[0];
const hint = (root, id) => findAll(root, (n) => n.getAttribute && n.getAttribute("id") === `${id}-hint`)[0].textContent;

test("S15 detects core (parent), add-on (health) and browser (client hints) and keeps the frontend untouched", async () => {
  healthReply = { status: "ok", addon_version: "0.1.0-3" };
  setNavigator({ userAgentData: { getHighEntropyValues: async () => ({ fullVersionList: [{ brand: "Not/A)Brand", version: "99.0.0.0" }, { brand: "Chromium", version: "156.0.8078.48" }, { brand: "Google Chrome", version: "156.0.8078.48" }] }) }, userAgent: "ignored" });
  try {
    const { root } = await mount({ win: haWindow("2026.10.4") });
    await settle();
    assert.match(hint(root, "spike-core"), /2026\.10\.4 \(Detected automatically\)/);
    assert.match(hint(root, "spike-addon"), /0\.1\.0-3 \(Detected automatically\)/);
    assert.match(hint(root, "spike-app"), /Google Chrome 156\.0\.8078\.48/);
    assert.match(hint(root, "spike-frontend"), /not recorded/);
    const result = resultJson(root);
    assert.deepEqual(result.ha, { core: "2026.10.4", core_source: "auto", frontend: "", frontend_source: "not_recorded", addon: "0.1.0-3", addon_source: "auto" });
    assert.deepEqual(result.client, { app: "Google Chrome 156.0.8078.48", app_source: "auto" });
    assert.equal(result.probes.S15.ok, false); // the frontend version is still missing, nothing is guessed
  } finally {
    healthReply = null;
    restoreNavigator();
  }
});

test("S15 falls back to not_recorded when parent, health and navigator give nothing", async () => {
  setNavigator({});
  try {
    const { root } = await mount({ win: haWindow(undefined) });
    await settle();
    const { ha, client } = resultJson(root);
    assert.deepEqual(ha, { core: "", core_source: "not_recorded", frontend: "", frontend_source: "not_recorded", addon: "", addon_source: "not_recorded" });
    assert.deepEqual(client, { app: "", app_source: "not_recorded" });
  } finally {
    restoreNavigator();
  }
});

test("S15 typed values override detected ones per field and are labelled manual; the add-on never lands in the frontend field", async () => {
  healthReply = { status: "ok", addon_version: "0.1.0-3" };
  setNavigator({ userAgent: "Mozilla/5.0 Firefox/140.0" });
  try {
    const { root } = await mount({ win: haWindow("2026.10.4") });
    await settle();
    for (const [id, value] of [["spike-core", "2026.10.9"], ["spike-frontend", "20261001.0"]]) {
      const el = field(root, id);
      el.value = value;
      el.dispatch("input", { target: el });
    }
    await settle();
    const { ha, client } = resultJson(root);
    assert.equal(ha.core, "2026.10.9");
    assert.equal(ha.core_source, "manual");
    assert.equal(ha.frontend, "20261001.0");
    assert.equal(ha.frontend_source, "manual");
    assert.equal(ha.addon, "0.1.0-3");
    assert.equal(ha.addon_source, "auto");
    assert.deepEqual(client, { app: "Firefox 140.0", app_source: "auto" });
    assert.equal(resultJson(root).probes.S15.ok, true);
  } finally {
    healthReply = null;
    restoreNavigator();
  }
});

test("S15 has four separately labelled version fields in de and en", async () => {
  for (const [lang, labels] of [["en", ["HA core version", "HA frontend version", "Add-on version", "Browser or app"]], ["de", ["HA-Core-Version", "HA-Frontend-Version", "Add-on-Version", "Browser oder App"]]]) {
    const { root } = await mount({ lang });
    const text = panel(root, "S15").textContent;
    for (const label of labels) assert.ok(text.includes(label), `${lang} ${label}`);
  }
  setLang("en");
});

test("the only parent read of the hass object lives in spike-versions.mjs and touches config.version only", () => {
  const src = readFileSync(new URL("spike-versions.mjs", STATIC), "utf8");
  assert.equal((src.match(/\.hass\b/g) || []).length, 1);
  assert.ok(src.includes(".hass.config.version"));
  for (const bad of ["localStorage", "sessionStorage", "cookie", "hass.states", "hass.user", "hass.auth", "callService"]) assert.ok(!src.includes(bad), bad);
});

test("the result block records which path the info link took last, never more", async () => {
  assert.deepEqual(buildResult(FIXTURE).navigate, { last_path: "none", count: 0 });
  assert.deepEqual(buildResult({ ...FIXTURE, infoNav: { last: "bridge", count: 2 } }).navigate, { last_path: "bridge", count: 2 });
  assert.deepEqual(buildResult({ ...FIXTURE, infoNav: { last: "https://evil", count: "x" } }).navigate, { last_path: "none", count: 0 });
  const ha = makeHa();
  const listeners = new Set();
  let state = { last: "none", count: 0 };
  ha.infoNav = { getState: () => state, subscribe: (fn) => (listeners.add(fn), () => listeners.delete(fn)) };
  const { root } = await mount({ ha });
  assert.deepEqual(resultJson(root).navigate, { last_path: "none", count: 0 });
  assert.match(panel(root, "S7").textContent, /Info link last used: not used yet \(0\)/);
  state = { last: "fallback", count: 1 };
  listeners.forEach((fn) => fn(state));
  await settle();
  assert.deepEqual(resultJson(root).navigate, { last_path: "fallback", count: 1 });
  assert.match(panel(root, "S7").textContent, /fallback \(link to the top window\) \(1\)/);
  assert.equal(findAll(root, (n) => n.localName === "button" && n.textContent.trim() === "Open HA settings").length, 1); // S7 button stays
});
