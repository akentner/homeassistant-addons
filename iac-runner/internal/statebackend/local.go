package statebackend

// localBackend implements Backend for the on-disk state file at
// /data/terraform.tfstate. There are no credentials — the
// OpenTofu `local` backend reads + writes the state file directly,
// and the runner is the only process that touches it. Locking is
// file-based via /data/terraform.tfstate.lock (STBK-05).
type localBackend struct{}

// newLocalBackend returns a localBackend. Options are accepted for
// signature parity with newR2Backend / newS3Backend but are ignored —
// the local backend's bucket path is hard-coded.
func newLocalBackend(_ Options) (Backend, error) {
	return &localBackend{}, nil
}

// Endpoint returns the empty string. The local backend has no
// HTTP endpoint; Phase 17's `tofu init -backend-config=…` invocation
// skips the endpoint entirely.
func (l *localBackend) Endpoint() string { return "" }

// Bucket returns the absolute path of the state file. Phase 17
// passes this as the `path` argument to `tofu init -backend-config`.
func (l *localBackend) Bucket() string { return "/data/terraform.tfstate" }

// Region returns the empty string. The local backend ignores
// region semantics.
func (l *localBackend) Region() string { return "" }

// UseLockfile returns false: the local backend uses
// `/data/terraform.tfstate.lock` (file-based locking via OpenTofu's
// default local-backend behavior). This is a DIFFERENT mechanism
// than `use_lockfile = true` (which is S3-object-lock semantics);
// mixing them up would either disable locking or produce an
// unrecognized-backend-config error.
func (l *localBackend) UseLockfile() bool { return false }

// CredentialFiles returns nil — the local backend has no
// credential dependencies. The keys validator (SEC-01) skips the
// required-files loop when this list is empty, and skips the
// directory walk entirely when /data/keys does not exist.
func (l *localBackend) CredentialFiles() []string { return nil }

func (l *localBackend) Name() string { return "local" }
