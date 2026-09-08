package git

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"iac-runner/internal/contract"
)

// CommandResult is one git invocation's captured outcome. A non-zero
// ExitCode is data, not a Go error — callers classify it from Stderr.
type CommandResult struct {
	Stdout   string
	Stderr   string
	ExitCode int
}

// CommandRunner executes a git command. Production uses
// DefaultCommandRunner (os/exec); tests inject a fake so the backoff
// curve, the ref semantics and the error classification are verifiable
// without a network or an SSH server.
type CommandRunner func(ctx context.Context, workDir string, env []string, name string, args ...string) (CommandResult, error)

// DefaultCommandRunner is the production os/exec implementation.
//
// A non-zero exit is NOT a Go error: it returns CommandResult{ExitCode:
// n} with a nil error so callers classify from stderr. The error return
// is reserved for "could not start the process at all" — a missing git
// binary or an unusable workDir.
func DefaultCommandRunner(ctx context.Context, workDir string, env []string, name string, args ...string) (CommandResult, error) {
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Dir = workDir
	cmd.Env = env

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	res := CommandResult{Stdout: stdout.String(), Stderr: stderr.String()}
	if err != nil {
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			res.ExitCode = exitErr.ExitCode()
			return res, nil
		}
		return res, fmt.Errorf("git: run %s %s: %w", name, strings.Join(args, " "), err)
	}
	return res, nil
}

// maxCloneAttempts is the CONTEXT D-13 attempt budget for the startup
// clone. After the third failure the caller logs git_clone_failed and
// startup proceeds (ROADMAP SC-2).
const maxCloneAttempts = 3

// cloneBackoff is the CONTEXT D-13 retry curve. Element i is the sleep
// AFTER attempt i+1, so with maxCloneAttempts = 3 only the first two
// entries are reached: attempt 1 fails -> sleep 1s, attempt 2 fails ->
// sleep 5s, attempt 3 fails -> return immediately. The third entry is
// kept because D-13 names it as part of the curve; it becomes live the
// moment maxCloneAttempts is raised.
var cloneBackoff = []time.Duration{
	1 * time.Second,
	5 * time.Second,
	30 * time.Second,
}

// CloneOutcome is one repo's startup-clone result. Skipped marks a
// checkout that already existed (GIT-02); Err carries the typed failure
// after the attempt budget is spent.
type CloneOutcome struct {
	Name     string
	Skipped  bool
	Attempts int
	Err      error
}

// Manager owns /data/repos/ and the configured repo set.
type Manager struct {
	reposDir string
	keysDir  string
	repos    map[string]RepoConfig
	order    []string // config order, for a deterministic CloneAll
	run      CommandRunner
	sleep    func(time.Duration)

	safeDirErr error
}

// NewManager validates every repo entry, rejects duplicate names,
// creates reposDir with 0700 and runs the one-time ownership guard.
// run defaults to DefaultCommandRunner and sleep to time.Sleep when nil.
func NewManager(reposDir, keysDir string, repos []RepoConfig, run CommandRunner, sleep func(time.Duration)) (*Manager, error) {
	if run == nil {
		run = DefaultCommandRunner
	}
	if sleep == nil {
		sleep = time.Sleep
	}
	m := &Manager{
		reposDir: reposDir,
		keysDir:  keysDir,
		repos:    make(map[string]RepoConfig, len(repos)),
		run:      run,
		sleep:    sleep,
	}
	for _, r := range repos {
		if err := r.Validate(); err != nil {
			return nil, err
		}
		if _, dup := m.repos[r.Name]; dup {
			return nil, fmt.Errorf("git: duplicate repo name %q in the `repos` Options list", r.Name)
		}
		m.repos[r.Name] = r
		m.order = append(m.order, r.Name)
	}
	// 0700: the checkouts can contain private tfvars, and only this
	// process needs to read them.
	if err := os.MkdirAll(reposDir, 0o700); err != nil {
		return nil, fmt.Errorf("git: mkdir %s: %w", reposDir, err)
	}
	m.safeDirErr = m.allowDubiousOwnership()
	return m, nil
}

// allowDubiousOwnership runs `git config --global --add safe.directory
// '*'` once at construction. /data/repos/<name>/ is created by this
// process, but the HA /data volume can end up owned by a different UID
// after a snapshot restore or a manual `docker cp`, and modern git then
// refuses every command in that checkout with "detected dubious
// ownership in repository". markdown-renderer/run.sh hit exactly this
// and fixed it the same way.
//
// The `*` wildcard is not a meaningful privilege boundary here: the
// add-on container is single-tenant and this process is the only reader
// of /data/repos.
//
// A failure must not block startup (ROADMAP SC-2), so it is returned for
// the caller to log rather than made fatal.
func (m *Manager) allowDubiousOwnership() error {
	res, err := m.run(context.Background(), "", os.Environ(),
		"git", "config", "--global", "--add", "safe.directory", "*")
	if err != nil {
		return fmt.Errorf("git: safe.directory guard could not run: %w", err)
	}
	if res.ExitCode != 0 {
		return fmt.Errorf("git: safe.directory guard exited %d", res.ExitCode)
	}
	return nil
}

// SafeDirectoryWarning reports a failure of the one-time ownership
// guard, or nil. 17-07 logs it at startup; git operations are attempted
// regardless because the guard only matters on a UID-mismatched volume.
func (m *Manager) SafeDirectoryWarning() error { return m.safeDirErr }

// Repo returns the configuration for name.
func (m *Manager) Repo(name string) (RepoConfig, bool) {
	r, ok := m.repos[name]
	return r, ok
}

// Repos returns the configured repo names in Options order.
func (m *Manager) Repos() []string {
	return append([]string(nil), m.order...)
}

// WorkTree returns the on-disk checkout path for name. The name is
// schema-validated by RepoConfig.Validate, so it cannot escape reposDir.
func (m *Manager) WorkTree(name string) string {
	return filepath.Join(m.reposDir, name)
}

// IsCloned reports whether name has a non-empty working tree. Both a
// missing and an empty directory count as not-cloned — that is exactly
// CONTEXT D-13's "missing or empty" trigger for the startup clone.
func (m *Manager) IsCloned(name string) bool {
	entries, err := os.ReadDir(m.WorkTree(name))
	if err != nil {
		return false
	}
	return len(entries) > 0
}

// EnsureCloned is the CONTEXT D-14 precondition check: a repo whose
// clone never succeeded reports git_clone_missing instead of letting a
// later tofu invocation fail on an empty directory.
func (m *Manager) EnsureCloned(name string) error {
	if _, ok := m.repos[name]; !ok {
		return m.unknownRepoError(name)
	}
	if m.IsCloned(name) {
		return nil
	}
	return &Error{
		Code:    contract.ErrCodeGitCloneMissing,
		Message: fmt.Sprintf("repo %s has no working tree at %s", name, m.WorkTree(name)),
		Hint: "the startup clone failed — check the add-on log for git_clone_failed and " +
			"POST /v1/repos/" + name + "/pull after fixing the deploy key or url",
	}
}

func (m *Manager) unknownRepoError(name string) *Error {
	return &Error{
		Code:    contract.ErrCodeRunUnknownRepo,
		Message: fmt.Sprintf("unknown repo %s", name),
		Hint:    "add it to the `repos` Options list",
	}
}

// sshEnv is the GIT-03 credential contract for every network-touching
// git invocation on repo name.
//
//   - -i <key> plus IdentitiesOnly=yes — GIT-03 requires the repo's own
//     deploy key. Without IdentitiesOnly, ssh may offer an agent key and
//     succeed with the wrong identity, which would make a misconfigured
//     deploy key look fine.
//   - StrictHostKeyChecking=yes plus UserKnownHostsFile=<keysDir>/known_hosts
//     — GIT-03 pins the host key. This is what turns an unknown host into
//     git_ssh_handshake instead of a silent trust-on-first-use accept.
//   - BatchMode=yes plus GIT_TERMINAL_PROMPT=0 — a missing or
//     passphrase-protected key must fail fast, never block a job
//     goroutine on an interactive prompt forever.
func (m *Manager) sshEnv(name string) []string {
	keyPath := filepath.Join(m.keysDir, name+".key")
	knownHosts := filepath.Join(m.keysDir, "known_hosts")
	sshCmd := fmt.Sprintf(
		"ssh -i %s -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=%s -o BatchMode=yes",
		keyPath, knownHosts)
	return append(os.Environ(),
		"GIT_SSH_COMMAND="+sshCmd,
		"GIT_TERMINAL_PROMPT=0",
	)
}

// git runs one git invocation and converts a non-zero exit into a typed
// *Error. A runner error (git not installed, unusable workDir) is
// wrapped with the same fallback code so callers never see an untyped
// failure. message is caller-authored and single-line — never stderr,
// per GIT-04.
func (m *Manager) git(
	ctx context.Context,
	name, workDir string,
	env []string,
	fallback, message string,
	args ...string,
) (CommandResult, error) {
	res, err := m.run(ctx, workDir, env, "git", args...)
	if err != nil {
		gerr := newGitError(name, message, res.Stderr, res.ExitCode, fallback)
		gerr.wrapped = err
		return res, gerr
	}
	if res.ExitCode != 0 {
		return res, newGitError(name, message, res.Stderr, res.ExitCode, fallback)
	}
	return res, nil
}

// Clone performs the startup clone for name, skipping a checkout that
// already exists (GIT-02) and retrying per CONTEXT D-13.
func (m *Manager) Clone(ctx context.Context, name string) error {
	return m.cloneOutcome(ctx, name).Err
}

// CloneAll clones every configured repo in Options order and reports one
// outcome per repo. It never returns an error: per ROADMAP SC-2 and
// CONTEXT D-13 a clone failure is logged by the caller (17-07) and
// startup proceeds.
func (m *Manager) CloneAll(ctx context.Context) []CloneOutcome {
	outcomes := make([]CloneOutcome, 0, len(m.order))
	for _, name := range m.order {
		outcomes = append(outcomes, m.cloneOutcome(ctx, name))
	}
	return outcomes
}

func (m *Manager) cloneOutcome(ctx context.Context, name string) CloneOutcome {
	out := CloneOutcome{Name: name}
	cfg, ok := m.repos[name]
	if !ok {
		out.Err = m.unknownRepoError(name)
		return out
	}
	// GIT-02: an existing checkout is left untouched — the caller is
	// responsible for triggering POST /v1/repos/{name}/pull.
	if m.IsCloned(name) {
		out.Skipped = true
		return out
	}

	workTree := m.WorkTree(name)
	env := m.sshEnv(name)
	var last error
	for attempt := 1; attempt <= maxCloneAttempts; attempt++ {
		out.Attempts = attempt
		last = m.cloneAttempt(ctx, cfg, workTree, env)
		if last == nil {
			return out
		}
		// A failed clone can leave a partial checkout behind, and git
		// refuses to clone into a non-empty directory. Without this
		// cleanup attempt 2 would fail with "destination path already
		// exists" — a symptom unrelated to the real fault.
		_ = os.RemoveAll(workTree)
		if attempt < maxCloneAttempts {
			m.sleep(cloneBackoff[attempt-1])
		}
	}
	out.Err = last
	return out
}

func (m *Manager) cloneAttempt(ctx context.Context, cfg RepoConfig, workTree string, env []string) error {
	args := []string{"clone"}
	if cfg.Pinned() {
		// D-10: a pinned repo clones full history and then lands on the
		// ref, because --branch cannot take a bare commit SHA.
		args = append(args, cfg.URL, workTree)
	} else {
		args = append(args, "--branch", cfg.EffectiveBranch(), "--single-branch", cfg.URL, workTree)
	}

	message := fmt.Sprintf("clone of repo %s failed", cfg.Name)
	if _, err := m.git(ctx, cfg.Name, "", env, contract.ErrCodeGitCloneFailed, message, args...); err != nil {
		return err
	}
	if !cfg.Pinned() {
		return nil
	}
	return m.landOnRef(ctx, cfg, workTree, env)
}

// landOnRef implements CONTEXT D-10: fetch the pinned ref, then detach
// onto FETCH_HEAD. `checkout --detach FETCH_HEAD` lands correctly on a
// SHA, a tag and a branch alike, so no ref-shape sniffing is needed.
func (m *Manager) landOnRef(ctx context.Context, cfg RepoConfig, workTree string, env []string) error {
	message := fmt.Sprintf("fetch of ref %s for repo %s failed", cfg.Ref, cfg.Name)
	if _, err := m.git(ctx, cfg.Name, workTree, env, contract.ErrCodeGitRefNotFound, message,
		"fetch", "origin", cfg.Ref); err != nil {
		return err
	}

	message = fmt.Sprintf("checkout of ref %s for repo %s failed", cfg.Ref, cfg.Name)
	_, err := m.git(ctx, cfg.Name, workTree, env, contract.ErrCodeGitRefNotFound, message,
		"checkout", "--detach", "FETCH_HEAD")
	return err
}
