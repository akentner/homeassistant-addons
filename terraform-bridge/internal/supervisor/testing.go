// testing.go exposes test-only hooks for the supervisor package. These
// methods are exported (capitalised) so handler tests in package
// handlers can stub out the tokenFn and baseURL without copying the
// Client struct shape. The file is intentionally NOT named _test.go:
// Go's test build only compiles _test.go files within the SAME
// package, and handler tests live in package handlers, not package
// supervisor. The methods are unexported-helper-style (named
// "ForTest") so callers don't confuse them for production APIs.
package supervisor

// TokenFnForTest returns the Clients tokenFn for handler-level tests.
func (c *Client) TokenFnForTest() func() string { return c.tokenFn }

// WithBaseURLForTest returns a copy of the Client whose baseURL is
// overridden. Used by handler tests that drive the Client against an
// httptest.NewServer.
func (c *Client) WithBaseURLForTest(baseURL string) *Client {
	out := *c
	out.baseURL = baseURL
	return &out
}
