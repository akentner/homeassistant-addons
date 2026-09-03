package nonce

import (
	"bytes"
	"context"
	"errors"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"
)

func newTestManager(t *testing.T, ttl time.Duration) *Manager {
	t.Helper()
	dir := t.TempDir()
	m, err := NewManager(dir, ttl)
	if err != nil {
		t.Fatalf("NewManager: %v", err)
	}
	t.Cleanup(func() { _ = m.Close() })
	return m
}

func TestManagerIssueReturnsValidNonce(t *testing.T) {
	m := newTestManager(t, DefaultTTL)
	now := time.Now()
	m.clock = func() time.Time { return now }

	plaintext, expiresAt, err := m.Issue("actor-fp", "req-1")
	if err != nil {
		t.Fatalf("Issue: %v", err)
	}
	if len(plaintext) != 43 {
		t.Errorf("plaintext length = %d, want 43 (32-byte base64url)", len(plaintext))
	}
	if expiresAt.IsZero() {
		t.Errorf("expiresAt is zero")
	}
	if !expiresAt.After(now) {
		t.Errorf("expiresAt = %v must be after now = %v", expiresAt, now)
	}
	if expiresAt.Sub(now) != DefaultTTL {
		t.Errorf("expiresAt - now = %v, want %v", expiresAt.Sub(now), DefaultTTL)
	}
}

func TestManagerValidateConsumes(t *testing.T) {
	m := newTestManager(t, DefaultTTL)

	plaintext, _, err := m.Issue("actor-fp", "req-1")
	if err != nil {
		t.Fatalf("Issue: %v", err)
	}

	ok, err := m.Validate(plaintext, "actor-fp", "req-2")
	if err != nil {
		t.Errorf("first Validate: %v", err)
	}
	if !ok {
		t.Errorf("first Validate ok = false, want true")
	}
}

func TestManagerValidateUsedNonce(t *testing.T) {
	m := newTestManager(t, DefaultTTL)

	plaintext, _, err := m.Issue("actor-fp", "req-1")
	if err != nil {
		t.Fatalf("Issue: %v", err)
	}

	if _, err := m.Validate(plaintext, "actor-fp", "req-2"); err != nil {
		t.Fatalf("first Validate: %v", err)
	}

	_, err = m.Validate(plaintext, "actor-fp", "req-3")
	if !errors.Is(err, ErrNonceUsed) {
		t.Errorf("second Validate err = %v, want ErrNonceUsed", err)
	}
}

func TestManagerValidateExpiredNonce(t *testing.T) {
	m := newTestManager(t, 10*time.Millisecond)
	plaintext, _, err := m.Issue("actor-fp", "req-1")
	if err != nil {
		t.Fatalf("Issue: %v", err)
	}

	// Advance past TTL.
	time.Sleep(20 * time.Millisecond)

	_, err = m.Validate(plaintext, "actor-fp", "req-2")
	if !errors.Is(err, ErrNonceExpired) {
		t.Errorf("Validate after ttl err = %v, want ErrNonceExpired", err)
	}
}

func TestManagerValidateNeverIssued(t *testing.T) {
	m := newTestManager(t, DefaultTTL)

	_, err := m.Validate("non-existent-nonce", "actor-fp", "req-1")
	if !errors.Is(err, ErrNonceExpired) {
		t.Errorf("Validate never-issued err = %v, want ErrNonceExpired", err)
	}
}

func TestManagerValidateEmptyString(t *testing.T) {
	m := newTestManager(t, DefaultTTL)

	_, err := m.Validate("", "actor-fp", "req-1")
	if !errors.Is(err, ErrNonceExpired) {
		t.Errorf("Validate empty err = %v, want ErrNonceExpired", err)
	}
}

func TestNonceIssueContinuesAfterJournalFailure(t *testing.T) {
	// Inject a Manager whose journal always fails. We do this
	// by constructing the journalWriter directly with a path
	// inside a read-only directory (best portable fault
	// injection), OR by replacing the journal with an
	// in-memory helper. For this test we use the package's
	// low-level entry point: replace the jw field after
	// construction.
	dir := t.TempDir()
	m, err := NewManager(dir, DefaultTTL)
	if err != nil {
		t.Fatalf("NewManager: %v", err)
	}
	t.Cleanup(func() { _ = m.Close() })

	// Replace jw with a closed writer so appendJSONL returns
	// "journal closed" error.
	m.jw.f = nil // forces appendJSONL to return an error

	plaintext, expiresAt, err := m.Issue("actor-fp", "req-1")
	if err != nil {
		t.Errorf("Issue with broken journal returned err = %v, want nil (Pitfall 5)", err)
	}
	if plaintext == "" {
		t.Errorf("plaintext is empty, want valid nonce")
	}
	if expiresAt.IsZero() {
		t.Errorf("expiresAt is zero")
	}
}

func TestNonceGCRespectsContextCancellation(t *testing.T) {
	m := newTestManager(t, DefaultTTL)
	ctx, cancel := context.WithCancel(context.Background())

	m.StartGC(ctx)

	// Cancel immediately. The goroutine should exit within the
	// next GC tick + a small scheduling window.
	cancel()

	// We can't directly observe the goroutine count via the
	// Manager; instead, validate that subsequent Issue + Close
	// work cleanly (no use-after-close panic).
	done := make(chan struct{})
	go func() {
		defer close(done)
		_, _, _ = m.Issue("actor-fp", "req-1")
	}()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("Issue did not return within 2s after GC cancel (goroutine may be wedged)")
	}
}

func TestNonceJournalNeverContainsPlaintext(t *testing.T) {
	dir := t.TempDir()
	m, err := NewManager(dir, DefaultTTL)
	if err != nil {
		t.Fatalf("NewManager: %v", err)
	}
	t.Cleanup(func() { _ = m.Close() })

	plaintext, _, err := m.Issue("actor-fp", "req-1")
	if err != nil {
		t.Fatalf("Issue: %v", err)
	}
	// Validate so a "validate" event is also written.
	if _, err := m.Validate(plaintext, "actor-fp", "req-2"); err != nil {
		t.Fatalf("Validate: %v", err)
	}

	// Force a Sync on the journal so bytes are on disk.
	if err := m.jw.f.Sync(); err != nil {
		t.Fatalf("Sync: %v", err)
	}

	path := filepath.Join(dir, journalPath)
	body, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("ReadFile %s: %v", path, err)
	}
	if bytes.Contains(body, []byte(plaintext)) {
		t.Errorf("journal contains plaintext nonce %q:\n%s", plaintext, body)
	}
}

func TestManagerConcurrentValidateSingleUse(t *testing.T) {
	m := newTestManager(t, DefaultTTL)
	plaintext, _, err := m.Issue("actor-fp", "req-1")
	if err != nil {
		t.Fatalf("Issue: %v", err)
	}

	const N = 20
	var wg sync.WaitGroup
	results := make([]error, N)
	for i := 0; i < N; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			_, err := m.Validate(plaintext, "actor-fp", "req-r")
			results[i] = err
		}(i)
	}
	wg.Wait()

	successes := 0
	for _, err := range results {
		if err == nil {
			successes++
			continue
		}
		if !errors.Is(err, ErrNonceUsed) {
			t.Errorf("got unexpected error %v (must be either nil or ErrNonceUsed)", err)
		}
	}
	if successes != 1 {
		t.Errorf("success count = %d, want exactly 1 (single-use under concurrency)", successes)
	}
}
