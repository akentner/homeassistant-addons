package runs

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"iac-runner/internal/contract"
)

// seedFinished creates a run in a terminal state that finished `ago`
// before the store's frozen clock.
func seedFinished(t *testing.T, s *Store, status contract.RunStatus, ago time.Duration) string {
	t.Helper()
	id := newRunID(t)
	finished := baseTime.Add(-ago)
	mustCreate(t, s, Meta{
		RunID:      id,
		Repo:       "infra",
		Status:     status,
		StartedAt:  finished.Add(-time.Minute),
		FinishedAt: &finished,
	})
	return id
}

// seedActive creates a non-terminal run that started `ago` before the
// store's frozen clock and has no FinishedAt.
func seedActive(t *testing.T, s *Store, status contract.RunStatus, ago time.Duration) string {
	t.Helper()
	id := newRunID(t)
	mustCreate(t, s, Meta{
		RunID:     id,
		Repo:      "infra",
		Status:    status,
		StartedAt: baseTime.Add(-ago),
	})
	return id
}

// runDirExists reports whether the run directory is still on disk.
func runDirExists(t *testing.T, s *Store, runID string) bool {
	t.Helper()
	_, err := os.Stat(s.Dir(runID))
	if err == nil {
		return true
	}
	if os.IsNotExist(err) {
		return false
	}
	t.Fatalf("stat %s: %v", runID, err)
	return false
}

// TestSweepInterruptedTransitionsActiveRuns pins the D-02 sweep to
// the NON-TERMINAL statuses. `queued` is included (WR-06): the queue
// is in-process only (D-05), so a persisted queued run has no worker
// after a restart — and Rotate never touches a queued run, so leaving
// it would exempt the directory from retention permanently as well as
// showing the operator a job that never starts.
func TestSweepInterruptedTransitionsActiveRuns(t *testing.T) {
	s := newTestStore(t)

	running := seedActive(t, s, contract.RunStatusRunning, time.Hour)
	queued := seedActive(t, s, contract.RunStatusQueued, time.Hour)
	succeeded := seedFinished(t, s, contract.RunStatusSucceeded, time.Hour)
	failed := seedFinished(t, s, contract.RunStatusFailed, time.Hour)
	interrupted := seedFinished(t, s, contract.RunStatusInterrupted, time.Hour)

	n, err := s.SweepInterrupted()
	if err != nil {
		t.Fatalf("SweepInterrupted: %v", err)
	}
	if n != 2 {
		t.Errorf("count: got %d want 2 (running + queued)", n)
	}

	for _, id := range []string{running, queued} {
		got, err := s.Load(id)
		if err != nil {
			t.Fatalf("Load swept run: %v", err)
		}
		if got.Status != contract.RunStatusInterrupted {
			t.Errorf("swept run status: got %q want %q", got.Status, contract.RunStatusInterrupted)
		}
		if got.FinishedAt == nil {
			t.Errorf("swept run has no FinishedAt — the timeline is incomplete")
		} else if !got.FinishedAt.Equal(baseTime) {
			t.Errorf("swept run FinishedAt: got %s want %s", got.FinishedAt, baseTime)
		}
	}

	untouched := map[string]contract.RunStatus{
		succeeded:   contract.RunStatusSucceeded,
		failed:      contract.RunStatusFailed,
		interrupted: contract.RunStatusInterrupted,
	}
	for id, want := range untouched {
		m, err := s.Load(id)
		if err != nil {
			t.Fatalf("Load %s: %v", id, err)
		}
		if m.Status != want {
			t.Errorf("run %s: got status %q want %q", id, m.Status, want)
		}
	}
}

func TestSweepInterruptedSurvivesCorruptRun(t *testing.T) {
	s := newTestStore(t)

	running := seedActive(t, s, contract.RunStatusRunning, time.Hour)
	corrupt := seedActive(t, s, contract.RunStatusRunning, time.Hour)
	if err := os.WriteFile(filepath.Join(s.Dir(corrupt), "meta.json"), []byte("{"), 0o600); err != nil {
		t.Fatalf("corrupt meta.json: %v", err)
	}

	n, err := s.SweepInterrupted()
	if err != nil {
		t.Fatalf("SweepInterrupted must not fail on a corrupt run: %v", err)
	}
	if n != 1 {
		t.Errorf("count: got %d want 1", n)
	}
	m, err := s.Load(running)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if m.Status != contract.RunStatusInterrupted {
		t.Errorf("valid run status: got %q want interrupted", m.Status)
	}
}

func TestRotateDeletesOldFinishedRuns(t *testing.T) {
	s := newTestStore(t)

	old := seedFinished(t, s, contract.RunStatusSucceeded, 48*time.Hour)
	recent := seedFinished(t, s, contract.RunStatusSucceeded, time.Hour)

	n, err := s.Rotate(24 * time.Hour)
	if err != nil {
		t.Fatalf("Rotate: %v", err)
	}
	if n != 1 {
		t.Errorf("count: got %d want 1", n)
	}
	if runDirExists(t, s, old) {
		t.Errorf("run finished 48h ago still on disk")
	}
	if !runDirExists(t, s, recent) {
		t.Errorf("run finished 1h ago was deleted")
	}
}

func TestRotateSkipsActiveRuns(t *testing.T) {
	s := newTestStore(t)

	queued := seedActive(t, s, contract.RunStatusQueued, 100*time.Hour)
	running := seedActive(t, s, contract.RunStatusRunning, 100*time.Hour)

	n, err := s.Rotate(24 * time.Hour)
	if err != nil {
		t.Fatalf("Rotate: %v", err)
	}
	if n != 0 {
		t.Errorf("count: got %d want 0", n)
	}
	if !runDirExists(t, s, queued) || !runDirExists(t, s, running) {
		t.Errorf("Rotate deleted a live run directory")
	}
}

func TestRotateUsesStartedAtWhenFinishedAtNil(t *testing.T) {
	s := newTestStore(t)

	stale := seedActive(t, s, contract.RunStatusInterrupted, 72*time.Hour)

	n, err := s.Rotate(24 * time.Hour)
	if err != nil {
		t.Fatalf("Rotate: %v", err)
	}
	if n != 1 {
		t.Errorf("count: got %d want 1", n)
	}
	if runDirExists(t, s, stale) {
		t.Errorf("interrupted run with nil FinishedAt and old StartedAt survived rotation")
	}
}

func TestTickIntervalCadenceAndFloor(t *testing.T) {
	cases := []struct {
		name      string
		retention time.Duration
		want      time.Duration
	}{
		{name: "default 24h retention ticks every 6h", retention: 24 * time.Hour, want: 6 * time.Hour},
		{name: "schema minimum 1h retention ticks every 15m", retention: time.Hour, want: 15 * time.Minute},
		{name: "tiny retention is floored", retention: time.Minute, want: minTickInterval},
		{name: "zero retention is floored", retention: 0, want: minTickInterval},
		{name: "negative retention is floored", retention: -time.Hour, want: minTickInterval},
	}
	for _, tc := range cases {
		if got := tickInterval(tc.retention); got != tc.want {
			t.Errorf("%s: tickInterval(%s) got %s want %s", tc.name, tc.retention, got, tc.want)
		}
	}
}

func TestStartRetentionTickerStops(t *testing.T) {
	s := newTestStore(t)
	old := seedFinished(t, s, contract.RunStatusSucceeded, 100*time.Hour)

	ctx, cancel := context.WithCancel(context.Background())
	stop := s.StartRetentionTicker(ctx, time.Second)

	// The floor means a 1s retention still ticks no faster than
	// minTickInterval, so nothing may be rotated in this window.
	time.Sleep(150 * time.Millisecond)
	if !runDirExists(t, s, old) {
		t.Errorf("ticker rotated before minTickInterval elapsed — the floor is not applied")
	}

	// Both shutdown paths must be safe, in either order, more than
	// once: main.go cancels the context AND calls stop on shutdown.
	stop()
	stop()
	cancel()
	time.Sleep(50 * time.Millisecond)
}

func TestStartRetentionTickerStopsOnContextCancel(t *testing.T) {
	s := newTestStore(t)

	ctx, cancel := context.WithCancel(context.Background())
	stop := s.StartRetentionTicker(ctx, 24*time.Hour)
	cancel()
	time.Sleep(50 * time.Millisecond)
	stop()
}

// TestRotateReclaimsUnparseableRunDirectory is the WR-06 regression:
// a directory whose meta.json is missing or corrupt cannot be aged by
// its metadata, and skipping it made it exempt from retention forever.
// A disk-full episode (Create's MkdirAll succeeded, its writeMeta did
// not) therefore left permanent garbage under /data/runs that the
// add-on could not recover from without a manual rm -rf.
func TestRotateReclaimsUnparseableRunDirectory(t *testing.T) {
	s := newTestStore(t)

	// A meta-less directory, aged past retention.
	stillborn := newRunID(t)
	if err := os.MkdirAll(s.Dir(stillborn), 0o700); err != nil {
		t.Fatalf("mkdir stillborn: %v", err)
	}
	old := s.now().Add(-72 * time.Hour)
	if err := os.Chtimes(s.Dir(stillborn), old, old); err != nil {
		t.Fatalf("chtimes: %v", err)
	}

	// A corrupt meta.json, aged past retention.
	corrupt := seedFinished(t, s, contract.RunStatusSucceeded, 72*time.Hour)
	if err := os.WriteFile(filepath.Join(s.Dir(corrupt), "meta.json"), []byte("{"), 0o600); err != nil {
		t.Fatalf("corrupt meta.json: %v", err)
	}
	if err := os.Chtimes(s.Dir(corrupt), old, old); err != nil {
		t.Fatalf("chtimes: %v", err)
	}

	// A meta-less directory being created RIGHT NOW must survive.
	fresh := newRunID(t)
	if err := os.MkdirAll(s.Dir(fresh), 0o700); err != nil {
		t.Fatalf("mkdir fresh: %v", err)
	}

	n, err := s.Rotate(24 * time.Hour)
	if err != nil {
		t.Fatalf("Rotate: %v", err)
	}
	if n != 2 {
		t.Errorf("deleted %d, want 2 (the stillborn and the corrupt directory)", n)
	}
	if runDirExists(t, s, stillborn) {
		t.Errorf("a meta-less directory older than retention is still on disk")
	}
	if runDirExists(t, s, corrupt) {
		t.Errorf("a corrupt run directory older than retention is still on disk")
	}
	if !runDirExists(t, s, fresh) {
		t.Errorf("Rotate deleted a run directory that is mid-creation")
	}
}
