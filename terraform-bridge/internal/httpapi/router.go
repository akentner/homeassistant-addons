// Phase 10 router: GET /healthz (no auth, OPS-03); /v1/whoami test
// endpoint under RequireBearer; RequestLogger globally mounted for
// OPS-01. Phase 11+ adds /v1/version, /v1/addons, /v1/info under the
// same /v1/* auth subrouter. Phase 12 adds /v1/auth/nonce +
// /v1/state/index + /v1/addons/{slug}/uninstall + (Plan 02)
// /v1/addons/{slug}/install + /v1/addons/{slug}/start +
// /v1/addons/{slug}/stop + /v1/addons/{slug}/options (all require
// bearer).
package httpapi

import (
	"net/http"
	"path/filepath"
	"time"

	"github.com/go-chi/chi/v5"
	chimiddleware "github.com/go-chi/chi/v5/middleware"

	"terraform-bridge/internal/auth"
	"terraform-bridge/internal/httpapi/handlers"
	reqlog "terraform-bridge/internal/httpapi/middleware"
	"terraform-bridge/internal/mutex"
	"terraform-bridge/internal/nonce"
	"terraform-bridge/internal/supervisor"
)

// NewRouter builds the Bridge HTTP router. The signature
// intentionally bundles every Phase 12 dependency (mutex
// manager, nonce manager, critical_addons list, lock + install
// timeouts) so Plan 03's main.go has a single, well-typed
// construction site. Handlers that don't need a given manager
// receive nil; that handler panics on first request if the
// dependency is misconfigured (fail-fast at startup in
// production). Tests pass stub values.
//
// tryLockTimeout is accepted now so Plan 03 can wire it through
// cmd/bridge/main.go without another signature churn. installJobTimeout
// IS used by handlers.Install (Plan 02) — the per-install polling
// loop's outer ctx.
//
// Auth subrouter order (read-only-first-then-mutation, then by
// destructive-ness):
//
//	/version, /whoami, /addons, /addons/{slug}/info, /state/index,
//	/auth/nonce (mutation: issuance),
//	/addons/{slug}/install (Plan 02 Task 1; non-destructive),
//	/addons/{slug}/start (Plan 02 Task 2; non-destructive),
//	/addons/{slug}/stop (Plan 02 Task 2; non-destructive),
//	/addons/{slug}/uninstall (Plan 01; destructive),
//	/addons/{slug}/options (Plan 02 Task 2; destructive),
//	/auth/rotate (mutation: rotate).
func NewRouter(bridgeVersion string, store *auth.TokenStore, supClient *supervisor.Client,
	mutexMgr *mutex.Manager, nonceMgr *nonce.Manager, criticalAddons []string,
	startTime time.Time, stateFilePath string, tryLockTimeout time.Duration, installJobTimeout time.Duration) http.Handler {
	_ = tryLockTimeout // reserved for Plan 03 wiring

	r := chi.NewRouter()

	// D-09 / CF-06 order: RequestID -> Recoverer -> RequestLogger
	r.Use(chimiddleware.RequestID)
	r.Use(chimiddleware.Recoverer)
	r.Use(reqlog.RequestLogger())

	// Public, unauthenticated.
	r.Get("/", rootHandler(bridgeVersion))
	r.Get("/healthz", handlers.Healthz(supClient, bridgeVersion))
	r.Get("/v1/info", handlers.Info(supClient, bridgeVersion, startTime, stateFilePath))

	// Compute the data directory once for the StateIndex handler.
	// Production: /data (stateFilePath = /data/terraform.tfstate).
	dataDir := filepath.Dir(stateFilePath)

	// Auth-protected /v1/*.
	r.Route("/v1", func(r chi.Router) {
		r.Use(auth.RequireBearer(store))
		r.Get("/version", handlers.Version(bridgeVersion))
		r.Get("/whoami", handlers.Whoami())
		r.Get("/addons", handlers.Addons(supClient))
		r.Get("/addons/{slug}/info", handlers.AddonInfo(supClient))
		r.Get("/state/index", handlers.StateIndex(dataDir))
		r.Post("/auth/nonce", handlers.Nonce(nonceMgr))
		r.Post("/addons/{slug}/install", handlers.Install(supClient, mutexMgr, criticalAddons, installJobTimeout))
		r.Post("/addons/{slug}/uninstall", handlers.Uninstall(supClient, mutexMgr, nonceMgr, criticalAddons))
		r.Post("/auth/rotate", handlers.AuthRotate(store))
	})

	return r
}
