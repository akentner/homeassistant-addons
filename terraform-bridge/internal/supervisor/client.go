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
