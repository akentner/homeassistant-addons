// HAOS Monitor page shell: topbar with the overall status, the overview of all hosts and the optional HA wiring.
// Relative URLs only (the page lives below an ingress path); the lib is imported through its public modules.
import { html, render, useEffect, useRef } from "./vendor/admin-ui/ui.mjs";
import { Topbar, ErrorBoundary } from "./vendor/admin-ui/shell.mjs";
import { registerStrings, tp, useT } from "./vendor/admin-ui/i18n.mjs";
import { createHaBridge } from "./vendor/admin-ui/ha-bridge.mjs";
import { createThemeSync } from "./vendor/admin-ui/theme-sync.mjs";
import { overallStatus } from "./model.mjs";
import { Overview, useOverview } from "./views/overview.mjs";
import de from "./strings.de.mjs";
import en from "./strings.en.mjs";

registerStrings({ de, en });

// The lib modules take the window explicitly; created lazily so tests and non-browser loads never touch it.
// Failing to create them only means the page keeps its own theme (R-13).
function defaultHa() {
  try {
    return { bridge: createHaBridge({ win: globalThis.window }), sync: createThemeSync({ win: globalThis.window }) };
  } catch {
    return {};
  }
}

export function App({ ha }) {
  const tt = useT();
  const overview = useOverview();
  const wiring = useRef(null);
  if (!wiring.current) wiring.current = ha || defaultHa();
  const { bridge, sync } = wiring.current;

  useEffect(() => {
    if (bridge && typeof bridge.start === "function") bridge.start();
    if (sync && typeof sync.start === "function") sync.start();
    return () => {
      if (sync && typeof sync.dispose === "function") sync.dispose();
      if (bridge && typeof bridge.dispose === "function") bridge.dispose();
    };
  }, []);

  const info = overallStatus(overview.data, overview.error, overview.busy);
  const labels = { "state.loading": tt("state.loading"), "state.error": tt("state.error"), "state.degraded": tt("state.degraded"), "state.ok": tt("state.ok") };
  const status = { kind: info.kind, text: info.count > 0 ? tp("hm.problems", info.count) : labels[info.labelKey] };

  return html`<div>
    <${Topbar} title=${tt("app.title")} status=${status} bridge=${bridge} />
    <main>
      <${ErrorBoundary}><${Overview} ...${overview} /><//>
    </main>
  </div>`;
}

if (typeof document !== "undefined" && document.getElementById("app")) {
  render(html`<${App} />`, document.getElementById("app"));
}
