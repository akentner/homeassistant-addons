// Package httpapi wires the chi v5 router for the Phase 9 scaffold.
//
// Phase 9 exposes a single GET / endpoint that returns the bridge_version /
// status / msg placeholder JSON. Later phases (10-12) layer in /healthz, the
// bearer-auth middleware, and the read/write API surface. Keeping the router
// wiring isolated here means Plan 03 (signal handling + no-token-leak verify)
// and Plan 10 (auth + structured logging) can modify routes without touching
// the process entrypoint in cmd/bridge.
package httpapi

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

// NewRouter returns the Phase 9 HTTP handler. The bridgeVersion parameter is
// captured at call time so the version embedded in the placeholder JSON matches
// the binary's compiled-in value (overwritten via -ldflags at build time).
func NewRouter(bridgeVersion string) http.Handler {
	r := chi.NewRouter()

	r.Get("/", rootHandler(bridgeVersion))

	return r
}