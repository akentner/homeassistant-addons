import test from "node:test";
import assert from "node:assert/strict";

const STATIC = new URL("../../app/web/static/", import.meta.url);
const {
  ROWS,
  PORTS,
  REASONS,
  isUnknown,
  isViolated,
  bootMs,
  reasonIds,
  portState,
  keyInfo,
  overallStatus,
} = await import(new URL("model.mjs", STATIC));

test("ROWS: the ten values of the old page in order with their threshold flags", () => {
  assert.deepEqual(
    ROWS.map((r) => [r.field, r.flag ?? null]),
    [
      ["age", "r_age"],
      ["up", null],
      ["load1", null],
      ["io_some10", null],
      ["io_full10", "r_io"],
      ["mem_full10", null],
      ["sda_inflight", "r_sda"],
      ["mmc_inflight", null],
      ["dstate", "r_dstate"],
      ["kmsg_errors", "r_kmsg"],
    ],
  );
  assert.equal(ROWS.find((r) => r.field === "up").kind, "boot");
  for (const row of ROWS) assert.match(row.labelKey, /^hm\.row\.[a-z0-9_]+$/);
});

test("PORTS and REASONS carry a label key each", () => {
  assert.deepEqual(
    PORTS.map((p) => p.field),
    ["ping", "p22222", "p1883", "p8123", "p4357"],
  );
  assert.deepEqual(
    REASONS.map((r) => r.id),
    ["stale", "io_full10", "sda_inflight", "dstate", "kmsg"],
  );
  for (const item of [...PORTS, ...REASONS]) assert.match(item.labelKey, /^hm\.(port|reason)\.[a-z0-9_]+$/);
});

test("isUnknown: negative numbers, non-numbers and NaN", () => {
  for (const v of [-1, -0.5, "5", null, undefined, NaN, Infinity, {}, true]) assert.equal(isUnknown(v), true, String(v));
  for (const v of [0, 1, 0.5, 999999]) assert.equal(isUnknown(v), false, String(v));
});

test("isViolated: only a flag that is exactly 1", () => {
  const row = ROWS[0];
  assert.equal(isViolated({ r_age: 1 }, row), true);
  for (const v of [0, -1, "1", true, null, undefined, 2]) assert.equal(isViolated({ r_age: v }, row), false, String(v));
  assert.equal(isViolated({ r_age: 1 }, ROWS[1]), false, "rows without a flag are never violated");
  assert.equal(isViolated(null, row), false);
});

test("bootMs: now minus uptime and sample age", () => {
  assert.equal(bootMs({ up: 100, age: 5 }, 1_000_000), 1_000_000 - 105_000);
  assert.equal(bootMs({ up: 100, age: -1 }, 1_000_000), 1_000_000 - 100_000);
  assert.equal(bootMs({ up: 100 }, 1_000_000), 1_000_000 - 100_000);
  assert.equal(bootMs({ up: -1, age: 5 }, 1_000_000), null);
  assert.equal(bootMs({ up: "x" }, 1_000_000), null);
  assert.equal(bootMs({ up: 100, age: 5 }, NaN), null);
  assert.equal(bootMs({ up: 100, age: 5 }, undefined), null);
  assert.equal(bootMs(null, 1), null);
});

test("reasonIds: split, drop empty parts and none, keep unknown tokens", () => {
  assert.deepEqual(reasonIds({ reasons: "stale,io_full10" }), ["stale", "io_full10"]);
  assert.deepEqual(reasonIds({ reasons: "none" }), []);
  assert.deepEqual(reasonIds({ reasons: "" }), []);
  assert.deepEqual(reasonIds({ reasons: ",stale,,<b>x</b>," }), ["stale", "<b>x</b>"]);
  assert.deepEqual(reasonIds({}), []);
  assert.deepEqual(reasonIds(null), []);
});

test("portState: up for 1, down for 0, unknown otherwise", () => {
  assert.equal(portState({ ping: 1 }, "ping"), "up");
  assert.equal(portState({ ping: 0 }, "ping"), "down");
  for (const v of [-1, "1", null, undefined, 2]) assert.equal(portState({ ping: v }, "ping"), "unknown", String(v));
  assert.equal(portState({}, "p22222"), "unknown");
  assert.equal(portState(null, "ping"), "unknown");
});

test("keyInfo: unknown, invalid and ok with or without a type; hostile text passes through", () => {
  assert.deepEqual(keyInfo({ key_fp: "" }), { kind: "unknown" });
  assert.deepEqual(keyInfo({}), { kind: "unknown" });
  assert.deepEqual(keyInfo({ key_fp: "invalid" }), { kind: "invalid" });
  assert.deepEqual(keyInfo({ key_fp: "SHA256:abc", key_type: "ED25519" }), { kind: "ok", type: "ED25519", fp: "SHA256:abc" });
  assert.deepEqual(keyInfo({ key_fp: "SHA256:abc", key_type: "" }), { kind: "ok", type: "", fp: "SHA256:abc" });
  assert.deepEqual(keyInfo({ key_fp: "<b>x</b>", key_type: "<i>" }), { kind: "ok", type: "<i>", fp: "<b>x</b>" });
});

const host = (status, error = null) => ({ slug: "a", name: "a", host: "h", status, error, incidents: [] });

test("overallStatus: loading, error, problem count, degraded and ok", () => {
  assert.deepEqual(overallStatus(null, null, true), { kind: "muted", labelKey: "state.loading", count: 0 });
  assert.deepEqual(overallStatus(null, null, false), { kind: "muted", labelKey: "state.loading", count: 0 });
  assert.deepEqual(overallStatus(null, { code: "x" }, false), { kind: "error", labelKey: "state.error", count: 0 });
  const problems = { hosts: [host({ problem: 1 }), host({ problem: 0 }), host({ problem: 1 })] };
  assert.deepEqual(overallStatus(problems, null, false), { kind: "error", labelKey: "hm.problems.other", count: 2 });
  const mixed = { hosts: [host({ problem: 1 }), host(null, "status_failed")] };
  assert.equal(overallStatus(mixed, null, false).kind, "error", "a problem beats a degraded host");
  const degraded = { hosts: [host({ problem: 0 }), host(null, "status_failed")] };
  assert.deepEqual(overallStatus(degraded, null, false), { kind: "degraded", labelKey: "state.degraded", count: 0 });
  assert.equal(overallStatus({ hosts: [host(null)] }, null, false).kind, "degraded");
  assert.deepEqual(overallStatus({ hosts: [host({ problem: 0 })] }, null, false), { kind: "ok", labelKey: "state.ok", count: 0 });
  assert.deepEqual(overallStatus({ hosts: [] }, null, false), { kind: "ok", labelKey: "state.ok", count: 0 });
  assert.equal(overallStatus({ hosts: [host({ problem: 0 })] }, { code: "x" }, false).kind, "ok", "last data stays authoritative");
  assert.equal(overallStatus({ nonsense: true }, null, false).kind, "ok");
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
