// Package handlers: GET /v1/info (BRIDGE-10) returns the Bridge's
// self-description for use in terraform_data and lifecycle.precondition
// blocks. The endpoint is PUBLIC (no RequireBearer) because Terraform
// references it from arbitrary resource graphs without an actor token.
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

// infoTimeout caps the upstream Supervisor call so a stalled Supervisor
// does not exhaust the caller's HTTP timeout budget.
const infoTimeout = 3 * time.Second

// Info returns the handler mounted at GET /v1/info (router.go).
// supClient fetches Supervisor version; bridgeVersion is the compiled-in
// bridge_version (cmd/bridge/version.go); startTime is captured in
// main.go as the first line of func main(); stateFilePath is
// /data/terraform.tfstate (Phase 1 default).
//
// On supClient error the handler returns HTTP 502 +
// {error_code: "upstream_error"} so the response body never leaks
// internal Supervisor error text (PITFALLS S-1).
func Info(supClient *supervisor.Client, bridgeVersion string, startTime time.Time, stateFilePath string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), infoTimeout)
		defer cancel()

		info, err := supClient.GetSupervisorInfo(ctx)
		if err != nil {
			slog.Warn("bridge_info_upstream_failed", "err", err.Error())
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadGateway)
			_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
				ErrorCode: "upstream_error",
			})
			return
		}

		uptimeSeconds := int64(time.Since(startTime) / time.Second)
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Cache-Control", "no-store")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(contract.BridgeInfo{
			BridgeVersion:     bridgeVersion,
			SupervisorVersion: info.Version,
			UptimeSeconds:     uptimeSeconds,
			StateFilePath:     stateFilePath,
		})
	}
}
