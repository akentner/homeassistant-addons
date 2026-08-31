// Package handlers hosts the HTTP handler functions for the Bridge.
// whoami is a Phase-10 test endpoint that proves the auth middleware
// works end-to-end without depending on the Supervisor API surface
// (which lands in Phase 11).
package handlers

import (
	"encoding/json"
	"net/http"

	"terraform-bridge/contract"
	"terraform-bridge/internal/auth"
)

// Whoami returns the actor_token_fp derived from the validated bearer
// token. The plaintext token itself never leaves the auth package —
// only the 16-char hex Fingerprint reaches the wire.
//
// Mounted at GET /v1/whoami under RequireBearer (router.go).
func Whoami() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		plaintext, ok := r.Context().Value(auth.ActorTokenContextKey()).(string)
		if !ok || plaintext == "" {
			// Should never happen — RequireBearer sets the context value
			// before this handler runs. Defensive 401 keeps the
			// invariant explicit.
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			_ = json.NewEncoder(w).Encode(contract.ErrorResponse{ErrorCode: "unauthorized"})
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(contract.TokenResponse{
			ActorTokenFP: auth.Fingerprint(plaintext),
		})
	}
}
