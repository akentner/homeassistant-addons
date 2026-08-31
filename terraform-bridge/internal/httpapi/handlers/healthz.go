// Package handlers hosts the Bridge HTTP handler functions. Healthz
// is the OPS-03 endpoint: probes /supervisor/ping on every request
// (no caching) and returns 200 + JSON on success, 503 + empty body
// on failure. HA Supervisor's health-check polls this endpoint.
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

// healthzTimeout caps the per-probe budget for /healthz. HA
// Supervisor's health-check polls at a configurable cadence (often
// 15-30s); 2s per probe is well below the lowest reasonable poll
// interval (D-07).
const healthzTimeout = 2 * time.Second

// Healthz returns an http.HandlerFunc that probes Supervisor and
// emits the OPS-03 response. bridgeVersion is embedded in the 200
// body so external monitors can correlate Bridge version with
// liveness signal (Phase 11 expands the version contract).
func Healthz(supClient *supervisor.Client, bridgeVersion string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), healthzTimeout)
		defer cancel()

		err := supClient.Ping(ctx)
		if err != nil {
			// D-08: 503 body is empty. Log a single Warn record
			// BEFORE writing the response so operators have a
			// forensic trail (the response itself never leaks
			// internal state).
			slog.Warn("supervisor.ping_failed", "err", err.Error())
			w.Header().Set("Content-Length", "0")
			w.WriteHeader(http.StatusServiceUnavailable)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(contract.HealthResponse{
			Status:              "ok",
			SupervisorReachable: true,
			BridgeVersion:       bridgeVersion,
		})
	}
}
