import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { install, findAll, findByText, settle } from "./fakedom.mjs";

const doc = install();
const STATIC = new URL("../../../app/web/static/", import.meta.url);
const example = JSON.parse(readFileSync(new URL("../../../docs/state.example.json", import.meta.url), "utf8"));
const clone = (o) => JSON.parse(JSON.stringify(o));
const XSS = "<img src=x onerror=alert(1)><script>boom()</script>";

// ---- window / location stub with a controllable hashchange, storage and clipboard ----
const handlers = new Set();
globalThis.window = {
  addEventListener: (type, fn) => type === "hashchange" && handlers.add(fn),
  removeEventListener: (type, fn) => type === "hashchange" && handlers.delete(fn),
};
globalThis.location = { hash: "" };
const store = {};
globalThis.localStorage = { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => (store[k] = String(v)) };
const navigate = async (hash) => {
  globalThis.location.hash = hash;
  for (const fn of [...handlers]) fn({});
  await settle();
};
let clipboard = null;
Object.defineProperty(globalThis, "navigator", {
  value: { language: "en", clipboard: { writeText: async (text) => (clipboard = text) } },
  configurable: true,
});

// ---- fetch stub ----
let calls = [];
let statusPayload = clone(example);
let statusFails = false;
let syncReply = { status: 202, data: { started: true } };
let previewReply = { status: 200, data: { added: ["new_key"], removed: ["old_key"], changed: [], errors: [] } };
const reply = (status, data) => ({ ok: status < 400, status, json: async () => data });
globalThis.fetch = async (url, init = {}) => {
  const method = init.method || "GET";
  calls.push({ method, url, body: init.body ? JSON.parse(init.body) : undefined });
  if (url === "api/status.json") return statusFails ? reply(500, { error: "internal_error", message: "SERVER TEXT" }) : reply(200, statusPayload);
  if (url.startsWith("api/sync")) return reply(syncReply.status, syncReply.data);
  if (url === "api/preview") return reply(previewReply.status, previewReply.data);
  return reply(404, { error: "not_found" });
};

const { html, render } = await import(new URL("vendor/admin-ui/ui.mjs", STATIC));
const i18n = await import(new URL("vendor/admin-ui/i18n.mjs", STATIC));
const model = await import(new URL("model.mjs", STATIC));
const parts = await import(new URL("parts.mjs", STATIC));
const { App, readTab, writeTab } = await import(new URL("app.mjs", STATIC));
const { default: KeysView } = await import(new URL("views/keys.mjs", STATIC));
const { default: SyntheticView } = await import(new URL("views/synthetic.mjs", STATIC));
const { default: UsageView } = await import(new URL("views/usage.mjs", STATIC));
const { default: EventsView } = await import(new URL("views/events.mjs", STATIC));
i18n.setLang("en");

const mount = async (vnode) => {
  const root = doc.createElement("div");
  render(vnode, root);
  await settle();
  return root;
};
const buttons = (root, text) => findAll(root, (n) => n.localName === "button" && n.textContent.trim() === text);
const click = async (node) => {
  node.dispatch("click", { bubbles: true });
  await settle();
};
const type = async (input, value) => {
  input.value = value;
  input.dispatch("input");
  await settle();
};
const chips = (root) => findAll(root, (n) => n.className.split(" ").includes("key"));
const names = (root) => chips(root).map((n) => n.textContent);
const ALLOWED = new Set(["div", "span", "section", "h1", "h2", "h3", "p", "button", "table", "caption", "thead", "tbody", "tr", "th", "td", "code",
  "details", "summary", "input", "select", "option", "header", "nav", "main", "a", "img", "label"]);
const forbidden = (root) => findAll(root, (n) => ["script", "style", "iframe"].includes(n.localName) || (n.localName === "img" && n.getAttribute("src") === "x"));
const dblclick = (node) => {
  const kind = ["dblclick", "DblClick"].find((k) => (node.listeners[k] || []).length);
  assert.ok(kind, "double click handler registered");
  node.dispatch(kind);
};

// ---- model ----
test("filterKeys is a case-insensitive substring filter", () => {
  const list = ["MQTT_password", "mqtt_username", "db_dsn"];
  assert.deepEqual(model.filterKeys(list, "MQTT"), ["MQTT_password", "mqtt_username"]);
  assert.deepEqual(model.filterKeys(list, " dsn "), ["db_dsn"]);
  assert.deepEqual(model.filterKeys(list, ""), list);
  assert.deepEqual(model.filterKeys(list, "zzz"), []);
  assert.deepEqual(model.filterKeys("nope", "a"), []);
  assert.deepEqual(model.filterKeys(null, null), []);
});

test("pickTab: hash first, stored second, first tab last", () => {
  assert.equal(model.pickTab("usage", "events"), "usage");
  assert.equal(model.pickTab(null, "events"), "events");
  assert.equal(model.pickTab("bogus", "synthetic"), "synthetic");
  assert.equal(model.pickTab("bogus", "bogus"), "keys");
  assert.equal(model.pickTab(undefined, null), "keys");
});

test("statusInfo maps ok, stale and unknown values", () => {
  assert.deepEqual(model.statusInfo(example), { id: "ok", kind: "ok" });
  assert.equal(model.statusInfo({ status: "ok", stale: true }).id, "stale");
  assert.equal(model.statusInfo({ status: "ok", age_seconds: 601, interval: 300 }).id, "stale");
  assert.equal(model.statusInfo({}).id, "starting");
  assert.equal(model.statusInfo({ status: "<b>x" }).id, "starting");
  assert.equal(model.statusInfo({ status: "error" }).kind, "error");
});

test("copyText: clipboard, textarea fallback and failure", async () => {
  let written = null;
  assert.equal(await model.copyText("a", { nav: { clipboard: { writeText: async (t) => (written = t) } } }), "copied");
  assert.equal(written, "a");
  const body = doc.createElement("body");
  const fake = (copyOk) => ({ ...doc, createElement: (t) => doc.createElement(t), body, execCommand: () => copyOk });
  const blocked = { clipboard: { writeText: async () => Promise.reject(new Error("blocked")) } };
  assert.equal(await model.copyText("b", { nav: blocked, doc: fake(true) }), "copied");
  assert.equal(await model.copyText("c", { nav: blocked, doc: fake(false) }), "selected");
  assert.equal(body.childNodes.length, 0, "textarea removed again");
  assert.equal(await model.copyText("d", { nav: blocked, doc: {} }), "failed");
});

// ---- views ----
test("keys view: sections, synthetic badge, search and cap", async () => {
  const s = clone(example);
  s.keys.names = ["db_dsn", "mqtt_password", "mqtt_username"];
  s.keys.added = ["db_dsn"];
  s.keys.synthetic = ["db_dsn"];
  const root = await mount(html`<${KeysView} state=${s} />`);
  assert.match(root.textContent, /Added \(1\)/);
  assert.match(root.textContent, /Changed \(1\)/);
  assert.doesNotMatch(root.textContent, /Removed/);
  assert.match(root.textContent, /All keys \(3\)/);
  assert.equal(findByText(root, "span", "synthetic").length, 2, "db_dsn in Added and All keys");
  const input = findAll(root, (n) => n.localName === "input")[0];
  await type(input, "MQTT");
  assert.match(root.textContent, /All keys \(2\)/);
  assert.doesNotMatch(root.textContent, /db_dsn/);
  const big = clone(example);
  big.keys = { names: Array.from({ length: 600 }, (_, i) => `k${i}`), added: [], removed: [], changed: [] };
  const bigRoot = await mount(html`<${KeysView} state=${big} />`);
  assert.equal(chips(bigRoot).length, 500);
  assert.match(bigRoot.textContent, /\+100 more/);
});

test("double click on a key name copies it and says so", async () => {
  clipboard = null;
  const s = clone(example);
  const root = await mount(html`<div><${KeysView} state=${s} /><${parts.KeyList} names=${["x"]} /></div>`);
  const toasts = await mount(html`<${(await import(new URL("vendor/admin-ui/ui.mjs", STATIC))).Toasts} />`);
  dblclick(chips(root).find((n) => n.textContent === "mqtt_username"));
  await settle();
  assert.equal(clipboard, "mqtt_username");
  assert.match(toasts.textContent, /Copied/);
});

test("synthetic view: empty state, statuses, template as text", async () => {
  assert.match((await mount(html`<${SyntheticView} state=${{}} />`)).textContent, /No synthetic keys configured/);
  const s = { synthetic: [
    { name: "a", template: "{{ x }}", refs: ["x"], status: "ok", error_code: null },
    { name: "b", template: "t", refs: [], status: "pending", error_code: null },
    { name: "c", template: "t", refs: [], status: "error", error_code: "synthetic_render_failed" },
  ] };
  const root = await mount(html`<${SyntheticView} state=${s} />`);
  assert.match(root.textContent, /parsed \(not rendered yet\)/);
  assert.match(root.textContent, /error synthetic_render_failed/);
  assert.match(root.textContent, /\{\{ x \}\}/);
});

test("usage view: disabled, missing first, search", async () => {
  assert.match((await mount(html`<${UsageView} state=${{ usage: { enabled: false } }} />`)).textContent, /Usage scan is off/);
  const usage = { enabled: true, roots: ["config"], scanned_at: "2026-10-27T10:00:00Z", files_scanned: 3, truncated: true,
    missing: { gone: { count: 1, refs: [{ file: "a.yaml", line: 4 }] } },
    used: { mqtt_password: { count: 2, refs: [{ file: "b.yaml", line: 1 }] }, db_dsn: { count: 1, refs: [] } },
    unused: ["old_key"] };
  const root = await mount(html`<${UsageView} state=${{ usage }} />`);
  const t = root.textContent;
  assert.match(t, /The scan stopped at a limit/);
  assert.match(t, /missing in secrets\.yaml \(1\)/);
  assert.match(t, /a\.yaml:4/);
  assert.match(t, /Unused \(1\)/);
  assert.match(t, /Used \(2\)/);
  assert.match(t, /2 uses/);
  await type(findAll(root, (n) => n.localName === "input")[0], "MQTT");
  assert.match(root.textContent, /mqtt_password/);
  assert.doesNotMatch(root.textContent, /db_dsn|gone|old_key/);
});

test("events view: capped at 100, empty text", async () => {
  const events = Array.from({ length: 150 }, (_, i) => ({ at: "2026-10-27T10:00:00Z", level: "info", code: "c", message: `m${i}` }));
  const root = await mount(html`<${EventsView} state=${{ events }} />`);
  assert.equal(findAll(root, (n) => n.localName === "tbody")[0].childNodes.length, 100);
  assert.match((await mount(html`<${EventsView} state=${{}} />`)).textContent, /No events/);
});

test("general card: check block only when present, disabled and error cases", async () => {
  const render1 = async (s) => (await mount(html`<${parts.GeneralCard} state=${s} now=${Date.now()} />`)).textContent;
  assert.match(await render1(example), /Change check/);
  const old = clone(example);
  delete old.check;
  assert.doesNotMatch(await render1(old), /Change check/);
  const off = clone(example);
  off.check = { enabled: false, interval: 0, last_check_at: null, result: null };
  assert.match(await render1(off), /disabled/);
  const err = clone(example);
  err.check.result = "error";
  err.check.error_code = "git_auth_failed";
  const t = await render1(err);
  assert.match(t, /git_auth_failed/);
});

test("providers card shows revision and the empty state", async () => {
  assert.match((await mount(html`<${parts.ProvidersCard} state=${example} />`)).textContent, /1761560000/);
  assert.match((await mount(html`<${parts.ProvidersCard} state=${{}} />`)).textContent, /No providers reported yet/);
});

test("missing and garbage blocks never throw", async () => {
  const garbage = { keys: 3, providers: [], events: "x", usage: "u", synthetic: {}, check: 7, guard: "g", versions: [], items: "many" };
  for (const s of [{}, garbage]) {
    for (const [name, C] of [["keys", KeysView], ["synthetic", SyntheticView], ["usage", UsageView], ["events", EventsView], ["general", parts.GeneralCard], ["providers", parts.ProvidersCard], ["guard", parts.GuardCard]]) {
      await assert.doesNotReject(() => mount(html`<${C} state=${s} onApply=${async () => {}} />`), name);
    }
  }
});

test("hostile strings in state stay text, never elements", async () => {
  const s = clone(example);
  s.keys = { names: [XSS, "ok"], added: [XSS], removed: [XSS], changed: [XSS], synthetic: [XSS] };
  s.events = [{ at: XSS, level: XSS, code: XSS, message: XSS }];
  s.providers.bitwarden.problems = [{ severity: XSS, code: XSS, message: XSS }];
  s.providers.bitwarden.revision = XSS;
  s.synthetic = [{ name: XSS, template: XSS, refs: [XSS], status: "error", error_code: XSS }];
  s.usage = { enabled: true, roots: [XSS], scanned_at: XSS, files_scanned: 1,
    missing: { [XSS]: { count: 1, refs: [{ file: XSS, line: 1 }] } }, used: { [XSS]: { count: 1, refs: [{ file: XSS, line: 2 }] } }, unused: [XSS] };
  s.check = { enabled: true, interval: XSS, last_check_at: XSS, result: XSS, error_code: XSS };
  s.error_code = "shrink_guard";
  s.guard = { new_items: XSS, last_items: XSS, removed: [XSS], added: [XSS], changed: [XSS] };
  for (const [name, C] of [["keys", KeysView], ["synthetic", SyntheticView], ["usage", UsageView], ["events", EventsView], ["general", parts.GeneralCard], ["providers", parts.ProvidersCard], ["guard", parts.GuardCard]]) {
    const root = await mount(html`<${C} state=${s} onApply=${async () => {}} />`);
    assert.deepEqual(forbidden(root), [], name);
    for (const n of findAll(root, () => true)) assert.ok(ALLOWED.has(n.localName), `${name}: unexpected <${n.localName}>`);
  }
  const preview = await mount(html`<${parts.PreviewPanel} result=${{ added: [XSS], errors: [XSS, { code: XSS }] }} onClose=${() => {}} />`);
  assert.deepEqual(forbidden(preview), []);
  assert.ok(preview.textContent.includes(XSS));
});

// ---- guard card ----
const guardState = () => {
  const s = clone(example);
  s.error_code = "shrink_guard";
  s.guard = { new_items: 1, last_items: 9, removed: ["a", "b"], added: ["c"], changed: [] };
  return s;
};

test("guard card only for shrink_guard with an object", async () => {
  const shows = async (s) => (await mount(html`<${parts.GuardCard} state=${s} onApply=${async () => {}} />`)).textContent.includes("shrink guard");
  assert.equal(await shows(guardState()), true);
  assert.equal(await shows({ ...example, guard: guardState().guard }), false);
  assert.equal(await shows({ ...guardState(), guard: null }), false);
  assert.equal(await shows({ ...guardState(), guard: [1] }), false);
});

test("Apply anyway needs the typed word (no window.confirm) and then calls onApply", async () => {
  globalThis.confirm = () => assert.fail("window.confirm must not be used");
  let applied = 0;
  const root = await mount(html`<${parts.GuardCard} state=${guardState()} onApply=${async () => void (applied += 1)} />`);
  assert.match(root.textContent, /Would be removed \(2\)/);
  await click(buttons(root, "Apply anyway")[0]);
  assert.match(root.textContent, /Remove 2 keys from secrets\.yaml\?/);
  const confirmBtn = buttons(root, "Remove keys")[0];
  assert.equal(confirmBtn.disabled, true);
  const input = findAll(root, (n) => n.localName === "input")[0];
  await type(input, "remov");
  assert.equal(buttons(root, "Remove keys")[0].disabled, true);
  await type(input, "remove");
  assert.equal(buttons(root, "Remove keys")[0].disabled, false);
  await click(buttons(root, "Remove keys")[0]);
  assert.equal(applied, 1);
  assert.equal(buttons(root, "Remove keys").length, 0, "dialog closed after success");
  delete globalThis.confirm;
});

test("cancel in the confirm dialog does not apply", async () => {
  let applied = 0;
  const root = await mount(html`<${parts.GuardCard} state=${guardState()} onApply=${async () => void (applied += 1)} />`);
  await click(buttons(root, "Apply anyway")[0]);
  await click(buttons(root, "Cancel")[0]);
  assert.equal(applied, 0);
  assert.equal(buttons(root, "Remove keys").length, 0);
});

test("the confirm word follows the language", async () => {
  i18n.setLang("de");
  const root = await mount(html`<${parts.GuardCard} state=${guardState()} onApply=${async () => {}} />`);
  await click(buttons(root, "Trotzdem übernehmen")[0]);
  assert.match(root.textContent, /„?"?entfernen"?/);
  await type(findAll(root, (n) => n.localName === "input")[0], "entfernen");
  assert.equal(buttons(root, "Schlüssel entfernen")[0].disabled, false);
  i18n.setLang("en");
});

// ---- App ----
const mountApp = async (hash = "") => {
  calls = [];
  statusFails = false;
  globalThis.location.hash = hash;
  const root = await mount(html`<${App} />`);
  await settle(10);
  return root;
};

test("app loads api/status.json (relative) and shows badges and sections", async () => {
  statusPayload = clone(example);
  const root = await mountApp();
  assert.ok(calls.some((c) => c.method === "GET" && c.url === "api/status.json"));
  for (const c of calls) assert.ok(!/^(\/|[a-z][a-z0-9+.-]*:)/i.test(c.url), c.url);
  assert.equal(findByText(root, "h1", "Secrets Sync").length, 1);
  const t = root.textContent;
  for (const needle of ["OK", "42 items", "v0.1.0", "Providers", "General", "Keys (2)", "mqtt_password"]) assert.ok(t.includes(needle), needle);
  assert.ok(buttons(root, "Sync now").length >= 1 && buttons(root, "Preview").length >= 1 && buttons(root, "Refresh").length >= 1);
});

test("tabs follow the hash and the choice is stored", async () => {
  const root = await mountApp("#/usage");
  assert.equal(findAll(root, (n) => n.attributes.role === "tab" && n.attributes["aria-selected"] === "true")[0].textContent.includes("Key usage"), true);
  await navigate("#/events");
  assert.ok(findAll(root, (n) => n.attributes.role === "tab" && n.attributes["aria-selected"] === "true")[0].textContent.includes("Events"));
  await click(findAll(root, (n) => n.attributes.role === "tab" && n.textContent.includes("Synthetic"))[0]);
  assert.equal(globalThis.location.hash, "#/synthetic");
  assert.equal(store["secrets-sync:tab"], "synthetic");
  assert.equal(readTab(), "synthetic");
});

test("storage failures are tolerated", () => {
  const broken = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
  assert.equal(readTab(broken), null);
  assert.doesNotThrow(() => writeTab("keys", broken));
});

test("Sync now posts api/sync; 429 is a hint, not an error state", async () => {
  syncReply = { status: 202, data: { started: true } };
  const root = await mountApp();
  await click(buttons(root, "Sync now")[0]);
  assert.ok(calls.some((c) => c.method === "POST" && c.url === "api/sync"));
  assert.match(root.textContent, /Sync started/);
  syncReply = { status: 429, data: { started: false, error: "rate_limited", message: "SERVER TEXT" } };
  await click(buttons(root, "Sync now")[0]);
  assert.match(root.textContent, /Please wait a moment/);
  assert.doesNotMatch(root.textContent, /SERVER TEXT/);
  assert.equal(findAll(root, (n) => n.attributes.role === "alert").length, 0, "no error alert for 429");
  syncReply = { status: 202, data: { started: true } };
});

test("server error messages are never shown", async () => {
  syncReply = { status: 500, data: { error: "internal_error", message: "SERVER TEXT" } };
  const root = await mountApp();
  await click(buttons(root, "Sync now")[0]);
  assert.match(root.textContent, /internal error/);
  assert.doesNotMatch(root.textContent, /SERVER TEXT/);
  syncReply = { status: 202, data: { started: true } };
});

test("Apply anyway in the app posts api/sync?force=1 after the typed word", async () => {
  statusPayload = guardState();
  const root = await mountApp();
  await click(buttons(root, "Apply anyway")[0]);
  await type(findAll(root, (n) => n.localName === "input" && n.getAttribute("type") === "text")[0], "remove");
  await click(buttons(root, "Remove keys")[0]);
  assert.ok(calls.some((c) => c.method === "POST" && c.url === "api/sync?force=1"));
  statusPayload = clone(example);
});

test("Preview posts api/preview and lists key names, closable", async () => {
  const root = await mountApp();
  await click(buttons(root, "Preview")[0]);
  assert.ok(calls.some((c) => c.method === "POST" && c.url === "api/preview"));
  assert.match(root.textContent, /Preview \(dry run/);
  assert.match(root.textContent, /new_key/);
  await click(buttons(root, "Close")[0]);
  assert.doesNotMatch(root.textContent, /Preview \(dry run/);
});

test("failed fetch keeps the old data and shows an offline hint", async () => {
  statusPayload = clone(example);
  const root = await mountApp("#/keys");
  statusFails = true;
  await click(buttons(root, "Refresh")[0]);
  await settle(10);
  assert.match(root.textContent, /Could not load the status\. Showing the data from/);
  assert.match(root.textContent, /mqtt_password/);
  assert.doesNotMatch(root.textContent, /SERVER TEXT/);
  statusFails = false;
});

test("first load failing shows the offline text and an empty page, no throw", async () => {
  statusFails = true;
  calls = [];
  const root = await mount(html`<${App} />`);
  await settle(10);
  assert.match(root.textContent, /Could not load the status\./);
  assert.match(root.textContent, /Secrets Sync/);
  statusFails = false;
});

test("old state without check, usage and synthetic renders the page", async () => {
  statusPayload = { status: "ok", items: 1, keys: { names: ["a"], added: [], removed: [], changed: [] }, providers: {}, events: [], versions: { addon: "0.6.0" } };
  const root = await mountApp();
  assert.doesNotMatch(root.textContent, /Change check/);
  assert.match(root.textContent, /v0\.6\.0/);
  statusPayload = clone(example);
});

// ---- i18n rules (R-06) ----
const loadStrings = async (code) => (await import(new URL(`strings.${code}.mjs`, STATIC))).default;
const placeholders = (text) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");

test("de and en define the same keys and placeholders", async () => {
  const de = await loadStrings("de");
  const en = await loadStrings("en");
  assert.deepEqual(Object.keys(de).sort(), Object.keys(en).sort());
  for (const key of Object.keys(en)) assert.equal(placeholders(de[key]), placeholders(en[key]), key);
});

test("every literal t()/tt()/tp() key used in the sources exists, and none is built dynamically", async () => {
  const en = await loadStrings("en");
  const lib = (await import(new URL("vendor/admin-ui/strings.en.mjs", STATIC))).default;
  const files = ["app.mjs", "parts.mjs", "model.mjs", "views/keys.mjs", "views/synthetic.mjs", "views/usage.mjs", "views/events.mjs"];
  for (const file of files) {
    const src = readFileSync(new URL(file, STATIC), "utf8");
    assert.ok(!/\bt[pt]?\(\s*`/.test(src), `${file}: template literal key`);
    for (const m of src.matchAll(/\b(?:tt|tp)\(\s*"([\w.]+)"/g)) {
      const key = m[1];
      assert.ok(key in en || key in lib || `${key}.other` in en, `${file}: missing key ${key}`);
    }
  }
});

test("registered keys do not collide with the lib namespace values", async () => {
  const en = await loadStrings("en");
  const lib = (await import(new URL("vendor/admin-ui/strings.en.mjs", STATIC))).default;
  for (const key of Object.keys(en)) assert.ok(!(key in lib) || lib[key] === en[key], key);
});

// usePoll leaves an interval behind; end the process once the tests are done.
test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
