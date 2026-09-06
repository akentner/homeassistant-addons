package statebackend

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// r2Backend implements Backend for Cloudflare R2. The endpoint is
// constructed from /data/keys/r2-account-id (plaintext, non-sensitive)
// and the bucket name comes from Options.R2Bucket. Credentials are
// loaded by `tofu` from /data/keys/r2-access.key + r2-secret.key;
// this struct does not read them — the S3 backend respects the
// standard AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY env vars and
// the OpenTofu S3 backend reads them out of the standard paths.
type r2Backend struct {
	accountID string
	bucket    string
}

// newR2Backend reads the Cloudflare account ID from
// <DataDir>/keys/r2-account-id and constructs an r2Backend. Returns
// a wrapped error if the file is missing or unreadable — main.go
// treats this as a startup failure (SEC-01 fail-fast).
func newR2Backend(opts Options) (Backend, error) {
	idPath := filepath.Join(opts.DataDir, "keys", "r2-account-id")
	idBytes, err := os.ReadFile(idPath)
	if err != nil {
		return nil, fmt.Errorf("statebackend: r2-account-id: %w", err)
	}
	accountID := strings.TrimSpace(string(idBytes))
	if accountID == "" {
		return nil, fmt.Errorf("statebackend: r2-account-id: %s is empty", idPath)
	}
	return &r2Backend{accountID: accountID, bucket: opts.R2Bucket}, nil
}

// Endpoint constructs the R2 S3-compatible endpoint URL. R2 ignores
// region semantics but the OpenTofu S3 backend requires the URL form
// `<account>.r2.cloudflarestorage.com`; we surface it verbatim.
func (r *r2Backend) Endpoint() string {
	return "https://" + r.accountID + ".r2.cloudflarestorage.com"
}

func (r *r2Backend) Bucket() string { return r.bucket }

// Region returns the literal "auto" — R2 does not have AWS-style
// regions but the OpenTofu S3 backend rejects an empty region. The
// value is what R2 documents for the AWS_REGION env var when using
// the S3-compatible API.
func (r *r2Backend) Region() string { return "auto" }

// UseLockfile returns true: R2 supports the S3-object-lock-based
// locking that the OpenTofu S3 backend exposes via
// `use_lockfile = true`. No DynamoDB required (STBK-05).
func (r *r2Backend) UseLockfile() bool { return true }

// CredentialFiles lists the files the keys validator must assert
// are present + chmod 600 under /data/keys/. The validator
// (SEC-01) iterates this list. r2-account-id is plaintext (the
// account ID is not a secret) but its inclusion in the list
// ensures its chmod 600 + UID ownership is also enforced.
func (r *r2Backend) CredentialFiles() []string {
	return []string{"r2-access.key", "r2-secret.key", "r2-account-id"}
}

func (r *r2Backend) Name() string { return "r2" }
