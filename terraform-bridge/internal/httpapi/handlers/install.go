// Package handlers: POST /v1/addons/{slug}/install (BRIDGE-04 +
// CONTEXT D-17/D-18/D-26) wraps Supervisor /store/apps/{slug}/install.
//
// Flow per SPECIFIC ordering:
//
//  1. parse slug from r.PathValue("slug")
//  2. critical_addons check (D-10 explicit: install is allowed even
//     on critical slugs for idempotent re-install / upgrade). The
//     check is a NO-OP — install never returns 403 (mirrors the
//     TestInstallHandlerCriticalSlugAllowed regression).
//  3. mutexMgr.TryAcquire(r.Context(), slug) -> release closure
//     deferred; ErrLockedTimeout -> 423 + locked + bridge_slug_lock_timeout.
//  4. outer ctx with installJobTimeout (D-03 / D-17).
//  5. supClient.Install(outerCtx, slug) -> jobID.
//     - errors.Is(err, ErrAlreadyInstalled) (D-26): fall through
//     to the post-install GetAddonInfo adoption path; do NOT
//     short-circuit.
//     - other errors: MapError -> ErrorResponse + return BEFORE
//     polling (no point polling a job that never started).
//  6. linear 1-second polling loop bounded by outerCtx (D-17):
//     for each tick create a 3s sub-ctx, call GetJobStatus,
//     on Done=true break, on transient poll error slog.Warn +
//     continue (don't abort install on /jobs blip), on outerCtx
//     expiration -> 504 + install_timeout + bridge_install_polling_timeout.
//  7. post-install GetAddonInfo with 3x500ms retry (Pitfall 8);
//     only ErrNotFound is retried — other errors surface via
//     MapError.
//
// PITFALLS S-1: every slog record touching the nonce or token uses
// auth.Fingerprint(...) — no plaintext in any log path.
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
	"terraform-bridge/internal/supervisor"
)

// pollInterval is the linear 1-second tick cadence per CONTEXT
// D-17. Hard-coded so the operator cannot accidentally configure
// exponential backoff (which would starve the Provider's per-request
// deadline).
const pollInterval = 1 * time.Second

// pollSubTimeout caps each individual /jobs/{id} poll so a single
// hung /jobs endpoint cannot exhaust the whole outer budget.
const pollSubTimeout = 3 * time.Second

// postInstallRetries + postInstallBackoff implement Pitfall 8: the
// Supervisor job may report Done=true a brief moment before the
// add-on is registered under /apps/{slug}/info. We retry the
// post-install GetAddonInfo this many times at this interval before
// giving up with 502 + upstream_error.
const (
	postInstallRetries  = 3
	postInstallBackoff  = 500 * time.Millisecond
	postInstallAttempts = postInstallRetries // 3 attempts total
)

// Install returns the handler mounted at POST
// /v1/addons/{slug}/install (router.go). The polling loop lives in
// the handler goroutine (NOT a background goroutine, per CONTEXT
// D-18) so ctx cancellation terminates the loop immediately and
// the request log middleware observes the actual elapsed duration.
func Install(supClient *supervisor.Client, mutexMgr *mutex.Manager, criticalAddons []string, installJobTimeout time.Duration) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// (1) parse slug.
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

		// (2) critical_addons check (NO-OP for install per D-10:
		// install is allowed even on critical slugs for idempotent
		// re-install / upgrade). The check stays in the code path
		// for symmetry with the destructive ops (uninstall +
		// options) so operators have a single mental model.
		_ = slices.Contains(criticalAddons, slug)

		// (3) mutex acquire.
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
			slog.Warn("bridge_install_mutex_error",
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

		// (4) outer ctx with installJobTimeout (D-03 / D-17).
		outerCtx, cancelOuter := context.WithTimeout(r.Context(), installJobTimeout)
		defer cancelOuter()

		// (5) first Supervisor call: POST install with
		// background:true (Pitfall 1).
		jobID, err := supClient.Install(outerCtx, slug)
		if err != nil {
			// D-26: 409 already_installed is the Provider adoption
			// signal. Do NOT short-circuit; fall through to
			// GetAddonInfo so the Provider can read the existing
			// add-on state and adopt it (Phase 13 PROV-05).
			if errors.Is(err, supervisor.ErrAlreadyInstalled) {
				slog.Info("bridge_install_adoption",
					"slug", slug,
					"actor_token_fp", actorFP,
					"request_id", requestID,
				)
				info, infoErr := fetchAddonInfoWithRetry(outerCtx, supClient, slug)
				if infoErr != nil {
					status, code := supervisor.MapError(infoErr)
					slog.Warn("bridge_install_postinfo_failed",
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
				slog.Info("bridge_install_succeeded",
					"slug", slug,
					"actor_token_fp", actorFP,
					"request_id", requestID,
					"job_id", "adoption",
				)
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusOK)
				_ = json.NewEncoder(w).Encode(info)
				return
			}
			status, code := supervisor.MapError(err)
			slog.Warn("bridge_install_upstream_failed",
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

		// (6) linear 1-second polling loop (D-17). The for{} exits
		// on Done=true (break) OR outerCtx expiration (return).
		for {
			pollCtx, pollCancel := context.WithTimeout(outerCtx, pollSubTimeout)
			status, pollErr := supClient.GetJobStatus(pollCtx, jobID)
			pollCancel()
			if pollErr != nil {
				// Transient /jobs blip: log warn + keep polling.
				// A single failure does NOT abort the install; the
				// outer ctx still bounds the total budget.
				slog.Warn("bridge_install_poll_failed",
					"slug", slug,
					"job_id", jobID,
					"err", pollErr.Error(),
				)
			} else if status != nil && status.Done {
				break
			}
			// Either transient poll error or Done=false: sleep
			// for pollInterval, but bail immediately if outerCtx
			// expires during the sleep.
			timer := time.NewTimer(pollInterval)
			select {
			case <-outerCtx.Done():
				timer.Stop()
				slog.Warn("bridge_install_polling_timeout",
					"slug", slug,
					"job_id", jobID,
					"actor_token_fp", actorFP,
					"request_id", requestID,
					"elapsed_seconds", int(installJobTimeout.Seconds()),
				)
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusGatewayTimeout)
				_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
					ErrorCode: "install_timeout",
				})
				return
			case <-timer.C:
				// next tick
			}
		}

		// (7) post-install final fetch with retry (Pitfall 8).
		info, infoErr := fetchAddonInfoWithRetry(outerCtx, supClient, slug)
		if infoErr != nil {
			status, code := supervisor.MapError(infoErr)
			slog.Warn("bridge_install_postinfo_failed",
				"slug", slug,
				"job_id", jobID,
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

		slog.Info("bridge_install_succeeded",
			"slug", slug,
			"job_id", jobID,
			"actor_token_fp", actorFP,
			"request_id", requestID,
		)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(info)
	}
}

// fetchAddonInfoWithRetry implements the Pitfall 8 post-install
// retry: 3 attempts total, 500ms backoff between attempts. Only
// ErrNotFound is retried (the brief window between Supervisor's
// job-completion event and the add-on registration). Other errors
// (5xx, network, etc.) surface immediately via MapError downstream.
func fetchAddonInfoWithRetry(ctx context.Context, supClient *supervisor.Client, slug string) (*contract.AddOnInfo, error) {
	var lastErr error
	for attempt := 0; attempt < postInstallAttempts; attempt++ {
		if attempt > 0 {
			// Backoff with ctx-cancellation respect.
			timer := time.NewTimer(postInstallBackoff)
			select {
			case <-ctx.Done():
				timer.Stop()
				return nil, ctx.Err()
			case <-timer.C:
			}
		}
		info, err := supClient.GetAddonInfo(ctx, slug)
		if err == nil {
			return info, nil
		}
		lastErr = err
		if !errors.Is(err, supervisor.ErrNotFound) {
			return nil, err
		}
	}
	return nil, lastErr
}
