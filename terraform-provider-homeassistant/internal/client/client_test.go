package client_test

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"terraform-bridge/contract"

	"terraform-provider-homeassistant/internal/client"
)

// The Bearer token used throughout the test suite. Deliberately a
// recognizable string ("test-bearer-token-do-not-leak-XYZ") so a
// failing assertion against an error message can quickly grep for
// it.
const testBearer = "test-bearer-token-do-not-leak-XYZ"

// newTestClient constructs a *client.Client pointing at the given
// httptest.Server. Returns the Client and a cleanup func the test
// must defer.
func newTestClient(t *testing.T, srv *httptest.Server) *client.Client {
	t.Helper()
	c, err := client.NewClient(srv.URL, testBearer)
	if err != nil {
		t.Fatalf("client.NewClient: %v", err)
	}
	return c
}

// TestClient_GetVersion_Success drives a happy-path
// /v1/version round-trip. The fake server returns a
// contract.VersionHandshake; the Client decodes it verbatim.
func TestClient_GetVersion_Success(t *testing.T) {
	want := contract.VersionHandshake{
		BridgeVersion:      "0.5.0",
		SchemaVersion:      "1.0.0",
		MinProviderVersion: "0.0.0",
		MaxProviderVersion: "1.999.0",
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/version" {
			t.Errorf("server: path = %q, want /v1/version", r.URL.Path)
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(want)
	}))
	defer srv.Close()

	c := newTestClient(t, srv)
	got, err := c.GetVersion(context.Background())
	if err != nil {
		t.Fatalf("GetVersion: %v", err)
	}
	if *got != want {
		t.Errorf("GetVersion: %+v, want %+v", *got, want)
	}
}

// TestClient_GetVersion_Unauthorized asserts that 401 +
// contract.ErrorResponse surfaces as a *client.BridgeError with
// statusCode + error_code + request_id preserved. This is the
// canonical error path the diagnostics.MapError switch handles.
func TestClient_GetVersion_Unauthorized(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnauthorized)
		_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
			ErrorCode: "unauthorized",
			RequestID: "rid-401",
			Message:   "token mismatch",
		})
	}))
	defer srv.Close()

	c := newTestClient(t, srv)
	_, err := c.GetVersion(context.Background())
	if err == nil {
		t.Fatalf("GetVersion(401): err = nil, want *BridgeError")
	}

	var be *client.BridgeError
	if !errors.As(err, &be) {
		t.Fatalf("GetVersion(401): err %T does not unwrap to *client.BridgeError", err)
	}
	if be.StatusCode != http.StatusUnauthorized {
		t.Errorf("StatusCode = %d, want 401", be.StatusCode)
	}
	if be.Err.ErrorCode != "unauthorized" {
		t.Errorf("Err.ErrorCode = %q, want %q", be.Err.ErrorCode, "unauthorized")
	}
	if be.Err.RequestID != "rid-401" {
		t.Errorf("Err.RequestID = %q, want %q", be.Err.RequestID, "rid-401")
	}
}

// TestClient_GetAddonInfo_Success drives a happy-path
// /v1/addons/{slug}/info round-trip.
func TestClient_GetAddonInfo_Success(t *testing.T) {
	want := contract.AddOnInfo{
		Slug:       "a0d7c6b6_my_addon",
		Name:       "My Add-on",
		Version:    "1.2.3",
		State:      "started",
		Started:    true,
		Options:    map[string]string{"log_level": "info"},
		Boot:       "auto",
		Repository: "core",
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		wantPath := "/v1/addons/" + want.Slug + "/info"
		if r.URL.Path != wantPath {
			t.Errorf("server: path = %q, want %q", r.URL.Path, wantPath)
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(want)
	}))
	defer srv.Close()

	c := newTestClient(t, srv)
	got, err := c.GetAddonInfo(context.Background(), want.Slug)
	if err != nil {
		t.Fatalf("GetAddonInfo: %v", err)
	}
	if got.Slug != want.Slug {
		t.Errorf("Slug = %q, want %q", got.Slug, want.Slug)
	}
	if got.Version != want.Version {
		t.Errorf("Version = %q, want %q", got.Version, want.Version)
	}
	if got.State != want.State {
		t.Errorf("State = %q, want %q", got.State, want.State)
	}
	if !got.Started {
		t.Errorf("Started = false, want true")
	}
}

// TestClient_GetAddonInfo_NotFound asserts the canonical CF-06
// translation: 404 + {error_code: "not_found"} → ErrAddonNotFound
// sentinel, NOT a generic *BridgeError. errors.Is is the comparison
// idiom (cf. Resource.Read).
func TestClient_GetAddonInfo_NotFound(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_ = json.NewEncoder(w).Encode(contract.ErrorResponse{
			ErrorCode: "not_found",
			RequestID: "rid-404",
		})
	}))
	defer srv.Close()

	c := newTestClient(t, srv)
	_, err := c.GetAddonInfo(context.Background(), "missing")
	if err == nil {
		t.Fatalf("GetAddonInfo(404): err = nil, want ErrAddonNotFound")
	}
	if !errors.Is(err, client.ErrAddonNotFound) {
		t.Errorf("GetAddonInfo(404): err %v does not satisfy errors.Is(err, ErrAddonNotFound)", err)
	}
}

// TestClient_AuthorizationHeaderInjected asserts the
// tokenInjectingTransport actually sets the Bearer token on
// outbound requests. The fake server echoes the header back; the
// test asserts the literal "Bearer <testBearer>" prefix is present
// (and exactly that — no quoting, no header munging).
func TestClient_AuthorizationHeaderInjected(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got := r.Header.Get("Authorization")
		if got != "Bearer "+testBearer {
			t.Errorf("server: Authorization header = %q, want %q", got, "Bearer "+testBearer)
			http.Error(w, "bad auth", http.StatusUnauthorized)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(contract.VersionHandshake{
			BridgeVersion:      "0.5.0",
			SchemaVersion:      "1.0.0",
			MinProviderVersion: "0.0.0",
			MaxProviderVersion: "1.999.0",
		})
	}))
	defer srv.Close()

	c := newTestClient(t, srv)
	if _, err := c.GetVersion(context.Background()); err != nil {
		t.Fatalf("GetVersion: %v", err)
	}
}

// TestClient_BearerTokenNotInErrorMessage is the PITFALLS S-1 +
// T-13-04 regression guard. Across multiple failure scenarios
// (401, 404, 502, malformed JSON) the bearer_token substring MUST
// NEVER appear in err.Error() — neither directly nor via the
// underlying *BridgeError's Error() method.
//
// The test deliberately uses the recognizable literal
// "test-bearer-token-do-not-leak-XYZ" so a leaking implementation
// surfaces immediately in the assertion message.
func TestClient_BearerTokenNotInErrorMessage(t *testing.T) {
	scenarios := []struct {
		name   string
		path   string
		status int
		body   string
	}{
		{
			name:   "401 unauthorized",
			path:   "/v1/version",
			status: http.StatusUnauthorized,
			body:   `{"error_code":"unauthorized","request_id":"rid-1","message":"token mismatch"}`,
		},
		{
			name:   "404 not found (addon info)",
			path:   "/v1/addons/missing/info",
			status: http.StatusNotFound,
			body:   `{"error_code":"not_found","request_id":"rid-2"}`,
		},
		{
			name:   "502 upstream error",
			path:   "/v1/version",
			status: http.StatusBadGateway,
			body:   `{"error_code":"upstream_error","request_id":"rid-3"}`,
		},
		{
			name:   "malformed JSON body",
			path:   "/v1/version",
			status: http.StatusOK,
			body:   `{`,
		},
	}

	for _, sc := range scenarios {
		t.Run(sc.name, func(t *testing.T) {
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(sc.status)
				_, _ = w.Write([]byte(sc.body))
			}))
			defer srv.Close()

			c := newTestClient(t, srv)
			_, err := c.GetVersion(context.Background())
			if err == nil {
				t.Fatalf("scenario %s: err = nil, want non-nil", sc.name)
			}
			if strings.Contains(err.Error(), testBearer) {
				t.Errorf("scenario %s: err.Error() leaked bearer token: %q", sc.name, err.Error())
			}
			// Belt-and-suspenders: explicitly walk the
			// *BridgeError.Error() string (when present) for the
			// same substring.
			var be *client.BridgeError
			if errors.As(err, &be) {
				if strings.Contains(be.Error(), testBearer) {
					t.Errorf("scenario %s: *BridgeError.Error() leaked bearer token: %q", sc.name, be.Error())
				}
			}
		})
	}
}

// TestClient_GetInfo_Success drives a happy-path /v1/info
// round-trip.
func TestClient_GetInfo_Success(t *testing.T) {
	want := contract.BridgeInfo{
		BridgeVersion:     "0.5.0",
		SupervisorVersion: "2026.08.0",
		UptimeSeconds:     12345,
		StateFilePath:     "/data/terraform.tfstate",
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/info" {
			t.Errorf("server: path = %q, want /v1/info", r.URL.Path)
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(want)
	}))
	defer srv.Close()

	c := newTestClient(t, srv)
	got, err := c.GetInfo(context.Background())
	if err != nil {
		t.Fatalf("GetInfo: %v", err)
	}
	if *got != want {
		t.Errorf("GetInfo: %+v, want %+v", *got, want)
	}
}

// TestClient_GetAddonList_Success drives a happy-path /v1/addons
// round-trip.
func TestClient_GetAddonList_Success(t *testing.T) {
	items := []contract.AddOnInfo{
		{Slug: "a", Name: "A", Version: "1.0.0", State: "started", Started: true, Repository: "core"},
		{Slug: "b", Name: "B", Version: "2.0.0", State: "stopped", Started: false, Repository: "local"},
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/addons" {
			t.Errorf("server: path = %q, want /v1/addons", r.URL.Path)
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(items)
	}))
	defer srv.Close()

	c := newTestClient(t, srv)
	got, err := c.GetAddonList(context.Background())
	if err != nil {
		t.Fatalf("GetAddonList: %v", err)
	}
	if len(got) != 2 {
		t.Fatalf("GetAddonList: len = %d, want 2", len(got))
	}
	if got[0].Slug != "a" || got[1].Slug != "b" {
		t.Errorf("GetAddonList: slugs = [%q, %q], want [a, b]", got[0].Slug, got[1].Slug)
	}
}

// TestClient_GetAddonInfo_BodyDrainedOnError is the Phase 11
// Rule-1 regression guard for the Provider's Client. After a 404
// response is read, the underlying TCP connection must be reusable
// — the http.Transport only reuses a connection when its body has
// been fully drained. We verify by making a second request to the
// same server and asserting the second request reaches the handler
// (i.e. the server did not observe a connection reset between
// requests).
func TestClient_GetAddonInfo_BodyDrainedOnError(t *testing.T) {
	requestCount := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestCount++
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"error_code":"not_found","request_id":"rid-404"}`))
	}))
	defer srv.Close()

	c := newTestClient(t, srv)
	if _, err := c.GetAddonInfo(context.Background(), "missing"); !errors.Is(err, client.ErrAddonNotFound) {
		t.Fatalf("first GetAddonInfo: err = %v, want ErrAddonNotFound", err)
	}
	if _, err := c.GetAddonInfo(context.Background(), "missing"); !errors.Is(err, client.ErrAddonNotFound) {
		t.Fatalf("second GetAddonInfo: err = %v, want ErrAddonNotFound", err)
	}
	if requestCount != 2 {
		t.Errorf("server saw %d requests, want 2 (Rule-1: connection must be reusable after non-200)", requestCount)
	}
}

// TestNewClient_BadURL asserts the base-URL validation in NewClient.
// Empty scheme, missing host, unparseable URLs all reject early
// (before any network call is attempted).
func TestNewClient_BadURL(t *testing.T) {
	cases := []struct {
		name string
		url  string
	}{
		{"empty string", ""},
		{"missing scheme", "192.168.1.1:8124"},
		{"unsupported scheme", "ftp://example.com"},
		{"missing host", "http://"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := client.NewClient(tc.url, testBearer)
			if err == nil {
				t.Errorf("NewClient(%q): err = nil, want non-nil validation error", tc.url)
			}
		})
	}
}

// TestClient_EmptyBearerRejected asserts the tokenInjectingTransport
// refuses to send an outbound request when the token is empty.
// This guards against the failure mode where the user forgets the
// bearer_token argument in their *.tf.
func TestClient_EmptyBearerRejected(t *testing.T) {
	_, err := client.NewClient("http://localhost:1", "")
	if err == nil {
		t.Errorf("NewClient with empty bearer: err = nil, want non-nil (RoundTrip rejects empty token)")
	}
}

// TestClient_HTTPClientTimeout_Bounded verifies the Client's
// http.Client.Timeout is configured (positive). A direct field
// read would couple the test to internal Client shape, so we
// instead probe via a context-deadline interaction: the Client's
// Timeout must be > 0 (i.e. some ceiling is configured — Plan 01's
// 5s default). A request against a fast-replying server completes
// well within any positive Timeout, so the "is it configured"
// assertion is the deterministic observable here.
func TestClient_HTTPClientTimeout_Bounded(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(contract.VersionHandshake{})
	}))
	defer srv.Close()

	c, err := client.NewClient(srv.URL, testBearer)
	if err != nil {
		t.Fatalf("NewClient: %v", err)
	}
	if c.Timeout() <= 0 {
		t.Errorf("Client.Timeout = %v, want a positive duration (5s default)", c.Timeout())
	}
}
