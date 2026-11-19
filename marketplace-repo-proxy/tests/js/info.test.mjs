import test from "node:test";
import assert from "node:assert/strict";
import { install, findAll, settle } from "./fakedom.mjs";
import { auditNames, auditTables } from "./a11y_audit.mjs";

const doc = install();
const STATIC = new URL("../../app/web/static/", import.meta.url);

// ---- recording fetch stub: the Info view itself must never call it ----
const reply = (status, data) => ({ ok: status < 400, status, json: async () => data });
let calls = [];
globalThis.fetch = async (url, init = {}) => {
  calls.push({ method: init.method || "GET", url: String(url) });
  if (String(url).replace(/^api\//, "") === "meta") return reply(200, { version: null });
  return reply(404, { error: "not_found" });
};

globalThis.location = { hash: "#/info" };

const { html, render } = await import(new URL("vendor/admin-ui/ui.mjs", STATIC));
const { setLang } = await import(new URL("vendor/admin-ui/i18n.mjs", STATIC));
// Importing app.mjs registers the add-on strings, as on the real page.
const { App, VIEWS } = await import(new URL("app.mjs", STATIC));
const { default: Info } = await import(new URL("views/info.mjs", STATIC));
setLang("en");

const tag = (root, name) => findAll(root, (n) => n.localName === name);
const cls = (root, name) => findAll(root, (n) => (n.className || "").split(" ").includes(name));

function makeHa() {
  return {
    bridge: { getState: () => ({ kiosk: false }), subscribe: () => () => {}, toggleMenu() {}, start() {}, dispose() {} },
    sync: { start() {}, dispose() {} },
  };
}

async function mountView() {
  calls = [];
  const root = doc.createElement("div");
  render(html`<${Info} />`, root);
  await settle();
  return root;
}

test("tracer: #/info renders the Info view in the app and the navigation lists Repositories, Access, Info", async () => {
  calls = [];
  const root = doc.createElement("div");
  render(html`<${App} ha=${makeHa()} />`, root);
  await settle(10);
  const links = cls(root, "topnav-link");
  assert.deepEqual(
    links.map((a) => a.textContent.trim()),
    ["Repositories", "Access", "Info"],
  );
  assert.deepEqual(VIEWS.map((v) => v.id), ["repositories", "access", "info"]);
  assert.deepEqual(VIEWS.at(-1), { id: "info", titleKey: "view.info" });
  const titles = tag(root, "h2").map((h) => h.textContent.trim());
  assert.deepEqual(titles, ["Add a store URL in Home Assistant", "Publish through a reverse proxy", "Rotate a store URL"]);
  // Only the shell's own api/meta request; the view adds none.
  assert.deepEqual(
    calls.map((c) => c.url),
    ["api/meta"],
  );
  render(null, root);
});

test("view: three sections with setup, reverse proxy and rotation text in English", async () => {
  const root = await mountView();
  const sections = tag(root, "section");
  assert.equal(sections.length, 3);
  for (const s of sections) assert.ok(s.className.split(" ").includes("card"), s.className);
  const [setup, proxy, rotation] = sections.map((s) => s.textContent);
  assert.match(setup, /Access view/);
  assert.match(setup, /host name/);
  assert.match(setup, /internal URL/i);
  assert.match(setup, /secret/i);
  assert.match(proxy, /TLS/);
  assert.match(proxy, /cach/);
  assert.match(proxy, /\/repo\/\*/);
  assert.match(proxy, /log/);
  assert.match(rotation, /back up/i);
  assert.match(rotation, /reinstall/);
  assert.match(rotation, /remove the old repository/i);
  assert.equal(calls.length, 0);
  render(null, root);
});

test("view: German text is real German and differs from the English text", async () => {
  const en = (await mountView()).textContent;
  setLang("de");
  try {
    const root = await mountView();
    const de = root.textContent;
    assert.notEqual(de, en);
    assert.match(de, /Zugriff/);
    assert.match(de, /TLS/);
    assert.match(de, /Add-ons darüber neu/);
    assert.equal(calls.length, 0);
    render(null, root);
  } finally {
    setLang("en");
  }
});

test("idempotent: rendering twice (unmount, mount) gives identical text and no request", async () => {
  const first = await mountView();
  const a = first.textContent;
  render(null, first);
  const second = await mountView();
  assert.equal(second.textContent, a);
  assert.ok(a.length > 200);
  await settle(10);
  assert.equal(calls.length, 0);
  render(null, second);
});

test("static: no button, no input, no link and no table; a11y audits report nothing", async () => {
  const root = await mountView();
  for (const name of ["button", "input", "select", "textarea", "a", "form"]) assert.equal(tag(root, name).length, 0, name);
  assert.deepEqual(auditNames(root), []);
  assert.deepEqual(auditTables(root), []);
  render(null, root);
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
