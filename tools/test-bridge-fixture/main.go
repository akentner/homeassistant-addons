// Command test-bridge-fixture is a CI-only minimal HTTP server that mimics
// the Bridge's GET /v1/version endpoint for the OpenTofu Provider's
// schema-version handshake. It is NOT shipped in any production binary.
//
// Usage:
//
//	go run ./tools/test-bridge-fixture --port 18224 --repo-root ..
//
// The fixture reads terraform-bridge/build.yaml for the VERSION and serves
// it on every GET /v1/version. Any other path returns 404.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

func main() {
	port := flag.Int("port", 18224, "port to listen on (127.0.0.1 only)")
	repoRoot := flag.String("repo-root", "..", "path to the repo root containing terraform-bridge/build.yaml")
	flag.Parse()

	version, err := readVersion(filepath.Join(*repoRoot, "terraform-bridge", "build.yaml"))
	if err != nil {
		log.Fatalf("test-bridge-fixture: %v", err)
	}

	addr := fmt.Sprintf("127.0.0.1:%d", *port)
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/version", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_ = json.NewEncoder(w).Encode(map[string]string{
			"bridge_version": version,
		})
	})
	mux.HandleFunc("/", func(w http.ResponseWriter, _ *http.Request) {
		http.NotFound(w, nil)
	})

	log.Printf("test-bridge-fixture: listening on %s, version=%s", addr, version)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatalf("test-bridge-fixture: %v", err)
	}
}

func readVersion(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("read %s: %w", path, err)
	}
	for _, line := range strings.Split(string(data), "\n") {
		const prefix = "VERSION: "
		if strings.HasPrefix(strings.TrimLeft(line, " \t"), prefix) {
			return strings.Trim(strings.TrimPrefix(strings.TrimLeft(line, " \t"), prefix), `"`), nil
		}
	}
	return "", fmt.Errorf("no VERSION in %s", path)
}