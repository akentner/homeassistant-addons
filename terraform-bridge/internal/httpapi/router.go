// Phase 10 router: GET /healthz (no auth, OPS-03); /v1/whoami test
// endpoint under RequireBearer; RequestLogger globally mounted for
// OPS-01. Phase 11+ adds /v1/version, /v1/addons, /v1/info under the
// same /v1/* auth subrouter.
package httpapi

import (
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	chimiddleware "github.com/go-chi/chi/v5/middleware"

	"terraform-bridge/internal/auth"
	"terraform-bridge/internal/httpapi/handlers"
	reqlog "terraform-bridge/internal/httpapi/middleware"
	"terraform-bridge/internal/supervisor"
)

func NewRouter(bridgeVersion string, store *auth.TokenStore, supClient *supervisor.Client, startTime time.Time, stateFilePath string) http.Handler {
	r := chi.NewRouter()

	// D-09 / CF-06 order: RequestID -> Recoverer -> RequestLogger
	r.Use(chimiddleware.RequestID)
	r.Use(chimiddleware.Recoverer)
	r.Use(reqlog.RequestLogger())

	// Public, unauthenticated.
	r.Get("/", rootHandler(bridgeVersion))
	r.Get("/healthz", handlers.Healthz(supClient, bridgeVersion))
	r.Get("/v1/info", handlers.Info(supClient, bridgeVersion, startTime, stateFilePath))

	// Auth-protected /v1/*.
	r.Route("/v1", func(r chi.Router) {
		r.Use(auth.RequireBearer(store))
		r.Get("/version", handlers.Version(bridgeVersion))
		r.Get("/whoami", handlers.Whoami())
		r.Post("/auth/rotate", handlers.AuthRotate(store))
	})

	return r
}
