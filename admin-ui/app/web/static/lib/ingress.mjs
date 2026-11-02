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
