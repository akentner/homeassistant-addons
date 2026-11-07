// ACL rules view: filterable table, inline permission change, add and delete. Built on the admin-ui lib.
import { html, useState, useAsync, toast, ConfirmDialog, Loading, Field } from "../vendor/admin-ui/ui.mjs";
import { get, put, del } from "../vendor/admin-ui/api.mjs";
import { useT, tError } from "../vendor/admin-ui/i18n.mjs";
import { OriginBadge, PermSelect, ScrollTable, FormNotice, ErrorNote } from "../components.mjs";
import { sortRules, validTopicPattern, PERMISSIONS } from "../lib/model.mjs";

export const meta = { id: "acl", titleKey: "view.acl" };

export default function View() {
  const tt = useT();
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
  const reloadAll = () => {
    rulesQ.reload();
    usersQ.reload();
  };
  // Returns true on success; failures are toasted with the localized code text.
  const save = async (user, topic, permission) => {
    try {
      await put("acl", { body: { user, topic, permission } });
      toast("ok", tt("acl.saved", { user, topic, permission }));
      reloadAll();
      return true;
    } catch (e) {
      toast("error", tError(e));
      return false;
    }
  };
  const add = async () => {
    if (!targets.includes(form.user)) return setFormError(tt("acl.err.user"));
    if (!validTopicPattern(form.topic)) return setFormError(tt("acl.err.topic"));
    if (!PERMISSIONS.includes(form.permission)) return setFormError(tt("acl.err.permission"));
    setFormError("");
    if (await save(form.user, form.topic, form.permission)) setForm({ ...form, topic: "" });
  };
  // Throws on API errors so the confirmation dialog shows them.
  const remove = async (r) => {
    await del("acl", { query: { user: r.user, topic: r.topic } });
    toast("ok", tt("acl.delete.done"));
    setPending(null);
    reloadAll();
  };
  return html`<div>
    <div class="card">
      <h2>${tt("acl.add.title")}</h2>
      <div class="toolbar">
        <${Field} id="acl-add-user" label=${tt("acl.add.user")}>
          <select
            id="acl-add-user"
            value=${form.user}
            onChange=${(e) => setForm({ ...form, user: e.target.value })}
          >
            <option value="">${tt("acl.add.user_none")}</option>
            ${targets.map((n) => html`<option key=${n} value=${n}>${n}</option>`)}
          </select>
        <//>
        <${Field} id="acl-add-topic" label=${tt("acl.add.topic")}>
          <input
            id="acl-add-topic"
            type="text"
            value=${form.topic}
            autocomplete="off"
            onInput=${(e) => setForm({ ...form, topic: e.target.value })}
          />
        <//>
        <div class="form-row">
          <label>${tt("acl.add.permission")}</label>
          <${PermSelect}
            value=${form.permission}
            label=${tt("acl.add.permission")}
            onChange=${(p) => setForm({ ...form, permission: p })}
          />
        </div>
        <button class="btn" type="button" onClick=${add}>${tt("acl.add.submit")}</button>
      </div>
      <div class="muted">
        ${tt("acl.hint_before")} <code>alerts-*</code>. ${tt("acl.hint_after")}
      </div>
      <${FormNotice}>${formError}<//>
    </div>
    <div class="toolbar">
      <${Field} id="acl-filter" label=${tt("acl.filter")}>
        <input
          id="acl-filter"
          type="text"
          value=${filter}
          autocomplete="off"
          onInput=${(e) => setFilter(e.target.value)}
        />
      <//>
    </div>
    <div class="card">
      <${ScrollTable} caption=${tt("acl.caption")}>
        <thead>
          <tr>
            <th scope="col">${tt("acl.col.user")}</th>
            <th scope="col">${tt("acl.col.topic")}</th>
            <th scope="col">${tt("acl.col.permission")}</th>
            <th scope="col">${tt("acl.col.origin")}</th>
            <th scope="col">${tt("acl.col.actions")}</th>
          </tr>
        </thead>
        <tbody>
          ${rules.map(
            (r) =>
              html`<tr key=${r.user + "|" + r.topic}>
                <td>${r.user}</td>
                <td class="mono">${r.topic}</td>
                <td>
                  <${PermSelect}
                    value=${r.permission}
                    label=${tt("acl.aria.permission", { user: r.user, topic: r.topic })}
                    onChange=${(p) => save(r.user, r.topic, p)}
                  />
                </td>
                <td><${OriginBadge} origin=${r.origin} /></td>
                <td class="actions">
                  <button
                    class="btn small danger"
                    type="button"
                    aria-label=${tt("acl.aria.delete", { user: r.user, topic: r.topic })}
                    onClick=${() => setPending(r)}
                  >
                    ${tt("btn.delete")}
                  </button>
                </td>
              </tr>`,
          )}
        </tbody>
      <//>
      ${rules.length === 0 && html`<div class="muted">${tt("acl.empty")}</div>`}
    </div>
    ${pending &&
    html`<${ConfirmDialog}
      title=${tt("acl.delete.title")}
      danger=${true}
      confirmLabel=${tt("btn.delete")}
      message=${tt("acl.delete.message", { user: pending.user, topic: pending.topic })}
      onCancel=${() => setPending(null)}
      onConfirm=${() => remove(pending)}
    />`}
  </div>`;
}
