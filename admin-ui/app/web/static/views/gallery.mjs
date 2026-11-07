// Component gallery: every shared component of the lib, working. Texts come from i18n, values stay text nodes.
import {
  html,
  useState,
  Badge,
  ConfirmDialog,
  CopyField,
  DataTable,
  ErrorNote,
  Field,
  Loading,
  Modal,
  Tabs,
  toast,
} from "../lib/ui.mjs";
import { Topbar } from "../lib/shell.mjs";
import { useLang, useT } from "../lib/i18n.mjs";
import { formatBytes, formatDateTime } from "../lib/format.mjs";
import { COMPONENT_IDS, DOCS, topbarCode } from "./gallery-docs.mjs";

export const meta = { id: "gallery", titleKey: "demo.nav.gallery" };

const BADGE_KINDS = ["ok", "warn", "degraded", "error", "muted", "info"];
const BADGE_KEYS = {
  ok: "demo.gallery.badge.ok",
  warn: "demo.gallery.badge.warn",
  degraded: "demo.gallery.badge.degraded",
  error: "demo.gallery.badge.error",
  muted: "demo.gallery.badge.muted",
  info: "demo.gallery.badge.info",
};
const TAB_IDS = [
  { id: "one", titleKey: "demo.gallery.tabs.one" },
  { id: "two", titleKey: "demo.gallery.tabs.two" },
  { id: "three", titleKey: "demo.gallery.tabs.three" },
];
// Fixed sample data; the first name is hostile on purpose and must render as text.
const SAMPLE_ROWS = [
  { id: "1", name: "<b>bold</b> row", note: "alpha", size: 2048, created: 1700000000000 },
  { id: "2", name: "plain row", note: "beta", size: 5242880, created: 1710000000000 },
];

const DEFAULT_COMPONENT = COMPONENT_IDS[0];

// One page per component: preview, option table and a code example. The sub-navigation picks the component through the
// hash query (#/gallery?c=<id>); an unknown id falls back to the first one.
export function componentOf(params) {
  const raw = params && typeof params.c === "string" ? params.c : "";
  return COMPONENT_IDS.includes(raw) ? raw : DEFAULT_COMPONENT;
}

function SubNav({ active }) {
  const tt = useT();
  return html`<nav class="subnav" aria-label=${tt("demo.gallery.subnav")}>
    <ul>
      ${COMPONENT_IDS.map(
        (id) => html`<li key=${id}>
          <a href=${`#/gallery?c=${id}`} aria-current=${id === active ? "page" : null}>${tt(`demo.gallery.sub.${id}`)}</a>
        </li>`,
      )}
    </ul>
  </nav>`;
}

function OptionsTable({ id }) {
  const tt = useT();
  const options = DOCS[id].options;
  if (options.length === 0) return html`<p class="muted">${tt("demo.gallery.opt.none")}</p>`;
  return html`<div class="table-scroll"><table class="data">
    <caption class="sr-only">${tt("demo.gallery.opt.caption")}</caption>
    <thead>
      <tr>
        <th scope="col">${tt("demo.gallery.col.option")}</th>
        <th scope="col">${tt("demo.gallery.col.type")}</th>
        <th scope="col">${tt("demo.gallery.col.default")}</th>
        <th scope="col">${tt("demo.gallery.col.desc")}</th>
      </tr>
    </thead>
    <tbody>
      ${options.map(
        (opt) => html`<tr key=${opt.name}>
          <td class="mono">${opt.name}</td>
          <td class="mono">${opt.type}</td>
          <td class="mono">${opt.def}</td>
          <td>${tt(opt.key)}</td>
        </tr>`,
      )}
    </tbody>
  </table></div>`;
}

function Usage({ code }) {
  const tt = useT();
  return html`<div>
    <p class="hint">${tt("demo.gallery.code.hint")}</p>
    <pre class="code" tabindex="0" aria-label=${tt("demo.gallery.code.label")}><code>${code}</code></pre>
  </div>`;
}

// Live topbar with switchable options.
function TopbarPreview({ opts, setOpts }) {
  const tt = useT();
  const switches = [
    ["showLang", opts.showLang],
    ["info", opts.info],
    ["version", opts.version],
  ];
  return html`<div>
    <div class="row" role="group" aria-label=${tt("demo.gallery.topbar.controls")}>
      ${switches.map(
        ([key, on]) => html`<label key=${key} class="row">
          <input type="checkbox" checked=${on} onChange=${(ev) => setOpts({ ...opts, [key]: ev.target.checked })} />
          ${tt(`demo.gallery.topbar.${key}`)}
        </label>`,
      )}
    </div>
    <div class="topbar-preview">
      <${Topbar}
        title=${tt("app.title")}
        status=${{ kind: "ok", text: tt("state.ok") }}
        infoPath=${opts.info ? "/config/app/local_admin_ui/config" : undefined}
        version=${opts.version ? "0.8.3-0" : undefined}
        showLang=${opts.showLang}
      />
    </div>
  </div>`;
}

function Preview({ id, topbar, setTopbar }) {
  const tt = useT();
  const lang = useLang();
  const [modalOpen, setModalOpen] = useState(false);
  const [confirmKind, setConfirmKind] = useState(null);
  const [tab, setTab] = useState("one");
  const [expanded, setExpanded] = useState(false);
  const [knownError, setKnownError] = useState(false);

  const columns = [
    { key: "name", titleKey: "demo.gallery.col.name" },
    { key: "note", titleKey: "demo.gallery.col.note" },
    { key: "size", titleKey: "demo.gallery.col.size", render: (row) => formatBytes(row.size, lang) },
    { key: "created", titleKey: "demo.gallery.col.created", render: (row) => formatDateTime(row.created, lang) },
  ];
  const phrase = tt("demo.gallery.confirm.phrase");

  if (id === "topbar") return html`<${TopbarPreview} opts=${topbar} setOpts=${setTopbar} />`;
  if (id === "badge")
    return html`<div class="row">
      ${BADGE_KINDS.map((kind) => html`<${Badge} key=${kind} kind=${kind}>${tt(BADGE_KEYS[kind])}<//>`)}
    </div>`;
  if (id === "toast")
    return html`<div class="row">
      <button class="btn secondary" type="button" onClick=${() => toast("ok", tt("demo.gallery.toast.ok_text"))}>
        ${tt("demo.gallery.toast.ok")}
      </button>
      <button class="btn secondary" type="button" onClick=${() => toast("error", tt("demo.gallery.toast.error_text"))}>
        ${tt("demo.gallery.toast.error")}
      </button>
      <button class="btn secondary" type="button" onClick=${() => toast("info", tt("demo.gallery.toast.info_text"))}>
        ${tt("demo.gallery.toast.info")}
      </button>
    </div>`;
  if (id === "modal")
    return html`<div>
      <button class="btn" type="button" onClick=${() => setModalOpen(true)}>${tt("demo.gallery.modal.open")}</button>
      ${modalOpen &&
      html`<${Modal} title=${tt("demo.gallery.modal.heading")} onClose=${() => setModalOpen(false)}>
        <p>${tt("demo.gallery.modal.text")}</p>
        <div class="actions">
          <button class="btn" type="button" onClick=${() => setModalOpen(false)}>${tt("btn.close")}</button>
        </div>
      <//>`}
    </div>`;
  if (id === "confirm")
    return html`<div>
      <div class="row">
        <button class="btn secondary" type="button" onClick=${() => setConfirmKind("plain")}>
          ${tt("demo.gallery.confirm.open_plain")}
        </button>
        <button class="btn danger" type="button" onClick=${() => setConfirmKind("danger")}>
          ${tt("demo.gallery.confirm.open_danger")}
        </button>
      </div>
      ${confirmKind === "plain" &&
      html`<${ConfirmDialog}
        title=${tt("demo.gallery.confirm.plain_title")}
        message=${tt("demo.gallery.confirm.plain_text")}
        onCancel=${() => setConfirmKind(null)}
        onConfirm=${() => {
          setConfirmKind(null);
          toast("ok", tt("demo.gallery.confirm.done"));
        }}
      />`}
      ${confirmKind === "danger" &&
      html`<${ConfirmDialog}
        danger=${true}
        expected=${phrase}
        title=${tt("demo.gallery.confirm.danger_title")}
        message=${tt("demo.gallery.confirm.danger_text")}
        confirmLabel=${tt("btn.delete")}
        onCancel=${() => setConfirmKind(null)}
        onConfirm=${() => {
          setConfirmKind(null);
          toast("ok", tt("demo.gallery.confirm.done"));
        }}
      />`}
    </div>`;
  if (id === "copy") return html`<${CopyField} value="demo-token-0123456789" label=${tt("demo.gallery.copy.label")} />`;
  if (id === "table")
    return html`<div>
      <div class="table-scroll"><table class="data">
        <caption class="sr-only">${tt("demo.gallery.table.caption")}</caption>
        <thead><tr><th scope="col">${tt("demo.gallery.col.name")}</th><th scope="col">${tt("demo.gallery.table.actions")}</th></tr></thead>
        <tbody>
          <tr><td>${tt("demo.gallery.table.plain")}</td><td></td></tr>
          <tr><td>${tt("demo.gallery.table.interactive")}</td><td class="actions">
            <button class="btn small secondary" type="button" aria-expanded=${expanded ? "true" : "false"} onClick=${() => setExpanded(!expanded)}>${tt("demo.gallery.table.expand")}</button>
            <button class="btn small secondary" type="button" disabled>${tt("btn.delete")}</button>
          </td></tr>
        </tbody>
      </table></div>
      ${expanded && html`<section class="card"><h2>${tt("demo.gallery.table.details")}</h2>
        <${DataTable} columns=${columns} rows=${SAMPLE_ROWS} rowKey="id" caption=${tt("demo.gallery.table.caption")} />
      </section>`}
      <${DataTable} columns=${columns} rows=${SAMPLE_ROWS} rowKey="id" caption=${tt("demo.gallery.table.caption")} />
    </div>`;
  if (id === "tabs")
    return html`<${Tabs} tabs=${TAB_IDS} active=${tab} onChange=${setTab} label=${tt("demo.gallery.tabs.title")}>
      <p>${tt("demo.gallery.tabs.panel", { tab })}</p>
    <//>`;
  if (id === "loading") return html`<${Loading} />`;
  if (id === "error")
    return html`<div>
      <div class="row">
        <button class="btn secondary" type="button" onClick=${() => setKnownError(!knownError)}>
          ${tt("demo.gallery.error.toggle")}
        </button>
      </div>
      ${knownError && html`<${ErrorNote} error=${{ code: "conflict" }} />`}
      <${ErrorNote} error=${{ code: "teapot" }} />
    </div>`;
  return html`<${Field} id="gallery-field" label=${tt("demo.gallery.field.label")} hint=${tt("demo.gallery.field.hint")}>
    <input id="gallery-field" type="text" aria-describedby="gallery-field-hint" />
  <//>`;
}

export default function Gallery({ params }) {
  const tt = useT();
  const id = componentOf(params);
  const [topbar, setTopbar] = useState({ showLang: false, info: true, version: true });
  const code = id === "topbar" ? topbarCode(topbar) : DOCS[id].code.join("\n");
  return html`<div class="gallery">
    <${SubNav} active=${id} />
    <section class="section card" key=${id}>
      <h2>${tt(`demo.gallery.sub.${id}`)}</h2>
      <p>${tt(`demo.gallery.desc.${id}`)}</p>
      <h3>${tt("demo.gallery.h.preview")}</h3>
      <${Preview} id=${id} topbar=${topbar} setTopbar=${setTopbar} />
      <h3>${tt("demo.gallery.h.options")}</h3>
      <${OptionsTable} id=${id} />
      <h3>${tt("demo.gallery.h.usage")}</h3>
      <${Usage} code=${code} />
    </section>
  </div>`;
}
