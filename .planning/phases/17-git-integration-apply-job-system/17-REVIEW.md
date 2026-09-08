---
phase: 17-git-integration-apply-job-system
reviewed: 2026-09-08T13:05:00Z
depth: standard
files_reviewed: 45
files_reviewed_list:
  - iac-runner/DOCS.md
  - iac-runner/Dockerfile
  - iac-runner/README.md
  - iac-runner/build.yaml
  - iac-runner/cmd/runner/main.go
  - iac-runner/cmd/runner/signals.go
  - iac-runner/config.yaml
  - iac-runner/internal/contract/types.go
  - iac-runner/internal/git/errors.go
  - iac-runner/internal/git/errors_test.go
  - iac-runner/internal/git/manager.go
  - iac-runner/internal/git/manager_test.go
  - iac-runner/internal/git/repo.go
  - iac-runner/internal/httpapi/handlers/get_run.go
  - iac-runner/internal/httpapi/handlers/get_run_test.go
  - iac-runner/internal/httpapi/handlers/list_runs.go
  - iac-runner/internal/httpapi/handlers/list_runs_test.go
  - iac-runner/internal/httpapi/handlers/plan.go
  - iac-runner/internal/httpapi/handlers/plan_test.go
  - iac-runner/internal/httpapi/handlers/redaction_audit.go
  - iac-runner/internal/httpapi/handlers/redaction_audit_test.go
  - iac-runner/internal/httpapi/handlers/repos_pull.go
  - iac-runner/internal/httpapi/handlers/repos_pull_test.go
  - iac-runner/internal/httpapi/handlers/write_error.go
  - iac-runner/internal/httpapi/handlers/write_error_test.go
  - iac-runner/internal/httpapi/router.go
  - iac-runner/internal/httpapi/router_test.go
  - iac-runner/internal/jobq/exec.go
  - iac-runner/internal/jobq/exec_test.go
  - iac-runner/internal/jobq/queue.go
  - iac-runner/internal/jobq/queue_test.go
  - iac-runner/internal/jobq/serialization_test.go
  - iac-runner/internal/runs/dir.go
  - iac-runner/internal/runs/dir_test.go
  - iac-runner/internal/runs/ids.go
  - iac-runner/internal/runs/ids_test.go
  - iac-runner/internal/runs/output.go
  - iac-runner/internal/runs/output_test.go
  - iac-runner/internal/runs/redact.go
  - iac-runner/internal/runs/redact_test.go
  - iac-runner/internal/runs/retention.go
  - iac-runner/internal/runs/retention_test.go
  - iac-runner/internal/runs/store.go
  - iac-runner/internal/runs/store_test.go
  - internal/update-version.py
findings:
  critical: 3
  warning: 14
  info: 9
  total: 26
status: issues_found
---

# Phase 17: Code Review Report

**Reviewed:** 2026-09-08T13:05:00Z
**Depth:** standard
**Files Reviewed:** 45
**Status:** issues_found

## Summary

Reviewed the Phase 17 surface: the git manager (`internal/git`), run store/redaction/retention
(`internal/runs`), the tofu job queue and process spawn (`internal/jobq`), the five new HTTP handlers plus the
router, the `cmd/runner` wiring, the add-on manifest/Dockerfile/docs, and the `update-version.py` change.

Baseline is green and reproducibly so: inside `golang:1.25-alpine` with a `tofu` stub on PATH,
`go build ./...`, `go vet ./...` and `go test -race ./...` all pass. Test density is high (7.2k lines of test
for ~3k lines of source) and the taxonomy/status mapping, the traversal guards on `{id}` and `dir`, the
flock+atomic-rename meta write, and the "no stderr on the wire" rule are all genuinely covered.

The defects that matter are in the places the tests do **not** look:

- **SEC-03 redaction is a per-line function with no cross-line state**, so a multi-line PEM private key —
  the exact artifact the `-----BEGIN` rule exists for — is served over the API with only its header line
  masked. Proven with a probe against the real `ReadOutput` path (CR-01).
- **The D-18 plan-artifact path has no consumption and no freshness check.** A `plan.tfplan` stays eligible
  forever, so an apply issued after `POST /v1/repos/{name}/pull` silently hands tofu a plan built against
  the pre-pull commit (CR-02).
- **`Env: os.Environ()`** forwards the whole add-on container environment — including `SUPERVISOR_TOKEN`,
  usable against the Core API because `config.yaml` sets `homeassistant_api: true` — into every `tofu` child,
  i.e. into arbitrary operator IaC and third-party providers (CR-03).

Three further behaviours were confirmed empirically rather than argued: the "join the scanners before Wait"
invariant in `DefaultExec` is void for every command longer than 10s and emits a spurious WARN per invocation
(WR-01); the `?page=` arithmetic overflows silently and serves the wrong window (WR-03); and the redaction
pattern set does not match real Cloudflare R2 credential formats or credentials embedded in a URL (WR-02),
despite r2 being the default backend.

Several findings are documentation asserting behaviour the code does not have (WR-11, WR-12, IN-03, and the
`repos` re-validation claim behind WR-04/WR-07). Those are treated as defects, not nits: DOCS.md is the
operator contract for this add-on.

No structural pre-pass was supplied with this review, so there is no fallow-findings section.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Multi-line PEM private keys pass SEC-03 redaction almost intact

**File:** `iac-runner/internal/runs/redact.go:65-71` (with `iac-runner/internal/runs/output.go:206-223`)

**Issue:** `Redact` is invoked once per physical output line and holds no state between calls. The PEM rule
therefore masks only the line that *contains* `-----BEGIN`; every base64 body line that follows is a separate
call with no memory of the header. The comment at `redact.go:66-68` asserts the opposite — "A PEM header means
everything around it is key material. There is no safe partial redaction of a private key, so the line goes as
a whole" — but "everything around it" lives on other lines, which are untouched. The 40-char AWS pattern does
not incidentally catch them either: standard PEM wrapping is 64 characters.

Proven against the real write→read path (`Store.OpenOutput` → `WriteLine` → `Store.ReadOutput`), which is what
`GET /v1/runs/{id}` serves:

```
--- multi-line PEM served over the API ---
  "<redacted>"
  "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtz"
  "c2gtZWQyNTUxOQAAACBHo3lC0M8kQ1c4v3S9pRQwZ1kZ0oXwYnZ9V0hZKk1v9wAA"
  "-----END OPENSSH PRIVATE KEY-----"
  redactions=1
```

A `tls_private_key` resource in a plan diff, a `terraform output` of a key, or a heredoc'd key in a `.tfvars`
echoed by an error is enough to reach this. `redact_test.go:41-50` tests only single-line PEM inputs, which is
why the gap survived.

**Fix:** redaction has to be stateful across the page. Redact at the page level and latch on the header until
`-----END` (or until a non-base64 line), e.g.:

```go
// RedactPage redacts a whole window; PEM bodies span lines, so the
// BEGIN latch must survive between them.
func RedactPage(lines []string) ([]string, int) {
	out := make([]string, 0, len(lines))
	count := 0
	inPEM := false
	for _, l := range lines {
		switch {
		case strings.Contains(l, pemHeaderPrefix):
			inPEM = true
			out = append(out, redactedMarker)
			count++
		case inPEM:
			out = append(out, redactedMarker)
			count++
			if strings.Contains(l, pemFooterPrefix) { // "-----END"
				inPEM = false
			}
		default:
			red, n := Redact(l)
			count += n
			out = append(out, red)
		}
	}
	return out, count
}
```

and have `windowCollector` buffer the window's raw text so `ReadOutput` calls `RedactPage` once instead of
`Redact` per line. Note that a page boundary must not reset the latch: start the latch scan from the first
line of the file, or persist "inside a PEM" as part of the scan that already walks every line for
`TotalLines`.

### CR-02: An apply silently reuses a stale plan artifact — including one built before a `pull`

**File:** `iac-runner/internal/jobq/exec.go:141-143, 155-185`

**Issue:** `priorPlanFile` selects the newest `succeeded` plan run for `(repo, dir)` whose `plan.tfplan` still
exists, and `runJob` appends it to `tofu apply`. Nothing ever invalidates that artifact:

- the file is not removed after the apply consumes it,
- `meta.PlanFile` is not cleared,
- there is no freshness constraint at all — no commit/ref comparison, no age bound.

Two concrete consequences:

1. `POST /v1/repos/homelab/pull` advances the working tree to a new commit, then `POST /v1/apply` passes the
   plan file generated against the **pre-pull** commit. OpenTofu applies the saved plan, not the current
   configuration — the operator gets the previous revision's changes applied and no signal that their pull was
   ignored. This is the data-integrity case.
2. Two applies in a row with no intervening plan hand the same file to tofu twice. The second is rejected as a
   stale plan (the state no longer matches what the plan was created against), so `/v1/apply` becomes
   non-idempotent for a reason no error message in this codebase explains.

D-17's wording ("no `-out` flag, no plan file consumption") implies the D-18 path *does* consume. It does not.

**Fix:** make consumption explicit and add a freshness gate. Minimum:

```go
// after a successful apply that consumed prior:
if prior != "" && res.ExitCode == 0 {
	if err := os.Remove(prior); err != nil && !errors.Is(err, os.ErrNotExist) {
		slog.Warn("jobq.plan_artifact_remove_failed", "path", prior, "err", err.Error())
	}
	// and clear meta.PlanFile on the plan run so priorPlanFile stops finding it
	if _, err := q.store.Update(planRunID, func(m *runs.Meta) error {
		m.PlanFile = ""
		return nil
	}); err != nil { /* log */ }
}
```

plus a freshness check before use: record the repo HEAD SHA in `runs.Meta` at plan time and skip the artifact
in `priorPlanFile` when the current `git rev-parse HEAD` differs. Falling back to an inline apply (already a
supported D-17 mode) is the safe default whenever freshness cannot be established.

### CR-03: The whole container environment — including `SUPERVISOR_TOKEN` — is handed to every tofu child

**File:** `iac-runner/internal/jobq/exec.go:90-96` (also `iac-runner/internal/git/manager.go:252-255, 163, 434`)

**Issue:** `Env: os.Environ()` passes the add-on container's full environment to the spawned `tofu` process.
`tofu` then executes arbitrary operator IaC: third-party providers downloaded from a registry, `local-exec`
provisioners, external data sources. Everything in the runner's environment is readable by all of them.

`SUPERVISOR_TOKEN` is injected into add-on containers by the Supervisor, and `iac-runner/config.yaml:12` sets
`homeassistant_api: true`, which is what makes that token usable against `http://supervisor/core/api` (state
writes, service calls). `iac-runner` is the only add-on in this repository that requests that flag
(`grep -l homeassistant_api */config.yaml`), while `README.md:6-7` advertises the add-on as "no
`SUPERVISOR_TOKEN` required". The runner's own security posture — bearer auth, Tailscale bind-gate, chmod-600
key enforcement — is undermined by handing a Home Assistant API credential to code the runner does not control.

The same `os.Environ()` pattern is used for git (`manager.go:252`), where the child is trusted but the
allowlist argument is identical.

**Fix:** build an explicit environment instead of inheriting. `ExecSpec.Env` is already a field, so this is
local to `runJob`:

```go
// tofuEnv is the ONLY environment a tofu child receives. Inheriting
// os.Environ() would hand SUPERVISOR_TOKEN (and anything else the
// Supervisor injects) to arbitrary provider code.
func tofuEnv() []string {
	const keep = "PATH HOME TMPDIR LANG TZ"
	var env []string
	for _, k := range strings.Fields(keep) {
		if v, ok := os.LookupEnv(k); ok {
			env = append(env, k+"="+v)
		}
	}
	// TF_* / TOFU_* knobs are the documented operator surface.
	for _, kv := range os.Environ() {
		if strings.HasPrefix(kv, "TF_") || strings.HasPrefix(kv, "TOFU_") {
			env = append(env, kv)
		}
	}
	return env
}
```

When the deferred backend-credential projection lands (see WR-14), it appends to this slice rather than
relying on inheritance. Do the same for `git.Manager.sshEnv`, and if the HA API is genuinely unused, drop
`homeassistant_api: true` from `config.yaml` so the token carries no Core-API authority in the first place.

## Warnings

### WR-01: `DefaultExec` trips its own "bounded join" on every job longer than 10s

**File:** `iac-runner/internal/jobq/exec.go:241-252`

**Issue:** `joinTimer` is armed immediately after `cmd.Start()`, not when the deadline fires. `killGrace` is
10s in production, so any command that runs longer than 10 seconds — i.e. every real `tofu init`, `plan` and
`apply` — takes the timeout branch, logs `jobq.output_join_timeout` at WARN, and proceeds to `cmd.Wait()`
while the scanners are still running. The comment's guarantee ("Join the scanners BEFORE `cmd.Wait()` so no
line emitted just before exit is lost") is therefore void on the normal path, and the operator gets 2-3
spurious warnings per job. Output is still captured in practice only because `Wait` blocks until the process
exits and `WaitDelay` gives the scanners another `killGrace` afterwards.

Reproduced with `DefaultExec` against `sh -c 'echo first; sleep 12; echo last'`:

```
[t= 0.0s] stdout: "first"
2026/09/08 12:56:06 WARN jobq.output_join_timeout path=/bin/sh
[t=12.0s] stdout: "last"
```

`exec_test.go` only exercises short-lived commands, so the suite never sees it.

**Fix:** the bound only needs to exist *after* the process is gone. Wait on the process first, then join with a
deadline:

```go
waitErr := cmd.Wait() // WaitDelay closes the pipes if a grandchild holds them
joinTimer := time.NewTimer(killGrace)
defer joinTimer.Stop()
select {
case <-scanned:
case <-joinTimer.C:
	slog.Warn("jobq.output_join_timeout", "path", spec.Path)
}
```

`cmd.WaitDelay` already guarantees the pipes get closed, which is what unblocks the scanners — so this
ordering keeps the anti-wedge property while removing the false positive.

### WR-02: The SEC-03 pattern set misses real R2 credential formats and credentials embedded in URLs

**File:** `iac-runner/internal/runs/redact.go:28-33, 50`

**Issue:** the two token regexes are `^[A-Z0-9]{20}$` (AWS-style access key id) and `^[A-Za-z0-9/+=]{40}$`
(AWS-style secret). Cloudflare R2 — the **default** backend (`cmd/runner/main.go:29`) — issues a 32-character
lowercase-hex access key id and a 64-character lowercase-hex secret. Neither matches. Additionally, `/`, `@`
and `.` are absent from `tokenDelimiters`, so a credential inside a URL is never isolated as a token.

Probed against `Redact`:

```
n=0 in="access_key_id = 3a1f9c0e7b25d48af6301bc9e2d7845f"          # real R2 access key id shape
n=0 in="secret = 9f2c1e4b...8e5d2a7f"                              # real R2 secret shape (64 hex)
n=0 in="https://AKIAIOSFODNN7EXAMPLE:wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY@example.com/x"
n=1 in="AKIAIOSFODNN7EXAMPLE"                                      # only the bare AWS id is caught
```

The `^…$` patterns come from ROADMAP SC-10, so the implementation matches its spec — the spec is what is
incomplete, and DOCS.md repeats it as if it were coverage ("The patterns are R2/AWS access keys (20-char
upper-alnum)…").

**Fix:** add the R2 shapes and make URL-embedded credentials reachable:

```go
// r2HexKeyRe covers Cloudflare R2: 32-hex access key id, 64-hex secret.
var r2HexKeyRe = regexp.MustCompile(`^[0-9a-f]{32}$|^[0-9a-f]{64}$`)
```

and add `@` plus `/` handling for the `scheme://user:pass@host` shape — either a dedicated pre-pass regex
(`(?i)(https?|ssh)://[^/\s:@]+:[^/\s@]+@` → replace the userinfo with the marker) or a secondary split on
`@` before token matching. Raise the spec change through the requirement, and extend `redact_test.go` with the
four probe lines above.

### WR-03: `?page=` arithmetic overflows and serves the wrong window

**File:** `iac-runner/internal/httpapi/handlers/get_run.go:96, 171-180`, `iac-runner/internal/runs/output.go:156`

**Issue:** `parsePositiveInt` accepts any positive `int` for `page` (only `page_size` is capped), and
`ReadOutput` computes `lo = (page-1)*pageSize`, `hi = page*pageSize` with no overflow check. For large `page`
both products wrap; picking the right value makes `lo` wrap negative while `hi` wraps positive, and the
handler serves page 1's content while reporting the caller's absurd page number.

Reproduced against `Store.ReadOutput` with 10 stored lines and `pageSize=100`:

```
page=1                  -> lines=10 total=10 reported_page=1
page=2                  -> lines=0  total=10 reported_page=2
page=92233720368547759  -> lines=0  total=10 reported_page=92233720368547759
page=184467440737095517 -> lines=10 total=10 reported_page=184467440737095517   <-- page 1's content
```

Window size stays bounded by `pageSize`, so this is a correctness bug rather than a memory-exhaustion one, but
a client paging to termination can be handed data it already consumed under a page number it will never
revisit.

**Fix:** bound `page` where every other pagination parameter is already bounded — in the handler, mirroring the
`page_size` clamp — and add a defensive check in the store:

```go
// get_run.go
const maxOutputPage = 1 << 20 // 1M pages * max 1000 lines covers any real log
page := parsePositiveInt(q.Get("page"), 1)
if page > maxOutputPage {
	page = maxOutputPage
}

// output.go, after the pageSize clamp
if page > (math.MaxInt/pageSize) {
	return OutputPage{Lines: []string{}, Page: page, PageSize: pageSize}, nil
}
```

### WR-04: `url`, `ref` and `branch` reach git's argv unvalidated

**File:** `iac-runner/internal/git/repo.go:63-77`, `iac-runner/internal/git/manager.go:336-370, 411-423`

**Issue:** `RepoConfig.Validate` documents itself as the guard for "a hand-edited /data/options.json", but it is
strictly weaker than the Supervisor schema it claims to mirror:

- `url` is only rejected for an `http://` / `https://` prefix. The schema requires `^(git@|ssh://).+$`; the Go
  guard accepts anything else, including git's `ext::` transport (`ext::sh -c …`, which executes a command) and
  any value starting with `-`, which `git clone` parses as an option (`--upload-pack=…`, `--config=…`) because
  no `--` separator is used before positional arguments.
- `ref` and `branch` are not validated at all, in either the schema (`str?`) or Go, yet both land in positional
  argv slots: `git fetch origin <ref>` (`manager.go:362`) and `git pull --ff-only origin <branch>`
  (`manager.go:419`).

This is operator-supplied configuration, not request input, so it is not a remote-attacker path — but the code
asserts a defense-in-depth guard it does not implement, and the fix is cheap.

**Fix:** finish the guard and separate options from operands:

```go
var refRe = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._/+-]{0,254}$`) // no leading '-'

func (r RepoConfig) Validate() error {
	// … name checks …
	if !regexp.MustCompile(`^(git@|ssh://).+$`).MatchString(strings.TrimSpace(r.URL)) {
		return fmt.Errorf("git: repo %q url must match ^(git@|ssh://).+$", r.Name)
	}
	for field, v := range map[string]string{"ref": r.Ref, "branch": r.Branch} {
		if v != "" && !refRe.MatchString(v) {
			return fmt.Errorf("git: repo %q %s %q is not a valid ref name", r.Name, field, v)
		}
	}
	return nil
}
```

and add `"--"` before the positional operands in `cloneAttempt` / `landOnRef` / `Pull`
(`git clone --branch <b> --single-branch -- <url> <dir>`, `git fetch origin -- <ref>`).

### WR-05: No timeout on any git invocation — a hanging remote wedges startup before the listener binds

**File:** `iac-runner/cmd/runner/main.go:235`, `iac-runner/internal/git/manager.go:246-256`, `iac-runner/internal/httpapi/handlers/repos_pull.go:109`

**Issue:** `CloneAll(context.Background())` runs before `srv.ListenAndServe()` with no deadline, and
`GIT_SSH_COMMAND` sets no `ConnectTimeout`. A blackholed or firewalled remote (a Tailscale peer that is down,
a DNS answer that routes nowhere) leaves each clone attempt hanging on TCP, retried three times per repo,
serially across repos. The process never reaches `listening`, so `/healthz` cannot answer and the operator
sees an add-on that "started" with no diagnosis. ROADMAP SC-2 ("a failed clone never blocks startup") holds
for a *failing* clone but not for a *hanging* one.

`Pull` inherits only `r.Context()`, so a pull is bounded by the client's patience — and since `http.Server`
sets no `ReadTimeout`/`IdleTimeout` (WR-10), a `curl` left open holds a git process indefinitely.

**Fix:** bound both paths and let ssh fail fast:

```go
// main.go
cloneCtx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
defer cancel()
for _, outcome := range gitMgr.CloneAll(cloneCtx) { … }

// manager.go sshEnv
"ssh -i %s -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes " +
	"-o UserKnownHostsFile=%s -o BatchMode=yes -o ConnectTimeout=10"
```

and wrap the handler's pull in `context.WithTimeout(r.Context(), 2*time.Minute)`.

### WR-06: Runs can become permanently stuck in `queued`, and their directories are never reclaimed

**File:** `iac-runner/internal/jobq/queue.go:325-335, 273-283`, `iac-runner/internal/runs/retention.go:119-131`

**Issue:** three paths converge on unreclaimable state under `/data/runs`:

1. `work` returns early when the `running` status `Update` fails (`queue.go:332-334`), logging and writing **no
   terminal state**. The run stays `queued` forever.
2. `Rotate` skips any directory whose `Load` returns `ErrRunNotFound` (`retention.go:126-130`) and
   unconditionally skips `queued`/`running` (`retention.go:132`). So both a stuck-`queued` run and a run with a
   corrupt or missing `meta.json` are exempt from retention permanently.
3. `Submit` returns the `store.Create` error without removing the directory `MkdirAll` just created
   (`queue.go:280-283`), so a `writeMeta` failure (full disk — precisely when this matters) leaves a
   meta-less directory behind, which (2) then never reclaims.

Net effect: a full-disk or I/O-error episode leaves permanent garbage under `/data/runs` plus runs the operator
sees as `queued` with no explanation, and the add-on cannot recover without manual `rm -rf`.

**Fix:** (a) write the terminal state on the early-return path —

```go
if _, err := q.store.Update(runID, /* running */); err != nil {
	slog.Error("jobq.status_update_failed", "run_id", runID, "err", err.Error())
	q.fail(runID, contract.ErrCodeApplyFailed, "the run could not be marked running")
	return
}
```

(b) clean up in `Submit`: `if err := q.store.Create(...); err != nil { _ = os.RemoveAll(q.store.Dir(runID)); … }`;
and (c) give `Rotate` an age-based fallback for directories it cannot parse — when `Load` fails and the
directory's mtime is older than `maxAge`, delete it instead of skipping it.

### WR-07: A malformed `/data/options.json` is silently half-applied

**File:** `iac-runner/cmd/runner/main.go:119-123`

**Issue:** `_ = json.Unmarshal(b, &opts)` with the comment "fall back to defaults on parse failure". That is not
what `encoding/json` does: it populates fields until it hits the error and leaves the rest at their previous
values. A wrong type on `repos` (or on any field before it) therefore boots the runner with a **partial**
configuration — most damagingly an empty `repos` list, which makes every `/v1/plan` answer `run_unknown_repo`
with nothing in the log to explain why.

This also contradicts the file's own stance three times over (`bind_resolution_failed`,
`state_backend_init_failed`, `keys_validation_failed` are all `os.Exit(1)`, commented "Refusal is fatal — no
degraded mode") and DOCS.md:96, which states the runner "refuses to start on a malformed or duplicated entry".

**Fix:** treat it like every other startup input:

```go
if b, err := os.ReadFile("/data/options.json"); err == nil {
	if err := json.Unmarshal(b, &opts); err != nil {
		slog.Error("options_parse_failed", "err", err.Error())
		os.Exit(1)
	}
} else if !os.IsNotExist(err) {
	slog.Error("options_read_failed", "err", err.Error())
	os.Exit(1)
}
```

### WR-08: Same-repo waiters occupy `max_parallel_jobs` slots, starving other repos for up to `apply_timeout`

**File:** `iac-runner/internal/jobq/queue.go:258-265, 315-322`

**Issue:** the global semaphore is acquired in `Submit`, before the worker blocks on the per-repo mutex in
`work`. A job waiting its turn on a repo therefore holds a capacity slot for the entire wait, bounded only by
`acquire(lock, q.applyTimeout)` — 60 minutes by default. With the default `max_parallel_jobs: 4`, four queued
applies against one repo pin the whole runner: every other repo's `/v1/plan` gets 503
`apply_capacity_exhausted` while nothing is actually executing on three of those slots.

That contradicts DOCS.md:132-133 ("Only cross-repo jobs actually run in parallel" is offered as reassurance
about parallelism, not as a starvation warning) and D-06's stated purpose of making saturation mean "the runner
is busy".

**Fix:** either acquire the repo mutex before the semaphore slot (so waiting does not consume capacity), or
size the lock wait independently of the job budget and account for waiters separately:

```go
// separate, much smaller bound for the serialization wait
var lockWait = 5 * time.Minute
if !acquire(lock, lockWait) { … }
```

The cleanest form is a per-repo waiting queue that holds no global slot, with the slot taken immediately before
`runJob`. At minimum, document the interaction and count waiters in the capacity decision.

### WR-09: D-18 silently degrades to inline apply once a repo has 100 newer succeeded runs

**File:** `iac-runner/internal/jobq/exec.go:159-163`

**Issue:** `priorPlanFile` asks `store.List` for `Limit: contract.MaxRunListLimit` (100) succeeded runs for the
repo and then filters for `Kind == plan && Dir == cleanDir`. The limit is applied *before* the kind/dir filter,
so on a repo with more than 100 newer succeeded runs — trivially reached by a polling CI that applies often, or
by several `dir`s sharing a repo — the matching plan falls outside the window and the apply quietly becomes an
inline apply. No log record marks the degradation.

**Fix:** query without the response cap, or push the filter into the store:

```go
metas, err := q.store.List(runs.ListFilter{
	Repo:   repo,
	Status: contract.RunStatusSucceeded,
	Kind:   contract.RunKindPlan, // new filter field
	Dir:    cleanDir,             // new filter field
	Limit:  1,
})
```

`ListFilter` already exists as the extension point, and `retention.go:6-11` documents that the RUN-05 caps are
"exactly wrong" for non-API callers — the same reasoning applies here.

### WR-10: No request body limit and no server read/idle timeouts

**File:** `iac-runner/internal/httpapi/handlers/plan.go:86-95`, `iac-runner/internal/httpapi/handlers/repos_pull.go:155-157`, `iac-runner/cmd/runner/main.go:378-382`

**Issue:** all three POST handlers wrap `r.Body` in a `json.Decoder` with no `http.MaxBytesReader`, so a
multi-gigabyte string value for `dir` is read into memory before validation rejects it. `http.Server` sets only
`ReadHeaderTimeout`; without `ReadTimeout`/`WriteTimeout`/`IdleTimeout`, a client that opens connections and
sends nothing (or dribbles a body) holds them indefinitely, including against the unauthenticated `/` and
`/healthz`.

**Fix:**

```go
// per handler, before decoding
r.Body = http.MaxBytesReader(w, r.Body, 64*1024)

// main.go
srv := &http.Server{
	Addr:              bindIP + ":8125",
	Handler:           router,
	ReadHeaderTimeout: 5 * time.Second,
	ReadTimeout:       30 * time.Second,
	WriteTimeout:      60 * time.Second,
	IdleTimeout:       120 * time.Second,
}
```

`WriteTimeout` must stay above the largest expected `GET /v1/runs/{id}` response; if the multi-megabyte-line
case (D-09/D-24) can exceed it, exempt that route rather than dropping the timeout.

### WR-11: DOCS.md documents an HTTP 423 `locked` response that does not exist

**File:** `iac-runner/DOCS.md:513`

**Issue:** "Apply fails fast with HTTP 423 (`locked`) when another apply holds the lock." No handler returns
423, `statusForCode` has no such row, and there is no `locked` error code in `contract/types.go`. The
implemented behaviour is the opposite and is documented correctly elsewhere in the same file (DOCS.md:132-133,
RUN-06): a same-repo apply is accepted with 202 and serializes. A client written against this sentence will
wait for a status it can never receive.

**Fix:** delete the sentence, or replace it with the actual contract:

```markdown
When another apply holds the per-repo lock the second request is still accepted with `202` and serializes
behind the first (RUN-06). Only if the lock is held longer than `apply_timeout_minutes` does the run reach a
terminal `error_code: "apply_already_running"`.
```

### WR-12: DOCS.md promises a `redaction.audit` record per request; the code is silent on zero redactions

**File:** `iac-runner/DOCS.md:485-487` vs `iac-runner/internal/httpapi/handlers/redaction_audit.go:48-51`

**Issue:** DOCS states "Each `GET /v1/runs/{id}` emits one `redaction.audit` log record for the page it served
… so an operator can tell 'nothing was redacted' from 'redaction never ran'." `auditRedactions` returns early
when `page.Redactions <= 0`, which makes those two cases *indistinguishable* — the exact question the
documentation says the record answers. The early return is a deliberate, well-argued anti-noise decision
(`redaction_audit.go:38-43`, asserted by `TestAuditRedactionsSilentWhenNothingRedacted`); the documentation was
not updated to match.

**Fix:** correct DOCS.md to describe the implemented contract:

```markdown
A `redaction.audit` record is emitted only for pages where at least one redaction occurred (a running apply is
polled repeatedly, and a zero-record per poll would bury the ones that matter). No record means nothing
credential-shaped was withheld from that page.
```

If the distinguishability property is actually required by SC-10, emit at DEBUG for the zero case instead.

### WR-13: `update-version.py` can create and push a `<addon>/v` tag when `config.yaml` cannot be parsed

**File:** `internal/update-version.py:344-346, 411-421`

**Issue:** `update_config_yaml` returns `(False, "", "")` when `config.yaml` is missing, has no matching
`version:` line, or raises. `main()` never checks `config_new` before use: `success_count == 0` prints
"✅ Already at target version — confirming tag" and calls `create_and_push_tag(config_new, …)` with an empty
string, producing and pushing the tag `<addon>/v`. Tag pushes trigger the per-add-on build workflows, so a
malformed manifest turns into a bogus release ref. The diff under review changed the two failure-message
`f`-strings to `config_new` (fixing a `NameError` on `new_v`), which makes this the remaining hole on the same
path.

**Fix:** guard before tagging:

```python
if not config_new:
    print("❌ Could not determine the config.yaml version — refusing to tag")
    return 1
```

placed immediately after the three `update_*` calls, so both the dry-run and the real tag path are covered.

### WR-14: `exec.go` documents a backend-credential env projection that does not exist

**File:** `iac-runner/internal/jobq/exec.go:91-93`

**Issue:** "os.Environ() carries the backend credentials 17-07 exports (AWS_ACCESS_KEY_ID and friends) plus
TF_* knobs." Nothing in the repository exports them — no `os.Setenv`, no export in `run.sh`, and
`statebackend.Backend` exposes only `CredentialFiles()` (consumed solely by the SEC-01 validator). Confirmed by
`grep -rn "Setenv\|AWS_ACCESS_KEY_ID" --include="*.go"`. The gap itself is recorded in
`.planning/phases/17-git-integration-apply-job-system/deferred-items.md` and deferred to Phase 19; the stale
comment is not, and it will convince the next reader that credentials flow when `tofu init` against r2/s3
cannot authenticate at all.

**Fix:** make the comment state the current truth and point at the deferral:

```go
// Env is the environment the tofu child sees. NOTE: no backend
// credential projection exists yet (deferred to Phase 19 — see
// 17 deferred-items.md); tofu authenticates only if the operator's
// own IaC supplies credentials another way.
```

Fold this into CR-03's allowlist change so the two land together.

## Info

### IN-01: Exported git API that only tests call

**File:** `iac-runner/internal/git/manager.go:186-188, 284-286`, `iac-runner/internal/git/errors.go:124`

**Issue:** `Manager.Repos()`, `Manager.Clone()` and `git.Classify()` have no non-test caller (`main.go` uses
`CloneAll`; `Classify` is reached only through `newGitError`). Exported surface with no consumer is surface
that has to keep working for no reason.

**Fix:** unexport `Classify` (`classify`) and drop `Repos()`/`Clone()`, or keep them and note the intended
Phase 18 consumer in the doc comment.

### IN-02: `initialScanBufBytes` / `maxScanLineBytes` duplicated across two packages

**File:** `iac-runner/internal/jobq/exec.go:45-48` and `iac-runner/internal/runs/output.go:35, 43`

**Issue:** both constants are declared twice with a comment in each place saying they "mirror" the other. The
D-09/D-24 no-truncation invariant depends on the read ceiling being ≥ the write ceiling, and nothing enforces
that they stay equal.

**Fix:** export them once from `internal/runs` (`runs.InitialScanBufBytes`, `runs.MaxScanLineBytes`) and have
`jobq` reference those.

### IN-03: `write_error.go` claims absolute paths never reach the wire; several messages carry them

**File:** `iac-runner/internal/httpapi/handlers/write_error.go:98-102`, `iac-runner/internal/git/manager.go:219-222`, `iac-runner/internal/git/errors.go:71, 93, 110`

**Issue:** the comment asserts "Raw stderr, error strings from os/exec, stack traces and absolute paths never
reach this function (GIT-04)". `EnsureCloned`'s message interpolates `m.WorkTree(name)` (`/data/repos/<name>`)
and several hints name `/data/keys/<name>.key` and `/data/repos/<name>/`. The disclosure is harmless — these
are fixed, documented container paths, and the hints are deliberately actionable — but the stated invariant is
not the one being enforced.

**Fix:** narrow the comment to what is actually guaranteed ("no captured stderr, no wrapped `os/exec` error, no
stack trace; the fixed `/data/...` paths in a hint are intentional and documented in DOCS.md").

### IN-04: A malformed JSON body reports `run_invalid_dir`

**File:** `iac-runner/internal/httpapi/handlers/plan.go:91-94`, `iac-runner/internal/httpapi/handlers/repos_pull.go:104-106`, `iac-runner/internal/httpapi/handlers/list_runs.go:69-72`

**Issue:** `run_invalid_dir` is reused as the generic request-shape slot for a malformed body on `/v1/plan`,
`/v1/apply` and `/v1/repos/{name}/pull`, and for a bad `?status=` on `/v1/runs`. A client branching on
`error_code` — which DOCS.md:400 calls "the contract" — cannot distinguish "your JSON is broken" from "your
`dir` escapes the repo", and on `/v1/runs` the code names a field the request does not even have. Each handler
documents this as a deliberate choice to avoid a contract change.

**Fix:** D-20 makes new codes additive, so add `run_invalid_request` (400) to `contract/types.go` plus a
DOCS.md row, and use it for body/query-shape failures. Keep `run_invalid_dir` for `dir` only.

### IN-05: `ValidateDir`'s "can never escape the working tree" does not hold against symlinks

**File:** `iac-runner/internal/runs/dir.go:30-32`, `iac-runner/internal/jobq/exec.go:66`

**Issue:** the comment states that rejecting `..` means "the run can never escape the repo working tree". The
check is purely lexical, so a symlink committed inside the repo (`envs -> /etc`) makes `dir=envs` resolve
outside `/data/repos/<name>/`. Exploitability is nil in practice — anyone who can commit that symlink can also
make tofu execute arbitrary code via a provisioner — but the invariant as written is stronger than the code.

**Fix:** either soften the comment, or resolve and verify after joining:

```go
resolved, err := filepath.EvalSymlinks(workDir)
if err != nil || !strings.HasPrefix(resolved+string(os.PathSeparator), worktree+string(os.PathSeparator)) {
	return ExecResult{ExitCode: -1}, "", fmt.Errorf("jobq: dir resolves outside the repo working tree")
}
```

### IN-06: `NewRouter` accepts nil dependencies and fails at request time

**File:** `iac-runner/internal/httpapi/router.go:52-59`

**Issue:** `gitMgr`, `runStore` and `q` are taken without a nil check; `router_test.go` legitimately passes
`nil` for the git manager and the queue. In production a wiring mistake would surface as a nil-pointer panic
inside `Submit`, recovered by `chimiddleware.Recoverer` into an opaque 500, rather than as a startup failure.

**Fix:** either validate in `NewRouter` (`panic`/error on a nil dependency, with the test switching to
stubs), or state in the doc comment that nil is a supported test-only input and that the corresponding routes
will 500.

### IN-07: Two retention-ticker tests assert nothing

**File:** `iac-runner/internal/runs/retention_test.go:204-233`

**Issue:** `TestStartRetentionTickerStops` ends with `stop(); stop(); cancel(); time.Sleep(50ms)` and
`TestStartRetentionTickerStopsOnContextCancel` is only `cancel(); sleep; stop()`. Both pass as long as nothing
panics; neither observes that the goroutine actually stopped, which is the property under test. A regression
that leaked the goroutine or rotated after `stop()` would stay green.

**Fix:** make the stop observable — seed an over-age run, use a retention short enough that a tick *would*
fire, then assert the directory still exists a few tick-intervals after `stop()`; or add `goleak`-style
goroutine accounting.

### IN-08: The unclassified-git hint reports "git exited 0" when the process could not start

**File:** `iac-runner/internal/git/manager.go:270-275`, `iac-runner/internal/git/errors.go:137-139`

**Issue:** on a runner error (git binary missing, unusable workDir) `CommandResult.ExitCode` is still 0, so the
fallback hint renders as "git exited 0 with an error this add-on does not recognize" — which reads as a
success and sends the operator looking for the wrong thing.

**Fix:** pass a sentinel for the start-failure path, e.g. `newGitError(name, message, res.Stderr, -1, fallback)`
in the `err != nil` branch, and have `Classify` render `-1` as "git could not be started".

### IN-09: JSON bodies are not checked for trailing data

**File:** `iac-runner/internal/httpapi/handlers/plan.go:86-95`, `iac-runner/internal/httpapi/handlers/repos_pull.go:155-164`

**Issue:** `dec.Decode(&body)` consumes the first JSON value and ignores anything after it, so
`{"repo":"a"}{"repo":"b"}` is accepted and the second object is silently discarded. This is the same class of
mistake `DisallowUnknownFields` was added to prevent (a request that does something other than what the caller
wrote).

**Fix:** after a successful decode, assert the stream is exhausted:

```go
if err := dec.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
	// 400 — the body carries more than one JSON value
}
```

---

_Reviewed: 2026-09-08T13:05:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
