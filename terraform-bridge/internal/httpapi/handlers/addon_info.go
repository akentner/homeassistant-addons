// Package handlers: GET /v1/addons/{slug}/info (BRIDGE-03) returns
// the Supervisor info payload for a single add-on. The endpoint
// requires a valid bearer (mounted inside the /v1 auth subrouter).
// Unknown slugs return HTTP 404 + {error_code: "not_found"}; other
// Supervisor errors return HTTP 502 + {error_code: "upstream_error"}.
//
// The {slug} URL parameter is read via chi's r.PathValue (the chi
// v5 idiomatic accessor; do NOT use chi.URLParam).
package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"time"

	"terraform-bridge/contract"
	"terraform-bridge/internal/supervisor"
)

// addonInfoTimeout caps the upstream Supervisor call for the per-add-on info endpoint.
const addonInfoTimeout = 3 * time.Second

// AddonInfo returns the handler mounted at GET /v1/addons/{slug}/info
// (router.go). Maps supervisor.ErrNotFound to HTTP 404 +
// {error_code: "not_found"} with NO message field (BRIDGE-03
// success criterion uses literal `error_code: "not_found"`).
func AddonInfo(supClient *supervisor.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		slug := r.PathValue("slug")
		if slug == "" {
			// Should be impossible because chi's route pattern
			// requires the {slug} segment, but defensive 404 keeps
			// the invariant explicit.
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusNotFound)
			_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
				ErrorCode: "not_found",
			})
			return
		}

		ctx, cancel := context.WithTimeout(r.Context(), addonInfoTimeout)
		defer cancel()

		info, err := supClient.GetAddonInfo(ctx, slug)
		if err != nil {
			if errors.Is(err, supervisor.ErrNotFound) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusNotFound)
				_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
					ErrorCode: "not_found",
				})
				return
			}
			slog.Warn("bridge_addon_info_upstream_failed",
				"slug", slug, "err", err.Error())
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadGateway)
			_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
				ErrorCode: "upstream_error",
			})
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(info)
	}
}
