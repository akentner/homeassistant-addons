import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../app/web/static/terminal-clipboard.mjs', import.meta.url), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));
const payload = text => `c;${Buffer.from(text).toString('base64')}`;

function setup({ writeText, legacy = false, ready = true } = {}) {
  const writes = [];
  const timers = new Map();
  let timerId = 0;
  let receiver;
  let disposals = 0;
  let legacyCalls = 0;
  function element() {
    return {
      handlers: {}, value: '', textContent: '', disabled: true, open: false, style: {},
      addEventListener(type, handler) { this.handlers[type] = handler; },
      focus() {}, select() { this.selected = true; }, remove() {},
      showModal() { this.open = true; }, close() { this.open = false; },
    };
  }
  const elements = Object.fromEntries([
    'frameTerminal', 'copySelection', 'clipboardStatus', 'clipboardDialog', 'clipboardText', 'closeClipboard',
  ].map(id => [id, element()]));
  const term = { parser: { registerOscHandler(code, callback) {
    assert.equal(code, 52);
    receiver = callback;
    return { dispose() { disposals++; } };
  } } };
  const frame = elements.frameTerminal;
  frame.contentDocument = { readyState: 'complete' };
  frame.contentWindow = { term: ready ? term : undefined };
  frame.hidden = false;
  frame.classList = { contains: () => frame.hidden };
  const document = {
    getElementById: id => elements[id],
    createElement: element,
    body: { appendChild() {} },
    execCommand(command) { assert.equal(command, 'copy'); legacyCalls++; return legacy; },
  };
  const navigator = { clipboard: { writeText(text) {
    writes.push(text);
    return writeText ? writeText(text) : Promise.resolve();
  } } };
  vm.runInNewContext(source.replace("export ", "") + "\ninstallTerminalClipboard(key => ({'ca.clipboard.copied': 'Copied', 'ca.clipboard.ready': 'Ready to copy'}[key]));", {
    document, navigator, atob, TextDecoder, Uint8Array,
    setTimeout(callback) { timers.set(++timerId, callback); return timerId; },
    clearTimeout(id) { timers.delete(id); },
  });
  return {
    elements, frame, term, timers, writes, navigator,
    receive: data => receiver(data),
    click: () => elements.copySelection.handlers.click(),
    get disposals() { return disposals; },
    get legacyCalls() { return legacyCalls; },
  };
}

test('copies exact Unicode pane text from OSC 52 without reading xterm screen selection', async () => {
  const state = setup();
  assert.equal(state.receive(payload('Grüße 👋\nsecond line')), true);
  await settle();
  assert.deepEqual(state.writes, ['Grüße 👋\nsecond line']);
  assert.equal(state.elements.copySelection.disabled, false);
  assert.equal(state.elements.clipboardStatus.textContent, 'Copied');
});

test('ignores queries, other targets, malformed data, invalid UTF-8 and oversized writes', async () => {
  const state = setup();
  for (const data of ['c;?', 'p;YQ==', 'c;', 'no separator', 'c;%%%','c;/w==', `c;${'A'.repeat(1048577)}`]) {
    assert.equal(state.receive(data), true);
  }
  await settle();
  assert.deepEqual(state.writes, []);
  assert.equal(state.elements.copySelection.disabled, true);
});

test('permission denial offers a button; explicit click can use legacy copy', async () => {
  const state = setup({ writeText: () => Promise.reject(new Error('denied')), legacy: true });
  state.receive(payload('pane text'));
  await settle();
  assert.equal(state.legacyCalls, 0);
  assert.equal(state.elements.clipboardStatus.textContent, 'Ready to copy');
  state.click();
  await settle();
  assert.equal(state.legacyCalls, 1);
  assert.equal(state.elements.clipboardStatus.textContent, 'Copied');
  assert.equal(state.elements.clipboardDialog.open, false);
});

test('without clipboard APIs, explicit copy opens a selected readonly text view', async () => {
  const state = setup();
  delete state.navigator.clipboard;
  const text = '<script>literal text</script>\nsecond line';
  state.receive(payload(text));
  await settle();
  assert.equal(state.elements.clipboardDialog.open, false);
  state.click();
  await settle();
  assert.equal(state.elements.clipboardDialog.open, true);
  assert.equal(state.elements.clipboardText.value, text);
  assert.equal(state.elements.clipboardText.selected, true);
});

test('iframe reload clears stale text, closes the dialog and disposes the old parser', async () => {
  const state = setup();
  delete state.navigator.clipboard;
  state.receive(payload('old selection'));
  state.click();
  await settle();
  state.frame.handlers.load();
  assert.equal(state.disposals, 1);
  assert.equal(state.elements.copySelection.disabled, true);
  assert.equal(state.elements.clipboardText.value, '');
  assert.equal(state.elements.clipboardDialog.open, false);
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
  assert.equal(state.elements.copySelection.disabled, true);
});

test('serializes asynchronous writes and skips superseded selections', async () => {
  let release;
  const state = setup({ writeText: text => text === 'first' ? new Promise(resolve => { release = resolve; }) : undefined });
  state.receive(payload('first'));
  await settle();
  state.receive(payload('second'));
  state.receive(payload('latest'));
  release();
  await settle();
  assert.deepEqual(state.writes, ['first', 'latest']);
  assert.equal(state.elements.clipboardStatus.textContent, 'Copied');
});
