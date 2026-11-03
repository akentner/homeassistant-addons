// Topic x user matrix of explicit rules with cell editing. Cells are real buttons. Built on the admin-ui lib.
import { html, useState, useAsync, toast, Modal, Loading } from "../vendor/admin-ui/ui.mjs";
import { get, put, del } from "../vendor/admin-ui/api.mjs";
import { useT, tError } from "../vendor/admin-ui/i18n.mjs";
import { PermSelect, ErrorNote } from "../components.mjs";
import { buildMatrix, validTopic } from "../lib/model.mjs";

export const meta = { id: "matrix", titleKey: "view.matrix" };

function CellEditor({ cell, onClose, onSaved }) {
  const tt = useT();
  const [value, setValue] = useState(cell.permission || "");
  const save = async () => {
    try {
      if (value) await put("acl", { body: { user: cell.user, topic: cell.topic, permission: value } });
      else if (cell.permission) await del("acl", { query: { user: cell.user, topic: cell.topic } });
      toast("ok", tt("matrix.saved", { user: cell.user, topic: cell.topic, permission: value || tt("matrix.no_rule") }));
      onSaved();
    } catch (e) {
      toast("error", tError(e));
    }
  };
  return html`<${Modal} title=${tt("matrix.edit.title", { user: cell.user, topic: cell.topic })} onClose=${onClose}>
    <div class="form-row">
      <label>${tt("matrix.edit.permission")}</label>
      <${PermSelect}
        value=${value}
        includeNone=${true}
        label=${tt("matrix.edit.permission")}
        onChange=${setValue}
      />
    </div>
    <div class="actions">
      <button class="btn secondary" type="button" onClick=${onClose}>${tt("btn.cancel")}</button>
      <button class="btn" type="button" onClick=${save}>${tt("btn.save")}</button>
    </div>
  <//>`;
}

export default function View() {
  const tt = useT();
  const usersQ = useAsync(() => get("users"));
  const rulesQ = useAsync(() => get("acl"));
  const [cell, setCell] = useState(null);
  if ((usersQ.loading && !usersQ.data) || (rulesQ.loading && !rulesQ.data)) return html`<${Loading} />`;
  if (usersQ.error || rulesQ.error) return html`<${ErrorNote} error=${usersQ.error || rulesQ.error} />`;
  const users = (usersQ.data.users || []).filter((u) => u.role !== "admin");
  const rules = rulesQ.data.rules || [];
  const grid = buildMatrix([{ username: "everyone" }, ...users.map((u) => ({ username: u.name }))], rules);
  const adminNames = new Set((usersQ.data.users || []).filter((u) => u.role === "admin").map((u) => u.name));
  const columns = grid.users.filter((n) => !adminNames.has(n));
  const saved = () => {
    setCell(null);
    rulesQ.reload();
    usersQ.reload();
  };
  return html`<div>
    <div class="muted">
      ${tt("matrix.help_before")} <a href="#/tools">${tt("matrix.help_link")}</a>${tt("matrix.help_after")}
    </div>
    <div class="matrix">
      <table>
        <caption class="sr-only">
          ${tt("matrix.caption")}
        </caption>
        <thead>
          <tr>
            <th scope="col">${tt("matrix.col.topic")}</th>
            ${columns.map((n) => html`<th scope="col" key=${n}>${n}</th>`)}
          </tr>
        </thead>
        <tbody>
          ${grid.topics.map(
            (topic) =>
              html`<tr key=${topic}>
                <th scope="row" class="mono">
                  ${topic}
                  ${validTopic(topic) &&
                  html`<a
                    href=${`#/tools?topic=${encodeURIComponent(topic)}`}
                    aria-label=${tt("matrix.tools_link", { topic })}
                    >?</a
                  >`}
                </th>
                ${columns.map((user) => {
                  const permission = (grid.cells[user] || {})[topic] || "";
                  return html`<td key=${user} class=${`cell ${permission}`}>
                    <button
                      class="cell-btn"
                      type="button"
                      aria-label=${tt("matrix.cell", { user, topic, permission: permission || tt("matrix.no_rule") })}
                      onClick=${() => setCell({ user, topic, permission })}
                    >
                      ${permission || "·"}
                    </button>
                  </td>`;
                })}
              </tr>`,
          )}
        </tbody>
      </table>
      ${grid.topics.length === 0 && html`<div class="muted">${tt("matrix.empty")}</div>`}
    </div>
    ${cell && html`<${CellEditor} cell=${cell} onClose=${() => setCell(null)} onSaved=${saved} />`}
  </div>`;
}
