// Package handlers: POST /v1/addons/{slug}/start (BRIDGE-06 +
// CONTEXT D-19) wraps Supervisor /apps/{slug}/start. Sync per
// supervisor/api/apps.py (asyncio.shield awaits to completion),
// so the handler makes a single Supervisor call and returns 200
// + AddOnInfo (re-fetched so the response carries the latest
// state).
//
// Order of operations (D-10 explicit):
//
//  1. parse slug from r.PathValue("slug")
//  2. mutexMgr.TryAcquire(r.Context(), slug) -> release closure
//     deferred; ErrLockedTimeout -> 423 + locked +
//     bridge_slug_lock_timeout. start is NOT destructive per
//     D-10 so no critical_addons check + no nonce. Start is
//     allowed even on critical slugs.
//
// PITFALLS S-1: every slog record touching the token uses
// auth.Fingerprint(...) — no plaintext in any log path.
package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"time"

	chimiddleware "github.com/go-chi/chi/v5/middleware"

	"terraform-bridge/contract"
	"terraform-bridge/internal/auth"
	"terraform-bridge/internal/mutex"
	"terraform-bridge/internal/supervisor"
)

const startTimeout = 3 * time.Second

// Start returns the handler mounted at POST /v1/addons/{slug}/start
// (router.go). On Supervisor success re-fetches /apps/{slug}/info
// so the response body reflects the new state (started=true after
// the call).
func Start(supClient *supervisor.Client, mutexMgr *mutex.Manager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		slug := r.PathValue("slug")
		if slug == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusNotFound)
			_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
				ErrorCode: "not_found",
			})
			return
		}
		requestID := chimiddleware.GetReqID(r.Context())
		actorPlain, _ := r.Context().Value(auth.ActorTokenContextKey()).(string)
		actorFP := auth.Fingerprint(actorPlain)

		// Per-slug mutex. start is allowed concurrently across
		// distinct slugs but serializes against uninstall +
		// options on the same slug (D-14).
		release, err := mutexMgr.TryAcquire(r.Context(), slug)
		if err != nil {
			if errors.Is(err, mutex.ErrLockedTimeout) {
				slog.Warn("bridge_slug_lock_timeout",
					"slug", slug,
					"actor_token_fp", actorFP,
					"request_id", requestID,
				)
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusLocked)
				_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
					ErrorCode: "locked",
				})
				return
			}
			slog.Warn("bridge_start_mutex_error",
				"slug", slug,
				"err", err.Error(),
			)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadGateway)
			_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
				ErrorCode: "upstream_error",
			})
			return
		}
		defer release()

		// 3s upstream timeout (D-02).
		ctx, cancel := context.WithTimeout(r.Context(), startTimeout)
		defer cancel()

		if err := supClient.Start(ctx, slug); err != nil {
			status, code := supervisor.MapError(err)
			slog.Warn("bridge_start_upstream_failed",
				"slug", slug,
				"actor_token_fp", actorFP,
				"request_id", requestID,
				"status", status,
				"error_code", code,
				"err", err.Error(),
			)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(status)
			_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
				ErrorCode: code,
			})
			return
		}

		// Re-fetch AddOnInfo so the response carries the latest
		// state (started=true). Uses the same 3s budget; if the
		// refetch fails we still return 502 so the Provider can
		// retry rather than silently masking a stale-state bug.
		info, infoErr := supClient.GetAddonInfo(ctx, slug)
		if infoErr != nil {
			status, code := supervisor.MapError(infoErr)
			slog.Warn("bridge_start_postinfo_failed",
				"slug", slug,
				"actor_token_fp", actorFP,
				"request_id", requestID,
				"status", status,
				"error_code", code,
				"err", infoErr.Error(),
			)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(status)
			_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
				ErrorCode: code,
			})
			return
		}

		slog.Info("bridge_start_succeeded",
			"slug", slug,
			"actor_token_fp", actorFP,
			"request_id", requestID,
		)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(info)
	}
}
