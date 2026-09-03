// Package handlers: GET /v1/addons (BRIDGE-02) returns a JSON array
// of every installed add-on. The endpoint requires a valid bearer
// (mounted inside the /v1 auth subrouter). Supervisor V2 (/apps)
// is preferred with V1 (/addons) fallback; the V1/V2 selection is
// entirely inside supervisor.Client.ListAddons.
//
// Slog key convention: warning keys follow the form
// `bridge_<endpoint>_upstream_failed` (matching the precedent set in
// info.go's `bridge_info_upstream_failed`). New upstream-failure log
// keys MUST use the same prefix so log greppers don't have to
// maintain a per-handler allowlist.
package handlers

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"time"

	"terraform-bridge/contract"
	"terraform-bridge/internal/supervisor"
)

// addonsTimeout caps the upstream Supervisor call for /v1/addons.
const addonsTimeout = 3 * time.Second

// Addons returns the handler mounted at GET /v1/addons (router.go).
// On supClient error the handler returns HTTP 502 +
// {error_code: "upstream_error"}; the response body never leaks
// internal Supervisor error text (PITFALLS S-1).
func Addons(supClient *supervisor.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), addonsTimeout)
		defer cancel()

		items, err := supClient.ListAddons(ctx)
		if err != nil {
			slog.Warn("bridge_addons_upstream_failed", "err", err.Error())
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadGateway)
			_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
				ErrorCode: "upstream_error",
			})
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		// BRIDGE-02 specifies the body is a JSON array, NOT a
		// wrapped envelope. Encode the slice directly.
		_ = json.NewEncoder(w).Encode(items)
	}
}
