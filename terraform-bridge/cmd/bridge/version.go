package main

// bridgeVersion is overwritten at build time via:
//   -ldflags "-X main.bridgeVersion=${BRIDGE_VERSION}"
//
// Dockerfile (multi-stage) sets BRIDGE_VERSION from build.yaml's VERSION
// argument. When the binary is built locally via `go build ./...` outside of
// Docker, the variable keeps its default value "dev" so the placeholder JSON
// clearly distinguishes local-dev runs from tagged releases.
var bridgeVersion = "dev"