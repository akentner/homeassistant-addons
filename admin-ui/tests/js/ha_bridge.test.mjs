import test from "node:test";
import assert from "node:assert/strict";

const LIB = new URL("../../app/web/static/lib/", import.meta.url);
const { createHaBridge } = await import(new URL("ha-bridge.mjs", LIB));

const ORIGIN = "http://ha.local";
const INSETS = { top: "0px", right: "0px", bottom: "0px", left: "0px" };

function makeEnv({ embedded = true, origin = ORIGIN, top = 0, probeThrows = false, ...opts } = {}) {
  const env = { posts: [], listeners: new Set(), timers: [], top, clock: 1000 };
  const parent = {
    postMessage(message, targetOrigin) {
      if (env.postThrows) throw new Error("DataCloneError");
      env.posts.push({ message, targetOrigin });
    },
  };
  const win = {
    location: { origin },
    frameElement: {
      getBoundingClientRect: () => {
        if (probeThrows) throw new Error("SecurityError");
        return { top: env.top };
      },
    },
    addEventListener: (type, fn) => type === "message" && env.listeners.add(fn),
    removeEventListener: (type, fn) => type === "message" && env.listeners.delete(fn),
  };
  win.parent = embedded ? parent : win;
  env.win = win;
  env.parent = parent;
  env.bridge = createHaBridge({
    win,
    now: () => env.clock,
    setTimeout: (fn, ms) => {
      env.timers.push({ fn, ms, cleared: false });
      return env.timers.length - 1;
    },
    clearTimeout: (id) => {
      if (env.timers[id]) env.timers[id].cleared = true;
    },
    ...opts,
  });
  env.send = (data, over = {}) => {
    const ev = { source: parent, origin, data, ...over };
    for (const fn of [...env.listeners]) fn(ev);
  };
  env.props = (narrow, extra = {}) =>
    env.send({ type: "home-assistant/properties", narrow, safeAreaInsets: INSETS, route: null, ...extra });
  env.types = () => env.posts.map((p) => p.message.type.replace("home-assistant/", ""));
  return env;
}

test("not embedded: posts nothing, registers nothing, actions return false", () => {
  for (const mode of ["equal", "missing"]) {
    const env = makeEnv({ embedded: false });
    if (mode === "missing") env.win.parent = undefined;
    env.bridge.start();
    assert.equal(env.posts.length, 0);
    assert.equal(env.listeners.size, 0);
    assert.equal(env.timers.length, 0);
    const st = env.bridge.getState();
    assert.equal(st.embedded, false);
    assert.equal(st.status, "idle");
    assert.equal(env.bridge.toggleMenu(), false);
    assert.equal(env.bridge.navigate("/config"), false);
  }
});

test("embedded start subscribes to the page origin, waits and arms the fallback timer", () => {
  const env = makeEnv();
  env.bridge.start();
  assert.equal(env.listeners.size, 1);
  assert.deepEqual(env.posts, [{ message: { type: "home-assistant/subscribe-properties" }, targetOrigin: ORIGIN }]);
  assert.equal(env.bridge.getState().status, "waiting");
  assert.equal(env.timers.length, 1);
  assert.equal(env.timers[0].ms, 1500);
});

test("target origin option wins, an opaque origin falls back to *", () => {
  const a = makeEnv({ targetOrigin: "https://ha.example" });
  a.bridge.start();
  assert.equal(a.posts[0].targetOrigin, "https://ha.example");
  for (const origin of ["null", ""]) {
    const b = makeEnv({ origin });
    b.bridge.start();
    assert.equal(b.posts[0].targetOrigin, "*");
  }
});

test("handleSafeArea and the always policy add their fields; narrow adds neither", () => {
  const plain = makeEnv();
  plain.bridge.start();
  assert.deepEqual(Object.keys(plain.posts[0].message), ["type"]);
  const env = makeEnv({ handleSafeArea: true, kiosk: "always" });
  env.bridge.start();
  assert.deepEqual(env.posts[0].message, {
    type: "home-assistant/subscribe-properties",
    handleSafeArea: true,
    kioskMode: true,
  });
  assert.equal(env.bridge.getState().kiosk, true);
});

test("inbound filter: wrong source, origin, type or narrow type is ignored", () => {
  const env = makeEnv();
  env.bridge.start();
  const good = { type: "home-assistant/properties", narrow: false };
  env.send(good, { source: {} });
  env.send(good, { source: null });
  env.send(good, { origin: "http://evil.example" });
  env.send({ ...good, type: "home-assistant/other" });
  env.send({ ...good, narrow: "yes" });
  env.send({ type: "home-assistant/properties" });
  env.send(null);
  env.send("home-assistant/properties");
  assert.equal(env.bridge.getState().messages, 0);
  assert.equal(env.bridge.getState().status, "waiting");
  env.send(good);
  assert.equal(env.bridge.getState().messages, 1);
});

test("an opaque page origin never accepts inbound messages", () => {
  const env = makeEnv({ origin: "null" });
  env.bridge.start();
  env.send({ type: "home-assistant/properties", narrow: false });
  assert.equal(env.bridge.getState().messages, 0);
});

test("fields are validated: insets, route and unknown fields", () => {
  const env = makeEnv();
  env.bridge.start();
  env.props(false, {
    safeAreaInsets: { top: "47px", right: "0", bottom: "34.5px", left: "-1px" },
    route: { path: "/a", prefix: "/app", evil: "x" },
    extra: "dropped",
  });
  let st = env.bridge.getState();
  assert.deepEqual(st.safeAreaInsets, { top: "47px", right: "0", bottom: "34.5px", left: "-1px" });
  assert.deepEqual(st.route, { path: "/a", prefix: "/app" });
  assert.equal("extra" in st, false);

  env.props(false, { safeAreaInsets: { top: "1em", right: "0", bottom: "0", left: "0" }, route: { path: "a", prefix: "" } });
  st = env.bridge.getState();
  assert.equal(st.safeAreaInsets, null);
  assert.equal(st.route, null);

  env.props(false, { safeAreaInsets: { top: "0", right: "0", bottom: "0" }, route: { path: "/" + "x".repeat(600), prefix: "" } });
  st = env.bridge.getState();
  assert.equal(st.safeAreaInsets, null);
  assert.equal(st.route, null);
});

test("a valid message sets ok, counts, stamps the time and clears the fallback timer", () => {
  const env = makeEnv();
  env.bridge.start();
  env.clock = 4242;
  env.props(false);
  const st = env.bridge.getState();
  assert.equal(st.status, "ok");
  assert.equal(st.messages, 1);
  assert.equal(st.lastMessageAt, 4242);
  assert.equal(env.timers[0].cleared, true);
});

test("no answer in time reports no_answer, a late answer still recovers", () => {
  const env = makeEnv();
  const seen = [];
  env.bridge.subscribe((s) => seen.push(s.status));
  env.bridge.start();
  env.timers[0].fn();
  assert.equal(env.bridge.getState().status, "no_answer");
  env.props(false);
  assert.equal(env.bridge.getState().status, "ok");
  assert.ok(seen.includes("no_answer"));
});

test("narrow policy: narrow true requests kiosk once, the echo posts nothing more", () => {
  const env = makeEnv();
  env.bridge.start();
  env.props(true);
  assert.equal(env.bridge.getState().kiosk, true);
  assert.deepEqual(env.posts.at(-1).message, { type: "home-assistant/subscribe-properties", kioskMode: true });
  const count = env.posts.length;
  env.props(true);
  env.props(true);
  assert.equal(env.posts.length, count);
});

test("narrow true to false: unsubscribe then subscribe without kioskMode", () => {
  const env = makeEnv();
  env.bridge.start();
  env.props(true);
  const from = env.posts.length;
  env.props(false);
  const tail = env.posts.slice(from).map((p) => p.message);
  assert.deepEqual(tail, [
    { type: "home-assistant/unsubscribe-properties" },
    { type: "home-assistant/subscribe-properties" },
  ]);
  assert.equal(env.bridge.getState().kiosk, false);
});

test("a docked desktop (narrow false, no host bar) never requests kiosk", () => {
  const env = makeEnv({ top: 0 });
  env.bridge.start();
  env.props(false);
  env.props(false);
  assert.equal(env.bridge.getState().kiosk, false);
  assert.equal(env.bridge.getState().hostBar, false);
  assert.deepEqual(env.types(), ["subscribe-properties"]);
});

test("host-bar probe requests kiosk and stays sticky when the bar disappears", () => {
  const env = makeEnv({ top: 40 });
  env.bridge.start();
  env.props(false);
  assert.equal(env.bridge.getState().hostBar, true);
  assert.equal(env.bridge.getState().kiosk, true);
  env.top = 0;
  env.props(false);
  env.props(false);
  assert.equal(env.bridge.getState().hostBar, true);
  assert.equal(env.bridge.getState().kiosk, true);
  env.props(true);
  env.props(false);
  assert.equal(env.bridge.getState().hostBar, false);
  assert.equal(env.bridge.getState().kiosk, false);
});

test("the probe subtracts the safe-area top before deciding", () => {
  const env = makeEnv({ top: 47 });
  env.bridge.start();
  env.props(false, { safeAreaInsets: { ...INSETS, top: "47px" } });
  assert.equal(env.bridge.getState().hostBar, false);
  env.top = 87;
  env.props(false, { safeAreaInsets: { ...INSETS, top: "47px" } });
  assert.equal(env.bridge.getState().hostBar, true);
});

test("frameProbe false or a throwing probe leaves hostBar null", () => {
  const off = makeEnv({ top: 40, frameProbe: false });
  off.bridge.start();
  off.props(false);
  assert.equal(off.bridge.getState().hostBar, null);
  assert.equal(off.bridge.getState().kiosk, false);
  const bad = makeEnv({ probeThrows: true });
  bad.bridge.start();
  bad.props(false);
  assert.equal(bad.bridge.getState().hostBar, null);
});

test("never policy never requests kiosk; configure switches policy and re-subscribes", () => {
  const env = makeEnv({ kiosk: "never" });
  env.bridge.start();
  env.props(true);
  assert.equal(env.bridge.getState().kiosk, false);
  assert.deepEqual(env.types(), ["subscribe-properties"]);

  env.bridge.configure({ kiosk: "always" });
  assert.equal(env.bridge.getState().kiosk, true);
  assert.deepEqual(env.posts.slice(-2).map((p) => p.message), [
    { type: "home-assistant/unsubscribe-properties" },
    { type: "home-assistant/subscribe-properties", kioskMode: true },
  ]);

  env.bridge.configure({ kiosk: "never" });
  assert.equal(env.bridge.getState().kiosk, false);
  assert.deepEqual(env.posts.at(-1).message, { type: "home-assistant/subscribe-properties" });

  env.bridge.configure({ handleSafeArea: true });
  assert.equal(env.posts.at(-1).message.handleSafeArea, true);
});

test("freeze guard stops a kiosk transition loop", () => {
  const env = makeEnv();
  env.bridge.start();
  for (let i = 0; i < 12; i += 1) {
    env.clock += 100;
    env.props(i % 2 === 0);
  }
  const st = env.bridge.getState();
  assert.equal(st.kioskFrozen, true);
  const count = env.posts.length;
  env.clock += 100;
  env.props(true);
  env.props(false);
  assert.equal(env.posts.length, count);
});

test("transitions spread over time do not freeze", () => {
  const env = makeEnv();
  env.bridge.start();
  for (let i = 0; i < 10; i += 1) {
    env.clock += 11000;
    env.props(i % 2 === 0);
  }
  assert.equal(env.bridge.getState().kioskFrozen, false);
});

test("toggleMenu posts the menu message", () => {
  const env = makeEnv();
  env.bridge.start();
  assert.equal(env.bridge.toggleMenu(), true);
  assert.deepEqual(env.posts.at(-1), { message: { type: "home-assistant/toggle-menu" }, targetOrigin: ORIGIN });
});

test("navigate posts only safe single-slash paths", () => {
  const env = makeEnv();
  env.bridge.start();
  assert.equal(env.bridge.navigate("/config/integrations"), true);
  assert.deepEqual(env.posts.at(-1).message, { type: "home-assistant/navigate", path: "/config/integrations" });
  const count = env.posts.length;
  const bad = [
    "config",
    "//evil.example",
    "/a//b",
    "https://evil.example",
    "javascript:alert(1)",
    "/a\\b",
    "/a\nb",
    "/a\u0000b",
    "/" + "x".repeat(600),
    "",
    null,
    undefined,
    42,
    {},
  ];
  for (const path of bad) assert.equal(env.bridge.navigate(path), false, String(path).slice(0, 30));
  assert.equal(env.posts.length, count);
});

test("a throwing postMessage is caught", () => {
  const env = makeEnv();
  env.bridge.start();
  env.postThrows = true;
  assert.doesNotThrow(() => env.bridge.toggleMenu());
  assert.equal(env.bridge.toggleMenu(), false);
  assert.equal(env.bridge.navigate("/config"), false);
  assert.doesNotThrow(() => env.props(true));
});

test("dispose removes the listener and timer, unsubscribes and resets to idle", () => {
  const env = makeEnv();
  env.bridge.start();
  env.props(false);
  env.bridge.dispose();
  assert.equal(env.listeners.size, 0);
  assert.deepEqual(env.posts.at(-1).message, { type: "home-assistant/unsubscribe-properties" });
  const st = env.bridge.getState();
  assert.equal(st.status, "idle");
  assert.equal(st.messages, 0);
  assert.equal(st.kiosk, false);
  const fresh = makeEnv();
  fresh.bridge.start();
  fresh.bridge.dispose();
  assert.equal(fresh.timers[0].cleared, true);
  const never = makeEnv({ embedded: false });
  never.bridge.start();
  never.bridge.dispose();
  assert.equal(never.posts.length, 0);
});

test("subscribe notifies on state changes, unsubscribes, and getState returns a copy", () => {
  const env = makeEnv();
  const seen = [];
  const off = env.bridge.subscribe((s) => seen.push(s.status));
  env.bridge.start();
  env.props(false, { route: { path: "/x", prefix: "/p" } });
  assert.deepEqual(seen, ["waiting", "ok"]);
  off();
  const copy = env.bridge.getState();
  copy.route.path = "/changed";
  copy.status = "tampered";
  assert.equal(env.bridge.getState().status, "ok");
  assert.equal(env.bridge.getState().route.path, "/x");
  env.props(false);
  assert.equal(seen.length, 2);
});
