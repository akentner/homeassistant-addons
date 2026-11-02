// Tools: effective-rights lookup and random topic generator with default ACL (D-17).
import { html, useState, useAsync, Badge, CopyField, PermSelect, ErrorNote, Loading } from "../lib/ui.mjs";
import { get, put } from "../lib/api.mjs";
import { validTopic, describeEffective } from "../lib/model.mjs";

export const meta = { id: "tools", title: "Tools" };

const msg = (e) => (e && e.message) || String(e);

function Effective({ users, params }) {
  const [user, setUser] = useState((params && params.user) || "everyone");
  const [topic, setTopic] = useState((params && params.topic) || "");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const lookup = async () => {
    setResult(null);
    if (!validTopic(topic)) return setError("Enter a concrete topic name (no wildcard).");
    setError("");
    try {
      setResult(await get("effective", { query: { user, topic } }));
    } catch (e) {
      setError(msg(e));
    }
  };
  const deciding = result && result.source && result.source.rule;
  return html`<div class="card">
    <h2>Effective rights</h2>
    <div class="toolbar">
      <select value=${user} onChange=${(e) => setUser(e.target.value)}>
        ${users.map((n) => html`<option key=${n} value=${n}>${n}</option>`)}
      </select>
      <input type="text" placeholder="topic" value=${topic} onInput=${(e) => setTopic(e.target.value)} />
      <button class="btn" type="button" onClick=${lookup}>Check</button>
    </div>
    ${error && html`<div class="notice">${error}</div>`}
    ${result &&
    html`<div>
      <div>
        read <${Badge} kind=${result.read ? "ok" : "error"}>${result.read ? "allowed" : "denied"}<//> write
        <${Badge} kind=${result.write ? "ok" : "error"}>${result.write ? "allowed" : "denied"}<//>
      </div>
      <div>${describeEffective(result)}</div>
      ${(result.candidates || []).map(
        (r, i) =>
          html`<div key=${i} class="mono">
            ${i + 1}. ${r.user} ${r.topic} ${r.permission}
            ${deciding &&
            deciding.user === r.user &&
            deciding.topic === r.topic &&
            html`<${Badge} kind="ok">decides<//>`}
          </div>`,
      )}
    </div>`}
  </div>`;
}

function Generator({ known }) {
  const [state, setState] = useState(null);
  const [error, setError] = useState("");
  const [report, setReport] = useState(null);
  const generate = async () => {
    setReport(null);
    try {
      const res = await get("topics/suggest");
      setState({ topic: res.topic, acl: (res.acl || []).map((a) => ({ ...a })) });
      setError("");
    } catch (e) {
      setError(msg(e));
    }
  };
  const setEntry = (i, patch) =>
    setState({ ...state, acl: state.acl.map((a, j) => (j === i ? { ...a, ...patch } : a)) });
  const apply = async () => {
    const lines = [];
    const skipped = [];
    for (const a of state.acl) {
      if (!known.includes(a.user)) {
        skipped.push(a.user);
        continue;
      }
      try {
        await put("acl", { body: { user: a.user, topic: state.topic, permission: a.permission } });
        lines.push(`${a.user}: ${a.permission} ok`);
      } catch (e) {
        lines.push(`${a.user}: error ${msg(e)}`);
      }
    }
    setReport({ lines, skipped });
  };
  return html`<div class="card">
    <h2>Topic generator</h2>
    <div class="toolbar"><button class="btn" type="button" onClick=${generate}>Generate</button></div>
    ${error && html`<div class="notice">${error}</div>`}
    ${state &&
    html`<div>
      <${CopyField} value=${state.topic} />
      ${state.acl.map(
        (a, i) =>
          html`<div key=${i} class="toolbar">
            <input type="text" value=${a.user} onInput=${(e) => setEntry(i, { user: e.target.value })} />
            <${PermSelect} value=${a.permission} onChange=${(p) => setEntry(i, { permission: p })} />
          </div>`,
      )}
      <button class="btn" type="button" onClick=${apply}>Apply</button>
    </div>`}
    ${report &&
    html`<div>
      ${report.lines.map((l, i) => html`<div key=${i}>${l}</div>`)}
      ${report.skipped.length > 0 &&
      html`<div class="notice info">Skipped unknown users: ${report.skipped.join(", ")}</div>`}
    </div>`}
  </div>`;
}

export default function View({ params }) {
  const { data, error, loading } = useAsync(() => get("users"));
  if (loading && !data) return html`<${Loading} />`;
  if (error) return html`<${ErrorNote} error=${error} />`;
  const names = (data.users || []).map((u) => u.name);
  const users = names.includes("everyone") ? names : ["everyone", ...names];
  return html`<div>
    <${Effective} users=${users} params=${params} />
    <${Generator} known=${users} />
  </div>`;
}
