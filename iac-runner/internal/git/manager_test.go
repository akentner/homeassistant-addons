package git

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"iac-runner/internal/contract"
)

// Compile-time signature locks. The plan's acceptance criteria pin these
// exported signatures with regexes anchored at end-of-line, which no
// valid Go declaration can satisfy (the language requires `{` on the
// signature line). These assertions check the same contracts at the type
// level, where drift is a build failure rather than a grep miss.
var (
	_ func(string, string, []RepoConfig, CommandRunner, func(time.Duration)) (*Manager, error) = NewManager
	_ CommandRunner                                                                            = DefaultCommandRunner
	_ func(context.Context, string, bool) (PullOutcome, error)                                 = (&Manager{}).Pull
)

// recordedCall is one git invocation the fake runner observed.
type recordedCall struct {
	workDir string
	env     []string
	name    string
	args    []string
}

// fakeGit is the injected CommandRunner plus a fake clock. No test in
// this file spawns a real git process: the whole point of the
// CommandRunner seam is that the retry curve, the ref semantics and the
// error classification are verifiable without a network or an SSH
// server.
type fakeGit struct {
	calls  []recordedCall
	sleeps []time.Duration
	// respond scripts one invocation's outcome. A nil respond means
	// "exit 0 with empty output" for every call.
	respond func(call recordedCall) (CommandResult, error)
}

func (f *fakeGit) run(_ context.Context, workDir string, env []string, name string, args ...string) (CommandResult, error) {
	call := recordedCall{
		workDir: workDir,
		env:     append([]string(nil), env...),
		name:    name,
		args:    append([]string(nil), args...),
	}
	f.calls = append(f.calls, call)
	if f.respond == nil {
		return CommandResult{}, nil
	}
	return f.respond(call)
}

func (f *fakeGit) sleep(d time.Duration) { f.sleeps = append(f.sleeps, d) }

// subcommands returns the first argument of every recorded invocation,
// e.g. ["clone", "fetch", "checkout"].
func (f *fakeGit) subcommands() []string {
	out := make([]string, 0, len(f.calls))
	for _, c := range f.calls {
		if len(c.args) > 0 {
			out = append(out, c.args[0])
		}
	}
	return out
}

// failWith scripts every invocation as a non-zero exit carrying stderr.
func failWith(stderr string) func(recordedCall) (CommandResult, error) {
	return func(recordedCall) (CommandResult, error) {
		return CommandResult{Stderr: stderr, ExitCode: 128}, nil
	}
}

// newTestManager builds a Manager over t.TempDir() with the fake runner
// and fake clock injected. Recorded calls are reset after construction
// so a test asserting "no git ran" is not tripped by NewManager's
// one-time safe.directory guard, which
// TestNewManagerConfiguresSafeDirectory covers separately.
func newTestManager(
	t *testing.T,
	repos []RepoConfig,
	respond func(recordedCall) (CommandResult, error),
) (*Manager, *fakeGit, string, string) {
	t.Helper()
	root := t.TempDir()
	reposDir := filepath.Join(root, "repos")
	keysDir := filepath.Join(root, "keys")
	f := &fakeGit{respond: respond}
	m, err := NewManager(reposDir, keysDir, repos, f.run, f.sleep)
	if err != nil {
		t.Fatalf("NewManager: %v", err)
	}
	f.calls = nil
	return m, f, reposDir, keysDir
}

// preClone materializes a non-empty working tree so IsCloned reports
// true without any git process having run.
func preClone(t *testing.T, reposDir, name string) {
	t.Helper()
	dir := filepath.Join(reposDir, name)
	if err := os.MkdirAll(filepath.Join(dir, ".git"), 0o700); err != nil {
		t.Fatalf("pre-clone %s: %v", name, err)
	}
}

// gitErr asserts err is a *Error with the expected code.
func gitErr(t *testing.T, err error, wantCode string) *Error {
	t.Helper()
	if err == nil {
		t.Fatalf("expected a *git.Error with code %q, got nil", wantCode)
	}
	var gerr *Error
	if !errors.As(err, &gerr) {
		t.Fatalf("error %v is not a *git.Error", err)
	}
	if gerr.Code != wantCode {
		t.Fatalf("error code = %q, want %q (message: %s)", gerr.Code, wantCode, gerr.Message)
	}
	if gerr.Hint == "" {
		t.Errorf("error code %q carries an empty hint", gerr.Code)
	}
	return gerr
}

// callAt returns the i-th recorded invocation, failing the test rather
// than panicking when fewer calls were made than the test expects.
func callAt(t *testing.T, f *fakeGit, i int) recordedCall {
	t.Helper()
	if i >= len(f.calls) {
		t.Fatalf("expected at least %d git invocations, got %d: %v", i+1, len(f.calls), f.subcommands())
	}
	return f.calls[i]
}

func argsEqual(got, want []string) bool {
	if len(got) != len(want) {
		return false
	}
	for i := range got {
		if got[i] != want[i] {
			return false
		}
	}
	return true
}

func TestNewManagerRejectsInvalidAndDuplicateRepos(t *testing.T) {
	root := t.TempDir()
	f := &fakeGit{}

	if _, err := NewManager(root, root, []RepoConfig{{Name: "a b", URL: "git@h:x.git"}}, f.run, f.sleep); err == nil {
		t.Errorf("NewManager with an invalid repo name = nil error, want a validation error")
	}
	if _, err := NewManager(root, root, []RepoConfig{{Name: "infra", URL: "https://h/x.git"}}, f.run, f.sleep); err == nil {
		t.Errorf("NewManager with an https url = nil error, want a validation error")
	}
	dupes := []RepoConfig{
		{Name: "infra", URL: "git@h:x.git"},
		{Name: "infra", URL: "git@h:y.git"},
	}
	if _, err := NewManager(root, root, dupes, f.run, f.sleep); err == nil {
		t.Errorf("NewManager with duplicate repo names = nil error, want an error")
	}
}

func TestNewManagerCreatesReposDirAndConfiguresSafeDirectory(t *testing.T) {
	root := t.TempDir()
	reposDir := filepath.Join(root, "repos")
	f := &fakeGit{}

	if _, err := NewManager(reposDir, filepath.Join(root, "keys"), nil, f.run, f.sleep); err != nil {
		t.Fatalf("NewManager: %v", err)
	}

	info, err := os.Stat(reposDir)
	if err != nil {
		t.Fatalf("reposDir was not created: %v", err)
	}
	if !info.IsDir() {
		t.Fatalf("reposDir is not a directory")
	}
	if perm := info.Mode().Perm(); perm != 0o700 {
		t.Errorf("reposDir mode = %o, want 0700", perm)
	}

	// The /data volume can be owned by a different UID after a snapshot
	// restore; without this guard modern git refuses every command with
	// "detected dubious ownership in repository".
	var found bool
	for _, c := range f.calls {
		if argsEqual(c.args, []string{"config", "--global", "--add", "safe.directory", "*"}) {
			found = true
		}
	}
	if !found {
		t.Errorf("NewManager did not run the safe.directory guard; calls = %v", f.subcommands())
	}
}

func TestNewManagerSafeDirectoryFailureIsNotFatal(t *testing.T) {
	root := t.TempDir()
	f := &fakeGit{respond: failWith("error: could not lock config file /root/.gitconfig")}

	m, err := NewManager(root, root, nil, f.run, f.sleep)
	if err != nil {
		t.Fatalf("NewManager must not fail when the safe.directory guard fails: %v", err)
	}
	// ROADMAP SC-2: startup proceeds, but the failure is reportable
	// rather than silently swallowed.
	if m.SafeDirectoryWarning() == nil {
		t.Errorf("SafeDirectoryWarning() = nil, want the guard failure for the caller to log")
	}
}

func TestManagerWorkTreeAndIsCloned(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	m, _, reposDir, _ := newTestManager(t, repos, nil)

	if got, want := m.WorkTree("infra"), filepath.Join(reposDir, "infra"); got != want {
		t.Errorf("WorkTree() = %q, want %q", got, want)
	}
	if m.IsCloned("infra") {
		t.Errorf("IsCloned() on a missing directory = true, want false")
	}

	if err := os.MkdirAll(m.WorkTree("infra"), 0o700); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if m.IsCloned("infra") {
		t.Errorf("IsCloned() on an empty directory = true, want false")
	}

	preClone(t, reposDir, "infra")
	if !m.IsCloned("infra") {
		t.Errorf("IsCloned() on a populated directory = false, want true")
	}
}

func TestManagerCloneSkipsExistingWorkTree(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	m, f, reposDir, _ := newTestManager(t, repos, nil)
	preClone(t, reposDir, "infra")

	if err := m.Clone(context.Background(), "infra"); err != nil {
		t.Fatalf("Clone on an existing work tree = %v, want nil", err)
	}
	// GIT-02: existing directories are left untouched.
	if len(f.calls) != 0 {
		t.Errorf("Clone ran %d git commands on an existing work tree, want 0: %v", len(f.calls), f.subcommands())
	}
}

func TestManagerCloneUnpinnedUsesBranchSingleBranch(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	m, f, _, _ := newTestManager(t, repos, nil)

	if err := m.Clone(context.Background(), "infra"); err != nil {
		t.Fatalf("Clone: %v", err)
	}
	if len(f.calls) != 1 {
		t.Fatalf("Clone ran %d commands, want 1: %v", len(f.calls), f.subcommands())
	}
	want := []string{"clone", "--branch", "main", "--single-branch", "--", "git@github.com:acme/infra.git", m.WorkTree("infra")}
	if got := callAt(t, f, 0).args; !argsEqual(got, want) {
		t.Errorf("clone args = %v, want %v", got, want)
	}
}

func TestManagerCloneUsesConfiguredBranch(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git", Branch: "production"}}
	m, f, _, _ := newTestManager(t, repos, nil)

	if err := m.Clone(context.Background(), "infra"); err != nil {
		t.Fatalf("Clone: %v", err)
	}
	got := callAt(t, f, 0).args
	if !strings.Contains(strings.Join(got, " "), "--branch production --single-branch") {
		t.Errorf("clone args = %v, want --branch production --single-branch", got)
	}
}

func TestManagerClonePinnedFetchesAndChecksOutRef(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git", Ref: "abc123"}}
	m, f, _, _ := newTestManager(t, repos, nil)

	if err := m.Clone(context.Background(), "infra"); err != nil {
		t.Fatalf("Clone: %v", err)
	}
	if got, want := f.subcommands(), []string{"clone", "fetch", "checkout"}; !argsEqual(got, want) {
		t.Fatalf("subcommands = %v, want %v", got, want)
	}
	// D-10: a pinned repo must not be cloned with --branch (a bare SHA
	// is not a valid --branch argument).
	if got := callAt(t, f, 0).args; strings.Contains(strings.Join(got, " "), "--branch") {
		t.Errorf("pinned clone args = %v, want no --branch", got)
	}
	if want := []string{"fetch", "origin", "--", "abc123"}; !argsEqual(callAt(t, f, 1).args, want) {
		t.Errorf("fetch args = %v, want %v", callAt(t, f, 1).args, want)
	}
	if want := []string{"checkout", "--detach", "FETCH_HEAD"}; !argsEqual(callAt(t, f, 2).args, want) {
		t.Errorf("checkout args = %v, want %v", callAt(t, f, 2).args, want)
	}
	// fetch and checkout must run inside the checkout, not the CWD.
	for _, i := range []int{1, 2} {
		if got := callAt(t, f, i).workDir; got != m.WorkTree("infra") {
			t.Errorf("call %d workDir = %q, want %q", i, got, m.WorkTree("infra"))
		}
	}
}

func TestManagerCloneRetriesThreeTimesWithBackoff(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	m, f, _, _ := newTestManager(t, repos, failWith("git@github.com: Permission denied (publickey)."))

	err := m.Clone(context.Background(), "infra")
	gitErr(t, err, contract.ErrCodeGitSSHHandshake)

	// D-13: three attempts, with 1s and 5s slept between them.
	if len(f.calls) != 3 {
		t.Errorf("clone attempts = %d, want 3: %v", len(f.calls), f.subcommands())
	}
	wantSleeps := []time.Duration{1 * time.Second, 5 * time.Second}
	if len(f.sleeps) != len(wantSleeps) {
		t.Fatalf("sleeps = %v, want %v", f.sleeps, wantSleeps)
	}
	for i := range wantSleeps {
		if f.sleeps[i] != wantSleeps[i] {
			t.Errorf("sleeps = %v, want %v", f.sleeps, wantSleeps)
			break
		}
	}
}

func TestManagerCloneUnrecognizedFailureIsCloneFailed(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	m, _, _, _ := newTestManager(t, repos, failWith("fatal: something entirely new went wrong"))

	gitErr(t, m.Clone(context.Background(), "infra"), contract.ErrCodeGitCloneFailed)
}

func TestManagerCloneRemovesPartialWorkTreeBetweenAttempts(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	var m *Manager
	f := &fakeGit{}
	// Simulate git leaving a partial checkout behind on every failure:
	// without cleanup, attempt 2 would fail with "destination path
	// already exists" for a reason unrelated to the real fault.
	f.respond = func(call recordedCall) (CommandResult, error) {
		// m is still nil while NewManager runs its safe.directory guard,
		// which is not a clone and must not be scripted here.
		if m == nil || len(call.args) == 0 || call.args[0] != "clone" {
			return CommandResult{}, nil
		}
		if err := os.MkdirAll(filepath.Join(m.WorkTree("infra"), ".git"), 0o700); err != nil {
			t.Fatalf("simulate partial clone: %v", err)
		}
		return CommandResult{Stderr: "ssh: Could not resolve hostname github.internal", ExitCode: 128}, nil
	}
	root := t.TempDir()
	var err error
	m, err = NewManager(filepath.Join(root, "repos"), filepath.Join(root, "keys"), repos, f.run, f.sleep)
	if err != nil {
		t.Fatalf("NewManager: %v", err)
	}
	f.calls = nil

	gitErr(t, m.Clone(context.Background(), "infra"), contract.ErrCodeGitDNSFailure)
	if len(f.calls) != 3 {
		t.Errorf("clone attempts = %d, want 3 (a leftover partial checkout must not stop the retry loop)", len(f.calls))
	}
}

func TestManagerCloneAllReportsPerRepoOutcomes(t *testing.T) {
	repos := []RepoConfig{
		{Name: "present", URL: "git@github.com:acme/present.git"},
		{Name: "broken", URL: "git@github.com:acme/broken.git"},
	}
	m, f, reposDir, _ := newTestManager(t, repos, failWith("git@github.com: Permission denied (publickey)."))
	preClone(t, reposDir, "present")

	outcomes := m.CloneAll(context.Background())
	if len(outcomes) != 2 {
		t.Fatalf("CloneAll returned %d outcomes, want 2", len(outcomes))
	}
	if outcomes[0].Name != "present" || !outcomes[0].Skipped || outcomes[0].Err != nil {
		t.Errorf("outcome[0] = %+v, want present/skipped/no-error", outcomes[0])
	}
	if outcomes[1].Name != "broken" || outcomes[1].Skipped {
		t.Errorf("outcome[1] = %+v, want broken/not-skipped", outcomes[1])
	}
	gitErr(t, outcomes[1].Err, contract.ErrCodeGitSSHHandshake)
	if outcomes[1].Attempts != 3 {
		t.Errorf("outcome[1].Attempts = %d, want 3", outcomes[1].Attempts)
	}
	// Only the broken repo may have produced git invocations.
	if len(f.calls) != 3 {
		t.Errorf("CloneAll ran %d commands, want 3: %v", len(f.calls), f.subcommands())
	}
}

func TestManagerEnsureClonedReportsCloneMissing(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	m, f, reposDir, _ := newTestManager(t, repos, nil)

	// D-14: a repo whose clone never succeeded must be reported as
	// git_clone_missing, not surface later as an obscure tofu error.
	err := gitErr(t, m.EnsureCloned("infra"), contract.ErrCodeGitCloneMissing)
	if !strings.Contains(err.Message, m.WorkTree("infra")) {
		t.Errorf("message = %q, want the missing work tree path %q", err.Message, m.WorkTree("infra"))
	}
	gitErr(t, m.EnsureCloned("nope"), contract.ErrCodeRunUnknownRepo)

	preClone(t, reposDir, "infra")
	if err := m.EnsureCloned("infra"); err != nil {
		t.Errorf("EnsureCloned on a present work tree = %v, want nil", err)
	}
	if len(f.calls) != 0 {
		t.Errorf("EnsureCloned ran %d git commands, want 0", len(f.calls))
	}
}

func TestManagerCloneUnknownRepo(t *testing.T) {
	m, _, _, _ := newTestManager(t, nil, nil)
	gitErr(t, m.Clone(context.Background(), "nope"), contract.ErrCodeRunUnknownRepo)
}

func TestManagerSSHEnvCarriesKeyAndKnownHosts(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	m, f, _, keysDir := newTestManager(t, repos, nil)

	if err := m.Clone(context.Background(), "infra"); err != nil {
		t.Fatalf("Clone: %v", err)
	}
	cloneEnv := callAt(t, f, 0).env
	env := strings.Join(cloneEnv, "\n")

	var sshCmd string
	for _, kv := range cloneEnv {
		if strings.HasPrefix(kv, "GIT_SSH_COMMAND=") {
			sshCmd = strings.TrimPrefix(kv, "GIT_SSH_COMMAND=")
		}
	}
	if sshCmd == "" {
		t.Fatalf("GIT_SSH_COMMAND is absent from the clone environment")
	}
	// GIT-03: only the repo's own deploy key, host key pinned, no
	// interactive fallback.
	for _, want := range []string{
		"-i " + filepath.Join(keysDir, "infra.key"),
		"IdentitiesOnly=yes",
		"StrictHostKeyChecking=yes",
		"UserKnownHostsFile=" + filepath.Join(keysDir, "known_hosts"),
		"BatchMode=yes",
	} {
		if !strings.Contains(sshCmd, want) {
			t.Errorf("GIT_SSH_COMMAND = %q, want substring %q", sshCmd, want)
		}
	}
	if !strings.Contains(env, "GIT_TERMINAL_PROMPT=0") {
		t.Errorf("clone environment is missing GIT_TERMINAL_PROMPT=0")
	}
}

// scripted responds per git subcommand; a subcommand absent from the map
// exits 0 with empty output.
func scripted(bySubcommand map[string]CommandResult) func(recordedCall) (CommandResult, error) {
	return func(call recordedCall) (CommandResult, error) {
		if len(call.args) == 0 {
			return CommandResult{}, nil
		}
		if res, ok := bySubcommand[call.args[0]]; ok {
			return res, nil
		}
		return CommandResult{}, nil
	}
}

// newClonedManager is newTestManager plus a materialized working tree,
// so EnsureCloned passes and Pull reaches the git layer.
func newClonedManager(
	t *testing.T,
	repos []RepoConfig,
	respond func(recordedCall) (CommandResult, error),
) (*Manager, *fakeGit, string) {
	t.Helper()
	m, f, reposDir, keysDir := newTestManager(t, repos, respond)
	for _, r := range repos {
		preClone(t, reposDir, r.Name)
	}
	return m, f, keysDir
}

func TestManagerPullUnpinnedRunsFastForward(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	m, f, _ := newClonedManager(t, repos, nil)

	out, err := m.Pull(context.Background(), "infra", false)
	if err != nil {
		t.Fatalf("Pull: %v", err)
	}
	// D-11: an unpinned repo fast-forwards its configured branch.
	if want := []string{"pull", "--ff-only", "origin", "--", "main"}; !argsEqual(callAt(t, f, 0).args, want) {
		t.Errorf("pull args = %v, want %v", callAt(t, f, 0).args, want)
	}
	if callAt(t, f, 0).workDir != m.WorkTree("infra") {
		t.Errorf("pull workDir = %q, want %q", callAt(t, f, 0).workDir, m.WorkTree("infra"))
	}
	if out.Mode != PullModeFastForward {
		t.Errorf("Mode = %q, want %q", out.Mode, PullModeFastForward)
	}
	if out.Name != "infra" {
		t.Errorf("Name = %q, want infra", out.Name)
	}
}

func TestManagerPullUnpinnedUsesConfiguredBranch(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git", Branch: "production"}}
	m, f, _ := newClonedManager(t, repos, nil)

	if _, err := m.Pull(context.Background(), "infra", true); err != nil {
		t.Fatalf("Pull: %v", err)
	}
	if want := []string{"pull", "--ff-only", "origin", "--", "production"}; !argsEqual(callAt(t, f, 0).args, want) {
		t.Errorf("pull args = %v, want %v", callAt(t, f, 0).args, want)
	}
}

func TestManagerPullPinnedFetchesAndChecksOut(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git", Ref: "v1.2.3"}}
	m, f, _ := newClonedManager(t, repos, nil)

	out, err := m.Pull(context.Background(), "infra", false)
	if err != nil {
		t.Fatalf("Pull: %v", err)
	}
	// D-10: a pinned repo re-lands on its ref instead of fast-forwarding.
	if want := []string{"fetch", "origin", "--", "v1.2.3"}; !argsEqual(callAt(t, f, 0).args, want) {
		t.Errorf("fetch args = %v, want %v", callAt(t, f, 0).args, want)
	}
	if want := []string{"checkout", "--detach", "FETCH_HEAD"}; !argsEqual(callAt(t, f, 1).args, want) {
		t.Errorf("checkout args = %v, want %v", callAt(t, f, 1).args, want)
	}
	if out.Mode != PullModeRef {
		t.Errorf("Mode = %q, want %q", out.Mode, PullModeRef)
	}
	for _, sub := range f.subcommands() {
		if sub == "pull" {
			t.Errorf("a pinned repo must not run `git pull`; subcommands = %v", f.subcommands())
		}
	}
}

func TestManagerPullFFOnlyOnPinnedRepoIsRefused(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git", Ref: "v1.2.3"}}
	m, f, _ := newClonedManager(t, repos, nil)

	_, err := m.Pull(context.Background(), "infra", true)
	// D-12 survives as an explicit-conflict guard: a caller that asked
	// for fast-forward semantics against a pinned repo requested two
	// contradictory things.
	gitErr(t, err, contract.ErrCodeGitRefPullIncompatible)
	if len(f.calls) != 0 {
		t.Errorf("the D-12 guard ran %d git commands, want 0: %v", len(f.calls), f.subcommands())
	}
}

func TestManagerPullOnMissingWorkTreeReportsCloneMissing(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	m, f, _, _ := newTestManager(t, repos, nil)

	_, err := m.Pull(context.Background(), "infra", false)
	gitErr(t, err, contract.ErrCodeGitCloneMissing)
	if len(f.calls) != 0 {
		t.Errorf("Pull ran %d git commands on a missing work tree, want 0", len(f.calls))
	}
}

func TestManagerPullUnknownRepo(t *testing.T) {
	m, f, _, _ := newTestManager(t, nil, nil)

	_, err := m.Pull(context.Background(), "nope", false)
	gitErr(t, err, contract.ErrCodeRunUnknownRepo)
	if len(f.calls) != 0 {
		t.Errorf("Pull ran %d git commands for an unknown repo, want 0", len(f.calls))
	}
}

func TestManagerPullNonFastForwardIsTyped(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	m, _, _ := newClonedManager(t, repos, scripted(map[string]CommandResult{
		"pull": {Stderr: "fatal: Not possible to fast-forward, aborting.", ExitCode: 128},
	}))

	_, err := m.Pull(context.Background(), "infra", false)
	gitErr(t, err, contract.ErrCodeGitNonFastForward)
}

func TestManagerPullBadKeyIsTyped(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	m, _, _ := newClonedManager(t, repos, scripted(map[string]CommandResult{
		"pull": {Stderr: "git@github.com: Permission denied (publickey).", ExitCode: 128},
	}))

	_, err := m.Pull(context.Background(), "infra", false)
	gitErr(t, err, contract.ErrCodeGitSSHHandshake)
}

func TestManagerPullMissingRefIsTyped(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git", Ref: "v9.9.9"}}
	m, _, _ := newClonedManager(t, repos, scripted(map[string]CommandResult{
		"fetch": {Stderr: "fatal: couldn't find remote ref v9.9.9", ExitCode: 128},
	}))

	_, err := m.Pull(context.Background(), "infra", false)
	gitErr(t, err, contract.ErrCodeGitRefNotFound)
}

func TestManagerPullReturnsHead(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	m, f, _ := newClonedManager(t, repos, scripted(map[string]CommandResult{
		"rev-parse": {Stdout: "9f1c0de4ab7e5f2c1d3b8a90e7654321fedcba98\n"},
	}))

	out, err := m.Pull(context.Background(), "infra", false)
	if err != nil {
		t.Fatalf("Pull: %v", err)
	}
	if want := "9f1c0de4ab7e5f2c1d3b8a90e7654321fedcba98"; out.Head != want {
		t.Errorf("Head = %q, want %q", out.Head, want)
	}
	if want := []string{"rev-parse", "HEAD"}; !argsEqual(callAt(t, f, 1).args, want) {
		t.Errorf("head lookup args = %v, want %v", callAt(t, f, 1).args, want)
	}
	// The SHA lookup is local: it needs no deploy key.
	for _, kv := range callAt(t, f, 1).env {
		if strings.HasPrefix(kv, "GIT_SSH_COMMAND=") {
			t.Errorf("the rev-parse call must not carry GIT_SSH_COMMAND")
		}
	}
}

func TestManagerPullHeadLookupFailureIsNonFatal(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	m, _, _ := newClonedManager(t, repos, scripted(map[string]CommandResult{
		"rev-parse": {Stderr: "fatal: ambiguous argument 'HEAD'", ExitCode: 128},
	}))

	out, err := m.Pull(context.Background(), "infra", false)
	if err != nil {
		t.Fatalf("a failed HEAD lookup must not fail a pull that succeeded: %v", err)
	}
	if out.Head != "" {
		t.Errorf("Head = %q, want empty", out.Head)
	}
	if out.Mode != PullModeFastForward {
		t.Errorf("Mode = %q, want %q", out.Mode, PullModeFastForward)
	}
}

func TestManagerPullErrorBodyHasNoStderrDump(t *testing.T) {
	rawStderr := "From github.com:acme/infra\n" +
		" ! [rejected]        main -> main (non-fast-forward)\n" +
		"error: failed to push some refs\n" +
		"hint: Updates were rejected because the tip of your current branch is behind\n"
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	m, _, _ := newClonedManager(t, repos, scripted(map[string]CommandResult{
		"pull": {Stderr: rawStderr, ExitCode: 1},
	}))

	_, err := m.Pull(context.Background(), "infra", false)
	gerr := gitErr(t, err, contract.ErrCodeGitNonFastForward)

	// GIT-04: no stack traces or raw output in the surfaced error.
	got := gerr.Error()
	if strings.Contains(got, rawStderr) || strings.Contains(got, "hint: Updates were rejected") {
		t.Errorf("Error() leaked raw git stderr: %q", got)
	}
	if strings.Contains(got, "\n") {
		t.Errorf("Error() must be a single line, got %q", got)
	}
	if !strings.Contains(gerr.Hint, "infra") {
		t.Errorf("hint = %q, want the concrete repo name substituted", gerr.Hint)
	}
}

func TestManagerPullCarriesSSHCredentials(t *testing.T) {
	repos := []RepoConfig{{Name: "infra", URL: "git@github.com:acme/infra.git"}}
	m, f, keysDir := newClonedManager(t, repos, nil)

	if _, err := m.Pull(context.Background(), "infra", false); err != nil {
		t.Fatalf("Pull: %v", err)
	}
	env := strings.Join(callAt(t, f, 0).env, "\n")
	for _, want := range []string{
		"-i " + filepath.Join(keysDir, "infra.key"),
		"UserKnownHostsFile=" + filepath.Join(keysDir, "known_hosts"),
		"IdentitiesOnly=yes",
		"BatchMode=yes",
		"GIT_TERMINAL_PROMPT=0",
	} {
		if !strings.Contains(env, want) {
			t.Errorf("pull environment is missing %q", want)
		}
	}
}

// TestGitChildEnvironmentIsAllowlisted asserts the CR-03 companion on
// the git side: the add-on container environment (SUPERVISOR_TOKEN and
// anything else the Supervisor injects) is not handed to git or to the
// ssh it spawns. Only the allowlisted variables plus the two GIT_*
// settings GIT-03 requires are present.
func TestGitChildEnvironmentIsAllowlisted(t *testing.T) {
	t.Setenv("SUPERVISOR_TOKEN", "supervisor-token-must-not-leak")

	var envs [][]string
	runner := func(_ context.Context, _ string, env []string, _ string, args ...string) (CommandResult, error) {
		envs = append(envs, env)
		if len(args) > 0 && args[0] == "rev-parse" {
			return CommandResult{Stdout: "deadbeef\n"}, nil
		}
		return CommandResult{}, nil
	}

	dir := t.TempDir()
	m, err := NewManager(filepath.Join(dir, "repos"), filepath.Join(dir, "keys"),
		[]RepoConfig{{Name: "infra", URL: "git@example.invalid:org/infra.git"}},
		runner, func(time.Duration) {})
	if err != nil {
		t.Fatalf("NewManager: %v", err)
	}
	// The construction-time safe.directory guard, an SSH-keyed clone
	// and the local HEAD lookup: all three environments.
	if err := m.Clone(context.Background(), "infra"); err != nil {
		t.Fatalf("Clone: %v", err)
	}
	m.Head(context.Background(), "infra")

	if len(envs) < 2 {
		t.Fatalf("recorded %d git invocations, want at least the guard and the clone", len(envs))
	}
	for i, env := range envs {
		for _, kv := range env {
			if strings.HasPrefix(kv, "SUPERVISOR_TOKEN=") {
				t.Errorf("git invocation %d leaked SUPERVISOR_TOKEN", i)
			}
		}
		found := false
		for _, kv := range env {
			if strings.HasPrefix(kv, "PATH=") {
				found = true
			}
		}
		if !found {
			t.Errorf("git invocation %d env = %v, want PATH", i, env)
		}
	}
}
