// Async and polling hooks. Plain Node can load this module (no DOM access at import time).
import { useState, useEffect, useRef, useCallback } from "./vendor/preact-htm.mjs";

// Runs fn on mount and whenever deps change; a stale result (unmount, newer run) is ignored.
export function useAsync(fn, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true }));
    Promise.resolve()
      .then(fn)
      .then(
        (data) => live && setState({ data, error: null, loading: false }),
        (error) => live && setState({ data: null, error, loading: false }),
      );
    return () => {
      live = false;
    };
  }, [...deps, tick]);
  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { ...state, reload };
}

// Calls the latest fn every ms while the page is not hidden.
export function usePoll(fn, ms) {
  const saved = useRef(fn);
  saved.current = fn;
  useEffect(() => {
    const run = () => {
      if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
      saved.current();
    };
    const timer = setInterval(run, ms);
    return () => clearInterval(timer);
  }, [ms]);
}
