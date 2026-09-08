package runs

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"iac-runner/internal/contract"
)

// seedRun creates one run and returns its id, ready for output writes.
func seedRun(t *testing.T, s *Store) string {
	t.Helper()
	id := newRunID(t)
	mustCreate(t, s, Meta{RunID: id, Status: contract.RunStatusRunning, StartedAt: baseTime})
	return id
}

// rawOutput returns the untouched bytes of a run's output.log — the
// D-08 invariant is asserted against this, never against ReadOutput.
func rawOutput(t *testing.T, s *Store, runID string) string {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(s.Dir(runID), "output.log"))
	if err != nil {
		t.Fatalf("read raw output.log: %v", err)
	}
	return string(b)
}

func TestWriteLineProducesJSONL(t *testing.T) {
	s := newTestStore(t)
	id := seedRun(t, s)

	w, err := s.OpenOutput(id)
	if err != nil {
		t.Fatalf("OpenOutput: %v", err)
	}
	want := []OutputLine{
		{TS: baseTime.Format(time.RFC3339), Stream: "stdout", Line: "Initializing the backend..."},
		{TS: baseTime.Format(time.RFC3339), Stream: "stderr", Line: "Warning: deprecated attribute"},
		{TS: baseTime.Format(time.RFC3339), Stream: "stdout", Line: "Plan: 1 to add, 0 to change, 0 to destroy."},
	}
	for _, l := range want {
		if err := w.WriteLine(l.Stream, l.Line); err != nil {
			t.Fatalf("WriteLine: %v", err)
		}
	}
	if err := w.Close(); err != nil {
		t.Fatalf("Close: %v", err)
	}

	physical := strings.Split(strings.TrimRight(rawOutput(t, s, id), "\n"), "\n")
	if len(physical) != len(want) {
		t.Fatalf("physical lines: got %d want %d", len(physical), len(want))
	}
	for i, raw := range physical {
		var got OutputLine
		if err := json.Unmarshal([]byte(raw), &got); err != nil {
			t.Fatalf("line %d is not JSON: %v (%q)", i, err, raw)
		}
		if got != want[i] {
			t.Errorf("line %d: got %+v want %+v", i, got, want[i])
		}
	}
}

func TestWriteLineNoTruncation(t *testing.T) {
	s := newTestStore(t)
	id := seedRun(t, s)

	long := strings.Repeat("x", 10*1024)
	tricky := "quote \" backslash \\ newline \n tab \t end"

	w, err := s.OpenOutput(id)
	if err != nil {
		t.Fatalf("OpenOutput: %v", err)
	}
	for _, l := range []string{long, tricky} {
		if err := w.WriteLine("stdout", l); err != nil {
			t.Fatalf("WriteLine: %v", err)
		}
	}
	if err := w.Close(); err != nil {
		t.Fatalf("Close: %v", err)
	}

	page, err := s.ReadOutput(id, 1, contract.DefaultOutputPageSize)
	if err != nil {
		t.Fatalf("ReadOutput: %v", err)
	}
	if page.TotalLines != 2 {
		t.Fatalf("TotalLines: got %d want 2", page.TotalLines)
	}
	if len(page.Lines) != 2 {
		t.Fatalf("Lines: got %d want 2", len(page.Lines))
	}
	if page.Lines[0] != long {
		t.Errorf("long line: got %d chars want %d", len(page.Lines[0]), len(long))
	}
	if page.Lines[1] != tricky {
		t.Errorf("tricky line: got %q want %q", page.Lines[1], tricky)
	}
}

func TestReadOutputHandlesLineBeyondScannerCeiling(t *testing.T) {
	s := newTestStore(t)
	id := seedRun(t, s)

	huge := strings.Repeat("y", maxScanLineBytes+1024)
	w, err := s.OpenOutput(id)
	if err != nil {
		t.Fatalf("OpenOutput: %v", err)
	}
	if err := w.WriteLine("stdout", huge); err != nil {
		t.Fatalf("WriteLine: %v", err)
	}
	if err := w.WriteLine("stdout", "after the huge line"); err != nil {
		t.Fatalf("WriteLine: %v", err)
	}
	if err := w.Close(); err != nil {
		t.Fatalf("Close: %v", err)
	}

	page, err := s.ReadOutput(id, 1, contract.DefaultOutputPageSize)
	if err != nil {
		t.Fatalf("ReadOutput: %v", err)
	}
	if page.TotalLines != 2 {
		t.Fatalf("TotalLines: got %d want 2", page.TotalLines)
	}
	if len(page.Lines) != 2 || len(page.Lines[0]) != len(huge) {
		t.Fatalf("huge line: got %d chars want %d", len(page.Lines[0]), len(huge))
	}
	if page.Lines[1] != "after the huge line" {
		t.Errorf("line after huge: got %q", page.Lines[1])
	}
}

func TestReadOutputPagination(t *testing.T) {
	s := newTestStore(t)
	id := seedRun(t, s)

	w, err := s.OpenOutput(id)
	if err != nil {
		t.Fatalf("OpenOutput: %v", err)
	}
	const total = 250
	for i := 0; i < total; i++ {
		if err := w.WriteLine("stdout", fmt.Sprintf("line-%d", i)); err != nil {
			t.Fatalf("WriteLine: %v", err)
		}
	}
	if err := w.Close(); err != nil {
		t.Fatalf("Close: %v", err)
	}

	cases := []struct {
		page      int
		wantLen   int
		wantFirst string
	}{
		{page: 1, wantLen: 100, wantFirst: "line-0"},
		{page: 2, wantLen: 100, wantFirst: "line-100"},
		{page: 3, wantLen: 50, wantFirst: "line-200"},
		{page: 4, wantLen: 0},
	}
	for _, tc := range cases {
		page, err := s.ReadOutput(id, tc.page, 100)
		if err != nil {
			t.Fatalf("ReadOutput(page=%d): %v", tc.page, err)
		}
		if page.TotalLines != total {
			t.Errorf("page %d TotalLines: got %d want %d", tc.page, page.TotalLines, total)
		}
		if len(page.Lines) != tc.wantLen {
			t.Fatalf("page %d length: got %d want %d", tc.page, len(page.Lines), tc.wantLen)
		}
		if tc.wantLen > 0 && page.Lines[0] != tc.wantFirst {
			t.Errorf("page %d first line: got %q want %q", tc.page, page.Lines[0], tc.wantFirst)
		}
		if page.Page != tc.page {
			t.Errorf("page %d echoed Page: got %d", tc.page, page.Page)
		}
	}
}

func TestReadOutputClampsPageSize(t *testing.T) {
	s := newTestStore(t)
	id := seedRun(t, s)

	w, err := s.OpenOutput(id)
	if err != nil {
		t.Fatalf("OpenOutput: %v", err)
	}
	for i := 0; i < contract.MaxOutputPageSize+50; i++ {
		if err := w.WriteLine("stdout", fmt.Sprintf("line-%d", i)); err != nil {
			t.Fatalf("WriteLine: %v", err)
		}
	}
	if err := w.Close(); err != nil {
		t.Fatalf("Close: %v", err)
	}

	zero, err := s.ReadOutput(id, 1, 0)
	if err != nil {
		t.Fatalf("ReadOutput(pageSize=0): %v", err)
	}
	if zero.PageSize != contract.DefaultOutputPageSize || len(zero.Lines) != contract.DefaultOutputPageSize {
		t.Errorf("pageSize 0: got PageSize=%d len=%d want %d", zero.PageSize, len(zero.Lines), contract.DefaultOutputPageSize)
	}

	over, err := s.ReadOutput(id, 1, 5000)
	if err != nil {
		t.Fatalf("ReadOutput(pageSize=5000): %v", err)
	}
	if over.PageSize != contract.MaxOutputPageSize || len(over.Lines) != contract.MaxOutputPageSize {
		t.Errorf("pageSize 5000: got PageSize=%d len=%d want %d", over.PageSize, len(over.Lines), contract.MaxOutputPageSize)
	}

	zeroPage, err := s.ReadOutput(id, 0, 10)
	if err != nil {
		t.Fatalf("ReadOutput(page=0): %v", err)
	}
	if zeroPage.Page != 1 || len(zeroPage.Lines) != 10 || zeroPage.Lines[0] != "line-0" {
		t.Errorf("page 0 should behave as page 1: got Page=%d first=%q", zeroPage.Page, zeroPage.Lines[0])
	}
}

func TestReadOutputRedactsAndCounts(t *testing.T) {
	s := newTestStore(t)
	id := seedRun(t, s)

	secretLine := "r2_access_key_id = " + r2Key
	pemLine := "-----BEGIN OPENSSH PRIVATE KEY-----"

	w, err := s.OpenOutput(id)
	if err != nil {
		t.Fatalf("OpenOutput: %v", err)
	}
	for _, l := range []string{secretLine, pemLine, "Plan: 1 to add, 0 to change, 0 to destroy."} {
		if err := w.WriteLine("stdout", l); err != nil {
			t.Fatalf("WriteLine: %v", err)
		}
	}
	if err := w.Close(); err != nil {
		t.Fatalf("Close: %v", err)
	}

	page, err := s.ReadOutput(id, 1, contract.DefaultOutputPageSize)
	if err != nil {
		t.Fatalf("ReadOutput: %v", err)
	}
	joined := strings.Join(page.Lines, "\n")
	if strings.Contains(joined, r2Key) {
		t.Errorf("R2 key leaked into the API payload: %q", joined)
	}
	if strings.Contains(joined, "BEGIN OPENSSH") {
		t.Errorf("PEM header leaked into the API payload: %q", joined)
	}
	if page.Redactions != 2 {
		t.Errorf("Redactions: got %d want 2", page.Redactions)
	}

	// D-08: redaction happens at READ time only. The raw file under
	// /data must still hold the secrets so an operator can debug.
	raw := rawOutput(t, s, id)
	if !strings.Contains(raw, r2Key) {
		t.Errorf("on-disk output.log lost the raw R2 key — redaction leaked into the write path")
	}
	if !strings.Contains(raw, "BEGIN OPENSSH") {
		t.Errorf("on-disk output.log lost the raw PEM header — redaction leaked into the write path")
	}
}

func TestReadOutputMissingFileIsEmptyPage(t *testing.T) {
	s := newTestStore(t)
	id := seedRun(t, s)

	page, err := s.ReadOutput(id, 1, contract.DefaultOutputPageSize)
	if err != nil {
		t.Fatalf("ReadOutput on a run with no output: %v", err)
	}
	if page.TotalLines != 0 || len(page.Lines) != 0 {
		t.Errorf("empty page: got TotalLines=%d len=%d", page.TotalLines, len(page.Lines))
	}
	if page.Page != 1 || page.PageSize != contract.DefaultOutputPageSize {
		t.Errorf("empty page echo: got Page=%d PageSize=%d", page.Page, page.PageSize)
	}
}

func TestReadOutputUnknownRunIsNotFound(t *testing.T) {
	s := newTestStore(t)
	if _, err := s.ReadOutput("../etc", 1, 10); err == nil {
		t.Errorf("ReadOutput on an invalid id: got nil error")
	}
}

func TestWriteLineConcurrentStreams(t *testing.T) {
	s := newTestStore(t)
	id := seedRun(t, s)

	w, err := s.OpenOutput(id)
	if err != nil {
		t.Fatalf("OpenOutput: %v", err)
	}

	const perStream = 200
	var wg sync.WaitGroup
	for _, stream := range []string{"stdout", "stderr"} {
		wg.Add(1)
		go func(stream string) {
			defer wg.Done()
			for i := 0; i < perStream; i++ {
				if err := w.WriteLine(stream, fmt.Sprintf("%s-%d", stream, i)); err != nil {
					t.Errorf("WriteLine(%s): %v", stream, err)
					return
				}
			}
		}(stream)
	}
	wg.Wait()
	if err := w.Close(); err != nil {
		t.Fatalf("Close: %v", err)
	}

	raw := strings.Split(strings.TrimRight(rawOutput(t, s, id), "\n"), "\n")
	if len(raw) != 2*perStream {
		t.Fatalf("physical lines: got %d want %d", len(raw), 2*perStream)
	}
	counts := map[string]int{}
	for i, l := range raw {
		var rec OutputLine
		if err := json.Unmarshal([]byte(l), &rec); err != nil {
			t.Fatalf("record %d interleaved mid-object: %v (%q)", i, err, l)
		}
		counts[rec.Stream]++
	}
	if counts["stdout"] != perStream || counts["stderr"] != perStream {
		t.Errorf("per-stream counts: got %v want %d each", counts, perStream)
	}
}
