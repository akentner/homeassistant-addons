package auth

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"

	"terraform-bridge/contract"
)

// actorTokenCtxKey is the request context key under which the
// validated bearer plaintext is stored for downstream handlers
// (e.g. /v1/whoami uses it to compute actor_token_fp). The value
// is the plaintext token — never logged by middleware/handler code
// (the only token-derived field in any log record is Fingerprint).
type actorTokenCtxKey struct{}

// ActorTokenContextKey returns the context key under which the
// validated bearer plaintext is stored by RequireBearer. Handlers
// down the chain (e.g. Whoami) read it via this accessor so the
// underlying unexported key type stays package-private.
func ActorTokenContextKey() actorTokenCtxKey { return actorTokenCtxKey{} }

// RequireBearer returns a chi-compatible middleware that rejects
// every request lacking a valid Authorization: Bearer <token>
// header with HTTP 401 + {"error_code":"unauthorized"} (CF-03).
//
// The body is the bare error_code; no request body, no token, no
// request_id is echoed back. The middleware never logs the
// presented token (auth package forbids slog calls by invariant;
// see token.go's SECURITY INVARIANTS comment).
func RequireBearer(store *TokenStore) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			header := r.Header.Get("Authorization")
			if !strings.HasPrefix(header, "Bearer ") {
				unauthorized(w)
				return
			}
			plaintext := strings.TrimPrefix(header, "Bearer ")
			if plaintext == "" {
				unauthorized(w)
				return
			}
			if err := store.Validate(plaintext); err != nil {
				unauthorized(w)
				return
			}
			// Stash for downstream handlers (e.g. /v1/whoami).
			ctx := context.WithValue(r.Context(), actorTokenCtxKey{}, plaintext)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

func unauthorized(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnauthorized)
	_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
		ErrorCode: "unauthorized",
	})
}
