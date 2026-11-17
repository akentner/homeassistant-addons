// Shared Preact components. Text nodes only: values are never inserted as markup. All visible and aria text comes
// from i18n (every component calls useT, so it re-renders when the language changes).
import {
  Component,
  createContext,
  h,
  html,
  render,
  useCallback,
  useContext,
  useDebugValue,
  useEffect,
  useErrorBoundary,
  useImperativeHandle,
  useLayoutEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "./vendor/preact-htm.mjs";
import { useAsync, usePoll } from "./hooks.mjs";
import { t, tError, useT } from "./i18n.mjs";
import { nextTabTarget, tabbables, useUid } from "./a11y.mjs";

export {
  Component,
  createContext,
  h,
  html,
  render,
  useCallback,
  useContext,
  useDebugValue,
  useEffect,
  useErrorBoundary,
  useImperativeHandle,
  useLayoutEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  useAsync,
  usePoll,
};

// ---- toasts (module-level store so any view can call toast()) ----
const TOAST_MS = 5000;
const TOAST_KINDS = ["ok", "error", "info"];
let toasts = [];
let nextToastId = 1;
const listeners = new Set();
const publish = () => listeners.forEach((fn) => fn(toasts));

// text must already be the final (translated) string.
export function toast(kind, text) {
  const id = nextToastId++;
  toasts = [...toasts, { id, kind: TOAST_KINDS.includes(kind) ? kind : "info", text: String(text) }];
  publish();
  setTimeout(() => dismissToast(id), TOAST_MS);
  return id;
}

function dismissToast(id) {
  if (!toasts.some((item) => item.id === id)) return;
  toasts = toasts.filter((item) => item.id !== id);
  publish();
}

export function Toasts() {
  const tt = useT();
  const [items, setItems] = useState(toasts);
  useEffect(() => {
    listeners.add(setItems);
    setItems(toasts);
    return () => listeners.delete(setItems);
  }, []);
  return html`<div class="toast-stack" aria-live="polite">
    ${items.map(
      (item) => html`<div
        key=${item.id}
        class=${`toast ${item.kind}`}
        role=${item.kind === "error" ? "alert" : "status"}
        onClick=${() => dismissToast(item.id)}
      >
        ${item.text}
        <button
          class="btn small secondary"
          type="button"
          aria-label=${tt("btn.close")}
          onClick=${() => dismissToast(item.id)}
        >
          ×
        </button>
      </div>`,
    )}
  </div>`;
}

// ---- dialogs ----
// Focus moves into the dialog on open, Tab wraps inside it, Escape closes it, focus returns to the opener.
export function Modal({ title, onClose, children, initialFocusRef }) {
  const tt = useT();
  const dialog = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const titleId = `${useUid("modal")}-title`;

  useEffect(() => {
    const previous = document.activeElement;
    const root = dialog.current;
    const target = (initialFocusRef && initialFocusRef.current) || tabbables(root)[0] || root;
    target.focus();
    const onKey = (ev) => ev.key === "Escape" && closeRef.current && closeRef.current();
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      if (previous && typeof previous.focus === "function" && previous !== document.body) previous.focus();
    };
  }, []);

  const trap = (ev) => {
    if (ev.key !== "Tab") return;
    const list = tabbables(dialog.current);
    if (!list.length) return ev.preventDefault();
    const target = nextTabTarget(list, document.activeElement, ev.shiftKey);
    if (target) {
      ev.preventDefault();
      target.focus();
    }
  };

  const close = () => closeRef.current && closeRef.current();
  return html`<div class="modal-backdrop" onClick=${(ev) => ev.target === ev.currentTarget && close()}>
    <div
      class="modal"
      ref=${dialog}
      role="dialog"
      aria-modal="true"
      aria-labelledby=${titleId}
      tabindex="-1"
      onKeyDown=${trap}
    >
      <div class="modal-head">
        <h2 id=${titleId}>${title}</h2>
        <button class="btn small secondary" type="button" aria-label=${tt("btn.close")} onClick=${close}>×</button>
      </div>
      <div class="modal-body">${children}</div>
    </div>
  </div>`;
}

export const confirmMatches = (typed, expected) => typeof typed === "string" && typed === expected;

export function ConfirmDialog({ title, message, confirmLabel, cancelLabel, danger, expected, onConfirm, onCancel }) {
  const tt = useT();
  const uid = useUid("confirm");
  const cancelRef = useRef(null);
  const inputRef = useRef(null);
  const live = useRef(true);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  useEffect(
    () => () => {
      live.current = false;
    },
    [],
  );
  const needsText = Boolean(expected);
  const ok = !needsText || confirmMatches(typed, expected);
  const go = async () => {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
    } catch (err) {
      if (live.current) setError(err || new Error("confirm failed"));
    } finally {
      if (live.current) setBusy(false);
    }
  };
  const inputId = `${uid}-phrase`;
  return html`<${Modal} title=${title} onClose=${onCancel} initialFocusRef=${danger ? cancelRef : needsText ? inputRef : null}>
    <p>${message}</p>
    ${needsText &&
    html`<div class="form-row">
      <label for=${inputId}>${tt("dlg.type_to_confirm", { phrase: expected })}</label>
      <input
        id=${inputId}
        ref=${inputRef}
        type="text"
        value=${typed}
        autocomplete="off"
        onInput=${(ev) => setTyped(ev.target.value)}
      />
    </div>`}
    <${ErrorNote} error=${error} />
    <div class="actions">
      <button class="btn secondary" type="button" ref=${cancelRef} onClick=${onCancel}>
        ${cancelLabel || tt("btn.cancel")}
      </button>
      <button class=${`btn${danger ? " danger" : ""}`} type="button" disabled=${!ok || busy} onClick=${go}>
        ${confirmLabel || tt("btn.confirm")}
      </button>
    </div>
  <//>`;
}

// ---- small display components ----
export function Badge({ kind = "muted", children }) {
  return html`<span class=${`badge ${kind}`}>${children}</span>`;
}

// Localised by error code; the backend message is never shown.
export function ErrorNote({ error, onRetry }) {
  const tt = useT();
  if (!error) return null;
  return html`<div class="notice error" role="alert">
    ${tError(error)}
    ${onRetry &&
    html`<button class="btn small secondary" type="button" onClick=${onRetry}>${tt("btn.retry")}</button>`}
  </div>`;
}

export function Loading() {
  const tt = useT();
  return html`<div class="muted loading" role="status">${tt("state.loading")}</div>`;
}

export function CopyField({ value, label }) {
  const tt = useT();
  const input = useRef(null);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      toast("ok", t("copy.done"));
      return;
    } catch {
      // clipboard access may be blocked inside the ingress iframe: fall back to select + execCommand
    }
    try {
      input.current.select();
      toast(document.execCommand("copy") ? "ok" : "info", t("copy.selected"));
    } catch {
      toast("info", t("copy.manual"));
    }
  };
  return html`<span class="copy-field">
    <input
      ref=${input}
      class="mono"
      type="text"
      readonly
      aria-label=${label || tt("btn.copy")}
      value=${value}
      onFocus=${(ev) => ev.target.select()}
    />
    <button class="btn small secondary" type="button" onClick=${copy}>${tt("btn.copy")}</button>
  </span>`;
}

const titleOf = (item, tt) => (item.titleKey ? tt(item.titleKey) : item.title);

// tabs: [{id, title | titleKey}]. children render inside the tabpanel of the active tab.
export function Tabs({ tabs, active, onChange, label, children }) {
  const tt = useT();
  const uid = useUid("tabs");
  const refs = useRef({});
  const panelId = `${uid}-panel`;
  const tabId = (id) => `${uid}-tab-${id}`;
  const onKey = (ev, index) => {
    const last = tabs.length - 1;
    const next = { ArrowRight: index >= last ? 0 : index + 1, ArrowLeft: index <= 0 ? last : index - 1, Home: 0, End: last }[
      ev.key
    ];
    if (next === undefined) return;
    ev.preventDefault();
    onChange(tabs[next].id);
    const el = refs.current[tabs[next].id];
    if (el) el.focus();
  };
  return html`<div>
    <div class="tablist" role="tablist" aria-label=${label}>
      ${tabs.map(
        (tab, index) => html`<button
          key=${tab.id}
          id=${tabId(tab.id)}
          ref=${(el) => (refs.current[tab.id] = el)}
          class="tab"
          type="button"
          role="tab"
          aria-selected=${tab.id === active ? "true" : "false"}
          aria-controls=${panelId}
          tabindex=${tab.id === active ? "0" : "-1"}
          onClick=${() => onChange(tab.id)}
          onKeyDown=${(ev) => onKey(ev, index)}
        >
          ${titleOf(tab, tt)}
        </button>`,
      )}
    </div>
    <div class="tabpanel" id=${panelId} role="tabpanel" aria-labelledby=${tabId(active)}>${children}</div>
  </div>`;
}

// columns: [{key, title | titleKey, render?(row)}]; rowKey: property name or function(row, index).
export function DataTable({ columns, rows, rowKey, caption, empty }) {
  const tt = useT();
  const keyOf = (row, index) => (typeof rowKey === "function" ? rowKey(row, index) : rowKey ? row[rowKey] : index);
  return html`<table class="data">
    <caption class="sr-only">
      ${caption}
    </caption>
    <thead>
      <tr>
        ${columns.map((col) => html`<th key=${col.key} scope="col">${titleOf(col, tt)}</th>`)}
      </tr>
    </thead>
    <tbody>
      ${rows && rows.length
        ? rows.map(
            (row, index) => html`<tr key=${keyOf(row, index)}>
              ${columns.map((col) => html`<td key=${col.key}>${col.render ? col.render(row) : row[col.key]}</td>`)}
            </tr>`,
          )
        : html`<tr>
            <td colspan=${columns.length} class="muted">${empty ?? tt("state.empty")}</td>
          </tr>`}
    </tbody>
  </table>`;
}

// Label plus control. The caller links a hint with aria-describedby="<id>-hint" on the control.
export function Field({ id, label, hint, children }) {
  return html`<div class="form-row">
    <label for=${id}>${label}</label>
    ${children} ${hint && html`<span class="hint" id=${`${id}-hint`}>${hint}</span>`}
  </div>`;
}
