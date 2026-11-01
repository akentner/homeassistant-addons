// Shell: hash router, tabs, lazy view loader, health poll. Relative URLs only (page lives below an ingress path).
import { html, render, useState, useEffect, Toasts, ErrorNote, Loading, Badge, usePoll } from "./lib/ui.mjs";
import { get } from "./lib/api.mjs";
import { useErrorBoundary } from "./vendor/preact-htm.mjs";

export const VIEWS = [
  { id: "users", title: "Users" },
  { id: "acl", title: "ACL rules" },
  { id: "matrix", title: "Matrix" },
  { id: "tokens", title: "Tokens" },
  { id: "tools", title: "Tools" },
  { id: "health", title: "Health" },
  { id: "data", title: "Export & backups" },
];

export function parseHash(hash) {
  const raw = String(hash || "").replace(/^#\/?/, "");
  const [path, query = ""] = raw.split("?");
  const id = VIEWS.some((v) => v.id === path) ? path : "users";
  const params = {};
  for (const part of query.split("&")) {
    if (!part) continue;
    const [k, v = ""] = part.split("=");
    try {
      params[decodeURIComponent(k)] = decodeURIComponent(v.replace(/\+/g, " "));
    } catch {
      // ignore malformed escapes
    }
  }
  return { id, params };
}

const cache = new Map();
const loadView = (id) => {
  if (!cache.has(id)) {
    // Literal-prefixed relative path keeps the import analyzable and below the ingress path.
    cache.set(
      id,
      import(`./views/${id}.mjs`).catch((err) => {
        cache.delete(id);
        throw err;
      }),
    );
  }
  return cache.get(id);
};

// Error boundary as a hook-free wrapper around a view component.
function Guarded({ id, params }) {
  const [state, setState] = useState({ view: null, error: null });
  useEffect(() => {
    let live = true;
    setState({ view: null, error: null });
    loadView(id).then(
      (mod) => live && setState({ view: mod.default, error: null }),
      (error) => live && setState({ view: null, error }),
    );
    return () => {
      live = false;
    };
  }, [id]);
  if (state.error)
    return html`<${ErrorNote} error=${{ code: "view_failed", message: String(state.error.message || state.error) }} />`;
  if (!state.view) return html`<${Loading} />`;
  return html`<${Boundary} key=${id}><${state.view} params=${params} /><//>`;
}

function Boundary({ children }) {
  const [error] = useErrorBoundary();
  if (error) return html`<${ErrorNote} error=${{ code: "render_failed", message: String(error.message || error) }} />`;
  return children;
}

export function App() {
  const [route, setRoute] = useState(() => parseHash(globalThis.location ? location.hash : ""));
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState(null);
  const [iconOk, setIconOk] = useState(true);
  const load = () =>
    get("health").then(
      (h) => {
        setHealth(h);
        setHealthError(null);
      },
      (e) => setHealthError(e),
    );
  useEffect(() => {
    const onHash = () => setRoute(parseHash(location.hash));
    window.addEventListener("hashchange", onHash);
    load();
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  usePoll(load, 15000);
  const status = healthError ? "error" : health ? health.status : "loading";
  return html`<div>
    <header class="topbar">
      ${iconOk &&
      html`<img class="brand-icon" alt="" width="28" height="28" src="./icon" onError=${() => setIconOk(false)} />`}
      <h1>ntfy</h1>
      <${Badge} kind=${status === "ok" ? "ok" : status === "loading" ? "muted" : status}>${status}<//>
      ${health && html`<span class="muted">add-on ${health.addon_version}</span>`}
    </header>
    <nav class="tabs">
      ${VIEWS.map(
        (v) =>
          html`<a key=${v.id} class=${`tab${route.id === v.id ? " active" : ""}`} href=${`#/${v.id}`}>${v.title}</a>`,
      )}
    </nav>
    <main>
      ${health &&
      health.status === "degraded" &&
      html`<div class="notice error">Degraded: ${(health.db && health.db.error) || "auth database unusable"}</div>`}
      <${Guarded} id=${route.id} params=${route.params} />
    </main>
    <${Toasts} />
  </div>`;
}

if (typeof document !== "undefined" && document.getElementById("app")) {
  // The static header of index.html is replaced by the one rendered here.
  const root = document.getElementById("app");
  const stale = document.querySelector("body > header.topbar");
  if (stale) stale.remove();
  render(html`<${App} />`, root);
}
