package nonce

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sync"
)

// journalPath is the filename of the nonce audit journal under
// the dataDir passed to openJournalWriter. Phase 12 §CF-08:
// same atomic-rename + chmod-600 precedent as
// internal/auth/token.go:187 (initial-token) / 384 (grace).
const journalPath = "bridge-nonce-audit.json"

// Event is one JSONL row in the audit journal. IssuedAt is the
// RFC3339 instant the nonce was minted; UsedAt is zero unless
// operation == "validate" records a consumption. ActorTokenFP
// and NonceFP are the sha256[8] hex fingerprints of the
// plaintexts - safe for forensics (PITFALLS S-1 invariant:
// plaintext nonce + bearer NEVER enter the journal).
type Event struct {
	NonceFP      string `json:"nonce_fp"`
	IssuedAt     string `json:"issued_at"`
	UsedAt       string `json:"used_at,omitempty"`
	ActorTokenFP string `json:"actor_token_fp"`
	RequestID    string `json:"request_id"`
	Operation    string `json:"operation"` // "issue" | "validate"
}

// journalWriter is the append-only JSONL writer. Single mutex
// serializes writes so that we never interleave two
// json.Encode lines in the same file. The file is opened with
// O_APPEND so that the underlying syscall is atomic at the
// kernel level (writes <PIPE_BUF are atomic on POSIX; journal
// lines are ~250 bytes < 4096 = PIPE_BUF on Linux).
type journalWriter struct {
	mu sync.Mutex
	f  *os.File
}

// newJournalWriter opens dataDir/journalPath with O_APPEND |
// O_CREATE | O_WRONLY and chmod 600. The file is created if
// missing; chmod is set on every open because os.Chmod is a
// no-op on a preexisting file with the desired mode, and a
// fresh create race is harmless (chmod is racy but the file is
// chmod 600 either way).
func newJournalWriter(dataDir string) (*journalWriter, error) {
	if err := os.MkdirAll(dataDir, 0o700); err != nil {
		return nil, fmt.Errorf("nonce: mkdir data dir: %w", err)
	}
	path := filepath.Join(dataDir, journalPath)
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o600)
	if err != nil {
		return nil, fmt.Errorf("nonce: open journal: %w", err)
	}
	// Best-effort chmod in case the file pre-existed with a
	// permissive mode (e.g. from a pre-Phase-12 deployment).
	// The OpenFile flag is sufficient on fresh create.
	if err := os.Chmod(path, 0o600); err != nil {
		f.Close()
		return nil, fmt.Errorf("nonce: chmod journal: %w", err)
	}
	return &journalWriter{f: f}, nil
}

// close releases the underlying fd. Idempotent on multiple
// calls so the Manager defer can call it during shutdown.
func (j *journalWriter) close() error {
	if j == nil || j.f == nil {
		return nil
	}
	err := j.f.Close()
	j.f = nil
	return err
}

// Close satisfies io.Closer so callers (e.g. Manager.Close)
// can defer Close() without custom helper code.
func (j *journalWriter) Close() error { return j.close() }

// appendJSONL writes one Event as a single JSON line
// (newline-terminated) under a mutex that serializes the file
// writes. Returns any I/O error so the Manager can convert it
// to slog.Warn per PITFALLS S-5 (journal failure does NOT
// propagate to Issue or Validate).
func (j *journalWriter) appendJSONL(ev Event) error {
	j.mu.Lock()
	defer j.mu.Unlock()
	if j.f == nil {
		return fmt.Errorf("nonce: journal closed")
	}
	b, err := json.Marshal(ev)
	if err != nil {
		return fmt.Errorf("nonce: marshal event: %w", err)
	}
	b = append(b, '\n')
	if _, err := j.f.Write(b); err != nil {
		return fmt.Errorf("nonce: write journal: %w", err)
	}
	return nil
}

// compile-time check that journalWriter satisfies io.Closer
// (used by callers wanting a single Close() signature).
var _ io.Closer = (*journalWriter)(nil)
