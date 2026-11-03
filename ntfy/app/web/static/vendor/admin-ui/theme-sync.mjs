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
// Safety: nothing from the parent is written as-is. Values are parsed to numbers and
// re-serialised by serializeColor (#rrggbb or rgba()), so a hostile value cannot inject CSS.
// This module writes no log output.
import { parseColor, serializeColor, isDarkColor, contrastRatio, pickOnColor } from "./color.mjs";

const MIN_CONTRAST = 4.5;
const ON_ACC = "--sync-on-acc";

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
      const values = {};
      for (const entry of THEME_WHITELIST) {
        values[entry.key] = String(style.getPropertyValue(entry.ha)).trim();
      }
      return { values };
    } catch {
      return { reason: "parent_inaccessible" };
    }
  }

  function evaluate(colors) {
    const { bg, card, fg, bd, acc } = colors;
    const skipped = [];
    const wanted = new Map();
    const surface =
      bg !== null &&
      card !== null &&
      fg !== null &&
      bd !== null &&
      opaque(card) &&
      opaque(fg) &&
      contrastRatio(fg, bg) >= MIN_CONTRAST &&
      contrastRatio(fg, card) >= MIN_CONTRAST;
    if (surface) {
      wanted.set("--sync-bg", serializeColor(bg));
      wanted.set("--sync-card", serializeColor(card));
      wanted.set("--sync-fg", serializeColor(fg));
      wanted.set("--sync-bd", serializeColor(bd));
    } else {
      skipped.push("surface");
    }
    let accent = false;
    if (surface) {
      const onAcc = acc !== null && opaque(acc) ? parseColor(pickOnColor(acc)) : null;
      accent =
        onAcc !== null &&
        contrastRatio(acc, bg) >= MIN_CONTRAST &&
        contrastRatio(acc, card) >= MIN_CONTRAST &&
        contrastRatio(onAcc, acc) >= MIN_CONTRAST;
      if (accent) {
        wanted.set("--sync-acc", serializeColor(acc));
        wanted.set(ON_ACC, serializeColor(onAcc));
      }
    }
    if (!accent) skipped.push("accent");
    return { surface, accent, skipped, wanted };
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
      state = { ...freshState("unparseable_background"), raw };
      return;
    }
    const mode = isDarkColor(colors.bg) ? "dark" : "light";
    const result = evaluate(colors);
    writeTheme(mode);
    writeProps(result.wanted);
    state = {
      active: true,
      reason: "ok",
      mode,
      surface: result.surface,
      accent: result.accent,
      skipped: result.skipped,
      lastSync: now(),
      raw,
    };
  }

  const snapshot = () => ({
    ...state,
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
