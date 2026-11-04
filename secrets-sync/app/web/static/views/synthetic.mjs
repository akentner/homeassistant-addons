// Synthetic keys tab: configured templates (configuration, never values), the keys they use and their status.
import { html, DataTable } from "../vendor/admin-ui/ui.mjs";
import { useT } from "../vendor/admin-ui/i18n.mjs";
import { asArr, asObj, str } from "../model.mjs";
import { KeyList, KeyChip } from "../parts.mjs";

function statusText(tt, item) {
  let label;
  switch (item.status) {
    case "ok":
      label = tt("synthetic.status.ok");
      break;
    case "error":
      label = tt("synthetic.status.error");
      break;
    default:
      label = tt("synthetic.status.pending");
  }
  return item.status === "error" && item.error_code ? `${label} ${str(item.error_code)}` : label;
}

export default function SyntheticView({ state }) {
  const tt = useT();
  const items = asArr(state.synthetic).map(asObj);
  if (!items.length) return html`<p class="muted">${tt("synthetic.none")}</p>`;
  const columns = [
    { key: "name", titleKey: "synthetic.col.key", render: (r) => html`<${KeyChip} name=${str(r.name)} />` },
    { key: "template", titleKey: "synthetic.col.template", render: (r) => html`<code>${str(r.template)}</code>` },
    { key: "refs", titleKey: "synthetic.col.uses", render: (r) => html`<${KeyList} names=${r.refs} />` },
    {
      key: "status",
      titleKey: "synthetic.col.status",
      render: (r) => html`<span class=${r.status === "error" ? "result error" : r.status === "ok" ? "result ok" : "result warning"}>${statusText(tt, r)}</span>`,
    },
  ];
  return html`<div class="scroll">
    <${DataTable} columns=${columns} rows=${items} rowKey=${(row, i) => `${i}:${str(row.name)}`} caption=${tt("synthetic.caption")} />
  </div>`;
}
