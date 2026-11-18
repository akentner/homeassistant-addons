// Accessible-name and table-header audits over a rendered (fake or real) DOM tree. Plain helper, no imports, so
// it can audit any tree. Each function returns a list of violations (empty = clean).
const walk = (node, visit) => {
  if (node.nodeType === 1) visit(node);
  for (const child of node.childNodes || []) walk(child, visit);
};

const attr = (node, name) => (typeof node.getAttribute === "function" ? node.getAttribute(name) : null);
const text = (node) => String(node.textContent || "").trim();

function nameOf(node, root) {
  const label = attr(node, "aria-label");
  if (label && label.trim()) return label.trim();

  const by = attr(node, "aria-labelledby");
  if (by) {
    for (const id of by.split(/\s+/).filter(Boolean)) {
      let found = null;
      walk(root, (n) => {
        if (!found && attr(n, "id") === id) found = n;
      });
      if (found && text(found)) return text(found);
    }
  }

  const id = attr(node, "id");
  if (id) {
    let found = "";
    walk(root, (n) => {
      if (!found && n.localName === "label" && attr(n, "for") === id && text(n)) found = text(n);
    });
    if (found) return found;
  }

  for (let p = node.parentNode; p; p = p.parentNode) {
    if (p.localName === "label" && text(p)) return text(p);
  }

  const type = String(attr(node, "type") || "").toLowerCase();
  if (node.localName === "button" || node.localName === "a") return text(node);
  if (node.localName === "input" && ["button", "submit", "reset"].includes(type)) return String(node.value || "").trim();
  return "";
}

const isControl = (n) =>
  n.localName === "button" ||
  (n.localName === "a" && attr(n, "href") !== null) ||
  n.localName === "select" ||
  n.localName === "textarea" ||
  (n.localName === "input" && String(attr(n, "type")).toLowerCase() !== "hidden");

export function auditNames(root) {
  const out = [];
  walk(root, (n) => {
    if (isControl(n) && !nameOf(n, root)) out.push({ rule: "name", tag: n.localName, id: attr(n, "id"), node: n });
  });
  return out;
}

export function auditTables(root) {
  const out = [];
  walk(root, (n) => {
    if (n.localName === "th" && !attr(n, "scope")) out.push({ rule: "th-scope", tag: "th", node: n });
  });
  return out;
}
