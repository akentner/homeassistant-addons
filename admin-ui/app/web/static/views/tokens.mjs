// Token view: the light and dark token sets side by side in isolated panels, with live contrast ratios.
// The panels set data-theme and `theme-isolated`, so they show the real tokens even while theme-sync is active.
import { html, useEffect, useRef, useState, Badge, DataTable } from "../lib/ui.mjs";
import { useLang, useT } from "../lib/i18n.mjs";
import { formatNumber } from "../lib/format.mjs";
import { THEME_WHITELIST } from "../lib/theme-sync.mjs";
import { contrastRatio, parseColor } from "../lib/color.mjs";

export const meta = { id: "tokens", titleKey: "demo.nav.tokens" };

const TOKENS = ["bg", "fg", "card", "bd", "mut", "ok", "warn", "err", "acc", "chip", "hover", "shadow", "on-acc", "on-err"];
const THEMES = ["light", "dark"];
const MIN_RATIO = 4.5;
// [foreground, background] pairs checked against 4.5:1
const FG_ON_BG = ["fg", "mut", "ok", "warn", "err", "acc"].flatMap((fg) =>
  ["bg", "card", "chip", "hover"].map((bg) => [fg, bg]),
);
const PAIRS = [...FG_ON_BG, ["on-acc", "acc"], ["on-err", "err"]];
const THEME_KEYS = { light: "demo.tokens.theme.light", dark: "demo.tokens.theme.dark" };

function readTokens(el) {
  const out = {};
  if (typeof getComputedStyle !== "function" || !el) return out;
  try {
    const style = getComputedStyle(el);
    for (const name of TOKENS) {
      const value = String(style.getPropertyValue(`--${name}`) || "").trim();
      if (value) out[name] = value;
    }
  } catch {
    // no computed style (non-browser): values show as "-"
  }
  return out;
}

function ratioOf(values, fg, bg) {
  const a = values[fg] && parseColor(values[fg]);
  const b = values[bg] && parseColor(values[bg]);
  return a && b ? contrastRatio(a, b) : null;
}

function ThemePanel({ theme }) {
  const tt = useT();
  const lang = useLang();
  const ref = useRef(null);
  const [values, setValues] = useState({});
  useEffect(() => setValues(readTokens(ref.current)), [theme]);

  const columns = [
    { key: "pair", titleKey: "demo.tokens.col.pair" },
    { key: "ratio", titleKey: "demo.tokens.col.ratio" },
    { key: "verdict", titleKey: "demo.tokens.col.verdict" },
  ];
  const rows = PAIRS.map(([fg, bg]) => {
    const ratio = ratioOf(values, fg, bg);
    return { id: `${fg}/${bg}`, fg, bg, ratio };
  });
  const cells = [
    { ...columns[0], render: (row) => `--${row.fg} / --${row.bg}` },
    { ...columns[1], render: (row) => (row.ratio === null ? "-" : `${formatNumber(Math.round(row.ratio * 100) / 100, lang)}:1`) },
    {
      ...columns[2],
      render: (row) =>
        row.ratio === null
          ? "-"
          : html`<${Badge} kind=${row.ratio >= MIN_RATIO ? "ok" : "error"}>
              ${row.ratio >= MIN_RATIO ? tt("demo.tokens.pass") : tt("demo.tokens.fail")}
            <//>`,
    },
  ];

  return html`<div class="theme-isolated panel" data-theme=${theme} ref=${ref}>
    <h2>${tt(THEME_KEYS[theme])}</h2>
    <ul class="swatches">
      ${TOKENS.map(
        (name) => html`<li key=${name}>
          <span class=${`swatch swatch-${name}`} aria-hidden="true"></span>
          <code>--${name}</code>
          <span class="muted">${values[name] || "-"}</span>
        </li>`,
      )}
    </ul>
    <div class="card">
      <p>${tt("demo.tokens.sample_text")}</p>
      <p class="muted">${tt("demo.tokens.sample_muted")}</p>
      <div class="row">
        <${Badge} kind="ok">${tt("demo.tokens.badge.ok")}<//>
        <${Badge} kind="warn">${tt("demo.tokens.badge.warn")}<//>
        <${Badge} kind="error">${tt("demo.tokens.badge.error")}<//>
        <${Badge} kind="info">${tt("demo.tokens.badge.info")}<//>
      </div>
      <div class="row">
        <button class="btn" type="button">${tt("demo.tokens.btn.primary")}</button>
        <button class="btn secondary" type="button">${tt("demo.tokens.btn.secondary")}</button>
        <button class="btn danger" type="button">${tt("demo.tokens.btn.danger")}</button>
      </div>
    </div>
    <${DataTable} columns=${cells} rows=${rows} rowKey="id" caption=${tt("demo.tokens.caption", { theme: tt(THEME_KEYS[theme]) })} />
  </div>`;
}

function pageTheme() {
  try {
    const attr = document.documentElement && document.documentElement.getAttribute("data-theme");
    if (attr) return attr;
    if (typeof matchMedia === "function") return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    // no DOM
  }
  return "-";
}

function readSyncValue(name) {
  try {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "-";
  } catch {
    return "-";
  }
}

export default function Tokens({ ha }) {
  const tt = useT();
  const sync = ha && ha.sync;
  const readStatus = () => sync && typeof sync.status === "function" ? sync.status() : null;
  const [syncStatus, setSyncStatus] = useState(readStatus);
  useEffect(() => {
    const refresh = () => setSyncStatus(readStatus());
    refresh();
    return sync && typeof sync.subscribe === "function" ? sync.subscribe(refresh) : undefined;
  }, [sync]);
  const sourceStatus = (applied) => applied ? tt("demo.tokens.applied") : tt("demo.tokens.fallback");
  const syncRows = THEME_WHITELIST.map((entry) => ({
    id: entry.key, source: entry.ha, target: entry.sync,
    value: syncStatus?.raw?.[entry.key] || "-",
    state: sourceStatus(Boolean(syncStatus?.[entry.group])),
  }));
  syncRows.push({ id: "header-height", source: "--header-height", target: "--sync-header-height",
    value: syncStatus?.headerHeight || "56px", state: sourceStatus(Boolean(syncStatus?.headerHeight)) });
  syncRows.push({ id: "on-acc", source: tt("demo.tokens.derived"), target: "--sync-on-acc",
    value: readSyncValue("--sync-on-acc"), state: sourceStatus(Boolean(syncStatus?.accent)) });
  const cards = syncStatus?.cardStyle || {};
  const reasonKeys = { missing: "demo.tokens.card_missing", invalid: "demo.tokens.card_invalid", contrast: "demo.tokens.card_contrast" };
  for (const entry of [
    { id: "card-background", source: "--ha-card-background → --card-background-color", target: "--sync-ha-card-background", value: cards.background, input: cards.backgroundInput, fallback: syncStatus?.raw?.card || "-", reason: cards.backgroundReason },
    { id: "card-radius", source: "--ha-card-border-radius → --ha-border-radius-lg", target: "--sync-card-radius", value: cards.radius, fallback: "8px" },
    { id: "card-shadow", source: "--ha-card-box-shadow", target: "--sync-card-shadow", value: cards.shadow, fallback: "none" },
  ]) syncRows.push({ ...entry, value: entry.input || entry.value || entry.fallback,
    state: entry.reason && reasonKeys[entry.reason] ? `${sourceStatus(false)}: ${tt(reasonKeys[entry.reason])}`
      : sourceStatus(entry.value !== null && entry.value !== undefined) });
  const syncColumns = [
    { key: "source", titleKey: "demo.tokens.source" },
    { key: "target", titleKey: "demo.tokens.target" },
    { key: "value", titleKey: "demo.tokens.value" },
    { key: "state", titleKey: "demo.tokens.col.verdict" },
  ];
  const syncText = syncStatus && syncStatus.active ? syncStatus.mode || "-" : tt("demo.tokens.sync_off");
  return html`<div>
    <p class="muted">
      ${tt("demo.tokens.page_theme", { theme: pageTheme() })} · ${tt("demo.tokens.sync_status", { state: syncText })}
    </p>
    <section class="section card">
      <h2>${tt("demo.tokens.live_sync")}</h2>
      <p class="muted">${tt("demo.tokens.live_sync_hint")}</p>
      <div class="table-scroll"><${DataTable} columns=${syncColumns} rows=${syncRows} rowKey="id" caption=${tt("demo.tokens.live_sync")} /></div>
    </section>
    <div class="grid">${THEMES.map((theme) => html`<${ThemePanel} key=${theme} theme=${theme} />`)}</div>
  </div>`;
}
