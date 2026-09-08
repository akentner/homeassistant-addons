package git

import (
	"fmt"
	"strings"

	"iac-runner/internal/contract"
)

// Error is the typed git failure every exported Manager method returns.
// Code is a contract.ErrCodeGit* value (CONTEXT D-19), Message is a
// single-line operator-facing summary, and Hint names the Options field
// or credential path to fix (GIT-04).
//
// Error deliberately does NOT carry git's raw stderr: GIT-04 requires
// "no stack traces in the response body", and stderr from a failed
// clone echoes the remote URL and occasionally token material. The full
// stderr is logged server-side by the caller through the scrubbing slog
// handler instead.
type Error struct {
	Code    string
	Message string
	Hint    string
	wrapped error
}

// namePlaceholder is substituted with the concrete repo name by
// hintFor. Classify has no repo context, so it emits hint templates and
// the Manager fills in the name before the hint reaches an operator.
const namePlaceholder = "<name>"

func (e *Error) Error() string {
	return fmt.Sprintf("git: %s: %s (hint: %s)", e.Code, e.Message, e.Hint)
}

func (e *Error) Unwrap() error { return e.wrapped }

// hintFor substitutes the repo name into a hint template returned by
// Classify, so the emitted hint always names a concrete path.
func hintFor(hint, name string) string {
	return strings.ReplaceAll(hint, namePlaceholder, name)
}

// newGitError classifies a failed git invocation's stderr and returns
// the typed error with the repo name substituted into the hint. message
// must be a caller-authored single-line summary — never stderr.
func newGitError(name, message, stderr string, exitCode int, fallback string) *Error {
	code, hint := Classify(stderr, exitCode, fallback)
	return &Error{Code: code, Message: message, Hint: hintFor(hint, name)}
}

// classifyRule is one ordered stderr→code mapping. A rule matches when
// any of its substrings appears in the lowercased stderr.
type classifyRule struct {
	substrings []string
	code       string
	hint       string
}

// classifyRules is the GIT-04 taxonomy, evaluated top to bottom with
// first-match-wins. Order encodes specificity: an unambiguous signal
// (a rejected public key, a failed host-key check, an unresolvable
// host, an explicit authorization refusal) must be consulted before
// git's generic "Could not read from remote repository" line, which
// accompanies almost every SSH-side failure and would otherwise mask
// the real cause.
var classifyRules = []classifyRule{
	{
		substrings: []string{"permission denied (publickey)", "permission denied (public key)"},
		code:       contract.ErrCodeGitSSHHandshake,
		hint:       "check the deploy key at /data/keys/" + namePlaceholder + ".key (chmod 600) and that its public half is registered on the remote",
	},
	{
		substrings: []string{"host key verification failed", "no matching host key"},
		code:       contract.ErrCodeGitSSHHandshake,
		hint:       "add the remote's host key to /data/keys/known_hosts",
	},
	{
		substrings: []string{"could not resolve hostname", "temporary failure in name resolution"},
		code:       contract.ErrCodeGitDNSFailure,
		hint:       "check the host part of the repo `url` Options field and the add-on's DNS/Tailscale connectivity",
	},
	{
		substrings: []string{"authentication failed", "access denied", "repository not found"},
		code:       contract.ErrCodeGitUnauthorized,
		hint:       "the deploy key is valid but not authorized for this repo — check the repo `url` Options field and the key's repo access",
	},
	{
		// Generic SSH reachability failure: reached only when none of
		// the specific SSH rules above matched.
		substrings: []string{"could not read from remote repository"},
		code:       contract.ErrCodeGitSSHHandshake,
		hint:       "check the deploy key at /data/keys/" + namePlaceholder + ".key and the remote host key in /data/keys/known_hosts",
	},
	{
		substrings: []string{"couldn't find remote ref", "did not match any file(s) known to git", "unknown revision"},
		code:       contract.ErrCodeGitRefNotFound,
		hint:       "check the `ref` (or `branch`) Options field for this repo",
	},
	{
		substrings: []string{
			"not possible to fast-forward",
			"non-fast-forward",
			"need to specify how to reconcile",
			"diverging branches",
			"divergent branches",
		},
		code: contract.ErrCodeGitNonFastForward,
		hint: "the local checkout has diverged from the remote; pin the repo with `ref`, " +
			"or delete /data/repos/" + namePlaceholder + "/ and let the add-on re-clone",
	},
}

// Classify maps a git stderr blob onto the git_* taxonomy (CONTEXT
// D-19) and returns the code plus a hint template. Matching is
// case-insensitive and substring-based because git's wording varies
// across versions while these phrases have been stable for years.
//
// fallback is the caller's context-appropriate code for stderr that
// matches no rule: Clone passes contract.ErrCodeGitCloneFailed and Pull
// passes contract.ErrCodeGitNonFastForward. Classify never returns an
// empty code — an empty fallback degrades to
// contract.ErrCodeGitCloneFailed rather than emitting "" onto the wire.
func Classify(stderr string, exitCode int, fallback string) (string, string) {
	lower := strings.ToLower(stderr)
	for _, rule := range classifyRules {
		for _, s := range rule.substrings {
			if strings.Contains(lower, s) {
				return rule.code, rule.hint
			}
		}
	}
	code := fallback
	if code == "" {
		code = contract.ErrCodeGitCloneFailed
	}
	hint := fmt.Sprintf(
		"git exited %d with an error this add-on does not recognize — "+
			"check the add-on log for the full git output", exitCode)
	return code, hint
}
