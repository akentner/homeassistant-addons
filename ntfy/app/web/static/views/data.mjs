// Export, backups and the guarded reset actions (D-09, D-11, D-14, D-17).
import { html, useState, useAsync, toast, ConfirmDialog, ErrorNote, Loading } from "../lib/ui.mjs";
import { get, post, buildUrl } from "../lib/api.mjs";
import { RESET_PHRASES, fmtBytes } from "../lib/model.mjs";

export const meta = { id: "data", title: "Export & backups" };

const msg = (e) => (e && e.message) || String(e);

const RESETS = [
  {
    kind: "acls",
    title: "Reset ACLs",
    text: "Removes all explicit access rules. Users and tokens stay.",
  },
  {
    kind: "cache",
    title: "Clear message cache",
    text: "Deletes cached messages and attachments. Users and rules stay.",
  },
  {
    kind: "everything",
    title: "Reset everything incl. users",
    text: "Removes all users, rules and tokens. The admin from the add-on options is recreated on the next start.",
  },
];

function Export() {
  const [format, setFormat] = useState("yaml");
  const [hashes, setHashes] = useState(false);
  const href = buildUrl("export", { format, include_hashes: hashes ? 1 : 0 });
  return html`<div class="card">
    <h2>Export</h2>
    <div class="toolbar">
      <select value=${format} onChange=${(e) => setFormat(e.target.value)}>
        <option value="yaml">YAML</option>
        <option value="json">JSON</option>
      </select>
      <label>
        <input type="checkbox" checked=${hashes} onChange=${(e) => setHashes(e.target.checked)} />
        include password hashes
      </label>
      <a class="btn" href=${href} download>Download export</a>
    </div>
    ${hashes && html`<div class="notice">Password hashes are secrets. Store the file like a password.</div>`}
    <div class="muted">Token values are never exported.</div>
  </div>`;
}

function Backups() {
  const { data, error, loading, reload } = useAsync(() => get("backups"));
  const create = async () => {
    try {
      const res = await post("backups", { body: {} });
      toast("ok", `Backup ${res.backup.name} created`);
      reload();
    } catch (e) {
      toast("error", msg(e));
    }
  };
  const list = (data && data.backups) || [];
  return html`<div class="card">
    <div class="toolbar">
      <h2>Backups</h2>
      <span class="spacer"></span>
      <button class="btn small" type="button" onClick=${create}>Create backup now</button>
    </div>
    ${loading && !data && html`<${Loading} />`} ${error && html`<${ErrorNote} error=${error} />`}
    <table class="data">
      <thead>
        <tr>
          <th>Name</th>
          <th>Created</th>
          <th>Size</th>
          <th>Reason</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${list.map(
          (b) =>
            html`<tr key=${b.name}>
              <td class="mono">${b.name}</td>
              <td>${b.created}</td>
              <td>${fmtBytes(b.size_bytes)}</td>
              <td>${b.reason}</td>
              <td class="actions">
                <a class="btn small secondary" href=${buildUrl(`backups/${b.name}`)} download>Download</a>
              </td>
            </tr>`,
        )}
      </tbody>
    </table>
    ${data && list.length === 0 && html`<div class="muted">No backups yet.</div>`}
  </div>`;
}

function Danger() {
  const [pending, setPending] = useState(null);
  const run = async () => {
    try {
      const res = await post(`reset/${pending.kind}`, { body: { confirm: RESET_PHRASES[pending.kind] } });
      const extra = [];
      if (res.messages_deleted !== undefined) extra.push(`${res.messages_deleted} messages`);
      if (res.attachments_deleted !== undefined) extra.push(`${res.attachments_deleted} attachments`);
      toast("ok", `${pending.title} done${extra.length ? `: ${extra.join(", ")}` : ""}`);
    } catch (e) {
      toast("error", msg(e));
    }
    setPending(null);
  };
  return html`<div class="card danger-zone">
    <h2>Danger zone</h2>
    <div class="muted">Each action writes an auth.db backup first.</div>
    ${RESETS.map(
      (r) =>
        html`<div key=${r.kind} class="danger-row">
          <div>
            <strong>${r.title}</strong>
            <div class="muted">${r.text}</div>
          </div>
          <button class="btn danger" type="button" onClick=${() => setPending(r)}>${r.title}</button>
        </div>`,
    )}
    ${pending &&
    html`<${ConfirmDialog}
      title=${pending.title}
      danger=${true}
      message=${pending.text}
      expected=${RESET_PHRASES[pending.kind]}
      confirmLabel="Execute"
      onCancel=${() => setPending(null)}
      onConfirm=${run}
    />`}
  </div>`;
}

export default function View() {
  return html`<div>
    <${Export} />
    <${Backups} />
    <${Danger} />
  </div>`;
}
