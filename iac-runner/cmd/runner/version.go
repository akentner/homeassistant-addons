package main

// runnerVersion is overwritten at build time via:
//   -ldflags "-X main.runnerVersion=${RUNNER_VERSION}"
//
// Dockerfile (multi-stage) sets RUNNER_VERSION from build.yaml's VERSION
// argument. When the binary is built locally via `go build ./...` outside
// of Docker, the variable keeps its default value "dev" so the placeholder
// JSON clearly distinguishes local-dev runs from tagged releases.
var runnerVersion = "dev"
