// Minimal DOM double, just enough for Preact render and the view mount tests. Markup is never parsed.
const HTML_NS = "http://www.w3.org/1999/xhtml";
const EVENT_PROPS = [
  "onclick",
  "oninput",
  "onchange",
  "onfocus",
  "onerror",
  "onkeydown",
  "onblur",
  "onsubmit",
  "onkeyup",
  "onkeypress",
  "onpointerdown",
  "onfocusin",
  "onfocusout",
  "onmousedown",
];

class FakeNode {
  constructor(nodeType) {
    this.nodeType = nodeType;
    this.parentNode = null;
    this.childNodes = [];
  }

  get firstChild() {
    return this.childNodes[0] || null;
  }

  get lastChild() {
    return this.childNodes[this.childNodes.length - 1] || null;
  }

  get nextSibling() {
    if (!this.parentNode) return null;
    const siblings = this.parentNode.childNodes;
    return siblings[siblings.indexOf(this) + 1] || null;
  }

  get previousSibling() {
    if (!this.parentNode) return null;
    const siblings = this.parentNode.childNodes;
    return siblings[siblings.indexOf(this) - 1] || null;
  }

  removeChild(child) {
    const i = this.childNodes.indexOf(child);
    if (i >= 0) this.childNodes.splice(i, 1);
    child.parentNode = null;
    const doc = child.ownerDocument;
    if (doc && doc.activeElement && child.contains && child.contains(doc.activeElement)) doc.activeElement = null;
    return child;
  }

  insertBefore(child, ref) {
    if (child.parentNode) child.parentNode.removeChild(child);
    const i = ref ? this.childNodes.indexOf(ref) : -1;
    if (i < 0) this.childNodes.push(child);
    else this.childNodes.splice(i, 0, child);
    child.parentNode = this;
    return child;
  }

  appendChild(child) {
    return this.insertBefore(child, null);
  }

  remove() {
    if (this.parentNode) this.parentNode.removeChild(this);
  }
}

export class FakeText extends FakeNode {
  constructor(data) {
    super(3);
    this.data = String(data);
  }

  get nodeValue() {
    return this.data;
  }

  set nodeValue(v) {
    this.data = String(v);
  }

  get textContent() {
    return this.data;
  }
}

export class FakeElement extends FakeNode {
  constructor(tag) {
    super(1);
    this.localName = String(tag).toLowerCase();
    this.nodeName = String(tag).toUpperCase();
    this.namespaceURI = HTML_NS;
    this.attributes = {};
    this.listeners = {};
    this.style = { cssText: "", setProperty() {}, removeProperty() {} };
    this.disabled = false;
    this.checked = false;
    this.value = "";
    for (const name of EVENT_PROPS) this[name] = null;
  }

  get className() {
    return this.attributes.class || "";
  }

  set className(v) {
    this.attributes.class = String(v);
  }

  get textContent() {
    return this.childNodes.map((c) => c.textContent).join("");
  }

  set textContent(v) {
    this.childNodes = [];
    if (v !== "" && v !== null && v !== undefined) this.appendChild(new FakeText(v));
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
    if (name === "value") this.value = String(value);
  }

  removeAttribute(name) {
    delete this.attributes[name];
  }

  getAttribute(name) {
    return name in this.attributes ? this.attributes[name] : null;
  }

  addEventListener(type, fn) {
    (this.listeners[type] ||= []).push(fn);
  }

  removeEventListener(type, fn) {
    this.listeners[type] = (this.listeners[type] || []).filter((f) => f !== fn);
  }

  // Pass { bubbles: true } to walk the parent chain (off by default, as before).
  dispatch(type, extra = {}) {
    const { bubbles, ...rest } = extra;
    let stopped = false;
    const ev = {
      type,
      target: this,
      currentTarget: this,
      key: "",
      defaultPrevented: false,
      preventDefault() {
        ev.defaultPrevented = true;
      },
      stopPropagation() {
        stopped = true;
      },
      ...rest,
    };
    for (let node = this; node && !stopped; node = bubbles ? node.parentNode : null) {
      if (!node.listeners) continue;
      ev.currentTarget = node;
      for (const fn of [...(node.listeners[type] || [])]) fn.call(node, ev);
    }
    return ev;
  }

  get tabIndex() {
    const raw = this.attributes.tabindex;
    if (raw !== undefined && Number.isFinite(Number(raw))) return Number(raw);
    return ["a", "button", "input", "select", "textarea"].includes(this.localName) ? 0 : -1;
  }

  // True for the element itself and every descendant.
  contains(node) {
    for (let n = node; n; n = n.parentNode) if (n === this) return true;
    return false;
  }

  focus() {
    const doc = this.ownerDocument;
    if (!doc || doc.activeElement === this) return;
    const previous = doc.activeElement;
    doc.activeElement = this;
    if (previous) previous.dispatch("blur");
    this.dispatch("focus");
  }

  blur() {
    const doc = this.ownerDocument;
    if (!doc || doc.activeElement !== this) return;
    doc.activeElement = null;
    this.dispatch("blur");
  }

  select() {}
}

export function createDocument() {
  const doc = new FakeElement("#document");
  doc.activeElement = null;
  const make = (tag) => {
    const node = new FakeElement(tag);
    node.ownerDocument = doc;
    return node;
  };
  doc.createElement = make;
  doc.createElementNS = (_ns, tag) => make(tag);
  doc.createTextNode = (text) => new FakeText(text);
  doc.getElementById = () => null;
  doc.visibilityState = "visible";
  doc.execCommand = () => false;
  return doc;
}

export function findAll(node, predicate, out = []) {
  if (node.nodeType === 1 && predicate(node)) out.push(node);
  for (const child of node.childNodes) findAll(child, predicate, out);
  return out;
}

export const textOf = (node) => node.textContent;

// Property or attribute lookup (Preact sets booleans and value as properties).
export const prop = (node, name) => (name in node.attributes ? node.attributes[name] : node[name]);

export const findByText = (root, tag, text) => findAll(root, (n) => n.localName === tag && n.textContent.trim() === text);

export function install() {
  const doc = createDocument();
  globalThis.document = doc;
  globalThis.window = { addEventListener() {}, removeEventListener() {} };
  globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0);
  globalThis.cancelAnimationFrame = (id) => clearTimeout(id);
  globalThis.navigator ??= {};
  return doc;
}

export const settle = async (ticks = 6) => {
  for (let i = 0; i < ticks; i++) await new Promise((r) => setTimeout(r, 5));
};
