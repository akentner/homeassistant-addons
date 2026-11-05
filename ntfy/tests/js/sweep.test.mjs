// Cross-cutting sweep over every view in en and de: no key placeholder, clean accessible names and table headers,
// localized text, error mapping without backend messages, hostile text stays text, titleKey equals the VIEWS entry.
import test from "node:test";
import assert from "node:assert/strict";
import { findAll, mount, all, calls, fixtures, failures, setLang, STATIC } from "./harness.mjs";
import { auditNames, auditTables } from "./a11y_audit.mjs";

const { VIEWS } = await import(new URL("app.mjs", STATIC));

const PLACEHOLDER = /\[[a-z][a-z0-9_]*\.[a-z0-9_.]+\]/;
const MARKER = "SECRET-BACKEND-MESSAGE-4711";
const LANGS = ["en", "de"];

// Runs fn with temporary fixtures and failures and restores both afterwards.
async function withData({ fix = {}, fail = {} }, fn) {
  const saved = { ...fixtures };
  Object.assign(fixtures, fix);
  Object.assign(failures, fail);
  try {
    return await fn();
  } finally {
    for (const key of Object.keys(fixtures)) if (!(key in saved)) delete fixtures[key];
    Object.assign(fixtures, saved);
    for (const key of Object.keys(failures)) delete failures[key];
  }
}

const texts = {};

test("VIEWS lists the five views and every module carries the matching titleKey", async () => {
  assert.equal(VIEWS.length, 5);
  for (const view of VIEWS) {
    const mod = await import(new URL(`views/${view.id}.mjs`, STATIC));
    assert.equal(mod.meta.titleKey, view.titleKey, view.id);
  }
});

for (const view of VIEWS) {
  for (const lang of LANGS) {
    test(`sweep ${view.id} (${lang}): no placeholder, clean names and tables`, async () => {
      const root = await mount(view.id, {}, { lang });
      const text = all(root);
      assert.ok(text.trim().length > 0, "view rendered nothing");
      assert.ok(!PLACEHOLDER.test(text), `key placeholder in ${view.id}/${lang}: ${text.match(PLACEHOLDER)}`);
      assert.deepEqual(auditNames(root), []);
      assert.deepEqual(auditTables(root), []);
      (texts[view.id] ||= {})[lang] = text;
    });
  }

  test(`sweep ${view.id}: the German text differs from the English text`, () => {
    assert.ok(texts[view.id] && texts[view.id].en && texts[view.id].de, "mounts ran first");
    assert.notEqual(texts[view.id].de, texts[view.id].en);
  });
}

test("sweep: with every GET failing 409 the localized conflict text shows and the backend message never does", async () => {
  const fail = {};
  for (const key of Object.keys(fixtures)) {
    if (key.startsWith("GET ")) fail[key] = { status: 409, error: "conflict", message: MARKER };
  }
  const expected = { en: /conflicts with the current state/, de: /Konflikt mit dem aktuellen Stand/ };
  let failing = 0;
  await withData({ fail }, async () => {
    for (const view of VIEWS) {
      for (const lang of LANGS) {
        const root = await mount(view.id, {}, { lang });
        const text = all(root);
        assert.ok(!text.includes(MARKER), `${view.id}/${lang} shows the backend message`);
        assert.ok(!PLACEHOLDER.test(text), `${view.id}/${lang}: ${text.match(PLACEHOLDER)}`);
        if (calls().some((c) => c.method === "GET")) {
          assert.match(text, expected[lang], `${view.id}/${lang} lacks the localized conflict text`);
          if (lang === "en") failing += 1;
        }
      }
    }
  });
  assert.ok(failing >= 5, `only ${failing} views fetch on mount`);
});

test("sweep: an unknown error code shows the generic unknown-error text with the code, never the message", async () => {
  const fail = {};
  for (const key of Object.keys(fixtures)) {
    if (key.startsWith("GET ")) fail[key] = { status: 418, error: "teapot", message: MARKER };
  }
  await withData({ fail }, async () => {
    for (const view of VIEWS) {
      const root = await mount(view.id, {}, { lang: "en" });
      if (!calls().some((c) => c.method === "GET")) continue;
      const text = all(root);
      assert.ok(text.includes("Unknown error [teapot]"), `${view.id}: ${text}`);
      assert.ok(!text.includes(MARKER), view.id);
    }
    const root = await mount("users", {}, { lang: "de" });
    assert.ok(all(root).includes("[teapot]"));
    assert.ok(!all(root).includes(MARKER));
  });
});

test("sweep: hostile names, topics and labels never create elements", async () => {
  const HOSTILE = ["<b>x</b>", "<i>y</i>", "<img src=x onerror=boom()>"];
  const [user, topic, label] = HOSTILE;
  const fix = {
    "GET api/users": {
      users: [
        { name: user, role: "user", tier: null, origin: "gui", provisioned: false, protected: false,
          protected_reason: null, acl_count: 1, token_count: 1 },
      ],
    },
    "GET api/acl": { rules: [{ user, topic, permission: "rw", origin: "gui" }] },
    "GET api/tokens": {
      tokens: [
        { id: "tk_abcde", user, prefix: "tk_abcde", label, expires: 0, expires_at: null, last_access: 0,
          last_origin: "", origin: "gui" },
      ],
    },
  };
  await withData({ fix }, async () => {
    for (const id of ["users", "acl", "matrix", "tokens"]) {
      for (const lang of LANGS) {
        const root = await mount(id, {}, { lang });
        const injected = findAll(root, (n) => ["b", "i", "img", "script"].includes(n.localName));
        assert.equal(injected.length, 0, `${id}/${lang} created ${injected.map((n) => n.localName)}`);
        assert.ok(all(root).includes(user) || all(root).includes(topic) || all(root).includes(label), `${id}/${lang}`);
      }
    }
  });
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
