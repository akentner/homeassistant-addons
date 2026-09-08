package git

import (
	"errors"
	"strings"
	"testing"

	"iac-runner/internal/contract"
)

// Compile-time signature lock. The plan's acceptance criteria pin the
// exported signature with a regex anchored at end-of-line, which no
// valid Go declaration can satisfy (the language requires `{` on the
// signature line). This assertion checks the same contract at the type
// level, where drift is a build failure rather than a grep miss.
var _ func(string, int, string) (string, string) = Classify

// TestClassify is the GIT-04 taxonomy table: every git stderr family
// an operator can provoke must land on a distinct contract.ErrCodeGit*
// value with a non-empty, actionable hint. Unrecognized stderr falls
// back to the caller-supplied code and never to the empty string.
func TestClassify(t *testing.T) {
	tests := []struct {
		name     string
		stderr   string
		exitCode int
		fallback string
		wantCode string
		wantHint string // substring the returned hint must contain
	}{
		{
			name:     "permission denied publickey is ssh handshake",
			stderr:   "git@github.com: Permission denied (publickey).",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitSSHHandshake,
			wantHint: "/data/keys/<name>.key",
		},
		{
			name:     "could not read from remote repository is ssh handshake",
			stderr:   "fatal: Could not read from remote repository.",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitSSHHandshake,
			wantHint: "/data/keys/",
		},
		{
			name:     "host key verification failed points at known_hosts",
			stderr:   "Host key verification failed.\nfatal: Could not read from remote repository.",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitSSHHandshake,
			wantHint: "/data/keys/known_hosts",
		},
		{
			name:     "no matching host key points at known_hosts",
			stderr:   "Unable to negotiate with 10.0.0.1 port 22: no matching host key type found.",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitSSHHandshake,
			wantHint: "/data/keys/known_hosts",
		},
		{
			name:     "could not resolve hostname is dns failure",
			stderr:   "ssh: Could not resolve hostname github.internal: Name or service not known",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitDNSFailure,
			wantHint: "Options field",
		},
		{
			name:     "temporary name resolution failure is dns failure",
			stderr:   "ssh: Temporary failure in name resolution",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitDNSFailure,
			wantHint: "Options field",
		},
		{
			name:     "authentication failed is unauthorized",
			stderr:   "fatal: Authentication failed for 'git@github.com:acme/infra.git'",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitUnauthorized,
			wantHint: "Options field",
		},
		{
			name:     "access denied is unauthorized",
			stderr:   "remote: access denied or repository not exported",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitUnauthorized,
			wantHint: "Options field",
		},
		{
			name:     "repository not found is unauthorized even with the generic ssh line",
			stderr:   "ERROR: Repository not found.\nfatal: Could not read from remote repository.",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitUnauthorized,
			wantHint: "Options field",
		},
		{
			name:     "missing remote ref is ref not found",
			stderr:   "fatal: couldn't find remote ref v9.9.9",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitRefNotFound,
			wantHint: "Options field",
		},
		{
			name:     "pathspec mismatch is ref not found",
			stderr:   "error: pathspec 'release' did not match any file(s) known to git",
			exitCode: 1,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitRefNotFound,
			wantHint: "Options field",
		},
		{
			name:     "unknown revision is ref not found",
			stderr:   "fatal: ambiguous argument 'abc123': unknown revision or path not in the working tree.",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitRefNotFound,
			wantHint: "Options field",
		},
		{
			name:     "not possible to fast-forward is non fast forward",
			stderr:   "fatal: Not possible to fast-forward, aborting.",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitNonFastForward,
			wantHint: "/data/repos/<name>/",
		},
		{
			name:     "rejected non-fast-forward is non fast forward",
			stderr:   " ! [rejected]        main -> main (non-fast-forward)",
			exitCode: 1,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitNonFastForward,
			wantHint: "ref",
		},
		{
			name:     "need to specify how to reconcile is non fast forward",
			stderr:   "hint: You have divergent branches and need to specify how to reconcile them.",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitNonFastForward,
			wantHint: "ref",
		},
		{
			name:     "diverging branches is non fast forward",
			stderr:   "fatal: Need to specify how to reconcile diverging branches.",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitNonFastForward,
			wantHint: "ref",
		},
		{
			name:     "matching is case insensitive",
			stderr:   "GIT@GITHUB.COM: PERMISSION DENIED (PUBLICKEY).",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitSSHHandshake,
			wantHint: "/data/keys/<name>.key",
		},
		{
			name: "multi-line stderr matches on any line",
			stderr: "Cloning into '/data/repos/infra'...\n" +
				"Warning: Permanently added the ED25519 host key.\n" +
				"git@github.com: Permission denied (publickey).\n" +
				"fatal: Could not read from remote repository.\n",
			exitCode: 128,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitSSHHandshake,
			wantHint: "/data/keys/<name>.key",
		},
		{
			name:     "empty stderr falls back to the caller code",
			stderr:   "",
			exitCode: 1,
			fallback: contract.ErrCodeGitCloneFailed,
			wantCode: contract.ErrCodeGitCloneFailed,
			wantHint: "log",
		},
		{
			name:     "unrelated stderr falls back to the caller code",
			stderr:   "fatal: not a git repository (or any of the parent directories): .git",
			exitCode: 128,
			fallback: contract.ErrCodeGitNonFastForward,
			wantCode: contract.ErrCodeGitNonFastForward,
			wantHint: "log",
		},
		{
			name:     "an empty fallback still yields a non-empty code",
			stderr:   "fatal: something entirely new went wrong",
			exitCode: 128,
			fallback: "",
			wantCode: contract.ErrCodeGitCloneFailed,
			wantHint: "log",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			code, hint := Classify(tc.stderr, tc.exitCode, tc.fallback)
			if code != tc.wantCode {
				t.Errorf("Classify(%q) code = %q, want %q", tc.stderr, code, tc.wantCode)
			}
			if code == "" {
				t.Errorf("Classify(%q) returned an empty code", tc.stderr)
			}
			if hint == "" {
				t.Fatalf("Classify(%q) returned an empty hint", tc.stderr)
			}
			if !strings.Contains(hint, tc.wantHint) {
				t.Errorf("Classify(%q) hint = %q, want substring %q", tc.stderr, hint, tc.wantHint)
			}
		})
	}
}

// TestErrorMessageCarriesCodeAndHintButNotStderr locks the GIT-04
// promise: the surfaced error names the code, the summary and the
// hint, and never echoes git's raw multi-line stderr.
func TestErrorMessageCarriesCodeAndHintButNotStderr(t *testing.T) {
	rawStderr := "Cloning into '/data/repos/infra'...\ngit@github.com: Permission denied (publickey).\n"
	code, hint := Classify(rawStderr, 128, contract.ErrCodeGitCloneFailed)
	err := &Error{
		Code:    code,
		Message: "clone of repo infra failed after 3 attempts",
		Hint:    strings.ReplaceAll(hint, "<name>", "infra"),
	}

	got := err.Error()
	for _, want := range []string{code, "clone of repo infra failed", "/data/keys/infra.key"} {
		if !strings.Contains(got, want) {
			t.Errorf("Error() = %q, want substring %q", got, want)
		}
	}
	if strings.Contains(got, rawStderr) {
		t.Errorf("Error() leaked the raw stderr dump: %q", got)
	}
	if strings.Contains(got, "\n") {
		t.Errorf("Error() must be a single line, got %q", got)
	}
}

// TestErrorUnwrap proves *Error participates in errors.Is/As chains so
// callers can keep a cause without putting it on the wire.
func TestErrorUnwrap(t *testing.T) {
	cause := errors.New("exec: \"git\": executable file not found in $PATH")
	err := &Error{Code: contract.ErrCodeGitCloneFailed, Message: "clone failed", Hint: "install git", wrapped: cause}

	if !errors.Is(err, cause) {
		t.Errorf("errors.Is(err, cause) = false, want true")
	}

	var bare *Error
	if !errors.As(error(err), &bare) {
		t.Fatalf("errors.As did not match *Error")
	}
	if bare.Code != contract.ErrCodeGitCloneFailed {
		t.Errorf("unwrapped Code = %q, want %q", bare.Code, contract.ErrCodeGitCloneFailed)
	}

	if (&Error{Code: "x"}).Unwrap() != nil {
		t.Errorf("Unwrap() on an Error with no cause = non-nil, want nil")
	}
}

// TestRepoConfigEffectiveBranch covers GIT-01's "branch (default main)"
// and CONTEXT D-11.
func TestRepoConfigEffectiveBranch(t *testing.T) {
	tests := []struct {
		name   string
		branch string
		want   string
	}{
		{name: "empty defaults to main", branch: "", want: "main"},
		{name: "whitespace defaults to main", branch: "   ", want: "main"},
		{name: "configured branch wins", branch: "production", want: "production"},
		{name: "slashed branch preserved", branch: "release/1.2", want: "release/1.2"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := RepoConfig{Name: "infra", URL: "git@github.com:acme/infra.git", Branch: tc.branch}.EffectiveBranch()
			if got != tc.want {
				t.Errorf("EffectiveBranch() with branch %q = %q, want %q", tc.branch, got, tc.want)
			}
		})
	}
}

// TestRepoConfigPinned covers CONTEXT D-10's trigger condition.
func TestRepoConfigPinned(t *testing.T) {
	if (RepoConfig{Ref: ""}).Pinned() {
		t.Errorf("Pinned() with empty ref = true, want false")
	}
	if (RepoConfig{Ref: "  "}).Pinned() {
		t.Errorf("Pinned() with whitespace ref = true, want false")
	}
	if !(RepoConfig{Ref: "v1.2.3"}).Pinned() {
		t.Errorf("Pinned() with ref v1.2.3 = false, want true")
	}
}

func TestRepoConfigValidateAccepts(t *testing.T) {
	tests := []struct {
		name string
		repo RepoConfig
	}{
		{name: "scp-style url", repo: RepoConfig{Name: "infra", URL: "git@github.com:akentner/homelab-infra.git"}},
		{name: "ssh scheme url", repo: RepoConfig{Name: "infra", URL: "ssh://git@host/path.git"}},
		{name: "dotted name", repo: RepoConfig{Name: "home.lab", URL: "git@github.com:a/b.git"}},
		{name: "dashed name", repo: RepoConfig{Name: "home-lab_1", URL: "git@github.com:a/b.git"}},
		{name: "ref pinned", repo: RepoConfig{Name: "infra", URL: "git@github.com:a/b.git", Ref: "abc1234"}},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if err := tc.repo.Validate(); err != nil {
				t.Errorf("Validate() = %v, want nil", err)
			}
		})
	}
}

func TestRepoConfigValidateRejects(t *testing.T) {
	tests := []struct {
		name string
		repo RepoConfig
	}{
		{name: "empty name", repo: RepoConfig{Name: "", URL: "git@github.com:a/b.git"}},
		{name: "name with space", repo: RepoConfig{Name: "a b", URL: "git@github.com:a/b.git"}},
		{name: "name with traversal", repo: RepoConfig{Name: "../etc", URL: "git@github.com:a/b.git"}},
		{name: "name with slash", repo: RepoConfig{Name: "a/b", URL: "git@github.com:a/b.git"}},
		{name: "name starting with dot", repo: RepoConfig{Name: ".hidden", URL: "git@github.com:a/b.git"}},
		{name: "empty url", repo: RepoConfig{Name: "infra", URL: ""}},
		{name: "whitespace url", repo: RepoConfig{Name: "infra", URL: "   "}},
		{name: "https url", repo: RepoConfig{Name: "infra", URL: "https://github.com/x/y.git"}},
		{name: "http url", repo: RepoConfig{Name: "infra", URL: "http://github.com/x/y.git"}},
		{name: "uppercase https url", repo: RepoConfig{Name: "infra", URL: "HTTPS://github.com/x/y.git"}},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if err := tc.repo.Validate(); err == nil {
				t.Errorf("Validate() = nil, want an error for %+v", tc.repo)
			}
		})
	}
}
