package runs

import (
	"errors"
	"time"

	"iac-runner/internal/contract"
)

// ErrRunNotFound is the sentinel every "this run is not readable"
// condition maps to.
var ErrRunNotFound = errors.New("runs: run not found")

// Meta is the persisted state of one run.
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
	PlanFile   string             `json:"plan_file,omitempty"`
}

// ListFilter narrows a List call.
type ListFilter struct {
	Repo   string
	Status contract.RunStatus
	Limit  int
}

// Store is the durable run store. RED-phase stub.
type Store struct {
	runsDir string
	now     func() time.Time
}

var errNotImplemented = errors.New("runs: store not implemented")

func NewStore(runsDir string, now func() time.Time) (*Store, error) {
	return nil, errNotImplemented
}

func (s *Store) Dir(runID string) string { return "" }

func (s *Store) Create(m Meta) error { return errNotImplemented }

func (s *Store) Load(runID string) (Meta, error) { return Meta{}, errNotImplemented }

func (s *Store) Update(runID string, mutate func(*Meta) error) (Meta, error) {
	return Meta{}, errNotImplemented
}

func (s *Store) List(f ListFilter) ([]Meta, error) { return nil, errNotImplemented }
