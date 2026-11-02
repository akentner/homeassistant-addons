// Export contract of every lib module: the public API is exactly this list (DOCS.md "Library reference").
// Extend EXPECTED only together with the module, the DOCS.md table and the CHANGELOG.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const LIB = new URL("../../app/web/static/lib/", import.meta.url);
const load = (name) => import(new URL(name, LIB).href);

const PREACT = [
  "Component",
  "createContext",
  "h",
  "html",
  "render",
  "useCallback",
  "useContext",
  "useDebugValue",
  "useEffect",
  "useErrorBoundary",
  "useImperativeHandle",
  "useLayoutEffect",
  "useMemo",
  "useReducer",
  "useRef",
  "useState",
];

const EXPECTED = {
  "api.mjs": ["ApiClientError", "buildUrl", "request", "get", "post", "put", "patch", "del"],
  "ingress.mjs": ["isEmbedded", "assertRelative", "apiHref", "errorKey", "detectEmbedContext", "infoLinkPlan"],
  "hooks.mjs": ["useAsync", "usePoll"],
  "format.mjs": ["formatDateTime", "formatRelative", "formatBytes", "formatNumber"],
  "i18n.mjs": [
    "LANGS",
    "LANG_STORAGE_KEY",
    "detectLang",
    "getLang",
    "setLang",
    "useLang",
    "useT",
    "t",
    "tp",
    "tError",
    "registerStrings",
  ],
  "color.mjs": ["parseColor", "serializeColor", "relativeLuminance", "contrastRatio", "isDarkColor", "pickOnColor"],
  "theme-sync.mjs": ["createThemeSync", "THEME_WHITELIST"],
  "ha-bridge.mjs": ["createHaBridge"],
  "a11y.mjs": ["tabbables", "nextTabTarget", "useUid"],
  "shell.mjs": ["Topbar", "LangSwitch", "TabNav", "ErrorBoundary", "parseHash", "useHashRoute", "needsBurger"],
  "ui.mjs": [
    ...PREACT,
    "toast",
    "Toasts",
    "Modal",
    "ConfirmDialog",
    "confirmMatches",
    "Badge",
    "ErrorNote",
    "Loading",
    "CopyField",
    "Tabs",
    "DataTable",
    "Field",
    "useAsync",
    "usePoll",
  ],
};

// Exported names that are data, not functions.
const CONSTANTS = { LANGS: "object", LANG_STORAGE_KEY: "string", THEME_WHITELIST: "object" };

async function checkModule(file) {
  const mod = await load(file);
  assert.deepEqual(Object.keys(mod).sort(), [...EXPECTED[file]].sort(), `${file} exports`);
  for (const name of EXPECTED[file]) {
    assert.equal(typeof mod[name], CONSTANTS[name] || "function", `${file}: typeof ${name}`);
  }
}

test("api.mjs exports", () => checkModule("api.mjs"));
test("ingress.mjs exports", () => checkModule("ingress.mjs"));
test("hooks.mjs exports", () => checkModule("hooks.mjs"));
test("format.mjs exports", () => checkModule("format.mjs"));
test("i18n.mjs exports", () => checkModule("i18n.mjs"));
test("color.mjs exports", () => checkModule("color.mjs"));
test("theme-sync.mjs exports", () => checkModule("theme-sync.mjs"));
test("ha-bridge.mjs exports", () => checkModule("ha-bridge.mjs"));
test("a11y.mjs exports", () => checkModule("a11y.mjs"));
test("shell.mjs exports", () => checkModule("shell.mjs"));
test("ui.mjs exports", () => checkModule("ui.mjs"));

test("strings modules have only a default export", async () => {
  for (const file of ["strings.de.mjs", "strings.en.mjs"]) {
    const mod = await load(file);
    assert.deepEqual(Object.keys(mod), ["default"], file);
    assert.equal(typeof mod.default, "object");
  }
});

test("every lib module is covered by the contract", () => {
  const files = readdirSync(fileURLToPath(LIB)).filter((f) => f.endsWith(".mjs"));
  const covered = new Set([...Object.keys(EXPECTED), "strings.de.mjs", "strings.en.mjs"]);
  assert.deepEqual(
    files.filter((f) => !covered.has(f)),
    [],
    "lib module without an export contract",
  );
});

test("importing every module in plain Node does not throw", async () => {
  const files = readdirSync(fileURLToPath(LIB)).filter((f) => f.endsWith(".mjs"));
  assert.ok(files.length >= 13);
  for (const file of files) await load(file);
  await import(new URL("vendor/preact-htm.mjs", LIB).href);
});
