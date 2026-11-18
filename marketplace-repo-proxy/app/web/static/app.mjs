// Shell on the admin-ui lib: Topbar with the navigation in the bar, hash routing, lazy views, the add-on version from
// api/meta and the optional HA wiring (bridge + theme sync, progressive enhancement only, R-13).
// Relative URLs only (the page lives below an ingress path); the lib is imported through its public modules only.
import { html, render, useState, useEffect, useRef, useAsync, ErrorNote, Loading, Toasts } from "./vendor/admin-ui/ui.mjs";
import { Topbar, ErrorBoundary, useHashRoute } from "./vendor/admin-ui/shell.mjs";
import { registerStrings, useT, useLang } from "./vendor/admin-ui/i18n.mjs";
import { get } from "./vendor/admin-ui/api.mjs";
import { createHaBridge } from "./vendor/admin-ui/ha-bridge.mjs";
import { createThemeSync } from "./vendor/admin-ui/theme-sync.mjs";
import de from "./strings.de.mjs";
import en from "./strings.en.mjs";

registerStrings({ de, en });

export const VIEWS = [
  { id: "repositories", titleKey: "view.repositories" },
  { id: "access", titleKey: "view.access" },
];
const IDS = VIEWS.map((v) => v.id);
const DEFAULT_VIEW = "repositories";

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

export function App({ ha, load = loadView }) {
  const tt = useT();
  const lang = useLang();
  const route = useHashRoute(IDS, DEFAULT_VIEW);
  // The full add-on version from the image build (D-30); null or a failed request leaves the version out.
  const meta = useAsync(() => get("meta"), []);
  const wiring = useRef(null);
  if (!wiring.current) wiring.current = ha || defaultHa();
  const { bridge, sync } = wiring.current;

  useEffect(() => {
    if (bridge && typeof bridge.start === "function") safely(() => bridge.start());
    if (sync && typeof sync.start === "function") safely(() => sync.start());
    return () => {
      if (sync && typeof sync.dispose === "function") safely(() => sync.dispose());
      if (bridge && typeof bridge.dispose === "function") safely(() => bridge.dispose());
    };
  }, []);
  useEffect(() => {
    if (typeof document !== "undefined" && document.documentElement) document.documentElement.lang = lang;
  }, [lang]);

  return html`<div>
    <${Topbar} title=${tt("app.title")} bridge=${bridge} views=${VIEWS} activeId=${route.id} nav="topbar" iconSrc=${null}
      version=${meta.data && meta.data.version} />
    <main>
      <${Guarded} id=${route.id} params=${route.params} load=${load} />
    </main>
    <${Toasts} />
  </div>`;
}

if (typeof document !== "undefined" && document.getElementById("app")) {
  render(html`<${App} />`, document.getElementById("app"));
}
