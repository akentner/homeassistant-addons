package middleware

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

// chiRouteContext returns the chi.RouteContext from r.Context()
// or nil if no chi router has been mounted for this request.
func chiRouteContext(r *http.Request) *chi.Context {
	if rctx, ok := r.Context().Value(chi.RouteCtxKey).(*chi.Context); ok {
		return rctx
	}
	return nil
}
