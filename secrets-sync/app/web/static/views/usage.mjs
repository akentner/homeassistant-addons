// Key usage tab: where `!secret <key>` is referenced (names and file:line positions only).
import { html, useState } from "../vendor/admin-ui/ui.mjs";
import { tp, useLang, useT } from "../vendor/admin-ui/i18n.mjs";
import { formatDateTime } from "../vendor/admin-ui/format.mjs";
import { asArr, asObj, filterKeys, MAX_REFS, MAX_USAGE, parseTime, str } from "../model.mjs";
import { KeyList, useNum } from "../parts.mjs";

function Entries({ map, query, bad }) {
  const tt = useT();
  const num = useNum();
  const source = asObj(map);
  const names = filterKeys(Object.keys(source), query).sort();
  return html`<div>
    ${names.slice(0, MAX_USAGE).map((name) => {
      const entry = asObj(source[name]);
      const refs = asArr(entry.refs).map(asObj);
      const total = typeof entry.count === "number" ? entry.count : refs.length;
      return html`<details key=${name}>
        <summary>
          <span class=${`key${bad ? " bad" : ""}`}>${name}</span>
          <span class="muted"> ${tp("usage.uses", total, { n: num(total) })}</span>
        </summary>
        ${refs.slice(0, MAX_REFS).map((r, i) => html`<div key=${i}><code>${`${str(r.file)}:${str(r.line)}`}</code></div>`)}
        ${total > Math.min(refs.length, MAX_REFS) && html`<div class="muted">${tt("keys.more", { n: num(total - Math.min(refs.length, MAX_REFS)) })}</div>`}
      </details>`;
    })}
    ${names.length > MAX_USAGE && html`<div class="muted">${tt("keys.more", { n: num(names.length - MAX_USAGE) })}</div>`}
  </div>`;
}

export default function UsageView({ state }) {
  const tt = useT();
  const num = useNum();
  const lang = useLang();
  const [query, setQuery] = useState("");
  const usage = asObj(state.usage);
  if (usage.enabled !== true) return html`<p class="muted">${tt("usage.off")}</p>`;
  const missingCount = Object.keys(asObj(usage.missing)).length;
  const usedCount = Object.keys(asObj(usage.used)).length;
  const unused = filterKeys(usage.unused, query);
  const at = parseTime(usage.scanned_at);
  const roots = asArr(usage.roots).map(str).join(", ") || "-";
  return html`<div>
    <input type="search" class="search" value=${query} aria-label=${tt("usage.search")} placeholder=${tt("usage.search")}
      autocomplete="off" onInput=${(ev) => setQuery(ev.target.value)} />
    <p class="muted">
      ${tt("usage.summary", {
        files: typeof usage.files_scanned === "number" ? num(usage.files_scanned) : "-",
        roots,
        at: at === null ? "-" : formatDateTime(at, lang),
      })}
      ${usage.truncated === true && ` ${tt("usage.truncated")}`}
    </p>
    ${missingCount > 0 &&
    html`<h3 class="bad">${tt("usage.missing", { n: num(missingCount) })}</h3>
      <${Entries} map=${usage.missing} query=${query} bad=${true} />`}
    <h3>${tt("usage.unused", { n: num(unused.length) })}</h3>
    <${KeyList} names=${unused} />
    <h3>${tt("usage.used", { n: num(usedCount) })}</h3>
    ${usedCount > 0 ? html`<${Entries} map=${usage.used} query=${query} />` : html`<p class="muted">${tt("usage.none")}</p>`}
  </div>`;
}
