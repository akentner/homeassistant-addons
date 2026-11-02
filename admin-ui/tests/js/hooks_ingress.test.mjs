import test from "node:test";
import assert from "node:assert/strict";
import { install, settle } from "./fakedom.mjs";

const doc = install();
const LIB = new URL("../../app/web/static/lib/", import.meta.url);
const { html, render, useState } = await import(new URL("vendor/preact-htm.mjs", LIB));
const { useAsync, usePoll } = await import(new URL("hooks.mjs", LIB));
const { isEmbedded, assertRelative, apiHref, errorKey } = await import(new URL("ingress.mjs", LIB));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

test("assertRelative accepts relative paths and rejects the rest", () => {
  assert.equal(assertRelative("api/x"), "api/x");
  for (const bad of ["/x", "//host/x", "http://evil/x", "javascript:alert(1)", "", null, undefined, 5]) {
    assert.throws(() => assertRelative(bad), undefined, String(bad));
  }
});

test("apiHref encodes like buildUrl and rejects absolute paths", () => {
  assert.equal(apiHref("backups/a b.db", { x: 1 }), "api/backups/a%20b.db?x=1");
  assert.throws(() => apiHref("/backups"));
  assert.throws(() => apiHref("https://evil/x"));
});

test("errorKey maps stable codes and falls back for malformed ones", () => {
  assert.equal(errorKey({ code: "conflict" }), "errors.conflict");
  for (const bad of [{}, null, undefined, { code: "" }, { code: "Upper" }, { code: "a b" }, { code: "../x" }, { code: 5 }]) {
    assert.equal(errorKey(bad), "errors.unknown");
  }
});

test("isEmbedded compares parent and never throws", () => {
  const top = {};
  top.parent = top;
  assert.equal(isEmbedded(top), false);
  assert.equal(isEmbedded({ parent: {} }), true);
  assert.equal(isEmbedded({}), false);
  assert.equal(isEmbedded(null), false);
  const hostile = {
    get parent() {
      throw new Error("cross-origin");
    },
  };
  assert.equal(isEmbedded(hostile), false);
});

function mountAsync(fnRef, deps) {
  const out = { root: doc.createElement("div"), last: null };
  function Probe() {
    const r = useAsync(() => fnRef.fn(), deps.value);
    out.last = r;
    return html`<p>${r.loading ? "loading" : r.error ? "error:" + r.error.message : "data:" + JSON.stringify(r.data)}</p>`;
  }
  render(html`<${Probe} />`, out.root);
  return out;
}

test("useAsync goes loading to data", async () => {
  const out = mountAsync({ fn: async () => 42 }, { value: [] });
  assert.ok(out.root.textContent.includes("loading"));
  await settle();
  assert.equal(out.root.textContent, "data:42");
  render(null, out.root);
});

test("useAsync goes loading to error", async () => {
  const out = mountAsync({ fn: async () => { throw new Error("boom"); } }, { value: [] });
  await settle();
  assert.equal(out.root.textContent, "error:boom");
  render(null, out.root);
});

test("useAsync reload re-runs the function", async () => {
  let n = 0;
  const out = mountAsync({ fn: async () => ++n }, { value: [] });
  await settle();
  assert.equal(out.root.textContent, "data:1");
  out.last.reload();
  await settle();
  assert.equal(out.root.textContent, "data:2");
  render(null, out.root);
});

test("useAsync ignores a stale response after a dependency change", async () => {
  const deps = { value: ["a"] };
  const gates = {};
  const fnRef = { fn: () => new Promise((resolve) => { gates[deps.value[0]] = resolve; }) };
  const root = doc.createElement("div");
  let setDep;
  function Probe() {
    const [dep, setD] = useState("a");
    setDep = setD;
    const r = useAsync(() => new Promise((resolve) => { gates[dep] = resolve; }), [dep]);
    return html`<p>${r.loading ? "loading" : String(r.data)}</p>`;
  }
  render(html`<${Probe} />`, root);
  await settle();
  setDep("b");
  await settle();
  gates.b("B");
  await settle();
  gates.a("A");
  await settle();
  assert.equal(root.textContent, "B");
  render(null, root);
  void fnRef;
});

test("useAsync ignores a response that arrives after unmount", async () => {
  let resolve;
  const root = doc.createElement("div");
  function Probe() {
    const r = useAsync(() => new Promise((res) => { resolve = res; }), []);
    return html`<p>${r.loading ? "loading" : "done"}</p>`;
  }
  render(html`<${Probe} />`, root);
  await settle();
  render(null, root);
  resolve("late");
  await settle();
  assert.equal(root.textContent, "");
});

test("usePoll calls repeatedly, skips hidden ticks, uses the latest closure and stops on unmount", async () => {
  const seen = [];
  const root = doc.createElement("div");
  let bump;
  function Probe() {
    const [n, setN] = useState(0);
    bump = () => setN((v) => v + 1);
    usePoll(() => seen.push(n), 20);
    return html`<p>${n}</p>`;
  }
  doc.visibilityState = "visible";
  render(html`<${Probe} />`, root);
  await sleep(90);
  const visibleCalls = seen.length;
  assert.ok(visibleCalls >= 2, `expected polling, got ${visibleCalls}`);

  doc.visibilityState = "hidden";
  await sleep(70);
  assert.equal(seen.length, visibleCalls, "no calls while hidden");

  doc.visibilityState = "visible";
  bump();
  await settle();
  await sleep(60);
  assert.equal(seen.at(-1), 1, "latest closure is used");

  render(null, root);
  const afterUnmount = seen.length;
  await sleep(70);
  assert.equal(seen.length, afterUnmount, "stops after unmount");
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
