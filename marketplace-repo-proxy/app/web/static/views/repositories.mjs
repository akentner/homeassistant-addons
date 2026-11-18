// Repositories view: every configured repository with branch, sync status, last sync, HEAD and found add-ons, read from
// api/overview every 15 s, plus one global "Sync now" button (the sync trigger covers all repositories, D-18). The last
// good data stays on screen while a refresh runs or fails. Text nodes only (R-03).
import { html, useCallback, useEffect, useRef, useState, usePoll, toast, Badge, DataTable, ErrorNote, Loading } from "../vendor/admin-ui/ui.mjs";
import { useLang, useT, t, tp, tError } from "../vendor/admin-ui/i18n.mjs";
import { formatRelative } from "../vendor/admin-ui/format.mjs";
import { get, post } from "../vendor/admin-ui/api.mjs";
import { statusKey, statusKind, shortSha, toMs } from "../model.mjs";

export const POLL_MS = 15000;

function useOverview(pollMs) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const inflight = useRef(false);
  const live = useRef(true);

  const reload = useCallback(async () => {
    if (inflight.current) return;
    inflight.current = true;
    try {
      const next = await get("overview");
      if (!live.current) return;
      if (!next || !Array.isArray(next.repositories)) {
        setError({ code: "http_error" });
      } else {
        setData(next);
        setError(null);
      }
    } catch (err) {
      if (live.current) setError(err);
    } finally {
      inflight.current = false;
    }
  }, []);

  useEffect(() => {
    live.current = true;
    reload();
    return () => {
      live.current = false;
    };
  }, []);
  usePoll(reload, pollMs);
  return { data, error, reload };
}

function branchText(tt, row) {
  const branch = typeof row.branch === "string" ? row.branch : "";
  if (!branch) return tt("mrp.repo.branch_unknown");
  if (row.branch_source === "configured") return tt("mrp.repo.branch_configured", { branch });
  return tt("mrp.repo.branch_default", { branch });
}

function SyncLine({ sync }) {
  const tt = useT();
  if (!sync) return null;
  const text =
    sync.state === "running" ? tt("mrp.repo.sync_running") : tt("mrp.repo.sync_idle", { minutes: sync.interval_minutes });
  return html`<p class="sync-line">${text}</p>`;
}

// One button for all repositories: POST api/sync with the empty JSON object (the server rejects any other body), then
// refresh the overview so the requested/running state shows at once.
function SyncNow({ onDone }) {
  const tt = useT();
  const [busy, setBusy] = useState(false);
  const run = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await post("sync", { body: {} });
      toast("ok", t("mrp.sync.requested"));
    } catch (err) {
      toast("error", tError(err));
    } finally {
      setBusy(false);
    }
    onDone();
  };
  return html`<div class="sync-actions">
    <button class="btn" type="button" disabled=${busy} onClick=${run}>${tt("mrp.sync.now")}</button>
  </div>`;
}

export default function Repositories() {
  const tt = useT();
  const lang = useLang();
  const { data, error, reload } = useOverview(POLL_MS);
  const rows = data ? data.repositories : [];
  const nowMs = data ? data.now_ms : undefined;

  const columns = [
    {
      key: "repository",
      titleKey: "mrp.repo.col.repository",
      render: (row) => html`<span class="repo-name">${row.repository}</span>
        <span class="repo-sub">${branchText(tt, row)}</span>`,
    },
    {
      key: "status",
      titleKey: "mrp.repo.col.status",
      render: (row) => html`<${Badge} kind=${statusKind(row.status)}>${tt(statusKey(row.status))}<//>
        ${row.message && html`<span class="repo-message">${row.message}</span>`}`,
    },
    {
      key: "last_sync",
      titleKey: "mrp.repo.col.last_sync",
      render: (row) => {
        const ms = toMs(row.last_success);
        return ms === null ? tt("mrp.repo.never") : formatRelative(ms, lang, nowMs);
      },
    },
    {
      key: "head",
      titleKey: "mrp.repo.col.head",
      render: (row) => html`<span class="repo-sha">${shortSha(row.head) || "-"}</span>`,
    },
    {
      key: "addons",
      titleKey: "mrp.repo.col.addons",
      render: (row) => tp("mrp.repo.addons", Array.isArray(row.addons) ? row.addons.length : 0),
    },
  ];

  return html`<div>
    ${error && html`<${ErrorNote} error=${error} onRetry=${reload} />`}
    ${!data && !error && html`<${Loading} />`}
    ${data &&
    html`<section class="card repo-card">
      <h2>${tt("mrp.repo.title")}</h2>
      <${SyncLine} sync=${data.sync} />
      <${SyncNow} onDone=${reload} />
      ${!data.status_available && html`<p class="hint">${tt("mrp.repo.no_status")}</p>`}
      <div class="repo-table">
        <${DataTable}
          columns=${columns}
          rows=${rows}
          rowKey="repository"
          caption=${tt("mrp.repo.caption")}
          empty=${tt("mrp.repo.empty")}
        />
      </div>
    </section>`}
  </div>`;
}
