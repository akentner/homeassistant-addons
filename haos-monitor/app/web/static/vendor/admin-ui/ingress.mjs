// Helpers for the ingress setting: relative URLs only, stable error keys.
import { buildUrl } from "./api.mjs";

// True when the page runs inside a frame (HA ingress iframe). Never throws.
export function isEmbedded(win = globalThis.window) {
  try {
    return Boolean(win) && Boolean(win.parent) && win.parent !== win;
  } catch {
    return false;
  }
}

// Returns the path unchanged when it is relative, throws otherwise.
export function assertRelative(path) {
  if (typeof path !== "string" || path === "" || path.startsWith("/") || /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(path)) {
    throw new Error(`absolute or empty path rejected: ${path}`);
  }
  return path;
}

// The sanctioned way to build href values for downloads (never concatenate URLs by hand).
export const apiHref = (path, query) => buildUrl(path, query);

const CODE_RE = /^[a-z][a-z0-9_]*$/;

// Maps a backend error to the i18n key errors.<code>; unusable codes give errors.unknown.
export function errorKey(err) {
  const code = err && typeof err.code === "string" ? err.code : "";
  return CODE_RE.test(code) ? `errors.${code}` : "errors.unknown";
}

const TOP_TOKENS = ["allow-top-navigation", "allow-top-navigation-by-user-activation"];
const POPUP_TOKENS = ["allow-popups"];
const RELEVANT_TOKENS = [...TOP_TOKENS, ...POPUP_TOKENS, "allow-popups-to-escape-sandbox"];

// How the page is embedded, from what the page itself can read (never throws).
//   kind: "tab" (no parent), "panel" (the HA bridge answered), "card" (frame with a sandbox attribute, the host did not
//         answer) or "unknown" (framed, host silent, no readable sandbox)
//   sandbox: the navigation relevant tokens of the frame's sandbox attribute, or null when there is none / unreadable
//   topNavigation: "allowed" | "blocked" | "unknown" (frameElement is only readable for a same-origin parent; a sandbox
//   sent as CSP header cannot be seen)
//   popups: true when new windows may be opened (no sandbox, or allow-popups)
export function detectEmbedContext(win = globalThis.window, { bridgeOk = false } = {}) {
  const tab = { kind: "tab", sandbox: null, topNavigation: "allowed", popups: true };
  try {
    if (!win || !win.parent || win.parent === win) return tab;
  } catch {
    return tab;
  }
  let frame = null;
  try {
    frame = win.frameElement || null;
  } catch {
    frame = null;
  }
  let attr = null;
  try {
    attr = frame && typeof frame.getAttribute === "function" ? frame.getAttribute("sandbox") : null;
  } catch {
    attr = null;
  }
  const readable = Boolean(frame);
  const sandboxed = typeof attr === "string";
  const tokens = sandboxed ? attr.split(/\s+/).filter(Boolean) : [];
  const has = (list) => list.some((t) => tokens.includes(t));
  let topNavigation = "unknown";
  if (readable) topNavigation = !sandboxed || has(TOP_TOKENS) ? "allowed" : "blocked";
  let kind = "unknown";
  if (bridgeOk) kind = "panel";
  else if (sandboxed) kind = "card";
  return {
    kind,
    sandbox: sandboxed ? tokens.filter((t) => RELEVANT_TOKENS.includes(t)) : null,
    topNavigation,
    popups: readable ? !sandboxed || has(POPUP_TOKENS) : true,
  };
}

// How a link that leaves the add-on page (to a Home Assistant page) should be offered in this context:
//   "bridge"  the host answers: navigate message first, the anchor is the fallback
//   "same"    plain link in the same window (direct tab)
//   "top"     link targeting the top window
//   "blank"   top navigation is blocked by the sandbox but popups are allowed: a new tab
//   "hidden"  neither works: offer nothing (a click would only produce a console error)
export function infoLinkPlan(context) {
  const ctx = context || {};
  if (ctx.kind === "panel") return "bridge";
  if (ctx.kind === "tab") return "same";
  if (ctx.topNavigation === "blocked") return ctx.popups ? "blank" : "hidden";
  return "top";
}
