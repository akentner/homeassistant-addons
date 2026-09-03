// Package nonce implements the X-Force-Destroy nonce primitive
// that destructive Bridge operations (uninstall, options-change)
// require per CONTEXT Area 2 + LIFE-03.
//
// Storage layout (D-05):
//
//  1. In-memory map[string]entry{issuedAt, used} guarded by
//     sync.RWMutex. This is the SINGLE-USE ENFORCEMENT layer.
//     Every X-Force-Destroy validation reads the entry, marks
//     used = true, and returns success. On Bridge restart the
//     cache is empty - callers see 401 nonce_expired and
//     re-request a fresh nonce via POST /v1/auth/nonce
//     (D-08: cache loss is acceptable; journal is forensics
//     only).
//
//  2. Append-only journal /data/bridge-nonce-audit.json with
//     chmod 600. Each issued/used nonce event writes one JSONL
//     line with {nonce_fp, issued_at, used_at?, actor_token_fp,
//     request_id, operation}. The plaintext nonce is NEVER
//     written (PITFALLS S-1 invariant; see journal.go).
//
// The package has no HTTP awareness; it is consumed by
// handlers/nonce.go (issuance) and handlers/uninstall.go
// (validation).
package nonce

import (
	"sync"
	"time"
)

// entry is the cache row for a single issued nonce. issuedAt
// drives the 60s window check; used drives single-use
// enforcement. We deliberately store the plaintext nonce value
// (43 chars) in the key plus a struct value rather than
// fingerprinting to avoid a second map for the lookups: the
// nonce itself is the lookup key, so the plaintext is already
// in our hands. We MUST NOT log plaintext values out of this
// package (entry used as audit blob only; never passed to
// slog).
type entry struct {
	issuedAt time.Time
	used     bool
}

// cache is the in-memory nonce store guarded by sync.RWMutex
// (read-mostly: the validate path reads then marks used, both
// under the same write lock). Exposed package-private - tested
// via the Manager entry points above, not directly.
type cache struct {
	mu sync.RWMutex
	m  map[string]entry
}

// newCache returns an empty cache ready for Issue + Validate.
func newCache() *cache {
	return &cache{m: make(map[string]entry)}
}

// set inserts or replaces the entry for n with the given
// issuedAt. The used flag is taken from used (true on second
// Validate). Caller MUST hold the write lock already or not
// hold any lock (this method does the locking).
func (c *cache) set(n string, issuedAt time.Time, used bool) {
	c.mu.Lock()
	c.m[n] = entry{issuedAt: issuedAt, used: used}
	c.mu.Unlock()
}

// get returns a copy of the entry for n + its existence.
// Nonce-fingerprint: the lookup key IS the plaintext nonce; we
// accept that because both issuance and validation must own
// the plaintext to compare against the X-Force-Destroy header.
// The plaintext never leaves this package.
func (c *cache) get(n string) (entry, bool) {
	c.mu.RLock()
	e, ok := c.m[n]
	c.mu.RUnlock()
	return e, ok
}

// del removes n from the cache. Used when Validate discovers
// the nonce has expired (CONTEXT D-06).
func (c *cache) del(n string) {
	c.mu.Lock()
	delete(c.m, n)
	c.mu.Unlock()
}

// expired returns true when the nonce is in the cache but past
// its TTL, or when it is missing entirely. Missing is treated
// as "expired" so a never-issued nonce and a long-past-issued
// nonce look identical to the validator (CONTEXT D-06:
// caller can't distinguish "never issued" from "issued in a
// previous process - cache didn't survive restart" - both
// return nonce_expired).
//
// We treat TTL expiry as a soft delete at GC time; this
// function is called during Validate to short-circuit
// used=true + expired entries fast.
func (c *cache) expired(n string, ttl time.Duration, now time.Time) bool {
	e, ok := c.get(n)
	if !ok {
		return true
	}
	return now.Sub(e.issuedAt) > ttl
}
