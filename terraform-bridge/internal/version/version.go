// Package version holds compile-time semver constants for the
// terraform-bridge HTTP API. The constants here are referenced by both
// the Bridge binary (via /v1/version) and (in a later Phase 13) the
// terraform-provider-homeassistant module (via the existing
// `replace terraform-bridge => ../terraform-bridge` directive in the
// Provider go.mod), so they live in a sub-package rather than in
// cmd/bridge or contract.
//
// Bump policy:
//   - SchemaVersion: Bump the MAJOR segment (1.0.0 -> 2.0.0) on every
//     breaking change to the /v1/* Bridge API surface (new required
//     field, removed field, renamed field, changed error_code values).
//     MINOR and PATCH bumps are informational and signal additive
//     (backwards-compatible) changes - the Providers
//     min_provider_version..max_provider_version window still accepts
//     them.
//   - MinProviderVersion: Bump when the Bridge adds a feature that
//     requires a Provider newer than the floor. Phase 1 keeps it at
//     "0.0.0" because the floor is "any Provider that knows the
//     schema_version field".
//   - MaxProviderVersion: Bump when the Bridge deprecates a feature
//     that no Provider newer than the ceiling can rely on. Phase 1
//     keeps it at "1.999.0" because no Phase 1+ Provider is newer
//     than the v1 schema.
//
// The three constants are intentionally separate (rather than a
// single semver struct) so callers can compare against just the
// schema_version field without parsing semver themselves.
package version

const (
	// SchemaVersion is the semver string that increments on every
	// breaking change to the Bridge HTTP API surface. The Provider's
	// PROV-03 Configure handshake checks this against its own
	// [min_provider_version, max_provider_version] window.
	SchemaVersion = "1.0.0"

	// MinProviderVersion is the lowest Provider version that the
	// current Bridge accepts. Providers with min_provider_version
	// below this value cannot operate against this Bridge.
	MinProviderVersion = "0.0.0"

	// MaxProviderVersion is the highest Provider version that the
	// current Bridge accepts. Providers newer than this value cannot
	// operate against this Bridge (the Bridge predates features the
	// Provider requires).
	MaxProviderVersion = "1.999.0"
)
