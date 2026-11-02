// Shared preact components and hooks. Text nodes only: values are never inserted as markup.
import { html, render, useState, useEffect, useMemo, useRef, useCallback } from "../vendor/preact-htm.mjs";
import { PERMISSIONS, PERMISSION_LABELS, ORIGINS, confirmMatches } from "./model.mjs";

export { html, render, useState, useEffect, useMemo, useRef, useCallback };

// ---- toasts (module-level store so any view can call toast()) ----
const TOAST_MS = 5000;
let toasts = [];
let nextToastId = 1;
const listeners = new Set();
const publish = () => listeners.forEach((fn) => fn(toasts));

export function toast(kind, text) {
  const id = nextToastId++;
  toasts = [...toasts, { id, kind: ["ok", "error", "info"].includes(kind) ? kind : "info", text: String(text) }];
  publish();
  setTimeout(() => dismissToast(id), TOAST_MS);
  return id;
}

function dismissToast(id) {
  toasts = toasts.filter((t) => t.id !== id);
  publish();
}

export function Toasts() {
  const [items, setItems] = useState(toasts);
  useEffect(() => {
    listeners.add(setItems);
    setItems(toasts);
    return () => listeners.delete(setItems);
  }, []);
  return html`<div class="toast-stack" aria-live="polite">
    ${items.map(
      (t) => html`<div key=${t.id} class=${`toast ${t.kind}`} onClick=${() => dismissToast(t.id)}>${t.text}</div>`,
    )}
  </div>`;
}

// ---- dialogs ----
export function Modal({ title, onClose, children }) {
  useEffect(() => {
    const onKey = (ev) => ev.key === "Escape" && onClose && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return html`<div class="modal-backdrop" onClick=${(ev) => ev.target === ev.currentTarget && onClose && onClose()}>
    <div class="modal" role="dialog" aria-modal="true" aria-label=${title}>
      <div class="modal-head">
        <h2>${title}</h2>
        <button class="btn small secondary" type="button" aria-label="Close" onClick=${onClose}>×</button>
      </div>
      <div class="modal-body">${children}</div>
    </div>
  </div>`;
}

export function ConfirmDialog({ title, message, confirmLabel = "Confirm", danger, expected, onConfirm, onCancel }) {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const needsText = Boolean(expected);
  const ok = !needsText || confirmMatches(typed, expected);
  const go = async () => {
    setBusy(true);
    try {
      await onConfirm();
    } finally {
      setBusy(false);
    }
  };
  return html`<${Modal} title=${title} onClose=${onCancel}>
    <p>${message}</p>
    ${needsText &&
    html`<div class="form-row">
      <label>Type <code class="mono">${expected}</code> to confirm</label>
      <input type="text" value=${typed} autocomplete="off" onInput=${(ev) => setTyped(ev.target.value)} />
    </div>`}
    <div class="actions">
      <button class="btn secondary" type="button" onClick=${onCancel}>Cancel</button>
      <button class=${`btn${danger ? " danger" : ""}`} type="button" disabled=${!ok || busy} onClick=${go}>
        ${confirmLabel}
      </button>
    </div>
  <//>`;
}

// ---- small display components ----
export function Badge({ kind = "muted", children }) {
  return html`<span class=${`badge ${kind}`}>${children}</span>`;
}

export function OriginBadge({ origin }) {
  const known = ORIGINS.includes(origin);
  return html`<${Badge} kind=${known ? origin : "muted"}>${known ? origin : String(origin || "?")}<//>`;
}

const ERROR_HINTS = {
  db_unsupported: "The ntfy auth database has an unsupported schema version. Update the add-on or ntfy.",
  db_unavailable: "The ntfy auth database is not available yet. Wait a moment and reload.",
};

export function ErrorNote({ error }) {
  if (!error) return null;
  const hint = ERROR_HINTS[error.code];
  return html`<div class="notice error" role="alert">
    <strong>${error.code || "error"}</strong>: ${error.message || String(error)}
    ${hint && html`<div class="muted">${hint}</div>`}
  </div>`;
}

export function Loading() {
  return html`<div class="muted loading">Loading…</div>`;
}

export function PermSelect({ value, onChange, includeNone, disabled }) {
  return html`<select value=${value || ""} disabled=${disabled} onChange=${(ev) => onChange(ev.target.value)}>
    ${includeNone && html`<option value="">none</option>`}
    ${PERMISSIONS.map((p) => html`<option value=${p}>${PERMISSION_LABELS[p]} (${p})</option>`)}
  </select>`;
}

export function CopyField({ value }) {
  const input = useRef(null);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      toast("ok", "Copied");
      return;
    } catch {
      // clipboard access may be blocked inside the ingress iframe: fall back to select + execCommand
    }
    try {
      input.current.select();
      toast(document.execCommand("copy") ? "ok" : "info", "Selected, press Ctrl+C if not copied");
    } catch {
      toast("info", "Selected, press Ctrl+C to copy");
    }
  };
  return html`<span class="copy-field">
    <input ref=${input} class="mono" type="text" readonly value=${value} onFocus=${(ev) => ev.target.select()} />
    <button class="btn small secondary" type="button" onClick=${copy}>Copy</button>
  </span>`;
}

// ---- hooks ----
export function useAsync(fn, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true }));
    Promise.resolve()
      .then(fn)
      .then(
        (data) => live && setState({ data, error: null, loading: false }),
        (error) => live && setState({ data: null, error, loading: false }),
      );
    return () => {
      live = false;
    };
  }, [...deps, tick]);
  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { ...state, reload };
}

export function usePoll(fn, ms) {
  const saved = useRef(fn);
  saved.current = fn;
  useEffect(() => {
    const run = () => document.visibilityState === "visible" && saved.current();
    const timer = setInterval(run, ms);
    return () => clearInterval(timer);
  }, [ms]);
}
