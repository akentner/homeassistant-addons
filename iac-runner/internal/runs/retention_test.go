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

func TestSweepInterruptedTransitionsRunningOnly(t *testing.T) {
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
	if n != 1 {
		t.Errorf("count: got %d want 1", n)
	}

	got, err := s.Load(running)
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

	untouched := map[string]contract.RunStatus{
		queued:      contract.RunStatusQueued,
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
