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

func TestWriteInitialTokenFileCreatesChmod600(t *testing.T) {
	dir := t.TempDir()
	store, err := NewFileTokenStore(dir)
	if err != nil {
		t.Fatalf("NewFileTokenStore: %v", err)
	}
	token, _ := store.Generate()

	path, err := store.WriteInitialTokenFile(token)
	if err != nil {
		t.Fatalf("WriteInitialTokenFile: %v", err)
	}
	if path != filepath.Join(dir, "initial-token") {
		t.Errorf("path = %q, want %q", path, filepath.Join(dir, "initial-token"))
	}

	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat initial-token: %v", err)
	}
	if perm := info.Mode().Perm(); perm != 0o600 {
		t.Errorf("initial-token mode = %o, want 0600", perm)
	}

	body, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read initial-token: %v", err)
	}
	if strings.TrimSpace(string(body)) != token {
		t.Errorf("initial-token body = %q, want %q", string(body), token)
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

// TestNewFileTokenStoreCreatesMissingDataDir is a regression test for
// item-7-data-mkdir-gap: NewFileTokenStore must create dataDir if it
// does not already exist, rather than silently deferring the failure
// to the first Persist/WriteInitialTokenFile call (which is what
// caused the terraform-bridge container to crash on first start when
// run without a pre-existing /data — reproduced live in CI, see
// .planning/debug/resolved/item-7-data-mkdir-gap.md).
func TestNewFileTokenStoreCreatesMissingDataDir(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "nested", "does-not-exist-yet")

	store, err := NewFileTokenStore(dir)
	if err != nil {
		t.Fatalf("NewFileTokenStore on missing dir: %v", err)
	}

	info, err := os.Stat(dir)
	if err != nil {
		t.Fatalf("dataDir was not created: %v", err)
	}
	if !info.IsDir() {
		t.Fatalf("dataDir path exists but is not a directory")
	}

	// First-start sequence exactly as main.go performs it — must not
	// fail with ENOENT now that dataDir is guaranteed to exist.
	token, err := store.Generate()
	if err != nil {
		t.Fatalf("Generate: %v", err)
	}
	if err := store.Persist(token); err != nil {
		t.Fatalf("Persist on freshly-created dataDir: %v", err)
	}
	if _, err := store.WriteInitialTokenFile(token); err != nil {
		t.Fatalf("WriteInitialTokenFile on freshly-created dataDir: %v", err)
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

func TestTruncatePreviewFormat(t *testing.T) {
	// Normal-length token (43 chars, real base64url token length).
	tok := "abcdefghijklmnopqrstuvwxyz0123456789abcdefghi"
	got := Truncate(tok)
	want := "abc...ghi"
	if got != want {
		t.Errorf("Truncate(43-char) = %q, want %q", got, want)
	}

	// Short token below the 6-char threshold: full string preserved.
	if got := Truncate("abc"); got != "abc" {
		t.Errorf("Truncate(3-char) = %q, want %q", got, "abc")
	}

	// Exactly 6 chars: full string preserved (2*edge boundary).
	if got := Truncate("abcdef"); got != "abcdef" {
		t.Errorf("Truncate(6-char) = %q, want %q", got, "abcdef")
	}

	// 7 chars: truncation kicks in.
	if got := Truncate("abcdefg"); got != "abc...efg" {
		t.Errorf("Truncate(7-char) = %q, want %q", got, "abc...efg")
	}
}

func TestTruncatePreviewDoesNotContainInterior(t *testing.T) {
	// Negative control: the interior of the token must NOT appear in
	// the preview. Guards against regressions where Truncate starts
	// leaking more than the 3+3 edges.
	tok := "prefix-INTERIOR-suffix"
	got := Truncate(tok)
	if strings.Contains(got, "INTERIOR") {
		t.Errorf("Truncate leaked interior: %q", got)
	}
	if !strings.HasPrefix(got, "pre") {
		t.Errorf("Truncate prefix wrong: %q", got)
	}
	if !strings.HasSuffix(got, "fix") {
		t.Errorf("Truncate suffix wrong: %q", got)
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

func TestTokenStoreRotate(t *testing.T) {
	dir := t.TempDir()
	store, _ := NewFileTokenStore(dir)
	oldPlain, _ := store.Generate()
	_ = store.Persist(oldPlain)

	res, err := store.Rotate()
	if err != nil {
		t.Fatalf("Rotate: %v", err)
	}
	if res.NewPlaintext == oldPlain {
		t.Errorf("Rotate returned the same plaintext as before")
	}
	if res.NewPlaintext == "" {
		t.Errorf("NewPlaintext is empty")
	}
	if res.GraceExpiresAt == "" {
		t.Errorf("GraceExpiresAt is empty")
	}

	if err := store.Validate(oldPlain); err != nil {
		t.Errorf("Validate(oldPlain) during grace: %v", err)
	}
	if err := store.Validate(res.NewPlaintext); err != nil {
		t.Errorf("Validate(NewPlaintext) during grace: %v", err)
	}

	store.mu.Lock()
	store.grace.expiresAt = time.Now().Add(-1 * time.Second)
	store.mu.Unlock()

	if err := store.Validate(oldPlain); err != ErrInvalidToken {
		t.Errorf("Validate(oldPlain) after expiry = %v, want ErrInvalidToken", err)
	}
	if err := store.Validate(res.NewPlaintext); err != nil {
		t.Errorf("Validate(NewPlaintext) after expiry: %v", err)
	}
}

func TestTokenStoreGracePersistsAcrossReload(t *testing.T) {
	dir := t.TempDir()
	store, _ := NewFileTokenStore(dir)
	oldPlain, _ := store.Generate()
	_ = store.Persist(oldPlain)
	res, _ := store.Rotate()

	reloaded, err := NewFileTokenStore(dir)
	if err != nil {
		t.Fatalf("reload: %v", err)
	}
	if err := reloaded.Validate(oldPlain); err != nil {
		t.Errorf("Validate(oldPlain) after reload: %v", err)
	}
	if err := reloaded.Validate(res.NewPlaintext); err != nil {
		t.Errorf("Validate(NewPlaintext) after reload: %v", err)
	}

	graceBytes, err := os.ReadFile(filepath.Join(dir, "bridge-token.grace"))
	if err != nil {
		t.Fatalf("read grace: %v", err)
	}
	lines := strings.Split(strings.TrimSpace(string(graceBytes)), "\n")
	if len(lines) != 2 {
		t.Errorf("grace file lines = %d, want 2", len(lines))
	}
	if len(lines[0]) != 64 {
		t.Errorf("grace file line 1 length = %d, want 64 hex chars", len(lines[0]))
	}
	if _, err := time.Parse(time.RFC3339, lines[1]); err != nil {
		t.Errorf("grace file line 2 not RFC3339: %v", err)
	}

	info, err := os.Stat(filepath.Join(dir, "bridge-token.grace"))
	if err != nil {
		t.Fatalf("stat grace: %v", err)
	}
	if perm := info.Mode().Perm(); perm != 0o600 {
		t.Errorf("grace file mode = %o, want 0600", perm)
	}
}
