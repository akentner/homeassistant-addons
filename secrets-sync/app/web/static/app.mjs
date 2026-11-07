// Secrets Sync page: sticky topbar with status badges and actions, general info, providers and the tabs Keys,
// Synthetic keys, Key usage and Events. Data comes only from api/status.json (names and positions, never values).
// Relative URLs only (the page lives below an ingress path); the lib is imported through its public modules.
import {
  html,
  render,
  useCallback,
  useEffect,
  useRef,
  useState,
  usePoll,
  Badge,
  Tabs,
  Toasts,
  ErrorNote,
  toast,
} from "./vendor/admin-ui/ui.mjs";
import { Topbar, ErrorBoundary, useHashRoute } from "./vendor/admin-ui/shell.mjs";
import { registerStrings, tError, useLang, useT } from "./vendor/admin-ui/i18n.mjs";
import { formatDateTime, formatRelative } from "./vendor/admin-ui/format.mjs";
import { get, post } from "./vendor/admin-ui/api.mjs";
import { asArr, asObj, isObj, pickTab, parseTime, statusInfo, TAB_IDS } from "./model.mjs";
import { GeneralCard, GuardCard, PreviewPanel, ProvidersCard, useNum } from "./parts.mjs";
import KeysView from "./views/keys.mjs";
import SyntheticView from "./views/synthetic.mjs";
import UsageView from "./views/usage.mjs";
import EventsView from "./views/events.mjs";
import de from "./strings.de.mjs";
import en from "./strings.en.mjs";

registerStrings({ de, en });

export const POLL_MS = 15000;
export const REFRESH_AFTER_MS = [3000, 10000];
const TAB_KEY = "secrets-sync:tab";

export function readTab(storage) {
  try {
    return (storage || globalThis.localStorage).getItem(TAB_KEY);
  } catch {
    return null;
  }
}
export function writeTab(id, storage) {
  try {
    (storage || globalThis.localStorage).setItem(TAB_KEY, id);
  } catch {
    // storage unavailable: the choice only lasts for this page load
  }
}

function Actions({ busy, onSync, onPreview, onRefresh }) {
  const tt = useT();
  return html`<div class="action-buttons" role="group" aria-label=${tt("act.group")}>
    <button class="btn small" type="button" disabled=${busy} onClick=${onSync}>${tt("act.sync")}</button>
    <button class="btn small secondary" type="button" disabled=${busy} onClick=${onPreview}>${tt("act.preview")}</button>
    <button class="btn small secondary" type="button" onClick=${onRefresh}>${tt("act.refresh")}</button>
  </div>`;
}

export function App() {
  const tt = useT();
  const lang = useLang();
  const num = useNum();
  const [state, setState] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [failed, setFailed] = useState(false);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const route = useHashRoute(TAB_IDS, pickTab(null, readTab()));
  const timers = useRef([]);
  const live = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const data = await get("status.json");
      if (!live.current) return;
      setState(isObj(data) ? data : {});
      setLastUpdate(Date.now());
      setFailed(false);
    } catch {
      if (live.current) setFailed(true);
    }
  }, []);

  const refreshSoon = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = REFRESH_AFTER_MS.map((ms) => setTimeout(refresh, ms));
  }, [refresh]);

  useEffect(() => {
    live.current = true;
    refresh();
    const onVisible = () => {
      if (document.visibilityState !== "hidden") refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      live.current = false;
      timers.current.forEach(clearTimeout);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);
  usePoll(refresh, POLL_MS);

  // A rate limit answer (429) is a hint, not a page error.
  const notify = (err) => toast(err && err.code === "rate_limited" ? "info" : "error", tError(err));

  const sync = async () => {
    setBusy(true);
    try {
      await post("sync");
      toast("ok", tt("notice.sync_started"));
    } catch (err) {
      notify(err);
    } finally {
      setBusy(false);
      refreshSoon();
    }
  };
  // Apply anyway: the confirmation (type to confirm) is asked by the guard card; errors bubble into its dialog.
  const applyForce = async () => {
    await post("sync", { query: { force: 1 } });
    toast("ok", tt("guard.started"));
    refreshSoon();
  };
  const runPreview = async () => {
    setBusy(true);
    try {
      setPreview(await post("preview"));
      refreshSoon();
    } catch (err) {
      notify(err);
    } finally {
      setBusy(false);
    }
  };
  const changeTab = (id) => {
    writeTab(id);
    try {
      globalThis.location.hash = `#/${id}`;
    } catch {
      // no location (tests, odd embeddings)
    }
  };

  const s = state || {};
  const info = statusInfo(s);
  const now = Date.now();
  const lastSync = parseTime(s.last_success_at);
  const versions = asObj(s.versions);
  const labelFor = { ok: tt("state.ok"), degraded: tt("state.degraded"), error: tt("state.error"), stale: tt("status.stale"), starting: tt("status.starting") };
  const status = { kind: info.kind, text: state ? labelFor[info.id] : tt("state.loading") };
  const syntheticCount = asArr(s.synthetic).length;
  const missing = Object.keys(asObj(asObj(s.usage).missing)).length;
  const counted = (key, count) => tt("tab.with_count", { title: tt(key), count: num(count) });
  const tabs = [
    { id: "keys", title: asArr(asObj(s.keys).names).length ? counted("tab.keys", asArr(asObj(s.keys).names).length) : tt("tab.keys") },
    { id: "synthetic", title: syntheticCount ? counted("tab.synthetic", syntheticCount) : tt("tab.synthetic") },
    {
      id: "usage",
      title: asObj(s.usage).enabled === true ? tt("tab.usage_missing", { title: tt("tab.usage"), count: num(missing) }) : tt("tab.usage"),
    },
    { id: "events", title: asArr(s.events).length ? counted("tab.events", asArr(s.events).length) : tt("tab.events") },
  ];
  const View = { keys: KeysView, synthetic: SyntheticView, usage: UsageView, events: EventsView }[route.id];
  // Two placements (topbar, hidden below 600 px by the lib, and a row under it for phones): fresh vnode each time.
  const actions = () => html`<${Actions} busy=${busy} onSync=${sync} onPreview=${runPreview} onRefresh=${refresh} />`;

  return html`<div>
    <${Topbar} title=${tt("app.title")} status=${status}>
      ${state && html`<${Badge} kind="muted">${tt("app.items", { n: typeof s.items === "number" ? num(s.items) : "-" })}<//>`}
      ${state && html`<${Badge} kind="muted"><span title=${lastSync === null ? "" : formatDateTime(lastSync, lang)}>${lastSync === null ? tt("app.never") : tt("app.synced", { when: formatRelative(lastSync, lang, now) })}</span><//>`}
      ${state && versions.addon && html`<${Badge} kind="muted">${tt("app.version", { version: String(versions.addon) })}<//>`}
      ${actions()}
    <//>
    <main>
      <div class="actions-row">${actions()}</div>
      ${lastUpdate !== null && !failed && html`<p class="hint">${tt("app.updated", { time: formatDateTime(lastUpdate, lang, { dateStyle: undefined, timeStyle: "medium" }) })}</p>`}
      ${failed &&
      html`<div class="notice error" role="alert">${lastUpdate === null ? tt("notice.offline_nodata") : tt("notice.offline", { time: formatDateTime(lastUpdate, lang, { dateStyle: undefined, timeStyle: "medium" }) })}</div>`}
      <${GuardCard} state=${s} onApply=${applyForce} />
      ${preview && html`<${PreviewPanel} result=${preview} onClose=${() => setPreview(null)} />`}
      <${GeneralCard} state=${s} now=${now} />
      <${ProvidersCard} state=${s} />
      <section class="card section">
        <${Tabs} tabs=${tabs} active=${route.id} onChange=${changeTab} label=${tt("tab.label")}>
          <${ErrorBoundary} key=${route.id}><${View} state=${s} /><//>
        <//>
      </section>
    </main>
    <${Toasts} />
  </div>`;
}

if (typeof document !== "undefined" && document.getElementById("app")) {
  render(html`<${App} />`, document.getElementById("app"));
}
