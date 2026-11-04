// Aggregator of the ntfy string parts (de); a key defined in two parts is an error.
import core from "./strings/core.de.mjs";
import access from "./strings/access.de.mjs";
import manage from "./strings/manage.de.mjs";

const merged = {};
for (const part of [core, access, manage]) {
  for (const [key, value] of Object.entries(part)) {
    if (key in merged) throw new Error(`strings.de: key defined in two parts: ${key}`);
    merged[key] = value;
  }
}

export default merged;
