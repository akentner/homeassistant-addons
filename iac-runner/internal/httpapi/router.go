// Package httpapi hosts the iac-runner HTTP API. Phase 16 mounts:
//
//	GET  /              — rootHandler placeholder
//	GET  /healthz       — handlers.Healthz (real probes: exec.LookPath("tofu") + keys.Validate())
//	POST /v1/auth/rotate — handlers.AuthRotate (RequireBearer-wrapped)
//
// Plan 03 adds GET /v1/version (handlers.Version using
// contract.VersionHandshake). Plans 17/18 add /v1/plan, /v1/apply,
// /v1/runs/{id}, /v1/runs.
package httpapi

import (
	"net/http"

	"github.com/go-chi/chi/v5"
	chimiddleware "github.com/go-chi/chi/v5/middleware"

	"iac-runner/internal/auth"
	"iac-runner/internal/httpapi/handlers"
	"iac-runner/internal/keys"
	reqlog "iac-runner/internal/httpapi/middleware"
)

// NewRouter builds the iac-runner HTTP router. The Plan 01 signature
// was (runnerVersion, store); Plan 02 extends with the keys
// validator so the /healthz handler can probe /data/keys/ chmod 600
// on every request. Plan 03 adds the version handler; Plans 17/18
// add run-history + MQTT.
//
// Middleware order: RequestID → Recoverer → RequestLogger (per
// terraform-bridge Phase 10 OBS-01 ordering).
func NewRouter(runnerVersion string, store *auth.TokenStore, validator *keys.Validator) http.Handler {
	r := chi.NewRouter()

	r.Use(chimiddleware.RequestID)
	r.Use(chimiddleware.Recoverer)
	r.Use(reqlog.RequestLogger())

	// Public, unauthenticated.
	r.Get("/", rootHandler(runnerVersion))
	r.Get("/healthz", handlers.Healthz(runnerVersion, validator))

	// Auth-protected /v1/*.
	r.Route("/v1", func(r chi.Router) {
		r.Use(auth.RequireBearer(store))
		r.Get("/version", handlers.Version(runnerVersion))
		r.Post("/auth/rotate", handlers.AuthRotate(store))
	})

	return r
}
