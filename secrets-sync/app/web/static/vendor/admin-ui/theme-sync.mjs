// Optional HA theme sync: reads a whitelist of CSS variables from the parent document and maps
// them to --sync-* custom properties that base.css consumes as var(--sync-x, <own default>).
//
// Progressive enhancement (D-11): inert unless embedded; every failure removes everything this
// module wrote, so the own theme applies. The parent theme variables are undocumented HA
// internals without a stability promise, hence the guards and the injectable window.
//
// Deliberately NOT synced: chip, hover, mut, ok, warn, err. They form text-on-fill pairs whose
// counterpart HA does not expose, so the own, contrast-validated defaults stay.
//
// Safety: nothing from the parent is written as-is. Colours are parsed to numbers and
// re-serialised by serializeColor (#rrggbb or rgba()); header height uses a strict pixel parser.
// Header height, card radius and shadows have bounded parsers. This module writes no log output.
import { parseColor, serializeColor, isDarkColor, contrastRatio, pickOnColor } from "./color.mjs";

const MIN_CONTRAST = 4.5;
const ON_ACC = "--sync-on-acc";
const HEADER_HEIGHT = "--sync-header-height";

// A bounded CSS-pixel length, never arbitrary CSS from the parent. Missing/invalid values use the CSS fallback.
function headerHeight(value) {
  const text = String(value || "").trim();
  if (!/^\d+(?:\.\d{1,3})?px$/.test(text)) return null;
  const px = Number(text.slice(0, -2));
  return px >= 32 && px <= 128 ? `${px}px` : null;
}

function cardBackground(value) {
  return String(value).trim().toLowerCase() === "transparent"
    ? { r: 0, g: 0, b: 0, a: 0 }
    : parseColor(value);
}

function cardRadius(value) {
  const parts = String(value || "").trim().split(/\s+/);
  if (parts.length > 4) return null;
  const parsed = parts.map((part) => {
    if (part === "0") return "0px";
    if (!/^\d+(?:\.\d{1,3})?(px|%)$/.test(part)) return null;
    const number = parseFloat(part);
    return number <= (part.endsWith("%") ? 100 : 256) ? part : null;
  });
  return parsed.every((part) => part !== null) ? parsed.join(" ") : null;
}

function cardShadow(value) {
  const text = String(value || "").trim().toLowerCase();
  if (text === "none") return "none";
  if (!text || text.length > 1024) return null;
  const layers = text.split(/,(?![^()]*\))/);
  if (layers.length > 8) return null;
  const result = [];
  for (const layer of layers) {
    const tokens = layer.trim().match(/rgba?\([^)]*\)|[^\s]+/g) || [];
    const lengths = [];
    let color = null, inset = false;
    for (const token of tokens) {
      if (token === "inset" && !inset) { inset = true; continue; }
      const parsed = parseColor(token);
      const named = { black: "#000000", white: "#ffffff", transparent: "rgba(0, 0, 0, 0)", currentcolor: "currentcolor" };
      if (parsed || Object.hasOwn(named, token)) {
        if (color !== null) return null;
        color = parsed ? serializeColor(parsed) : named[token];
        continue;
      }
      if (token !== "0" && !/^-?(?:\d+(?:\.\d{1,3})?|\.\d{1,3})px$/.test(token)) return null;
      const n = parseFloat(token);
      if (Math.abs(n) > 512) return null;
      lengths.push(n);
    }
    if (lengths.length < 2 || lengths.length > 4 || (lengths.length > 2 && lengths[2] < 0)) return null;
    result.push([...(inset ? ["inset"] : []), ...lengths.map((n) => `${n}px`), color || "currentcolor"].join(" "));
  }
  return result.join(", ");
}

export const THEME_WHITELIST = Object.freeze(
  [
    { key: "bg", sync: "--sync-bg", ha: "--primary-background-color", group: "surface" },
    { key: "card", sync: "--sync-card", ha: "--card-background-color", group: "surface" },
    { key: "fg", sync: "--sync-fg", ha: "--primary-text-color", group: "surface" },
    { key: "bd", sync: "--sync-bd", ha: "--divider-color", group: "surface" },
    { key: "acc", sync: "--sync-acc", ha: "--primary-color", group: "accent" },
  ].map(Object.freeze),
);

const opaque = (c) => c !== null && c.a === 1;

// Composite in sRGB for contrast checks; retain the original RGBA value when applying the theme.
function over(color, background) {
  return {
    r: color.r * color.a + background.r * (1 - color.a),
    g: color.g * color.a + background.g * (1 - color.a),
    b: color.b * color.a + background.b * (1 - color.a),
    a: 1,
  };
}

export function createThemeSync(options = {}) {
  const { win, pollMs = 3000 } = options;
  const setIntervalFn = options.setInterval || ((...a) => globalThis.setInterval(...a));
  const clearIntervalFn = options.clearInterval || ((...a) => globalThis.clearInterval(...a));
  const now = options.now || (() => Date.now());

  const written = new Map();
  const listeners = new Set();
  const counters = { refresh: 0, observer: 0, poll: 0, event: 0, apply: 0 };
  let themeSet = false;
  let started = false;
  let observer = null;
  let timer = null;
  let wired = [];
  let state = null;

  function freshState(reason) {
    return {
      active: false,
      reason,
      mode: null,
      headerHeight: null,
      cardStyle: { background: null, backgroundInput: null, backgroundReason: "missing", radius: null, shadow: null },
      surface: false,
      accent: false,
      skipped: [],
      lastSync: state ? state.lastSync : null,
      raw: Object.fromEntries(THEME_WHITELIST.map((w) => [w.key, null])),
    };
  }

  state = freshState("idle");

  const rootEl = () => options.root || win.document.documentElement;

  function clearWritten() {
    try {
      const root = rootEl();
      for (const name of written.keys()) root.style.removeProperty(name);
      if (themeSet) root.removeAttribute("data-theme");
    } catch {
      // nothing left to do: the properties are either gone or the root is unusable
    }
    written.clear();
    themeSet = false;
  }

  function writeProps(wanted) {
    const root = rootEl();
    for (const name of [...written.keys()]) {
      if (!wanted.has(name)) {
        root.style.removeProperty(name);
        written.delete(name);
      }
    }
    for (const [name, value] of wanted) {
      if (written.get(name) !== value) {
        root.style.setProperty(name, value);
        written.set(name, value);
        counters.apply += 1;
      }
    }
  }

  function writeTheme(mode) {
    const root = rootEl();
    if (root.getAttribute("data-theme") !== mode) {
      root.setAttribute("data-theme", mode);
      counters.apply += 1;
    }
    themeSet = true;
  }

  function readParent() {
    const parent = win.parent;
    if (!parent || parent === win) return { reason: "not_embedded" };
    try {
      const style = parent.getComputedStyle(parent.document.documentElement);
      const host = parent.document.querySelector?.("home-assistant");
      const hostStyle = host ? parent.getComputedStyle(host) : null;
      const read = (name) => String(hostStyle?.getPropertyValue(name) || style.getPropertyValue(name) || "").trim();
      const values = {};
      for (const entry of THEME_WHITELIST) values[entry.key] = read(entry.ha);
      const background = read("--ha-card-background") || read("--card-background-color");
      return {
        values,
        cardBackgroundInput: background.slice(0, 1024),
        headerHeight: headerHeight(read("--header-height")),
        cardBackground: cardBackground(background),
        cardRadius: cardRadius(read("--ha-card-border-radius") || read("--ha-border-radius-lg")),
        cardShadow: cardShadow(read("--ha-card-box-shadow")),
        toastBg: read("--ha-color-neutral-10"),
        toastFg: read("--ha-color-on-neutral-loud"),
        toastRadius: cardRadius(read("--ha-border-radius-sm")),
      };
    } catch {
      return { reason: "parent_inaccessible" };
    }
  }

  function evaluate(colors) {
    const { bg, card, fg, bd, acc, haCard } = colors;
    const skipped = [];
    const wanted = new Map();
    const cardFill = bg && card ? over(card, bg) : null;
    const surface =
      bg !== null &&
      card !== null &&
      fg !== null &&
      bd !== null &&
      contrastRatio(over(fg, bg), bg) >= MIN_CONTRAST &&
      contrastRatio(over(fg, cardFill), cardFill) >= MIN_CONTRAST;
    if (surface) {
      wanted.set("--sync-bg", serializeColor(bg));
      wanted.set("--sync-card", serializeColor(card));
      wanted.set("--sync-fg", serializeColor(fg));
      wanted.set("--sync-bd", serializeColor(bd));
    } else {
      skipped.push("surface");
    }
    const haCardFill = surface && haCard ? over(haCard, bg) : null;
    const cardBackground = haCardFill && contrastRatio(over(fg, haCardFill), haCardFill) >= MIN_CONTRAST
      ? serializeColor(haCard) : null;
    if (cardBackground) wanted.set("--sync-ha-card-background", cardBackground);
    let accent = false;
    if (surface) {
      const onAcc = acc !== null && opaque(acc) ? parseColor(pickOnColor(acc)) : null;
      accent =
        onAcc !== null &&
        contrastRatio(acc, bg) >= MIN_CONTRAST &&
        contrastRatio(acc, cardFill) >= MIN_CONTRAST &&
        (!cardBackground || contrastRatio(acc, haCardFill) >= MIN_CONTRAST) &&
        contrastRatio(onAcc, acc) >= MIN_CONTRAST;
      if (accent) {
        wanted.set("--sync-acc", serializeColor(acc));
        wanted.set(ON_ACC, serializeColor(onAcc));
      }
    }
    if (!accent) skipped.push("accent");
    return { surface, accent, skipped, wanted, cardBackground };
  }

  function run() {
    const read = readParent();
    if (!read.values) {
      clearWritten();
      state = freshState(read.reason);
      return;
    }
    const colors = {};
    for (const entry of THEME_WHITELIST) colors[entry.key] = parseColor(read.values[entry.key]);
    const raw = Object.fromEntries(THEME_WHITELIST.map((w) => [w.key, serializeColor(colors[w.key])]));
    if (!opaque(colors.bg)) {
      clearWritten();
      if (read.headerHeight) writeProps(new Map([[HEADER_HEIGHT, read.headerHeight]]));
      state = { ...freshState("unparseable_background"), headerHeight: read.headerHeight, raw };
      return;
    }
    const mode = isDarkColor(colors.bg) ? "dark" : "light";
    const result = evaluate({ ...colors, haCard: read.cardBackground });
    if (read.cardRadius) result.wanted.set("--sync-card-radius", read.cardRadius);
    if (read.cardShadow) result.wanted.set("--sync-card-shadow", read.cardShadow);
    // The parent's snackbar surface; only taken when both colours are opaque and readable, else the own toast tokens stay.
    const toastBg = parseColor(read.toastBg);
    const toastFg = parseColor(read.toastFg);
    if (opaque(toastBg) && opaque(toastFg) && contrastRatio(toastFg, toastBg) >= MIN_CONTRAST) {
      result.wanted.set("--sync-toast-bg", serializeColor(toastBg));
      result.wanted.set("--sync-toast-fg", serializeColor(toastFg));
    }
    if (read.toastRadius) result.wanted.set("--sync-toast-radius", read.toastRadius);
    if (read.headerHeight) result.wanted.set(HEADER_HEIGHT, read.headerHeight);
    writeTheme(mode);
    writeProps(result.wanted);
    state = {
      active: true,
      reason: "ok",
      mode,
      headerHeight: read.headerHeight,
      cardStyle: {
        background: result.cardBackground,
        backgroundInput: read.cardBackgroundInput,
        backgroundReason: result.cardBackground ? null : !read.cardBackgroundInput ? "missing" : !read.cardBackground ? "invalid" : "contrast",
        radius: read.cardRadius, shadow: read.cardShadow,
      },
      surface: result.surface,
      accent: result.accent,
      skipped: result.skipped,
      lastSync: now(),
      raw,
    };
  }

  const snapshot = () => ({
    ...state,
    cardStyle: { ...state.cardStyle },
    skipped: [...state.skipped],
    raw: { ...state.raw },
    counters: { ...counters },
  });

  function notify() {
    const snap = snapshot();
    for (const fn of [...listeners]) {
      try {
        fn(snap);
      } catch {
        // a failing listener must not break the others or the sync
      }
    }
  }

  function refresh(source) {
    counters.refresh += 1;
    if (source) counters[source] += 1;
    try {
      run();
    } catch {
      clearWritten();
      state = freshState("error");
    }
    notify();
  }

  function listen(target, type) {
    try {
      const fn = () => refresh("event");
      target.addEventListener(type, fn);
      wired.push(() => target.removeEventListener(type, fn));
    } catch {
      // optional trigger only
    }
  }

  function start() {
    if (started) return;
    started = true;
    refresh();
    if (state.reason === "not_embedded") return;
    try {
      const parent = win.parent;
      observer = new parent.MutationObserver(() => refresh("observer"));
      observer.observe(parent.document.documentElement, { attributes: true, attributeFilter: ["style"] });
    } catch {
      observer = null;
    }
    timer = setIntervalFn(() => refresh("poll"), pollMs);
    if (win.document) listen(win.document, "visibilitychange");
    listen(win, "focus");
  }

  function dispose() {
    started = false;
    try {
      if (observer) observer.disconnect();
    } catch {
      // already gone
    }
    observer = null;
    if (timer !== null) clearIntervalFn(timer);
    timer = null;
    for (const off of wired) {
      try {
        off();
      } catch {
        // already gone
      }
    }
    wired = [];
    clearWritten();
    state = freshState("disposed");
    notify();
  }

  function subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  }

  return { start, dispose, refresh: () => refresh(), status: snapshot, subscribe };
}
