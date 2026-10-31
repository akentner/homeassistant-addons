import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { doc, all, tags, text } from './fakedom.mjs';

const require = createRequire(import.meta.url);
const ui = require('../../../app/web/static/app.js');
const example = JSON.parse(readFileSync(new URL('../../../docs/state.example.json', import.meta.url)));
const NOW = new Date('2026-10-27T16:01:30Z');
const clone = (o) => JSON.parse(JSON.stringify(o));
const XSS = '<img src=x onerror=alert(1)><script>boom()</script>';

const ALLOWED = new Set(['div', 'span', 'section', 'h2', 'h3', 'p', 'button', 'table', 'tr', 'th', 'td', 'code',
  'details', 'summary', '#text']);

function assertNoMarkup(nodes) {
  for (const t of tags(nodes)) assert.ok(ALLOWED.has(t), `unexpected element <${t}>`);
}

test('relTime', () => {
  assert.equal(ui.relTime('2026-10-27T16:00:30Z', NOW), '1 min ago');
  assert.equal(ui.relTime('2026-10-27T16:01:20Z', NOW), '10 s ago');
  assert.equal(ui.relTime('2026-10-27T10:01:30Z', NOW), '6 h ago');
  assert.equal(ui.relTime('2026-10-25T16:01:30Z', NOW), '2 d ago');
  assert.equal(ui.relTime('2026-10-27T19:00:00Z', NOW), 'just now');
  for (const bad of [null, undefined, 5, 'junk', {}]) assert.equal(ui.relTime(bad, NOW), '-');
});

test('statusInfo', () => {
  assert.deepEqual(ui.statusInfo(example), { label: 'ok', cls: 'ok' });
  assert.deepEqual(ui.statusInfo({ status: 'ok', stale: true }), { label: 'stale', cls: 'stale' });
  assert.deepEqual(ui.statusInfo({ status: 'ok', age_seconds: 601, interval: 300 }), { label: 'stale', cls: 'stale' });
  assert.deepEqual(ui.statusInfo({}), { label: 'starting', cls: 'starting' });
  assert.equal(ui.statusInfo({ status: '<b>x' }).cls, 'starting');
  assert.equal(ui.statusInfo({ status: 'error' }).cls, 'error');
});

test('filterKeys is case-insensitive substring', () => {
  const names = ['MQTT_password', 'mqtt_username', 'db_dsn'];
  assert.deepEqual(ui.filterKeys(names, 'MQTT'), ['MQTT_password', 'mqtt_username']);
  assert.deepEqual(ui.filterKeys(names, ' dsn '), ['db_dsn']);
  assert.deepEqual(ui.filterKeys(names, ''), names);
  assert.deepEqual(ui.filterKeys(names, 'zzz'), []);
  assert.deepEqual(ui.filterKeys('nope', 'a'), []);
  assert.deepEqual(ui.filterKeys(null, null), []);
});

test('pickTab from hash, stored value and fallback', () => {
  assert.equal(ui.pickTab('#usage', 'events'), 'usage');
  assert.equal(ui.pickTab('', 'events'), 'events');
  assert.equal(ui.pickTab('#bogus', 'synthetic'), 'synthetic');
  assert.equal(ui.pickTab('#bogus', 'bogus'), 'keys');
  assert.equal(ui.pickTab(undefined, null), 'keys');
});

test('badges from example and from empty state', () => {
  const t = text(ui.buildBadges(doc, example, NOW));
  assert.match(t, /ok/); assert.match(t, /42 items/); assert.match(t, /v0\.1\.0/);
  assert.doesNotThrow(() => ui.buildBadges(doc, {}, NOW));
  assert.match(text(ui.buildBadges(doc, {}, NOW)), /starting/);
});

test('missing blocks never throw', () => {
  for (const state of [{}, { keys: 3, providers: [], events: 'x', usage: 'u', synthetic: {}, check: 7, guard: 'g' }]) {
    assert.doesNotThrow(() => {
      ui.buildGeneral(doc, state, NOW); ui.buildProviders(doc, state); ui.buildKeysPanel(doc, state, '');
      ui.buildSyntheticPanel(doc, state); ui.buildUsagePanel(doc, state, ''); ui.buildEvents(doc, state);
      ui.buildGuardCard(doc, state, () => {}); ui.buildPreview(doc, null, () => {});
    });
  }
});

test('XSS strings end up as text, never as elements', () => {
  const s = clone(example);
  s.keys.names = [XSS, 'ok_key'];
  s.keys.added = [XSS];
  s.keys.synthetic = [XSS];
  s.events = [{ at: XSS, level: XSS, code: XSS, message: XSS }];
  s.providers.bitwarden.problems = [{ severity: XSS, code: XSS, message: XSS }];
  s.providers.bitwarden.revision = XSS;
  s.synthetic = [{ name: XSS, template: XSS, refs: [XSS], status: 'error', error_code: XSS }];
  s.usage = { enabled: true, roots: [XSS], scanned_at: XSS, files_scanned: 1, missing: { [XSS]: { count: 1, refs: [{ file: XSS, line: 1 }] } },
    used: { [XSS]: { count: 1, refs: [{ file: XSS, line: 2 }] } }, unused: [XSS] };
  s.check = { enabled: true, interval: XSS, last_check_at: XSS, result: XSS, error_code: XSS };
  s.error_code = 'shrink_guard';
  s.guard = { new_items: XSS, last_items: XSS, removed: [XSS], added: [XSS], changed: [XSS] };
  const built = [
    ui.buildBadges(doc, s, NOW), ui.buildGeneral(doc, s, NOW), [ui.buildGuardCard(doc, s, () => {})],
    [ui.buildProviders(doc, s)], ui.buildKeysPanel(doc, s, ''), ui.buildSyntheticPanel(doc, s),
    ui.buildUsagePanel(doc, s, ''), [ui.buildEvents(doc, s)], ui.buildPreview(doc, { added: [XSS], errors: [XSS, { code: XSS }] }, () => {}),
  ].flat();
  assertNoMarkup(built);
  assert.ok(text(built).includes(XSS));
});

test('keys panel: sections, synthetic badge, search, cap', () => {
  const s = clone(example);
  s.keys.names = ['db_dsn', 'mqtt_password', 'mqtt_username'];
  s.keys.added = ['db_dsn'];
  s.keys.synthetic = ['db_dsn'];
  const t = text(ui.buildKeysPanel(doc, s, ''));
  assert.match(t, /Added \(1\)/); assert.match(t, /Changed \(1\)/); assert.doesNotMatch(t, /Removed/);
  assert.match(t, /All keys \(3\)/);
  const nodes = ui.buildKeysPanel(doc, s, '');
  const tagCount = nodes.flatMap((n) => n.find((x) => x.className === 'tag')).length;
  assert.equal(tagCount, 2); // db_dsn in Added and in All keys
  const filtered = text(ui.buildKeysPanel(doc, s, 'MQTT'));
  assert.match(filtered, /All keys \(2\)/); assert.doesNotMatch(filtered, /db_dsn/);
  s.keys.names = Array.from({ length: 600 }, (_, i) => `k${i}`);
  s.keys.added = []; s.keys.changed = [];
  const big = ui.buildKeysPanel(doc, s, '');
  assert.match(text(big), /\+100 more/);
  assert.equal(big.flatMap((n) => n.find((x) => x.className === 'key')).length, 500);
});

test('guard card only for shrink_guard with an object', () => {
  const guard = { new_items: 1, last_items: 9, removed: ['a', 'b'], added: ['c'], changed: [] };
  assert.equal(ui.buildGuardCard(doc, { ...example, guard }, () => {}), null);
  assert.equal(ui.buildGuardCard(doc, { ...example, error_code: 'shrink_guard', guard: null }, () => {}), null);
  assert.equal(ui.buildGuardCard(doc, { ...example, error_code: 'shrink_guard', guard: [1] }, () => {}), null);
  let applied = null;
  const card = ui.buildGuardCard(doc, { ...example, error_code: 'shrink_guard', guard }, (n) => { applied = n; });
  const t = text([card]);
  assert.match(t, /Would be removed \(2\)/); assert.match(t, /Would be added \(1\)/); assert.match(t, /Apply anyway/);
  const btn = card.find((n) => n.tag === 'button')[0];
  btn.click();
  assert.equal(applied, 2);
});

test('synthetic panel: empty state and statuses', () => {
  assert.match(text(ui.buildSyntheticPanel(doc, {})), /No synthetic keys configured/);
  const t = text(ui.buildSyntheticPanel(doc, { synthetic: [
    { name: 'a', template: '{{ x }}', refs: ['x'], status: 'ok', error_code: null },
    { name: 'b', template: 't', refs: [], status: 'pending', error_code: null },
    { name: 'c', template: 't', refs: [], status: 'error', error_code: 'synthetic_render_failed' },
  ] }));
  assert.match(t, /parsed \(not rendered yet\)/); assert.match(t, /error synthetic_render_failed/);
});

test('usage panel: disabled, search, missing first', () => {
  assert.match(text(ui.buildUsagePanel(doc, { usage: { enabled: false } }, '')), /scan is off/i);
  const usage = { enabled: true, roots: ['config'], scanned_at: 'now', files_scanned: 3, truncated: true,
    missing: { gone: { count: 1, refs: [{ file: 'a.yaml', line: 4 }] } },
    used: { mqtt_password: { count: 2, refs: [{ file: 'b.yaml', line: 1 }] }, db_dsn: { count: 1, refs: [] } },
    unused: ['old_key'] };
  const t = text(ui.buildUsagePanel(doc, { usage }, ''));
  assert.match(t, /scan stopped at a limit/); assert.match(t, /missing in secrets\.yaml \(1\)/);
  assert.match(t, /a\.yaml:4/); assert.match(t, /Unused \(1\)/); assert.match(t, /Used \(2\)/);
  const f = text(ui.buildUsagePanel(doc, { usage }, 'MQTT'));
  assert.match(f, /mqtt_password/); assert.doesNotMatch(f, /db_dsn/); assert.doesNotMatch(f, /gone/);
});

test('events capped at 100 and general includes check block only when present', () => {
  const events = Array.from({ length: 150 }, (_, i) => ({ at: 't', level: 'info', code: 'c', message: `m${i}` }));
  const rows = ui.buildEvents(doc, { events }).find((n) => n.tag === 'tr');
  assert.equal(rows.length, 101); // header + 100
  assert.match(text(ui.buildGeneral(doc, example, NOW)), /Change check/);
  const old = clone(example); delete old.check;
  assert.doesNotMatch(text(ui.buildGeneral(doc, old, NOW)), /Change check/);
  const dis = clone(example); dis.check = { enabled: false, interval: 0, last_check_at: null, result: null };
  assert.match(text(ui.buildGeneral(doc, dis, NOW)), /disabled/);
  const err = clone(example); err.check.result = 'error'; err.check.error_code = 'git_auth_failed';
  const nodes = ui.buildGeneral(doc, err, NOW);
  assert.ok(nodes.flatMap((n) => n.find((x) => x.className === 'error')).length >= 1);
  assert.match(text(nodes), /git_auth_failed/);
});

test('providers table shows revision', () => {
  assert.match(text([ui.buildProviders(doc, example)]), /1761560000/);
  assert.match(text([ui.buildProviders(doc, {})]), /no providers reported yet/);
});
