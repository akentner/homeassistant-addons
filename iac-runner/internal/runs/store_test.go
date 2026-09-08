package runs

import (
	"errors"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"iac-runner/internal/contract"
)

// fixedClock returns a now() function frozen at t. Every store test
// injects one so no assertion depends on wall-clock time.
func fixedClock(t time.Time) func() time.Time {
	return func() time.Time { return t }
}

// baseTime is the reference instant for every store test.
var baseTime = time.Date(2026, 9, 8, 10, 0, 0, 0, time.UTC)

// newTestStore builds a Store rooted in a fresh temp dir with a frozen
// clock.
func newTestStore(t *testing.T) *Store {
	t.Helper()
	s, err := NewStore(filepath.Join(t.TempDir(), "runs"), fixedClock(baseTime))
	if err != nil {
		t.Fatalf("NewStore: %v", err)
	}
	return s
}

// mustCreate seeds one run and fails the test if the store rejects it.
func mustCreate(t *testing.T, s *Store, m Meta) {
	t.Helper()
	if err := s.Create(m); err != nil {
		t.Fatalf("Create(%s): %v", m.RunID, err)
	}
}

// newRunID returns a fresh valid run id for seeding.
func newRunID(t *testing.T) string {
	t.Helper()
	id, err := NewRunID()
	if err != nil {
		t.Fatalf("NewRunID: %v", err)
	}
	return id
}

func TestStoreCreateLoadRoundTrip(t *testing.T) {
	s := newTestStore(t)
	id := newRunID(t)
	finished := baseTime.Add(90 * time.Second)

	want := Meta{
		RunID:      id,
		Repo:       "homelab-infra",
		Dir:        "envs/prod",
		Kind:       contract.RunKindApply,
		Status:     contract.RunStatusSucceeded,
		ExitCode:   nil,
		StartedAt:  baseTime,
		FinishedAt: &finished,
		ErrorCode:  "",
		PlanFile:   "/data/runs/" + id + "/plan.tfplan",
	}
	mustCreate(t, s, want)

	got, err := s.Load(id)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if got.RunID != want.RunID || got.Repo != want.Repo || got.Dir != want.Dir {
		t.Errorf("identity fields: got %+v want %+v", got, want)
	}
	if got.Kind != want.Kind || got.Status != want.Status {
		t.Errorf("kind/status: got %q/%q want %q/%q", got.Kind, got.Status, want.Kind, want.Status)
	}
	if got.ExitCode != nil {
		t.Errorf("ExitCode: got %v want nil", *got.ExitCode)
	}
	if !got.StartedAt.Equal(want.StartedAt) {
		t.Errorf("StartedAt: got %s want %s", got.StartedAt, want.StartedAt)
	}
	if got.FinishedAt == nil || !got.FinishedAt.Equal(finished) {
		t.Errorf("FinishedAt: got %v want %s", got.FinishedAt, finished)
	}
	if got.PlanFile != want.PlanFile {
		t.Errorf("PlanFile: got %q want %q", got.PlanFile, want.PlanFile)
	}
}

func TestStoreCreateLoadRoundTripKeepsExitCodeZero(t *testing.T) {
	s := newTestStore(t)
	id := newRunID(t)
	zero := 0
	mustCreate(t, s, Meta{
		RunID:     id,
		Kind:      contract.RunKindPlan,
		Status:    contract.RunStatusSucceeded,
		ExitCode:  &zero,
		StartedAt: baseTime,
	})

	got, err := s.Load(id)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if got.ExitCode == nil {
		t.Fatalf("ExitCode: got nil want pointer to 0")
	}
	if *got.ExitCode != 0 {
		t.Errorf("ExitCode: got %d want 0", *got.ExitCode)
	}
}

func TestStoreCreateSetsModes(t *testing.T) {
	s := newTestStore(t)
	id := newRunID(t)
	mustCreate(t, s, Meta{RunID: id, Status: contract.RunStatusQueued, StartedAt: baseTime})

	di, err := os.Stat(s.Dir(id))
	if err != nil {
		t.Fatalf("stat run dir: %v", err)
	}
	if got := di.Mode().Perm(); got != 0o700 {
		t.Errorf("run dir mode: got %#o want 0700", got)
	}

	fi, err := os.Stat(filepath.Join(s.Dir(id), "meta.json"))
	if err != nil {
		t.Fatalf("stat meta.json: %v", err)
	}
	if got := fi.Mode().Perm(); got != 0o600 {
		t.Errorf("meta.json mode: got %#o want 0600", got)
	}
}

func TestStoreLoadUnknownIDReturnsErrRunNotFound(t *testing.T) {
	s := newTestStore(t)

	t.Run("unknown but valid id", func(t *testing.T) {
		if _, err := s.Load(newRunID(t)); !errors.Is(err, ErrRunNotFound) {
			t.Errorf("got %v want ErrRunNotFound", err)
		}
	})

	t.Run("invalid id", func(t *testing.T) {
		for _, bad := range []string{"../etc", "", "aaaaaaaaaaaaaaaa", "AAAAAAAAAAAAAAA"} {
			if _, err := s.Load(bad); !errors.Is(err, ErrRunNotFound) {
				t.Errorf("Load(%q): got %v want ErrRunNotFound", bad, err)
			}
		}
	})

	t.Run("corrupt meta.json", func(t *testing.T) {
		id := newRunID(t)
		mustCreate(t, s, Meta{RunID: id, Status: contract.RunStatusQueued, StartedAt: baseTime})
		if err := os.WriteFile(filepath.Join(s.Dir(id), "meta.json"), []byte("{"), 0o600); err != nil {
			t.Fatalf("corrupt meta.json: %v", err)
		}
		if _, err := s.Load(id); !errors.Is(err, ErrRunNotFound) {
			t.Errorf("got %v want ErrRunNotFound", err)
		}
	})
}

func TestStoreUpdateConcurrent(t *testing.T) {
	s := newTestStore(t)
	id := newRunID(t)
	zero := 0
	mustCreate(t, s, Meta{
		RunID:     id,
		Status:    contract.RunStatusRunning,
		StartedAt: baseTime,
		ExitCode:  &zero,
	})

	const workers = 50
	var wg sync.WaitGroup
	errs := make(chan error, workers)
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, err := s.Update(id, func(m *Meta) error {
				n := 0
				if m.ExitCode != nil {
					n = *m.ExitCode
				}
				n++
				m.ExitCode = &n
				return nil
			})
			if err != nil {
				errs <- err
			}
		}()
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		t.Errorf("Update: %v", err)
	}

	got, err := s.Load(id)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if got.ExitCode == nil {
		t.Fatalf("ExitCode: got nil want %d", workers)
	}
	if *got.ExitCode != workers {
		t.Errorf("lost writes: ExitCode got %d want %d", *got.ExitCode, workers)
	}
}

func TestStoreUpdateNoTornReadUnderConcurrentLoad(t *testing.T) {
	s := newTestStore(t)
	id := newRunID(t)
	mustCreate(t, s, Meta{RunID: id, Status: contract.RunStatusRunning, StartedAt: baseTime})

	const iterations = 200
	var wg sync.WaitGroup
	writeErrs := make(chan error, iterations)
	readErrs := make(chan error, iterations)

	wg.Add(1)
	go func() {
		defer wg.Done()
		for i := 0; i < iterations; i++ {
			n := i
			if _, err := s.Update(id, func(m *Meta) error {
				m.ExitCode = &n
				m.ErrorCode = "still-running"
				return nil
			}); err != nil {
				writeErrs <- err
			}
		}
	}()

	wg.Add(1)
	go func() {
		defer wg.Done()
		for i := 0; i < iterations; i++ {
			if _, err := s.Load(id); err != nil {
				readErrs <- err
			}
		}
	}()

	wg.Wait()
	close(writeErrs)
	close(readErrs)
	for err := range writeErrs {
		t.Errorf("writer: %v", err)
	}
	for err := range readErrs {
		t.Errorf("reader observed torn state: %v", err)
	}
}

func TestStoreListOrdersByStartedAtDesc(t *testing.T) {
	s := newTestStore(t)
	oldest, middle, newest := newRunID(t), newRunID(t), newRunID(t)
	mustCreate(t, s, Meta{RunID: oldest, Status: contract.RunStatusSucceeded, StartedAt: baseTime})
	mustCreate(t, s, Meta{RunID: middle, Status: contract.RunStatusSucceeded, StartedAt: baseTime.Add(time.Hour)})
	mustCreate(t, s, Meta{RunID: newest, Status: contract.RunStatusSucceeded, StartedAt: baseTime.Add(2 * time.Hour)})

	got, err := s.List(ListFilter{})
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(got) != 3 {
		t.Fatalf("List length: got %d want 3", len(got))
	}
	want := []string{newest, middle, oldest}
	for i, id := range want {
		if got[i].RunID != id {
			t.Errorf("position %d: got %s want %s", i, got[i].RunID, id)
		}
	}
}

func TestStoreListFiltersAndCaps(t *testing.T) {
	t.Run("repo and status filters", func(t *testing.T) {
		s := newTestStore(t)
		a := newRunID(t)
		b := newRunID(t)
		c := newRunID(t)
		mustCreate(t, s, Meta{RunID: a, Repo: "infra", Status: contract.RunStatusSucceeded, StartedAt: baseTime})
		mustCreate(t, s, Meta{RunID: b, Repo: "infra", Status: contract.RunStatusFailed, StartedAt: baseTime.Add(time.Minute)})
		mustCreate(t, s, Meta{RunID: c, Repo: "other", Status: contract.RunStatusSucceeded, StartedAt: baseTime.Add(2 * time.Minute)})

		byRepo, err := s.List(ListFilter{Repo: "infra"})
		if err != nil {
			t.Fatalf("List by repo: %v", err)
		}
		if len(byRepo) != 2 {
			t.Errorf("repo filter: got %d want 2", len(byRepo))
		}

		byStatus, err := s.List(ListFilter{Status: contract.RunStatusSucceeded})
		if err != nil {
			t.Fatalf("List by status: %v", err)
		}
		if len(byStatus) != 2 {
			t.Errorf("status filter: got %d want 2", len(byStatus))
		}

		both, err := s.List(ListFilter{Repo: "infra", Status: contract.RunStatusFailed})
		if err != nil {
			t.Fatalf("List by repo+status: %v", err)
		}
		if len(both) != 1 || both[0].RunID != b {
			t.Errorf("repo+status filter: got %+v want only %s", both, b)
		}
	})

	t.Run("limit defaults and caps", func(t *testing.T) {
		s := newTestStore(t)
		for i := 0; i < contract.MaxRunListLimit+5; i++ {
			mustCreate(t, s, Meta{
				RunID:     newRunID(t),
				Repo:      "infra",
				Status:    contract.RunStatusSucceeded,
				StartedAt: baseTime.Add(time.Duration(i) * time.Minute),
			})
		}

		def, err := s.List(ListFilter{Limit: 0})
		if err != nil {
			t.Fatalf("List default limit: %v", err)
		}
		if len(def) != contract.DefaultRunListLimit {
			t.Errorf("default limit: got %d want %d", len(def), contract.DefaultRunListLimit)
		}

		capped, err := s.List(ListFilter{Limit: 500})
		if err != nil {
			t.Fatalf("List capped limit: %v", err)
		}
		if len(capped) != contract.MaxRunListLimit {
			t.Errorf("capped limit: got %d want %d", len(capped), contract.MaxRunListLimit)
		}

		explicit, err := s.List(ListFilter{Limit: 3})
		if err != nil {
			t.Fatalf("List explicit limit: %v", err)
		}
		if len(explicit) != 3 {
			t.Errorf("explicit limit: got %d want 3", len(explicit))
		}
	})

	t.Run("skips non-run directories and corrupt runs", func(t *testing.T) {
		s := newTestStore(t)
		good := newRunID(t)
		corrupt := newRunID(t)
		mustCreate(t, s, Meta{RunID: good, Status: contract.RunStatusSucceeded, StartedAt: baseTime})
		mustCreate(t, s, Meta{RunID: corrupt, Status: contract.RunStatusSucceeded, StartedAt: baseTime})
		if err := os.WriteFile(filepath.Join(s.Dir(corrupt), "meta.json"), []byte("{"), 0o600); err != nil {
			t.Fatalf("corrupt meta.json: %v", err)
		}
		if err := os.MkdirAll(filepath.Join(s.Dir(good), "..", "tmp"), 0o700); err != nil {
			t.Fatalf("mkdir tmp: %v", err)
		}

		got, err := s.List(ListFilter{})
		if err != nil {
			t.Fatalf("List: %v", err)
		}
		if len(got) != 1 || got[0].RunID != good {
			t.Errorf("got %+v want only %s", got, good)
		}
	})
}
