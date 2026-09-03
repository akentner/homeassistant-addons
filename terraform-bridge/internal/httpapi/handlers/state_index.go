// Package handlers: GET /v1/state/index (STATE-02) returns the
// per-file SHA-256 of every *.tfstate + *.tfstate.backup in the
// data directory (CONTEXT D-20..D-23). Auth required — mounted
// inside the /v1 chi subrouter. Empty result returns 200 +
// {files: []}, not 404 (D-23). Per-file errors are accumulated
// as a skipped slice.
package handlers

import (
	"encoding/json"
	"log/slog"
	"net/http"

	chimiddleware "github.com/go-chi/chi/v5/middleware"

	"terraform-bridge/contract"
	"terraform-bridge/internal/state"
)

// StateIndex returns the handler mounted at GET /v1/state/index
// (router.go). The dataDir parameter is the directory to
// enumerate (production: filepath.Dir(stateFilePath) = /data;
// tests: t.TempDir()).
//
// On success: 200 + StateIndexResponse{files, skipped} +
// slog.Info bridge_state_index_served.
//
// On Index() top-level error (rare — typically a syntax error
// in the glob pattern, never hits in practice): 502 +
// upstream_error. Per-file I/O errors do NOT propagate — they
// surface as Skipped entries on the response (D-23).
func StateIndex(dataDir string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		entries, skipped, err := state.Index(dataDir)
		if err != nil {
			slog.Warn("bridge_state_index_failed",
				"data_dir", dataDir,
				"request_id", chimiddleware.GetReqID(r.Context()),
				"err", err.Error(),
			)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadGateway)
			_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
				ErrorCode: "upstream_error",
			})
			return
		}

		// Convert internal state.FileEntry -> contract.StateFileEntry
		// so the wire shape is governed by the contract package.
		files := make([]contract.StateFileEntry, len(entries))
		for i, e := range entries {
			files[i] = contract.StateFileEntry{
				Name:      e.Name,
				SizeBytes: e.SizeBytes,
				SHA256:    e.SHA256,
			}
		}

		slog.Info("bridge_state_index_served",
			"data_dir", dataDir,
			"files_count", len(files),
			"skipped_count", len(skipped),
			"request_id", chimiddleware.GetReqID(r.Context()),
		)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(contract.StateIndexResponse{
			Files:   files,
			Skipped: skippedNames(skipped),
		})
	}
}

// skippedNames flattens []SkippedEntry to []string so the
// response shape stays compact. We deliberately expose only
// the basename + the error string formatted by the State package.
func skippedNames(s []state.SkippedEntry) []string {
	if len(s) == 0 {
		return nil
	}
	out := make([]string, 0, len(s))
	for _, e := range s {
		out = append(out, e.Name+": "+e.Err)
	}
	return out
}
