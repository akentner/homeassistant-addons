// Topic x user matrix of explicit rules with cell editing (D-17).
import { html, useState, useAsync, toast, Modal, PermSelect, ErrorNote, Loading } from "../lib/ui.mjs";
import { get, put, del } from "../lib/api.mjs";
import { buildMatrix, validTopic } from "../lib/model.mjs";

export const meta = { id: "matrix", title: "Matrix" };

const msg = (e) => (e && e.message) || String(e);

function CellEditor({ cell, onClose, onSaved }) {
  const [value, setValue] = useState(cell.permission || "");
  const save = async () => {
    try {
      if (value) await put("acl", { body: { user: cell.user, topic: cell.topic, permission: value } });
      else if (cell.permission) await del("acl", { query: { user: cell.user, topic: cell.topic } });
      toast("ok", `${cell.user} on ${cell.topic}: ${value || "no rule"}`);
      onSaved();
    } catch (e) {
      toast("error", msg(e));
    }
  };
  return html`<${Modal} title=${`${cell.user} on ${cell.topic}`} onClose=${onClose}>
    <div class="form-row">
      <label>Permission</label>
      <${PermSelect} value=${value} includeNone=${true} onChange=${setValue} />
    </div>
    <div class="actions">
      <button class="btn secondary" type="button" onClick=${onClose}>Cancel</button>
      <button class="btn" type="button" onClick=${save}>Save</button>
    </div>
  <//>`;
}

export default function View() {
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
      The grid shows explicit rules only. For the effective result of a user and topic use the
      <a href="#/tools">Tools</a> view.
    </div>
    <div class="matrix">
      <table>
        <thead>
          <tr>
            <th>Topic</th>
            ${columns.map((n) => html`<th key=${n}>${n}</th>`)}
          </tr>
        </thead>
        <tbody>
          ${grid.topics.map(
            (t) =>
              html`<tr key=${t}>
                <th class="mono">
                  ${t} ${validTopic(t) && html`<a href=${`#/tools?topic=${encodeURIComponent(t)}`}>?</a>`}
                </th>
                ${columns.map((n) => {
                  const permission = (grid.cells[n] || {})[t] || "";
                  return html`<td
                    key=${n}
                    class=${`cell ${permission}`}
                    title=${`${n} on ${t}`}
                    onClick=${() => setCell({ user: n, topic: t, permission })}
                  >
                    ${permission || "·"}
                  </td>`;
                })}
              </tr>`,
          )}
        </tbody>
      </table>
      ${grid.topics.length === 0 && html`<div class="muted">No rules yet.</div>`}
    </div>
    ${cell && html`<${CellEditor} cell=${cell} onClose=${() => setCell(null)} onSaved=${saved} />`}
  </div>`;
}
