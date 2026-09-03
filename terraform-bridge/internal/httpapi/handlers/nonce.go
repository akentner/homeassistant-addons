// Package handlers hosts the HTTP handler functions for the Bridge.
// nonce.go mounts POST /v1/auth/nonce inside the existing /v1 auth
// subrouter (RequireBearer). The handler issues a 60s single-use
// nonce via internal/nonce.Manager.Issue and returns the contract
// NonceResponse. Anti-CSRF (per 12-CONTEXT/DISCUSSION-LOG): nonce
// issuance MUST require a valid bearer; otherwise an attacker on
// the same Tailscale network could trivially mint nonces and bypass
// X-Force-Destroy entirely. The TestRouterNonceRequiresAuth router
// test enforces this invariant.
package handlers

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"time"

	chimiddleware "github.com/go-chi/chi/v5/middleware"

	"terraform-bridge/contract"
	"terraform-bridge/internal/auth"
	"terraform-bridge/internal/nonce"
)

// Nonce issues a single-use destruction nonce. The handler:
//
//  1. Reads the validated bearer from r.Context() (RequireBearer
//     stashed it during auth). If absent - defensive 401.
//  2. Computes actor_token_fp via auth.Fingerprint(plaintext).
//  3. Reads request_id via chimiddleware.GetReqID for the journal row.
//  4. Calls nonceMgr.Issue(actorFP, requestID) -> (nonce, expiresAt).
//  5. Writes 200 + NonceResponse{nonce, expires_at:RFC3339}.
//  6. Emits slog.Info bridge_nonce_issued with actor_token_fp +
//     nonce_fp (PITFALLS S-1 invariant - plaintext never logged).
//
// On Manager.Issue error (rare - rand.Read failure): 502 +
// upstream_error + slog.Warn bridge_nonce_issue_failed.
func Nonce(nonceMgr *nonce.Manager) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		actorPlain, _ := r.Context().Value(auth.ActorTokenContextKey()).(string)
		actorFP := auth.Fingerprint(actorPlain)
		requestID := chimiddleware.GetReqID(r.Context())

		plaintext, expiresAt, err := nonceMgr.Issue(actorFP, requestID)
		if err != nil {
			slog.Warn("bridge_nonce_issue_failed",
				"actor_token_fp", actorFP,
				"request_id", requestID,
				"err", err.Error(),
			)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadGateway)
			_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
				ErrorCode: "upstream_error",
			})
			return
		}

		// PITFALLS S-1: log only fingerprint, never the plaintext nonce.
		slog.Info("bridge_nonce_issued",
			"actor_token_fp", actorFP,
			"nonce_fp", auth.Fingerprint(plaintext),
			"request_id", requestID,
			"expires_at", expiresAt.UTC().Format(time.RFC3339),
		)

		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Cache-Control", "no-store")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(contract.NonceResponse{
			Nonce:     plaintext,
			ExpiresAt: expiresAt.UTC().Format(time.RFC3339),
		})
	}
}
