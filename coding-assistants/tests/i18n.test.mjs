import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import de from "../app/web/static/strings.de.mjs";
import en from "../app/web/static/strings.en.mjs";
import lib from "../app/web/static/vendor/admin-ui/strings.en.mjs";

test("German and English keys and placeholders match", () => {
  assert.deepEqual(Object.keys(de).sort(), Object.keys(en).sort());
  for (const key of Object.keys(en)) {
    assert.ok(en[key] && de[key]);
    assert.deepEqual(de[key].match(/\{\w+\}/g), en[key].match(/\{\w+\}/g));
  }
});

test("every literal translation and navigation key resolves", () => {
  const strings = { ...lib, ...en };
  for (const name of ["app.mjs", "terminal-clipboard.mjs"]) {
    const source = readFileSync(new URL(`../app/web/static/${name}`, import.meta.url), "utf8");
    for (const match of source.matchAll(/(?:\b(?:tt|t)\(\s*|titleKey:\s*)["']([^"']+)["']/g)) {
      assert.ok(Object.hasOwn(strings, match[1]), `${name}: missing ${match[1]}`);
    }
    for (const match of source.matchAll(/["'](ca\.[\w.]+)["']/g)) {
      assert.ok(Object.hasOwn(en, match[1]), `${name}: missing ${match[1]}`);
    }
  }
});
