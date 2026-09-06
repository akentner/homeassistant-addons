package runs

import (
	"errors"
	"testing"
)

func TestValidateDirAccepts(t *testing.T) {
	tests := []struct {
		name string
		in   string
		want string
	}{
		{name: "empty is repo root", in: "", want: ""},
		{name: "dot is repo root", in: ".", want: ""},
		{name: "simple subdir", in: "envs/prod", want: "envs/prod"},
		{name: "dot-slash prefix normalized", in: "./envs/prod", want: "envs/prod"},
		{name: "trailing slash normalized", in: "envs/prod/", want: "envs/prod"},
		{name: "single segment", in: "infra", want: "infra"},
		{name: "inner dot segment normalized", in: "envs/./prod", want: "envs/prod"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ValidateDir(tc.in)
			if err != nil {
				t.Fatalf("ValidateDir(%q) error: %v", tc.in, err)
			}
			if got != tc.want {
				t.Errorf("ValidateDir(%q) = %q, want %q", tc.in, got, tc.want)
			}
		})
	}
}

func TestValidateDirRejects(t *testing.T) {
	tests := []struct {
		name string
		in   string
	}{
		{name: "absolute path", in: "/etc/passwd"},
		{name: "parent traversal", in: "../../etc"},
		{name: "traversal after clean", in: "envs/../../etc"},
		{name: "bare dotdot", in: ".."},
		{name: "trailing dotdot", in: "envs/.."},
		{name: "null byte", in: "envs/\x00prod"},
		{name: "null byte only", in: "\x00"},
		{name: "absolute with traversal", in: "/../etc"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			_, err := ValidateDir(tc.in)
			if err == nil {
				t.Fatalf("ValidateDir(%q) returned nil error, want ErrInvalidDir", tc.in)
			}
			if !errors.Is(err, ErrInvalidDir) {
				t.Errorf("ValidateDir(%q) error = %v, want errors.Is(ErrInvalidDir)", tc.in, err)
			}
			if !contains(err.Error(), InvalidDirMessage) {
				t.Errorf("ValidateDir(%q) error message = %q, want substring %q",
					tc.in, err.Error(), InvalidDirMessage)
			}
		})
	}
}

func contains(s, substr string) bool {
	for i := 0; i+len(substr) <= len(s); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
