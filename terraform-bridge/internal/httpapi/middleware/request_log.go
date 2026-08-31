// Package middleware hosts chi-compatible middleware for the Bridge.
// RequestLogger emits one structured slog record per HTTP request
// carrying the OPS-01 mandatory fields. Authorization is stripped
// from r.Header before any header value is read (D-10 layer 2).
package middleware

import (
	"log/slog"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5/middleware"
)

// statusRecorder wraps http.ResponseWriter to capture the status
// code and bytes written, so the post-request log record carries
// both values.
type statusRecorder struct {
	http.ResponseWriter
	status       int
	bytesWritten int
}

func (r *statusRecorder) WriteHeader(code int) {
	r.status = code
	r.ResponseWriter.WriteHeader(code)
}

func (r *statusRecorder) Write(b []byte) (int, error) {
	if r.status == 0 {
		r.status = http.StatusOK
	}
	n, err := r.ResponseWriter.Write(b)
	r.bytesWritten += n
	return n, err
}

// RequestLogger returns chi middleware that emits one structured
// slog record per request. The record carries the OPS-01 fields
// (ts, level, msg, request_id, route, method, status, duration_ms)
// via slog's default keys plus explicit attrs.
//
// Layer 2 of the AUTH-05 masking: Authorization is deleted from
// r.Header before any header value is read. The slog scrubber
// (Task 1) is layer 1.
func RequestLogger() func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Layer 2: strip Authorization from the r.Header snapshot.
			// We do NOT modify the original r.Header (handlers may
			// need it); we only strip the value from the local copy
			// we pass to slog.
			headersForLog := r.Header.Clone()
			headersForLog.Del("Authorization")

			start := time.Now()
			rec := &statusRecorder{ResponseWriter: w}
			next.ServeHTTP(rec, r)
			duration := time.Since(start)

			route := chiRoutePattern(r)
			if route == "" {
				route = r.URL.Path
			}

			slog.Info("http.request",
				"request_id", middleware.GetReqID(r.Context()),
				"route", route,
				"method", r.Method,
				"status", rec.status,
				"duration_ms", duration.Milliseconds(),
				"bytes", rec.bytesWritten,
				"remote_addr", r.RemoteAddr,
				"user_agent", headersForLog.Get("User-Agent"),
			)
		})
	}
}

// chiRoutePattern returns the chi route pattern (e.g. "/v1/{slug}/info")
// if one is registered for r.URL.Path; otherwise empty string.
func chiRoutePattern(r *http.Request) string {
	// chi's RouteContext is on the request context; we use the
	// public chi helper to read the matched pattern. If the route
	// did not match (404), this returns "" and the logger falls
	// back to the raw path.
	rctx := chiRouteContext(r)
	if rctx == nil {
		return ""
	}
	return rctx.RoutePattern()
}
