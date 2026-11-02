// Demo-local record of how the add-on info link was last followed (feeds the spike result block, S7).
// HA never confirms a navigate message, so this stores the chosen path only, never a success.
const PATHS = ["bridge", "fallback"];

export function createInfoNav() {
  const state = { last: "none", count: 0 };
  const listeners = new Set();
  return {
    getState: () => ({ ...state }),
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    record(path) {
      if (!PATHS.includes(path)) return;
      state.last = path;
      state.count += 1;
      listeners.forEach((fn) => fn({ ...state }));
    },
  };
}
