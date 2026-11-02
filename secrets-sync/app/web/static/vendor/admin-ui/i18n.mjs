// i18n mechanics: de/en tables, language detection and persistence, t/tp/tError and a re-render hook.
// Every storage and document access is guarded: HA's origin may block storage, tests run without a DOM.
import { useState, useEffect } from "./vendor/preact-htm.mjs";
import { errorKey } from "./ingress.mjs";
import de from "./strings.de.mjs";
import en from "./strings.en.mjs";

export const LANGS = ["de", "en"];
export const LANG_STORAGE_KEY = "admin-ui:lang";

const tables = { de: { ...de }, en: { ...en } };
const listeners = new Set();

function globalStorage() {
  try {
    return typeof localStorage !== "undefined" ? localStorage : undefined;
  } catch {
    return undefined;
  }
}

// stored choice -> navigator.language (de* -> de, else en)
export function detectLang(navLike, storageLike) {
  try {
    const stored = storageLike && storageLike.getItem(LANG_STORAGE_KEY);
    if (LANGS.includes(stored)) return stored;
  } catch {
    // storage unavailable: fall through to the browser language
  }
  const nav = navLike && typeof navLike.language === "string" ? navLike.language.toLowerCase() : "";
  return nav === "de" || nav.startsWith("de-") ? "de" : "en";
}

let lang = detectLang(typeof navigator !== "undefined" ? navigator : undefined, globalStorage());

export const getLang = () => lang;

export function setLang(next) {
  if (!LANGS.includes(next)) return;
  try {
    const storage = globalStorage();
    if (storage) storage.setItem(LANG_STORAGE_KEY, next);
  } catch {
    // persistence is best effort
  }
  if (next === lang) return;
  lang = next;
  try {
    if (typeof document !== "undefined" && document.documentElement) document.documentElement.lang = next;
  } catch {
    // no DOM
  }
  listeners.forEach((fn) => fn(lang));
}

export function useLang() {
  const [current, setCurrent] = useState(lang);
  useEffect(() => {
    listeners.add(setCurrent);
    setCurrent(lang);
    return () => listeners.delete(setCurrent);
  }, []);
  return current;
}

export function useT() {
  useLang();
  return t;
}

const lookup = (key) => {
  const own = tables[lang][key];
  return own !== undefined ? own : tables.en[key];
};

function interpolate(text, params) {
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (match, name) =>
    Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match,
  );
}

// Returns plain text: components must render it as a text node, never as markup.
export function t(key, params) {
  const text = lookup(key);
  return text === undefined ? `[${key}]` : interpolate(text, params);
}

export function tp(key, n, params) {
  const rule = new Intl.PluralRules(lang).select(n);
  const chosen = lookup(`${key}.${rule}`) !== undefined ? `${key}.${rule}` : `${key}.other`;
  return t(chosen, { n, ...params });
}

// Localised text by error code; the backend message is never shown.
export function tError(err) {
  const key = errorKey(err);
  if (key !== "errors.unknown" && lookup(key) !== undefined) return t(key);
  return t("errors.unknown", { code: key === "errors.unknown" ? "unknown" : key.slice("errors.".length) });
}

export function registerStrings({ de: addDe, en: addEn } = {}) {
  const incoming = { de: addDe || {}, en: addEn || {} };
  const keysDe = Object.keys(incoming.de).sort();
  const keysEn = Object.keys(incoming.en).sort();
  if (keysDe.join("\n") !== keysEn.join("\n")) {
    throw new Error("registerStrings: de and en must define the same keys");
  }
  for (const code of LANGS) {
    for (const [key, value] of Object.entries(incoming[code])) {
      if (key in tables[code] && tables[code][key] !== value) {
        throw new Error(`registerStrings: key collision for ${key}`);
      }
    }
  }
  for (const code of LANGS) Object.assign(tables[code], incoming[code]);
}
