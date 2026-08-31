// Package auth implements the Bridge's bearer-token primitive:
// generation, persistence (atomic, chmod 600), validation
// (constant-time compare against the on-disk SHA-256 hash), and a
// rotation-with-grace flow used by POST /v1/auth/rotate (Plan 03).
//
// AUTH-02 / AUTH-03 / AUTH-04 are satisfied by this package:
//   - AUTH-02: Generate() uses crypto/rand (32 bytes); plaintext is
//     base64url-encoded with RawURLEncoding so the result is 43 chars,
//     URL-safe, and has no padding that would need escaping.
//   - AUTH-03: Validate() compares the SHA-256 of the presented token
//     against the on-disk hash via subtle.ConstantTimeCompare.
//   - AUTH-04: Rotate() (Plan 03) writes the previous hash to a
//     .grace file with grace_expires_at = now + 24h.
//
// SECURITY INVARIANTS — DO NOT VIOLATE:
//  1. The plaintext token never enters a log record. The Fingerprint
//     helper (sha256[8] hex) is the only token-derived value that
//     ever appears in logs. Truncate is a deliberate, narrow
//     exception for first-start identification — it surfaces 6 of
//     43 chars (3 prefix + 3 suffix) for human correlation only;
//     callers needing security MUST use Fingerprint instead.
//  2. The hash on disk is SHA-256 (not the plaintext). Restoring the
//     plaintext from disk is impossible by construction.
//  3. Error messages do not include the presented token, the on-disk
//     hash, or any fragment thereof.
//  4. The plaintext token is written to disk exactly once, on first
//     start, at /data/initial-token (chmod 600, atomic rename), so
//     operators can configure their Provider without the token ever
//     passing through a log stream. Subsequent restarts do NOT
//     re-write this file.
package auth

import (
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// ErrNoToken is returned by Load when /data/bridge-token does not yet
// exist (first-start condition). Callers translate this to
// "generate a fresh token" logic in main.go.
var ErrNoToken = errors.New("auth: no token on disk; first start")

// ErrInvalidToken is returned by Validate when the presented token
// does not match the on-disk hash. Callers translate this to HTTP
// 401 with body {"error_code":"unauthorized"} (CF-03).
var ErrInvalidToken = errors.New("auth: invalid token")

// TokenStore owns the on-disk hash and the in-memory mutex that
// guards concurrent Validate calls. The struct is intentionally
// small — no cached plaintext, no rotation cache — so the lifetime
// of the plaintext is bounded to the rotation response body.
type TokenStore struct {
	dataDir string // /data
	// tokenPath and gracePath are computed at construction.
	tokenPath string // /data/bridge-token
	gracePath string // /data/bridge-token.grace

	mu    sync.RWMutex // guards hash, grace
	hash  []byte       // SHA-256 of current valid token
	grace *graceEntry  // nil when no grace is active
}

// graceEntry records the rotation grace window. Both fields are
// required: prevHash lets the OLD token keep authenticating until
// expiresAt; expiresAt drives per-request expiry checks.
type graceEntry struct {
	prevHash  []byte
	expiresAt time.Time
}

// NewFileTokenStore loads any existing hash + grace from disk. If
// the token file does not exist the returned store is empty and the
// caller must call Generate+Persist before exposing any authed
// endpoint. The returned error is only non-nil for I/O failures
// OTHER than ErrNoToken — partial reads, permission errors, or a
// corrupt hash file all surface as wrapped errors here.
func NewFileTokenStore(dataDir string) (*TokenStore, error) {
	s := &TokenStore{
		dataDir:   dataDir,
		tokenPath: filepath.Join(dataDir, "bridge-token"),
		gracePath: filepath.Join(dataDir, "bridge-token.grace"),
	}
	hash, err := readHashFile(s.tokenPath)
	if err != nil {
		if errors.Is(err, ErrNoToken) {
			return s, nil // first start — caller will generate
		}
		return nil, fmt.Errorf("auth: load hash: %w", err)
	}
	s.hash = hash

	grace, err := readGraceFile(s.gracePath)
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		return nil, fmt.Errorf("auth: load grace: %w", err)
	}
	s.grace = grace

	return s, nil
}

// Generate creates a fresh 256-bit token (32 random bytes) and
// returns its base64url-encoded plaintext (43 chars). The plaintext
// is returned to the caller exactly once — for the rotation
// response body or the first-start log line — and is never persisted.
func (s *TokenStore) Generate() (string, error) {
	raw := make([]byte, 32)
	if _, err := rand.Read(raw); err != nil {
		return "", fmt.Errorf("auth: rand.Read: %w", err)
	}
	return base64.RawURLEncoding.EncodeToString(raw), nil
}

// Persist hashes the plaintext and writes the hash to
// /data/bridge-token with chmod 600. The write is atomic: a
// tempfile in the same directory is written, fsynced, and renamed
// over the destination so concurrent reads never observe a partial
// hash. After Persist returns, s.hash is loaded from disk so the
// next Validate call succeeds without re-reading.
func (s *TokenStore) Persist(plaintext string) error {
	sum := sha256.Sum256([]byte(plaintext))
	hash := sum[:]

	// Atomic write: tmpfile in same dir → fsync → rename.
	tmp, err := os.CreateTemp(s.dataDir, ".bridge-token.*.tmp")
	if err != nil {
		return fmt.Errorf("auth: create tmp: %w", err)
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName) // no-op if rename succeeded

	if _, err := tmp.Write(hash); err != nil {
		tmp.Close()
		return fmt.Errorf("auth: write hash: %w", err)
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return fmt.Errorf("auth: sync hash: %w", err)
	}
	if err := tmp.Close(); err != nil {
		return fmt.Errorf("auth: close tmp: %w", err)
	}
	if err := os.Chmod(tmpName, 0o600); err != nil {
		return fmt.Errorf("auth: chmod tmp: %w", err)
	}
	if err := os.Rename(tmpName, s.tokenPath); err != nil {
		return fmt.Errorf("auth: rename hash: %w", err)
	}

	s.mu.Lock()
	s.hash = hash
	s.mu.Unlock()
	return nil
}

// WriteInitialTokenFile persists the plaintext token to
// /data/initial-token (chmod 600, atomic rename) on first start so
// operators can configure their Provider without the plaintext
// ever passing through a log stream. The returned path is logged
// (along with the truncated preview emitted by Truncate) in the
// bridge.token.issued record. Subsequent restarts do NOT call this
// method — the file is written exactly once. Operators SHOULD delete
// the file (e.g. `ha addons cli terraform-bridge exec rm /data/initial-token`)
// after configuring their Provider so the plaintext is not stored
// on disk any longer than necessary.
func (s *TokenStore) WriteInitialTokenFile(plaintext string) (string, error) {
	path := filepath.Join(s.dataDir, "initial-token")

	tmp, err := os.CreateTemp(s.dataDir, ".initial-token.*.tmp")
	if err != nil {
		return "", fmt.Errorf("auth: create initial-token tmp: %w", err)
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName) // no-op if rename succeeded

	if _, err := tmp.WriteString(plaintext + "\n"); err != nil {
		tmp.Close()
		return "", fmt.Errorf("auth: write initial-token: %w", err)
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return "", fmt.Errorf("auth: sync initial-token: %w", err)
	}
	if err := tmp.Close(); err != nil {
		return "", fmt.Errorf("auth: close initial-token: %w", err)
	}
	if err := os.Chmod(tmpName, 0o600); err != nil {
		return "", fmt.Errorf("auth: chmod initial-token: %w", err)
	}
	if err := os.Rename(tmpName, path); err != nil {
		return "", fmt.Errorf("auth: rename initial-token: %w", err)
	}
	return path, nil
}

// Hash returns the on-disk SHA-256 hash (copy), used by the
// /v1/whoami handler to compute actor_token_fp. Returns nil if no
// token has been generated yet (first-start, pre-Generate).
func (s *TokenStore) Hash() []byte {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.hash == nil {
		return nil
	}
	out := make([]byte, len(s.hash))
	copy(out, s.hash)
	return out
}

// Validate returns nil if the presented plaintext hashes to the
// on-disk hash OR, during an active grace window, to the previous
// hash stored in /data/bridge-token.grace. Returns ErrInvalidToken
// otherwise. Comparison is constant-time via subtle.ConstantTimeCompare.
//
// Grace expiry is checked on every call (D-13): if expiresAt is
// past, the previous-hash match path is skipped and only the
// current hash can succeed.
func (s *TokenStore) Validate(plaintext string) error {
	sum := sha256.Sum256([]byte(plaintext))
	presented := sum[:]

	s.mu.RLock()
	current := s.hash
	grace := s.grace
	s.mu.RUnlock()

	if current == nil {
		return ErrInvalidToken // no token generated yet
	}

	if subtle.ConstantTimeCompare(presented, current) == 1 {
		return nil
	}

	if grace != nil && time.Now().Before(grace.expiresAt) {
		if subtle.ConstantTimeCompare(presented, grace.prevHash) == 1 {
			return nil
		}
	}

	return ErrInvalidToken
}

// GraceWindow is the lifetime of a rotation grace period (D-02).
// After this window elapses, the previous token stops authenticating.
const GraceWindow = 24 * time.Hour

// RotateResult is what TokenStore.Rotate returns. OldTokenFP and
// NewTokenFP are the sha256[8] hex fingerprints of the previous and
// newly-issued tokens respectively — safe to log in audit records.
// NewPlaintext is the freshly-issued plaintext (the caller surfaces
// it in the POST /v1/auth/rotate response body exactly once per CF-02).
// GraceExpiresAt is the RFC3339 instant after which the previous
// token stops authenticating (D-13).
type RotateResult struct {
	NewPlaintext   string
	OldTokenFP     string
	NewTokenFP     string
	GraceExpiresAt string // RFC3339
}

// Fingerprint returns the first 8 bytes of SHA-256(plaintext) as
// hex — a stable, non-reversible identifier safe to log in audit
// records. Two distinct tokens never collide at this width with
// negligible probability (~ 1 / 2^32).
//
// Truncate returns a log-safe *preview* of a plaintext token:
// first 3 chars + "..." + last 3 chars. Used by main.go's
// first-start emission (bridge.token.issued) so the log carries a
// human-readable identifier without disclosing the bearer. For
// tokens shorter than 6 chars the entire string is returned
// (truncation would discard more than it preserves). The preview is
// NOT cryptographically derived — it is purely a display helper.
// Callers that need a stable, non-reversible identifier MUST use
// Fingerprint instead.
func Fingerprint(plaintext string) string {
	sum := sha256.Sum256([]byte(plaintext))
	return hex.EncodeToString(sum[:8])
}

// HashFingerprint returns the first 8 bytes of an already-computed
// SHA-256 hash as hex — the log-safe fingerprint of a token when the
// plaintext is no longer available (used by main.go's bridge.token.loaded
// record and by Rotate when fingerprinting the just-replaced token
// without re-deriving its plaintext). Both fingerprints are derivable
// from the same SHA-256 input, so HashFingerprint(hash) ==
// Fingerprint(plaintext) for any plaintext hashing to `hash`.
func HashFingerprint(hash []byte) string {
	if len(hash) < 8 {
		return ""
	}
	return hex.EncodeToString(hash[:8])
}

// Truncate returns a log-safe preview of a plaintext token:
// first 3 chars + "..." + last 3 chars. Used by main.go's
// first-start emission (bridge.token.issued) so the log carries a
// human-readable identifier without disclosing the bearer. For
// tokens shorter than 6 chars the entire string is returned
// (truncation would discard more than it preserves). The preview is
// NOT cryptographically derived — it is purely a display helper.
// Callers that need a stable, non-reversible identifier MUST use
// Fingerprint instead.
func Truncate(plaintext string) string {
	const edge = 3
	if len(plaintext) <= 2*edge {
		return plaintext
	}
	return plaintext[:edge] + "..." + plaintext[len(plaintext)-edge:]
}

// Rotate issues a fresh token, persists its hash to the primary
// /data/bridge-token file (chmod 600, atomic rename), and persists
// the previous hash to /data/bridge-token.grace with a grace expiry
// of now + GraceWindow (D-02). The returned RotateResult carries
// the new plaintext (caller surfaces once) and three fingerprints
// for the audit record. After Rotate returns, Validate accepts
// BOTH the old and new tokens until GraceExpiresAt.
//
// The auth package emits no log records; the caller is responsible
// for logging the audit record (auth package invariant: "no slog
// calls in this package").
func (s *TokenStore) Rotate() (RotateResult, error) {
	prevHash := s.Hash()

	newPlaintext, err := s.Generate()
	if err != nil {
		return RotateResult{}, fmt.Errorf("auth: rotate generate: %w", err)
	}

	sum := sha256.Sum256([]byte(newPlaintext))
	newHash := sum[:]

	tmp, err := os.CreateTemp(s.dataDir, ".bridge-token.*.tmp")
	if err != nil {
		return RotateResult{}, fmt.Errorf("auth: rotate create tmp: %w", err)
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)

	if _, err := tmp.Write(newHash); err != nil {
		tmp.Close()
		return RotateResult{}, fmt.Errorf("auth: rotate write: %w", err)
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return RotateResult{}, fmt.Errorf("auth: rotate sync: %w", err)
	}
	if err := tmp.Close(); err != nil {
		return RotateResult{}, fmt.Errorf("auth: rotate close: %w", err)
	}
	if err := os.Chmod(tmpName, 0o600); err != nil {
		return RotateResult{}, fmt.Errorf("auth: rotate chmod: %w", err)
	}
	if err := os.Rename(tmpName, s.tokenPath); err != nil {
		return RotateResult{}, fmt.Errorf("auth: rotate rename: %w", err)
	}

	expiresAt := time.Now().Add(GraceWindow)
	graceExpiresRFC := expiresAt.UTC().Format(time.RFC3339)

	prevHashHex := hex.EncodeToString(prevHash)
	graceBody := prevHashHex + "\n" + graceExpiresRFC + "\n"

	gtmp, err := os.CreateTemp(s.dataDir, ".bridge-token.grace.*.tmp")
	if err != nil {
		return RotateResult{}, fmt.Errorf("auth: rotate grace tmp: %w", err)
	}
	gtmpName := gtmp.Name()
	defer os.Remove(gtmpName)

	if _, err := gtmp.WriteString(graceBody); err != nil {
		gtmp.Close()
		return RotateResult{}, fmt.Errorf("auth: rotate grace write: %w", err)
	}
	if err := gtmp.Sync(); err != nil {
		gtmp.Close()
		return RotateResult{}, fmt.Errorf("auth: rotate grace sync: %w", err)
	}
	if err := gtmp.Close(); err != nil {
		return RotateResult{}, fmt.Errorf("auth: rotate grace close: %w", err)
	}
	if err := os.Chmod(gtmpName, 0o600); err != nil {
		return RotateResult{}, fmt.Errorf("auth: rotate grace chmod: %w", err)
	}
	if err := os.Rename(gtmpName, s.gracePath); err != nil {
		return RotateResult{}, fmt.Errorf("auth: rotate grace rename: %w", err)
	}

	s.mu.Lock()
	s.hash = newHash
	s.grace = &graceEntry{
		prevHash:  prevHash,
		expiresAt: expiresAt,
	}
	s.mu.Unlock()

	return RotateResult{
		NewPlaintext:   newPlaintext,
		OldTokenFP:     HashFingerprint(prevHash),
		NewTokenFP:     Fingerprint(newPlaintext),
		GraceExpiresAt: graceExpiresRFC,
	}, nil
}

// readHashFile reads the on-disk hash; returns ErrNoToken when the
// file does not exist (first-start condition).
func readHashFile(path string) ([]byte, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, ErrNoToken
		}
		return nil, err
	}
	if len(b) != sha256.Size {
		return nil, fmt.Errorf("auth: hash file has wrong size %d (want %d)", len(b), sha256.Size)
	}
	return b, nil
}

// readGraceFile reads the grace entry; returns (nil, os.ErrNotExist)
// when no grace is active. Format is two lines:
//   <hex-encoded prevHash, 64 chars>
//   <RFC3339 expiresAt>
// Plan 03's Rotate method writes this file; this read path is
// committed here so the Validate grace branch above is testable
// once Plan 03 lands.
func readGraceFile(path string) (*graceEntry, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err // caller distinguishes os.ErrNotExist
	}
	// Minimal parser — Plan 03's writer matches this format.
	var line1, line2 string
	_, err = fmt.Sscanf(string(b), "%s\n%s", &line1, &line2)
	if err != nil {
		return nil, fmt.Errorf("auth: grace file format: %w", err)
	}
	prevHash, err := hex.DecodeString(line1)
	if err != nil {
		return nil, fmt.Errorf("auth: grace prevHash hex: %w", err)
	}
	expiresAt, err := time.Parse(time.RFC3339, line2)
	if err != nil {
		return nil, fmt.Errorf("auth: grace expiresAt: %w", err)
	}
	return &graceEntry{prevHash: prevHash, expiresAt: expiresAt}, nil
}
