package runs

import (
	"context"
	"errors"
	"time"
)

// RED-phase stubs for the boot sweep and retention rotation.

// minTickInterval floors the rotation cadence.
const minTickInterval = 1 * time.Minute

var errRetentionNotImplemented = errors.New("runs: retention not implemented")

func (s *Store) SweepInterrupted() (int, error) { return 0, errRetentionNotImplemented }

func (s *Store) Rotate(maxAge time.Duration) (int, error) { return 0, errRetentionNotImplemented }

func (s *Store) StartRetentionTicker(ctx context.Context, retention time.Duration) func() {
	return func() {}
}

func tickInterval(retention time.Duration) time.Duration { return 0 }
