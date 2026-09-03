// Package supervisor (extended from Phase 9) wraps the Supervisor
// HTTP API access in a Client struct that re-reads SUPERVISOR_TOKEN
// on every outbound request. The token is injected via an http.RoundTripper
// (not a constructor closure) so the http.Client can be reused for
// concurrent /healthz probes and future /apps calls without leaking
// the token across goroutine boundaries.
//
// The RoundTripper holds a function pointer to the env-reader so the
// H-1 PITFALLS contingency ("token may rotate across Supervisor
// restart") is handled automatically: every call to RoundTrip reads
// os.Getenv("SUPERVISOR_TOKEN") afresh. Phase 9's H-1 spike confirmed
// the token is empirically stable across restarts, so the re-read is
// a cheap defensive measure, not a hot-path optimization.
package supervisor

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"terraform-bridge/contract"
)

// ErrNotFound is returned by GetAddonInfo when both Supervisor V2
// (/apps/{slug}/info) and V1 (/addons/{slug}/info) return HTTP 404,
// OR when V2 returns HTTP 403 Forbidden AND V1 returns HTTP 404
// (relaxed fallback for Supervisor versions that disable per-slug
// V2 lookups). Callers (the /v1/addons/{slug}/info handler) translate
// this to HTTP 404 + {error_code: "not_found"}. Other supervisor
// client errors (network failure, 5xx, malformed JSON) propagate
// without ErrNotFound so callers can distinguish "the add-on
// doesn't exist" from "Supervisor is broken".
var ErrNotFound = errors.New("supervisor: not found")

// Sentinel errors added by Phase 12 + the BRIDGE-09 error-code map.
// All sentinels wrap their respective Phase-9/Phase-11 supervisors
// errors so errors.Is works inside MapError's switch
// (CONTEXT D-25 + BRIDGE-09 traceability).
//
// MapError translates each sentinel into an (HTTP status, error_code)
// pair. Callers (Phase 12 handlers + future Provider) compare via
// errors.Is, never by string matching.

// ErrAlreadyInstalled is returned by Install when Supervisor reports
// HTTP 409 "already installed". Per CONTEXT D-26 the install handler
// treats this as an ADOPTION signal (fall through to GET info + 200
// + payload) rather than an error.
var ErrAlreadyInstalled = errors.New("supervisor: already installed")

// ErrCriticalAddon is returned by Uninstall when the slug is on the
// Bridge's critical_addons list. Per CONTEXT D-09..D-11 the
// critical_addons guard lives in the handler, not the supervisor
// client; this sentinel is reserved for future Supervisor-side
// rejections where Supervisor itself blocks a destructive op against
// a critical slug.
var ErrCriticalAddon = errors.New("supervisor: critical addon protected")

// ErrPreventedDestroy is reserved for Phase 13's Provider lifecycle
// integration; Bridge never emits it in Phase 12.
var ErrPreventedDestroy = errors.New("supervisor: prevented destroy")

// ErrLocked is returned by any mutating call when Supervisor reports
// HTTP 423 (slug currently locked by another in-flight mutation).
// CONTEXT D-13: handler maps to 423 + {error_code: "locked"} via
// MapError.
var ErrLocked = errors.New("supervisor: slug currently locked")

// ErrTransient wraps 5xx responses + transport errors. The
// supervisor handler does not let the Provider distinguish "broken"
// from "unreachable" by status alone — both surface as 502 +
// upstream_error per Phase 11.
var ErrTransient = errors.New("supervisor: transient failure")

// OptionsValidateDiagnostic mirrors Supervisor's
// /apps/{slug}/options/validate envelope so the Bridge can
// surface valid + pwned diagnostics to the Provider (BRIDGE-08).
type OptionsValidateDiagnostic struct {
	Message string `json:"message"`
	Valid   bool   `json:"valid"`
	Pwned   *bool  `json:"pwned,omitempty"`
}

// Client wraps http.Client with the SUPERVISOR_TOKEN injection. The
// zero value is not usable; construct via NewClient.
type Client struct {
	httpClient *http.Client
	baseURL    string
	tokenFn    func() string
}

// NewClient returns a Client whose base URL is the in-container
// Supervisor alias ("http://supervisor"). tokenFn is called on
// every outbound request; pass supervisor.ReadSupervisorToken in
// production. Tests inject a fake.
func NewClient(tokenFn func() string) *Client {
	transport := &tokenInjectingTransport{tokenFn: tokenFn}
	return &Client{
		httpClient: &http.Client{
			Timeout:   2 * time.Second,
			Transport: transport,
		},
		baseURL: "http://supervisor",
		tokenFn: tokenFn,
	}
}

// Ping calls GET /supervisor/ping and returns nil on HTTP 200.
// The /healthz handler (Plan 02) uses this to probe Supervisor
// liveness on every health-check request.
//
// The ctx parameter caps the per-request budget independently of
// the http.Client Timeout so the caller can impose a tighter limit
// (e.g. when /healthz has a 2-second overall budget from HA
// Supervisor's health-check poll).
func (c *Client) Ping(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+"/supervisor/ping", nil)
	if err != nil {
		return fmt.Errorf("supervisor: build ping request: %w", err)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("supervisor: ping: %w", err)
	}
	defer resp.Body.Close()
	// Drain so the connection can be reused.
	_, _ = io.Copy(io.Discard, resp.Body)
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("supervisor: ping status %d", resp.StatusCode)
	}
	return nil
}

// SupervisorInfo is a typed view of the fields Bridge reads from
// /supervisor/info. Phase 11 only needs Version (BRIDGE-10
// supervisor_version); the struct is shaped so future fields can be
// added without breaking the contract.SupervisorInfo JSON shape.
type SupervisorInfo struct {
	Version string // data.supervisor, e.g. "2026.08.0"
}

// GetSupervisorInfo calls GET /supervisor/info and returns the
// Supervisor-reported version. The Bridges /v1/info handler (BRIDGE-10)
// embeds this as the supervisor_version field. The endpoint requires the
// SUPERVISOR_TOKEN (already injected by tokenInjectingTransport); no
// additional auth headers are needed.
//
// On non-200 responses or JSON decode failures the method returns a
// wrapped error whose message never includes the token value
// (PITFALLS S-1 invariant). The /v1/info handler translates this to
// HTTP 502 + {error_code: "upstream_error"} so callers never see
// raw Supervisor internals.
func (c *Client) GetSupervisorInfo(ctx context.Context) (*SupervisorInfo, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+"/supervisor/info", nil)
	if err != nil {
		return nil, fmt.Errorf("supervisor: build info request: %w", err)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("supervisor: info: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		_, _ = io.Copy(io.Discard, resp.Body) // drain for connection reuse
		return nil, fmt.Errorf("supervisor: info status %d", resp.StatusCode)
	}

	var envelope struct {
		Data struct {
			Supervisor string `json:"supervisor"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&envelope); err != nil {
		return nil, fmt.Errorf("supervisor: decode info: %w", err)
	}
	return &SupervisorInfo{Version: envelope.Data.Supervisor}, nil
}

// ListAddons returns every installed add-on. V2 (/apps) is tried
// first; V1 (/addons) is the fallback when V2 returns non-200
// (typically 403 because the host Supervisor does not advertise
// supervisor_api_v2). Both envelopes decode into the same
// []contract.AddOnInfo slice after normalization (the `started`
// field is derived from `state`).
func (c *Client) ListAddons(ctx context.Context) ([]contract.AddOnInfo, error) {
	items, err := c.listAddonsFromPath(ctx, "/apps")
	if err == nil {
		return items, nil
	}
	items, v1Err := c.listAddonsFromPath(ctx, "/addons")
	if v1Err == nil {
		return items, nil
	}
	return nil, err // surface V2 error
}

// listAddonsFromPath tries a single Supervisor endpoint and
// returns the decoded AddOnInfo slice or a wrapped error.
func (c *Client) listAddonsFromPath(ctx context.Context, path string) ([]contract.AddOnInfo, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+path, nil)
	if err != nil {
		return nil, fmt.Errorf("supervisor: build %s request: %w", path, err)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("supervisor: %s: %w", path, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		_, _ = io.Copy(io.Discard, resp.Body) // drain for connection reuse
		return nil, fmt.Errorf("supervisor: %s status %d", path, resp.StatusCode)
	}

	// Supervisor's {result, data:{apps|addons:[...]}} envelope.
	// V2 puts the array under "apps"; V1 under "addons". Decode
	// both shapes by trying V2 first, then V1, accepting whichever
	// produces a non-empty array.
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("supervisor: read %s: %w", path, err)
	}
	var v2Env struct {
		Data struct {
			Apps []contract.AddOnInfo `json:"apps"`
		} `json:"data"`
	}
	if json.Unmarshal(body, &v2Env) == nil && len(v2Env.Data.Apps) >= 0 && containsField(body, `"apps"`) {
		return normalizeStarted(v2Env.Data.Apps), nil
	}
	var v1Env struct {
		Data struct {
			Addons []contract.AddOnInfo `json:"addons"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &v1Env); err != nil {
		return nil, fmt.Errorf("supervisor: decode %s envelope: %w", path, err)
	}
	return normalizeStarted(v1Env.Data.Addons), nil
}

// normalizeStarted derives the `started` boolean from the `state`
// string for any entry where `started` is zero-valued. Supervisor
// V1 omits the `started` field entirely; V2 includes it but the
// state field is the source of truth either way.
func normalizeStarted(items []contract.AddOnInfo) []contract.AddOnInfo {
	for i := range items {
		if !items[i].Started {
			items[i].Started = items[i].State == "started"
		}
	}
	return items
}

// containsField returns true if the JSON body contains the literal
// field name. Used to disambiguate V2 vs V1 envelopes when both
// are technically valid JSON.
func containsField(body []byte, field string) bool {
	return bytes.Contains(body, []byte(field))
}

// GetAddonInfo returns the Supervisor info payload for a single
// add-on. V2 (/apps/{slug}/info) is tried first; on non-200 the
// call falls back to V1 (/addons/{slug}/info). If both endpoints
// return 404 — OR V2 returns 403 Forbidden AND V1 returns 404 —
// the sentinel ErrNotFound is returned (relaxed fallback for
// Supervisor versions that disable per-slug V2 lookups).
func (c *Client) GetAddonInfo(ctx context.Context, slug string) (*contract.AddOnInfo, error) {
	v2Path := "/apps/" + slug + "/info"
	info, v2Err := c.getAddonInfoFromPath(ctx, v2Path)
	if v2Err == nil {
		return info, nil
	}
	v1Path := "/addons/" + slug + "/info"
	info, v1Err := c.getAddonInfoFromPath(ctx, v1Path)
	if v1Err == nil {
		return info, nil
	}
	// Both endpoints 404 (or V2 returns 403 Forbidden AND V1 returns 404)
	// -> surface ErrNotFound. The V2-403 case is included because some
	// Supervisor versions disable per-slug lookups via the V2 endpoint
	// while still returning 404 on V1 for unknown slugs; treating V2's
	// 403 the same as V2's 404 for the "V2 unavailable" branch means
	// such slugs surface as 404 + not_found instead of 502 + upstream_error.
	if (isHTTPStatus(v2Err, http.StatusNotFound) || isHTTPStatus(v2Err, http.StatusForbidden)) && isHTTPStatus(v1Err, http.StatusNotFound) {
		return nil, ErrNotFound
	}
	return nil, v1Err // surface V1 error
}

// getAddonInfoFromPath tries a single Supervisor endpoint and
// returns the decoded AddOnInfo or a wrapped error.
func (c *Client) getAddonInfoFromPath(ctx context.Context, path string) (*contract.AddOnInfo, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+path, nil)
	if err != nil {
		return nil, fmt.Errorf("supervisor: build %s request: %w", path, err)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("supervisor: %s: %w", path, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusNotFound {
		_, _ = io.Copy(io.Discard, resp.Body) // drain for connection reuse
		return nil, fmt.Errorf("supervisor: %s status %d", path, resp.StatusCode)
	}
	if resp.StatusCode != http.StatusOK {
		_, _ = io.Copy(io.Discard, resp.Body) // drain for connection reuse
		return nil, fmt.Errorf("supervisor: %s status %d", path, resp.StatusCode)
	}

	// V2 and V1 share the same /info envelope shape: {result:ok, data:{...}}
	var envelope struct {
		Data contract.AddOnInfo `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&envelope); err != nil {
		return nil, fmt.Errorf("supervisor: decode %s: %w", path, err)
	}
	// Normalize: if upstream omitted started, derive from state.
	if !envelope.Data.Started {
		envelope.Data.Started = envelope.Data.State == "started"
	}
	return &envelope.Data, nil
}

// isHTTPStatus returns true if err is a wrapped "supervisor: ... status NNN"
// error matching the requested status code.
func isHTTPStatus(err error, code int) bool {
	return err != nil && strings.Contains(err.Error(), fmt.Sprintf("status %d", code))
}

// tokenInjectingTransport wraps http.RoundTripper and adds the
// SUPERVISOR_TOKEN bearer header on every request.
type tokenInjectingTransport struct {
	tokenFn func() string
}

// RoundTrip satisfies http.RoundTripper. It reads the token via
// the injected function pointer on EVERY call (H-1 contingency)
// and sets Authorization: Bearer <token> on the outbound request.
func (t *tokenInjectingTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	token := t.tokenFn()
	if token == "" {
		return nil, errors.New("supervisor: SUPERVISOR_TOKEN is empty")
	}
	// Clone the request to avoid mutating the caller's headers.
	clone := req.Clone(req.Context())
	clone.Header.Set("Authorization", "Bearer "+token)
	return http.DefaultTransport.RoundTrip(clone)
}

// ----------------------------------------------------------------------------
// Phase 12: mutating endpoints + MapError helper.
// ----------------------------------------------------------------------------
//
// CONTEXT D-19: uninstall / start / stop / options are SYNC per
// supervisor/api/apps.py (asyncio.shield-awaited server-side).
// CONTEXT D-17: install is ASYNC; the handler (Plan 02) polls
// /jobs/{id}. All methods try V2 /apps/{slug}/{op} first and
// fall back to /addons/{slug}/{op} on non-200 (matching the
// Phase 11 pattern). Status codes 409 (already_installed),
// 423 (locked), 403 (critical_addon | prevented_destroy), 5xx
// (transient) surface as sentinels.

// drainBody discards the response body AFTER a non-200 status so
// the underlying TCP connection can be reused. Mirrors Phase 11's
// Rule 1 fix from 11-01-SUMMARY: drain AFTER the StatusCode check,
// not before. Used by every write method below.
func drainBody(resp *http.Response) {
	if resp == nil || resp.Body == nil {
		return
	}
	_, _ = io.Copy(io.Discard, resp.Body)
}

// classifyStatus maps a Supervisor non-2xx HTTP status to one
// of the package sentinel errors (BRIDGE-09 + CONTEXT D-25).
// The wrapped message preserves the underlying status for logs;
// it never contains token or nonce values (PITFALLS S-1).
func classifyStatus(method, op string, code int) error {
	base := fmt.Sprintf("supervisor: %s %s status %d", method, op, code)
	switch code {
	case http.StatusNotFound:
		return fmt.Errorf("%w: %s", ErrNotFound, base)
	case http.StatusConflict: // 409 — install already done
		return fmt.Errorf("%w: %s", ErrAlreadyInstalled, base)
	case http.StatusLocked: // 423
		return fmt.Errorf("%w: %s", ErrLocked, base)
	case http.StatusForbidden: // 403 — default mapping is critical_addon; prevented_destroy is detected per-call if needed
		return fmt.Errorf("%w: %s", ErrCriticalAddon, base)
	default:
		// 5xx + unhandled 4xx both surface as ErrTransient so
		// the handler returns 502 + upstream_error.
		return fmt.Errorf("%w: %s", ErrTransient, base)
	}
}

// tryPost calls POST {baseURL}{path} with the given body (or no
// body when body == nil) and returns the response on success or
// a sentinel error on non-200. Used as the building block by
// every write method below (V2 first, V1 second).
func (c *Client) tryPost(ctx context.Context, path string, body []byte) (*http.Response, error) {
	var r io.Reader
	if body != nil {
		r = bytes.NewReader(body)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+path, r)
	if err != nil {
		return nil, fmt.Errorf("supervisor: build %s request: %w", path, err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
		req.ContentLength = int64(len(body))
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("supervisor: %s: %w", path, err)
	}
	return resp, nil
}

// postV2V1 issues POST with V2-preferred/V1-fallback for endpoints
// with no request body (Uninstall, Start, Stop). Returns the typed
// error on non-200.
func (c *Client) postV2V1(ctx context.Context, slug, op string) error {
	v2 := "/apps/" + slug + "/" + op
	resp, err := c.tryPost(ctx, v2, nil)
	if err != nil {
		return err
	}
	if resp.StatusCode == http.StatusOK {
		drainBody(resp)
		resp.Body.Close()
		return nil
	}
	drainBody(resp)
	v2Code := resp.StatusCode
	resp.Body.Close()

	v1 := "/addons/" + slug + "/" + op
	resp2, err := c.tryPost(ctx, v1, nil)
	if err != nil {
		return classifyStatus(http.MethodPost, op, v2Code)
	}
	defer resp2.Body.Close()
	if resp2.StatusCode == http.StatusOK {
		drainBody(resp2)
		return nil
	}
	drainBody(resp2)
	return classifyStatus(http.MethodPost, op, resp2.StatusCode)
}

// postWithBodyV2V1 is the body-carrying variant (Options). On V2
// success returns nil; on V2 non-200 drains + falls back to V1;
// on V1 non-200 maps via classifyStatus.
func (c *Client) postWithBodyV2V1(ctx context.Context, slug, op string, body []byte) error {
	v2 := "/apps/" + slug + "/" + op
	resp, err := c.tryPost(ctx, v2, body)
	if err != nil {
		return err
	}
	if resp.StatusCode == http.StatusOK {
		drainBody(resp)
		resp.Body.Close()
		return nil
	}
	drainBody(resp)
	v2Code := resp.StatusCode
	resp.Body.Close()

	v1 := "/addons/" + slug + "/" + op
	resp2, err := c.tryPost(ctx, v1, body)
	if err != nil {
		return classifyStatus(http.MethodPost, op, v2Code)
	}
	defer resp2.Body.Close()
	if resp2.StatusCode == http.StatusOK {
		drainBody(resp2)
		return nil
	}
	drainBody(resp2)
	return classifyStatus(http.MethodPost, op, resp2.StatusCode)
}

// Install triggers Supervisor /store/apps/{slug}/install (note:
// /store/ prefix, NOT /apps/ — supervisor/api/store.py).
// Returns the job_id for polling via GetJobStatus. The request
// body is {"background":true} per Pitfall 1 (background:false
// blocks until install completes; the polling path is the
// correct one).
//
// On Supervisor 409 returns ErrAlreadyInstalled which the handler
// adopts as a fall-through to GET info per CONTEXT D-26.
func (c *Client) Install(ctx context.Context, slug string) (string, error) {
	body := []byte(`{"background":true}`)
	path := "/store/apps/" + slug + "/install"

	resp, err := c.tryPost(ctx, path, body)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusConflict {
		drainBody(resp)
		return "", fmt.Errorf("%w: supervisor: POST %s status 409", ErrAlreadyInstalled, path)
	}
	if resp.StatusCode != http.StatusOK {
		drainBody(resp)
		return "", classifyStatus(http.MethodPost, "install", resp.StatusCode)
	}

	// Supervisor envelope: {result: "ok", data: {job_id: "..."}}
	var env struct {
		Data struct {
			JobID string `json:"job_id"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&env); err != nil {
		return "", fmt.Errorf("supervisor: decode install envelope: %w", err)
	}
	return env.Data.JobID, nil
}

// Uninstall wraps Supervisor /apps/{slug}/uninstall (V2 preferred;
// /addons/{slug}/uninstall V1 fallback). Sync endpoint per
// supervisor/api/apps.py (CONTEXT D-19).
func (c *Client) Uninstall(ctx context.Context, slug string) error {
	return c.postV2V1(ctx, slug, "uninstall")
}

// Start wraps Supervisor /apps/{slug}/start (sync per D-19).
func (c *Client) Start(ctx context.Context, slug string) error {
	return c.postV2V1(ctx, slug, "start")
}

// Stop wraps Supervisor /apps/{slug}/stop (sync per D-19).
func (c *Client) Stop(ctx context.Context, slug string) error {
	return c.postV2V1(ctx, slug, "stop")
}

// Options applies a new options payload via Supervisor
// /apps/{slug}/options (sync per D-19). The body shape is the
// per-add-on options object the Provider computed (a JSON object
// whose keys match the add-on's schema).
func (c *Client) Options(ctx context.Context, slug string, body map[string]any) error {
	b, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("supervisor: marshal options body: %w", err)
	}
	return c.postWithBodyV2V1(ctx, slug, "options", b)
}

// ValidateOptions calls Supervisor /apps/{slug}/options/validate
// and decodes the typed diagnostic envelope ({message, valid,
// pwned}) per BRIDGE-08 + supervisor/api/apps.py.
func (c *Client) ValidateOptions(ctx context.Context, slug string, body map[string]any) (*OptionsValidateDiagnostic, error) {
	b, err := json.Marshal(body)
	if err != nil {
		return nil, fmt.Errorf("supervisor: marshal options/validate body: %w", err)
	}

	newReq := func(path string) (*http.Request, error) {
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+path, bytes.NewReader(b))
		if err != nil {
			return nil, err
		}
		req.Header.Set("Content-Type", "application/json")
		req.ContentLength = int64(len(b))
		return req, nil
	}

	// V2 first.
	v2 := "/apps/" + slug + "/options/validate"
	req, err := newReq(v2)
	if err != nil {
		return nil, fmt.Errorf("supervisor: build %s: %w", v2, err)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("supervisor: %s: %w", v2, err)
	}
	if resp.StatusCode == http.StatusOK {
		var diag OptionsValidateDiagnostic
		if err := json.NewDecoder(resp.Body).Decode(&diag); err != nil {
			resp.Body.Close()
			return nil, fmt.Errorf("supervisor: decode options/validate: %w", err)
		}
		resp.Body.Close()
		return &diag, nil
	}
	drainBody(resp)
	v2Code := resp.StatusCode
	resp.Body.Close()

	// V1 fallback.
	v1 := "/addons/" + slug + "/options/validate"
	req2, err := newReq(v1)
	if err != nil {
		return nil, classifyStatus(http.MethodPost, "options/validate", v2Code)
	}
	resp2, err := c.httpClient.Do(req2)
	if err != nil {
		return nil, classifyStatus(http.MethodPost, "options/validate", v2Code)
	}
	defer resp2.Body.Close()
	if resp2.StatusCode == http.StatusOK {
		var diag OptionsValidateDiagnostic
		if err := json.NewDecoder(resp.Body).Decode(&diag); err != nil {
			return nil, fmt.Errorf("supervisor: decode options/validate (v1): %w", err)
		}
		return &diag, nil
	}
	drainBody(resp2)
	return nil, classifyStatus(http.MethodPost, "options/validate", resp2.StatusCode)
}

// GetJobStatus polls Supervisor /jobs/{jobID}. The response is
// the BARE job dict {job_id, done, result} per
// supervisor/api/jobs.py:job_info — NOT wrapped in the standard
// {result, data} envelope (Pitfall/Assumption A3 in 12-CONTEXT).
// Decode directly into contract.JobStatus.
func (c *Client) GetJobStatus(ctx context.Context, jobID string) (*contract.JobStatus, error) {
	path := "/jobs/" + jobID
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+path, nil)
	if err != nil {
		return nil, fmt.Errorf("supervisor: build job request: %w", err)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("supervisor: %s: %w", path, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		drainBody(resp)
		return nil, classifyStatus(http.MethodGet, "job", resp.StatusCode)
	}

	var st contract.JobStatus
	if err := json.NewDecoder(resp.Body).Decode(&st); err != nil {
		return nil, fmt.Errorf("supervisor: decode job: %w", err)
	}
	return &st, nil
}

// MapError translates a sentinel error returned by any Client
// method into the (HTTP status, error_code) pair the Bridge
// handler writes to the wire (CONTEXT D-25 + BRIDGE-09).
//
// The mapping is centralized so future sentinels require a
// single switch update. The default branch is 502 +
// upstream_error (never a 5xx without the error_code envelope,
// per BRIDGE-09).
func MapError(err error) (int, string) {
	switch {
	case err == nil:
		return http.StatusOK, ""
	case errors.Is(err, ErrNotFound):
		return http.StatusNotFound, "not_found"
	case errors.Is(err, ErrAlreadyInstalled):
		return http.StatusConflict, "already_installed"
	case errors.Is(err, ErrCriticalAddon):
		return http.StatusForbidden, "critical_addon_protected"
	case errors.Is(err, ErrPreventedDestroy):
		return http.StatusForbidden, "prevented_destroy"
	case errors.Is(err, ErrLocked):
		return http.StatusLocked, "locked"
	case errors.Is(err, ErrTransient):
		return http.StatusBadGateway, "upstream_error"
	default:
		return http.StatusBadGateway, "upstream_error"
	}
}
