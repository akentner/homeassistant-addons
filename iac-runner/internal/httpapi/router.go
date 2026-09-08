// Package httpapi hosts the iac-runner HTTP API. Mounted routes:
//
//	GET  /                     — rootHandler placeholder
//	GET  /healthz              — handlers.Healthz (exec.LookPath("tofu") + keys.Validate())
//	GET  /v1/version           — handlers.Version (RUN-01)
//	POST /v1/auth/rotate       — handlers.AuthRotate
//	POST /v1/repos/{name}/pull — handlers.ReposPull (GIT-03)
//	POST /v1/plan              — handlers.Plan (RUN-02)
//	POST /v1/apply             — handlers.Apply (RUN-03)
//	GET  /v1/runs/{id}         — handlers.GetRun (RUN-04)
//	GET  /v1/runs              — handlers.ListRuns (RUN-05)
//
// Everything under /v1 sits behind auth.RequireBearer; / and /healthz
// are deliberately unauthenticated so an external monitor can probe
// liveness without a token. Phase 18 adds MQTT Discovery, which
// subscribes to the job-status changes this package surfaces.
package httpapi

import (
	"net/http"

	"github.com/go-chi/chi/v5"
	chimiddleware "github.com/go-chi/chi/v5/middleware"

	"iac-runner/internal/auth"
	"iac-runner/internal/git"
	"iac-runner/internal/httpapi/handlers"
	reqlog "iac-runner/internal/httpapi/middleware"
	"iac-runner/internal/jobq"
	"iac-runner/internal/keys"
	"iac-runner/internal/runs"
)

// NewRouter builds the iac-runner HTTP router.
//
// The Phase 16 signature was (runnerVersion, store, validator);
// Phase 17 appends the three dependencies its endpoints need — the
// git manager (GIT-03), the run store (RUN-04/RUN-05) and the job
// queue (RUN-02/RUN-03). Appending rather than reordering keeps the
// Phase 16 arguments in place, so the RUN-01 /v1/version mount and
// the auth gate are unchanged by this refactor.
//
// This is the ONE place where a Phase 17 URL becomes reachable. Every
// new mount goes inside the existing r.Route("/v1", …) block, which
// is what makes "reachable" and "bearer-authenticated" the same
// statement for all five of them.
//
// Middleware order: RequestID → Recoverer → RequestLogger (per
// terraform-bridge Phase 10 OBS-01 ordering). Recoverer sits above
// every handler, so a panic in a Phase 17 endpoint is a 500 rather
// than a dead listener.
func NewRouter(
	runnerVersion string,
	store *auth.TokenStore,
	validator *keys.Validator,
	gitMgr *git.Manager,
	runStore *runs.Store,
	q *jobq.Queue,
) http.Handler {
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

		// Phase 16 surface — unchanged.
		r.Get("/version", handlers.Version(runnerVersion))
		r.Post("/auth/rotate", handlers.AuthRotate(store))

		// Phase 17 surface.
		r.Post("/repos/{name}/pull", handlers.ReposPull(gitMgr))
		r.Post("/plan", handlers.Plan(q))
		r.Post("/apply", handlers.Apply(q))
		r.Get("/runs/{id}", handlers.GetRun(runStore))
		r.Get("/runs", handlers.ListRuns(runStore))
	})

	return r
}
