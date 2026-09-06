package keys

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"iac-runner/internal/statebackend"
)

// fakeBackend implements statebackend.Backend with a configurable
// CredentialFiles list. Tests construct one with the file names they
// want the validator to require.
type fakeBackend struct {
	creds []string
}

func (f *fakeBackend) Endpoint() string            { return "" }
func (f *fakeBackend) Bucket() string               { return "" }
func (f *fakeBackend) Region() string               { return "" }
func (f *fakeBackend) UseLockfile() bool            { return false }
func (f *fakeBackend) CredentialFiles() []string    { return f.creds }
func (f *fakeBackend) Name() string                 { return "fake" }

// writeKey creates a file at path with the given mode bytes and
// content. Tests pass 0o600 for the happy path, 0o644 for the
// "wrong mode" failure mode. Errors are surfaced via t.Fatal so
// setup failures don't silently produce a "passing" assertion.
func writeKey(t *testing.T, path string, mode os.FileMode, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), mode); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}

// TestValidateKeysDirAllChmod600: every required file exists with
// 0600 + UID ownership → Validate returns nil.
func TestValidateKeysDirAllChmod600(t *testing.T) {
	dir := t.TempDir()
	keysDir := filepath.Join(dir, "keys")
	if err := os.MkdirAll(keysDir, 0o700); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	for _, name := range []string{"r2-access.key", "r2-secret.key", "r2-account-id"} {
		writeKey(t, filepath.Join(keysDir, name), 0o600, "AKIA-CONTENT")
	}
	v := NewValidator(keysDir, &fakeBackend{creds: []string{"r2-access.key", "r2-secret.key", "r2-account-id"}})
	if err := v.Validate(); err != nil {
		t.Errorf("Validate() = %v, want nil", err)
	}
}

// TestValidateKeysDirMissingRequired: one required file is absent →
// ErrKeysMissing wrapped with the missing filename.
func TestValidateKeysDirMissingRequired(t *testing.T) {
	dir := t.TempDir()
	keysDir := filepath.Join(dir, "keys")
	if err := os.MkdirAll(keysDir, 0o700); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	writeKey(t, filepath.Join(keysDir, "r2-access.key"), 0o600, "AKIA")
	// r2-secret.key + r2-account-id missing on purpose.
	v := NewValidator(keysDir, &fakeBackend{creds: []string{"r2-access.key", "r2-secret.key", "r2-account-id"}})
	err := v.Validate()
	if err == nil {
		t.Fatal("Validate() = nil, want error")
	}
	if !errors.Is(err, ErrKeysMissing) {
		t.Errorf("err chain missing ErrKeysMissing sentinel: %v", err)
	}
	if !strings.Contains(err.Error(), "r2-secret.key") {
		t.Errorf("error must name the missing file 'r2-secret.key': %v", err)
	}
}

// TestValidateKeysDirWrongMode: one file has mode 0644 →
// ErrKeysNotChmod600 wrapped with the filename + the offending mode.
func TestValidateKeysDirWrongMode(t *testing.T) {
	dir := t.TempDir()
	keysDir := filepath.Join(dir, "keys")
	if err := os.MkdirAll(keysDir, 0o700); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	writeKey(t, filepath.Join(keysDir, "r2-access.key"), 0o644, "AKIA")
	writeKey(t, filepath.Join(keysDir, "r2-secret.key"), 0o600, "secret-content")
	v := NewValidator(keysDir, &fakeBackend{creds: []string{"r2-access.key", "r2-secret.key"}})
	err := v.Validate()
	if err == nil {
		t.Fatal("Validate() = nil, want error")
	}
	if !errors.Is(err, ErrKeysNotChmod600) {
		t.Errorf("err chain missing ErrKeysNotChmod600 sentinel: %v", err)
	}
	if !strings.Contains(err.Error(), "r2-access.key") {
		t.Errorf("error must name the wrong-mode file 'r2-access.key': %v", err)
	}
	if !strings.Contains(err.Error(), "644") {
		t.Errorf("error must report the offending mode '644' (0644 octal): %v", err)
	}
}

// TestValidateKeysDirLocalNoRequired: local backend has no required
// files. An empty /data/keys dir is acceptable (no err). An absent
// /data/keys is acceptable (the validator returns nil because the
// local backend has no credential dependencies).
func TestValidateKeysDirLocalNoRequired(t *testing.T) {
	// local-backend case 1: empty keysDir.
	dir := t.TempDir()
	keysDir := filepath.Join(dir, "keys")
	if err := os.MkdirAll(keysDir, 0o700); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	v := NewValidator(keysDir, &fakeBackend{creds: nil})
	if err := v.Validate(); err != nil {
		t.Errorf("Validate() empty dir = %v, want nil", err)
	}
	// local-backend case 2: keysDir absent entirely.
	v2 := NewValidator(filepath.Join(dir, "nonexistent"), &fakeBackend{creds: nil})
	if err := v2.Validate(); err != nil {
		t.Errorf("Validate() absent dir = %v, want nil", err)
	}
}

// TestValidateKeysDirExtraFilesChecked: even files NOT in the
// required list are mode-checked. The validator doesn't trust the
// "required" list as a deny-list of valid files — if a stray
// 0644 file is present, the validator rejects it.
func TestValidateKeysDirExtraFilesChecked(t *testing.T) {
	dir := t.TempDir()
	keysDir := filepath.Join(dir, "keys")
	if err := os.MkdirAll(keysDir, 0o700); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	writeKey(t, filepath.Join(keysDir, "r2-access.key"), 0o600, "AKIA")
	writeKey(t, filepath.Join(keysDir, "r2-secret.key"), 0o600, "secret")
	// Extra file with wrong mode — the validator must catch it
	// even though it isn't in the required list.
	writeKey(t, filepath.Join(keysDir, "scratchpad.txt"), 0o644, "leaky")
	v := NewValidator(keysDir, &fakeBackend{creds: []string{"r2-access.key", "r2-secret.key"}})
	err := v.Validate()
	if err == nil {
		t.Fatal("Validate() = nil, want error for extra 0644 file")
	}
	if !errors.Is(err, ErrKeysNotChmod600) {
		t.Errorf("err chain missing ErrKeysNotChmod600 sentinel: %v", err)
	}
	if !strings.Contains(err.Error(), "scratchpad.txt") {
		t.Errorf("error must name the extra file 'scratchpad.txt': %v", err)
	}
}

// TestValidateKeysDirKeysDirIsFile: /data/keys exists but is a
// regular file, not a directory → clear error naming the path.
func TestValidateKeysDirKeysDirIsFile(t *testing.T) {
	dir := t.TempDir()
	keysDir := filepath.Join(dir, "keys")
	if err := os.WriteFile(keysDir, []byte("not a dir"), 0o600); err != nil {
		t.Fatalf("writefile: %v", err)
	}
	v := NewValidator(keysDir, &fakeBackend{creds: nil})
	err := v.Validate()
	if err == nil {
		t.Fatal("Validate() = nil, want error for non-directory keysDir")
	}
	if !strings.Contains(err.Error(), "is not a directory") {
		t.Errorf("error should explain non-directory: %v", err)
	}
}

// TestNewValidatorRequiredFilesCopy: RequiredFiles returns a
// defensive copy — mutating the returned slice does NOT affect
// subsequent Validate calls.
func TestNewValidatorRequiredFilesCopy(t *testing.T) {
	backend := &fakeBackend{creds: []string{"r2-access.key", "r2-secret.key"}}
	v := NewValidator("/data/keys", backend)
	files := v.RequiredFiles()
	files[0] = "MUTATED"
	if v.RequiredFiles()[0] != "r2-access.key" {
		t.Errorf("RequiredFiles() returned a non-defensive copy: %v", v.RequiredFiles())
	}
}

// Compile-time check that the validator's statebackend parameter is
// the real interface (not a one-off duck-typed shape).
var _ statebackend.Backend = (*fakeBackend)(nil)
