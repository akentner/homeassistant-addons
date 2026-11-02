// Focus helpers and unique ids. They walk childNodes (no selector engine), so they behave the same in browsers
// and in the fake DOM used by the node tests.
import { useRef } from "./vendor/preact-htm.mjs";

const NATIVE = new Set(["button", "select", "textarea", "input"]);

const hasAttr = (el, name) => typeof el.getAttribute === "function" && el.getAttribute(name) !== null;

function isTabbable(el) {
  if (el.disabled === true || hasAttr(el, "disabled")) return false;
  const raw = el.getAttribute("tabindex");
  const index = raw === null || raw.trim() === "" ? null : Number(raw);
  if (index !== null && Number.isFinite(index)) return index >= 0;
  if (NATIVE.has(el.localName)) return el.localName !== "input" || String(el.getAttribute("type")).toLowerCase() !== "hidden";
  return el.localName === "a" && hasAttr(el, "href");
}

// Tabbable descendants of root in document order. The root itself and hidden subtrees are skipped.
export function tabbables(root) {
  const out = [];
  const walk = (node) => {
    for (const child of node.childNodes || []) {
      if (child.nodeType !== 1) continue;
      if (child.hidden === true || hasAttr(child, "hidden")) continue;
      if (isTabbable(child)) out.push(child);
      walk(child);
    }
  };
  walk(root);
  return out;
}

// Element that must receive focus to keep Tab inside a dialog, or null when the browser may move focus itself.
export function nextTabTarget(list, active, backwards) {
  if (!list.length) return null;
  const at = list.indexOf(active);
  if (backwards) return at <= 0 ? list[list.length - 1] : null;
  return at === -1 || at === list.length - 1 ? list[0] : null;
}

let uidCounter = 0;

// Stable id per component instance, e.g. "modal-3".
export function useUid(prefix = "id") {
  const ref = useRef(null);
  if (ref.current === null) ref.current = `${prefix}-${++uidCounter}`;
  return ref.current;
}
