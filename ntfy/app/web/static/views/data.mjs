// Export, backups and the guarded reset actions. Texts come from i18n; download links are built with apiHref.
import { html, useState, useAsync, toast, ConfirmDialog, Loading, Field } from "../vendor/admin-ui/ui.mjs";
import { get, post } from "../vendor/admin-ui/api.mjs";
import { apiHref } from "../vendor/admin-ui/ingress.mjs";
import { useT, useLang, tp, tError } from "../vendor/admin-ui/i18n.mjs";
import { formatBytes, formatDateTime, formatNumber } from "../vendor/admin-ui/format.mjs";
import { ErrorNote, ScrollTable } from "../components.mjs";
import { RESET_PHRASES } from "../lib/model.mjs";

export const meta = { id: "data", titleKey: "view.data" };

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

export default function View() {
  return html`<div>
    <${Export} />
    <${Backups} />
    <${Danger} />
  </div>`;
}
