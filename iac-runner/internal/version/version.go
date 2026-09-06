// Package version holds compile-time semver constants for the
// iac-runner HTTP API. The constants are referenced by the runner
// binary (via /v1/version — added in Plan 03) and by future plans
// that gate OpenTofu version compatibility.
//
// Bump policy:
//   - SchemaVersion: Bump MAJOR on every breaking change to the
//     /v1/* HTTP API surface (new required field, removed field,
//     renamed field, changed error_code values). MINOR and PATCH
//     bumps are additive (backwards-compatible).
//   - MinSupportedOpenTofu: Bump when the runner adds a feature
//     that requires OpenTofu newer than the floor. Phase 1 keeps
//     it at "1.6.0" (the oldest OpenTofu the runner can drive).
//   - MaxSupportedOpenTofu: Bump when the runner deprecates a
//     feature that no OpenTofu newer than the ceiling can rely on.
//     Phase 1 keeps it at "1.999.0" (no upper bound yet).
package version

const (
	SchemaVersion = "1.0.0"

	// MinSupportedOpenTofu is the lowest OpenTofu version the runner
	// can drive. OpenTofu 1.6.0 was the first stable release; older
	// versions are out of scope.
	MinSupportedOpenTofu = "1.6.0"

	// MaxSupportedOpenTofu is the highest OpenTofu version the runner
	// accepts. Phase 1 has no upper bound.
	MaxSupportedOpenTofu = "1.999.0"
)
