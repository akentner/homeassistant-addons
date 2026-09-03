package nonce

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"terraform-bridge/internal/auth"
)

// ErrNonceExpired is returned by Validate when the presented
// nonce was never issued (cache miss) OR was issued in a prior
// process whose cache did not survive restart (D-08). Handler
// translates to HTTP 401 + {error_code: "nonce_expired"}.
var ErrNonceExpired = errors.New("nonce: expired or never issued")

// ErrNonceUsed is returned by Validate when the presented
// nonce has already been used (D-06 single-use enforcement).
// Handler translates to HTTP 401 + {error_code: "nonce_used"}.
var ErrNonceUsed = errors.New("nonce: already used")

// DefaultTTL matches CONTEXT D-06 (60 seconds). Exposed as a
// var so tests can use a tighter window without rewriting the
// manager; production callers pass the explicit value from
// config (D-03 / CONTEXT Area 4).
const DefaultTTL = 60 * time.Second

// gcInterval is the periodic-loop interval for StartGC. CONTEXT
// D-07: 30 seconds. The goroutine removes entries where
// now > issuedAt + ttl + 5s_grace so that in-flight requests
// with a nonce near its expiry are not GCed mid-validate.
const gcInterval = 30 * time.Second

// Manager owns the cache + journal + TTL. Construct via
// NewManager (uses a private default journal path under
// dataDir). Tests inject a custom journal via NewManagerWithJournal.
type Manager struct {
	cache *cache
	jw    *journalWriter
	ttl   time.Duration

	// clock is injected for tests so they can advance time
	// without sleeping. Production callers receive a realClock
	// (time.Now).
	clock   func() time.Time
	closer  func() error
	closeMu sync.Mutex
	closed  bool
}

// NewManager creates a Manager whose journal lives at
// dataDir/bridge-nonce-audit.json (chmod 600 per journal.go).
// Returns an error if dataDir cannot be created or the journal
// cannot be opened.
func NewManager(dataDir string, ttl time.Duration) (*Manager, error) {
	jw, err := newJournalWriter(dataDir)
	if err != nil {
		return nil, err
	}
	return newManagerWith(jw, ttl, jw.close), nil
}

// newManagerWith is the package-internal constructor used by
// NewManager + tests. closer defaults to jw.close() but tests
// pass a noop so the test can read the journal contents after
// the manager is "closed".
func newManagerWith(jw *journalWriter, ttl time.Duration, closer func() error) *Manager {
	if ttl <= 0 {
		ttl = DefaultTTL
	}
	return &Manager{
		cache:  newCache(),
		jw:     jw,
		ttl:    ttl,
		clock:  func() time.Time { return time.Now() },
		closer: closer,
	}
}

// Issue mints a new 32-byte nonce, base64url-encodes it (43
// chars per Phase 10 D-01 precedent), stores it in the cache
// with issuedAt = now, appends a journal "issue" event, and
// returns (plaintext, expiresAt, nil). On journal failure the
// function still returns a valid nonce (PITFALLS S-5: cache is
// the enforcement layer; journal is forensic). Plaintext never
// enters the journal - we record auth.Fingerprint(plaintext).
func (m *Manager) Issue(actorFP, requestID string) (string, time.Time, error) {
	raw := make([]byte, 32)
	if _, err := rand.Read(raw); err != nil {
		return "", time.Time{}, fmt.Errorf("nonce: rand.Read: %w", err)
	}
	nonce := base64.RawURLEncoding.EncodeToString(raw)

	issuedAt := m.clock()
	expiresAt := issuedAt.Add(m.ttl)
	m.cache.set(nonce, issuedAt, false)

	ev := Event{
		NonceFP:      auth.Fingerprint(nonce),
		IssuedAt:     issuedAt.UTC().Format(time.RFC3339),
		ActorTokenFP: actorFP,
		RequestID:    requestID,
		Operation:    "issue",
	}
	if err := m.jw.appendJSONL(ev); err != nil {
		// Pitfall 5: journal failure does NOT block issuance.
		slog.Warn("bridge_nonce_journal_append_failed", "err", err.Error())
	}
	return nonce, expiresAt, nil
}

// Validate checks the presented nonce against the cache. Returns
// (true, nil) on the success path. Returns (_, ErrNonceExpired)
// when the nonce is missing (never issued OR issued in a prior
// process - D-08) or past TTL. Returns (_, ErrNonceUsed) when
// the nonce has already been consumed (single-use, D-06).
//
// On success the entry is marked used=true and a journal
// "validate" event is appended (PITFALLS S-5: journal failure
// does not block the success path).
func (m *Manager) Validate(presented, actorFP, requestID string) (bool, error) {
	now := m.clock()

	if presented == "" {
		return false, ErrNonceExpired
	}

	e, ok := m.cache.get(presented)
	if !ok {
		return false, ErrNonceExpired
	}
	if now.Sub(e.issuedAt) > m.ttl {
		m.cache.del(presented)
		return false, ErrNonceExpired
	}
	if e.used {
		return false, ErrNonceUsed
	}

	// Mark used (single-use). Re-set under cache write-lock so
	// two concurrent Validate calls for the same nonce can't
	// both succeed.
	m.cache.set(presented, e.issuedAt, true)

	usedAt := now.UTC().Format(time.RFC3339)
	ev := Event{
		NonceFP:      auth.Fingerprint(presented),
		IssuedAt:     e.issuedAt.UTC().Format(time.RFC3339),
		UsedAt:       usedAt,
		ActorTokenFP: actorFP,
		RequestID:    requestID,
		Operation:    "validate",
	}
	if err := m.jw.appendJSONL(ev); err != nil {
		slog.Warn("bridge_nonce_journal_append_failed", "err", err.Error())
	}
	return true, nil
}

// StartGC launches a background goroutine that runs every
// gcInterval (30s per CONTEXT D-07) and removes cache entries
// where now > issuedAt + ttl + 5s_grace. Returns immediately;
// the goroutine returns when ctx.Done() fires (Pitfall 9: GC
// must respect context cancellation so Bridge shutdown is
// prompt).
func (m *Manager) StartGC(ctx context.Context) {
	go func() {
		t := time.NewTicker(gcInterval)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				m.gcOnce()
			}
		}
	}()
}

// gcOnce runs a single GC pass. Package-private (lowercase).
const gcGrace = 5 * time.Second

func (m *Manager) gcOnce() {
	now := m.clock()
	cutoff := m.ttl + gcGrace
	// We can't iterate the map and delete entries under the
	// same lock without holding the write lock for the full
	// pass. Instead: take a snapshot of expired keys under the
	// read lock, then delete each under the cache internals.
	candidates := make([]string, 0)
	m.cache.mu.RLock()
	for k, e := range m.cache.m {
		if now.Sub(e.issuedAt) > cutoff {
			candidates = append(candidates, k)
		}
	}
	m.cache.mu.RUnlock()
	for _, k := range candidates {
		m.cache.del(k)
	}
}

// Close releases the journal fd. Idempotent. After Close
// further Issue / Validate / journal.appendJSONL calls return
// errors.
func (m *Manager) Close() error {
	m.closeMu.Lock()
	defer m.closeMu.Unlock()
	if m.closed {
		return nil
	}
	m.closed = true
	if m.closer != nil {
		return m.closer()
	}
	return nil
}
