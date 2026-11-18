import test from "node:test";
import assert from "node:assert/strict";

const STATIC = new URL("../../app/web/static/", import.meta.url);
const {
  STATUS_KEYS,
  REGISTRATION_KEYS,
  BRANCH_KEYS,
  statusKey,
  statusKind,
  registrationKind,
  shortSha,
  toMs,
  pollMs,
  hasRegistration,
  SOURCE_KEYS,
  isSource,
  sourceKind,
  USER_LABEL_RE,
  validUser,
  splitRepository,
} = await import(new URL("model.mjs", STATIC));

const CODES = ["pending", "ok", "auth_failed", "not_found", "no_repository_yaml", "fetch_failed"];

test("statusKey: all six status codes map to their own literal key, anything else to mrp.status.none", () => {
  assert.deepEqual(Object.keys(STATUS_KEYS).sort(), [...CODES].sort());
  for (const code of CODES) assert.equal(statusKey(code), `mrp.status.${code}`);
  for (const other of [null, undefined, "", "OK", "toString", "__proto__", 3]) assert.equal(statusKey(other), "mrp.status.none");
});

test("statusKind: ok, warn for pending and no_repository_yaml, err for failures, muted otherwise", () => {
  assert.equal(statusKind("ok"), "ok");
  assert.equal(statusKind("pending"), "warn");
  assert.equal(statusKind("no_repository_yaml"), "warn");
  for (const code of ["auth_failed", "not_found", "fetch_failed"]) assert.equal(statusKind(code), "err");
  for (const other of [null, undefined, "", "bogus"]) assert.equal(statusKind(other), "muted");
});

test("shortSha: 12 characters of a 7-40 hex SHA, empty string otherwise", () => {
  const full = "0123456789abcdef0123456789abcdef01234567";
  assert.equal(shortSha(full), "0123456789ab");
  assert.equal(shortSha("0123456789ab"), "0123456789ab");
  assert.equal(shortSha("0123456"), "0123456");
  for (const bad of [null, undefined, "", "012345", `${full}8`, "0123456789AB", "g123456789ab", 123]) assert.equal(shortSha(bad), "");
});

test("toMs: ISO timestamp to epoch ms, null for garbage", () => {
  assert.equal(toMs("2026-11-18T12:00:00Z"), Date.UTC(2026, 10, 18, 12));
  for (const bad of [null, undefined, "", "yesterday", 1700000000000, {}]) assert.equal(toMs(bad), null);
});

test("pollMs: 2 s while a sync is requested or running, 15 s otherwise and without data", () => {
  assert.equal(pollMs({ sync: { state: "running", requested: false } }), 2000);
  assert.equal(pollMs({ sync: { state: "idle", requested: true } }), 2000);
  assert.equal(pollMs({ sync: { state: "running", requested: true } }), 2000);
  assert.equal(pollMs({ sync: { state: "idle", requested: false } }), 15000);
  assert.equal(pollMs({ sync: { state: "idle", requested: "yes" } }), 15000, "only a real true counts");
  assert.equal(pollMs({ sync: null }), 15000);
  assert.equal(pollMs({}), 15000);
  assert.equal(pollMs(null), 15000);
  assert.equal(pollMs(undefined), 15000);
});

test("REGISTRATION_KEYS: exactly the four D-19 states, each with its own literal key", () => {
  assert.deepEqual(REGISTRATION_KEYS, {
    registered: "mrp.reg.registered",
    missing: "mrp.reg.missing",
    leftover: "mrp.reg.leftover",
    error: "mrp.reg.error",
  });
});

test("registrationKind: badge kind per registration state, muted for anything else", () => {
  assert.equal(registrationKind("registered"), "ok");
  assert.equal(registrationKind("missing"), "warn");
  assert.equal(registrationKind("leftover"), "warn");
  assert.equal(registrationKind("error"), "err");
  for (const other of [null, undefined, "", "pending", "toString"]) assert.equal(registrationKind(other), "muted");
});

test("BRANCH_KEYS: the two branch sources of status.json", () => {
  assert.deepEqual(BRANCH_KEYS, {
    configured: "mrp.repo.branch.configured",
    upstream_default: "mrp.repo.branch.upstream_default",
  });
});

test("hasRegistration: true only when some row carries a non-null registration", () => {
  assert.equal(hasRegistration([]), false);
  assert.equal(hasRegistration([{ registration: null }, { registration: null }]), false);
  assert.equal(hasRegistration([{}, { registration: undefined }]), false);
  assert.equal(hasRegistration([{ registration: null }, { registration: { state: "registered" } }]), true);
  assert.equal(hasRegistration([{ registration: { state: "leftover", detail: "x" } }]), true);
  assert.equal(hasRegistration(null), false);
  assert.equal(hasRegistration(undefined), false);
  assert.equal(hasRegistration([null]), false);
});

test("SOURCE_KEYS: the four access sources, each with its own literal key; isSource only for own keys", () => {
  assert.deepEqual(SOURCE_KEYS, {
    gui: "mrp.source.gui",
    cli: "mrp.source.cli",
    api: "mrp.source.api",
    system: "mrp.source.system",
  });
  for (const source of ["gui", "cli", "api", "system"]) assert.equal(isSource(source), true);
  for (const other of [null, undefined, "", "GUI", "toString", "__proto__", "hasOwnProperty", 1]) assert.equal(isSource(other), false);
});

test("sourceKind: info for the system user, muted for everything else", () => {
  assert.equal(sourceKind("system"), "info");
  for (const other of ["gui", "cli", "api", null, undefined, "x"]) assert.equal(sourceKind(other), "muted");
});

test("validUser: same pattern as USER_RE in app/access.py (ASCII, 1-64 characters, letter or digit first)", () => {
  assert.equal(USER_LABEL_RE.source, "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$");
  for (const ok of ["alice", "a.b-c_1", "A", "7", "x".repeat(64)]) assert.equal(validUser(ok), true, ok);
  for (const bad of ["", "-x", ".x", "_x", "x".repeat(65), "ä", "a b", "a/b", "a\nb", " alice", "alice ", null, undefined, 5, ["alice"]]) {
    assert.equal(validUser(bad), false, String(bad));
  }
});

test("splitRepository: owner/repo into its two parts, null for anything else", () => {
  assert.deepEqual(splitRepository("example-org/private-addons"), ["example-org", "private-addons"]);
  for (const bad of ["", "example-org", "a/b/c", "/repo", "owner/", null, undefined, 3]) assert.equal(splitRepository(bad), null);
});
