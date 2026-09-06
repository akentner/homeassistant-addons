// Package statebackend abstracts the three state-storage backends
// the runner supports (Cloudflare R2, any S3-compatible service, and
// a local file). The Backend interface is the contract Phase 17's
// /v1/plan and /v1/apply handlers consume: they read
// backend.Endpoint() + backend.Bucket() + backend.Region() +
// backend.UseLockfile() to construct the `tofu init` /
// `tofu plan` / `tofu apply` command lines. Phase 19's E2E test
// asserts each backend's tofu invocation empirically.
//
// The package is independent of /internal/auth/ and /internal/keys/ —
// keys imports statebackend (to read CredentialFiles()) but
// statebackend has no inbound dependency on either. This is the
// layering that lets the validator be unit-tested with a fakeBackend
// without dragging the bearer-auth or signal-handling code along.
package statebackend

import "errors"

// Backend is the abstraction the runner uses to construct per-run
// `tofu` command lines. Implementations are r2Backend, s3Backend,
// and localBackend; the factory function New returns the concrete
// instance based on the configured backend name. The interface is
// deliberately small — exactly the methods Phase 17 needs.
type Backend interface {
	// Endpoint returns the S3-compatible URL the `tofu` S3 backend
	// is configured against. For r2 this is
	// "https://<account_id>.r2.cloudflarestorage.com"; for s3 it
	// is the user-supplied s3_endpoint; for local it is empty (no
	// HTTP endpoint — state lives on disk).
	Endpoint() string
	// Bucket returns the storage bucket name. For r2/s3 this is the
	// bucket name in the bucket; for local this is the absolute
	// path to the state file (/data/terraform.tfstate).
	Bucket() string
	// Region returns the AWS region for s3 (empty for local). For
	// r2 the value is the literal "auto" — R2 ignores region
	// semantics but the S3 backend still requires a non-empty
	// region key.
	Region() string
	// UseLockfile reports whether OpenTofu should be invoked with
	// `use_lockfile = true`. r2 and s3 return true (native
	// S3-object locking, no DynamoDB required); local returns
	// false (file-based lock via /data/terraform.tfstate.lock).
	UseLockfile() bool
	// CredentialFiles lists the credential filenames under
	// /data/keys/ that this backend requires. The local backend
	// returns nil (no credentials); the keys validator uses this
	// list to assert each required file exists with chmod 600.
	CredentialFiles() []string
	// Name returns the canonical backend identifier
	// ("r2" | "s3" | "local") used in log records + the factory
	// round-trip.
	Name() string
}

// Options carries the per-backend values the factory needs to
// construct a Backend. Fields are populated from /data/options.json
// in main.go; unset fields produce a Backend that surfaces the
// underlying problem (e.g. empty R2Bucket → tofu init complains
// about a missing bucket name).
type Options struct {
	// R2Bucket is the Cloudflare R2 bucket name. Used by the r2
	// backend; ignored by s3 / local.
	R2Bucket string
	// S3Endpoint is the user-supplied S3-compatible endpoint URL.
	// Used by the s3 backend; ignored by r2 / local.
	S3Endpoint string
	// S3Bucket is the S3-compatible bucket name. Used by the s3
	// backend; ignored by r2 / local.
	S3Bucket string
	// S3Region is the AWS-style region string. Used by the s3
	// backend; ignored by r2 / local. (R2 hard-codes "auto".)
	S3Region string
	// DataDir is the add-on's persistent data directory (typically
	// "/data"). The R2 backend reads /data/keys/r2-account-id from
	// here at construction time.
	DataDir string
}

// ErrUnsupported is the sentinel returned by New when the backend
// name does not match "r2" | "s3" | "local". Wrapped with the
// offending name via fmt.Errorf("%w: %q", …) so callers can use
// errors.Is(err, ErrUnsupported) without parsing strings.
var ErrUnsupported = errors.New("statebackend: unsupported backend")