package runs

// Durable run metadata: the /data/runs/{run_id}/meta.json half of the
// CONTEXT D-01 layout. The output.log half lives in output.go.
//
// Design constraints this file satisfies:
//   - OBS-03: the file on disk is the source of truth. The API keeps no
//     run state in memory, so an add-on restart loses nothing except
//     the tofu child processes themselves.
//   - D-01: writes go through flock + atomic rename, so a concurrent
//     reader can never observe a half-written meta.json.
//   - RUN-05: List answers GET /v1/runs — newest first, repo/status
//     filters, default 20 / max 100 from the shared contract constants.

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"syscall"
	"time"

	"iac-runner/internal/contract"
)

// ErrRunNotFound is the sentinel every "this run is not readable"
// condition maps to: an unknown id, a syntactically invalid id, and a
// corrupt meta.json all wrap it. Handlers translate it to HTTP 404 +
// contract.ErrCodeRunUnknownID.
var ErrRunNotFound = errors.New("runs: run not found")

// metaFileName is the per-run metadata file (CONTEXT D-01).
const metaFileName = "meta.json"

// lockFileName is the advisory-lock companion of meta.json. It is a
// SEPARATE file on purpose — see Update for why locking meta.json
// itself would protect nothing.
const lockFileName = ".meta.lock"

// Meta is the persisted state of one run, serialized to
// /data/runs/{run_id}/meta.json (CONTEXT D-01). It is the source of
// truth for GET /v1/runs/{id} and GET /v1/runs — the API never keeps
// run state in memory (OBS-03), so a restart loses nothing except the
// tofu processes themselves.
//
// The json tags mirror contract.RunDetail / contract.RunSummary field
// for field, so the handler layer in 17-06 is a straight projection
// rather than a translation.
type Meta struct {
	RunID      string             `json:"run_id"`
	Repo       string             `json:"repo"`
	Dir        string             `json:"dir"`
	Kind       contract.RunKind   `json:"kind"`
	Status     contract.RunStatus `json:"status"`
	ExitCode   *int               `json:"exit_code"`
	StartedAt  time.Time          `json:"started_at"`
	FinishedAt *time.Time         `json:"finished_at,omitempty"`
	ErrorCode  string             `json:"error_code,omitempty"`
	// PlanFile is the absolute path of the plan artifact a successful
	// `plan` run produced. /v1/apply looks it up to decide between
	// consuming a prior plan and an inline apply (CONTEXT D-18); an
	// empty value means "no plan artifact".
	PlanFile string `json:"plan_file,omitempty"`
}

// ListFilter narrows a List call. The zero value means "everything,
// capped at contract.DefaultRunListLimit".
type ListFilter struct {
	Repo   string
	Status contract.RunStatus
	Limit  int
}

// Store owns the /data/runs tree. It holds no run state — every read
// goes to disk (OBS-03) — so multiple Stores over the same directory,
// or a Store plus an operator's `jq`, stay consistent.
type Store struct {
	runsDir string
	// now is injectable so tests can freeze time; nil defaults to
	// time.Now in NewStore.
	now func() time.Time
}

// NewStore roots a Store at runsDir, creating the directory (0700) if
// it does not exist. Under HA Supervisor /data is bind-mounted before
// the container starts, but the store must not depend on that external
// guarantee: a plain `docker run` with no volume, and every test, gets
// a working store rather than a failure on the first Create.
func NewStore(runsDir string, now func() time.Time) (*Store, error) {
	if runsDir == "" {
		return nil, errors.New("runs: NewStore requires a runs directory")
	}
	if err := os.MkdirAll(runsDir, 0o700); err != nil {
		return nil, fmt.Errorf("runs: mkdir runs dir: %w", err)
	}
	if now == nil {
		now = time.Now
	}
	return &Store{runsDir: runsDir, now: now}, nil
}

// RunsDir returns the root of the run tree, for callers that need to
// report it (startup log records, retention diagnostics).
func (s *Store) RunsDir() string { return s.runsDir }

// Now exposes the store's injected clock so sibling files in this
// package (retention.go, output.go) share one time source.
func (s *Store) Now() time.Time { return s.now() }

// Dir returns /data/runs/{runID}, or the empty string when runID is
// not shaped like a run id. This is the SECOND line of defense: the
// handler already validates the {id} path parameter before it reaches
// the store, but a store method must never join an unvalidated string
// onto s.runsDir. Every caller in this package treats "" as
// not-found rather than falling through to a filesystem call.
func (s *Store) Dir(runID string) string {
	if !IsValidRunID(runID) {
		return ""
	}
	return filepath.Join(s.runsDir, runID)
}

// metaPath returns the meta.json path for runID, or "" for an invalid
// id (propagating Dir's guard).
func (s *Store) metaPath(runID string) string {
	dir := s.Dir(runID)
	if dir == "" {
		return ""
	}
	return filepath.Join(dir, metaFileName)
}

// Create materializes /data/runs/{run_id}/ (0700) and writes the
// initial meta.json (0600). It does not check for an existing run:
// run ids come from crypto/rand (ids.go), so a collision is not a
// condition worth a round-trip to the filesystem.
func (s *Store) Create(m Meta) error {
	dir := s.Dir(m.RunID)
	if dir == "" {
		return fmt.Errorf("%w: %q", ErrRunNotFound, m.RunID)
	}
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return fmt.Errorf("runs: mkdir run dir: %w", err)
	}
	return s.writeMeta(m)
}

// writeMeta persists m atomically, mirroring the chmod-600 atomic
// write in internal/auth/token.go: a tempfile in the SAME directory
// (so the rename cannot cross filesystems) is written, fsynced,
// chmodded and renamed over meta.json. A reader therefore observes
// either the previous complete file or the new complete file, never a
// prefix of either.
func (s *Store) writeMeta(m Meta) error {
	dir := s.Dir(m.RunID)
	if dir == "" {
		return fmt.Errorf("%w: %q", ErrRunNotFound, m.RunID)
	}

	tmp, err := os.CreateTemp(dir, ".meta-*.json")
	if err != nil {
		return fmt.Errorf("runs: create temp meta: %w", err)
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName) // no-op once the rename succeeded

	if err := json.NewEncoder(tmp).Encode(m); err != nil {
		tmp.Close()
		return fmt.Errorf("runs: encode meta: %w", err)
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return fmt.Errorf("runs: sync meta: %w", err)
	}
	if err := tmp.Close(); err != nil {
		return fmt.Errorf("runs: close temp meta: %w", err)
	}
	if err := os.Chmod(tmpName, 0o600); err != nil {
		return fmt.Errorf("runs: chmod meta: %w", err)
	}
	if err := os.Rename(tmpName, filepath.Join(dir, metaFileName)); err != nil {
		return fmt.Errorf("runs: rename meta: %w", err)
	}
	return nil
}

// Load reads the persisted Meta for runID.
//
// A missing file, an invalid run id, and a corrupt/partial meta.json
// all return ErrRunNotFound. That collapse is deliberate: from the
// API's point of view a corrupt meta.json is operationally identical
// to a missing run, and surfacing `json: cannot unmarshal …` to a
// caller tells them nothing they can act on while leaking the on-disk
// layout. The operator still sees the real cause — the raw file is
// right there under /data.
func (s *Store) Load(runID string) (Meta, error) {
	path := s.metaPath(runID)
	if path == "" {
		return Meta{}, fmt.Errorf("%w: %q", ErrRunNotFound, runID)
	}
	b, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return Meta{}, fmt.Errorf("%w: %s", ErrRunNotFound, runID)
		}
		return Meta{}, fmt.Errorf("runs: read meta %s: %w", runID, err)
	}
	var m Meta
	if err := json.Unmarshal(b, &m); err != nil {
		return Meta{}, fmt.Errorf("%w: %s (corrupt meta.json)", ErrRunNotFound, runID)
	}
	return m, nil
}

// Update applies mutate to the persisted Meta and writes the result
// back atomically. The whole read-modify-write is serialized by an
// exclusive flock, so two goroutines (or two processes) incrementing
// the same field cannot lose an update — the concurrency contract of
// CONTEXT D-01.
//
// The lock lives on a DEDICATED .meta.lock file rather than on
// meta.json itself. writeMeta finishes with an atomic rename, which
// replaces meta.json's inode; a flock held on the old meta.json file
// descriptor would then be a lock on an unlinked inode that no
// subsequent opener can see, and would protect nothing. The separate
// lock file is never renamed, so every participant locks the same
// inode for the lifetime of the run directory.
func (s *Store) Update(runID string, mutate func(*Meta) error) (Meta, error) {
	dir := s.Dir(runID)
	if dir == "" {
		return Meta{}, fmt.Errorf("%w: %q", ErrRunNotFound, runID)
	}

	lockFile, err := os.OpenFile(filepath.Join(dir, lockFileName), os.O_CREATE|os.O_RDWR, 0o600)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			// The run directory itself is gone (rotated away).
			return Meta{}, fmt.Errorf("%w: %s", ErrRunNotFound, runID)
		}
		return Meta{}, fmt.Errorf("runs: open lock file: %w", err)
	}
	defer lockFile.Close()

	// syscall.Flock is Linux-only; the add-on ships as an amd64 Linux
	// container (config.yaml `arch: [amd64]`), and syscall is stdlib —
	// no new module dependency for the lock.
	if err := syscall.Flock(int(lockFile.Fd()), syscall.LOCK_EX); err != nil {
		return Meta{}, fmt.Errorf("runs: flock: %w", err)
	}
	defer func() { _ = syscall.Flock(int(lockFile.Fd()), syscall.LOCK_UN) }()

	// Read INSIDE the lock: reading before acquiring it would reopen
	// the lost-update window the lock exists to close.
	m, err := s.Load(runID)
	if err != nil {
		return Meta{}, err
	}
	if err := mutate(&m); err != nil {
		return Meta{}, err
	}
	if err := s.writeMeta(m); err != nil {
		return Meta{}, err
	}
	return m, nil
}

// List answers GET /v1/runs (RUN-05): newest first, optional repo and
// status filters, and the default-20 / max-100 caps taken from the
// contract constants so handler and store cannot drift.
//
// Robustness over strictness: a directory that is not a run id, a run
// whose meta.json is mid-creation, and a run with a corrupt meta.json
// are all skipped rather than failing the call. One bad run must not
// blank out the operator's entire history.
func (s *Store) List(f ListFilter) ([]Meta, error) {
	entries, err := os.ReadDir(s.runsDir)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, nil
		}
		return nil, fmt.Errorf("runs: read runs dir: %w", err)
	}

	out := make([]Meta, 0, len(entries))
	for _, e := range entries {
		if !e.IsDir() || !IsValidRunID(e.Name()) {
			continue
		}
		m, err := s.Load(e.Name())
		if err != nil {
			if errors.Is(err, ErrRunNotFound) {
				continue
			}
			return nil, err
		}
		if f.Repo != "" && m.Repo != f.Repo {
			continue
		}
		if f.Status != "" && m.Status != f.Status {
			continue
		}
		out = append(out, m)
	}

	sort.SliceStable(out, func(i, j int) bool {
		return out[i].StartedAt.After(out[j].StartedAt)
	})

	limit := f.Limit
	if limit <= 0 {
		limit = contract.DefaultRunListLimit
	}
	if limit > contract.MaxRunListLimit {
		limit = contract.MaxRunListLimit
	}
	if len(out) > limit {
		out = out[:limit]
	}
	return out, nil
}
