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

import (
	"fmt"
	"regexp"
	"strings"
)

// defaultBranch is the branch used when a repo entry omits `branch`.
// GIT-01 specifies "default main"; the HA options schema cannot express
// a default for a member of a list-of-dict, so the default lives here
// (see 17-01 Task 1).
const defaultBranch = "main"

// repoNameRe mirrors the config.yaml schema regex for repo names
// (17-01 Task 1). Re-validating in Go is deliberate defense in depth:
// the name becomes a filesystem path segment under /data/repos/ and a
// URL path segment in /v1/repos/{name}/pull.
var repoNameRe = regexp.MustCompile(`^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$`)

// repoURLRe mirrors the config.yaml schema regex for `url`. Rejecting
// only the http(s) prefixes was strictly weaker than the schema this
// guard claims to re-implement: it accepted git's `ext::` transport
// (`ext::sh -c …` runs a command) and any value starting with `-`,
// which git parses as an option (`--upload-pack=…`, `--config=…`).
var repoURLRe = regexp.MustCompile(`^(git@|ssh://).+$`)

// refRe bounds `ref` and `branch`. Neither the HA schema (`str?`) nor
// this guard validated them at all, yet both land in a positional
// argv slot — `git fetch origin <ref>`, `git pull --ff-only origin
// <branch>`. The leading character is deliberately not `-`, and the
// 255-byte ceiling matches git's own ref-name limit.
var refRe = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._/+-]{0,254}$`)

// RepoConfig is one entry of the `repos` Options list (GIT-01). Field
// names match the HA schema keys exactly so main.go can unmarshal
// /data/options.json straight into []RepoConfig.
type RepoConfig struct {
	Name   string `json:"name"`
	URL    string `json:"url"`
	Branch string `json:"branch"`
	Ref    string `json:"ref"`
}

// EffectiveBranch returns the branch to track: the configured value,
// or "main" when unset (GIT-01 / CONTEXT D-11).
func (r RepoConfig) EffectiveBranch() string {
	if strings.TrimSpace(r.Branch) == "" {
		return defaultBranch
	}
	return r.Branch
}

// Pinned reports whether this repo is pinned to an explicit ref. When
// true, CONTEXT D-10 replaces pull semantics with fetch + checkout and
// the `branch` field is ignored — the caller is expected to log that at
// startup so an operator who set both fields understands which one won.
func (r RepoConfig) Pinned() bool {
	return strings.TrimSpace(r.Ref) != ""
}

// Validate checks a single entry from Options. The Supervisor already
// enforces the same rules via the config.yaml schema; this guard covers
// a hand-edited /data/options.json and keeps the invariant local to the
// code that depends on it.
func (r RepoConfig) Validate() error {
	if !repoNameRe.MatchString(r.Name) {
		return fmt.Errorf("git: invalid repo name %q: must match %s", r.Name, repoNameRe.String())
	}
	if strings.TrimSpace(r.URL) == "" {
		return fmt.Errorf("git: repo %q has an empty url", r.Name)
	}
	if !repoURLRe.MatchString(strings.TrimSpace(r.URL)) {
		return fmt.Errorf(
			"git: repo %q url must be an SSH url matching %s; "+
				"an https clone cannot authenticate with the deploy key at /data/keys/%s.key",
			r.Name, repoURLRe.String(), r.Name)
	}
	for _, f := range []struct{ field, value string }{
		{"ref", r.Ref},
		{"branch", r.Branch},
	} {
		if f.value == "" {
			continue
		}
		if !refRe.MatchString(f.value) {
			return fmt.Errorf("git: repo %q %s %q is not a valid ref name: must match %s",
				r.Name, f.field, f.value, refRe.String())
		}
	}
	return nil
}
