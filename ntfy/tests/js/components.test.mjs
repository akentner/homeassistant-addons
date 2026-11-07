// Shared ntfy components: text-node-only rendering, accessible names, language switching, no backend text.
import test from "node:test";
import assert from "node:assert/strict";
import { doc, STATIC, html, render, setLang, findAll, findByText, prop, settle } from "./harness.mjs";

const C = await import(new URL("components.mjs", STATIC));
const { ApiClientError } = await import(new URL("vendor/admin-ui/api.mjs", STATIC));

async function show(vnode) {
  setLang("en");
  const root = doc.createElement("div");
  render(vnode, root);
  await settle();
  return root;
}
const cls = (n) => (n.className || "").split(" ");

test("OriginBadge: class is the origin for known origins and muted otherwise; hostile text stays a text node", async () => {
  for (const origin of ["gui", "options", "iac"]) {
    const root = await show(html`<${C.OriginBadge} origin=${origin} />`);
    const badge = findAll(root, (n) => n.localName === "span" && cls(n).includes("badge"))[0];
    assert.ok(cls(badge).includes(origin), origin);
  }
  assert.match((await show(html`<${C.OriginBadge} origin="iac" />`)).textContent, /IaC/);
  const root = await show(html`<${C.OriginBadge} origin="<img src=x onerror=1>" />`);
  const badge = findAll(root, (n) => n.localName === "span" && cls(n).includes("badge"))[0];
  assert.ok(cls(badge).includes("muted"));
  assert.equal(findAll(root, (n) => n.localName === "img").length, 0);
  assert.ok(root.textContent.includes("<img src=x onerror=1>"));
  assert.match((await show(html`<${C.OriginBadge} origin=${null} />`)).textContent, /\?/);
});

test("PermSelect lists rw, ro, wo, deny with localized label plus code and forwards the value", async () => {
  const seen = [];
  const root = await show(html`<${C.PermSelect} value="ro" onChange=${(v) => seen.push(v)} />`);
  const select = findAll(root, (n) => n.localName === "select")[0];
  const options = findAll(select, (n) => n.localName === "option");
  assert.deepEqual(options.map((o) => prop(o, "value")), ["rw", "ro", "wo", "deny"]);
  assert.deepEqual(options.map((o) => o.textContent), ["read + write (rw)", "read only (ro)", "write only (wo)", "deny (deny)"]);
  select.value = "wo";
  select.dispatch("change");
  assert.deepEqual(seen, ["wo"]);
});

test("PermSelect: includeNone adds none, the accessible name is the label prop or the generic text", async () => {
  const none = await show(html`<${C.PermSelect} value="" includeNone onChange=${() => {}} />`);
  const select = findAll(none, (n) => n.localName === "select")[0];
  assert.deepEqual(findAll(select, (n) => n.localName === "option").map((o) => prop(o, "value")), ["", "rw", "ro", "wo", "deny"]);
  assert.equal(findAll(select, (n) => n.localName === "option")[0].textContent, "none");
  assert.equal(select.getAttribute("aria-label"), "Permission");
  const named = await show(html`<${C.PermSelect} value="rw" label="Rule for alice" onChange=${() => {}} />`);
  assert.equal(findAll(named, (n) => n.localName === "select")[0].getAttribute("aria-label"), "Rule for alice");
});

test("PermSelect: an id prop reaches the select element and no id is set without it", async () => {
  const withId = await show(html`<${C.PermSelect} id="perm-x" value="rw" onChange=${() => {}} />`);
  assert.equal(findAll(withId, (n) => n.localName === "select")[0].getAttribute("id"), "perm-x");
  const without = await show(html`<${C.PermSelect} value="rw" onChange=${() => {}} />`);
  assert.equal(findAll(without, (n) => n.localName === "select")[0].getAttribute("id"), null);
});

test("PermSelect follows a language switch", async () => {
  const root = await show(html`<${C.PermSelect} value="rw" onChange=${() => {}} />`);
  setLang("de");
  await settle();
  const texts = findAll(root, (n) => n.localName === "option").map((o) => o.textContent);
  assert.equal(texts[0], "lesen + schreiben (rw)");
  assert.equal(findAll(root, (n) => n.localName === "select")[0].getAttribute("aria-label"), "Berechtigung");
  setLang("en");
});

test("ErrorNote shows the localized text of the code, never the backend message, plus the hint", async () => {
  const marker = "SECRET-BACKEND-MESSAGE";
  const root = await show(html`<${C.ErrorNote} error=${new ApiClientError(503, "db_unsupported", marker)} />`);
  assert.match(root.textContent, /unsupported schema version/);
  assert.match(root.textContent, /Update the add-on or ntfy\./);
  assert.ok(!root.textContent.includes(marker));
  assert.equal(findAll(root, (n) => n.attributes && n.attributes.role === "alert").length, 1);
  const unavailable = await show(html`<${C.ErrorNote} error=${new ApiClientError(503, "db_unavailable", marker)} />`);
  assert.match(unavailable.textContent, /Wait a moment and reload\./);
  const plain = await show(html`<${C.ErrorNote} error=${new ApiClientError(409, "conflict", marker)} />`);
  assert.match(plain.textContent, /conflicts with the current state/);
  assert.ok(!/Update the add-on|Wait a moment/.test(plain.textContent));
  assert.ok(!plain.textContent.includes(marker));
  const none = await show(html`<${C.ErrorNote} error=${null} />`);
  assert.equal(none.textContent, "");
  assert.deepEqual(C.ERROR_HINTS, { db_unsupported: "hint.db_unsupported", db_unavailable: "hint.db_unavailable" });
});

test("ErrorNote is German after a language switch", async () => {
  const root = await show(html`<${C.ErrorNote} error=${new ApiClientError(503, "locked", "x")} />`);
  setLang("de");
  await settle();
  assert.match(root.textContent, /gesperrt/);
  setLang("en");
});

test("FormNotice renders role=alert text; LinkButton renders button.link-btn type=button", async () => {
  const notice = await show(html`<${C.FormNotice}>Name <b>taken</b><//>`);
  const alert = findAll(notice, (n) => n.attributes && n.attributes.role === "alert");
  assert.equal(alert.length, 1);
  assert.match(alert[0].textContent, /Name/);
  const clicks = [];
  const root = await show(html`<${C.LinkButton} onClick=${() => clicks.push(1)}>Details<//>`);
  const btn = findByText(root, "button", "Details")[0];
  assert.ok(cls(btn).includes("link-btn"));
  assert.equal(prop(btn, "type"), "button");
  btn.dispatch("click");
  assert.equal(clicks.length, 1);
});

test("ScrollTable renders div.table-scroll > table.data with an sr-only caption", async () => {
  const root = await show(html`<${C.ScrollTable} caption="Users"><thead><tr><th>Name</th></tr></thead><tbody><tr><td>a</td></tr></tbody><//>`);
  const wrap = findAll(root, (n) => n.localName === "div" && cls(n).includes("table-scroll"))[0];
  const table = findAll(wrap, (n) => n.localName === "table")[0];
  assert.ok(cls(table).includes("data"));
  const caption = findAll(table, (n) => n.localName === "caption")[0];
  assert.ok(cls(caption).includes("sr-only"));
  assert.equal(caption.textContent, "Users");
  assert.equal(findAll(table, (n) => n.localName === "td").length, 1);
});

test("TimeStamp renders a dash for 0 or null, otherwise the date in the active language", async () => {
  assert.equal((await show(html`<${C.TimeStamp} ts=${0} />`)).textContent, "-");
  assert.equal((await show(html`<${C.TimeStamp} ts=${null} />`)).textContent, "-");
  const ts = Date.UTC(2026, 10, 2, 10, 0, 0) / 1000;
  const root = await show(html`<${C.TimeStamp} ts=${ts} />`);
  assert.match(root.textContent, /Nov 2, 2026/);
  setLang("de");
  await settle();
  assert.match(root.textContent, /02\.11\.2026/);
  setLang("en");
  const rel = await show(html`<${C.TimeStamp} ts=${Math.floor(Date.now() / 1000) - 7200} relative />`);
  assert.match(rel.textContent, /2 hours ago/);
});

test("ExpiryText: never for 0, expired with the date when past, else the date", async () => {
  const now = Date.UTC(2026, 10, 2) ;
  assert.equal((await show(html`<${C.ExpiryText} ts=${0} nowMs=${now} />`)).textContent, "never");
  const past = await show(html`<${C.ExpiryText} ts=${now / 1000 - 86400} nowMs=${now} />`);
  assert.match(past.textContent, /^expired .*2026/);
  const future = await show(html`<${C.ExpiryText} ts=${now / 1000 + 86400 * 30} nowMs=${now} />`);
  assert.ok(!/expired|never/.test(future.textContent));
  assert.match(future.textContent, /2026/);
  const root = await show(html`<${C.ExpiryText} ts=${0} nowMs=${now} />`);
  setLang("de");
  await settle();
  assert.equal(root.textContent, "nie");
  setLang("en");
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
