package runs

import "errors"

// RED-phase stubs for the JSONL output stream.

// OutputLine is one record of /data/runs/{run_id}/output.log.
type OutputLine struct {
	TS     string `json:"ts"`
	Stream string `json:"stream"`
	Line   string `json:"line"`
}

// OutputPage is a bounded, redacted window over output.log.
type OutputPage struct {
	Lines      []string
	Page       int
	PageSize   int
	TotalLines int
	Redactions int
}

// OutputWriter appends JSONL records to a run's output.log.
type OutputWriter struct{}

// maxScanLineBytes is the ceiling of the bufio.Scanner buffer.
const maxScanLineBytes = 8 * 1024 * 1024

var errOutputNotImplemented = errors.New("runs: output not implemented")

func (s *Store) OpenOutput(runID string) (*OutputWriter, error) {
	return nil, errOutputNotImplemented
}

func (w *OutputWriter) WriteLine(stream, line string) error { return errOutputNotImplemented }

func (w *OutputWriter) Close() error { return errOutputNotImplemented }

func (s *Store) ReadOutput(runID string, page, pageSize int) (OutputPage, error) {
	return OutputPage{}, errOutputNotImplemented
}
