// Users view: list, add, password, role (drop-rules warning), delete with typed name. Built on the admin-ui lib.
import {
  html,
  useState,
  useAsync,
  toast,
  Modal,
  ConfirmDialog,
  Badge,
  Loading,
  Field,
} from "../vendor/admin-ui/ui.mjs";
import { get, post, patch, del } from "../vendor/admin-ui/api.mjs";
import { useT, tp, tError } from "../vendor/admin-ui/i18n.mjs";
import {
  OriginBadge,
  ScrollTable,
  LinkButton,
  TimeStamp,
  ExpiryText,
  FormNotice,
  ErrorNote,
} from "../components.mjs";
import { validUsername, protectionKind } from "../lib/model.mjs";

export const meta = { id: "users", titleKey: "view.users" };

// Literal key tables: call sites index them so the i18n scanner can follow every key.
const ROLE_KEYS = { user: "users.role.user", admin: "users.role.admin", anonymous: "users.role.anonymous" };
const PROTECT_KEYS = {
  last_admin: "users.protect.last_admin",
  options_admin: "users.protect.options_admin",
  anonymous: "users.protect.anonymous",
  other: "users.protect.other",
};

// Unknown roles fall back to the raw role text (still a text node).
const roleText = (tt, role) => (Object.prototype.hasOwnProperty.call(ROLE_KEYS, role) ? tt(ROLE_KEYS[role]) : String(role));

function AddUser({ onClose, onDone }) {
  const tt = useT();
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("user");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState(null);
  const submit = async () => {
    setError(null);
    if (!validUsername(name)) return setNotice(tt("users.err.name"));
    if (!password) return setNotice(tt("users.err.password"));
    setNotice("");
    try {
      await post("users", { body: { name, password, role } });
      toast("ok", tt("users.add.done", { user: name }));
      onDone();
    } catch (e) {
      setError(e);
    }
  };
  return html`<${Modal} title=${tt("users.add.title")} onClose=${onClose}>
    <${Field} id="users-add-name" label=${tt("users.add.name")}>
      <input
        id="users-add-name"
        type="text"
        value=${name}
        autocomplete="off"
        onInput=${(e) => setName(e.target.value)}
      />
    <//>
    <${Field} id="users-add-password" label=${tt("users.add.password")}>
      <input
        id="users-add-password"
        type="password"
        value=${password}
        autocomplete="new-password"
        onInput=${(e) => setPassword(e.target.value)}
      />
    <//>
    <${Field} id="users-add-role" label=${tt("users.add.role")}>
      <select id="users-add-role" value=${role} onChange=${(e) => setRole(e.target.value)}>
        <option value="user">${tt("users.role.user")}</option>
        <option value="admin">${tt("users.role.admin")}</option>
      </select>
    <//>
    <${FormNotice}>${notice}<//>
    <${ErrorNote} error=${error} />
    <div class="actions">
      <button class="btn secondary" type="button" onClick=${onClose}>${tt("btn.cancel")}</button>
      <button class="btn" type="button" onClick=${submit}>${tt("users.add.create")}</button>
    </div>
  <//>`;
}

function Password({ user, onClose }) {
  const tt = useT();
  const [password, setPassword] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState(null);
  const submit = async () => {
    setError(null);
    if (!password) return setNotice(tt("users.err.password"));
    setNotice("");
    try {
      await patch(`users/${user.name}`, { body: { password } });
      toast("ok", tt("users.pw.done", { user: user.name }));
      onClose();
    } catch (e) {
      setError(e);
    }
  };
  return html`<${Modal} title=${tt("users.pw.title", { user: user.name })} onClose=${onClose}>
    <${Field} id="users-pw-new" label=${tt("users.pw.label")}>
      <input
        id="users-pw-new"
        type="password"
        value=${password}
        autocomplete="new-password"
        onInput=${(e) => setPassword(e.target.value)}
      />
    <//>
    <${FormNotice}>${notice}<//>
    <${ErrorNote} error=${error} />
    <div class="actions">
      <button class="btn secondary" type="button" onClick=${onClose}>${tt("btn.cancel")}</button>
      <button class="btn" type="button" onClick=${submit}>${tt("users.pw.change")}</button>
    </div>
  <//>`;
}

function Detail({ name }) {
  const tt = useT();
  const { data, error, loading } = useAsync(() => get(`users/${name}`), [name]);
  if (loading) return html`<${Loading} />`;
  if (error) return html`<${ErrorNote} error=${error} />`;
  const acl = data.acl || [];
  const tokens = data.tokens || [];
  return html`<div>
    <h3>${tt("users.detail.rules")}</h3>
    ${acl.length === 0 && html`<div class="muted">${tt("users.detail.none")}</div>`}
    ${acl.map(
      (r) =>
        html`<div key=${r.topic} class="mono">
          ${r.topic} <${Badge}>${r.permission}<//> <${OriginBadge} origin=${r.origin} />
        </div>`,
    )}
    <h3>${tt("users.detail.tokens")}</h3>
    ${tokens.length === 0 && html`<div class="muted">${tt("users.detail.none")}</div>`}
    ${tokens.map(
      (k) =>
        html`<div key=${k.id} class="mono">
          ${k.prefix}… ${k.label || ""} ${tt("users.detail.expires")}
          <${ExpiryText} ts=${Date.parse(k.expires_at || "") / 1000 || 0} />
          ${tt("users.detail.last_used")} <${TimeStamp} ts=${k.last_access} relative=${true} />
        </div>`,
    )}
  </div>`;
}

export default function View() {
  const tt = useT();
  const { data, error, loading, reload } = useAsync(() => get("users"));
  const [modal, setModal] = useState(null);
  const [open, setOpen] = useState(null);
  const done = () => {
    setModal(null);
    reload();
  };
  // Throws on API errors: the confirmation dialog shows them, quick actions toast them.
  const applyRole = async (u, role) => {
    const res = await patch(`users/${u.name}`, { body: { role } });
    const dropped = res && Number.isInteger(res.dropped_rules) ? res.dropped_rules : 0;
    const who = { user: u.name, role: roleText(tt, role) };
    toast("ok", dropped > 0 ? tp("users.role.changed_dropped", dropped, who) : tt("users.role.changed", who));
    done();
  };
  const quickRole = async (u, role) => {
    try {
      await applyRole(u, role);
    } catch (e) {
      toast("error", tError(e));
    }
  };
  const setRole = (u, role) => {
    if (role === "admin" && u.acl_count > 0) return setModal({ kind: "role", user: u, role });
    return quickRole(u, role);
  };
  if (loading && !data) return html`<${Loading} />`;
  if (error) return html`<${ErrorNote} error=${error} />`;
  const users = data.users || [];
  return html`<div>
    <div class="toolbar">
      <h2>${tt("view.users")}</h2>
      <span class="spacer"></span>
      <button class="btn" type="button" onClick=${() => setModal({ kind: "add" })}>${tt("users.btn.add")}</button>
    </div>
    <div class="card">
      <${ScrollTable} caption=${tt("users.caption")}>
        <thead>
          <tr>
            <th scope="col">${tt("users.col.name")}</th>
            <th scope="col">${tt("users.col.role")}</th>
            <th scope="col">${tt("users.col.tier")}</th>
            <th scope="col">${tt("users.col.origin")}</th>
            <th scope="col">${tt("users.col.protection")}</th>
            <th scope="col">${tt("users.col.rules")}</th>
            <th scope="col">${tt("users.col.tokens")}</th>
            <th scope="col">${tt("users.col.actions")}</th>
          </tr>
        </thead>
        <tbody>
          ${users.map((u) => {
            const isEveryone = u.name === "everyone" || u.role === "anonymous";
            const kind = protectionKind(u.protected_reason);
            const shown = open === u.name;
            return html`<tr key=${u.name}>
              <td>
                <${LinkButton}
                  ariaLabel=${shown ? tt("users.aria.hide", { user: u.name }) : tt("users.aria.show", { user: u.name })}
                  onClick=${() => setOpen(shown ? null : u.name)}
                  >${u.name}<//
                >
              </td>
              <td><${Badge} kind=${u.role === "admin" ? "warn" : "muted"}>${roleText(tt, u.role)}<//></td>
              <td>${u.tier || "-"}</td>
              <td><${OriginBadge} origin=${u.origin} /></td>
              <td>${u.protected ? html`<${Badge} kind="warn">${tt(PROTECT_KEYS[kind])}<//>` : ""}</td>
              <td>${u.acl_count}</td>
              <td>${u.token_count}</td>
              <td class="actions">
                ${!isEveryone &&
                html`<button
                    class="btn small secondary"
                    type="button"
                    aria-label=${tt("users.aria.password", { user: u.name })}
                    onClick=${() => setModal({ kind: "password", user: u })}
                  >
                    ${tt("users.btn.password")}
                  </button>
                  <button
                    class="btn small secondary"
                    type="button"
                    disabled=${u.protected}
                    aria-label=${u.role === "admin"
                      ? tt("users.aria.demote", { user: u.name })
                      : tt("users.aria.make_admin", { user: u.name })}
                    onClick=${() => setRole(u, u.role === "admin" ? "user" : "admin")}
                  >
                    ${u.role === "admin" ? tt("users.btn.demote") : tt("users.btn.make_admin")}
                  </button>
                  <button
                    class="btn small danger"
                    type="button"
                    disabled=${u.protected}
                    aria-label=${tt("users.aria.delete", { user: u.name })}
                    onClick=${() => setModal({ kind: "delete", user: u })}
                  >
                    ${tt("btn.delete")}
                  </button>`}
              </td>
            </tr>`;
          })}
          ${users.length === 0 &&
          html`<tr>
            <td colspan="8" class="muted">${tt("users.empty")}</td>
          </tr>`}
        </tbody>
      <//>
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
      title=${tt("users.role.confirm_title")}
      message=${tp("users.role.confirm_message", modal.user.acl_count, { user: modal.user.name })}
      confirmLabel=${tt("users.btn.make_admin")}
      onCancel=${() => setModal(null)}
      onConfirm=${() => applyRole(modal.user, modal.role)}
    />`}
    ${modal &&
    modal.kind === "delete" &&
    html`<${ConfirmDialog}
      title=${tt("users.delete.title", { user: modal.user.name })}
      danger=${true}
      message=${tt("users.delete.message")}
      expected=${modal.user.name}
      confirmLabel=${tt("btn.delete")}
      onCancel=${() => setModal(null)}
      onConfirm=${async () => {
        await del(`users/${modal.user.name}`, { body: { confirm: modal.user.name } });
        toast("ok", tt("users.delete.done", { user: modal.user.name }));
        done();
      }}
    />`}
  </div>`;
}
