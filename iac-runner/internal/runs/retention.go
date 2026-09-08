package runs

// Lifecycle maintenance of the /data/runs tree: the boot-time
// `interrupted` sweep (CONTEXT D-02) and age-based rotation that bounds
// disk usage (OBS-02, CONTEXT D-25, ROADMAP SC-11).
//
// Both operations walk os.ReadDir directly rather than going through
// List. List applies the RUN-05 response caps (default 20, max 100),
// which are exactly wrong here: a capped sweep would silently leave
// older runs stale forever, and a capped rotation would stop reclaiming
// disk as soon as the history grew past 100 runs.

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"sync"
	"time"

	"iac-runner/internal/contract"
)

// minTickInterval floors the rotation cadence. runs_retention_hours has
// a schema minimum of 1 (17-01), which would otherwise give a 15-minute
// tick; the floor keeps that sane and, more importantly, keeps a
// hand-edited /data/options.json from turning the ticker into a busy
// loop that walks /data/runs continuously.
const minTickInterval = 1 * time.Minute

// SweepInterrupted rewrites every run still marked `running` or
// `queued` to `interrupted` and returns how many it transitioned.
//
// Why this exists (CONTEXT D-02): a run's tofu process died with the
// previous container, so a persisted `running` status can never resolve
// on its own — nothing is left to write the terminal state. Leaving it
// would show the operator a job that runs forever; calling it `failed`
// would be a lie that sends them looking for a tofu error that does not
// exist. `interrupted` says exactly what happened: the add-on restarted
// mid-run.
//
// `queued` is swept for the same reason. The job queue is in-process
// only (D-05: a restart resumes nothing), so a persisted `queued` run
// has no worker either — and because Rotate deliberately never touches
// a queued run (its writer may hold an open fd), leaving it would make
// the directory exempt from retention permanently on top of showing
// the operator a job that never starts. This runs BEFORE the listener
// opens and before the queue exists, so it cannot race a live
// submission.
//
// 17-07 calls this once from main.go BEFORE the HTTP listener starts,
// so no client ever observes a stale `running`.
//
// A single unreadable or corrupt run is collected via errors.Join and
// does NOT abort the sweep: the add-on must still start, and the other
// runs must still be corrected.
func (s *Store) SweepInterrupted() (int, error) {
	entries, err := os.ReadDir(s.runsDir)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return 0, nil
		}
		return 0, fmt.Errorf("runs: read runs dir: %w", err)
	}

	swept := 0
	var errs []error
	for _, e := range entries {
		if !e.IsDir() || !IsValidRunID(e.Name()) {
			continue
		}
		runID := e.Name()
		m, err := s.Load(runID)
		if err != nil {
			if errors.Is(err, ErrRunNotFound) {
				continue // corrupt or half-created — nothing to sweep
			}
			errs = append(errs, err)
			continue
		}
		if m.Status != contract.RunStatusRunning && m.Status != contract.RunStatusQueued {
			continue
		}
		if _, err := s.Update(runID, func(m *Meta) error {
			m.Status = contract.RunStatusInterrupted
			if m.FinishedAt == nil {
				t := s.now().UTC()
				m.FinishedAt = &t
			}
			// ErrorCode stays empty on purpose: the run was cut
			// short, it did not fail, so there is no tofu error to
			// attribute. The status alone carries the diagnosis.
			return nil
		}); err != nil {
			errs = append(errs, fmt.Errorf("runs: sweep %s: %w", runID, err))
			continue
		}
		swept++
	}
	return swept, errors.Join(errs...)
}

// Rotate deletes run directories older than maxAge and returns how many
// it removed (OBS-02, CONTEXT D-25).
//
// Age reference is FinishedAt when set, otherwise StartedAt. After the
// boot sweep every non-terminal run from a previous container has a
// FinishedAt; StartedAt is the fallback for a run that never reached a
// terminal state within this container's lifetime.
//
// Queued and running runs are skipped unconditionally, regardless of
// age: their writer still holds an open fd on output.log, and deleting
// the directory under it would silently discard the output of a job
// that is still executing.
func (s *Store) Rotate(maxAge time.Duration) (int, error) {
	entries, err := os.ReadDir(s.runsDir)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return 0, nil
		}
		return 0, fmt.Errorf("runs: read runs dir: %w", err)
	}

	deleted := 0
	var errs []error
	now := s.now()
	for _, e := range entries {
		if !e.IsDir() || !IsValidRunID(e.Name()) {
			continue
		}
		runID := e.Name()
		m, err := s.Load(runID)
		if err != nil {
			if errors.Is(err, ErrRunNotFound) {
				// No usable metadata: a corrupt meta.json, or none at
				// all because Create's MkdirAll succeeded and its
				// writeMeta did not (a full disk — precisely when
				// retention matters). Skipping made such a directory
				// exempt from rotation FOREVER, so the add-on could
				// not recover from a disk-full episode without a
				// manual rm -rf. Age it by its own mtime instead; a
				// directory being created right now is by definition
				// not over-age.
				if s.rotateUnparseable(e, now, maxAge) {
					deleted++
				}
				continue
			}
			errs = append(errs, err)
			continue
		}
		if m.Status == contract.RunStatusQueued || m.Status == contract.RunStatusRunning {
			continue
		}
		ref := m.StartedAt
		if m.FinishedAt != nil {
			ref = *m.FinishedAt
		}
		if now.Sub(ref) <= maxAge {
			continue
		}
		if err := os.RemoveAll(s.Dir(runID)); err != nil {
			errs = append(errs, fmt.Errorf("runs: rotate %s: %w", runID, err))
			continue
		}
		deleted++
	}
	return deleted, errors.Join(errs...)
}

// rotateUnparseable deletes a run directory that carries no readable
// meta.json and whose own mtime is older than maxAge, reporting
// whether it did. Every failure is swallowed: this is a best-effort
// reclaim of state nothing else can interpret, and it must not turn
// into an error the boot path reports.
func (s *Store) rotateUnparseable(e os.DirEntry, now time.Time, maxAge time.Duration) bool {
	info, err := e.Info()
	if err != nil {
		return false
	}
	if now.Sub(info.ModTime()) <= maxAge {
		return false
	}
	if err := os.RemoveAll(s.Dir(e.Name())); err != nil {
		slog.Warn("runs.rotate_unparseable_failed", "run_id", e.Name(), "err", err.Error())
		return false
	}
	slog.Info("runs.rotated_unparseable", "run_id", e.Name(), "mtime", info.ModTime().UTC().Format(time.RFC3339))
	return true
}

// tickInterval is the rotation cadence for a given retention window:
// retention / 4 (ROADMAP SC-11 — the 24h default gives a 6h tick),
// never below minTickInterval.
func tickInterval(retention time.Duration) time.Duration {
	interval := retention / 4
	if interval < minTickInterval {
		return minTickInterval
	}
	return interval
}

// StartRetentionTicker runs Rotate on the tickInterval cadence until
// ctx is cancelled or the returned stop function is called, and returns
// that stop function.
//
// No Rotate runs immediately on start: 17-07 calls Rotate once
// explicitly at boot so the startup reclaim is a distinct, observable
// log record. This ticker only handles the steady state.
//
// The stop function is sync.Once-guarded because main.go's shutdown
// path exercises BOTH exits — it cancels the context and calls stop —
// and an unguarded second close of the channel would panic during
// shutdown.
func (s *Store) StartRetentionTicker(ctx context.Context, retention time.Duration) func() {
	interval := tickInterval(retention)
	ticker := time.NewTicker(interval)
	done := make(chan struct{})

	go func() {
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-done:
				return
			case <-ticker.C:
				n, err := s.Rotate(retention)
				if err != nil {
					slog.Warn("runs.rotate_failed",
						"err", err.Error(),
						"deleted", n,
						"retention_hours", retention.Hours(),
					)
					continue
				}
				if n > 0 {
					slog.Info("runs.rotated",
						"deleted", n,
						"retention_hours", retention.Hours(),
					)
				}
			}
		}
	}()

	var once sync.Once
	return func() { once.Do(func() { close(done) }) }
}
