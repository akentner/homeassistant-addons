// Repositories view: every configured repository with branch and its source, sync status, last sync, HEAD and found
// add-ons, read from api/overview (every 2 s while a sync is requested or running, every 15 s otherwise), plus one
// global "Sync now" button (the sync trigger covers all repositories, D-18) and the optional registration column
// (D-19). The last good data stays on screen while a refresh runs or fails. Text nodes only (R-03).
import { html, useCallback, useEffect, useRef, useState, usePoll, toast, Badge, DataTable, ErrorNote, Loading } from "../vendor/admin-ui/ui.mjs";
import { useLang, useT, t, tp, tError } from "../vendor/admin-ui/i18n.mjs";
import { formatRelative } from "../vendor/admin-ui/format.mjs";
import { get, post } from "../vendor/admin-ui/api.mjs";
import {
  BRANCH_KEYS,
  REGISTRATION_KEYS,
  statusKey,
  statusKind,
  registrationKey,
  registrationKind,
  hasRegistration,
  shortSha,
  toMs,
  pollMs,
} from "../model.mjs";

function useOverview() {
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
  // usePoll re-arms when the interval changes, so the cadence follows the sync state.
  usePoll(reload, pollMs(data));
  return { data, error, reload };
}

const syncBusy = (sync) => Boolean(sync) && (sync.requested === true || sync.state === "running");

function branchText(tt, row) {
  const branch = typeof row.branch === "string" ? row.branch : "";
  if (!branch) return tt("mrp.repo.branch_unknown");
  // Without status the branch comes from the add-on options, i.e. it is configured.
  if (row.branch_source === "upstream_default") return tt(BRANCH_KEYS.upstream_default, { branch });
  return tt(BRANCH_KEYS.configured, { branch });
}

// State of the sync service; the next due time only while it waits (during a cycle it is the old value).
function SyncLine({ sync, nowMs }) {
  const tt = useT();
  const lang = useLang();
  if (!sync) return null;
  const parts = [];
  if (sync.state === "running") parts.push(tt("mrp.sync.running"));
  else if (sync.requested === true) parts.push(tt("mrp.sync.requested"));
  else {
    parts.push(tt("mrp.sync.idle"));
    const due = toMs(sync.next_due);
    if (due !== null) parts.push(tt("mrp.sync.next_due", { time: formatRelative(due, lang, nowMs) }));
    const minutes = sync.interval_minutes;
    if (Number.isInteger(minutes) && minutes > 0) parts.push(tt("mrp.sync.interval", { minutes }));
  }
  return html`<p class="sync-line">${parts.join(" · ")}</p>`;
}

// One button for all repositories: POST api/sync with the empty JSON object (the server rejects any other body), then
// refresh the overview so the requested/running state shows at once. Disabled while a sync is requested or running.
function SyncNow({ blocked, onDone }) {
  const tt = useT();
  const [busy, setBusy] = useState(false);
  const run = async () => {
    if (busy || blocked) return;
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
    <button class="btn" type="button" disabled=${busy || blocked} onClick=${run}>${tt("mrp.sync.now")}</button>
  </div>`;
}

function RegistrationCell({ registration }) {
  const tt = useT();
  if (!registration || registrationKey(registration.state) === null) return null;
  const detail = typeof registration.detail === "string" ? registration.detail : "";
  return html`<${Badge} kind=${registrationKind(registration.state)}>${tt(REGISTRATION_KEYS[registration.state])}<//>
    ${detail && html`<span class="repo-message">${detail}</span>`}`;
}

export default function Repositories() {
  const tt = useT();
  const lang = useLang();
  const { data, error, reload } = useOverview();
  const rows = data ? data.repositories : [];
  const nowMs = data ? data.now_ms : undefined;
  const withRegistration = hasRegistration(rows);
  const leftover = rows.some((row) => row && row.registration && row.registration.state === "leftover");

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
    ...(withRegistration
      ? [
          {
            key: "registration",
            titleKey: "mrp.reg.col",
            render: (row) => html`<${RegistrationCell} registration=${row.registration} />`,
          },
        ]
      : []),
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
      render: (row) => {
        const names = Array.isArray(row.addons) ? row.addons.filter((name) => typeof name === "string") : [];
        return html`${tp("mrp.repo.addons", names.length)}
          ${names.length > 0 && html`<span class="repo-sub">${names.join(", ")}</span>`}`;
      },
    },
  ];

  return html`<div>
    ${error && html`<${ErrorNote} error=${error} onRetry=${reload} />`}
    ${!data && !error && html`<${Loading} />`}
    ${data &&
    html`<section class="card repo-card">
      <h2>${tt("mrp.repo.title")}</h2>
      <${SyncLine} sync=${data.sync} nowMs=${nowMs} />
      <${SyncNow} blocked=${syncBusy(data.sync)} onDone=${reload} />
      ${!data.status_available && html`<p class="hint">${tt("mrp.repo.no_status")}</p>`}
      ${leftover && html`<p class="hint">${tt("mrp.reg.leftover_note")}</p>`}
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
