// Package git owns every interaction with the `git` binary: the
// per-repo configuration read from add-on Options, the startup clone
// into /data/repos/<name>/, the SSH-keyed pull, and the translation of
// git's stderr into the stable git_* error_code taxonomy (CONTEXT
// D-19).
//
// The package never talks HTTP and never touches /data/runs/ —
// internal/runs owns run state and internal/jobq owns tofu execution.
// Every git invocation goes through a CommandRunner so the retry
// curve, the ref semantics, and the error classification are testable
// without a network, an SSH server, or a real repository.
package git

// RepoConfig is one entry of the `repos` Options list (GIT-01).
type RepoConfig struct {
	Name   string `json:"name"`
	URL    string `json:"url"`
	Branch string `json:"branch"`
	Ref    string `json:"ref"`
}

// EffectiveBranch returns the branch to track.
func (r RepoConfig) EffectiveBranch() string { return "" }

// Pinned reports whether this repo is pinned to an explicit ref.
func (r RepoConfig) Pinned() bool { return false }

// Validate checks a single entry from Options.
func (r RepoConfig) Validate() error { return nil }
