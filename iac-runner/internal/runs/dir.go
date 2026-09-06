package runs

import (
	"errors"
	"fmt"
	"path/filepath"
	"strings"
)

// ErrInvalidDir is the sentinel every ValidateDir failure wraps.
// Handlers map it to HTTP 400 + contract.ErrCodeRunInvalidDir
// (CONTEXT D-22).
var ErrInvalidDir = errors.New("runs: invalid dir")

// InvalidDirMessage is the operator-facing message returned with
// every run_invalid_dir response. Wording is fixed by CONTEXT D-22 —
// it names both rejected constructs so the operator can fix the
// request without reading the source.
const InvalidDirMessage = "dir must be a relative path under the repo working tree; " +
	"leading '/' and '..' segments are forbidden"

// ValidateDir normalizes and validates the `dir` field of
// POST /v1/plan and POST /v1/apply (CONTEXT D-21).
//
// Rules, all applied at parse time before any filesystem access:
//   - a null byte anywhere is rejected (it would truncate the path
//     in any syscall)
//   - a leading '/' is rejected: dir is always relative to
//     /data/repos/<name>/
//   - any '..' segment, before or after filepath.Clean, is rejected,
//     so the run can never escape the repo working tree
//
// The empty string is LEGAL and means the repo root (CONTEXT D-23);
// "." normalizes to the same thing. On success the cleaned relative
// path is returned and is the only value callers may join onto the
// repo directory.
func ValidateDir(dir string) (string, error) {
	if strings.ContainsRune(dir, 0) {
		return "", fmt.Errorf("%w: %s", ErrInvalidDir, InvalidDirMessage)
	}
	if dir == "" {
		return "", nil
	}
	if strings.HasPrefix(dir, "/") {
		return "", fmt.Errorf("%w: %s", ErrInvalidDir, InvalidDirMessage)
	}

	for _, seg := range strings.Split(dir, "/") {
		if seg == ".." {
			return "", fmt.Errorf("%w: %s", ErrInvalidDir, InvalidDirMessage)
		}
	}

	cleaned := filepath.Clean(dir)
	if cleaned == "." {
		return "", nil
	}
	if cleaned == ".." || strings.HasPrefix(cleaned, "../") ||
		strings.Contains(cleaned, "/../") || strings.HasSuffix(cleaned, "/..") {
		return "", fmt.Errorf("%w: %s", ErrInvalidDir, InvalidDirMessage)
	}
	if filepath.IsAbs(cleaned) {
		return "", fmt.Errorf("%w: %s", ErrInvalidDir, InvalidDirMessage)
	}
	return cleaned, nil
}
