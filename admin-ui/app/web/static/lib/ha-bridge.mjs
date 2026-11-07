// Optional bridge to the Home Assistant frontend that frames this page (app panel / ingress).
//
// Protocol source: home-assistant/frontend src/panels/app/ha-panel-app.ts. It is UNDOCUMENTED and
// has no stability promise; everything here degrades silently. Minimum HA frontend versions:
// 20260128.0 for subscribe-properties and kioskMode, 20260729.0 only for handleSafeArea.
// An old or silent host yields status "no_answer", and the fixed layout applies (D-13).
//
// Messages out (to window.parent): home-assistant/subscribe-properties, unsubscribe-properties,
// toggle-menu, navigate. Message in: home-assistant/properties only, accepted when
// event.source is window.parent AND event.origin equals the page origin (HA posts with target
// origin "*", so source and origin are the only authentication). Inbound data is untrusted: only
// validated fields are kept and nothing is reflected into the DOM.
//
// Kiosk policy (PD-11): HA draws its own 40px bar only when narrow (or the sidebar is hidden), so
// the own bar is requested to take over (kioskMode) from narrow transitions only, never on a
// docked desktop sidebar (kiosk would turn that sidebar into a modal drawer). Transitions are
// driven by received messages and configure(), never by timers; a freeze guard stops loops.

const POLICIES = ["narrow", "never", "always"];
const BAR_HEIGHT = 40;
const MAX_PATH = 512;
const INSET = /^-?\d+(\.\d+)?(px)?$/;
const INSET_SIDES = ["top", "right", "bottom", "left"];
const FREEZE_WINDOW_MS = 10000;
const FREEZE_LIMIT = 4;

const T_SUBSCRIBE = "home-assistant/subscribe-properties";
const T_UNSUBSCRIBE = "home-assistant/unsubscribe-properties";
const T_PROPERTIES = "home-assistant/properties";
const T_MENU = "home-assistant/toggle-menu";
const T_NAVIGATE = "home-assistant/navigate";

const isOpaqueOrigin = (origin) => typeof origin !== "string" || origin === "" || origin === "null";

// The one place that decides whether the own bar should take over from HA's.
function wantKiosk(policy, narrow, hostBar, state) {
  if (state.kioskFrozen) return state.kiosk;
  if (policy === "never") return false;
  if (policy === "always") return true;
  return narrow === true || hostBar === true;
}

function cleanInsets(value) {
  if (!value || typeof value !== "object") return null;
  const out = {};
  for (const side of INSET_SIDES) {
    const v = value[side];
    if (typeof v !== "string" || v.length > 32 || !INSET.test(v)) return null;
    out[side] = v;
  }
  return out;
}

function cleanRoute(value) {
  if (!value || typeof value !== "object") return null;
  const { path, prefix } = value;
  if (typeof path !== "string" || typeof prefix !== "string") return null;
  if (!path.startsWith("/") || path.length > MAX_PATH || prefix.length > MAX_PATH) return null;
  return { path, prefix };
}

function safePath(path) {
  if (typeof path !== "string" || path.length > MAX_PATH) return false;
  if (!path.startsWith("/") || path.startsWith("//")) return false;
  // eslint-disable-next-line no-control-regex
  return !/[\u0000-\u001f\u007f\\]/.test(path) && !path.includes("//");
}

export function createHaBridge(options = {}) {
  const { win, fallbackMs = 1500, targetOrigin, frameProbe = true } = options;
  const setTimer = options.setTimeout || ((...a) => globalThis.setTimeout(...a));
  const clearTimer = options.clearTimeout || ((...a) => globalThis.clearTimeout(...a));
  const now = options.now || (() => Date.now());

  let policy = POLICIES.includes(options.kiosk) ? options.kiosk : "narrow";
  let handleSafeArea = options.handleSafeArea === true;
  let started = false;
  let subscribed = false;
  let timer = null;
  let transitions = [];
  const listeners = new Set();

  const initial = () => ({
    embedded: false,
    status: "idle",
    narrow: null,
    safeAreaInsets: null,
    route: null,
    kiosk: false,
    hostBar: null,
    kioskFrozen: false,
    messages: 0,
    lastMessageAt: null,
  });
  let state = initial();

  const isEmbedded = () => Boolean(win && win.parent && win.parent !== win);

  function snapshot() {
    return {
      ...state,
      safeAreaInsets: state.safeAreaInsets ? { ...state.safeAreaInsets } : null,
      route: state.route ? { ...state.route } : null,
    };
  }

  function notify() {
    const snap = snapshot();
    for (const fn of [...listeners]) {
      try {
        fn(snap);
      } catch {
        // a failing listener must not break the bridge
      }
    }
  }

  function post(message) {
    if (!isEmbedded()) return false;
    try {
      const origin = targetOrigin || (isOpaqueOrigin(win.location && win.location.origin) ? "*" : win.location.origin);
      win.parent.postMessage(message, origin);
      return true;
    } catch {
      return false;
    }
  }

  function postSubscribe() {
    const message = { type: T_SUBSCRIBE };
    if (handleSafeArea) message.handleSafeArea = true;
    if (state.kiosk) message.kioskMode = true;
    if (post(message)) subscribed = true;
  }

  function resubscribe() {
    if (subscribed) post({ type: T_UNSUBSCRIBE });
    postSubscribe();
  }

  function probeHostBar() {
    if (!frameProbe) return null;
    try {
      const top = win.frameElement.getBoundingClientRect().top;
      const inset = state.safeAreaInsets ? parseFloat(state.safeAreaInsets.top) || 0 : 0;
      return Number.isFinite(top) ? top >= BAR_HEIGHT + inset : null;
    } catch {
      return null;
    }
  }

  function setKiosk(desired) {
    if (desired === state.kiosk || state.kioskFrozen) return;
    const t = now();
    transitions = transitions.filter((at) => t - at < FREEZE_WINDOW_MS);
    if (transitions.length >= FREEZE_LIMIT) {
      state.kioskFrozen = true;
      return;
    }
    transitions.push(t);
    state.kiosk = desired;
    if (desired) postSubscribe();
    else resubscribe();
  }

  function clearTimerSafe() {
    if (timer !== null) clearTimer(timer);
    timer = null;
  }

  function onMessage(event) {
    try {
      if (!event || event.source !== win.parent) return;
      const pageOrigin = win.location && win.location.origin;
      if (isOpaqueOrigin(pageOrigin) || event.origin !== pageOrigin) return;
      const data = event.data;
      if (!data || typeof data !== "object" || data.type !== T_PROPERTIES) return;
      if (typeof data.narrow !== "boolean") return;

      const narrowChanged = state.narrow !== data.narrow;
      state.narrow = data.narrow;
      state.safeAreaInsets = cleanInsets(data.safeAreaInsets);
      state.route = cleanRoute(data.route);
      state.status = "ok";
      state.messages += 1;
      state.lastMessageAt = now();
      clearTimerSafe();

      if (narrowChanged) state.hostBar = null;
      if (!data.narrow && state.hostBar !== true) state.hostBar = probeHostBar();
      else if (data.narrow) state.hostBar = null;
      setKiosk(wantKiosk(policy, state.narrow, state.hostBar, state));
    } catch {
      // never throw out of a message handler
    }
    notify();
  }

  function start() {
    if (started) return;
    started = true;
    state = initial();
    state.embedded = isEmbedded();
    if (!state.embedded) {
      notify();
      return;
    }
    win.addEventListener("message", onMessage);
    state.kiosk = policy === "always";
    postSubscribe();
    state.status = "waiting";
    timer = setTimer(() => {
      timer = null;
      if (state.status === "waiting") {
        state.status = "no_answer";
        notify();
      }
    }, fallbackMs);
    notify();
  }

  function dispose() {
    if (started && state.embedded) {
      try {
        win.removeEventListener("message", onMessage);
      } catch {
        // already gone
      }
    }
    clearTimerSafe();
    if (subscribed) post({ type: T_UNSUBSCRIBE });
    subscribed = false;
    started = false;
    transitions = [];
    state = initial();
    state.embedded = isEmbedded();
    notify();
  }

  function configure(next = {}) {
    if (POLICIES.includes(next.kiosk)) policy = next.kiosk;
    if (typeof next.handleSafeArea === "boolean") handleSafeArea = next.handleSafeArea;
    if (!started || !state.embedded) return false;
    state.hostBar = null;
    state.kioskFrozen = false;
    transitions = [];
    state.kiosk = wantKiosk(policy, state.narrow, null, state);
    resubscribe();
    notify();
    return true;
  }

  return {
    start,
    dispose,
    getState: snapshot,
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    configure,
    toggleMenu: () => post({ type: T_MENU }),
    navigate: (path) => (safePath(path) ? post({ type: T_NAVIGATE, path }) : false),
  };
}
