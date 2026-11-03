// View tests of the access group: users, acl, matrix (owned by plan 27-03).
import test from "node:test";
import assert from "node:assert/strict";
import { findAll, findByText, prop, mount, all } from "./harness.mjs";

test("users view: protected row has disabled Delete, hostile name stays text", async () => {
  const root = await mount("users");
  const text = all(root);
  assert.match(text, /admin from options/);
  assert.match(text, /<b>alice<\/b>/);
  assert.equal(findAll(root, (n) => n.localName === "b").length, 0);
  const rows = findAll(root, (n) => n.localName === "tr");
  const adminRow = rows.find((r) => r.textContent.includes("options_admin") || r.textContent.includes("admin from"));
  const del = findByText(adminRow, "button", "Delete")[0];
  assert.ok(del && prop(del, "disabled"));
  const aliceRow = rows.find((r) => r.textContent.includes("alice"));
  assert.ok(!prop(findByText(aliceRow, "button", "Delete")[0], "disabled"));
});

test("acl view renders rules", async () => {
  const text = all(await mount("acl"));
  assert.match(text, /alerts/);
  assert.match(text, /news-\*/);
  assert.match(text, /everyone/);
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
