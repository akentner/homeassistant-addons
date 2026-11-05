// Orphan check: every key of the English ntfy string table (except the errors. namespace, which the backend codes
// reference) occurs as a quoted literal in the ntfy sources. A plural base key counts through its .one or .other form.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const STATIC = new URL("../../app/web/static/", import.meta.url);
const ROOT = fileURLToPath(STATIC);

const sourceFiles = [
  "app.mjs",
  "components.mjs",
  "lib/model.mjs",
  ...readdirSync(new URL("views/", STATIC)).filter((f) => f.endsWith(".mjs")).map((f) => `views/${f}`),
];
const source = sourceFiles.map((f) => readFileSync(`${ROOT}${f}`, "utf8")).join("\n");

const stripComments = (src) => src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
const literals = new Set([...stripComments(source).matchAll(/(["'`])([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)\1/g)].map((m) => m[2]));

test("every ntfy string key is referenced by a literal in the ntfy sources", async () => {
  const { default: en } = await import(new URL("strings.en.mjs", STATIC));
  const orphans = [];
  for (const key of Object.keys(en)) {
    if (key.startsWith("errors.")) continue;
    const base = key.replace(/\.(one|other)$/, "");
    if (!literals.has(key) && !literals.has(base)) orphans.push(key);
  }
  assert.ok(sourceFiles.length >= 8, "the scan covers app, components, model and the five views");
  assert.deepEqual(orphans, [], `unreferenced string keys: ${orphans.join(", ")}`);
});
