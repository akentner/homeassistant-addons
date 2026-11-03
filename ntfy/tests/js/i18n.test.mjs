// i18n guards: de/en parity of every string table (parts and aggregators), no key defined twice, every key used by
// ntfy sources resolves in the union of the lib and ntfy tables. Adapted from admin-ui/tests/js/i18n.test.mjs;
// ntfy also scans tt() calls and allows UPPER_CASE table indexes as the only non-literal key form.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { setLang } from "./harness.mjs";

setLang("en");
const STATIC = new URL("../../app/web/static/", import.meta.url);
const ROOT = fileURLToPath(STATIC);
const PARTS = ["core", "access", "manage"];

const load = async (rel) => (await import(new URL(rel, STATIC))).default;
const placeholders = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (name === "vendor") continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (name.endsWith(".mjs")) out.push(p);
  }
  return out;
}
const sources = walk(ROOT).filter((f) => !/strings(\.|\/)/.test(relative(ROOT, f)) && !f.endsWith("/strings.de.mjs"));

const pairs = [
  ["strings.de.mjs", "strings.en.mjs"],
  ...PARTS.map((p) => [`strings/${p}.de.mjs`, `strings/${p}.en.mjs`]),
];

test("parity: every strings pair has identical keys and placeholders and no empty text", async () => {
  for (const [deFile, enFile] of pairs) {
    const [tde, ten] = [await load(deFile), await load(enFile)];
    assert.deepEqual(Object.keys(tde).sort(), Object.keys(ten).sort(), `key sets differ in ${enFile}`);
    for (const key of Object.keys(ten)) {
      assert.equal(typeof ten[key], "string", `${key} (${enFile})`);
      assert.equal(typeof tde[key], "string", `${key} (${deFile})`);
      assert.ok(ten[key].length > 0 && tde[key].length > 0, `empty text for ${key}`);
      assert.equal(placeholders(tde[key]), placeholders(ten[key]), `placeholders differ for ${key} (${enFile})`);
    }
  }
});

test("no key is defined in two parts and the aggregators hold exactly the union of the parts", async () => {
  for (const lang of ["de", "en"]) {
    const seen = new Map();
    for (const part of PARTS) {
      for (const key of Object.keys(await load(`strings/${part}.${lang}.mjs`))) {
        assert.ok(!seen.has(key), `${key} defined in ${seen.get(key)} and ${part} (${lang})`);
        seen.set(key, part);
      }
    }
    assert.deepEqual(Object.keys(await load(`strings.${lang}.mjs`)).sort(), [...seen.keys()].sort());
  }
});

test("the lib and ntfy tables do not disagree on a shared key", async () => {
  for (const lang of ["de", "en"]) {
    const lib = await load(`vendor/admin-ui/strings.${lang}.mjs`);
    const own = await load(`strings.${lang}.mjs`);
    for (const key of Object.keys(own)) if (key in lib) assert.equal(own[key], lib[key], `${key} (${lang})`);
  }
});

// ---- used keys ----

const stripComments = (src) => src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
const TABLE_INDEX = /^[A-Z][A-Z0-9_]*\[[^\]]+\]$/;

export function scanKeys(src) {
  const code = stripComments(src);
  const literal = [];
  const dynamic = [];
  for (const m of code.matchAll(/(?<![\w.$])(tt|tp|t)\(\s*([^\s)][^,)]*)/g)) {
    const arg = m[2].trim();
    const lit = /^(["'])([^"']+)\1$/.exec(arg);
    if (lit) literal.push({ fn: m[1], key: lit[2] });
    else if (!TABLE_INDEX.test(arg)) dynamic.push(m[0]);
  }
  for (const m of code.matchAll(/\b(?:titleKey|labelKey)\s*:\s*(["'])([^"']+)\1/g)) literal.push({ fn: "t", key: m[2] });
  return { literal, dynamic };
}

test("scanner: finds literal keys in t, tt and tp, allows table indexes, rejects other dynamic forms", () => {
  const ok = scanKeys(`const a = t("btn.save"); tt('x.y'); tp('x.items', 3); const o = { titleKey: "view.users" }; // t(dyn)`);
  assert.deepEqual(ok.literal.map((k) => k.key), ["btn.save", "x.y", "x.items", "view.users"]);
  assert.equal(ok.dynamic.length, 0);
  assert.equal(scanKeys("tt(PERM_KEYS[value])").dynamic.length, 0);
  assert.equal(scanKeys("tt(`btn.${x}`)").dynamic.length, 1);
  assert.equal(scanKeys("t(name)").dynamic.length, 1);
  assert.equal(scanKeys("tt(keys[x])").dynamic.length, 1);
  assert.equal(scanKeys("const format = (x) => x; format(1); obj.t(2)").dynamic.length, 0);
});

async function union() {
  const out = {};
  for (const file of ["vendor/admin-ui/strings.en.mjs", "strings.en.mjs"]) Object.assign(out, await load(file));
  return out;
}

test("used keys: every literal t/tt/tp key in ntfy sources resolves and no key is dynamic", async () => {
  const keys = await union();
  assert.ok(sources.length >= 8, "scan covers the ntfy sources");
  for (const f of sources) {
    const { literal, dynamic } = scanKeys(readFileSync(f, "utf8"));
    const where = relative(ROOT, f);
    assert.deepEqual(dynamic, [], `dynamic i18n key in ${where}`);
    for (const { fn, key } of literal) {
      const want = fn === "tp" ? `${key}.other` : key;
      assert.ok(want in keys, `unresolved key ${want} in ${where}`);
    }
  }
});

test("used keys: every quoted literal that looks like an ntfy key resolves", async () => {
  const keys = await union();
  const own = await load("strings.en.mjs");
  const namespaces = [...new Set(Object.keys(own).map((k) => k.split(".")[0]))];
  const looksLikeKey = new RegExp(`(["'\`])((?:${namespaces.join("|")})\\.[a-z0-9_.]+)\\1`, "g");
  for (const f of sources) {
    const code = stripComments(readFileSync(f, "utf8"));
    for (const m of code.matchAll(looksLikeKey)) {
      const key = m[2];
      assert.ok(key in keys || `${key}.other` in keys, `unresolved key ${key} in ${relative(ROOT, f)}`);
    }
  }
});

test("every ntfy-specific error code has a text in the ntfy tables (both languages)", async () => {
  const codes = ["ntfy_error", "locked", "db_unavailable", "db_unsupported"];
  for (const lang of ["de", "en"]) {
    const own = await load(`strings.${lang}.mjs`);
    for (const code of codes) assert.ok(`errors.${code}` in own, `errors.${code} (${lang})`);
  }
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
