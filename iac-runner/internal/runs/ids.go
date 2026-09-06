// Package runs owns the run lifecycle primitives shared by the
// durable store (17-04), the job queue (17-05), and the HTTP
// handlers (17-06): collision-free run identifiers, validated
// working-directory paths, the /data/runs/{run_id}/ layout,
// read-time secret redaction, and age-based retention rotation.
//
// This file holds the identifier primitive only — no I/O.
package runs

import (
	"crypto/rand"
	"encoding/base32"
)

// RunIDLength is the character length of every run identifier. 10
// random bytes encode to exactly 16 base32 characters with padding
// disabled (10 * 8 / 5 == 16), which is why runIDBytes and
// RunIDLength must be changed together.
const RunIDLength = 16

// runIDBytes is the raw entropy per identifier: 80 bits. Collision
// probability is negligible at this workload (a handful of runs per
// hour, retained for runs_retention_hours; CONTEXT D-03 — UUIDv4 is
// an acceptable alternative; base32 is chosen because the value
// doubles as a directory name and a URL path segment with no
// escaping).
const runIDBytes = 10

// runIDEncoding is standard base32 with padding disabled. The
// alphabet is [A-Z2-7]: no '=', '/', '+', '.', '-'. That makes every
// identifier simultaneously safe as a filesystem directory name
// (D-01) and as a URL path segment (/v1/runs/{id}) without
// escaping, and it cannot express ".." so an identifier can never
// traverse out of /data/runs/.
var runIDEncoding = base32.StdEncoding.WithPadding(base32.NoPadding)

// NewRunID returns a fresh 16-character run identifier. The error
// is non-nil only when the system CSPRNG fails, which callers must
// treat as fatal for the request — no fallback to time-based IDs,
// since a predictable identifier would let a caller guess another
// run's directory.
func NewRunID() (string, error) {
	b := make([]byte, runIDBytes)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return runIDEncoding.EncodeToString(b), nil
}

// IsValidRunID reports whether id has exactly the shape NewRunID
// produces. Handlers call it on the {id} path parameter BEFORE
// touching the filesystem, so a hostile value never reaches
// filepath.Join.
func IsValidRunID(id string) bool {
	if len(id) != RunIDLength {
		return false
	}
	for i := 0; i < len(id); i++ {
		c := id[i]
		switch {
		case c >= 'A' && c <= 'Z':
		case c >= '2' && c <= '7':
		default:
			return false
		}
	}
	return true
}
