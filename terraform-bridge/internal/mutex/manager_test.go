package mutex

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func TestManagerSameSlugSerializes(t *testing.T) {
	m := NewManager()
	ctx := context.Background()

	release1, err := m.TryAcquire(ctx, "core_mosquitto")
	if err != nil {
		t.Fatalf("first acquire: %v", err)
	}

	// Start a goroutine that tries to acquire the same slug.
	// Since release1 has not been called yet, the attempt must
	// block until we release.
	got := make(chan time.Duration, 1)
	go func() {
		start := time.Now()
		release2, err := m.TryAcquire(ctx, "core_mosquitto")
		if err != nil {
			t.Errorf("second acquire: %v", err)
			return
		}
		got <- time.Since(start)
		release2()
	}()

	// Hold the lock for ~100ms.
	time.Sleep(100 * time.Millisecond)

	acquiredAt := time.Now()
	release1()

	// The second goroutine must NOT have acquired yet (we just
	// released) - give it a chance.
	select {
	case elapsed := <-got:
		releaseAt := time.Now()
		acquiredLatency := releaseAt.Sub(acquiredAt)
		// Goroutine 2 should not have acquired BEFORE release1
		// returned; it must take >= 0ms after release. Allow a
		// tiny scheduling window.
		if acquiredLatency < 0 {
			acquiredLatency = 0
		}
		if elapsed < 50*time.Millisecond {
			t.Errorf("second acquire elapsed = %v, want >= 50ms (should have waited for first release)", elapsed)
		}
		_ = acquiredLatency
	case <-time.After(2 * time.Second):
		t.Fatal("second acquire did not return within 2s after release")
	}
}

func TestManagerDifferentSlugsParallel(t *testing.T) {
	m := NewManager()
	ctx := context.Background()

	release1, err := m.TryAcquire(ctx, "core_mosquitto")
	if err != nil {
		t.Fatalf("first acquire: %v", err)
	}
	defer release1()

	// A different slug should acquire immediately - no waiting.
	start := time.Now()
	release2, err := m.TryAcquire(ctx, "core_zigbee2mqtt")
	elapsed := time.Since(start)
	if err != nil {
		t.Fatalf("different-slug acquire: %v", err)
	}
	defer release2()

	// Allow up to 50ms for scheduling - should be well under 100ms.
	if elapsed > 50*time.Millisecond {
		t.Errorf("different-slug acquire took %v, want < 50ms (locks must NOT be global)", elapsed)
	}
}

func TestManagerTryAcquireTimeout(t *testing.T) {
	m := NewManager()
	ctx := context.Background()

	release1, err := m.TryAcquire(ctx, "core_mosquitto")
	if err != nil {
		t.Fatalf("first acquire: %v", err)
	}
	defer release1()

	// Hold release1; meanwhile, a fresh ctx with 50ms deadline
	// attempts acquire - must return ErrLockedTimeout promptly.
	ctx2, cancel := context.WithTimeout(ctx, 50*time.Millisecond)
	defer cancel()

	start := time.Now()
	_, err = m.TryAcquire(ctx2, "core_mosquitto")
	elapsed := time.Since(start)
	if err == nil {
		t.Fatal("expected ErrLockedTimeout, got nil")
	}
	if !errors.Is(err, ErrLockedTimeout) {
		t.Errorf("err = %v, want ErrLockedTimeout (errors.Is)", err)
	}
	// Must return in approximately the deadline window, well
	// under 100ms total response latency per CONTEXT pitfall 2.
	if elapsed > 150*time.Millisecond {
		t.Errorf("TryAcquire took %v, want < 150ms (deadline was 50ms)", elapsed)
	}
}

func TestManagerReleaseUnblocks(t *testing.T) {
	m := NewManager()
	ctx := context.Background()

	release1, err := m.TryAcquire(ctx, "core_mosquitto")
	if err != nil {
		t.Fatalf("first acquire: %v", err)
	}

	done := make(chan struct{})
	var observed atomic.Bool
	go func() {
		defer close(done)
		release2, err := m.TryAcquire(ctx, "core_mosquitto")
		if err != nil {
			t.Errorf("second acquire: %v", err)
			return
		}
		observed.Store(true)
		release2()
	}()

	// Give the goroutine a moment to actually be queued waiting
	// on the lock.
	time.Sleep(20 * time.Millisecond)

	if observed.Load() {
		t.Fatalf("second acquire observed before release - serialization broken")
	}

	release1()

	select {
	case <-done:
		if !observed.Load() {
			t.Fatal("second acquire returned but observed flag not set")
		}
	case <-time.After(2 * time.Second):
		t.Fatal("second acquire did not return within 2s after release")
	}
}

func TestManagerReleaseCalledOnce(t *testing.T) {
	m := NewManager()
	ctx := context.Background()

	release, err := m.TryAcquire(ctx, "core_mosquitto")
	if err != nil {
		t.Fatalf("acquire: %v", err)
	}

	// Calling release twice must NOT panic (sync.Once guards
	// the Unlock internally).
	release()
	release()

	// And we can acquire + release again afterward.
	release2, err := m.TryAcquire(ctx, "core_mosquitto")
	if err != nil {
		t.Fatalf("second acquire: %v", err)
	}
	release2()
}

func TestManagerManySlugsSameTime(t *testing.T) {
	m := NewManager()
	ctx := context.Background()

	var wg sync.WaitGroup
	const N = 50
	for i := 0; i < N; i++ {
		slug := string(rune('A' + i%26))
		wg.Add(1)
		go func(s string) {
			defer wg.Done()
			release, err := m.TryAcquire(ctx, s)
			if err != nil {
				t.Errorf("acquire %s: %v", s, err)
				return
			}
			time.Sleep(5 * time.Millisecond)
			release()
		}(slug)
	}
	wg.Wait()
}
