import test from "node:test";
import assert from "node:assert/strict";
import { install, findAll, prop, settle } from "../../admin-ui/tests/js/fakedom.mjs";

const doc = install();
const listeners = new Map();
window.addEventListener = (type, fn) => {
  if (!listeners.has(type)) listeners.set(type, new Set());
  listeners.get(type).add(fn);
};
window.removeEventListener = (type, fn) => listeners.get(type)?.delete(fn);
globalThis.location = { href: "https://ha.example/api/hassio_ingress/test/", hash: "" };
const STATIC = new URL("../app/web/static/", import.meta.url);
const { html, render } = await import(new URL("vendor/admin-ui/ui.mjs", STATIC));
const { setLang, t } = await import(new URL("vendor/admin-ui/i18n.mjs", STATIC));
const { installTerminalClipboard } = await import(new URL("terminal-clipboard.mjs", STATIC));
const { App, openCodeUrl } = await import(new URL("app.mjs", STATIC));
const byId = (root, id) => findAll(root, n => prop(n, "id") === id)[0];
const versions = { addon: "1.3.1-0", claude: "2.0.0", herdr: "0.9.3", opencode: "2.2.6", codex: "0.167.0" };

async function mount(props = {}) {
  location.hash = "";
  setLang("en");
  const events = [];
  const bridge = {
    getState: () => ({ kiosk: false, status: "idle" }), subscribe: () => () => {},
    start: () => events.push("bridge.start"), dispose: () => events.push("bridge.dispose"),
  };
  const sync = { start: () => events.push("sync.start"), dispose: () => events.push("sync.dispose") };
  const root = doc.createElement("div");
  doc.getElementById = id => byId(root, id) || null;
  render(html`<${App} ha=${{ bridge, sync }} fetchVersions=${async () => versions}
    terminalSetup=${() => {
      events.push("terminal.setup");
      return { refreshLabels: () => events.push("terminal.labels"), dispose: () => events.push("terminal.dispose") };
    }} ...${props} />`, root);
  await settle();
  return { root, events, async close() { render(null, root); await settle(); } };
}

async function navigate(id) {
  location.hash = `#/${id}`;
  for (const fn of listeners.get("hashchange") || []) fn();
  await settle();
}

test("uses the shared topbar and starts HA enhancement and terminal helpers once", async () => {
  const state = await mount();
  try {
    assert.equal(findAll(state.root, n => n.localName === "header").length, 1);
    assert.equal(findAll(state.root, n => n.localName === "h1")[0].textContent, "Coding Assistants");
    assert.ok(state.root.textContent.includes(versions.addon));
    assert.deepEqual(state.events.filter(x => x.endsWith("start") || x.endsWith("setup")), ["bridge.start", "sync.start", "terminal.setup"]);
    assert.equal(prop(byId(state.root, "frameTerminal"), "src"), "./terminal/");
    assert.equal(prop(byId(state.root, "frameTerminal"), "allow"), "clipboard-write");
  } finally { await state.close(); }
  assert.ok(state.events.includes("bridge.dispose"));
  assert.ok(state.events.includes("sync.dispose"));
  assert.ok(state.events.includes("terminal.dispose"));
});

test("navigation lazy-loads Services and preserves both iframe instances across routes and languages", async () => {
  const state = await mount();
  try {
    const terminal = byId(state.root, "frameTerminal");
    const services = byId(state.root, "frameServices");
    assert.ok(!prop(services, "src"));
    await navigate("services");
    assert.equal(prop(services, "src"), "./services/");
    assert.equal(String(prop(terminal, "hidden")), "true");
    await navigate("info");
    setLang("de");
    await settle();
    assert.ok(state.root.textContent.includes("Auswahl kopieren"));
    assert.ok(state.root.textContent.includes("Versionen"));
    await navigate("terminal");
    assert.equal(byId(state.root, "frameTerminal"), terminal);
    assert.equal(byId(state.root, "frameServices"), services);
    assert.equal(prop(services, "src"), "./services/");
    assert.equal(prop(terminal, "src"), "./terminal/");
    assert.notEqual(String(prop(terminal, "hidden")), "true");
    assert.equal(state.events.filter(x => x === "terminal.setup").length, 1);
  } finally { await state.close(); }
});

test("the legacy Info entry shows version rows; untrusted version values remain text", async () => {
  const hostile = "<img src=x onerror=alert(1)>";
  const state = await mount({ initialView: "info", fetchVersions: async () => ({ ...versions, claude: hostile }) });
  try {
    assert.equal(byId(state.root, "v-claude").textContent, hostile);
    assert.equal(byId(state.root, "v-herdr").textContent, versions.herdr);
    assert.equal(byId(state.root, "v-codex").textContent, versions.codex);
    assert.equal(findAll(state.root, n => prop(n, "src") === "x").length, 0);
    assert.ok(findAll(state.root, n => n.localName === "th").every(n => prop(n, "scope") === "row"));
  } finally { await state.close(); }
});

test("a real clipboard selection stays usable and its status translates after a shell rerender", async () => {
  const originalClipboard = navigator.clipboard;
  const writes = [];
  navigator.clipboard = { writeText: async text => { writes.push(text); } };
  let receive;
  const state = await mount({ terminalSetup: () => {
    const frame = doc.getElementById("frameTerminal");
    frame.contentDocument = { readyState: "complete" };
    frame.classList = { contains: name => (frame.className || "").split(" ").includes(name) };
    frame.contentWindow = { term: { parser: { registerOscHandler(code, handler) {
      assert.equal(code, 52);
      receive = handler;
      return { dispose() {} };
    } } } };
    return installTerminalClipboard(t);
  } });
  try {
    receive(`c;${Buffer.from("pane text").toString("base64")}`);
    await settle();
    assert.deepEqual(writes, ["pane text"]);
    assert.equal(byId(state.root, "clipboardStatus").textContent, "Copied");
    assert.equal(byId(state.root, "copySelection").disabled, false);
    setLang("de");
    await settle();
    assert.equal(byId(state.root, "clipboardStatus").textContent, "Kopiert");
    assert.equal(byId(state.root, "copySelection").disabled, false);
  } finally {
    await state.close();
    if (originalClipboard === undefined) delete navigator.clipboard;
    else navigator.clipboard = originalClipboard;
  }
});

test("versions use the relative shared API client and failure leaves the terminal mounted", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push([url, init.credentials]);
    throw new Error("offline");
  };
  const state = await mount({ fetchVersions: undefined });
  try {
    assert.deepEqual(calls, [["api/versions", "same-origin"]]);
    assert.ok(byId(state.root, "frameTerminal"));
    assert.ok(findAll(state.root, n => prop(n, "role") === "alert").length > 0);
  } finally { await state.close(); globalThis.fetch = originalFetch; }
});

test("OpenCode link preserves the host and clears ingress path, query and hash", () => {
  assert.equal(openCodeUrl("https://ha.example:8123/api/hassio_ingress/secret/?x=1#/info"), "https://ha.example:4096/");
  assert.equal(openCodeUrl("http://[::1]:8123/addon/"), "http://[::1]:4096/");
});
