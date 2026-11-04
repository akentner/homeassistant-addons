import test from "node:test";
import assert from "node:assert/strict";
import { install, findAll, prop, settle } from "./fakedom.mjs";
import { auditNames, auditTables } from "./a11y_audit.mjs";

const doc = install();
const STATIC = new URL("../../app/web/static/", import.meta.url);

// ---- timers: capture the polling interval instead of scheduling it ----
const intervals = [];
globalThis.setInterval = (fn, ms) => intervals.push({ fn, ms });
globalThis.clearInterval = () => {};
const poll = () => intervals.filter((i) => i.ms === 10000).at(-1);

// ---- fetch stub ----
const NOW1 = Date.UTC(2026, 10, 2, 12, 0, 0);
const NOW2 = Date.UTC(2026, 10, 2, 12, 0, 10);
const reply = (status, data) => ({ ok: status < 400, status, json: async () => data });
const status = (over = {}) => ({
  age: 3, up: 400000, load1: 1.5, io_some10: 2, io_full10: 0, mem_full10: 0, sda_inflight: 0, mmc_inflight: 1, dstate: 0,
  probe_age: 2, ping: 1, p22222: 1, p1883: 1, p8123: 1, p4357: 1, problem: 0, r_age: 0, r_io: 0, r_sda: 0, r_dstate: 0,
  r_kmsg: 0, reasons: "none", dstate_tasks: "", kmsg_errors: 0, kmsg_last: "", key_fp: "SHA256:abc", key_type: "ED25519", ...over,
});
const entry = (slug, over = {}) => ({ slug, name: slug.toUpperCase(), host: `${slug}.example`, status: status(), error: null, incidents: [], ...over });
const overview = (hosts, now_ms = NOW1) => ({ now_ms, hosts });

let calls = [];
let responder = async () => reply(200, overview([entry("a"), entry("b")]));
globalThis.fetch = async (url, init = {}) => {
  calls.push({ method: init.method || "GET", url });
  return responder(url, init);
};
const deferred = () => {
  let resolve;
  const promise = new Promise((r) => (resolve = r));
  return { promise, resolve };
};

const { html, render } = await import(new URL("vendor/admin-ui/ui.mjs", STATIC));
const { setLang } = await import(new URL("vendor/admin-ui/i18n.mjs", STATIC));
const { formatDateTime } = await import(new URL("vendor/admin-ui/format.mjs", STATIC));
const { App } = await import(new URL("app.mjs", STATIC));
const { POLL_MS } = await import(new URL("views/overview.mjs", STATIC));
setLang("en");

function makeHa() {
  const log = [];
  return {
    log,
    bridge: {
      getState: () => ({ kiosk: false }),
      subscribe: () => () => {},
      toggleMenu() {},
      start: () => log.push("bridge.start"),
      dispose: () => log.push("bridge.dispose"),
    },
    sync: { start: () => log.push("sync.start"), dispose: () => log.push("sync.dispose") },
  };
}

async function mountApp({ ha = makeHa(), props = {} } = {}) {
  calls = [];
  intervals.length = 0;
  const root = doc.createElement("div");
  render(html`<${App} ha=${ha} ...${props} />`, root);
  await settle();
  return { root, ha };
}

const cls = (root, name) => findAll(root, (n) => (n.className || "").split(" ").includes(name));
const tag = (root, name) => findAll(root, (n) => n.localName === name);
const barBadge = (root) => cls(tag(root, "header")[0], "badge")[0];
const reloadButton = (root) => tag(root, "button").find((b) => b.textContent.trim() === "Reload");
const tick = async () => {
  poll().fn();
  await settle();
};

test("mount: one relative request, one card per host in order, title and no navigation", async () => {
  const { root } = await mountApp();
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0], { method: "GET", url: "api/overview" });
  assert.ok(!/^(\/|[a-z][a-z0-9+.-]*:)/i.test(calls[0].url));
  assert.deepEqual(tag(root, "h2").map((h) => h.textContent), ["A", "B"]);
  assert.equal(tag(root, "h1")[0].textContent, "HAOS Monitor");
  assert.equal(cls(root, "tabs").length + cls(root, "topnav").length + tag(root, "nav").length, 0);
  assert.equal(tag(root, "main").length, 1);
  assert.equal(tag(root, "select").filter((s) => s.className === "lang-switch").length, 1);
});

test("bar status: loading, ok, problems (plural), degraded, error", async () => {
  const pending = deferred();
  responder = () => pending.promise;
  let { root } = await mountApp();
  assert.equal(barBadge(root).textContent, "Loading…");
  assert.ok(barBadge(root).className.includes("muted"));
  pending.resolve(reply(200, overview([entry("a")])));
  await settle();
  assert.equal(barBadge(root).textContent, "OK");
  assert.ok(barBadge(root).className.includes("ok"));

  responder = async () => reply(200, overview([entry("a", { status: status({ problem: 1 }) }), entry("b")]));
  ({ root } = await mountApp());
  assert.equal(barBadge(root).textContent, "1 problem");
  assert.ok(barBadge(root).className.includes("error"));

  responder = async () => reply(200, overview([entry("a", { status: status({ problem: 1 }) }), entry("b", { status: status({ problem: 1 }) })]));
  ({ root } = await mountApp());
  assert.equal(barBadge(root).textContent, "2 problems");

  responder = async () => reply(200, overview([entry("a"), entry("b", { status: null, error: "status_failed" })]));
  ({ root } = await mountApp());
  assert.equal(barBadge(root).textContent, "Degraded");
  assert.ok(barBadge(root).className.includes("degraded"));

  responder = async () => reply(500, { error: "internal_error", message: "SERVER TEXT" });
  ({ root } = await mountApp());
  assert.equal(barBadge(root).textContent, "Error");
  assert.ok(barBadge(root).className.includes("error"));
  responder = async () => reply(200, overview([entry("a"), entry("b")]));
});

test("refresh: the interval is 10000 ms, a tick issues a new request and re-renders the values", async () => {
  assert.equal(POLL_MS, 10000);
  responder = async () => reply(200, overview([entry("a")], NOW1));
  const { root } = await mountApp();
  assert.equal(intervals.filter((i) => i.ms === 10000).length, 1);
  assert.match(root.textContent, /Updated/);
  responder = async () => reply(200, overview([entry("a", { status: status({ load1: 7.25 }) })], NOW2));
  await tick();
  assert.equal(calls.length, 2);
  assert.ok(root.textContent.includes("7.25"));
  responder = async () => reply(200, overview([entry("a"), entry("b")]));
});

test("refresh: a failing refresh keeps the cards and shows a localized note with retry, a recovery clears it", async () => {
  const { root } = await mountApp();
  const before = tag(root, "h2").length;
  responder = async () => reply(500, { error: "internal_error", message: "SERVER TEXT" });
  await tick();
  const alerts = findAll(root, (n) => n.getAttribute("role") === "alert");
  assert.equal(alerts.length, 1);
  assert.ok(alerts[0].textContent.includes("The server hit an internal error"));
  assert.ok(!root.textContent.includes("SERVER TEXT"));
  assert.equal(tag(root, "h2").length, before, "last cards stay");
  const retry = tag(alerts[0], "button")[0];
  assert.equal(retry.textContent.trim(), "Retry");

  responder = async () => {
    throw new TypeError("offline");
  };
  await tick();
  assert.ok(findAll(root, (n) => n.getAttribute("role") === "alert")[0].textContent.includes("could not be reached"));

  responder = async () => reply(200, overview([entry("a"), entry("b")], NOW2));
  retry.dispatch("click", { bubbles: true });
  await settle();
  assert.equal(findAll(root, (n) => n.getAttribute("role") === "alert").length, 0);
});

test("errors without data: network error and hosts_unavailable use localized text, never the backend message", async () => {
  responder = async () => reply(503, { error: "hosts_unavailable", message: "BACKEND MESSAGE" });
  let { root } = await mountApp();
  const alert = findAll(root, (n) => n.getAttribute("role") === "alert")[0];
  assert.ok(alert.textContent.includes("The host list is not available"));
  assert.ok(!root.textContent.includes("BACKEND MESSAGE"));
  assert.equal(tag(root, "section").length, 0);
  responder = async () => {
    throw new TypeError("offline");
  };
  ({ root } = await mountApp());
  assert.ok(root.textContent.includes("The server could not be reached"));
  responder = async () => reply(200, overview([entry("a"), entry("b")]));
});

test("empty host list shows the empty text", async () => {
  responder = async () => reply(200, overview([]));
  const { root } = await mountApp();
  assert.ok(root.textContent.includes("No hosts configured."));
  assert.equal(tag(root, "section").length, 0);
  assert.equal(barBadge(root).textContent, "OK");
  responder = async () => reply(200, overview([entry("a"), entry("b")]));
});

test("Reload: disabled while a request runs, triggers an immediate refresh, overlapping refreshes never run twice", async () => {
  const gate = deferred();
  responder = () => gate.promise;
  const { root } = await mountApp();
  assert.equal(calls.length, 1);
  assert.equal(prop(reloadButton(root), "disabled"), true);
  poll().fn();
  reloadButton(root).dispatch("click", { bubbles: true });
  await settle();
  assert.equal(calls.length, 1, "a request is already in flight");
  gate.resolve(reply(200, overview([entry("a")])));
  await settle();
  assert.equal(prop(reloadButton(root), "disabled"), false);

  responder = async () => reply(200, overview([entry("a")], NOW2));
  reloadButton(root).dispatch("click", { bubbles: true });
  await settle();
  assert.equal(calls.length, 2);
  responder = async () => reply(200, overview([entry("a"), entry("b")]));
});

test("Updated line uses the server clock through hm.updated and changes after a refresh", async () => {
  responder = async () => reply(200, overview([entry("a")], NOW1));
  const { root } = await mountApp();
  const text = () => cls(root, "hint")[0].textContent.trim();
  const fmt = (ms) => formatDateTime(ms, "en", { dateStyle: undefined, timeStyle: "medium" });
  assert.equal(text(), `Updated ${fmt(NOW1)}`);
  responder = async () => reply(200, overview([entry("a")], NOW2));
  await tick();
  assert.equal(text(), `Updated ${fmt(NOW2)}`);
  assert.notEqual(fmt(NOW1), fmt(NOW2));
  responder = async () => reply(200, overview([entry("a"), entry("b")]));
});

test("boot time comes from now_ms, not from the browser clock", async () => {
  const realNow = Date.now;
  Date.now = () => 42;
  try {
    responder = async () => reply(200, overview([entry("a")], NOW1));
    const { root } = await mountApp();
    const boot = (r) => tag(tag(r, "tr")[1], "td")[0].textContent;
    const first = boot(root);
    assert.equal(first.includes("1970"), false);
    assert.ok(first.includes(formatDateTime(NOW1 - 400003 * 1000, "en")));
    responder = async () => reply(200, overview([entry("a")], NOW2));
    await tick();
    assert.ok(boot(root).includes(formatDateTime(NOW2 - 400003 * 1000, "en")));
  } finally {
    Date.now = realNow;
    responder = async () => reply(200, overview([entry("a"), entry("b")]));
  }
});

test("language: the switch re-renders in german and issues no new request", async () => {
  const { root } = await mountApp();
  const [select] = tag(root, "select").filter((s) => s.className === "lang-switch");
  select.value = "de";
  select.dispatch("change");
  await settle();
  assert.equal(calls.length, 1);
  assert.ok(root.textContent.includes("Messwerte von A"));
  assert.ok(tag(root, "h3").some((h) => h.textContent === "Letzte Vorfälle"));
  assert.ok(root.textContent.includes("Aktualisiert"));
  select.value = "en";
  select.dispatch("change");
  await settle();
  assert.ok(root.textContent.includes("Updated"));
  setLang("en");
});

test("HA wiring: start once on mount, dispose on unmount", async () => {
  const { root, ha } = await mountApp();
  assert.deepEqual(ha.log.filter((e) => e.endsWith("start")).sort(), ["bridge.start", "sync.start"]);
  assert.equal(ha.log.filter((e) => e.endsWith("dispose")).length, 0);
  render(null, root);
  await settle();
  assert.deepEqual(ha.log.filter((e) => e.endsWith("dispose")).sort(), ["bridge.dispose", "sync.dispose"]);
});

test("HA wiring: without injection and without a parent window nothing throws and the page renders", async () => {
  const saved = globalThis.window;
  globalThis.window = { addEventListener() {}, removeEventListener() {}, document: doc, location: { hash: "", origin: "https://ha.example" } };
  globalThis.window.parent = globalThis.window;
  try {
    calls = [];
    intervals.length = 0;
    const root = doc.createElement("div");
    render(html`<${App} />`, root);
    await settle();
    assert.equal(tag(root, "h1")[0].textContent, "HAOS Monitor");
    assert.equal(tag(root, "h2").length, 2);
    render(null, root);
    await settle();
  } finally {
    globalThis.window = saved;
  }
});

test("hostile overview payload renders as text only and stays accessible", async () => {
  const XSS = "<img src=x onerror=alert(1)><script>boom()</script><b>x</b>";
  responder = async () =>
    reply(
      200,
      overview([
        entry("a", {
          name: XSS,
          host: XSS,
          status: status({ problem: 1, reasons: XSS, dstate_tasks: XSS, kmsg_last: XSS, key_fp: XSS, key_type: XSS }),
          incidents: [XSS],
        }),
      ]),
    );
  const { root } = await mountApp();
  for (const name of ["script", "b"]) assert.equal(tag(root, name).length, 0, name);
  // the only image is the brand icon of the topbar
  assert.deepEqual(tag(root, "img").map((n) => n.className), ["brand-icon"]);
  assert.ok(root.textContent.includes(XSS));
  assert.deepEqual(auditNames(root), []);
  assert.deepEqual(auditTables(root), []);
  responder = async () => reply(200, overview([entry("a"), entry("b")]));
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
