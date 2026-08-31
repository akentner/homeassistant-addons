package auth

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestTokenStoreGeneratePersistLoadValidate(t *testing.T) {
	dir := t.TempDir()
	store, err := NewFileTokenStore(dir)
	if err != nil {
		t.Fatalf("NewFileTokenStore: %v", err)
	}

	token, err := store.Generate()
	if err != nil {
		t.Fatalf("Generate: %v", err)
	}
	if len(token) != 43 {
		t.Errorf("token length = %d, want 43", len(token))
	}
	if strings.ContainsAny(token, "+/=") {
		t.Errorf("token contains non-base64url chars: %q", token)
	}

	if err := store.Persist(token); err != nil {
		t.Fatalf("Persist: %v", err)
	}

	// File exists with correct mode bits.
	info, err := os.Stat(filepath.Join(dir, "bridge-token"))
	if err != nil {
		t.Fatalf("stat token file: %v", err)
	}
	if perm := info.Mode().Perm(); perm != 0o600 {
		t.Errorf("token file mode = %o, want 0600", perm)
	}

	// Reload from disk and re-validate — proves persistence works.
	reloaded, err := NewFileTokenStore(dir)
	if err != nil {
		t.Fatalf("reloaded NewFileTokenStore: %v", err)
	}
	if err := reloaded.Validate(token); err != nil {
		t.Errorf("Validate after reload: %v", err)
	}
}

func TestTokenStoreValidateRejectsWrongToken(t *testing.T) {
	dir := t.TempDir()
	store, _ := NewFileTokenStore(dir)
	token, _ := store.Generate()
	_ = store.Persist(token)

	wrong, _ := store.Generate() // different plaintext
	if err := store.Validate(wrong); err != ErrInvalidToken {
		t.Errorf("Validate(wrong) = %v, want ErrInvalidToken", err)
	}
}

func TestTokenStoreLoadMissingReturnsErrNoToken(t *testing.T) {
	dir := t.TempDir()
	store, err := NewFileTokenStore(dir)
	if err != nil {
		t.Fatalf("NewFileTokenStore: %v", err)
	}
	if store.Hash() != nil {
		t.Errorf("Hash() on fresh store = %v, want nil", store.Hash())
	}
	if err := store.Validate("anything"); err != ErrInvalidToken {
		t.Errorf("Validate on fresh store = %v, want ErrInvalidToken", err)
	}
}

func TestFingerprintIsStable(t *testing.T) {
	a := Fingerprint("token-a")
	b := Fingerprint("token-a")
	if a != b {
		t.Errorf("Fingerprint not stable: %s vs %s", a, b)
	}
	if len(a) != 16 {
		t.Errorf("Fingerprint len = %d, want 16 (8 bytes hex)", len(a))
	}
}

func TestGraceWindowAcceptsPreviousHash(t *testing.T) {
	dir := t.TempDir()
	store, _ := NewFileTokenStore(dir)

	oldToken, _ := store.Generate()
	_ = store.Persist(oldToken)
	oldHash := store.Hash()

	newToken, _ := store.Generate()
	_ = store.Persist(newToken)

	// Inject a grace entry directly (Plan 03's Rotate is the real path).
	store.mu.Lock()
	store.grace = &graceEntry{
		prevHash:  oldHash,
		expiresAt: time.Now().Add(1 * time.Hour),
	}
	store.mu.Unlock()

	if err := store.Validate(oldToken); err != nil {
		t.Errorf("Validate(oldToken) during grace: %v", err)
	}
	if err := store.Validate(newToken); err != nil {
		t.Errorf("Validate(newToken) during grace: %v", err)
	}

	// Expire the grace window.
	store.mu.Lock()
	store.grace.expiresAt = time.Now().Add(-1 * time.Second)
	store.mu.Unlock()

	if err := store.Validate(oldToken); err != ErrInvalidToken {
		t.Errorf("Validate(oldToken) after grace expiry = %v, want ErrInvalidToken", err)
	}
	if err := store.Validate(newToken); err != nil {
		t.Errorf("Validate(newToken) after grace expiry: %v", err)
	}
}
