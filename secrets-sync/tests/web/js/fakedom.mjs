// Minimal DOM double: just what static/app.js uses. Markup is never parsed, so anything that is not
// created through createElement/createTextNode/textContent cannot show up as an element.
export class Node {
  constructor(tag, text = '') {
    this.tag = tag;
    this.children = [];
    this.attrs = {};
    this.listeners = {};
    this.className = '';
    this._text = text;
    this.hidden = false;
  }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  appendChild(c) { this.children.push(c); return c; }
  addEventListener(t, f) { (this.listeners[t] ||= []).push(f); }
  click() { (this.listeners.click || []).forEach((f) => f({})); }
  set textContent(v) { this.children = []; this._text = String(v); }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(''); }
  walk(fn) { fn(this); this.children.forEach((c) => c.walk(fn)); }
  find(pred) { const out = []; this.walk((n) => { if (pred(n)) out.push(n); }); return out; }
}

export const doc = {
  createElement: (tag) => new Node(tag),
  createTextNode: (t) => new Node('#text', t),
};

export const all = (nodes) => (Array.isArray(nodes) ? nodes : [nodes]);
export const tags = (nodes) => all(nodes).flatMap((n) => n.find(() => true).map((x) => x.tag));
export const text = (nodes) => all(nodes).map((n) => n.textContent).join('|');
