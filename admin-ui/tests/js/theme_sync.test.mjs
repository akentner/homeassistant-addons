import test from "node:test";
import assert from "node:assert/strict";

const LIB = new URL("../../app/web/static/lib/", import.meta.url);
const { createThemeSync, THEME_WHITELIST } = await import(new URL("theme-sync.mjs", LIB));
const { parseColor, serializeColor, contrastRatio } = await import(new URL("color.mjs", LIB));

const SAFE = /^(#[0-9a-f]{6}|rgba\(\d{1,3}, \d{1,3}, \d{1,3}, (0|1|0\.\d{1,3})\))$/;

const LIGHT = {
  "--primary-background-color": "#fafafa",
  "--card-background-color": "#ffffff",
  "--primary-text-color": "rgb(33, 33, 33)",
  "--divider-color": "rgba(0, 0, 0, 0.12)",
  "--primary-color": "#009ac7",
};
const DARK = {
  "--primary-background-color": "#111111",
  "--card-background-color": "#1c1c1c",
  "--primary-text-color": "rgb(225, 225, 225)",
  "--divider-color": "rgba(225, 225, 225, 0.12)",
  "--primary-color": "#03a9f4",
};

function makeRoot() {
  const props = new Map();
  const attrs = new Map();
  return {
    props,
    attrs,
    style: {
      setProperty: (n, v) => props.set(n, v),
      removeProperty: (n) => props.delete(n),
    },
    setAttribute: (n, v) => attrs.set(n, v),
    removeAttribute: (n) => attrs.delete(n),
    getAttribute: (n) => (attrs.has(n) ? attrs.get(n) : null),
  };
}

function makeEnv({ vars = LIGHT, embedded = true, throwDoc = false, noObserver = false } = {}) {
  const env = { vars: { ...vars }, observers: [], intervals: [], winListeners: {}, docListeners: {} };
  class MO {
    constructor(cb) {
      this.cb = cb;
      this.target = null;
      this.opts = null;
      this.disconnected = false;
      env.observers.push(this);
    }
    observe(target, opts) {
      this.target = target;
      this.opts = opts;
    }
    disconnect() {
      this.disconnected = true;
    }
  }
  const docEl = { id: "parent-root" };
  const parent = {
    getComputedStyle: () => ({ getPropertyValue: (name) => env.vars[name] ?? "" }),
    MutationObserver: noObserver ? undefined : MO,
  };
  Object.defineProperty(parent, "document", {
    get() {
      if (throwDoc) throw new Error("SecurityError");
      return { documentElement: docEl };
    },
  });
  const reg = (store) => ({
    addEventListener: (t, f) => (store[t] ||= new Set()).add(f),
    removeEventListener: (t, f) => store[t]?.delete(f),
  });
  const win = { location: { origin: "http://ha" }, document: reg(env.docListeners), ...reg(env.winListeners) };
  win.parent = embedded ? parent : win;
  env.win = win;
  env.parentDocEl = docEl;
  env.root = makeRoot();
  env.sync = createThemeSync({
    win,
    root: env.root,
    pollMs: 3000,
    now: () => 1234,
    setInterval: (fn, ms) => {
      env.intervals.push({ fn, ms, cleared: false });
      return env.intervals.length - 1;
    },
    clearInterval: (id) => {
      if (env.intervals[id]) env.intervals[id].cleared = true;
    },
  });
  return env;
}

const assertSafeWrites = (root) => {
  for (const [name, value] of root.props) {
    assert.match(name, /^--sync-/);
    assert.match(value, SAFE, `${name}=${value}`);
  }
};

test("whitelist is frozen and names exactly the five synced variables", () => {
  assert.ok(Object.isFrozen(THEME_WHITELIST));
  assert.deepEqual(
    THEME_WHITELIST.map((w) => [w.sync, w.ha, w.group]),
    [
      ["--sync-bg", "--primary-background-color", "surface"],
      ["--sync-card", "--card-background-color", "surface"],
      ["--sync-fg", "--primary-text-color", "surface"],
      ["--sync-bd", "--divider-color", "surface"],
      ["--sync-acc", "--primary-color", "accent"],
    ],
  );
});

test("not embedded: inert, no observer, no timer, nothing written", () => {
  const env = makeEnv({ embedded: false });
  env.sync.start();
  assert.deepEqual(
    { active: env.sync.status().active, reason: env.sync.status().reason },
    { active: false, reason: "not_embedded" },
  );
  assert.equal(env.observers.length, 0);
  assert.equal(env.intervals.length, 0);
  assert.equal(env.root.props.size, 0);
  assert.equal(env.root.attrs.size, 0);
  assert.equal(Object.keys(env.winListeners).length, 0);
});

test("missing parent counts as not embedded", () => {
  const env = makeEnv();
  env.win.parent = undefined;
  env.sync.start();
  assert.equal(env.sync.status().reason, "not_embedded");
  assert.equal(env.root.props.size, 0);
});

test("inaccessible parent: reason parent_inaccessible, nothing written, no exception", () => {
  const env = makeEnv({ throwDoc: true });
  assert.doesNotThrow(() => env.sync.start());
  assert.equal(env.sync.status().active, false);
  assert.equal(env.sync.status().reason, "parent_inaccessible");
  assert.equal(env.root.props.size, 0);
  assert.equal(env.root.attrs.size, 0);
});

test("HA default light theme: surface applied, accent skipped for contrast", () => {
  const env = makeEnv({ vars: LIGHT });
  env.sync.start();
  const st = env.sync.status();
  assert.equal(st.mode, "light");
  assert.equal(env.root.attrs.get("data-theme"), "light");
  assert.equal(env.root.props.get("--sync-bg"), "#fafafa");
  assert.equal(env.root.props.get("--sync-card"), "#ffffff");
  assert.equal(env.root.props.get("--sync-fg"), "#212121");
  assert.equal(env.root.props.get("--sync-bd"), "rgba(0, 0, 0, 0.12)");
  assert.equal(env.root.props.has("--sync-acc"), false);
  assert.equal(env.root.props.has("--sync-on-acc"), false);
  assert.equal(st.surface, true);
  assert.equal(st.accent, false);
  assert.deepEqual(st.skipped, ["accent"]);
  assert.equal(st.lastSync, 1234);
  assertSafeWrites(env.root);
});

test("dark theme: surface and accent applied, on-colour meets 4.5:1", () => {
  const env = makeEnv({ vars: DARK });
  env.sync.start();
  const st = env.sync.status();
  assert.equal(st.mode, "dark");
  assert.equal(env.root.attrs.get("data-theme"), "dark");
  assert.equal(env.root.props.get("--sync-acc"), "#03a9f4");
  const on = parseColor(env.root.props.get("--sync-on-acc"));
  assert.ok(contrastRatio(on, parseColor("#03a9f4")) >= 4.5);
  assert.deepEqual(st.skipped, []);
  assert.equal(st.accent, true);
  assertSafeWrites(env.root);
});

test("unparseable or non-opaque background removes everything it set", () => {
  const env = makeEnv({ vars: DARK });
  env.sync.start();
  assert.ok(env.root.props.size > 0);
  env.vars["--primary-background-color"] = "var(--x)";
  env.sync.refresh();
  assert.equal(env.sync.status().reason, "unparseable_background");
  assert.equal(env.root.props.size, 0);
  assert.equal(env.root.attrs.has("data-theme"), false);

  env.vars["--primary-background-color"] = "rgba(0, 0, 0, 0.5)";
  env.sync.refresh();
  assert.equal(env.sync.status().reason, "unparseable_background");
  assert.equal(env.root.props.size, 0);
});

test("text failing 4.5:1 skips the surface group but data-theme still follows luminance", () => {
  const env = makeEnv({ vars: DARK });
  env.sync.start();
  assert.ok(env.root.props.has("--sync-bg"));
  env.vars["--primary-text-color"] = "#222222";
  env.sync.refresh();
  const st = env.sync.status();
  assert.equal(st.surface, false);
  assert.equal(st.accent, false);
  assert.ok(st.skipped.includes("surface"));
  assert.equal(env.root.props.size, 0);
  assert.equal(env.root.attrs.get("data-theme"), "dark");
});

test("hostile parent values never reach setProperty", () => {
  const hostile = [
    "red; background:url(//evil)",
    "url(javascript:alert(1))",
    "#fff; } body { display:none",
    "x".repeat(100000),
    "rgb(0,0,0); --x:1",
  ];
  for (const value of hostile) {
    for (const key of Object.keys(DARK)) {
      const env = makeEnv({ vars: DARK });
      env.vars[key] = value;
      env.sync.start();
      assertSafeWrites(env.root);
      for (const v of env.root.props.values()) assert.ok(!v.includes("evil") && !v.includes("javascript"));
    }
  }
});

test("status.raw holds serialised colours only, never the original strings", () => {
  const env = makeEnv({ vars: { ...LIGHT, "--primary-text-color": "  RGB(33, 33, 33)  ", "--primary-color": "evil;" } });
  env.sync.start();
  const { raw } = env.sync.status();
  assert.equal(raw.fg, "#212121");
  assert.equal(raw.acc, null);
  assert.equal(raw.bg, serializeColor(parseColor("#fafafa")));
  assert.ok(!JSON.stringify(raw).includes("evil"));
});

test("observer and interval call refresh and count; identical input writes nothing new", () => {
  const env = makeEnv({ vars: DARK });
  env.sync.start();
  assert.equal(env.observers.length, 1);
  assert.equal(env.observers[0].target, env.parentDocEl);
  assert.deepEqual(env.observers[0].opts, { attributes: true, attributeFilter: ["style"] });
  assert.equal(env.intervals.length, 1);
  assert.equal(env.intervals[0].ms, 3000);
  const applied = env.sync.status().counters.apply;
  assert.ok(applied > 0);
  env.observers[0].cb();
  env.intervals[0].fn();
  const st = env.sync.status();
  assert.equal(st.counters.observer, 1);
  assert.equal(st.counters.poll, 1);
  assert.equal(st.counters.apply, applied);
});

test("a changed parent value rewrites only the changed properties", () => {
  const env = makeEnv({ vars: DARK });
  env.sync.start();
  const before = env.sync.status().counters.apply;
  env.vars["--card-background-color"] = "#202020";
  env.observers[0].cb();
  assert.equal(env.root.props.get("--sync-card"), "#202020");
  assert.equal(env.sync.status().counters.apply, before + 1);
});

test("focus and visibilitychange trigger a refresh and are removed on dispose", () => {
  const env = makeEnv({ vars: DARK });
  env.sync.start();
  assert.equal(env.winListeners.focus.size, 1);
  assert.equal(env.docListeners.visibilitychange.size, 1);
  const before = env.sync.status().counters.refresh;
  [...env.winListeners.focus][0]();
  [...env.docListeners.visibilitychange][0]();
  assert.equal(env.sync.status().counters.refresh, before + 2);
  env.sync.dispose();
  assert.equal(env.winListeners.focus.size, 0);
  assert.equal(env.docListeners.visibilitychange.size, 0);
});

test("a missing MutationObserver falls back to polling only", () => {
  const env = makeEnv({ vars: DARK, noObserver: true });
  assert.doesNotThrow(() => env.sync.start());
  assert.equal(env.observers.length, 0);
  assert.equal(env.intervals.length, 1);
  assert.equal(env.sync.status().active, true);
});

test("subscribe listeners get a status snapshot after each refresh", () => {
  const env = makeEnv({ vars: DARK });
  const seen = [];
  const off = env.sync.subscribe((s) => seen.push(s.mode));
  env.sync.start();
  env.sync.refresh();
  assert.deepEqual(seen, ["dark", "dark"]);
  off();
  env.sync.refresh();
  assert.equal(seen.length, 2);
});

test("an internal failure is caught: reason error and sync properties removed", () => {
  const env = makeEnv({ vars: DARK });
  env.sync.start();
  assert.ok(env.root.props.size > 0);
  env.vars["--card-background-color"] = "#202020";
  const real = env.root.style.setProperty;
  env.root.style.setProperty = () => {
    throw new Error("boom");
  };
  assert.doesNotThrow(() => env.observers[0].cb());
  assert.equal(env.sync.status().reason, "error");
  assert.equal(env.sync.status().active, false);
  assert.equal(env.root.props.size, 0);
  env.root.style.setProperty = real;
  env.sync.refresh();
  assert.equal(env.sync.status().reason, "ok");
});

test("dispose cleans up everything and start works again afterwards", () => {
  const env = makeEnv({ vars: DARK });
  env.sync.start();
  env.sync.dispose();
  assert.equal(env.observers[0].disconnected, true);
  assert.equal(env.intervals[0].cleared, true);
  assert.equal(env.root.props.size, 0);
  assert.equal(env.root.attrs.has("data-theme"), false);
  assert.equal(env.sync.status().active, false);
  env.sync.start();
  assert.equal(env.sync.status().active, true);
  assert.equal(env.root.attrs.get("data-theme"), "dark");
  assert.equal(env.observers.length, 2);
  assert.equal(env.intervals.length, 2);
});

test("data-theme set by someone else is left alone when sync never set it", () => {
  const env = makeEnv({ embedded: false });
  env.root.attrs.set("data-theme", "dark");
  env.sync.start();
  env.sync.dispose();
  assert.equal(env.root.attrs.get("data-theme"), "dark");
});
