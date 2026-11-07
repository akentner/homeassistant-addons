import test from "node:test";
import assert from "node:assert/strict";

const STATIC = new URL("../../app/web/static/", import.meta.url);
const { cleanVersion, readCoreVersion, parseUserAgent, detectBrowser, resolveVersion } = await import(new URL("spike-versions.mjs", STATIC));

const parentWith = (hass) => ({ document: { querySelector: (sel) => (sel === "home-assistant" ? { hass } : null) } });

test("cleanVersion accepts plain version strings only", () => {
  assert.equal(cleanVersion(" 2026.10.4 "), "2026.10.4");
  assert.equal(cleanVersion("0.1.0-3"), "0.1.0-3");
  for (const bad of ["", "https://x/y", "a b", "x".repeat(31), 5, null, undefined]) assert.equal(cleanVersion(bad), null, String(bad));
});

test("readCoreVersion reads hass.config.version from a readable parent", () => {
  const win = { parent: parentWith({ config: { version: "2026.10.4" } }) };
  assert.equal(readCoreVersion(win), "2026.10.4");
});

test("readCoreVersion gives null without parent, with a throwing parent or hostile values", () => {
  const solo = {};
  solo.parent = solo;
  assert.equal(readCoreVersion(solo), null);
  assert.equal(readCoreVersion({ parent: { get document() { throw new DOMException("blocked", "SecurityError"); } } }), null);
  assert.equal(readCoreVersion({ parent: parentWith(undefined) }), null);
  assert.equal(readCoreVersion({ parent: parentWith({ config: { version: "https://evil/x" } }) }), null);
  assert.equal(readCoreVersion({ parent: { document: { querySelector: () => null } } }), null);
  assert.equal(readCoreVersion(undefined), null);
});

test("parseUserAgent shortens common user agents and rejects unknown ones", () => {
  assert.equal(parseUserAgent("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.8078.48 Safari/537.36"), "Chrome 156.0.8078.48");
  assert.equal(parseUserAgent("Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"), "Firefox 140.0");
  assert.equal(parseUserAgent("Mozilla/5.0 Chrome/150.0.0.0 Safari/537.36 Edg/150.0.1.2"), "Edge 150.0.1.2");
  assert.equal(parseUserAgent("Mozilla/5.0 (iPhone) AppleWebKit/605 Version/18.1 Mobile Safari/604.1"), "Safari 18.1");
  assert.equal(parseUserAgent("curl/8"), null);
  assert.equal(parseUserAgent(undefined), null);
});

test("detectBrowser prefers client hints, skips the GREASE brand and the generic Chromium brand", async () => {
  const nav = { userAgent: "Firefox/1.0", userAgentData: { getHighEntropyValues: async (hints) => (assert.deepEqual(hints, ["fullVersionList"]), { fullVersionList: [{ brand: "Not;A=Brand", version: "8.0.0.0" }, { brand: "Chromium", version: "156.0.1" }, { brand: "Brave", version: "156.0.1" }] }) } };
  assert.equal(await detectBrowser(nav), "Brave 156.0.1");
  const only = { userAgentData: { getHighEntropyValues: async () => ({ fullVersionList: [{ brand: "Chromium", version: "156.0.1" }] }) } };
  assert.equal(await detectBrowser(only), "Chromium 156.0.1");
});

test("detectBrowser falls back to the user agent when hints throw, are empty or missing", async () => {
  const ua = "Mozilla/5.0 Firefox/140.0";
  assert.equal(await detectBrowser({ userAgent: ua, userAgentData: { getHighEntropyValues: async () => { throw new Error("denied"); } } }), "Firefox 140.0");
  assert.equal(await detectBrowser({ userAgent: ua, userAgentData: { getHighEntropyValues: async () => ({ fullVersionList: [] }) } }), "Firefox 140.0");
  assert.equal(await detectBrowser({ userAgent: ua }), "Firefox 140.0");
  assert.equal(await detectBrowser({}), null);
  assert.equal(await detectBrowser(undefined), null);
});

test("resolveVersion: typed beats detected, detected beats nothing, nothing is not_recorded", () => {
  assert.deepEqual(resolveVersion("1.0", " 2.0 "), { value: "2.0", source: "manual" });
  assert.deepEqual(resolveVersion("1.0", ""), { value: "1.0", source: "auto" });
  assert.deepEqual(resolveVersion(null, "  "), { value: "", source: "not_recorded" });
});
