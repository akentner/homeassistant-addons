package middleware

import (
	"context"
	"net/http"
	"time"
)

// TryLockTimeout returns a chi-compatible middleware that wraps each
// incoming request's context with a deadline-bounded context.WithTimeout.
// The deadline is the per-request budget the handler uses for
// mutexMgr.TryAcquire(r.Context(), slug) so a contended slug returns
// 423 + locked within a predictable window instead of waiting for the
// client to disconnect.
//
// Bridge Plan 03 wiring: cmd/bridge/main.go reads
// try_lock_timeout_seconds from /data/options.json (default 5s) and
// passes it to NewRouter, which mounts this middleware inside the
// /v1 auth subrouter BEFORE auth.RequireBearer. That way every
// handler call that does mutexMgr.TryAcquire(r.Context(), slug) —
// install/start/stop/uninstall/options — has a deadline the goroutine
// inside TryAcquire can select on.
//
// The deadline wraps the request context; downstream code that reads
// r.Context() sees the wrapped ctx. If the handler returns before the
// deadline elapses, the cancel func is called via the deferred cancel
// in the middleware wrapper below.
//
// Auth is checked BEFORE this middleware via the existing
// RequireBearer (CF-03 order), so anonymous requests do not consume a
// try-lock timeout slot — the 401 short-circuits the chain.
//
// PITFALLS S-1 invariant: nothing here logs the request body, the
// bearer, or any token-derived value. The middleware carries no log
// record.
func TryLockTimeout(d time.Duration) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if d <= 0 {
				// Defensive: NewRouter clamps to a non-zero default
				// upstream; if a caller still passes zero, skip the
				// wrap so handlers don't immediately see ctx.Done().
				next.ServeHTTP(w, r)
				return
			}
			ctx, cancel := context.WithTimeout(r.Context(), d)
			defer cancel()
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}
