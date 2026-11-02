// Overview of all hosts: one request to api/overview every 10 s (plus the Reload button), cards in a responsive grid.
// The last good data stays on screen while a refresh runs or fails; a failure shows a localized note with a retry button.
import { html, useCallback, useEffect, useRef, useState, usePoll, ErrorNote } from "../vendor/admin-ui/ui.mjs";
import { useLang, useT } from "../vendor/admin-ui/i18n.mjs";
import { formatDateTime } from "../vendor/admin-ui/format.mjs";
import { get } from "../vendor/admin-ui/api.mjs";
import { HostCard } from "./host-card.mjs";

export const POLL_MS = 10000;

// Returns {data, error, busy, reload}. Overlapping refreshes never run (a ref guards them); results that arrive after
// unmount are dropped.
export function useOverview(pollMs = POLL_MS) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const inflight = useRef(false);
  const live = useRef(true);

  const reload = useCallback(async () => {
    if (inflight.current) return;
    inflight.current = true;
    setBusy(true);
    try {
      const next = await get("overview");
      if (!live.current) return;
      if (!next || !Array.isArray(next.hosts)) {
        setError({ code: "http_error" });
      } else {
        setData(next);
        setError(null);
      }
    } catch (err) {
      if (live.current) setError(err);
    } finally {
      inflight.current = false;
      if (live.current) setBusy(false);
    }
  }, []);

  useEffect(() => {
    live.current = true;
    reload();
    return () => {
      live.current = false;
    };
  }, []);
  usePoll(reload, pollMs);
  return { data, error, busy, reload };
}

export function Overview({ data, error, busy, reload }) {
  const tt = useT();
  const lang = useLang();
  const hosts = data && Array.isArray(data.hosts) ? data.hosts : [];
  return html`<div>
    <div class="toolbar">
      <button class="btn small secondary" type="button" disabled=${busy} onClick=${reload}>${tt("btn.reload")}</button>
    </div>
    ${error && html`<${ErrorNote} error=${error} onRetry=${reload} />`}
    ${data && hosts.length === 0 && html`<p class="muted">${tt("hm.empty")}</p>`}
    ${hosts.length > 0 &&
    html`<div class="hosts">
      ${hosts.map((host) => html`<${HostCard} key=${host.slug} host=${host} nowMs=${data.now_ms} />`)}
    </div>`}
    ${data &&
    html`<p class="hint">
      ${tt("hm.updated", { time: formatDateTime(data.now_ms, lang, { dateStyle: undefined, timeStyle: "medium" }) })}
    </p>`}
  </div>`;
}
