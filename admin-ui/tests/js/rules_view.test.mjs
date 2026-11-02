import test from "node:test";
import assert from "node:assert/strict";
import { install, findAll, findByText, prop, settle } from "./fakedom.mjs";
import { auditNames } from "./a11y_audit.mjs";

const doc = install();
const STATIC = new URL("../../app/web/static/", import.meta.url);

const { html, render } = await import(new URL("lib/ui.mjs", STATIC));
const { setLang, registerStrings } = await import(new URL("lib/i18n.mjs", STATIC));
registerStrings({
  de: (await import(new URL("strings.de.mjs", STATIC))).default,
  en: (await import(new URL("strings.en.mjs", STATIC))).default,
});
const mod = await import(new URL("views/rules.mjs", STATIC));
const { RULES, RULES_STORAGE_KEY } = mod;

const makeStorage = (initial = {}) => {
  const data = { ...initial };
  return {
    data,
    getItem: (k) => (k in data ? data[k] : null),
    setItem: (k, v) => {
      data[k] = String(v);
    },
    removeItem: (k) => {
      delete data[k];
    },
  };
};
const throwing = {
  getItem() {
    throw new Error("blocked");
  },
  setItem() {
    throw new Error("blocked");
  },
  removeItem() {
    throw new Error("blocked");
  },
};

async function mount(storage, lang = "en") {
  setLang(lang);
  if (storage === undefined) delete globalThis.localStorage;
  else Object.defineProperty(globalThis, "localStorage", { value: storage, configurable: true, writable: true });
  const root = doc.createElement("div");
  render(html`<${mod.default} params=${{}} />`, root);
  await settle();
  return root;
}
const boxes = (root) => findAll(root, (n) => n.localName === "input" && n.getAttribute("type") === "checkbox");

test("meta, ids and data shape", () => {
  assert.equal(mod.meta.id, "rules");
  assert.equal(mod.meta.titleKey, "demo.nav.rules");
  assert.deepEqual(RULES.map((r) => r.id), Array.from({ length: 15 }, (_, i) => `R-${String(i + 1).padStart(2, "0")}`));
  for (const r of RULES) {
    assert.ok(["enforced", "review", "unverified"].includes(r.status), r.id);
    assert.ok(Array.isArray(r.enforcedBy) && r.enforcedBy.length > 0, r.id);
  }
  assert.equal(RULES_STORAGE_KEY, "admin-ui:demo-rules");
});

test("renders 15 labelled checkboxes with status badges and the summary", async () => {
  const root = await mount(makeStorage());
  assert.equal(boxes(root).length, 15);
  assert.equal(auditNames(root).length, 0);
  assert.equal(findAll(root, (n) => n.localName === "h2").length >= 1, true);
  assert.match(root.textContent, /0 of 15/);
  const kinds = findAll(root, (n) => n.localName === "span" && /^badge /.test(n.className)).map((n) => n.className);
  assert.ok(kinds.includes("badge ok") && kinds.includes("badge warn") && kinds.includes("badge muted"));
  assert.ok(root.textContent.includes("R-01"));
});

test("toggling a rule updates the summary and persists the checked ids", async () => {
  const storage = makeStorage();
  const root = await mount(storage);
  const first = boxes(root)[0];
  first.checked = true;
  first.dispatch("change", { target: first });
  await settle();
  assert.match(root.textContent, /1 of 15/);
  assert.deepEqual(JSON.parse(storage.data[RULES_STORAGE_KEY]), ["R-01"]);
  await Array.from([0]).map(() => findByText(root, "button", "Reset")[0].dispatch("click"));
  await settle();
  assert.match(root.textContent, /0 of 15/);
});

test("stored progress is restored; malformed data is ignored", async () => {
  const root = await mount(makeStorage({ [RULES_STORAGE_KEY]: JSON.stringify(["R-02", "R-03", "bogus", 7]) }));
  assert.match(root.textContent, /2 of 15/);
  assert.equal(boxes(root).filter((b) => prop(b, "checked")).length, 2);
  for (const bad of ["{not json", JSON.stringify({ a: 1 }), "null"]) {
    const r = await mount(makeStorage({ [RULES_STORAGE_KEY]: bad }));
    assert.match(r.textContent, /0 of 15/);
  }
});

test("blocked or missing storage leaves everything unchecked and does not throw", async () => {
  for (const storage of [throwing, undefined]) {
    const root = await mount(storage);
    assert.match(root.textContent, /0 of 15/);
    const first = boxes(root)[0];
    first.checked = true;
    first.dispatch("change", { target: first });
    await settle();
    assert.match(root.textContent, /1 of 15/);
  }
});

test("de and en render without unresolved key markers", async () => {
  for (const lang of ["en", "de"]) {
    const root = await mount(makeStorage(), lang);
    assert.ok(!/\[demo\.[\w.]+\]/.test(root.textContent), lang);
    assert.equal(auditNames(root).length, 0, lang);
  }
  setLang("en");
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
