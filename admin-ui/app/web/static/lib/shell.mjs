// App shell pieces: topbar, language switch, tab navigation, error boundary and hash routing. The HA bridge is
// never imported here: apps pass its store as the `bridge` prop (getState/subscribe/toggleMenu).
import { html, useState, useEffect, useErrorBoundary } from "./vendor/preact-htm.mjs";
import { Badge, ErrorNote } from "./ui.mjs";
import { LANGS, setLang, useLang, useT } from "./i18n.mjs";

const LANG_KEYS = { de: "lang.de", en: "lang.en" };

// "#/users?x=1&y=a%20b" -> {id: "users", params: {x: "1", y: "a b"}}; unknown ids fall back to defaultId.
export function parseHash(hash, ids, defaultId) {
  const known = Array.isArray(ids) ? ids : [];
  const fallback = defaultId !== undefined ? defaultId : known[0];
  const raw = typeof hash === "string" ? hash.replace(/^#\/?/, "") : "";
  const cut = raw.indexOf("?");
  const path = cut < 0 ? raw : raw.slice(0, cut);
  const query = cut < 0 ? "" : raw.slice(cut + 1);
  const params = {};
  for (const part of query.split("&")) {
    if (!part) continue;
    const eq = part.indexOf("=");
    const k = eq < 0 ? part : part.slice(0, eq);
    const v = eq < 0 ? "" : part.slice(eq + 1);
    try {
      params[decodeURIComponent(k.replace(/\+/g, " "))] = decodeURIComponent(v.replace(/\+/g, " "));
    } catch {
      // ignore malformed escapes
    }
  }
  return { id: known.includes(path) ? path : fallback, params };
}

export function useHashRoute(ids, defaultId) {
  const read = () => parseHash(globalThis.location ? globalThis.location.hash : "", ids, defaultId);
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const win = globalThis.window;
    if (!win || typeof win.addEventListener !== "function") return undefined;
    const onHash = () => setRoute(read());
    win.addEventListener("hashchange", onHash);
    return () => win.removeEventListener("hashchange", onHash);
  }, [ids.join("\n"), defaultId]);
  return route;
}

export function LangSwitch() {
  const tt = useT();
  const lang = useLang();
  return html`<select
    class="lang-switch"
    aria-label=${tt("lang.label")}
    value=${lang}
    onChange=${(ev) => setLang(ev.target.value)}
  >
    ${LANGS.map(
      (code) => html`<option key=${code} value=${code} selected=${code === lang}>${tt(LANG_KEYS[code])}</option>`,
    )}
  </select>`;
}

// status: {kind, text}. The menu button only shows while the bridge reports a requested kiosk mode.
export function Topbar({ title, iconSrc, status, bridge, children }) {
  const tt = useT();
  const [iconOk, setIconOk] = useState(true);
  const [kiosk, setKiosk] = useState(() => Boolean(bridge && bridge.getState().kiosk === true));
  useEffect(() => {
    if (!bridge) {
      setKiosk(false);
      return undefined;
    }
    const sync = () => setKiosk(bridge.getState().kiosk === true);
    sync();
    const off = bridge.subscribe(sync);
    return () => typeof off === "function" && off();
  }, [bridge]);
  return html`<header class="topbar">
    ${kiosk &&
    html`<button class="menu-btn" type="button" aria-label=${tt("btn.menu")} onClick=${() => bridge.toggleMenu()}>
      ☰
    </button>`}
    ${iconSrc &&
    iconOk &&
    html`<img class="brand-icon" alt="" width="28" height="28" src=${iconSrc} onError=${() => setIconOk(false)} />`}
    <h1>${title}</h1>
    ${status && html`<${Badge} kind=${status.kind}>${status.text}<//>`} ${children}
    <${LangSwitch} />
  </header>`;
}

// views: [{id, title | titleKey}]; links are fixed "#/<id>" routes.
export function TabNav({ views, activeId, label }) {
  const tt = useT();
  return html`<nav class="tabs" aria-label=${label || tt("nav.label")}>
    ${views.map(
      (view) => html`<a
        key=${view.id}
        class=${`tab${view.id === activeId ? " active" : ""}`}
        href=${`#/${view.id}`}
        aria-current=${view.id === activeId ? "page" : null}
      >
        ${view.titleKey ? tt(view.titleKey) : view.title}
      </a>`,
    )}
  </nav>`;
}

// A child that throws while rendering is replaced by a localized error note; siblings keep rendering.
export function ErrorBoundary({ children }) {
  const [error, reset] = useErrorBoundary();
  if (error) return html`<${ErrorNote} error=${{ code: "render_failed" }} onRetry=${reset} />`;
  return children;
}
