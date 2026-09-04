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
	"bytes"
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

// ErrAlreadyInstalled is returned by PostAddonInstall when Bridge
// returns HTTP 409 + {error_code: "already_installed"}. The Create
// handler compares via errors.Is so a 409 falls through to the
// adoption path (re-fetch via GetAddonInfo) per CF-07. The Create
// handler's D-04 GET-first adoption preemptively avoids 409 in the
// common case; this sentinel exists for the concurrent-race fallback
// where two Providers race to install the same slug.
var ErrAlreadyInstalled = errors.New("client: addon already installed")

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

// PostAuthNonce calls POST /v1/auth/nonce and returns the freshly
// minted NonceResponse. The nonce is a single-use, 60s-TTL secret
// (Phase 12 D-05..D-08); the Provider never persists or caches it
// (every Delete re-fetches). PITFALLS S-1 + T-13-10: the nonce
// value never enters any log path; it only flows through the
// X-Force-Destroy header on the immediate next destructive call.
func (c *Client) PostAuthNonce(ctx context.Context) (*contract.NonceResponse, error) {
	const path = "/v1/auth/nonce"
	resp, err := c.doRequest(ctx, http.MethodPost, path, nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, c.decodeError(http.MethodPost, path, resp)
	}

	var nonce contract.NonceResponse
	if err := json.NewDecoder(resp.Body).Decode(&nonce); err != nil {
		return nil, fmt.Errorf("client: decode nonce: %w", err)
	}
	return &nonce, nil
}

// PostAddonInstall calls POST /v1/addons/{slug}/install. The
// request body is empty — the Bridge drives the install lifecycle
// (Supervisor /store/apps/{slug}/install with background:true +
// 1s polling per Phase 12 D-17). The Provider does not poll; the
// Bridge's response on 200 carries the post-install AddOnInfo
// payload verbatim.
//
// On 409 + {error_code: "already_installed"} the method returns
// an InstallAlreadyInstalledError (CF-07 adoption signal). The
// error BOTH wraps ErrAlreadyInstalled (so callers can use
// errors.Is(err, ErrAlreadyInstalled)) AND carries the decoded
// *BridgeError (so callers can use errors.As to read the
// error_code / request_id). On any other non-200 the method
// returns a *BridgeError.
func (c *Client) PostAddonInstall(ctx context.Context, slug string) error {
	if slug == "" {
		return fmt.Errorf("client: PostAddonInstall requires non-empty slug")
	}
	path := "/v1/addons/" + slug + "/install"
	resp, err := c.doRequest(ctx, http.MethodPost, path, nil)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusConflict {
		body, _ := io.ReadAll(resp.Body)
		var errResp contract.ErrorResponse
		if json.Unmarshal(body, &errResp) == nil && errResp.ErrorCode == "already_installed" {
			return &InstallAlreadyInstalledError{
				Path:   path,
				Bridge: &BridgeError{StatusCode: resp.StatusCode, Err: errResp, Method: http.MethodPost, Path: path},
			}
		}
		// 409 with a different error_code is a real error, not an
		// adoption signal — fall through to parseErrorResponse.
		return c.parseErrorResponse(http.MethodPost, path, resp, body)
	}
	if resp.StatusCode != http.StatusOK {
		return c.decodeError(http.MethodPost, path, resp)
	}
	drainBody(resp)
	return nil
}

// InstallAlreadyInstalledError is the structured error returned
// by PostAddonInstall on 409 + already_installed. The error wraps
// ErrAlreadyInstalled (so errors.Is works for the adoption
// sentinel) AND carries the decoded *BridgeError so callers can
// inspect the request_id for diagnostics. The Error() string
// never contains the bearer token (PITFALLS S-1).
type InstallAlreadyInstalledError struct {
	Path   string
	Bridge *BridgeError
}

func (e *InstallAlreadyInstalledError) Error() string {
	return fmt.Sprintf("bridge: POST %s status 409: error_code=already_installed (adoption signal): %s", e.Path, ErrAlreadyInstalled.Error())
}

// Is satisfies errors.Is for the sentinel match.
func (e *InstallAlreadyInstalledError) Is(target error) bool {
	return target == ErrAlreadyInstalled
}

// PostAddonStart calls POST /v1/addons/{slug}/start. Start is NOT
// destructive (Phase 12 D-10) so no critical_addons check and no
// X-Force-Destroy nonce are required by the Bridge. The Bridge
// re-fetches the AddOnInfo and returns 200 + the payload; the
// Provider ignores the response body (state is refreshed by the
// framework's post-operation Read).
func (c *Client) PostAddonStart(ctx context.Context, slug string) error {
	return c.postAddonNoBody(ctx, slug, "start")
}

// PostAddonStop calls POST /v1/addons/{slug}/stop. Symmetric to
// PostAddonStart (Phase 12 D-19: no nonce, sync Supervisor call).
func (c *Client) PostAddonStop(ctx context.Context, slug string) error {
	return c.postAddonNoBody(ctx, slug, "stop")
}

// postAddonNoBody is the shared body-less POST helper for start + stop
// (and any future symmetric write endpoints). On 200 returns nil;
// on non-200 returns *BridgeError.
func (c *Client) postAddonNoBody(ctx context.Context, slug, op string) error {
	if slug == "" {
		return fmt.Errorf("client: PostAddon%s requires non-empty slug", op)
	}
	path := "/v1/addons/" + slug + "/" + op
	resp, err := c.doRequest(ctx, http.MethodPost, path, nil)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return c.decodeError(http.MethodPost, path, resp)
	}
	drainBody(resp)
	return nil
}

// PostAddonOptions calls POST /v1/addons/{slug}/options with the
// given options body. The body is marshaled as JSON; nested maps /
// arrays / scalars flow through verbatim (Phase 12 BRIDGE-08
// re-validates against Supervisor's apps.options schema on the
// Bridge side). The Provider sends the user's *.tf options body
// verbatim per CF-08 + PROV-06.
//
// Returns the decoded response body as a map[string]any so the
// caller can inspect top-level fields like `pwned` (CF-08 +
// PROV-06 + D-09: the Bridge may surface a `pwned: true` field
// in the apply response per Phase 14 verification; until the
// typed OptionsValidateDiagnostic envelope is wired end-to-end
// the Provider treats any top-level `pwned` field as a Warning).
// On non-200 returns *BridgeError.
func (c *Client) PostAddonOptions(ctx context.Context, slug string, body map[string]any) (map[string]any, error) {
	if slug == "" {
		return nil, fmt.Errorf("client: PostAddonOptions requires non-empty slug")
	}
	bodyBytes, err := json.Marshal(body)
	if err != nil {
		return nil, fmt.Errorf("client: marshal options body: %w", err)
	}
	path := "/v1/addons/" + slug + "/options"
	resp, err := c.doRequest(ctx, http.MethodPost, path, bytes.NewReader(bodyBytes))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, c.decodeError(http.MethodPost, path, resp)
	}
	// Decode the response body so the caller can inspect
	// top-level fields (notably `pwned`). Empty body is valid
	// (the Bridge's current 200 response is the AddOnInfo
	// payload, which has no top-level `pwned` — Phase 13
	// surfaces no Warning; Phase 14 wires the typed envelope).
	body2, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("client: read options response body: %w", err)
	}
	if len(body2) == 0 {
		return map[string]any{}, nil
	}
	var decoded map[string]any
	if err := json.Unmarshal(body2, &decoded); err != nil {
		// Body present but not JSON: surface as decode error so
		// the resource handler can map it (rare; usually means
		// the Bridge changed shape).
		return nil, fmt.Errorf("client: decode options response body: %w", err)
	}
	return decoded, nil
}

// PostAddonUninstall calls POST /v1/addons/{slug}/uninstall with the
// supplied nonce passed via the X-Force-Destroy header. The nonce is
// the Bridge's anti-CSRF guard for destructive operations (LIFE-03 +
// Phase 12 D-05..D-08); it MUST be fresh (60s TTL) and presented as
// the only header (no Bearer conflict — Bearer is on Authorization).
//
// The plaintext nonce NEVER enters any log path (PITFALLS S-1 +
// T-13-10). The Provider passes it through the request header
// directly; the http.Client.Transport machinery does not log it.
//
// On 204 No Content returns nil (CF-09 success). On 404 returns
// nil (CF-06 idempotency — Delete on a missing add-on is a no-op).
// On other non-200 returns *BridgeError. The non-200 path is where
// MapError surfaces `nonce_expired` / `nonce_used` as typed Error
// diagnostics, prompting the Resource.Delete handler to retry once
// with a fresh nonce (CF-09 + D-07).
func (c *Client) PostAddonUninstall(ctx context.Context, slug, nonce string) error {
	if slug == "" {
		return fmt.Errorf("client: PostAddonUninstall requires non-empty slug")
	}
	if nonce == "" {
		return fmt.Errorf("client: PostAddonUninstall requires non-empty nonce")
	}
	path := "/v1/addons/" + slug + "/uninstall"
	resp, err := c.doRequestWithHeader(ctx, http.MethodPost, path, nil, map[string]string{
		"X-Force-Destroy": nonce,
	})
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNoContent {
		return nil
	}
	if resp.StatusCode == http.StatusNotFound {
		// CF-06 idempotency: Delete on missing add-on is a no-op.
		drainBody(resp)
		return nil
	}
	return c.decodeError(http.MethodPost, path, resp)
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

// doRequestWithHeader is the doRequest variant for endpoints that
// require extra headers (Plan 02: X-Force-Destroy on
// /v1/addons/{slug}/uninstall). The headers map is shallow — the
// caller passes one entry per custom header; Content-Type /
// Authorization are NOT in this map (Content-Type is set by
// doRequest based on body presence; Authorization is injected by
// the tokenInjectingTransport on every outbound request).
func (c *Client) doRequestWithHeader(ctx context.Context, method, path string, body io.Reader, headers map[string]string) (*http.Response, error) {
	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, body)
	if err != nil {
		return nil, fmt.Errorf("client: build %s %s: %w", method, path, err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	for k, v := range headers {
		req.Header.Set(k, v)
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

// parseErrorResponse is the variant of decodeError for callers that
// already read the body themselves (e.g. PostAddonInstall peeks at
// the 409 body to detect `already_installed`). The caller passes
// the already-read body bytes; the helper decodes the
// contract.ErrorResponse and constructs the *BridgeError.
//
// The body is NOT re-read — the caller's pre-read consumed it; the
// helper does not touch resp.Body (callers continue to own its
// lifecycle). Used by PostAddonInstall for the 409-not-already-installed
// branch where we have the body but no error_code match.
func (c *Client) parseErrorResponse(method, path string, resp *http.Response, body []byte) error {
	var errResp contract.ErrorResponse
	_ = json.Unmarshal(body, &errResp) // best-effort

	return &BridgeError{
		StatusCode: resp.StatusCode,
		Err:        errResp,
		Method:     method,
		Path:       path,
	}
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
