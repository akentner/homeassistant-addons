package handlers

// auth_rotate is the POST /v1/auth/rotate handler: requires a valid
// bearer (AUTHR-04, enforced by the router's RequireBearer middleware),
// calls TokenStore.Rotate to issue a fresh token with a 24-hour grace
// window for the previous token, and emits a structured audit record
// containing only token fingerprints — never plaintext.

import (
	"encoding/json"
	"log/slog"
	"net/http"

	"iac-runner/internal/auth"
	"iac-runner/internal/contract"
)

// AuthRotate returns the handler mounted at POST /v1/auth/rotate by
// router.go. RequireBearer runs first and rejects anonymous callers
// with 401 + {"error_code":"unauthorized"}.
func AuthRotate(store *auth.TokenStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		actorPlain, _ := r.Context().Value(auth.ActorTokenContextKey()).(string)

		res, err := store.Rotate()
		if err != nil {
			slog.Error("token_rotate_failed", "err", err.Error())
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
				ErrorCode: "rotate_failed",
				Message:   "see iac-runner logs",
			})
			return
		}

		slog.Info("iac_runner.token.rotated",
			"actor_token_fp", auth.Fingerprint(actorPlain),
			"old_token_fp", res.OldTokenFP,
			"new_token_fp", res.NewTokenFP,
			"grace_expires_at", res.GraceExpiresAt,
		)

		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Cache-Control", "no-store")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(contract.RotateResponse{
			NewToken:           res.NewPlaintext,
			GraceExpiresAt:     res.GraceExpiresAt,
			OldTokenValidUntil: res.GraceExpiresAt, // same instant
		})
	}
}
