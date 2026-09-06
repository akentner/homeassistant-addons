package statebackend

// s3Backend implements Backend for any S3-compatible storage service
// (AWS S3, MinIO, Backblaze B2, Wasabi, etc.). The endpoint,
// bucket, and region are all operator-supplied via /data/options.json.
// Credentials are loaded from /data/keys/s3-access.key +
// /data/keys/s3-secret.key via the standard AWS_ACCESS_KEY_ID +
// AWS_SECRET_ACCESS_KEY env vars that the OpenTofu S3 backend reads.
type s3Backend struct {
	endpoint string
	bucket   string
	region   string
}

// newS3Backend returns an s3Backend populated from Options. No file
// I/O at construction time — the keys validator (SEC-01) enforces
// the file presence + chmod 600 invariants at startup.
func newS3Backend(opts Options) (Backend, error) {
	return &s3Backend{
		endpoint: opts.S3Endpoint,
		bucket:   opts.S3Bucket,
		region:   opts.S3Region,
	}, nil
}

// Endpoint returns the user-supplied s3_endpoint URL verbatim. The
// caller (Phase 17) passes it through to OpenTofu unchanged.
func (s *s3Backend) Endpoint() string { return s.endpoint }

func (s *s3Backend) Bucket() string { return s.bucket }

func (s *s3Backend) Region() string { return s.region }

// UseLockfile returns true for s3: AWS S3 + all S3-compatible
// services the runner supports natively implement the S3 object-lock
// semantics that the OpenTofu `use_lockfile = true` flag relies on
// (per the IRUN-H-1 spike — Phase 16 R2 lockfile behavior
// verified empirically).
func (s *s3Backend) UseLockfile() bool { return true }

// CredentialFiles lists the S3 credential files the keys validator
// must assert are present + chmod 600 under /data/keys/. There is
// no s3-account-id equivalent — the s3_endpoint URL itself is the
// routing key for non-AWS services.
func (s *s3Backend) CredentialFiles() []string {
	return []string{"s3-access.key", "s3-secret.key"}
}

func (s *s3Backend) Name() string { return "s3" }
