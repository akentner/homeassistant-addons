// Package httpapi wires the chi v5 router for the Bridge. Phase 9
// exposed a single GET / placeholder; Phase 10 layers in the auth
// middleware (RequireBearer) and the auth-protected test endpoint
// /v1/whoami. Phase 11+ adds /v1/version, /v1/addons, /v1/info
// under the same /v1/* auth subrouter.
package httpapi

import (
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"

	"terraform-bridge/internal/auth"
	"terraform-bridge/internal/httpapi/handlers"
)

// NewRouter returns the Bridge HTTP handler. store is the TokenStore
// (Plan 01 Task 1) — passed by main.go after the first-start token
// generation step. bridgeVersion is captured at call time so the
// version embedded in the placeholder JSON matches the binary's
// compiled-in value.
func NewRouter(bridgeVersion string, store *auth.TokenStore) http.Handler {
	r := chi.NewRouter()

	// Global middleware order (D-09): RequestID first so every
	// downstream middleware/handler can read it; Recoverer next so
	// panics in any handler don't kill the process. Request-logging
	// middleware (Plan 02) sits between Recoverer and the per-route
	// auth, so it sees the request_id and the auth outcome.
	r.Use(middleware.RequestID)
	r.Use(middleware.Recoverer)

	// Public, unauthenticated surface.
	r.Get("/", rootHandler(bridgeVersion))
	// /healthz lands in Plan 02.

	// Auth-protected /v1/* surface.
	r.Route("/v1", func(r chi.Router) {
		r.Use(auth.RequireBearer(store))
		r.Get("/whoami", handlers.Whoami())
		// /v1/auth/rotate (Plan 03), /v1/version (Phase 11), /v1/addons
		// (Phase 11), /v1/info (Phase 11) mount here in later plans.
	})

	return r
}
