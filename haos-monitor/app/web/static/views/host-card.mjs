// One card per host: verdict and reasons, the measured values with violated thresholds highlighted, port chips, the SSH
// key line, blocked tasks, the last kernel error and the recent incident lines.
// Every value from the server is rendered as a text node (never as markup); all keys are literal.
import { html, Badge, ErrorNote } from "../vendor/admin-ui/ui.mjs";
import { useLang, useT } from "../vendor/admin-ui/i18n.mjs";
import { formatDateTime, formatNumber, formatRelative } from "../vendor/admin-ui/format.mjs";
import { PORTS, REASONS, ROWS, bootMs, isUnknown, isViolated, keyInfo, portState, reasonIds } from "../model.mjs";

const GLYPH = { up: "✓", down: "✗", unknown: "–" };
const BADGE_KIND = { ok: "ok", problem: "error", syncing: "info", unknown: "muted" };

function verdictOf(status) {
  if (!status) return "unknown";
  if (status.problem === 1) return "problem";
  return status.syncing === true ? "syncing" : "ok";
}

function ValueRow({ row, status, nowMs, tt, lang }) {
  const raw = status[row.field];
  let text;
  if (row.kind === "boot") {
    const boot = bootMs(status, nowMs);
    text =
      boot === null
        ? tt("hm.value.unknown")
        : tt("hm.row.up.value", { time: formatDateTime(boot, lang), relative: formatRelative(boot, lang, nowMs) });
  } else {
    text = isUnknown(raw) ? tt("hm.value.unknown") : formatNumber(raw, lang);
  }
  const bad = isViolated(status, row);
  return html`<tr class=${bad ? "bad" : ""}>
    <th scope="row">${tt(row.labelKey)}</th>
    <td>${text}${bad && html` <span class="sr-only">${tt("hm.violated")}</span>`}</td>
  </tr>`;
}

export function HostCard({ host, nowMs }) {
  const tt = useT();
  const lang = useLang();
  const status = host.status || null;
  const verdict = verdictOf(status);
  const verdictText = {
    ok: tt("hm.verdict.ok"),
    syncing: tt("hm.verdict.syncing"),
    problem: tt("hm.verdict.problem"),
    unknown: tt("hm.verdict.unknown"),
  };
  const known = new Map(REASONS.map((r) => [r.id, tt(r.labelKey)]));
  const reasons = verdict === "problem" ? reasonIds(status).map((id) => known.get(id) ?? id) : [];
  const stateText = { up: tt("hm.port.state.up"), down: tt("hm.port.state.down"), unknown: tt("hm.port.state.unknown") };
  const key = status ? keyInfo(status) : null;
  const keyText =
    key && key.kind === "invalid"
      ? tt("hm.key.invalid")
      : key && key.kind === "ok"
        ? key.type
          ? `${key.type} ${key.fp}`
          : key.fp
        : tt("hm.value.unknown");
  const incidents = Array.isArray(host.incidents) ? host.incidents : [];

  return html`<section class="card host-card" aria-label=${host.name}>
    <div class="host-head">
      <h2>${host.name}</h2>
      <span class="muted mono">${host.host}</span>
      <${Badge} kind=${BADGE_KIND[verdict]}>${verdictText[verdict]}<//>
      ${reasons.length > 0 && html`<span class="reasons">${reasons.join(", ")}</span>`}
    </div>
    ${host.error && html`<${ErrorNote} error=${{ code: host.error }} />`}
    ${status &&
    html`<table class="data values">
      <caption class="sr-only">
        ${tt("hm.values.caption", { host: host.name })}
      </caption>
      <tbody>
        ${ROWS.map((row) => html`<${ValueRow} key=${row.field} row=${row} status=${status} nowMs=${nowMs} tt=${tt} lang=${lang} />`)}
      </tbody>
    </table>`}
    ${status &&
    html`<ul class="chips" aria-label=${tt("hm.ports.label")}>
      ${PORTS.map((port) => {
        const state = portState(status, port.field);
        return html`<li key=${port.field} class=${`chip ${state}`}>
          ${tt(port.labelKey)} <span aria-hidden="true">${GLYPH[state]}</span><span class="sr-only">${stateText[state]}</span>
        </li>`;
      })}
    </ul>`}
    ${status &&
    html`<div class=${key.kind === "invalid" ? "key-line bad" : "key-line"}>
      <span class="muted">${tt("hm.key.label")}</span> <span class="mono">${keyText}</span>
    </div>`}
    ${status && status.dstate_tasks && html`<h3>${tt("hm.blocked.title")}</h3><pre class="mono log">${status.dstate_tasks}</pre>`}
    ${status && status.kmsg_last && html`<h3>${tt("hm.kmsg.title")}</h3><pre class="mono log">${status.kmsg_last}</pre>`}
    <h3>${tt("hm.incidents.title")}</h3>
    <pre class="mono log log-muted">${incidents.length > 0 ? incidents.join("\n") : tt("hm.incidents.none")}</pre>
  </section>`;
}
