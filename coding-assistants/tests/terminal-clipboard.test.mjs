import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../app/web/static/terminal-clipboard.mjs', import.meta.url), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));
const payload = text => `c;${Buffer.from(text).toString('base64')}`;

function setup({ writeText, ready = true } = {}) {
  const writes = [];
  const timers = new Map();
  let timerId = 0;
  let receiver;
  let disposals = 0;
  const frame = {
    handlers: {}, hidden: false,
    addEventListener(type, handler) { this.handlers[type] = handler; },
    removeEventListener(type) { delete this.handlers[type]; },
    contentDocument: { readyState: 'complete' },
    classList: { contains: () => frame.hidden },
  };
  const term = { parser: { registerOscHandler(code, callback) {
    assert.equal(code, 52);
    receiver = callback;
    return { dispose() { disposals++; } };
  } } };
  frame.contentWindow = { term: ready ? term : undefined };
  const navigator = { clipboard: { writeText(text) {
    writes.push(text);
    return writeText ? writeText(text) : Promise.resolve();
  } } };
  const api = vm.runInNewContext(source.replace('export ', '') + '\ninstallTerminalClipboard();', {
    document: { getElementById: () => frame }, navigator, atob, TextDecoder, Uint8Array, Promise,
    setTimeout(callback) { timers.set(++timerId, callback); return timerId; },
    clearTimeout(id) { timers.delete(id); },
  });
  return { frame, term, timers, writes, api, receive: data => receiver(data), get disposals() { return disposals; } };
}

test('copies exact Unicode pane text from OSC 52', async () => {
  const state = setup();
  assert.equal(state.receive(payload('Grüße 👋\nsecond line')), true);
  await settle();
  assert.deepEqual(state.writes, ['Grüße 👋\nsecond line']);
});

test('ignores queries, other targets, malformed data, invalid UTF-8 and oversized writes', async () => {
  const state = setup();
  for (const data of ['c;?', 'p;YQ==', 'c;', 'no separator', 'c;%%%', 'c;/w==', `c;${'A'.repeat(1048577)}`]) {
    assert.equal(state.receive(data), true);
  }
  await settle();
  assert.deepEqual(state.writes, []);
});

test('a denied clipboard write is swallowed and later writes still work', async () => {
  let deny = true;
  const state = setup({ writeText: () => deny ? Promise.reject(new Error('denied')) : Promise.resolve() });
  state.receive(payload('first'));
  await settle();
  deny = false;
  state.receive(payload('second'));
  await settle();
  assert.deepEqual(state.writes, ['first', 'second']);
});

test('handles delayed ttyd initialization and ignores output from a hidden terminal', async () => {
  const state = setup({ ready: false });
  assert.equal(state.timers.size, 1);
  state.frame.contentWindow.term = state.term;
  [...state.timers.values()][0]();
  state.frame.hidden = true;
  state.receive(payload('background output'));
  await settle();
  assert.deepEqual(state.writes, []);
});

test('iframe reload disposes the old parser hook; dispose detaches everything', () => {
  const state = setup();
  state.frame.handlers.load();
  assert.equal(state.disposals, 1);
  state.api.dispose();
  assert.equal(state.disposals, 2);
  assert.equal(state.frame.handlers.load, undefined);
});
