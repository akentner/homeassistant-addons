// Token management: hidden by default, reveal per row on demand, create and revoke (D-13).
import {
  html,
  useState,
  useAsync,
  toast,
  Modal,
  ConfirmDialog,
  Badge,
  OriginBadge,
  CopyField,
  ErrorNote,
  Loading,
} from "../lib/ui.mjs";
import { get, post, del } from "../lib/api.mjs";
import { validDuration, validLabel, fmtExpiry, expiryState, relTime } from "../lib/model.mjs";

export const meta = { id: "tokens", title: "Tokens" };

const msg = (e) => (e && e.message) || String(e);
const PRESETS = [
  ["never", "never"],
  ["1h", "1 hour"],
  ["1d", "1 day"],
  ["7d", "7 days"],
  ["30d", "30 days"],
  ["90d", "90 days"],
  ["custom", "custom…"],
];

function CreateToken({ users, initial, onClose, onDone }) {
  const [user, setUser] = useState(initial || "");
  const [label, setLabel] = useState("");
  const [preset, setPreset] = useState("never");
  const [custom, setCustom] = useState("");
  const [error, setError] = useState("");
  const [created, setCreated] = useState(null);
  const submit = async () => {
    const expires = preset === "custom" ? custom : preset === "never" ? "" : preset;
    if (!user) return setError("Choose a user.");
    if (!validLabel(label)) return setError("Label too long or contains control characters.");
    if (expires && !validDuration(expires)) return setError("Duration must look like 30m, 12h or 7d.");
    try {
      const body = { user, label };
      if (expires) body.expires = expires;
      const res = await post("tokens", { body });
      setCreated(res.token);
    } catch (e) {
      setError(msg(e));
    }
  };
  if (created) {
    return html`<${Modal} title="Token created" onClose=${onDone}>
      <p>Copy the token now. It can be revealed again later from the token list.</p>
      <${CopyField} value=${created.value} />
      <div class="actions"><button class="btn" type="button" onClick=${onDone}>Done</button></div>
    <//>`;
  }
  return html`<${Modal} title="Create token" onClose=${onClose}>
    <div class="form-row">
      <label>User</label>
      <select value=${user} onChange=${(e) => setUser(e.target.value)}>
        <option value="">choose…</option>
        ${users.map((n) => html`<option key=${n} value=${n}>${n}</option>`)}
      </select>
    </div>
    <div class="form-row">
      <label>Label</label>
      <input type="text" value=${label} onInput=${(e) => setLabel(e.target.value)} />
    </div>
    <div class="form-row">
      <label>Expires</label>
      <select value=${preset} onChange=${(e) => setPreset(e.target.value)}>
        ${PRESETS.map(([v, t]) => html`<option key=${v} value=${v}>${t}</option>`)}
      </select>
      ${preset === "custom" &&
      html`<input type="text" placeholder="e.g. 12h" value=${custom} onInput=${(e) => setCustom(e.target.value)} />`}
    </div>
    ${error && html`<div class="notice">${error}</div>`}
    <div class="actions">
      <button class="btn secondary" type="button" onClick=${onClose}>Cancel</button>
      <button class="btn" type="button" onClick=${submit}>Create</button>
    </div>
  <//>`;
}

function Row({ t, onRevoke }) {
  const [value, setValue] = useState(null);
  const reveal = async () => {
    try {
      const res = await post("tokens/reveal", { body: { user: t.user, id: t.id } });
      setValue(res.value);
    } catch (e) {
      toast("error", msg(e));
    }
  };
  const expiresTs = t.expires_at ? Math.floor(Date.parse(t.expires_at) / 1000) : 0;
  const state = expiryState(expiresTs);
  return html`<tr>
    <td>${t.user}</td>
    <td class="mono">${t.prefix}…</td>
    <td>${t.label || ""}</td>
    <td>
      ${fmtExpiry(expiresTs)}
      <${Badge} kind=${state === "expired" ? "error" : state === "active" ? "ok" : "muted"}>${state}<//>
    </td>
    <td title="ntfy updates this value lazily, so it is approximate">${relTime(t.last_access)}</td>
    <td><${OriginBadge} origin=${t.origin} /></td>
    <td class="actions">
      ${value === null
        ? html`<button class="btn small secondary" type="button" onClick=${reveal}>Reveal</button>`
        : html`<${CopyField} value=${value} />
            <button class="btn small secondary" type="button" onClick=${() => setValue(null)}>Hide</button>`}
      <button class="btn small danger" type="button" onClick=${() => onRevoke(t)}>Revoke</button>
    </td>
  </tr>`;
}

export default function View({ params }) {
  const [filter, setFilter] = useState((params && params.user) || "");
  const usersQ = useAsync(() => get("users"));
  const tokensQ = useAsync(() => get("tokens", { query: { user: filter || undefined } }), [filter]);
  const [modal, setModal] = useState(null);
  const [revoke, setRevoke] = useState(null);
  if (usersQ.loading && !usersQ.data) return html`<${Loading} />`;
  if (usersQ.error) return html`<${ErrorNote} error=${usersQ.error} />`;
  const names = (usersQ.data.users || []).filter((u) => u.name !== "everyone").map((u) => u.name);
  const doRevoke = async () => {
    try {
      await del("tokens", { query: { user: revoke.user, id: revoke.id } });
      toast("ok", "Token revoked");
      setRevoke(null);
      tokensQ.reload();
      usersQ.reload();
    } catch (e) {
      toast("error", msg(e));
    }
  };
  const tokens = (tokensQ.data && tokensQ.data.tokens) || [];
  return html`<div>
    <div class="toolbar">
      <select value=${filter} onChange=${(e) => setFilter(e.target.value)}>
        <option value="">all users</option>
        ${names.map((n) => html`<option key=${n} value=${n}>${n}</option>`)}
      </select>
      <span class="spacer"></span>
      <button class="btn" type="button" onClick=${() => setModal("create")}>Create token</button>
    </div>
    ${tokensQ.error && html`<${ErrorNote} error=${tokensQ.error} />`}
    <div class="card">
      <table class="data">
        <thead>
          <tr>
            <th>User</th>
            <th>Token</th>
            <th>Label</th>
            <th>Expires</th>
            <th>Last used (approx.)</th>
            <th>Origin</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${tokens.map((t) => html`<${Row} key=${t.user + t.id} t=${t} onRevoke=${setRevoke} />`)}
        </tbody>
      </table>
      ${!tokensQ.loading && tokens.length === 0 && html`<div class="muted">No tokens.</div>`}
    </div>
    ${modal === "create" &&
    html`<${CreateToken}
      users=${names}
      initial=${filter}
      onClose=${() => setModal(null)}
      onDone=${() => {
        setModal(null);
        tokensQ.reload();
        usersQ.reload();
      }}
    />`}
    ${revoke &&
    html`<${ConfirmDialog}
      title="Revoke token"
      danger=${true}
      confirmLabel="Revoke"
      message=${`Revoke the token ${revoke.prefix}… of ${revoke.user}? Clients using it lose access.`}
      onCancel=${() => setRevoke(null)}
      onConfirm=${doRevoke}
    />`}
  </div>`;
}
