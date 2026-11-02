// Rules checklist: the rules of DOCS.md as an interactive checklist. tests/test_rules_view.py keeps ids, statuses and
// enforcing paths identical to the DOCS table and the repository.
import { html, useState, Badge } from "../lib/ui.mjs";
import { useT } from "../lib/i18n.mjs";

export const meta = { id: "rules", titleKey: "demo.nav.rules" };

export const RULES_STORAGE_KEY = "admin-ui:demo-rules";

export const RULES = [
  { id: "R-01", status: "enforced", enforcedBy: ["admin-ui/tests/test_skeleton_server.py", "internal/verify-admin-ui-scaffold.sh"] },
  { id: "R-02", status: "enforced", enforcedBy: ["internal/check-admin-ui-rules.py", "admin-ui/tests/js/api.test.mjs"] },
  { id: "R-03", status: "enforced", enforcedBy: ["internal/check-admin-ui-rules.py", "admin-ui/tests/js/ui.test.mjs"] },
  { id: "R-04", status: "enforced", enforcedBy: ["admin-ui/tests/js/ui.test.mjs", "admin-ui/tests/test_demo_api.py"] },
  { id: "R-05", status: "enforced", enforcedBy: ["internal/check-admin-ui-rules.py", "admin-ui/tests/test_static_rules.py"] },
  { id: "R-06", status: "enforced", enforcedBy: ["admin-ui/tests/js/i18n.test.mjs"] },
  { id: "R-07", status: "review", enforcedBy: ["admin-ui/tests/js/format.test.mjs"] },
  { id: "R-08", status: "enforced", enforcedBy: ["admin-ui/tests/test_css.py"] },
  { id: "R-09", status: "enforced", enforcedBy: ["admin-ui/tests/js/a11y.test.mjs", "admin-ui/tests/js/ui.test.mjs", "admin-ui/tests/test_css.py"] },
  { id: "R-10", status: "enforced", enforcedBy: ["internal/check-admin-ui-rules.py", "admin-ui/tests/js/i18n.test.mjs"] },
  { id: "R-11", status: "unverified", enforcedBy: ["internal/check-admin-ui-rules.py"] },
  { id: "R-12", status: "review", enforcedBy: [".github/workflows/lint.yml"] },
  { id: "R-13", status: "unverified", enforcedBy: ["admin-ui/tests/js/theme_sync.test.mjs", "admin-ui/tests/js/ha_bridge.test.mjs"] },
  { id: "R-14", status: "enforced", enforcedBy: ["admin-ui/tests/js/i18n.test.mjs", "admin-ui/tests/test_demo_api.py"] },
  { id: "R-15", status: "enforced", enforcedBy: ["Makefile", "admin-ui/tests/test_sync.py"] },
];

// Literal keys per rule (R-06: keys are never built dynamically).
const TEXT = {
  "R-01": { title: "demo.rules.r01.title", how: "demo.rules.r01.how" },
  "R-02": { title: "demo.rules.r02.title", how: "demo.rules.r02.how" },
  "R-03": { title: "demo.rules.r03.title", how: "demo.rules.r03.how" },
  "R-04": { title: "demo.rules.r04.title", how: "demo.rules.r04.how" },
  "R-05": { title: "demo.rules.r05.title", how: "demo.rules.r05.how" },
  "R-06": { title: "demo.rules.r06.title", how: "demo.rules.r06.how" },
  "R-07": { title: "demo.rules.r07.title", how: "demo.rules.r07.how" },
  "R-08": { title: "demo.rules.r08.title", how: "demo.rules.r08.how" },
  "R-09": { title: "demo.rules.r09.title", how: "demo.rules.r09.how" },
  "R-10": { title: "demo.rules.r10.title", how: "demo.rules.r10.how" },
  "R-11": { title: "demo.rules.r11.title", how: "demo.rules.r11.how" },
  "R-12": { title: "demo.rules.r12.title", how: "demo.rules.r12.how" },
  "R-13": { title: "demo.rules.r13.title", how: "demo.rules.r13.how" },
  "R-14": { title: "demo.rules.r14.title", how: "demo.rules.r14.how" },
  "R-15": { title: "demo.rules.r15.title", how: "demo.rules.r15.how" },
};
const STATUS_TEXT = {
  enforced: "demo.rules.status.enforced",
  review: "demo.rules.status.review",
  unverified: "demo.rules.status.unverified",
};
const STATUS_KIND = { enforced: "ok", review: "warn", unverified: "muted" };
const known = new Set(RULES.map((r) => r.id));

// Every storage access is guarded: blocked storage, malformed JSON or foreign ids never throw and never leak in.
function load() {
  try {
    if (typeof localStorage === "undefined") return [];
    const parsed = JSON.parse(localStorage.getItem(RULES_STORAGE_KEY));
    return Array.isArray(parsed) ? parsed.filter((id) => typeof id === "string" && known.has(id)) : [];
  } catch {
    return [];
  }
}

function save(ids) {
  try {
    if (typeof localStorage !== "undefined") localStorage.setItem(RULES_STORAGE_KEY, JSON.stringify(ids));
  } catch {
    // progress is a convenience only
  }
}

export default function Rules() {
  const tt = useT();
  const [checked, setChecked] = useState(load);
  const update = (next) => {
    setChecked(next);
    save(next);
  };
  const toggle = (id) => update(checked.includes(id) ? checked.filter((x) => x !== id) : [...checked, id]);

  return html`<section class="section card">
    <h2>${tt("demo.rules.title")}</h2>
    <p class="muted">${tt("demo.rules.intro")}</p>
    <div class="row">
      <span role="status">${tt("demo.rules.summary", { done: checked.length, total: RULES.length })}</span>
      <button class="btn small secondary" type="button" onClick=${() => update([])}>${tt("demo.rules.reset")}</button>
    </div>
    <ul class="rules-list">
      ${RULES.map((rule) => {
        const inputId = `rule-${rule.id}`;
        return html`<li key=${rule.id} class="rule">
          <input
            id=${inputId}
            type="checkbox"
            checked=${checked.includes(rule.id)}
            onChange=${() => toggle(rule.id)}
          />
          <div>
            <label for=${inputId}>
              <strong>${rule.id}</strong> ${tt(TEXT[rule.id].title)}
            </label>
            <${Badge} kind=${STATUS_KIND[rule.status]}>${tt(STATUS_TEXT[rule.status])}<//>
            <p class="muted">${tt(TEXT[rule.id].how)}</p>
            <p class="muted">${rule.enforcedBy.map((p) => html`<code key=${p}>${p}</code> `)}</p>
          </div>
        </li>`;
      })}
    </ul>
  </section>`;
}
