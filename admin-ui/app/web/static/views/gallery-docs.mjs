// Option tables and code examples of the component gallery. Texts come from i18n (key per option); code stays English.
export const COMPONENT_IDS = ["topbar", "badge", "toast", "modal", "confirm", "copy", "table", "tabs", "loading", "error", "field"];

export const DOCS = {
  "topbar": {
    "options": [
      {
        "name": "title",
        "type": "string",
        "def": "required",
        "key": "demo.gallery.doc.topbar.title"
      },
      {
        "name": "iconSrc",
        "type": "string | null",
        "def": "\"./icon\"",
        "key": "demo.gallery.doc.topbar.iconSrc"
      },
      {
        "name": "status",
        "type": "{ kind, text }",
        "def": "none",
        "key": "demo.gallery.doc.topbar.status"
      },
      {
        "name": "version",
        "type": "string",
        "def": "none",
        "key": "demo.gallery.doc.topbar.version"
      },
      {
        "name": "infoPath",
        "type": "string",
        "def": "none",
        "key": "demo.gallery.doc.topbar.infoPath"
      },
      {
        "name": "onInfoNavigate",
        "type": "(via) => void",
        "def": "none",
        "key": "demo.gallery.doc.topbar.onInfoNavigate"
      },
      {
        "name": "showLang",
        "type": "boolean",
        "def": "true",
        "key": "demo.gallery.doc.topbar.showLang"
      },
      {
        "name": "views",
        "type": "[{ id, title | titleKey, icon? }]",
        "def": "none",
        "key": "demo.gallery.doc.topbar.views"
      },
      {
        "name": "activeId",
        "type": "string",
        "def": "none",
        "key": "demo.gallery.doc.topbar.activeId"
      },
      {
        "name": "nav",
        "type": "\"tabs\" | \"topbar\"",
        "def": "\"tabs\"",
        "key": "demo.gallery.doc.topbar.nav"
      },
      {
        "name": "navLabel",
        "type": "string",
        "def": "none",
        "key": "demo.gallery.doc.topbar.navLabel"
      },
      {
        "name": "bridge",
        "type": "HaBridge",
        "def": "none",
        "key": "demo.gallery.doc.topbar.bridge"
      },
      {
        "name": "children",
        "type": "node",
        "def": "none",
        "key": "demo.gallery.doc.topbar.children"
      }
    ],
    "code": [
      "import { Topbar } from \"<lib>/shell.mjs\";",
      "",
      "html`<${Topbar}",
      "  title=\"My add-on\"",
      "  status=${{ kind: \"ok\", text: \"OK\" }}",
      "  infoPath=${\"/config/app/\" + slug + \"/config\"}",
      "  version=\"0.8.3-0\"",
      "  showLang=${false}",
      "/>`;"
    ]
  },
  "badge": {
    "options": [
      {
        "name": "kind",
        "type": "\"ok\" | \"warn\" | \"degraded\" | \"error\" | \"muted\" | \"info\"",
        "def": "\"muted\"",
        "key": "demo.gallery.doc.badge.kind"
      },
      {
        "name": "children",
        "type": "node",
        "def": "none",
        "key": "demo.gallery.doc.badge.children"
      }
    ],
    "code": [
      "import { Badge } from \"<lib>/ui.mjs\";",
      "",
      "html`<${Badge} kind=\"ok\">OK<//>`;"
    ]
  },
  "toast": {
    "options": [
      {
        "name": "kind",
        "type": "\"ok\" | \"error\" | \"info\"",
        "def": "\"info\"",
        "key": "demo.gallery.doc.toast.kind"
      },
      {
        "name": "text",
        "type": "string",
        "def": "required",
        "key": "demo.gallery.doc.toast.text"
      },
      {
        "name": "<Toasts />",
        "type": "component",
        "def": "once",
        "key": "demo.gallery.doc.toast.Toasts"
      }
    ],
    "code": [
      "import { toast, Toasts } from \"<lib>/ui.mjs\";",
      "",
      "// once, at the root:",
      "html`<${Toasts} />`;",
      "",
      "// anywhere:",
      "toast(\"ok\", \"Saved\");"
    ]
  },
  "modal": {
    "options": [
      {
        "name": "title",
        "type": "string",
        "def": "required",
        "key": "demo.gallery.doc.modal.title"
      },
      {
        "name": "onClose",
        "type": "() => void",
        "def": "required",
        "key": "demo.gallery.doc.modal.onClose"
      },
      {
        "name": "initialFocusRef",
        "type": "ref",
        "def": "first focusable",
        "key": "demo.gallery.doc.modal.initialFocusRef"
      },
      {
        "name": "children",
        "type": "node",
        "def": "none",
        "key": "demo.gallery.doc.modal.children"
      }
    ],
    "code": [
      "import { Modal } from \"<lib>/ui.mjs\";",
      "",
      "open &&",
      "  html`<${Modal} title=\"Details\" onClose=${() => setOpen(false)}>",
      "    <p>Body</p>",
      "  <//>`;"
    ]
  },
  "confirm": {
    "options": [
      {
        "name": "title",
        "type": "string",
        "def": "required",
        "key": "demo.gallery.doc.confirm.title"
      },
      {
        "name": "message",
        "type": "string",
        "def": "required",
        "key": "demo.gallery.doc.confirm.message"
      },
      {
        "name": "confirmLabel",
        "type": "string",
        "def": "Confirm",
        "key": "demo.gallery.doc.confirm.confirmLabel"
      },
      {
        "name": "cancelLabel",
        "type": "string",
        "def": "Cancel",
        "key": "demo.gallery.doc.confirm.cancelLabel"
      },
      {
        "name": "danger",
        "type": "boolean",
        "def": "false",
        "key": "demo.gallery.doc.confirm.danger"
      },
      {
        "name": "expected",
        "type": "string",
        "def": "none",
        "key": "demo.gallery.doc.confirm.expected"
      },
      {
        "name": "onConfirm",
        "type": "() => void | Promise",
        "def": "required",
        "key": "demo.gallery.doc.confirm.onConfirm"
      },
      {
        "name": "onCancel",
        "type": "() => void",
        "def": "required",
        "key": "demo.gallery.doc.confirm.onCancel"
      }
    ],
    "code": [
      "import { ConfirmDialog } from \"<lib>/ui.mjs\";",
      "",
      "html`<${ConfirmDialog}",
      "  danger=${true}",
      "  expected=\"delete\"",
      "  title=\"Delete everything?\"",
      "  message=\"This cannot be undone.\"",
      "  onCancel=${close}",
      "  onConfirm=${remove}",
      "/>`;"
    ]
  },
  "copy": {
    "options": [
      {
        "name": "value",
        "type": "string",
        "def": "required",
        "key": "demo.gallery.doc.copy.value"
      },
      {
        "name": "label",
        "type": "string",
        "def": "none",
        "key": "demo.gallery.doc.copy.label"
      }
    ],
    "code": [
      "import { CopyField } from \"<lib>/ui.mjs\";",
      "",
      "html`<${CopyField} value=${token} label=\"API token\" />`;"
    ]
  },
  "table": {
    "options": [
      {
        "name": "columns",
        "type": "[{ key, title | titleKey, render? }]",
        "def": "required",
        "key": "demo.gallery.doc.table.columns"
      },
      {
        "name": "rows",
        "type": "object[]",
        "def": "required",
        "key": "demo.gallery.doc.table.rows"
      },
      {
        "name": "rowKey",
        "type": "string | (row, i) => key",
        "def": "index",
        "key": "demo.gallery.doc.table.rowKey"
      },
      {
        "name": "caption",
        "type": "string",
        "def": "required",
        "key": "demo.gallery.doc.table.caption"
      },
      {
        "name": "empty",
        "type": "string",
        "def": "No entries",
        "key": "demo.gallery.doc.table.empty"
      }
    ],
    "code": [
      "import { DataTable } from \"<lib>/ui.mjs\";",
      "",
      "html`<${DataTable}",
      "  caption=\"Users\"",
      "  rowKey=\"id\"",
      "  columns=${[{ key: \"name\", title: \"Name\" }]}",
      "  rows=${users}",
      "/>`;"
    ]
  },
  "tabs": {
    "options": [
      {
        "name": "tabs",
        "type": "[{ id, title | titleKey }]",
        "def": "required",
        "key": "demo.gallery.doc.tabs.tabs"
      },
      {
        "name": "active",
        "type": "string",
        "def": "required",
        "key": "demo.gallery.doc.tabs.active"
      },
      {
        "name": "onChange",
        "type": "(id) => void",
        "def": "required",
        "key": "demo.gallery.doc.tabs.onChange"
      },
      {
        "name": "label",
        "type": "string",
        "def": "none",
        "key": "demo.gallery.doc.tabs.label"
      },
      {
        "name": "children",
        "type": "node",
        "def": "none",
        "key": "demo.gallery.doc.tabs.children"
      }
    ],
    "code": [
      "import { Tabs } from \"<lib>/ui.mjs\";",
      "",
      "html`<${Tabs} tabs=${tabs} active=${tab} onChange=${setTab} label=\"Sections\">",
      "  <p>Panel</p>",
      "<//>`;"
    ]
  },
  "loading": {
    "options": [],
    "code": [
      "import { Loading } from \"<lib>/ui.mjs\";",
      "",
      "data ? html`<${View} />` : html`<${Loading} />`;"
    ]
  },
  "error": {
    "options": [
      {
        "name": "error",
        "type": "{ code } | Error | null",
        "def": "none",
        "key": "demo.gallery.doc.error.error"
      },
      {
        "name": "onRetry",
        "type": "() => void",
        "def": "none",
        "key": "demo.gallery.doc.error.onRetry"
      }
    ],
    "code": [
      "import { ErrorNote } from \"<lib>/ui.mjs\";",
      "",
      "html`<${ErrorNote} error=${error} onRetry=${reload} />`;"
    ]
  },
  "field": {
    "options": [
      {
        "name": "id",
        "type": "string",
        "def": "required",
        "key": "demo.gallery.doc.field.id"
      },
      {
        "name": "label",
        "type": "string",
        "def": "required",
        "key": "demo.gallery.doc.field.label"
      },
      {
        "name": "hint",
        "type": "string",
        "def": "none",
        "key": "demo.gallery.doc.field.hint"
      },
      {
        "name": "children",
        "type": "node",
        "def": "required",
        "key": "demo.gallery.doc.field.children"
      }
    ],
    "code": [
      "import { Field } from \"<lib>/ui.mjs\";",
      "",
      "html`<${Field} id=\"name\" label=\"Name\" hint=\"Shown in the list\">",
      "  <input id=\"name\" aria-describedby=\"name-hint\" />",
      "<//>`;"
    ]
  }
};

// Code example of the live topbar; it follows the switches of the preview.
export function topbarCode({ showLang, info, version }) {
  const lines = ["html`<${Topbar}", '  title="My add-on"', '  status=${{ kind: "ok", text: "OK" }}'];
  if (info) lines.push('  infoPath="/config/app/<slug>/config"');
  if (version) lines.push('  version="0.8.3-0"');
  lines.push(`  showLang=\${${showLang}}`, "/>`;");
  return ['import { Topbar } from "<lib>/shell.mjs";', "", ...lines].join("\n");
}
