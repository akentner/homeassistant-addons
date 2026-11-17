import { html, render, useEffect, useRef, useState, ErrorNote } from "./vendor/admin-ui/ui.mjs";
import { Topbar, ErrorBoundary, useHashRoute } from "./vendor/admin-ui/shell.mjs";
import { registerStrings, t, useLang, useT } from "./vendor/admin-ui/i18n.mjs";
import { get } from "./vendor/admin-ui/api.mjs";
import { createHaBridge } from "./vendor/admin-ui/ha-bridge.mjs";
import { createThemeSync } from "./vendor/admin-ui/theme-sync.mjs";
import { installTerminalInput } from "./terminal-input.mjs";
import { installTerminalClipboard } from "./terminal-clipboard.mjs";
import de from "./strings.de.mjs";
import en from "./strings.en.mjs";

registerStrings({ de, en });
const ROUTES = ["terminal", "services", "info"];
const loadVersions = () => get("versions");
const REPOSITORY = "https://github.com/akentner/homeassistant-addons";
const DOCUMENTATION = `${REPOSITORY}/blob/main/coding-assistants/DOCS.md`;

export function openCodeUrl(href) {
  const url = new URL(href);
  url.port = "4096";
  url.pathname = "/";
  url.search = "";
  url.hash = "";
  return url.href;
}

function defaultHa() {
  try {
    return { bridge: createHaBridge({ win: globalThis.window }), sync: createThemeSync({ win: globalThis.window }) };
  } catch {
    return {};
  }
}

function setupTerminal() {
  const stopInput = installTerminalInput(document.getElementById("frameTerminal"));
  const clipboard = installTerminalClipboard(t);
  return { refreshLabels: () => clipboard.refreshLabels(), dispose() { stopInput(); clipboard.dispose(); } };
}

export function Info({ versions, error }) {
  const tt = useT();
  const rows = [
    ["addon", tt("ca.info.addon")], ["claude", "Claude Code"], ["herdr", "herdr"],
    ["opencode", "OpenCode"], ["codex", "Codex"],
  ];
  return html`<div class="info-content">
    <section class="card">
      <h2>${tt("ca.info.versions")}</h2>
      ${error && html`<${ErrorNote} error=${error} />`}
      <table class="data"><tbody>${rows.map(([key, label]) => html`<tr key=${key}>
        <th scope="row">${label}</th><td id=${`v-${key}`}>${versions?.[key] || "—"}</td>
      </tr>`)}</tbody></table>
    </section>
    <section class="card">
      <h2>${tt("ca.info.services")}</h2>
      <table class="data"><tbody>
        <tr><th scope="row">${tt("ca.info.terminal")}</th><td>${tt("ca.info.terminal.detail")}</td></tr>
        <tr><th scope="row">OpenCode</th><td>${tt("ca.info.opencode.detail")}</td></tr>
        <tr><th scope="row">${tt("ca.nav.services")}</th><td>${tt("ca.info.services.detail")}</td></tr>
        <tr><th scope="row">SSH</th><td>${tt("ca.info.ssh.detail")}</td></tr>
      </tbody></table>
    </section>
    <section class="card">
      <h2>${tt("ca.info.shortcuts")}</h2>
      <p>${tt("ca.info.newline")}</p><p>${tt("ca.info.copy")}</p>
    </section>
    <section class="card">
      <h2>${tt("ca.info.links")}</h2>
      <ul><li><a href=${DOCUMENTATION} target="_blank" rel="noopener noreferrer">${tt("ca.info.docs")}</a></li>
        <li><a href=${REPOSITORY} target="_blank" rel="noopener noreferrer">${tt("ca.info.repository")}</a></li></ul>
    </section>
  </div>`;
}

export function App({ ha, fetchVersions = loadVersions, terminalSetup = setupTerminal, initialView = "terminal" }) {
  const tt = useT();
  const lang = useLang();
  const route = useHashRoute(ROUTES, initialView);
  const active = route.id;
  const [servicesOpened, setServicesOpened] = useState(active === "services");
  const [versions, setVersions] = useState(null);
  const [error, setError] = useState(null);
  const wiring = useRef(null);
  const terminal = useRef(null);
  if (!wiring.current) wiring.current = ha || defaultHa();
  const { bridge, sync } = wiring.current;

  useEffect(() => {
    if (bridge?.start) bridge.start();
    if (sync?.start) sync.start();
    return () => { sync?.dispose?.(); bridge?.dispose?.(); };
  }, []);
  useEffect(() => {
    let disposed = false;
    Promise.resolve().then(fetchVersions).then(data => {
      if (!disposed) setVersions(data);
    }).catch(err => { if (!disposed) setError(err); });
    return () => { disposed = true; };
  }, []);
  useEffect(() => {
    terminal.current = terminalSetup();
    return () => { terminal.current?.dispose(); terminal.current = null; };
  }, []);
  useEffect(() => {
    if (globalThis.document?.documentElement) document.documentElement.lang = lang;
    terminal.current?.refreshLabels();
  }, [lang]);
  useEffect(() => { if (active === "services") setServicesOpened(true); }, [active]);

  const views = [
    { id: "terminal", titleKey: "ca.nav.terminal" },
    { id: "services", titleKey: "ca.nav.services" },
    { id: "info", titleKey: "ca.nav.info" },
  ];
  const href = globalThis.location?.href;
  return html`<div class="app-shell">
    <${Topbar} title=${tt("ca.title")} iconSrc="./icon.png" views=${views} activeId=${active}
      nav="topbar" bridge=${bridge} version=${versions?.addon} />
    <main class="workspace">
      <div class="terminal-toolbar" hidden=${active !== "terminal"}>
        <button id="copySelection" class="btn secondary small" type="button" disabled title=${tt("ca.clipboard.hint")}>${tt("ca.clipboard.copy")}</button>
        <span id="clipboardStatus" class="hint" role="status" aria-live="polite"></span>
        <span class="hint terminal-hint">${tt("ca.terminal.hint")}</span>
        ${href && html`<a class="btn secondary small" href=${openCodeUrl(href)} target="_blank" rel="noopener noreferrer" title=${tt("ca.opencode.title")}>${tt("ca.opencode.open")}</a>`}
      </div>
      <div class="frames">
        <iframe id="frameTerminal" src="./terminal/" title=${tt("ca.terminal.title")}
          class=${active === "terminal" ? "" : "hidden"} hidden=${active !== "terminal"} allow="clipboard-write"></iframe>
        <iframe id="frameServices" src=${servicesOpened || active === "services" ? "./services/" : undefined}
          title=${tt("ca.services.title")} hidden=${active !== "services"}></iframe>
        <section class="info-panel" hidden=${active !== "info"} aria-label=${tt("ca.nav.info")}>
          <${ErrorBoundary}><${Info} versions=${versions} error=${error} /><//>
        </section>
      </div>
    </main>
    <dialog id="clipboardDialog" class="clipboard-dialog" aria-labelledby="clipboardHeading" aria-describedby="clipboardHelp">
      <h2 id="clipboardHeading">${tt("ca.clipboard.title")}</h2>
      <p id="clipboardHelp">${tt("ca.clipboard.manual")}</p>
      <textarea id="clipboardText" readonly aria-label=${tt("ca.clipboard.text")} spellcheck="false"></textarea>
      <div class="dialog-actions"><button id="closeClipboard" class="btn secondary" type="button">${tt("btn.close")}</button></div>
    </dialog>
  </div>`;
}

const root = typeof document !== "undefined" && document.getElementById("app");
if (root) render(html`<${App} initialView=${root.dataset.initialView || "terminal"} />`, root);
