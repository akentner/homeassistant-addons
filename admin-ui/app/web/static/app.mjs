// Demo page seed (tracer): shows the add-on health as a Badge. Relative URLs only (the page lives below an ingress path).
import { html, render, useState, useEffect, Badge } from "./lib/ui.mjs";
import { get } from "./lib/api.mjs";

export function App() {
  const [health, setHealth] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    get("health").then(
      (data) => live && setHealth(data),
      () => live && setFailed(true),
    );
    return () => {
      live = false;
    };
  }, []);
  const status = failed ? "error" : health ? String(health.status) : "loading";
  const kind = failed ? "error" : !health ? "muted" : status === "ok" ? "ok" : "warn";
  return html`<header>
    <h1>Admin UI</h1>
    <${Badge} kind=${kind}>${status}<//>
  </header>`;
}

if (typeof document !== "undefined" && document.getElementById("app")) {
  render(html`<${App} />`, document.getElementById("app"));
}
