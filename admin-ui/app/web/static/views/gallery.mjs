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
import { useLang, useT } from "../lib/i18n.mjs";
import { formatBytes, formatDateTime } from "../lib/format.mjs";

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

function Section({ title, children }) {
  return html`<section class="section card">
    <h2>${title}</h2>
    ${children}
  </section>`;
}

export default function Gallery() {
  const tt = useT();
  const lang = useLang();
  const [modalOpen, setModalOpen] = useState(false);
  const [confirmKind, setConfirmKind] = useState(null);
  const [tab, setTab] = useState("one");
  const [knownError, setKnownError] = useState(false);

  const columns = [
    { key: "name", titleKey: "demo.gallery.col.name" },
    { key: "note", titleKey: "demo.gallery.col.note" },
    { key: "size", titleKey: "demo.gallery.col.size", render: (row) => formatBytes(row.size, lang) },
    { key: "created", titleKey: "demo.gallery.col.created", render: (row) => formatDateTime(row.created, lang) },
  ];
  const phrase = tt("demo.gallery.confirm.phrase");

  return html`<div>
    <${Section} title=${tt("demo.gallery.badge.title")}>
      <div class="row">
        ${BADGE_KINDS.map((kind) => html`<${Badge} key=${kind} kind=${kind}>${tt(BADGE_KEYS[kind])}<//>`)}
      </div>
    <//>

    <${Section} title=${tt("demo.gallery.toast.title")}>
      <div class="row">
        <button class="btn secondary" type="button" onClick=${() => toast("ok", tt("demo.gallery.toast.ok_text"))}>
          ${tt("demo.gallery.toast.ok")}
        </button>
        <button class="btn secondary" type="button" onClick=${() => toast("error", tt("demo.gallery.toast.error_text"))}>
          ${tt("demo.gallery.toast.error")}
        </button>
        <button class="btn secondary" type="button" onClick=${() => toast("info", tt("demo.gallery.toast.info_text"))}>
          ${tt("demo.gallery.toast.info")}
        </button>
      </div>
    <//>

    <${Section} title=${tt("demo.gallery.modal.title")}>
      <button class="btn" type="button" onClick=${() => setModalOpen(true)}>${tt("demo.gallery.modal.open")}</button>
      ${modalOpen &&
      html`<${Modal} title=${tt("demo.gallery.modal.heading")} onClose=${() => setModalOpen(false)}>
        <p>${tt("demo.gallery.modal.text")}</p>
        <div class="actions">
          <button class="btn" type="button" onClick=${() => setModalOpen(false)}>${tt("btn.close")}</button>
        </div>
      <//>`}
    <//>

    <${Section} title=${tt("demo.gallery.confirm.title")}>
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
    <//>

    <${Section} title=${tt("demo.gallery.copy.title")}>
      <${CopyField} value="demo-token-0123456789" label=${tt("demo.gallery.copy.label")} />
    <//>

    <${Section} title=${tt("demo.gallery.table.title")}>
      <${DataTable} columns=${columns} rows=${SAMPLE_ROWS} rowKey="id" caption=${tt("demo.gallery.table.caption")} />
    <//>

    <${Section} title=${tt("demo.gallery.tabs.title")}>
      <${Tabs} tabs=${TAB_IDS} active=${tab} onChange=${setTab} label=${tt("demo.gallery.tabs.title")}>
        <p>${tt("demo.gallery.tabs.panel", { tab })}</p>
      <//>
    <//>

    <${Section} title=${tt("demo.gallery.loading.title")}>
      <${Loading} />
    <//>

    <${Section} title=${tt("demo.gallery.error.title")}>
      <div class="row">
        <button class="btn secondary" type="button" onClick=${() => setKnownError(!knownError)}>
          ${tt("demo.gallery.error.toggle")}
        </button>
      </div>
      ${knownError && html`<${ErrorNote} error=${{ code: "conflict" }} />`}
      <${ErrorNote} error=${{ code: "teapot" }} />
    <//>

    <${Section} title=${tt("demo.gallery.field.title")}>
      <${Field} id="gallery-field" label=${tt("demo.gallery.field.label")} hint=${tt("demo.gallery.field.hint")}>
        <input id="gallery-field" type="text" aria-describedby="gallery-field-hint" />
      <//>
    <//>
  </div>`;
}
