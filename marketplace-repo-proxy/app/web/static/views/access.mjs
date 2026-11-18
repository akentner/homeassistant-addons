// Access view: per configured repository the users with label, source badge and creation time (api/access, polled
// every 15 s), store URLs on demand ("Show URLs" -> api/access/{owner}/{repo}/{user}/urls, shown only as text in
// CopyField, D-16), an add form, and Rotate / Revoke behind type-to-confirm dialogs that state the consequences
// (D-12). System users are read-only (D-13); entries of repositories that are no longer configured are listed in an
// inactive group with Revoke only. The list never carries a hash or a URL. Text nodes only (R-03); errors through
// tError (R-14).
import {
  html,
  useCallback,
  useEffect,
  useRef,
  useState,
  usePoll,
  toast,
  Badge,
  ConfirmDialog,
  CopyField,
  DataTable,
  ErrorNote,
  Field,
  Loading,
} from "../vendor/admin-ui/ui.mjs";
import { useLang, useT, t } from "../vendor/admin-ui/i18n.mjs";
import { formatRelative } from "../vendor/admin-ui/format.mjs";
import { del, get, post } from "../vendor/admin-ui/api.mjs";
import { SOURCE_KEYS, isSource, sourceKind, splitRepository, toMs, validUser } from "../model.mjs";

export const ACCESS_POLL_MS = 15000;

function useAccess() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const inflight = useRef(false);
  const live = useRef(true);

  const reload = useCallback(async () => {
    if (inflight.current) return;
    inflight.current = true;
    try {
      const next = await get("access");
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
  usePoll(reload, ACCESS_POLL_MS);
  return { data, error, reload };
}

const usersOf = (row) => (Array.isArray(row.users) ? row.users.filter((u) => u && typeof u.user === "string") : []);

function SourceBadge({ source }) {
  const tt = useT();
  return html`<${Badge} kind=${sourceKind(source)}>${isSource(source) ? tt(SOURCE_KEYS[source]) : tt("mrp.source.unknown")}<//>`;
}

function SourceCell({ entry }) {
  const tt = useT();
  return html`<${SourceBadge} source=${entry.source} />
    ${entry.protected === true && html` <${Badge} kind="info">${tt("mrp.access.protected")}<//>`}`;
}

function CreatedCell({ entry, nowMs }) {
  const tt = useT();
  const lang = useLang();
  const ms = toMs(entry.created);
  return ms === null ? tt("mrp.access.created_unknown") : formatRelative(ms, lang, nowMs);
}

// One CopyField per store URL (internal always, public when configured).
function UrlFields({ urls }) {
  const tt = useT();
  if (!urls) return null;
  return html`<div class="access-urls">
    ${typeof urls.internal === "string" &&
    html`<div class="form-row">
      <span class="hint">${tt("mrp.access.url.internal")}</span>
      <${CopyField} value=${urls.internal} label=${tt("mrp.access.url.internal")} />
    </div>`}
    ${typeof urls.public === "string" &&
    html`<div class="form-row">
      <span class="hint">${tt("mrp.access.url.public")}</span>
      <${CopyField} value=${urls.public} label=${tt("mrp.access.url.public")} />
    </div>`}
  </div>`;
}

// URLs handed out once by the add or rotate response, with the secret notice.
function FreshUrls({ fresh, onHide }) {
  const tt = useT();
  return html`<div class="access-new">
    <p class="repo-name">${tt("mrp.access.urls.new", { user: fresh.user })}</p>
    <div class="notice info" role="status">${tt("mrp.access.urls.secret")}</div>
    <${UrlFields} urls=${fresh.urls} />
    <button class="btn small secondary" type="button" onClick=${onHide}>${tt("mrp.access.urls.hide")}</button>
  </div>`;
}

// "Show URLs": fetched on demand, never part of the polled list; "Hide URLs" drops them from the page again.
function ShowUrls({ owner, repo, user }) {
  const tt = useT();
  const [urls, setUrls] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const show = async () => {
    setBusy(true);
    setError(null);
    try {
      setUrls(await get(`access/${owner}/${repo}/${user}/urls`));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  if (urls) {
    return html`<div>
      <${UrlFields} urls=${urls} />
      <button class="btn small secondary" type="button" onClick=${() => setUrls(null)}>${tt("mrp.access.urls.hide")}</button>
    </div>`;
  }
  return html`<div>
    <button
      class="btn small secondary"
      type="button"
      aria-label=${tt("mrp.access.urls.show_aria", { user })}
      disabled=${busy}
      onClick=${show}
    >
      ${tt("mrp.access.urls.show")}
    </button>
    <${ErrorNote} error=${error} />
  </div>`;
}

// Destructive actions of one row; protected (system) users get none (D-13).
function RowActions({ entry, rotate, onAsk }) {
  const tt = useT();
  if (entry.protected === true) return null;
  const user = entry.user;
  return html`${rotate &&
    html`<button
      class="btn small danger"
      type="button"
      aria-label=${tt("mrp.access.rotate.aria", { user })}
      onClick=${() => onAsk("rotate", user)}
    >
      ${tt("mrp.access.rotate.button")}
    </button>`}
    <button
      class="btn small danger"
      type="button"
      aria-label=${tt("mrp.access.revoke.aria", { user })}
      onClick=${() => onAsk("revoke", user)}
    >
      ${tt("mrp.access.revoke.button")}
    </button>`;
}

// Add form: the label is checked locally first, then POSTed as { user }; the response carries the URLs once.
function AddUser({ owner, repo, onAdded }) {
  const tt = useT();
  const id = `access-add-${owner}-${repo}`;
  const [label, setLabel] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const submit = async (ev) => {
    if (ev && typeof ev.preventDefault === "function") ev.preventDefault();
    if (busy) return;
    setError(null);
    if (!validUser(label)) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    setBusy(true);
    try {
      const result = await post(`access/${owner}/${repo}`, { body: { user: label } });
      setLabel("");
      toast("ok", t("mrp.access.add.done", { user: result && typeof result.user === "string" ? result.user : label }));
      onAdded(result);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  return html`<div class="access-add">
    <form onSubmit=${submit}>
      <${Field} id=${id} label=${tt("mrp.access.add.label")} hint=${tt("mrp.access.add.hint")}>
        <input
          id=${id}
          type="text"
          value=${label}
          autocomplete="off"
          aria-describedby=${`${id}-hint`}
          aria-invalid=${invalid ? "true" : "false"}
          onInput=${(ev) => setLabel(ev.target.value)}
        />
      <//>
      ${invalid && html`<div class="notice error" role="alert">${tt("mrp.access.add.invalid")}</div>`}
      <div class="actions">
        <button class="btn" type="submit" disabled=${busy}>${tt("mrp.access.add.submit")}</button>
      </div>
    </form>
    <${ErrorNote} error=${error} />
  </div>`;
}

function RepositoryCard({ row, nowMs, fresh, onFresh, onAsk, onChange }) {
  const tt = useT();
  const parts = splitRepository(row.repository);
  if (!parts) return null;
  const [owner, repo] = parts;
  const columns = [
    { key: "user", titleKey: "mrp.access.col.user", render: (u) => html`<span class="repo-name">${u.user}</span>` },
    { key: "source", titleKey: "mrp.access.col.source", render: (u) => html`<${SourceCell} entry=${u} />` },
    { key: "created", titleKey: "mrp.access.col.created", render: (u) => html`<${CreatedCell} entry=${u} nowMs=${nowMs} />` },
    {
      key: "urls",
      titleKey: "mrp.access.col.urls",
      // keyed by label and creation time: a rotation remounts it, so URLs shown before the rotation disappear
      render: (u) => html`<${ShowUrls} key=${`${u.user}|${u.created}`} owner=${owner} repo=${repo} user=${u.user} />`,
    },
    {
      key: "actions",
      titleKey: "mrp.access.col.actions",
      render: (u) => html`<${RowActions} entry=${u} rotate=${true} onAsk=${(kind, user) => onAsk(kind, row.repository, user)} />`,
    },
  ];
  return html`<section class="card repo-card">
    <h2 class="repo-name">${row.repository}</h2>
    <div class="repo-table">
      <${DataTable}
        columns=${columns}
        rows=${usersOf(row)}
        rowKey="user"
        caption=${tt("mrp.access.caption", { repository: row.repository })}
        empty=${tt("mrp.access.no_users")}
      />
    </div>
    ${fresh && html`<${FreshUrls} fresh=${fresh} onHide=${() => onFresh(null)} />`}
    <${AddUser}
      owner=${owner}
      repo=${repo}
      onAdded=${(result) => {
        if (result && result.urls) onFresh({ repository: row.repository, user: result.user, urls: result.urls });
        onChange();
      }}
    />
  </section>`;
}

// Entries of repositories that are no longer configured: they grant no access and can only be revoked.
function InactiveCard({ rows, nowMs, onAsk }) {
  const tt = useT();
  const columns = (repository) => [
    { key: "user", titleKey: "mrp.access.col.user", render: (u) => html`<span class="repo-name">${u.user}</span>` },
    { key: "source", titleKey: "mrp.access.col.source", render: (u) => html`<${SourceCell} entry=${u} />` },
    { key: "created", titleKey: "mrp.access.col.created", render: (u) => html`<${CreatedCell} entry=${u} nowMs=${nowMs} />` },
    {
      key: "actions",
      titleKey: "mrp.access.col.actions",
      render: (u) => html`<${RowActions} entry=${u} rotate=${false} onAsk=${(kind, user) => onAsk(kind, repository, user)} />`,
    },
  ];
  return html`<section class="card repo-card">
    <h2>${tt("mrp.access.inactive")}</h2>
    <p class="hint">${tt("mrp.access.inactive_hint")}</p>
    ${rows.map(
      (row) => html`<div key=${row.repository} class="repo-table">
        <h3 class="repo-name">${row.repository}</h3>
        <${DataTable}
          columns=${columns(row.repository)}
          rows=${usersOf(row)}
          rowKey="user"
          caption=${tt("mrp.access.caption", { repository: row.repository })}
          empty=${tt("mrp.access.no_users")}
        />
      </div>`,
    )}
  </section>`;
}

// Type-to-confirm with the exact label (R-04, D-12). Errors propagate, so the dialog shows them through tError.
function ActionDialog({ ask, onClose, onRotated, onRevoked }) {
  const tt = useT();
  const parts = splitRepository(ask.repository);
  const path = parts ? `access/${parts[0]}/${parts[1]}/${ask.user}` : null;
  const body = { confirm: ask.user };
  if (ask.kind === "rotate") {
    return html`<${ConfirmDialog}
      title=${tt("mrp.access.rotate.title")}
      message=${tt("mrp.access.rotate.message", { user: ask.user })}
      confirmLabel=${tt("mrp.access.rotate.confirm")}
      danger=${true}
      expected=${ask.user}
      onCancel=${onClose}
      onConfirm=${async () => {
        const result = await post(`${path}/rotate`, { body });
        onRotated(result);
      }}
    />`;
  }
  return html`<${ConfirmDialog}
    title=${tt("mrp.access.revoke.title")}
    message=${tt("mrp.access.revoke.message", { user: ask.user })}
    confirmLabel=${tt("mrp.access.revoke.confirm")}
    danger=${true}
    expected=${ask.user}
    onCancel=${onClose}
    onConfirm=${async () => {
      await del(path, { body });
      onRevoked();
    }}
  />`;
}

export default function Access() {
  const tt = useT();
  const { data, error, reload } = useAccess();
  const [ask, setAsk] = useState(null);
  const [fresh, setFresh] = useState(null);
  const rows = data ? data.repositories.filter((row) => row && typeof row.repository === "string") : [];
  const activeRows = rows.filter((row) => row.active === true);
  const inactiveRows = rows.filter((row) => row.active !== true && usersOf(row).length > 0 && splitRepository(row.repository));
  const onAsk = (kind, repository, user) => setAsk({ kind, repository, user });
  return html`<div>
    ${error && html`<${ErrorNote} error=${error} onRetry=${reload} />`}
    ${!data && !error && html`<${Loading} />`}
    ${data && activeRows.length === 0 && html`<p class="hint">${tt("mrp.access.empty")}</p>`}
    ${activeRows.map(
      (row) => html`<${RepositoryCard}
        key=${row.repository}
        row=${row}
        nowMs=${data.now_ms}
        fresh=${fresh && fresh.repository === row.repository ? fresh : null}
        onFresh=${setFresh}
        onAsk=${onAsk}
        onChange=${reload}
      />`,
    )}
    ${inactiveRows.length > 0 && html`<${InactiveCard} rows=${inactiveRows} nowMs=${data.now_ms} onAsk=${onAsk} />`}
    ${ask &&
    html`<${ActionDialog}
      ask=${ask}
      onClose=${() => setAsk(null)}
      onRotated=${(result) => {
        setAsk(null);
        if (result && result.urls) setFresh({ repository: ask.repository, user: ask.user, urls: result.urls });
        toast("ok", t("mrp.access.rotate.done", { user: ask.user }));
        reload();
      }}
      onRevoked=${() => {
        setAsk(null);
        toast("ok", t("mrp.access.revoke.done", { user: ask.user }));
        reload();
      }}
    />`}
  </div>`;
}
