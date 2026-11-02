// Demo shell: topbar with health and theme chips, hash navigation, lazy views, toasts and the optional HA wiring.
// Relative URLs only (the page lives below an ingress path); imports the lib through its public modules only.
import {
  html,
  render,
  useState,
  useEffect,
  useRef,
  usePoll,
  Badge,
  ErrorNote,
  Loading,
  Toasts,
} from "./lib/ui.mjs";
import { Topbar, ErrorBoundary, useHashRoute } from "./lib/shell.mjs";
import { registerStrings, useT } from "./lib/i18n.mjs";
import { get } from "./lib/api.mjs";
import { createHaBridge } from "./lib/ha-bridge.mjs";
import { createThemeSync } from "./lib/theme-sync.mjs";
import { createInfoNav } from "./info-nav.mjs";
import de from "./strings.de.mjs";
import en from "./strings.en.mjs";

registerStrings({ de, en });

export const VIEWS = [
  { id: "gallery", titleKey: "demo.nav.gallery" },
  { id: "tokens", titleKey: "demo.nav.tokens" },
  { id: "language", titleKey: "demo.nav.language" },
  { id: "crud", titleKey: "demo.nav.crud" },
  { id: "rules", titleKey: "demo.nav.rules" },
  { id: "spike", titleKey: "demo.nav.spike" },
];
const IDS = VIEWS.map((v) => v.id);
const DEFAULT_VIEW = "gallery";
const HEALTH_POLL_MS = 15000;
const NAV_KEY = "admin-ui:demo-nav";
const NAV_MODES = ["topbar", "tabs"];

// Navigation style choice, kept per browser; storage may be missing or blocked, then the default applies.
export function readNavMode(storage = globalThis.localStorage) {
  try {
    const raw = storage.getItem(NAV_KEY);
    return NAV_MODES.includes(raw) ? raw : "topbar";
  } catch {
    return "topbar";
  }
}
export function writeNavMode(mode, storage = globalThis.localStorage) {
  try {
    storage.setItem(NAV_KEY, mode);
  } catch {
    // storage unavailable: the choice only lasts for this page load
  }
}

const cache = new Map();
// The id is always validated against VIEWS by parseHash before it gets here. The literal relative prefix keeps the
// import analysable and below the ingress path.
export function loadView(id) {
  if (!cache.has(id)) {
    cache.set(
      id,
      import(`./views/${id}.mjs`).catch((err) => {
        cache.delete(id);
        throw err;
      }),
    );
  }
  return cache.get(id);
}

// HA's own info page of this add-on; the slug comes from the server (api/health), unknown means no link.
export function infoPath(health) {
  const slug = health && typeof health.addon_slug === "string" ? health.addon_slug : "";
  return /^[a-z0-9][a-z0-9_]{0,63}$/.test(slug) ? `/hassio/addon/${slug}/info` : null;
}

// Shows whether the page follows the embedding Home Assistant theme or uses its own.
export function ThemeChip({ sync }) {
  const tt = useT();
  const read = () => (sync && typeof sync.status === "function" ? sync.status() : null);
  const [status, setStatus] = useState(read);
  useEffect(() => {
    setStatus(read());
    if (!sync || typeof sync.subscribe !== "function") return undefined;
    const off = sync.subscribe(() => setStatus(read()));
    return () => typeof off === "function" && off();
  }, [sync]);
  const active = Boolean(status && status.active);
  return html`<${Badge} kind=${active ? "info" : "muted"}>
    ${active ? tt("demo.theme.sync", { mode: status.mode || "-" }) : tt("demo.theme.own")}
  <//>`;
}

function Guarded({ id, params, ha, load }) {
  const [state, setState] = useState({ id: null, view: null, error: null });
  useEffect(() => {
    let live = true;
    setState({ id, view: null, error: null });
    Promise.resolve()
      .then(() => load(id))
      .then(
        (mod) => live && setState({ id, view: mod.default, error: null }),
        (error) => live && setState({ id, view: null, error }),
      );
    return () => {
      live = false;
    };
  }, [id]);
  if (state.error) return html`<${ErrorNote} error=${{ code: "view_failed" }} />`;
  if (!state.view || state.id !== id) return html`<${Loading} />`;
  return html`<${ErrorBoundary} key=${id}><${state.view} params=${params} ha=${ha} /><//>`;
}

// The lib modules take the window explicitly; created lazily so tests and non-browser loads never touch it.
const defaultHa = () => ({
  bridge: createHaBridge({ win: globalThis.window }),
  sync: createThemeSync({ win: globalThis.window }),
});

export function App({ ha, load = loadView }) {
  const tt = useT();
  const route = useHashRoute(IDS, DEFAULT_VIEW);
  const [health, setHealth] = useState(null);
  const [failed, setFailed] = useState(false);
  const [nav, setNav] = useState(() => readNavMode());
  const changeNav = (mode) => {
    if (!NAV_MODES.includes(mode)) return;
    setNav(mode);
    writeNavMode(mode);
  };
  const wiring = useRef(null);
  if (!wiring.current) wiring.current = ha || defaultHa();
  const { bridge, sync } = wiring.current;
  // The info link record travels to the spike view next to bridge and sync.
  if (!wiring.current.infoNav) wiring.current.infoNav = createInfoNav();
  const infoNav = wiring.current.infoNav;

  const refresh = () =>
    get("health").then(
      (data) => {
        setHealth(data);
        setFailed(false);
      },
      () => setFailed(true),
    );
  useEffect(() => {
    refresh();
    if (bridge && typeof bridge.start === "function") bridge.start();
    if (sync && typeof sync.start === "function") sync.start();
    return () => {
      if (sync && typeof sync.dispose === "function") sync.dispose();
      if (bridge && typeof bridge.dispose === "function") bridge.dispose();
    };
  }, []);
  usePoll(refresh, HEALTH_POLL_MS);

  let status = { kind: "muted", text: tt("state.loading") };
  if (failed) status = { kind: "error", text: tt("state.error") };
  else if (health) {
    const raw = String(health.status);
    if (raw === "ok") status = { kind: "ok", text: tt("state.ok") };
    else if (raw === "degraded") status = { kind: "degraded", text: tt("state.degraded") };
    else status = { kind: "warn", text: raw };
  }

  return html`<div>
    <${Topbar} title=${tt("app.title")} status=${status} bridge=${bridge} views=${VIEWS} activeId=${route.id} nav=${nav}
      infoPath=${infoPath(health)} onInfoNavigate=${(via) => infoNav.record(via)}>
      ${health && html`<span class="muted">${tt("app.version", { version: String(health.addon_version) })}</span>`}
      <${ThemeChip} sync=${sync} />
    <//>
    <main>
      <div class="toolbar">
        <label class="hint" for="nav-mode">${tt("demo.nav.mode.label")}</label>
        <select id="nav-mode" value=${nav} onChange=${(ev) => changeNav(ev.target.value)}>
          ${NAV_MODES.map(
            (mode) => html`<option key=${mode} value=${mode} selected=${mode === nav}>${tt(`demo.nav.mode.${mode}`)}</option>`,
          )}
        </select>
      </div>
      <${Guarded} id=${route.id} params=${route.params} ha=${wiring.current} load=${load} />
    </main>
    <${Toasts} />
  </div>`;
}

if (typeof document !== "undefined" && document.getElementById("app")) {
  render(html`<${App} />`, document.getElementById("app"));
}
