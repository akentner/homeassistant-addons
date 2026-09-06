// Package keys validates the credentials directory mounted at
// /data/keys/ — the SEC-01 invariant. Every credential file
// (state-backend access keys, SSH deploy keys) MUST be chmod 600 and
// owned by the current process UID; non-conforming files cause
// startup failure with a clear error message naming the offending
// file. There is no degraded mode (no 0644 fallback, no auto-chmod,
// no "best effort"). Operator correction is required.
//
// The validator is independent of /internal/auth/ — keys knows about
// statebackend.Backend.CredentialFiles() but not about the token
// store or the bearer-auth flow. This is intentional: keys is the
// only thing standing between the runner and an over-permissive
// credential file that would let any local user read the AWS access
// key, so its dependency surface stays minimal.
package keys

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"

	"iac-runner/internal/statebackend"
)

// ErrKeysNotChmod600 indicates a credential file's permission bits
// are not exactly 0600. Wrapped with the filename + the offending
// mode so the operator knows which file to chmod.
var ErrKeysNotChmod600 = errors.New("keys: file is not chmod 600")

// ErrKeysMissing indicates a credential file required by the
// configured state backend is absent. Wrapped with the missing path.
var ErrKeysMissing = errors.New("keys: required file is missing")

// Validator walks keysDir, asserts every existing file is chmod 600
// + owned by the current process UID, and asserts every required
// file (from backend.CredentialFiles()) exists. The validator is
// constructed once at startup and reused for the /healthz per-request
// probe; the directory walk is cheap (a handful of files), so no
// caching is needed.
type Validator struct {
	keysDir  string
	required []string
}

// NewValidator returns a Validator bound to keysDir (typically
// "/data/keys") and the credential file names reported by backend.
// Required files are derived from backend.CredentialFiles(); for the
// local backend this list is empty (no credentials), so Validate
// only checks the keysDir itself (if present) and skips the file
// iteration when the directory is empty or absent.
func NewValidator(keysDir string, backend statebackend.Backend) *Validator {
	return &Validator{
		keysDir:  keysDir,
		required: backend.CredentialFiles(),
	}
}

// Validate walks keysDir and returns the first failure encountered.
// Order: (1) stat the keysDir itself — for the local backend an
// absent /data/keys is acceptable; for r2/s3 an absent /data/keys is
// fatal; (2) for every required file (from backend.CredentialFiles())
// assert it exists; (3) for every file in keysDir (regardless of
// whether it is in the required list — extra files are also
// validated) assert perm == 0600 and UID == os.Getuid().
//
// Returns nil when every check passes.
func (v *Validator) Validate() error {
	info, err := os.Stat(v.keysDir)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) && len(v.required) == 0 {
			// local backend: missing /data/keys is fine.
			return nil
		}
		return fmt.Errorf("keys: stat %s: %w", v.keysDir, err)
	}
	if !info.IsDir() {
		return fmt.Errorf("keys: %s is not a directory", v.keysDir)
	}
	// Required files must exist (r2/s3 backends).
	for _, name := range v.required {
		path := filepath.Join(v.keysDir, name)
		if _, err := os.Stat(path); err != nil {
			if errors.Is(err, os.ErrNotExist) {
				return fmt.Errorf("%w: %s", ErrKeysMissing, path)
			}
			return fmt.Errorf("keys: stat %s: %w", path, err)
		}
	}
	// Every existing file is mode-checked + ownership-checked.
	entries, err := os.ReadDir(v.keysDir)
	if err != nil {
		return fmt.Errorf("keys: readdir %s: %w", v.keysDir, err)
	}
	uid := os.Getuid()
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		path := filepath.Join(v.keysDir, e.Name())
		finfo, err := e.Info()
		if err != nil {
			return fmt.Errorf("keys: stat %s: %w", path, err)
		}
		perm := finfo.Mode().Perm()
		if perm != 0o600 {
			return fmt.Errorf("%w: %s mode is %o, want 0600", ErrKeysNotChmod600, path, perm)
		}
		if sys := finfo.Sys(); sys != nil {
			if uidInfo, ok := sys.(interface{ UID() int }); ok {
				if uidInfo.UID() != uid {
					return fmt.Errorf("%w: %s owned by UID %d, want %d", ErrKeysNotChmod600, path, uidInfo.UID(), uid)
				}
			}
		}
	}
	return nil
}

// RequiredFiles returns a defensive copy of the required-file list.
// Tests use this to assert the validator was constructed with the
// expected set; production code does not need it.
func (v *Validator) RequiredFiles() []string {
	return append([]string(nil), v.required...)
}

// KeysDir returns the directory the validator was constructed with.
// Exposed for tests + the bootstrap log line in main.go.
func (v *Validator) KeysDir() string {
	return v.keysDir
}