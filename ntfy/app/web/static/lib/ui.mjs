// Temporary shim (removed by plan 27-05): everything comes from the synced admin-ui lib copy, except the two
// ntfy-specific components below that the old views still import from here.
import { html, Badge } from "../vendor/admin-ui/ui.mjs";
import { PERMISSIONS, PERMISSION_LABELS, ORIGINS } from "./model.mjs";

export * from "../vendor/admin-ui/ui.mjs";

export function OriginBadge({ origin }) {
  const known = ORIGINS.includes(origin);
  return html`<${Badge} kind=${known ? origin : "muted"}>${known ? origin : String(origin || "?")}<//>`;
}

export function PermSelect({ value, onChange, includeNone, disabled }) {
  return html`<select value=${value || ""} disabled=${disabled} onChange=${(ev) => onChange(ev.target.value)}>
    ${includeNone && html`<option value="">none</option>`}
    ${PERMISSIONS.map((p) => html`<option value=${p}>${PERMISSION_LABELS[p]} (${p})</option>`)}
  </select>`;
}
