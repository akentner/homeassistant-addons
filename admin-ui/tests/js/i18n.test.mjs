import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, relative } from "node:path";
import { install, settle } from "./fakedom.mjs";

const doc = install();
const STATIC = new URL("../../app/web/static/", import.meta.url);
const LIB = new URL("lib/", STATIC);
const { html, render } = await import(new URL("vendor/preact-htm.mjs", LIB));
const i18n = await import(new URL("i18n.mjs", LIB));
const { LANGS, LANG_STORAGE_KEY, detectLang, getLang, setLang, useLang, useT, t, tp, tError, registerStrings } = i18n;
const { ApiClientError } = await import(new URL("api.mjs", LIB));

const C5_KEYS = `btn.cancel btn.confirm btn.close btn.copy btn.delete btn.save btn.retry btn.menu btn.reload
copy.done copy.selected copy.manual dlg.type_to_confirm state.loading state.empty state.ok state.degraded state.error
errors.network_error errors.http_error errors.bad_request errors.confirmation_required errors.ingress_only
errors.not_found errors.method_not_allowed errors.conflict errors.protected errors.payload_too_large
errors.internal_error errors.view_failed errors.render_failed errors.unknown lang.label lang.de lang.en nav.label`
  .split(/\s+/);

function fakeStorage(initial = {}) {
  const data = { ...initial };
  return {
    data,
    getItem: (k) => (k in data ? data[k] : null),
    setItem: (k, v) => {
      data[k] = String(v);
    },
  };
}

function withStorage(storage, fn) {
  globalThis.localStorage = storage;
  try {
    return fn();
  } finally {
    delete globalThis.localStorage;
  }
}

test("detectLang: stored choice beats navigator, invalid stored value is ignored", () => {
  const nav = { language: "de-DE" };
  assert.equal(detectLang(nav, fakeStorage({ [LANG_STORAGE_KEY]: "en" })), "en");
  assert.equal(detectLang(nav, fakeStorage({ [LANG_STORAGE_KEY]: "fr" })), "de");
  assert.equal(detectLang({ language: "en-US" }, fakeStorage({ [LANG_STORAGE_KEY]: "de" })), "de");
});

test("detectLang: navigator mapping", () => {
  for (const lang of ["de-DE", "de", "DE-at"]) assert.equal(detectLang({ language: lang }, null), "de", lang);
  for (const lang of ["en-US", "fr", "den", ""]) assert.equal(detectLang({ language: lang }, null), "en", lang);
  assert.equal(detectLang(undefined, undefined), "en");
  assert.equal(detectLang({}, undefined), "en");
});

test("detectLang: throwing or incomplete storage falls through to the navigator", () => {
  const throwing = {
    getItem() {
      throw new Error("blocked");
    },
  };
  assert.equal(detectLang({ language: "de-DE" }, throwing), "de");
  assert.equal(detectLang({ language: "de-DE" }, {}), "de");
});

test("setLang persists under the namespaced key and ignores unsupported values", () => {
  setLang("en");
  const storage = fakeStorage();
  withStorage(storage, () => {
    setLang("de");
    assert.equal(storage.data[LANG_STORAGE_KEY], "de");
    assert.equal(getLang(), "de");
    setLang("xx");
    assert.equal(getLang(), "de");
    assert.equal(storage.data[LANG_STORAGE_KEY], "de");
  });
  setLang("en");
});

test("setLang notifies subscribers exactly once per change", async () => {
  setLang("en");
  const root = doc.createElement("div");
  const renders = [];
  function Probe() {
    renders.push(useLang());
    return html`<p>x</p>`;
  }
  render(html`<${Probe} />`, root);
  await settle();
  const base = renders.length;
  setLang("de");
  setLang("de");
  await settle();
  assert.deepEqual(renders.slice(base), ["de"]);
  setLang("en");
  await settle();
  assert.deepEqual(renders.slice(base), ["de", "en"]);
  render(null, root);
});

test("setLang survives absent and throwing storage and sets document.documentElement.lang when present", () => {
  setLang("en");
  setLang("de");
  assert.equal(getLang(), "de");
  setLang("en");
  const throwing = {
    getItem: () => null,
    setItem() {
      throw new Error("quota");
    },
  };
  withStorage(throwing, () => {
    assert.doesNotThrow(() => setLang("de"));
    assert.equal(getLang(), "de");
  });
  const saved = doc.documentElement;
  doc.documentElement = { lang: "" };
  setLang("en");
  assert.equal(doc.documentElement.lang, "en");
  doc.documentElement = saved;
  setLang("en");
});

test("t: language, english fallback and visible marker", () => {
  setLang("en");
  assert.equal(t("btn.cancel"), "Cancel");
  setLang("de");
  assert.equal(t("btn.cancel"), "Abbrechen");
  assert.equal(t("no.such.key"), "[no.such.key]");
  setLang("en");
});

test("t: interpolation is plain text and missing params stay untouched", () => {
  setLang("en");
  assert.equal(t("dlg.type_to_confirm", { phrase: "<b>x</b>" }), 'Type "<b>x</b>" to confirm');
  assert.equal(t("dlg.type_to_confirm"), 'Type "{phrase}" to confirm');
  assert.equal(t("errors.unknown", { code: "$&" }), "Unknown error [$&]");
});

test("tp selects plural forms and falls back to .other", () => {
  registerStrings({
    de: { "test.items.one": "{n} Eintrag", "test.items.other": "{n} Einträge", "test.solo.other": "{n} Stück" },
    en: { "test.items.one": "{n} item", "test.items.other": "{n} items", "test.solo.other": "{n} pieces" },
  });
  setLang("en");
  assert.equal(tp("test.items", 1), "1 item");
  assert.equal(tp("test.items", 2), "2 items");
  assert.equal(tp("test.solo", 1), "1 pieces");
  setLang("de");
  assert.equal(tp("test.items", 1), "1 Eintrag");
  assert.equal(tp("test.items", 0), "0 Einträge");
  setLang("en");
});

test("tError maps known codes and hides unknown codes and backend messages", () => {
  setLang("en");
  assert.equal(tError({ code: "conflict" }), t("errors.conflict"));
  assert.equal(tError({ code: "teapot" }), "Unknown error [teapot]");
  assert.equal(tError({}), "Unknown error [unknown]");
  assert.equal(tError(null), "Unknown error [unknown]");
  assert.equal(tError("boom"), "Unknown error [unknown]");
  const apiErr = new ApiClientError(418, "teapot", "I am a teapot <b>");
  assert.equal(tError(apiErr), "Unknown error [teapot]");
  assert.ok(!tError(apiErr).includes("teapot <b>"));
  assert.equal(tError(new ApiClientError(409, "conflict", "backend text")), t("errors.conflict"));
  setLang("de");
  assert.equal(tError({ code: "teapot" }), "Unbekannter Fehler [teapot]");
  setLang("en");
});

test("registerStrings: no-op for identical input, throws on collision and on one-sided keys", () => {
  const add = { de: { "reg.a": "A de" }, en: { "reg.a": "A en" } };
  registerStrings(add);
  assert.doesNotThrow(() => registerStrings({ de: { "reg.a": "A de" }, en: { "reg.a": "A en" } }));
  assert.throws(() => registerStrings({ de: { "reg.a": "other" }, en: { "reg.a": "A en" } }), /collision/);
  assert.throws(() => registerStrings({ de: { "reg.b": "B" }, en: {} }), /same keys/);
  assert.equal(t("reg.b"), "[reg.b]");
});

test("useLang and useT re-render a mounted component on a language change", async () => {
  setLang("en");
  const root = doc.createElement("div");
  function Probe() {
    const lang = useLang();
    const tt = useT();
    return html`<p>${lang}:${tt("btn.save")}</p>`;
  }
  render(html`<${Probe} />`, root);
  await settle();
  assert.equal(root.textContent, "en:Save");
  setLang("de");
  await settle();
  assert.equal(root.textContent, "de:Speichern");
  render(null, root);
  setLang("en");
});

// ---- table parity and used keys (scans every strings pair and source file under static/) ----

const ROOT = fileURLToPath(STATIC);

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (name === "vendor") continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (name.endsWith(".mjs")) out.push(p);
  }
  return out;
}

const placeholders = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");
const files = walk(ROOT);
const pairs = files.filter((f) => f.endsWith("strings.de.mjs")).map((f) => f.replace("strings.de.mjs", "strings.en.mjs"));

async function loadTable(file) {
  return (await import(`file://${file}`)).default;
}

test("parity: de and en tables have identical keys and placeholders in every strings pair", async () => {
  assert.ok(pairs.length >= 1);
  for (const enFile of pairs) {
    const deFile = enFile.replace("strings.en.mjs", "strings.de.mjs");
    const [tde, ten] = [await loadTable(deFile), await loadTable(enFile)];
    const where = relative(ROOT, enFile);
    assert.deepEqual(Object.keys(tde).sort(), Object.keys(ten).sort(), `key sets differ near ${where}`);
    for (const key of Object.keys(ten)) {
      assert.equal(placeholders(tde[key]), placeholders(ten[key]), `placeholders differ for ${key} (${where})`);
      assert.equal(typeof ten[key], "string");
      assert.ok(ten[key].length > 0 && tde[key].length > 0, `empty text for ${key}`);
    }
  }
});

test("parity: every contract key exists in the lib tables", async () => {
  const [tde, ten] = [await loadTable(join(ROOT, "lib/strings.de.mjs")), await loadTable(join(ROOT, "lib/strings.en.mjs"))];
  for (const key of C5_KEYS) {
    assert.ok(key in ten, `en misses ${key}`);
    assert.ok(key in tde, `de misses ${key}`);
  }
  assert.equal(ten["lang.de"], "Deutsch");
  assert.equal(tde["lang.en"], "English");
  assert.equal(ten["errors.unknown"], "Unknown error [{code}]");
  assert.equal(tde["errors.unknown"], "Unbekannter Fehler [{code}]");
});

const stripComments = (src) => src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");

export function scanKeys(src) {
  const code = stripComments(src);
  const literal = [];
  const dynamic = [];
  for (const m of code.matchAll(/(?<![\w.$])(tp?)\(\s*([^\s)][^,)]*)/g)) {
    const lit = /^(["'])([^"']+)\1$/.exec(m[2].trim());
    if (lit) literal.push({ fn: m[1], key: lit[2] });
    else dynamic.push(m[0]);
  }
  for (const m of code.matchAll(/\b(?:titleKey|labelKey)\s*:\s*(["'])([^"']+)\1/g)) literal.push({ fn: "t", key: m[2] });
  return { literal, dynamic };
}

test("used keys: the scanner finds literal keys and rejects dynamic ones", () => {
  const ok = scanKeys(`const a = t("btn.save"); tp('x.items', 3); const o = { titleKey: "nav.label" }; // t(dyn)`);
  assert.deepEqual(ok.literal.map((k) => k.key), ["btn.save", "x.items", "nav.label"]);
  assert.equal(ok.dynamic.length, 0);
  assert.equal(scanKeys("t(`btn.${x}`)").dynamic.length, 1);
  assert.equal(scanKeys("t(name)").dynamic.length, 1);
  assert.equal(scanKeys("const format = (x) => x; format(1)").dynamic.length, 0);
});

test("used keys: every literal t()/tp() key resolves and no key is dynamic", async () => {
  const union = {};
  for (const enFile of pairs) Object.assign(union, await loadTable(enFile));
  for (const f of files) {
    const base = f.split("/").pop();
    if (base === "i18n.mjs" || base === "ingress.mjs" || base.startsWith("strings.")) continue;
    const { literal, dynamic } = scanKeys(readFileSync(f, "utf8"));
    const where = relative(ROOT, f);
    assert.deepEqual(dynamic, [], `dynamic i18n key in ${where}`);
    for (const { fn, key } of literal) {
      const want = fn === "tp" ? `${key}.other` : key;
      assert.ok(want in union, `unresolved key ${want} in ${where}`);
    }
  }
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
