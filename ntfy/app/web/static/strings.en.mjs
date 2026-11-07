// Aggregator of the ntfy string parts (en); a key defined in two parts is an error.
import core from "./strings/core.en.mjs";
import access from "./strings/access.en.mjs";
import manage from "./strings/manage.en.mjs";

const merged = {};
for (const part of [core, access, manage]) {
  for (const [key, value] of Object.entries(part)) {
    if (key in merged) throw new Error(`strings.en: key defined in two parts: ${key}`);
    merged[key] = value;
  }
}

export default merged;
