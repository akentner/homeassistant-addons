// ntfy-specific shared components. Values go in as text nodes only; every component calls useT/useLang so it
// re-renders when the language changes. Imports the lib through its public modules only.
import { html, Badge, ErrorNote as LibErrorNote } from "./vendor/admin-ui/ui.mjs";
import { useT, useLang } from "./vendor/admin-ui/i18n.mjs";
import { formatDateTime, formatRelative } from "./vendor/admin-ui/format.mjs";
import { PERMISSIONS, ORIGINS } from "./lib/model.mjs";

// Literal key tables: call sites use the table index form (tt(PERM_KEYS[p])) so the i18n scanner can follow them.
const PERM_KEYS = { rw: "perm.rw", ro: "perm.ro", wo: "perm.wo", deny: "perm.deny" };
const ORIGIN_KEYS = { gui: "origin.gui", options: "origin.options", iac: "origin.iac" };

// Extra hint line per backend error code (the primary text is errors.<code> from the string tables).
export const ERROR_HINTS = {
  db_unsupported: "hint.db_unsupported",
  db_unavailable: "hint.db_unavailable",
};

export function ErrorNote({ error, onRetry }) {
  const tt = useT();
  if (!error) return null;
  const hinted = Object.prototype.hasOwnProperty.call(ERROR_HINTS, error.code);
  return html`<${LibErrorNote} error=${error} onRetry=${onRetry} />
    ${hinted && html`<div class="hint">${tt(ERROR_HINTS[error.code])}</div>`}`;
}

export function FormNotice({ children }) {
  if (children === undefined || children === null || children === "") return null;
  return html`<div class="notice error" role="alert">${children}</div>`;
}

export function LinkButton({ onClick, disabled, ariaLabel, children }) {
  return html`<button class="link-btn" type="button" disabled=${disabled} aria-label=${ariaLabel || null} onClick=${onClick}>
    ${children}
  </button>`;
}

export function ScrollTable({ caption, children }) {
  return html`<div class="table-scroll">
    <table class="data">
      ${caption && html`<caption class="sr-only">${caption}</caption>`}
      ${children}
    </table>
  </div>`;
}

export function OriginBadge({ origin }) {
  const tt = useT();
  const known = ORIGINS.includes(origin);
  return html`<${Badge} kind=${known ? origin : "muted"}>${known ? tt(ORIGIN_KEYS[origin]) : String(origin || "?")}<//>`;
}

export function PermSelect({ value, onChange, includeNone, disabled, label }) {
  const tt = useT();
  return html`<select
    value=${value || ""}
    disabled=${disabled}
    aria-label=${label || tt("perm.label")}
    onChange=${(ev) => onChange(ev.target.value)}
  >
    ${includeNone && html`<option value="">${tt("perm.none")}</option>`}
    ${PERMISSIONS.map((p) => html`<option key=${p} value=${p}>${tt(PERM_KEYS[p])} (${p})</option>`)}
  </select>`;
}

// ts: Unix seconds. 0, null and other non-numbers read as "-".
export function TimeStamp({ ts, relative }) {
  useT();
  const lang = useLang();
  if (!ts || typeof ts !== "number") return html`<span>-</span>`;
  const full = formatDateTime(ts * 1000, lang);
  if (relative) return html`<span title=${full}>${formatRelative(ts * 1000, lang)}</span>`;
  return html`<span>${full}</span>`;
}

// ts: Unix seconds, 0 means the entry never expires.
export function ExpiryText({ ts, nowMs = Date.now() }) {
  const tt = useT();
  const lang = useLang();
  if (!ts) return html`<span>${tt("expiry.never")}</span>`;
  const date = formatDateTime(ts * 1000, lang);
  return html`<span>${ts * 1000 <= nowMs ? tt("expiry.expired", { date }) : date}</span>`;
}
