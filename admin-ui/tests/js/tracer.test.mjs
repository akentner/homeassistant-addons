import test from "node:test";
import assert from "node:assert/strict";
import { install, findAll, findByText, settle } from "./fakedom.mjs";

const doc = install();
const STATIC = new URL("../../app/web/static/", import.meta.url);

let calls = [];
let payload = { status: "ok", addon_version: "0.1.0-0", lib_version: "0.1.0" };
globalThis.fetch = async (url, init = {}) => {
  calls.push({ url, method: init.method });
  return { ok: true, status: 200, json: async () => payload };
};

const { html, render } = await import(new URL("lib/ui.mjs", STATIC));
const { App } = await import(new URL("app.mjs", STATIC));

async function mount() {
  calls = [];
  const root = doc.createElement("div");
  render(html`<${App} />`, root);
  await settle();
  return root;
}

test("the health badge shows ok and the request URL is relative", async () => {
  payload = { status: "ok", addon_version: "0.1.0-0", lib_version: "0.1.0" };
  const root = await mount();
  assert.equal(findByText(root, "span", "ok").length, 1);
  assert.equal(findByText(root, "h1", "Admin UI").length, 1);
  assert.deepEqual(calls, [{ url: "api/health", method: "GET" }]);
  assert.ok(!/^(\/|[a-z][a-z0-9+.-]*:)/i.test(calls[0].url));
});

test("hostile status text stays a text node", async () => {
  payload = { status: "<b>x</b>", addon_version: "0.1.0-0", lib_version: "0.1.0" };
  const root = await mount();
  assert.equal(findAll(root, (n) => n.localName === "b").length, 0);
  assert.ok(root.textContent.includes("<b>x</b>"));
});

test("a failing request renders the error badge", async () => {
  const saved = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, status: 500, json: async () => ({ error: "internal_error" }) });
  const root = await mount();
  globalThis.fetch = saved;
  assert.equal(findByText(root, "span", "error").length, 1);
});

// Preact timers can outlive the tests; end the worker once the results are reported.
test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
