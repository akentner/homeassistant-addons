// Package handlers: POST /v1/addons/{slug}/stop (BRIDGE-07 +
// CONTEXT D-19) wraps Supervisor /apps/{slug}/stop. Symmetric to
// start.go (sync per D-19; no nonce required per D-10).
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

const stopTimeout = 3 * time.Second

// Stop returns the handler mounted at POST /v1/addons/{slug}/stop
// (router.go). On Supervisor success re-fetches /apps/{slug}/info
// so the response body reflects the new state (started=false).
func Stop(supClient *supervisor.Client, mutexMgr *mutex.Manager) http.HandlerFunc {
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
			slog.Warn("bridge_stop_mutex_error",
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

		ctx, cancel := context.WithTimeout(r.Context(), stopTimeout)
		defer cancel()

		if err := supClient.Stop(ctx, slug); err != nil {
			status, code := supervisor.MapError(err)
			slog.Warn("bridge_stop_upstream_failed",
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

		info, infoErr := supClient.GetAddonInfo(ctx, slug)
		if infoErr != nil {
			status, code := supervisor.MapError(infoErr)
			slog.Warn("bridge_stop_postinfo_failed",
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

		slog.Info("bridge_stop_succeeded",
			"slug", slug,
			"actor_token_fp", actorFP,
			"request_id", requestID,
		)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(info)
	}
}
