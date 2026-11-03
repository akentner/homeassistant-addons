// View tests of the access group: users, acl, matrix (owned by plan 27-03).
import test from "node:test";
import assert from "node:assert/strict";
import {
  findAll, findByText, prop, settle, mount, all, calls, fixtures, failures, setLang, doc, html, render, STATIC,
} from "./harness.mjs";
import { auditNames, auditTables } from "../../../admin-ui/tests/js/a11y_audit.mjs";

const { Toasts } = await import(new URL("vendor/admin-ui/ui.mjs", STATIC));

const click = async (node) => {
  node.dispatch("click");
  await settle();
};
const type = async (node, value) => {
  node.value = value;
  node.dispatch("input");
  await settle();
};
const choose = async (node, value) => {
  node.value = value;
  node.dispatch("change");
  await settle();
};
const btn = (root, text) => findByText(root, "button", text)[0];
const byTag = (root, tag) => findAll(root, (n) => n.localName === tag);
const inputs = (root, kind = "text") => findAll(root, (n) => n.localName === "input" && prop(n, "type") === kind);
const cls = (n) => (n.className || "").split(" ");
const rowOf = (root, needle) => byTag(root, "tr").find((r) => r.textContent.includes(needle));
const used = (method, path) =>
  calls().filter((c) => c.method === method && decodeURIComponent(c.url.split("?")[0]) === path);

async function toasts() {
  const stack = doc.createElement("div");
  render(html`<${Toasts} />`, stack);
  await settle();
  return stack;
}

// Runs fn with temporary fixtures/failures and restores them afterwards.
async function withData(patchFixtures, fn, patchFailures = {}) {
  const savedFix = { ...fixtures };
  Object.assign(fixtures, patchFixtures);
  Object.assign(failures, patchFailures);
  try {
    return await fn();
  } finally {
    for (const key of Object.keys(fixtures)) if (!(key in savedFix)) delete fixtures[key];
    Object.assign(fixtures, savedFix);
    for (const key of Object.keys(patchFailures)) delete failures[key];
  }
}

const ENGLISH_LEFTOVERS = /Add user|Make admin|Cancel|Delete|Password|Create|Demote|No rules|Add rule|Filter by|Save/;
const noPlaceholder = (text, ns) => assert.ok(!text.includes(`[${ns}.`) && !/\[(btn|dlg|state|perm|origin)\./.test(text), text);

// ---------------------------------------------------------------- users

const ALICE = "<b>alice</b>";
const adminUser = {
  name: "carol", role: "admin", tier: null, origin: "gui", provisioned: false, protected: false,
  protected_reason: null, acl_count: 0, token_count: 0,
};
const usersWith = (...extra) => ({ "GET api/users": { users: [...fixtures["GET api/users"].users, ...extra] } });

test("users view: meta, scrollable table with caption and header scopes, no accessibility violation", async () => {
  const mod = await import(new URL("views/users.mjs", STATIC));
  assert.deepEqual(mod.meta, { id: "users", titleKey: "view.users" });
  const root = await mount("users");
  const wrap = findAll(root, (n) => cls(n).includes("table-scroll"))[0];
  assert.ok(wrap && byTag(wrap, "table").length === 1);
  const caption = byTag(root, "caption")[0];
  assert.ok(caption && cls(caption).includes("sr-only") && caption.textContent.length > 0);
  const heads = byTag(root, "th");
  assert.equal(heads.length, 8);
  assert.ok(heads.every((th) => th.getAttribute("scope") === "col"));
  assert.ok(heads.map((th) => th.textContent.trim()).includes("Actions"));
  assert.deepEqual(auditNames(root), []);
  assert.deepEqual(auditTables(root), []);
});

test("users view: protected row has disabled Demote and Delete, hostile name stays text", async () => {
  const root = await mount("users");
  const text = all(root);
  assert.match(text, /admin from options/);
  assert.ok(text.includes(ALICE));
  assert.equal(findAll(root, (n) => n.localName === "b").length, 0);
  const adminRow = rowOf(root, "admin from options");
  assert.ok(prop(findByText(adminRow, "button", "Delete")[0], "disabled"));
  assert.ok(prop(findByText(adminRow, "button", "Demote")[0], "disabled"));
  const aliceRow = rowOf(root, ALICE);
  assert.ok(!prop(findByText(aliceRow, "button", "Delete")[0], "disabled"));
});

test("users view: the everyone row has no action buttons", async () => {
  const root = await mount("users");
  const row = byTag(root, "tr").find((r) => byTag(r, "td")[0] && byTag(r, "td")[0].textContent.trim() === "everyone");
  assert.ok(row);
  const cells = byTag(row, "td");
  assert.equal(byTag(cells[cells.length - 1], "button").length, 0);
});

test("users view: the name opens a detail card (rules, tokens) and a second click closes it", async () => {
  await withData(
    {
      "GET api/users/<b>alice</b>": {
        user: { name: ALICE },
        acl: [{ topic: "alerts", permission: "rw", origin: "gui" }],
        tokens: [{ id: "tk_1", prefix: "tk_abcde", label: "phone", expires_at: null, last_access: 0 }],
      },
    },
    async () => {
      const root = await mount("users");
      const opener = findAll(root, (n) => n.localName === "button" && cls(n).includes("link-btn"))
        .find((n) => n.textContent.trim() === ALICE);
      assert.ok(opener);
      await click(opener);
      assert.equal(used("GET", `api/users/${ALICE}`).length, 1);
      assert.match(all(root), /alerts/);
      assert.match(all(root), /tk_abcde/);
      assert.match(all(root), /phone/);
      assert.match(all(root), /expiry\s*never/);
      assert.deepEqual(auditNames(root), []);
      await click(
        findAll(root, (n) => n.localName === "button" && cls(n).includes("link-btn")).find((n) => n.textContent.trim() === ALICE),
      );
      assert.ok(!all(root).includes("tk_abcde"));
    },
  );
});

test("users view: add user validates locally, maps a conflict to the localized text and posts the body", async () => {
  const root = await mount("users");
  await click(btn(root, "Add user"));
  const nameInput = inputs(root)[0];
  const pwInput = inputs(root, "password")[0];
  assert.ok(nameInput && pwInput);
  // every input has an accessible name through its label
  assert.deepEqual(auditNames(root), []);
  const before = calls().length;
  await type(nameInput, "bad name!");
  await click(btn(root, "Create"));
  assert.ok(findAll(root, (n) => n.getAttribute && n.getAttribute("role") === "alert").some((n) => /Invalid user name/.test(n.textContent)));
  await type(nameInput, "dave");
  await click(btn(root, "Create"));
  assert.match(all(root), /Password must not be empty/);
  assert.equal(calls().length, before, "no request for invalid input");

  await type(pwInput, "s3cret");
  await withData({}, async () => {
    failures["POST api/users"] = { status: 409, error: "conflict", message: "user dave exists in sqlite row 7" };
    await click(btn(root, "Create"));
    assert.match(all(root), /The change conflicts with the current state/);
    assert.ok(!all(root).includes("sqlite row 7"));
    assert.ok(byTag(root, "h2").some((h) => h.textContent === "Add user"), "dialog stays open");
  }, {});
  delete failures["POST api/users"];

  const stack = await toasts();
  fixtures["POST api/users"] = { user: { name: "dave" } };
  await click(btn(root, "Create"));
  delete fixtures["POST api/users"];
  const post = used("POST", "api/users").pop();
  assert.deepEqual(post.body, { name: "dave", password: "s3cret", role: "user" });
  assert.match(stack.textContent, /User dave created/);
});

test("users view: change password needs a value and patches {password}", async () => {
  const root = await mount("users");
  await click(findByText(rowOf(root, ALICE), "button", "Password")[0]);
  assert.ok(byTag(root, "h2").some((h) => h.textContent === `Change password: ${ALICE}`));
  await click(btn(root, "Change"));
  assert.match(all(root), /Password must not be empty/);
  assert.equal(used("PATCH", `api/users/${ALICE}`).length, 0);
  await type(inputs(root, "password")[0], "n3w");
  fixtures[`PATCH api/users/${ALICE}`] = { user: { name: ALICE }, dropped_rules: 0 };
  await click(btn(root, "Change"));
  delete fixtures[`PATCH api/users/${ALICE}`];
  assert.deepEqual(used("PATCH", `api/users/${ALICE}`)[0].body, { password: "n3w" });
});

test("users view: promoting a user with rules asks first and shows the dropped count from the integer field", async () => {
  const root = await mount("users");
  const stack = await toasts();
  fixtures[`PATCH api/users/${ALICE}`] = { user: { name: ALICE }, dropped_rules: 2 };
  await click(findByText(rowOf(root, ALICE), "button", "Make admin")[0]);
  assert.equal(used("PATCH", `api/users/${ALICE}`).length, 0, "nothing sent before the confirmation");
  assert.match(all(root), /has 2 explicit rules/);
  assert.ok(all(root).includes(ALICE));
  assert.equal(findAll(root, (n) => n.localName === "b").length, 0);
  const dialog = findAll(root, (n) => n.getAttribute && n.getAttribute("role") === "dialog")[0];
  await click(findByText(dialog, "button", "Make admin")[0]);
  delete fixtures[`PATCH api/users/${ALICE}`];
  assert.deepEqual(used("PATCH", `api/users/${ALICE}`)[0].body, { role: "admin" });
  assert.match(stack.textContent, /is now admin, 2 rules dropped/);
});

test("users view: promoting a user without rules and demoting need no confirmation", async () => {
  await withData(usersWith(adminUser, { ...adminUser, name: "erin", role: "user", acl_count: 0 }), async () => {
    const root = await mount("users");
    fixtures["PATCH api/users/carol"] = { user: { name: "carol" }, dropped_rules: 0 };
    fixtures["PATCH api/users/erin"] = { user: { name: "erin" }, dropped_rules: 0 };
    await click(findByText(rowOf(root, "carol"), "button", "Demote")[0]);
    assert.deepEqual(used("PATCH", "api/users/carol")[0].body, { role: "user" });
    await click(findByText(rowOf(root, "erin"), "button", "Make admin")[0]);
    assert.deepEqual(used("PATCH", "api/users/erin")[0].body, { role: "admin" });
    delete fixtures["PATCH api/users/carol"];
    delete fixtures["PATCH api/users/erin"];
  });
});

test("users view: a failing role change toasts the localized code text, not the backend message", async () => {
  await withData(usersWith(adminUser), async () => {
    const root = await mount("users");
    const stack = await toasts();
    failures["PATCH api/users/carol"] = { status: 403, error: "protected", message: "secret backend text" };
    await click(findByText(rowOf(root, "carol"), "button", "Demote")[0]);
    delete failures["PATCH api/users/carol"];
    assert.match(stack.textContent, /This item is protected and cannot be changed/);
    assert.ok(!stack.textContent.includes("secret backend text"));
    failures["PATCH api/users/carol"] = { status: 500, error: "weird_code", message: "x" };
    await click(findByText(rowOf(root, "carol"), "button", "Demote")[0]);
    delete failures["PATCH api/users/carol"];
    assert.match(stack.textContent, /Unknown error \[weird_code\]/);
  });
});

test("users view: delete needs the exact name, sends confirm and keeps the dialog open on failure", async () => {
  const root = await mount("users");
  await click(findByText(rowOf(root, ALICE), "button", "Delete")[0]);
  const dialog = () => findAll(root, (n) => n.getAttribute && n.getAttribute("role") === "dialog")[0];
  const confirm = () => findByText(dialog(), "button", "Delete")[0];
  assert.ok(prop(confirm(), "disabled"));
  const phrase = inputs(dialog())[0];
  await type(phrase, "alice");
  assert.ok(prop(confirm(), "disabled"));
  await type(phrase, ALICE);
  assert.ok(!prop(confirm(), "disabled"));

  const path = `DELETE api/users/${ALICE}`;
  failures[path] = { status: 409, error: "conflict", message: "backend says no" };
  await click(confirm());
  delete failures[path];
  assert.ok(dialog(), "dialog stays open");
  assert.match(dialog().textContent, /The change conflicts with the current state/);
  assert.ok(!dialog().textContent.includes("backend says no"));

  fixtures[path] = { deleted: true };
  const stack = await toasts();
  await click(confirm());
  delete fixtures[path];
  assert.deepEqual(used("DELETE", `api/users/${ALICE}`).pop().body, { confirm: ALICE });
  assert.equal(dialog(), undefined);
  assert.match(stack.textContent, /deleted/);
});

test("users view: a German mount has no English literal and no key placeholder, and a switch re-renders", async () => {
  const root = await mount("users", {}, { lang: "de" });
  const text = all(root);
  assert.match(text, /Benutzer anlegen/);
  assert.match(text, /Admin aus den Optionen/);
  assert.ok(!ENGLISH_LEFTOVERS.test(text), text);
  noPlaceholder(text, "users");
  await click(btn(root, "Benutzer anlegen"));
  assert.ok(!/Add user|Cancel|Create/.test(all(root)));
  noPlaceholder(all(root), "users");
  setLang("en");
  await settle();
  assert.match(all(root), /Add user/);
  assert.match(all(root), /Cancel/);
  setLang("de");
  await settle();
  assert.match(all(root), /Abbrechen/);
});

// ---------------------------------------------------------------- acl

const aclRows = (root) => byTag(root, "tbody")[0] && byTag(byTag(root, "tbody")[0], "tr");
const selects = (root) => byTag(root, "select");

test("acl view: meta, scrollable table with caption, scopes and a uniquely named permission select per row", async () => {
  const mod = await import(new URL("views/acl.mjs", STATIC));
  assert.deepEqual(mod.meta, { id: "acl", titleKey: "view.acl" });
  const root = await mount("acl");
  assert.ok(findAll(root, (n) => cls(n).includes("table-scroll")).length === 1);
  const caption = byTag(root, "caption")[0];
  assert.ok(caption && cls(caption).includes("sr-only"));
  assert.ok(byTag(root, "th").every((th) => th.getAttribute("scope") === "col"));
  assert.equal(byTag(root, "th").length, 5);
  const rowSelects = selects(byTag(root, "table")[0]);
  assert.equal(rowSelects.length, 2);
  const names = rowSelects.map((n) => n.getAttribute("aria-label"));
  assert.equal(new Set(names).size, 2);
  assert.ok(names.some((n) => n.includes("alerts") && n.includes(ALICE)));
  assert.ok(byTag(root, "tr").some((r) => r.textContent.includes("news-*") && r.textContent.includes("GUI")));
  assert.deepEqual(auditNames(root), []);
  assert.deepEqual(auditTables(root), []);
});

test("acl view: hostile user and topic names stay text", async () => {
  await withData(
    { "GET api/acl": { rules: [{ user: ALICE, topic: "<img src=x>", permission: "ro", origin: "gui" }] } },
    async () => {
      const root = await mount("acl");
      assert.ok(all(root).includes(ALICE) && all(root).includes("<img src=x>"));
      assert.equal(findAll(root, (n) => n.localName === "b" || n.localName === "img").length, 0);
    },
  );
});

test("acl view: the add form is labelled and rejects an unknown user, a bad topic and a missing permission locally", async () => {
  const root = await mount("acl");
  const fields = findAll(root, (n) => n.localName === "label").map((l) => l.textContent.trim());
  assert.ok(fields.includes("User") && fields.includes("Topic or pattern"));
  const form = selects(root)[0];
  const topic = inputs(root).find((n) => n.getAttribute("id") === "acl-add-topic");
  assert.ok(form && topic);
  const before = calls().length;
  await click(btn(root, "Add"));
  assert.ok(findAll(root, (n) => n.getAttribute && n.getAttribute("role") === "alert").some((n) => /Choose a user/.test(n.textContent)));
  await choose(form, "everyone");
  await type(topic, "bad topic!");
  await click(btn(root, "Add"));
  assert.match(all(root), /Invalid topic pattern/);
  assert.equal(calls().length, before, "no request for invalid input");
});

test("acl view: a valid add sends PUT with exactly user, topic and permission, clears the topic and reloads", async () => {
  await withData({ "PUT api/acl": { ok: true } }, async () => {
    const root = await mount("acl");
    const stack = await toasts();
    await choose(selects(root)[0], "everyone");
    const topic = inputs(root).find((n) => n.getAttribute("id") === "acl-add-topic");
    await type(topic, "alerts-*");
    await click(btn(root, "Add"));
    const put = used("PUT", "api/acl")[0];
    assert.deepEqual(Object.keys(put.body).sort(), ["permission", "topic", "user"]);
    assert.deepEqual(put.body, { user: "everyone", topic: "alerts-*", permission: "rw" });
    assert.match(stack.textContent, /everyone on alerts-\*: rw/);
    assert.equal(prop(topic, "value"), "");
    assert.equal(used("GET", "api/acl").length, 2, "rules reloaded");
    assert.equal(used("GET", "api/users").length, 2, "users reloaded");
  });
});

test("acl view: the filter narrows by user or topic, case-insensitive, and shows the empty text", async () => {
  const root = await mount("acl");
  const filter = inputs(root).find((n) => n.getAttribute("id") === "acl-filter");
  assert.ok(filter);
  assert.equal(aclRows(root).length, 2);
  await type(filter, "NEWS");
  assert.equal(aclRows(root).length, 1);
  assert.ok(aclRows(root)[0].textContent.includes("news-*"));
  await type(filter, "alice");
  assert.equal(aclRows(root).length, 1);
  await type(filter, "zzz");
  assert.match(all(root), /No rules\./);
});

test("acl view: a row permission change sends PUT; a failing save toasts the localized code text", async () => {
  await withData({ "PUT api/acl": { ok: true } }, async () => {
    const root = await mount("acl");
    const stack = await toasts();
    const rowSelect = selects(byTag(root, "table")[0])[0];
    await choose(rowSelect, "deny");
    assert.deepEqual(used("PUT", "api/acl")[0].body, { user: "everyone", topic: "news-*", permission: "deny" });
    failures["PUT api/acl"] = { status: 409, error: "conflict", message: "raw backend text" };
    await choose(rowSelect, "ro");
    delete failures["PUT api/acl"];
    assert.match(stack.textContent, /The change conflicts with the current state/);
    assert.ok(!stack.textContent.includes("raw backend text"));
  });
});

test("acl view: delete asks first, keeps the dialog open on failure and sends user and topic as query", async () => {
  await withData({ "DELETE api/acl": { ok: true } }, async () => {
    const root = await mount("acl");
    const stack = await toasts();
    const delBtn = byTag(root, "button").find((b) => (b.getAttribute("aria-label") || "").includes("news-*"));
    await click(delBtn);
    const dialog = () => findAll(root, (n) => n.getAttribute && n.getAttribute("role") === "dialog")[0];
    assert.ok(dialog().textContent.includes("news-*") && dialog().textContent.includes("everyone"));
    assert.equal(used("DELETE", "api/acl").length, 0);
    failures["DELETE api/acl"] = { status: 404, error: "not_found", message: "raw backend text" };
    await click(findByText(dialog(), "button", "Delete")[0]);
    delete failures["DELETE api/acl"];
    assert.ok(dialog(), "dialog stays open");
    assert.match(dialog().textContent, /Not found/);
    assert.ok(!dialog().textContent.includes("raw backend text"));
    await click(findByText(dialog(), "button", "Delete")[0]);
    const call = calls().filter((c) => c.method === "DELETE").pop();
    assert.equal(call.url, "api/acl?user=everyone&topic=news-%2A");
    assert.equal(dialog(), undefined);
    assert.match(stack.textContent, /Rule deleted/);
  });
});

test("acl view: a German mount has no English literal and no key placeholder", async () => {
  const root = await mount("acl", {}, { lang: "de" });
  const text = all(root);
  assert.match(text, /Regel hinzufügen/);
  assert.match(text, /Admins haben immer vollen Zugriff/);
  assert.ok(!ENGLISH_LEFTOVERS.test(text), text);
  assert.ok(!/Add rule|Topic or pattern|User\b|Origin|Permission/.test(text), text);
  noPlaceholder(text, "acl");
  assert.deepEqual(auditNames(root), []);
});

test("matrix view has everyone column and a row per topic", async () => {
  const root = await mount("matrix");
  const heads = findAll(root, (n) => n.localName === "th").map((n) => n.textContent.trim());
  assert.ok(heads.includes("everyone"));
  const body = findAll(root, (n) => n.localName === "tbody")[0];
  assert.equal(findAll(body, (n) => n.localName === "tr").length, 2);
});

// Preact/toast timers can outlive the tests; end the worker once the results are reported.
test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
