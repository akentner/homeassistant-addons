// Tools: status table, test message, effective rights, topic generator, export, backups and the danger zone, in that
// order. Texts come from i18n, values stay text nodes; download links are built with apiHref.
import {
  html, useState, useAsync, usePoll, toast, Badge, ConfirmDialog, CopyField, Field, Loading,
} from "../vendor/admin-ui/ui.mjs";
import { get, post, put } from "../vendor/admin-ui/api.mjs";
import { apiHref } from "../vendor/admin-ui/ingress.mjs";
import { useT, useLang, tp, tError } from "../vendor/admin-ui/i18n.mjs";
import { formatBytes, formatDateTime, formatNumber } from "../vendor/admin-ui/format.mjs";
import { ErrorNote, FormNotice, PermSelect, ScrollTable } from "../components.mjs";
import { validTopic, effectiveExplain, RESET_PHRASES } from "../lib/model.mjs";

export const meta = { id: "tools", titleKey: "view.tools" };

const STATUS_KEYS = { ok: "state.ok", degraded: "state.degraded", error: "state.error" };
const has = (table, key) => Object.prototype.hasOwnProperty.call(table, key);

// Reason text of a publish that ntfy did not accept (ok false): 429 is the rate limit, 0 means ntfy was unreachable.
function failReason(tt, status) {
  if (status === 429) return tt("health.fail_rate_limit");
  if (status === 0) return tt("health.fail_unreachable");
  return tt("health.fail_status");
}

function Status() {
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
  return html`<div class="card">
    <div class="toolbar">
      <h2>${tt("health.status_title")}</h2>
      <span class="spacer"></span>
      <button class="btn small secondary" type="button" onClick=${reload}>${tt("health.refresh")}</button>
    </div>
    <${ScrollTable} caption=${tt("health.status_title")}>
      <tbody>
        <tr>
          <th scope="row">${tt("health.row_state")}</th>
          <td>
            <${Badge} kind=${statusKnown ? data.status : "muted"}>
              ${statusKnown ? tt(STATUS_KEYS[data.status]) : String(data.status)}
            <//>
          </td>
        </tr>
        <tr>
          <th scope="row">${tt("health.row_version")}</th>
          <td class="mono">${String(data.addon_version)}</td>
        </tr>
        <tr>
          <th scope="row">ntfy</th>
          <td>
            ${ntfy.healthy ? tt("health.ntfy_healthy") : tt("health.ntfy_unhealthy")}${ntfy.role
              ? `, ${tt("health.ntfy_role", { role: ntfy.role })}`
              : ""}
          </td>
        </tr>
        <tr>
          <th scope="row">${tt("health.row_schema")}</th>
          <td>
            ${db.supported
              ? tt("health.schema_supported", { version: db.schema_version })
              : tt("health.schema_unsupported", { version: db.schema_version })}
            ${db.error && html`<div class="muted">${db.error}</div>`}
          </td>
        </tr>
        <tr>
          <th scope="row">${tt("health.row_db_size")}</th>
          <td>${formatBytes(db.size_bytes, lang)}</td>
        </tr>
        <tr>
          <th scope="row">${tt("health.row_cache_size")}</th>
          <td>${formatBytes(db.cache_size_bytes, lang)}</td>
        </tr>
        ${counts &&
        html`<tr>
          <th scope="row">${tt("health.row_counts")}</th>
          <td>
            ${tt("health.counts", {
              users: tp("health.users", counts.users, { n: num(counts.users) }),
              rules: tp("health.rules", counts.acl_rules, { n: num(counts.acl_rules) }),
              tokens: tp("health.tokens", counts.tokens, { n: num(counts.tokens) }),
            })}
          </td>
        </tr>`}
      </tbody>
    <//>
  </div>`;
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

const RESET_KINDS = ["acls", "cache", "everything"];
const RESET_TITLES = {
  acls: "data.reset_acls_title",
  cache: "data.reset_cache_title",
  everything: "data.reset_everything_title",
};
const RESET_TEXTS = {
  acls: "data.reset_acls_text",
  cache: "data.reset_cache_text",
  everything: "data.reset_everything_text",
};
const REASON_KEYS = {
  daily: "data.reason_daily",
  manual: "data.reason_manual",
  "user-delete": "data.reason_user_delete",
  "role-change": "data.reason_role_change",
  "reset-acls": "data.reason_reset_acls",
  "clear-cache": "data.reason_clear_cache",
  "reset-everything": "data.reason_reset_everything",
};

function Export() {
  const tt = useT();
  const [format, setFormat] = useState("yaml");
  const [hashes, setHashes] = useState(false);
  const href = apiHref("export", { format, include_hashes: hashes ? 1 : 0 });
  return html`<div class="card">
    <h2>${tt("data.export_title")}</h2>
    <div class="toolbar">
      <${Field} id="data-format" label=${tt("data.format")}>
        <select id="data-format" value=${format} onChange=${(ev) => setFormat(ev.target.value)}>
          <option value="yaml">YAML</option>
          <option value="json">JSON</option>
        </select>
      <//>
      <label>
        <input type="checkbox" checked=${hashes} onChange=${(ev) => setHashes(ev.target.checked)} />
        ${tt("data.hashes")}
      </label>
      <a class="btn" href=${href} download="">${tt("data.download_export")}</a>
    </div>
    ${hashes && html`<div class="notice info" role="alert">${tt("data.hashes_notice")}</div>`}
    <div class="muted">${tt("data.tokens_hint")}</div>
  </div>`;
}

function Backups() {
  const tt = useT();
  const lang = useLang();
  const { data, error, loading, reload } = useAsync(() => get("backups"));
  const create = async () => {
    try {
      const res = await post("backups", { body: {} });
      toast("ok", tt("data.backup_created", { name: res.backup.name }));
      reload();
    } catch (err) {
      toast("error", tError(err));
    }
  };
  const reasonText = (reason) =>
    Object.prototype.hasOwnProperty.call(REASON_KEYS, reason) ? tt(REASON_KEYS[reason]) : String(reason || "-");
  const list = (data && data.backups) || [];
  return html`<div class="card">
    <div class="toolbar">
      <h2>${tt("data.backups_title")}</h2>
      <span class="spacer"></span>
      <button class="btn small" type="button" onClick=${create}>${tt("data.backup_now")}</button>
    </div>
    ${loading && !data && html`<${Loading} />`}
    <${ErrorNote} error=${error} onRetry=${reload} />
    <${ScrollTable} caption=${tt("data.backups_caption")}>
      <thead>
        <tr>
          <th scope="col">${tt("data.col_name")}</th>
          <th scope="col">${tt("data.col_created")}</th>
          <th scope="col">${tt("data.col_size")}</th>
          <th scope="col">${tt("data.col_reason")}</th>
          <th scope="col"><span class="sr-only">${tt("data.col_actions")}</span></th>
        </tr>
      </thead>
      <tbody>
        ${list.map(
          (b) =>
            html`<tr key=${b.name}>
              <td class="mono">${b.name}</td>
              <td>${formatDateTime(Date.parse(b.created), lang)}</td>
              <td>${formatBytes(b.size_bytes, lang)}</td>
              <td>${reasonText(b.reason)}</td>
              <td class="actions">
                <a
                  class="btn small secondary"
                  href=${apiHref(`backups/${b.name}`)}
                  aria-label=${tt("data.download_aria", { name: b.name })}
                  download=""
                >
                  ${tt("data.download")}
                </a>
              </td>
            </tr>`,
        )}
      </tbody>
    <//>
    ${data && list.length === 0 && html`<div class="muted">${tt("data.backups_empty")}</div>`}
  </div>`;
}

function Danger() {
  const tt = useT();
  const lang = useLang();
  const [pending, setPending] = useState(null);
  // A thrown error keeps the confirm dialog open and shows the localized code text.
  const run = async () => {
    const res = await post(`reset/${pending}`, { body: { confirm: RESET_PHRASES[pending] } });
    const counts = [];
    if (res.messages_deleted !== undefined) {
      counts.push(tp("data.deleted_messages", res.messages_deleted, { n: formatNumber(res.messages_deleted, lang) }));
    }
    if (res.attachments_deleted !== undefined) {
      counts.push(
        tp("data.deleted_attachments", res.attachments_deleted, { n: formatNumber(res.attachments_deleted, lang) }),
      );
    }
    const title = tt(RESET_TITLES[pending]);
    toast(
      "ok",
      counts.length ? tt("data.reset_done_counts", { title, counts: counts.join(", ") }) : tt("data.reset_done", { title }),
    );
    setPending(null);
  };
  return html`<div class="card danger-zone">
    <h2>${tt("data.danger_title")}</h2>
    <div class="muted">${tt("data.danger_hint")}</div>
    ${RESET_KINDS.map(
      (kind) =>
        html`<div key=${kind} class="danger-row">
          <div>
            <strong>${tt(RESET_TITLES[kind])}</strong>
            <div class="muted">${tt(RESET_TEXTS[kind])}</div>
          </div>
          <button class="btn danger" type="button" onClick=${() => setPending(kind)}>${tt(RESET_TITLES[kind])}</button>
        </div>`,
    )}
    ${pending &&
    html`<${ConfirmDialog}
      title=${tt(RESET_TITLES[pending])}
      danger=${true}
      message=${tt(RESET_TEXTS[pending])}
      expected=${RESET_PHRASES[pending]}
      confirmLabel=${tt("data.execute")}
      onCancel=${() => setPending(null)}
      onConfirm=${run}
    />`}
  </div>`;
}

// Effective rights and the generator need the user list; a failing list must not hide the other sections.
function UserTools({ params }) {
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

export default function View({ params }) {
  return html`<div>
    <${Status} />
    <${Publish} />
    <${UserTools} params=${params} />
    <${Export} />
    <${Backups} />
    <${Danger} />
  </div>`;
}
