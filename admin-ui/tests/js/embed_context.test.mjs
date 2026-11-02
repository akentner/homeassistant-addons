import test from "node:test";
import assert from "node:assert/strict";

const STATIC = new URL("../../app/web/static/", import.meta.url);
const { detectEmbedContext, infoLinkPlan } = await import(new URL("lib/ingress.mjs", STATIC));

const win = (frame, parent = {}) => ({ parent, frameElement: frame });
const frame = (sandbox) => ({ getAttribute: (n) => (n === "sandbox" ? sandbox : null) });

test("no window, no parent or parent === window: an own tab", () => {
  const solo = {};
  solo.parent = solo;
  for (const w of [undefined, null, {}, solo]) assert.deepEqual(detectEmbedContext(w), { kind: "tab", sandbox: null, topNavigation: "allowed", popups: true });
});

test("a throwing parent access counts as a tab, never throws", () => {
  const hostile = { get parent() { throw new Error("x"); } };
  assert.equal(detectEmbedContext(hostile).kind, "tab");
});

test("a framed page whose host answers is the panel", () => {
  assert.deepEqual(detectEmbedContext(win(frame(null)), { bridgeOk: true }), { kind: "panel", sandbox: null, topNavigation: "allowed", popups: true });
});

test("sandbox tokens decide top navigation and popups", () => {
  const cases = [
    ["allow-scripts allow-same-origin", ["blocked", false, []]],
    ["allow-scripts allow-popups", ["blocked", true, ["allow-popups"]]],
    ["allow-top-navigation", ["allowed", false, ["allow-top-navigation"]]],
    ["allow-top-navigation-by-user-activation allow-popups-to-escape-sandbox", ["allowed", false, ["allow-top-navigation-by-user-activation", "allow-popups-to-escape-sandbox"]]],
    ["", ["blocked", false, []]],
  ];
  for (const [attr, [top, popups, tokens]] of cases) {
    const ctx = detectEmbedContext(win(frame(attr)));
    assert.equal(ctx.kind, "card", attr);
    assert.equal(ctx.topNavigation, top, attr);
    assert.equal(ctx.popups, popups, attr);
    assert.deepEqual(ctx.sandbox, tokens, attr);
  }
});

test("framed without a sandbox attribute: readable, top navigation allowed, kind unknown", () => {
  assert.deepEqual(detectEmbedContext(win(frame(null))), { kind: "unknown", sandbox: null, topNavigation: "allowed", popups: true });
});

test("an unreadable or throwing frame element gives unknown", () => {
  assert.deepEqual(detectEmbedContext(win(null)), { kind: "unknown", sandbox: null, topNavigation: "unknown", popups: true });
  const throwing = { parent: {} };
  Object.defineProperty(throwing, "frameElement", { get() { throw new DOMException("blocked", "SecurityError"); } });
  assert.equal(detectEmbedContext(throwing).topNavigation, "unknown");
  assert.equal(detectEmbedContext(win({ getAttribute() { throw new Error("x"); } })).topNavigation, "allowed");
});

test("infoLinkPlan maps contexts to the offered link", () => {
  assert.equal(infoLinkPlan({ kind: "panel", topNavigation: "blocked", popups: false }), "bridge");
  assert.equal(infoLinkPlan({ kind: "tab", topNavigation: "allowed", popups: true }), "same");
  assert.equal(infoLinkPlan({ kind: "card", topNavigation: "blocked", popups: true }), "blank");
  assert.equal(infoLinkPlan({ kind: "card", topNavigation: "blocked", popups: false }), "hidden");
  assert.equal(infoLinkPlan({ kind: "card", topNavigation: "allowed", popups: false }), "top");
  assert.equal(infoLinkPlan({ kind: "unknown", topNavigation: "unknown", popups: true }), "top");
  assert.equal(infoLinkPlan(undefined), "top");
});
