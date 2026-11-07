// Shell on the admin-ui lib: Topbar with the navigation in the bar, hash routing, lazy views, health poll, toasts and the
// optional HA wiring (bridge + theme sync, progressive enhancement only: nothing depends on them, D-10).
// Relative URLs only (the page lives below an ingress path); the lib is imported through its public modules only.
import { html, render, useState, useEffect, useRef, usePoll, ErrorNote, Loading, Toasts } from "./vendor/admin-ui/ui.mjs";
import { Topbar, ErrorBoundary, useHashRoute } from "./vendor/admin-ui/shell.mjs";
import { registerStrings, useT, useLang } from "./vendor/admin-ui/i18n.mjs";
import { get } from "./vendor/admin-ui/api.mjs";
import { createHaBridge } from "./vendor/admin-ui/ha-bridge.mjs";
import { createThemeSync } from "./vendor/admin-ui/theme-sync.mjs";
import de from "./strings.de.mjs";
import en from "./strings.en.mjs";

registerStrings({ de, en });

// Icons are Material Design Icons path data (24x24), decorative next to the visible label.
export const VIEWS = [
  { id: "users", titleKey: "view.users", icon: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2h14M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8m11 18v-2a6 6 0 0 0-3-5.2V21h3M16 3v8a4 4 0 0 0 0-8Z" },
  { id: "acl", titleKey: "view.acl", icon: "M12,1L3,5V11C3,16.55 6.84,21.74 12,23C17.16,21.74 21,16.55 21,11V5L12,1M12,7C13.4,7 14.8,8.1 14.8,9.5V11C15.4,11 16,11.6 16,12.3V15.8C16,16.4 15.4,17 14.7,17H9.2C8.6,17 8,16.4 8,15.7V12.2C8,11.6 8.6,11 9.2,11V9.5C9.2,8.1 10.6,7 12,7M12,8.2C11.2,8.2 10.5,8.7 10.5,9.5V11H13.5V9.5C13.5,8.7 12.8,8.2 12,8.2Z" },
  { id: "matrix", titleKey: "view.matrix", icon: "M4,3H20A2,2 0 0,1 22,5V20A2,2 0 0,1 20,22H4A2,2 0 0,1 2,20V5A2,2 0 0,1 4,3M4,7V10H8V7H4M10,7V10H14V7H10M20,10V7H16V10H20M4,12V15H8V12H4M4,20H8V17H4V20M10,12V15H14V12H10M10,20H14V17H10V20M20,20V17H16V20H20M20,12H16V15H20V12Z" },
  { id: "tokens", titleKey: "view.tokens", icon: "M22,18V22H18V19H15V16H12L9.74,13.74C9.19,13.91 8.61,14 8,14A6,6 0 0,1 2,8A6,6 0 0,1 8,2A6,6 0 0,1 14,8C14,8.61 13.91,9.19 13.74,9.74L22,18M7,5A2,2 0 0,0 5,7A2,2 0 0,0 7,9A2,2 0 0,0 9,7A2,2 0 0,0 7,5Z" },
  { id: "tools", titleKey: "view.tools", icon: "M22.7,19L13.6,9.9C14.5,7.6 14,4.9 12.1,3C10.1,1 7.1,0.6 4.7,1.7L9,6L6,9L1.6,4.7C0.4,7.1 0.9,10.1 2.9,12.1C4.8,14 7.5,14.5 9.8,13.6L18.9,22.7C19.3,23.1 19.9,23.1 20.3,22.7L22.6,20.4C23.1,20 23.1,19.3 22.7,19Z" },
];
const IDS = VIEWS.map((v) => v.id);
const DEFAULT_VIEW = "users";
const HEALTH_POLL_MS = 15000;

const cache = new Map();
// The id is always validated against VIEWS by useHashRoute before it gets here. The literal relative prefix keeps the
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

function Guarded({ id, params, load }) {
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
  return html`<${ErrorBoundary} key=${id}><${state.view} params=${params} /><//>`;
}

// The lib modules take the window explicitly; built lazily and defensively so tests and odd embeddings never break
// the page: any failure just means no bridge and no theme sync.
function defaultHa() {
  const ha = {};
  try {
    ha.bridge = createHaBridge({ win: globalThis.window });
  } catch {
    // no bridge
  }
  try {
    ha.sync = createThemeSync({ win: globalThis.window });
  } catch {
    // no theme sync
  }
  return ha;
}

const safely = (fn) => {
  try {
    fn();
  } catch {
    // progressive enhancement: a failing HA helper must never break the page
  }
};

// HA's info page of this add-on (its settings live there); the slug comes from api/health, unknown means no link.
// Since HA 2026.2 the frontend route is /config/app/<slug>/config (the settings tab; /info is the overview).
export function infoPath(health) {
  const slug = health && typeof health.addon_slug === "string" ? health.addon_slug : "";
  return /^[a-z0-9][a-z0-9_]{0,63}$/.test(slug) ? `/config/app/${slug}/config` : null;
}

// "2.37.2-6" -> "2.37.2": the subpatch counts add-on-only fixes; anything that is not a version shows nothing.
export function semver(raw) {
  const match = /^(\d+\.\d+\.\d+)(?:-[\w.]+)?$/.exec(typeof raw === "string" ? raw : "");
  return match ? match[1] : "";
}

// The health and data pages were merged into tools: old bookmarks (#/health, #/data) land there instead of on users.
export function migrateLegacyHash(loc = globalThis.location) {
  const match = /^#\/?(?:health|data)(\?.*)?$/.exec(loc && typeof loc.hash === "string" ? loc.hash : "");
  if (match) loc.hash = `#/tools${match[1] || ""}`;
}

export function App({ ha, load = loadView }) {
  const tt = useT();
  const lang = useLang();
  migrateLegacyHash();
  const route = useHashRoute(IDS, DEFAULT_VIEW);
  const [health, setHealth] = useState(null);
  const [failed, setFailed] = useState(false);
  const wiring = useRef(null);
  if (!wiring.current) wiring.current = ha || defaultHa();
  const { bridge, sync } = wiring.current;

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
    if (bridge && typeof bridge.start === "function") safely(() => bridge.start());
    if (sync && typeof sync.start === "function") safely(() => sync.start());
    return () => {
      if (sync && typeof sync.dispose === "function") safely(() => sync.dispose());
      if (bridge && typeof bridge.dispose === "function") safely(() => bridge.dispose());
    };
  }, []);
  usePoll(refresh, HEALTH_POLL_MS);
  useEffect(() => {
    if (typeof document !== "undefined" && document.documentElement) document.documentElement.lang = lang;
  }, [lang]);

  let status = { kind: "muted", text: tt("state.loading") };
  if (failed) status = { kind: "error", text: tt("state.error") };
  else if (health) {
    const raw = String(health.status);
    if (raw === "ok") status = { kind: "ok", text: tt("state.ok") };
    else if (raw === "degraded") status = { kind: "degraded", text: tt("state.degraded") };
    else status = { kind: "warn", text: raw };
  }
  const dbError = health && health.db && typeof health.db.error === "string" ? health.db.error : "";

  return html`<div>
    <${Topbar} title=${tt("app.title")} status=${status} bridge=${bridge} views=${VIEWS} activeId=${route.id} nav="topbar" infoPath=${infoPath(health)} showLang=${false}
      version=${semver(health && health.addon_version)} />
    <main>
      ${health &&
      health.status === "degraded" &&
      html`<div class="notice error" role="alert">
        ${tt("app.degraded")}${dbError && html` <span class="muted">${dbError}</span>`}
      </div>`}
      <${Guarded} id=${route.id} params=${route.params} load=${load} />
    </main>
    <${Toasts} />
  </div>`;
}

if (typeof document !== "undefined" && document.getElementById("app")) {
  render(html`<${App} />`, document.getElementById("app"));
}
