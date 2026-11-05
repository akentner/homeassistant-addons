// App shell pieces: topbar, language switch, tab navigation, error boundary and hash routing. The HA bridge is
// never imported here: apps pass its store as the `bridge` prop (getState/subscribe/toggleMenu).
import { html, useState, useEffect, useLayoutEffect, useRef, useErrorBoundary } from "./vendor/preact-htm.mjs";
import { Badge, ErrorNote } from "./ui.mjs";
import { LANGS, setLang, useLang, useT } from "./i18n.mjs";
import { detectEmbedContext, infoLinkPlan } from "./ingress.mjs";

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
// An absolute path on the HA origin ("/config/app/<slug>/info"): no scheme, no protocol-relative form.
const isInfoPath = (path) => typeof path === "string" && /^\/[A-Za-z0-9._~\-/]{1,200}$/.test(path) && !path.startsWith("//");
// Plain text only (a release such as "0.7.3-0"); anything else is not shown.
const isVersion = (v) => typeof v === "string" && /^[A-Za-z0-9._+-]{1,32}$/.test(v);
const NAV_MODES = ["topbar", "tabs"];
const MENU_PATH = "M3 6h18v2H3V6m0 5h18v2H3v-2m0 5h18v2H3v-2Z";
const INFO_PATH = "M11 17h2v-6h-2v6m0-8h2V7h-2v2m1-7a10 10 0 1 0 0 20 10 10 0 0 0 0-20m0 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16Z";
let menuSeq = 0;

// Collapse the inline navigation into the burger menu when it does not fit its slot (a zero-width slot collapses too).
// Unknown sizes never collapse.
export const needsBurger = (needed, available) =>
  Number.isFinite(needed) && Number.isFinite(available) && needed > 0 && available >= 0 && needed > available;

// Optional trusted SVG path data, e.g. an MDI path. Labels remain visible; icons are decorative.
function NavIcon({ path }) {
  return typeof path === "string" && path.trim()
    ? html`<svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d=${path} /></svg>`
    : null;
}

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
function TopbarNav({ views, activeId, label, kiosk, info, onCollapse }) {
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
  const sig = `${lang}\n${titles.join("\n")}\n${views.map((v) => v.icon || "").join("\n")}`;

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
    if (typeof onCollapse === "function") onCollapse(collapsed);
  }, [collapsed]);
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
        ${view.icon && html`<${NavIcon} path=${view.icon} />`}${titles[i]}
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
      ${kiosk && active ? `${active} ▾` : html`<${NavIcon} path=${MENU_PATH} />`}
    </button>`}
    ${collapsed &&
    open &&
    html`<div class="topnav-menu" id=${menuId.current} role="group" aria-label=${label || tt("nav.label")}>
      ${links("topnav-menu-link")}
      ${info &&
      html`<a class="topnav-menu-link info-link" href=${info.href} target=${info.target} rel=${info.rel} onClick=${(ev) => {
        setOpen(false);
        info.onClick(ev);
      }}>
        ${tt("nav.info")}
      </a>`}
    </div>`}
  </div>`;
}

// status: {kind, text}. iconSrc defaults to the add-on icon route "./icon" (null/"" turns it off; a load error hides it).
// With `views`, `nav` picks where the navigation goes: "tabs" (default: tab bar below the bar) or "topbar" (links in
// the bar between name and status, folding into a burger menu when too narrow). The whole head is sticky.
// The menu button only shows while the bridge reports a requested kiosk mode.
// infoPath ("/config/app/<slug>/info") adds an info link: icon in the bar, or an entry in the burger menu once the
// navigation folds. onInfoNavigate("bridge" | "fallback" | "new_tab") reports which path a click took.
// showLang={false} leaves the language switch out (default true). version (a short string such as "0.7.3-0") shows
// as plain text after the status badge; right-aligned order is: info icon, badge, version, [children], language switch.
export function Topbar({ title, iconSrc, status, bridge, children, views, activeId, nav, navLabel, infoPath, onInfoNavigate, showLang = true, version }) {
  const tt = useT();
  const [iconOk, setIconOk] = useState(true);
  const [kiosk, setKiosk] = useState(() => Boolean(bridge && bridge.getState().kiosk === true));
  const [safe, setSafe] = useState(() => (bridge ? insetKey(bridge.getState().safeAreaInsets) : ""));
  const [bridgeOk, setBridgeOk] = useState(() => Boolean(bridge && bridge.getState().status === "ok"));
  useEffect(() => {
    if (!bridge) {
      setKiosk(false);
      setSafe("");
      setBridgeOk(false);
      return undefined;
    }
    const sync = () => {
      const state = bridge.getState();
      setKiosk(state.kiosk === true);
      setSafe(insetKey(state.safeAreaInsets));
      setBridgeOk(state.status === "ok");
    };
    sync();
    const off = bridge.subscribe(sync);
    return () => typeof off === "function" && off();
  }, [bridge]);
  const [navCollapsed, setNavCollapsed] = useState(false);
  // How the link is offered depends on the embedding (see infoLinkPlan): bridge first inside HA's own app panel, a
  // top-window link in a plain frame, a new tab when the sandbox blocks top navigation but allows popups, and no link at
  // all when neither works (a click would only log a console error). HA never confirms navigate, so only the chosen
  // path is reported, not a success.
  const plan = infoLinkPlan(detectEmbedContext(globalThis.window, { bridgeOk }));
  const info =
    isInfoPath(infoPath) && plan !== "hidden"
      ? {
          href: infoPath,
          target: plan === "same" ? "_self" : plan === "blank" ? "_blank" : "_top",
          rel: plan === "blank" ? "noopener noreferrer" : "noopener",
          onClick: (ev) => {
            let via = plan === "blank" ? "new_tab" : "fallback";
            try {
              if (bridge && bridge.getState().status === "ok" && bridge.navigate(infoPath) === true) {
                ev.preventDefault();
                via = "bridge";
              }
            } catch {
              // keep the plain link
            }
            if (typeof onInfoNavigate === "function") onInfoNavigate(via);
          },
        }
      : null;
  const icon = iconSrc === undefined ? DEFAULT_ICON : iconSrc;
  const list = Array.isArray(views) ? views : [];
  const mode = NAV_MODES.includes(nav) ? nav : "tabs";
  const inBar = mode === "topbar" && list.length > 0;
  return html`<div class="shell-head" style=${insetStyle(safe)}>
    <header class=${`topbar${inBar ? " topbar-nav" : ""}`}>
      ${kiosk &&
      html`<button class="menu-btn" type="button" aria-label=${tt("btn.menu")} onClick=${() => bridge.toggleMenu()}>
        <${NavIcon} path=${MENU_PATH} />
      </button>`}
      ${icon &&
      iconOk &&
      html`<img class="brand-icon" alt="" width="28" height="28" src=${icon} onError=${() => setIconOk(false)} />`}
      <h1>${title}</h1>
      ${inBar && html`<${TopbarNav} views=${list} activeId=${activeId} label=${navLabel} kiosk=${kiosk} info=${info} onCollapse=${setNavCollapsed} />`}
      ${info &&
      !(inBar && navCollapsed) &&
      html`<a class="info-btn" href=${info.href} target=${info.target} rel=${info.rel} aria-label=${tt("nav.info")} title=${tt("nav.info")} onClick=${info.onClick}><${NavIcon} path=${INFO_PATH} /></a>`}
      ${status && html`<${Badge} kind=${status.kind}>${status.text}<//>`}
      ${isVersion(version) && html`<span class="topbar-version">${version}</span>`}
      ${children && html`<span class="topbar-extra">${children}</span>`}
      ${showLang !== false && html`<${LangSwitch} />`}
    </header>
    ${mode === "tabs" && list.length > 0 && html`<${TabNav} views=${list} activeId=${activeId} label=${navLabel} />`}
  </div>`;
}

// views: [{id, title | titleKey, icon? (SVG path data)}]; links are fixed "#/<id>" routes.
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
        ${view.icon && html`<${NavIcon} path=${view.icon} />`}${view.titleKey ? tt(view.titleKey) : view.title}
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
