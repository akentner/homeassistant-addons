package runs

// The output.log half of the CONTEXT D-01 run layout: per-line capture
// of tofu stdout/stderr (OBS-02) and the paginated, redacted read path
// the run-detail response is built from (OBS-03, SEC-03).
//
// Two invariants drive the whole file:
//   - D-09 / D-24: lines are written VERBATIM. There is no maximum line
//     length anywhere in the write path. Bounding the API response is
//     pagination's job, not the writer's.
//   - D-08: redaction happens at READ time. The bytes under /data stay
//     raw so an operator can debug with `cat … | jq`.

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"iac-runner/internal/contract"
)

// outputFileName is the per-run captured-output file (CONTEXT D-01).
const outputFileName = "output.log"

// initialScanBufBytes is the starting size of the read buffer. Most
// tofu lines are well under 64 KiB, so this is the common-case
// allocation; the scanner grows it on demand up to maxScanLineBytes.
const initialScanBufBytes = 64 * 1024

// maxScanLineBytes is the ceiling of the bufio.Scanner buffer. It is
// the read-side consequence of the no-truncation decision (D-09/D-24):
// because the writer never shortens a line, the reader must be able to
// swallow a multi-megabyte one. A line past this ceiling is not lost
// either — ReadOutput falls back to bufio.Reader.ReadString, which has
// no per-line limit at all.
const maxScanLineBytes = 8 * 1024 * 1024

// OutputLine is one record of /data/runs/{run_id}/output.log
// (CONTEXT D-07). One JSON object per physical file line — JSONL — so
// an operator can stream it through jq and filter a single stream:
//
//	cat /data/runs/ABC…/output.log | jq -r 'select(.stream=="stderr").line'
type OutputLine struct {
	TS     string `json:"ts"`
	Stream string `json:"stream"`
	Line   string `json:"line"`
}

// OutputPage is a bounded window over one run's output, already
// redacted (SEC-03). TotalLines counts the WHOLE file, not the window,
// so a client can page through a long apply without a second call to
// discover the length. Redactions is the per-page count the handler
// surfaces in its `redaction.audit` record.
type OutputPage struct {
	Lines      []string
	Page       int
	PageSize   int
	TotalLines int
	Redactions int
}

// OutputWriter appends JSONL records to one run's output.log.
//
// The mutex is load-bearing: tofu's stdout and stderr are captured by
// two separate goroutines, and without serialization their JSON
// objects interleave mid-object and the file stops being parseable.
type OutputWriter struct {
	mu  sync.Mutex
	f   *os.File
	enc *json.Encoder
	now func() time.Time
}

// OpenOutput opens (creating if needed) the append-only output.log of
// runID. The file is opened with os.O_APPEND so a restart of the
// capture loop extends the log instead of truncating it, and with mode
// 0600 — the run output can contain anything tofu printed, so it is
// treated as sensitive on disk even though the API redacts it.
func (s *Store) OpenOutput(runID string) (*OutputWriter, error) {
	dir := s.Dir(runID)
	if dir == "" {
		return nil, fmt.Errorf("%w: %q", ErrRunNotFound, runID)
	}
	f, err := os.OpenFile(filepath.Join(dir, outputFileName), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o600)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, fmt.Errorf("%w: %s", ErrRunNotFound, runID)
		}
		return nil, fmt.Errorf("runs: open output.log: %w", err)
	}
	return &OutputWriter{f: f, enc: json.NewEncoder(f), now: s.now}, nil
}

// WriteLine appends one JSONL record. stream is "stdout" or "stderr";
// line is written verbatim — no truncation, no trimming (D-09/D-24).
// json.Encoder.Encode appends the newline that makes the file JSONL.
func (w *OutputWriter) WriteLine(stream, line string) error {
	w.mu.Lock()
	defer w.mu.Unlock()
	rec := OutputLine{
		TS:     w.now().UTC().Format(time.RFC3339),
		Stream: stream,
		Line:   line,
	}
	if err := w.enc.Encode(rec); err != nil {
		return fmt.Errorf("runs: write output line: %w", err)
	}
	return nil
}

// Close flushes and closes the underlying file. It is safe to call
// once; a second call returns the os.File error.
func (w *OutputWriter) Close() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if err := w.f.Close(); err != nil {
		return fmt.Errorf("runs: close output.log: %w", err)
	}
	return nil
}

// ReadOutput returns the requested page of runID's output, redacted
// per SEC-03 / D-08.
//
// Clamping follows OBS-03 and uses the shared contract constants so
// the handler and the store cannot drift: page < 1 becomes 1,
// pageSize <= 0 becomes contract.DefaultOutputPageSize, and a pageSize
// above contract.MaxOutputPageSize is capped.
//
// A missing output.log is NOT an error — a queued run has simply
// produced nothing yet — and yields an empty page with TotalLines 0.
// A page past the end likewise yields an empty slice, so a client that
// walks pages until it gets nothing back needs no special case.
func (s *Store) ReadOutput(runID string, page, pageSize int) (OutputPage, error) {
	dir := s.Dir(runID)
	if dir == "" {
		return OutputPage{}, fmt.Errorf("%w: %q", ErrRunNotFound, runID)
	}
	if page < 1 {
		page = 1
	}
	if pageSize <= 0 {
		pageSize = contract.DefaultOutputPageSize
	}
	if pageSize > contract.MaxOutputPageSize {
		pageSize = contract.MaxOutputPageSize
	}

	c := &windowCollector{lo: (page - 1) * pageSize, hi: page * pageSize}
	path := filepath.Join(dir, outputFileName)

	err := withOutputFile(path, func(f *os.File) error { return collectScanner(f, c) })
	if errors.Is(err, bufio.ErrTooLong) {
		// A line exceeded maxScanLineBytes. Nothing is truncated:
		// discard the partial pass and re-read with bufio.Reader,
		// which has no per-line ceiling.
		c.reset()
		err = withOutputFile(path, func(f *os.File) error { return collectReader(f, c) })
	}
	if err != nil {
		return OutputPage{}, err
	}

	return OutputPage{
		Lines:      c.lines,
		Page:       page,
		PageSize:   pageSize,
		TotalLines: c.total,
		Redactions: c.redactions,
	}, nil
}

// withOutputFile opens path and hands it to fn. A missing file is a
// no-op success (see ReadOutput's contract).
func withOutputFile(path string, fn func(*os.File) error) error {
	f, err := os.Open(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil
		}
		return fmt.Errorf("runs: open output.log: %w", err)
	}
	defer f.Close()
	return fn(f)
}

// windowCollector counts every record in the file but only unmarshals,
// redacts and keeps the ones inside [lo, hi). Doing the cheap work for
// the whole file and the expensive work for one page is what lets
// TotalLines be exact without holding a multi-megabyte log in memory.
type windowCollector struct {
	lo, hi     int
	lines      []string
	total      int
	redactions int
}

// add ingests one raw physical line.
func (c *windowCollector) add(raw string) {
	i := c.total
	c.total++
	if i < c.lo || i >= c.hi {
		return
	}
	text := raw
	var rec OutputLine
	if err := json.Unmarshal([]byte(raw), &rec); err == nil {
		text = rec.Line
	}
	// A record that does not parse is surfaced as its raw text: the
	// final line of a RUNNING job is routinely half-flushed, and
	// dropping it would look to the operator like missing output.
	redacted, n := Redact(text)
	c.redactions += n
	c.lines = append(c.lines, redacted)
}

// reset clears accumulated state so a failed pass can be retried with
// a different reader.
func (c *windowCollector) reset() {
	c.lines = nil
	c.total = 0
	c.redactions = 0
}

// collectScanner is the common read path: a bufio.Scanner with an
// enlarged buffer.
func collectScanner(f *os.File, c *windowCollector) error {
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, initialScanBufBytes), maxScanLineBytes)
	for sc.Scan() {
		c.add(sc.Text())
	}
	if err := sc.Err(); err != nil {
		if errors.Is(err, bufio.ErrTooLong) {
			return err // ReadOutput retries with collectReader
		}
		return fmt.Errorf("runs: scan output.log: %w", err)
	}
	return nil
}

// collectReader is the fallback for a line past maxScanLineBytes.
// bufio.Reader.ReadString has no per-line limit, so no output is ever
// lost to its own size — the price is one allocation per line.
func collectReader(f *os.File, c *windowCollector) error {
	r := bufio.NewReaderSize(f, initialScanBufBytes)
	for {
		s, err := r.ReadString('\n')
		if len(s) > 0 {
			c.add(strings.TrimRight(s, "\r\n"))
		}
		if err != nil {
			if errors.Is(err, io.EOF) {
				return nil
			}
			return fmt.Errorf("runs: read output.log: %w", err)
		}
	}
}
