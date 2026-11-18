import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, relative } from "node:path";
import { install } from "./fakedom.mjs";

install();
const STATIC = new URL("../../app/web/static/", import.meta.url);
const LIB = new URL("vendor/admin-ui/", STATIC);
const ROOT = fileURLToPath(STATIC);
const { registerStrings, setLang, t, tp } = await import(new URL("i18n.mjs", LIB));
const model = await import(new URL("model.mjs", STATIC));

async function loadTable(file) {
  return (await import(`file://${file}`)).default;
}
const placeholders = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");

const addon = { de: await loadTable(join(ROOT, "strings.de.mjs")), en: await loadTable(join(ROOT, "strings.en.mjs")) };
const lib = {
  de: await loadTable(join(ROOT, "vendor/admin-ui/strings.de.mjs")),
  en: await loadTable(join(ROOT, "vendor/admin-ui/strings.en.mjs")),
};

test("parity: de and en tables have identical keys and placeholders, all values non-empty strings", () => {
  assert.deepEqual(Object.keys(addon.de).sort(), Object.keys(addon.en).sort());
  for (const key of Object.keys(addon.en)) {
    assert.equal(typeof addon.en[key], "string", key);
    assert.equal(typeof addon.de[key], "string", key);
    assert.ok(addon.en[key].trim().length > 0 && addon.de[key].trim().length > 0, `empty text for ${key}`);
    assert.equal(placeholders(addon.de[key]), placeholders(addon.en[key]), `placeholders differ for ${key}`);
  }
});

test("german texts are real german, not copied english (except names, symbols and loanwords)", () => {
  const same = Object.keys(addon.en).filter((key) => addon.en[key] === addon.de[key]);
  const allowed = new Set([
    "app.title",
    "view.repositories",
    "mrp.repo.col.repository",
    "mrp.repo.col.status",
    "mrp.repo.col.head",
    "mrp.repo.col.addons",
    "mrp.status.ok",
  ]);
  assert.deepEqual(same.filter((key) => !allowed.has(key)), []);
});

test("registerStrings on top of the lib tables does not throw (no key collision with another value)", () => {
  assert.doesNotThrow(() => registerStrings({ de: addon.de, en: addon.en }));
  assert.doesNotThrow(() => registerStrings({ de: addon.de, en: addon.en }));
  for (const key of Object.keys(addon.en)) {
    assert.ok(!(key in lib.en), `${key} redefines a lib key`);
    assert.ok(!(key in lib.de), `${key} redefines a lib key`);
  }
});

test("registered strings resolve in both languages and plurals follow the language", () => {
  setLang("en");
  assert.equal(t("mrp.sync.now"), "Sync now");
  assert.equal(tp("mrp.repo.addons", 1), "1 add-on");
  assert.equal(tp("mrp.repo.addons", 2), "2 add-ons");
  assert.equal(t("mrp.repo.branch.configured", { branch: "main" }), "Branch main (configured)");
  setLang("de");
  assert.equal(t("mrp.sync.now"), "Jetzt synchronisieren");
  assert.equal(tp("mrp.repo.addons", 1), "1 Add-on");
  assert.equal(tp("mrp.repo.addons", 3), "3 Add-ons");
  assert.equal(t("mrp.reg.registered"), "Registriert");
  setLang("en");
});

test("the lib keys the add-on relies on exist in both lib tables", () => {
  const keys = `btn.retry btn.close state.loading state.empty errors.view_failed errors.http_error errors.network_error
errors.bad_request errors.internal_error errors.unknown lang.de lang.en`.split(/\s+/);
  for (const key of keys) {
    assert.ok(key in lib.en, `lib en misses ${key}`);
    assert.ok(key in lib.de, `lib de misses ${key}`);
  }
});

test("model tables: every value of STATUS_KEYS, REGISTRATION_KEYS and BRANCH_KEYS and the fallbacks exist in both tables", () => {
  const values = [
    ...Object.values(model.STATUS_KEYS),
    ...Object.values(model.REGISTRATION_KEYS),
    ...Object.values(model.BRANCH_KEYS),
    model.statusKey(null),
  ];
  assert.ok(values.length >= 13);
  for (const key of values) {
    assert.ok(key in addon.en, `en misses ${key}`);
    assert.ok(key in addon.de, `de misses ${key}`);
  }
});

// ---- used keys: every literal key resolves, none is built from data ----

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (name === "vendor") continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (name.endsWith(".mjs")) out.push(p);
  }
  return out;
}

const stripComments = (src) => src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");

// t(, tt( and tp( calls plus labelKey:/titleKey: properties. `tt` is the conventional name of the useT() result here.
// Sanctioned non-literal arguments, because the model spells every such key as a literal that the test above checks:
// `x.labelKey`/`x.titleKey`, a lookup in one of the model's `*_KEYS` tables (`STATUS_KEYS[...]`, `BRANCH_KEYS.name`)
// and `statusKey(...)`. Any other non-literal argument is a dynamic key and fails.
const SANCTIONED = [/^[\w$]+\.(?:labelKey|titleKey)$/, /^[A-Z][A-Z_]*_KEYS(?:\[[^\]]+\]|\.\w+)$/, /^statusKey\(/];
const sanctioned = (arg) => SANCTIONED.some((re) => re.test(arg));
export function scanKeys(src) {
  const code = stripComments(src);
  const literal = [];
  const dynamic = [];
  for (const m of code.matchAll(/(?<![\w.$])(tt|tp|t)\(\s*([^\s)][^,)]*)/g)) {
    const arg = m[2].trim();
    const lit = /^(["'])([^"']+)\1$/.exec(arg);
    if (lit) literal.push({ fn: m[1], key: lit[2] });
    else if (!sanctioned(arg)) dynamic.push(m[0]);
  }
  for (const m of code.matchAll(/\b(?:titleKey|labelKey)\s*:\s*(["'])([^"']+)\1/g)) literal.push({ fn: "t", key: m[2] });
  return { literal, dynamic };
}

test("scanner: finds literal keys including the tt alias and rejects dynamic ones", () => {
  const ok = scanKeys(`const a = t("btn.save"); tt('x.y'); tp('x.items', 3); const o = { titleKey: "nav.label" }; // t(dyn)`);
  assert.deepEqual(ok.literal.map((k) => k.key), ["btn.save", "x.y", "x.items", "nav.label"]);
  assert.equal(ok.dynamic.length, 0);
  assert.equal(scanKeys("t(`btn.${x}`)").dynamic.length, 1);
  assert.equal(scanKeys("tt(name)").dynamic.length, 1);
  assert.equal(scanKeys("tp(key, 2)").dynamic.length, 1);
  assert.equal(scanKeys('tt("mrp.reg." + state)').dynamic.length, 1);
  assert.equal(scanKeys("tt(`mrp.reg.${state}`)").dynamic.length, 1);
  assert.equal(scanKeys("tt(row.labelKey)").dynamic.length, 0, "table keys are scanned where they are spelled out");
  assert.equal(scanKeys("tt(REGISTRATION_KEYS[reg.state])").dynamic.length, 0);
  assert.equal(scanKeys("tt(BRANCH_KEYS.configured, { branch })").dynamic.length, 0);
  assert.equal(scanKeys("tt(statusKey(row.status))").dynamic.length, 0);
  assert.equal(scanKeys("tt(row.label)").dynamic.length, 1);
  assert.equal(scanKeys("tt(keys[state])").dynamic.length, 1);
  assert.equal(scanKeys("const format = (x) => x; format(1); split(1); tError(e)").dynamic.length, 0);
});

test("used keys: every literal key in app.mjs, model.mjs and views/*.mjs resolves and no key is dynamic", () => {
  const union = { ...lib.en, ...addon.en };
  const files = walk(ROOT).filter((f) => !/strings\.(de|en)\.mjs$/.test(f));
  const names = files.map((f) => relative(ROOT, f));
  for (const want of ["app.mjs", "model.mjs", join("views", "repositories.mjs")]) assert.ok(names.includes(want), want);
  for (const file of files) {
    const { literal, dynamic } = scanKeys(readFileSync(file, "utf8"));
    const where = relative(ROOT, file);
    assert.deepEqual(dynamic, [], `dynamic i18n key in ${where}`);
    for (const { fn, key } of literal) {
      const want = fn === "tp" ? `${key}.other` : key;
      assert.ok(want in union, `unresolved key ${want} in ${where}`);
      if (fn === "tp") assert.ok(want in addon.de || want in lib.de, `de misses ${want}`);
    }
  }
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
