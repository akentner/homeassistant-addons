package git

import (
	"context"
	"time"
)

// CommandResult is one git invocation's captured outcome.
type CommandResult struct {
	Stdout   string
	Stderr   string
	ExitCode int
}

// CommandRunner executes a git command.
type CommandRunner func(ctx context.Context, workDir string, env []string, name string, args ...string) (CommandResult, error)

// DefaultCommandRunner is the production os/exec implementation.
func DefaultCommandRunner(ctx context.Context, workDir string, env []string, name string, args ...string) (CommandResult, error) {
	return CommandResult{}, nil
}

// CloneOutcome is one repo's startup-clone result.
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
	order    []string
	run      CommandRunner
	sleep    func(time.Duration)
}

// NewManager builds a Manager over reposDir and keysDir.
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
		m.repos[r.Name] = r
		m.order = append(m.order, r.Name)
	}
	return m, nil
}

// SafeDirectoryWarning reports a failure of the one-time ownership guard.
func (m *Manager) SafeDirectoryWarning() error { return nil }

// Repo returns the configuration for name.
func (m *Manager) Repo(name string) (RepoConfig, bool) {
	r, ok := m.repos[name]
	return r, ok
}

// WorkTree returns the on-disk checkout path for name.
func (m *Manager) WorkTree(name string) string { return "" }

// IsCloned reports whether name has a non-empty working tree.
func (m *Manager) IsCloned(name string) bool { return false }

// EnsureCloned reports git_clone_missing when name has no working tree.
func (m *Manager) EnsureCloned(name string) error { return nil }

// Clone performs the startup clone for name.
func (m *Manager) Clone(ctx context.Context, name string) error { return nil }

// CloneAll clones every configured repo, reporting per-repo outcomes.
func (m *Manager) CloneAll(ctx context.Context) []CloneOutcome { return nil }
