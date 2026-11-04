// Live spike instrument (D-14): probes the HA integration checks S1..S15 and builds a redacted, uniform result block.
// Every probe is guarded and reports {ok, detail} with a short fixed token; parent-derived strings are only rendered
// as text, colours only after the lib parsed them, and the result never contains identity, URLs or tokens.
import { html, useEffect, useRef, useState, Badge, CopyField, DataTable, Field } from "../lib/ui.mjs";
import { useLang, useT } from "../lib/i18n.mjs";
import { LangSwitch } from "../lib/shell.mjs";
import { detectEmbedContext, isEmbedded } from "../lib/ingress.mjs";
import { THEME_WHITELIST } from "../lib/theme-sync.mjs";
import { formatDateTime } from "../lib/format.mjs";
import { get } from "../lib/api.mjs";
import { cleanVersion, detectBrowser, readCoreVersion, resolveVersion } from "../spike-versions.mjs";

export const meta = { id: "spike", titleKey: "demo.nav.spike" };

export const CHECKS = [
  { id: "S1", titleKey: "demo.spike.s01.title", hintKey: "demo.spike.s01.hint" },
  { id: "S2", titleKey: "demo.spike.s02.title", hintKey: "demo.spike.s02.hint" },
  { id: "S3", titleKey: "demo.spike.s03.title", hintKey: "demo.spike.s03.hint" },
  { id: "S4", titleKey: "demo.spike.s04.title", hintKey: "demo.spike.s04.hint" },
  { id: "S5", titleKey: "demo.spike.s05.title", hintKey: "demo.spike.s05.hint" },
  { id: "S6", titleKey: "demo.spike.s06.title", hintKey: "demo.spike.s06.hint" },
  { id: "S7", titleKey: "demo.spike.s07.title", hintKey: "demo.spike.s07.hint" },
  { id: "S8", titleKey: "demo.spike.s08.title", hintKey: "demo.spike.s08.hint" },
  { id: "S9", titleKey: "demo.spike.s09.title", hintKey: "demo.spike.s09.hint" },
  { id: "S10", titleKey: "demo.spike.s10.title", hintKey: "demo.spike.s10.hint" },
  { id: "S11", titleKey: "demo.spike.s11.title", hintKey: "demo.spike.s11.hint" },
  { id: "S12", titleKey: "demo.spike.s12.title", hintKey: "demo.spike.s12.hint" },
  { id: "S13", titleKey: "demo.spike.s13.title", hintKey: "demo.spike.s13.hint" },
  { id: "S14", titleKey: "demo.spike.s14.title", hintKey: "demo.spike.s14.hint" },
  { id: "S15", titleKey: "demo.spike.s15.title", hintKey: "demo.spike.s15.hint" },
];

const SPIKE_STORAGE_KEY = "admin-ui:spike-test";
const POLICIES = ["narrow", "never", "always"];
// Literal keys (R-06: keys are never built dynamically).
const POLICY_KEYS = { narrow: "demo.spike.policy.narrow", never: "demo.spike.policy.never", always: "demo.spike.policy.always" };
const STORAGE_KEYS = { ok: "demo.spike.storage.ok", blocked: "demo.spike.storage.blocked" };
const PATH_KEYS = { ingress: "demo.spike.path.ingress", direct: "demo.spike.path.direct" };
const MAX_LOG = 20;
const NAV_PATHS = ["bridge", "fallback", "new_tab"];
// Short result tokens: the full sandbox token names are long enough to look like secrets to the redaction.
const SANDBOX_SHORT = { "allow-top-navigation": "top", "allow-top-navigation-by-user-activation": "top_user", "allow-popups": "popups", "allow-popups-to-escape-sandbox": "popups_escape" };
const EMBED_KINDS = ["panel", "card", "tab", "unknown"];
const TOP_STATES = ["allowed", "blocked", "unknown"];
const SOURCES = ["auto", "manual", "not_recorded"];
const MAX_TEXT = 80;
const TOKEN_RE = /^[a-z][a-z0-9_]{0,23}$/;
const NAME_RE = /^[A-Za-z]{1,40}$/;
const COLOR_RE = /^(?:#[0-9a-f]{6}|rgba\([0-9., ]{1,40}\))$/i;
const GROUP_RE = /^[A-Za-z0-9_-]{1,19}$/;

// ---- redaction ----
const FORBIDDEN_KEYS = new Set([
  "user_id", "name", "display_name", "href", "origin", "url", "host", "hostname", "token", "email", "username", "password", "cookie",
]);
const PRIVATE_IP = /\b(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7]))\.\d{1,3}\.\d{1,3}\b/;
const HOSTNAME = /\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:local|lan|home|internal|net|com|org|io|de|dev|app)\b/i;
const TOKENISH = /[A-Za-z0-9+/=_-]{20,}/;

const looksSensitive = (text) =>
  text.includes("://") || /bearer/i.test(text) || PRIVATE_IP.test(text) || HOSTNAME.test(text) || TOKENISH.test(text);

// Removes forbidden keys and URL-, host- or token-like strings at any depth. Pure: returns a cleaned copy.
export function redact(value) {
  if (typeof value === "string") return looksSensitive(value) ? undefined : value;
  if (Array.isArray(value)) return value.map(redact).filter((v) => v !== undefined);
  if (value && typeof value === "object") {
    const out = {};
    for (const [key, inner] of Object.entries(value)) {
      if (FORBIDDEN_KEYS.has(key.toLowerCase())) continue;
      const cleaned = redact(inner);
      if (cleaned !== undefined) out[key] = cleaned;
    }
    return out;
  }
  return value;
}

// ---- sanitizers for external values ----
const token = (v, fallback = "other") => (typeof v === "string" && TOKEN_RE.test(v) ? v : fallback);
const errName = (err) => (err && typeof err.name === "string" && NAME_RE.test(err.name) ? err.name : "Error");
const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : 0);
const colorOf = (v) => (typeof v === "string" && COLOR_RE.test(v) ? v : null);
const bool = (v) => (typeof v === "boolean" ? v : null);
const text = (v) => (typeof v === "string" ? v.replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, MAX_TEXT) : "");

export const accessPathOf = (pathname) =>
  typeof pathname === "string" && pathname.includes("/api/hassio_ingress/") ? "ingress" : "direct";

// ---- probes: small guarded functions, each returns plain data ----
export function probeParent(win = globalThis.window) {
  let embedded = false;
  try {
    embedded = isEmbedded(win);
  } catch {
    embedded = false;
  }
  if (!embedded) return { embedded: false, readable: null, sameOrigin: null, error: null };
  let readable = false;
  let error = null;
  try {
    readable = Boolean(win.parent.document.documentElement);
  } catch (err) {
    error = errName(err);
  }
  let sameOrigin = false;
  try {
    sameOrigin = win.location.origin === win.parent.location.origin;
  } catch {
    sameOrigin = false;
  }
  return { embedded: true, readable, sameOrigin, error };
}

export function probeFrameTop(win = globalThis.window) {
  try {
    const top = win.frameElement.getBoundingClientRect().top;
    return Number.isFinite(top) ? Math.round(top) : null;
  } catch {
    return null;
  }
}

export function probeStorage(storage) {
  try {
    const store = storage === undefined ? globalThis.localStorage : storage;
    store.setItem(SPIKE_STORAGE_KEY, "1");
    const back = store.getItem(SPIKE_STORAGE_KEY);
    store.removeItem(SPIKE_STORAGE_KEY);
    return back === "1" ? "ok" : "blocked";
  } catch {
    return "blocked";
  }
}

export function cspKey(ev) {
  const directive = typeof ev.effectiveDirective === "string" && /^[a-z-]{1,30}$/.test(ev.effectiveDirective) ? ev.effectiveDirective : "other";
  const blocked = ev.blockedURI;
  const category = blocked === "inline" || blocked === "eval" || blocked === "self" ? blocked : "other";
  return `${directive}/${category}`;
}

// ---- result ----
const pass = (ok, detail) => ({ ok, detail });

// Computes all probe outcomes from the collected inputs; pure.
export function evaluateProbes(i) {
  const parent = i.parent || {};
  const sync = i.sync || {};
  const bridge = i.bridge || {};
  const counters = sync.counters || {};
  const csp = i.csp || {};
  const parsed = THEME_WHITELIST.filter((w) => colorOf((sync.raw || {})[w.key])).length;
  const violations = Object.values(csp.counts || {}).reduce((a, b) => a + num(b), 0);
  const embedded = Boolean(i.embedded);
  return {
    S1: embedded ? pass(Boolean(parent.readable), parent.readable ? `readable_${parent.sameOrigin ? "same" : "cross"}` : `blocked_${errName({ name: parent.error })}`) : pass(true, "not_embedded"),
    S2: pass(parsed > 0, `${parsed}_of_${THEME_WHITELIST.length}`),
    S3: pass(Boolean(sync.active), `observer ${num(counters.observer)}, poll ${num(counters.poll)}, apply ${num(counters.apply)}`),
    S4: pass(bridge.status === "ok", token(bridge.status, "unknown")),
    S5: pass(!(bridge.hostBar === true && bridge.kiosk !== true) && bridge.kioskFrozen !== true, `bar ${String(bool(bridge.hostBar))}, kiosk ${String(bool(bridge.kiosk))}`),
    S6: pass(Boolean(bridge.safeAreaInsets), `safe_area_${i.handleSafeArea ? "on" : "off"}`),
    S7: pass(typeof i.navigateResult === "boolean" ? i.navigateResult : null, i.navigateResult === null || i.navigateResult === undefined ? "not_run" : String(i.navigateResult)),
    S8: pass(i.clipboard === "copied" ? true : i.clipboard === "failed" ? false : null, token(i.clipboard, "not_run")),
    S9: pass(violations === 0, `violations_${violations}`),
    S10: pass(i.storage === "ok" ? true : i.storage === "blocked" ? false : null, token(i.storage, "not_run")),
    S11: pass(i.whoami ? true : null, i.whoami ? `identity_${i.whoami.identity_present ? "yes" : "no"}` : "not_run"),
    S12: pass(true, token(i.accessPath, "direct")),
    S13: pass(embedded ? Boolean(sync.active) : null, embedded ? `sync_${sync.active ? "on" : "off"}` : "not_embedded"),
    S14: pass(null, `${token(i.lang, "en")}_${token(sync.mode || "own", "own")}`),
    S15: pass(Boolean(i.versions && i.versions.core && i.versions.frontend), i.versions && i.versions.core && i.versions.frontend ? "versions_entered" : "missing"),
  };
}

// Builds the allow-listed result object and runs it through redact().
export function buildResult(i = {}) {
  const sync = i.sync || {};
  const bridge = i.bridge || {};
  const counters = sync.counters || {};
  const csp = i.csp || {};
  const colors = {};
  for (const w of THEME_WHITELIST) colors[w.key] = colorOf((sync.raw || {})[w.key]);
  const violations = {};
  for (const [key, n] of Object.entries(csp.counts || {})) violations[key] = num(n);
  const versions = i.versions || {};
  const whoami = i.whoami || null;
  const nav = i.infoNav || {};
  const embed = i.embed || {};
  // Plain strings (typed values) count as manual; a field without a value is "not_recorded" (never guessed).
  const source = (key) => {
    const given = versions[`${key}Source`];
    if (SOURCES.includes(given) && text(versions[key])) return given;
    return text(versions[key]) ? "manual" : "not_recorded";
  };
  return redact({
    schema: 1,
    generated_at: text(i.generatedAt),
    ha: {
      core: text(versions.core),
      core_source: source("core"),
      frontend: text(versions.frontend),
      frontend_source: source("frontend"),
      addon: text(versions.addon),
      addon_source: source("addon"),
    },
    client: { app: text(versions.app), app_source: source("app") },
    access_path: token(i.accessPath, "direct"),
    embedded: Boolean(i.embedded),
    probes: evaluateProbes(i),
    sync: {
      mode: sync.mode === "dark" || sync.mode === "light" ? sync.mode : null,
      surface: Boolean(sync.surface),
      accent: Boolean(sync.accent),
      skipped: (Array.isArray(sync.skipped) ? sync.skipped : []).map((s) => token(s)),
      counters: { observer: num(counters.observer), poll: num(counters.poll), apply: num(counters.apply), refresh: num(counters.refresh) },
      colors,
    },
    bridge: {
      status: token(bridge.status, "unknown"),
      narrow: bool(bridge.narrow),
      kiosk: bool(bridge.kiosk),
      hostBar: bool(bridge.hostBar),
      kioskFrozen: bool(bridge.kioskFrozen),
      messages: num(bridge.messages),
      insets_present: Boolean(bridge.safeAreaInsets),
      route_present: Boolean(bridge.route),
    },
    csp: { violations },
    // Which path the info link took last; HA does not confirm navigate, so this is the path, not a success.
    embed: {
      kind: EMBED_KINDS.includes(embed.kind) ? embed.kind : "unknown",
      sandbox: Array.isArray(embed.sandbox) ? embed.sandbox.map((t) => SANDBOX_SHORT[t]).filter(Boolean) : null,
      top_navigation: TOP_STATES.includes(embed.topNavigation) ? embed.topNavigation : "unknown",
    },
    navigate: { last_path: NAV_PATHS.includes(nav.last) ? nav.last : "none", count: num(nav.count) },
    whoami: {
      identity_present: Boolean(whoami && whoami.identity_present),
      groups: whoami && Array.isArray(whoami.groups) ? whoami.groups.filter((g) => typeof g === "string" && GROUP_RE.test(g)) : [],
    },
  });
}

// ---- view ----
const safe = (fn, fallback) => {
  try {
    const v = fn();
    return v === undefined ? fallback : v;
  } catch {
    return fallback;
  }
};

function Panel({ check, children }) {
  const tt = useT();
  return html`<section class="section card" id=${`spike-${check.id}`}>
    <h2>${check.id} ${tt(check.titleKey)}</h2>
    <p class="muted">${tt(check.hintKey)}</p>
    ${children}
  </section>`;
}

// Literal keys (R-06).
const NAV_KEYS = { none: "demo.spike.info_path.none", bridge: "demo.spike.info_path.bridge", fallback: "demo.spike.info_path.fallback", new_tab: "demo.spike.info_path.new_tab" };
const EMBED_KIND_KEYS = { panel: "demo.spike.kind.panel", card: "demo.spike.kind.card", tab: "demo.spike.kind.tab", unknown: "demo.spike.kind.unknown" };
const TOP_KEYS = { allowed: "demo.spike.top.allowed", blocked: "demo.spike.top.blocked", unknown: "demo.spike.top.unknown" };
const SOURCE_KEYS = {
  auto: "demo.spike.source.auto",
  manual: "demo.spike.source.manual",
  not_recorded: "demo.spike.source.not_recorded",
};

// One version row: the effective value with its source, and an optional typed override.
function VersionField({ id, label, resolved, value, onChange, max }) {
  const tt = useT();
  return html`<${Field} id=${id} label=${label} hint=${`${resolved.value || tt(SOURCE_KEYS.not_recorded)} (${tt(SOURCE_KEYS[resolved.source])})`}>
    <input id=${id} type="text" value=${value} maxlength=${max} placeholder=${tt("demo.spike.override")} onInput=${(ev) => onChange(ev.target.value)} />
  <//>`;
}

const byId = (id) => CHECKS.find((c) => c.id === id);

export default function Spike({ ha = {} }) {
  const tt = useT();
  const lang = useLang();
  const bridge = ha.bridge || null;
  const syncApi = ha.sync || null;
  const win = globalThis.window;

  const [syncStatus, setSyncStatus] = useState(() => safe(() => syncApi.status(), {}));
  const [bridgeState, setBridgeState] = useState(() => safe(() => bridge.getState(), {}));
  const [log, setLog] = useState([]);
  const [csp, setCsp] = useState({ counts: {} });
  const [policy, setPolicy] = useState("narrow");
  const [safeArea, setSafeArea] = useState(false);
  const [navigateResult, setNavigateResult] = useState(null);
  const [storage, setStorage] = useState(null);
  const [whoami, setWhoami] = useState(null);
  const [whoamiFailed, setWhoamiFailed] = useState(false);
  const [clipboard, setClipboard] = useState(null);
  const [note, setNote] = useState("");
  // Typed overrides; empty means "use the detected value". Detection is read-only and runs once.
  const [core, setCore] = useState("");
  const [frontend, setFrontend] = useState("");
  const [addon, setAddon] = useState("");
  const [app, setApp] = useState("");
  const infoNav = ha.infoNav || null;
  const [infoState, setInfoState] = useState(() => safe(() => infoNav.getState(), { last: "none", count: 0 }));
  useEffect(() => {
    setInfoState(safe(() => infoNav.getState(), { last: "none", count: 0 }));
    if (!infoNav || typeof infoNav.subscribe !== "function") return undefined;
    const off = infoNav.subscribe((next) => setInfoState(next && typeof next === "object" ? next : { last: "none", count: 0 }));
    return () => typeof off === "function" && off();
  }, [infoNav]);
  const [detected, setDetected] = useState({ core: null, addon: null, app: null });
  const [frameTop, setFrameTop] = useState(() => probeFrameTop(win));
  const logRef = useRef([]);

  useEffect(() => {
    setSyncStatus(safe(() => syncApi.status(), {}));
    if (!syncApi || typeof syncApi.subscribe !== "function") return undefined;
    const off = safe(
      () => syncApi.subscribe((snap) => setSyncStatus(snap && typeof snap === "object" ? snap : safe(() => syncApi.status(), {}))),
      null,
    );
    return () => typeof off === "function" && off();
  }, [syncApi]);

  useEffect(() => {
    setBridgeState(safe(() => bridge.getState(), {}));
    if (!bridge || typeof bridge.subscribe !== "function") return undefined;
    const off = safe(() => bridge.subscribe((snap) => {
      const state = snap && typeof snap === "object" ? snap : {};
      setBridgeState(state);
      setFrameTop(probeFrameTop(win));
      logRef.current = [
        { at: Date.now(), status: token(state.status, "unknown"), narrow: bool(state.narrow), messages: num(state.messages) },
        ...logRef.current,
      ].slice(0, MAX_LOG);
      setLog(logRef.current);
    }), null);
    return () => typeof off === "function" && off();
  }, [bridge]);

  useEffect(() => {
    const doc = globalThis.document;
    if (!doc || typeof doc.addEventListener !== "function") return undefined;
    const onViolation = (ev) => {
      const key = cspKey(ev || {});
      setCsp((prev) => ({ counts: { ...prev.counts, [key]: num(prev.counts[key]) + 1 } }));
    };
    doc.addEventListener("securitypolicyviolation", onViolation);
    return () => doc.removeEventListener("securitypolicyviolation", onViolation);
  }, []);

  const embedContext = detectEmbedContext(win, { bridgeOk: bridgeState.status === "ok" });
  const parent = probeParent(win);
  const accessPath = accessPathOf(safe(() => win.location.pathname, ""));
  const embedded = parent.embedded;

  const runWhoami = async () => {
    setWhoamiFailed(false);
    try {
      const data = await get("whoami");
      const user = data && data.user ? data.user : null;
      const groups = user && Array.isArray(user.groups) ? user.groups.filter((g) => typeof g === "string" && GROUP_RE.test(g)) : [];
      setWhoami({ identity_present: Boolean(user), groups });
    } catch {
      setWhoami(null);
      setWhoamiFailed(true);
    }
  };
  useEffect(() => {
    runWhoami();
  }, []);

  useEffect(() => {
    let live = true;
    setDetected((d) => ({ ...d, core: readCoreVersion(win) }));
    get("health").then(
      (data) => live && setDetected((d) => ({ ...d, addon: cleanVersion(data && data.addon_version) })),
      () => {},
    );
    detectBrowser(globalThis.navigator).then((app) => live && setDetected((d) => ({ ...d, app })));
    return () => {
      live = false;
    };
  }, []);
  const vCore = resolveVersion(detected.core, core);
  const vFrontend = resolveVersion(null, frontend);
  const vAddon = resolveVersion(detected.addon, addon);
  const vApp = resolveVersion(detected.app, app);

  const applyPolicy = (next) => {
    safe(() => bridge.configure({ kiosk: next }), false);
    setPolicy(next);
  };
  const toggleSafeArea = () => {
    const next = !safeArea;
    safe(() => bridge.configure({ handleSafeArea: next }), false);
    setSafeArea(next);
  };
  const runNavigate = () => setNavigateResult(safe(() => bridge.navigate("/config"), false) === true);

  const inputs = {
    generatedAt: new Date().toISOString().slice(0, 10),
    infoNav: infoState,
    embed: embedContext,
    versions: {
      core: vCore.value,
      coreSource: vCore.source,
      frontend: vFrontend.value,
      frontendSource: vFrontend.source,
      addon: vAddon.value,
      addonSource: vAddon.source,
      app: vApp.value,
      appSource: vApp.source,
    },
    accessPath,
    embedded,
    parent,
    sync: syncStatus,
    bridge: bridgeState,
    csp,
    handleSafeArea: safeArea,
    navigateResult,
    clipboard,
    storage,
    whoami,
    lang,
  };
  const result = buildResult(inputs);
  const pretty = JSON.stringify(result, null, 2);
  const compact = JSON.stringify(result);

  const counters = syncStatus.counters || {};
  const skipped = Array.isArray(syncStatus.skipped) ? syncStatus.skipped : [];
  const insets = bridgeState.safeAreaInsets && typeof bridgeState.safeAreaInsets === "object" ? bridgeState.safeAreaInsets : null;
  const yn = (v) => (v === true ? tt("demo.spike.yes") : v === false ? tt("demo.spike.no") : tt("demo.spike.na"));
  const row = (label, value) => html`<li><span class="muted">${label}:</span> ${value}</li>`;

  const varColumns = [
    { key: "var", titleKey: "demo.spike.col.var", render: (r) => html`<code>${r.ha}</code>` },
    { key: "value", titleKey: "demo.spike.col.value", render: (r) => r.value || "-" },
    { key: "state", titleKey: "demo.spike.col.state", render: (r) => (r.value ? tt("demo.spike.parsed") : tt("demo.spike.unparsed")) },
  ];
  const varRows = THEME_WHITELIST.map((w) => ({ key: w.key, ha: w.ha, value: colorOf((syncStatus.raw || {})[w.key]) }));
  varRows.push({ key: "header-height", ha: "--header-height", value: syncStatus.headerHeight || null });
  const logColumns = [
    { key: "at", titleKey: "demo.spike.col.time", render: (r) => formatDateTime(r.at, lang) },
    { key: "status", titleKey: "demo.spike.col.status" },
    { key: "narrow", titleKey: "demo.spike.col.narrow", render: (r) => yn(r.narrow) },
    { key: "messages", titleKey: "demo.spike.col.messages" },
  ];

  return html`<div>
    <section class="section card">
      <h2>${tt("demo.spike.title")}</h2>
      <p>${tt("demo.spike.intro")}</p>
    </section>

    <${Panel} check=${byId("S1")}>
      <ul>
        ${row(tt("demo.spike.embedded"), yn(embedded))}
        ${row(tt("demo.spike.parent_readable"), yn(parent.readable))}
        ${row(tt("demo.spike.same_origin"), yn(parent.sameOrigin))}
        ${parent.error && row(tt("demo.spike.error_name"), parent.error)}
      </ul>
    <//>

    <${Panel} check=${byId("S2")}>
      <${DataTable} columns=${varColumns} rows=${varRows} rowKey="key" caption=${tt("demo.spike.s02.caption")} />
      <ul>
        ${row(tt("demo.spike.mode"), syncStatus.mode === "dark" || syncStatus.mode === "light" ? syncStatus.mode : "-")}
        ${row(tt("demo.spike.skipped"), skipped.length ? skipped.map((s) => String(s)).join(", ") : "-")}
      </ul>
      <button class="btn small secondary" type="button" onClick=${() => safe(() => syncApi.refresh(), null)}>
        ${tt("demo.spike.refresh")}
      </button>
    <//>

    <${Panel} check=${byId("S3")}>
      <ul>
        ${row("observer", num(counters.observer))}
        ${row("poll", num(counters.poll))}
        ${row("apply", num(counters.apply))}
        ${row(tt("demo.spike.last_sync"), syncStatus.lastSync ? formatDateTime(num(syncStatus.lastSync), lang) : "-")}
      </ul>
    <//>

    <${Panel} check=${byId("S4")}>
      <ul>
        ${row(tt("demo.spike.status"), token(bridgeState.status, "unknown"))}
        ${row(tt("demo.spike.narrow"), yn(bool(bridgeState.narrow)))}
        ${row(tt("demo.spike.messages"), num(bridgeState.messages))}
        ${row(tt("demo.spike.last_message"), bridgeState.lastMessageAt ? formatDateTime(num(bridgeState.lastMessageAt), lang) : "-")}
        ${row(tt("demo.spike.insets"), insets ? ["top", "right", "bottom", "left"].map((s) => `${s} ${String(insets[s])}`).join(", ") : "-")}
      </ul>
      <${DataTable} columns=${logColumns} rows=${log} rowKey="at" caption=${tt("demo.spike.s04.caption")} empty=${tt("demo.spike.log_empty")} />
    <//>

    <${Panel} check=${byId("S5")}>
      <ul>
        ${row(tt("demo.spike.frame_top"), frameTop === null ? "-" : frameTop)}
        ${row(tt("demo.spike.narrow"), yn(bool(bridgeState.narrow)))}
        ${row(tt("demo.spike.kiosk"), yn(bool(bridgeState.kiosk)))}
        ${row(tt("demo.spike.host_bar"), yn(bool(bridgeState.hostBar)))}
        ${row(tt("demo.spike.kiosk_frozen"), yn(bool(bridgeState.kioskFrozen)))}
        ${row(tt("demo.spike.policy"), tt(POLICY_KEYS[policy]))}
      </ul>
      <div class="row">
        ${POLICIES.map(
          (p) => html`<button key=${p} class=${`btn small ${p === policy ? "" : "secondary"}`} type="button" onClick=${() => applyPolicy(p)}>
            ${tt(POLICY_KEYS[p])}
          </button>`,
        )}
      </div>
    <//>

    <${Panel} check=${byId("S6")}>
      <ul>
        ${row(tt("demo.spike.safe_area"), yn(safeArea))}
        ${row(tt("demo.spike.insets"), insets ? ["top", "right", "bottom", "left"].map((s) => `${s} ${String(insets[s])}`).join(", ") : "-")}
      </ul>
      <button class="btn small secondary" type="button" onClick=${toggleSafeArea}>${tt("demo.spike.toggle_safe_area")}</button>
    <//>

    <${Panel} check=${byId("S7")}>
      <button class="btn small secondary" type="button" onClick=${runNavigate}>${tt("demo.spike.navigate")}</button>
      <p>${tt("demo.spike.navigate_result")}: ${navigateResult === null ? "-" : yn(navigateResult)}</p>
      <p>${tt("demo.spike.embed_kind")}: ${tt(EMBED_KIND_KEYS[EMBED_KINDS.includes(embedContext.kind) ? embedContext.kind : "unknown"])}</p>
      <p>${tt("demo.spike.top_navigation")}: ${tt(TOP_KEYS[embedContext.topNavigation] || TOP_KEYS.unknown)}</p>
      <p>${tt("demo.spike.sandbox_tokens")}: ${Array.isArray(embedContext.sandbox) ? embedContext.sandbox.map((t) => SANDBOX_SHORT[t]).filter(Boolean).join(", ") || "-" : "-"}</p>
      <p>${tt("demo.spike.info_link")}: ${tt(NAV_KEYS[NAV_PATHS.includes(infoState.last) ? infoState.last : "none"])} (${num(infoState.count)})</p>
    <//>

    <${Panel} check=${byId("S8")}>
      <${CopyField} value=${tt("demo.spike.copy_sample")} label=${tt("demo.spike.copy_label")} />
      <${Field} id="spike-clipboard" label=${tt("demo.spike.clipboard_outcome")}>
        <select id="spike-clipboard" value=${clipboard || ""} onChange=${(ev) => setClipboard(ev.target.value || null)}>
          <option value="" selected=${!clipboard}>${tt("demo.spike.na")}</option>
          <option value="copied" selected=${clipboard === "copied"}>${tt("demo.spike.clip.copied")}</option>
          <option value="fallback" selected=${clipboard === "fallback"}>${tt("demo.spike.clip.fallback")}</option>
          <option value="failed" selected=${clipboard === "failed"}>${tt("demo.spike.clip.failed")}</option>
        </select>
      <//>
      <${Field} id="spike-note" label=${tt("demo.spike.note")} hint=${tt("demo.spike.note_hint")}>
        <input id="spike-note" type="text" value=${note} aria-describedby="spike-note-hint" onInput=${(ev) => setNote(ev.target.value)} />
      <//>
    <//>

    <${Panel} check=${byId("S9")}>
      <p>${tt("demo.spike.violations")}: ${Object.values(csp.counts).reduce((a, b) => a + b, 0)}</p>
      <ul>
        ${Object.entries(csp.counts).map(([key, n]) => html`<li key=${key}><code>${key}</code>: ${n}</li>`)}
      </ul>
    <//>

    <${Panel} check=${byId("S10")}>
      <button class="btn small secondary" type="button" onClick=${() => setStorage(probeStorage())}>${tt("demo.spike.storage_run")}</button>
      <p>
        ${tt("demo.spike.storage_result")}:
        ${storage === null ? "-" : html`<${Badge} kind=${storage === "ok" ? "ok" : "warn"}>${tt(STORAGE_KEYS[storage])}<//>`}
      </p>
    <//>

    <${Panel} check=${byId("S11")}>
      <button class="btn small secondary" type="button" onClick=${runWhoami}>${tt("demo.spike.whoami_run")}</button>
      ${whoamiFailed && html`<p role="alert">${tt("demo.spike.whoami_failed")}</p>`}
      ${whoami &&
      html`<ul>
        ${row(tt("demo.spike.identity"), yn(whoami.identity_present))}
        ${row(tt("demo.spike.groups"), whoami.groups.length ? whoami.groups.join(", ") : "-")}
      </ul>`}
    <//>

    <${Panel} check=${byId("S12")}>
      <ul>
        ${row(tt("demo.spike.access_path"), tt(PATH_KEYS[accessPath]))}
        ${row(tt("demo.spike.embedded"), yn(embedded))}
        ${row(tt("demo.spike.theme"), syncStatus.active ? tt("demo.theme.sync", { mode: String(syncStatus.mode) }) : tt("demo.theme.own"))}
      </ul>
    <//>

    <${Panel} check=${byId("S13")}>
      <ul>
        ${row(tt("demo.spike.embedded"), yn(embedded))}
        ${row(tt("demo.spike.theme"), syncStatus.active ? tt("demo.theme.sync", { mode: String(syncStatus.mode) }) : tt("demo.theme.own"))}
      </ul>
    <//>

    <${Panel} check=${byId("S14")}>
      <div class="row">
        <${LangSwitch} />
        <span>${syncStatus.active ? tt("demo.theme.sync", { mode: String(syncStatus.mode) }) : tt("demo.theme.own")}</span>
      </div>
    <//>

    <${Panel} check=${byId("S15")}>
      <${VersionField} id="spike-core" label=${tt("demo.spike.ha_core")} resolved=${vCore} value=${core} onChange=${setCore} max=${30} />
      <${VersionField} id="spike-frontend" label=${tt("demo.spike.ha_frontend")} resolved=${vFrontend} value=${frontend} onChange=${setFrontend} max=${30} />
      <${VersionField} id="spike-addon" label=${tt("demo.spike.addon_version")} resolved=${vAddon} value=${addon} onChange=${setAddon} max=${30} />
      <${VersionField} id="spike-app" label=${tt("demo.spike.client_app")} resolved=${vApp} value=${app} onChange=${setApp} max=${MAX_TEXT} />
    <//>

    <section class="section card">
      <h2>${tt("demo.spike.result_title")}</h2>
      <p class="muted">${tt("demo.spike.result_allowed")}</p>
      <p class="muted">${tt("demo.spike.result_forbidden")}</p>
      <${CopyField} value=${compact} label=${tt("demo.spike.result_copy")} />
      <pre class="mono spike-result">${pretty}</pre>
    </section>
  </div>`;
}
