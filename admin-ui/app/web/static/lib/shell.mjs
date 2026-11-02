// App shell pieces: topbar, language switch, tab navigation, error boundary and hash routing. The HA bridge is
// never imported here: apps pass its store as the `bridge` prop (getState/subscribe/toggleMenu).
import { html, useState, useEffect, useLayoutEffect, useRef, useErrorBoundary } from "./vendor/preact-htm.mjs";
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

const DEFAULT_ICON = "./icon";
const NAV_MODES = ["topbar", "tabs"];
let menuSeq = 0;

// Collapse the inline navigation into the burger menu when it does not fit its slot. Unknown sizes never collapse.
export const needsBurger = (needed, available) =>
  Number.isFinite(needed) && Number.isFinite(available) && needed > 0 && available > 0 && needed > available;

const viewTitle = (tt, view) => (view.titleKey ? tt(view.titleKey) : view.title);
const inside = (root, node) => {
  for (let cur = node; cur; cur = cur.parentNode) if (cur === root) return true;
  return false;
};

// Bridge insets are validated numbers with an optional px suffix; negative values count as 0.
function insetStyle(key) {
  if (!key) return undefined;
  const [top, right, bottom, left] = key.split("|");
  return { "--safe-top": top, "--safe-right": right, "--safe-bottom": bottom, "--safe-left": left };
}
function insetKey(insets) {
  if (!insets || typeof insets !== "object") return "";
  const px = (v) => `${Math.max(0, parseFloat(v) || 0)}px`;
  return [insets.top, insets.right, insets.bottom, insets.left].map(px).join("|");
}

// Navigation inside the topbar. The inline links stay mounted (hidden when collapsed) so their natural width can be
// measured against the slot width, which does not depend on the collapsed state: no flicker, no oscillation.
function TopbarNav({ views, activeId, label, kiosk }) {
  const tt = useT();
  const lang = useLang();
  const wrap = useRef(null);
  const inline = useRef(null);
  const button = useRef(null);
  const menuId = useRef(null);
  if (!menuId.current) menuId.current = `topnav-menu-${++menuSeq}`;
  const [collapsed, setCollapsed] = useState(false);
  const [open, setOpen] = useState(false);
  const titles = views.map((v) => viewTitle(tt, v));
  const sig = `${lang}\n${titles.join("\n")}`;

  const measure = () => {
    const box = wrap.current;
    const links = inline.current;
    if (!box || !links) return;
    setCollapsed(needsBurger(links.scrollWidth, box.clientWidth));
  };
  useLayoutEffect(measure, [sig, kiosk]);
  useEffect(() => {
    const box = wrap.current;
    const Observer = globalThis.ResizeObserver;
    if (box && typeof Observer === "function") {
      const ro = new Observer(measure);
      ro.observe(box);
      return () => ro.disconnect();
    }
    const win = globalThis.window;
    if (!win || typeof win.addEventListener !== "function") return undefined;
    win.addEventListener("resize", measure);
    return () => win.removeEventListener("resize", measure);
  }, []);

  useEffect(() => setOpen(false), [activeId, collapsed]);
  useEffect(() => {
    const doc = globalThis.document;
    if (!open || !doc || typeof doc.addEventListener !== "function") return undefined;
    const onDown = (ev) => {
      if (!inside(wrap.current, ev.target)) setOpen(false);
    };
    doc.addEventListener("pointerdown", onDown);
    return () => doc.removeEventListener("pointerdown", onDown);
  }, [open]);

  const close = (refocus) => {
    setOpen(false);
    if (refocus && button.current && typeof button.current.focus === "function") button.current.focus();
  };
  const onKeyDown = (ev) => {
    if (open && ev.key === "Escape") {
      if (typeof ev.stopPropagation === "function") ev.stopPropagation();
      close(true);
    }
  };
  const onFocusOut = (ev) => {
    const next = ev.relatedTarget;
    if (open && next && !inside(wrap.current, next)) setOpen(false);
  };

  const activeIdx = views.findIndex((v) => v.id === activeId);
  const active = activeIdx >= 0 ? titles[activeIdx] : "";
  const links = (cls) =>
    views.map(
      (view, i) => html`<a
        key=${view.id}
        class=${`${cls}${view.id === activeId ? " active" : ""}`}
        href=${`#/${view.id}`}
        aria-current=${view.id === activeId ? "page" : null}
        onClick=${() => setOpen(false)}
      >
        ${titles[i]}
      </a>`,
    );
  // In kiosk mode the host's own sidebar button is on screen: the nav trigger then shows the current view so the two
  // never look alike.
  const burgerLabel = kiosk && active ? tt("nav.menu_current", { title: active }) : tt("nav.menu");
  return html`<div class="topnav" ref=${wrap} onKeyDown=${onKeyDown} onFocusOut=${onFocusOut}>
    <div class="topnav-slot">
      <nav class=${`topnav-inline${collapsed ? " is-collapsed" : ""}`} ref=${inline} aria-label=${label || tt("nav.label")}>
        ${links("topnav-link")}
      </nav>
    </div>
    ${collapsed &&
    html`<button
      class=${`menu-btn nav-burger${kiosk ? " with-title" : ""}`}
      type="button"
      ref=${button}
      aria-label=${burgerLabel}
      aria-expanded=${open ? "true" : "false"}
      aria-controls=${menuId.current}
      onClick=${() => setOpen(!open)}
    >
      ${kiosk && active ? `${active} ▾` : "☰"}
    </button>`}
    ${collapsed &&
    open &&
    html`<div class="topnav-menu" id=${menuId.current} role="group" aria-label=${label || tt("nav.label")}>
      ${links("topnav-menu-link")}
    </div>`}
  </div>`;
}

// status: {kind, text}. iconSrc defaults to the add-on icon route "./icon" (null/"" turns it off; a load error hides it).
// With `views`, `nav` picks where the navigation goes: "tabs" (default: tab bar below the bar) or "topbar" (links in
// the bar between name and status, folding into a burger menu when too narrow). The whole head is sticky.
// The menu button only shows while the bridge reports a requested kiosk mode.
export function Topbar({ title, iconSrc, status, bridge, children, views, activeId, nav, navLabel }) {
  const tt = useT();
  const [iconOk, setIconOk] = useState(true);
  const [kiosk, setKiosk] = useState(() => Boolean(bridge && bridge.getState().kiosk === true));
  const [safe, setSafe] = useState(() => (bridge ? insetKey(bridge.getState().safeAreaInsets) : ""));
  useEffect(() => {
    if (!bridge) {
      setKiosk(false);
      setSafe("");
      return undefined;
    }
    const sync = () => {
      const state = bridge.getState();
      setKiosk(state.kiosk === true);
      setSafe(insetKey(state.safeAreaInsets));
    };
    sync();
    const off = bridge.subscribe(sync);
    return () => typeof off === "function" && off();
  }, [bridge]);
  const icon = iconSrc === undefined ? DEFAULT_ICON : iconSrc;
  const list = Array.isArray(views) ? views : [];
  const mode = NAV_MODES.includes(nav) ? nav : "tabs";
  const inBar = mode === "topbar" && list.length > 0;
  return html`<div class="shell-head" style=${insetStyle(safe)}>
    <header class=${`topbar${inBar ? " topbar-nav" : ""}`}>
      ${kiosk &&
      html`<button class="menu-btn" type="button" aria-label=${tt("btn.menu")} onClick=${() => bridge.toggleMenu()}>
        ☰
      </button>`}
      ${icon &&
      iconOk &&
      html`<img class="brand-icon" alt="" width="28" height="28" src=${icon} onError=${() => setIconOk(false)} />`}
      <h1>${title}</h1>
      ${inBar && html`<${TopbarNav} views=${list} activeId=${activeId} label=${navLabel} kiosk=${kiosk} />`}
      ${status && html`<${Badge} kind=${status.kind}>${status.text}<//>`} ${children}
      <${LangSwitch} />
    </header>
    ${mode === "tabs" && list.length > 0 && html`<${TabNav} views=${list} activeId=${activeId} label=${navLabel} />`}
  </div>`;
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
