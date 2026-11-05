import test from "node:test";
import assert from "node:assert/strict";
import { install, findAll, settle } from "./fakedom.mjs";
import { auditNames, auditTables } from "./a11y_audit.mjs";

const doc = install();
const STATIC = new URL("../../app/web/static/", import.meta.url);
const { html, render } = await import(new URL("vendor/admin-ui/ui.mjs", STATIC));
const { registerStrings, setLang } = await import(new URL("vendor/admin-ui/i18n.mjs", STATIC));
const { formatNumber, formatDateTime, formatRelative } = await import(new URL("vendor/admin-ui/format.mjs", STATIC));
const { ROWS } = await import(new URL("model.mjs", STATIC));
const { HostCard } = await import(new URL("views/host-card.mjs", STATIC));
const { default: de } = await import(new URL("strings.de.mjs", STATIC));
const { default: en } = await import(new URL("strings.en.mjs", STATIC));
registerStrings({ de, en });
setLang("en");

const NOW = Date.UTC(2026, 10, 2, 12, 0, 0);
const XSS = "<img src=x onerror=alert(1)><script>boom()</script><b>x</b>";

const status = (over = {}) => ({
  age: 3, up: 400000, load1: 1.5, io_some10: 2, io_full10: 0, mem_full10: 0, sda_inflight: 0, mmc_inflight: 1, dstate: 0,
  probe_age: 2, ping: 1, p22222: 1, p1883: 1, p8123: 1, p4357: 1, problem: 0, r_age: 0, r_io: 0, r_sda: 0, r_dstate: 0,
  r_kmsg: 0, reasons: "none", dstate_tasks: "", kmsg_errors: 0, kmsg_last: "", key_fp: "SHA256:abcDEF123", key_type: "ED25519", syncing: false,
  ...over,
});
const host = (over = {}) => ({ slug: "ha_backup", name: "ha-backup", host: "192.0.2.9", status: status(), error: null, incidents: [], ...over });

const mount = async (h, nowMs = NOW) => {
  const root = doc.createElement("div");
  render(html`<${HostCard} host=${h} nowMs=${nowMs} />`, root);
  await settle();
  return root;
};
const cls = (root, name) => findAll(root, (n) => (n.className || "").split(" ").includes(name));
const tag = (root, name) => findAll(root, (n) => n.localName === name);
const rows = (root) => tag(root, "tr");
const rowOf = (root, label) => rows(root).find((r) => tag(r, "th")[0].textContent.trim() === label);

test("header: name, address, OK verdict and no reasons for a healthy host", async () => {
  const root = await mount(host());
  assert.equal(tag(root, "h2")[0].textContent, "ha-backup");
  assert.ok(cls(root, "muted").some((n) => n.textContent === "192.0.2.9"));
  const badge = cls(root, "badge")[0];
  assert.equal(badge.textContent, "OK");
  assert.ok(badge.className.includes("ok"));
  assert.equal(cls(root, "reasons").length, 0);
  assert.equal(tag(root, "section")[0].getAttribute("aria-label"), "ha-backup");
});

test("header: PROBLEM verdict with translated and raw reasons", async () => {
  const root = await mount(host({ status: status({ problem: 1, reasons: "stale,io_full10,weird_token" }) }));
  const badge = cls(root, "badge")[0];
  assert.equal(badge.textContent, "PROBLEM");
  assert.ok(badge.className.includes("error"));
  assert.equal(cls(root, "reasons")[0].textContent, "Stale samples, I/O stall, weird_token");
});

test("values table: caption, ten rows with row headers in ROWS order, localized numbers", async () => {
  const root = await mount(host());
  assert.equal(tag(root, "caption")[0].textContent.trim(), "Measured values of ha-backup");
  assert.equal(rows(root).length, 10);
  assert.ok(tag(root, "th").every((th) => th.getAttribute("scope") === "row"));
  assert.deepEqual(
    rows(root).map((r) => tag(r, "th")[0].textContent.trim()),
    [
      "Sample age (s)", "Host booted", "Load (1 min)", "I/O some (10 s avg %)", "I/O full (10 s avg %)",
      "Memory full (10 s avg %)", "sda in-flight requests", "mmc in-flight requests", "Tasks in D-state", "Kernel errors (10 min)",
    ],
  );
  assert.equal(tag(rowOf(root, "Load (1 min)"), "td")[0].textContent, formatNumber(1.5, "en"));
  assert.equal(tag(rowOf(root, "Load (1 min)"), "td")[0].textContent, "1.5");
  assert.equal(tag(rowOf(root, "mmc in-flight requests"), "td")[0].textContent, "1");
});

test("values table: unknown values show the localized dash", async () => {
  const root = await mount(host({ status: status({ load1: -1, io_some10: -1, up: -1, mmc_inflight: -1 }) }));
  for (const label of ["Load (1 min)", "I/O some (10 s avg %)", "Host booted", "mmc in-flight requests"]) {
    assert.equal(tag(rowOf(root, label), "td")[0].textContent, "–", label);
  }
});

test("values table: boot time and relative uptime come from the server clock", async () => {
  const root = await mount(host());
  const boot = NOW - (400000 + 3) * 1000;
  const expected = `${formatDateTime(boot, "en")} (${formatRelative(boot, "en", NOW)})`;
  assert.equal(tag(rowOf(root, "Host booted"), "td")[0].textContent, expected);
  assert.match(expected, /5 days ago/);
});

const FLAGS = [
  ["r_age", "Sample age (s)"], ["r_io", "I/O full (10 s avg %)"], ["r_sda", "sda in-flight requests"],
  ["r_dstate", "Tasks in D-state"], ["r_kmsg", "Kernel errors (10 min)"],
];
for (const [flag, label] of FLAGS) {
  test(`violation: ${flag} highlights exactly its row, not by colour alone`, async () => {
    const root = await mount(host({ status: status({ [flag]: 1 }) }));
    const bad = rows(root).filter((r) => r.className.split(" ").includes("bad"));
    assert.equal(bad.length, 1);
    assert.equal(tag(bad[0], "th")[0].textContent.trim().startsWith(label), true);
    assert.equal(cls(bad[0], "sr-only")[0].textContent, "Threshold exceeded");
    assert.equal(findAll(root, (n) => n.className === "sr-only" && n.textContent === "Threshold exceeded").length, 1);
  });
}

test("no violation: no highlighted row and no screen reader hint", async () => {
  const root = await mount(host({ status: status({ r_age: 0, r_io: -1 }) }));
  assert.equal(rows(root).filter((r) => r.className.includes("bad")).length, 0);
  assert.equal(root.textContent.includes("Threshold exceeded"), false);
  assert.equal(ROWS.filter((r) => r.flag).length, 5);
});

test("port chips: five items with label, glyph and state text; -1 is unknown", async () => {
  const root = await mount(host({ status: status({ ping: 0, p1883: -1 }) }));
  const [list] = tag(root, "ul");
  assert.equal(list.getAttribute("aria-label"), "Reachability");
  const chips = tag(list, "li");
  assert.equal(chips.length, 5);
  assert.deepEqual(chips.map((c) => c.className), ["chip down", "chip up", "chip unknown", "chip up", "chip up"]);
  assert.ok(chips[0].textContent.includes("Ping") && chips[1].textContent.includes("SSH 22222"));
  assert.ok(chips[2].textContent.includes("MQTT 1883"));
  assert.equal(cls(chips[0], "sr-only")[0].textContent, "unreachable");
  assert.equal(cls(chips[1], "sr-only")[0].textContent, "reachable");
  assert.equal(cls(chips[2], "sr-only")[0].textContent, "unknown");
  for (const chip of chips) {
    const glyph = findAll(chip, (n) => n.getAttribute("aria-hidden") === "true");
    assert.equal(glyph.length, 1);
    assert.ok(["✓", "✗", "–"].includes(glyph[0].textContent));
  }
});

test("SSH key line: valid, no type, invalid and unknown", async () => {
  const line = (root) => cls(root, "key-line")[0];
  let root = await mount(host());
  assert.ok(line(root).textContent.includes("SSH key"));
  assert.ok(findAll(line(root), (n) => n.className.includes("mono"))[0].textContent === "ED25519 SHA256:abcDEF123");
  assert.equal(line(root).className, "key-line");

  root = await mount(host({ status: status({ key_type: "" }) }));
  assert.equal(findAll(line(root), (n) => n.className.includes("mono"))[0].textContent, "SHA256:abcDEF123");

  root = await mount(host({ status: status({ key_fp: "invalid", key_type: "" }) }));
  assert.equal(line(root).className, "key-line bad");
  assert.equal(findAll(line(root), (n) => n.className.includes("mono"))[0].textContent, "invalid");

  root = await mount(host({ status: status({ key_fp: "", key_type: "" }) }));
  assert.equal(line(root).className, "key-line");
  assert.equal(findAll(line(root), (n) => n.className.includes("mono"))[0].textContent, "–");
});

test("blocked tasks, kernel error and incidents blocks", async () => {
  let root = await mount(host());
  assert.deepEqual(tag(root, "h3").map((h) => h.textContent), ["Recent incidents"]);
  assert.equal(tag(root, "pre")[0].textContent, "none logged");

  root = await mount(
    host({
      status: status({ dstate_tasks: "12 jbd2:wait", kmsg_last: "EXT4-fs error" }),
      incidents: ["2026-11-02T10:00:00Z INCIDENT start a", "2026-11-02T10:01:00Z INCIDENT end b"],
    }),
  );
  assert.deepEqual(tag(root, "h3").map((h) => h.textContent), ["Blocked tasks", "Last kernel error", "Recent incidents"]);
  const pres = tag(root, "pre");
  assert.deepEqual(pres.map((p) => p.textContent), [
    "12 jbd2:wait", "EXT4-fs error", "2026-11-02T10:00:00Z INCIDENT start a\n2026-11-02T10:01:00Z INCIDENT end b",
  ]);
});

test("status_failed: alert note, no values, no chips, incidents still shown", async () => {
  const root = await mount(host({ status: null, error: "status_failed", incidents: ["x INCIDENT start y"] }));
  const alert = findAll(root, (n) => n.getAttribute("role") === "alert");
  assert.equal(alert.length, 1);
  assert.ok(alert[0].textContent.includes("The status of this host could not be determined"));
  assert.equal(tag(root, "table").length, 0);
  assert.equal(tag(root, "ul").length, 0);
  assert.equal(cls(root, "key-line").length, 0);
  assert.equal(cls(root, "badge")[0].textContent, "Unknown");
  assert.ok(cls(root, "badge")[0].className.includes("muted"));
  assert.equal(tag(root, "pre")[0].textContent, "x INCIDENT start y");
});

test("hostile text stays text everywhere", async () => {
  const root = await mount(
    host({
      name: XSS,
      host: XSS,
      status: status({ problem: 1, reasons: XSS, dstate_tasks: XSS, kmsg_last: XSS, key_fp: XSS, key_type: XSS }),
      incidents: [XSS, XSS],
    }),
  );
  for (const name of ["b", "script", "img"]) assert.equal(tag(root, name).length, 0, name);
  assert.ok(root.textContent.includes(XSS));
  assert.ok(tag(root, "pre").every((p) => p.textContent.includes(XSS)));
});

test("german: headings, row labels and chip states differ from english, switching back restores english", async () => {
  setLang("de");
  let root = await mount(host({ incidents: [] }));
  assert.ok(rowOf(root, "Alter der Messung (s)"));
  assert.deepEqual(tag(root, "h3").map((h) => h.textContent), ["Letzte Vorfälle"]);
  assert.equal(cls(cls(root, "chip")[0], "sr-only")[0].textContent, "erreichbar");
  assert.equal(tag(rowOf(root, "Last (1 Min.)"), "td")[0].textContent, formatNumber(1.5, "de"));
  assert.equal(tag(rowOf(root, "Last (1 Min.)"), "td")[0].textContent, "1,5");
  assert.equal(tag(root, "pre")[0].textContent, "keine protokolliert");
  assert.match(tag(rowOf(root, "Host gestartet"), "td")[0].textContent, /vor 5 Tagen/);
  setLang("en");
  root = await mount(host());
  assert.ok(rowOf(root, "Sample age (s)"));
});

test("a11y: names and table headers are clean", async () => {
  const root = await mount(host({ status: status({ problem: 1, reasons: "stale", r_age: 1 }), incidents: ["a INCIDENT b"] }));
  assert.deepEqual(auditNames(root), []);
  assert.deepEqual(auditTables(root), []);
});

test.after(() => {
  setTimeout(() => process.exit(process.exitCode ?? 0), 300).unref();
});

test("header: syncing shows an info badge instead of the red verdict, in both languages", async () => {
  const root = await mount(host({ status: status({ syncing: true, age: 200 }) }));
  const badge = cls(root, "badge")[0];
  assert.equal(badge.textContent, "Updating…");
  assert.ok(badge.className.includes("info"));
  assert.equal(cls(root, "reasons").length, 0);
  setLang("de");
  const de = await mount(host({ status: status({ syncing: true }) }));
  assert.equal(cls(de, "badge")[0].textContent, "Aktualisiere…");
  setLang("en");
});

test("header: a real problem beats syncing", async () => {
  const root = await mount(host({ status: status({ syncing: true, problem: 1, reasons: "io_full10" }) }));
  assert.equal(cls(root, "badge")[0].textContent, "PROBLEM");
});
