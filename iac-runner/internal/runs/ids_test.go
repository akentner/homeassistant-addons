package runs

import (
	"strings"
	"testing"
)

func TestNewRunIDLengthAndCharset(t *testing.T) {
	for i := 0; i < 100; i++ {
		id, err := NewRunID()
		if err != nil {
			t.Fatalf("NewRunID: %v", err)
		}
		if len(id) != RunIDLength {
			t.Errorf("id %q has length %d, want %d", id, len(id), RunIDLength)
		}
		for j := 0; j < len(id); j++ {
			c := id[j]
			ok := (c >= 'A' && c <= 'Z') || (c >= '2' && c <= '7')
			if !ok {
				t.Errorf("id %q contains non-base32 char %q at position %d", id, c, j)
				break
			}
		}
	}
}

func TestNewRunIDUniqueness(t *testing.T) {
	const n = 10000
	seen := make(map[string]struct{}, n)
	for i := 0; i < n; i++ {
		id, err := NewRunID()
		if err != nil {
			t.Fatalf("NewRunID: %v", err)
		}
		if _, dup := seen[id]; dup {
			t.Fatalf("duplicate id %q after %d iterations", id, i)
		}
		seen[id] = struct{}{}
	}
	if got := len(seen); got != n {
		t.Errorf("seen = %d, want %d", got, n)
	}
}

func TestIsValidRunIDAcceptsGenerated(t *testing.T) {
	for i := 0; i < 100; i++ {
		id, err := NewRunID()
		if err != nil {
			t.Fatalf("NewRunID: %v", err)
		}
		if !IsValidRunID(id) {
			t.Errorf("IsValidRunID(%q) = false, want true", id)
		}
	}
}

func TestIsValidRunIDRejectsMalformed(t *testing.T) {
	cases := []struct {
		name string
		in   string
	}{
		{"empty", ""},
		{"short", "SHORT"},
		{"fifteen chars", strings.Repeat("A", 15)},
		{"seventeen chars", strings.Repeat("A", 17)},
		{"lowercase", "abcdefghijklmnop"},
		{"double dot", "AAAAAAAAAAAAAA.."},
		{"slash", "AAAAAAA/AAAAAAAA"},
		{"zero", "AAAAAAAAAAAAAAA0"},
		{"one", "AAAAAAAAAAAAAAA1"},
		{"eight", "AAAAAAAAAAAAAAA8"},
		{"nine", "AAAAAAAAAAAAAAA9"},
		{"padding", "AAAAAAAAAAAAAAA="},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if IsValidRunID(tc.in) {
				t.Errorf("IsValidRunID(%q) = true, want false", tc.in)
			}
		})
	}
}
