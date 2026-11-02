// ACL rules view: filterable table, inline permission change, add and delete (D-17).
import {
  html,
  useState,
  useAsync,
  toast,
  ConfirmDialog,
  OriginBadge,
  PermSelect,
  ErrorNote,
  Loading,
} from "../lib/ui.mjs";
import { get, put, del } from "../lib/api.mjs";
import { sortRules, validTopicPattern, PERMISSIONS } from "../lib/model.mjs";

export const meta = { id: "acl", title: "ACL rules" };

const msg = (e) => (e && e.message) || String(e);

export default function View() {
  const rulesQ = useAsync(() => get("acl"));
  const usersQ = useAsync(() => get("users"));
  const [filter, setFilter] = useState("");
  const [pending, setPending] = useState(null);
  const [form, setForm] = useState({ user: "", topic: "", permission: "rw" });
  const [formError, setFormError] = useState("");
  if ((rulesQ.loading && !rulesQ.data) || (usersQ.loading && !usersQ.data)) return html`<${Loading} />`;
  if (rulesQ.error || usersQ.error) return html`<${ErrorNote} error=${rulesQ.error || usersQ.error} />`;
  const targets = (usersQ.data.users || []).filter((u) => u.role !== "admin").map((u) => u.name);
  if (!targets.includes("everyone")) targets.unshift("everyone");
  const f = filter.trim().toLowerCase();
  const rules = sortRules(rulesQ.data.rules || []).filter(
    (r) => !f || r.user.toLowerCase().includes(f) || r.topic.toLowerCase().includes(f),
  );
  const save = async (user, topic, permission) => {
    try {
      await put("acl", { body: { user, topic, permission } });
      toast("ok", `${user} on ${topic}: ${permission}`);
      rulesQ.reload();
      usersQ.reload();
    } catch (e) {
      toast("error", msg(e));
    }
  };
  const add = async () => {
    if (!targets.includes(form.user)) return setFormError("Choose a user.");
    if (!validTopicPattern(form.topic)) return setFormError("Invalid topic pattern (letters, digits, _ - and *).");
    if (!PERMISSIONS.includes(form.permission)) return setFormError("Choose a permission.");
    setFormError("");
    await save(form.user, form.topic, form.permission);
    setForm({ ...form, topic: "" });
  };
  const remove = async (r) => {
    try {
      await del("acl", { query: { user: r.user, topic: r.topic } });
      toast("ok", "Rule deleted");
      setPending(null);
      rulesQ.reload();
      usersQ.reload();
    } catch (e) {
      toast("error", msg(e));
    }
  };
  return html`<div>
    <div class="card">
      <h2>Add rule</h2>
      <div class="toolbar">
        <select value=${form.user} onChange=${(e) => setForm({ ...form, user: e.target.value })}>
          <option value="">user…</option>
          ${targets.map((n) => html`<option key=${n} value=${n}>${n}</option>`)}
        </select>
        <input
          type="text"
          placeholder="topic or pattern"
          value=${form.topic}
          onInput=${(e) => setForm({ ...form, topic: e.target.value })}
        />
        <${PermSelect} value=${form.permission} onChange=${(p) => setForm({ ...form, permission: p })} />
        <button class="btn" type="button" onClick=${add}>Add</button>
      </div>
      <div class="muted">Use * as wildcard, for example <code>alerts-*</code>. Admins always have full access.</div>
      ${formError && html`<div class="notice">${formError}</div>`}
    </div>
    <div class="toolbar">
      <input
        type="text"
        placeholder="Filter by user or topic"
        value=${filter}
        onInput=${(e) => setFilter(e.target.value)}
      />
    </div>
    <div class="card">
      <table class="data">
        <thead>
          <tr>
            <th>User</th>
            <th>Topic</th>
            <th>Permission</th>
            <th>Origin</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${rules.map(
            (r) =>
              html`<tr key=${r.user + "|" + r.topic}>
                <td>${r.user}</td>
                <td class="mono">${r.topic}</td>
                <td><${PermSelect} value=${r.permission} onChange=${(p) => save(r.user, r.topic, p)} /></td>
                <td><${OriginBadge} origin=${r.origin} /></td>
                <td class="actions">
                  <button class="btn small danger" type="button" onClick=${() => setPending(r)}>Delete</button>
                </td>
              </tr>`,
          )}
        </tbody>
      </table>
      ${rules.length === 0 && html`<div class="muted">No rules.</div>`}
    </div>
    ${pending &&
    html`<${ConfirmDialog}
      title="Delete rule"
      danger=${true}
      confirmLabel="Delete"
      message=${`Delete the rule for ${pending.user} on ${pending.topic}?`}
      onCancel=${() => setPending(null)}
      onConfirm=${() => remove(pending)}
    />`}
  </div>`;
}
