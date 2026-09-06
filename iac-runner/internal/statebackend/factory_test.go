package statebackend

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestFactoryNewR2: backend="r2" + DataDir containing
// /data/keys/r2-account-id → R2 implementation with the right
// endpoint, bucket, region, credential files.
func TestFactoryNewR2(t *testing.T) {
	dir := t.TempDir()
	keysDir := filepath.Join(dir, "keys")
	if err := os.MkdirAll(keysDir, 0o700); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(keysDir, "r2-account-id"), []byte("a1b2c3d4e5f6"), 0o600); err != nil {
		t.Fatalf("write: %v", err)
	}

	be, err := New("r2", Options{R2Bucket: "homelab-tfstate", DataDir: dir})
	if err != nil {
		t.Fatalf("New(r2) = %v, want nil err", err)
	}
	if be.Name() != "r2" {
		t.Errorf("Name() = %q, want %q", be.Name(), "r2")
	}
	if want := "https://a1b2c3d4e5f6.r2.cloudflarestorage.com"; be.Endpoint() != want {
		t.Errorf("Endpoint() = %q, want %q", be.Endpoint(), want)
	}
	if be.Bucket() != "homelab-tfstate" {
		t.Errorf("Bucket() = %q, want %q", be.Bucket(), "homelab-tfstate")
	}
	if be.Region() != "auto" {
		t.Errorf("Region() = %q, want %q", be.Region(), "auto")
	}
	if !be.UseLockfile() {
		t.Errorf("UseLockfile() = false, want true (R2 supports S3-object lock)")
	}
	creds := be.CredentialFiles()
	want := map[string]bool{"r2-access.key": false, "r2-secret.key": false, "r2-account-id": false}
	for _, c := range creds {
		if _, ok := want[c]; ok {
			want[c] = true
		}
	}
	for name, seen := range want {
		if !seen {
			t.Errorf("CredentialFiles() missing %q (got %v)", name, creds)
		}
	}
}

// TestFactoryNewR2MissingAccountID: backend="r2" but the
// r2-account-id file is absent → New returns a wrapped error
// mentioning "r2-account-id".
func TestFactoryNewR2MissingAccountID(t *testing.T) {
	dir := t.TempDir()
	_, err := New("r2", Options{R2Bucket: "homelab-tfstate", DataDir: dir})
	if err == nil {
		t.Fatal("New(r2) = nil err, want error for missing r2-account-id")
	}
	if !strings.Contains(err.Error(), "r2-account-id") {
		t.Errorf("err must name r2-account-id: %v", err)
	}
}

// TestFactoryNewS3: backend="s3" with user-supplied endpoint +
// bucket + region → S3 implementation with the right values; locks
// via use_lockfile=true.
func TestFactoryNewS3(t *testing.T) {
	be, err := New("s3", Options{
		S3Endpoint: "https://minio.example.com:9000",
		S3Bucket:   "homelab-state",
		S3Region:   "us-east-1",
		DataDir:    t.TempDir(),
	})
	if err != nil {
		t.Fatalf("New(s3) = %v, want nil err", err)
	}
	if be.Name() != "s3" {
		t.Errorf("Name() = %q, want %q", be.Name(), "s3")
	}
	if be.Endpoint() != "https://minio.example.com:9000" {
		t.Errorf("Endpoint() = %q, want user-supplied", be.Endpoint())
	}
	if be.Bucket() != "homelab-state" {
		t.Errorf("Bucket() = %q, want %q", be.Bucket(), "homelab-state")
	}
	if be.Region() != "us-east-1" {
		t.Errorf("Region() = %q, want %q", be.Region(), "us-east-1")
	}
	if !be.UseLockfile() {
		t.Errorf("UseLockfile() = false, want true (S3-object lock)")
	}
	creds := be.CredentialFiles()
	if len(creds) != 2 || creds[0] != "s3-access.key" || creds[1] != "s3-secret.key" {
		t.Errorf("CredentialFiles() = %v, want [s3-access.key s3-secret.key]", creds)
	}
}

// TestFactoryNewLocal: backend="local" → Local implementation. No
// credentials required; state lives at /data/terraform.tfstate;
// locking is file-based (UseLockfile=false).
func TestFactoryNewLocal(t *testing.T) {
	be, err := New("local", Options{})
	if err != nil {
		t.Fatalf("New(local) = %v, want nil err", err)
	}
	if be.Name() != "local" {
		t.Errorf("Name() = %q, want %q", be.Name(), "local")
	}
	if be.Endpoint() != "" {
		t.Errorf("Endpoint() = %q, want empty for local", be.Endpoint())
	}
	if be.Bucket() != "/data/terraform.tfstate" {
		t.Errorf("Bucket() = %q, want /data/terraform.tfstate", be.Bucket())
	}
	if be.Region() != "" {
		t.Errorf("Region() = %q, want empty for local", be.Region())
	}
	if be.UseLockfile() {
		t.Errorf("UseLockfile() = true, want false (local = file-based lock)")
	}
	if creds := be.CredentialFiles(); creds != nil {
		t.Errorf("CredentialFiles() = %v, want nil for local", creds)
	}
}

// TestFactoryInvalid: backend="minio" (or anything not in the
// supported set) → ErrUnsupported wrapped with the offending name.
// errors.Is works because we use fmt.Errorf("%w: %q", …).
func TestFactoryInvalid(t *testing.T) {
	_, err := New("minio", Options{})
	if err == nil {
		t.Fatal("New(minio) = nil err, want ErrUnsupported")
	}
	if !errors.Is(err, ErrUnsupported) {
		t.Errorf("err chain missing ErrUnsupported sentinel: %v", err)
	}
	if !strings.Contains(err.Error(), `"minio"`) {
		t.Errorf("err must quote the offending backend name: %v", err)
	}
	// Empty string is also unsupported (defensive — main.go
	// substitutes the default before calling New, but we don't
	// want to be permissive if a future caller forgets).
	if _, err := New("", Options{}); !errors.Is(err, ErrUnsupported) {
		t.Errorf("New(\"\") should also return ErrUnsupported, got %v", err)
	}
}