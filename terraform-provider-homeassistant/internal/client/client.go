// Package client wraps the Bridge HTTP API access in a Client struct
// that mirrors the Bridge's own supervisor.Client style (Phase 11+12;
// CF-16). The bearer token is injected via an http.RoundTripper (not
// a constructor closure) so the http.Client can be reused for
// concurrent /v1/version, /v1/addons, and /v1/info calls without
// leaking the token across goroutine boundaries. PITFALLS S-1
// invariants are honored verbatim: the token value never appears in
// any error message, log record, or HTTP body.
//
// RoundTrip pattern is taken from Bridge's
// terraform-bridge/internal/supervisor/client.go:84-91 — every call
// to RoundTrip injects the configured token on the cloned request
// before delegating to http.DefaultTransport. Phase 13's Client keeps
// the same shape rather than re-inventing it.
package client

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"

	"terraform-bridge/contract"
)

// ErrAddonNotFound is returned by GetAddonInfo when Bridge returns
// HTTP 404 + {error_code: "not_found"}. This is the Provider's mirror
// of the Bridge's supervisor.ErrNotFound sentinel — Resource.Read
// compares via errors.Is so 404 → empty state (CF-06 idempotency).
var ErrAddonNotFound = errors.New("client: addon not found")

// httpClientTimeout bounds every outbound request at the transport
// layer (independent of any per-call context timeout the caller
// passes). 5s matches Phase 11's supervisor.Client ceiling; the
// per-operation timeouts from terraform-plugin-framework-timeouts in
// Plan 02 add tighter caller-side budgets where appropriate.
const httpClientTimeout = 5 * time.Second

// Client wraps http.Client with bearer-token injection. The zero
// value is not usable; construct via NewClient.
type Client struct {
	httpClient  *http.Client
	baseURL     string
	bearerToken string
}

// NewClient returns a Client whose base URL is the user's
// `endpoint` Provider argument and whose bearer token is the user's
// `bearer_token` Provider argument. Both arguments are validated:
// the base URL must parse as a URL with an http or https scheme; the
// token must be non-empty (the empty token check happens in
// RoundTrip so a future test helper can supply a deliberately empty
// token without failing NewClient).
//
// The returned Client owns a fresh http.Client with a 5-second
// Timeout and the bearer-injecting RoundTripper wired up — callers
// do not need to install anything else.
func NewClient(baseURL, bearerToken string) (*Client, error) {
	parsed, err := url.Parse(baseURL)
	if err != nil {
		return nil, fmt.Errorf("client: parse base URL: %w", err)
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return nil, fmt.Errorf("client: base URL must use http or https scheme, got %q", parsed.Scheme)
	}
	if parsed.Host == "" {
		return nil, fmt.Errorf("client: base URL must include a host")
	}
	if bearerToken == "" {
		return nil, fmt.Errorf("client: bearer_token is empty (must be supplied in the Provider configuration)")
	}

	transport := &tokenInjectingTransport{token: bearerToken}
	return &Client{
		httpClient: &http.Client{
			Timeout:   httpClientTimeout,
			Transport: transport,
		},
		baseURL:     baseURL,
		bearerToken: bearerToken,
	}, nil
}

// WithBaseURLForTest returns a copy of the Client whose baseURL is
// overridden. Used by package-internal tests that drive the Client
// against httptest.NewServer without exercising the production URL
// parser. Mirrors supervisor.Client.WithBaseURLForTest at
// terraform-bridge/internal/supervisor/testing.go.
func (c *Client) WithBaseURLForTest(baseURL string) *Client {
	out := *c
	out.baseURL = baseURL
	// Re-instantiate the http.Client so the same Transport (with the
	// same bearer token) points at the new base URL. The
	// tokenInjectingTransport is shared because its token is
	// unchanged.
	out.httpClient = &http.Client{
		Timeout:   httpClientTimeout,
		Transport: c.httpClient.Transport,
	}
	return &out
}

// Timeout returns the Client's http.Client.Timeout. Exposed so
// tests can assert the configured ceiling without coupling to the
// internal http.Client field shape.
func (c *Client) Timeout() time.Duration {
	return c.httpClient.Timeout
}

// GetVersion calls GET /v1/version and returns the decoded handshake.
// On non-200 the method returns a *BridgeError carrying the status
// and the contract.ErrorResponse body. Network failures and decode
// failures return plain errors with wrapped context — neither carries
// the bearer token (PITFALLS S-1).
func (c *Client) GetVersion(ctx context.Context) (*contract.VersionHandshake, error) {
	resp, err := c.doRequest(ctx, http.MethodGet, "/v1/version", nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, c.decodeError(http.MethodGet, "/v1/version", resp)
	}

	var hs contract.VersionHandshake
	if err := json.NewDecoder(resp.Body).Decode(&hs); err != nil {
		return nil, fmt.Errorf("client: decode version handshake: %w", err)
	}
	return &hs, nil
}

// GetAddonInfo calls GET /v1/addons/{slug}/info and returns the
// decoded add-on info. On 404 the method returns ErrAddonNotFound
// (a sentinel suitable for errors.Is comparisons inside Resource.Read
// per CF-06). On any other non-200 the method returns a *BridgeError.
// On 200 + successful decode, the returned *contract.AddOnInfo is
// passed back verbatim (no normalization; Bridge already returns the
// same shape Supervisor does, including the `started` field).
func (c *Client) GetAddonInfo(ctx context.Context, slug string) (*contract.AddOnInfo, error) {
	if slug == "" {
		return nil, fmt.Errorf("client: GetAddonInfo requires non-empty slug")
	}
	path := "/v1/addons/" + slug + "/info"
	resp, err := c.doRequest(ctx, http.MethodGet, path, nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		// Translate 404 to the production sentinel. We still drain
		// the body (Phase 11 Rule-1 fix) so the connection can be
		// reused; BridgeError is not constructed for this branch
		// because 404 → ErrAddonNotFound is a deliberate
		// translation, not a Bridge-supplied error_code.
		drainBody(resp)
		return nil, ErrAddonNotFound
	}
	if resp.StatusCode != http.StatusOK {
		return nil, c.decodeError(http.MethodGet, path, resp)
	}

	var info contract.AddOnInfo
	if err := json.NewDecoder(resp.Body).Decode(&info); err != nil {
		return nil, fmt.Errorf("client: decode addon info: %w", err)
	}
	return &info, nil
}

// GetAddonList calls GET /v1/addons and returns the decoded list.
// Non-200 responses surface as *BridgeError; network / decode
// failures surface as wrapped errors (no bearer token in any message).
func (c *Client) GetAddonList(ctx context.Context) ([]contract.AddOnInfo, error) {
	resp, err := c.doRequest(ctx, http.MethodGet, "/v1/addons", nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, c.decodeError(http.MethodGet, "/v1/addons", resp)
	}

	var items []contract.AddOnInfo
	if err := json.NewDecoder(resp.Body).Decode(&items); err != nil {
		return nil, fmt.Errorf("client: decode addon list: %w", err)
	}
	return items, nil
}

// GetInfo calls GET /v1/info (BRIDGE-10, no auth) and returns the
// decoded BridgeInfo. The endpoint is unauthenticated at the Bridge
// layer but the Client still injects the bearer header (Bridge
// accepts both — the auth middleware is a passthrough when no token
// is required). Same error semantics as GetVersion.
func (c *Client) GetInfo(ctx context.Context) (*contract.BridgeInfo, error) {
	resp, err := c.doRequest(ctx, http.MethodGet, "/v1/info", nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, c.decodeError(http.MethodGet, "/v1/info", resp)
	}

	var info contract.BridgeInfo
	if err := json.NewDecoder(resp.Body).Decode(&info); err != nil {
		return nil, fmt.Errorf("client: decode info: %w", err)
	}
	return &info, nil
}

// doRequest is the internal helper that builds the request, executes
// it, and returns the response. The caller is responsible for
// draining / decoding / closing the body per the Phase 11 Rule-1
// discipline (status check FIRST, drain AFTER, decode LAST).
func (c *Client) doRequest(ctx context.Context, method, path string, body io.Reader) (*http.Response, error) {
	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, body)
	if err != nil {
		return nil, fmt.Errorf("client: build %s %s: %w", method, path, err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("client: %s %s: %w", method, path, err)
	}
	return resp, nil
}

// decodeError reads the response body so the decoded
// contract.ErrorResponse is available, then drains so the
// underlying TCP connection can be reused (Phase 11 Rule-1:
// drain AFTER the read, so the read sees the full body).
//
// The returned *BridgeError always carries the HTTP status code;
// the contract.ErrorResponse is included when the body parses
// cleanly, otherwise its ErrorCode is the empty string and MapError
// falls back to the unknown_code branch.
//
// The body's Error() method is constructed so that the bearer token
// substring NEVER appears (PITFALLS S-1 + T-13-04). The shape is
// `bridge: <method> <path> status <code>: error_code=<code> message=<message>`.
//
// Callers must still close resp.Body — decodeError does not defer
// Close so the helper can return the response's status code without
// touching the Body again.
func (c *Client) decodeError(method, path string, resp *http.Response) error {
	body, _ := io.ReadAll(resp.Body)
	drainBody(resp)

	var errResp contract.ErrorResponse
	_ = json.Unmarshal(body, &errResp) // best-effort; empty struct on parse failure

	be := &BridgeError{
		StatusCode: resp.StatusCode,
		Err:        errResp,
		Method:     method,
		Path:       path,
	}
	return be
}

// drainBody discards the response body so the underlying TCP
// connection can be reused. Mirrors the supervisor.Client.drainBody
// helper at terraform-bridge/internal/supervisor/client.go:374-379;
// drain AFTER the StatusCode check, NOT before (Phase 11 Rule-1 fix).
func drainBody(resp *http.Response) {
	if resp == nil || resp.Body == nil {
		return
	}
	_, _ = io.Copy(io.Discard, resp.Body)
}

// BridgeError wraps a non-200 response from the Bridge. StatusCode
// is the HTTP status; Err is the decoded contract.ErrorResponse (its
// ErrorCode drives MapError's switch); Method and Path are the
// request shape, used by Error() to construct a token-free
// diagnostic message.
//
// BridgeError implements the error interface so it composes with
// errors.Is / errors.As / fmt.Errorf("%w") without surprises. The
// Error() string never contains the bearer token (PITFALLS S-1 +
// T-13-04).
type BridgeError struct {
	StatusCode int
	Err        contract.ErrorResponse
	Method     string
	Path       string
}

// Error returns the canonical token-free error string. The format
// matches the Bridge's own supervisor.Client.classifyStatus style:
// `<method> <path> status <code>: error_code=<code> message=<message>`.
// When the body did not parse, `error_code=` and `message=` are
// empty.
func (e *BridgeError) Error() string {
	return fmt.Sprintf("bridge: %s %s status %d: error_code=%s message=%s",
		e.Method, e.Path, e.StatusCode, e.Err.ErrorCode, e.Err.Message)
}

// tokenInjectingTransport wraps http.RoundTripper and adds the
// Bearer auth header on every request. Mirrors the
// tokenInjectingTransport in
// terraform-bridge/internal/supervisor/client.go:339-355 — the
// token is held in a struct field rather than a function pointer
// because the Provider's token comes from user configuration
// (bearer_token argument), not from the SUPERVISOR_TOKEN env var.
type tokenInjectingTransport struct {
	token string
}

// RoundTrip satisfies http.RoundTripper. It clones the inbound
// request (so the caller's headers are untouched), sets the
// Authorization: Bearer <token> header, and delegates to
// http.DefaultTransport.
//
// If the token is empty (only possible via a misconfigured Provider
// or a deliberate test setup), RoundTrip returns an error rather
// than sending an unauthenticated request. This protects against
// the failure mode where the bearer_token argument is forgotten in
// the user's *.tf.
func (t *tokenInjectingTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	if t.token == "" {
		return nil, errors.New("client: bearer_token is empty")
	}
	// Clone to avoid mutating the caller's headers (the framework
	// shares *http.Request across retry paths).
	clone := req.Clone(req.Context())
	clone.Header.Set("Authorization", "Bearer "+t.token)
	return http.DefaultTransport.RoundTrip(clone)
}
