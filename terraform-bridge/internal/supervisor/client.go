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
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"
)

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
