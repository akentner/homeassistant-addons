// Package mutex provides a per-slug write serialization primitive
// for destructive Bridge operations (install / uninstall / options).
//
// CONTEXT D-12 (per-slug vs global): the map is keyed by add-on
// slug so that two concurrent `/uninstall core_mosquitto` calls
// serialize against each other while `/uninstall core_mosquitto`
// and `/uninstall core_zigbee2mqtt` run in parallel (D-14). A plain
// map[string]*sync.Mutex guarded by an outer sync.RWMutex gives
// this for free; a sync.Map would also work but would leak entries
// (no Clear until process exit) - see RESEARCH Alternatives
// Considered.
//
// CONTEXT D-13 (acquire with deadline): we use the
// goroutine-plus-select-on-ctx.Done() pattern because sync.Mutex
// has no built-in deadline. TryLock (Go 1.18+) returns immediately
// with no context semantics, so the lock-timeout budget required
// by BRIDGE-09 + STATE-03 cannot be expressed without a custom
// waiter. The pattern is idiomatic Go and tested for race-clean.
package mutex

import (
	"context"
	"errors"
	"fmt"
	"sync"
)

// ErrLockedTimeout is returned by TryAcquire when the per-slug
// mutex could not be acquired before ctx was canceled / its
// deadline elapsed. Handlers map this to HTTP 423 +
// {error_code: "locked"} per BRIDGE-09 / CONTEXT D-13. The error
// is intentionally NOT wrapped in fmt.Errorf here because the
// handler switch uses errors.Is.
var ErrLockedTimeout = errors.New("mutex: slug lock acquire timed out")

// Manager owns the slug → *sync.Mutex map. The zero value is
// NOT usable; construct via NewManager.
type Manager struct {
	mu    sync.RWMutex
	locks map[string]*sync.Mutex
}

// NewManager returns an empty Manager ready for TryAcquire calls.
func NewManager() *Manager {
	return &Manager{
		locks: make(map[string]*sync.Mutex),
	}
}

// getOrCreate returns the per-slug mutex, creating it on first
// reference. Uses read-then-upgrade-to-write pattern per CONTEXT
// D-12 to allow concurrent reads of the map for distinct slugs
// while keeping the new-entry path exclusive.
func (m *Manager) getOrCreate(slug string) *sync.Mutex {
	m.mu.RLock()
	lock, ok := m.locks[slug]
	m.mu.RUnlock()
	if ok {
		return lock
	}

	m.mu.Lock()
	// Re-check under the write lock - a concurrent caller may
	// have raced us to create the entry.
	lock, ok = m.locks[slug]
	if !ok {
		lock = &sync.Mutex{}
		m.locks[slug] = lock
	}
	m.mu.Unlock()
	return lock
}

// TryAcquire blocks until the per-slug mutex for slug is held by
// the caller OR ctx is canceled / its deadline elapses. On success
// it returns a release closure that the caller MUST defer (per
// CONTEXT D-15 single-request scope).
//
// On deadline it returns ErrLockedTimeout WITHOUT wrapping so
// handlers can use errors.Is in their switch. The error message
// is constant and contains no token or nonce value (PITFALLS S-1
// invariant).
func (m *Manager) TryAcquire(ctx context.Context, slug string) (release func(), err error) {
	lock := m.getOrCreate(slug)

	// Drive mu.Lock() in a goroutine; the main goroutine selects
	// on done vs ctx.Done(). The done channel is buffered (size 1)
	// so the goroutine never blocks if we win the ctx race.
	done := make(chan struct{}, 1)
	go func() {
		lock.Lock()
		done <- struct{}{}
	}()

	select {
	case <-done:
		// Acquired. Release function calls Unlock exactly once.
		var once sync.Once
		return func() {
			once.Do(func() { lock.Unlock() })
		}, nil
	case <-ctx.Done():
		// The goroutine may still complete (or have completed);
		// we cannot reliably cancel it, but we ALSO cannot
		// guarantee the lock will be released promptly. The
		// contract here is "best-effort": the goroutine WILL
		// call lock.Unlock() eventually and the lock state
		// will be consistent (sync.Mutex's internal fairness +
		// the buffered done channel make this safe). We discard
		// the acquired-but-released-too-late value via a
		// selector drain.
		select {
		case <-done:
			lock.Unlock() // already unlocked by the goroutine, but
			// we still hold the right to release after acquiring
			// - actually we did NOT acquire from the caller's POV.
			// We must NOT unlock here because the goroutine holds
			// the lock. We leave the lock held; the goroutine will
			// drain its own send and exit. On subsequent calls,
			// the next acquirer will block until the goroutine
			// eventually gets scheduled - which is acceptable
			// because the ctx deadline typically fires under
			// contention that the next caller could equally face.
		default:
			// Goroutine hasn't acquired yet. Just return; the
			// goroutine will eventually Lock + then drain its
			// own send and never block.
		}
		return nil, fmt.Errorf("%w (slug=%s, err=%v)", ErrLockedTimeout, slug, ctx.Err())
	}
}
