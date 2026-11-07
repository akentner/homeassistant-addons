// Language and formatting view: t() with parameters, tp() plurals, Intl formatting and localized backend errors.
import { html, useState, useAsync, ErrorNote, Loading } from "../lib/ui.mjs";
import { tp, useLang, useT } from "../lib/i18n.mjs";
import { LangSwitch } from "../lib/shell.mjs";
import { formatBytes, formatDateTime, formatNumber, formatRelative } from "../lib/format.mjs";
import { get } from "../lib/api.mjs";

export const meta = { id: "language", titleKey: "demo.nav.language" };

// Fixed reference values keep the output stable; "now" for the relative examples is fixed as well.
const SAMPLE_TIME = 1700000000000;
const OFFSETS_S = [-90, -10800, -172800, 86400];
const PROBE_CODES = ["teapot", "conflict"];

function Section({ title, children }) {
  return html`<section class="section card">
    <h2>${title}</h2>
    ${children}
  </section>`;
}

// Requests the probe endpoints and collects the errors; the backend message is never shown, only the code is used.
async function probeErrors() {
  const out = [];
  for (const code of PROBE_CODES) {
    try {
      await get(`fail/${code}`);
    } catch (err) {
      out.push(err);
    }
  }
  return out;
}

export default function Language() {
  const tt = useT();
  const lang = useLang();
  const [count, setCount] = useState("1");
  const probe = useAsync(probeErrors, []);
  const n = Number.parseInt(count, 10);
  const plural = Number.isFinite(n) && n >= 0 ? n : 0;

  return html`<div>
    <${Section} title=${tt("demo.language.active.title")}>
      <div class="row">
        <span>${tt("demo.language.active.text", { lang: tt(lang === "de" ? "lang.de" : "lang.en") })}</span>
        <${LangSwitch} />
      </div>
    <//>

    <${Section} title=${tt("demo.language.param.title")}>
      <p>${tt("demo.language.param.text", { name: "Alex", count: 3 })}</p>
    <//>

    <${Section} title=${tt("demo.language.plural.title")}>
      <div class="form-row">
        <label for="language-count">${tt("demo.language.plural.label")}</label>
        <input
          id="language-count"
          type="number"
          min="0"
          value=${count}
          onInput=${(ev) => setCount(ev.target.value)}
        />
      </div>
      <p>${tp("demo.language.plural.items", plural)}</p>
    <//>

    <${Section} title=${tt("demo.language.format.title")}>
      <ul>
        <li>${tt("demo.language.format.datetime")}: ${formatDateTime(SAMPLE_TIME, lang)}</li>
        ${OFFSETS_S.map(
          (offset) =>
            html`<li key=${offset}>
              ${tt("demo.language.format.relative")}: ${formatRelative(SAMPLE_TIME + offset * 1000, lang, SAMPLE_TIME)}
            </li>`,
        )}
        <li>${tt("demo.language.format.bytes")}: ${formatBytes(1536, lang)}</li>
        <li>${tt("demo.language.format.number")}: ${formatNumber(1234567.89, lang)}</li>
      </ul>
    <//>

    <${Section} title=${tt("demo.language.errors.title")}>
      <p class="muted">${tt("demo.language.errors.hint")}</p>
      ${probe.loading && html`<${Loading} />`}
      ${!probe.loading && probe.error && html`<${ErrorNote} error=${probe.error} />`}
      ${!probe.loading &&
      (probe.data || []).map((err, index) => html`<${ErrorNote} key=${index} error=${err} />`)}
    <//>
  </div>`;
}
