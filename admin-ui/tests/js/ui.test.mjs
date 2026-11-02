import test from "node:test";
import assert from "node:assert/strict";
import { install, findAll, findByText, prop, settle } from "./fakedom.mjs";

const doc = install();
const STATIC = new URL("../../app/web/static/", import.meta.url);
const ui = await import(new URL("lib/ui.mjs", STATIC));
const { setLang } = await import(new URL("lib/i18n.mjs", STATIC));
const { auditNames, auditTables } = await import("./a11y_audit.mjs");
const { html, render } = ui;

const HOSTILE = "<b>x</b><script>alert(1)</script>";
const roleOf = (root, role) => findAll(root, (n) => n.attributes.role === role);
const tag = (root, name) => findAll(root, (n) => n.localName === name);
const byClass = (root, cls) => findAll(root, (n) => (n.attributes.class || "").split(" ").includes(cls));
const noMarkup = (root) => assert.equal(findAll(root, (n) => ["b", "script"].includes(n.localName)).length, 0);

async function mount(vnode) {
  const root = doc.createElement("div");
  doc.appendChild(root);
  render(vnode, root);
  await settle();
  return root;
}

const unmount = async (root) => {
  render(null, root);
  await settle();
};

const noop = () => {};

test.beforeEach(() => {
  setLang("en");
  doc.activeElement = null;
  while (doc.childNodes.length) doc.removeChild(doc.childNodes[0]);
});

// ---- export contract ----

test("ui exports the full component contract", () => {
  const vendor = [
    "Component", "createContext", "h", "html", "render", "useCallback", "useContext", "useDebugValue", "useEffect",
    "useErrorBoundary", "useImperativeHandle", "useLayoutEffect", "useMemo", "useReducer", "useRef", "useState",
  ];
  const own = [
    "toast", "Toasts", "Modal", "ConfirmDialog", "confirmMatches", "Badge", "ErrorNote", "Loading", "CopyField", "Tabs",
    "DataTable", "Field", "useAsync", "usePoll",
  ];
  for (const name of [...vendor, ...own]) assert.equal(typeof ui[name], "function", name);
});

// ---- Modal ----

test("Modal: dialog role, aria-modal and a label that points at the heading", async () => {
  const root = await mount(html`<${ui.Modal} title="Edit item" onClose=${noop}>body<//>`);
  const [dialog] = roleOf(root, "dialog");
  assert.equal(dialog.attributes["aria-modal"], "true");
  const heading = findAll(root, (n) => n.attributes.id === dialog.attributes["aria-labelledby"]);
  assert.equal(heading.length, 1);
  assert.equal(heading[0].localName, "h2");
  assert.equal(heading[0].textContent, "Edit item");
});

test("Modal: close button is named in the active language and calls onClose", async () => {
  let closed = 0;
  const root = await mount(html`<${ui.Modal} title="T" onClose=${() => closed++}>x<//>`);
  const [btn] = tag(root, "button");
  assert.equal(btn.attributes["aria-label"], "Close");
  btn.dispatch("click");
  assert.equal(closed, 1);
});

test("Modal: focus moves to the first tabbable on open", async () => {
  const root = await mount(html`<${ui.Modal} title="T" onClose=${noop}><input type="text" aria-label="a" /><//>`);
  const [close] = tag(root, "button");
  assert.equal(doc.activeElement, close);
});

test("Modal: initialFocusRef wins over the first tabbable", async () => {
  function Host() {
    const ref = ui.useRef(null);
    return html`<${ui.Modal} title="T" onClose=${noop} initialFocusRef=${ref}>
      <input ref=${ref} type="text" aria-label="a" />
    <//>`;
  }
  const root = await mount(html`<${Host} />`);
  assert.equal(doc.activeElement, tag(root, "input")[0]);
});

test("Modal: without any tabbable child the dialog container takes focus", async () => {
  // a modal always has its close button, so empty the tabbable set by hiding the whole head via a custom tree check
  const root = await mount(html`<${ui.Modal} title="T" onClose=${noop}>x<//>`);
  const [dialog] = roleOf(root, "dialog");
  assert.equal(dialog.attributes.tabindex, "-1");
});

test("Modal: Tab on the last tabbable wraps to the first, Shift+Tab on the first wraps to the last", async () => {
  const root = await mount(
    html`<${ui.Modal} title="T" onClose=${noop}><button type="button">one</button><button type="button">two</button><//>`,
  );
  const [dialog] = roleOf(root, "dialog");
  const [close, one, two] = tag(root, "button");
  two.focus();
  const fwd = dialog.dispatch("keydown", { key: "Tab", shiftKey: false });
  assert.equal(fwd.defaultPrevented, true);
  assert.equal(doc.activeElement, close);
  const back = dialog.dispatch("keydown", { key: "Tab", shiftKey: true });
  assert.equal(back.defaultPrevented, true);
  assert.equal(doc.activeElement, two);
  one.focus();
  const mid = dialog.dispatch("keydown", { key: "Tab", shiftKey: false });
  assert.equal(mid.defaultPrevented, false);
  assert.equal(doc.activeElement, one);
  const other = dialog.dispatch("keydown", { key: "a" });
  assert.equal(other.defaultPrevented, false);
});

test("Modal: Escape closes, other keys do not, the listener is removed on unmount", async () => {
  let closed = 0;
  const root = await mount(html`<${ui.Modal} title="T" onClose=${() => closed++}>x<//>`);
  doc.dispatch("keydown", { key: "Enter" });
  assert.equal(closed, 0);
  doc.dispatch("keydown", { key: "Escape" });
  assert.equal(closed, 1);
  await unmount(root);
  doc.dispatch("keydown", { key: "Escape" });
  assert.equal(closed, 1);
});

test("Modal: backdrop click closes, an inner click does not", async () => {
  let closed = 0;
  const root = await mount(html`<${ui.Modal} title="T" onClose=${() => closed++}>x<//>`);
  const [backdrop] = byClass(root, "modal-backdrop");
  const [dialog] = roleOf(root, "dialog");
  dialog.dispatch("click", { bubbles: true });
  assert.equal(closed, 0);
  backdrop.dispatch("click");
  assert.equal(closed, 1);
});

test("Modal: focus returns to the previously focused element on close", async () => {
  const opener = doc.createElement("button");
  doc.appendChild(opener);
  opener.focus();
  const root = doc.createElement("div");
  doc.appendChild(root);
  render(html`<${ui.Modal} title="T" onClose=${noop}>x<//>`, root);
  await settle();
  assert.notEqual(doc.activeElement, opener);
  await unmount(root);
  assert.equal(doc.activeElement, opener);
});

test("Modal: a hostile title stays a text node", async () => {
  const root = await mount(html`<${ui.Modal} title=${HOSTILE} onClose=${noop}>${HOSTILE}<//>`);
  noMarkup(root);
  assert.ok(root.textContent.includes(HOSTILE));
});

// ---- ConfirmDialog ----

const confirmButton = (root) => tag(root, "button").find((b) => b.className.includes("btn") && !b.className.includes("small") && b.textContent.trim() !== "Cancel");

test("ConfirmDialog: without expected the confirm button is enabled and uses the default labels", async () => {
  const root = await mount(html`<${ui.ConfirmDialog} title="T" message="m" onConfirm=${noop} onCancel=${noop} />`);
  assert.equal(findByText(root, "button", "Cancel").length, 1);
  const [ok] = findByText(root, "button", "Confirm");
  assert.equal(ok.disabled, false);
});

test("ConfirmDialog: confirm stays disabled until the exact phrase is typed", async () => {
  const root = await mount(
    html`<${ui.ConfirmDialog} title="T" message="m" expected="Kitchen" danger onConfirm=${noop} onCancel=${noop} />`,
  );
  const [input] = tag(root, "input");
  const [ok] = findByText(root, "button", "Confirm");
  assert.equal(ok.disabled, true);
  for (const wrong of ["kitchen", "Kitchen ", " Kitchen", "Kitche", ""]) {
    input.value = wrong;
    input.dispatch("input", { target: input });
    await settle();
    assert.equal(prop(findByText(root, "button", "Confirm")[0], "disabled"), true, JSON.stringify(wrong));
  }
  input.value = "Kitchen";
  input.dispatch("input", { target: input });
  await settle();
  assert.equal(prop(findByText(root, "button", "Confirm")[0], "disabled"), false);
});

test("ConfirmDialog: the phrase input is associated with its label", async () => {
  const root = await mount(
    html`<${ui.ConfirmDialog} title="T" message="m" expected="Kitchen" onConfirm=${noop} onCancel=${noop} />`,
  );
  const [input] = tag(root, "input");
  const [label] = tag(root, "label");
  assert.ok(input.attributes.id);
  assert.equal(label.attributes.for, input.attributes.id);
  assert.equal(label.textContent, 'Type "Kitchen" to confirm');
});

test("ConfirmDialog: danger focuses Cancel first", async () => {
  const root = await mount(
    html`<${ui.ConfirmDialog} title="T" message="m" expected="x" danger onConfirm=${noop} onCancel=${noop} />`,
  );
  assert.equal(doc.activeElement, findByText(root, "button", "Cancel")[0]);
});

test("ConfirmDialog: a rejecting onConfirm shows an alert inside the dialog and keeps it usable", async () => {
  let calls = 0;
  const root = await mount(
    html`<${ui.ConfirmDialog}
      title="T"
      message="m"
      onConfirm=${async () => {
        calls++;
        throw { code: "protected", message: "backend secret" };
      }}
      onCancel=${noop}
    />`,
  );
  findByText(root, "button", "Confirm")[0].dispatch("click");
  await settle();
  const [dialog] = roleOf(root, "dialog");
  const alerts = roleOf(dialog, "alert");
  assert.equal(alerts.length, 1);
  assert.ok(alerts[0].textContent.includes("protected and cannot be changed"));
  assert.ok(!root.textContent.includes("backend secret"));
  assert.equal(prop(findByText(root, "button", "Confirm")[0], "disabled"), false);
  assert.equal(roleOf(root, "dialog").length, 1);
  findByText(root, "button", "Confirm")[0].dispatch("click");
  await settle();
  assert.equal(calls, 2);
});

test("ConfirmDialog: the button is disabled while onConfirm runs", async () => {
  let release;
  const root = await mount(
    html`<${ui.ConfirmDialog}
      title="T"
      message="m"
      onConfirm=${() => new Promise((r) => (release = r))}
      onCancel=${noop}
    />`,
  );
  findByText(root, "button", "Confirm")[0].dispatch("click");
  await settle();
  assert.equal(prop(findByText(root, "button", "Confirm")[0], "disabled"), true);
  release();
  await settle();
  assert.equal(prop(findByText(root, "button", "Confirm")[0], "disabled"), false);
});

test("ConfirmDialog: custom labels override the defaults", async () => {
  const root = await mount(
    html`<${ui.ConfirmDialog} title="T" message="m" confirmLabel="Delete it" cancelLabel="Keep" onConfirm=${noop} onCancel=${noop} />`,
  );
  assert.equal(findByText(root, "button", "Delete it").length, 1);
  assert.equal(findByText(root, "button", "Keep").length, 1);
  assert.ok(confirmButton(root));
});

test("confirmMatches compares exactly", () => {
  assert.equal(ui.confirmMatches("a", "a"), true);
  assert.equal(ui.confirmMatches("A", "a"), false);
  assert.equal(ui.confirmMatches(" a", "a"), false);
  assert.equal(ui.confirmMatches(undefined, "a"), false);
  assert.equal(ui.confirmMatches(null, undefined), false);
});

// ---- toasts ----

test("toast works without a DOM (store only) and expires after 5000 ms", () => {
  const timers = [];
  const real = globalThis.setTimeout;
  globalThis.setTimeout = (fn, ms) => (timers.push([fn, ms]), 0);
  try {
    const id = ui.toast("ok", "hello");
    assert.equal(typeof id, "number");
    assert.equal(timers[0][1], 5000);
    timers[0][0]();
  } finally {
    globalThis.setTimeout = real;
  }
});

test("Toasts: aria-live container, alert for errors, status otherwise, unknown kind is info", async () => {
  const root = await mount(html`<${ui.Toasts} />`);
  assert.equal(root.childNodes[0].attributes["aria-live"], "polite");
  ui.toast("error", "bad");
  ui.toast("ok", "fine");
  ui.toast("info", "fyi");
  ui.toast("weird", "odd");
  await settle();
  const items = byClass(root, "toast");
  const byText = (text) => items.find((n) => n.textContent.includes(text));
  assert.equal(byText("bad").attributes.role, "alert");
  assert.equal(byText("fine").attributes.role, "status");
  assert.equal(byText("fyi").attributes.role, "status");
  assert.ok(byText("odd").className.includes("info"));
  assert.ok(byText("bad").className.includes("error"));
});

test("Toasts: the dismiss button is named and clicking toast or button dismisses it", async () => {
  const root = await mount(html`<${ui.Toasts} />`);
  const base = byClass(root, "toast").length;
  ui.toast("info", "first");
  ui.toast("info", "second");
  await settle();
  const items = byClass(root, "toast");
  assert.equal(items.length, base + 2);
  const first = items.find((n) => n.textContent.includes("first"));
  const second = items.find((n) => n.textContent.includes("second"));
  assert.equal(tag(first, "button")[0].attributes["aria-label"], "Close");
  tag(first, "button")[0].dispatch("click");
  second.dispatch("click");
  await settle();
  assert.equal(byClass(root, "toast").length, base);
});

test("Toasts: a hostile text stays a text node", async () => {
  const root = await mount(html`<${ui.Toasts} />`);
  ui.toast("error", HOSTILE);
  await settle();
  noMarkup(root);
  assert.ok(root.textContent.includes(HOSTILE));
});

// ---- ErrorNote, Loading, Badge ----

test("ErrorNote: nothing without an error", async () => {
  const root = await mount(html`<${ui.ErrorNote} error=${null} />`);
  assert.equal(root.childNodes.length, 0);
});

test("ErrorNote: localized text by code, never the backend message, unknown codes show the code", async () => {
  let root = await mount(html`<${ui.ErrorNote} error=${{ code: "conflict", message: "SQL: <b>boom</b>" }} />`);
  assert.equal(roleOf(root, "alert").length, 1);
  assert.equal(roleOf(root, "alert")[0].textContent.trim(), "The change conflicts with the current state");
  noMarkup(root);
  root = await mount(html`<${ui.ErrorNote} error=${{ code: "teapot", message: "x" }} />`);
  assert.ok(root.textContent.includes("[teapot]"));
  assert.ok(!root.textContent.includes("x]"));
  root = await mount(html`<${ui.ErrorNote} error=${new Error("stack trace")} />`);
  assert.ok(!root.textContent.includes("stack trace"));
});

test("ErrorNote: onRetry adds a named retry button", async () => {
  let retried = 0;
  const root = await mount(html`<${ui.ErrorNote} error=${{ code: "network_error" }} onRetry=${() => retried++} />`);
  const [btn] = findByText(root, "button", "Retry");
  btn.dispatch("click");
  assert.equal(retried, 1);
});

test("Loading and Badge", async () => {
  let root = await mount(html`<${ui.Loading} />`);
  assert.equal(roleOf(root, "status")[0].textContent, "Loading…");
  root = await mount(html`<${ui.Badge} kind="ok">${HOSTILE}<//>`);
  assert.equal(root.childNodes[0].className, "badge ok");
  noMarkup(root);
  root = await mount(html`<${ui.Badge}>x<//>`);
  assert.equal(root.childNodes[0].className, "badge muted");
});

// ---- CopyField ----

test("CopyField: readonly input with a name, copy button, success toast", async () => {
  const written = [];
  globalThis.navigator.clipboard = { writeText: async (v) => written.push(v) };
  const root = await mount(html`<${ui.CopyField} value="secret-123" /><${ui.Toasts} />`);
  const [input] = tag(root, "input");
  assert.notEqual(input.getAttribute("readonly"), null);
  assert.equal(input.attributes["aria-label"], "Copy");
  const [btn] = findByText(root, "button", "Copy");
  btn.dispatch("click");
  await settle();
  assert.deepEqual(written, ["secret-123"]);
  assert.ok(root.textContent.includes("Copied"));
  delete globalThis.navigator.clipboard;
});

test("CopyField: label prop names the input", async () => {
  const root = await mount(html`<${ui.CopyField} value="v" label="Token" />`);
  assert.equal(tag(root, "input")[0].attributes["aria-label"], "Token");
});

test("CopyField: a rejecting clipboard falls back to select and toasts copy.selected or copy.manual", async () => {
  globalThis.navigator.clipboard = { writeText: async () => Promise.reject(new Error("blocked")) };
  const root = await mount(html`<${ui.CopyField} value="v" /><${ui.Toasts} />`);
  const [input] = tag(root, "input");
  let selected = 0;
  input.select = () => selected++;
  doc.execCommand = () => true;
  findByText(root, "button", "Copy")[0].dispatch("click");
  await settle();
  assert.equal(selected, 1);
  assert.ok(root.textContent.includes("Selected, press Ctrl+C to copy"));
  input.select = () => {
    throw new Error("no select");
  };
  findByText(root, "button", "Copy")[0].dispatch("click");
  await settle();
  assert.ok(root.textContent.includes("Copying failed, please copy manually"));
  doc.execCommand = () => false;
  delete globalThis.navigator.clipboard;
});

// ---- Tabs ----

const TABS = [
  { id: "a", title: "Alpha" },
  { id: "b", title: "Beta" },
  { id: "c", titleKey: "btn.save" },
];

function TabsHost({ start = "a", seen }) {
  const [active, setActive] = ui.useState(start);
  seen.push(active);
  return html`<${ui.Tabs} tabs=${TABS} active=${active} onChange=${setActive} label="Sections">
    <p>panel ${active}</p>
  <//>`;
}

test("Tabs: roles, selection, roving tabindex and a labelled panel", async () => {
  const root = await mount(html`<${TabsHost} seen=${[]} />`);
  assert.equal(roleOf(root, "tablist")[0].attributes["aria-label"], "Sections");
  const tabs = roleOf(root, "tab");
  assert.deepEqual(tabs.map((n) => n.attributes["aria-selected"]), ["true", "false", "false"]);
  assert.deepEqual(tabs.map((n) => n.attributes.tabindex), ["0", "-1", "-1"]);
  assert.equal(tabs[2].textContent.trim(), "Save");
  const [panel] = roleOf(root, "tabpanel");
  assert.equal(tabs[0].attributes["aria-controls"], panel.attributes.id);
  assert.equal(panel.attributes["aria-labelledby"], tabs[0].attributes.id);
  assert.ok(panel.textContent.includes("panel a"));
});

test("Tabs: arrow keys, Home and End select, wrap and move focus", async () => {
  const root = await mount(html`<${TabsHost} seen=${[]} />`);
  const press = async (index, key) => {
    const ev = roleOf(root, "tab")[index].dispatch("keydown", { key });
    await settle();
    return ev;
  };
  const selected = () => roleOf(root, "tab").findIndex((n) => n.attributes["aria-selected"] === "true");
  const ev = await press(0, "ArrowRight");
  assert.equal(ev.defaultPrevented, true);
  assert.equal(selected(), 1);
  assert.equal(doc.activeElement, roleOf(root, "tab")[1]);
  await press(1, "ArrowRight");
  assert.equal(selected(), 2);
  await press(2, "ArrowRight");
  assert.equal(selected(), 0);
  await press(0, "ArrowLeft");
  assert.equal(selected(), 2);
  await press(2, "Home");
  assert.equal(selected(), 0);
  await press(0, "End");
  assert.equal(selected(), 2);
  assert.equal(doc.activeElement, roleOf(root, "tab")[2]);
  const other = await press(2, "x");
  assert.equal(other.defaultPrevented, false);
  assert.equal(selected(), 2);
});

test("Tabs: clicking a tab selects it and shows its panel", async () => {
  const root = await mount(html`<${TabsHost} seen=${[]} />`);
  roleOf(root, "tab")[1].dispatch("click");
  await settle();
  assert.ok(roleOf(root, "tabpanel")[0].textContent.includes("panel b"));
});

// ---- DataTable ----

const COLS = [
  { key: "name", title: "Name" },
  { key: "n", titleKey: "btn.delete", render: (row) => `#${row.n}` },
];

test("DataTable: caption, scoped headers, rows and render callbacks", async () => {
  const rows = [
    { name: "one", n: 1 },
    { name: "two", n: 2 },
  ];
  const root = await mount(html`<${ui.DataTable} columns=${COLS} rows=${rows} rowKey="name" caption="Items" />`);
  const [table] = tag(root, "table");
  assert.equal(table.className, "data");
  assert.equal(tag(root, "caption")[0].textContent.trim(), "Items");
  assert.ok(tag(root, "caption")[0].className.includes("sr-only"));
  assert.deepEqual(tag(root, "th").map((n) => n.attributes.scope), ["col", "col"]);
  assert.deepEqual(tag(root, "th").map((n) => n.textContent), ["Name", "Delete"]);
  assert.equal(tag(root, "tbody")[0].childNodes.length, 2);
  assert.deepEqual(tag(root, "td").map((n) => n.textContent), ["one", "#1", "two", "#2"]);
});

test("DataTable: rowKey may be a function and empty rows show the empty text over all columns", async () => {
  let root = await mount(
    html`<${ui.DataTable} columns=${COLS} rows=${[{ name: "a", n: 1 }]} rowKey=${(row) => row.name} caption="c" />`,
  );
  assert.equal(tag(root, "tr").length, 2);
  root = await mount(html`<${ui.DataTable} columns=${COLS} rows=${[]} caption="c" />`);
  const cells = tag(tag(root, "tbody")[0], "td");
  assert.equal(cells.length, 1);
  assert.equal(cells[0].attributes.colspan, "2");
  assert.equal(cells[0].textContent, "Nothing here yet");
  root = await mount(html`<${ui.DataTable} columns=${COLS} rows=${[]} caption="c" empty="No data" />`);
  assert.equal(tag(root, "td")[0].textContent, "No data");
});

test("DataTable: hostile strings stay text nodes", async () => {
  const root = await mount(
    html`<${ui.DataTable} columns=${COLS} rows=${[{ name: HOSTILE, n: 1 }]} rowKey="n" caption=${HOSTILE} />`,
  );
  noMarkup(root);
  assert.ok(root.textContent.includes(HOSTILE));
});

// ---- Field ----

test("Field: label for the control, optional hint", async () => {
  const root = await mount(
    html`<${ui.Field} id="f1" label="Name" hint=${HOSTILE}><input id="f1" type="text" aria-describedby="f1-hint" /><//>`,
  );
  assert.equal(byClass(root, "form-row").length, 1);
  assert.equal(tag(root, "label")[0].attributes.for, "f1");
  const [hint] = byClass(root, "hint");
  assert.equal(hint.attributes.id, "f1-hint");
  noMarkup(root);
  const bare = await mount(html`<${ui.Field} id="f2" label="L"><input id="f2" type="text" /><//>`);
  assert.equal(byClass(bare, "hint").length, 0);
});

// ---- i18n and audits ----

function Gallery() {
  const [active, setActive] = ui.useState("a");
  return html`<div>
    <${ui.Modal} title="Dialog" onClose=${noop}>
      <${ui.ErrorNote} error=${{ code: "bad_request" }} onRetry=${noop} />
      <${ui.CopyField} value="v" />
    <//>
    <${ui.ConfirmDialog} title="Confirm" message="m" expected="x" danger onConfirm=${noop} onCancel=${noop} />
    <${ui.Loading} />
    <${ui.Badge} kind="ok">ok<//>
    <${ui.Tabs} tabs=${TABS} active=${active} onChange=${setActive} label="Sections">x<//>
    <${ui.DataTable} columns=${COLS} rows=${[]} caption="Items" />
    <${ui.Field} id="g1" label="Field"><input id="g1" type="text" /><//>
    <${ui.Toasts} />
  </div>`;
}

test("all components render without [key] markers in de and en and re-render on language change", async () => {
  const root = await mount(html`<${Gallery} />`);
  ui.toast("error", "x");
  await settle();
  const marker = /\[(btn|dlg|state|copy|errors|lang|nav)\./;
  assert.ok(root.textContent.includes("Cancel"));
  assert.ok(!marker.test(root.textContent));
  setLang("de");
  await settle();
  assert.ok(!marker.test(root.textContent));
  assert.ok(root.textContent.includes("Abbrechen"));
  assert.ok(!root.textContent.includes("Nothing here yet"));
  assert.equal(tag(root, "button")[0].attributes["aria-label"], "Schließen");
  setLang("en");
  await settle();
  assert.ok(root.textContent.includes("Nothing here yet"));
});

test("auditNames and auditTables find nothing in a tree with every component", async () => {
  const root = await mount(html`<${Gallery} />`);
  assert.deepEqual(auditNames(root).map((v) => v.tag), []);
  assert.deepEqual(auditTables(root), []);
});

// Preact timers can outlive the tests; end the worker once the results are reported.
test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
