// Package handlers: POST /v1/addons/{slug}/options (BRIDGE-08 +
// LIFE-01/LIFE-03 + CONTEXT D-09..D-12 + Pitfall 7) wraps
// Supervisor /apps/{slug}/options with a validate-first flow.
//
// STRICT ORDERING (Destructive op — D-10 + Pitfall 2):
//
//  1. parse slug from r.PathValue("slug")
//  2. critical_addons check FIRST (BEFORE nonce + mutex) ->
//     403 critical_addon_protected. The cheap local list
//     lookup short-circuits even when another request holds
//     the per-slug mutex (regression-tested in <100ms).
//  3. X-Force-Destroy header validation SECOND -> 401
//     nonce_expired|nonce_used BEFORE the mutex (Pitfall 2).
//     Missing header -> nonce_expired; presented-but-invalid ->
//     nonce_expired or nonce_used.
//  4. mutexMgr.TryAcquire -> release deferred; ErrLockedTimeout
//     -> 423 + locked + bridge_slug_lock_timeout.
//  5. read r.Body ONCE into map[string]any (Pitfall 7
//     anti-pattern: "Reading r.Body twice" — re-marshal the
//     decoded map for the second call instead of re-reading
//     the body).
//  6. ctx with 3s upstream timeout (D-02).
//  7. supClient.ValidateOptions -> *OptionsValidateDiagnostic.
//     On err: 502 + upstream_error + bridge_options_validate_failed.
//     On diag.Valid=false: 400 with diag as the response body
//     VERBATIM (NOT wrapped in ErrorResponse; pwned tri-state
//     preserved per BRIDGE-08 typed diagnostics).
//  8. On diag.Valid=true: supClient.Options apply-phase.
//     On err mapping 4xx (Pitfall 7 validate-options race):
//     400 with the supervisor diagnostic envelope (NOT 502).
//     On err mapping 5xx: 502 + upstream_error + slog.Warn
//     bridge_options_upstream_failed.
//  9. On apply success: re-fetch via supClient.GetAddonInfo
//     and write 200 + AddOnInfo.
//
// PITFALLS S-1: every slog record touching the nonce or token
// uses auth.Fingerprint(...) — no plaintext in any log path.
package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"slices"
	"strings"
	"time"

	chimiddleware "github.com/go-chi/chi/v5/middleware"

	"terraform-bridge/contract"
	"terraform-bridge/internal/auth"
	"terraform-bridge/internal/mutex"
	"terraform-bridge/internal/nonce"
	"terraform-bridge/internal/supervisor"
)

const optionsTimeout = 3 * time.Second

// Options returns the handler mounted at POST
// /v1/addons/{slug}/options (router.go). The handler enforces
// the strict ordering documented in the package comment; the
// TestOptionsHandlerCriticalSlug403BeforeMutex + the nonce-401
// tests prove the critical_addons + nonce checks complete in
// <100ms even when the per-slug mutex is held.
func Options(supClient *supervisor.Client, mutexMgr *mutex.Manager, nonceMgr *nonce.Manager, criticalAddons []string) http.HandlerFunc {
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

		// (2) critical_addons FIRST (BEFORE nonce + mutex).
		// 403 critical_addon_protected; NO slug echo.
		if slices.Contains(criticalAddons, slug) {
			slog.Warn("bridge_options_critical_addon",
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
		// nonce_expired (mirrors uninstall's contract).
		presented := r.Header.Get("X-Force-Destroy")
		if presented == "" {
			slog.Warn("bridge_options_nonce_missing",
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
			slog.Warn("bridge_options_nonce_invalid",
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

		// (4) mutex acquire.
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
			slog.Warn("bridge_options_mutex_error",
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

		// (5) read body ONCE into map[string]any (Pitfall 7).
		// All subsequent Supervisor calls reuse `opts` — never
		// re-read r.Body (Pitfall 7 anti-pattern: "Reading
		// r.Body twice").
		body, _ := io.ReadAll(r.Body)
		var opts map[string]any
		if len(body) > 0 {
			if err := json.Unmarshal(body, &opts); err != nil {
				slog.Warn("bridge_options_body_invalid",
					"slug", slug,
					"actor_token_fp", actorFP,
					"nonce_fp", nonceFP,
					"request_id", requestID,
					"err", err.Error(),
				)
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
					ErrorCode: "invalid_body",
				})
				return
			}
		}

		// (6) upstream ctx.
		ctx, cancel := context.WithTimeout(r.Context(), optionsTimeout)
		defer cancel()

		// (7) ValidateOptions FIRST.
		diag, err := supClient.ValidateOptions(ctx, slug, opts)
		if err != nil {
			status, code := supervisor.MapError(err)
			slog.Warn("bridge_options_validate_failed",
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
		if diag != nil && !diag.Valid {
			// 400 + Supervisor's diagnostic envelope VERBATIM
			// (NOT wrapped in ErrorResponse). pwned tri-state
			// (true/false/nil) is preserved per BRIDGE-08.
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			_ = json.NewEncoder(w).Encode(diag)
			return
		}

		// (8) apply options.
		if err := supClient.Options(ctx, slug, opts); err != nil {
			// Pitfall 7: apply-options race. Supervisor
			// apps.options re-validates internally; if the
			// re-validation fails (4xx) we surface 400 — NOT
			// 502 — because the validator already returned
			// valid=true and the Provider expects typed
			// diagnostic semantics on bad options. We detect
			// the 4xx from the wrapped error message BEFORE
			// MapError can mask it (4xx falls into the
			// ErrTransient default branch in classifyStatus,
			// which MapError returns as 502).
			isClientError := strings.Contains(err.Error(), "status 4")
			status, code := supervisor.MapError(err)
			if isClientError {
				slog.Warn("bridge_options_apply_race",
					"slug", slug,
					"actor_token_fp", actorFP,
					"nonce_fp", nonceFP,
					"request_id", requestID,
					"status", status,
					"err", err.Error(),
				)
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
					ErrorCode: code,
				})
				return
			}
			slog.Warn("bridge_options_upstream_failed",
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

		// (9) re-fetch AddOnInfo for the response body.
		info, infoErr := supClient.GetAddonInfo(ctx, slug)
		if infoErr != nil {
			status, code := supervisor.MapError(infoErr)
			slog.Warn("bridge_options_postinfo_failed",
				"slug", slug,
				"actor_token_fp", actorFP,
				"nonce_fp", nonceFP,
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

		slog.Info("bridge_options_succeeded",
			"slug", slug,
			"actor_token_fp", actorFP,
			"nonce_fp", nonceFP,
			"request_id", requestID,
		)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(info)
	}
}
