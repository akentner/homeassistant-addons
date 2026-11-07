// Shell tests: Topbar, tab navigation, hash routing with params, health badge, degraded notice, language switch,
// optional HA wiring, view loading, plus the cross-cutting view file and relative URL checks.
import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { doc, STATIC, html, render, setLang, fixtures, failures, calls, mount, findAll, findByText, settle } from "./harness.mjs";

// ---- window / location stub with a controllable hashchange ----
const handlers = new Set();
globalThis.window = {
  addEventListener: (type, fn) => type === "hashchange" && handlers.add(fn),
  removeEventListener: (type, fn) => type === "hashchange" && handlers.delete(fn),
};
globalThis.window.parent = globalThis.window;
globalThis.location = { hash: "" };
doc.documentElement = { lang: "" };
const navigate = async (hash) => {
  globalThis.location.hash = hash;
  for (const fn of [...handlers]) fn({});
  await settle();
};

const { App, VIEWS, semver, migrateLegacyHash } = await import(new URL("app.mjs", STATIC));

const HEALTH = fixtures["GET api/health"];
const fakeLoad = async (id) => ({ default: ({ params }) => html`<p class="fake-view">view ${id} ${JSON.stringify(params)}</p>` });

async function mountApp({ ha = {}, load = fakeLoad, hash = "", lang = "en" } = {}) {
  setLang(lang);
  globalThis.location.hash = hash;
  const root = doc.createElement("div");
  render(html`<${App} ha=${ha} load=${load} />`, root);
  await settle();
  return root;
}

const withHealth = async (payload, fn) => {
  fixtures["GET api/health"] = payload;
  try {
    return await fn();
  } finally {
    fixtures["GET api/health"] = HEALTH;
  }
};
const links = (root) => findAll(root, (n) => n.localName === "a" && (n.className || "").split(" ").includes("topnav-link"));

test("topbar shows the title and five nav links in VIEWS order", async () => {
  const root = await mountApp();
  assert.equal(findByText(root, "h1", "ntfy").length, 1);
  assert.deepEqual(VIEWS.map((v) => v.id), ["users", "acl", "matrix", "tokens", "tools"]);
  assert.deepEqual(links(root).map((a) => a.getAttribute("href")), VIEWS.map((v) => `#/${v.id}`));
  assert.equal(findAll(root, (n) => n.localName === "select" && n.className === "lang-switch").length, 0);
});

test("the active tab follows the hash, an unknown or hostile hash falls back to users", async () => {
  const seen = [];
  const load = async (id) => {
    seen.push(id);
    return fakeLoad(id);
  };
  const root = await mountApp({ load });
  assert.deepEqual(seen, ["users"]);
  await navigate("#/matrix");
  assert.match(root.textContent, /view matrix/);
  const active = findAll(root, (n) => n.localName === "a" && n.className.includes("active"));
  assert.equal(active.length, 1);
  assert.equal(active[0].getAttribute("href"), "#/matrix");
  await navigate("#/../../x");
  assert.equal(seen.at(-1), "users");
  await navigate("#/nope");
  assert.ok(seen.every((id) => VIEWS.some((v) => v.id === id)), seen.join());
});

test("query params of the hash reach the view", async () => {
  const root = await mountApp({ hash: "#/tools?topic=a%20b" });
  assert.match(root.textContent, /view tools \{"topic":"a b"\}/);
});

test("health badge: ok, degraded with alert, failed and loading", async () => {
  let root = await mountApp();
  assert.equal(findByText(root, "span", "OK").length, 1);
  assert.equal(findAll(root, (n) => (n.className || "") === "topbar-version")[0].textContent, "2.36.0");

  await withHealth({ ...HEALTH, status: "degraded", db: { ...HEALTH.db, error: "locked <b>x</b>" } }, async () => {
    root = await mountApp();
    assert.equal(findByText(root, "span", "Degraded").length, 1);
    const alert = findAll(root, (n) => n.attributes && n.attributes.role === "alert");
    assert.equal(alert.length, 1);
    assert.match(alert[0].textContent, /auth database cannot be used/);
    assert.match(alert[0].textContent, /locked <b>x<\/b>/);
    assert.equal(findAll(root, (n) => n.localName === "b").length, 0);
  });

  failures["GET api/health"] = { status: 500, error: "internal_error" };
  try {
    root = await mountApp();
    assert.equal(findByText(root, "span", "Error").length, 1);
  } finally {
    delete failures["GET api/health"];
  }

  // before the first answer the badge is muted "Loading…"
  root = doc.createElement("div");
  setLang("en");
  render(html`<${App} ha=${{}} load=${fakeLoad} />`, root);
  assert.equal(findByText(root, "span", "Loading…").length, 1);
  await settle();
});

test("a language switch re-renders tab titles in German without a reload", async () => {
  const root = await mountApp();
  assert.equal(findByText(root, "a", "Users").length, 1);
  setLang("de");
  await settle();
  assert.equal(findByText(root, "a", "Benutzer").length, 1);
  assert.equal(findByText(root, "a", "Users").length, 0);
  assert.equal(findAll(root, (n) => (n.className || "") === "topbar-version")[0].textContent, "2.36.0");
  assert.equal(globalThis.document.documentElement.lang, "de");
  setLang("en");
  await settle();
});

test("the app works without HA wiring and with the default wiring when window.parent is window", async () => {
  assert.match((await mountApp({ ha: {} })).textContent, /view users/);
  const root = doc.createElement("div");
  setLang("en");
  globalThis.location.hash = "";
  render(html`<${App} load=${fakeLoad} />`, root);
  await settle();
  assert.match(root.textContent, /view users/);
  render(null, root);
});

test("HA bridge and theme sync are started after mount and disposed on unmount", async () => {
  const log = [];
  const ha = {
    bridge: {
      getState: () => ({ kiosk: false }),
      subscribe: () => () => {},
      toggleMenu() {},
      start: () => log.push("bridge.start"),
      dispose: () => log.push("bridge.dispose"),
    },
    sync: { start: () => log.push("sync.start"), dispose: () => { throw new Error("dispose must not break the page"); } },
  };
  const root = await mountApp({ ha });
  assert.deepEqual(log.sort(), ["bridge.start", "sync.start"]);
  render(null, root);
  await settle();
  assert.ok(log.includes("bridge.dispose"));
});

test("a view whose module fails to load shows the localized note, no backend text", async () => {
  const root = await mountApp({
    load: async () => {
      throw new Error("boom detail");
    },
  });
  assert.match(root.textContent, /This view could not be loaded/);
  assert.ok(!root.textContent.includes("boom detail"));
  setLang("de");
  await settle();
  assert.match(root.textContent, /Ansicht konnte nicht geladen werden/);
  setLang("en");
});

test("every view file exists, exports meta and a default function, and its relative imports exist", async () => {
  assert.equal(VIEWS.length, 5);
  for (const v of VIEWS) {
    const file = new URL(`views/${v.id}.mjs`, STATIC);
    assert.ok(existsSync(file), v.id);
    const mod = await import(file);
    assert.equal(mod.meta.id, v.id);
    assert.equal(typeof mod.default, "function");
    const src = readFileSync(file, "utf8");
    for (const m of src.matchAll(/from\s+"(\.[^"]+)"/g)) assert.ok(existsSync(new URL(m[1], file)), `${v.id}: ${m[1]}`);
  }
});

test("all requested URLs are relative", async () => {
  for (const v of VIEWS) {
    await mount(v.id);
    assert.ok(calls().length > 0, v.id);
    for (const c of calls()) assert.ok(!/^(\/|[a-z][a-z0-9+.-]*:)/i.test(c.url), c.url);
  }
  await mountApp();
  assert.ok(calls().some((c) => c.method === "GET" && c.url === "api/health"));
});

// Preact/toast timers can outlive the tests; end the worker once the results are reported.
test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});

test("the info button points at the HA info page of the add-on and is hidden without a slug", async () => {
  const hrefs = (root) => findAll(root, (n) => n.localName === "a" && (n.className || "").split(" ").includes("info-btn"));
  const root = await mountApp();
  const btn = hrefs(root);
  assert.equal(btn.length, 1);
  assert.equal(btn[0].getAttribute("href"), "/config/app/72a005f5_ntfy/config");
  await withHealth({ ...HEALTH, addon_slug: undefined }, async () => {
    assert.equal(hrefs(await mountApp()).length, 0);
  });
});

test("semver drops the subpatch and anything that is not a version", () => {
  assert.equal(semver("2.37.2-6"), "2.37.2");
  assert.equal(semver("2.37.2"), "2.37.2");
  assert.equal(semver("unknown"), "");
  assert.equal(semver(undefined), "");
});

test("the merged health and data pages still resolve: old hashes land on tools, query kept", async () => {
  for (const [from, to] of [["#/health", "#/tools"], ["#/data", "#/tools"], ["#/data?x=1", "#/tools?x=1"]]) {
    const seen = [];
    const root = await mountApp({ hash: from, load: async (id) => (seen.push(id), fakeLoad(id)) });
    assert.equal(globalThis.location.hash, to);
    assert.deepEqual(seen, ["tools"]);
    assert.match(root.textContent, /view tools/);
  }
  const loc = { hash: "#/healthy" };
  migrateLegacyHash(loc);
  assert.equal(loc.hash, "#/healthy");
});

test("every view has a decorative icon rendered next to its nav label", async () => {
  assert.ok(VIEWS.every((v) => /^M[-\d.,A-Za-z\s]+Z$/.test(v.icon || "")), "icon path data per view");
  const root = await mountApp();
  const withIcon = links(root).filter((a) => findAll(a, (n) => n.localName === "svg").length === 1);
  assert.equal(withIcon.length, VIEWS.length);
});
