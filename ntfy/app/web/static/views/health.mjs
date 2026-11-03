// Health view: status, sizes, counts and a guarded test publish. Texts come from i18n, values stay text nodes.
import { html, useState, useAsync, usePoll, toast, Badge, ConfirmDialog, Loading, Field } from "../vendor/admin-ui/ui.mjs";
import { get, post } from "../vendor/admin-ui/api.mjs";
import { useT, useLang, tp } from "../vendor/admin-ui/i18n.mjs";
import { formatBytes, formatNumber } from "../vendor/admin-ui/format.mjs";
import { ErrorNote } from "../components.mjs";

export const meta = { id: "health", titleKey: "view.health" };

const STATUS_KEYS = { ok: "state.ok", degraded: "state.degraded", error: "state.error" };
const has = (table, key) => Object.prototype.hasOwnProperty.call(table, key);

// Reason text of a publish that ntfy did not accept (ok false): 429 is the rate limit, 0 means ntfy was unreachable.
function failReason(tt, status) {
  if (status === 429) return tt("health.fail_rate_limit");
  if (status === 0) return tt("health.fail_unreachable");
  return tt("health.fail_status");
}

function Publish() {
  const tt = useT();
  const aclQ = useAsync(() => get("acl"));
  const [topic, setTopic] = useState("");
  const [message, setMessage] = useState(() => tt("health.default_message"));
  const [confirm, setConfirm] = useState(false);
  const [result, setResult] = useState(null);
  const concrete = [...new Set(((aclQ.data && aclQ.data.rules) || []).map((r) => r.topic))].filter(
    (name) => !name.includes("*"),
  );
  // An API error is thrown on purpose: the confirm dialog stays open and shows the localized code text.
  const send = async () => {
    const res = await post("health/publish", { body: { topic, message } });
    setConfirm(false);
    if (res && res.ok) {
      setResult({ ok: true, status: res.status, id: res.id });
      toast("ok", tt("health.publish_ok"));
    } else {
      const status = res && typeof res.status === "number" ? res.status : 0;
      setResult({ ok: false, status });
      toast("error", failReason(tt, status));
    }
  };
  return html`<div class="card">
    <h2>${tt("health.publish_title")}</h2>
    <div class="toolbar">
      <${Field} id="health-topic" label=${tt("health.topic")}>
        <input
          id="health-topic"
          type="text"
          list="health-topics"
          value=${topic}
          onInput=${(ev) => setTopic(ev.target.value)}
        />
      <//>
      <datalist id="health-topics">${concrete.map((name) => html`<option key=${name} value=${name}></option>`)}</datalist>
      <${Field} id="health-message" label=${tt("health.message")}>
        <input id="health-message" type="text" value=${message} onInput=${(ev) => setMessage(ev.target.value)} />
      <//>
      <button class="btn" type="button" disabled=${!topic} onClick=${() => setConfirm(true)}>
        ${tt("health.publish")}
      </button>
    </div>
    ${result &&
    html`<div class="mono" role="status">
      ${result.ok
        ? tt("health.result_ok", { status: result.status, id: result.id || "-" })
        : tt("health.result_failed", { reason: failReason(tt, result.status), status: result.status })}
    </div>`}
    ${confirm &&
    html`<${ConfirmDialog}
      title=${tt("health.confirm_title")}
      confirmLabel=${tt("health.publish")}
      message=${tt("health.confirm_message", { topic })}
      onCancel=${() => setConfirm(false)}
      onConfirm=${send}
    />`}
  </div>`;
}

export default function View() {
  const tt = useT();
  const lang = useLang();
  const { data, error, loading, reload } = useAsync(() => get("health"));
  usePoll(reload, 10000);
  if (loading && !data) return html`<${Loading} />`;
  if (error) return html`<${ErrorNote} error=${error} onRetry=${reload} />`;
  const db = data.db || {};
  const ntfy = data.ntfy || {};
  const counts = data.counts;
  const statusKnown = has(STATUS_KEYS, data.status);
  const num = (n) => formatNumber(n, lang);
  return html`<div>
    <div class="card">
      <div class="toolbar">
        <h2>${tt("health.status_title")}</h2>
        <${Badge} kind=${statusKnown ? data.status : "muted"}>
          ${statusKnown ? tt(STATUS_KEYS[data.status]) : String(data.status)}
        <//>
        <span class="spacer"></span>
        <button class="btn small secondary" type="button" onClick=${reload}>${tt("health.refresh")}</button>
      </div>
      <div>${tt("health.addon", { version: data.addon_version })}</div>
      <div>
        ${ntfy.healthy ? tt("health.ntfy_healthy") : tt("health.ntfy_unhealthy")}${ntfy.role
          ? `, ${tt("health.ntfy_role", { role: ntfy.role })}`
          : ""}
      </div>
      <div>
        ${db.supported
          ? tt("health.schema_supported", { version: db.schema_version })
          : tt("health.schema_unsupported", { version: db.schema_version })}
      </div>
      ${db.error && html`<div class="muted">${db.error}</div>`}
      <div>${tt("health.db_size", { size: formatBytes(db.size_bytes, lang) })}</div>
      <div>${tt("health.cache_size", { size: formatBytes(db.cache_size_bytes, lang) })}</div>
      ${counts &&
      html`<div>
        ${tt("health.counts", {
          users: tp("health.users", counts.users, { n: num(counts.users) }),
          rules: tp("health.rules", counts.acl_rules, { n: num(counts.acl_rules) }),
          tokens: tp("health.tokens", counts.tokens, { n: num(counts.tokens) }),
        })}
      </div>`}
    </div>
    <${Publish} />
  </div>`;
}
