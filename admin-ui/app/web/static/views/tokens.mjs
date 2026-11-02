// Token view: the light and dark token sets side by side in isolated panels, with live contrast ratios.
// The panels set data-theme and `theme-isolated`, so they show the real tokens even while theme-sync is active.
import { html, useEffect, useRef, useState, Badge, DataTable } from "../lib/ui.mjs";
import { useLang, useT } from "../lib/i18n.mjs";
import { formatNumber } from "../lib/format.mjs";
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

export default function Tokens({ ha }) {
  const tt = useT();
  const syncStatus = ha && ha.sync && typeof ha.sync.status === "function" ? ha.sync.status() : null;
  const syncText = syncStatus && syncStatus.active ? syncStatus.mode || "-" : tt("demo.tokens.sync_off");
  return html`<div>
    <p class="muted">
      ${tt("demo.tokens.page_theme", { theme: pageTheme() })} · ${tt("demo.tokens.sync_status", { state: syncText })}
    </p>
    <div class="grid">${THEMES.map((theme) => html`<${ThemePanel} key=${theme} theme=${theme} />`)}</div>
  </div>`;
}
