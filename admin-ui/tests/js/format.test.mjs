import test from "node:test";
import assert from "node:assert/strict";

const LIB = new URL("../../app/web/static/lib/", import.meta.url);
const { formatDateTime, formatRelative, formatBytes, formatNumber } = await import(new URL("format.mjs", LIB));

// Node and ICU versions differ in narrow no-break spaces: compare with whitespace runs collapsed.
const ws = (s) => s.replace(/\s+/g, " ").trim();
const UTC = { timeZone: "UTC" };

test("formatDateTime renders 1970 for epoch 0 in both languages", () => {
  const de = ws(formatDateTime(0, "de", UTC));
  const en = ws(formatDateTime(0, "en", UTC));
  assert.ok(de.includes("1970") && en.includes("1970"));
  assert.ok(!/AM|PM/i.test(de), de);
  assert.match(de, /\b00:00\b/);
  assert.match(en, /Jan/);
  assert.match(en, /AM|PM/);
});

test("formatDateTime returns a dash for invalid input", () => {
  for (const bad of [null, undefined, NaN, ""]) assert.equal(formatDateTime(bad, "en"), "-");
});

test("formatRelative picks the unit by magnitude", () => {
  const now = 1_000_000_000_000;
  assert.equal(ws(formatRelative(now - 10_000, "en", now)), "now");
  assert.equal(ws(formatRelative(now - 5 * 60_000, "en", now)), "5 minutes ago");
  assert.equal(ws(formatRelative(now - 3 * 3_600_000, "en", now)), "3 hours ago");
  assert.equal(ws(formatRelative(now - 86_400_000, "en", now)), "yesterday");
  assert.equal(ws(formatRelative(now - 86_400_000, "de", now)), "gestern");
  assert.equal(ws(formatRelative(now - 5 * 60_000, "de", now)), "vor 5 Minuten");
  assert.equal(ws(formatRelative(now + 2 * 3_600_000, "en", now)), "in 2 hours");
});

test("formatRelative returns a dash for invalid input", () => {
  for (const bad of [null, undefined, NaN, ""]) assert.equal(formatRelative(bad, "en", 0), "-");
});

test("formatBytes scales units and localises the decimal separator", () => {
  assert.equal(formatBytes(0, "en"), "0 B");
  assert.equal(formatBytes(1536, "en"), "1.5 KiB");
  assert.equal(formatBytes(1536, "de"), "1,5 KiB");
  assert.equal(formatBytes(1048576, "en"), "1 MiB");
  assert.equal(formatBytes(1024 ** 3, "de"), "1 GiB");
  assert.equal(formatBytes(1024 ** 4, "en"), "1 TiB");
  for (const bad of [-1, NaN, Infinity, "x", null]) assert.equal(formatBytes(bad, "en"), "-");
});

test("formatNumber uses locale separators", () => {
  assert.equal(formatNumber(1234.5, "en"), "1,234.5");
  assert.equal(formatNumber(1234.5, "de"), "1.234,5");
  for (const bad of [NaN, Infinity, null, undefined, "x"]) assert.equal(formatNumber(bad, "en"), "-");
});

test("an unknown language falls back to en", () => {
  assert.equal(formatNumber(1234.5, "fr"), "1,234.5");
  assert.equal(formatNumber(1234.5, undefined), "1,234.5");
});
