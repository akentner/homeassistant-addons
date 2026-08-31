// Package supervisor provides primitives for talking to the Home Assistant
// Supervisor from inside an add-on container.
//
// Phase 9 ships only the env-reader (ReadSupervisorToken) so AUTH-01's
// "auto-injected by Supervisor when hassio_api: true" invariant is observable
// in the source tree. Phase 10 wraps the token in a Supervisor HTTP client
// struct that re-reads the env on every outbound call (cheap; per
// PITFALLS.md §H-1, the token MAY rotate across Supervisor restarts).
package supervisor

import "os"

// ReadSupervisorToken returns the Supervisor-issued token from the process
// environment. Supervisor auto-injects it for every add-on declaring
// hassio_api: true in config.yaml (developers.home-assistant.io/docs/add-ons/
// communication).
//
// The value is intentionally NEVER logged, NEVER serialised, and NEVER echoed
// in any error message. AUTH-01 forbids it. If you find yourself wanting to
// fmt.Sprintf("%s", token), STOP — read PITFALLS S-1 first.
func ReadSupervisorToken() string {
	return os.Getenv("SUPERVISOR_TOKEN")
}