import test from "node:test";
import assert from "node:assert/strict";

const LIB = new URL("../../app/web/static/lib/", import.meta.url);
const {
  parseColor,
  serializeColor,
  relativeLuminance,
  contrastRatio,
  isDarkColor,
  pickOnColor,
} = await import(new URL("color.mjs", LIB));

const SERIALIZED = /^(#[0-9a-f]{6}|rgba\(\d{1,3}, \d{1,3}, \d{1,3}, (0|1|0\.\d{1,3})\))$/;

test("parseColor reads hex, rgb, rgba and the space/slash form", () => {
  assert.deepEqual(parseColor("#fff"), { r: 255, g: 255, b: 255, a: 1 });
  assert.deepEqual(parseColor("#FAFAFA"), { r: 250, g: 250, b: 250, a: 1 });
  assert.deepEqual(parseColor("rgb(33, 33, 33)"), { r: 33, g: 33, b: 33, a: 1 });
  assert.deepEqual(parseColor("rgba(0, 0, 0, 0.12)"), { r: 0, g: 0, b: 0, a: 0.12 });
  assert.deepEqual(parseColor("rgb(10 20 30 / 0.5)"), { r: 10, g: 20, b: 30, a: 0.5 });
  assert.deepEqual(parseColor("rgb(10 20 30)"), { r: 10, g: 20, b: 30, a: 1 });
});

test("parseColor tolerates whitespace and letter case", () => {
  assert.deepEqual(parseColor("  RGB( 1 , 2 , 3 )  "), { r: 1, g: 2, b: 3, a: 1 });
  assert.deepEqual(parseColor("\n#AbC\t"), { r: 170, g: 187, b: 204, a: 1 });
  assert.deepEqual(parseColor("RGBA(1,2,3,.5)"), { r: 1, g: 2, b: 3, a: 0.5 });
});

test("parseColor rejects names, functions, junk and out-of-range numbers", () => {
  const bad = [
    "red",
    "transparent",
    "hsl(0, 0%, 0%)",
    "var(--x)",
    "",
    "   ",
    "#ff",
    "#ggg",
    "#fffff",
    "rgb(256, 0, 0)",
    "rgb(0, 0, 0, 2)",
    "rgb(-1, 0, 0)",
    "rgb(1.5, 0, 0)",
    "red; x:y",
    "#fff url(//x)",
    "#fff; background:url(//evil)",
    "rgb(0, 0, 0) !important",
    "url(javascript:alert(1))",
    "#" + "f".repeat(5000),
    null,
    undefined,
    42,
    {},
  ];
  for (const value of bad) assert.equal(parseColor(value), null, String(value).slice(0, 40));
});

test("serializeColor emits #rrggbb for opaque and rgba() with 3 decimals otherwise", () => {
  assert.equal(serializeColor({ r: 250, g: 250, b: 250, a: 1 }), "#fafafa");
  assert.equal(serializeColor({ r: 0, g: 0, b: 0, a: 0.12 }), "rgba(0, 0, 0, 0.12)");
  assert.equal(serializeColor({ r: 1, g: 2, b: 3, a: 0.123456 }), "rgba(1, 2, 3, 0.123)");
  assert.equal(serializeColor({ r: 1, g: 2, b: 3, a: 0 }), "rgba(1, 2, 3, 0)");
  assert.equal(serializeColor({ r: 1, g: 2, b: 3, a: 0.9999 }), "#010203");
  assert.equal(serializeColor(null), null);
  assert.equal(serializeColor({ r: "x", g: 0, b: 0, a: 1 }), null);
});

test("serializeColor output always matches the safe pattern", () => {
  const inputs = ["#009ac7", "rgb(33, 33, 33)", "rgba(0, 0, 0, 0.12)", "rgb(255 255 255 / 0.001)", "#abc"];
  for (const input of inputs) {
    const out = serializeColor(parseColor(input));
    assert.match(out, SERIALIZED, input);
  }
});

test("relativeLuminance and contrastRatio follow WCAG 2", () => {
  const black = parseColor("#000000");
  const white = parseColor("#ffffff");
  assert.equal(relativeLuminance(black), 0);
  assert.equal(relativeLuminance(white), 1);
  assert.equal(contrastRatio(black, white), 21);
  assert.equal(contrastRatio(white, black), 21);
  assert.equal(contrastRatio(white, white), 1);
  const grey = contrastRatio(parseColor("#777777"), white);
  assert.ok(grey > 4.47 && grey < 4.49, String(grey));
  const accent = contrastRatio(parseColor("#009ac7"), white);
  assert.ok(accent > 3.2 && accent < 3.3, String(accent));
});

test("isDarkColor uses the 0.179 luminance threshold", () => {
  assert.equal(isDarkColor(parseColor("#111111")), true);
  assert.equal(isDarkColor(parseColor("#1c1c1c")), true);
  assert.equal(isDarkColor(parseColor("#fafafa")), false);
  const mid = relativeLuminance(parseColor("#808080")) < 0.179;
  assert.equal(isDarkColor(parseColor("#808080")), mid);
  assert.equal(isDarkColor(parseColor("#767676")), false);
});

test("pickOnColor returns the better contrasting of white and #111111", () => {
  assert.equal(pickOnColor(parseColor("#000000")), "#ffffff");
  assert.equal(pickOnColor(parseColor("#ffffff")), "#111111");
  assert.equal(pickOnColor(parseColor("#03a9f4")), "#111111");
  assert.equal(pickOnColor(parseColor("#1a237e")), "#ffffff");
  for (const hex of ["#03a9f4", "#009ac7", "#1a237e", "#808080", "#e53935"]) {
    const bg = parseColor(hex);
    const on = parseColor(pickOnColor(bg));
    const other = parseColor(pickOnColor(bg) === "#ffffff" ? "#111111" : "#ffffff");
    assert.ok(contrastRatio(on, bg) >= contrastRatio(other, bg), hex);
  }
});
