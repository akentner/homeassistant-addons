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

export const VIEWS = [
  { id: "users", titleKey: "view.users", icon: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2h14M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8m11 18v-2a6 6 0 0 0-3-5.2V21h3M16 3v8a4 4 0 0 0 0-8Z" },
  { id: "acl", titleKey: "view.acl" },
  { id: "matrix", titleKey: "view.matrix" },
  { id: "tokens", titleKey: "view.tokens" },
  { id: "tools", titleKey: "view.tools" },
  { id: "health", titleKey: "view.health" },
  { id: "data", titleKey: "view.data" },
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

export function App({ ha, load = loadView }) {
  const tt = useT();
  const lang = useLang();
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
