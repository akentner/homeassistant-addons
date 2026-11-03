// View tests of the management group: tokens, tools, health, data (owned by plan 27-04).
import test from "node:test";
import assert from "node:assert/strict";
import { findAll, findByText, prop, settle, mount, all, calls, TOKEN_VALUE } from "./harness.mjs";

const { RESET_PHRASES } = await import(new URL("lib/model.mjs", new URL("../../app/web/static/", import.meta.url)));

test("tokens view: no token value before reveal, once after, gone after hide", async () => {
  const root = await mount("tokens");
  assert.match(all(root), /tk_abcde/);
  assert.match(all(root), /phone/);
  assert.ok(!/tk_[a-z0-9]{29}/.test(all(root)));
  const inputValues = () => findAll(root, (n) => n.localName === "input").map((n) => prop(n, "value"));
  findByText(root, "button", "Reveal")[0].dispatch("click");
  await settle();
  assert.equal(inputValues().filter((v) => v === TOKEN_VALUE).length, 1);
  assert.ok(calls().some((c) => c.url === "api/tokens/reveal" && c.body.id === "tk_abcde"));
  findByText(root, "button", "Hide")[0].dispatch("click");
  await settle();
  assert.equal(inputValues().filter((v) => v === TOKEN_VALUE).length, 0);
  assert.ok(!all(root).includes(TOKEN_VALUE));
});

test("tools view renders lookup form and generator", async () => {
  const root = await mount("tools");
  assert.match(all(root), /Effective rights/);
  assert.equal(findByText(root, "button", "Generate").length, 1);
  findByText(root, "button", "Generate")[0].dispatch("click");
  await settle();
  assert.ok(findAll(root, (n) => n.localName === "input").some((n) => prop(n, "value") === "abcdefghijklmnop"));
});

test("health view shows status and formatted sizes", async () => {
  const text = all(await mount("health"));
  assert.match(text, /ok/);
  assert.match(text, /2\.0 KiB/);
  assert.match(text, /1\.0 MiB/);
  assert.match(text, /Test publish/);
});

test("data view: reset needs the exact phrase, then posts it", async () => {
  const root = await mount("data");
  assert.match(all(root), /Download export/);
  assert.match(all(root), /auth-20261102T100000Z\.db/);
  assert.equal(findAll(root, (n) => n.localName === "button" && /Reset|Clear/.test(n.textContent)).length, 3);
  findByText(root, "button", "Reset ACLs")[0].dispatch("click");
  await settle();
  const confirm = findByText(root, "button", "Execute")[0];
  assert.ok(prop(confirm, "disabled"));
  const input = findAll(root, (n) => n.localName === "input" && prop(n, "type") === "text").pop();
  input.value = "reset acl";
  input.dispatch("input");
  await settle();
  assert.ok(prop(findByText(root, "button", "Execute")[0], "disabled"));
  input.value = RESET_PHRASES.acls;
  input.dispatch("input");
  await settle();
  const ready = findByText(root, "button", "Execute")[0];
  assert.ok(!prop(ready, "disabled"));
  ready.dispatch("click");
  await settle();
  const call = calls().find((c) => c.method === "POST" && c.url === "api/reset/acls");
  assert.deepEqual(call.body, { confirm: "reset acls" });
});

// Preact/toast timers can outlive the tests; end the worker once the results are reported.
test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
