// Tools: effective-rights lookup and random topic generator with default ACL. Texts come from i18n.
import { html, useState, useAsync, Badge, CopyField, Field, Loading } from "../vendor/admin-ui/ui.mjs";
import { get, put } from "../vendor/admin-ui/api.mjs";
import { useT, tError } from "../vendor/admin-ui/i18n.mjs";
import { ErrorNote, FormNotice, PermSelect } from "../components.mjs";
import { validTopic, effectiveExplain } from "../lib/model.mjs";

export const meta = { id: "tools", titleKey: "view.tools" };

// effectiveExplain returns the kind; the texts live in the string tables (tools.effective.*).
const EXPLAIN_KEYS = {
  admin: "tools.effective.admin",
  user_rule: "tools.effective.user_rule",
  everyone_rule: "tools.effective.everyone_rule",
  default: "tools.effective.default",
};

function Effective({ users, params }) {
  const tt = useT();
  const [user, setUser] = useState((params && params.user) || "everyone");
  const [topic, setTopic] = useState((params && params.topic) || "");
  const [result, setResult] = useState(null);
  const [notice, setNotice] = useState("");
  const [apiError, setApiError] = useState(null);
  const lookup = async () => {
    setResult(null);
    setApiError(null);
    if (!validTopic(topic)) {
      setNotice(tt("tools.topic_invalid"));
      return;
    }
    setNotice("");
    try {
      setResult(await get("effective", { query: { user, topic } }));
    } catch (err) {
      setApiError(err);
    }
  };
  const deciding = result && result.source && result.source.rule;
  const explain = result ? effectiveExplain(result) : null;
  const verdict = (allowed) =>
    html`<${Badge} kind=${allowed ? "ok" : "error"}>${allowed ? tt("tools.allowed") : tt("tools.denied")}<//>`;
  return html`<div class="card">
    <h2>${tt("tools.effective_title")}</h2>
    <div class="toolbar">
      <${Field} id="tools-user" label=${tt("tools.user")}>
        <select id="tools-user" value=${user} onChange=${(ev) => setUser(ev.target.value)}>
          ${users.map((name) => html`<option key=${name} value=${name}>${name}</option>`)}
        </select>
      <//>
      <${Field} id="tools-topic" label=${tt("tools.topic")}>
        <input id="tools-topic" type="text" value=${topic} onInput=${(ev) => setTopic(ev.target.value)} />
      <//>
      <button class="btn" type="button" onClick=${lookup}>${tt("tools.check")}</button>
    </div>
    <${FormNotice}>${notice}<//>
    <${ErrorNote} error=${apiError} />
    ${result &&
    html`<div>
      <div>${tt("tools.read")} ${verdict(result.read)} ${tt("tools.write")} ${verdict(result.write)}</div>
      <div>${tt(EXPLAIN_KEYS[explain.kind], explain.params)}</div>
      ${(result.candidates || []).map(
        (rule, i) =>
          html`<div key=${i} class="mono">
            ${i + 1}. ${rule.user} ${rule.topic} ${rule.permission}
            ${deciding &&
            deciding.user === rule.user &&
            deciding.topic === rule.topic &&
            html`<${Badge} kind="ok">${tt("tools.decides")}<//>`}
          </div>`,
      )}
    </div>`}
  </div>`;
}

function Generator({ known }) {
  const tt = useT();
  const [state, setState] = useState(null);
  const [apiError, setApiError] = useState(null);
  const [report, setReport] = useState(null);
  const generate = async () => {
    setReport(null);
    try {
      const res = await get("topics/suggest");
      setState({ topic: res.topic, acl: (res.acl || []).map((rule) => ({ ...rule })) });
      setApiError(null);
    } catch (err) {
      setApiError(err);
    }
  };
  const setEntry = (i, patch) =>
    setState({ ...state, acl: state.acl.map((rule, j) => (j === i ? { ...rule, ...patch } : rule)) });
  const apply = async () => {
    const lines = [];
    const skipped = [];
    for (const rule of state.acl) {
      if (!known.includes(rule.user)) {
        skipped.push(rule.user);
        continue;
      }
      try {
        await put("acl", { body: { user: rule.user, topic: state.topic, permission: rule.permission } });
        lines.push({ user: rule.user, permission: rule.permission, error: null });
      } catch (err) {
        lines.push({ user: rule.user, permission: rule.permission, error: err });
      }
    }
    setReport({ lines, skipped });
  };
  return html`<div class="card">
    <h2>${tt("tools.generator_title")}</h2>
    <div class="toolbar"><button class="btn" type="button" onClick=${generate}>${tt("tools.generate")}</button></div>
    <${ErrorNote} error=${apiError} />
    ${state &&
    html`<div>
      <${CopyField} value=${state.topic} label=${tt("tools.generated_topic")} />
      ${state.acl.map(
        (rule, i) =>
          html`<div key=${i} class="toolbar">
            <input
              type="text"
              aria-label=${tt("tools.rule_user", { n: i + 1 })}
              value=${rule.user}
              onInput=${(ev) => setEntry(i, { user: ev.target.value })}
            />
            <${PermSelect}
              value=${rule.permission}
              label=${tt("tools.rule_perm", { n: i + 1 })}
              onChange=${(permission) => setEntry(i, { permission })}
            />
          </div>`,
      )}
      <button class="btn" type="button" onClick=${apply}>${tt("tools.apply")}</button>
    </div>`}
    ${report &&
    html`<div>
      ${report.lines.map(
        (line, i) =>
          html`<div key=${i}>
            ${line.error
              ? tt("tools.line_error", { user: line.user, error: tError(line.error) })
              : tt("tools.line_ok", { user: line.user, permission: line.permission })}
          </div>`,
      )}
      ${report.skipped.length > 0 &&
      html`<div class="notice info">${tt("tools.skipped", { users: report.skipped.join(", ") })}</div>`}
    </div>`}
  </div>`;
}

export default function View({ params }) {
  const { data, error, loading, reload } = useAsync(() => get("users"));
  if (loading && !data) return html`<${Loading} />`;
  if (error) return html`<${ErrorNote} error=${error} onRetry=${reload} />`;
  const names = (data.users || []).map((u) => u.name);
  const users = names.includes("everyone") ? names : ["everyone", ...names];
  return html`<div>
    <${Effective} users=${users} params=${params} />
    <${Generator} known=${users} />
  </div>`;
}
