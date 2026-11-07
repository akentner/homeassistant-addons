// Events tab: newest first, capped at MAX_EVENTS. Messages are state text and rendered as text only.
import { html, DataTable } from "../vendor/admin-ui/ui.mjs";
import { useLang, useT } from "../vendor/admin-ui/i18n.mjs";
import { formatDateTime } from "../vendor/admin-ui/format.mjs";
import { asArr, asObj, MAX_EVENTS, parseTime, str } from "../model.mjs";

export default function EventsView({ state }) {
  const tt = useT();
  const lang = useLang();
  const rows = asArr(state.events).map(asObj).slice(0, MAX_EVENTS);
  const columns = [
    {
      key: "at",
      titleKey: "events.col.time",
      render: (r) => (parseTime(r.at) === null ? str(r.at) || "-" : formatDateTime(parseTime(r.at), lang)),
    },
    {
      key: "level",
      titleKey: "events.col.level",
      render: (r) => html`<span class=${`result ${["warning", "error"].includes(r.level) ? r.level : ""}`}>${str(r.level)}</span>`,
    },
    { key: "code", titleKey: "events.col.code", render: (r) => html`<code>${str(r.code)}</code>` },
    { key: "message", titleKey: "events.col.message", render: (r) => str(r.message) },
  ];
  return html`<div class="scroll">
    <${DataTable} columns=${columns} rows=${rows} rowKey=${(row, i) => i} caption=${tt("events.caption")} empty=${tt("events.none")} />
  </div>`;
}
