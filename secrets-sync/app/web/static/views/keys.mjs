// Keys tab: search box, added/removed/changed sections (only when non-empty) and all key names.
import { html, useState } from "../vendor/admin-ui/ui.mjs";
import { useT } from "../vendor/admin-ui/i18n.mjs";
import { asObj, filterKeys, syntheticSet } from "../model.mjs";
import { KeyList, useNum } from "../parts.mjs";

export default function KeysView({ state }) {
  const tt = useT();
  const num = useNum();
  const [query, setQuery] = useState("");
  const keys = asObj(state.keys);
  const synthetic = syntheticSet(state);
  const sections = [
    ["added", "keys.added", false],
    ["removed", "keys.removed", true],
    ["changed", "keys.changed", false],
  ].map(([id, title, bad]) => ({ id, title, bad, list: filterKeys(keys[id], query) }));
  const all = filterKeys(keys.names, query);
  return html`<div>
    <input type="search" class="search" value=${query} aria-label=${tt("keys.search")} placeholder=${tt("keys.search")}
      autocomplete="off" onInput=${(ev) => setQuery(ev.target.value)} />
    ${sections
      .filter((s) => s.list.length > 0)
      .map(
        (s) => html`<div key=${s.id}>
          <h3 class=${s.bad ? "bad" : ""}>${tt(s.title, { n: num(s.list.length) })}</h3>
          <${KeyList} names=${s.list} synthetic=${synthetic} bad=${s.bad} />
        </div>`,
      )}
    <h3>${tt("keys.all", { n: num(all.length) })}</h3>
    <${KeyList} names=${all} synthetic=${synthetic} />
  </div>`;
}
