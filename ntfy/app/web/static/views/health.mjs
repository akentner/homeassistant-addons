// Health view: status, sizes, counts and a guarded test publish (D-17).
import { html, useState, useAsync, usePoll, toast, Badge, ConfirmDialog, ErrorNote, Loading } from "../lib/ui.mjs";
import { get, post } from "../lib/api.mjs";
import { fmtBytes } from "../lib/model.mjs";

export const meta = { id: "health", title: "Health" };

const msg = (e) => (e && e.message) || String(e);

function Publish() {
  const aclQ = useAsync(() => get("acl"));
  const [topic, setTopic] = useState("");
  const [message, setMessage] = useState("Test message from the ntfy add-on");
  const [confirm, setConfirm] = useState(false);
  const [result, setResult] = useState("");
  const concrete = [...new Set(((aclQ.data && aclQ.data.rules) || []).map((r) => r.topic))].filter(
    (t) => !t.includes("*"),
  );
  const send = async () => {
    try {
      const res = await post("health/publish", { body: { topic, message } });
      setResult(`status ${res.status}, id ${res.id}`);
      toast("ok", "Test message published");
    } catch (e) {
      setResult(`error: ${msg(e)}`);
      toast("error", msg(e));
    }
    setConfirm(false);
  };
  return html`<div class="card">
    <h2>Test publish</h2>
    <div class="toolbar">
      <input
        type="text"
        list="health-topics"
        placeholder="topic"
        value=${topic}
        onInput=${(e) => setTopic(e.target.value)}
      />
      <datalist id="health-topics">${concrete.map((t) => html`<option key=${t} value=${t}></option>`)}</datalist>
      <input type="text" placeholder="message" value=${message} onInput=${(e) => setMessage(e.target.value)} />
      <button class="btn" type="button" disabled=${!topic} onClick=${() => setConfirm(true)}>Publish</button>
    </div>
    ${result && html`<div class="mono">${result}</div>`}
    ${confirm &&
    html`<${ConfirmDialog}
      title="Publish test message"
      confirmLabel="Publish"
      message=${`A real message is sent to all subscribers of the topic ${topic}.`}
      onCancel=${() => setConfirm(false)}
      onConfirm=${send}
    />`}
  </div>`;
}

export default function View() {
  const { data, error, loading, reload } = useAsync(() => get("health"));
  usePoll(reload, 10000);
  if (loading && !data) return html`<${Loading} />`;
  if (error) return html`<${ErrorNote} error=${error} />`;
  const db = data.db || {};
  const counts = data.counts;
  const kind = data.status === "ok" ? "ok" : data.status;
  return html`<div>
    <div class="card">
      <div class="toolbar">
        <h2>Status</h2>
        <${Badge} kind=${kind}>${data.status}<//>
        <span class="spacer"></span>
        <button class="btn small secondary" type="button" onClick=${reload}>Refresh</button>
      </div>
      <div>add-on ${data.addon_version}</div>
      <div>
        ntfy
        ${data.ntfy && data.ntfy.healthy ? "healthy" : "not healthy"}${data.ntfy && data.ntfy.role
          ? `, role ${data.ntfy.role}`
          : ""}
      </div>
      <div>auth.db schema ${db.schema_version} (${db.supported ? "supported" : "unsupported"})</div>
      ${db.error && html`<div class="notice">${db.error}</div>`}
      <div>auth.db size: ${fmtBytes(db.size_bytes)}</div>
      <div>message cache size: ${fmtBytes(db.cache_size_bytes)}</div>
      ${counts && html`<div>${counts.users} users, ${counts.acl_rules} rules, ${counts.tokens} tokens</div>`}
    </div>
    <${Publish} />
  </div>`;
}
