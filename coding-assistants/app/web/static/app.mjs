import { html, render, useEffect, useRef, useState, ErrorNote } from "./vendor/admin-ui/ui.mjs";
import { Topbar, ErrorBoundary, useHashRoute } from "./vendor/admin-ui/shell.mjs";
import { registerStrings, useLang, useT } from "./vendor/admin-ui/i18n.mjs";
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

function defaultHa() {
  try {
    return { bridge: createHaBridge({ win: globalThis.window }), sync: createThemeSync({ win: globalThis.window }) };
  } catch {
    return {};
  }
}

function setupTerminal() {
  const stopInput = installTerminalInput(document.getElementById("frameTerminal"));
  const clipboard = installTerminalClipboard();
  return { dispose() { stopInput(); clipboard.dispose(); } };
}

// HA's info page of this add-on. The slug differs per installation (repository hash prefix), so run.sh reports it in
// versions.json; unknown means no link.
export function infoPath(versions) {
  const slug = versions && typeof versions.slug === "string" ? versions.slug : "";
  return /^[a-z0-9][a-z0-9_]{0,63}$/.test(slug) ? `/config/app/${slug}/info` : null;
}

// MDI path data for the navigation icons.
const ICONS = {
  terminal: "M20 19V7H4v12h16m0-16a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h16M7.5 17l-1.41-1.41L8.67 13l-2.58-2.59L7.5 9l4 4-4 4m4.5 0v-2h6v2h-6Z",
  services: "M4 1h16a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1m0 12h16a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-8a1 1 0 0 1 1-1M7 7a1 1 0 1 0 0-2 1 1 0 0 0 0 2m0 12a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z",
  info: "M11 9h2V7h-2m1 13a8 8 0 1 1 0-16 8 8 0 0 1 0 16m0-18a10 10 0 1 0 0 20 10 10 0 0 0 0-20m-1 15h2v-6h-2v6Z",
};

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
  }, [lang]);
  useEffect(() => { if (active === "services") setServicesOpened(true); }, [active]);

  const views = [
    { id: "terminal", titleKey: "ca.nav.terminal", icon: ICONS.terminal },
    { id: "services", titleKey: "ca.nav.services", icon: ICONS.services },
    { id: "info", titleKey: "ca.nav.info", icon: ICONS.info },
  ];
  return html`<div class="app-shell">
    <${Topbar} title=${tt("ca.title")} iconSrc="./icon.png" views=${views} activeId=${active}
      nav="topbar" bridge=${bridge} version=${versions?.addon} showLang=${false}
      infoPath=${infoPath(versions)} />
    <main class="workspace">
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
  </div>`;
}

const root = typeof document !== "undefined" && document.getElementById("app");
if (root) render(html`<${App} initialView=${root.dataset.initialView || "terminal"} />`, root);
