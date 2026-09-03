// Package handlers: POST /v1/addons/{slug}/uninstall (BRIDGE-05 +
// LIFE-01/LIFE-03 + CONTEXT D-09..D-15) wraps Supervisor
// /apps/{slug}/uninstall.
//
// STRICT ORDERING (Specifics + D-11 + Pitfall 2):
//
//  1. parse slug from r.PathValue("slug")
//  2. critical_addons check -> 403 critical_addon_protected
//     BEFORE mutex acquisition so the cheap local list lookup
//     short-circuits and the Bridge returns 403 even when the
//     per-slug mutex is held by another request.
//  3. X-Force-Destroy header validation via nonceMgr.Validate.
//     Missing/expired/used -> 401 nonce_expired|nonce_used.
//  4. mutexMgr.TryAcquire with the handler's r.Context()
//     deadline (default 5s per CONTEXT D-13) -> 423 locked on
//     timeout. defer release().
//  5. context.WithTimeout(r.Context(), 3s) for the Supervisor call.
//  6. supClient.Uninstall -> 204 on success; supClient error
//     mapped via supervisor.MapError -> ErrorResponse.
//
// PITFALLS S-1: every log record touching the nonce uses
// auth.Fingerprint(presented) — the plaintext nonce is NEVER
// passed to slog.
package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"slices"
	"time"

	chimiddleware "github.com/go-chi/chi/v5/middleware"

	"terraform-bridge/contract"
	"terraform-bridge/internal/auth"
	"terraform-bridge/internal/mutex"
	"terraform-bridge/internal/nonce"
	"terraform-bridge/internal/supervisor"
)

const uninstallTimeout = 3 * time.Second

// Uninstall returns the handler mounted at POST
// /v1/addons/{slug}/uninstall (router.go). The handler enforces
// the strict ordering documented in the package comment; the
// TestUninstallCriticalSlug403BeforeMutex regression test
// proves the critical_addons check happens BEFORE the mutex
// acquisition by holding the mutex from another goroutine and
// asserting the 403 returns within 100ms.
func Uninstall(supClient *supervisor.Client, mutexMgr *mutex.Manager, nonceMgr *nonce.Manager, criticalAddons []string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// (1) parse slug — chi's route guarantees non-empty
		// unless the routing itself is broken; defensive 404
		// keeps the invariant explicit (mirrors Phase 11).
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

		// (2) critical_addons FIRST (BEFORE nonce + mutex).
		// 403 critical_addon_protected, NO message, NO slug echo.
		if slices.Contains(criticalAddons, slug) {
			slog.Warn("bridge_uninstall_critical_addon",
				"slug", slug,
				"actor_token_fp", actorFP,
				"request_id", requestID,
			)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusForbidden)
			_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
				ErrorCode: "critical_addon_protected",
			})
			return
		}

		// (3) X-Force-Destroy header validation. Missing ->
		// nonce_expired (covers "never issued" semantically per
		// D-06). Presented -> Validate.
		presented := r.Header.Get("X-Force-Destroy")
		if presented == "" {
			slog.Warn("bridge_uninstall_nonce_missing",
				"slug", slug,
				"actor_token_fp", actorFP,
				"request_id", requestID,
			)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
				ErrorCode: "nonce_expired",
			})
			return
		}
		nonceFP := auth.Fingerprint(presented)
		ok, err := nonceMgr.Validate(presented, actorFP, requestID)
		if err != nil {
			code := "nonce_expired"
			if errors.Is(err, nonce.ErrNonceUsed) {
				code = "nonce_used"
			}
			slog.Warn("bridge_uninstall_nonce_invalid",
				"slug", slug,
				"actor_token_fp", actorFP,
				"nonce_fp", nonceFP,
				"request_id", requestID,
				"err_code", code,
			)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
				ErrorCode: code,
			})
			return
		}
		_ = ok

		// (4) mutex acquisition per-slug. ctx is the request
		// context; 5s ceiling per CONTEXT D-13 is imposed by
		// the r.Context() that the router wired (handlers
		// always carry a deadline via the request log middleware
		// + the handler timeout imposed by the operation). The
		// Plan 03 main.go wires the 5s context ceiling.
		release, err := mutexMgr.TryAcquire(r.Context(), slug)
		if err != nil {
			if errors.Is(err, mutex.ErrLockedTimeout) {
				slog.Warn("bridge_slug_lock_timeout",
					"slug", slug,
					"actor_token_fp", actorFP,
					"nonce_fp", nonceFP,
					"request_id", requestID,
				)
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusLocked)
				_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
					ErrorCode: "locked",
				})
				return
			}
			// Unknown error from TryAcquire — treat as 502.
			slog.Warn("bridge_uninstall_mutex_error",
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

		// (5) request-scoped Supervisor ctx with 3s timeout.
		ctx, cancel := context.WithTimeout(r.Context(), uninstallTimeout)
		defer cancel()

		// (6) call Supervisor.
		err = supClient.Uninstall(ctx, slug)
		if err != nil {
			status, code := supervisor.MapError(err)
			slog.Warn("bridge_uninstall_upstream_failed",
				"slug", slug,
				"actor_token_fp", actorFP,
				"nonce_fp", nonceFP,
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

		slog.Info("bridge_uninstall_succeeded",
			"slug", slug,
			"actor_token_fp", actorFP,
			"nonce_fp", nonceFP,
			"request_id", requestID,
		)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNoContent)
	}
}
