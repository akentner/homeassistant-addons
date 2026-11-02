// Shared building blocks of the Secrets Sync page. Everything from the state is rendered as text nodes.
import { html, useState, Badge, ConfirmDialog, DataTable, toast } from "./vendor/admin-ui/ui.mjs";
import { tp, useLang, useT } from "./vendor/admin-ui/i18n.mjs";
import { formatDateTime, formatNumber, formatRelative } from "./vendor/admin-ui/format.mjs";
import { asArr, asObj, copyText, dash, isObj, MAX_KEYS, parseTime, str } from "./model.mjs";

export const useNum = () => {
  const lang = useLang();
  return (n) => formatNumber(typeof n === "number" ? n : Number(n), lang);
};

// Relative time with the full timestamp as title; "-" for a missing value.
export function When({ value, now }) {
  const lang = useLang();
  const ms = parseTime(value);
  if (ms === null) return html`<span>-</span>`;
  return html`<span title=${formatDateTime(ms, lang)}>${formatRelative(ms, lang, now)}</span>`;
}

// Key name. A double click copies it; the name never leaves the text node.
export function KeyChip({ name, synthetic, bad }) {
  const tt = useT();
  const copy = async () => {
    const result = await copyText(name);
    if (result === "copied") toast("ok", tt("copy.done"));
    else toast("info", tt(result === "selected" ? "copy.selected" : "copy.manual"));
  };
  return html`<span class="chip">
    <span class=${`key${bad ? " bad" : ""}`} title=${tt("keys.copy_hint")} onDblClick=${copy}>${name}</span>
    ${synthetic && html`<${Badge} kind="info">${tt("keys.synthetic_tag")}<//>`}
  </span>`;
}

// names: array of strings; synthetic: Set of names to badge; capped at MAX_KEYS.
export function KeyList({ names, synthetic, bad }) {
  const tt = useT();
  const num = useNum();
  const list = asArr(names).map(str);
  if (!list.length) return html`<p class="muted">${tt("keys.none")}</p>`;
  return html`<div class="chips">
    ${list.slice(0, MAX_KEYS).map((name, i) => html`<${KeyChip} key=${`${i}:${name}`} name=${name} synthetic=${Boolean(synthetic && synthetic.has(name))} bad=${bad} />`)}
    ${list.length > MAX_KEYS && html`<span class="muted">${tt("keys.more", { n: num(list.length - MAX_KEYS) })}</span>`}
  </div>`;
}

export function Stat({ label, children }) {
  return html`<div class="stat"><div class="hint">${label}</div><div>${children}</div></div>`;
}

const codeOrDash = (v) => (str(v) ? html`<code>${str(v)}</code>` : "-");

function resultLabel(tt, value) {
  switch (value) {
    case "unchanged":
      return tt("check.result.unchanged");
    case "changed":
      return tt("check.result.changed");
    case "error":
      return tt("check.result.error");
    case "unsupported":
      return tt("check.result.unsupported");
    default:
      return dash(value);
  }
}

export function GeneralCard({ state, now }) {
  const tt = useT();
  const num = useNum();
  const versions = asObj(state.versions);
  const check = state.check;
  return html`<section class="card section" aria-labelledby="general-title">
    <h2 id="general-title">${tt("general.title")}</h2>
    <div class="stats">
      <${Stat} label=${tt("general.last_sync")}><${When} value=${state.last_success_at} now=${now} /><//>
      <${Stat} label=${tt("general.last_attempt")}><${When} value=${state.last_attempt_at} now=${now} /><//>
      <${Stat} label=${tt("general.next_sync")}><${When} value=${state.next_sync_at} now=${now} /><//>
      <${Stat} label=${tt("general.items")}>${typeof state.items === "number" ? num(state.items) : "-"}<//>
      <${Stat} label=${tt("general.version")}>${dash(versions.addon)}<//>
      <${Stat} label=${tt("general.error")}>${codeOrDash(state.error_code)}<//>
      <${Stat} label=${tt("general.bw")}>${dash(versions.bw)}<//>
      <${Stat} label=${tt("general.sops")}>${dash(versions.sops)}<//>
      ${isObj(check) &&
      html`<${Stat} label=${tt("check.title")}>
          ${check.enabled === true ? tt("check.every", { n: num(check.interval) }) : tt("check.disabled")}
        <//>
        <${Stat} label=${tt("check.last")}><${When} value=${check.last_check_at} now=${now} /><//>
        <${Stat} label=${tt("check.result")}>
          <span class=${`result ${["unchanged", "changed", "error", "unsupported"].includes(check.result) ? check.result : ""}`}>
            ${resultLabel(tt, check.result)}
          </span>
        <//>
        <${Stat} label=${tt("check.error")}>${codeOrDash(check.error_code)}<//>
        <${Stat} label=${tt("check.triggered")}>${num(check.triggered_syncs === undefined ? 0 : check.triggered_syncs)}<//>`}
    </div>
  </section>`;
}

export function ProvidersCard({ state }) {
  const tt = useT();
  const num = useNum();
  const providers = asObj(state.providers);
  const rows = Object.keys(providers)
    .sort()
    .map((name) => ({ name, ...asObj(providers[name]) }));
  const columns = [
    { key: "name", titleKey: "providers.col.provider" },
    { key: "status", titleKey: "providers.col.status", render: (r) => codeOrDash(typeof r.status === "string" ? r.status : "unknown") },
    { key: "items", titleKey: "providers.col.items", render: (r) => (typeof r.items === "number" ? num(r.items) : "-") },
    { key: "revision", titleKey: "providers.col.revision", render: (r) => codeOrDash(r.revision) },
    { key: "last_success_at", titleKey: "providers.col.last_success", render: (r) => html`<${When} value=${r.last_success_at} />` },
    { key: "error_code", titleKey: "providers.col.error", render: (r) => codeOrDash(r.error_code) },
    {
      key: "problems",
      titleKey: "providers.col.problems",
      render: (r) =>
        asArr(r.problems).map((p, i) => {
          const problem = asObj(p);
          return html`<div key=${i}><span class=${problem.severity === "error" ? "result error" : "result warning"}>${str(problem.severity)}</span> <code>${str(problem.code)}</code> ${str(problem.message)}</div>`;
        }),
    },
  ];
  return html`<section class="card section" aria-labelledby="providers-title">
    <h2 id="providers-title">${tt("providers.title")}</h2>
    <div class="scroll">
      <${DataTable} columns=${columns} rows=${rows} rowKey="name" caption=${tt("providers.caption")} empty=${tt("providers.none")} />
    </div>
  </section>`;
}

// Only rendered while error_code is shrink_guard and guard is an object. onApply performs POST api/sync?force=1.
export function GuardCard({ state, onApply }) {
  const tt = useT();
  const num = useNum();
  const [asking, setAsking] = useState(false);
  const guard = state.error_code === "shrink_guard" && isObj(state.guard) ? state.guard : null;
  if (!guard) return null;
  const removed = asArr(guard.removed);
  const added = asArr(guard.added);
  const changed = asArr(guard.changed);
  const confirm = async () => {
    await onApply();
    setAsking(false);
  };
  return html`<section class="card section guard" aria-labelledby="guard-title">
    <h2 id="guard-title" class="bad">${tt("guard.title")}</h2>
    <p>${tt("guard.text", { new: dash(guard.new_items), last: dash(guard.last_items) })}</p>
    <h3 class="bad">${tt("guard.removed", { n: num(removed.length) })}</h3>
    <${KeyList} names=${removed} bad=${true} />
    <h3>${tt("guard.added", { n: num(added.length) })}</h3>
    <${KeyList} names=${added} />
    <h3>${tt("guard.changed", { n: num(changed.length) })}</h3>
    <${KeyList} names=${changed} />
    <p><button class="btn danger" type="button" onClick=${() => setAsking(true)}>${tt("guard.apply")}</button></p>
    ${asking &&
    html`<${ConfirmDialog}
      title=${tt("guard.confirm_title")}
      message=${tt("guard.confirm_message", { n: num(removed.length) })}
      confirmLabel=${tt("guard.confirm_label")}
      expected=${tt("guard.confirm_word")}
      danger=${true}
      onConfirm=${confirm}
      onCancel=${() => setAsking(false)}
    />`}
  </section>`;
}

// Result of POST api/preview: key names only.
export function PreviewPanel({ result, onClose }) {
  const tt = useT();
  const num = useNum();
  const r = asObj(result);
  const errors = asArr(r.errors);
  const errorText = (e) => (typeof e === "string" ? e : isObj(e) ? `${str(e.code)} ${str(e.message)}`.trim() : str(e));
  return html`<section class="card section" aria-labelledby="preview-title">
    <div class="row">
      <h2 id="preview-title">${tt("preview.title")}</h2>
      <button class="btn small secondary" type="button" onClick=${onClose}>${tt("btn.close")}</button>
    </div>
    <h3>${tt("keys.added", { n: num(asArr(r.added).length) })}</h3>
    <${KeyList} names=${r.added} />
    <h3 class="bad">${tt("keys.removed", { n: num(asArr(r.removed).length) })}</h3>
    <${KeyList} names=${r.removed} bad=${true} />
    <h3>${tt("keys.changed", { n: num(asArr(r.changed).length) })}</h3>
    <${KeyList} names=${r.changed} />
    ${errors.length > 0 &&
    html`<h3 class="bad">${tt("preview.errors", { n: num(errors.length) })}</h3>
      ${errors.map((e, i) => html`<div key=${i} class="notice error">${errorText(e)}</div>`)}`}
  </section>`;
}

export const usesLabel = (n) => tp("usage.uses", n);
