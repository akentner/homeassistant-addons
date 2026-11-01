import test from "node:test";
import assert from "node:assert/strict";
import * as ui from "../../app/web/static/lib/ui.mjs";

const EXPECTED = [
  "html", "render", "useState", "useEffect", "useMemo", "useRef", "useCallback",
  "toast", "Toasts", "Modal", "ConfirmDialog", "Badge", "OriginBadge", "ErrorNote", "Loading",
  "CopyField", "PermSelect", "useAsync", "usePoll",
];

test("ui exports the full component contract", () => {
  assert.ok(EXPECTED.length >= 12);
  for (const name of EXPECTED) assert.equal(typeof ui[name], "function", name);
});

test("toast works without a DOM (store only)", () => {
  const timers = [];
  const realSetTimeout = globalThis.setTimeout;
  globalThis.setTimeout = (fn, ms) => (timers.push([fn, ms]), 0);
  try {
    const id = ui.toast("ok", "hello");
    assert.equal(typeof id, "number");
    assert.equal(timers[0][1], 5000);
    timers[0][0]();
  } finally {
    globalThis.setTimeout = realSetTimeout;
  }
});
