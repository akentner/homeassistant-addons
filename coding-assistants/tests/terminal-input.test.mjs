import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../app/web/static/terminal-input.mjs', import.meta.url), 'utf8');

function setup({ ready = 'complete', terminal = true } = {}) {
  const sent = [];
  const handlers = [];
  const frame = {
    contentDocument: {
      readyState: ready,
      addEventListener(type, handler, capture) {
        assert.equal(type, 'keydown');
        assert.equal(capture, true);
        handlers.push(handler);
      },
    },
    contentWindow: { term: terminal ? { input: (...args) => sent.push(args) } : undefined },
    addEventListener(type, handler) {
      assert.equal(type, 'load');
      this.load = handler;
    },
  };
  vm.runInNewContext(source.replace("export ", "") + "\ninstallTerminalInput(document.getElementById('frameTerminal'));", { document: { getElementById: () => frame } });
  function press(overrides = {}) {
    const event = {
      key: 'Enter', shiftKey: true, ctrlKey: false, altKey: false, metaKey: false,
      isComposing: false, target: { classList: { contains: () => true } },
      prevented: false, stopped: false,
      preventDefault() { this.prevented = true; },
      stopImmediatePropagation() { this.stopped = true; },
      ...overrides,
    };
    for (const handler of handlers) handler(event);
    return event;
  }
  return { frame, sent, handlers, press };
}

test('Shift+Enter sends one LF as user input and prevents the original Enter', () => {
  const { sent, press } = setup();
  const event = press();
  assert.deepEqual(sent, [['\n', true]]);
  assert.equal(event.prevented, true);
  assert.equal(event.stopped, true);
});

test('ordinary Enter, other modifiers, IME and non-terminal fields pass through', () => {
  const { sent, press } = setup();
  for (const overrides of [
    { shiftKey: false }, { ctrlKey: true }, { altKey: true }, { metaKey: true },
    { key: 'j', ctrlKey: true }, { isComposing: true }, { target: null },
    { target: { classList: { contains: () => false } } },
  ]) {
    const event = press(overrides);
    assert.equal(event.prevented, false);
    assert.equal(event.stopped, false);
  }
  assert.deepEqual(sent, []);
});

test('a missing ttyd API leaves the original keyboard event alone', () => {
  const { press } = setup({ terminal: false });
  assert.equal(press().prevented, false);
});

test('load attaches once per document and reattaches after iframe navigation', () => {
  const { frame, sent, handlers, press } = setup({ ready: 'loading' });
  assert.equal(handlers.length, 0);
  frame.load();
  frame.load();
  assert.equal(handlers.length, 1);
  press();
  assert.equal(sent.length, 1);
  frame.contentDocument = { ...frame.contentDocument };
  frame.load();
  assert.equal(handlers.length, 2);
});
