// Package state enumerates the *.tfstate + *.tfstate.backup
// files in the Bridge's data directory (default /data) with
// their SHA-256 digests. CONTEXT D-20..D-23 / STATE-02.
//
// Pattern coverage:
//
//	*.tfstate          - canonical OpenTofu state file
//	*.tfstate.backup   - rolling backup written by tofu before
//	                     each apply (provider-local convention)
//	*.tfstate.lock     - EXCLUDED; ephemeral lock written by
//	                     tofu during apply; never user-relevant.
//
// The .lock exclusion is automatic because filepath.Glob uses
// literal pattern matching; "*.tfstate" does NOT match
// "foo.tfstate.lock". We rely on that and document it via the
// TestIndexSkipsLockedFiles regression test.
//
// Per-file I/O errors (permission denied on one file) are
// accumulated as Skipped entries rather than aborting the whole
// index (D-23). An empty result set is valid (D-23).
package state

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

// FileEntry is the per-file row of the /v1/state/index response.
// name is the basename only (no directory); size_bytes is the
// file size on disk; sha256 is the hex-encoded SHA-256 of the
// full file contents at the time of Index().
type FileEntry struct {
	Name      string `json:"name"`
	SizeBytes int64  `json:"size_bytes"`
	SHA256    string `json:"sha256"`
}

// SkippedEntry records a per-file error that did NOT abort the
// Index() call. Surfaces in the response via StateIndexResponse.
// Skipped.
//
// Skipped carries the basename + a short error reason so the
// caller can fix the permission issue without re-running the
// enumeration.
type SkippedEntry struct {
	Name string `json:"name"`
	Err  string `json:"err"`
}

// Index enumerates dir/*.tfstate + dir/*.tfstate.backup with
// their SHA-256 digests. *.tfstate.lock files are skipped
// (D-20). On per-file I/O failure the entry appears in the
// skipped slice; the error NEVER propagates (D-23).
//
// Returns (files, skipped, nil) on success or partial-success.
// Returns (nil, nil, err) only when filepath.Glob itself fails
// (e.g. dir does not exist - callers in production always pass
// /data which Supervisor bind-mounts; tests use t.TempDir()).
func Index(dir string) ([]FileEntry, []SkippedEntry, error) {
	patterns := []string{
		filepath.Join(dir, "*.tfstate"),
		filepath.Join(dir, "*.tfstate.backup"),
	}

	seen := make(map[string]bool)
	var files []FileEntry
	var skipped []SkippedEntry

	for _, pat := range patterns {
		matches, err := filepath.Glob(pat)
		if err != nil {
			return nil, nil, fmt.Errorf("state: glob %s: %w", pat, err)
		}
		for _, match := range matches {
			name := filepath.Base(match)
			if seen[name] {
				continue
			}
			seen[name] = true

			entry, err := computeEntry(match)
			if err != nil {
				skipped = append(skipped, SkippedEntry{Name: name, Err: err.Error()})
				continue
			}
			files = append(files, entry)
		}
	}

	if files == nil {
		files = []FileEntry{}
	}
	if skipped == nil {
		skipped = []SkippedEntry{}
	}
	return files, skipped, nil
}

// computeEntry reads the file at path, hashes its contents
// with SHA-256 (streaming via io.Copy, so large state files
// don't blow memory), and returns the FileEntry row. Any I/O
// error is wrapped and returned so Index can record it as a
// SkippedEntry.
func computeEntry(path string) (FileEntry, error) {
	f, err := os.Open(path)
	if err != nil {
		return FileEntry{}, err
	}
	defer f.Close()

	st, err := f.Stat()
	if err != nil {
		return FileEntry{}, err
	}

	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return FileEntry{}, err
	}

	return FileEntry{
		Name:      filepath.Base(path),
		SizeBytes: st.Size(),
		SHA256:    hex.EncodeToString(h.Sum(nil)),
	}, nil
}
