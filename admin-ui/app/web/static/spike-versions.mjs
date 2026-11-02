// Demo-local version detection for the live spike (S15). Read-only and guarded: every probe returns a short, validated
// string or null, never a URL, host name or token. The HA frontend version is deliberately NOT detected: the HA
// frontend only knows it as the build-time constant `__VERSION__` (ha-config-info.ts), there is no runtime property.

const VERSION_RE = /^[0-9A-Za-z][0-9A-Za-z.+_-]{0,29}$/;
const BRAND_RE = /^[A-Za-z][A-Za-z0-9 ._-]{0,30}$/;
const FALLBACKS = [
  ["Edge", /Edg\/(\d[\d.]*)/],
  ["Opera", /OPR\/(\d[\d.]*)/],
  ["Firefox", /Firefox\/(\d[\d.]*)/],
  ["Chrome", /(?:Chrome|CriOS)\/(\d[\d.]*)/],
  ["Safari", /Version\/(\d[\d.]*).*Safari/],
];

export const cleanVersion = (value) => (typeof value === "string" && VERSION_RE.test(value.trim()) ? value.trim() : null);

// HA core version from the same-origin parent (ha-panel-app embeds the page); null when the parent is not readable.
export function readCoreVersion(win = globalThis.window) {
  try {
    if (!win || win.parent === win) return null;
    return cleanVersion(win.parent.document.querySelector("home-assistant").hass.config.version);
  } catch {
    return null;
  }
}

// "Mozilla/5.0 ... Chrome/156.0.8078.48 Safari/537.36" -> "Chrome 156.0.8078.48"; unknown strings give null.
export function parseUserAgent(ua) {
  if (typeof ua !== "string") return null;
  for (const [name, re] of FALLBACKS) {
    const m = re.exec(ua);
    if (m) return `${name} ${m[1]}`.slice(0, 60);
  }
  return null;
}

// Client hints first (full version list), then the user agent string; null when neither gives a usable name.
export async function detectBrowser(nav = globalThis.navigator) {
  try {
    const data = nav && nav.userAgentData;
    if (data && typeof data.getHighEntropyValues === "function") {
      const { fullVersionList } = await data.getHighEntropyValues(["fullVersionList"]);
      const usable = (Array.isArray(fullVersionList) ? fullVersionList : []).filter(
        (b) => b && BRAND_RE.test(String(b.brand)) && !/not.?a.?brand/i.test(b.brand) && cleanVersion(b.version),
      );
      const pick = usable.find((b) => b.brand !== "Chromium") || usable[0];
      if (pick) return `${pick.brand} ${pick.version}`;
    }
  } catch {
    // fall through to the user agent string
  }
  try {
    return parseUserAgent(nav && nav.userAgent);
  } catch {
    return null;
  }
}

// A typed value overrides the detected one; with neither the field is "not_recorded".
export function resolveVersion(auto, manual) {
  const typed = typeof manual === "string" ? manual.trim() : "";
  if (typed) return { value: typed, source: "manual" };
  if (auto) return { value: auto, source: "auto" };
  return { value: "", source: "not_recorded" };
}
