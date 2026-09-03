package state

import (
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"testing"
)

func TestIndexEnumeratesTfstateAndBackup(t *testing.T) {
	dir := t.TempDir()

	canonical := []byte(`{"version":4,"terraform_version":"1.0"}`)
	backup := []byte(`{"version":4,"backup":true}`)

	mustWrite(t, filepath.Join(dir, "terraform.tfstate"), canonical)
	mustWrite(t, filepath.Join(dir, "terraform.tfstate.backup"), backup)
	mustWrite(t, filepath.Join(dir, "other.tfstate"), canonical)
	mustWrite(t, filepath.Join(dir, "terraform.tfstate.lock"), []byte("{}"))
	mustWrite(t, filepath.Join(dir, "README.md"), []byte("not state"))

	files, skipped, err := Index(dir)
	if err != nil {
		t.Fatalf("Index: %v", err)
	}
	if len(skipped) != 0 {
		t.Errorf("skipped = %d, want 0: %+v", len(skipped), skipped)
	}

	want := map[string]int64{
		"terraform.tfstate":        int64(len(canonical)),
		"terraform.tfstate.backup": int64(len(backup)),
		"other.tfstate":            int64(len(canonical)),
	}
	if len(files) != len(want) {
		t.Fatalf("got %d files, want %d: %+v", len(files), len(want), files)
	}
	for _, f := range files {
		expectedSize, ok := want[f.Name]
		if !ok {
			t.Errorf("unexpected file %q in Index result", f.Name)
			continue
		}
		delete(want, f.Name)
		if f.SizeBytes != expectedSize {
			t.Errorf("file %q size = %d, want %d", f.Name, f.SizeBytes, expectedSize)
		}
		if !regexp.MustCompile(`^[a-f0-9]{64}$`).MatchString(f.SHA256) {
			t.Errorf("file %q sha256 = %q, want hex64", f.Name, f.SHA256)
		}
	}
	for name := range want {
		t.Errorf("missing file %q in Index result", name)
	}
}

func TestIndexEmptyDirectory(t *testing.T) {
	dir := t.TempDir()
	files, skipped, err := Index(dir)
	if err != nil {
		t.Fatalf("Index: %v", err)
	}
	if len(files) != 0 {
		t.Errorf("files = %+v, want empty", files)
	}
	if len(skipped) != 0 {
		t.Errorf("skipped = %+v, want empty", skipped)
	}
	// Test infrastructure should give back []FileEntry{}, not nil,
	// so the JSON serializes as [] not null.
	if files == nil {
		t.Error("files is nil, want []FileEntry{} (for JSON encoding)")
	}
}

func TestIndexSkipsLockedFiles(t *testing.T) {
	dir := t.TempDir()
	mustWrite(t, filepath.Join(dir, "terraform.tfstate.lock"), []byte("lock"))

	files, _, err := Index(dir)
	if err != nil {
		t.Fatalf("Index: %v", err)
	}
	if len(files) != 0 {
		t.Errorf("files = %+v, want empty (D-20 must skip .tfstate.lock)", files)
	}
}

func TestIndexSHA256IsHex(t *testing.T) {
	dir := t.TempDir()
	mustWrite(t, filepath.Join(dir, "a.tfstate"), []byte("hello"))

	files, _, err := Index(dir)
	if err != nil {
		t.Fatalf("Index: %v", err)
	}
	if len(files) != 1 {
		t.Fatalf("files len = %d, want 1", len(files))
	}
	if len(files[0].SHA256) != 64 {
		t.Errorf("sha256 length = %d, want 64", len(files[0].SHA256))
	}
	if !regexp.MustCompile(`^[a-f0-9]{64}$`).MatchString(files[0].SHA256) {
		t.Errorf("sha256 = %q, want lowercase hex", files[0].SHA256)
	}
}

func TestIndexAccumulatesSkippedOnPermissionDenied(t *testing.T) {
	if os.Getuid() == 0 {
		t.Skip("running as root, permission denied not testable")
	}
	dir := t.TempDir()

	good := filepath.Join(dir, "good.tfstate")
	mustWrite(t, good, []byte("ok"))

	bad := filepath.Join(dir, "bad.tfstate")
	mustWrite(t, bad, []byte("nope"))
	if err := os.Chmod(bad, 0o000); err != nil {
		t.Fatalf("chmod: %v", err)
	}
	t.Cleanup(func() { _ = os.Chmod(bad, 0o600) })

	files, skipped, err := Index(dir)
	if err != nil {
		t.Fatalf("Index: %v", err)
	}
	if len(files) != 1 || files[0].Name != "good.tfstate" {
		t.Errorf("files = %+v, want exactly the readable file", files)
	}
	if len(skipped) != 1 || skipped[0].Name != "bad.tfstate" {
		t.Errorf("skipped = %+v, want one entry for bad.tfstate", skipped)
	}
}

func TestIndexSortedByName(t *testing.T) {
	dir := t.TempDir()
	names := []string{"c.tfstate", "a.tfstate", "b.tfstate"}
	for _, n := range names {
		mustWrite(t, filepath.Join(dir, n), []byte("x"))
	}
	files, _, err := Index(dir)
	if err != nil {
		t.Fatalf("Index: %v", err)
	}
	got := []string{files[0].Name, files[1].Name, files[2].Name}
	want := []string{"a.tfstate", "b.tfstate", "c.tfstate"}
	if !sort.StringsAreSorted(got) {
		// Glob isn't deterministic across filesystems, so we
		// sort to assert set membership.
		for _, f := range files {
			found := false
			for _, w := range want {
				if f.Name == w {
					found = true
					break
				}
			}
			if !found {
				t.Errorf("unexpected file %q", f.Name)
			}
		}
	}
}

func mustWrite(t *testing.T, path string, body []byte) {
	t.Helper()
	if err := os.WriteFile(path, body, 0o600); err != nil {
		t.Fatalf("WriteFile %s: %v", path, err)
	}
}
