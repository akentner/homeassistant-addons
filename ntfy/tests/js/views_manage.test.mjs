// View tests of the management group: health, tools, tokens, data (owned by plan 27-04).
import test from "node:test";
import assert from "node:assert/strict";
import {
  doc, STATIC, html, render, fixtures, failures, findAll, findByText, prop, settle, mount, all, calls, TOKEN_VALUE,
} from "./harness.mjs";
import { auditNames, auditTables } from "../../../admin-ui/tests/js/a11y_audit.mjs";

const { RESET_PHRASES } = await import(new URL("lib/model.mjs", STATIC));
const { Toasts } = await import(new URL("vendor/admin-ui/ui.mjs", STATIC));
const { apiHref } = await import(new URL("vendor/admin-ui/ingress.mjs", STATIC));
const { formatDateTime } = await import(new URL("vendor/admin-ui/format.mjs", STATIC));
const { default: STR_EN } = await import(new URL("strings.en.mjs", STATIC));
const { default: STR_DE } = await import(new URL("strings.de.mjs", STATIC));

// ---- helpers ----

const toastRoot = doc.createElement("div");
render(html`<${Toasts} />`, toastRoot);
const toastText = () => toastRoot.textContent;
const clearToasts = async () => {
  for (const node of findAll(toastRoot, (n) => (n.className || "").split(" ").includes("toast"))) node.dispatch("click");
  await settle();
};

const byId = (root, id) => findAll(root, (n) => n.getAttribute("id") === id)[0];
const byLabel = (root, label) => findAll(root, (n) => n.getAttribute("aria-label") === label)[0];
const buttons = (root, text) => findByText(root, "button", text);
const click = async (node) => {
  node.dispatch("click");
  await settle();
};
const type = async (node, value) => {
  node.value = value;
  node.dispatch("input");
  await settle();
};
const choose = async (node, value) => {
  node.value = value;
  node.dispatch("change");
  await settle();
};
const valuesOf = (root) => findAll(root, (n) => n.localName === "input").map((n) => prop(n, "value"));
const alerts = (root) => findAll(root, (n) => n.getAttribute("role") === "alert").map((n) => n.textContent.trim());
const cls = (n) => (n.className || "").split(" ");
const badges = (root) => findAll(root, (n) => cls(n).includes("badge")).map((n) => n.textContent.trim());
const callsTo = (method, url) => calls().filter((c) => c.method === method && c.url.split("?")[0] === url);

async function withFixtures(patch, fn) {
  const saved = {};
  for (const key of Object.keys(patch)) saved[key] = fixtures[key];
  Object.assign(fixtures, patch);
  try {
    return await fn();
  } finally {
    for (const [key, value] of Object.entries(saved)) {
      if (value === undefined) delete fixtures[key];
      else fixtures[key] = value;
    }
    for (const key of Object.keys(failures)) delete failures[key];
  }
}

// A German mount shows no English literal of the namespace and no [key] placeholder.
function assertGerman(root, prefix) {
  const text = all(root);
  assert.ok(!/\[(health|tools|tokens|data|view|btn|dlg|errors)\.[a-z0-9_.]+\]/.test(text), `placeholder in: ${text}`);
  for (const [key, en] of Object.entries(STR_EN)) {
    if (!key.startsWith(prefix) || en.includes("{") || en.length < 6 || en === STR_DE[key]) continue;
    if (STR_DE[key].includes(en)) continue;
    assert.ok(!text.includes(en), `English literal "${en}" (${key}) in German view`);
  }
}

const EFFECTIVE = {
  read: true,
  write: false,
  source: { kind: "user-rule", rule: { user: "<b>alice</b>", topic: "alerts", permission: "ro" } },
  candidates: [
    { user: "everyone", topic: "alerts", permission: "deny" },
    { user: "<b>alice</b>", topic: "alerts", permission: "ro" },
  ],
};
const PUBLISH_OK = { ok: true, status: 200, id: "msg123" };

// ---- health ----

test("health: status badge, version, sizes, plural-aware counts and a labelled Refresh button", async () => {
  const root = await mount("health");
  const text = all(root);
  assert.ok(badges(root).includes("OK"));
  assert.match(text, /Add-on 2\.36\.0-0/);
  assert.match(text, /ntfy is healthy, role server/);
  assert.match(text, /auth\.db schema 10 \(supported\)/);
  assert.match(text, /auth\.db size: 2 KiB/);
  assert.match(text, /Message cache size: 1 MiB/);
  assert.match(text, /3 users, 2 rules, 1 token(?!s)/);
  assert.equal(buttons(root, "Refresh").length, 1);
  assert.equal(auditNames(root).length, 0);
  assert.equal(auditTables(root).length, 0);
});

test("health: db.error is secondary text, unsupported schema and degraded status are shown", async () => {
  const payload = {
    ...fixtures["GET api/health"],
    status: "degraded",
    ntfy: { healthy: false, role: "" },
    db: { schema_version: 99, supported: false, size_bytes: 0, cache_size_bytes: 0, error: "boom <i>x</i>" },
  };
  await withFixtures({ "GET api/health": payload }, async () => {
    const root = await mount("health");
    assert.ok(badges(root).includes("Degraded"));
    assert.match(all(root), /ntfy is not healthy/);
    assert.match(all(root), /schema 99 \(unsupported\)/);
    assert.ok(all(root).includes("boom <i>x</i>"));
    assert.equal(findAll(root, (n) => n.localName === "i").length, 0);
  });
});

test("health: German mount has no English literal and German sizes and counts", async () => {
  const root = await mount("health", {}, { lang: "de" });
  assertGerman(root, "health.");
  assert.match(all(root), /Größe der auth\.db: 2 KiB/);
  assert.match(all(root), /3 Benutzer, 2 Regeln, 1 Token/);
  assert.equal(auditNames(root).length, 0);
});

test("health publish: Publish is disabled without a topic, the datalist offers concrete topics only", async () => {
  const root = await mount("health");
  assert.ok(prop(buttons(root, "Publish")[0], "disabled"));
  const options = findAll(byId(root, "health-topics"), (n) => n.localName === "option").map((n) => prop(n, "value"));
  assert.deepEqual(options, ["alerts"]);
  assert.equal(byId(root, "health-message").value, "Test message from the ntfy add-on");
  await type(byId(root, "health-topic"), "alerts");
  assert.ok(!prop(buttons(root, "Publish")[0], "disabled"));
});

test("health publish: a confirmation naming the topic comes first, then the POST; ok true reports success", async () => {
  await withFixtures({ "POST api/health/publish": PUBLISH_OK }, async () => {
    await clearToasts();
    const root = await mount("health");
    await type(byId(root, "health-topic"), "alerts");
    await click(buttons(root, "Publish")[0]);
    assert.equal(callsTo("POST", "api/health/publish").length, 0);
    assert.ok(all(root).includes("subscribers of the topic alerts"));
    await click(buttons(root, "Publish").pop());
    const sent = callsTo("POST", "api/health/publish");
    assert.equal(sent.length, 1);
    assert.deepEqual(sent[0].body, { topic: "alerts", message: "Test message from the ntfy add-on" });
    assert.match(toastText(), /Test message published/);
    assert.match(all(root), /Status 200, id msg123/);
    assert.ok(!all(root).includes("subscribers of the topic"), "dialog closed");
  });
});

test("health publish: ok false (rate limit 429, unreachable 0) is reported as a failure, not as success", async () => {
  for (const [status, reason] of [[429, /rate limit/], [0, /could not be reached/]]) {
    await withFixtures({ "POST api/health/publish": { ok: false, status, id: null } }, async () => {
      await clearToasts();
      const root = await mount("health");
      await type(byId(root, "health-topic"), "alerts");
      await click(buttons(root, "Publish")[0]);
      await click(buttons(root, "Publish").pop());
      assert.doesNotMatch(toastText(), /Test message published/);
      assert.match(toastText(), reason);
      assert.match(all(root), new RegExp(`Failed: .*\\(status ${status}\\)`));
    });
  }
});

test("health publish: an API error keeps the dialog open with the localized code, never the backend message", async () => {
  await withFixtures({}, async () => {
    failures["POST api/health/publish"] = { status: 500, error: "internal_error", message: "secret backend detail" };
    const root = await mount("health");
    await type(byId(root, "health-topic"), "alerts");
    await click(buttons(root, "Publish")[0]);
    await click(buttons(root, "Publish").pop());
    assert.ok(all(root).includes("subscribers of the topic alerts"), "dialog stays open");
    assert.ok(alerts(root).some((t) => t.includes("The server hit an internal error")));
    assert.ok(!all(root).includes("secret backend detail"));
  });
});

// ---- tools ----

test("tools: a wildcard or empty topic shows an alert and sends nothing", async () => {
  const root = await mount("tools");
  assert.match(all(root), /Effective rights/);
  await click(buttons(root, "Check")[0]);
  assert.deepEqual(alerts(root), ["Enter a concrete topic name (no wildcard)."]);
  await type(byId(root, "tools-topic"), "news-*");
  await click(buttons(root, "Check")[0]);
  assert.equal(alerts(root).length, 1);
  assert.equal(callsTo("GET", "api/effective").length, 0);
});

test("tools: defaults come from params; a valid lookup shows badges, the explanation and the deciding rule", async () => {
  await withFixtures({ "GET api/effective": EFFECTIVE }, async () => {
    const root = await mount("tools", { user: "<b>alice</b>", topic: "alerts" });
    assert.equal(byId(root, "tools-user").value, "<b>alice</b>");
    assert.equal(byId(root, "tools-topic").value, "alerts");
    await click(buttons(root, "Check")[0]);
    const sent = callsTo("GET", "api/effective");
    assert.equal(sent.length, 1);
    assert.ok(sent[0].url.includes("topic=alerts") && sent[0].url.includes("user="));
    assert.deepEqual(badges(root).filter((b) => /allowed|denied|decides/.test(b)), ["allowed", "denied", "decides"]);
    assert.ok(all(root).includes("Decided by the user rule <b>alice</b> on alerts (ro)"));
    assert.ok(all(root).includes("1. everyone alerts deny"));
    assert.ok(all(root).includes("2. <b>alice</b> alerts ro"));
    assert.equal(findAll(root, (n) => n.localName === "b").length, 0);
    assert.equal(auditNames(root).length, 0);
  });
});

test("tools: the four explanations come from the string tables and an API error shows the localized code", async () => {
  const cases = [
    [{ kind: "admin" }, "Admin role: full access"],
    [{ kind: "everyone-rule", rule: { user: "everyone", topic: "news", permission: "ro" } }, "Decided by the everyone rule everyone on news (ro)"],
    [{ kind: "none" }, "No rule matches, default access applies"],
  ];
  for (const [source, expected] of cases) {
    await withFixtures({ "GET api/effective": { ...EFFECTIVE, source, candidates: [] } }, async () => {
      const root = await mount("tools", { topic: "news" });
      await click(buttons(root, "Check")[0]);
      assert.ok(all(root).includes(expected), expected);
    });
  }
  await withFixtures({}, async () => {
    failures["GET api/effective"] = { status: 409, error: "locked", message: "hidden detail" };
    const root = await mount("tools", { topic: "news" });
    await click(buttons(root, "Check")[0]);
    assert.ok(alerts(root).some((t) => t.includes("The ntfy auth database is locked")));
    assert.ok(!all(root).includes("hidden detail"));
  });
});

test("tools generator: topic in a labelled CopyField, one labelled input and select per rule", async () => {
  const root = await mount("tools");
  assert.equal(buttons(root, "Generate").length, 1);
  await click(buttons(root, "Generate")[0]);
  const topicField = byLabel(root, "Generated topic");
  assert.equal(prop(topicField, "value"), "abcdefghijklmnop");
  assert.equal(prop(byLabel(root, "User of rule 1"), "value"), "everyone");
  assert.equal(prop(byLabel(root, "Permission of rule 1"), "value"), "wo");
  assert.equal(auditNames(root).length, 0);
});

test("tools generator: Apply puts known users, reports one line each and skips unknown users", async () => {
  const suggest = { topic: "abcdefghijklmnop", acl: [{ user: "everyone", permission: "wo" }, { user: "ghost", permission: "ro" }] };
  await withFixtures({ "GET api/topics/suggest": suggest, "PUT api/acl": { ok: true } }, async () => {
    const root = await mount("tools");
    await click(buttons(root, "Generate")[0]);
    await click(buttons(root, "Apply")[0]);
    const puts = callsTo("PUT", "api/acl");
    assert.equal(puts.length, 1);
    assert.deepEqual(puts[0].body, { user: "everyone", topic: "abcdefghijklmnop", permission: "wo" });
    assert.ok(all(root).includes("everyone: wo ok"));
    assert.ok(all(root).includes("Skipped unknown users: ghost"));
  });
  await withFixtures({ "GET api/topics/suggest": suggest }, async () => {
    failures["PUT api/acl"] = { status: 409, error: "conflict", message: "hidden detail" };
    const root = await mount("tools");
    await click(buttons(root, "Generate")[0]);
    await click(buttons(root, "Apply")[0]);
    assert.ok(all(root).includes("everyone: The change conflicts with the current state"));
    assert.ok(!all(root).includes("hidden detail"));
  });
});

test("tools: German mount has no English literal, also after a lookup", async () => {
  await withFixtures({ "GET api/effective": EFFECTIVE }, async () => {
    const root = await mount("tools", { topic: "alerts" }, { lang: "de" });
    await click(buttons(root, "Prüfen")[0]);
    await click(buttons(root, "Erzeugen")[0]);
    assertGerman(root, "tools.");
    assert.match(all(root), /Entschieden durch die Benutzerregel/);
    assert.ok(badges(root).includes("erlaubt"));
    assert.equal(auditNames(root).length, 0);
  });
});

// ---- tokens ----

test("tokens: no token value before reveal, once after, gone after hide", async () => {
  const root = await mount("tokens");
  assert.match(all(root), /tk_abcde/);
  assert.match(all(root), /phone/);
  assert.ok(!/tk_[a-z0-9]{29}/.test(all(root)));
  assert.ok(!valuesOf(root).some((v) => /tk_[a-z0-9]{29}/.test(v)));
  await click(buttons(root, "Reveal")[0]);
  assert.equal(valuesOf(root).filter((v) => v === TOKEN_VALUE).length, 1);
  assert.ok(!all(root).includes(TOKEN_VALUE), "the value lives in the input only, not in text");
  assert.ok(byLabel(root, "Value of token tk_abcde"), "labelled CopyField");
  assert.ok(callsTo("POST", "api/tokens/reveal").some((c) => c.body.id === "tk_abcde" && c.body.user === "<b>alice</b>"));
  await click(buttons(root, "Hide")[0]);
  assert.equal(valuesOf(root).filter((v) => v === TOKEN_VALUE).length, 0);
  assert.ok(!all(root).includes(TOKEN_VALUE));
  assert.ok(!/tk_[a-z0-9]{29}/.test(all(root)));
});

test("tokens: a failing reveal toasts the localized error and leaks no value", async () => {
  await withFixtures({}, async () => {
    await clearToasts();
    failures["POST api/tokens/reveal"] = { status: 404, error: "not_found", message: "hidden detail" };
    const root = await mount("tokens");
    await click(buttons(root, "Reveal")[0]);
    assert.match(toastText(), /Not found/);
    assert.ok(!toastText().includes("hidden detail"));
    assert.ok(!valuesOf(root).includes(TOKEN_VALUE));
  });
});

test("tokens: table has caption, th scope and scroll wrapper; hostile text stays text; audits are clean", async () => {
  const root = await mount("tokens");
  assert.equal(findAll(root, (n) => cls(n).includes("table-scroll") && findAll(n, (c) => c.localName === "table").length === 1).length, 1);
  const caption = findAll(root, (n) => n.localName === "caption")[0];
  assert.equal(caption.textContent.trim(), "Access tokens");
  assert.ok(cls(caption).includes("sr-only"));
  const heads = findAll(root, (n) => n.localName === "th");
  assert.equal(heads.length, 7);
  assert.ok(heads.every((th) => th.getAttribute("scope") === "col"));
  assert.ok(all(root).includes("<b>alice</b>"));
  assert.equal(findAll(root, (n) => n.localName === "b").length, 0);
  assert.equal(auditNames(root).length, 0);
  assert.equal(auditTables(root).length, 0);
});

test("tokens: expiry and state badge, relative last use with an approximation note, origin badge", async () => {
  const soon = new Date(Date.now() + 86_400_000 * 5).toISOString();
  const past = new Date(Date.now() - 86_400_000 * 5).toISOString();
  const tokens = [
    { id: "tk_aaaaa", user: "<b>alice</b>", prefix: "tk_aaaaa", label: "a", expires: 0, expires_at: null, last_access: 0, last_origin: "", origin: "gui" },
    { id: "tk_bbbbb", user: "<b>alice</b>", prefix: "tk_bbbbb", label: "<i>b</i>", expires: 1, expires_at: soon, last_access: Math.floor(Date.now() / 1000) - 7200, last_origin: "", origin: "iac" },
    { id: "tk_ccccc", user: "<b>alice</b>", prefix: "tk_ccccc", label: "c", expires: 1, expires_at: past, last_access: 0, last_origin: "", origin: "options" },
  ];
  await withFixtures({ "GET api/tokens": { tokens } }, async () => {
    const root = await mount("tokens");
    const rows = findAll(root, (n) => n.localName === "tr").slice(1);
    assert.equal(rows.length, 3);
    assert.deepEqual(badges(rows[0]).slice(0, 2), ["never", "GUI"]);
    assert.deepEqual(badges(rows[1]).slice(0, 2), ["active", "IaC"]);
    assert.deepEqual(badges(rows[2]).slice(0, 2), ["expired", "Options"]);
    assert.match(rows[2].textContent, /expired /);
    assert.match(rows[1].textContent, /2 hours ago/);
    assert.ok(findAll(rows[1], (n) => n.localName === "td").some((td) => td.getAttribute("title") === "ntfy updates this value lazily, so it is approximate"));
    assert.equal(findAll(root, (n) => n.localName === "i").length, 0);
  });
});

test("tokens: the filter is labelled, starts at params.user and re-queries with the user", async () => {
  const root = await mount("tokens", { user: "<b>alice</b>" });
  const filter = byId(root, "tokens-filter");
  assert.equal(filter.value, "<b>alice</b>");
  assert.ok(callsTo("GET", "api/tokens").some((c) => c.url.includes("user=")));
  await choose(filter, "");
  assert.ok(callsTo("GET", "api/tokens").some((c) => !c.url.includes("user=")));
});

test("tokens: empty state when no tokens exist", async () => {
  await withFixtures({ "GET api/tokens": { tokens: [] } }, async () => {
    assert.match(all(await mount("tokens")), /No tokens\./);
  });
});

test("tokens create: validation shows an alert and sends nothing", async () => {
  const root = await mount("tokens");
  await click(buttons(root, "Create token")[0]);
  assert.equal(findAll(root, (n) => n.getAttribute("role") === "dialog").length, 1);
  await click(buttons(root, "Create")[0]);
  assert.deepEqual(alerts(root), ["Choose a user."]);
  await choose(byId(root, "token-user"), "<b>alice</b>");
  await type(byId(root, "token-label"), "bad\u0001label");
  await click(buttons(root, "Create")[0]);
  assert.deepEqual(alerts(root), ["Label too long or contains control characters."]);
  await type(byId(root, "token-label"), "ok");
  await choose(byId(root, "token-expires"), "custom");
  await type(byId(root, "token-custom"), "soon");
  await click(buttons(root, "Create")[0]);
  assert.deepEqual(alerts(root), ["Duration must look like 30m, 12h or 7d."]);
  assert.equal(callsTo("POST", "api/tokens").length, 0);
  const options = findAll(byId(root, "token-expires"), (n) => n.localName === "option").map((n) => n.textContent.trim());
  assert.deepEqual(options, ["never", "1 hour", "1 day", "7 days", "30 days", "90 days", "Custom…"]);
});

test("tokens create: a valid form posts user and label plus expires only when set; the value is shown once", async () => {
  const created = { token: { value: TOKEN_VALUE, id: "tk_new", user: "<b>alice</b>" } };
  await withFixtures({ "POST api/tokens": created }, async () => {
    await clearToasts();
    const root = await mount("tokens");
    await click(buttons(root, "Create token")[0]);
    await choose(byId(root, "token-user"), "<b>alice</b>");
    await type(byId(root, "token-label"), "laptop");
    await click(buttons(root, "Create")[0]);
    assert.deepEqual(callsTo("POST", "api/tokens")[0].body, { user: "<b>alice</b>", label: "laptop" });
    assert.equal(valuesOf(root).filter((v) => v === TOKEN_VALUE).length, 1);
    assert.ok(byLabel(root, "New token value"));
    assert.ok(!toastText().includes(TOKEN_VALUE));
    await click(buttons(root, "Done")[0]);
    assert.equal(valuesOf(root).filter((v) => v === TOKEN_VALUE).length, 0);
    assert.ok(!/tk_[a-z0-9]{29}/.test(all(root)));
    assert.equal(findAll(root, (n) => n.getAttribute("role") === "dialog").length, 0);

    await click(buttons(root, "Create token")[0]);
    await choose(byId(root, "token-user"), "<b>alice</b>");
    await choose(byId(root, "token-expires"), "7d");
    await click(buttons(root, "Create")[0]);
    assert.deepEqual(callsTo("POST", "api/tokens")[1].body, { user: "<b>alice</b>", label: "", expires: "7d" });
  });
});

test("tokens revoke: danger confirmation names prefix and user, DELETE carries user and id, failure keeps it open", async () => {
  await withFixtures({ "DELETE api/tokens": { ok: true } }, async () => {
    await clearToasts();
    failures["DELETE api/tokens"] = { status: 409, error: "locked", message: "hidden detail" };
    const root = await mount("tokens");
    await click(buttons(root, "Revoke")[0]);
    assert.ok(all(root).includes("Revoke the token tk_abcde… of <b>alice</b>?"));
    assert.ok(cls(buttons(root, "Revoke").pop()).includes("danger"));
    assert.equal(callsTo("DELETE", "api/tokens").length, 0);
    await click(buttons(root, "Revoke").pop());
    assert.ok(alerts(root).some((t) => t.includes("The ntfy auth database is locked")));
    assert.ok(!all(root).includes("hidden detail"));
    assert.ok(all(root).includes("Revoke the token"), "dialog stays open");
    delete failures["DELETE api/tokens"];
    await click(buttons(root, "Revoke").pop());
    const sent = callsTo("DELETE", "api/tokens").pop();
    assert.ok(sent.url.includes("id=tk_abcde") && sent.url.includes("user="));
    assert.match(toastText(), /Token revoked/);
    assert.ok(!all(root).includes("Revoke the token"), "dialog closed");
  });
});

test("tokens: German mount has no English literal, also with the create dialog open", async () => {
  const root = await mount("tokens", {}, { lang: "de" });
  await click(buttons(root, "Token erstellen")[0]);
  assertGerman(root, "tokens.");
  assert.match(all(root), /Zuletzt genutzt \(ca\.\)/);
  assert.equal(auditNames(root).length, 0);
  assert.equal(auditTables(root).length, 0);
});

// ---- data ----

test("data: export link is relative and exactly what apiHref builds; the hashes box shows the notice", async () => {
  const root = await mount("data");
  const link = () => findAll(root, (n) => n.localName === "a" && cls(n).includes("btn") && !cls(n).includes("small"))[0];
  assert.equal(prop(link(), "href"), apiHref("export", { format: "yaml", include_hashes: 0 }));
  assert.ok(!prop(link(), "href").startsWith("/"));
  assert.ok(link().getAttribute("download") !== null);
  assert.match(all(root), /Token values are never exported\./);
  assert.ok(!all(root).includes("Password hashes are secrets"));
  const box = findAll(root, (n) => n.localName === "input" && prop(n, "type") === "checkbox")[0];
  box.checked = true;
  box.dispatch("change");
  await settle();
  assert.equal(prop(link(), "href"), apiHref("export", { format: "yaml", include_hashes: 1 }));
  assert.ok(all(root).includes("Password hashes are secrets. Store the file like a password."));
  await choose(byId(root, "data-format"), "json");
  assert.equal(prop(link(), "href"), apiHref("export", { format: "json", include_hashes: 1 }));
  assert.match(all(root), /Download export/);
});

test("data: backups table with localized date, size, reason and an apiHref download link", async () => {
  const root = await mount("data");
  const row = findAll(root, (n) => n.localName === "tr").find((r) => r.textContent.includes("auth-20261102T100000Z.db"));
  assert.ok(row.textContent.includes(formatDateTime(Date.parse("2026-11-02T10:00:00Z"), "en")));
  assert.ok(row.textContent.includes("4 KiB"));
  assert.ok(row.textContent.includes("manual"));
  const download = findAll(row, (n) => n.localName === "a")[0];
  assert.equal(prop(download, "href"), apiHref("backups/auth-20261102T100000Z.db"));
  assert.ok(!prop(download, "href").startsWith("/"));
  assert.equal(download.getAttribute("aria-label"), "Download backup auth-20261102T100000Z.db");
  const wrapper = findAll(root, (n) => cls(n).includes("table-scroll"));
  assert.ok(wrapper.length >= 1);
  assert.ok(findAll(root, (n) => n.localName === "caption").some((c) => c.textContent.trim() === "Backups of the auth database"));
  assert.equal(auditNames(root).length, 0);
  assert.equal(auditTables(root).length, 0);
});

test("data: reasons map to words, an unknown reason is shown raw, a bad date reads as a dash", async () => {
  const backups = [
    { name: "a.db", size_bytes: 1, created: "not a date", reason: "reset-acls" },
    { name: "b.db", size_bytes: 1, created: "2026-11-02T10:00:00Z", reason: "weird<b>" },
  ];
  await withFixtures({ "GET api/backups": { backups } }, async () => {
    const root = await mount("data");
    const rows = findAll(root, (n) => n.localName === "tr");
    const a = rows.find((r) => r.textContent.includes("a.db"));
    const b = rows.find((r) => r.textContent.includes("b.db"));
    assert.ok(a.textContent.includes("ACLs reset"));
    assert.deepEqual(findAll(a, (n) => n.localName === "td").map((n) => n.textContent.trim()).slice(1, 3), ["-", "1 B"]);
    assert.ok(b.textContent.includes("weird<b>"));
    assert.equal(findAll(root, (n) => n.localName === "b").length, 0);
  });
});

test("data: Create backup now posts an empty body, toasts the name and reloads the list", async () => {
  const backup = { backup: { name: "auth-20261103T090000Z-manual.db", size_bytes: 1, created: "2026-11-03T09:00:00Z", reason: "manual" } };
  await withFixtures({ "POST api/backups": backup }, async () => {
    await clearToasts();
    const root = await mount("data");
    const before = callsTo("GET", "api/backups").length;
    await click(buttons(root, "Create backup now")[0]);
    assert.deepEqual(callsTo("POST", "api/backups")[0].body, {});
    assert.match(toastText(), /Backup auth-20261103T090000Z-manual\.db created/);
    assert.equal(callsTo("GET", "api/backups").length, before + 1);
  });
});

test("data: empty backups list shows the empty text", async () => {
  await withFixtures({ "GET api/backups": { backups: [] } }, async () => {
    assert.match(all(await mount("data")), /No backups yet\./);
  });
});

test("data: reset needs the exact phrase (wrong and differently-cased stay disabled), then posts it", async () => {
  const root = await mount("data");
  assert.equal(findAll(root, (n) => n.localName === "button" && /^(Reset|Clear)/.test(n.textContent.trim())).length, 3);
  await click(buttons(root, "Reset ACLs")[0]);
  const phrase = () => findAll(root, (n) => n.localName === "input" && /-phrase$/.test(n.getAttribute("id") || ""))[0];
  const confirm = () => buttons(root, "Execute")[0];
  assert.ok(root.textContent.includes('Type "reset acls" to confirm'));
  assert.ok(prop(confirm(), "disabled"));
  await type(phrase(), "reset acl");
  assert.ok(prop(confirm(), "disabled"));
  await type(phrase(), "Reset ACLs");
  assert.ok(prop(confirm(), "disabled"));
  await type(phrase(), RESET_PHRASES.acls);
  assert.ok(!prop(confirm(), "disabled"));
  await click(confirm());
  const sent = callsTo("POST", "api/reset/acls");
  assert.equal(sent.length, 1);
  assert.deepEqual(sent[0].body, { confirm: "reset acls" });
});

test("data: cache and everything use their own phrases; the toast names deleted messages and attachments", async () => {
  await withFixtures(
    {
      "POST api/reset/cache": { done: true, messages_deleted: 1, attachments_deleted: 12 },
      "POST api/reset/everything": { done: true },
    },
    async () => {
      await clearToasts();
      const root = await mount("data");
      const phrase = () => findAll(root, (n) => n.localName === "input" && /-phrase$/.test(n.getAttribute("id") || ""))[0];
      await click(buttons(root, "Clear message cache")[0]);
      await type(phrase(), RESET_PHRASES.cache);
      await click(buttons(root, "Execute")[0]);
      assert.deepEqual(callsTo("POST", "api/reset/cache")[0].body, { confirm: "clear cache" });
      assert.match(toastText(), /Clear message cache done: 1 message, 12 attachments/);
      await click(buttons(root, "Reset everything incl. users")[0]);
      await type(phrase(), RESET_PHRASES.everything);
      await click(buttons(root, "Execute")[0]);
      assert.deepEqual(callsTo("POST", "api/reset/everything")[0].body, { confirm: "reset everything" });
      assert.match(toastText(), /Reset everything incl\. users done(?!:)/);
    },
  );
});

test("data: a failing reset keeps the dialog open with the localized error", async () => {
  await withFixtures({}, async () => {
    failures["POST api/reset/acls"] = { status: 409, error: "locked", message: "hidden detail" };
    const root = await mount("data");
    await click(buttons(root, "Reset ACLs")[0]);
    const input = findAll(root, (n) => n.localName === "input" && /-phrase$/.test(n.getAttribute("id") || ""))[0];
    await type(input, RESET_PHRASES.acls);
    await click(buttons(root, "Execute")[0]);
    assert.equal(buttons(root, "Execute").length, 1, "dialog stays open");
    assert.ok(alerts(root).some((t) => t.includes("The ntfy auth database is locked")));
    assert.ok(!all(root).includes("hidden detail"));
  });
});

test("data: German mount has no English literal, also with a reset dialog open", async () => {
  const root = await mount("data", {}, { lang: "de" });
  assertGerman(root, "data.");
  assert.ok(findAll(root, (n) => n.localName === "caption").some((c) => c.textContent.includes("Backups der Auth-Datenbank")));
  assert.ok(all(root).includes(formatDateTime(Date.parse("2026-11-02T10:00:00Z"), "de")));
  assert.match(all(root), /manuell/);
  await click(buttons(root, "ACLs zurücksetzen")[0]);
  assertGerman(root, "data.");
  assert.equal(auditNames(root).length, 0);
  assert.equal(auditTables(root).length, 0);
});

// Preact/toast timers can outlive the tests; end the worker once the results are reported.
test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});
