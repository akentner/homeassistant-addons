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
const REPO = "example-org/private-addons";
const GONE = "example-org/gone";
const HASH_A = "0123456789abcdef0123456789abcdef";
const HASH_B = "fedcba9876543210fedcba9876543210";
const BASE = "http://proxy-host:8080/repo";
const PUBLIC = "https://addons.example.invalid/repo";
const user = (over = {}) => ({ user: "alice", source: "gui", created: "2026-11-18T11:00:00Z", protected: false, ...over });
const active = (users, repository = REPO) => ({ repository, active: true, users });
const inactive = (users, repository = GONE) => ({ repository, active: false, users });
const listing = (repositories = [active([user()])]) => ({ now_ms: NOW, repositories });
const urlsOf = (hash, withPublic = false) => ({
  internal: `${BASE}/${REPO}/${hash}`,
  ...(withPublic ? { public: `${PUBLIC}/${REPO}/${hash}` } : {}),
});

// ---- recording fetch stub; routes keyed "METHOD path" (path without the api/ prefix) ----
const reply = (status, data) => ({ ok: status < 400, status, json: async () => data });
let calls = [];
let routes = {};
const setRoutes = (over = {}) => {
  routes = { "GET access": async () => reply(200, listing()), ...over };
};
setRoutes();
globalThis.fetch = async (url, init = {}) => {
  const method = init.method || "GET";
  calls.push({ method, url: String(url), body: init.body });
  const key = `${method} ${String(url).replace(/^api\//, "").split("?")[0]}`;
  const handler = routes[key];
  return handler ? handler(init) : reply(404, { error: "not_found" });
};

globalThis.location = { hash: "#/access" };

const { html, render, Toasts } = await import(new URL("vendor/admin-ui/ui.mjs", STATIC));
const { setLang } = await import(new URL("vendor/admin-ui/i18n.mjs", STATIC));
// Importing app.mjs registers the add-on strings, as on the real page.
const { VIEWS } = await import(new URL("app.mjs", STATIC));
const { default: Access, ACCESS_POLL_MS } = await import(new URL("views/access.mjs", STATIC));
const { default: en } = await import(new URL("strings.en.mjs", STATIC));
setLang("en");

async function mountView() {
  calls = [];
  intervals.length = 0;
  const root = doc.createElement("div");
  render(html`<div><${Access} /><${Toasts} /></div>`, root);
  await settle();
  return root;
}

const tag = (root, name) => findAll(root, (n) => n.localName === name);
const cls = (root, name) => findAll(root, (n) => (n.className || "").split(" ").includes(name));
const buttons = (root, text) => tag(root, "button").filter((b) => b.textContent.trim() === text);
const button = (root, text) => {
  const found = buttons(root, text)[0];
  assert.ok(found, `button "${text}" present`);
  return found;
};
// The table row whose first cell (the label) is exactly `label`.
const rowOf = (root, label) => {
  const row = tag(root, "tr").find((tr) => {
    const first = tag(tr, "td")[0];
    return Boolean(first) && first.textContent.trim() === label;
  });
  assert.ok(row, `row of ${label} present`);
  return row;
};
const dialog = (root) => findAll(root, (n) => n.getAttribute && n.getAttribute("role") === "dialog")[0];
const copyValues = (root) => cls(root, "copy-field").map((f) => tag(f, "input")[0].value);
const type = async (input, value) => {
  input.value = value;
  input.dispatch("input", { bubbles: true });
  await settle();
};
const posts = () => calls.filter((c) => c.method === "POST");
const gets = (path) => calls.filter((c) => c.method === "GET" && c.url === `api/${path}`);

test("tracer: the view is registered, polls api/access every 15 s and lists label, source and created", async () => {
  assert.ok(VIEWS.some((v) => v.id === "access" && v.titleKey === "view.access"));
  assert.equal(ACCESS_POLL_MS, 15000);
  setRoutes();
  const root = await mountView();
  assert.equal(gets("access").length, 1);
  assert.equal(activePoll().ms, 15000);
  const row = rowOf(root, "alice");
  assert.ok(row, "alice row");
  assert.ok(row.textContent.includes("GUI"));
  assert.ok(row.textContent.includes("1 hour ago"), row.textContent);
  render(null, root);
});

test("a hostile label renders as text, never as markup", async () => {
  setRoutes({ "GET access": async () => reply(200, listing([active([user({ user: "<b>x</b>" })])])) });
  const root = await mountView();
  assert.equal(tag(root, "b").length, 0);
  assert.ok(rowOf(root, "<b>x</b>"));
  render(null, root);
});

test("source badges: gui, cli, api and system from the literal table, unknown sources as unknown", async () => {
  const users = [
    user({ user: "a", source: "gui" }),
    user({ user: "b", source: "cli" }),
    user({ user: "c", source: "api" }),
    user({ user: "local", source: "system", protected: true }),
    user({ user: "e", source: null }),
  ];
  setRoutes({ "GET access": async () => reply(200, listing([active(users)])) });
  const root = await mountView();
  const badge = (label) => cls(rowOf(root, label), "badge").map((b) => b.textContent.trim());
  assert.ok(badge("a").includes(en["mrp.source.gui"]));
  assert.ok(badge("b").includes(en["mrp.source.cli"]));
  assert.ok(badge("c").includes(en["mrp.source.api"]));
  assert.ok(badge("local").includes(en["mrp.source.system"]));
  assert.ok(badge("e").includes(en["mrp.source.unknown"]));
  render(null, root);
});

test("protected row: protected badge, Show URLs, but no Rotate and no Revoke", async () => {
  const users = [user(), user({ user: "local", source: "system", protected: true })];
  setRoutes({ "GET access": async () => reply(200, listing([active(users)])) });
  const root = await mountView();
  const local = rowOf(root, "local");
  assert.ok(cls(local, "badge").some((b) => b.textContent.trim() === en["mrp.access.protected"]));
  assert.equal(buttons(local, en["mrp.access.urls.show"]).length, 1);
  assert.equal(buttons(local, en["mrp.access.rotate.button"]).length, 0);
  assert.equal(buttons(local, en["mrp.access.revoke.button"]).length, 0);
  const alice = rowOf(root, "alice");
  assert.equal(buttons(alice, en["mrp.access.rotate.button"]).length, 1);
  assert.equal(buttons(alice, en["mrp.access.revoke.button"]).length, 1);
  assert.ok(!cls(alice, "badge").some((b) => b.textContent.trim() === en["mrp.access.protected"]));
  render(null, root);
});

test("inactive repository: own heading and hint, Revoke only, no add form, no Show URLs, no Rotate", async () => {
  setRoutes({
    "GET access": async () => reply(200, listing([active([]), inactive([user({ user: "bob", source: "cli" })])])),
  });
  const root = await mountView();
  assert.ok(root.textContent.includes(en["mrp.access.inactive"]));
  assert.ok(root.textContent.includes(en["mrp.access.inactive_hint"]));
  assert.ok(root.textContent.includes(en["mrp.access.no_users"]), "empty text of the active repository");
  assert.ok(root.textContent.includes(GONE));
  const bob = rowOf(root, "bob");
  assert.equal(buttons(bob, en["mrp.access.revoke.button"]).length, 1);
  assert.equal(buttons(bob, en["mrp.access.urls.show"]).length, 0);
  assert.equal(buttons(bob, en["mrp.access.rotate.button"]).length, 0);
  assert.equal(tag(root, "form").length, 1, "only the active repository has an add form");
  render(null, root);
});

test("no CopyField exists before an action; Show URLs fetches on demand and Hide drops them", async () => {
  setRoutes({ "GET access/example-org/private-addons/alice/urls": async () => reply(200, urlsOf(HASH_A, true)) });
  const root = await mountView();
  assert.equal(cls(root, "copy-field").length, 0);
  assert.ok(!root.textContent.includes(HASH_A));
  button(rowOf(root, "alice"), en["mrp.access.urls.show"]).dispatch("click", { bubbles: true });
  await settle();
  assert.equal(gets("access/example-org/private-addons/alice/urls").length, 1);
  assert.deepEqual(copyValues(root), [`${BASE}/${REPO}/${HASH_A}`, `${PUBLIC}/${REPO}/${HASH_A}`]);
  button(root, en["mrp.access.urls.hide"]).dispatch("click", { bubbles: true });
  await settle();
  assert.equal(cls(root, "copy-field").length, 0);
  render(null, root);
});

test("rotate dialog: type-to-confirm with the label, consequences stated, POST with {confirm}, new URLs shown", async () => {
  setRoutes({
    "POST access/example-org/private-addons/alice/rotate": async () =>
      reply(200, { repository: REPO, user: "alice", source: "gui", created: "2026-11-18T12:00:00Z", urls: urlsOf(HASH_B) }),
  });
  const root = await mountView();
  button(rowOf(root, "alice"), en["mrp.access.rotate.button"]).dispatch("click", { bubbles: true });
  await settle();
  const dlg = dialog(root);
  assert.ok(dlg, "dialog open");
  const message = dlg.textContent;
  for (const part of ["new repository", "reinstall", "back up", "alice"]) assert.ok(message.includes(part), part);
  const confirm = button(dlg, en["mrp.access.rotate.confirm"]);
  assert.ok(cls(confirm, "danger").length === 1 || (confirm.className || "").includes("danger"));
  const phrase = tag(dlg, "input")[0];
  await type(phrase, "Alice");
  assert.equal(prop(button(dialog(root), en["mrp.access.rotate.confirm"]), "disabled"), true);
  assert.equal(posts().length, 0);
  await type(phrase, "alice");
  const go = button(dialog(root), en["mrp.access.rotate.confirm"]);
  assert.equal(prop(go, "disabled"), false);
  const before = gets("access").length;
  go.dispatch("click", { bubbles: true });
  await settle(10);
  assert.equal(posts().length, 1);
  assert.equal(posts()[0].url, "api/access/example-org/private-addons/alice/rotate");
  assert.equal(posts()[0].body, '{"confirm":"alice"}');
  assert.equal(dialog(root), undefined, "dialog closed");
  assert.deepEqual(copyValues(root), [`${BASE}/${REPO}/${HASH_B}`]);
  assert.ok(root.textContent.includes(en["mrp.access.urls.secret"]));
  assert.ok(gets("access").length > before, "list reloaded");
  render(null, root);
});

test("revoke dialog: exact label sends DELETE with {confirm} and reloads the list", async () => {
  setRoutes({ "DELETE access/example-org/private-addons/alice": async () => reply(204, null) });
  const root = await mountView();
  button(rowOf(root, "alice"), en["mrp.access.revoke.button"]).dispatch("click", { bubbles: true });
  await settle();
  const dlg = dialog(root);
  assert.ok(dlg.textContent.includes("alice"));
  assert.ok(dlg.textContent.includes("immediately"), dlg.textContent);
  await type(tag(dlg, "input")[0], "alice");
  const before = gets("access").length;
  button(dialog(root), en["mrp.access.revoke.confirm"]).dispatch("click", { bubbles: true });
  await settle(10);
  const dels = calls.filter((c) => c.method === "DELETE");
  assert.equal(dels.length, 1);
  assert.equal(dels[0].url, "api/access/example-org/private-addons/alice");
  assert.equal(dels[0].body, '{"confirm":"alice"}');
  assert.equal(dialog(root), undefined);
  assert.ok(gets("access").length > before, "list reloaded");
  render(null, root);
});

test("revoke of an inactive entry uses the stored repository path", async () => {
  setRoutes({
    "GET access": async () => reply(200, listing([active([]), inactive([user({ user: "bob", source: "cli" })])])),
    "DELETE access/example-org/gone/bob": async () => reply(204, null),
  });
  const root = await mountView();
  button(rowOf(root, "bob"), en["mrp.access.revoke.button"]).dispatch("click", { bubbles: true });
  await settle();
  await type(tag(dialog(root), "input")[0], "bob");
  button(dialog(root), en["mrp.access.revoke.confirm"]).dispatch("click", { bubbles: true });
  await settle(10);
  const dels = calls.filter((c) => c.method === "DELETE");
  assert.equal(dels.length, 1);
  assert.equal(dels[0].url, "api/access/example-org/gone/bob");
  render(null, root);
});

test("an API error in the dialog is shown through tError, never the server message", async () => {
  setRoutes({
    "DELETE access/example-org/private-addons/alice": async () =>
      reply(409, { error: "protected", message: "<b>server</b> text" }),
  });
  const root = await mountView();
  button(rowOf(root, "alice"), en["mrp.access.revoke.button"]).dispatch("click", { bubbles: true });
  await settle();
  await type(tag(dialog(root), "input")[0], "alice");
  button(dialog(root), en["mrp.access.revoke.confirm"]).dispatch("click", { bubbles: true });
  await settle(10);
  const dlg = dialog(root);
  assert.ok(dlg, "dialog stays open");
  assert.ok(dlg.textContent.includes("This item is protected and cannot be changed"), dlg.textContent);
  assert.ok(!root.textContent.includes("server"));
  assert.equal(tag(root, "b").length, 0);
  render(null, root);
});

test("add form: an invalid label shows the error and sends nothing; a valid one posts {user} and shows the URLs", async () => {
  setRoutes({
    "POST access/example-org/private-addons": async () =>
      reply(201, { repository: REPO, user: "carol", source: "gui", created: "2026-11-18T12:00:00Z", urls: urlsOf(HASH_B, true) }),
  });
  const root = await mountView();
  const form = tag(root, "form")[0];
  const input = tag(form, "input")[0];
  await type(input, "a b");
  form.dispatch("submit", { bubbles: true });
  await settle();
  assert.equal(posts().length, 0);
  assert.ok(findAll(root, (n) => n.getAttribute && n.getAttribute("role") === "alert").some((n) => n.textContent.includes(en["mrp.access.add.invalid"])));
  assert.equal(input.getAttribute("aria-invalid"), "true");
  await type(input, "carol");
  form.dispatch("submit", { bubbles: true });
  await settle(10);
  assert.equal(posts().length, 1);
  assert.equal(posts()[0].url, "api/access/example-org/private-addons");
  assert.equal(posts()[0].body, '{"user":"carol"}');
  assert.ok(root.textContent.includes(en["mrp.access.urls.secret"]));
  assert.deepEqual(copyValues(root), [`${BASE}/${REPO}/${HASH_B}`, `${PUBLIC}/${REPO}/${HASH_B}`]);
  render(null, root);
});

test("an unreadable access store shows the localised error", async () => {
  setRoutes({ "GET access": async () => reply(503, { error: "access_unavailable", message: "x" }) });
  const root = await mountView();
  assert.ok(root.textContent.includes(en["errors.access_unavailable"]));
  render(null, root);
});

// ---- accessibility audits ----

test("a11y: named controls and scoped table headers with active, protected and inactive rows and an open dialog", async () => {
  setRoutes({
    "GET access": async () =>
      reply(
        200,
        listing([
          active([user(), user({ user: "local", source: "system", protected: true })]),
          active([], "example-org/other"),
          inactive([user({ user: "bob", source: "cli" })]),
        ]),
      ),
    "GET access/example-org/private-addons/alice/urls": async () => reply(200, urlsOf(HASH_A, true)),
  });
  const root = await mountView();
  assert.deepEqual(auditNames(root), []);
  assert.deepEqual(auditTables(root), []);
  button(rowOf(root, "alice"), en["mrp.access.urls.show"]).dispatch("click", { bubbles: true });
  await settle();
  assert.deepEqual(auditNames(root), []);
  button(rowOf(root, "alice"), en["mrp.access.rotate.button"]).dispatch("click", { bubbles: true });
  await settle();
  assert.ok(dialog(root));
  assert.deepEqual(auditNames(root), []);
  const ids = findAll(root, (n) => n.getAttribute && n.getAttribute("id")).map((n) => n.getAttribute("id"));
  assert.equal(new Set(ids).size, ids.length, "ids are unique");
  render(null, root);
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
