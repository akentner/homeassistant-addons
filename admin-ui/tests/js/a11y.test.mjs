import test from "node:test";
import assert from "node:assert/strict";
import { install, findAll, settle } from "./fakedom.mjs";

const doc = install();
const STATIC = new URL("../../app/web/static/", import.meta.url);
const { tabbables, nextTabTarget, useUid } = await import(new URL("lib/a11y.mjs", STATIC));
const { html, render } = await import(new URL("lib/vendor/preact-htm.mjs", STATIC));
const { auditNames, auditTables } = await import("./a11y_audit.mjs");

// Builds a small element tree: el("div", {id: "x"}, [child, "text"])
function el(tag, attrs = {}, children = []) {
  const node = doc.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "disabled") node.disabled = Boolean(v);
    else node.setAttribute(k, v);
  }
  for (const child of children) node.appendChild(typeof child === "string" ? doc.createTextNode(child) : child);
  return node;
}

test("fakedom: focus sets activeElement, blur clears it, contains covers self and descendants", () => {
  assert.equal(doc.activeElement, null);
  const inner = el("button");
  const outer = el("div", {}, [el("span", {}, [inner])]);
  assert.ok(outer.contains(inner));
  assert.ok(outer.contains(outer));
  assert.ok(!inner.contains(outer));
  inner.focus();
  assert.equal(doc.activeElement, inner);
  outer.blur();
  assert.equal(doc.activeElement, inner);
  inner.blur();
  assert.equal(doc.activeElement, null);
});

test("fakedom: removing the focused element resets activeElement", () => {
  const btn = el("button");
  const box = el("div", {}, [btn]);
  btn.focus();
  box.removeChild(btn);
  assert.equal(doc.activeElement, null);
});

test("fakedom: dispatch records preventDefault and can bubble on request", () => {
  const seen = [];
  const child = el("button");
  const parent = el("div", {}, [child]);
  parent.addEventListener("click", (ev) => seen.push(ev.currentTarget === parent));
  child.dispatch("click");
  assert.deepEqual(seen, []);
  const ev = child.dispatch("click", { bubbles: true });
  assert.deepEqual(seen, [true]);
  assert.equal(ev.defaultPrevented, false);
  child.addEventListener("keydown", (e) => e.preventDefault());
  assert.equal(child.dispatch("keydown").defaultPrevented, true);
});

test("fakedom: tabIndex reads the tabindex attribute", () => {
  assert.equal(el("div", { tabindex: "0" }).tabIndex, 0);
  assert.equal(el("div", { tabindex: "-1" }).tabIndex, -1);
  assert.equal(el("button").tabIndex, 0);
  assert.equal(el("div").tabIndex, -1);
});

test("tabbables: document order, root excluded, nested descendants included", () => {
  const a = el("a", { href: "#x" }, ["a"]);
  const b = el("button", {}, ["b"]);
  const i = el("input", { type: "text" });
  const root = el("button", {}, [el("div", {}, [a, el("span", {}, [b])]), i]);
  assert.deepEqual(tabbables(root), [a, b, i]);
});

test("tabbables: native controls and tabindex >= 0 count, others do not", () => {
  const ok = [el("select"), el("textarea"), el("div", { tabindex: "0" }), el("span", { tabindex: "3" })];
  const no = [
    el("a", {}, ["no href"]),
    el("div"),
    el("input", { type: "hidden" }),
    el("button", { tabindex: "-1" }),
    el("div", { tabindex: "-1" }),
  ];
  const root = el("div", {}, [...no.slice(0, 3), ok[0], ok[1], no[3], ok[2], no[4], ok[3]]);
  assert.deepEqual(tabbables(root), ok);
});

test("tabbables: disabled elements are skipped", () => {
  const live = el("button");
  const root = el("div", {}, [el("button", { disabled: true }), live, el("input", { disabled: true })]);
  assert.deepEqual(tabbables(root), [live]);
});

test("tabbables: hidden subtrees are skipped", () => {
  const live = el("button");
  const root = el("div", {}, [el("div", { hidden: "" }, [el("button"), el("a", { href: "#" })]), live]);
  assert.deepEqual(tabbables(root), [live]);
});

test("nextTabTarget: empty list gives null", () => {
  assert.equal(nextTabTarget([], null, false), null);
  assert.equal(nextTabTarget([], null, true), null);
});

test("nextTabTarget: forward wraps from the last element or from outside", () => {
  const [x, y, z] = [el("button"), el("button"), el("button")];
  const list = [x, y, z];
  assert.equal(nextTabTarget(list, z, false), x);
  assert.equal(nextTabTarget(list, el("div"), false), x);
  assert.equal(nextTabTarget(list, null, false), x);
  assert.equal(nextTabTarget(list, x, false), null);
  assert.equal(nextTabTarget(list, y, false), null);
});

test("nextTabTarget: backwards wraps from the first element or from outside", () => {
  const [x, y, z] = [el("button"), el("button"), el("button")];
  const list = [x, y, z];
  assert.equal(nextTabTarget(list, x, true), z);
  assert.equal(nextTabTarget(list, el("div"), true), z);
  assert.equal(nextTabTarget(list, y, true), null);
  assert.equal(nextTabTarget(list, z, true), null);
});

test("nextTabTarget: a single element wraps onto itself", () => {
  const only = el("button");
  assert.equal(nextTabTarget([only], only, false), only);
  assert.equal(nextTabTarget([only], only, true), only);
});

test("useUid: stable per instance across re-renders, distinct across instances", async () => {
  const seen = [];
  function Probe({ name }) {
    const id = useUid("probe");
    seen.push([name, id]);
    return html`<span>${id}</span>`;
  }
  function Host() {
    return html`<div><${Probe} name="a" /><${Probe} name="b" /></div>`;
  }
  const root = doc.createElement("div");
  render(html`<${Host} />`, root);
  render(html`<${Host} />`, root);
  await settle();
  const byName = (name) => seen.filter(([n]) => n === name).map(([, id]) => id);
  const a = byName("a");
  const b = byName("b");
  assert.ok(a.length >= 2);
  assert.equal(new Set(a).size, 1);
  assert.equal(new Set(b).size, 1);
  assert.notEqual(a[0], b[0]);
  assert.match(a[0], /^probe-\d+$/);
});

test("auditNames: flags controls without an accessible name", () => {
  const root = el("div", {}, [
    el("button", {}, ["ok"]),
    el("button", {}), // unnamed
    el("button", { "aria-label": "  " }), // blank label is no name
    el("a", { href: "#x" }), // unnamed
    el("a", {}), // not a link without href, ignored
    el("input", { type: "text" }), // unnamed
    el("input", { type: "hidden" }), // ignored
    el("select"), // unnamed
    el("textarea"), // unnamed
  ]);
  const found = auditNames(root);
  assert.deepEqual(found.map((v) => v.tag).sort(), ["a", "button", "button", "input", "select", "textarea"]);
});

test("auditNames: accepts aria-label, aria-labelledby, label for and wrapping labels", () => {
  const root = el("div", {}, [
    el("button", { "aria-label": "Close" }),
    el("span", { id: "t1" }, ["Title"]),
    el("button", { "aria-labelledby": "t1" }),
    el("label", { for: "f1" }, ["Name"]),
    el("input", { id: "f1", type: "text" }),
    el("label", {}, ["Wrapped", el("input", { type: "text" })]),
    el("a", { href: "#x" }, ["Link"]),
  ]);
  assert.deepEqual(auditNames(root), []);
});

test("auditNames: a dangling aria-labelledby or an empty label does not count", () => {
  const root = el("div", {}, [
    el("button", { "aria-labelledby": "missing" }),
    el("label", { for: "f2" }, [" "]),
    el("input", { id: "f2", type: "text" }),
  ]);
  assert.equal(auditNames(root).length, 2);
});

test("auditTables: reports th without scope", () => {
  const root = el("table", {}, [
    el("tr", {}, [el("th", { scope: "col" }, ["a"]), el("th", {}, ["b"]), el("th", {}, ["c"])]),
  ]);
  assert.equal(auditTables(root).length, 2);
  assert.deepEqual(auditTables(el("div")), []);
});

test("auditNames walks rendered Preact trees", async () => {
  const root = doc.createElement("div");
  render(html`<div><button>ok</button><button></button></div>`, root);
  await settle();
  assert.equal(auditNames(root).length, 1);
  assert.equal(findAll(root, (n) => n.localName === "button").length, 2);
});

// Preact timers can outlive the tests; end the worker once the results are reported.
test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
