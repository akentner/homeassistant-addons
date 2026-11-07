// Sample CRUD against the fake API: list, create, edit, delete with type-to-confirm, plus loading and error states.
import {
  html,
  useState,
  useAsync,
  Badge,
  ConfirmDialog,
  DataTable,
  ErrorNote,
  Field,
  Loading,
  Modal,
  toast,
} from "../lib/ui.mjs";
import { tError, useLang, useT } from "../lib/i18n.mjs";
import { formatDateTime } from "../lib/format.mjs";
import { del, get, post, put } from "../lib/api.mjs";

export const meta = { id: "crud", titleKey: "demo.nav.crud" };

// Stable backend codes plus the demo-registered teapot. A code is an identifier, so it is shown as is.
const ERROR_CODES = [
  "bad_request",
  "confirmation_required",
  "ingress_only",
  "not_found",
  "method_not_allowed",
  "conflict",
  "protected",
  "payload_too_large",
  "internal_error",
  "teapot",
];
const SLOW_MS = 600;

function Section({ title, children }) {
  return html`<section class="section card">
    <h2>${title}</h2>
    ${children}
  </section>`;
}

function EditDialog({ item, onClose, onSaved }) {
  const tt = useT();
  const [name, setName] = useState(item.name);
  const [note, setNote] = useState(item.note);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const save = async (ev) => {
    ev.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await put(`items/${item.id}`, { body: { name, note } });
      toast("ok", tt("demo.crud.saved"));
      onSaved();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  return html`<${Modal} title=${tt("demo.crud.edit_title", { name: item.name })} onClose=${onClose}>
    <form onSubmit=${save}>
      <${Field} id="crud-edit-name" label=${tt("demo.crud.field.name")}>
        <input id="crud-edit-name" type="text" value=${name} onInput=${(ev) => setName(ev.target.value)} />
      <//>
      <${Field} id="crud-edit-note" label=${tt("demo.crud.field.note")}>
        <input id="crud-edit-note" type="text" value=${note} onInput=${(ev) => setNote(ev.target.value)} />
      <//>
      <${ErrorNote} error=${error} />
      <div class="actions">
        <button class="btn secondary" type="button" onClick=${onClose}>${tt("btn.cancel")}</button>
        <button class="btn" type="submit" disabled=${busy}>${tt("btn.save")}</button>
      </div>
    </form>
  <//>`;
}

export default function Crud() {
  const tt = useT();
  const lang = useLang();
  const list = useAsync(() => get("items"), []);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [createError, setCreateError] = useState(null);
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [slow, setSlow] = useState(false);
  const [code, setCode] = useState(ERROR_CODES[0]);
  const [genError, setGenError] = useState(null);

  const create = async (ev) => {
    ev.preventDefault();
    setCreateError(null);
    try {
      await post("items", { body: { name, note } });
      toast("ok", tt("demo.crud.created"));
      setName("");
      setNote("");
      list.reload();
    } catch (err) {
      setCreateError(err);
    }
  };

  const runSlow = async () => {
    setSlow(true);
    try {
      await get("slow", { query: { ms: SLOW_MS } });
      toast("info", tt("demo.crud.slow_done"));
    } catch (err) {
      toast("error", tError(err));
    } finally {
      setSlow(false);
    }
  };

  const runError = async () => {
    setGenError(null);
    try {
      await get(`fail/${code}`);
    } catch (err) {
      setGenError(err);
      toast("error", tError(err));
    }
  };

  const columns = [
    { key: "name", titleKey: "demo.crud.col.name" },
    { key: "note", titleKey: "demo.crud.col.note" },
    {
      key: "created",
      titleKey: "demo.crud.col.created",
      render: (row) => formatDateTime(row.created, lang),
    },
    {
      key: "actions",
      titleKey: "demo.crud.col.actions",
      render: (row) =>
        html`${row.locked && html`<${Badge} kind="info">${tt("demo.crud.locked")}<//> `}
          <button
            class="btn small secondary"
            type="button"
            aria-label=${tt("demo.crud.edit_item", { name: row.name })}
            onClick=${() => setEditing(row)}
          >
            ${tt("demo.crud.edit")}
          </button>
          <button
            class="btn small danger"
            type="button"
            aria-label=${tt("demo.crud.delete_item", { name: row.name })}
            onClick=${() => setDeleting(row)}
          >
            ${tt("btn.delete")}
          </button>`,
    },
  ];

  const items = list.data && Array.isArray(list.data.items) ? list.data.items : [];
  const reload = () => list.reload();

  return html`<div>
    <${Section} title=${tt("demo.crud.list.title")}>
      ${list.loading && !list.data && html`<${Loading} />`}
      ${list.error && html`<${ErrorNote} error=${list.error} onRetry=${reload} />`}
      ${(list.data || (!list.loading && !list.error)) &&
      html`<${DataTable}
        columns=${columns}
        rows=${items}
        rowKey="id"
        caption=${tt("demo.crud.list.caption")}
      />`}
    <//>

    <${Section} title=${tt("demo.crud.create.title")}>
      <form onSubmit=${create}>
        <${Field} id="crud-name" label=${tt("demo.crud.field.name")} hint=${tt("demo.crud.field.name_hint")}>
          <input
            id="crud-name"
            type="text"
            value=${name}
            aria-describedby="crud-name-hint"
            onInput=${(ev) => setName(ev.target.value)}
          />
        <//>
        <${Field} id="crud-note" label=${tt("demo.crud.field.note")}>
          <input id="crud-note" type="text" value=${note} onInput=${(ev) => setNote(ev.target.value)} />
        <//>
        <${ErrorNote} error=${createError} />
        <div class="actions">
          <button class="btn" type="submit">${tt("demo.crud.add")}</button>
        </div>
      </form>
    <//>

    <${Section} title=${tt("demo.crud.states.title")}>
      <div class="row">
        <button class="btn secondary" type="button" disabled=${slow} onClick=${runSlow}>
          ${tt("demo.crud.slow")}
        </button>
        ${slow && html`<${Loading} />`}
      </div>
      <div class="row">
        <${Field} id="crud-code" label=${tt("demo.crud.error_code")}>
          <select id="crud-code" value=${code} onChange=${(ev) => setCode(ev.target.value)}>
            ${ERROR_CODES.map((c) => html`<option key=${c} value=${c} selected=${c === code}>${c}</option>`)}
          </select>
        <//>
        <button class="btn secondary" type="button" onClick=${runError}>${tt("demo.crud.error_run")}</button>
      </div>
      <${ErrorNote} error=${genError} />
    <//>

    ${editing &&
    html`<${EditDialog}
      item=${editing}
      onClose=${() => setEditing(null)}
      onSaved=${() => {
        setEditing(null);
        reload();
      }}
    />`}
    ${deleting &&
    html`<${ConfirmDialog}
      danger=${true}
      expected=${deleting.name}
      title=${tt("demo.crud.delete_title")}
      message=${tt("demo.crud.delete_text", { name: deleting.name })}
      confirmLabel=${tt("btn.delete")}
      onCancel=${() => setDeleting(null)}
      onConfirm=${async () => {
        await del(`items/${deleting.id}`, { body: { confirm: deleting.name } });
        toast("ok", tt("demo.crud.deleted"));
        setDeleting(null);
        reload();
      }}
    />`}
  </div>`;
}
