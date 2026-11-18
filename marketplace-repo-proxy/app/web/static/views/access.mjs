// Access view: per configured repository the users with label, source badge and creation time (api/access, polled
// every 15 s), store URLs on demand ("Show URLs" -> api/access/{owner}/{repo}/{user}/urls, shown only as text in
// CopyField, D-16) and an add form that shows the new user's URLs once. The list never carries a hash or a URL.
// Text nodes only (R-03); errors through tError (R-14).
import {
  html,
  useCallback,
  useEffect,
  useRef,
  useState,
  usePoll,
  toast,
  Badge,
  CopyField,
  DataTable,
  ErrorNote,
  Field,
  Loading,
} from "../vendor/admin-ui/ui.mjs";
import { useLang, useT, t } from "../vendor/admin-ui/i18n.mjs";
import { formatRelative } from "../vendor/admin-ui/format.mjs";
import { get, post } from "../vendor/admin-ui/api.mjs";
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

function SourceBadge({ source }) {
  const tt = useT();
  return html`<${Badge} kind=${sourceKind(source)}>${isSource(source) ? tt(SOURCE_KEYS[source]) : tt("mrp.source.unknown")}<//>`;
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
    <button class="btn small secondary" type="button" disabled=${busy} onClick=${show}>${tt("mrp.access.urls.show")}</button>
    <${ErrorNote} error=${error} />
  </div>`;
}

// Add form: the label is checked locally first, then POSTed as { user }; the response carries the URLs once.
function AddUser({ owner, repo, onAdded }) {
  const tt = useT();
  const id = `access-add-${owner}-${repo}`;
  const [label, setLabel] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [added, setAdded] = useState(null);
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
      setAdded(result);
      setLabel("");
      toast("ok", t("mrp.access.add.done", { user: result && typeof result.user === "string" ? result.user : label }));
      onAdded();
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
    ${added &&
    html`<div class="access-new">
      <div class="notice info" role="status">${tt("mrp.access.urls.secret")}</div>
      <${UrlFields} urls=${added.urls} />
      <button class="btn small secondary" type="button" onClick=${() => setAdded(null)}>${tt("mrp.access.urls.hide")}</button>
    </div>`}
  </div>`;
}

function RepositoryCard({ row, nowMs, onChange }) {
  const tt = useT();
  const lang = useLang();
  const parts = splitRepository(row.repository);
  if (!parts) return null;
  const [owner, repo] = parts;
  const users = Array.isArray(row.users) ? row.users.filter((u) => u && typeof u.user === "string") : [];
  const columns = [
    { key: "user", titleKey: "mrp.access.col.user", render: (u) => html`<span class="repo-name">${u.user}</span>` },
    { key: "source", titleKey: "mrp.access.col.source", render: (u) => html`<${SourceBadge} source=${u.source} />` },
    {
      key: "created",
      titleKey: "mrp.access.col.created",
      render: (u) => {
        const ms = toMs(u.created);
        return ms === null ? tt("mrp.access.created_unknown") : formatRelative(ms, lang, nowMs);
      },
    },
    {
      key: "urls",
      titleKey: "mrp.access.col.urls",
      render: (u) => html`<${ShowUrls} owner=${owner} repo=${repo} user=${u.user} />`,
    },
  ];
  return html`<section class="card repo-card">
    <h2 class="repo-name">${row.repository}</h2>
    <div class="repo-table">
      <${DataTable}
        columns=${columns}
        rows=${users}
        rowKey="user"
        caption=${tt("mrp.access.caption", { repository: row.repository })}
        empty=${tt("mrp.access.no_users")}
      />
    </div>
    <${AddUser} owner=${owner} repo=${repo} onAdded=${onChange} />
  </section>`;
}

export default function Access() {
  const tt = useT();
  const { data, error, reload } = useAccess();
  const rows = data ? data.repositories.filter((row) => row && row.active === true) : [];
  return html`<div>
    ${error && html`<${ErrorNote} error=${error} onRetry=${reload} />`}
    ${!data && !error && html`<${Loading} />`}
    ${data && rows.length === 0 && html`<p class="hint">${tt("mrp.access.empty")}</p>`}
    ${data && rows.map((row) => html`<${RepositoryCard} key=${row.repository} row=${row} nowMs=${data.now_ms} onChange=${reload} />`)}
  </div>`;
}
