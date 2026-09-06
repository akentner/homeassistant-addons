package statebackend

import "fmt"

// New returns the Backend implementation that matches backend. The
// supported values are exactly "r2", "s3", and "local" — same set
// that the HA Supervisor options schema accepts in /data/options.json
// (STBK-01). Any other value returns ErrUnsupported wrapped with the
// offending name so the operator can grep the log line and find the
// typo.
//
// Options carries the per-backend values (R2Bucket for r2; S3Endpoint
// + S3Bucket + S3Region for s3; DataDir for r2's account-id read).
// The factory is a thin dispatcher — each backend's constructor does
// its own validation (e.g. r2 reads the account-id file).
func New(backend string, opts Options) (Backend, error) {
	switch backend {
	case "r2":
		return newR2Backend(opts)
	case "s3":
		return newS3Backend(opts)
	case "local":
		return newLocalBackend(opts)
	default:
		return nil, fmt.Errorf("%w: %q", ErrUnsupported, backend)
	}
}
