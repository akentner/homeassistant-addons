import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as m from "../../app/web/static/lib/model.mjs";

const cases = JSON.parse(readFileSync(new URL("./topic_cases.json", import.meta.url), "utf8"));

test("matchTopic agrees with the shared fixture", () => {
  assert.ok(cases.length >= 12);
  for (const c of cases) assert.equal(m.matchTopic(c.pattern, c.topic), c.match, `${c.pattern} vs ${c.topic}`);
});

test("validators", () => {
  assert.ok(m.validUsername("alice"));
  assert.ok(!m.validUsername("-x"));
  assert.ok(!m.validUsername("a".repeat(65)));
  assert.ok(m.validTopicPattern("pre*"));
  assert.ok(!m.validTopic("pre*"));
  assert.ok(m.validTopic("abc_1"));
  assert.ok(m.validDuration("2d"));
  assert.ok(!m.validDuration("2w"));
  assert.ok(m.validLabel("a".repeat(64)));
  assert.ok(!m.validLabel("a".repeat(65)));
  assert.ok(!m.validLabel("bad\nlabel"));
});

test("buildMatrix", () => {
  const mx = m.buildMatrix(
    [{ username: "bob" }, { username: "everyone" }, { username: "alice" }],
    [
      { user: "bob", topic: "t2", permission: "rw" },
      { user: "alice", topic: "t1", permission: "ro" },
      { user: "ghost", topic: "t1", permission: "deny" },
      { user: "bob", topic: "t1", permission: "wo" },
    ],
  );
  assert.deepEqual(mx.users, ["everyone", "alice", "bob", "ghost"]);
  assert.deepEqual(mx.topics, ["t1", "t2"]);
  assert.equal(mx.cells.bob.t2, "rw");
  assert.equal(mx.cells.ghost.t1, "deny");
  assert.equal(mx.cells.alice.t2, undefined);
});

test("sortRules and groupRulesByUser", () => {
  const rules = [
    { user: "b", topic: "z", permission: "ro" },
    { user: "everyone", topic: "a", permission: "ro" },
    { user: "b", topic: "a", permission: "rw" },
  ];
  assert.deepEqual(m.sortRules(rules).map((r) => `${r.user}:${r.topic}`), ["everyone:a", "b:a", "b:z"]);
  assert.deepEqual(Object.keys(m.groupRulesByUser(rules)), ["everyone", "b"]);
});

test("formatters", () => {
  assert.equal(m.fmtBytes(0), "0 B");
  assert.equal(m.fmtBytes(1536), "1.5 KiB");
  assert.equal(m.fmtExpiry(0), "never");
  assert.match(m.fmtExpiry(1, 10 ** 12), /^expired /);
  const now = 1_000_000_000_000;
  assert.equal(m.relTime(now / 1000 - 5, now), "just now");
  assert.equal(m.relTime(now / 1000 - 300, now), "5 min ago");
  assert.match(m.fmtUnix(1700000000), /^\d{4}-\d\d-\d\d \d\d:\d\d$/);
  assert.equal(m.protectionLabel("last_admin"), "last admin");
});

test("confirmMatches is strict", () => {
  assert.ok(m.confirmMatches("reset acls", "reset acls"));
  assert.ok(!m.confirmMatches("Reset ACLs", "reset acls"));
  assert.ok(!m.confirmMatches("reset acls ", "reset acls"));
});

test("constants mirror the contract", () => {
  assert.deepEqual(m.RESET_PHRASES, { acls: "reset acls", cache: "clear cache", everything: "reset everything" });
  assert.deepEqual(m.PERMISSIONS, ["rw", "ro", "wo", "deny"]);
});
