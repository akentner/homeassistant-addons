// Users view: list, add, password, role (drop-rules warning), delete with typed name (D-12, D-17).
import {
  html,
  useState,
  useAsync,
  toast,
  Modal,
  ConfirmDialog,
  Badge,
  OriginBadge,
  ErrorNote,
  Loading,
} from "../lib/ui.mjs";
import { get, post, patch, del } from "../lib/api.mjs";
import { validUsername, protectionLabel, fmtUnix, fmtExpiry } from "../lib/model.mjs";

export const meta = { id: "users", title: "Users" };

const ROLE_WARNING = (u) =>
  `${u.name} has ${u.acl_count} explicit rule(s). Admins have full access, so these rules will be dropped ` +
  "(a backup is written first) and are restored if the user is demoted again.";
const msg = (e) => (e && e.message) || String(e);

function AddUser({ onClose, onDone }) {
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("user");
  const [error, setError] = useState("");
  const submit = async () => {
    if (!validUsername(name)) return setError("Invalid user name (letters, digits, _ - . + @, max 64).");
    if (!password) return setError("Password must not be empty.");
    try {
      await post("users", { body: { name, password, role } });
      toast("ok", `User ${name} created`);
      onDone();
    } catch (e) {
      setError(msg(e));
    }
  };
  return html`<${Modal} title="Add user" onClose=${onClose}>
    <div class="form-row">
      <label>Name</label><input type="text" value=${name} onInput=${(e) => setName(e.target.value)} />
    </div>
    <div class="form-row">
      <label>Password</label>
      <input
        type="password"
        value=${password}
        autocomplete="new-password"
        onInput=${(e) => setPassword(e.target.value)}
      />
    </div>
    <div class="form-row">
      <label>Role</label>
      <select value=${role} onChange=${(e) => setRole(e.target.value)}>
        <option value="user">user</option>
        <option value="admin">admin</option>
      </select>
    </div>
    ${error && html`<div class="notice">${error}</div>`}
    <div class="actions">
      <button class="btn secondary" type="button" onClick=${onClose}>Cancel</button>
      <button class="btn" type="button" onClick=${submit}>Create</button>
    </div>
  <//>`;
}

function Password({ user, onClose }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const submit = async () => {
    if (!password) return setError("Password must not be empty.");
    try {
      await patch(`users/${user.name}`, { body: { password } });
      toast("ok", `Password of ${user.name} changed`);
      onClose();
    } catch (e) {
      setError(msg(e));
    }
  };
  return html`<${Modal} title=${`Change password: ${user.name}`} onClose=${onClose}>
    <div class="form-row">
      <label>New password</label>
      <input
        type="password"
        value=${password}
        autocomplete="new-password"
        onInput=${(e) => setPassword(e.target.value)}
      />
    </div>
    ${error && html`<div class="notice">${error}</div>`}
    <div class="actions">
      <button class="btn secondary" type="button" onClick=${onClose}>Cancel</button>
      <button class="btn" type="button" onClick=${submit}>Change</button>
    </div>
  <//>`;
}

function Detail({ name }) {
  const { data, error, loading } = useAsync(() => get(`users/${name}`), [name]);
  if (loading) return html`<${Loading} />`;
  if (error) return html`<${ErrorNote} error=${error} />`;
  const acl = data.acl || [];
  const tokens = data.tokens || [];
  return html`<div>
    <div><strong>Rules</strong> ${acl.length === 0 && html`<span class="muted">none</span>`}</div>
    ${acl.map(
      (r) =>
        html`<div key=${r.topic} class="mono">
          ${r.topic} <${Badge}>${r.permission}<//> <${OriginBadge} origin=${r.origin} />
        </div>`,
    )}
    <div><strong>Tokens</strong> ${tokens.length === 0 && html`<span class="muted">none</span>`}</div>
    ${tokens.map(
      (t) =>
        html`<div key=${t.id} class="mono">
          ${t.prefix}… ${t.label || ""} expires ${fmtExpiry(Date.parse(t.expires_at || "") / 1000 || 0)} last used
          ${fmtUnix(t.last_access)}
        </div>`,
    )}
  </div>`;
}

export default function View() {
  const { data, error, loading, reload } = useAsync(() => get("users"));
  const [modal, setModal] = useState(null);
  const [open, setOpen] = useState(null);
  const done = () => {
    setModal(null);
    reload();
  };
  const setRole = async (u, role) => {
    if (role === "admin" && u.acl_count > 0) {
      setModal({ kind: "role", user: u, role });
      return;
    }
    await applyRole(u, role);
  };
  const applyRole = async (u, role) => {
    try {
      const res = await patch(`users/${u.name}`, { body: { role } });
      const dropped = (res && res.dropped_rules) || [];
      toast("ok", `${u.name} is now ${role}` + (dropped.length ? `, ${dropped.length} rule(s) dropped` : ""));
      done();
    } catch (e) {
      toast("error", msg(e));
    }
  };
  if (loading && !data) return html`<${Loading} />`;
  if (error) return html`<${ErrorNote} error=${error} />`;
  const users = data.users || [];
  return html`<div>
    <div class="toolbar">
      <h2>Users</h2>
      <span class="spacer"></span>
      <button class="btn" type="button" onClick=${() => setModal({ kind: "add" })}>Add user</button>
    </div>
    <div class="card">
      <table class="data">
        <thead>
          <tr>
            <th>Name</th>
            <th>Role</th>
            <th>Tier</th>
            <th>Origin</th>
            <th>Protection</th>
            <th>Rules</th>
            <th>Tokens</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${users.map((u) => {
            const isEveryone = u.name === "everyone" || u.role === "anonymous";
            return html`<tr key=${u.name}>
              <td>
                <a
                  href="#/users"
                  onClick=${(e) => {
                    e.preventDefault();
                    setOpen(open === u.name ? null : u.name);
                  }}
                  >${u.name}</a
                >
              </td>
              <td><${Badge} kind=${u.role === "admin" ? "warn" : "muted"}>${u.role}<//></td>
              <td>${u.tier || "-"}</td>
              <td><${OriginBadge} origin=${u.origin} /></td>
              <td>
                ${u.protected
                  ? html`<${Badge} kind="warn">${protectionLabel(u.protected_reason) || "protected"}<//>`
                  : ""}
              </td>
              <td>${u.acl_count}</td>
              <td>${u.token_count}</td>
              <td class="actions">
                ${!isEveryone &&
                html` <button
                    class="btn small secondary"
                    type="button"
                    onClick=${() => setModal({ kind: "password", user: u })}
                  >
                    Password
                  </button>
                  <button
                    class="btn small secondary"
                    type="button"
                    disabled=${u.protected}
                    onClick=${() => setRole(u, u.role === "admin" ? "user" : "admin")}
                  >
                    ${u.role === "admin" ? "Demote" : "Make admin"}
                  </button>
                  <button
                    class="btn small danger"
                    type="button"
                    disabled=${u.protected}
                    onClick=${() => setModal({ kind: "delete", user: u })}
                  >
                    Delete
                  </button>`}
              </td>
            </tr>`;
          })}
        </tbody>
      </table>
      ${open &&
      html`<div class="card">
        <h2>${open}</h2>
        <${Detail} name=${open} />
      </div>`}
    </div>
    ${modal && modal.kind === "add" && html`<${AddUser} onClose=${() => setModal(null)} onDone=${done} />`}
    ${modal && modal.kind === "password" && html`<${Password} user=${modal.user} onClose=${() => setModal(null)} />`}
    ${modal &&
    modal.kind === "role" &&
    html`<${ConfirmDialog}
      title="Make admin"
      message=${ROLE_WARNING(modal.user)}
      confirmLabel="Make admin"
      onCancel=${() => setModal(null)}
      onConfirm=${() => applyRole(modal.user, modal.role)}
    />`}
    ${modal &&
    modal.kind === "delete" &&
    html`<${ConfirmDialog}
      title=${`Delete ${modal.user.name}`}
      danger=${true}
      message="This removes the user together with its rules and tokens."
      expected=${modal.user.name}
      confirmLabel="Delete"
      onCancel=${() => setModal(null)}
      onConfirm=${async () => {
        try {
          await del(`users/${modal.user.name}`, { body: { confirm: modal.user.name } });
          toast("ok", `User ${modal.user.name} deleted`);
          done();
        } catch (e) {
          toast("error", msg(e));
        }
      }}
    />`}
  </div>`;
}
